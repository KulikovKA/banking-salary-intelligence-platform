import socket
import ssl

import pytest

from app.ingestion.errors import IngestionError
from app.ingestion.transport import PinnedConnection, PinnedTransport, resolve_public


def test_pinned_socket_uses_no_dns_and_preserves_tls_hostname(monkeypatch):
    events = []

    class Socket:
        def settimeout(self, value):
            pass

        def connect(self, address):
            events.append(address)

        def getpeername(self):
            return ("93.184.216.34", 443)

        def close(self):
            pass

    ctx = ssl.create_default_context()
    sock = Socket()

    def wrap(self, raw, server_hostname):
        assert raw is sock
        events.append(server_hostname)
        return sock

    monkeypatch.setattr(socket, "socket", lambda *args: sock)
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *args, **kwargs: pytest.fail("second DNS lookup")
    )
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap)
    connection = PinnedConnection("example.com", "93.184.216.34", ctx, 1, lambda: None)
    connection.connect()
    assert events == [("93.184.216.34", 443), "example.com"]


def test_actual_peer_rejected_before_tls_or_http(monkeypatch):
    class Socket:
        def settimeout(self, value):
            pass

        def connect(self, address):
            pass

        def getpeername(self):
            return ("127.0.0.1", 443)

        def close(self):
            pass

    ctx = ssl.create_default_context()
    monkeypatch.setattr(socket, "socket", lambda *args: Socket())
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", lambda *args, **kw: pytest.fail("TLS sent"))
    with pytest.raises(IngestionError, match="SSRF_BLOCKED"):
        PinnedConnection("example.com", "93.184.216.34", ctx, 1, lambda: None).connect()


def test_pinned_transport_refuses_unverified_context():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    with pytest.raises(IngestionError, match="TLS_CONFIG_INVALID"):
        PinnedTransport(ctx)


def test_transport_itself_fails_closed_offline(monkeypatch):
    import httpx2 as httpx

    monkeypatch.setattr(socket, "socket", lambda *args: pytest.fail("offline socket"))
    transport = PinnedTransport(ssl.create_default_context())
    with pytest.raises(IngestionError, match="OFFLINE_EGRESS_BLOCKED"):
        transport.handle_request(httpx.Request("GET", "https://example.com/doc.pdf"))


def test_dns_resolution_has_a_deadline(monkeypatch):
    import threading

    event = threading.Event()
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: event.wait(0.05) or [])
    with pytest.raises(IngestionError, match="CONNECT_TIMEOUT"):
        resolve_public("example.com", timeout=0.001)
    event.set()
