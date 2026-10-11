"""PostgreSQL-only search integration and fixed synthetic Recall@10 harness."""

from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.contracts.corpus import SearchRequest
from app.contracts.evidence import EvidenceRef as EvidenceRefDTO
from app.corpus.models import DocumentChunk, ExtractionRun, Snapshot, SnapshotMember
from app.corpus.service import CorpusError, CorpusService, SnapshotManifest
from app.evidence.service import EvidenceService
from app.evidence.validation import EvidenceError, canonical_hash
from app.ingestion.gateway import FetchGateway
from app.ingestion.policy import AcquisitionPolicy
from app.ingestion.service import IngestionService
from app.registry.models import Bank, Blob, Source, SourceFetch, SourcePolicy, SourceVersion
from app.search.service import SnapshotSearchService
from app.storage.local import LocalBlobStore
from app.tariffs.models import EvidenceRef, FactReview, PublishedFact, TariffCandidate


@pytest.fixture
def search_db(tmp_path):
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
    store = LocalBlobStore(tmp_path / "search-synthetic-originals")
    snapshot_id = str(uuid4())
    all_codes = ("sber", "vtb", "alfa", "kuban_credit")
    doc_specs = (("sber", "sber"), ("vtb", "vtb"))
    ids_by_code: dict[str, dict[str, str]] = {}
    manifest_documents: list[dict[str, object]] = []
    bank_ids: dict[str, str] = {}
    with factory.begin() as session:
        for code in all_codes:
            bank = session.scalar(select(Bank).where(Bank.code == code))
            if bank is None:
                bank = Bank(id=str(uuid4()), code=code, name=f"Synthetic {code}")
                session.add(bank)
                session.flush()
            bank_ids[code] = bank.id
        for code, slug in doc_specs:
            ids = {
                key: str(uuid4())
                for key in ("source", "policy", "version", "fetch", "extraction", "blob")
            }
            ids_by_code[code] = ids
            url_value = f"https://example.com/{slug}-{uuid4().hex}.pdf"
            ids["url"] = url_value
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
            receipt = store.put(
                [f"%PDF-1.7 synthetic {slug} original".encode()], "pdf", "synthetic"
            )
            session.add(
                SourcePolicy(
                    id=ids["policy"],
                    bank_id=bank_ids[code],
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
                    bank_id=bank_ids[code],
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
            raw_hash = receipt.sha256
            ids["raw_hash"] = raw_hash
            extraction_hash = hashlib.sha256(f"{slug} extraction".encode()).hexdigest()
            session.add(
                ExtractionRun(
                    id=ids["extraction"],
                    source_version_id=ids["version"],
                    raw_sha256=raw_hash,
                    extraction_sha256=extraction_hash,
                    parser_version="search-test-1",
                    corpus_kind="synthetic",
                    status="ok",
                )
            )
            session.flush()
            texts = _fixture_texts(code)
            if code == "sber":
                texts = texts + ("особенныймаркер " + "условия " * 1300,)
            for ordinal, text in enumerate(texts):
                session.add(
                    DocumentChunk(
                        id=str(uuid4()),
                        extraction_run_id=ids["extraction"],
                        ordinal=ordinal,
                        text=text,
                        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                        locator={"kind": "pdf", "physical_page": ordinal + 1},
                        relations=[],
                        search_vector=func.to_tsvector("simple", text),
                    )
                )
            manifest_documents.append(
                {
                    "bank_code": code,
                    "source_id": ids["source"],
                    "source_version_id": ids["version"],
                    "source_fetch_id": ids["fetch"],
                    "policy_id": ids["policy"],
                    "extraction_run_id": ids["extraction"],
                    "sha256": raw_hash,
                    "acquisition_method": "automatic",
                    "original_url": url_value,
                    "final_url": url_value,
                    "acquired_at": now.isoformat(),
                    "scope": {"region": "RU-KDA", "segment": "SME"},
                    "effective_date": None,
                    "document_type": f"synthetic_{slug}_terms",
                }
            )
        session.flush()
        snapshot = Snapshot(
            id=snapshot_id,
            revision=int(str(int(uuid4().int % 1_000_000_000) + 1)),
            corpus_kind="synthetic",
            state="draft",
        )
        session.add(snapshot)
        session.flush()

    missing = [
        {
            "bank_code": code,
            "document_type": "salary_terms",
            "reason": "Not represented by this fixed fixture.",
            "basis_reference": "synthetic-test",
        }
        for code in ("alfa", "kuban_credit")
    ]
    manifest = SnapshotManifest.model_validate(
        {
            "snapshot_id": snapshot_id,
            "revision": snapshot.revision,
            "corpus_kind": "synthetic",
            "region": "RU-KDA",
            "employer_segment": "SME",
            "documents": manifest_documents,
            "missing_documents": missing,
        }
    )
    with factory.begin() as session:
        for item in manifest.documents:
            session.add(
                SnapshotMember(
                    snapshot_id=snapshot_id,
                    source_version_id=str(item.source_version_id),
                    extraction_run_id=str(item.extraction_run_id),
                )
            )
        session.flush()
        _add_published_fixture(session, ids_by_code["sber"], snapshot_id, bank_ids["sber"], "sber")
        _add_published_fixture(session, ids_by_code["vtb"], snapshot_id, bank_ids["vtb"], "vtb")
        session.get(Snapshot, snapshot_id).state = "frozen"
        frozen = session.get(Snapshot, snapshot_id)
        frozen.frozen_at = now
        frozen.manifest_sha256 = manifest.manifest_sha256
        session.flush()
        other_revision = Snapshot(
            id=str(uuid4()),
            revision=snapshot.revision + 1,
            corpus_kind="synthetic",
            state="draft",
        )
        session.add(other_revision)
        session.flush()
        other_extraction = ExtractionRun(
            id=str(uuid4()),
            source_version_id=ids_by_code["sber"]["version"],
            raw_sha256=ids_by_code["sber"]["raw_hash"],
            extraction_sha256=hashlib.sha256(b"other snapshot extraction").hexdigest(),
            parser_version="search-test-other-revision",
            corpus_kind="synthetic",
            status="ok",
        )
        session.add(other_extraction)
        session.flush()
        other_text = "текст только другая ревизия snapshotsegundo"
        session.add(
            DocumentChunk(
                id=str(uuid4()),
                extraction_run_id=other_extraction.id,
                ordinal=0,
                text=other_text,
                text_sha256=hashlib.sha256(other_text.encode()).hexdigest(),
                locator={"kind": "html", "element_path": "/html/body/p[1]"},
                relations=[],
                search_vector=func.to_tsvector("simple", other_text),
            )
        )
        session.add(
            SnapshotMember(
                snapshot_id=other_revision.id,
                source_version_id=ids_by_code["sber"]["version"],
                extraction_run_id=other_extraction.id,
            )
        )
    settings = Settings(app_env="test", storage_root=store.root)
    ingestion = IngestionService(factory, settings, store, FetchGateway(settings, store))
    corpus = CorpusService(ingestion)
    evidence = EvidenceService(corpus)
    service = SnapshotSearchService(
        corpus,
        evidence,
        lambda requested: manifest if requested == manifest.snapshot_id else _unknown_manifest(),
    )
    yield service, factory, manifest, ids_by_code, store
    outer.rollback()
    connection.close()
    engine.dispose()


def _unknown_manifest() -> SnapshotManifest:
    raise ValueError("SNAPSHOT_UNKNOWN")


def _fixture_texts(code: str) -> tuple[str, ...]:
    if code == "sber":
        return (
            "Обслуживание расчетного счета стоит 300 рублей в месяц при подключении пакета.",
            "Заработная плата начисляется сотрудникам банка согласно условиям проекта.",
            "Плата за перевод составляет 0.35% от суммы операции; действует условие тарифа.",
            "Код продукта СБЕР-ПП, номер тарифа 40817, обозначение ₽ и ставка 0.35%.",
        ) + tuple(
            f"Банк обслуживает зарплатный проект, документ fixture {index}." for index in range(11)
        )
    return ("Банк ВТБ предлагает отдельный расчетный счет и пакет обслуживания.",)


def _add_published_fixture(
    session, ids: dict[str, str], snapshot_id: str, bank_id: str, bank_code: str
) -> None:
    extraction = session.get(ExtractionRun, ids["extraction"])
    chunk = (
        session.scalar(
            select(DocumentChunk).where(
                DocumentChunk.extraction_run_id == ids["extraction"], DocumentChunk.ordinal == 0
            )
        )
        if bank_code == "sber"
        else None
    )
    candidate_id, evidence_id, review_id = str(uuid4()), str(uuid4()), str(uuid4())
    payload = {
        "id": candidate_id,
        "bank_code": bank_code,
        "metric_code": "account_monthly_fee",
        "corpus_kind": "synthetic",
        "publication_state": "pending_review",
        "value": {"kind": "money", "amount": "300", "currency": "RUB"},
        "evidence_ids": [evidence_id] if chunk is not None else [],
    }
    session.add(
        TariffCandidate(
            id=candidate_id,
            extraction_run_id=ids["extraction"],
            bank_id=bank_id,
            metric_code="account_monthly_fee",
            payload=payload,
            payload_sha256=canonical_hash(payload),
            corpus_kind="synthetic",
        )
    )
    session.flush()
    evidence_proof: dict[str, str] = {}
    if chunk is not None:
        ref_fields = {
            "id": evidence_id,
            "source_version_id": ids["version"],
            "extraction_run_id": ids["extraction"],
            "chunk_id": chunk.id,
            "raw_sha256": extraction.raw_sha256,
            "extraction_sha256": extraction.extraction_sha256,
            "quote": "300",
            "quote_start": chunk.text.index("300"),
            "quote_end": chunk.text.index("300") + 3,
            "locator": chunk.locator,
            "support_role": "value",
            "original_url": ids["url"],
            "acquired_at": datetime.now(UTC),
        }
        # This ref is tied to the exact fixture chunk and persisted locator.
        session.add(EvidenceRef(candidate_id=candidate_id, **ref_fields))
        session.flush()
        ref_dto = EvidenceRefDTO.model_validate(ref_fields)
        evidence_proof[evidence_id] = canonical_hash(ref_dto.model_dump(mode="json"))
    proof = {
        "candidate_id": candidate_id,
        "candidate_sha256": canonical_hash(payload),
        "extraction_run_id": extraction.id,
        "raw_sha256": extraction.raw_sha256,
        "extraction_sha256": extraction.extraction_sha256,
        "parser_version": extraction.parser_version,
        "evidence": evidence_proof,
    }
    session.add(
        FactReview(
            id=review_id,
            candidate_id=candidate_id,
            reviewer_label="synthetic fixture reviewer",
            decision="approved",
            reason="Explicit synthetic search integration fixture",
            validation={
                "valid": True,
                "technical_valid": True,
                "semantic_confirmed": True,
                "snapshot_id": snapshot_id,
                "proof": proof,
            },
        )
    )
    session.flush()
    session.add(
        PublishedFact(
            id=str(uuid4()),
            snapshot_id=snapshot_id,
            candidate_id=candidate_id,
            review_id=review_id,
        )
    )
    session.flush()


def _search(service: SnapshotSearchService, manifest: SnapshotManifest, query: str, **kwargs):
    return asyncio.run(
        service.search_with_status(
            SearchRequest(snapshot_id=manifest.snapshot_id, query=query, **kwargs)
        )
    )


def test_russian_morphology_and_search_vector_gin(search_db) -> None:
    service, _, manifest, _, _ = search_db
    result = _search(service, manifest, "обслуживания")
    assert result.hits
    assert any("Обслуживание" in hit.text for hit in result.hits)


def test_simple_fallback_matches_codes_numbers_and_symbols(search_db) -> None:
    service, _, manifest, _, _ = search_db
    result = _search(service, manifest, "40817 СБЕР-ПП 0.35%")
    assert any("40817" in hit.text for hit in result.hits)


def test_bank_and_metric_filters_are_applied(search_db) -> None:
    service, _, manifest, _, _ = search_db
    bank_hits = _search(service, manifest, "обслуживание", bank_codes=("vtb",))
    assert bank_hits.hits and all(
        hit.source_version_id == manifest.documents[1].source_version_id for hit in bank_hits.hits
    )
    metric_hits = _search(service, manifest, "обслуживание", metric_codes=("account_monthly_fee",))
    assert metric_hits.hits
    assert all(hit.evidence_ids for hit in metric_hits.hits)


def test_top_ten_ranking_and_deterministic_tie_break(search_db) -> None:
    service, _, manifest, _, _ = search_db
    first = _search(service, manifest, "зарплатный проект", limit=10)
    second = _search(service, manifest, "зарплатный проект", limit=10)
    assert len(first.hits) == 10
    assert [hit.chunk_id for hit in first.hits] == [hit.chunk_id for hit in second.hits]
    assert list(first.hits) == sorted(first.hits, key=lambda hit: -hit.score)


def test_zero_results_has_explicit_absence_of_evidence(search_db) -> None:
    service, _, manifest, _, _ = search_db
    result = _search(service, manifest, "космический телескоп")
    assert result.hits == ()
    assert result.absence_of_evidence is True
    assert result.status == "absence_of_evidence"


def test_large_hit_is_omitted_without_false_absence(search_db) -> None:
    service, _, manifest, _, _ = search_db
    result = _search(service, manifest, "особенныймаркер")
    assert result.hits == ()
    assert result.status == "result_exceeds_output_bound"
    assert result.omitted_oversize is True
    assert result.absence_of_evidence is False


def test_cross_snapshot_content_does_not_leak(search_db) -> None:
    service, _, manifest, _, _ = search_db
    result = _search(service, manifest, "snapshotsegundo")
    assert result.hits == ()
    assert result.absence_of_evidence


def test_revoked_permission_blocks_search(search_db) -> None:
    service, factory, manifest, ids_by_code, _ = search_db
    with factory.begin() as session:
        session.get(SourcePolicy, ids_by_code["sber"]["policy"]).collection_decision = "denied"
    with pytest.raises(CorpusError, match="PERMISSION_REVOKED"):
        _search(service, manifest, "обслуживание")


@pytest.mark.parametrize("state", ["rejected", "quarantine"])
def test_rejected_or_quarantined_member_is_not_searchable(search_db, state: str) -> None:
    service, factory, manifest, ids_by_code, _ = search_db
    with factory.begin() as session:
        session.get(SourceVersion, ids_by_code["sber"]["version"]).content_state = state
    with pytest.raises(CorpusError, match="SOURCE_VERSION_NOT_ACCEPTED"):
        _search(service, manifest, "обслуживание")


def test_synthetic_snapshot_cannot_be_read_as_real(search_db) -> None:
    service, _, manifest, _, _ = search_db
    contaminated = manifest.model_copy(update={"corpus_kind": "real"})
    service.manifest_provider = lambda _snapshot_id: contaminated
    with pytest.raises(EvidenceError, match="SNAPSHOT_NOT_READABLE"):
        _search(service, contaminated, "обслуживание")


def test_unpublished_candidate_never_becomes_search_evidence(search_db) -> None:
    service, factory, manifest, ids_by_code, _ = search_db
    with factory.begin() as session:
        extraction = session.get(ExtractionRun, ids_by_code["sber"]["extraction"])
        bank = session.scalar(select(Bank).where(Bank.code == "sber"))
        chunk = session.scalar(
            select(DocumentChunk).where(
                DocumentChunk.extraction_run_id == extraction.id, DocumentChunk.ordinal == 1
            )
        )
        candidate_id = str(uuid4())
        payload = {
            "id": candidate_id,
            "bank_code": "sber",
            "metric_code": "payroll_credit_fee",
            "corpus_kind": "synthetic",
            "publication_state": "pending_review",
            "evidence_ids": [],
        }
        session.add(
            TariffCandidate(
                id=candidate_id,
                extraction_run_id=extraction.id,
                bank_id=bank.id,
                metric_code="payroll_credit_fee",
                payload=payload,
                payload_sha256=canonical_hash(payload),
                corpus_kind="synthetic",
            )
        )
        session.flush()
        session.add(
            EvidenceRef(
                candidate_id=candidate_id,
                source_version_id=ids_by_code["sber"]["version"],
                extraction_run_id=extraction.id,
                chunk_id=chunk.id,
                raw_sha256=extraction.raw_sha256,
                extraction_sha256=extraction.extraction_sha256,
                quote=chunk.text[:12],
                quote_start=0,
                quote_end=12,
                locator=chunk.locator,
                support_role="value",
                original_url="https://example.com/unpublished.pdf",
                acquired_at=datetime.now(UTC),
            )
        )
    result = _search(service, manifest, "начисляется")
    unpublished_chunk = next(hit for hit in result.hits if "начисляется" in hit.text)
    assert unpublished_chunk.evidence_ids == ()


def test_hit_has_exact_version_hash_evidence_and_locator(search_db) -> None:
    service, _, manifest, ids_by_code, _ = search_db
    result = _search(service, manifest, "300 рублей")
    hit = next(hit for hit in result.hits if "300 рублей" in hit.text)
    assert hit.source_version_id == UUID(ids_by_code["sber"]["version"])
    assert hit.snapshot_id == manifest.snapshot_id
    assert hit.raw_sha256 == manifest.documents[0].sha256
    assert hit.locator.kind == "pdf" and hit.locator.physical_page == 1
    assert len(hit.evidence_ids) == 1


def test_query_is_parameterized_and_query_size_is_bounded(search_db) -> None:
    service, _, manifest, _, _ = search_db
    injection = "'; DROP TABLE document_chunks; --"
    _search(service, manifest, injection)
    with pytest.raises(ValueError):
        SearchRequest(snapshot_id=manifest.snapshot_id, query="x" * 1001)
    with pytest.raises(ValueError, match="SEARCH_QUERY_INVALID"):
        asyncio.run(
            service.search_with_status(SearchRequest(snapshot_id=manifest.snapshot_id, query="  "))
        )
    assert asyncio.run(
        service.search_with_status(
            SearchRequest(snapshot_id=manifest.snapshot_id, query="обслуживание", limit=10)
        )
    ).hits


def test_fixed_synthetic_recall_at_10_harness(search_db) -> None:
    """Repeatable fixture score; never reported as a real-corpus evaluation."""
    service, _, manifest, _, _ = search_db
    queries = (("300 рублей", {("sber", 0)}), ("СБЕР-ПП", {("sber", 3)}))
    scores: list[float] = []
    for query, relevant_banks in queries:
        result = _search(service, manifest, query, limit=10)
        with service.factory() as session:
            relevant_rows = session.execute(
                select(Bank.code, DocumentChunk.ordinal, DocumentChunk.id)
                .join(Source, Source.bank_id == Bank.id)
                .join(SourceVersion, SourceVersion.source_id == Source.id)
                .join(SnapshotMember, SnapshotMember.source_version_id == SourceVersion.id)
                .join(ExtractionRun, ExtractionRun.id == SnapshotMember.extraction_run_id)
                .join(DocumentChunk, DocumentChunk.extraction_run_id == ExtractionRun.id)
                .where(
                    SnapshotMember.snapshot_id == str(manifest.snapshot_id),
                    Bank.code == next(iter({bank for bank, _ in relevant_banks})),
                    DocumentChunk.ordinal.in_([ordinal for _, ordinal in relevant_banks]),
                )
            ).all()
        expected_ids = {UUID(chunk_id) for _, _, chunk_id in relevant_rows}
        found_ids = {hit.chunk_id for hit in result.hits} & expected_ids
        scores.append(len(found_ids) / len(expected_ids) if expected_ids else 1.0)
    assert scores == [1.0, 1.0]
