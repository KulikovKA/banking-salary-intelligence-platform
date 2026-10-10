"""Comparison request/result DTOs. Computation belongs to a later service."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .base import BankCode, ContractModel, DecimalStringModel, require_aware_utc, strict_decimal
from .tariffs import Scenario


class ComparisonRequest(ContractModel):
    snapshot_id: UUID
    bank_codes: tuple[BankCode, ...] = Field(min_length=2, max_length=4)
    metric_codes: tuple[str, ...] = Field(min_length=1, max_length=20)
    scenario: Scenario

    @field_validator("bank_codes")
    @classmethod
    def unique_banks(cls, values: tuple[BankCode, ...]) -> tuple[BankCode, ...]:
        if len(set(values)) != len(values):
            raise ValueError("BANK_CODES_DUPLICATE")
        return values

    @field_validator("metric_codes")
    @classmethod
    def unique_metrics(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values) or any(
            not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", code) for code in values
        ):
            raise ValueError("METRIC_CODES_INVALID")
        return values


class ComparisonCell(DecimalStringModel):
    bank_code: BankCode
    status: Literal["verified", "not_applicable", "unknown", "individual", "conflict", "blocked"]
    value: "Value | None" = None
    fact_ids: tuple[UUID, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    conditions: str | None = None

    @model_validator(mode="after")
    def validate_verified_support(self) -> "ComparisonCell":
        if self.status == "verified" and (self.value is None or not self.evidence_ids):
            raise ValueError("VERIFIED_CELL_REQUIRES_VALUE_AND_EVIDENCE")
        if self.status == "individual" and not isinstance(self.value, IndividualValue):
            raise ValueError("INDIVIDUAL_CELL_REQUIRES_INDIVIDUAL_VALUE")
        return self


class PairwiseResult(DecimalStringModel):
    left: BankCode
    right: BankCode
    status: Literal["better", "worse", "equal", "not_comparable", "insufficient", "conflict"]
    delta: Decimal | None = None
    formula: str | None = None
    claim_id: UUID | None = None

    @field_validator("delta", mode="before")
    @classmethod
    def parse_delta(cls, value: object) -> Decimal | None:
        return None if value is None else strict_decimal(value)


class ComparisonRow(ContractModel):
    metric_code: str
    cells: tuple[ComparisonCell, ...]
    pairwise: tuple[PairwiseResult, ...] = ()


class Claim(ContractModel):
    id: UUID
    kind: Literal["fact", "calculation", "comparison", "absence_of_evidence"]
    text: str
    fact_ids: tuple[UUID, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()
    formula_version: str | None = None
    scenario_hash: str | None = None
    computed_result: str | None = None


class ComparisonResult(ContractModel):
    id: UUID
    snapshot_id: UUID
    corpus_revision: int = Field(ge=1)
    scenario_echo: Scenario
    rows: tuple[ComparisonRow, ...]
    claims: tuple[Claim, ...] = ()
    limitations: tuple[str, ...] = ()
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class ComparisonService(Protocol):
    async def compare(self, request: ComparisonRequest) -> ComparisonResult: ...


from .tariffs import IndividualValue, Value  # noqa: E402

ComparisonCell.model_rebuild()


__all__ = ["Claim", "ComparisonRequest", "ComparisonResult", "ComparisonService"]
