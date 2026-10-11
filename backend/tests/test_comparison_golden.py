"""Independent synthetic financial oracles; real migrated PG provenance tests."""

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter
from sqlalchemy import select
from test_evidence_publication import approve, confirmation, setup_candidate
from test_extraction_pipeline import pipeline_db as pipeline_db

from app.comparison.calculations import (
    FORMULA_VERSION,
    Truth,
    applicability,
    calculate,
    condition_truth,
    sum_known_components,
)
from app.comparison.service import ComparisonService, scenario_hash
from app.contracts.comparison import ComparisonRequest, ComparisonResult
from app.contracts.tariffs import Condition, Scenario, TariffCandidate
from app.corpus.service import CorpusError, SnapshotManifest
from app.evidence.validation import EvidenceError, canonical_hash
from app.registry.models import SourcePolicy
from app.tariffs.models import EvidenceRef
from app.tariffs.models import TariffCandidate as CandidateRow

NOW = datetime(2026, 10, 11, tzinfo=UTC)


def scenario(**changes):
    payload = dict(
        payer="employer",
        operation="payroll_credit",
        currency="RUB",
        payroll_total="100000",
        transfer_amount="1000",
        transfers_count=10,
        employee_count=10,
        period="month",
        as_of="2026-10-11",
    )
    payload.update(changes)
    return Scenario.model_validate(payload)


def money(amount="100", currency="RUB", period="month"):
    return dict(kind="money", amount=amount, currency=currency, period=period)


def percent(rate="0.30", basis="payroll_total", period="month"):
    return dict(kind="percent", amount=rate, basis=basis, period=period)


def formula(rate="0.30", lower="100", upper="500", basis="payroll_total", period="month"):
    return dict(
        kind="formula",
        formula="percentage_clamped",
        parameters=dict(rate=rate, min_fee=lower, max_fee=upper),
        currency="RUB",
        basis=basis,
        period=period,
    )


def candidate(value=None, **changes):
    evidence = uuid4()
    payload = dict(
        id=uuid4(),
        bank_code="sber",
        metric_code="payroll_credit_fee",
        value=value or percent(),
        payer="employer",
        operation="payroll_credit",
        period=None,
        geography=dict(kind="federal", evidence_ids=[evidence]),
        employer_segment=dict(mode="any"),
        organization_category=dict(mode="any"),
        payroll_package=dict(mode="any"),
        contract_variant=dict(mode="any"),
        valid_from="2026-01-01",
        effective_date_status="explicit",
        evidence_ids=[evidence],
        corpus_kind="synthetic",
    )
    payload.update(changes)
    return TariffCandidate.model_validate(payload)


def manifest():
    return SnapshotManifest.model_validate(
        dict(
            snapshot_id=uuid4(),
            revision=1,
            corpus_kind="synthetic",
            region="RU-KDA",
            employer_segment="SME",
            documents=[
                dict(
                    bank_code="sber",
                    source_id=uuid4(),
                    source_version_id=uuid4(),
                    source_fetch_id=uuid4(),
                    policy_id=uuid4(),
                    extraction_run_id=uuid4(),
                    sha256="1" * 64,
                    acquisition_method="manual",
                    original_url="https://example.com/synthetic.html",
                    final_url="https://example.com/synthetic.html",
                    acquired_at=NOW,
                    scope={},
                    document_type="synthetic tariff",
                )
            ],
            missing_documents=[
                dict(bank_code=bank, document_type="synthetic tariff", reason="fixture")
                for bank in ("vtb", "alfa", "kuban_credit")
            ],
        )
    )


def record(item, snapshot, *, eligible=True, limitations=()):
    return dict(
        fact_id=str(uuid4()),
        review_id=str(uuid4()),
        snapshot_id=str(snapshot.snapshot_id),
        candidate=item.model_dump(mode="json"),
        evidence_ids=[str(i) for i in item.evidence_ids],
        eligible_for_comparison=eligible,
        limitations=limitations,
    )


class SyntheticReader:
    """Test double for the already-authorized SNAP-09 read, never runtime data."""

    def __init__(self, records):
        self.records = records
        self.calls = 0

    def read_published(self, chosen):
        self.calls += 1
        return self.records


def compare(items, user=None, *, banks=("sber", "vtb"), metrics=("payroll_credit_fee",)):
    chosen = manifest()
    records = tuple(record(item, chosen) for item in items)
    reader = SyntheticReader(records)
    service = ComparisonService(reader, lambda _: chosen, clock=lambda: NOW)
    request = ComparisonRequest(
        snapshot_id=chosen.snapshot_id,
        bank_codes=banks,
        metric_codes=metrics,
        scenario=user or scenario(),
    )
    return asyncio.run(service.compare(request))


# Each row has an independently specified expected result, not a copy of the formula.
@pytest.mark.parametrize(
    "value,inputs,expected,missing",
    [
        pytest.param(percent(), {}, "300", None, id="100000-times-0.30-percent"),
        pytest.param(percent("0.10"), {}, "100", None, id="one-tenth-percent"),
        pytest.param(percent("0"), {}, "0", None, id="explicit-zero-rate"),
        pytest.param(percent("1"), dict(payroll_total="0"), "0", None, id="zero-base"),
        pytest.param(formula(), {}, "300", None, id="clamp-interior"),
        pytest.param(formula(), dict(payroll_total="1000"), "100", None, id="minimum"),
        pytest.param(formula(), dict(payroll_total="1000000"), "500", None, id="maximum"),
        pytest.param(formula(lower="300", upper="300"), {}, "300", None, id="equal-bounds"),
        pytest.param(money("150"), {}, "150", None, id="fixed-fee"),
        pytest.param(
            dict(
                kind="formula",
                formula="constant",
                currency="RUB",
                period="month",
                parameters=dict(constant="75"),
            ),
            {},
            "75",
            None,
            id="constant",
        ),
        pytest.param(money("12", period="per_transfer"), {}, "120", None, id="per-transfer"),
        pytest.param(
            money("12", period="per_batch"),
            dict(period="per_batch"),
            "12",
            None,
            id="single-explicit-batch",
        ),
        pytest.param(
            money("12", period="per_batch"), {}, None, "batch_count", id="batch-count-unknown"
        ),
        pytest.param(
            percent(period="per_transfer", basis="transfer_amount"),
            {},
            "30",
            None,
            id="per-transfer-percentage",
        ),
        pytest.param(
            formula(period="per_transfer", basis="transfer_amount", lower="10", upper="20"),
            {},
            "100",
            None,
            id="clamp-before-transfer-multiplication",
        ),
        pytest.param(
            percent(), dict(payroll_total=None), None, "payroll_total", id="missing-payroll"
        ),
        pytest.param(
            percent(basis="transfer_amount"),
            dict(transfer_amount=None),
            None,
            "transfer_amount",
            id="missing-transfer-amount",
        ),
        pytest.param(
            money(period="per_transfer"),
            dict(transfers_count=None),
            None,
            "transfers_count",
            id="missing-transfer-count",
        ),
        pytest.param(money(), dict(period=None), None, "period", id="missing-horizon"),
        pytest.param(money(period="year"), {}, None, "period_incompatible", id="annual-vs-monthly"),
        pytest.param(money(currency="USD"), {}, None, "currency_incompatible", id="usd-vs-rub"),
        pytest.param(percent(basis="balance"), {}, None, "basis", id="unsupported-basis"),
        pytest.param(percent("-1"), {}, None, "negative_fee", id="negative-rate"),
        pytest.param(
            percent("0.30"),
            dict(payroll_total="100000.000000"),
            "300",
            None,
            id="decimal-trailing-zeros",
        ),
        pytest.param(
            percent("0.000001"),
            dict(payroll_total="99999999999999"),
            "999999.99999999",
            None,
            id="decimal-six-place-rate",
        ),
        pytest.param(
            percent("0.01"),
            dict(payroll_total="0.01"),
            "0.000001",
            None,
            id="retain-fractional-kopeck",
        ),
        pytest.param(
            percent("0.1234567890123456789012345678"),
            dict(payroll_total="999999999999999999999"),
            None,
            "decimal_precision_exceeded",
            id="no-silent-context-rounding",
        ),
        pytest.param(money(period=None), {}, None, "period", id="unknown-fact-period"),
    ],
)
def test_arithmetic_golden(value, inputs, expected, missing):
    result = calculate(candidate(value), scenario(**inputs))
    assert result.amount == (None if expected is None else Decimal(expected))
    assert result.missing == (() if missing is None else (missing,))
    if result.value and result.value.kind == "money":
        assert '"amount":"' in result.value.model_dump_json()


@pytest.mark.parametrize(
    "change,inputs,expected",
    [
        pytest.param(dict(valid_from="2026-10-12"), {}, Truth.FALSE, id="future"),
        pytest.param(dict(valid_to="2026-10-11"), {}, Truth.FALSE, id="exclusive-end"),
        pytest.param(dict(valid_from="2026-10-11"), {}, Truth.TRUE, id="inclusive-start"),
        pytest.param(
            dict(valid_from=None, effective_date_status="unknown"),
            {},
            Truth.UNKNOWN,
            id="unknown-date",
        ),
        pytest.param(
            dict(geography=dict(kind="unknown")), {}, Truth.UNKNOWN, id="unknown-geography"
        ),
        pytest.param(
            dict(employer_segment=dict(mode="unknown")), {}, Truth.UNKNOWN, id="unknown-scope"
        ),
        pytest.param(
            dict(employer_segment=dict(mode="specific", values=["SME"])),
            {},
            Truth.UNKNOWN,
            id="missing-segment",
        ),
        pytest.param(
            dict(employer_segment=dict(mode="specific", values=["SME"])),
            dict(employer_segment="large"),
            Truth.FALSE,
            id="wrong-segment",
        ),
        pytest.param(
            dict(payroll_package=dict(mode="specific", values=["premium"])),
            dict(package_by_bank={"sber": "premium"}),
            Truth.TRUE,
            id="bank-specific-package",
        ),
        pytest.param(
            dict(contract_variant=dict(mode="specific", values=["special"])),
            {},
            Truth.UNKNOWN,
            id="missing-contract-variant",
        ),
        pytest.param(dict(payer="employee"), {}, Truth.FALSE, id="different-payer"),
        pytest.param(
            dict(operation="external_transfer"), {}, Truth.FALSE, id="different-operation"
        ),
        pytest.param(
            dict(conditions_text="if individually agreed"),
            {},
            Truth.UNKNOWN,
            id="unparsed-condition",
        ),
        pytest.param(
            dict(requires_manual_interpretation=True), {}, Truth.UNKNOWN, id="manual-ambiguity"
        ),
    ],
)
def test_applicability_golden(change, inputs, expected):
    assert applicability(candidate(**change), scenario(**inputs))[0] is expected


def leaf(field="employee_count", op="gte", value=10, unit=None):
    return dict(kind="leaf", field=field, op=op, value=value, unit=unit)


@pytest.mark.parametrize(
    "tree,inputs,expected",
    [
        (leaf(), {}, Truth.TRUE),
        (leaf(op="gt"), {}, Truth.FALSE),
        (leaf(op="lt", value=11), {}, Truth.TRUE),
        (leaf(op="lte", value=9), {}, Truth.FALSE),
        (leaf(op="eq", value=10), {}, Truth.TRUE),
        (leaf(), dict(employee_count=None), Truth.UNKNOWN),
        (leaf(field="payroll_total", value="100000.00", unit="RUB"), {}, Truth.TRUE),
        (leaf(field="payroll_total", value="100000", unit="USD"), {}, Truth.UNKNOWN),
        (leaf(value=True), {}, Truth.UNKNOWN),
        (leaf(value="NaN"), {}, Truth.UNKNOWN),
        (leaf(field="as_of", op="eq", value="2026-10-11"), {}, Truth.TRUE),
        (leaf(field="region", op="in", value=["RU-KDA"]), dict(region="RU-KDA"), Truth.TRUE),
        (leaf(field="region", op="gt", value="RU-KDA"), dict(region="RU-MOW"), Truth.UNKNOWN),
        (
            dict(
                kind="all",
                conditions=[leaf(value=11), leaf(field="region", op="eq", value="RU-KDA")],
            ),
            {},
            Truth.FALSE,
        ),
        (
            dict(kind="any", conditions=[leaf(), leaf(field="region", op="eq", value="RU-KDA")]),
            {},
            Truth.TRUE,
        ),
        (
            dict(kind="all", conditions=[leaf(), leaf(field="region", op="eq", value="RU-KDA")]),
            {},
            Truth.UNKNOWN,
        ),
        (
            dict(
                kind="any",
                conditions=[leaf(value=11), leaf(field="region", op="eq", value="RU-KDA")],
            ),
            {},
            Truth.UNKNOWN,
        ),
    ],
)
def test_three_valued_ast_golden(tree, inputs, expected):
    condition = TypeAdapter(Condition).validate_python(tree)
    assert condition_truth(condition, scenario(**inputs)) is expected


def test_pairwise_percentage_evidence_operands_and_symmetry():
    left, right = candidate(percent()), candidate(percent("0.5"), bank_code="vtb")
    forward = compare([left, right])
    reverse = compare([right, left], banks=("vtb", "sber"))
    a, b = forward.rows[0].pairwise[0], reverse.rows[0].pairwise[0]
    assert (a.status, a.delta) == ("better", Decimal("-200"))
    assert (b.status, b.delta) == ("worse", Decimal("200"))
    claim = next(claim for claim in forward.claims if claim.id == a.claim_id)
    assert set(claim.evidence_ids) == set(left.evidence_ids + right.evidence_ids)
    assert len(claim.fact_ids) == 2 and claim.formula_version == FORMULA_VERSION
    assert (
        claim.scenario_hash
        == next(c for c in reverse.claims if c.kind == "comparison").scenario_hash
    )
    detail = json.loads(claim.text)
    assert detail["operands"][0][0]["operands"]["rate"] == "0.30"
    assert detail["sufficiency"] == "better" and len(detail["applicability"]) == 2
    assert ComparisonResult.model_validate_json(forward.model_dump_json()) == forward


@pytest.mark.parametrize(
    "left,right,inputs,expected",
    [
        (candidate(money("0"), conditions_text="free"), None, {}, "insufficient"),
        (
            candidate(money("0"), conditions_text="free"),
            candidate(money("10"), bank_code="vtb"),
            {},
            "better",
        ),
        (
            candidate(dict(kind="individual", text_value="negotiated")),
            candidate(money("10"), bank_code="vtb"),
            {},
            "insufficient",
        ),
        (candidate(money("10")), candidate(money("10"), bank_code="vtb"), {}, "equal"),
        (candidate(money("100")), candidate(money("50"), bank_code="vtb"), {}, "worse"),
        (
            candidate(money("10")),
            candidate(money("50", currency="USD"), bank_code="vtb"),
            {},
            "insufficient",
        ),
        (
            candidate(money("10")),
            candidate(money("50", period="year"), bank_code="vtb"),
            {},
            "insufficient",
        ),
        (
            candidate(percent()),
            candidate(percent(basis="transfer_amount"), bank_code="vtb"),
            dict(transfers_count=1),
            "not_comparable",
        ),
        (
            candidate(percent("0.001")),
            candidate(percent("0.002"), bank_code="vtb"),
            dict(payroll_total="0.1"),
            "insufficient",
        ),
        (
            candidate(money("10")),
            candidate(money("50"), bank_code="vtb", valid_from="2026-10-12"),
            {},
            "not_comparable",
        ),
        (
            candidate(
                money("10"), metric_code="external_bank_transfer_fee", operation="external_transfer"
            ),
            candidate(
                money("50"),
                bank_code="vtb",
                payer="employee",
                metric_code="external_bank_transfer_fee",
                operation="external_transfer",
            ),
            dict(operation="external_transfer"),
            "not_comparable",
        ),
        (
            candidate(percent()),
            candidate(percent("0.5"), bank_code="vtb"),
            dict(payroll_total=None),
            "insufficient",
        ),
    ],
)
def test_pairwise_guard_golden(left, right, inputs, expected):
    result = compare(
        [item for item in (left, right) if item], scenario(**inputs), metrics=(left.metric_code,)
    )
    pair = result.rows[0].pairwise[0]
    assert pair.status == expected
    if expected in {"insufficient", "not_comparable"}:
        assert pair.delta is None


def test_live_conflicts_and_unknown_alternative_never_select_latest():
    first, second = candidate(money("100")), candidate(money("200"))
    right = candidate(money("300"), bank_code="vtb")
    assert compare([first, second, right]).rows[0].pairwise[0].status == "conflict"
    unknown = candidate(money("0"), conditions_text="free", employer_segment=dict(mode="unknown"))
    assert compare([first, unknown, right]).rows[0].pairwise[0].status == "insufficient"


def test_past_and_future_alternatives_do_not_hide_current_value():
    past = candidate(money("999"), valid_to="2026-01-02")
    future = candidate(money("1"), valid_from="2026-10-12")
    current = candidate(money("100"))
    right = candidate(money("200"), bank_code="vtb")
    assert compare([past, future, current, right]).rows[0].pairwise[0].delta == Decimal("-100")


def test_fixed_plus_percentage_known_sum_and_missing_component():
    fixed = calculate(candidate(money("50")), scenario())
    rate = calculate(candidate(percent()), scenario())
    total = sum_known_components(dict(fixed=fixed, rate=rate), ("fixed", "rate"))
    assert total.amount == Decimal("350") and total.complete
    partial = sum_known_components(dict(rate=rate), ("fixed", "rate"))
    assert partial.amount == Decimal("300") and partial.missing_components == ("fixed",)
    assert not partial.complete
    empty = sum_known_components({}, ("fixed", "rate"))
    assert empty.amount is None and not empty.complete


def test_known_cost_cannot_mix_payers_operations_units_or_horizons():
    baseline = calculate(candidate(money("50")), scenario())
    for item, user in [
        (candidate(money(), payer="employee"), scenario(payer="employee")),
        (candidate(money(period="year")), scenario(period="year")),
        (
            candidate(money(), operation="external_transfer"),
            scenario(operation="external_transfer"),
        ),
    ]:
        other = calculate(item, user)
        result = sum_known_components(dict(a=baseline, b=other), ("a", "b"))
        assert result.amount is None and not result.complete


def test_partial_claim_is_never_complete_total_or_global_winner():
    result = compare([candidate(percent()), candidate(money("100"), bank_code="vtb")])
    subtotal = next(c for c in result.claims if "known_components_only" in c.text)
    assert subtotal.computed_result == "300.00"
    assert "Full cost" in subtotal.text
    assert any("never a complete total" in limitation for limitation in result.limitations)


def test_context_precision_is_local_and_unknown_rounding_retains_estimate():
    with localcontext() as context:
        context.prec = 3
        result = calculate(candidate(percent("0.123456")), scenario(payroll_total="123456.789"))
        assert str(result.amount) == "152.41481342784"
        assert result.limitations == ("rounding_rule_unknown",)
        assert context.prec == 3


def test_per_transfer_rounding_uncertainty_survives_integer_aggregate():
    item = candidate(percent("0.3", basis="transfer_amount", period="per_transfer"))
    user = scenario(transfer_amount="1", transfers_count=100)
    result = calculate(item, user)
    assert result.amount == Decimal("0.300")
    assert result.operands["unit_amount"] == "0.003"
    assert result.limitations == ("rounding_rule_unknown",)
    assert compare([item, candidate(money(), bank_code="vtb")], user).rows[0].pairwise[
        0
    ].status == ("insufficient")


@pytest.mark.parametrize(
    "value",
    [
        dict(
            kind="range", lower="100", upper="200", unit="currency", currency="RUB", period="month"
        ),
        dict(
            kind="range", lower="50", upper="300", unit="currency", currency="RUB", period="month"
        ),
    ],
)
def test_ranges_are_not_point_prices(value):
    result = compare([candidate(value), candidate(money("150"), bank_code="vtb")])
    assert result.rows[0].cells[0].status == "unknown"
    assert result.rows[0].pairwise[0].status == "insufficient"


def test_four_bank_pairs_and_permutation_evidence_are_complete():
    banks = ("sber", "vtb", "alfa", "kuban_credit")
    items = [
        candidate(money(str(100 + index * 10)), bank_code=bank) for index, bank in enumerate(banks)
    ]
    result = compare(items, banks=banks)
    assert len(result.rows[0].pairwise) == 6
    for pair in result.rows[0].pairwise:
        assert pair.status == "better"
        claim = next(claim for claim in result.claims if claim.id == pair.claim_id)
        refs = {
            ref
            for item in items
            if item.bank_code in {pair.left, pair.right}
            for ref in item.evidence_ids
        }
        assert set(claim.evidence_ids) == refs


def test_repeated_request_stable_identity_and_every_call_rechecks_read():
    chosen = manifest()
    records = tuple(record(candidate(bank_code=bank), chosen) for bank in ("sber", "vtb"))
    reader = SyntheticReader(records)
    service = ComparisonService(reader, lambda _: chosen, clock=lambda: NOW)
    request = ComparisonRequest(
        snapshot_id=chosen.snapshot_id,
        bank_codes=("sber", "vtb"),
        metric_codes=("payroll_credit_fee",),
        scenario=scenario(),
    )
    assert asyncio.run(service.compare(request)) == asyncio.run(service.compare(request))
    assert reader.calls == 2


def test_numeric_membership_and_equivalent_decimal_facts():
    tree = TypeAdapter(Condition).validate_python(
        leaf(field="payroll_total", op="in", value=["100000.00", "200000"], unit="RUB")
    )
    assert condition_truth(tree, scenario()) is Truth.TRUE
    left = candidate(percent("0.30"))
    duplicate = candidate(percent("0.300"))
    right = candidate(percent("0.5"), bank_code="vtb")
    result = compare([left, duplicate, right])
    assert result.rows[0].cells[0].status == "verified"
    assert result.rows[0].pairwise[0].status == "better"
    assert set(result.rows[0].cells[0].evidence_ids) == set(
        left.evidence_ids + duplicate.evidence_ids
    )


def test_not_applicable_claim_retains_exclusion_evidence_and_false_truth():
    left = candidate(money(), valid_from="2026-10-12")
    right = candidate(money(), bank_code="vtb")
    result = compare([left, right])
    cell = result.rows[0].cells[0]
    assert cell.status == "not_applicable" and set(cell.evidence_ids) == set(left.evidence_ids)
    detail = json.loads(cell.conditions)[0]
    assert detail["truth"] == "FALSE" and detail["valid_from"] == "2026-10-12"


def test_transfer_granularity_and_negative_clamped_fee_are_not_inferred():
    ambiguous = calculate(candidate(percent(basis="transfer_amount")), scenario())
    assert ambiguous.missing == ("transfer_fee_granularity",)
    negative = calculate(candidate(formula(rate="-1")), scenario())
    assert negative.missing == ("negative_fee",)


def test_separate_metric_direction_and_incompatible_count_units():
    left = candidate(
        money("50000"),
        metric_code="cash_withdrawal_limit",
        payer="employee",
        operation="cash_withdrawal",
    )
    right = candidate(
        money("10000"),
        metric_code="cash_withdrawal_limit",
        payer="employee",
        operation="cash_withdrawal",
        bank_code="vtb",
    )
    result = compare(
        [left, right],
        scenario(payer="employee", operation="cash_withdrawal"),
        metrics=("cash_withdrawal_limit",),
    )
    assert result.rows[0].pairwise[0].status == "better"
    left = candidate(
        dict(kind="count", amount=1, unit="day", period="month"), metric_code="crediting_time"
    )
    right = candidate(
        dict(kind="count", amount=1, unit="business_day", period="month"),
        metric_code="crediting_time",
        bank_code="vtb",
    )
    assert compare([left, right], metrics=("crediting_time",)).rows[0].pairwise[0].status == (
        "not_comparable"
    )


def test_scenario_hash_is_order_and_decimal_scale_independent_but_input_sensitive():
    chosen = manifest()
    base = ComparisonRequest(
        snapshot_id=chosen.snapshot_id,
        bank_codes=("sber", "vtb"),
        metric_codes=("payroll_credit_fee",),
        scenario=scenario(),
    )
    scaled = base.model_copy(update={"scenario": scenario(payroll_total="100000.00")})
    changed = base.model_copy(update={"scenario": scenario(payroll_total="100001")})
    assert scenario_hash(base) == scenario_hash(scaled)
    assert scenario_hash(base) != scenario_hash(changed)


@pytest.mark.parametrize("tamper", ["snapshot", "corpus", "evidence", "review", "eligibility"])
def test_read_interface_defence_and_review_eligibility(tamper):
    chosen = manifest()
    row = record(candidate(), chosen)
    if tamper == "snapshot":
        row["snapshot_id"] = str(uuid4())
    elif tamper == "corpus":
        row["candidate"]["corpus_kind"] = "real"
    elif tamper == "evidence":
        row["evidence_ids"] = [str(uuid4())]
    elif tamper == "review":
        row["review_id"] = None
    else:
        row["eligible_for_comparison"] = False
    request = ComparisonRequest(
        snapshot_id=chosen.snapshot_id,
        bank_codes=("sber", "vtb"),
        metric_codes=("payroll_credit_fee",),
        scenario=scenario(),
    )
    service = ComparisonService(SyntheticReader((row,)), lambda _: chosen)
    if tamper == "eligibility":
        assert asyncio.run(service.compare(request)).rows[0].cells[0].status == "unknown"
    else:
        with pytest.raises(ValueError, match="PROVENANCE_INVALID"):
            asyncio.run(service.compare(request))


def test_pg_reviewed_publication_snapshot_isolation_and_no_cached_revocation(pipeline_db):
    ids, first, candidate_id, evidence = setup_candidate(pipeline_db)
    approved = approve(pipeline_db, first, candidate_id, evidence)
    publication = evidence.publish(first, candidate_id, approved)
    evidence.corpus.freeze(first)
    second = first.model_copy(update={"snapshot_id": uuid4(), "revision": first.revision + 1})
    evidence.corpus.add_version(second, 0)
    second_review = approve(pipeline_db, second, candidate_id, evidence)
    second_publication = evidence.publish(second, candidate_id, second_review)
    evidence.corpus.freeze(second)
    service = ComparisonService(evidence, lambda key: first if key == first.snapshot_id else second)

    def request(chosen):
        return ComparisonRequest(
            snapshot_id=chosen.snapshot_id,
            bank_codes=("sber", "vtb"),
            metric_codes=("account_monthly_fee",),
            scenario=scenario(operation="account_maintenance", period="месяц"),
        )

    a = asyncio.run(service.compare(request(first)))
    b = asyncio.run(service.compare(request(second)))
    assert a.corpus_revision == first.revision and b.corpus_revision == second.revision
    assert a.rows[0].cells[0].fact_ids == (UUID(publication.fact_id),)
    assert b.rows[0].cells[0].fact_ids == (UUID(second_publication.fact_id),)
    assert UUID(second_publication.fact_id) not in {ref for c in a.claims for ref in c.fact_ids}
    assert a.rows[0].cells[0].status == "unknown"  # published is not automatically current
    assert a.rows[0].cells[1].status == "unknown"  # missing bank is not zero
    assert "effective_date" in a.rows[0].cells[0].missing_inputs
    with pipeline_db[0].begin() as session:
        session.get(SourcePolicy, ids["policy"]).collection_decision = "denied"
    with pytest.raises(CorpusError, match="PERMISSION_REVOKED"):
        asyncio.run(service.compare(request(first)))


def test_pg_pending_and_unreadable_manifest_cannot_enter_comparison(pipeline_db):
    _, chosen, _, evidence = setup_candidate(pipeline_db)
    service = ComparisonService(evidence, lambda _: chosen)
    request = ComparisonRequest(
        snapshot_id=chosen.snapshot_id,
        bank_codes=("sber", "vtb"),
        metric_codes=("account_monthly_fee",),
        scenario=scenario(operation="account_maintenance", period="месяц"),
    )
    with pytest.raises(EvidenceError, match="SNAPSHOT_NOT_READABLE"):
        asyncio.run(service.compare(request))


def test_pg_fully_reviewed_fact_decimal_and_original_evidence(pipeline_db):
    _, chosen, original_id, evidence = setup_candidate(
        pipeline_db,
        text=(
            "Обслуживание счета — 100 RUB в месяц, действует с 10.10.2026. "
            "Работодатель: все сегменты, организации, пакеты и варианты договора; вся Россия."
        ),
    )
    # An explicit synthetic analyst proposal copies locatable evidence into a
    # new immutable candidate, then passes the real semantic/manual review gate.
    with pipeline_db[0].begin() as session:
        original = session.get(CandidateRow, original_id)
        refs = session.scalars(
            select(EvidenceRef).where(EvidenceRef.candidate_id == original_id)
        ).all()
        new_id = str(uuid4())
        ref_ids = {ref.id: str(uuid4()) for ref in refs}
        payload = json.loads(json.dumps(original.payload))
        payload.update(
            id=new_id,
            evidence_ids=list(ref_ids.values()),
            valid_from="2026-10-10",
            effective_date_status="explicit",
            period="месяц",
        )
        payload["geography"] = dict(
            kind="federal",
            region_codes=[],
            evidence_ids=[ref_ids[r.id] for r in refs if r.support_role == "scope"],
        )
        for field in (
            "employer_segment",
            "organization_category",
            "payroll_package",
            "contract_variant",
        ):
            payload[field] = dict(mode="any", values=[])
        session.add(
            CandidateRow(
                id=new_id,
                extraction_run_id=original.extraction_run_id,
                bank_id=original.bank_id,
                metric_code=original.metric_code,
                corpus_kind="synthetic",
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
            session.add(EvidenceRef(id=ref_ids[ref.id], candidate_id=new_id, **fields))
    conf = confirmation(pipeline_db, chosen, new_id, evidence)
    assert evidence.validate(chosen, new_id, conf).eligible_for_comparison
    review = approve(pipeline_db, chosen, new_id, evidence)
    publication = evidence.publish(chosen, new_id, review)
    evidence.corpus.freeze(chosen)
    service = ComparisonService(evidence, lambda _: chosen)
    request = ComparisonRequest(
        snapshot_id=chosen.snapshot_id,
        bank_codes=("sber", "vtb"),
        metric_codes=("account_monthly_fee",),
        scenario=scenario(operation="account_maintenance", period="месяц"),
    )
    result = asyncio.run(service.compare(request))
    cell = result.rows[0].cells[0]
    assert cell.status == "verified" and cell.value.amount == Decimal("100")
    assert cell.fact_ids == (UUID(publication.fact_id),)
    assert set(cell.evidence_ids) == {UUID(ref) for ref in ref_ids.values()}
    assert result.rows[0].pairwise[0].status == "insufficient"
