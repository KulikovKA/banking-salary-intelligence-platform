"""Idempotent job enqueueing; callers own and commit the transaction."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.registry.models import JobRun


class JobKeyConflict(ValueError):
    """An idempotency key was reused for a different job payload."""


def enqueue_job(
    session: Session,
    *,
    job_type: str,
    idempotency_key: str,
    payload: dict[str, Any],
    source_id: str | None = None,
    max_attempts: int = 3,
) -> JobRun:
    """Insert once; return the existing row only when the request matches."""
    statement = insert(JobRun).values(
        type=job_type,
        idempotency_key=idempotency_key,
        payload=payload,
        source_id=source_id,
        state="queued",
        attempt=0,
        max_attempts=max_attempts,
        metrics={},
    )
    session.execute(statement.on_conflict_do_nothing(index_elements=[JobRun.idempotency_key]))
    job = session.scalar(select(JobRun).where(JobRun.idempotency_key == idempotency_key))
    if job is None:
        raise RuntimeError("JOB_ENQUEUE_FAILED: inserted or existing job could not be read")
    if (
        job.type != job_type
        or job.source_id != source_id
        or job.payload != payload
        or job.max_attempts != max_attempts
    ):
        raise JobKeyConflict("JOB_IDEMPOTENCY_CONFLICT: key is already used by another job")
    return job
