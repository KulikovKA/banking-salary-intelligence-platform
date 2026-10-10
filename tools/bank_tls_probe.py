"""Small opt-in research probe; not an ingestion gateway or scheduled collector.

No network without --host or --url. GET requires --research-get; redirects are
reported, never followed. Target GET is gated by a successful robots.txt read.
Raw TLS checks bypass HTTP proxies, so compare them with the HTTP result.
"""

import argparse
import hashlib
import importlib
import importlib.metadata
import ipaddress
import json
import os
import platform
import socket
import ssl
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

UA = "BankSalaryResearch/0.1"
MAX_BYTES = 50 * 1024 * 1024


def robots_allowed(body, status, url):
    if status != 200:
        raise ValueError("Robots unknown; target GET not performed")
    if "<html" in body.lower() or "<script" in body.lower() or "user-agent:" not in body.lower():
        raise ValueError("Robots invalid/challenge response; target GET not performed")
    from protego import Protego

    return Protego.parse(body).can_fetch(url, UA)


def bounded_get(client, url):
    with client.stream("GET", url) as response:
        chunks = []
        size = 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("Response exceeds 50 MiB; stopped")
            chunks.append(chunk)
        return response, b"".join(chunks)


def context(mode, extra_ca=None):
    if mode == "system":
        import truststore

        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    elif mode == "certifi":
        import certifi

        ctx = ssl.create_default_context(cafile=certifi.where())
    else:
        ctx = ssl.create_default_context()
    if extra_ca:
        ctx.load_verify_locations(cafile=str(extra_ca))
    return ctx


def error(exc):
    chain = []
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        chain.append(
            {
                "type": type(exc).__name__,
                "message": str(exc),
                "verify_code": getattr(exc, "verify_code", None),
                "verify_message": getattr(exc, "verify_message", None),
            }
        )
        exc = exc.__cause__ or exc.__context__
    return chain


def public_addresses(host, port):
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not infos or any(not ipaddress.ip_address(i[4][0]).is_global for i in infos):
        raise ValueError("Non-public DNS destination rejected")
    return infos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="One hostname for DNS and one TLS handshake")
    parser.add_argument("--family", choices=["auto", "4", "6"], default="auto")
    parser.add_argument("--mode", choices=["stdlib", "system", "certifi"], default="system")
    parser.add_argument("--extra-ca", type=Path, help="Authenticated CA PEM, scoped to this client")
    parser.add_argument("--url", help="One exact HTTPS research URL; not followed on redirect")
    parser.add_argument("--research-get", action="store_true")
    parser.add_argument("--client", choices=["httpx", "httpx2"], default="httpx2")
    parser.add_argument("--trust-env", action="store_true", help="Use configured HTTP proxy")
    parser.add_argument("--out", type=Path, help="JSON evidence file")
    parser.add_argument("--body", type=Path, help="Save successful response bytes explicitly")
    args = parser.parse_args()
    result = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "observed_at": datetime.now(UTC).isoformat(),
        "openssl": ssl.OPENSSL_VERSION,
        "mode": args.mode,
        "client": args.client,
        "trust_env": args.trust_env,
        "user_agent": UA,
        "raw_tls_uses_http_proxy": False,
        "env_present": {
            k: bool(os.environ.get(k))
            for k in (
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "ALL_PROXY",
                "NO_PROXY",
                "SSL_CERT_FILE",
                "SSL_CERT_DIR",
            )
        },
        "packages": {},
    }
    for name in ("httpx", "httpx2", "truststore", "certifi"):
        try:
            result["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][name] = None
    if args.url and not args.research_get:
        parser.error("--url requires explicit --research-get; no request made")
    if args.body and not args.url:
        parser.error("--body requires --url")
    if args.host:
        result["host"] = args.host
        try:
            infos = public_addresses(args.host, 443)
            result["dns"] = sorted({i[4][0] for i in infos})
            family = {"4": socket.AF_INET, "6": socket.AF_INET6}.get(args.family)
            candidates = [i for i in infos if family is None or i[0] == family]
            if not candidates:
                raise ValueError("No address for selected family")
            selected = candidates[0]
            with socket.socket(selected[0], selected[1], selected[2]) as raw:
                raw.settimeout(8)
                raw.connect(selected[4])
                with context(args.mode, args.extra_ca).wrap_socket(
                    raw, server_hostname=args.host
                ) as tls:
                    cert = tls.getpeercert()
                    result["tls"] = {
                        "verified": True,
                        "version": tls.version(),
                        "peer": tls.getpeername()[0],
                        "cipher": tls.cipher(),
                        "issuer": cert.get("issuer"),
                        "subject": cert.get("subject"),
                        "not_after": cert.get("notAfter"),
                        "leaf_sha256": hashlib.sha256(
                            tls.getpeercert(binary_form=True)
                        ).hexdigest(),
                    }
        except Exception as exc:
            result["tls_error"] = error(exc)
    if args.url:
        parsed = urlsplit(args.url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            parser.error("Only public HTTPS URLs without credentials on port 443")
        try:
            public_addresses(parsed.hostname, 443)
            client_module = importlib.import_module(args.client)
            with client_module.Client(
                verify=context(args.mode, args.extra_ca),
                trust_env=args.trust_env,
                follow_redirects=False,
                timeout=12,
                headers={"User-Agent": UA, "Accept-Encoding": "identity"},
            ) as client:
                robots_url = f"https://{parsed.netloc}/robots.txt"
                robots, robots_bytes = bounded_get(client, robots_url)
                robots_text = robots_bytes.decode("utf-8", errors="replace")
                result["robots"] = {
                    "url": robots_url,
                    "status": robots.status_code,
                    "location": robots.headers.get("location"),
                    "sha256": hashlib.sha256(robots_bytes).hexdigest(),
                }
                if parsed.path == "/robots.txt":
                    response = robots
                    response_bytes = robots_bytes
                else:
                    allowed = robots_allowed(robots_text, robots.status_code, args.url)
                    result["robots"]["target_allowed"] = allowed
                    if not allowed:
                        raise ValueError("Robots disallows target; target GET not performed")
                    response, response_bytes = bounded_get(client, args.url)
                result["http"] = {
                    "url": str(response.url),
                    "status": response.status_code,
                    "location": response.headers.get("location"),
                    "content_type": response.headers.get("content-type"),
                    "bytes": len(response_bytes),
                    "sha256": hashlib.sha256(response_bytes).hexdigest(),
                }
                if args.body and response.status_code == 200:
                    args.body.parent.mkdir(parents=True, exist_ok=True)
                    args.body.write_bytes(response_bytes)
        except Exception as exc:
            result["http_error"] = error(exc)
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
