"""Register operator sources without scheduler fields; retain existing audit data.

Revision ID: 0003_operator_only
Revises: 0002_source_recovery
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_operator_only"
down_revision: str | None = "0002_source_recovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Inert default satisfies the original NOT NULL/CHECK. It schedules nothing.
    op.alter_column(
        "sources", "schedule_seconds", existing_type=sa.Integer(), server_default=sa.text("1")
    )


def downgrade() -> None:
    op.alter_column(
        "sources", "schedule_seconds", existing_type=sa.Integer(), server_default=None
    )
