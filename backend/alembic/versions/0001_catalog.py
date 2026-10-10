"""Initial catalog, source archive metadata, and job queue.

Revision ID: 0001_catalog
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_catalog"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "banks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "source_policies",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column(
            "bank_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("banks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("allowed_hosts", postgresql.JSONB(), nullable=False),
        sa.Column("robots_checked_at", sa.DateTime(timezone=True)),
        sa.Column("terms_url", sa.Text()),
        sa.Column("terms_checked_at", sa.DateTime(timezone=True)),
        sa.Column("collection_decision", sa.String(20), nullable=False),
        sa.Column("reviewer", sa.String(200)),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("rate_seconds", sa.Integer()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "collection_decision in ('approved', 'pending', 'denied')",
            name="ck_source_policies_decision",
        ),
        sa.CheckConstraint(
            "rate_seconds is null or rate_seconds > 0",
            name="ck_source_policies_rate_positive",
        ),
    )
    op.create_index("ix_source_policies_bank_id", "source_policies", ["bank_id"])
    op.create_table(
        "blobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.String(200), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("byte_size > 0", name="ck_blobs_size_positive"),
    )
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column(
            "bank_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("banks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "policy_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("source_policies.id", ondelete="RESTRICT"),
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("scope_hint", postgresql.JSONB(), nullable=False),
        sa.Column("adapter_code", sa.String(80)),
        sa.Column("adapter_version", sa.String(40)),
        sa.Column("schedule_seconds", sa.Integer(), nullable=False),
        sa.Column("next_check_at", sa.DateTime(timezone=True)),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("last_check_at", sa.DateTime(timezone=True)),
        sa.Column("last_successful_check", sa.DateTime(timezone=True)),
        sa.Column("last_successful_parse", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("bank_id", "canonical_url", name="uq_sources_bank_canonical_url"),
        sa.CheckConstraint("schedule_seconds > 0", name="ck_sources_schedule_positive"),
        sa.CheckConstraint("kind in ('html', 'pdf', 'index', 'news')", name="ck_sources_kind"),
        sa.CheckConstraint(
            "state in ('healthy', 'degraded', 'unknown', 'disabled', 'blocked')",
            name="ck_sources_state",
        ),
    )
    op.create_index("ix_sources_bank_id", "sources", ["bank_id"])
    op.create_index("ix_sources_policy_id", "sources", ["policy_id"])
    op.create_index(
        "ix_sources_due_active",
        "sources",
        ["next_check_at"],
        postgresql_where=sa.text("state in ('healthy', 'degraded', 'unknown')"),
    )
    op.create_table(
        "job_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("type", sa.String(60), nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
        ),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=False)),
        sa.Column("scheduled_slot", sa.DateTime(timezone=True)),
        sa.Column("idempotency_key", sa.String(250), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("retry_at", sa.DateTime(timezone=True)),
        sa.Column("lease_token", postgresql.UUID(as_uuid=False)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("attempt >= 0 and max_attempts > 0", name="ck_job_runs_attempts"),
        sa.CheckConstraint(
            "state in ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_job_runs_state",
        ),
    )
    op.create_index("ix_job_runs_source_id", "job_runs", ["source_id"])
    op.create_index("ix_job_runs_state_retry", "job_runs", ["state", "retry_at"])
    op.create_index(
        "ix_job_runs_running_lease",
        "job_runs",
        ["lease_until"],
        postgresql_where=sa.text("state = 'running'"),
    )
    op.create_table(
        "source_versions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "blob_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("blobs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("source_id", "blob_id", name="uq_source_versions_source_blob"),
    )
    op.create_index("ix_source_versions_source_id", "source_versions", ["source_id"])
    op.create_index("ix_source_versions_blob_id", "source_versions", ["blob_id"])
    op.create_table(
        "source_fetches",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "job_run_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("job_runs.id", ondelete="RESTRICT"),
        ),
        sa.Column("requested_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text()),
        sa.Column("redirect_chain", postgresql.JSONB(), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("http_status", sa.Integer()),
        sa.Column("etag", sa.Text()),
        sa.Column("last_modified", sa.Text()),
        sa.Column("result", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column(
            "source_version_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("source_versions.id", ondelete="RESTRICT"),
        ),
        sa.CheckConstraint(
            "result in ('success', 'not_modified', 'rejected', 'error')",
            name="ck_source_fetches_result",
        ),
        sa.CheckConstraint(
            "http_status is null or http_status between 100 and 599",
            name="ck_source_fetches_http_status",
        ),
    )
    op.create_index("ix_source_fetches_source_id", "source_fetches", ["source_id"])
    op.create_index("ix_source_fetches_job_run_id", "source_fetches", ["job_run_id"])
    op.create_index("ix_source_fetches_source_version_id", "source_fetches", ["source_version_id"])
    op.create_index(
        "ix_source_fetches_source_fetched", "source_fetches", ["source_id", "fetched_at"]
    )

    banks = sa.table(
        "banks",
        sa.column("id", postgresql.UUID()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        banks,
        [
            {
                "id": "8a26f035-311f-4b01-a29d-08f1e3cc14f8",
                "code": "sber",
                "name": "Сбер",
                "active": True,
            },
            {
                "id": "37ff7414-fcc3-4ac9-aed2-6e745e4dce6d",
                "code": "vtb",
                "name": "ВТБ",
                "active": True,
            },
            {
                "id": "141aab85-5be0-4b68-8bc7-8429ea01f2fb",
                "code": "alfa",
                "name": "Альфа-Банк",
                "active": True,
            },
            {
                "id": "dc47c096-0645-4ec3-8f2a-1ff6218a328c",
                "code": "kuban_credit",
                "name": "Кубань Кредит",
                "active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("source_fetches")
    op.drop_table("source_versions")
    op.drop_table("job_runs")
    op.drop_table("sources")
    op.drop_table("blobs")
    op.drop_table("source_policies")
    op.drop_table("banks")
