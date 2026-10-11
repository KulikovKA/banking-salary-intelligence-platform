"""Pure Decimal arithmetic and conservative three-valued applicability.

No IO, tariff inference, rounding rule inference or LLM calls belong here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, DecimalException, Inexact, localcontext
from enum import Enum
from typing import Any

from app.contracts.tariffs import (
    BooleanValue,
    Condition,
    ConditionGroup,
    CountValue,
    FormulaValue,
    MoneyValue,
    PercentValue,
    Scenario,
    TariffCandidate,
    Value,
)

FORMULA_VERSION = "comparison-decimal-v1"


class Truth(Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


def conjunction(values: tuple[Truth, ...]) -> Truth:
    if Truth.FALSE in values:
        return Truth.FALSE
    return Truth.UNKNOWN if Truth.UNKNOWN in values else Truth.TRUE


def condition_truth(condition: Condition | None, scenario: Scenario) -> Truth:
    """Kleene logic; malformed types/units remain UNKNOWN, never truthy strings."""
    if condition is None:
        return Truth.TRUE
    if isinstance(condition, ConditionGroup):
        children = tuple(condition_truth(child, scenario) for child in condition.conditions)
        if condition.kind == "all":
            return conjunction(children)
        if Truth.TRUE in children:
            return Truth.TRUE
        return Truth.UNKNOWN if Truth.UNKNOWN in children else Truth.FALSE
    actual = getattr(scenario, condition.field)
    if actual is None:
        return Truth.UNKNOWN
    expected: Any = condition.value
    try:
        if condition.op == "in" and condition.field in {
            "payroll_total",
            "transfer_amount",
            "employee_count",
            "transfers_count",
            "as_of",
        }:
            if not isinstance(expected, tuple):
                return Truth.UNKNOWN
            if condition.field == "as_of":
                if condition.unit is not None:
                    return Truth.UNKNOWN
                expected_dates = tuple(date.fromisoformat(item) for item in expected)
                return Truth.TRUE if actual in expected_dates else Truth.FALSE
            units = (
                {None, "currency", scenario.currency}
                if condition.field in {"payroll_total", "transfer_amount"}
                else {
                    None,
                    "count",
                    "employee" if condition.field == "employee_count" else "transfer",
                }
            )
            if condition.unit not in units:
                return Truth.UNKNOWN
            expected_numbers = tuple(Decimal(item) for item in expected)
            if any(not item.is_finite() for item in expected_numbers):
                return Truth.UNKNOWN
            return Truth.TRUE if Decimal(actual) in expected_numbers else Truth.FALSE
        if condition.field in {"payroll_total", "transfer_amount"}:
            if condition.unit not in {None, "currency", scenario.currency}:
                return Truth.UNKNOWN
            if isinstance(expected, (bool, tuple)):
                return Truth.UNKNOWN
            expected = Decimal(expected)
            if not expected.is_finite():
                return Truth.UNKNOWN
        elif condition.field in {"employee_count", "transfers_count"}:
            units = {
                None,
                "count",
                "employee" if condition.field == "employee_count" else "transfer",
            }
            if condition.unit not in units or isinstance(expected, (bool, tuple)):
                return Truth.UNKNOWN
            expected = Decimal(expected)
            if not expected.is_finite() or expected != expected.to_integral_value():
                return Truth.UNKNOWN
            actual = Decimal(actual)
        elif condition.field == "as_of":
            if condition.unit is not None or not isinstance(expected, str):
                return Truth.UNKNOWN
            expected = date.fromisoformat(expected)
        elif condition.unit is not None:
            return Truth.UNKNOWN
        elif condition.op == "in":
            if not isinstance(actual, str) or not isinstance(expected, tuple):
                return Truth.UNKNOWN
            return Truth.TRUE if actual in expected else Truth.FALSE
        elif not isinstance(actual, str) or not isinstance(expected, str):
            return Truth.UNKNOWN
        elif condition.op != "eq":
            # There is no ordered domain for regions/packages/operation strings.
            return Truth.UNKNOWN
        if condition.op == "in":
            return Truth.UNKNOWN
        result = {
            "eq": lambda: actual == expected,
            "gte": lambda: actual >= expected,
            "gt": lambda: actual > expected,
            "lte": lambda: actual <= expected,
            "lt": lambda: actual < expected,
        }[condition.op]()
        return Truth.TRUE if result else Truth.FALSE
    except (ValueError, TypeError, DecimalException):
        return Truth.UNKNOWN


def applicability(candidate: TariffCandidate, scenario: Scenario) -> tuple[Truth, tuple[str, ...]]:
    states: list[Truth] = []
    missing: list[str] = []

    def check(state: Truth, field: str) -> None:
        states.append(state)
        if state is Truth.UNKNOWN:
            missing.append(field)

    check(Truth.TRUE if candidate.payer == scenario.payer else Truth.FALSE, "payer")
    check(Truth.TRUE if candidate.operation == scenario.operation else Truth.FALSE, "operation")
    if candidate.valid_from is None or candidate.effective_date_status == "unknown":
        check(Truth.UNKNOWN, "effective_date")
    else:
        current = candidate.valid_from <= scenario.as_of and (
            candidate.valid_to is None or scenario.as_of < candidate.valid_to
        )
        check(Truth.TRUE if current else Truth.FALSE, "as_of")
    geography = candidate.geography
    if geography.kind == "unknown":
        check(Truth.UNKNOWN, "geography")
    elif geography.kind == "regional":
        check(
            Truth.UNKNOWN
            if scenario.region is None
            else (Truth.TRUE if scenario.region in geography.region_codes else Truth.FALSE),
            "region",
        )
    for name, actual in (
        ("employer_segment", scenario.employer_segment),
        ("organization_category", scenario.organization_category),
        ("payroll_package", scenario.package_by_bank.get(candidate.bank_code)),
        ("contract_variant", scenario.contract_variant_by_bank.get(candidate.bank_code)),
    ):
        dimension = getattr(candidate, name)
        if dimension.mode == "any":
            check(Truth.TRUE, name)
        elif dimension.mode == "unknown" or actual is None:
            check(Truth.UNKNOWN, name)
        else:
            check(Truth.TRUE if actual in dimension.values else Truth.FALSE, name)
    unparsed = (
        candidate.conditions_text
        and candidate.conditions is None
        and (candidate.conditions_text not in {"free", "бесплатно", "без комиссии"})
    )
    if candidate.requires_manual_interpretation or unparsed:
        check(Truth.UNKNOWN, "conditions")
    else:
        check(condition_truth(candidate.conditions, scenario), "conditions")
    return conjunction(tuple(states)), tuple(missing)


@dataclass(frozen=True)
class Calculation:
    value: Value | None
    amount: Decimal | None
    # Comparison signature includes the original basis. Converting to money
    # does not erase semantic incompatibility between different tariff bases.
    signature: tuple[str, ...]
    operands: dict[str, str]
    formula: str
    missing: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @property
    def sufficient(self) -> bool:
        return not self.missing and not self.limitations and self.value is not None


def calculate(candidate: TariffCandidate, scenario: Scenario) -> Calculation:
    """Evaluate one fact. per_batch means one explicitly selected batch horizon.

    per_transfer amounts are multiplied by transfers_count over scenario.period.
    Unknown batch count is never inferred from transfers_count or employee_count.
    Unrounded money is an estimate when it has fractional minor units; without
    a reviewed rounding rule such an estimate must not produce a winner.
    """
    value = candidate.value
    period = candidate.period or getattr(value, "period", None)
    value_period = getattr(value, "period", None)
    basis = getattr(value, "basis", None)
    currency = getattr(value, "currency", None)
    unit = getattr(value, "unit", value.kind)
    operands: dict[str, str] = {"value": value.model_dump_json()}
    signature = (
        candidate.payer,
        candidate.operation,
        str(currency or ""),
        str(unit),
        str(period or ""),
        str(basis or ""),
    )

    def unavailable(reason: str) -> Calculation:
        return Calculation(None, None, signature, operands, "unavailable", (reason,))

    if candidate.period and value_period and candidate.period != value_period:
        return unavailable("period_conflict")
    if currency is not None and currency != scenario.currency:
        return unavailable("currency_incompatible")
    if isinstance(value, BooleanValue):
        return Calculation(
            value, Decimal(int(value.boolean_value)), signature, operands, "identity"
        )
    if not isinstance(value, (MoneyValue, PercentValue, FormulaValue, CountValue)):
        return Calculation(value, None, signature, operands, "identity", limitations=("non_exact",))
    if period is None:
        return unavailable("period")
    if scenario.period is None:
        return unavailable("period")
    multiplier = Decimal(1)
    if period == "per_transfer" and candidate.metric_code.endswith("_fee"):
        if scenario.transfers_count is None:
            return unavailable("transfers_count")
        multiplier = Decimal(scenario.transfers_count)
    elif period != scenario.period:
        return unavailable("batch_count" if period == "per_batch" else "period_incompatible")
    operands["multiplier"] = str(multiplier)
    try:
        with localcontext() as context:
            context.prec = 28
            context.traps[Inexact] = True
            if isinstance(value, (MoneyValue, CountValue)):
                unit_amount = Decimal(value.amount)
                formula = "amount * multiplier"
            elif isinstance(value, FormulaValue) and value.formula == "constant":
                unit_amount = value.parameters["constant"]
                formula = "constant * multiplier"
            else:
                if basis not in {"payroll_total", "transfer_amount"}:
                    return unavailable("basis")
                base = getattr(scenario, basis)
                if base is None:
                    return unavailable(basis)
                if (
                    basis == "transfer_amount"
                    and period != "per_transfer"
                    and (scenario.transfers_count is None or scenario.transfers_count != 1)
                ):
                    return unavailable("transfer_fee_granularity")
                operands["base"] = str(base)
                rate = value.amount if isinstance(value, PercentValue) else value.parameters["rate"]
                if rate < 0:
                    return unavailable("negative_fee")
                operands["rate"] = str(rate)
                unit_amount = base * rate / Decimal(100)
                formula = "base * rate / 100"
                if isinstance(value, FormulaValue) and value.formula == "percentage_clamped":
                    lower, upper = value.parameters["min_fee"], value.parameters["max_fee"]
                    if lower < 0 or upper < 0:
                        return unavailable("negative_fee")
                    operands.update(min_fee=str(lower), max_fee=str(upper))
                    unit_amount = min(max(unit_amount, lower), upper)
                    formula = "min(max(base * rate / 100, min_fee), max_fee)"
                formula += " * multiplier"
            amount = unit_amount * multiplier
            operands["unit_amount"] = str(unit_amount)
            if amount < 0:
                return unavailable("negative_fee")
            if isinstance(value, CountValue):
                return Calculation(value, amount, signature, operands, formula)
            if isinstance(value, FormulaValue) and currency is None:
                return unavailable("currency")
            result = MoneyValue(
                kind="money",
                amount=amount,
                currency=currency or scenario.currency,
                period=scenario.period,
            )
            signature = (
                candidate.payer,
                candidate.operation,
                result.currency,
                "currency",
                scenario.period,
                str(basis or ""),
            )
            # The current normalizer supports RUB money. Other currencies have
            # no reviewed minor-unit/rounding contract in v1.
            rounding_unknown = (
                result.currency != "RUB"
                or unit_amount % Decimal("0.01") != 0
                or amount % Decimal("0.01") != 0
            )
            limitations = ("rounding_rule_unknown",) if rounding_unknown else ()
            return Calculation(
                result, amount, signature, operands, formula, limitations=limitations
            )
    except DecimalException:
        return unavailable("decimal_precision_exceeded")


@dataclass(frozen=True)
class KnownCost:
    amount: Decimal | None
    missing_components: tuple[str, ...]
    complete: bool


def sum_known_components(
    components: dict[str, Calculation], required: tuple[str, ...]
) -> KnownCost:
    """Sum an explicitly supplied component set; never infer cost completeness.

    Different bases may contribute to the same cost horizon, but payer,
    operation, currency, unit and period must match. Duplicate required names
    or unknown required set is an error, rather than a false complete total.
    """
    if not required or len(required) != len(set(required)) or not set(components) <= set(required):
        raise ValueError("COST_COMPONENT_SET_INVALID")
    known = [item for item in components.values() if item.sufficient and item.amount is not None]
    missing = tuple(
        code for code in required if code not in components or not components[code].sufficient
    )
    signatures = {item.signature[:5] for item in known}
    if len(signatures) > 1 or any(item.signature[3] != "currency" for item in known):
        return KnownCost(None, required, False)
    if not known:
        return KnownCost(None, missing, False)
    try:
        with localcontext() as context:
            context.prec = 28
            context.traps[Inexact] = True
            amount = sum((item.amount for item in known if item.amount is not None), Decimal(0))
    except DecimalException:
        return KnownCost(None, required, False)
    return KnownCost(amount, missing, not missing)
