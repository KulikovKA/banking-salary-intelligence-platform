"""Offline regressions: group boundaries, wildcard rules and challenge rejection."""

import ssl

import pytest
from bank_tls_probe import UA, bounded_get, context, robots_allowed


def test_specific_group_does_not_leak_into_wildcard_group():
    from protego import Protego

    body = """User-agent: *
Disallow: /private/
Allow: /upload/*.jpg

User-agent: Yandex
Disallow: /private/
Disallow: /upload/*.pdf
Disallow: /upload/iblock/*.pdf
"""
    url = "https://example.com/upload/iblock/test/document.pdf"
    assert robots_allowed(body, 200, url)
    assert not Protego.parse(body).can_fetch(url, "Yandex")
    assert UA == "BankSalaryResearch/0.1"


def test_wildcard_file_ban_and_specific_allow():
    body = "User-agent: *\nDisallow: *.pdf$\nDisallow: *.xlsx$\nAllow: /public/file.pdf$"
    assert not robots_allowed(body, 200, "https://example.com/other/file.pdf")
    assert not robots_allowed(body, 200, "https://example.com/other/file.xlsx")
    assert robots_allowed(body, 200, "https://example.com/public/file.pdf")


@pytest.mark.parametrize(
    "status,body",
    [
        (403, "Forbidden"),
        (200, "<html><script>user_blocked</script></html>"),
        (200, ""),
        (302, "User-agent: *\nAllow: /"),
    ],
)
def test_unknown_robots_fails_closed(status, body):
    with pytest.raises(ValueError):
        robots_allowed(body, status, "https://example.com/product/")


@pytest.mark.parametrize("mode", ["stdlib", "system", "certifi"])
def test_every_tls_context_verifies_certificates_and_hostname(mode):
    ctx = context(mode)
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname


def test_bounded_get_stops_oversized_stream(monkeypatch):
    import bank_tls_probe

    monkeypatch.setattr(bank_tls_probe, "MAX_BYTES", 4)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def iter_bytes(self):
            yield b"123"
            yield b"45"

    class Client:
        def stream(self, method, url):
            assert method == "GET"
            return Response()

    with pytest.raises(ValueError, match="exceeds"):
        bounded_get(Client(), "https://example.com/file.pdf")
