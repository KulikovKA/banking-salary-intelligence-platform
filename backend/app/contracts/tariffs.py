"""Scenario, tariff value, applicability and candidate contracts."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .base import BankCode, ContractModel, CorpusKind, DecimalStringModel, strict_decimal


class ScopeDimension(ContractModel):
    mode: Literal["any", "specific", "unknown"]
    values: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_scope(self) -> "ScopeDimension":
        if (self.mode == "specific") != bool(self.values):
            raise ValueError("SCOPE_VALUES_MUST_MATCH_MODE")
        if len(set(self.values)) != len(self.values):
            raise ValueError("SCOPE_VALUES_DUPLICATE")
        return self


class Geography(ContractModel):
    kind: Literal["federal", "regional", "unknown"]
    region_codes: tuple[str, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def validate_regions(self) -> "Geography":
        if (self.kind == "regional") != bool(self.region_codes):
            raise ValueError("GEOGRAPHY_REGION_CODES_INVALID")
        if self.kind != "unknown" and not self.evidence_ids:
            raise ValueError("GEOGRAPHY_EVIDENCE_REQUIRED")
        if len(set(self.region_codes)) != len(self.region_codes):
            raise ValueError("GEOGRAPHY_REGION_CODES_DUPLICATE")
        return self


class Scenario(DecimalStringModel):
    region: str | None = None
    employer_segment: str | None = None
    organization_category: str | None = None
    package_by_bank: dict[BankCode, str] = Field(default_factory=dict)
    contract_variant_by_bank: dict[BankCode, str] = Field(default_factory=dict)
    payer: Literal["employer", "employee"]
    operation: str = Field(min_length=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    payroll_total: Decimal | None = None
    employee_count: int | None = Field(default=None, ge=1)
    transfer_amount: Decimal | None = None
    transfers_count: int | None = Field(default=None, ge=1)
    period: str | None = None
    as_of: date

    @field_validator("payroll_total", "transfer_amount", mode="before")
    @classmethod
    def parse_amount(cls, value: object) -> Decimal | None:
        return None if value is None else strict_decimal(value)

    @model_validator(mode="after")
    def validate_amounts(self) -> "Scenario":
        for amount in (self.payroll_total, self.transfer_amount):
            if amount is not None and amount < 0:
                raise ValueError("SCENARIO_AMOUNT_NEGATIVE")
        return self


class MoneyValue(DecimalStringModel):
    kind: Literal["money"]
    amount: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    unit: Literal["currency"] = "currency"
    period: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, value: object) -> Decimal:
        amount = strict_decimal(value)
        if amount < 0:
            raise ValueError("VALUE_AMOUNT_NEGATIVE")
        return amount


class PercentValue(DecimalStringModel):
    kind: Literal["percent"]
    amount: Decimal
    unit: Literal["percent"] = "percent"
    basis: str = Field(min_length=1)
    period: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, value: object) -> Decimal:
        return strict_decimal(value)


class CountValue(DecimalStringModel):
    kind: Literal["count"]
    amount: int
    unit: str = Field(min_length=1)
    period: str | None = None


class BooleanValue(ContractModel):
    kind: Literal["boolean"]
    boolean_value: bool


class TextValue(ContractModel):
    kind: Literal["text"]
    text_value: str


class RangeValue(DecimalStringModel):
    kind: Literal["range"]
    lower: Decimal | None = None
    upper: Decimal | None = None
    lower_inclusive: bool = True
    upper_inclusive: bool = True
    unit: str = Field(min_length=1)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    basis: str | None = None
    period: str | None = None

    @field_validator("lower", "upper", mode="before")
    @classmethod
    def parse_bound(cls, value: object) -> Decimal | None:
        return None if value is None else strict_decimal(value)

    @model_validator(mode="after")
    def validate_bounds(self) -> "RangeValue":
        if self.lower is None and self.upper is None:
            raise ValueError("RANGE_REQUIRES_BOUND")
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValueError("RANGE_BOUNDS_INVALID")
        return self


class FormulaValue(DecimalStringModel):
    kind: Literal["formula"]
    formula: Literal["constant", "percentage", "percentage_clamped"]
    parameters: dict[str, Decimal]
    basis: str | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    period: str | None = None

    @field_validator("parameters", mode="before")
    @classmethod
    def parse_parameters(cls, value: object) -> dict[str, Decimal]:
        if not isinstance(value, dict):
            raise ValueError("FORMULA_PARAMETERS_INVALID")
        return {key: strict_decimal(item) for key, item in value.items()}

    @model_validator(mode="after")
    def validate_formula(self) -> "FormulaValue":
        required = {"constant"} if self.formula == "constant" else {"rate"}
        if self.formula == "percentage_clamped":
            required |= {"min_fee", "max_fee"}
        if set(self.parameters) != required:
            raise ValueError("FORMULA_PARAMETERS_UNSUPPORTED")
        if "min_fee" in self.parameters and self.parameters["min_fee"] > self.parameters["max_fee"]:
            raise ValueError("FORMULA_BOUNDS_INVALID")
        return self


class IndividualValue(ContractModel):
    kind: Literal["individual"]
    text_value: str = Field(min_length=1)


Value: TypeAlias = Annotated[
    MoneyValue
    | PercentValue
    | CountValue
    | BooleanValue
    | TextValue
    | RangeValue
    | FormulaValue
    | IndividualValue,
    Field(discriminator="kind"),
]


ConditionField = Literal[
    "region",
    "employer_segment",
    "organization_category",
    "payer",
    "operation",
    "currency",
    "payroll_total",
    "employee_count",
    "transfer_amount",
    "transfers_count",
    "period",
    "as_of",
]
ConditionOp = Literal["eq", "in", "gte", "gt", "lte", "lt"]


class ConditionLeaf(ContractModel):
    kind: Literal["leaf"] = "leaf"
    field: ConditionField
    op: ConditionOp
    value: str | int | bool | tuple[str, ...]
    unit: str | None = None

    @field_validator("value", mode="before")
    @classmethod
    def reject_decimal_float(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("CONDITION_DECIMAL_STRING_REQUIRED")
        return value

    @model_validator(mode="after")
    def validate_operator_value(self) -> "ConditionLeaf":
        if self.op == "in" and (not isinstance(self.value, tuple) or not self.value):
            raise ValueError("CONDITION_IN_REQUIRES_VALUES")
        if self.op != "in" and isinstance(self.value, tuple):
            raise ValueError("CONDITION_VALUE_INVALID")
        return self


class ConditionGroup(ContractModel):
    kind: Literal["all", "any"]
    conditions: tuple["Condition", ...] = Field(min_length=1)


Condition: TypeAlias = Annotated[ConditionLeaf | ConditionGroup, Field(discriminator="kind")]
ConditionGroup.model_rebuild()


def _condition_stats(node: Condition, depth: int = 1) -> tuple[int, int]:
    if isinstance(node, ConditionLeaf):
        return depth, 1
    stats = [_condition_stats(child, depth + 1) for child in node.conditions]
    return max([depth, *(item[0] for item in stats)]), sum(item[1] for item in stats)


class TariffCandidate(DecimalStringModel):
    id: UUID
    bank_code: BankCode
    metric_code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    value: Value
    payer: Literal["employer", "employee"]
    operation: str = Field(min_length=1)
    period: str | None = None
    geography: Geography
    employer_segment: ScopeDimension
    organization_category: ScopeDimension
    payroll_package: ScopeDimension
    contract_variant: ScopeDimension
    conditions: Condition | None = None
    conditions_text: str | None = None
    requires_manual_interpretation: bool = False
    valid_from: date | None = None
    valid_to: date | None = None
    effective_date_status: Literal["explicit", "analyst_confirmed", "unknown"] = "unknown"
    evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    validation_flags: tuple[str, ...] = ()
    corpus_kind: CorpusKind
    publication_state: Literal["pending_review"] = "pending_review"

    @model_validator(mode="after")
    def validate_candidate(self) -> "TariffCandidate":
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("CANDIDATE_DATE_RANGE_INVALID")
        if (self.effective_date_status == "unknown") != (self.valid_from is None):
            raise ValueError("CANDIDATE_DATE_STATUS_MISMATCH")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("CANDIDATE_EVIDENCE_DUPLICATE")
        if not set(self.geography.evidence_ids) <= set(self.evidence_ids):
            raise ValueError("GEOGRAPHY_EVIDENCE_NOT_ATTACHED")
        if (
            isinstance(self.value, MoneyValue)
            and self.value.amount == 0
            and self.conditions is None
            and not self.conditions_text
        ):
            raise ValueError("ZERO_FEE_REQUIRES_CONDITIONS")
        if self.conditions is not None:
            depth, leaves = _condition_stats(self.conditions)
            if depth > 4 or leaves > 30:
                raise ValueError("CONDITION_AST_LIMIT_EXCEEDED")
        return self


__all__ = ["Condition", "Geography", "Scenario", "ScopeDimension", "TariffCandidate", "Value"]
