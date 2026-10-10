"""httpx2 transport connecting to a checked IP without a second DNS lookup.

No proxies, no connection pooling, no redirects, no cookies. TLS SNI/hostname
remain the original DNS name. Peer validation happens before HTTP bytes.
"""

from __future__ import annotations

import http.client
import os
import queue
import socket
import ssl
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx2 as httpx

from app.config import Settings
from app.ingestion.errors import IngestionError
from app.ingestion.policy import AcquisitionPolicy, public_ip, validate_url


class FakeTransport(httpx.MockTransport):
    """Explicit test seam: permitted only for synthetic offline contract tests."""


def resolve_public(host: str, timeout: float = 5) -> tuple[str, ...]:
    results: queue.Queue[tuple[str, ...] | Exception] = queue.Queue(maxsize=1)

    def lookup() -> None:
        try:
            results.put(_resolve_public(host))
        except Exception as exc:
            results.put(exc)

    threading.Thread(target=lookup, daemon=True).start()
    try:
        result = results.get(timeout=timeout)
    except queue.Empty as exc:
        raise IngestionError("CONNECT_TIMEOUT") from exc
    if isinstance(result, Exception):
        raise result
    return result


def _resolve_public(host: str) -> tuple[str, ...]:
    try:
        addresses = tuple(
            dict.fromkeys(
                public_ip(str(info[4][0]))
                for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            )
        )
        if not addresses:
            raise IngestionError("NETWORK_UNAVAILABLE")
        return addresses
    except OSError as exc:
        raise IngestionError("NETWORK_UNAVAILABLE") from exc


class PinnedConnection(http.client.HTTPSConnection):
    def __init__(
        self, host: str, ip: str, context: ssl.SSLContext, timeout: float, guard: Callable[[], None]
    ) -> None:
        super().__init__(host, port=443, context=context, timeout=timeout)
        self.ip = public_ip(ip)
        self.guard = guard
        self.context = context

    def connect(self) -> None:
        self.guard()
        family = socket.AF_INET6 if ":" in self.ip else socket.AF_INET
        raw = socket.socket(family, socket.SOCK_STREAM)
        try:
            assert self.timeout is not None
            connect_deadline = time.monotonic() + self.timeout
            raw.settimeout(self.timeout)
            raw.connect((self.ip, 443))
            if public_ip(raw.getpeername()[0]) != self.ip:
                raise IngestionError("SSRF_PEER_MISMATCH")
            remaining = connect_deadline - time.monotonic()
            if remaining <= 0:
                raise IngestionError("CONNECT_TIMEOUT")
            raw.settimeout(remaining)
            self.sock = self.context.wrap_socket(raw, server_hostname=self.host)
            if public_ip(self.sock.getpeername()[0]) != self.ip:
                raise IngestionError("SSRF_PEER_MISMATCH")
            self.guard()
        except BaseException:
            raw.close()
            if self.sock is not None:
                self.sock.close()
            raise


class ResponseStream(httpx.SyncByteStream):
    def __init__(
        self,
        response: http.client.HTTPResponse,
        connection: PinnedConnection,
        deadline: float,
        read_timeout: float,
        timer: threading.Timer,
    ) -> None:
        self.response = response
        self.connection = connection
        self.deadline = deadline
        self.read_timeout = read_timeout
        self.timer = timer

    def __iter__(self) -> Iterator[bytes]:
        while True:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise IngestionError("READ_TIMEOUT")
            if self.connection.sock is not None:
                self.connection.sock.settimeout(min(self.read_timeout, remaining))
            try:
                chunk = self.response.read1(65536)
            except TimeoutError as exc:
                raise IngestionError("READ_TIMEOUT") from exc
            if time.monotonic() >= self.deadline:
                raise IngestionError("READ_TIMEOUT")
            if not chunk:
                if self.response.length not in (None, 0):
                    raise IngestionError("NETWORK_UNAVAILABLE")
                break
            yield chunk

    def close(self) -> None:
        self.timer.cancel()
        self.response.close()
        self.connection.close()


class PinnedTransport(httpx.BaseTransport):
    def __init__(self, context: ssl.SSLContext, settings: Settings | None = None) -> None:
        if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
            raise IngestionError("TLS_CONFIG_INVALID")
        self.context = context
        self.settings = settings or Settings()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if (
            self.settings.ingestion_mode != "live"
            or self.settings.app_env == "test"
            or os.environ.get("CI")
            or os.environ.get("PYTEST_CURRENT_TEST")
        ):
            raise IngestionError("OFFLINE_EGRESS_BLOCKED")
        host = validate_url(str(request.url))
        extensions: dict[str, Any] = request.extensions
        guard = extensions.get("dispatch_guard")
        if request.method != "GET" or not callable(guard):
            raise IngestionError("POLICY_BLOCKED")

        def authorize_dispatch() -> None:
            policy = guard()
            if not isinstance(policy, AcquisitionPolicy) or policy.corpus_kind != "real":
                raise IngestionError("POLICY_BLOCKED")
            policy.authorize(
                str(request.url), "automatic", redirect=bool(extensions.get("redirect"))
            )

        deadline = float(extensions["deadline"])
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise IngestionError("CONNECT_TIMEOUT")
        connection = PinnedConnection(
            host,
            str(extensions["pinned_ip"]),
            self.context,
            min(float(extensions["connect_timeout"]), remaining),
            authorize_dispatch,
        )
        timer: threading.Timer | None = None
        try:
            connection.connect()

            def abort_socket() -> None:
                if connection.sock is not None:
                    try:
                        connection.sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

            timer = threading.Timer(max(0, deadline - time.monotonic()), abort_socket)
            timer.daemon = True
            timer.start()
            authorize_dispatch()
            connection.request(
                "GET", request.url.raw_path.decode("ascii"), headers=dict(request.headers)
            )
            if connection.sock is not None:
                connection.sock.settimeout(
                    min(float(extensions["read_timeout"]), max(0.001, deadline - time.monotonic()))
                )
            response = connection.getresponse()
            if time.monotonic() >= deadline:
                raise IngestionError("READ_TIMEOUT")
            return httpx.Response(
                response.status,
                headers=response.getheaders(),
                stream=ResponseStream(
                    response, connection, deadline, float(extensions["read_timeout"]), timer
                ),
            )
        except BaseException:
            if timer is not None:
                timer.cancel()
            connection.close()
            raise
