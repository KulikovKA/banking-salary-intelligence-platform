"""Synthetic contract-level boundary tests for pure tariff normalization."""

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from app.contracts.tariffs import TariffCandidate
from app.tariffs.metrics import METRICS, get_metric
from app.tariffs.normalize import normalize_candidate

EVIDENCE_ID = UUID("00000000-0000-0000-0000-000000000007")


def raw_candidate(**changes: object) -> dict[str, object]:
    """Build a complete, synthetic raw row; each test changes only its subject."""
    raw: dict[str, object] = {
        "id": UUID("00000000-0000-0000-0000-000000000070"),
        "bank_code": "sber",
        "metric_code": "external_bank_transfer_fee",
        "value": {"kind": "money", "amount": "15,00", "currency": "RUB", "period": "per_transfer"},
        "payer": "employee",
        "operation": "external_transfer",
        "period": "per_transfer",
        "geography": {"kind": "unknown"},
        "employer_segment": {"mode": "unknown"},
        "organization_category": {"mode": "unknown"},
        "payroll_package": {"mode": "unknown"},
        "contract_variant": {"mode": "unknown"},
        "valid_from": "2026-01-01",
        "effective_date_status": "explicit",
        "evidence_ids": (EVIDENCE_ID,),
        "corpus_kind": "synthetic",
    }
    raw.update(changes)
    return raw


def normalized(**changes: object) -> TariffCandidate:
    result = normalize_candidate(raw_candidate(**changes))
    assert result.candidate is not None, result.flags
    return result.candidate


def test_registry_matches_domain_contract_metric_set_and_is_read_only() -> None:
    expected = {
        "payroll_credit_fee",
        "external_bank_transfer_fee",
        "account_monthly_fee",
        "employee_card_fee",
        "cash_withdrawal_limit",
        "transfer_limit",
        "crediting_time",
        "employee_privilege",
        "integration_1c",
        "integration_api",
    }
    assert set(METRICS) == expected
    assert get_metric("external_bank_transfer_fee") is METRICS["external_bank_transfer_fee"]
    with pytest.raises(TypeError):
        METRICS["new_metric"] = METRICS["transfer_limit"]  # type: ignore[index]


def test_percent_comma_is_decimal_percent_not_fraction_or_whole_percent() -> None:
    candidate = normalized(value={"kind": "percent", "amount": "0,30%", "basis": "transfer_amount"})
    assert candidate.value.kind == "percent"
    assert candidate.value.amount == Decimal("0.30")
    assert candidate.value.basis == "transfer_amount"


def test_explicit_unit_strings_normalize_without_changing_percent_scale() -> None:
    candidate = normalized(value="0,30%", basis="transfer_amount")
    assert candidate.value.kind == "percent"
    assert candidate.value.amount == Decimal("0.30")


def test_rub_thousands_and_decimal_comma_are_exact_decimal() -> None:
    candidate = normalized(value={"kind": "money", "amount": "1 234,56 ₽", "period": "per_batch"})
    assert candidate.value.kind == "money"
    assert candidate.value.amount == Decimal("1234.56")
    assert candidate.value.currency == "RUB"
    assert candidate.value.period == "per_batch"


def test_unknown_fee_is_not_zero_and_malformed_decimal_is_rejected() -> None:
    unknown = normalize_candidate(raw_candidate(value="неизвестно"))
    malformed = normalize_candidate(
        raw_candidate(value={"kind": "money", "amount": "NaN", "currency": "RUB"})
    )
    assert unknown.candidate is None and "VALUE_UNKNOWN" in unknown.flags
    assert malformed.candidate is None and "VALUE_INVALID" in malformed.flags


def test_conditional_free_is_zero_only_with_condition_wording_and_review_flag() -> None:
    result = normalize_candidate(
        raw_candidate(value="Бесплатно при переводе от 50 000 ₽", currency="RUB")
    )
    assert result.candidate is not None
    assert result.candidate.value.kind == "money"
    assert result.candidate.value.amount == 0
    assert result.candidate.conditions_text == "Бесплатно при переводе от 50 000 ₽"
    assert result.candidate.requires_manual_interpretation
    assert "CONDITIONS_UNPARSED" in result.flags


def test_free_without_currency_evidence_is_unknown_not_zero() -> None:
    result = normalize_candidate(raw_candidate(value="Бесплатно при условии"))
    assert result.candidate is None
    assert "CURRENCY_UNKNOWN" in result.flags


def test_zero_without_evidence_text_does_not_silently_become_free() -> None:
    result = normalize_candidate(
        raw_candidate(value={"kind": "money", "amount": "0", "currency": "RUB"})
    )
    assert result.candidate is None
    assert any(flag.startswith("CANDIDATE_INVALID:") for flag in result.flags)


def test_explicitly_free_is_distinguished_from_unknown() -> None:
    candidate = normalized(value="Бесплатно", currency="RUB")
    assert candidate.value.kind == "money"
    assert candidate.value.amount == 0
    assert candidate.conditions_text == "Бесплатно"
    assert not candidate.requires_manual_interpretation


def test_range_bounds_are_decimal_and_reversed_bounds_fail() -> None:
    candidate = normalized(
        value={
            "kind": "range",
            "lower": "1 000,50",
            "upper": "2 000",
            "unit": "currency",
            "currency": "RUB",
        }
    )
    assert candidate.value.kind == "range"
    assert candidate.value.lower == Decimal("1000.50")
    assert candidate.value.upper == Decimal("2000")
    invalid = normalize_candidate(
        raw_candidate(
            value={
                "kind": "range",
                "lower": "2",
                "upper": "1",
                "unit": "currency",
                "currency": "RUB",
            }
        )
    )
    assert invalid.candidate is None


@pytest.mark.parametrize(
    ("bounds", "expected"),
    [({"lower": "10"}, (Decimal("10"), None)), ({"upper": "20"}, (None, Decimal("20")))],
)
def test_open_ended_from_and_up_to_ranges(
    bounds: dict[str, str], expected: tuple[Decimal | None, Decimal | None]
) -> None:
    candidate = normalized(value={"kind": "range", **bounds, "unit": "currency", "currency": "RUB"})
    assert candidate.value.kind == "range"
    assert (candidate.value.lower, candidate.value.upper) == expected


def test_individual_tariff_is_preserved_as_non_numeric_value() -> None:
    candidate = normalized(value="Индивидуально по запросу")
    assert candidate.value.kind == "individual"
    assert candidate.value.text_value == "Индивидуально по запросу"


def test_payer_is_preserved_and_metric_incompatible_payer_is_rejected() -> None:
    employee = normalized(payer="employee")
    assert employee.payer == "employee"
    employer_fee = normalized(payer="employer")
    assert employer_fee.payer == "employer"
    incompatible = normalize_candidate(
        raw_candidate(
            payer="employee", metric_code="payroll_credit_fee", operation="payroll_credit"
        )
    )
    assert incompatible.candidate is None
    assert "METRIC_SEMANTICS_MISMATCH" in incompatible.flags


def test_per_transfer_and_per_batch_values_remain_distinct() -> None:
    per_transfer = normalized(period="per_transfer")
    per_batch = normalized(
        period="per_batch",
        value={
            "kind": "money",
            "amount": "15,00",
            "currency": "RUB",
            "period": "per_batch",
        },
    )
    assert per_transfer.period == "per_transfer"
    assert per_batch.period == "per_batch"
    assert per_transfer.value.period == "per_transfer"
    assert per_batch.value.period == "per_batch"


def test_inclusive_end_date_becomes_exclusive_and_keeps_original_wording() -> None:
    result = normalize_candidate(
        raw_candidate(
            valid_to="2026-12-31",
            valid_to_inclusive=True,
            valid_to_text="действует по 31.12.2026 включительно",
        )
    )
    assert result.candidate is not None
    assert result.candidate.valid_to == date(2027, 1, 1)
    assert result.valid_to_text == "действует по 31.12.2026 включительно"


def test_inclusive_end_flag_without_end_date_is_invalid() -> None:
    result = normalize_candidate(raw_candidate(valid_to=None, valid_to_inclusive=True))
    assert result.candidate is None
    assert "DATE_INVALID" in result.flags


def test_future_and_unknown_dates_are_explicit_not_inferred() -> None:
    future = normalized(valid_from="2030-01-01", effective_date_status="explicit")
    assert future.valid_from == date(2030, 1, 1)
    unknown = normalize_candidate(raw_candidate(valid_from=None, valid_to=None))
    assert unknown.candidate is not None
    assert unknown.candidate.effective_date_status == "unknown"
    assert unknown.candidate.valid_from is None
    assert "DATE_UNKNOWN" in unknown.flags


def test_scope_and_conditions_are_not_guessed_and_invalid_ast_is_flagged() -> None:
    candidate = normalized()
    assert candidate.geography.kind == "unknown"
    assert candidate.employer_segment.mode == "unknown"
    invalid = normalize_candidate(
        raw_candidate(
            conditions={
                "kind": "leaf",
                "field": "secret_field",
                "op": "eq",
                "value": "x",
            }
        )
    )
    assert invalid.candidate is None
    assert "CONDITION_AST_INVALID" in invalid.flags


def test_condition_text_stays_conditional_and_ast_is_restricted() -> None:
    result = normalize_candidate(
        raw_candidate(
            conditions={"kind": "leaf", "field": "transfers_count", "op": "gte", "value": 10},
            conditions_text="при не менее 10 переводах за месяц",
        )
    )
    assert result.candidate is not None
    assert result.candidate.conditions is not None
    assert result.candidate.conditions_text == "при не менее 10 переводах за месяц"
    assert not result.candidate.requires_manual_interpretation


def test_unknown_metric_and_unit_kind_conflict_are_flags() -> None:
    metric = normalize_candidate(raw_candidate(metric_code="made_up_metric"))
    unit = normalize_candidate(
        raw_candidate(value={"kind": "money", "amount": "0,30%", "currency": "RUB"})
    )
    assert metric.candidate is None and "METRIC_UNKNOWN" in metric.flags
    assert unit.candidate is None and "VALUE_UNIT_KIND_CONFLICT" in unit.flags


def test_normalization_is_idempotent_on_candidate_dump() -> None:
    first = normalized(value={"kind": "percent", "amount": "0,30%", "basis": "transfer_amount"})
    second = normalize_candidate(first.model_dump(mode="python"))
    assert second.candidate == first
    assert second.candidate is not None
