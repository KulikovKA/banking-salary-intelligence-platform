"""PostgreSQL-only tests for the operator corpus and fixed snapshot service."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.corpus.models import ExtractionRun, Snapshot, SnapshotMember
from app.corpus.service import CorpusError, CorpusService, SnapshotManifest
from app.ingestion.gateway import FetchGateway
from app.ingestion.policy import AcquisitionPolicy
from app.ingestion.service import IngestionService
from app.registry.models import Bank, Blob, Source, SourceFetch, SourcePolicy, SourceVersion
from app.storage.local import LocalBlobStore


@pytest.fixture
def corpus_db(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("NOT RUN: TEST_DATABASE_URL is not set; PostgreSQL integration required")
    engine = create_engine(url)
    connection = engine.connect()
    outer = connection.begin()
    factory = sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    now = datetime.now(UTC)
    store = LocalBlobStore(tmp_path / "synthetic-originals")
    body = b"%PDF-1.7 synthetic fixed corpus fixture\n"
    receipt = store.put([body], "pdf", "synthetic")
    ids = {
        name: str(uuid4())
        for name in ("snapshot", "source", "policy", "version", "fetch", "extraction", "blob")
    }
    url_value = f"https://example.com/{uuid4().hex}.pdf"
    grant = AcquisitionPolicy(
        source_id=ids["source"],
        decision="approved",
        corpus_kind="synthetic",
        method="automatic",
        allowed_urls=(url_value,),
        reviewer="synthetic test",
        official_relationship="synthetic",
        acquisition_basis="synthetic fixture",
        storage_basis="synthetic fixture",
        reuse_basis="synthetic fixture",
        terms_evidence="synthetic fixture",
        purpose="test",
        expires_at=now + timedelta(days=1),
        rate_seconds=0.01,
    )
    with factory.begin() as session:
        bank = session.scalar(select(Bank).where(Bank.code == "sber"))
        if bank is None:
            bank = Bank(id=str(uuid4()), code="sber", name="Synthetic Sber identity")
            session.add(bank)
            session.flush()
        session.add(
            SourcePolicy(
                id=ids["policy"],
                bank_id=bank.id,
                allowed_hosts=["example.com"],
                collection_decision="approved",
                reason="synthetic test",
                acquisition_config={"automatic": grant.model_dump(mode="json")},
            )
        )
        session.flush()
        session.add(
            Source(
                id=ids["source"],
                bank_id=bank.id,
                policy_id=ids["policy"],
                url=url_value,
                canonical_url=url_value,
                kind="pdf",
                scope_hint={"region": "RU-KDA", "segment": "SME"},
                state="healthy",
                corpus_kind="synthetic",
            )
        )
        session.add(Blob(**asdict(receipt), id=ids["blob"], verified_at=now))
        session.flush()
        session.add(
            SourceVersion(
                id=ids["version"],
                source_id=ids["source"],
                blob_id=ids["blob"],
                metadata_json={
                    "applicability": {"region": "RU-KDA", "segment": "SME"},
                    "effective_date": None,
                },
                content_state="accepted",
                accepted_at=now,
                accepted_by="synthetic test",
            )
        )
        session.flush()
        session.add(
            SourceFetch(
                id=ids["fetch"],
                source_id=ids["source"],
                requested_url=url_value,
                final_url=url_value,
                redirect_chain=[],
                result="success",
                acquisition_method="automatic",
                source_version_id=ids["version"],
                fetched_at=now,
            )
        )
        session.flush()
        session.add(
            ExtractionRun(
                id=ids["extraction"],
                source_version_id=ids["version"],
                raw_sha256=receipt.sha256,
                extraction_sha256=hashlib.sha256(b"synthetic extraction").hexdigest(),
                parser_version="synthetic-test-1",
                corpus_kind="synthetic",
                status="ok",
            )
        )
    settings = Settings(app_env="test", storage_root=store.root)
    ingestion = IngestionService(factory, settings, store, FetchGateway(settings, store))
    service = CorpusService(ingestion)
    manifest = SnapshotManifest.model_validate(
        {
            "snapshot_id": ids["snapshot"],
            "revision": 1,
            "corpus_kind": "synthetic",
            "region": "RU-KDA",
            "employer_segment": "SME",
            "documents": [
                {
                    "bank_code": "sber",
                    "source_id": ids["source"],
                    "source_version_id": ids["version"],
                    "source_fetch_id": ids["fetch"],
                    "policy_id": ids["policy"],
                    "extraction_run_id": ids["extraction"],
                    "sha256": receipt.sha256,
                    "acquisition_method": "automatic",
                    "original_url": url_value,
                    "final_url": url_value,
                    "acquired_at": now.isoformat(),
                    "scope": {"region": "RU-KDA", "segment": "SME"},
                    "effective_date": None,
                    "document_type": "synthetic_salary_terms",
                }
            ],
            "missing_documents": [
                {
                    "bank_code": code,
                    "document_type": "salary_project_terms",
                    "reason": "No fixture was created for this bank.",
                    "basis_reference": "synthetic-test",
                }
                for code in ("vtb", "alfa", "kuban_credit")
            ],
        }
    )
    yield service, factory, store, ids, receipt, manifest
    outer.rollback()
    connection.close()
    engine.dispose()


def test_empty_corpus_and_incomplete_bank_registry_are_rejected():
    base = {
        "snapshot_id": str(uuid4()),
        "revision": 1,
        "corpus_kind": "synthetic",
        "region": "RU-KDA",
        "employer_segment": "SME",
        "documents": [],
        "missing_documents": [],
    }
    with pytest.raises(ValidationError, match="CORPUS_EMPTY"):
        SnapshotManifest.model_validate(base)


def test_committed_example_is_a_separate_synthetic_manifest():
    root = Path(__file__).resolve().parents[2]
    schema = json.loads((root / "manifests/snapshot.schema.json").read_text(encoding="utf-8"))
    example = CorpusService.load_manifest(root / "manifests/snapshot.example.json")
    assert schema["properties"]["corpus_kind"]["enum"] == ["real", "synthetic"]
    assert example.corpus_kind == "synthetic"
    assert {item.bank_code for item in example.missing_documents} == {"vtb", "alfa", "kuban_credit"}


def test_hash_quarantine_and_missing_original_are_rejected(corpus_db):
    service, factory, store, ids, receipt, manifest = corpus_db
    service.validate(manifest)
    changed = manifest.model_copy(
        update={"documents": (manifest.documents[0].model_copy(update={"sha256": "f" * 64}),)}
    )
    with pytest.raises(CorpusError, match="MANIFEST_HASH_MISMATCH"):
        service.validate(changed)
    with factory.begin() as session:
        session.get(SourceVersion, ids["version"]).content_state = "quarantine"
    with pytest.raises(CorpusError, match="SOURCE_VERSION_NOT_ACCEPTED"):
        service.validate(manifest)
    with factory.begin() as session:
        session.get(SourceVersion, ids["version"]).content_state = "accepted"
    store.path(receipt.storage_key).unlink()
    with pytest.raises(CorpusError, match="STORAGE_MISSING"):
        service.validate(manifest)


def test_exact_membership_freeze_is_idempotent_and_read_checks_hash(corpus_db):
    service, factory, store, ids, receipt, manifest = corpus_db
    with pytest.raises(CorpusError, match="DOCUMENT_INDEX_INVALID"):
        service.add_version(manifest, -1)
    assert service.add_version(manifest, 0)["added"] is True
    assert service.add_version(manifest, 0)["added"] is False
    result = service.freeze(manifest)
    assert result["state"] == "frozen" and result["idempotent"] is False
    assert service.freeze(manifest)["idempotent"] is True
    assert service.read_member(
        manifest.snapshot_id, manifest.documents[0].source_version_id
    ).read_bytes()
    with factory() as session:
        members = session.scalars(
            select(SnapshotMember).where(SnapshotMember.snapshot_id == ids["snapshot"])
        ).all()
        snapshot = session.get(Snapshot, ids["snapshot"])
    assert len(members) == 1
    assert members[0].source_version_id == ids["version"]
    assert members[0].extraction_run_id == ids["extraction"]
    assert snapshot is not None and snapshot.manifest_sha256 == manifest.manifest_sha256
    store.path(receipt.storage_key).write_bytes(b"corrupt after freeze")
    with pytest.raises(CorpusError, match="STORAGE_HASH_MISMATCH"):
        service.read_member(manifest.snapshot_id, manifest.documents[0].source_version_id)


def test_freeze_requires_manifest_membership_to_match_exactly(corpus_db):
    service, _, _, _, _, manifest = corpus_db
    changed = manifest.model_copy(
        update={
            "documents": (
                manifest.documents[0].model_copy(update={"extraction_run_id": str(uuid4())}),
            )
        }
    )
    service.add_version(manifest, 0)
    with pytest.raises(CorpusError, match="EXTRACTION_NOT_READY"):
        service.freeze(changed)


def test_real_snapshot_cannot_freeze_with_missing_bank_documents(corpus_db):
    service, _, _, _, _, manifest = corpus_db
    real = manifest.model_copy(update={"corpus_kind": "real"})
    with pytest.raises(CorpusError, match="REAL_CORPUS_INCOMPLETE"):
        service.freeze(real)


@pytest.mark.parametrize("revocation", ["decision", "grant"])
def test_revoked_permission_blocks_freeze_and_frozen_read(corpus_db, revocation):
    service, factory, _, ids, _, manifest = corpus_db
    service.add_version(manifest, 0)
    service.freeze(manifest)
    with factory.begin() as session:
        policy = session.get(SourcePolicy, ids["policy"])
        if revocation == "decision":
            policy.collection_decision = "denied"
        else:
            cfg = dict(policy.acquisition_config)
            cfg["automatic"] = {**cfg["automatic"], "revoked": True}
            policy.acquisition_config = cfg
    with pytest.raises(CorpusError, match="PERMISSION_REVOKED"):
        service.read_member(manifest.snapshot_id, manifest.documents[0].source_version_id)


def test_manifest_cannot_choose_an_unrelated_accepted_version(corpus_db):
    service, _, _, _, _, manifest = corpus_db
    forged = manifest.model_copy(
        update={
            "documents": (
                manifest.documents[0].model_copy(update={"source_version_id": str(uuid4())}),
            )
        }
    )
    with pytest.raises(CorpusError, match="PROVENANCE_UNKNOWN"):
        service.validate(forged)
