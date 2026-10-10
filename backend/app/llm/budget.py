"""PostgreSQL token reservations for the configured local safety ceilings."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from app.llm.models import LLMUsage

_MOSCOW = ZoneInfo("Europe/Moscow")
_current_user: ContextVar[str | None] = ContextVar("llm_budget_user", default=None)


class BudgetRejected(Exception):
    """A local token or concurrency ceiling rejected a reservation."""


def set_budget_user(user_id: str | None) -> Token[str | None]:
    """Set the authenticated user for this async request context."""
    if user_id is not None:
        UUID(user_id)
    return _current_user.set(user_id)


def reset_budget_user(token: Token[str | None]) -> None:
    _current_user.reset(token)


def current_budget_user() -> str | None:
    return _current_user.get()


class PostgresTokenBudget:
    """Atomic daily reservations; unresolved dispatched calls consume their estimate."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        *,
        daily_token_limit: int,
        global_concurrency: int = 1,
        user_concurrency: int = 1,
    ) -> None:
        if min(daily_token_limit, global_concurrency, user_concurrency) <= 0:
            raise ValueError("BUDGET_LIMITS_MUST_BE_POSITIVE")
        self._factory = factory
        self.daily_token_limit = daily_token_limit
        self.global_concurrency = global_concurrency
        self.user_concurrency = user_concurrency

    async def reserve(
        self, request_id: UUID, user_id: str | None, tokens: int, model_id: str
    ) -> None:
        await asyncio.to_thread(self._reserve, request_id, user_id, tokens, model_id)

    async def settle(
        self,
        request_id: UUID,
        prompt_tokens: int,
        completion_tokens: int,
        *,
        estimated: bool,
    ) -> None:
        await asyncio.to_thread(
            self._settle, request_id, prompt_tokens, completion_tokens, estimated
        )

    async def release(self, request_id: UUID) -> None:
        await asyncio.to_thread(self._finish, request_id, "released")

    async def mark_unknown(self, request_id: UUID) -> None:
        """Retain reservation after dispatch if provider usage cannot be established."""
        await asyncio.to_thread(self._finish, request_id, "failed", estimated=True)

    def _reserve(self, request_id: UUID, user_id: str | None, tokens: int, model_id: str) -> None:
        if tokens <= 0:
            raise ValueError("BUDGET_RESERVATION_MUST_BE_POSITIVE")
        now = datetime.now(UTC)
        local_date = now.astimezone(_MOSCOW).date()
        start = datetime.combine(local_date, time.min, _MOSCOW).astimezone(UTC)
        end = start + timedelta(days=1)
        with self._factory() as session, session.begin():
            if session.bind is None or session.bind.dialect.name != "postgresql":
                raise RuntimeError("POSTGRES_REQUIRED_FOR_TOKEN_BUDGET")
            # Lock global first and user second, so all processes serialize admission consistently.
            self._advisory_lock(session, "llm-budget:global")
            if user_id is not None:
                self._advisory_lock(session, f"llm-budget:user:{user_id}")
            total = session.scalar(
                select(func.coalesce(func.sum(self._accounted_tokens()), 0)).where(
                    LLMUsage.window_started_at == start,
                    LLMUsage.created_at >= start,
                    LLMUsage.created_at < end,
                )
            )
            active_since = now - timedelta(minutes=2)
            active = session.scalar(
                select(func.count()).select_from(LLMUsage).where(
                    LLMUsage.state == "reserved", LLMUsage.created_at >= active_since
                )
            ) or 0
            user_active = 0
            if user_id is not None:
                user_active = session.scalar(
                    select(func.count()).select_from(LLMUsage).where(
                        LLMUsage.state == "reserved",
                        LLMUsage.created_at >= active_since,
                        LLMUsage.user_id == user_id,
                    )
                ) or 0
            if int(total or 0) + tokens > self.daily_token_limit:
                raise BudgetRejected
            if active >= self.global_concurrency or user_active >= self.user_concurrency:
                raise BudgetRejected
            session.add(
                LLMUsage(
                    request_id=str(request_id),
                    user_id=user_id,
                    window_started_at=start,
                    reserved_tokens=tokens,
                    estimated=True,
                    state="reserved",
                    model_id=model_id,
                )
            )

    @staticmethod
    def _accounted_tokens() -> ColumnElement[int]:
        return case(
            (LLMUsage.state == "settled", LLMUsage.actual_tokens),
            (LLMUsage.state.in_(("reserved", "failed")), LLMUsage.reserved_tokens),
            else_=0,
        )

    @staticmethod
    def _advisory_lock(session: Session, key: str) -> None:
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": key},
        )

    def _settle(
        self,
        request_id: UUID,
        prompt_tokens: int,
        completion_tokens: int,
        estimated: bool,
    ) -> None:
        with self._factory() as session, session.begin():
            row = session.get(LLMUsage, str(request_id), with_for_update=True)
            if row is None or row.state != "reserved":
                return
            row.prompt_tokens = prompt_tokens
            row.completion_tokens = completion_tokens
            row.actual_tokens = prompt_tokens + completion_tokens
            row.estimated = estimated
            row.state = "settled"

    def _finish(self, request_id: UUID, state: str, estimated: bool = False) -> None:
        with self._factory() as session, session.begin():
            row = session.get(LLMUsage, str(request_id), with_for_update=True)
            if row is not None and row.state == "reserved":
                row.state = state
                row.estimated = estimated


__all__ = [
    "BudgetRejected",
    "PostgresTokenBudget",
    "current_budget_user",
    "reset_budget_user",
    "set_budget_user",
]
