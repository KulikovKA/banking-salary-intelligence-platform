"""Append-only human review and atomic publication into exact draft membership."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.models import AuthUser
from app.contracts.evidence import EvidenceRef as RefDTO
from app.corpus.models import ExtractionRun, Snapshot, SnapshotMember
from app.corpus.service import CorpusService, SnapshotManifest
from app.evidence.validation import (
    EvidenceError,
    EvidenceValidator,
    SemanticConfirmation,
    ValidationReport,
    canonical_hash,
)
from app.registry.models import Source, SourcePolicy, SourceVersion
from app.tariffs.models import EvidenceRef, FactReview, PublishedFact, TariffCandidate


@dataclass(frozen=True)
class PublicationResult:
    fact_id: str
    candidate_id: str
    review_id: str
    idempotent: bool


class EvidenceService:
    def __init__(
        self, corpus: CorpusService, *, validator: EvidenceValidator | None = None
    ) -> None:
        self.corpus = corpus
        self.factory = corpus.factory
        self.validator = validator or EvidenceValidator(corpus)

    def _lock(
        self,
        session: Session,
        manifest: SnapshotManifest,
        candidate_id: str,
    ) -> tuple[Snapshot, TariffCandidate]:
        snapshot = session.get(Snapshot, str(manifest.snapshot_id), with_for_update=True)
        if snapshot is None:
            raise EvidenceError("SNAPSHOT_UNKNOWN")
        if snapshot.revision != manifest.revision or snapshot.corpus_kind != manifest.corpus_kind:
            raise EvidenceError("SNAPSHOT_IDENTITY_MISMATCH")
        if snapshot.state == "frozen" and snapshot.manifest_sha256 != manifest.manifest_sha256:
            raise EvidenceError("SNAPSHOT_MANIFEST_MISMATCH")
        candidate = session.get(TariffCandidate, candidate_id, with_for_update=True)
        if candidate is None:
            raise EvidenceError("CANDIDATE_UNKNOWN")
        matches = [
            item
            for item in manifest.documents
            if str(item.extraction_run_id) == candidate.extraction_run_id
        ]
        if len(matches) != 1:
            raise EvidenceError("CANDIDATE_NOT_IN_MANIFEST")
        item = matches[0]
        session.get(SourceVersion, str(item.source_version_id), with_for_update=True)
        session.get(Source, str(item.source_id), with_for_update=True)
        session.get(SourcePolicy, str(item.policy_id), with_for_update=True)
        return snapshot, candidate

    def validate(
        self,
        manifest: SnapshotManifest,
        candidate_id: str,
        confirmation: SemanticConfirmation | None = None,
    ) -> ValidationReport:
        with self.factory.begin() as session:
            snapshot, _ = self._lock(session, manifest, candidate_id)
            if snapshot.state not in {"draft", "frozen"}:
                raise EvidenceError("SNAPSHOT_NOT_READABLE")
            return self.validator.validate(session, manifest, candidate_id, confirmation)

    def inspect(self, manifest: SnapshotManifest, candidate_id: str) -> dict[str, object]:
        with self.factory.begin() as session:
            snapshot, candidate = self._lock(session, manifest, candidate_id)
            if snapshot.state not in {"draft", "frozen"}:
                raise EvidenceError("SNAPSHOT_NOT_READABLE")
            report = self.validator.validate(session, manifest, candidate_id)
            if not report.technical_valid:
                raise EvidenceError(report.errors[0])
            refs = session.scalars(
                select(EvidenceRef)
                .where(EvidenceRef.candidate_id == candidate_id)
                .order_by(EvidenceRef.id)
            ).all()
            return {
                "candidate": candidate.payload,
                "evidence": [
                    {
                        "id": ref.id,
                        "quote": ref.quote,
                        "quote_start": ref.quote_start,
                        "quote_end": ref.quote_end,
                        "locator": ref.locator,
                        "support_role": ref.support_role,
                    }
                    for ref in refs
                ],
                "validation": report.as_dict(),
            }

    def review(
        self,
        manifest: SnapshotManifest,
        candidate_id: str,
        *,
        decision: Literal["approved", "rejected", "needs_review"],
        reviewer_label: str,
        reason: str,
        confirmation: SemanticConfirmation | None = None,
        user_id: str | None = None,
    ) -> str:
        if decision not in {"approved", "rejected", "needs_review"}:
            raise EvidenceError("REVIEW_DECISION_INVALID")
        label, explanation = reviewer_label.strip(), reason.strip()
        if not label or len(label) > 200 or not explanation or len(explanation) > 2000:
            raise EvidenceError("REVIEW_IDENTITY_OR_REASON_REQUIRED")
        try:
            with self.factory.begin() as session:
                snapshot, _ = self._lock(session, manifest, candidate_id)
                if snapshot.state != "draft":
                    raise EvidenceError("SNAPSHOT_NOT_DRAFT")
                if (
                    session.scalar(
                        select(PublishedFact.id)
                        .where(
                            PublishedFact.candidate_id == candidate_id,
                            PublishedFact.snapshot_id == snapshot.id,
                        )
                        .limit(1)
                    )
                    is not None
                ):
                    raise EvidenceError("PUBLISHED_CANDIDATE_IMMUTABLE")
                if user_id is not None:
                    user = session.get(AuthUser, user_id, with_for_update=True)
                    if user is None or not user.active or user.role != "admin":
                        raise EvidenceError("REVIEWER_NOT_AUTHORIZED")
                report = self.validator.validate(session, manifest, candidate_id, confirmation)
                if decision == "approved" and not report.valid:
                    raise EvidenceError(report.errors[0])
                review_id = str(uuid4())
                validation = report.as_dict()
                validation["snapshot_id"] = snapshot.id
                # A rejection remains a durable audit decision, never a publish grant.
                if decision != "approved":
                    validation["valid"] = False
                session.add(
                    FactReview(
                        id=review_id,
                        candidate_id=candidate_id,
                        reviewer_label=label,
                        user_id=user_id,
                        decision=decision,
                        reason=explanation,
                        validation=validation,
                        created_at=datetime.now(UTC),
                    )
                )
                session.flush()
            return review_id
        except SQLAlchemyError as exc:
            raise EvidenceError("REVIEW_PERSISTENCE_FAILED") from exc

    def publish(
        self,
        manifest: SnapshotManifest,
        candidate_id: str,
        review_id: str,
    ) -> PublicationResult:
        try:
            with self.factory.begin() as session:
                snapshot, candidate = self._lock(session, manifest, candidate_id)
                if snapshot.state not in {"draft", "frozen"}:
                    raise EvidenceError("SNAPSHOT_NOT_READABLE")
                review = session.get(FactReview, review_id)
                latest = session.scalar(
                    select(FactReview)
                    .where(
                        FactReview.candidate_id == candidate_id,
                        FactReview.validation["snapshot_id"].as_string() == snapshot.id,
                    )
                    .order_by(FactReview.created_at.desc(), FactReview.id.desc())
                    .limit(1)
                )
                if (
                    review is None
                    or latest is None
                    or latest.id != review.id
                    or review.candidate_id != candidate_id
                    or review.decision != "approved"
                    or review.validation.get("valid") is not True
                ):
                    raise EvidenceError("APPROVED_REVIEW_REQUIRED")
                proof = review.validation.get("proof")
                fields = proof.get("field_evidence") if isinstance(proof, dict) else None
                if not isinstance(fields, dict):
                    raise EvidenceError("REVIEW_VALIDATION_INVALID")
                report = self.validator.validate(
                    session, manifest, candidate_id, SemanticConfirmation(fields)
                )
                if not report.valid:
                    raise EvidenceError(report.errors[0])
                if {**report.as_dict(), "snapshot_id": snapshot.id} != review.validation:
                    raise EvidenceError("REVIEW_VALIDATION_MISMATCH")
                existing = session.scalar(
                    select(PublishedFact).where(
                        PublishedFact.snapshot_id == snapshot.id,
                        PublishedFact.candidate_id == candidate_id,
                    )
                )
                if existing is not None:
                    if existing.review_id != review_id:
                        raise EvidenceError("PUBLICATION_REVIEW_CONFLICT")
                    return PublicationResult(existing.id, candidate_id, review_id, True)
                if snapshot.state != "draft":
                    raise EvidenceError("SNAPSHOT_NOT_DRAFT")
                member_key = next(
                    item
                    for item in manifest.documents
                    if str(item.extraction_run_id) == candidate.extraction_run_id
                )
                member = session.get(
                    SnapshotMember, (snapshot.id, str(member_key.source_version_id))
                )
                if member is not None and member.extraction_run_id != candidate.extraction_run_id:
                    raise EvidenceError("SNAPSHOT_MEMBER_CONFLICT")
                if member is None:
                    session.add(
                        SnapshotMember(
                            snapshot_id=snapshot.id,
                            source_version_id=str(member_key.source_version_id),
                            extraction_run_id=candidate.extraction_run_id,
                        )
                    )
                    session.flush()
                fact_id = str(uuid4())
                session.add(
                    PublishedFact(
                        id=fact_id,
                        snapshot_id=snapshot.id,
                        candidate_id=candidate_id,
                        review_id=review_id,
                    )
                )
                session.flush()
            return PublicationResult(fact_id, candidate_id, review_id, False)
        except SQLAlchemyError as exc:
            raise EvidenceError("PUBLICATION_PERSISTENCE_FAILED") from exc

    def read_published(self, manifest: SnapshotManifest) -> tuple[dict[str, object], ...]:
        """Downstream read interface: exact frozen manifest, reviewed facts only."""
        with self.factory.begin() as session:
            snapshot = session.get(Snapshot, str(manifest.snapshot_id), with_for_update=True)
            if (
                snapshot is None
                or snapshot.state != "frozen"
                or snapshot.manifest_sha256 != manifest.manifest_sha256
                or snapshot.corpus_kind != manifest.corpus_kind
                or snapshot.revision != manifest.revision
            ):
                raise EvidenceError("SNAPSHOT_NOT_READABLE")
            members = set(
                session.execute(
                    select(
                        SnapshotMember.source_version_id, SnapshotMember.extraction_run_id
                    ).where(SnapshotMember.snapshot_id == snapshot.id)
                ).all()
            )
            if members != {
                (str(item.source_version_id), str(item.extraction_run_id))
                for item in manifest.documents
            }:
                raise EvidenceError("SNAPSHOT_COMPOSITION_MISMATCH")
            for item in sorted(manifest.documents, key=lambda item: str(item.source_version_id)):
                session.get(SourceVersion, str(item.source_version_id), with_for_update=True)
                session.get(Source, str(item.source_id), with_for_update=True)
                session.get(SourcePolicy, str(item.policy_id), with_for_update=True)
                self.corpus._validate_document(session, manifest, item)
            rows = session.execute(
                select(PublishedFact, TariffCandidate, FactReview)
                .join(TariffCandidate, PublishedFact.candidate_id == TariffCandidate.id)
                .join(FactReview, PublishedFact.review_id == FactReview.id)
                .where(PublishedFact.snapshot_id == snapshot.id)
                .order_by(PublishedFact.id)
            ).all()
            output = []
            for fact, candidate, review in rows:
                latest = session.scalar(
                    select(FactReview.id)
                    .where(
                        FactReview.candidate_id == candidate.id,
                        FactReview.validation["snapshot_id"].as_string() == snapshot.id,
                    )
                    .order_by(FactReview.created_at.desc(), FactReview.id.desc())
                    .limit(1)
                )
                if (
                    review.decision != "approved"
                    or review.validation.get("valid") is not True
                    or latest != review.id
                ):
                    raise EvidenceError("PUBLISHED_REVIEW_INVALID")
                run = session.get(ExtractionRun, candidate.extraction_run_id)
                if run is None or (run.source_version_id, run.id) not in members:
                    raise EvidenceError("PUBLISHED_FACT_PROVENANCE_MISMATCH")
                proof = review.validation.get("proof")
                if (
                    not isinstance(proof, dict)
                    or proof.get("candidate_id") != candidate.id
                    or proof.get("candidate_sha256") != candidate.payload_sha256
                    or canonical_hash(candidate.payload) != candidate.payload_sha256
                    or proof.get("extraction_run_id") != run.id
                    or proof.get("raw_sha256") != run.raw_sha256
                    or proof.get("extraction_sha256") != run.extraction_sha256
                    or review.validation.get("technical_valid") is not True
                    or review.validation.get("semantic_confirmed") is not True
                ):
                    raise EvidenceError("PUBLISHED_REVIEW_PROOF_INVALID")
                refs = session.scalars(
                    select(EvidenceRef).where(EvidenceRef.candidate_id == candidate.id)
                ).all()
                expected_refs = {
                    ref.id: canonical_hash(
                        RefDTO.model_validate(
                            {
                                name: getattr(ref, name)
                                for name in RefDTO.model_fields
                                if name != "schema_version"
                            }
                        ).model_dump(mode="json")
                    )
                    for ref in refs
                }
                if (
                    proof.get("evidence") != expected_refs
                    or set(expected_refs) != set(candidate.payload["evidence_ids"])
                    or proof.get("parser_version") != run.parser_version
                ):
                    raise EvidenceError("PUBLISHED_REVIEW_PROOF_INVALID")
                output.append(
                    {
                        "fact_id": fact.id,
                        "review_id": review.id,
                        "snapshot_id": snapshot.id,
                        "candidate": candidate.payload,
                        "evidence_ids": candidate.payload["evidence_ids"],
                        "limitations": review.validation.get("limitations", []),
                        "eligible_for_comparison": review.validation.get("eligible_for_comparison")
                        is True,
                    }
                )
            return tuple(output)
