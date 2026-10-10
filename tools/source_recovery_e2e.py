"""Opt-in offline E2E with generated PDFs and a dedicated PostgreSQL test database.

No bank requests, real imports, automatic grants or tariff publication. Commits
synthetic evidence so another process can inspect it; does not delete any data.
"""

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db.base import make_session_factory
from app.ingestion.errors import IngestionError
from app.ingestion.gateway import FetchGateway
from app.ingestion.policy import AcquisitionPolicy
from app.ingestion.service import IngestionService
from app.registry.models import Bank, Blob, Source, SourceFetch, SourcePolicy, SourceVersion
from app.storage.local import LocalBlobStore

URL = "https://example.com/synthetic-e2e.pdf"


def synthetic_pdf(edition: str) -> bytes:
    """A complete one-page PDF, including objects, xref and trailer."""
    content = f"BT /F1 12 Tf 72 720 Td (SYNTHETIC E2E - edition {edition}) Tj ET\n".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"endstream",
    ]
    result = b"%PDF-1.4\n"
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(result)
    result += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        result += f"{offset:010d} 00000 n \n".encode()
    result += (
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode()
    return result


def require(condition, message):
    if not condition:
        raise RuntimeError("E2E_CHECK_FAILED: " + message)


def run_synthetic_e2e(factory, root: Path) -> dict:
    run_id = uuid4().hex
    directory = root / run_id
    directory.mkdir(parents=True, exist_ok=False)
    source_id, bank_id = str(uuid4()), str(uuid4())
    grant = AcquisitionPolicy(
        source_id=source_id,
        decision="approved",
        allowed_urls=(URL,),
        method="manual",
        corpus_kind="synthetic",
        reviewer="offline-e2e-test",
        official_relationship="none: generated synthetic document, not a bank document",
        acquisition_basis="locally generated test PDF",
        storage_basis="isolated synthetic E2E archive",
        reuse_basis="test verification only; no real facts or publication",
        terms_evidence="synthetic_pdf() generator; contains no bank material",
        purpose="offline acquisition/archive/PostgreSQL/content acceptance verification",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    with factory.begin() as session:
        session.add(Bank(id=bank_id, code="syn_e2e_" + run_id, name="Synthetic E2E bank"))
        session.flush()
        policy = SourcePolicy(
            bank_id=bank_id,
            allowed_hosts=["example.com"],
            acquisition_config={"manual": grant.model_dump(mode="json")},
            collection_decision="approved",
            reviewer="offline-e2e-test",
            reason="Generated synthetic PDF only; no G0-LIVE grant",
        )
        session.add(policy)
        session.flush()
        session.add(
            Source(
                id=source_id,
                bank_id=bank_id,
                policy_id=policy.id,
                url=URL,
                canonical_url=URL,
                kind="pdf",
                corpus_kind="synthetic",
                schedule_seconds=86400,
            )
        )

    settings = Settings(app_env="test", ingestion_mode="offline", storage_root=directory)
    store = LocalBlobStore(directory / "archive")
    service = IngestionService(factory, settings, store, FetchGateway(settings, store))
    original = directory / "synthetic.pdf"
    body_a, body_b = synthetic_pdf(run_id + " A"), synthetic_pdf(run_id + " B")

    def import_document():
        return service.import_file(
            source_id,
            original,
            operator="offline-e2e-test",
            original_url=URL,
            final_url=URL,
            acquired_at=datetime.now(UTC) - timedelta(seconds=1),
        )

    def expect_error(expected):
        try:
            import_document()
        except IngestionError as exc:
            require(exc.code == expected, "unexpected error " + exc.code)
            return exc.code
        raise RuntimeError("E2E_CHECK_FAILED: missing rejection")

    original.write_bytes(body_a)
    first = import_document()
    require(first.result == "manual_imported", "initial import")
    with factory() as session:
        version_a = session.get(SourceVersion, first.version_id)
        require(version_a.content_state == "quarantine", "initial quarantine")
        blob_a = session.get(Blob, version_a.blob_id)
        receipt_a = service._receipt(blob_a)
        require(blob_a.sha256 == hashlib.sha256(body_a).hexdigest(), "SHA-256 A")
        require(store.verify(receipt_a).read_bytes() == body_a, "immutable original A")

    second = import_document()
    require(second.version_id == first.version_id, "deduplication")
    service.accept_content(
        first.version_id,
        reviewer="offline-e2e-test",
        applicability={"corpus_kind": "synthetic", "scope": "test only", "edition": "A"},
    )
    require(service.current_content(source_id)[0] == first.version_id, "accepted A")

    original.write_bytes(body_b)
    third = import_document()
    require(third.version_id != first.version_id, "new version B")
    require(service.current_content(source_id)[0] == first.version_id, "last accepted A retained")
    with factory() as session:
        require(
            session.get(SourceVersion, third.version_id).content_state == "quarantine",
            "B needs separate acceptance",
        )

    errors = []
    original.write_bytes(b"<html>Not a PDF</html>")
    errors.append(expect_error("FORMAT_INVALID"))
    original.unlink()
    errors.append(expect_error("STORAGE_WRITE_FAILED"))
    with factory.begin() as session:
        policy = session.get(SourcePolicy, session.get(Source, source_id).policy_id)
        policy.acquisition_config = {"manual": {**grant.model_dump(mode="json"), "revoked": True}}
    errors.append(expect_error("POLICY_BLOCKED"))
    require(service.current_content(source_id)[0] == first.version_id, "errors preserve A")
    blocked_fetch = service.fetch_source(source_id)
    require(blocked_fetch.error_code == "POLICY_BLOCKED", "no automatic grant")

    service.accept_content(
        third.version_id,
        reviewer="offline-e2e-test",
        applicability={"corpus_kind": "synthetic", "scope": "test only", "edition": "B"},
    )
    require(service.current_content(source_id)[0] == third.version_id, "accepted B is current")
    with factory() as session:
        source = session.get(Source, source_id)
        versions = list(
            session.scalars(select(SourceVersion).where(SourceVersion.source_id == source_id))
        )
        observations = list(
            session.scalars(select(SourceFetch).where(SourceFetch.source_id == source_id))
        )
        keys = set()
        blobs = []
        for version in versions:
            blob = session.get(Blob, version.blob_id)
            receipt = service._receipt(blob)
            store.verify(receipt)
            keys.add(blob.storage_key)
            require(blob.corpus_kind == "synthetic", "namespace separation")
            require(version.content_state == "accepted", "both versions retained accepted")
            blobs.append(
                {
                    "id": blob.id,
                    "sha256": blob.sha256,
                    "byte_size": blob.byte_size,
                    "storage_key": blob.storage_key,
                    "version_id": version.id,
                    "content_state": version.content_state,
                }
            )
        require(len(versions) == 2, "exactly two versions")
        require(len(observations) == 7, "every import and blocked fetch audited")
        require(source.last_successful_check is None, "manual is not scheduled-fetch success")
        require(all(o.http_status is None for o in observations), "no fabricated HTTP status")
        require(store.verify(receipt_a).read_bytes() == body_a, "A original unchanged")
        require(store.reconcile(keys) == {"missing": [], "orphan": []}, "archive consistency")
        require(
            session.scalar(select(func.count()).select_from(Blob).where(Blob.storage_key.in_(keys)))
            == 2,
            "exactly two blobs",
        )
        audit = [
            {
                "id": o.id,
                "result": o.result,
                "method": o.acquisition_method,
                "http_status": o.http_status,
                "error_code": o.error_code,
            }
            for o in observations
        ]

    report = {
        "run_id": run_id,
        "completed_at": datetime.now(UTC).isoformat(),
        "result": "PASS_SYNTHETIC_ONLY",
        "real_scenario": "BLOCKED: no acquisition/storage/reuse approval",
        "network_requests": 0,
        "source_id": source_id,
        "bank_id": bank_id,
        "imports": [asdict(first), asdict(second), asdict(third)],
        "expected_errors": errors,
        "current_version_id": third.version_id,
        "blobs": blobs,
        "observations": audit,
        "archive_reconcile": store.reconcile(keys),
        "scheduled_fetch_success": False,
    }
    (directory / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings.from_environment()
    require(
        settings.app_env == "test" and settings.ingestion_mode == "offline", "test/offline required"
    )
    require(settings.database_url is not None, "DATABASE_URL required")
    database_url = settings.database_url.get_secret_value()
    require(
        make_url(database_url).database in {"bsi_e2e", "bsi_test"},
        "dedicated test database required",
    )
    report = run_synthetic_e2e(make_session_factory(database_url), args.output_root)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
