"""Canonical registry for tariff metrics used by downstream deterministic logic."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

ValueKind = Literal[
    "money", "percent", "count", "boolean", "text", "range", "formula", "individual"
]
Payer = Literal["employer", "employee"]
Direction = Literal["lower", "higher", "neutral"]


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """Semantic constraints for one public comparison metric."""

    code: str
    title: str
    allowed_kinds: tuple[ValueKind, ...]
    allowed_units: tuple[str, ...]
    payer: tuple[Payer, ...]
    operation: tuple[str, ...]
    direction: Direction
    required_scenario_fields: tuple[str, ...]


_definitions = (
    MetricDefinition(
        "payroll_credit_fee",
        "Payroll crediting fee",
        ("money", "percent", "range", "formula", "individual"),
        ("currency", "percent"),
        ("employer",),
        ("payroll_credit",),
        "lower",
        ("payroll_total", "period"),
    ),
    MetricDefinition(
        "external_bank_transfer_fee",
        "External bank transfer fee",
        ("money", "percent", "range", "formula", "individual"),
        ("currency", "percent"),
        ("employer", "employee"),
        ("external_transfer",),
        "lower",
        ("transfer_amount", "transfers_count", "period"),
    ),
    MetricDefinition(
        "account_monthly_fee",
        "Monthly account fee",
        ("money", "range", "individual"),
        ("currency",),
        ("employer",),
        ("account_maintenance",),
        "lower",
        ("period",),
    ),
    MetricDefinition(
        "employee_card_fee",
        "Employee card fee",
        ("money", "range", "individual"),
        ("currency",),
        ("employer", "employee"),
        ("card_issuance", "card_maintenance"),
        "lower",
        ("employee_count", "period"),
    ),
    MetricDefinition(
        "cash_withdrawal_limit",
        "Cash withdrawal limit",
        ("money", "range", "individual"),
        ("currency",),
        ("employee",),
        ("cash_withdrawal",),
        "higher",
        ("transfer_amount", "period"),
    ),
    MetricDefinition(
        "transfer_limit",
        "Transfer limit",
        ("money", "count", "range", "individual"),
        ("currency", "transfer", "batch"),
        ("employee", "employer"),
        ("external_transfer", "internal_transfer"),
        "higher",
        ("transfer_amount", "period"),
    ),
    MetricDefinition(
        "crediting_time",
        "Payroll crediting time",
        ("count", "range", "text", "individual"),
        ("hour", "day", "business_day"),
        ("employer", "employee"),
        ("payroll_credit",),
        "lower",
        ("period",),
    ),
    MetricDefinition(
        "employee_privilege",
        "Employee privilege",
        ("boolean", "text", "individual"),
        ("boolean", "text"),
        ("employee",),
        ("employee_benefit",),
        "higher",
        (),
    ),
    MetricDefinition(
        "integration_1c",
        "1C integration",
        ("boolean", "text", "individual"),
        ("boolean", "text"),
        ("employer",),
        ("payroll_integration",),
        "neutral",
        (),
    ),
    MetricDefinition(
        "integration_api",
        "API integration",
        ("boolean", "text", "individual"),
        ("boolean", "text"),
        ("employer",),
        ("payroll_integration",),
        "neutral",
        (),
    ),
)

METRICS: Mapping[str, MetricDefinition] = MappingProxyType(
    {item.code: item for item in _definitions}
)


def get_metric(code: str) -> MetricDefinition | None:
    """Return a registered metric, or ``None`` for an unknown code."""

    return METRICS.get(code)


__all__ = ["METRICS", "MetricDefinition", "get_metric"]
