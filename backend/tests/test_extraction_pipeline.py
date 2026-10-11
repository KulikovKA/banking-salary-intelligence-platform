"""PostgreSQL integration for the accepted-original extraction pipeline."""

from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from uuid import uuid4

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.auth import models as _auth_models  # noqa: F401
from app.config import Settings
from app.contracts.parsing import ParseRequest
from app.corpus.models import DocumentChunk, ExtractionRun
from app.corpus.service import CorpusError, CorpusService, SnapshotManifest
from app.db.base import Base
from app.ingestion.gateway import FetchGateway
from app.ingestion.policy import AcquisitionPolicy
from app.ingestion.service import IngestionService
from app.llm import models as _llm_models  # noqa: F401
from app.parsing.html import PARSER_VERSION as HTML_VERSION
from app.parsing.html import HtmlParser
from app.parsing.pdf import PARSER_VERSION as PDF_VERSION
from app.parsing.pdf import PdfParser
from app.parsing.runner import BoundedParseCrash, BoundedParseTimeout
from app.parsing.service import ExtractionPipeline
from app.parsing.xlsx import PARSER_VERSION as XLSX_VERSION
from app.parsing.xlsx import XlsxParser
from app.registry.models import (
    Bank,
    Blob,
    Source,
    SourceFetch,
    SourcePolicy,
    SourceVersion,
)
from app.storage.local import LocalBlobStore
from app.tariffs.models import EvidenceRef, FactReview, PublishedFact, TariffCandidate


def _pdf_bytes(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 60 700 Td ({escaped}) Tj ET\n".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [5 0 R] /Count 1 >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /ProcSet [/PDF /Text] >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 3 0 R >> >> /Contents 6 0 R >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"endstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(data)


def _xlsx_bytes(value: str = "100 RUB") -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Rates"
    sheet["B2"] = value
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _html_bytes(text: str = "Обслуживание счета — 100 ₽ в месяц.") -> bytes:
    return (
        "<!doctype html><html><body><p>"
        + text
        + "</p></body></html>"
    ).encode("utf-8")


@pytest.fixture
def pipeline_db(tmp_path: Path):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT RUN: TEST_DATABASE_URL is not set; PostgreSQL integration required")
    engine = create_engine(database_url)
    connection = engine.connect()
    outer = connection.begin()
    factory = sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    store = LocalBlobStore(tmp_path / "synthetic-originals")
    settings = Settings(app_env="test", storage_root=store.root)
    ingestion = IngestionService(factory, settings, store, FetchGateway(settings, store))
    corpus = CorpusService(ingestion)
    pipeline = ExtractionPipeline(corpus)
    yield factory, store, corpus, pipeline
    outer.rollback()
    connection.close()
    engine.dispose()


@pytest.fixture
def concurrent_pipeline_db(tmp_path: Path):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT RUN: TEST_DATABASE_URL is not set; PostgreSQL integration required")
    engine = create_engine(database_url)
    schema = f"snap08_{uuid4().hex}"
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    schema_engine = engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(schema_engine)
    factory = sessionmaker(bind=schema_engine, expire_on_commit=False)
    store = LocalBlobStore(tmp_path / "concurrent-synthetic-originals")
    settings = Settings(app_env="test", storage_root=store.root)
    ingestion = IngestionService(factory, settings, store, FetchGateway(settings, store))
    corpus = CorpusService(ingestion)
    yield factory, store, corpus, ExtractionPipeline(corpus)
    schema_engine.dispose()
    with engine.begin() as connection:
        connection.execute(DropSchema(schema, cascade=True))
    engine.dispose()


def _seed_document(
    pipeline_db,
    kind: str,
    body: bytes,
    *,
    parser_version: str | None = None,
    source_state: str = "accepted",
):
    factory, store, corpus, pipeline = pipeline_db
    now = datetime.now(UTC)
    suffix = {"pdf": "pdf", "xlsx": "xlsx", "html": "html"}[kind]
    url = f"https://example.com/{uuid4().hex}.{suffix}"
    ids = {name: str(uuid4()) for name in (
        "source", "policy", "version", "fetch", "blob", "snapshot"
    )}
    receipt = store.put([body], kind, "synthetic")
    grant = AcquisitionPolicy(
        source_id=ids["source"],
        decision="approved",
        corpus_kind="synthetic",
        method="automatic",
        allowed_urls=(url,),
        reviewer="synthetic test",
        official_relationship="synthetic fixture",
        acquisition_basis="synthetic fixture",
        storage_basis="synthetic fixture",
        reuse_basis="synthetic fixture",
        terms_evidence="synthetic fixture",
        purpose="integration test",
        expires_at=now + timedelta(days=1),
        rate_seconds=0.01,
    )
    scope = {"region": "RU-KDA", "segment": "SME"}
    with factory.begin() as session:
        bank = session.scalar(select(Bank).where(Bank.code == "sber"))
        if bank is None:
            bank = Bank(id=str(uuid4()), code="sber", name="Synthetic bank")
            session.add(bank)
            session.flush()
        session.add(
            SourcePolicy(
                id=ids["policy"],
                bank_id=bank.id,
                allowed_hosts=["example.com"],
                collection_decision="approved",
                reason="synthetic integration fixture",
                acquisition_config={"automatic": grant.model_dump(mode="json")},
            )
        )
        session.flush()
        session.add(
            Source(
                id=ids["source"],
                bank_id=bank.id,
                policy_id=ids["policy"],
                url=url,
                canonical_url=url,
                kind=kind,
                scope_hint=scope,
                state="unknown",
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
                metadata_json={"applicability": scope, "effective_date": None},
                content_state=source_state,
                accepted_at=now if source_state == "accepted" else None,
                accepted_by="synthetic test" if source_state == "accepted" else None,
            )
        )
        session.flush()
        session.add(
            SourceFetch(
                id=ids["fetch"],
                source_id=ids["source"],
                requested_url=url,
                final_url=url,
                redirect_chain=[],
                result="success",
                acquisition_method="automatic",
                source_version_id=ids["version"],
                fetched_at=now,
            )
        )
    manifest = SnapshotManifest.model_validate({
        "snapshot_id": ids["snapshot"],
        "revision": int(ids["snapshot"].replace("-", "")[:6], 16) + 1,
        "corpus_kind": "synthetic",
        "region": "RU-KDA",
        "employer_segment": "SME",
        "documents": [{
            "bank_code": "sber",
            "source_id": ids["source"],
            "source_version_id": ids["version"],
            "source_fetch_id": ids["fetch"],
            "policy_id": ids["policy"],
            "extraction_run_id": None,
            "sha256": receipt.sha256,
            "acquisition_method": "automatic",
            "original_url": url,
            "final_url": url,
            "acquired_at": now.isoformat(),
            "scope": scope,
            "effective_date": None,
            "document_type": "synthetic_salary_terms",
        }],
        "missing_documents": [{
            "bank_code": code,
            "document_type": "salary_project_terms",
            "reason": "Synthetic fixture for an unselected bank.",
            "basis_reference": "test-only",
        } for code in ("vtb", "alfa", "kuban_credit")],
    })
    corpus.add_version(manifest, 0)
    receipt_path = store.verify(receipt)
    version = parser_version or {
        "pdf": PDF_VERSION, "xlsx": XLSX_VERSION, "html": HTML_VERSION
    }[kind]
    parser = {"pdf": PdfParser, "xlsx": XlsxParser, "html": HtmlParser}[kind]()
    parse_path = receipt_path
    with TemporaryDirectory() as temp_dir:
        if kind == "xlsx":
            parse_path = Path(temp_dir) / "synthetic.xlsx"
            parse_path.write_bytes(body)
        parsed = parser.parse(
            ParseRequest(
                source_version_id=ids["version"],
                raw_sha256=receipt.sha256,
                kind=kind,
                corpus_kind="synthetic",
                parser_version=version,
            ),
            str(parse_path),
        )
    return ids, manifest, parsed, pipeline


def _mapping_for_block(parsed, *, kind: str, metric: str = "account_monthly_fee"):
    block = next(
        (
            block for block in parsed.blocks
            if "100" in block.text or "0" in block.text or "?????????????" in block.text.lower()
        ),
        parsed.blocks[0],
    )
    rule = {"metric_code": metric}
    if block.locator.kind == "xlsx":
        rule["value_cell"] = {
            "sheet": block.locator.sheet,
            "cell_range": block.locator.cell_range,
        }
    else:
        rule["value_block_id"] = str(block.block_id)
    return json.dumps({"version": 1, "rules": [rule]})


_CONTEXT = {"payer": "employer", "operation": "account_maintenance"}


@pytest.mark.parametrize("kind", ["pdf", "xlsx", "html"])
def test_synthetic_original_reaches_postgres_candidate_and_exact_evidence(
    pipeline_db, kind: str
) -> None:
    body = {
        "pdf": _pdf_bytes("100 RUB"),
        "xlsx": _xlsx_bytes(),
        "html": _html_bytes(),
    }[kind]
    ids, manifest, parsed, pipeline = _seed_document(pipeline_db, kind, body)
    assert parsed.status == "ok"
    mapping = _mapping_for_block(parsed, kind=kind)
    result = pipeline.run(
        manifest,
        ids["version"],
        parser_version=parsed.parser_version,
        operator_mapping=mapping,
        context=_CONTEXT,
    )
    assert result.status == "ok"
    assert result.extraction_id is not None
    assert result.chunk_count == len(parsed.blocks)
    assert result.candidate_count == 1

    factory = pipeline_db[0]
    with factory() as session:
        run = session.get(ExtractionRun, result.extraction_id)
        candidate = session.scalar(
            select(TariffCandidate).where(
                TariffCandidate.extraction_run_id == result.extraction_id
            )
        )
        assert run is not None and run.raw_sha256 == manifest.documents[0].sha256
        assert candidate is not None
        from app.contracts.tariffs import TariffCandidate as CandidateDTO
        dto = CandidateDTO.model_validate(candidate.payload)
        assert dto.publication_state == "pending_review"
        assert dto.bank_code == "sber" and dto.corpus_kind == "synthetic"
        refs = session.scalars(
            select(EvidenceRef).where(EvidenceRef.candidate_id == candidate.id)
        ).all()
        assert refs
        for ref in refs:
            chunk = session.get(DocumentChunk, ref.chunk_id)
            assert chunk is not None and chunk.extraction_run_id == result.extraction_id
            assert chunk.text_sha256 == hashlib.sha256(chunk.text.encode()).hexdigest()
            assert chunk.text[ref.quote_start:ref.quote_end] == ref.quote
            assert ref.locator == chunk.locator
            assert ref.source_version_id == ids["version"]
            assert ref.raw_sha256 == run.raw_sha256
            assert ref.extraction_sha256 == run.extraction_sha256
        assert not session.scalars(
            select(FactReview).where(FactReview.candidate_id == candidate.id)
        ).all()
        assert not session.scalars(
            select(PublishedFact).where(PublishedFact.candidate_id == candidate.id)
        ).all()


def test_repeat_is_idempotent_and_new_parser_version_has_scoped_identity(pipeline_db) -> None:
    body = _html_bytes()
    ids, manifest, parsed, pipeline = _seed_document(pipeline_db, "html", body)
    first = pipeline.run(
        manifest, ids["version"], parser_version=HTML_VERSION, context=_CONTEXT
    )
    repeat = pipeline.run(
        manifest, ids["version"], parser_version=HTML_VERSION, context=_CONTEXT
    )
    revised = pipeline.run(
        manifest, ids["version"], parser_version=f"{HTML_VERSION}-reviewed", context=_CONTEXT
    )
    assert first.extraction_id == repeat.extraction_id
    assert repeat.idempotent is True
    assert first.candidate_count == repeat.candidate_count == revised.candidate_count == 1
    assert revised.extraction_id != first.extraction_id
    with pipeline_db[0]() as session:
        runs = session.scalars(
            select(ExtractionRun).where(
                ExtractionRun.source_version_id == ids["version"]
            )
        ).all()
        candidates = session.scalars(
            select(TariffCandidate).where(
                TariffCandidate.extraction_run_id.in_(
                    [first.extraction_id, revised.extraction_id]
                )
            )
        ).all()
        assert len(runs) == 2
        assert len({row.id for row in candidates}) == 2


def test_concurrent_repeats_commit_one_evidence_chain(concurrent_pipeline_db) -> None:
    ids, manifest, _, pipeline = _seed_document(
        concurrent_pipeline_db, "html", _html_bytes()
    )
    barrier = Barrier(2)
    parser = pipeline.parse_runner

    def synchronized_parse(*args, **kwargs):
        barrier.wait(timeout=15)
        return parser(*args, **kwargs)

    pipeline.parse_runner = synchronized_parse
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                pipeline.run,
                manifest,
                ids["version"],
                parser_version=HTML_VERSION,
                context=_CONTEXT,
            )
            for _ in range(2)
        ]
        results = [future.result(timeout=60) for future in futures]

    assert results[0].extraction_id == results[1].extraction_id
    assert sorted(result.idempotent for result in results) == [False, True]
    assert all(result.candidate_count == 1 for result in results)
    with concurrent_pipeline_db[0]() as session:
        extraction_id = results[0].extraction_id
        assert extraction_id is not None
        assert session.scalar(
            select(func.count()).select_from(ExtractionRun).where(
                ExtractionRun.id == extraction_id
            )
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.extraction_run_id == extraction_id
            )
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(TariffCandidate).where(
                TariffCandidate.extraction_run_id == extraction_id
            )
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(EvidenceRef).where(
                EvidenceRef.extraction_run_id == extraction_id
            )
        ) >= 1


def test_duplicate_operator_mapping_and_auto_detection_merge_evidence(pipeline_db) -> None:
    body = _html_bytes()
    ids, manifest, parsed, pipeline = _seed_document(pipeline_db, "html", body)
    mapping = _mapping_for_block(parsed, kind="html")
    result = pipeline.run(
        manifest,
        ids["version"],
        parser_version=HTML_VERSION,
        operator_mapping=mapping,
        context=_CONTEXT,
    )
    assert result.candidate_count == 1
    with pipeline_db[0]() as session:
        candidates = session.scalars(
            select(TariffCandidate).where(
                TariffCandidate.extraction_run_id == result.extraction_id
            )
        ).all()
        refs = session.scalars(
            select(EvidenceRef).where(EvidenceRef.candidate_id == candidates[0].id)
        ).all()
    assert len(candidates) == 1
    assert {ref.support_role for ref in refs} >= {"value", "unit"}


def test_unknown_value_and_invalid_mapping_remain_diagnostics(pipeline_db) -> None:
    body = _html_bytes("неизвестно")
    ids, manifest, parsed, pipeline = _seed_document(pipeline_db, "html", body)
    mapping = _mapping_for_block(parsed, kind="html")
    result = pipeline.run(
        manifest,
        ids["version"],
        parser_version=HTML_VERSION,
        operator_mapping=mapping,
        context=_CONTEXT,
    )
    assert result.candidate_count == 0
    codes = {item.code for item in result.diagnostics}
    assert "VALUE_UNKNOWN" in codes or "VALUE_UNIT_UNKNOWN" in codes

    other_ids, other_manifest, _, other_pipeline = _seed_document(
        pipeline_db, "html", _html_bytes()
    )
    invalid = json.dumps({
        "version": 1,
        "rules": [{
            "metric_code": "account_monthly_fee",
            "value_block_id": str(uuid4()),
        }],
    })
    failed_mapping = other_pipeline.run(
        other_manifest,
        other_ids["version"],
        parser_version=HTML_VERSION,
        operator_mapping=invalid,
        context=_CONTEXT,
    )
    # Independent automatic extraction remains available.
    assert failed_mapping.candidate_count == 1
    assert any(
        item.code == "OPERATOR_MAPPING_REFERENCE_MISSING"
        for item in failed_mapping.diagnostics
    )


def test_conditional_zero_and_individual_tariffs_are_not_flattened(pipeline_db) -> None:
    ids, manifest, _, pipeline = _seed_document(
        pipeline_db,
        "html",
        _html_bytes(
            "\u041e\u0431\u0441\u043b\u0443\u0436\u0438\u0432\u0430\u043d\u0438\u0435 "
            "\u0441\u0447\u0435\u0442\u0430: 0 \u20bd "
            "\u043f\u0440\u0438 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u0430\u043d\u0438\u0438 "
            "\u043e\u0441\u0442\u0430\u0442\u043a\u0430."
        ),
    )
    conditional = pipeline.run(
        manifest, ids["version"], parser_version=HTML_VERSION, context=_CONTEXT
    )
    assert conditional.candidate_count == 1
    with pipeline_db[0]() as session:
        candidate = session.scalar(
            select(TariffCandidate).where(
                TariffCandidate.extraction_run_id == conditional.extraction_id
            )
        )
        assert candidate is not None
        from app.contracts.tariffs import TariffCandidate as CandidateDTO
        dto = CandidateDTO.model_validate(candidate.payload)
        assert dto.value.kind == "money" and dto.value.amount == 0
        refs = session.scalars(
            select(EvidenceRef).where(EvidenceRef.candidate_id == candidate.id)
        ).all()
        assert "condition" in {ref.support_role for ref in refs}

    individual_ids, individual_manifest, parsed, individual_pipeline = _seed_document(
        pipeline_db, "html", _html_bytes("индивидуально")
    )
    mapping = _mapping_for_block(
        parsed, kind="html", metric="account_monthly_fee"
    )
    # The mapping's block is the exact unstructured individual tariff text.
    individual = individual_pipeline.run(
        individual_manifest,
        individual_ids["version"],
        parser_version=HTML_VERSION,
        operator_mapping=mapping,
        context=_CONTEXT,
    )
    assert individual.candidate_count == 1
    with pipeline_db[0]() as session:
        row = session.scalar(
            select(TariffCandidate).where(
                TariffCandidate.extraction_run_id == individual.extraction_id
            )
        )
        assert row is not None
        from app.contracts.tariffs import TariffCandidate as CandidateDTO
        dto = CandidateDTO.model_validate(row.payload)
        assert dto.value.kind == "individual"


def test_original_hash_permission_and_quarantine_are_checked_before_parse(pipeline_db) -> None:
    ids, manifest, _, pipeline = _seed_document(pipeline_db, "html", _html_bytes())
    real_corpus_view = manifest.model_copy(update={"corpus_kind": "real"})
    with pytest.raises(CorpusError, match="SNAPSHOT_IDENTITY_MISMATCH"):
        pipeline.run(
            real_corpus_view,
            ids["version"],
            parser_version=HTML_VERSION,
            context=_CONTEXT,
        )

    changed = manifest.model_copy(update={
        "documents": (
            manifest.documents[0].model_copy(update={"sha256": "f" * 64}),
        )
    })
    with pytest.raises(CorpusError, match="MANIFEST_HASH_MISMATCH"):
        pipeline.run(changed, ids["version"], parser_version=HTML_VERSION, context=_CONTEXT)

    with pipeline_db[0].begin() as session:
        session.get(SourcePolicy, ids["policy"]).collection_decision = "denied"
    with pytest.raises(CorpusError, match="PERMISSION_REVOKED"):
        pipeline.run(manifest, ids["version"], parser_version=HTML_VERSION, context=_CONTEXT)

    with pipeline_db[0].begin() as session:
        session.get(SourcePolicy, ids["policy"]).collection_decision = "approved"
        session.get(SourceVersion, ids["version"]).content_state = "quarantine"
    with pytest.raises(CorpusError, match="SOURCE_VERSION_NOT_ACCEPTED"):
        pipeline.run(manifest, ids["version"], parser_version=HTML_VERSION, context=_CONTEXT)
    with pipeline_db[0]() as session:
        assert session.scalar(
            select(func.count()).select_from(ExtractionRun).where(
                ExtractionRun.source_version_id == ids["version"]
            )
        ) == 0


@pytest.mark.parametrize("failure", [BoundedParseCrash, BoundedParseTimeout])
def test_parser_crash_or_timeout_leaves_no_extraction_chain(pipeline_db, failure) -> None:
    ids, manifest, _, _ = _seed_document(pipeline_db, "html", _html_bytes())

    def fail(*args, **kwargs):
        del args, kwargs
        raise failure()

    pipeline = ExtractionPipeline(pipeline_db[2], parse_runner=fail)
    with pytest.raises(failure):
        pipeline.run(
            manifest, ids["version"], parser_version=HTML_VERSION, context=_CONTEXT
        )
    with pipeline_db[0]() as session:
        assert session.scalar(
            select(func.count()).select_from(ExtractionRun).where(
                ExtractionRun.source_version_id == ids["version"]
            )
        ) == 0
        assert session.scalar(
            select(func.count()).select_from(DocumentChunk)
        ) == 0
        assert session.scalar(
            select(func.count()).select_from(TariffCandidate)
        ) == 0
        assert session.scalar(
            select(func.count()).select_from(EvidenceRef)
        ) == 0
