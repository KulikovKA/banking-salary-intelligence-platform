"""HTTP request/response contracts planned by API_CONTRACTS."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from .base import BankCode, ContractModel, require_aware_utc
from .comparison import Claim, ComparisonResult
from .evidence import EvidenceRef


class AnswerSource(ContractModel):
    evidence: EvidenceRef
    download_url: str = Field(pattern=r"^/api/v1/documents/[0-9a-fA-F-]+/original$")


class AnswerEnvelope(ContractModel):
    id: UUID
    status: Literal["answered", "partial", "clarification", "insufficient", "fallback"]
    snapshot_id: UUID
    corpus_revision: int = Field(ge=1)
    text: str
    comparison: ComparisonResult | None = None
    claims: tuple[Claim, ...] = ()
    sources: tuple[AnswerSource, ...] = ()
    limitations: tuple[str, ...] = ()
    data_as_of: date
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class ApiErrorDetail(ContractModel):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(max_length=1000)
    request_id: UUID
    details: dict[str, str] | None = None


class ApiError(ContractModel):
    error: ApiErrorDetail


class QuestionRequest(ContractModel):
    snapshot_id: UUID
    question: str = Field(min_length=1, max_length=2000)
    scenario: "Scenario | None" = None
    bank_codes: tuple[BankCode, ...] | None = Field(default=None, max_length=4)
    metric_codes: tuple[str, ...] | None = Field(default=None, max_length=20)

    @field_validator("bank_codes")
    @classmethod
    def unique_banks(cls, values: tuple[BankCode, ...] | None) -> tuple[BankCode, ...] | None:
        if values is not None and len(set(values)) != len(values):
            raise ValueError("BANK_CODES_DUPLICATE")
        return values

    @field_validator("metric_codes")
    @classmethod
    def unique_metrics(cls, values: tuple[str, ...] | None) -> tuple[str, ...] | None:
        import re

        if values is not None and (
            len(set(values)) != len(values)
            or any(not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", code) for code in values)
        ):
            raise ValueError("METRIC_CODES_INVALID")
        return values


from .tariffs import Scenario  # noqa: E402

QuestionRequest.model_rebuild()


__all__ = ["AnswerEnvelope", "AnswerSource", "ApiError", "ApiErrorDetail", "QuestionRequest"]
