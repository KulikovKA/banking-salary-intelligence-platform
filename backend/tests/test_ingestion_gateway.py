import ssl
from datetime import UTC, datetime, timedelta

import httpx2 as httpx
import pytest

from app.config import Settings
from app.ingestion.errors import IngestionError, retry_at
from app.ingestion.gateway import FetchGateway
from app.ingestion.policy import AcquisitionPolicy
from app.ingestion.transport import FakeTransport
from app.storage.local import LocalBlobStore

BASE = "https://example.com"
URL = BASE + "/doc.pdf"


def policy(**changes):
    values = dict(
        source_id="synthetic",
        decision="approved",
        allowed_urls=(URL, BASE + "/robots.txt"),
        method="automatic",
        corpus_kind="synthetic",
        reviewer="tester",
        official_relationship="synthetic",
        acquisition_basis="test",
        storage_basis="test",
        reuse_basis="test",
        terms_evidence="test",
        purpose="contract test",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        rate_seconds=0.001,
    )
    return AcquisitionPolicy(**(values | changes))


def response(status=200, body=b"%PDF-1.7\nsynthetic\n%%EOF", media="application/pdf", **headers):
    return httpx.Response(status, headers={"content-type": media, **headers}, content=iter([body]))


def gateway(tmp_path, handler=None, resolver=None, max_bytes=1024):
    calls = []

    def dispatch(request):
        calls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return response(body=b"User-agent: *\nAllow: /", media="text/plain")
        return handler(request) if handler else response()

    g = FetchGateway(
        Settings(app_env="test"),
        LocalBlobStore(tmp_path, max_bytes),
        transport=FakeTransport(dispatch),
        resolver=resolver or (lambda _: ("93.184.216.34",)),
    )
    return g, calls


def test_success_and_cached_304(tmp_path):
    g, calls = gateway(tmp_path)
    first = g.fetch(URL, "pdf", lambda: policy())
    assert first.receipt.byte_size > 0
    assert calls == [BASE + "/robots.txt", URL]
    assert first.audit["robots"]
    g, calls = gateway(tmp_path, lambda _: response(304))
    second = g.fetch(URL, "pdf", lambda: policy(), cached=first.receipt, etag='"v1"')
    assert first.receipt == second.receipt and second.status == 304


@pytest.mark.parametrize(
    "changes",
    [
        {"decision": "pending"},
        {"decision": "denied"},
        {"revoked": True},
        {"expires_at": datetime.now(UTC) - timedelta(days=1)},
        {"allowed_urls": ()},
        {"storage_basis": ""},
        {"method": "manual"},
    ],
)
def test_policy_prevents_all_transport_calls(tmp_path, changes):
    g, calls = gateway(tmp_path)
    with pytest.raises(IngestionError, match="POLICY_BLOCKED"):
        g.fetch(URL, "pdf", lambda: policy(**changes))
    assert calls == []


def test_offline_blocks_before_dns_or_transport(tmp_path):
    def forbidden(_):
        pytest.fail("offline must not resolve DNS")

    g = FetchGateway(Settings(), LocalBlobStore(tmp_path), resolver=forbidden)
    with pytest.raises(IngestionError, match="OFFLINE_EGRESS_BLOCKED"):
        g.fetch(URL, "pdf", lambda: policy())


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "::1",
        "fe80::1",
        "fc00::1",
        "100.100.100.200",
        "168.63.129.16",
        "::ffff:127.0.0.1",
        "2002:7f00:1::",
    ],
)
def test_ssrf_is_blocked_before_send(tmp_path, ip):
    g, calls = gateway(tmp_path, resolver=lambda _: (ip,))
    with pytest.raises(IngestionError, match="SSRF_BLOCKED"):
        g.fetch(URL, "pdf", lambda: policy())
    assert calls == []


def test_rebinding_between_requests_and_peer_mismatch(tmp_path):
    resolutions = iter([("93.184.216.34",), ("127.0.0.1",)])
    g, calls = gateway(tmp_path, resolver=lambda _: next(resolutions))
    with pytest.raises(IngestionError, match="SSRF_BLOCKED"):
        g.fetch(URL, "pdf", lambda: policy())
    assert calls == [BASE + "/robots.txt"]

    def mismatch(_):
        r = response()
        r.extensions["peer_ip"] = "93.184.216.35"
        return r

    g, _ = gateway(tmp_path, mismatch)
    with pytest.raises(IngestionError, match="SSRF_PEER_MISMATCH"):
        g.fetch(URL, "pdf", lambda: policy())


def test_policy_revoke_after_dns_prevents_dispatch(tmp_path):
    grant = policy()

    def resolver(_):
        nonlocal grant
        grant = grant.model_copy(update={"revoked": True})
        return ("93.184.216.34",)

    g, calls = gateway(tmp_path, resolver=resolver)
    with pytest.raises(IngestionError, match="POLICY_BLOCKED"):
        g.fetch(URL, "pdf", lambda: grant)
    assert not calls


@pytest.mark.parametrize(
    "target",
    [
        "https://127.0.0.1/doc.pdf",
        "http://example.com/doc.pdf",
        BASE + "/other.pdf",
        "https://other.example.com/doc.pdf",
    ],
)
def test_redirect_denied_before_target_request(tmp_path, target):
    g, calls = gateway(tmp_path, lambda _: response(302, location=target))
    with pytest.raises(IngestionError):
        g.fetch(URL, "pdf", lambda: policy())
    assert calls == [BASE + "/robots.txt", URL]


def test_allowed_redirect_and_redirect_limit(tmp_path):
    def dispatch(r):
        return response(302, location="/new.pdf") if r.url.path == "/doc.pdf" else response()

    grant = policy(redirect_urls=(BASE + "/new.pdf",))
    g, calls = gateway(tmp_path, dispatch)
    result = g.fetch(URL, "pdf", lambda: grant)
    assert result.audit["final_url"] == BASE + "/new.pdf"
    g, calls = gateway(tmp_path, lambda _: response(302, location="/doc.pdf"))
    with pytest.raises(IngestionError, match="REDIRECT_LIMIT"):
        g.fetch(URL, "pdf", lambda: policy(redirect_urls=(URL,)))
    assert len(calls) <= 7


@pytest.mark.parametrize(
    "status,body,media,code",
    [
        (403, b"forbidden", "text/html", "HTTP_FORBIDDEN"),
        (200, b"<html>user_blocked</html>", "text/html", "CHALLENGE"),
        (200, b"not a pdf", "application/pdf", "FORMAT_INVALID"),
        (304, b"", "application/pdf", "CACHE_MISSING"),
        (500, b"error", "text/html", "HTTP_UNAVAILABLE"),
        (429, b"error", "text/html", "HTTP_RATE_LIMIT"),
    ],
)
def test_network_content_errors(tmp_path, status, body, media, code):
    g, _ = gateway(tmp_path, lambda _: response(status, body, media, **{"retry-after": "12"}))
    with pytest.raises(IngestionError, match=code) as captured:
        g.fetch(URL, "pdf", lambda: policy())
    assert captured.value.audit["requests"]
    if status == 429:
        assert captured.value.retry_after == 12


def test_truncated_http_body_never_publishes_an_original(tmp_path):
    g, _ = gateway(tmp_path, lambda _: response(**{"content-length": "1000"}))
    with pytest.raises(IngestionError, match="NETWORK_UNAVAILABLE"):
        g.fetch(URL, "pdf", lambda: policy())
    assert not g.store.reconcile(set())["orphan"]


def test_size_and_robots_disallow(tmp_path):
    g, _ = gateway(tmp_path, max_bytes=4)
    with pytest.raises(IngestionError, match="SIZE_LIMIT"):
        g.fetch(URL, "pdf", lambda: policy())
    calls = []

    def handler(r):
        calls.append(str(r.url))
        return response(body=b"User-agent: *\nDisallow: *.pdf$", media="text/plain")

    g = FetchGateway(
        Settings(app_env="test"),
        LocalBlobStore(tmp_path),
        transport=FakeTransport(handler),
        resolver=lambda _: ("93.184.216.34",),
    )
    with pytest.raises(IngestionError, match="ROBOTS_DISALLOWED"):
        g.fetch(URL, "pdf", lambda: policy())
    assert calls == [BASE + "/robots.txt"]


@pytest.mark.parametrize(
    "failure,code",
    [
        (ssl.SSLCertVerificationError("hostname mismatch"), "TLS_CHAIN_INVALID"),
        (ssl.SSLEOFError(), "TLS_HANDSHAKE_EOF"),
        (TimeoutError(), "CONNECT_TIMEOUT"),
        (OSError(), "NETWORK_UNAVAILABLE"),
    ],
)
def test_tls_and_socket_errors_classified(tmp_path, failure, code):
    def fail(_):
        raise failure

    g, _ = gateway(tmp_path, fail)
    with pytest.raises(IngestionError, match=code):
        g.fetch(URL, "pdf", lambda: policy())
    assert (retry_at(IngestionError(code), 1) is None) == (code == "TLS_CHAIN_INVALID")
    assert retry_at(IngestionError(code), 3) is None


def test_per_host_concurrency_is_shared_between_gateways(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    entered, release = threading.Event(), threading.Event()

    def handler(_):
        entered.set()
        assert release.wait(5)
        return response()

    first, _ = gateway(tmp_path, handler)
    second, calls = gateway(tmp_path)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(first.fetch, URL, "pdf", lambda: policy())
        assert entered.wait(5)
        try:
            with pytest.raises(IngestionError, match="HOST_BUSY"):
                second.fetch(URL, "pdf", lambda: policy())
            assert not calls
        finally:
            release.set()
        assert task.result().status == 200


def test_rate_and_deadline_are_bounded(tmp_path):
    grant = policy(rate_seconds=10000)
    g, calls = gateway(tmp_path)
    with pytest.raises(IngestionError, match="REQUEST_RATE_LIMIT"):
        g.fetch(URL, "pdf", lambda: grant)
    assert len(calls) <= 1
