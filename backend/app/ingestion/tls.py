"""Scoped trust: never mutate OS stores or globally patch ssl."""

import ssl
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import certifi
import truststore
from cryptography import x509

from app.ingestion.errors import IngestionError


def build_tls_context(
    mode: Literal["system", "certifi"] = "system", extra_ca: Path | None = None
) -> ssl.SSLContext:
    try:
        if mode not in ("system", "certifi"):
            raise ValueError("Unknown TLS mode")
        ctx = (
            truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            if mode == "system"
            else ssl.create_default_context(cafile=certifi.where())
        )
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        if extra_ca is not None:
            if extra_ca.stat().st_size > 1024 * 1024:
                raise ValueError("CA too large")
            raw = extra_ca.read_bytes()
            certificates = x509.load_pem_x509_certificates(raw)
            if not certificates:
                raise ValueError("Empty CA")
            now = datetime.now(UTC)
            for certificate in certificates:
                if (
                    not certificate.extensions.get_extension_for_class(
                        x509.BasicConstraints
                    ).value.ca
                    or not certificate.not_valid_before_utc <= now < certificate.not_valid_after_utc
                ):
                    raise ValueError("Invalid CA")
            ctx.load_verify_locations(cadata=raw.decode("ascii"))
        if not ctx.check_hostname or ctx.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError("Verification required")
        return ctx
    except Exception as exc:
        raise IngestionError("TLS_CONFIG_INVALID") from exc
