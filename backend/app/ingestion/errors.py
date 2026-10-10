"""Public, secret-safe ingestion failures and scheduler retry decisions."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime


class IngestionError(Exception):
    def __init__(self, code: str, *, retry_after: float | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after
        self.audit: dict[str, object] = {}


TRANSIENT = {
    "CONNECT_TIMEOUT",
    "READ_TIMEOUT",
    "TLS_HANDSHAKE_EOF",
    "HTTP_UNAVAILABLE",
    "HTTP_RATE_LIMIT",
    "NETWORK_UNAVAILABLE",
    "HOST_BUSY",
    "REQUEST_RATE_LIMIT",
}


def retry_at(
    error: IngestionError, attempt: int, *, max_attempts: int = 3, now: datetime | None = None
) -> datetime | None:
    if error.code not in TRANSIENT or attempt >= max_attempts:
        return None
    delay = max(error.retry_after or 0, min(300, 2 ** max(1, attempt)) + random.random())
    return (now or datetime.now(UTC)) + timedelta(seconds=delay)


def parse_retry_after(value: str | None, now: datetime) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
        return max(0, seconds) if seconds < float("inf") else None
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            return max(0, (date - now).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return None
