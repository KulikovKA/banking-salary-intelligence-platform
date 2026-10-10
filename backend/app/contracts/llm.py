"""Provider-neutral asynchronous LLM contracts."""

from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, field_validator

from .base import BankCode, ContractModel


class LLMMessage(ContractModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(max_length=20_000)


class LLMRequest(ContractModel):
    purpose: Literal["intent", "explain"]
    template_version: str = Field(min_length=1, max_length=64)
    messages: tuple[LLMMessage, ...] = Field(min_length=1, max_length=20)
    output_schema: dict[str, object]
    max_output_tokens: int = Field(ge=1, le=4096)
    timeout_ms: int = Field(ge=1, le=60_000)
    request_id: UUID


class LLMUsage(ContractModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated: bool = False


class LLMResponse(ContractModel):
    parsed_json: dict[str, object]
    usage: LLMUsage
    provider_request_id: str | None = None
    model_id: str = Field(min_length=1)
    finish_reason: str = Field(min_length=1)
    latency_ms: int = Field(ge=0)


class LLMError(ContractModel):
    code: Literal[
        "timeout",
        "rate_limit",
        "auth",
        "unavailable",
        "invalid_output",
        "context_exceeded",
        "budget_exceeded",
    ]
    retry_after_ms: int | None = Field(default=None, ge=0)


class IntentResult(ContractModel):
    intent: Literal["compare", "facts", "documents", "clarify"]
    bank_codes: tuple[BankCode, ...] = Field(max_length=4)
    metric_codes: tuple[str, ...] = Field(max_length=20)
    scenario_patch: dict[str, object] = Field(default_factory=dict)
    clarification: str | None = Field(default=None, max_length=1000)

    @field_validator("bank_codes")
    @classmethod
    def validate_banks(cls, values: tuple[BankCode, ...]) -> tuple[BankCode, ...]:
        if len(set(values)) != len(values):
            raise ValueError("BANK_CODES_DUPLICATE")
        return values

    @field_validator("scenario_patch")
    @classmethod
    def validate_scenario_patch(cls, patch: dict[str, object]) -> dict[str, object]:
        allowed = {
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
            "package_by_bank",
            "contract_variant_by_bank",
        }
        if not set(patch) <= allowed:
            raise ValueError("SCENARIO_PATCH_FIELD_UNSUPPORTED")
        return patch


class ExplainResult(ContractModel):
    ordered_claim_ids: tuple[UUID, ...] = Field(max_length=50)
    template_by_claim: dict[UUID, str] = Field(default_factory=dict)


class LLMClient(Protocol):
    """Implementations return typed provider failures and must not expose traces."""

    async def complete(self, request: LLMRequest) -> LLMResponse | LLMError: ...


__all__ = [
    "ExplainResult",
    "IntentResult",
    "LLMClient",
    "LLMError",
    "LLMRequest",
    "LLMResponse",
    "LLMUsage",
]
