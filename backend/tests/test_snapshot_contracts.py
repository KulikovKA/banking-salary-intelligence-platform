"""Risk-focused tests for frozen snapshot DTO and Protocol contracts."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, assert_type
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from app.contracts.api import (
    AnswerEnvelope,
    AnswerSource,
    ApiError,
    ApiErrorDetail,
    QuestionRequest,
)
from app.contracts.comparison import (
    Claim,
    ComparisonCell,
    ComparisonRequest,
    ComparisonResult,
    ComparisonRow,
    PairwiseResult,
)
from app.contracts.corpus import (
    SearchHit,
    SearchRequest,
    Snapshot,
    SnapshotMember,
    SnapshotReadService,
)
from app.contracts.evidence import EvidenceRef, extraction_evidence_to_ref
from app.contracts.llm import (
    ExplainResult,
    IntentResult,
    LLMClient,
    LLMError,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMUsage,
)
from app.contracts.parsing import (
    Chunk,
    ExtractionRun,
    HtmlLocator,
    Locator,
    ParsedBlock,
    ParseDiagnostic,
    Parser,
    ParseRequest,
    ParseResult,
    PdfLocator,
    XlsxLocator,
)
from app.contracts.tariffs import (
    BooleanValue,
    ConditionGroup,
    ConditionLeaf,
    CountValue,
    FormulaValue,
    Geography,
    IndividualValue,
    MoneyValue,
    PercentValue,
    RangeValue,
    Scenario,
    ScopeDimension,
    TariffCandidate,
    TextValue,
)
from app.ingestion.evidence import ExtractionEvidence

HASH = "a" * 64
STAMP = datetime(2026, 1, 1, tzinfo=UTC)


class SyntheticFixtureIdentity(BaseModel):
    """A synthetic-only test identity, intentionally absent from production DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    identity: Literal["synthetic_a", "synthetic_b"]
    test_context: Literal[True]


class ParserStub:
    def parse(self, request: ParseRequest, original_path: str) -> ParseResult:
        return ParseResult(
            status="ok", extraction_sha256=HASH, parser_version=request.parser_version
        )


class LLMStub:
    async def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            parsed_json={},
            usage=LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            model_id="fake",
            finish_reason="stop",
            latency_ms=0,
        )


class ReadServiceStub:
    async def get_snapshot(self, snapshot_id: UUID) -> Snapshot:
        return Snapshot(
            id=snapshot_id,
            revision=1,
            corpus_kind="synthetic",
            state="draft",
            created_at=STAMP,
        )

    async def search(self, request: SearchRequest) -> tuple[SearchHit, ...]:
        return ()


def test_protocols_accept_structural_fake_stubs() -> None:
    parser: Parser = ParserStub()
    llm: LLMClient = LLMStub()
    read_service: SnapshotReadService = ReadServiceStub()
    assert_type(parser, Parser)
    assert_type(llm, LLMClient)
    assert_type(read_service, SnapshotReadService)
    assert callable(parser.parse)
    assert callable(llm.complete)
    assert callable(read_service.search)


def _sample_candidate(**overrides: object) -> TariffCandidate:
    evidence_id = uuid4()
    payload: dict[str, object] = {
        "id": uuid4(),
        "bank_code": "sber",
        "metric_code": "payroll_credit_fee",
        "value": {"kind": "money", "amount": "0", "currency": "RUB", "period": "monthly"},
        "payer": "employer",
        "operation": "payroll_credit",
        "geography": {
            "kind": "regional",
            "region_codes": ["RU-KDA"],
            "evidence_ids": [evidence_id],
        },
        "employer_segment": {"mode": "specific", "values": ["small_business"]},
        "organization_category": {"mode": "unknown"},
        "payroll_package": {"mode": "any"},
        "contract_variant": {"mode": "unknown"},
        "conditions": {
            "kind": "all",
            "conditions": [{"kind": "leaf", "field": "employee_count", "op": "gte", "value": 5}],
        },
        "valid_from": "2025-01-01",
        "effective_date_status": "explicit",
        "evidence_ids": [evidence_id],
        "corpus_kind": "synthetic",
    }
    payload.update(overrides)
    return TariffCandidate.model_validate(payload)


def test_decimal_wire_roundtrip_and_money_float_rejection() -> None:
    value = MoneyValue.model_validate({"kind": "money", "amount": "123.450000", "currency": "RUB"})
    assert value.model_dump(mode="json")["amount"] == "123.450000"
    assert MoneyValue.model_validate_json(value.model_dump_json()) == value
    assert value.amount == Decimal("123.450000")
    for amount in (1.25, "NaN", "Infinity", "-Infinity", "1_000", " 1"):
        with pytest.raises(ValidationError):
            MoneyValue.model_validate({"kind": "money", "amount": amount, "currency": "RUB"})


@pytest.mark.parametrize(
    "value",
    [
        {"kind": "money", "amount": "1", "currency": "RUB"},
        {"kind": "percent", "amount": "0.30", "basis": "payroll_total"},
        {"kind": "boolean", "boolean_value": True},
        {"kind": "text", "text_value": "included"},
        {"kind": "range", "lower": "1", "upper": "2", "unit": "currency", "currency": "RUB"},
        {"kind": "individual", "text_value": "upon agreement"},
        {"kind": "formula", "formula": "percentage", "parameters": {"rate": "0.3"}},
    ],
)
def test_discriminated_values_roundtrip(value: dict[str, object]) -> None:

    # Validate through Pydantic's containing DTO: discriminator and JSON roundtrip stay stable.
    candidate = _sample_candidate(value=value)
    restored = TariffCandidate.model_validate_json(candidate.model_dump_json())
    assert restored.value == candidate.value
    assert restored.model_dump(mode="json")["value"]["kind"] == value["kind"]


def test_all_locator_variants_and_parse_roundtrip() -> None:
    locators: list[Locator] = [
        PdfLocator(kind="pdf", physical_page=1, bbox=(0.0, 0.0, 1.0, 1.0)),
        XlsxLocator(kind="xlsx", sheet="Tariffs", cell_range="A1:B2", formula="=SUM(A1:A2)"),
        HtmlLocator(kind="html", element_path="/html/body/main/p[1]"),
    ]
    for locator in locators:
        block = ParsedBlock(block_id=uuid4(), text="fee", locator=locator)
        assert ParsedBlock.model_validate_json(block.model_dump_json()) == block
    request = ParseRequest(
        source_version_id=uuid4(),
        raw_sha256=HASH,
        kind="pdf",
        corpus_kind="synthetic",
        parser_version="pdf/1",
    )
    result = ParseResult(
        status="ok",
        extraction_sha256=HASH,
        parser_version="pdf/1",
        blocks=(ParsedBlock(block_id=uuid4(), text="fee", locator=locators[0]),),
        diagnostics=(ParseDiagnostic(code="OK", message="parsed"),),
    )
    assert ParseRequest.model_validate_json(request.model_dump_json()) == request
    assert ParseResult.model_validate_json(result.model_dump_json()) == result


def test_all_pipeline_dtos_roundtrip() -> None:
    snapshot = Snapshot(
        id=uuid4(),
        revision=1,
        corpus_kind="synthetic",
        state="frozen",
        created_at=STAMP,
        frozen_at=STAMP,
        manifest_sha256=HASH,
    )
    member = SnapshotMember(
        snapshot_id=snapshot.id, source_version_id=uuid4(), extraction_run_id=uuid4()
    )
    chunk = Chunk(
        id=uuid4(),
        extraction_run_id=member.extraction_run_id,
        ordinal=0,
        text="fee",
        text_sha256=HASH,
        locator=PdfLocator(kind="pdf", physical_page=1),
    )
    extraction = ExtractionRun(
        id=member.extraction_run_id,
        source_version_id=member.source_version_id,
        raw_sha256=HASH,
        extraction_sha256=HASH,
        parser_version="pdf/1",
        corpus_kind="synthetic",
        status="ok",
        created_at=STAMP,
    )
    evidence = EvidenceRef(
        id=uuid4(),
        source_version_id=member.source_version_id,
        extraction_run_id=member.extraction_run_id,
        chunk_id=chunk.id,
        raw_sha256=HASH,
        extraction_sha256=HASH,
        quote="fee",
        quote_start=0,
        quote_end=3,
        locator=chunk.locator,
        support_role="value",
        original_url="https://example.invalid/doc",
        acquired_at=STAMP,
    )
    scenario = Scenario(
        payer="employer",
        operation="payroll_credit",
        currency="RUB",
        as_of=date(2026, 1, 1),
        payroll_total=Decimal("100000.00"),
    )
    request = ComparisonRequest(
        snapshot_id=snapshot.id,
        bank_codes=("sber", "vtb"),
        metric_codes=("payroll_credit_fee",),
        scenario=scenario,
    )
    claim = Claim(id=uuid4(), kind="fact", text="Fee is documented", evidence_ids=(evidence.id,))
    result = ComparisonResult(
        id=uuid4(),
        snapshot_id=snapshot.id,
        corpus_revision=1,
        scenario_echo=scenario,
        rows=(
            ComparisonRow(
                metric_code="payroll_credit_fee",
                cells=(
                    ComparisonCell(
                        bank_code="sber",
                        status="verified",
                        value=MoneyValue(kind="money", amount=Decimal("0"), currency="RUB"),
                        evidence_ids=(evidence.id,),
                    ),
                ),
                pairwise=(PairwiseResult(left="sber", right="vtb", status="insufficient"),),
            ),
        ),
        claims=(claim,),
        generated_at=STAMP,
    )
    answer = AnswerEnvelope(
        id=uuid4(),
        status="answered",
        snapshot_id=snapshot.id,
        corpus_revision=1,
        text="Fee is documented",
        comparison=result,
        claims=(claim,),
        sources=(
            AnswerSource(
                evidence=evidence,
                download_url=f"/api/v1/documents/{member.source_version_id}/original",
            ),
        ),
        data_as_of=date(2026, 1, 1),
        generated_at=STAMP,
    )
    llm_request = LLMRequest(
        purpose="intent",
        template_version="intent/1",
        messages=(LLMMessage(role="user", content="compare"),),
        output_schema={"type": "object"},
        max_output_tokens=100,
        timeout_ms=1000,
        request_id=uuid4(),
    )
    llm_response = LLMResponse(
        parsed_json={"intent": "clarify"},
        usage=LLMUsage(prompt_tokens=2, completion_tokens=1, total_tokens=3),
        provider_request_id="fake-1",
        model_id="fake",
        finish_reason="stop",
        latency_ms=1,
    )
    search_hit = SearchHit(
        chunk_id=chunk.id,
        text=chunk.text,
        locator=chunk.locator,
        evidence_ids=(evidence.id,),
        source_version_id=member.source_version_id,
        raw_sha256=HASH,
        snapshot_id=snapshot.id,
        score=1.0,
    )
    group = ConditionGroup(
        kind="all", conditions=(ConditionLeaf(field="employee_count", op="gte", value=5),)
    )
    extras = [
        BooleanValue(kind="boolean", boolean_value=False),
        CountValue(kind="count", amount=5, unit="transfers"),
        TextValue(kind="text", text_value="included"),
        PercentValue(kind="percent", amount=Decimal("0.30"), basis="payroll_total"),
        RangeValue(
            kind="range", lower=Decimal("1"), upper=Decimal("2"), unit="currency", currency="RUB"
        ),
        FormulaValue(kind="formula", formula="percentage", parameters={"rate": Decimal("0.3")}),
        IndividualValue(kind="individual", text_value="upon agreement"),
        group,
        LLMUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        llm_response,
        LLMError(code="rate_limit", retry_after_ms=100),
        IntentResult(intent="compare", bank_codes=("sber", "vtb"), metric_codes=("fee",)),
        ExplainResult(ordered_claim_ids=(claim.id,), template_by_claim={claim.id: "summary"}),
        search_hit,
    ]
    dtos = [
        snapshot,
        member,
        chunk,
        extraction,
        evidence,
        scenario,
        request,
        result,
        answer,
        llm_request,
        *extras,
        ApiError(error=ApiErrorDetail(code="bad", message="invalid", request_id=uuid4())),
        QuestionRequest(snapshot_id=snapshot.id, question="compare", scenario=scenario),
        SearchRequest(snapshot_id=snapshot.id, query="fee", bank_codes=("sber",)),
        _sample_candidate(),
    ]
    for dto in dtos:
        assert type(dto).model_validate_json(dto.model_dump_json()) == dto


def test_reject_unknown_fields_invalid_offsets_scopes_and_dates() -> None:
    with pytest.raises(ValidationError):
        MoneyValue.model_validate({"kind": "money", "amount": "1", "currency": "RUB", "extra": 1})
    with pytest.raises(ValidationError):
        ScopeDimension(mode="specific", values=())
    with pytest.raises(ValidationError):
        ScopeDimension(mode="unknown", values=("all",))
    with pytest.raises(ValidationError):
        EvidenceRef(
            id=uuid4(),
            source_version_id=uuid4(),
            extraction_run_id=uuid4(),
            chunk_id=uuid4(),
            raw_sha256=HASH,
            extraction_sha256=HASH,
            quote="ab",
            quote_start=0,
            quote_end=3,
            locator=PdfLocator(kind="pdf", physical_page=1),
            support_role="value",
            original_url="https://example.invalid",
            acquired_at=STAMP,
        )
    with pytest.raises(ValidationError):
        Snapshot(
            id=uuid4(),
            revision=1,
            corpus_kind="synthetic",
            state="draft",
            created_at=datetime(2026, 1, 1),
        )


def test_reject_duplicate_banks_unknown_real_identity_and_bad_conditions() -> None:
    scenario = Scenario(payer="employer", operation="credit", currency="RUB", as_of=date.today())
    with pytest.raises(ValidationError, match="BANK_CODES_DUPLICATE"):
        ComparisonRequest(
            snapshot_id=uuid4(),
            bank_codes=("sber", "sber"),
            metric_codes=("fee",),
            scenario=scenario,
        )
    with pytest.raises(ValidationError):
        ComparisonRequest.model_validate(
            {
                "snapshot_id": uuid4(),
                "bank_codes": ("synthetic_a", "vtb"),
                "metric_codes": ("fee",),
                "scenario": scenario,
            }
        )
    assert (
        SyntheticFixtureIdentity(identity="synthetic_a", test_context=True).identity
        == "synthetic_a"
    )
    with pytest.raises(ValidationError):
        _sample_candidate(
            conditions={
                "kind": "all",
                "conditions": [{"kind": "leaf", "field": "raw_text", "op": "eq", "value": "x"}],
            }
        )
    with pytest.raises(ValidationError, match="GEOGRAPHY_EVIDENCE_REQUIRED"):
        Geography(kind="federal")
    with pytest.raises(ValidationError, match="ZERO_FEE_REQUIRES_CONDITIONS"):
        _sample_candidate(conditions=None, conditions_text=None)
    with pytest.raises(ValidationError):
        _sample_candidate(
            conditions={
                "kind": "all",
                "conditions": [
                    {"kind": "leaf", "field": "employee_count", "op": "in", "value": []}
                ],
            }
        )
    with pytest.raises(ValidationError):
        _sample_candidate(
            conditions={
                "kind": "all",
                "conditions": [
                    {
                        "kind": "all",
                        "conditions": [
                            {
                                "kind": "all",
                                "conditions": [
                                    {
                                        "kind": "all",
                                        "conditions": [
                                            {
                                                "kind": "all",
                                                "conditions": [
                                                    {
                                                        "kind": "leaf",
                                                        "field": "employee_count",
                                                        "op": "gte",
                                                        "value": 1,
                                                    }
                                                ],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        )


def test_nullable_and_unknown_are_explicit_not_defaults() -> None:
    scenario = Scenario(payer="employer", operation="credit", currency="RUB", as_of=date.today())
    assert scenario.payroll_total is None
    assert scenario.employee_count is None
    candidate = _sample_candidate(
        geography={"kind": "unknown"},
        employer_segment={"mode": "unknown"},
        valid_from=None,
        effective_date_status="unknown",
    )
    assert candidate.value == MoneyValue(
        kind="money", amount=Decimal("0"), currency="RUB", period="monthly"
    )
    assert candidate.geography.kind == "unknown"
    assert candidate.valid_from is None
    with pytest.raises(ValidationError, match="VERIFIED_CELL_REQUIRES_VALUE_AND_EVIDENCE"):
        ComparisonCell(bank_code="sber", status="verified")
    with pytest.raises(ValidationError, match="INDIVIDUAL_CELL_REQUIRES_INDIVIDUAL_VALUE"):
        ComparisonCell(bank_code="sber", status="individual", value=None)


def test_existing_ingestion_evidence_adapts_without_changing_its_contract() -> None:
    existing = ExtractionEvidence(
        source_version_id=uuid4(),
        raw_sha256=HASH,
        extraction_sha256=HASH,
        parser_version="existing/1",
        corpus_kind="synthetic",
        quote="fee",
        quote_start=0,
        quote_end=3,
        physical_page=2,
    )
    adapted = extraction_evidence_to_ref(
        existing,
        evidence_id=uuid4(),
        extraction_run_id=uuid4(),
        chunk_id=uuid4(),
        extraction_sha256=HASH,
        locator=PdfLocator(kind="pdf", physical_page=2),
        support_role="value",
        original_url="https://example.invalid/doc",
        acquired_at=STAMP,
    )
    assert adapted.source_version_id == existing.source_version_id
    assert adapted.quote == existing.quote
    assert adapted.quote_start == existing.quote_start
