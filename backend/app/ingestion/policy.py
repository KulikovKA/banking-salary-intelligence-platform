"""Exact URL grants, independent of content acceptance and discovery."""

import ipaddress
import re
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field

from app.ingestion.errors import IngestionError


def validate_url(url: str) -> str:
    try:
        p = urlsplit(url)
        decoded = unquote(p.path)
        if (
            p.scheme != "https"
            or not p.hostname
            or p.username
            or p.password
            or p.port not in (None, 443)
            or p.fragment
            or p.query
            or p.hostname.endswith(".")
            or p.hostname != p.hostname.encode("idna").decode()
            or "\\" in url
            or re.search(r"[\x00-\x20\x7f]", url)
            or decoded != p.path
            or any(part in (".", "..") for part in p.path.split("/"))
        ):
            raise ValueError("URL invalid")
        # Literal IPs are never approved sources; reject before DNS.
        try:
            ipaddress.ip_address(p.hostname)
        except ValueError:
            pass
        else:
            raise ValueError("IP URL")
        if not p.path.startswith("/") or p.netloc != p.hostname:
            raise ValueError("Non-canonical URL")
        return p.hostname
    except ValueError as exc:
        raise IngestionError("URL_FORBIDDEN") from exc


def public_ip(address: str) -> str:
    try:
        ip = ipaddress.ip_address(address)
        if (
            not ip.is_global
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
            or str(ip) == "168.63.129.16"
        ):
            raise ValueError("Non-public")
        if isinstance(ip, ipaddress.IPv6Address) and (
            ip.ipv4_mapped is not None or ip.sixtofour is not None or ip.teredo is not None
        ):
            raise ValueError("IPv6 tunnel")
        return str(ip)
    except ValueError as exc:
        raise IngestionError("SSRF_BLOCKED") from exc


class AcquisitionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    decision: Literal["approved", "pending", "denied"] = "pending"
    allowed_urls: tuple[str, ...] = ()
    redirect_urls: tuple[str, ...] = ()
    method: Literal["automatic", "manual"]
    corpus_kind: Literal["synthetic", "real"]
    reviewer: str = ""
    official_relationship: str = ""
    acquisition_basis: str = ""
    storage_basis: str = ""
    reuse_basis: str = ""
    terms_evidence: str = ""
    purpose: str = ""
    expires_at: datetime | None = None
    revoked: bool = False
    rate_seconds: float = Field(default=1, gt=0, allow_inf_nan=False)

    def authorize(self, url: str, method: str, *, redirect: bool = False) -> None:
        validate_url(url)
        expiry = self.expires_at
        if (
            self.decision != "approved"
            or self.revoked
            or self.method != method
            or expiry is None
            or expiry.tzinfo is None
            or expiry <= datetime.now(UTC)
            or not all(
                (
                    self.reviewer,
                    self.official_relationship,
                    self.acquisition_basis,
                    self.storage_basis,
                    self.reuse_basis,
                    self.terms_evidence,
                    self.purpose,
                )
            )
            or url not in (self.redirect_urls if redirect else self.allowed_urls)
        ):
            raise IngestionError("POLICY_BLOCKED")
