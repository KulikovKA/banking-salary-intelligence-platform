"""Real OpenSSL handshakes over MemoryBIO: no sockets or external network."""

import ssl
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.ingestion.tls import build_tls_context


def handshake(client_context, server_context, hostname):
    client_in, client_out, server_in, server_out = [ssl.MemoryBIO() for _ in range(4)]
    client = client_context.wrap_bio(
        client_in, client_out, server_side=False, server_hostname=hostname
    )
    server = server_context.wrap_bio(server_in, server_out, server_side=True)
    done = [False, False]
    for _ in range(20):
        for index, endpoint in enumerate((client, server)):
            if not done[index]:
                try:
                    endpoint.do_handshake()
                    done[index] = True
                except ssl.SSLWantReadError:
                    pass
        server_in.write(client_out.read())
        client_in.write(server_out.read())
        if all(done):
            return
    pytest.fail("MemoryBIO handshake did not complete")


def test_actual_chain_and_hostname_verification_without_network(tmp_path):
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic root")])
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "example.test")])
    now = datetime.now(UTC)

    def builder(subject, issuer, public_key):
        return (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=1))
        )

    root = (
        builder(root_name, root_name, root_key.public_key())
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(root_key, hashes.SHA256())
    )
    leaf = (
        builder(leaf_name, root_name, leaf_key.public_key())
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("example.test")]), critical=False)
        .sign(root_key, hashes.SHA256())
    )
    ca, cert, key = [
        tmp_path / name for name in ("synthetic-root.crt", "synthetic-leaf.crt", "synthetic.key")
    ]
    ca.write_bytes(root.public_bytes(serialization.Encoding.PEM))
    cert.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key.write_bytes(
        leaf_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(cert, key)
    trusted = build_tls_context("certifi", ca)
    handshake(trusted, server, "example.test")
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(trusted, server, "wrong.test")
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(build_tls_context("certifi"), server, "example.test")
