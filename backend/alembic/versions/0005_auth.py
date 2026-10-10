"""Add closed-application users, one-time tokens, sessions, and audit.

Revision ID: 0005_auth
Revises: 0004a_corpus_gates
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_auth"
down_revision: str | None = "0004a_corpus_gates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("login", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("role in ('admin', 'analyst')", name="ck_users_role"),
        sa.CheckConstraint("length(login) between 3 and 254", name="ck_users_login_length"),
        sa.UniqueConstraint("login", name="uq_users_login"),
    )
    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("login", sa.String(254), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("issuer_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["issuer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("role in ('admin', 'analyst')", name="ck_invitations_role"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_invitations_hash_length"),
        sa.CheckConstraint("expires_at > created_at", name="ck_invitations_expiry"),
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
    )
    op.create_index("ix_invitations_login_created", "invitations", ["login", "created_at"])
    op.create_table(
        "password_resets",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("issuer_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["issuer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_password_resets_hash_length"),
        sa.CheckConstraint("expires_at > created_at", name="ck_password_resets_expiry"),
        sa.UniqueConstraint("token_hash", name="uq_password_resets_token_hash"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_sessions_hash_length"),
        sa.CheckConstraint("length(csrf_hash) = 64", name="ck_sessions_csrf_hash_length"),
        sa.CheckConstraint("absolute_expires_at > created_at", name="ck_sessions_expiry"),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index("ix_sessions_user_active", "sessions", ["user_id", "revoked_at"])
    op.create_table(
        "auth_audit",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=False)),
        sa.Column("event_code", sa.String(48), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=False)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_auth_audit_created_at", "auth_audit", ["created_at"])
    op.create_foreign_key(
        "fk_fact_reviews_user_id",
        "fact_reviews",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_llm_usage_user_id",
        "llm_usage",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_llm_usage_user_id", "llm_usage", type_="foreignkey")
    op.drop_constraint("fk_fact_reviews_user_id", "fact_reviews", type_="foreignkey")
    op.drop_index("ix_auth_audit_created_at", table_name="auth_audit")
    op.drop_table("auth_audit")
    op.drop_index("ix_sessions_user_active", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("password_resets")
    op.drop_index("ix_invitations_login_created", table_name="invitations")
    op.drop_table("invitations")
    op.drop_table("users")
