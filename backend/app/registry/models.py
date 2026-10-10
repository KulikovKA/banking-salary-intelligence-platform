"""Initial catalog and immutable source archive SQLAlchemy models."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def uuid_pk() -> Mapped[str]:
    return mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))


class Bank(Base):
    __tablename__ = "banks"

    id: Mapped[str] = uuid_pk()
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SourcePolicy(Base):
    __tablename__ = "source_policies"
    __table_args__ = (
        CheckConstraint(
            "collection_decision in ('approved', 'pending', 'denied')",
            name="ck_source_policies_decision",
        ),
        CheckConstraint(
            "rate_seconds is null or rate_seconds > 0",
            name="ck_source_policies_rate_positive",
        ),
    )

    id: Mapped[str] = uuid_pk()
    bank_id: Mapped[str] = mapped_column(ForeignKey("banks.id", ondelete="RESTRICT"), index=True)
    allowed_hosts: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    robots_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terms_url: Mapped[str | None] = mapped_column(Text)
    terms_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collection_decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    rate_seconds: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("bank_id", "canonical_url", name="uq_sources_bank_canonical_url"),
        CheckConstraint("schedule_seconds > 0", name="ck_sources_schedule_positive"),
        CheckConstraint("kind in ('html', 'pdf', 'index', 'news')", name="ck_sources_kind"),
        CheckConstraint(
            "state in ('healthy', 'degraded', 'unknown', 'disabled', 'blocked')",
            name="ck_sources_state",
        ),
    )

    id: Mapped[str] = uuid_pk()
    bank_id: Mapped[str] = mapped_column(ForeignKey("banks.id", ondelete="RESTRICT"), index=True)
    policy_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_policies.id", ondelete="RESTRICT"), index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    scope_hint: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    adapter_code: Mapped[str | None] = mapped_column(String(80))
    adapter_version: Mapped[str | None] = mapped_column(String(40))
    schedule_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_parse: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Blob(Base):
    __tablename__ = "blobs"
    __table_args__ = (CheckConstraint("byte_size > 0", name="ck_blobs_size_positive"),)

    id: Mapped[str] = uuid_pk()
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index(
    "ix_sources_due_active",
    Source.next_check_at,
    postgresql_where=text("state in ('healthy', 'degraded', 'unknown')"),
)


class SourceVersion(Base):
    __tablename__ = "source_versions"
    __table_args__ = (
        UniqueConstraint("source_id", "blob_id", name="uq_source_versions_source_blob"),
    )

    id: Mapped[str] = uuid_pk()
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), index=True
    )
    blob_id: Mapped[str] = mapped_column(ForeignKey("blobs.id", ondelete="RESTRICT"), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        CheckConstraint("attempt >= 0 and max_attempts > 0", name="ck_job_runs_attempts"),
        CheckConstraint(
            "state in ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_job_runs_state",
        ),
        Index("ix_job_runs_state_retry", "state", "retry_at"),
        Index(
            "ix_job_runs_running_lease",
            "lease_until",
            postgresql_where=text("state = 'running'"),
        ),
    )

    id: Mapped[str] = uuid_pk()
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), index=True
    )
    aggregate_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    scheduled_slot: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class SourceFetch(Base):
    __tablename__ = "source_fetches"
    __table_args__ = (
        Index("ix_source_fetches_source_fetched", "source_id", "fetched_at"),
        CheckConstraint(
            "result in ('success', 'not_modified', 'rejected', 'error')",
            name="ck_source_fetches_result",
        ),
        CheckConstraint(
            "http_status is null or http_status between 100 and 599",
            name="ck_source_fetches_http_status",
        ),
    )

    id: Mapped[str] = uuid_pk()
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), index=True
    )
    job_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_runs.id", ondelete="RESTRICT"), index=True
    )
    requested_url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str | None] = mapped_column(Text)
    redirect_chain: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    http_status: Mapped[int | None] = mapped_column(Integer)
    etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(24), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    source_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_versions.id", ondelete="RESTRICT"), index=True
    )
