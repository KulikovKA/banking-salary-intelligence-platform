"""PostgreSQL records for users, one-time tokens, and server-side sessions."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.registry.models import uuid_pk


class AuthUser(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role in ('admin', 'analyst')", name="ck_users_role"),
        CheckConstraint("length(login) between 3 and 254", name="ck_users_login_length"),
    )

    id: Mapped[str] = uuid_pk()
    login: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="analyst")
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AuthInvitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("role in ('admin', 'analyst')", name="ck_invitations_role"),
        CheckConstraint("length(token_hash) = 64", name="ck_invitations_hash_length"),
        CheckConstraint("expires_at > created_at", name="ck_invitations_expiry"),
        Index("ix_invitations_login_created", "login", "created_at"),
    )

    id: Mapped[str] = uuid_pk()
    login: Mapped[str] = mapped_column(String(254), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    issuer_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthPasswordReset(Base):
    __tablename__ = "password_resets"
    __table_args__ = (
        CheckConstraint("length(token_hash) = 64", name="ck_password_resets_hash_length"),
        CheckConstraint("expires_at > created_at", name="ck_password_resets_expiry"),
    )

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    issuer_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("length(token_hash) = 64", name="ck_sessions_hash_length"),
        CheckConstraint("length(csrf_hash) = 64", name="ck_sessions_csrf_hash_length"),
        CheckConstraint("absolute_expires_at > created_at", name="ck_sessions_expiry"),
        Index("ix_sessions_user_active", "user_id", "revoked_at"),
    )

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthAudit(Base):
    __tablename__ = "auth_audit"
    __table_args__ = (Index("ix_auth_audit_created_at", "created_at"),)

    id: Mapped[str] = uuid_pk()
    actor_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    event_code: Mapped[str] = mapped_column(String(48), nullable=False)
    subject_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
