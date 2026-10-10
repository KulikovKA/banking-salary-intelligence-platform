import ssl
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.config import Settings, SettingsError
from app.ingestion.errors import IngestionError
from app.ingestion.robots import parse_robots
from app.ingestion.tls import build_tls_context


def test_ca_context_is_scoped_and_requires_valid_ca(tmp_path: Path) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic test CA")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    ca = tmp_path / "synthetic.crt"
    ca.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    for mode in ("system", "certifi"):
        ctx = build_tls_context(mode, ca)
        assert ctx.check_hostname and ctx.verify_mode == ssl.CERT_REQUIRED
    ca.write_text("not a certificate")
    with pytest.raises(IngestionError, match="TLS_CONFIG_INVALID"):
        build_tls_context(extra_ca=ca)


def test_robots_group_boundaries_and_wildcards() -> None:
    body = b"User-agent: *\nDisallow: /private/\nUser-agent: Yandex\nDisallow: /upload/*.pdf"
    snapshot = parse_robots("https://example.com/robots.txt", 200, body)
    snapshot.check("https://example.com/upload/iblock/doc.pdf")
    assert snapshot.matched_groups == ("*",)
    assert snapshot.raw_base64 and len(snapshot.sha256) == 64
    blocked = parse_robots(
        "https://example.com/robots.txt",
        200,
        b"User-agent: *\nDisallow: *.pdf$\nAllow: /public/file.pdf$",
    )
    blocked.check("https://example.com/public/file.pdf")
    with pytest.raises(IngestionError, match="ROBOTS_DISALLOWED"):
        blocked.check("https://example.com/other/file.pdf")


@pytest.mark.parametrize(
    "status,body,code",
    [
        (403, b"Forbidden", "HTTP_FORBIDDEN"),
        (200, b"<html>user_blocked</html>", "CHALLENGE"),
        (404, b"", "ROBOTS_UNKNOWN"),
        (200, b"garbage", "ROBOTS_INVALID"),
    ],
)
def test_robots_errors_are_distinct(status: int, body: bytes, code: str) -> None:
    with pytest.raises(IngestionError, match=code):
        parse_robots("https://example.com/robots.txt", status, body)


def test_specific_short_product_token_and_audit_group_agree() -> None:
    body = b"User-agent: *\nAllow: /\nUser-agent: B\nDisallow: /\nUser-agent: Research\nAllow: /"
    snapshot = parse_robots("https://example.com/robots.txt", 200, body)
    assert snapshot.matched_groups == ("B",)
    with pytest.raises(IngestionError, match="ROBOTS_DISALLOWED"):
        snapshot.check("https://example.com/doc.pdf")


def test_test_mode_cannot_enable_live() -> None:
    assert Settings().ingestion_mode == "offline"
    with pytest.raises(SettingsError, match="CONFIG_TEST_EGRESS_FORBIDDEN"):
        Settings.from_environment({"APP_ENV": "test", "INGESTION_MODE": "live"})
