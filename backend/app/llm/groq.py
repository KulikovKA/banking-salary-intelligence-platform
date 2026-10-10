"""Bounded Groq Chat Completions adapter with strict local output validation."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx2 as httpx

from app.config import Settings
from app.contracts.llm import LLMClient, LLMError, LLMRequest, LLMResponse, LLMUsage

from .base import OutputValidationError, validate_output
from .budget import BudgetRejected, PostgresTokenBudget, current_budget_user

_LOG = logging.getLogger(__name__)
_BASE_URL = "https://api.groq.com/openai/v1"
_MODEL = "openai/gpt-oss-120b"
_question_scope: ContextVar[_QuestionScope | None] = ContextVar("groq_question_scope", default=None)


@dataclass
class _QuestionScope:
    deadline: float
    dispatched: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class GroqLLM(LLMClient):
    """Groq implementation of the frozen provider-neutral async protocol."""

    def __init__(
        self,
        settings: Settings,
        budget: PostgresTokenBudget,
        *,
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        if settings.llm_mode != "provider":
            raise ValueError("GROQ_PROVIDER_MODE_REQUIRED")
        if settings.llm_api_key is None or settings.llm_model != _MODEL:
            raise ValueError("GROQ_CONFIGURATION_INVALID")
        self._key = settings.llm_api_key.get_secret_value()
        self._budget = budget
        self._model = settings.llm_model
        self._base = _validate_base(settings.llm_api_base or "")
        self._allowed_hosts = {item.lower() for item in settings.llm_allowed_hosts}
        if urlsplit(self._base).hostname not in self._allowed_hosts:
            raise ValueError("GROQ_HOST_NOT_ALLOWED")
        self._call_timeout = settings.llm_call_timeout_seconds
        self._total_timeout = settings.llm_total_timeout_seconds
        self._max_attempts = settings.llm_max_attempts
        self._max_input = settings.llm_max_input_tokens
        self._max_output = settings.llm_max_output_tokens
        self._daily_limit = settings.llm_daily_token_budget
        self._client_factory = client_factory

    @asynccontextmanager
    async def question_scope(self) -> AsyncIterator[None]:
        """Share call, token, and deadline ceilings across intent/explain calls."""
        if _question_scope.get() is not None:
            raise RuntimeError("GROQ_QUESTION_SCOPE_NESTED")
        scope = _QuestionScope(time.monotonic() + self._total_timeout)
        token = _question_scope.set(scope)
        try:
            yield
        finally:
            _question_scope.reset(token)

    async def complete(self, request: LLMRequest) -> LLMResponse | LLMError:
        started = time.monotonic()
        prompt_estimate = _estimate_tokens(request)
        output_cap = min(request.max_output_tokens, self._max_output)
        scope = _question_scope.get()
        attempts = min(self._max_attempts, 2)
        if scope is not None:
            attempts = min(attempts, 2 - scope.dispatched)
            if (
                attempts <= 0
                or scope.input_tokens + prompt_estimate > self._max_input
                or scope.output_tokens + output_cap > self._max_output
            ):
                return LLMError(code="budget_exceeded")
        if prompt_estimate > self._max_input or request.max_output_tokens > self._max_output:
            return LLMError(code="context_exceeded")
        reservation = prompt_estimate + output_cap
        # An ambiguous failed attempt may have consumed the entire reservation.
        reserved_total = reservation * attempts
        if reserved_total > self._daily_limit:
            return LLMError(code="budget_exceeded")
        try:
            await self._budget.reserve(
                request.request_id, current_budget_user(), reserved_total, self._model
            )
        except BudgetRejected:
            return LLMError(code="budget_exceeded")
        except Exception:
            _LOG.warning("llm_budget_unavailable")
            return LLMError(code="unavailable")
        if scope is not None:
            scope.input_tokens += prompt_estimate
            scope.output_tokens += output_cap

        deadline = started + min(self._total_timeout, request.timeout_ms / 1000)
        if scope is not None:
            deadline = min(deadline, scope.deadline)
        dispatched = False
        ambiguous = False
        used_prompt = 0
        used_completion = 0
        retry_after_ms: int | None = None
        response_data: dict[str, Any] | None = None
        status_error: str | None = None
        timeout = httpx.Timeout(self._call_timeout)
        try:
            async with self._client_factory(
                timeout=timeout,
                follow_redirects=False,
                trust_env=False,
                headers={
                    "Authorization": f"Bearer {self._key}",
                    "Content-Type": "application/json",
                },
            ) as client:
                for attempt in range(attempts):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        status_error = "timeout"
                        break
                    try:
                        dispatched = True
                        if scope is not None:
                            if scope.dispatched >= 2:
                                status_error = "budget_exceeded"
                                break
                            scope.dispatched += 1
                        response = await asyncio.wait_for(
                            client.post(
                                f"{self._base}/chat/completions",
                                json=_payload(request, self._model, output_cap),
                                timeout=min(self._call_timeout, remaining),
                            ),
                            timeout=remaining,
                        )
                    except (TimeoutError, httpx.TimeoutException):
                        ambiguous = True
                        status_error = "timeout"
                        if attempt + 1 < attempts and time.monotonic() < deadline:
                            continue
                        break
                    except (httpx.TransportError, OSError):
                        ambiguous = True
                        status_error = "unavailable"
                        if attempt + 1 < attempts and time.monotonic() < deadline:
                            continue
                        break
                    if response.status_code == 200:
                        try:
                            response_data = response.json()
                        except (ValueError, TypeError):
                            status_error = "invalid_output"
                        break
                    if response.status_code == 401 or response.status_code == 403:
                        status_error = "auth"
                        break
                    if response.status_code == 429:
                        retry_after_ms = _retry_after_ms(response.headers.get("retry-after"))
                        status_error = "rate_limit"
                        if (
                            attempt + 1 < attempts
                            and retry_after_ms is not None
                            and retry_after_ms <= max(0, int((deadline - time.monotonic()) * 1000))
                        ):
                            await asyncio.sleep(retry_after_ms / 1000)
                            continue
                        break
                    if response.status_code >= 500:
                        ambiguous = True
                        status_error = "unavailable"
                        if attempt + 1 < attempts and time.monotonic() < deadline:
                            continue
                        break
                    try:
                        error_body = response.json()
                    except (ValueError, TypeError):
                        error_body = {}
                    status_error = (
                        "context_exceeded"
                        if _is_context_error(response.status_code, error_body)
                        else "invalid_output"
                    )
                    break
        except (TimeoutError, httpx.TimeoutException):
            status_error = "timeout"
            ambiguous = dispatched
        except (httpx.TransportError, OSError):
            status_error = "unavailable"
            ambiguous = dispatched

        if response_data is not None:
            if not isinstance(response_data, dict):
                await self._safe_mark_unknown(request.request_id)
                return LLMError(code="invalid_output")
            try:
                result, used_prompt, used_completion, provider_id, finish_reason = _decode(
                    request, response_data
                )
            except OutputValidationError:
                await self._safe_mark_unknown(request.request_id)
                return LLMError(code="invalid_output")
            except (KeyError, TypeError, ValueError):
                await self._safe_mark_unknown(request.request_id)
                return LLMError(code="invalid_output")
            if ambiguous:
                # Earlier attempt's consumption is unknown; preserve the full reservation.
                await self._safe_mark_unknown(request.request_id)
                estimated = True
            else:
                try:
                    await self._budget.settle(
                        request.request_id, used_prompt, used_completion, estimated=False
                    )
                except Exception:
                    _LOG.warning("llm_usage_settlement_failed")
                    return LLMError(code="unavailable")
                estimated = False
            return LLMResponse(
                parsed_json=result,
                usage=LLMUsage(
                    prompt_tokens=used_prompt,
                    completion_tokens=used_completion,
                    total_tokens=used_prompt + used_completion,
                    estimated=estimated,
                ),
                provider_request_id=provider_id,
                model_id=self._model,
                finish_reason=finish_reason,
                latency_ms=max(0, int((time.monotonic() - started) * 1000)),
            )

        await self._preserve_usage(request.request_id, dispatched, ambiguous)
        if status_error == "rate_limit":
            return LLMError(code="rate_limit", retry_after_ms=retry_after_ms)
        if status_error in {"auth", "timeout", "context_exceeded", "invalid_output"}:
            return LLMError(code=status_error)  # type: ignore[arg-type]
        if status_error == "budget_exceeded":
            return LLMError(code="budget_exceeded")
        return LLMError(code="unavailable")

    async def _preserve_usage(
        self, request_id: UUID, dispatched: bool, ambiguous: bool
    ) -> None:
        if not dispatched:
            try:
                await self._budget.release(request_id)
            except Exception:
                _LOG.warning("llm_budget_release_failed")
        elif ambiguous:
            await self._safe_mark_unknown(request_id)
        else:
            try:
                await self._budget.release(request_id)
            except Exception:
                _LOG.warning("llm_budget_release_failed")

    async def _safe_mark_unknown(self, request_id: UUID) -> None:
        try:
            await self._budget.mark_unknown(request_id)
        except Exception:
            _LOG.warning("llm_unknown_usage_persist_failed")


def _validate_base(value: str) -> str:
    parsed = urlsplit(value)
    if (
        value.rstrip("/") != _BASE_URL
        or parsed.scheme != "https"
        or parsed.hostname != "api.groq.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("GROQ_ENDPOINT_INVALID")
    return _BASE_URL


def _estimate_tokens(request: LLMRequest) -> int:
    # Conservative character heuristic; provider token usage settles the reservation.
    chars = sum(len(message.content) for message in request.messages)
    return max(1, (chars + 2) // 3)


def _payload(request: LLMRequest, model: str, max_tokens: int) -> dict[str, object]:
    schema = _provider_schema(request.output_schema)
    return {
        "model": model,
        "messages": [message.model_dump(mode="json") for message in request.messages],
        "max_tokens": max_tokens,
        "stream": False,
        "tools": [],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": re.sub(
                    r"[^a-zA-Z0-9_-]", "_", request.purpose + "_" + request.template_version
                )[:64],
                "strict": True,
                "schema": schema,
            },
        },
    }


def _provider_schema(schema: dict[str, object]) -> dict[str, object]:
    """Build a strict-mode-compatible schema while keeping local DTO validation exact."""
    claim_ids = schema.get("allowed_claim_ids", [])
    templates = schema.get("allowed_templates", [])
    allowed_ids = claim_ids if isinstance(claim_ids, list) else []
    allowed_templates = templates if isinstance(templates, list) else []
    return _strict_schema_node(schema, None, allowed_ids, allowed_templates)


def _strict_schema_node(
    node: dict[str, object],
    property_name: str | None,
    claim_ids: list[object],
    templates: list[object],
) -> dict[str, object]:
    if property_name == "scenario_patch":
        return _scenario_patch_schema()
    if property_name == "template_by_claim":
        template_value = {"anyOf": [{"type": "string", "enum": templates}, {"type": "null"}]}
        ids = [value for value in claim_ids if isinstance(value, str)]
        return {
            "type": "object",
            "properties": {claim_id: template_value for claim_id in ids},
            "required": sorted(ids),
            "additionalProperties": False,
        }

    annotations = {"title", "description", "default", "format", "propertyNames"}
    result: dict[str, object] = {}
    for key, value in node.items():
        if key in annotations or key in {"allowed_claim_ids", "allowed_templates"}:
            continue
        if key == "const":
            result["enum"] = [value]
        elif key == "additionalProperties":
            # Unbounded dictionaries are closed below; their two frozen contract
            # instances are expanded from explicit backend allowlists above.
            continue
        elif key == "properties" and isinstance(value, dict):
            result[key] = {
                name: _strict_schema_node(item, name, claim_ids, templates)
                for name, item in value.items()
                if isinstance(name, str) and isinstance(item, dict)
            }
        elif isinstance(value, dict):
            result[key] = _strict_schema_node(value, None, claim_ids, templates)
        elif isinstance(value, list):
            result[key] = [
                _strict_schema_node(item, None, claim_ids, templates)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        elif key not in {"minLength", "maxLength", "minItems", "maxItems"}:
            result[key] = value
    properties = result.get("properties")
    if result.get("type") == "object":
        if not isinstance(properties, dict):
            properties = {}
            result["properties"] = properties
        result["required"] = sorted(properties)
        result["additionalProperties"] = False
    return result


def _scenario_patch_schema() -> dict[str, object]:
    nullable_string = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    nullable_integer = {"anyOf": [{"type": "integer"}, {"type": "null"}]}
    bank_value = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    bank_map = {
        "type": "object",
        "properties": {bank: bank_value for bank in ("sber", "vtb", "alfa", "kuban_credit")},
        "required": ["alfa", "kuban_credit", "sber", "vtb"],
        "additionalProperties": False,
    }
    nullable_bank_map = {"anyOf": [bank_map, {"type": "null"}]}
    properties: dict[str, object] = {
        key: nullable_string
        for key in (
            "region",
            "employer_segment",
            "organization_category",
            "payer",
            "operation",
            "currency",
            "payroll_total",
            "transfer_amount",
            "period",
            "as_of",
        )
    }
    properties.update({"employee_count": nullable_integer, "transfers_count": nullable_integer})
    properties["package_by_bank"] = nullable_bank_map
    properties["contract_variant_by_bank"] = nullable_bank_map
    return {
        "type": "object",
        "properties": properties,
        "required": sorted(properties),
        "additionalProperties": False,
    }


def _decode(
    request: LLMRequest, data: dict[str, Any]
) -> tuple[dict[str, object], int, int, str | None, str]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise OutputValidationError("CHOICES_MISSING")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict) or message.get("refusal"):
        raise OutputValidationError("REFUSED_OR_MISSING_MESSAGE")
    content = message.get("content")
    if not isinstance(content, str):
        raise OutputValidationError("CONTENT_MISSING")
    parsed = json.loads(content)
    parsed = _clean_wire_payload(request.purpose, parsed)
    normalized = validate_output(request, parsed)
    usage = data.get("usage")
    if not isinstance(usage, dict):
        raise OutputValidationError("USAGE_MISSING")
    prompt_tokens = _nonnegative_int(usage.get("prompt_tokens"))
    completion_tokens = _nonnegative_int(usage.get("completion_tokens"))
    provider_id = data.get("id")
    finish_reason = choice.get("finish_reason")
    if provider_id is not None and not isinstance(provider_id, str):
        provider_id = None
    if not isinstance(finish_reason, str) or not finish_reason:
        raise OutputValidationError("FINISH_REASON_MISSING")
    return normalized, prompt_tokens, completion_tokens, provider_id, finish_reason


def _clean_wire_payload(purpose: str, payload: object) -> object:
    if not isinstance(payload, dict):
        return payload
    cleaned = dict(payload)
    if purpose == "intent" and isinstance(cleaned.get("scenario_patch"), dict):
        patch = {
            key: value
            for key, value in cleaned["scenario_patch"].items()
            if value is not None
        }
        for key, value in tuple(patch.items()):
            if key in {"package_by_bank", "contract_variant_by_bank"} and isinstance(value, dict):
                patch[key] = {bank: item for bank, item in value.items() if item is not None}
        cleaned["scenario_patch"] = patch
    if purpose == "explain" and isinstance(cleaned.get("template_by_claim"), dict):
        cleaned["template_by_claim"] = {
            key: value
            for key, value in cleaned["template_by_claim"].items()
            if value is not None
        }
    return cleaned


def _nonnegative_int(value: object) -> int:
    if type(value) is not int or value < 0:
        raise OutputValidationError("USAGE_INVALID")
    return value


def _retry_after_ms(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return max(0, min(300_000, int(float(value) * 1000)))
    except ValueError:
        try:
            target = parsedate_to_datetime(value)
            if target.tzinfo is None:
                target = target.replace(tzinfo=UTC)
            return max(0, min(300_000, int((target - datetime.now(UTC)).total_seconds() * 1000)))
        except (TypeError, ValueError, OverflowError):
            return None


def _is_context_error(status: int, body: object) -> bool:
    if status != 400 or not isinstance(body, dict):
        return False
    error = body.get("error")
    message = error.get("message", "") if isinstance(error, dict) else ""
    return isinstance(message, str) and any(
        marker in message.lower()
        for marker in ("context length", "too many tokens", "maximum context")
    )


__all__ = ["GroqLLM"]
