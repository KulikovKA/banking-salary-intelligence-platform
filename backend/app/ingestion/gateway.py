"""Single document egress boundary; requests are explicit and offline by default."""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import ssl
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin

import httpx2 as httpx

from app.config import Settings
from app.ingestion.errors import IngestionError, parse_retry_after
from app.ingestion.formats import MEDIA_TYPES, DocumentKind
from app.ingestion.policy import AcquisitionPolicy, public_ip, validate_url
from app.ingestion.robots import USER_AGENT, RobotsSnapshot, parse_robots
from app.ingestion.tls import build_tls_context
from app.ingestion.transport import FakeTransport, PinnedTransport, resolve_public
from app.storage.local import BlobReceipt, LocalBlobStore

PolicyLoader = Callable[[], AcquisitionPolicy]
Resolver = Callable[[str], tuple[str, ...]]


@dataclass(frozen=True)
class FetchResult:
    receipt: BlobReceipt
    status: int
    audit: dict[str, object]
    etag: str | None
    last_modified: str | None


def audit_list(audit: dict[str, object], key: str) -> list[object]:
    value = audit[key]
    assert isinstance(value, list)
    return value


class FetchGateway:
    _state_lock = threading.Lock()
    _host_locks: dict[str, threading.Lock] = {}
    _last_dispatch: dict[str, float] = {}

    def __init__(
        self,
        settings: Settings,
        store: LocalBlobStore,
        *,
        transport: FakeTransport | None = None,
        resolver: Resolver | None = None,
    ) -> None:
        self.settings, self.store = settings, store
        if transport is not None and (
            type(transport) is not FakeTransport or settings.app_env != "test"
        ):
            raise IngestionError("OFFLINE_EGRESS_BLOCKED")
        self.fake, self.transport = transport is not None, transport
        if self.fake and resolver is None:
            raise IngestionError("FAKE_RESOLVER_REQUIRED")
        self.resolver = resolver or resolve_public

    def _guard(self, loader: PolicyLoader, url: str, redirect: bool) -> AcquisitionPolicy:
        policy = loader()
        if self.fake:
            if policy.corpus_kind != "synthetic":
                raise IngestionError("CORPUS_INVALID")
        elif (
            self.settings.ingestion_mode != "live"
            or self.settings.app_env == "test"
            or os.environ.get("CI")
            or os.environ.get("PYTEST_CURRENT_TEST")
        ):
            raise IngestionError("OFFLINE_EGRESS_BLOCKED")
        elif policy.corpus_kind != "real":
            raise IngestionError("CORPUS_INVALID")
        policy.authorize(url, "automatic", redirect=redirect)
        return policy

    def fetch(
        self,
        url: str,
        kind: DocumentKind,
        loader: PolicyLoader,
        *,
        cached: BlobReceipt | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> FetchResult:
        audit: dict[str, object] = {
            "requested_url": url,
            "redirect_chain": [],
            "requests": [],
            "robots": [],
            "final_url": None,
            "http_status": None,
        }
        locks: dict[str, threading.Lock] = {}
        try:
            self._guard(loader, url, False)  # Before DNS, TLS factory or transport creation.
            transport = self.transport or PinnedTransport(
                build_tls_context(
                    self.settings.bank_fetch_tls_mode, self.settings.bank_fetch_extra_ca_file
                ),
                self.settings,
            )
            with httpx.Client(
                transport=transport,
                follow_redirects=False,
                trust_env=False,
                headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
            ) as client:
                return self._fetch(
                    client, url, kind, loader, audit, locks, cached, etag, last_modified
                )
        except Exception as exc:
            if isinstance(exc, IngestionError):
                failure = exc
            elif isinstance(exc, ssl.SSLCertVerificationError):
                code = (
                    "TLS_UNTRUSTED_ROOT"
                    if getattr(exc, "verify_code", None) in (18, 19, 20, 21, 2148204809)
                    else "TLS_CHAIN_INVALID"
                )
                failure = IngestionError(code)
            elif isinstance(exc, ssl.SSLEOFError):
                failure = IngestionError("TLS_HANDSHAKE_EOF")
            elif isinstance(exc, (TimeoutError, httpx.TimeoutException)):
                failure = IngestionError("CONNECT_TIMEOUT")
            elif isinstance(exc, ssl.SSLError):
                failure = IngestionError("TLS_CHAIN_INVALID")
            elif isinstance(exc, (OSError, httpx.TransportError, http.client.HTTPException)):
                failure = IngestionError("NETWORK_UNAVAILABLE")
            else:
                raise
            failure.audit = audit
            raise failure from None
        finally:
            for lock in locks.values():
                lock.release()

    def _fetch(
        self,
        client: httpx.Client,
        url: str,
        kind: DocumentKind,
        loader: PolicyLoader,
        audit: dict[str, object],
        locks: dict[str, threading.Lock],
        cached: BlobReceipt | None,
        etag: str | None,
        last_modified: str | None,
    ) -> FetchResult:
        deadline = time.monotonic() + self.settings.fetch_total_timeout_seconds
        robots: dict[str, RobotsSnapshot] = {}
        current = url
        for hop in range(self.settings.fetch_max_redirects + 1):
            redirect = hop > 0
            policy = self._guard(loader, current, redirect)
            host = validate_url(current)
            if host not in locks:
                with self._state_lock:
                    lock = self._host_locks.setdefault(host, threading.Lock())
                if not lock.acquire(blocking=False):
                    raise IngestionError("HOST_BUSY", retry_after=policy.rate_seconds)
                locks[host] = lock
            if host not in robots:
                robot_url = f"https://{host}/robots.txt"
                with closing(self._request(client, robot_url, loader, False, deadline, audit)) as r:
                    body = self._read(r, 512 * 1024, deadline)
                    raw_snapshot: dict[str, object] = {
                        "url": robot_url,
                        "status": r.status_code,
                        "raw_base64": base64.b64encode(body).decode(),
                        "sha256": hashlib.sha256(body).hexdigest(),
                        "user_agent": USER_AGENT,
                        "checked_at": datetime.now(UTC).isoformat(),
                        "matched_groups": [],
                    }
                    audit_list(audit, "robots").append(raw_snapshot)
                    if r.status_code in (403, 429) or r.status_code >= 500:
                        self._check_status(r)
                    snapshot = parse_robots(robot_url, r.status_code, body)
                    robots[host] = snapshot
                    raw_snapshot.update(snapshot.audit())
            robots[host].check(current)
            headers: dict[str, str] = {}
            if cached is not None and current == url:
                self.store.verify(cached)
                if cached.corpus_kind != policy.corpus_kind:
                    raise IngestionError("CORPUS_INVALID")
                if etag:
                    headers["If-None-Match"] = etag
                if last_modified:
                    headers["If-Modified-Since"] = last_modified
            with closing(
                self._request(client, current, loader, redirect, deadline, audit, headers)
            ) as r:
                status = r.status_code
                audit["http_status"], audit["final_url"] = status, current
                if status in (301, 302, 303, 307, 308):
                    location = r.headers.get("location")
                    if not location:
                        raise IngestionError("REDIRECT_INVALID")
                    target = urljoin(current, location)
                    self._guard(loader, target, True)  # Before target DNS/robots/socket.
                    audit_list(audit, "redirect_chain").append(target)
                    current = target
                    continue
                self._check_status(r)
                if status == 304:
                    if cached is None or current != url or not headers:
                        raise IngestionError("CACHE_MISSING")
                    self.store.verify(cached)
                    return FetchResult(cached, 304, audit, etag, last_modified)
                media = r.headers.get("content-type", "").split(";")[0].strip().lower()
                if media != MEDIA_TYPES[kind]:
                    prefix = self._read(r, 65536, deadline)
                    if b"user_blocked" in prefix.lower() or b"captcha" in prefix.lower():
                        raise IngestionError("CHALLENGE")
                    raise IngestionError("FORMAT_INVALID")
                receipt = self.store.put(self._chunks(r, deadline), kind, policy.corpus_kind)
                return FetchResult(
                    receipt, status, audit, r.headers.get("etag"), r.headers.get("last-modified")
                )
        raise IngestionError("REDIRECT_LIMIT")

    def _request(
        self,
        client: httpx.Client,
        url: str,
        loader: PolicyLoader,
        redirect: bool,
        deadline: float,
        audit: dict[str, object],
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        policy = self._guard(loader, url, redirect)
        host = validate_url(url)
        wait = self._last_dispatch.get(host, -float("inf")) + policy.rate_seconds - time.monotonic()
        if wait > 0:
            if wait >= deadline - time.monotonic():
                raise IngestionError("REQUEST_RATE_LIMIT", retry_after=wait)
            time.sleep(wait)
        addresses = (
            self.resolver(host)
            if self.fake
            else resolve_public(
                host,
                max(
                    0.001,
                    min(self.settings.fetch_connect_timeout_seconds, deadline - time.monotonic()),
                ),
            )
        )
        if not addresses:
            raise IngestionError("NETWORK_UNAVAILABLE")
        ips = tuple(public_ip(ip) for ip in addresses)
        policy = self._guard(loader, url, redirect)
        if time.monotonic() >= deadline:
            raise IngestionError("CONNECT_TIMEOUT")
        self._last_dispatch[host] = time.monotonic()
        request = client.build_request(
            "GET",
            url,
            headers=headers,
            extensions={
                "pinned_ip": ips[0],
                "deadline": deadline,
                "connect_timeout": self.settings.fetch_connect_timeout_seconds,
                "read_timeout": self.settings.fetch_read_timeout_seconds,
                "redirect": redirect,
                "dispatch_guard": lambda: self._audit_guard(loader, url, redirect, event),
            },
        )
        client.cookies.clear()
        event: dict[str, object] = {
            "url": url,
            "host": host,
            "pinned_ip": ips[0],
            "status": None,
            "dispatched_at": datetime.now(UTC).isoformat(),
            "policy_sha256": hashlib.sha256(
                json.dumps(policy.model_dump(mode="json"), sort_keys=True).encode()
            ).hexdigest(),
            "approval": policy.model_dump(mode="json"),
        }
        audit_list(audit, "requests").append(event)
        response = client.send(request, stream=True)
        event["status"] = response.status_code
        if time.monotonic() >= deadline:
            response.close()
            raise IngestionError("READ_TIMEOUT")
        if self.fake and public_ip(str(response.extensions.get("peer_ip", ips[0]))) != ips[0]:
            response.close()
            raise IngestionError("SSRF_PEER_MISMATCH")
        if response.headers.get("content-encoding", "identity") != "identity":
            response.close()
            raise IngestionError("FORMAT_INVALID")
        return response

    def _audit_guard(
        self, loader: PolicyLoader, url: str, redirect: bool, event: dict[str, object]
    ) -> AcquisitionPolicy:
        policy = self._guard(loader, url, redirect)
        event["approval"] = policy.model_dump(mode="json")
        event["policy_sha256"] = hashlib.sha256(
            json.dumps(policy.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        return policy

    @staticmethod
    def _chunks(response: httpx.Response, deadline: float) -> Iterator[bytes]:
        declared = response.headers.get("content-length")
        expected = None
        if declared is not None:
            try:
                expected = int(declared)
                if expected < 0:
                    raise ValueError("Invalid length")
            except ValueError as exc:
                raise IngestionError("FORMAT_INVALID") from exc
        received = 0
        for chunk in response.iter_raw():
            if time.monotonic() >= deadline:
                raise IngestionError("READ_TIMEOUT")
            received += len(chunk)
            if expected is not None and received > expected:
                raise IngestionError("FORMAT_INVALID")
            yield chunk
        if expected is not None and received != expected:
            raise IngestionError("NETWORK_UNAVAILABLE")

    def _read(self, response: httpx.Response, maximum: int, deadline: float) -> bytes:
        parts: list[bytes] = []
        size = 0
        for chunk in self._chunks(response, deadline):
            size += len(chunk)
            if size > maximum:
                raise IngestionError("SIZE_LIMIT")
            parts.append(chunk)
        return b"".join(parts)

    @staticmethod
    def _check_status(response: httpx.Response) -> None:
        status = response.status_code
        if status == 403:
            raise IngestionError("HTTP_FORBIDDEN")
        if status == 429:
            raise IngestionError(
                "HTTP_RATE_LIMIT",
                retry_after=parse_retry_after(
                    response.headers.get("retry-after"), datetime.now(UTC)
                ),
            )
        if status >= 500:
            raise IngestionError("HTTP_UNAVAILABLE")
        if status not in (200, 304):
            raise IngestionError("HTTP_REJECTED")
