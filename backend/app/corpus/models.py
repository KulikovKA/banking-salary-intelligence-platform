"""Immutable extraction records and versioned snapshot membership."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid_pk() -> Mapped[str]:
    return mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))


def _hash_check(column: str, name: str) -> CheckConstraint:
    return CheckConstraint(f"{column} ~ '^[0-9a-f]{{64}}$'", name=name)


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_snapshots_revision_positive"),
        CheckConstraint("corpus_kind in ('real', 'synthetic')", name="ck_snapshots_corpus"),
        CheckConstraint("state in ('draft', 'frozen', 'revoked')", name="ck_snapshots_state"),
        CheckConstraint(
            "(state = 'draft' and frozen_at is null and manifest_sha256 is null) or "
            "(state in ('frozen', 'revoked') and frozen_at is not null "
            "and manifest_sha256 ~ '^[0-9a-f]{64}$')",
            name="ck_snapshots_freeze_fields",
        ),
        UniqueConstraint("revision", name="uq_snapshots_revision"),
    )

    id: Mapped[str] = _uuid_pk()
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    corpus_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"
    __table_args__ = (
        ForeignKeyConstraint(["source_version_id"], ["source_versions.id"], ondelete="RESTRICT"),
        _hash_check("raw_sha256", "ck_extraction_runs_raw_sha256"),
        _hash_check("extraction_sha256", "ck_extraction_runs_extraction_sha256"),
        CheckConstraint("corpus_kind in ('real', 'synthetic')", name="ck_extraction_runs_corpus"),
        CheckConstraint(
            "status in ('ok', 'needs_ocr', 'unsupported', 'failed')",
            name="ck_extraction_runs_status",
        ),
        UniqueConstraint(
            "source_version_id",
            "parser_version",
            "extraction_sha256",
            name="uq_extraction_runs_version_parser_hash",
        ),
        Index("ix_extraction_runs_source_version_id", "source_version_id"),
    )

    id: Mapped[str] = _uuid_pk()
    source_version_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(200), nullable=False)
    corpus_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="RESTRICT"),
        _hash_check("text_sha256", "ck_document_chunks_text_sha256"),
        CheckConstraint("ordinal >= 0", name="ck_document_chunks_ordinal_nonnegative"),
        UniqueConstraint("extraction_run_id", "ordinal", name="uq_document_chunks_run_ordinal"),
        Index("ix_document_chunks_extraction_ordinal", "extraction_run_id", "ordinal"),
        Index(
            "ix_document_chunks_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    id: Mapped[str] = _uuid_pk()
    extraction_run_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    locator: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    relations: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, default=list)
    search_vector: Mapped[Any] = mapped_column(TSVECTOR, nullable=False)


class SnapshotMember(Base):
    __tablename__ = "snapshot_members"
    __table_args__ = (
        ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["source_version_id"], ["source_versions.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="RESTRICT"),
        # The composite identity also allows facts to bind to one exact snapshot revision.
        UniqueConstraint("snapshot_id", "extraction_run_id", name="uq_snapshot_members_extraction"),
        Index("ix_snapshot_members_source_version_id", "source_version_id"),
    )

    snapshot_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    source_version_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    extraction_run_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
