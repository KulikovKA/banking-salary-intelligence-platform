"""Opt-in PostgreSQL integration only; never substitute SQLite or bank network."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx2 as httpx
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.ingestion.errors import IngestionError
from app.ingestion.gateway import FetchGateway
from app.ingestion.policy import AcquisitionPolicy
from app.ingestion.service import IngestionService
from app.ingestion.transport import FakeTransport
from app.registry.models import Bank, Blob, Source, SourceFetch, SourcePolicy, SourceVersion
from app.storage.local import LocalBlobStore


@pytest.fixture
def catalog(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("NOT RUN: TEST_DATABASE_URL is not set")
    engine = create_engine(url)
    connection = engine.connect()
    outer = connection.begin()
    # A dedicated connection + outer rollback isolates synthetic rows without schema deletion.
    factory = sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    source_id = str(uuid4())
    bank_id = str(uuid4())
    grant = AcquisitionPolicy(
        source_id=source_id,
        decision="approved",
        corpus_kind="synthetic",
        method="automatic",
        allowed_urls=("https://example.com/doc.pdf", "https://example.com/robots.txt"),
        reviewer="tester",
        official_relationship="synthetic",
        acquisition_basis="test",
        storage_basis="test",
        reuse_basis="test",
        terms_evidence="test",
        purpose="integration test",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        rate_seconds=0.001,
    )
    with factory.begin() as session:
        session.add(Bank(id=bank_id, code=f"syn_{uuid4().hex}", name="Synthetic test bank"))
        session.flush()
        row = SourcePolicy(
            bank_id=bank_id,
            allowed_hosts=["example.com"],
            collection_decision="approved",
            reason="synthetic test",
            acquisition_config={
                "automatic": grant.model_dump(mode="json"),
                "manual": grant.model_copy(update={"method": "manual"}).model_dump(mode="json"),
            },
        )
        session.add(row)
        session.flush()
        session.add(
            Source(
                id=source_id,
                bank_id=bank_id,
                policy_id=row.id,
                url="https://example.com/doc.pdf",
                canonical_url="https://example.com/doc.pdf",
                kind="pdf",
                corpus_kind="synthetic",
                schedule_seconds=86400,
            )
        )
    settings = Settings(app_env="test")
    store = LocalBlobStore(tmp_path)
    state = {"body": b"%PDF-1.7 synthetic-one", "status": 200}

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                headers={"content-type": "text/plain"},
                content=iter([b"User-agent: *\nAllow: /"]),
            )
        return httpx.Response(
            state["status"],
            headers={"content-type": "application/pdf", "etag": '"one"'},
            content=iter([state["body"]]),
        )

    gateway = FetchGateway(
        settings, store, transport=FakeTransport(handler), resolver=lambda _: ("93.184.216.34",)
    )
    yield IngestionService(factory, settings, store, gateway), factory, source_id, state, store
    outer.rollback()
    connection.close()
    engine.dispose()


def test_fetch_versions_quarantine_dedup_and_last_good(catalog):
    service, factory, source_id, state, store = catalog
    first = service.fetch_source(source_id)
    assert first.result == "success", first.error_code
    with factory() as session:
        assert session.get(SourceVersion, first.version_id).content_state == "quarantine"
    assert service.current_content(source_id)[0] is None
    service.accept_content(first.version_id, reviewer="tester", applicability={"scope": "unknown"})
    second = service.fetch_source(source_id)
    assert second.result == "success", second.error_code
    assert second.version_id == first.version_id
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(SourceFetch)
                .where(SourceFetch.source_id == source_id)
            )
            == 2
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(SourceVersion)
                .where(SourceVersion.source_id == source_id)
            )
            == 1
        )
    state["body"] = b"%PDF-1.7 synthetic-two"
    third = service.fetch_source(source_id)
    assert third.result == "success" and third.version_id != first.version_id
    assert service.current_content(source_id)[0] == first.version_id
    state["status"] = 403
    failed = service.fetch_source(source_id)
    assert failed.error_code == "HTTP_FORBIDDEN"
    assert service.current_content(source_id) == (first.version_id, True)
    with factory() as session:
        keys = set(session.scalars(select(Blob.storage_key).where(Blob.corpus_kind == "synthetic")))
    assert not store.reconcile(keys)["missing"]


def test_manual_import_has_separate_provenance(catalog, tmp_path):
    service, factory, source_id, _, _ = catalog
    document = tmp_path / "synthetic.pdf"
    document.write_bytes(b"%PDF-1.7 manual synthetic")
    result = service.import_file(
        source_id,
        document,
        operator="tester",
        original_url="https://example.com/doc.pdf",
        final_url="https://example.com/doc.pdf",
        acquired_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    assert result.result == "manual_imported"
    with factory() as session:
        observation = session.get(SourceFetch, result.observation_id)
        assert observation.acquisition_method == "manual" and observation.http_status is None
        assert observation.audit_metadata["operator"] == "tester"
        assert session.get(Source, source_id).last_successful_check is None


def test_revoked_manual_policy_prevents_read(catalog, tmp_path):
    service, factory, source_id, _, _ = catalog
    with factory.begin() as session:
        source = session.get(Source, source_id)
        row = session.get(SourcePolicy, source.policy_id)
        row.collection_decision = "denied"
    with pytest.raises(IngestionError, match="POLICY_BLOCKED"):
        service.import_file(
            source_id,
            tmp_path / "does-not-exist.pdf",
            operator="tester",
            original_url="https://example.com/doc.pdf",
            final_url="https://example.com/doc.pdf",
            acquired_at=datetime.now(UTC),
        )


def test_rollback_leaves_no_db_reference_to_partial_file(catalog, monkeypatch):
    service, factory, source_id, _, store = catalog
    original = service._register

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("simulated DB failure before commit")

    monkeypatch.setattr(service, "_register", fail)
    with pytest.raises(RuntimeError):
        service.fetch_source(source_id)
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(SourceVersion)
                .where(SourceVersion.source_id == source_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(SourceFetch)
                .where(SourceFetch.source_id == source_id)
            )
            == 0
        )
    assert store.reconcile(set())[
        "orphan"
    ]  # Complete orphan, safe for later read-only reconciliation.


def test_postgres_host_lock_blocks_other_connections(catalog):
    import hashlib

    service, factory, source_id, _, _ = catalog
    key = int.from_bytes(hashlib.sha256(b"example.com").digest()[:8], "big", signed=True)
    external = create_engine(os.environ["TEST_DATABASE_URL"])
    with external.begin() as connection:
        assert connection.scalar(select(func.pg_try_advisory_xact_lock(key)))
        result = service.fetch_source(source_id)
        assert result.error_code == "HOST_BUSY"
        assert result.retry_at is not None
    external.dispose()


def test_real_manual_import_is_blocked_before_file_read(catalog, tmp_path):
    service, factory, source_id, _, _ = catalog
    with factory.begin() as session:
        source = session.get(Source, source_id)
        source.corpus_kind = "real"
        row = session.get(SourcePolicy, source.policy_id)
        cfg = dict(row.acquisition_config)
        cfg["manual"] = {**cfg["manual"], "corpus_kind": "real"}
        row.acquisition_config = cfg
    with pytest.raises(IngestionError, match="MANUAL_PROVENANCE_INVALID"):
        service.import_file(
            source_id,
            tmp_path / "does-not-exist.pdf",
            operator="tester",
            original_url="https://example.com/doc.pdf",
            final_url="https://example.com/doc.pdf",
            acquired_at=datetime.now(UTC),
        )


def test_schema_matches_migration(catalog):
    _, factory, _, _, _ = catalog
    with factory() as session:
        assert (
            session.scalar(text("select version_num from alembic_version"))
            == "0002_source_recovery"
        )
