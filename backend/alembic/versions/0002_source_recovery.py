"""Exact acquisition grants, corpus separation, quarantine and manual observations."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_source_recovery"
down_revision: str | None = "0001_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_policies",
        sa.Column(
            "acquisition_config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.drop_constraint("ck_sources_kind", "sources", type_="check")
    op.create_check_constraint(
        "ck_sources_kind", "sources", "kind in ('html','pdf','xlsx','index','news')"
    )
    for table in ("sources", "blobs"):
        op.add_column(
            table, sa.Column("corpus_kind", sa.String(20), nullable=False, server_default="real")
        )
        op.create_check_constraint(
            f"ck_{table}_corpus", table, "corpus_kind in ('real','synthetic')"
        )
    op.drop_constraint("blobs_sha256_key", "blobs", type_="unique")
    op.create_unique_constraint("uq_blobs_corpus_sha256", "blobs", ["corpus_kind", "sha256"])
    op.add_column(
        "source_versions",
        sa.Column("content_state", sa.String(20), nullable=False, server_default="quarantine"),
    )
    op.add_column("source_versions", sa.Column("accepted_at", sa.DateTime(timezone=True)))
    op.add_column("source_versions", sa.Column("accepted_by", sa.String(200)))
    op.create_check_constraint(
        "ck_source_versions_content_state",
        "source_versions",
        "content_state in ('quarantine','accepted','rejected')",
    )
    op.add_column(
        "source_fetches",
        sa.Column("acquisition_method", sa.String(20), nullable=False, server_default="automatic"),
    )
    op.add_column(
        "source_fetches",
        sa.Column(
            "audit_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.drop_constraint("ck_source_fetches_result", "source_fetches", type_="check")
    op.create_check_constraint(
        "ck_source_fetches_result",
        "source_fetches",
        "result in ('success','not_modified','rejected','error','manual_imported')",
    )
    op.create_check_constraint(
        "ck_source_fetches_method", "source_fetches", "acquisition_method in ('automatic','manual')"
    )
    op.create_check_constraint(
        "ck_source_fetches_manual",
        "source_fetches",
        "result != 'manual_imported' or (acquisition_method = 'manual' and http_status is null)",
    )


def downgrade() -> None:
    # Collapsing corpus/history loses provenance; never silently perform that operation.
    raise RuntimeError("SOURCE_RECOVERY_DOWNGRADE_REQUIRES_REVIEW")
