"""Deterministic offline Fake implementing the SNAP-01 asynchronous LLM protocol."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal, TypeAlias

from app.contracts.llm import LLMClient, LLMError, LLMRequest, LLMResponse, LLMUsage

from .base import OutputValidationError, validate_output

FakeFailure: TypeAlias = Literal[
    "timeout",
    "rate_limit",
    "auth",
    "unavailable",
    "invalid_output",
    "context_exceeded",
    "budget_exceeded",
]


@dataclass(frozen=True)
class FakeFixture:
    """Explicit deterministic outcome selected by request ID, never by prompt text."""

    payload: dict[str, object] | None = None
    error: FakeFailure | None = None
    malformed_json: bool = False
    delay_ms: int = 0
    raw_json: str | None = None

    def __post_init__(self) -> None:
        if self.delay_ms < 0:
            raise ValueError("FAKE_DELAY_MUST_BE_NONNEGATIVE")
        if self.error is not None:
            LLMError(code=self.error)


class FakeLLM(LLMClient):
    """No network access; defaults only to clarification and empty explain output."""

    def __init__(
        self,
        fixtures: dict[str, FakeFixture] | None = None,
        *,
        model_id: str = "fake/offline-v1",
    ) -> None:
        self._fixtures = deepcopy(fixtures or {})
        self._model_id = model_id

    async def complete(self, request: LLMRequest) -> LLMResponse | LLMError:
        fixture = self._fixtures.get(str(request.request_id))
        if fixture is None:
            fixture = self._default_fixture(request)
        if fixture.delay_ms > request.timeout_ms:
            return LLMError(code="timeout")
        if fixture.delay_ms:
            await asyncio.sleep(fixture.delay_ms / 1000)
        if fixture.error is not None:
            return LLMError(
                code=fixture.error, retry_after_ms=1000 if fixture.error == "rate_limit" else None
            )
        try:
            raw_json = fixture.raw_json
            if fixture.malformed_json:
                raw_json = '{"unterminated":'
            if raw_json is None:
                raw_json = json.dumps(fixture.payload or {}, allow_nan=False)
            payload = json.loads(raw_json)
            normalized = validate_output(request, payload)
        except (OutputValidationError, ValueError, TypeError):
            return LLMError(code="invalid_output")
        token_count = len(json.dumps(normalized, ensure_ascii=False, sort_keys=True).split())
        usage = LLMUsage(
            prompt_tokens=sum((len(message.content) + 3) // 4 for message in request.messages),
            completion_tokens=token_count,
            total_tokens=token_count
            + sum((len(message.content) + 3) // 4 for message in request.messages),
            estimated=True,
        )
        return LLMResponse(
            parsed_json=normalized,
            usage=usage,
            model_id=self._model_id,
            finish_reason="stop",
            latency_ms=0,
        )

    @staticmethod
    def _default_fixture(request: LLMRequest) -> FakeFixture:
        if request.purpose == "intent":
            return FakeFixture(
                payload={
                    "intent": "clarify",
                    "bank_codes": [],
                    "metric_codes": [],
                    "scenario_patch": {},
                    "clarification": "Уточните банки, условия или сценарий для поиска.",
                }
            )
        return FakeFixture(payload={"ordered_claim_ids": [], "template_by_claim": {}})


__all__ = ["FakeFailure", "FakeFixture", "FakeLLM"]
