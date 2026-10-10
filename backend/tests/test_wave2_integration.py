"""Integration of authenticated identity, real PG quotas and mocked Groq transport."""

import asyncio
import json
from uuid import uuid4

import httpx2 as httpx
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete
from test_auth_sessions import auth_db  # noqa: F401 -- shared real PostgreSQL fixture

from app.auth.api import AuthContext, create_auth_router
from app.config import Settings
from app.contracts.llm import IntentResult, LLMMessage, LLMRequest, LLMResponse
from app.llm.budget import PostgresTokenBudget, reset_budget_user, set_budget_user
from app.llm.fake import FakeLLM
from app.llm.groq import GroqLLM
from app.llm.models import LLMUsage


def test_authenticated_user_fk_flows_through_groq_budget_and_fake(auth_db):  # noqa: F811
    factory, passwords, admin_id, login = auth_db
    request_id = uuid4()
    local_settings = Settings(app_env="test", public_base_url="http://testserver")
    context = AuthContext(session_factory=factory, settings=local_settings, passwords=passwords)
    app = FastAPI()
    app.include_router(create_auth_router(factory, local_settings, passwords=passwords))

    identity_dependency = Depends(context.require_user)

    @app.get("/protected")
    def protected(identity=identity_dependency):
        return {"id": identity[0].id}

    client = TestClient(app)
    assert client.get("/protected").status_code == 401
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://testserver",
            "X-CSRF-Token": csrf,
        },
        json={"login": login, "password": "A-very-long synthetic password 1!"},
    )
    assert response.status_code == 200
    assert client.get("/protected").json() == {"id": admin_id}
    request = LLMRequest(
        request_id=request_id,
        purpose="intent",
        template_version="v1",
        messages=(LLMMessage(role="user", content="Synthetic clarification only."),),
        output_schema=IntentResult.model_json_schema(),
        max_output_tokens=128,
        timeout_ms=1000,
    )
    result_payload = {
        "intent": "clarify",
        "bank_codes": [],
        "metric_codes": [],
        "scenario_patch": {},
        "clarification": "Specify a synthetic scenario.",
    }
    calls = []

    def mock_handler(wire_request):
        calls.append(wire_request.url.host)
        return httpx.Response(
            200,
            json={
                "id": "synthetic-provider-response",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(result_payload),
                        },
                    }
                ],
                "usage": {"prompt_tokens": 32, "completion_tokens": 16, "total_tokens": 48},
            },
        )

    provider_settings = Settings.from_environment(
        {
            "APP_ENV": "test",
            "LLM_MODE": "provider",
            "LLM_MODEL": "openai/gpt-oss-120b",
            "LLM_API_BASE": "https://api.groq.com/openai/v1",
            "LLM_ALLOWED_HOSTS": "api.groq.com",
            "LLM_API_KEY": "synthetic-mock-key",
        }
    )
    provider = GroqLLM(
        provider_settings,
        PostgresTokenBudget(factory, daily_token_limit=10000),
        client_factory=lambda **kwargs: httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            **kwargs,
        ),
    )

    async def run():
        binding = set_budget_user(admin_id)
        try:
            async with provider.question_scope():
                result = await provider.complete(request)
            fake = await FakeLLM().complete(request)
            assert isinstance(fake, LLMResponse)
            return result
        finally:
            reset_budget_user(binding)
            await provider.aclose()

    try:
        result = asyncio.run(run())
        assert isinstance(result, LLMResponse)
        assert calls == ["api.groq.com"]  # MockTransport only; no external connection.
        with factory() as db:
            usage = db.get(LLMUsage, str(request_id))
            assert usage.user_id == admin_id and usage.state == "settled"
            assert usage.actual_tokens == 48
    finally:
        with factory.begin() as db:
            db.execute(delete(LLMUsage).where(LLMUsage.request_id == str(request_id)))
