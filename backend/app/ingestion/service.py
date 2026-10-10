"""Transactional integration with the existing catalog, not a scheduled worker.

One operator attempt owns a transaction. PG source locks and advisory host locks
serialize concurrent calls. Files are completed first; rollback can leave an orphan but
cannot commit a DB reference to a partial file. Content acceptance is separate.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.ingestion.errors import TRANSIENT, IngestionError, retry_at
from app.ingestion.formats import document_kind
from app.ingestion.gateway import FetchGateway, FetchResult
from app.ingestion.policy import AcquisitionPolicy, validate_url
from app.registry.models import Blob, Source, SourceFetch, SourcePolicy, SourceVersion
from app.storage.local import BlobReceipt, LocalBlobStore


@dataclass(frozen=True)
class AcquisitionOutcome:
    observation_id: str
    version_id: str | None
    result: str
    error_code: str | None
    retry_at: datetime | None = None


class IngestionService:
    def __init__(
        self,
        factory: sessionmaker[Session],
        settings: Settings,
        store: LocalBlobStore,
        gateway: FetchGateway,
    ) -> None:
        self.factory, self.settings, self.store, self.gateway = factory, settings, store, gateway

    @staticmethod
    def _source(session: Session, source_id: str) -> Source:
        source = session.scalar(select(Source).where(Source.id == source_id).with_for_update())
        if source is None:
            raise IngestionError("SOURCE_UNKNOWN")
        return source

    @staticmethod
    def _loader(session: Session, source: Source, method: str) -> Callable[[], AcquisitionPolicy]:
        def load() -> AcquisitionPolicy:
            row = session.scalar(
                select(SourcePolicy)
                .where(SourcePolicy.id == source.policy_id)
                .execution_options(populate_existing=True)
            )
            if row is None or row.bank_id != source.bank_id:
                raise IngestionError("POLICY_BLOCKED")
            try:
                cfg = row.acquisition_config[method]
                policy = AcquisitionPolicy.model_validate(cfg)
            except (KeyError, ValueError, TypeError) as exc:
                raise IngestionError("POLICY_BLOCKED") from exc
            if (
                row.collection_decision != "approved"
                or policy.source_id != source.id
                or policy.corpus_kind != source.corpus_kind
                or not {
                    validate_url(url) for url in policy.allowed_urls + policy.redirect_urls
                }.issubset(set(row.allowed_hosts))
            ):
                raise IngestionError("POLICY_BLOCKED")
            return policy

        return load

    @staticmethod
    def _host_locks(session: Session, policy: AcquisitionPolicy) -> None:
        hosts = sorted({validate_url(url) for url in policy.allowed_urls + policy.redirect_urls})
        for host in hosts:
            key = int.from_bytes(hashlib.sha256(host.encode()).digest()[:8], "big", signed=True)
            if not session.scalar(select(func.pg_try_advisory_xact_lock(key))):
                raise IngestionError("HOST_BUSY", retry_after=policy.rate_seconds)
            latest = session.scalar(
                select(func.max(SourceFetch.fetched_at)).where(
                    SourceFetch.acquisition_method == "automatic",
                    SourceFetch.audit_metadata.contains({"requests": [{"host": host}]}),
                )
            )
            if latest is not None:
                wait = policy.rate_seconds - (datetime.now(UTC) - latest).total_seconds()
                if wait > 0:
                    raise IngestionError("REQUEST_RATE_LIMIT", retry_after=wait)

    def fetch_source(self, source_id: str, *, attempt: int = 1) -> AcquisitionOutcome:
        if attempt < 1 or attempt > self.settings.fetch_max_attempts:
            raise IngestionError("ATTEMPT_LIMIT")
        with self.factory.begin() as session:
            source = self._source(session, source_id)
            loader = self._loader(session, source, "automatic")
            now = datetime.now(UTC)
            observation = SourceFetch(
                source_id=source.id,
                requested_url=source.url,
                acquisition_method="automatic",
                fetched_at=now,
                result="error",
                audit_metadata={},
            )
            session.add(observation)
            next_attempt = None
            try:
                policy = loader()
                policy.authorize(source.url, "automatic")
                self._host_locks(session, policy)
                last = session.scalar(
                    select(SourceFetch)
                    .where(
                        SourceFetch.source_id == source.id,
                        SourceFetch.result == "success",
                        SourceFetch.acquisition_method == "automatic",
                    )
                    .order_by(SourceFetch.fetched_at.desc())
                    .limit(1)
                )
                cached = None
                if last is not None and last.source_version_id:
                    version = session.get(SourceVersion, last.source_version_id)
                    blob = session.get(Blob, version.blob_id) if version else None
                    if blob and blob.verified_at:
                        cached = self._receipt(blob)
                kind = document_kind(source.kind)
                fetched = self.gateway.fetch(
                    source.url,
                    kind,
                    loader,
                    cached=cached,
                    etag=last.etag if last else None,
                    last_modified=last.last_modified if last else None,
                )
                version = self._register(
                    session,
                    source,
                    fetched.receipt,
                    {
                        "acquisition_method": "automatic",
                        "original_url": source.url,
                        "final_url": fetched.audit["final_url"],
                        "kind": kind,
                        "corpus_kind": policy.corpus_kind,
                        "observed_at": now.isoformat(),
                        "effective_from": None,
                        "scope": "unknown",
                    },
                )
                self._successful_observation(observation, fetched, version)
                source.last_successful_check = now
                source.state = "healthy"
            except IngestionError as exc:
                next_attempt = retry_at(exc, attempt, max_attempts=self.settings.fetch_max_attempts)
                observation.error_code = exc.code
                observation.audit_metadata = {
                    **exc.audit,
                    "retry_at": next_attempt.isoformat() if next_attempt else None,
                }
                status = exc.audit.get("http_status")
                observation.http_status = status if isinstance(status, int) else None
                final_url = exc.audit.get("final_url")
                observation.final_url = final_url if isinstance(final_url, str) else None
                observation.result = "error" if exc.code in TRANSIENT else "rejected"
                source.state = "degraded" if exc.code in TRANSIENT else "blocked"
            source.last_check_at = now
            observation.fetched_at = datetime.now(UTC)
            session.flush()
            return AcquisitionOutcome(
                observation.id,
                observation.source_version_id,
                observation.result,
                observation.error_code,
                next_attempt,
            )

    @staticmethod
    def _receipt(blob: Blob) -> BlobReceipt:
        if blob.corpus_kind not in ("real", "synthetic"):
            raise IngestionError("CORPUS_INVALID")
        return BlobReceipt(
            blob.sha256,
            blob.byte_size,
            blob.media_type,
            blob.storage_key,
            "real" if blob.corpus_kind == "real" else "synthetic",
        )

    def _register(
        self, session: Session, source: Source, receipt: BlobReceipt, metadata: dict[str, Any]
    ) -> SourceVersion:
        self.store.verify(receipt)
        if source.corpus_kind != receipt.corpus_kind:
            raise IngestionError("CORPUS_INVALID")
        session.execute(
            insert(Blob)
            .values(**asdict(receipt), verified_at=datetime.now(UTC))
            .on_conflict_do_nothing(constraint="uq_blobs_corpus_sha256")
        )
        blob = session.scalar(
            select(Blob).where(
                Blob.sha256 == receipt.sha256, Blob.corpus_kind == receipt.corpus_kind
            )
        )
        assert blob is not None
        self.store.verify(self._receipt(blob))
        session.execute(
            insert(SourceVersion)
            .values(
                source_id=source.id, blob_id=blob.id, metadata=metadata, content_state="quarantine"
            )
            .on_conflict_do_nothing(constraint="uq_source_versions_source_blob")
        )
        version = session.scalar(
            select(SourceVersion).where(
                SourceVersion.source_id == source.id, SourceVersion.blob_id == blob.id
            )
        )
        assert version is not None
        return version

    @staticmethod
    def _successful_observation(
        observation: SourceFetch, fetched: FetchResult, version: SourceVersion
    ) -> None:
        observation.source_version_id = version.id
        observation.result = "not_modified" if fetched.status == 304 else "success"
        observation.http_status = fetched.status
        observation.final_url = str(fetched.audit["final_url"])
        redirects = fetched.audit["redirect_chain"]
        assert isinstance(redirects, list)
        observation.redirect_chain = [str(url) for url in redirects]
        observation.etag, observation.last_modified = fetched.etag, fetched.last_modified
        observation.audit_metadata = fetched.audit

    def import_file(
        self,
        source_id: str,
        path: Path,
        *,
        operator: str,
        original_url: str,
        final_url: str,
        acquired_at: datetime,
    ) -> AcquisitionOutcome:
        try:
            return self._import_file(
                source_id,
                path,
                operator=operator,
                original_url=original_url,
                final_url=final_url,
                acquired_at=acquired_at,
            )
        except IngestionError as exc:
            # Audit rejected manual attempts separately; no bytes or local filename are stored.
            with self.factory.begin() as session:
                source = session.get(Source, source_id)
                if source is not None:
                    session.add(
                        SourceFetch(
                            source_id=source_id,
                            requested_url=source.url,
                            acquisition_method="manual",
                            result="rejected",
                            error_code=exc.code,
                            audit_metadata={"acquisition_method": "manual", "error_code": exc.code},
                        )
                    )
            raise

    def _import_file(
        self,
        source_id: str,
        path: Path,
        *,
        operator: str,
        original_url: str,
        final_url: str,
        acquired_at: datetime,
    ) -> AcquisitionOutcome:
        with self.factory.begin() as session:
            source = self._source(session, source_id)
            policy = self._loader(session, source, "manual")()
            policy.authorize(original_url, "manual")
            if final_url != original_url:
                policy.authorize(final_url, "manual", redirect=True)
            if (
                not operator.strip()
                or len(operator) > 200
                or acquired_at.tzinfo is None
                or acquired_at > datetime.now(UTC)
                or source.url != original_url
                or path.is_symlink()
                or (
                    source.corpus_kind == "real"
                    and (self.settings.ingestion_mode != "live" or self.settings.app_env == "test")
                )
            ):
                raise IngestionError("MANUAL_PROVENANCE_INVALID")
            kind = document_kind(source.kind)
            metadata = {
                "acquisition_method": "manual",
                "operator": operator,
                "original_url": original_url,
                "final_url": final_url,
                "acquired_at": acquired_at.isoformat(),
                "policy_id": source.policy_id,
                "approval": policy.model_dump(mode="json"),
                "kind": kind,
                "corpus_kind": policy.corpus_kind,
                "effective_from": None,
                "scope": "unknown",
            }
            receipt = self.store.put(read_chunks(path), kind, policy.corpus_kind)
            version = self._register(session, source, receipt, metadata)
            observation = SourceFetch(
                source_id=source.id,
                requested_url=original_url,
                final_url=final_url,
                acquisition_method="manual",
                result="manual_imported",
                source_version_id=version.id,
                audit_metadata=metadata,
                fetched_at=datetime.now(UTC),
            )
            session.add(observation)
            session.flush()
            return AcquisitionOutcome(observation.id, version.id, "manual_imported", None)

    def accept_content(
        self, version_id: str, *, reviewer: str, applicability: dict[str, Any]
    ) -> None:
        if not reviewer.strip() or not applicability:
            raise IngestionError("CONTENT_ACCEPTANCE_INVALID")
        with self.factory.begin() as session:
            version = session.scalar(
                select(SourceVersion).where(SourceVersion.id == version_id).with_for_update()
            )
            if version is None or version.content_state != "quarantine":
                raise IngestionError("CONTENT_ACCEPTANCE_INVALID")
            blob = session.get(Blob, version.blob_id)
            if blob is None:
                raise IngestionError("STORAGE_MISSING")
            self.store.verify(self._receipt(blob))
            version.content_state = "accepted"
            version.accepted_at, version.accepted_by = datetime.now(UTC), reviewer
            version.metadata_json = {**version.metadata_json, "applicability": applicability}

    def current_content(self, source_id: str) -> str | None:
        """Last accepted version for operator inspection, not a snapshot/read permission check."""
        with self.factory() as session:
            source = session.get(Source, source_id)
            if source is None:
                raise IngestionError("SOURCE_UNKNOWN")
            version = session.scalar(
                select(SourceVersion)
                .where(
                    SourceVersion.source_id == source_id, SourceVersion.content_state == "accepted"
                )
                .order_by(SourceVersion.accepted_at.desc())
                .limit(1)
            )
            return version.id if version else None


def read_chunks(path: Path) -> Iterator[bytes]:
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        while chunk := stream.read(65536):
            yield chunk
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise IngestionError("MANUAL_FILE_CHANGED")
