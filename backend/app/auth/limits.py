"""Small single-process sliding-window limiter for the single API instance."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class LoginLimiter:
    def __init__(self, *, window_seconds: int = 60, account_limit: int = 5, ip_limit: int = 20):
        self.window_seconds = window_seconds
        self.account_limit = account_limit
        self.ip_limit = ip_limit
        self._lock = threading.Lock()
        self._accounts: dict[str, deque[float]] = defaultdict(deque)
        self._ips: dict[str, deque[float]] = defaultdict(deque)
        self._requests = 0

    def check_and_record(self, account_key: str, ip_key: str, now: float | None = None) -> bool:
        timestamp = time.monotonic() if now is None else now
        cutoff = timestamp - self.window_seconds
        with self._lock:
            if (
                account_key not in self._accounts
                and len(self._accounts) >= 10000
                or ip_key not in self._ips
                and len(self._ips) >= 10000
            ):
                self._prune(cutoff)
                if (
                    account_key not in self._accounts
                    and len(self._accounts) >= 10000
                    or ip_key not in self._ips
                    and len(self._ips) >= 10000
                ):
                    return False
            account_hits = self._accounts[account_key]
            ip_hits = self._ips[ip_key]
            for hits in (account_hits, ip_hits):
                while hits and hits[0] <= cutoff:
                    hits.popleft()
            allowed = len(account_hits) < self.account_limit and len(ip_hits) < self.ip_limit
            if len(account_hits) < self.account_limit:
                account_hits.append(timestamp)
            if len(ip_hits) < self.ip_limit:
                ip_hits.append(timestamp)
            self._requests += 1
            if self._requests % 256 == 0:
                self._prune(cutoff)
            return allowed

    def _prune(self, cutoff: float) -> None:
        for buckets in (self._accounts, self._ips):
            for key, hits in list(buckets.items()):
                while hits and hits[0] <= cutoff:
                    hits.popleft()
                if not hits:
                    buckets.pop(key, None)
