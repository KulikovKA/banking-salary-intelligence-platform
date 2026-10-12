"""One resource owner, explicit operator manifests, no user permission cache."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.auth.api import AuthContext
from app.auth.limits import LoginLimiter
from app.auth.models import AuthSession, AuthUser
from app.auth.service import SESSION_IDLE_TTL
from app.comparison.service import ComparisonService
from app.config import Settings
from app.contracts.llm import LLMClient
from app.corpus.service import CorpusError, CorpusService, SnapshotManifest
from app.evidence.service import EvidenceService
from app.ingestion.gateway import FetchGateway
from app.ingestion.service import IngestionService
from app.llm.budget import PostgresTokenBudget
from app.llm.fake import FakeLLM
from app.llm.groq import GroqLLM
from app.search.service import SnapshotSearchService
from app.storage.local import LocalBlobStore

ManifestResolver = Callable[[UUID], SnapshotManifest]


class HttpLoginLimiter(LoginLimiter):
    """Reuse SNAP-15 counters with the API's explicit 429 semantics."""

    def check_and_record(self, account_key: str, ip_key: str, now: float | None = None) -> bool:
        if not super().check_and_record(account_key, ip_key, now):
            raise HTTPException(429, "RATE_LIMITED", headers={"Retry-After": "60"})
        return True


class FileManifestResolver:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def __call__(self, snapshot_id: UUID) -> SnapshotManifest:
        path = self.root / f"{snapshot_id}.json"
        if not path.is_file():
            raise HTTPException(404, "OBJECT_UNAVAILABLE")
        if path.is_symlink() or path.resolve().parent != self.root:
            raise CorpusError("MANIFEST_INVALID")
        if path.stat().st_size > 1_048_576:
            raise CorpusError("MANIFEST_INVALID")
        manifest = CorpusService.load_manifest(path)
        if manifest.snapshot_id != snapshot_id:
            raise CorpusError("SNAPSHOT_IDENTITY_MISMATCH")
        return manifest


class ProcessingAdmission(BaseModel):
    """Operator decision for an exact corpus; local file existence alone grants nothing."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    snapshot_id: UUID
    manifest_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    provider: str = Field(pattern="^groq$")
    model: str = Field(pattern=r"^openai/gpt-oss-120b$")
    decision: str = Field(pattern="^approved$")
    reviewer: str = Field(min_length=1, max_length=200)
    basis_reference: str = Field(min_length=1, max_length=2000)
    terms_processing_retention_reference: str = Field(min_length=1, max_length=2000)
    corpus_reuse_reference: str = Field(min_length=1, max_length=2000)
    expires_at: datetime


class Runtime:
    def __init__(
        self,
        settings: Settings,
        *,
        factory: sessionmaker[Session] | None = None,
        resolve_manifest: ManifestResolver | None = None,
        llm: LLMClient | None = None,
        admission_root: Path | None = None,
    ) -> None:
        self.settings = settings
        self.engine: Engine | None = None
        if factory is None:
            if settings.database_url:
                url = make_url(settings.database_url.get_secret_value())
                if url.get_backend_name() != "postgresql":
                    raise ValueError("API_POSTGRESQL_REQUIRED")
                self.engine = create_engine(
                    url,
                    pool_pre_ping=True,
                    pool_timeout=5,
                    connect_args={"connect_timeout": 5, "options": "-c statement_timeout=10000"},
                )
                factory = sessionmaker(self.engine, expire_on_commit=False)
            else:
                # Keep liveness and OpenAPI available; DB routes fail closed with 503.
                factory = sessionmaker(expire_on_commit=False)
        self.factory = factory
        self.auth = AuthContext(session_factory=factory, settings=settings)
        self.login_limiter = HttpLoginLimiter()
        self.read_limiter = LoginLimiter(account_limit=60, ip_limit=120)
        self.question_limiter = LoginLimiter(account_limit=10, ip_limit=30)
        store = LocalBlobStore(settings.storage_root, settings.source_max_bytes)
        ingestion = IngestionService(factory, settings, store, FetchGateway(settings, store))
        self.corpus = CorpusService(ingestion)
        self.evidence = EvidenceService(self.corpus)
        self.resolve_manifest = resolve_manifest or FileManifestResolver(
            Path(os.environ.get("SNAPSHOT_MANIFEST_ROOT", str(store.root / "manifests")))
        )
        self.admission_root = admission_root or Path(
            os.environ.get("PROVIDER_ADMISSION_ROOT", str(store.root / "processing-admissions"))
        )
        self.llm: LLMClient
        if llm is not None:
            if settings.app_env != "test" or not isinstance(llm, FakeLLM):
                raise ValueError("API_TEST_FAKE_OVERRIDE_ONLY")
            self.llm = llm
        elif settings.llm_mode == "fake":
            self.llm = FakeLLM()
        else:
            self.llm = GroqLLM(
                settings,
                PostgresTokenBudget(
                    factory,
                    daily_token_limit=settings.llm_daily_token_budget,
                    global_concurrency=settings.llm_global_concurrency,
                    user_concurrency=settings.llm_user_concurrency,
                ),
            )

    def check_identity(
        self, identity: tuple[AuthUser, AuthSession], *, admin: bool = False
    ) -> None:
        """Recheck session expiry/revocation/role across service and provider boundaries."""
        with self.factory.begin() as db:
            user = db.get(AuthUser, identity[0].id)
            session = db.get(AuthSession, identity[1].id)
            if (
                user is None
                or not user.active
                or session is None
                or session.user_id != user.id
                or session.revoked_at is not None
                or session.absolute_expires_at <= datetime.now(UTC)
                or session.last_seen_at + SESSION_IDLE_TTL <= datetime.now(UTC)
            ):
                raise HTTPException(401, "AUTH_REQUIRED")
            if admin and user.role != "admin":
                raise HTTPException(403, "ROLE_REQUIRED")

    def check_processing(self, manifest: SnapshotManifest) -> None:
        if not isinstance(self.llm, GroqLLM):
            return
        root = self.admission_root.resolve()
        path = root / f"{manifest.snapshot_id}.json"
        try:
            if path.is_symlink() or path.resolve().parent != root or path.stat().st_size > 65536:
                raise ValueError
            admission = ProcessingAdmission.model_validate_json(path.read_bytes())
            if (
                admission.snapshot_id != manifest.snapshot_id
                or admission.manifest_sha256 != manifest.manifest_sha256
                or admission.expires_at.tzinfo is None
                or admission.expires_at <= datetime.now(UTC)
                or not all(
                    value.strip()
                    for value in (
                        admission.reviewer,
                        admission.basis_reference,
                        admission.terms_processing_retention_reference,
                        admission.corpus_reuse_reference,
                    )
                )
            ):
                raise ValueError
        except (OSError, ValueError, ValidationError):
            raise HTTPException(403, "PROVIDER_PROCESSING_NOT_ADMITTED") from None

    def search(self, resolver: ManifestResolver) -> SnapshotSearchService:
        return SnapshotSearchService(self.corpus, self.evidence, resolver)

    def comparison(self, resolver: ManifestResolver) -> ComparisonService:
        return ComparisonService(self.evidence, resolver)

    async def close(self) -> None:
        if isinstance(self.llm, GroqLLM):
            await self.llm.aclose()
        if self.engine is not None:
            await asyncio.to_thread(self.engine.dispose)
