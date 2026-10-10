"""Deterministic offline Fake implementing the SNAP-01 asynchronous LLM protocol."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import TypeAlias

from app.contracts.llm import LLMClient, LLMError, LLMRequest, LLMResponse, LLMUsage

from .base import OutputValidationError, validate_output

FakeFailure: TypeAlias = str
FakePayload: TypeAlias = dict[str, object] | FakeFailure


@dataclass(frozen=True)
class FakeFixture:
    """Explicit deterministic outcome, optionally scoped by request purpose."""

    payload: dict[str, object] | None = None
    error: str | None = None
    malformed_json: bool = False
    delay_ms: int = 0


class FakeLLM(LLMClient):
    """No network access; defaults only to clarification and empty explain output."""

    def __init__(
        self,
        fixtures: dict[str, FakeFixture] | None = None,
        *,
        model_id: str = "fake/offline-v1",
    ) -> None:
        self._fixtures = dict(fixtures or {})
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
            if fixture.error not in {
                "timeout",
                "rate_limit",
                "auth",
                "unavailable",
                "invalid_output",
                "context_exceeded",
                "budget_exceeded",
            }:
                return LLMError(code="invalid_output")
            return LLMError(
                code=fixture.error, retry_after_ms=1000 if fixture.error == "rate_limit" else None
            )
        if fixture.malformed_json:
            try:
                json.loads('{"unterminated":')
            except json.JSONDecodeError:
                return LLMError(code="invalid_output")
        payload = fixture.payload or {}
        try:
            normalized = validate_output(request, payload)
        except OutputValidationError:
            return LLMError(code="invalid_output")
        token_count = len(json.dumps(normalized, ensure_ascii=False, sort_keys=True).split())
        usage = LLMUsage(
            prompt_tokens=0,
            completion_tokens=token_count,
            total_tokens=token_count,
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


__all__ = ["FakeFixture", "FakeLLM"]
