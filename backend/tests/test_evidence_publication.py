"""Synthetic original-backed evidence/review/publication on migrated PostgreSQL."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, attributes
from sqlalchemy.schema import CreateSchema, DropSchema
from test_extraction_pipeline import (
    _CONTEXT,
    _html_bytes,
    _mapping_for_block,
    _pdf_bytes,
    _seed_document,
    _xlsx_bytes,
)
from test_extraction_pipeline import pipeline_db as pipeline_db

from app.config import Settings
from app.corpus.models import DocumentChunk, ExtractionRun, SnapshotMember
from app.corpus.service import CorpusError, CorpusService
from app.db.base import make_session_factory
from app.evidence.service import EvidenceService
from app.evidence.validation import (
    EvidenceError,
    SemanticConfirmation,
    canonical_hash,
)
from app.ingestion.gateway import FetchGateway
from app.ingestion.service import IngestionService
from app.registry.models import SourcePolicy
from app.storage.local import LocalBlobStore
from app.tariffs.models import EvidenceRef, FactReview, PublishedFact, TariffCandidate


def setup_candidate(db, kind="html", text=None):
    body = {
        "html": _html_bytes(text or "Обслуживание счета — 100 RUB в месяц."),
        "pdf": _pdf_bytes("Employer account monthly servicing: 100 RUB"),
        "xlsx": _xlsx_bytes(),
    }[kind]
    ids, manifest, parsed, pipeline = _seed_document(db, kind, body)
    result = pipeline.run(
        manifest,
        ids["version"],
        parser_version=parsed.parser_version,
        context=_CONTEXT,
        operator_mapping=_mapping_for_block(parsed, kind=kind) if kind != "html" else None,
    )
    assert result.status == "ok"
    manifest = manifest.model_copy(
        update={
            "documents": (
                manifest.documents[0].model_copy(
                    update={"extraction_run_id": uuid_id(result.extraction_id)}
                ),
            )
        }
    )
    with db[0]() as session:
        candidate = session.scalar(
            select(TariffCandidate).where(TariffCandidate.extraction_run_id == result.extraction_id)
        )
        candidate_id = candidate.id
    return ids, manifest, candidate_id, EvidenceService(db[2])


def uuid_id(value):
    from uuid import UUID

    return UUID(value)


def confirmation(db, manifest, candidate_id, service):
    report = service.validate(manifest, candidate_id)
    assert report.technical_valid, report.errors
    assert not report.valid
    roles = {
        "value": {"value"},
        "unit": {"unit", "value"},
        "metric": {"scope", "value"},
        "payer": {"scope", "value"},
        "operation": {"scope", "value"},
        "relations": {"scope", "value", "condition", "unit"},
        "conditions": {"condition", "value"},
        "basis": {"basis", "value"},
        "period": {"unit", "basis", "condition", "scope", "value"},
        "date": {"date"},
        "interpretation": {"scope", "value", "condition", "unit", "basis", "date"},
        "geography": {"scope"},
        "employer_segment": {"scope"},
        "organization_category": {"scope"},
        "payroll_package": {"scope"},
        "contract_variant": {"scope"},
    }
    with db[0]() as session:
        refs = session.scalars(
            select(EvidenceRef).where(EvidenceRef.candidate_id == candidate_id)
        ).all()
        fields = {
            field: tuple(ref.id for ref in refs if ref.support_role in roles[field])
            for field in report.required_fields
        }
    return SemanticConfirmation(fields)


def approve(db, manifest, candidate_id, service):
    return service.review(
        manifest,
        candidate_id,
        decision="approved",
        reviewer_label="synthetic reviewer",
        reason="Synthetic fixture: operator checked each cited field and original.",
        confirmation=confirmation(db, manifest, candidate_id, service),
    )


@pytest.mark.parametrize("kind", ["pdf", "xlsx", "html"])
def test_actual_original_to_review_publication_freeze_and_limited_read(pipeline_db, kind):
    ids, manifest, candidate_id, service = setup_candidate(pipeline_db, kind)
    with pytest.raises(EvidenceError, match="SEMANTIC_CONFIRMATION_REQUIRED"):
        service.review(
            manifest,
            candidate_id,
            decision="approved",
            reviewer_label="test reviewer",
            reason="Technical match alone cannot approve.",
        )
    review_id = approve(pipeline_db, manifest, candidate_id, service)
    result = service.publish(manifest, candidate_id, review_id)
    assert not result.idempotent
    assert service.publish(manifest, candidate_id, review_id).idempotent
    service.corpus.freeze(manifest)
    facts = service.read_published(manifest)
    assert len(facts) == 1 and facts[0]["fact_id"] == result.fact_id
    assert "DATE_UNKNOWN" in facts[0]["limitations"]
    assert not facts[0]["eligible_for_comparison"]
    with pipeline_db[0]() as session:
        assert (
            session.get(TariffCandidate, candidate_id).payload["publication_state"]
            == "pending_review"
        )
        review = session.get(FactReview, review_id)
        assert review.reviewer_label == "synthetic reviewer" and review.user_id is None
    with pipeline_db[0].begin() as session:
        session.get(SourcePolicy, ids["policy"]).collection_decision = "denied"
    with pytest.raises(CorpusError, match="PERMISSION_REVOKED"):
        service.read_published(manifest)
    with pytest.raises(EvidenceError, match="PERMISSION_REVOKED"):
        service.publish(manifest, candidate_id, review_id)


@pytest.mark.parametrize("decision", ["rejected", "needs_review"])
def test_rejected_or_pending_review_and_raw_candidate_are_not_readable_facts(pipeline_db, decision):
    _, manifest, candidate_id, service = setup_candidate(pipeline_db)
    review_id = service.review(
        manifest,
        candidate_id,
        decision=decision,
        reviewer_label="synthetic reviewer",
        reason="Support not confirmed.",
    )
    with pytest.raises(EvidenceError, match="APPROVED_REVIEW_REQUIRED"):
        service.publish(manifest, candidate_id, review_id)
    with pytest.raises(EvidenceError, match="SNAPSHOT_NOT_READABLE"):
        service.read_published(manifest)
    with pipeline_db[0]() as session:
        assert session.scalar(select(func.count()).select_from(PublishedFact)) == 0
        assert session.scalar(select(func.count()).select_from(SnapshotMember)) == 0


def test_latest_rejection_supersedes_unpublished_approval(pipeline_db):
    _, manifest, candidate_id, service = setup_candidate(pipeline_db)
    old = approve(pipeline_db, manifest, candidate_id, service)
    service.review(
        manifest,
        candidate_id,
        decision="rejected",
        reviewer_label="synthetic reviewer",
        reason="Synthetic second review rejects initial interpretation.",
    )
    with pytest.raises(EvidenceError, match="APPROVED_REVIEW_REQUIRED"):
        service.publish(manifest, candidate_id, old)


@pytest.mark.parametrize(
    "kind,model,field,value",
    [
        ("html", EvidenceRef, "quote", "999 RUB"),
        ("html", EvidenceRef, "quote_start", 99),
        ("html", EvidenceRef, "raw_sha256", "0" * 64),
        ("html", EvidenceRef, "extraction_sha256", "0" * 64),
        ("html", EvidenceRef, "source_version_id", str(uuid4())),
        ("html", EvidenceRef, "extraction_run_id", str(uuid4())),
        ("html", EvidenceRef, "original_url", "https://www.sberbank.ru/official-but-unsupported"),
        ("html", DocumentChunk, "text_sha256", "0" * 64),
        ("pdf", DocumentChunk, "locator", {"kind": "pdf", "physical_page": 99}),
        ("xlsx", DocumentChunk, "locator", {"kind": "xlsx", "sheet": "Rates", "cell_range": "Z99"}),
        ("html", DocumentChunk, "locator", {"kind": "html", "element_path": "/wrong[1]"}),
        ("html", ExtractionRun, "extraction_sha256", "0" * 64),
    ],
)
def test_validator_independently_rejects_tampered_chain(pipeline_db, kind, model, field, value):
    _, manifest, candidate_id, service = setup_candidate(pipeline_db, kind)
    with pipeline_db[0]() as session:
        candidate = session.get(TariffCandidate, candidate_id)
        if model == EvidenceRef:
            row = session.scalar(
                select(EvidenceRef).where(
                    EvidenceRef.candidate_id == candidate_id, EvidenceRef.support_role == "value"
                )
            )
        elif model == DocumentChunk:
            row = session.scalar(
                select(DocumentChunk)
                .where(DocumentChunk.extraction_run_id == candidate.extraction_run_id)
                .order_by(DocumentChunk.ordinal)
            )
        else:
            row = session.get(ExtractionRun, candidate.extraction_run_id)
        # DB immutability is preserved: simulate an untrusted stored record in the
        # identity map without flushing it, to exercise the independent validator.
        attributes.set_committed_value(row, field, value)
        report = service.validator.validate(session, manifest, candidate_id)
        assert not report.technical_valid and report.errors


@pytest.mark.parametrize("changed", ["value", "currency", "conditions"])
def test_exact_quote_and_real_looking_url_do_not_prove_semantic_support(pipeline_db, changed):
    _, manifest, candidate_id, service = setup_candidate(pipeline_db)
    conf = confirmation(pipeline_db, manifest, candidate_id, service)
    with pipeline_db[0]() as session:
        candidate = session.get(TariffCandidate, candidate_id)
        payload = json.loads(json.dumps(candidate.payload))
        if changed == "value":
            payload["value"]["amount"] = "999"
        elif changed == "currency":
            payload["value"]["currency"] = "USD"
        else:
            payload["conditions_text"] = "При подключении пакета Premium"
            fields = dict(conf.field_evidence)
            fields["conditions"] = fields["value"]
            conf = SemanticConfirmation(fields)
        attributes.set_committed_value(candidate, "payload", payload)
        attributes.set_committed_value(candidate, "payload_sha256", canonical_hash(payload))
        report = service.validator.validate(session, manifest, candidate_id, conf)
        assert report.technical_valid and not report.valid
        assert report.errors[0] in {
            "VALUE_NOT_SUPPORTED",
            "UNIT_NOT_SUPPORTED",
            "CONDITIONS_NOT_SUPPORTED",
        }


def test_permission_revocation_and_synthetic_to_real_block_publication(pipeline_db):
    ids, manifest, candidate_id, service = setup_candidate(pipeline_db)
    review_id = approve(pipeline_db, manifest, candidate_id, service)
    with pytest.raises(EvidenceError, match="SNAPSHOT_IDENTITY_MISMATCH"):
        service.publish(
            manifest.model_copy(update={"corpus_kind": "real"}), candidate_id, review_id
        )
    with pipeline_db[0].begin() as session:
        session.get(SourcePolicy, ids["policy"]).collection_decision = "denied"
    with pytest.raises(EvidenceError, match="PERMISSION_REVOKED"):
        service.publish(manifest, candidate_id, review_id)
    with pytest.raises(CorpusError, match="PERMISSION_REVOKED"):
        service.corpus.freeze(manifest)


def test_failure_after_membership_insert_rolls_back_publication(pipeline_db):
    _, manifest, candidate_id, service = setup_candidate(pipeline_db)
    review_id = approve(pipeline_db, manifest, candidate_id, service)

    def fail(session, flush_context, instances):
        if any(isinstance(row, PublishedFact) for row in session.new):
            raise SQLAlchemyError("synthetic controlled failure")

    event.listen(Session, "before_flush", fail)
    try:
        with pytest.raises(EvidenceError, match="PUBLICATION_PERSISTENCE_FAILED"):
            service.publish(manifest, candidate_id, review_id)
    finally:
        event.remove(Session, "before_flush", fail)
    with pipeline_db[0]() as session:
        assert session.scalar(select(func.count()).select_from(SnapshotMember)) == 0
        assert session.scalar(select(func.count()).select_from(PublishedFact)) == 0
        assert session.get(FactReview, review_id) is not None


def test_concurrent_publication_uses_one_fact_on_migrated_database(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("NOT RUN: dedicated migrated PostgreSQL TEST_DATABASE_URL required")
    schema = f"snap09_{uuid4().hex}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    scoped_url = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    factory = make_session_factory(scoped_url.render_as_string(hide_password=False))
    store = LocalBlobStore(tmp_path / "originals")
    settings = Settings(app_env="test", storage_root=store.root)
    ingestion = IngestionService(factory, settings, store, FetchGateway(settings, store))
    corpus = CorpusService(ingestion)
    from app.parsing.service import ExtractionPipeline

    try:
        migration_env = {
            **os.environ,
            "DATABASE_URL": url,
            "PGOPTIONS": f"-csearch_path={schema}",
        }
        for action in ("upgrade", "check"):
            command = [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", action]
            if action == "upgrade":
                command.append("head")
            completed = subprocess.run(command, env=migration_env, capture_output=True, timeout=60)
            assert completed.returncode == 0, f"isolated schema Alembic {action} failed"
        db = (factory, store, corpus, ExtractionPipeline(corpus))
        _, manifest, candidate_id, service = setup_candidate(db)
        review_id = approve(db, manifest, candidate_id, service)
        barrier = Barrier(2)

        def publish():
            barrier.wait(timeout=10)
            return service.publish(manifest, candidate_id, review_id)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(publish) for _ in range(2)]
            results = [future.result(timeout=90) for future in futures]
        assert len({result.fact_id for result in results}) == 1
        assert sorted(result.idempotent for result in results) == [False, True]
        with factory() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(PublishedFact)
                    .where(PublishedFact.candidate_id == candidate_id)
                )
                == 1
            )
    finally:
        factory.kw["bind"].dispose()
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def test_cli_inspection_confirmation_review_and_publish(pipeline_db, tmp_path, monkeypatch, capsys):
    from app.evidence import cli

    _, manifest, candidate_id, service = setup_candidate(pipeline_db)
    monkeypatch.setattr(cli, "_service", lambda: service)
    path = tmp_path / "manifest.json"
    path.write_text(manifest.model_dump_json(), encoding="utf-8")
    base = ["--manifest", str(path)]
    target = ["--candidate-id", candidate_id]
    assert cli.main(base + ["inspect"] + target) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["validation"]["technical_valid"]
    assert cli.main(base + ["validate"] + target) == 1
    assert not json.loads(capsys.readouterr().out)["valid"]
    conf = confirmation(pipeline_db, manifest, candidate_id, service)
    conf_path = tmp_path / "confirmation.json"
    conf_path.write_text(json.dumps({"field_evidence": conf.field_evidence}), encoding="utf-8")
    assert (
        cli.main(
            base
            + ["review"]
            + target
            + [
                "--decision",
                "approved",
                "--reviewer",
                "synthetic CLI reviewer",
                "--reason",
                "Synthetic manual check of all fields.",
                "--confirmation",
                str(conf_path),
            ]
        )
        == 0
    )
    review_id = json.loads(capsys.readouterr().out)["review_id"]
    assert cli.main(base + ["publish"] + target + ["--review-id", review_id]) == 0
    assert json.loads(capsys.readouterr().out)["fact_id"]


def test_reviewer_identity_reason_and_reference_confirmation_are_mandatory(pipeline_db):
    _, manifest, candidate_id, service = setup_candidate(pipeline_db)
    for label, reason in (("", "explanation"), ("synthetic reviewer", "")):
        with pytest.raises(EvidenceError, match="REVIEW_IDENTITY_OR_REASON_REQUIRED"):
            service.review(
                manifest, candidate_id, decision="approved", reviewer_label=label, reason=reason
            )
    conf = confirmation(pipeline_db, manifest, candidate_id, service)
    fields = dict(conf.field_evidence)
    fields["value"] = [str(uuid4())]
    report = service.validate(manifest, candidate_id, SemanticConfirmation(fields))
    assert report.errors == ("SEMANTIC_EVIDENCE_INVALID",)


def test_original_corruption_blocks_review_before_any_publication(pipeline_db):
    _, manifest, candidate_id, service = setup_candidate(pipeline_db)
    path = service.corpus.read_draft_document(manifest, 0)
    path.write_bytes(b"synthetic corruption")
    report = service.validate(manifest, candidate_id)
    assert not report.technical_valid
    with pytest.raises(EvidenceError):
        service.review(
            manifest,
            candidate_id,
            decision="approved",
            reviewer_label="synthetic reviewer",
            reason="Cannot approve corrupt original.",
        )


def test_linked_footnote_support_is_checked_not_only_quote_offsets(pipeline_db):
    body = (
        '<html><body><p>Обслуживание счета — 0 RUB в месяц <a href="#note">*</a></p>'
        '<p id="note" role="doc-footnote">* При поддержании остатка.</p></body></html>'
    ).encode()
    ids, manifest, parsed, pipeline = _seed_document(pipeline_db, "html", body)
    result = pipeline.run(
        manifest, ids["version"], parser_version=parsed.parser_version, context=_CONTEXT
    )
    manifest = manifest.model_copy(
        update={
            "documents": (
                manifest.documents[0].model_copy(
                    update={"extraction_run_id": uuid_id(result.extraction_id)}
                ),
            )
        }
    )
    service = EvidenceService(pipeline_db[2])
    with pipeline_db[0]() as session:
        row = session.scalar(
            select(TariffCandidate).where(TariffCandidate.extraction_run_id == result.extraction_id)
        )
        candidate_id = row.id
    conf = confirmation(pipeline_db, manifest, candidate_id, service)
    report = service.validate(manifest, candidate_id, conf)
    assert report.valid and not report.eligible_for_comparison
    assert "CONDITIONS_UNPARSED" in report.limitations
    assert "relations" in report.required_fields
    with pipeline_db[0]() as session:
        ref = session.scalar(
            select(EvidenceRef).where(
                EvidenceRef.candidate_id == candidate_id, EvidenceRef.support_role == "condition"
            )
        )
        attributes.set_committed_value(ref, "support_role", "scope")
        report = service.validator.validate(session, manifest, candidate_id, conf)
        assert not report.technical_valid and report.errors == ("FOOTNOTE_SUPPORT_MISSING",)


def test_review_and_publication_are_immutable_and_review_user_must_be_admin(pipeline_db):
    _, manifest, candidate_id, service = setup_candidate(pipeline_db)
    with pytest.raises(EvidenceError, match="REVIEWER_NOT_AUTHORIZED"):
        service.review(
            manifest,
            candidate_id,
            decision="approved",
            user_id=str(uuid4()),
            reviewer_label="synthetic unknown user",
            reason="Cannot impersonate reviewer.",
        )
    review_id = approve(pipeline_db, manifest, candidate_id, service)
    service.publish(manifest, candidate_id, review_id)
    with pytest.raises(EvidenceError, match="PUBLISHED_CANDIDATE_IMMUTABLE"):
        service.review(
            manifest,
            candidate_id,
            decision="rejected",
            reviewer_label="synthetic reviewer",
            reason="Corrections require a new draft revision.",
        )
    with pytest.raises(SQLAlchemyError):
        with pipeline_db[0].begin() as session:
            session.get(FactReview, review_id).reason = "illegal rewrite"


@pytest.mark.parametrize(
    "field", ["period", "date", "basis", "condition_ast", "condition_eq", "condition_in"]
)
def test_unsupported_period_date_basis_and_condition_threshold_are_rejected(pipeline_db, field):
    text = {
        "period": "Обслуживание счета — 100 RUB в месяц.",
        "date": "Обслуживание счета — 100 RUB в месяц, действует с 10.10.2026.",
        "basis": "Комиссия за зачисление зарплаты — 0,5% от суммы зарплаты.",
        "condition_ast": "Обслуживание счета — 100 RUB в месяц при остатке 1000.",
        "condition_eq": "Обслуживание счета — 100 RUB в месяц при остатке 1000.",
        "condition_in": "Обслуживание счета — 100 RUB в месяц при остатке 1000.",
    }[field]
    ids, manifest, parsed, pipeline = _seed_document(pipeline_db, "html", _html_bytes(text))
    context = {
        "payer": "employer",
        "operation": ("payroll_credit" if field == "basis" else "account_maintenance"),
    }
    if field == "date":
        context["valid_from"] = "2026-10-10"
        context["effective_date_status"] = "explicit"
    result = pipeline.run(
        manifest, ids["version"], parser_version=parsed.parser_version, context=context
    )
    assert result.status == "ok"
    manifest = manifest.model_copy(
        update={
            "documents": (
                manifest.documents[0].model_copy(
                    update={"extraction_run_id": uuid_id(result.extraction_id)}
                ),
            )
        }
    )
    service = EvidenceService(pipeline_db[2])
    with pipeline_db[0]() as session:
        row = session.scalar(
            select(TariffCandidate).where(TariffCandidate.extraction_run_id == result.extraction_id)
        )
        candidate_id = row.id
    conf = confirmation(pipeline_db, manifest, candidate_id, service)
    assert service.validate(manifest, candidate_id, conf).valid
    with pipeline_db[0]() as session:
        row = session.get(TariffCandidate, candidate_id)
        payload = json.loads(json.dumps(row.payload))
        fields = dict(conf.field_evidence)
        if field == "period":
            payload["period"] = "per year"
            fields["period"] = fields["metric"]
        elif field == "date":
            payload["valid_from"] = "2020-01-01"
        elif field == "basis":
            payload["value"]["basis"] = "transfer_amount"
        else:
            payload["conditions"] = {
                "kind": "leaf",
                "field": "payroll_total",
                "op": {"condition_ast": "gte", "condition_eq": "eq", "condition_in": "in"}[field],
                "value": ["999"] if field == "condition_in" else "999",
                "unit": "RUB",
            }
            payload["conditions_text"] = None
        attributes.set_committed_value(row, "payload", payload)
        attributes.set_committed_value(row, "payload_sha256", canonical_hash(payload))
        report = service.validator.validate(
            session, manifest, candidate_id, SemanticConfirmation(fields)
        )
        assert report.technical_valid and not report.valid
        assert report.errors == (
            {
                "period": "PERIOD_NOT_SUPPORTED",
                "date": "DATE_NOT_SUPPORTED",
                "basis": "BASIS_NOT_SUPPORTED",
                "condition_ast": "CONDITIONS_NOT_SUPPORTED",
                "condition_eq": "CONDITIONS_NOT_SUPPORTED",
                "condition_in": "CONDITIONS_NOT_SUPPORTED",
            }[field],
        )


def test_new_snapshot_requires_new_scoped_review_without_changing_old_fact(pipeline_db):
    _, manifest, candidate_id, service = setup_candidate(pipeline_db)
    first_review = approve(pipeline_db, manifest, candidate_id, service)
    first = service.publish(manifest, candidate_id, first_review)
    service.corpus.freeze(manifest)
    revised = manifest.model_copy(
        update={"snapshot_id": uuid4(), "revision": manifest.revision + 1}
    )
    service.corpus.add_version(revised, 0)
    with pytest.raises(EvidenceError, match="APPROVED_REVIEW_REQUIRED"):
        service.publish(revised, candidate_id, first_review)
    second_review = approve(pipeline_db, revised, candidate_id, service)
    second = service.publish(revised, candidate_id, second_review)
    assert first.fact_id != second.fact_id and first.review_id != second.review_id
    assert service.read_published(manifest)[0]["fact_id"] == first.fact_id


def test_fully_supported_manual_review_can_clear_review_flags_without_inventing_scope(pipeline_db):
    _, manifest, original_id, service = setup_candidate(
        pipeline_db,
        text=(
            "Обслуживание счета — 100 RUB в месяц, действует с 10.10.2026. "
            "Работодатель: все сегменты, организации, пакеты и варианты договора; вся Россия."
        ),
    )
    # Explicit synthetic analyst proposal into the existing frozen DTO/ORM,
    # retaining the actual source chain. It does not modify the extracted candidate.
    with pipeline_db[0].begin() as session:
        original = session.get(TariffCandidate, original_id)
        refs = session.scalars(
            select(EvidenceRef).where(EvidenceRef.candidate_id == original_id)
        ).all()
        candidate_id = str(uuid4())
        ids = {ref.id: str(uuid4()) for ref in refs}
        payload = json.loads(json.dumps(original.payload))
        payload["id"] = candidate_id
        payload["evidence_ids"] = list(ids.values())
        scope_ids = [ids[ref.id] for ref in refs if ref.support_role == "scope"]
        payload["geography"] = {"kind": "federal", "region_codes": [], "evidence_ids": scope_ids}
        for field in (
            "employer_segment",
            "organization_category",
            "payroll_package",
            "contract_variant",
        ):
            payload[field] = {"mode": "any", "values": []}
        payload["valid_from"] = "2026-10-10"
        payload["effective_date_status"] = "explicit"
        payload["period"] = "месяц"
        session.add(
            TariffCandidate(
                id=candidate_id,
                extraction_run_id=original.extraction_run_id,
                bank_id=original.bank_id,
                metric_code=original.metric_code,
                corpus_kind=original.corpus_kind,
                payload=payload,
                payload_sha256=canonical_hash(payload),
            )
        )
        session.flush()
        for ref in refs:
            fields = {
                name: getattr(ref, name)
                for name in (
                    "source_version_id",
                    "extraction_run_id",
                    "chunk_id",
                    "raw_sha256",
                    "extraction_sha256",
                    "quote",
                    "quote_start",
                    "quote_end",
                    "locator",
                    "support_role",
                    "original_url",
                    "acquired_at",
                )
            }
            session.add(EvidenceRef(id=ids[ref.id], candidate_id=candidate_id, **fields))
    conf = confirmation(pipeline_db, manifest, candidate_id, service)
    report = service.validate(manifest, candidate_id, conf)
    assert report.valid and report.eligible_for_comparison and not report.limitations
    review_id = approve(pipeline_db, manifest, candidate_id, service)
    service.publish(manifest, candidate_id, review_id)
    service.corpus.freeze(manifest)
    assert service.read_published(manifest)[0]["eligible_for_comparison"]
