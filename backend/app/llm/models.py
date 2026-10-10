"""Provider usage accounting schema; no provider or reservation service lives here."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LLMUsage(Base):
    __tablename__ = "llm_usage"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_llm_usage_user_id", ondelete="RESTRICT"
        ),
        CheckConstraint("window_started_at <= created_at", name="ck_llm_usage_window_start"),
        CheckConstraint("reserved_tokens > 0", name="ck_llm_usage_reserved_positive"),
        CheckConstraint(
            "prompt_tokens is null or prompt_tokens >= 0",
            name="ck_llm_usage_prompt_tokens",
        ),
        CheckConstraint(
            "completion_tokens is null or completion_tokens >= 0",
            name="ck_llm_usage_completion_tokens",
        ),
        CheckConstraint(
            "actual_tokens is null or actual_tokens >= 0",
            name="ck_llm_usage_actual_tokens",
        ),
        CheckConstraint(
            "state in ('reserved', 'settled', 'released', 'failed')", name="ck_llm_usage_state"
        ),
        CheckConstraint(
            "(state = 'settled' and prompt_tokens is not null and completion_tokens is not null "
            "and actual_tokens = prompt_tokens + completion_tokens) or "
            "(state != 'settled' and actual_tokens is null)",
            name="ck_llm_usage_settled_tokens",
        ),
        Index("ix_llm_usage_user_window", "user_id", "window_started_at"),
        Index("ix_llm_usage_state_created", "state", "created_at"),
    )

    request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reserved_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    actual_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated: Mapped[bool] = mapped_column(nullable=False, default=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="reserved")
    model_id: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
