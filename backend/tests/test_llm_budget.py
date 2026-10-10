"""PostgreSQL-only reservation checks; never substitute SQLite for advisory locks."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.llm.budget import BudgetRejected, PostgresTokenBudget
from app.llm.models import LLMUsage


@pytest.fixture
def budget_factory():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured for dedicated PostgreSQL integration")
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name != "postgresql":
        engine.dispose()
        pytest.skip("token reservations require PostgreSQL advisory locks")
    factory = sessionmaker(engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def reserve(budget: PostgresTokenBudget, request_id, user_id: str, tokens: int = 100) -> bool:
    try:
        asyncio.run(budget.reserve(request_id, user_id, tokens, "openai/gpt-oss-120b"))
        return True
    except BudgetRejected:
        return False


def test_concurrent_reservations_are_serialized_per_global_ceiling(budget_factory) -> None:
    ids = [uuid4(), uuid4()]
    users = [str(uuid4()), str(uuid4())]
    budget = PostgresTokenBudget(
        budget_factory, daily_token_limit=10_000, global_concurrency=1, user_concurrency=1
    )
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(
                pool.map(lambda item: reserve(budget, *item), zip(ids, users, strict=True))
            )
        assert sorted(outcomes) == [False, True]
    finally:
        with budget_factory() as session, session.begin():
            session.execute(delete(LLMUsage).where(LLMUsage.request_id.in_([str(i) for i in ids])))


def test_unknown_usage_keeps_daily_reservation_and_crashed_reservation_releases_concurrency(
    budget_factory,
) -> None:
    unknown_id, crash_id, next_id, next_id2 = uuid4(), uuid4(), uuid4(), uuid4()
    user = str(uuid4())
    budget = PostgresTokenBudget(
        budget_factory, daily_token_limit=100, global_concurrency=1, user_concurrency=1
    )
    try:
        asyncio.run(budget.reserve(unknown_id, user, 100, "openai/gpt-oss-120b"))
        asyncio.run(budget.mark_unknown(unknown_id))
        with pytest.raises(BudgetRejected):
            asyncio.run(budget.reserve(next_id, user, 1, "openai/gpt-oss-120b"))

        # Remove the unknown-usage fixture, then simulate a crash using an old row.
        with budget_factory() as session, session.begin():
            session.execute(delete(LLMUsage).where(LLMUsage.request_id == str(unknown_id)))
            now = datetime.now(UTC)
            old = now - timedelta(minutes=3)
            window_start = now.astimezone(ZoneInfo("Europe/Moscow")).replace(
                hour=0, minute=0, second=0, microsecond=0
            ).astimezone(UTC)
            session.add(
                LLMUsage(
                    request_id=str(crash_id),
                    user_id=user,
                    window_started_at=window_start,
                    created_at=old,
                    reserved_tokens=1,
                    estimated=True,
                    state="reserved",
                    model_id="openai/gpt-oss-120b",
                )
            )
        # Stale reservations still consume daily tokens but no longer block the
        # global/user in-flight concurrency slot after a crashed process.
        assert reserve(budget, next_id, user, 99)
        with pytest.raises(BudgetRejected):
            asyncio.run(budget.reserve(next_id2, user, 1, "openai/gpt-oss-120b"))
    finally:
        with budget_factory() as session, session.begin():
            session.execute(
                delete(LLMUsage).where(
                    LLMUsage.request_id.in_(
                        [str(unknown_id), str(crash_id), str(next_id), str(next_id2)]
                    )
                )
            )
