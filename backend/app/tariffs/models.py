"""Normalized tariff candidates, evidence links, human decisions, and publication."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid_pk() -> Mapped[str]:
    return mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))


def _hash_check(column: str, name: str) -> CheckConstraint:
    return CheckConstraint(f"{column} ~ '^[0-9a-f]{{64}}$'", name=name)


class TariffCandidate(Base):
    __tablename__ = "tariff_candidates"
    __table_args__ = (
        ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["bank_id"], ["banks.id"], ondelete="RESTRICT"),
        CheckConstraint("corpus_kind in ('real', 'synthetic')", name="ck_tariff_candidates_corpus"),
        CheckConstraint(
            "metric_code ~ '^[a-z][a-z0-9_]{1,63}$'", name="ck_tariff_candidates_metric"
        ),
        CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name="ck_tariff_candidates_payload_object"
        ),
        _hash_check("payload_sha256", "ck_tariff_candidates_payload_sha256"),
        Index("ix_tariff_candidates_bank_metric", "bank_id", "metric_code"),
        Index("ix_tariff_candidates_extraction_run_id", "extraction_run_id"),
        Index("ix_tariff_candidates_corpus_kind", "corpus_kind"),
    )

    id: Mapped[str] = _uuid_pk()
    extraction_run_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    bank_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    corpus_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvidenceRef(Base):
    __tablename__ = "evidence_refs"
    __table_args__ = (
        ForeignKeyConstraint(["candidate_id"], ["tariff_candidates.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["source_version_id"], ["source_versions.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="RESTRICT"),
        _hash_check("raw_sha256", "ck_evidence_refs_raw_sha256"),
        _hash_check("extraction_sha256", "ck_evidence_refs_extraction_sha256"),
        CheckConstraint("quote_start >= 0", name="ck_evidence_refs_quote_start"),
        CheckConstraint("quote_end > quote_start", name="ck_evidence_refs_quote_end"),
        CheckConstraint(
            "quote_end - quote_start = char_length(quote)",
            name="ck_evidence_refs_quote_length",
        ),
        CheckConstraint(
            "support_role in ('value', 'unit', 'basis', 'condition', 'scope', 'date')",
            name="ck_evidence_refs_support_role",
        ),
        Index("ix_evidence_refs_candidate_id", "candidate_id"),
        Index("ix_evidence_refs_chunk_id", "chunk_id"),
    )

    id: Mapped[str] = _uuid_pk()
    candidate_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    source_version_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    extraction_run_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    chunk_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    quote_start: Mapped[int] = mapped_column(nullable=False)
    quote_end: Mapped[int] = mapped_column(nullable=False)
    locator: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    support_role: Mapped[str] = mapped_column(String(20), nullable=False)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FactReview(Base):
    __tablename__ = "fact_reviews"
    __table_args__ = (
        ForeignKeyConstraint(["candidate_id"], ["tariff_candidates.id"], ondelete="RESTRICT"),
        CheckConstraint(
            "decision in ('approved', 'rejected', 'needs_review')", name="ck_fact_reviews_decision"
        ),
        CheckConstraint(
            "reviewer_label = 'operator' or length(btrim(reviewer_label)) > 0",
            name="ck_fact_reviews_reviewer_label",
        ),
        CheckConstraint("jsonb_typeof(validation) = 'object'", name="ck_fact_reviews_validation"),
        Index("ix_fact_reviews_candidate_created", "candidate_id", "created_at"),
    )

    id: Mapped[str] = _uuid_pk()
    candidate_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    reviewer_label: Mapped[str] = mapped_column(String(200), nullable=False)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    validation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PublishedFact(Base):
    __tablename__ = "published_facts"
    __table_args__ = (
        ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["candidate_id"], ["tariff_candidates.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["review_id"], ["fact_reviews.id"], ondelete="RESTRICT"),
        UniqueConstraint(
            "snapshot_id", "candidate_id", name="uq_published_facts_snapshot_candidate"
        ),
        UniqueConstraint("review_id", name="uq_published_facts_review"),
        Index("ix_published_facts_snapshot_id", "snapshot_id"),
    )

    id: Mapped[str] = _uuid_pk()
    snapshot_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    candidate_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    review_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
