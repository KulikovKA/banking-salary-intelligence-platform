"""PostgreSQL-only coverage of snapshot integrity and append-only guarantees."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, inspect, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.corpus.models import (
    DocumentChunk,
    ExtractionRun,
    Snapshot,
    SnapshotMember,
)
from app.llm.models import LLMUsage
from app.registry.models import Bank, Blob, Source, SourceVersion
from app.tariffs.models import EvidenceRef, FactReview, PublishedFact, TariffCandidate


@pytest.fixture
def snapshot_db():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("NOT RUN: TEST_DATABASE_URL is not set; PostgreSQL integration required")
    engine = create_engine(url)
    connection = engine.connect()
    outer = connection.begin()
    factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    ids = {
        "bank": str(uuid4()),
        "source": str(uuid4()),
        "blob": str(uuid4()),
        "version": str(uuid4()),
        "corpus": f"syn_{uuid4().hex}",
        "raw_hash": "0" * 64,
    }
    with factory.begin() as session:
        session.add(Bank(id=ids["bank"], code=ids["corpus"], name="Synthetic test bank"))
        session.add(
            Source(
                id=ids["source"],
                bank_id=ids["bank"],
                url="https://example.invalid/synthetic.pdf",
                canonical_url="https://example.invalid/synthetic.pdf",
                kind="pdf",
                scope_hint={},
                state="unknown",
                corpus_kind="synthetic",
            )
        )
        session.add(
            Blob(
                id=ids["blob"],
                sha256=ids["raw_hash"],
                corpus_kind="synthetic",
                byte_size=10,
                media_type="application/pdf",
                storage_key=f"synthetic/{ids['raw_hash']}",
                verified_at=datetime.now(UTC),
            )
        )
        session.add(
            SourceVersion(
                id=ids["version"],
                source_id=ids["source"],
                blob_id=ids["blob"],
                metadata_json={"fixture": "synthetic"},
                content_state="accepted",
                accepted_at=datetime.now(UTC),
                accepted_by="test fixture",
            )
        )
    yield factory, ids, engine
    outer.rollback()
    connection.close()
    engine.dispose()


def _expect_rejected(factory: sessionmaker, statement: object) -> None:
    with pytest.raises(SQLAlchemyError):
        with factory.begin() as session:
            session.execute(statement)  # type: ignore[arg-type]


def _add_published_chain(factory: sessionmaker, ids: dict[str, str]) -> dict[str, str]:
    chain = {
        "extraction": str(uuid4()),
        "chunk": str(uuid4()),
        "snapshot": str(uuid4()),
        "candidate": str(uuid4()),
        "evidence": str(uuid4()),
        "review": str(uuid4()),
        "published": str(uuid4()),
        "extraction_hash": "1" * 64,
        "text_hash": "2" * 64,
        "payload_hash": "3" * 64,
    }
    with factory.begin() as session:
        session.add(
            ExtractionRun(
                id=chain["extraction"],
                source_version_id=ids["version"],
                raw_sha256=ids["raw_hash"],
                extraction_sha256=chain["extraction_hash"],
                parser_version="test-parser-1",
                corpus_kind="synthetic",
                status="ok",
            )
        )
        session.flush()
        session.add(
            DocumentChunk(
                id=chain["chunk"],
                extraction_run_id=chain["extraction"],
                ordinal=0,
                text="Fee",
                text_sha256=chain["text_hash"],
                locator={"kind": "pdf", "physical_page": 1},
                relations=[],
                search_vector="",
            )
        )
        session.add(
            Snapshot(id=chain["snapshot"], revision=1, corpus_kind="synthetic", state="draft")
        )
        session.flush()
        session.add(
            SnapshotMember(
                snapshot_id=chain["snapshot"],
                source_version_id=ids["version"],
                extraction_run_id=chain["extraction"],
            )
        )
        session.flush()
        payload = {
            "id": chain["candidate"],
            "bank_code": ids["corpus"],
            "metric_code": "account_monthly_fee",
            "corpus_kind": "synthetic",
            "publication_state": "pending_review",
            "value": {"kind": "money", "amount": "0", "currency": "RUB"},
        }
        session.add(
            TariffCandidate(
                id=chain["candidate"],
                extraction_run_id=chain["extraction"],
                bank_id=ids["bank"],
                metric_code="account_monthly_fee",
                payload=payload,
                payload_sha256=chain["payload_hash"],
                corpus_kind="synthetic",
            )
        )
        session.flush()
        session.add(
            EvidenceRef(
                id=chain["evidence"],
                candidate_id=chain["candidate"],
                source_version_id=ids["version"],
                extraction_run_id=chain["extraction"],
                chunk_id=chain["chunk"],
                raw_sha256=ids["raw_hash"],
                extraction_sha256=chain["extraction_hash"],
                quote="Fee",
                quote_start=0,
                quote_end=3,
                locator={"kind": "pdf", "physical_page": 1},
                support_role="value",
                original_url="https://example.invalid/synthetic.pdf",
                acquired_at=datetime.now(UTC),
            )
        )
        session.add(
            FactReview(
                id=chain["review"],
                candidate_id=chain["candidate"],
                reviewer_label="operator",
                user_id=None,
                decision="approved",
                reason="synthetic DB contract fixture",
                validation={"valid": True, "evidence_ids": [chain["evidence"]]},
            )
        )
        session.flush()
        session.add(
            PublishedFact(
                id=chain["published"],
                snapshot_id=chain["snapshot"],
                candidate_id=chain["candidate"],
                review_id=chain["review"],
            )
        )
        session.flush()
        session.execute(
            update(Snapshot)
            .where(Snapshot.id == chain["snapshot"])
            .values(
                state="frozen",
                frozen_at=datetime.now(UTC),
                manifest_sha256="f" * 64,
            )
        )
        session.flush()
        session.add(
            LLMUsage(
                request_id=str(uuid4()),
                user_id=None,
                window_started_at=datetime(2000, 1, 1, tzinfo=UTC),
                reserved_tokens=32,
                estimated=True,
                state="reserved",
                model_id="openai/gpt-oss-120b",
            )
        )
    return chain


def test_snapshot_schema_runs_on_postgresql_18(snapshot_db) -> None:
    factory, _, _ = snapshot_db
    with factory() as session:
        version = session.scalar(text("select current_setting('server_version_num')::int"))
        migration = session.scalar(text("select version_num from alembic_version"))
    assert version is not None and 180000 <= version < 190000
    assert migration == "0005_auth"
    with factory() as session:
        schema = inspect(session.connection())
        for table in ("fact_reviews", "llm_usage"):
            assert next(c for c in schema.get_columns(table) if c["name"] == "user_id")["nullable"]
            assert any(
                fk["constrained_columns"] == ["user_id"]
                and fk["referred_table"] == "users"
                and fk["options"].get("ondelete") == "RESTRICT"
                for fk in schema.get_foreign_keys(table)
            )


def test_provenance_review_publication_and_usage_rows_round_trip(snapshot_db) -> None:
    factory, ids, _ = snapshot_db
    chain = _add_published_chain(factory, ids)
    with factory() as session:
        fact = session.get(PublishedFact, chain["published"])
        assert fact is not None and fact.snapshot_id == chain["snapshot"]
        assert session.get(Snapshot, chain["snapshot"]).state == "frozen"  # type: ignore[union-attr]
        assert session.scalar(
            select(DocumentChunk.search_vector).where(DocumentChunk.id == chain["chunk"])
        )
        assert (
            session.scalar(select(LLMUsage.request_id).where(LLMUsage.state == "reserved"))
            is not None
        )


def test_frozen_membership_and_immutable_payloads_reject_raw_mutation(snapshot_db) -> None:
    factory, ids, _ = snapshot_db
    chain = _add_published_chain(factory, ids)
    _expect_rejected(
        factory,
        update(SnapshotMember)
        .where(SnapshotMember.snapshot_id == chain["snapshot"])
        .values(extraction_run_id=str(uuid4())),
    )
    _expect_rejected(
        factory,
        delete(SnapshotMember).where(SnapshotMember.snapshot_id == chain["snapshot"]),
    )
    _expect_rejected(
        factory,
        text(
            "insert into snapshot_members (snapshot_id, source_version_id, extraction_run_id) "
            "values (:snapshot, :version, :extraction)"
        ).bindparams(
            snapshot=chain["snapshot"],
            version=ids["version"],
            extraction=chain["extraction"],
        ),
    )
    _expect_rejected(
        factory,
        update(TariffCandidate)
        .where(TariffCandidate.id == chain["candidate"])
        .values(payload={"changed": True}),
    )
    _expect_rejected(
        factory,
        delete(FactReview).where(FactReview.id == chain["review"]),
    )


def test_usage_settlement_requires_actual_prompt_and_completion_totals(snapshot_db) -> None:
    factory, _, _ = snapshot_db
    with factory.begin() as session:
        session.add(
            LLMUsage(
                request_id=str(uuid4()),
                user_id=None,
                window_started_at=datetime(2000, 1, 1, tzinfo=UTC),
                reserved_tokens=16,
                estimated=False,
                state="reserved",
                model_id="openai/gpt-oss-120b",
            )
        )
    _expect_rejected(
        factory,
        text("update llm_usage set state = 'settled' where state = 'reserved'"),
    )


def test_duplicate_extraction_and_publication_are_rejected(snapshot_db) -> None:
    factory, ids, _ = snapshot_db
    chain = _add_published_chain(factory, ids)
    _expect_rejected(
        factory,
        text(
            """insert into extraction_runs
            (id, source_version_id, raw_sha256, extraction_sha256, parser_version,
             corpus_kind, status)
            values (:id, :version, :raw, :extraction_hash, 'test-parser-1', 'synthetic', 'ok')"""
        ).bindparams(
            id=str(uuid4()),
            version=ids["version"],
            raw=ids["raw_hash"],
            extraction_hash=chain["extraction_hash"],
        ),
    )
    _expect_rejected(
        factory,
        text(
            "insert into published_facts (id, snapshot_id, candidate_id, review_id) "
            "values (:id, :snapshot, :candidate, :review)"
        ).bindparams(
            id=str(uuid4()),
            snapshot=chain["snapshot"],
            candidate=chain["candidate"],
            review=chain["review"],
        ),
    )


def test_invalid_foreign_key_and_wrong_quote_are_rejected(snapshot_db) -> None:
    factory, ids, _ = snapshot_db
    chain = _add_published_chain(factory, ids)
    _expect_rejected(
        factory,
        text(
            """insert into evidence_refs
            (id, candidate_id, source_version_id, extraction_run_id, chunk_id,
             raw_sha256, extraction_sha256, quote, quote_start, quote_end, locator,
             support_role, original_url, acquired_at)
            values (:id, :candidate, :version, :extraction, :chunk,
             :raw, :extraction_hash, 'Fee', 0, 3, '{"kind":"pdf","physical_page":1}'::jsonb,
             'value', 'https://example.invalid/synthetic.pdf', now())"""
        ).bindparams(
            id=str(uuid4()),
            candidate=chain["candidate"],
            version=ids["version"],
            extraction=chain["extraction"],
            chunk=str(uuid4()),
            raw=ids["raw_hash"],
            extraction_hash=chain["extraction_hash"],
        ),
    )
    _expect_rejected(
        factory,
        text(
            """insert into evidence_refs
            (id, candidate_id, source_version_id, extraction_run_id, chunk_id,
             raw_sha256, extraction_sha256, quote, quote_start, quote_end, locator,
             support_role, original_url, acquired_at)
            values (:id, :candidate, :version, :extraction, :chunk,
             :raw, :extraction_hash, 'Fee', 1, 4, '{"kind":"pdf","physical_page":1}'::jsonb,
             'value', 'https://example.invalid/synthetic.pdf', now())"""
        ).bindparams(
            id=str(uuid4()),
            candidate=chain["candidate"],
            version=ids["version"],
            extraction=chain["extraction"],
            chunk=chain["chunk"],
            raw=ids["raw_hash"],
            extraction_hash=chain["extraction_hash"],
        ),
    )
