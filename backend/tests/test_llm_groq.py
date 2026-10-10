"""All Groq transport behavior is exercised through httpx2 HTTP mocks."""

import asyncio
import json
import logging
from uuid import UUID

import httpx2 as httpx
import pytest

from app.config import Settings
from app.contracts.llm import IntentResult, LLMError, LLMMessage, LLMRequest, LLMResponse
from app.llm.groq import GroqLLM, _payload, _retry_after_ms, _validate_base

_KEY = "canary-groq-secret-do-not-log"
_DEFAULT_REQUEST_ID = UUID(int=11)


class BudgetStub:
    def __init__(self, *, reject: bool = False) -> None:
        self.reject = reject
        self.reserved: list[int] = []
        self.settled: list[tuple[int, int, bool]] = []
        self.released: list[UUID] = []
        self.unknown: list[UUID] = []

    async def reserve(self, request_id, user_id, tokens, model_id) -> None:
        self.reserved.append(tokens)
        if self.reject:
            from app.llm.budget import BudgetRejected

            raise BudgetRejected

    async def settle(self, request_id, prompt_tokens, completion_tokens, *, estimated) -> None:
        self.settled.append((prompt_tokens, completion_tokens, estimated))

    async def release(self, request_id) -> None:
        self.released.append(request_id)

    async def mark_unknown(self, request_id) -> None:
        self.unknown.append(request_id)


def make_request(
    *, timeout_ms: int = 1000, request_id: UUID = _DEFAULT_REQUEST_ID
) -> LLMRequest:
    return LLMRequest(
        purpose="intent",
        template_version="v1",
        messages=(LLMMessage(role="user", content="Compare synthetic offers."),),
        output_schema=IntentResult.model_json_schema(),
        max_output_tokens=128,
        timeout_ms=timeout_ms,
        request_id=request_id,
    )


def valid_body(*, usage: dict[str, int] | None = None) -> dict[str, object]:
    scenario_fields = (
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
        "employee_count",
        "transfers_count",
        "package_by_bank",
        "contract_variant_by_bank",
    )
    return {
        "id": "mock-request-id",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps(
                        {
                            "schema_version": 1,
                            "intent": "clarify",
                            "bank_codes": [],
                            "metric_codes": [],
                            "scenario_patch": {key: None for key in scenario_fields},
                            "clarification": "Please clarify.",
                        }
                    )
                },
            }
        ],
        "usage": usage or {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
    }


def configured_client(handler, budget: BudgetStub | None = None) -> tuple[GroqLLM, BudgetStub]:
    selected_budget = budget or BudgetStub()
    transport = httpx.MockTransport(handler)

    def factory(**kwargs):
        return httpx.AsyncClient(transport=transport, **kwargs)

    settings = Settings.from_environment(
        {
            "APP_ENV": "test",
            "LLM_MODE": "provider",
            "LLM_MODEL": "openai/gpt-oss-120b",
            "LLM_API_BASE": "https://api.groq.com/openai/v1",
            "LLM_ALLOWED_HOSTS": "api.groq.com",
            "LLM_API_KEY": _KEY,
        }
    )
    return GroqLLM(settings, selected_budget, client_factory=factory), selected_budget


def run(client: GroqLLM, request: LLMRequest | None = None):
    return asyncio.run(client.complete(request or make_request()))


def test_valid_structured_output_is_locally_validated_and_settled() -> None:
    def handler(request):
        assert request.url == "https://api.groq.com/openai/v1/chat/completions"
        assert request.headers["authorization"] == f"Bearer {_KEY}"
        body = json.loads(request.content)
        assert body["model"] == "openai/gpt-oss-120b"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["tools"] == [] and body["stream"] is False
        return httpx.Response(200, json=valid_body())

    client, budget = configured_client(handler)
    response = run(client)
    assert isinstance(response, LLMResponse)
    assert response.parsed_json["intent"] == "clarify"
    assert response.usage.total_tokens == 20 and not response.usage.estimated
    assert response.provider_request_id == "mock-request-id"
    assert budget.settled == [(12, 8, False)]


@pytest.mark.parametrize(
    "body",
    [
        {**valid_body(), "choices": []},
        {**valid_body(), "choices": [{"message": {"content": "not json"}}]},
        {
            **valid_body(),
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": (
                            '{"intent":"compare","bank_codes":["invented"],'
                            '"metric_codes":[],"scenario_patch":{}}'
                        )
                    },
                }
            ],
        },
        {**valid_body(), "usage": {"prompt_tokens": -1, "completion_tokens": 1}},
    ],
)
def test_invalid_json_or_contract_is_rejected(body) -> None:
    client, _ = configured_client(lambda request: httpx.Response(200, json=body))
    assert run(client) == LLMError(code="invalid_output")


def test_429_retries_once_only_when_retry_after_fits_deadline() -> None:
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": "busy"})
        return httpx.Response(200, json=valid_body())

    client, _ = configured_client(handler)
    assert isinstance(run(client), LLMResponse)
    assert calls == 2


def test_question_scope_caps_total_provider_dispatches() -> None:
    calls = [0]

    def handler(request):
        calls[0] += 1
        return httpx.Response(200, json=valid_body())

    selected_budget = BudgetStub()
    transport = httpx.MockTransport(handler)

    def factory(**kwargs):
        return httpx.AsyncClient(transport=transport, **kwargs)

    settings = Settings.from_environment(
        {
            "APP_ENV": "test",
            "LLM_MODE": "provider",
            "LLM_MODEL": "openai/gpt-oss-120b",
            "LLM_API_BASE": "https://api.groq.com/openai/v1",
            "LLM_ALLOWED_HOSTS": "api.groq.com",
            "LLM_API_KEY": _KEY,
        }
    )
    client = GroqLLM(settings, selected_budget, client_factory=factory)

    async def scenario():
        async with client.question_scope():
            first = await client.complete(make_request(request_id=UUID(int=11)))
            second = await client.complete(make_request(request_id=UUID(int=12)))
            third = await client.complete(make_request(request_id=UUID(int=13)))
            return first, second, third

    first, second, third = asyncio.run(scenario())
    assert isinstance(first, LLMResponse) and isinstance(second, LLMResponse)
    assert third == LLMError(code="budget_exceeded")
    assert calls == [2]


@pytest.mark.parametrize(
    "status,headers,body,expected",
    [
        (429, {"retry-after": "120"}, {"error": "busy"}, "rate_limit"),
        (401, {}, {"error": {"message": _KEY}}, "auth"),
        (503, {}, {"error": "down"}, "unavailable"),
        (400, {}, {"error": {"message": "maximum context length exceeded"}}, "context_exceeded"),
    ],
)
def test_status_mapping_and_unknown_usage_reservation(status, headers, body, expected) -> None:
    client, budget = configured_client(
        lambda request: httpx.Response(status, headers=headers, json=body)
    )
    assert run(client) == LLMError(code=expected, retry_after_ms=120_000 if status == 429 else None)
    if status == 503:
        assert budget.unknown == [UUID(int=11)]
    else:
        assert budget.released == [UUID(int=11)]


def test_network_timeout_unknown_usage_and_budget_exhaustion() -> None:
    def disconnect(request):
        raise httpx.ConnectError("private transport detail", request=request)

    client, budget = configured_client(disconnect)
    assert run(client) == LLMError(code="unavailable")
    assert budget.unknown == [UUID(int=11)]

    timeout_calls = 0

    def timeout(request):
        nonlocal timeout_calls
        timeout_calls += 1
        raise httpx.ReadTimeout("private timeout detail", request=request)

    client, budget = configured_client(timeout)
    assert run(client) == LLMError(code="timeout")
    assert timeout_calls == 2
    assert budget.unknown == [UUID(int=11)]

    rejecting = BudgetStub(reject=True)
    client, _ = configured_client(lambda request: httpx.Response(200), rejecting)
    assert run(client) == LLMError(code="budget_exceeded")


def test_response_redirect_is_rejected_without_following() -> None:
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(307, headers={"location": "https://attacker.test/collect"})

    client, _ = configured_client(handler)
    assert run(client) == LLMError(code="invalid_output")
    assert calls == 1


def test_strict_wire_schema_is_closed_required_and_uses_request_allowlists() -> None:
    schema = _payload(make_request(), "openai/gpt-oss-120b", 128)["response_format"]
    assert isinstance(schema, dict)
    root = schema["json_schema"]["schema"]

    def visit(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert sorted(node["properties"]) == node["required"]
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(root)
    assert "propertyNames" not in json.dumps(root)
    assert "scenario_patch" in root["properties"]


def test_secret_canary_does_not_appear_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    client, _ = configured_client(
        lambda request: httpx.Response(401, json={"error": {"message": _KEY}})
    )
    with caplog.at_level(logging.WARNING):
        assert run(client) == LLMError(code="auth")
    assert _KEY not in caplog.text


@pytest.mark.parametrize("endpoint", ["http://api.groq.com/openai/v1", "https://evil.test/v1", "https://u:p@api.groq.com/openai/v1"])
def test_endpoint_must_be_the_groq_allowlisted_origin(endpoint: str) -> None:
    with pytest.raises(ValueError):
        _validate_base(endpoint)


def test_retry_after_supports_seconds_and_http_dates() -> None:
    assert _retry_after_ms("1.5") == 1500
    assert _retry_after_ms("not-a-date") is None
    schema = _payload(make_request(), "openai/gpt-oss-120b", 128)["response_format"]
    assert isinstance(schema, dict)
    assert schema["json_schema"]["strict"] is True
