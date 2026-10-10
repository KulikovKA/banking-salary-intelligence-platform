"""Operator-controlled, provenance-checked fixed corpus snapshots."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.corpus.models import ExtractionRun, Snapshot, SnapshotMember
from app.ingestion.errors import IngestionError
from app.ingestion.policy import AcquisitionPolicy, validate_url
from app.ingestion.service import IngestionService
from app.registry.models import Bank, Blob, Source, SourceFetch, SourcePolicy, SourceVersion
from app.tariffs.models import FactReview, PublishedFact, TariffCandidate

BANK_CODES = ("sber", "vtb", "alfa", "kuban_credit")


class CorpusError(ValueError):
    """Safe operator-facing corpus error code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class MissingDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bank_code: Literal["sber", "vtb", "alfa", "kuban_credit"]
    document_type: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)
    basis_reference: str | None = Field(default=None, max_length=300)


class ManifestDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bank_code: Literal["sber", "vtb", "alfa", "kuban_credit"]
    source_id: UUID
    source_version_id: UUID
    source_fetch_id: UUID
    policy_id: UUID
    extraction_run_id: UUID | None
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    acquisition_method: Literal["automatic", "manual"]
    original_url: str = Field(min_length=1, max_length=2000)
    final_url: str = Field(min_length=1, max_length=2000)
    acquired_at: datetime
    scope: dict[str, str | list[str] | None]
    effective_date: str | None = None
    document_type: str = Field(min_length=1, max_length=100)

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError("EFFECTIVE_DATE_INVALID") from exc
        return value

    @field_validator("acquired_at")
    @classmethod
    def validate_acquired_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ACQUISITION_DATE_INVALID")
        return value.astimezone(UTC)


class SnapshotManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    snapshot_id: UUID
    revision: int = Field(ge=1)
    corpus_kind: Literal["real", "synthetic"]
    region: str = Field(min_length=1, max_length=80)
    employer_segment: str = Field(min_length=1, max_length=80)
    documents: tuple[ManifestDocument, ...]
    missing_documents: tuple[MissingDocument, ...]

    @model_validator(mode="after")
    def validate_coverage(self) -> SnapshotManifest:
        seen_versions: set[str] = set()
        for item in self.documents:
            key = str(item.source_version_id)
            if key in seen_versions:
                raise ValueError("MANIFEST_DUPLICATE_VERSION")
            seen_versions.add(key)
        missing_keys = {(item.bank_code, item.document_type) for item in self.missing_documents}
        if len(missing_keys) != len(self.missing_documents):
            raise ValueError("MANIFEST_DUPLICATE_MISSING_DOCUMENT")
        if not self.documents:
            raise ValueError("CORPUS_EMPTY")
        missing_banks = {item.bank_code for item in self.missing_documents}
        represented_banks = {item.bank_code for item in self.documents}
        if represented_banks | missing_banks != set(BANK_CODES):
            raise ValueError("MANIFEST_COVERAGE_INCOMPLETE")
        if represented_banks & missing_banks:
            raise ValueError("MANIFEST_COVERAGE_CONFLICT")
        return self

    def canonical_json(self) -> bytes:
        payload = self.model_dump(mode="json")
        payload["documents"] = sorted(
            payload["documents"],
            key=lambda row: (row["bank_code"], row["document_type"], row["source_version_id"]),
        )
        payload["missing_documents"] = sorted(
            payload["missing_documents"], key=lambda row: (row["bank_code"], row["document_type"])
        )
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256(self.canonical_json()).hexdigest()


class CorpusService:
    """Snapshot operations reuse the established ingestion factory and blob store."""

    def __init__(self, ingestion: IngestionService):
        self.ingestion = ingestion
        self.factory: sessionmaker[Session] = ingestion.factory
        self.store = ingestion.store

    @staticmethod
    def load_manifest(path: Path) -> SnapshotManifest:
        try:
            return SnapshotManifest.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            if isinstance(exc, ValidationError):
                codes = {str(err["msg"]).replace("Value error, ", "") for err in exc.errors()}
                for code in (
                    "CORPUS_EMPTY",
                    "MANIFEST_DUPLICATE_VERSION",
                    "MANIFEST_DUPLICATE_MISSING_DOCUMENT",
                    "MANIFEST_COVERAGE_INCOMPLETE",
                    "MANIFEST_COVERAGE_CONFLICT",
                ):
                    if code in codes:
                        raise CorpusError(code) from exc
            raise CorpusError("MANIFEST_INVALID") from exc

    def _validate_document(
        self, session: Session, manifest: SnapshotManifest, item: ManifestDocument,
        *, require_extraction: bool = True,
    ) -> None:
        source = session.get(Source, str(item.source_id))
        version = session.get(SourceVersion, str(item.source_version_id))
        fetch = session.get(SourceFetch, str(item.source_fetch_id))
        policy = session.get(SourcePolicy, str(item.policy_id))
        bank = session.get(Bank, source.bank_id) if source is not None else None
        if source is None or version is None or fetch is None or policy is None or bank is None:
            raise CorpusError("PROVENANCE_UNKNOWN")
        if (
            source.id != version.source_id
            or source.id != fetch.source_id
            or source.policy_id != policy.id
        ):
            raise CorpusError("PROVENANCE_MISMATCH")
        if bank.code != item.bank_code or source.corpus_kind != manifest.corpus_kind:
            raise CorpusError("CORPUS_KIND_OR_BANK_MISMATCH")
        if version.content_state != "accepted":
            raise CorpusError("SOURCE_VERSION_NOT_ACCEPTED")
        if (
            fetch.source_version_id != version.id
            or fetch.acquisition_method != item.acquisition_method
        ):
            raise CorpusError("ACQUISITION_MISMATCH")
        if fetch.requested_url != item.original_url or fetch.final_url != item.final_url:
            raise CorpusError("ACQUISITION_URL_MISMATCH")
        acquired_at = fetch.fetched_at
        if acquired_at.tzinfo is None or acquired_at.astimezone(UTC) != item.acquired_at.astimezone(
            UTC
        ):
            raise CorpusError("ACQUISITION_DATE_MISMATCH")
        if fetch.result not in {"success", "manual_imported", "not_modified"}:
            raise CorpusError("ACQUISITION_NOT_SUCCESSFUL")
        if policy.bank_id != source.bank_id or policy.collection_decision != "approved":
            raise CorpusError("PERMISSION_REVOKED")
        self._authorize_read(
            policy,
            source,
            manifest.corpus_kind,
            item.acquisition_method,
            item.original_url,
            tuple(fetch.redirect_chain) + (
                (item.final_url,) if item.final_url != item.original_url else ()
            ),
        )
        applicability = version.metadata_json.get("applicability")
        if not isinstance(applicability, dict) or applicability != item.scope:
            raise CorpusError("SCOPE_MISMATCH")
        if version.metadata_json.get("effective_date") != item.effective_date:
            raise CorpusError("EFFECTIVE_DATE_MISMATCH")
        if (
            item.scope.get("region") != manifest.region
            or item.scope.get("segment") != manifest.employer_segment
        ):
            raise CorpusError("SCOPE_MISMATCH")
        blob = session.get(Blob, version.blob_id)
        if blob is None or blob.corpus_kind != manifest.corpus_kind:
            raise CorpusError("BLOB_PROVENANCE_MISMATCH")
        if blob.sha256 != item.sha256:
            raise CorpusError("MANIFEST_HASH_MISMATCH")
        try:
            self.store.verify(self.ingestion._receipt(blob))
        except IngestionError as exc:
            raise CorpusError(exc.code) from exc
        if not require_extraction:
            return
        if item.extraction_run_id is None:
            raise CorpusError("EXTRACTION_NOT_READY")
        extraction = session.get(ExtractionRun, str(item.extraction_run_id))
        if (
            extraction is None
            or extraction.source_version_id != version.id
            or extraction.raw_sha256 != blob.sha256
            or extraction.corpus_kind != manifest.corpus_kind
            or extraction.status != "ok"
        ):
            raise CorpusError("EXTRACTION_NOT_READY")

    def validate(self, manifest: SnapshotManifest) -> dict[str, object]:
        with self.factory() as session:
            for item in manifest.documents:
                self._validate_document(
                    session, manifest, item, require_extraction=item.extraction_run_id is not None
                )
        return {
            "valid": True,
            "snapshot_id": str(manifest.snapshot_id),
            "revision": manifest.revision,
            "document_count": len(manifest.documents),
            "missing_document_count": len(manifest.missing_documents),
            "manifest_sha256": manifest.manifest_sha256,
            "corpus_kind": manifest.corpus_kind,
        }

    @staticmethod
    def _authorize_read(
        policy: SourcePolicy,
        source: Source,
        corpus_kind: str,
        method: str,
        url: str,
        redirects: tuple[str, ...] = (),
    ) -> None:
        try:
            grant = AcquisitionPolicy.model_validate(policy.acquisition_config.get(method))
            grant_hosts = {
                validate_url(candidate)
                for candidate in grant.allowed_urls + grant.redirect_urls
            }
            if (
                policy.bank_id != source.bank_id
                or
                grant.source_id != source.id
                or grant.corpus_kind != corpus_kind
                or grant.method != method
                or not grant_hosts.issubset(set(policy.allowed_hosts))
            ):
                raise CorpusError("PERMISSION_MISMATCH")
            grant.authorize(url, method)
            for target in redirects:
                grant.authorize(target, method, redirect=True)
        except CorpusError:
            raise
        except (ValidationError, IngestionError, TypeError) as exc:
            raise CorpusError("PERMISSION_REVOKED") from exc

    def add_version(self, manifest: SnapshotManifest, document_index: int) -> dict[str, object]:
        if document_index < 0:
            raise CorpusError("DOCUMENT_INDEX_INVALID")
        try:
            item = manifest.documents[document_index]
        except IndexError as exc:
            raise CorpusError("DOCUMENT_INDEX_INVALID") from exc
        with self.factory.begin() as session:
            self._validate_document(
                session, manifest, item, require_extraction=item.extraction_run_id is not None
            )
            snapshot = session.get(Snapshot, str(manifest.snapshot_id), with_for_update=True)
            if snapshot is None:
                snapshot = Snapshot(
                    id=str(manifest.snapshot_id),
                    revision=manifest.revision,
                    corpus_kind=manifest.corpus_kind,
                    state="draft",
                )
                session.add(snapshot)
                session.flush()
            if (
                snapshot.revision != manifest.revision
                or snapshot.corpus_kind != manifest.corpus_kind
            ):
                raise CorpusError("SNAPSHOT_IDENTITY_MISMATCH")
            if snapshot.state != "draft":
                raise CorpusError("SNAPSHOT_NOT_DRAFT")
            if item.extraction_run_id is None:
                return {"snapshot_id": snapshot.id, "added": False, "staged": True}
            exists = session.get(
                SnapshotMember,
                (str(manifest.snapshot_id), str(item.source_version_id)),
            )
            if exists is not None and exists.extraction_run_id != str(item.extraction_run_id):
                raise CorpusError("SNAPSHOT_MEMBER_CONFLICT")
            if exists is None:
                session.add(
                    SnapshotMember(
                        snapshot_id=str(manifest.snapshot_id),
                        source_version_id=str(item.source_version_id),
                        extraction_run_id=str(item.extraction_run_id),
                    )
                )
        return {"snapshot_id": str(manifest.snapshot_id), "added": exists is None}

    def read_draft_document(self, manifest: SnapshotManifest, document_index: int) -> Path:
        """Operator pipeline input before extraction; exact manifest, never latest version."""
        if not 0 <= document_index < len(manifest.documents):
            raise CorpusError("DOCUMENT_INDEX_INVALID")
        item = manifest.documents[document_index]
        with self.factory() as session:
            snapshot = session.get(Snapshot, str(manifest.snapshot_id))
            if snapshot is None or snapshot.state != "draft":
                raise CorpusError("SNAPSHOT_NOT_DRAFT")
            if (
                snapshot.revision != manifest.revision
                or snapshot.corpus_kind != manifest.corpus_kind
            ):
                raise CorpusError("SNAPSHOT_IDENTITY_MISMATCH")
            self._validate_document(session, manifest, item, require_extraction=False)
            version = session.get(SourceVersion, str(item.source_version_id))
            assert version is not None
            blob = session.get(Blob, version.blob_id)
            assert blob is not None
            return self.store.verify(self.ingestion._receipt(blob))

    def freeze(self, manifest: SnapshotManifest) -> dict[str, object]:
        if manifest.corpus_kind == "real" and manifest.missing_documents:
            raise CorpusError("REAL_CORPUS_INCOMPLETE")
        expected = {
            (str(item.source_version_id), str(item.extraction_run_id))
            for item in manifest.documents
        }
        with self.factory.begin() as session:
            snapshot = session.get(Snapshot, str(manifest.snapshot_id), with_for_update=True)
            if snapshot is None:
                raise CorpusError("SNAPSHOT_UNKNOWN")
            if (
                snapshot.revision != manifest.revision
                or snapshot.corpus_kind != manifest.corpus_kind
            ):
                raise CorpusError("SNAPSHOT_IDENTITY_MISMATCH")
            for item in manifest.documents:
                self._validate_document(session, manifest, item)
            members = set(
                session.execute(
                    select(
                        SnapshotMember.source_version_id, SnapshotMember.extraction_run_id
                    ).where(SnapshotMember.snapshot_id == snapshot.id)
                ).all()
            )
            if snapshot.state == "frozen":
                if snapshot.manifest_sha256 == manifest.manifest_sha256 and members == expected:
                    return {
                        "snapshot_id": snapshot.id,
                        "state": "frozen",
                        "manifest_sha256": snapshot.manifest_sha256,
                        "idempotent": True,
                    }
                raise CorpusError("FROZEN_SNAPSHOT_MISMATCH")
            if snapshot.state != "draft":
                raise CorpusError("SNAPSHOT_NOT_DRAFT")
            if members != expected:
                raise CorpusError("SNAPSHOT_COMPOSITION_MISMATCH")
            for item in manifest.documents:
                ready = session.scalar(
                    select(PublishedFact.id)
                    .join(TariffCandidate, TariffCandidate.id == PublishedFact.candidate_id)
                    .join(FactReview, FactReview.id == PublishedFact.review_id)
                    .where(
                        PublishedFact.snapshot_id == snapshot.id,
                        TariffCandidate.extraction_run_id == str(item.extraction_run_id),
                        FactReview.candidate_id == TariffCandidate.id,
                        FactReview.decision == "approved",
                        FactReview.validation["valid"].as_boolean().is_(True),
                    ).limit(1)
                )
                if ready is None:
                    raise CorpusError("PUBLISHED_FACTS_NOT_READY")
            snapshot.state = "frozen"
            snapshot.frozen_at = datetime.now(UTC)
            snapshot.manifest_sha256 = manifest.manifest_sha256
            return {
                "snapshot_id": snapshot.id,
                "state": "frozen",
                "manifest_sha256": snapshot.manifest_sha256,
                "idempotent": False,
            }

    def read_member(self, snapshot_id: UUID, source_version_id: UUID) -> Path:
        """Read an original only through frozen exact membership and current rights."""
        with self.factory() as session:
            snapshot = session.get(Snapshot, str(snapshot_id))
            if snapshot is None or snapshot.state != "frozen":
                raise CorpusError("SNAPSHOT_NOT_READABLE")
            row = session.execute(
                select(SourceVersion, Source, SourcePolicy, Blob, ExtractionRun)
                .join(Source, Source.id == SourceVersion.source_id)
                .join(SourcePolicy, SourcePolicy.id == Source.policy_id)
                .join(Blob, Blob.id == SourceVersion.blob_id)
                .join(SnapshotMember, SnapshotMember.source_version_id == SourceVersion.id)
                .join(ExtractionRun, ExtractionRun.id == SnapshotMember.extraction_run_id)
                .where(
                    SnapshotMember.snapshot_id == snapshot.id,
                    SourceVersion.id == str(source_version_id),
                )
            ).first()
            if row is None:
                raise CorpusError("SNAPSHOT_MEMBER_UNKNOWN")
            version, source, policy, blob, extraction = row
            if (
                version.content_state != "accepted"
                or source.corpus_kind != snapshot.corpus_kind
                or blob.corpus_kind != snapshot.corpus_kind
                or extraction.source_version_id != version.id
                or extraction.raw_sha256 != blob.sha256
                or extraction.corpus_kind != snapshot.corpus_kind
                or extraction.status != "ok"
            ):
                raise CorpusError("SNAPSHOT_MEMBER_INVALID")
            if policy.collection_decision != "approved":
                raise CorpusError("PERMISSION_REVOKED")
            fetch = session.scalar(
                select(SourceFetch)
                .where(SourceFetch.source_version_id == version.id)
                .order_by(SourceFetch.fetched_at.desc())
                .limit(1)
            )
            if fetch is None:
                raise CorpusError("PROVENANCE_UNKNOWN")
            if (
                fetch.source_version_id != version.id
                or fetch.source_id != source.id
                or fetch.final_url is None
                or fetch.result not in {"success", "manual_imported", "not_modified"}
            ):
                raise CorpusError("ACQUISITION_NOT_SUCCESSFUL")
            self._authorize_read(
                policy,
                source,
                snapshot.corpus_kind,
                fetch.acquisition_method,
                fetch.requested_url,
                tuple(fetch.redirect_chain) + (
                    (fetch.final_url,) if fetch.final_url != fetch.requested_url else ()
                ),
            )
            try:
                return self.store.verify(self.ingestion._receipt(blob))
            except IngestionError as exc:
                raise CorpusError(exc.code) from exc
