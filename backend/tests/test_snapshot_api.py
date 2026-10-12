"""HTTP integration on migrated PostgreSQL, synthetic originals and actual services."""

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx2 as httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema
from test_assistant_answers import RoutedFake
from test_assistant_answers import question_system as question_system
from test_comparison_golden import scenario
from test_evidence_publication import approve, confirmation, setup_candidate
from test_extraction_pipeline import pipeline_db as pipeline_db

from app.api.composition import FileManifestResolver, ProcessingAdmission
from app.api.typescript import render_typescript
from app.auth.models import AuthSession, AuthUser
from app.auth.security import PasswordService
from app.config import Settings
from app.contracts.api import AnswerEnvelope, ApiError
from app.contracts.comparison import ComparisonResult
from app.corpus.service import CorpusService
from app.ingestion.gateway import FetchGateway
from app.ingestion.service import IngestionService
from app.llm.budget import PostgresTokenBudget, current_budget_user
from app.llm.groq import GroqLLM
from app.llm.models import LLMUsage
from app.main import create_app
from app.parsing.service import ExtractionPipeline
from app.registry.models import SourcePolicy
from app.storage.local import LocalBlobStore
from app.tariffs.models import FactReview, PublishedFact

ORIGIN = "http://testserver"
PASSWORD = "Synthetic-test-password-16!"


@pytest.fixture(scope="module")
def migrated_factory():
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.skip("NOT RUN: TEST_DATABASE_URL required for migrated PostgreSQL API integration")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql" or not url.database or "test" not in url.database:
        pytest.fail("Dedicated PostgreSQL test database required")
    engine = create_engine(url)
    schema = f"snap16_{uuid4().hex}"
    with engine.begin() as db:
        db.execute(CreateSchema(schema))
    scoped_url = url.update_query_dict({"options": f"-csearch_path={schema}"})
    env = dict(
        os.environ,
        DATABASE_URL=raw,
        PGOPTIONS=f"-csearch_path={schema}",
        APP_ENV="test",
        INGESTION_MODE="offline",
    )
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            pytest.fail("Real Alembic migration failed")
        scoped_engine = create_engine(scoped_url, pool_pre_ping=True)
        factory = sessionmaker(scoped_engine, expire_on_commit=False)
        with factory() as db:
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0005_auth"
        yield factory
        scoped_engine.dispose()
    finally:
        with engine.begin() as db:
            db.execute(DropSchema(schema, cascade=True))
        engine.dispose()


@pytest.fixture
def api_system(migrated_factory, tmp_path):
    factory = migrated_factory
    store = LocalBlobStore(tmp_path / "synthetic-originals")
    settings = Settings(
        app_env="test",
        storage_root=store.root,
        public_base_url=ORIGIN,
        auth_enabled=True,
        fake_identity=False,
    )
    corpus = CorpusService(
        IngestionService(factory, settings, store, FetchGateway(settings, store))
    )
    pipeline_db = factory, store, corpus, ExtractionPipeline(corpus)
    ids, manifest, candidate_id, evidence = setup_candidate(
        pipeline_db, text=f"Обслуживание счета — 100 RUB в месяц. Fixture {uuid4().hex}."
    )
    review_id = approve(pipeline_db, manifest, candidate_id, evidence)
    evidence.publish(manifest, candidate_id, review_id)
    corpus.freeze(manifest)
    manifests = {manifest.snapshot_id: manifest}
    passwords = PasswordService()
    users = {}
    with factory.begin() as db:
        for key, role in (("admin", "admin"), ("a", "analyst"), ("b", "analyst")):
            user = AuthUser(
                login=f"{key}-{uuid4().hex}@synthetic.invalid",
                password_hash=passwords.hash(PASSWORD),
                role=role,
                active=True,
            )
            db.add(user)
            db.flush()
            users[key] = user

    def resolver(snapshot_id):
        if snapshot_id not in manifests:
            raise HTTPException(404, "OBJECT_UNAVAILABLE")
        return manifests[snapshot_id]

    fake = RoutedFake()
    app = create_app(settings, session_factory=factory, resolve_manifest=resolver, llm=fake)
    clients = {key: TestClient(app) for key in users}
    for key, client in clients.items():
        login(client, users[key].login)
    yield dict(
        app=app,
        clients=clients,
        users=users,
        db=pipeline_db,
        ids=ids,
        manifest=manifest,
        candidate_id=candidate_id,
        manifests=manifests,
        fake=fake,
    )
    for client in clients.values():
        client.close()


def login(client, name, password=PASSWORD):
    challenge = client.get("/api/v1/auth/csrf")
    assert challenge.status_code == 200
    response = client.post(
        "/api/v1/auth/login",
        json={"login": name, "password": password},
        headers={"Origin": ORIGIN, "X-CSRF-Token": challenge.json()["csrf_token"]},
    )
    assert response.status_code == 200, response.text
    return response


def headers(client):
    return {"Origin": ORIGIN, "X-CSRF-Token": client.cookies["bsi-csrf"]}


def error(response, status):
    assert response.status_code == status, response.text
    parsed = ApiError.model_validate(response.json())
    assert str(parsed.error.request_id) == response.headers["x-request-id"]
    assert "no-store" in response.headers["cache-control"]
    return parsed.error.code


def test_health_and_missing_session():
    app = create_app(Settings(app_env="test"))
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        # The unconfigured database fails closed; liveness stays independent.
        assert error(client.get("/api/v1/auth/me"), 401) == "AUTH_REQUIRED"


def test_auth_invite_logout_expiry_and_cookie_security(api_system):
    system = api_system
    admin = system["clients"]["admin"]
    analyst = system["clients"]["a"]
    error(
        analyst.post(
            "/api/v1/admin/invitations",
            headers=headers(analyst),
            json={"login": "new@synthetic.invalid"},
        ),
        403,
    )
    name = f"invited-{uuid4().hex}@synthetic.invalid"
    invitation = admin.post(
        "/api/v1/admin/invitations", headers=headers(admin), json={"login": name}
    )
    assert invitation.status_code == 201
    with TestClient(system["app"]) as client:
        error(client.get("/api/v1/snapshots"), 401)
        challenge = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        response = client.post(
            "/api/v1/auth/accept-invite",
            json={
                "token": invitation.json()["token"],
                "password": PASSWORD,
            },
            headers={"Origin": ORIGIN, "X-CSRF-Token": challenge},
        )
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Secure" not in cookie
        assert client.get("/api/v1/auth/me").json()["login"] == name
        error(client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN}), 403)
        assert client.post("/api/v1/auth/logout", headers=headers(client)).status_code == 200
        error(client.get("/api/v1/auth/me"), 401)
        error(
            client.post(
                "/api/v1/auth/accept-invite",
                json={
                    "token": invitation.json()["token"],
                    "password": PASSWORD,
                },
                headers={"Origin": ORIGIN, "X-CSRF-Token": challenge},
            ),
            400,
        )
    with system["db"][0].begin() as db:
        row = db.scalar(select(AuthSession).where(AuthSession.user_id == system["users"]["a"].id))
        row.last_seen_at = datetime.now(UTC) - timedelta(hours=9)
    error(analyst.get("/api/v1/auth/me"), 401)


def test_origin_csrf_and_payload_redaction(api_system):
    client = api_system["clients"]["a"]
    body = {"snapshot_id": str(api_system["manifest"].snapshot_id), "question": "Сколько стоит?"}
    error(client.post("/api/v1/assistant/questions", json=body), 403)
    error(
        client.post(
            "/api/v1/assistant/questions",
            json=body,
            headers={**headers(client), "Origin": "https://attacker.invalid"},
        ),
        403,
    )
    error(
        client.post(
            "/api/v1/assistant/questions",
            json=body,
            headers={**headers(client), "X-CSRF-Token": "incorrect"},
        ),
        403,
    )
    response = client.post("/api/v1/auth/login", json={"login": "x", "password": "SECRET_CANARY"})
    error(response, 422)
    assert "SECRET_CANARY" not in response.text


def test_snapshot_search_document_and_hash(api_system):
    client = api_system["clients"]["a"]
    snapshot_id = str(api_system["manifest"].snapshot_id)
    page = client.get("/api/v1/snapshots").json()
    assert any(
        row["id"] == snapshot_id and row["corpus_kind"] == "synthetic" for row in page["items"]
    )
    view = client.get(f"/api/v1/snapshots/{snapshot_id}")
    assert view.status_code == 200 and view.json()["document_count"] == 1
    assert "policy_id" not in view.text and "storage_key" not in view.text
    search = client.get("/api/v1/search", params={"snapshot_id": snapshot_id, "query": "100"})
    assert search.status_code == 200 and search.json()["hits"]
    hit = search.json()["hits"][0]
    assert hit["raw_sha256"] == api_system["manifest"].documents[0].sha256
    filtered = client.get(
        "/api/v1/search", params={"snapshot_id": snapshot_id, "query": "100", "bank_codes": "vtb"}
    ).json()
    assert filtered["absence_of_evidence"] and filtered["hits"] == []
    missing = client.get("/api/v1/search", params={"snapshot_id": snapshot_id, "query": "zzznone"})
    assert missing.status_code == 200 and missing.json()["absence_of_evidence"]
    version_id = api_system["ids"]["version"]
    metadata = client.get(f"/api/v1/documents/{version_id}")
    assert metadata.status_code == 200 and "storage_key" not in metadata.text
    downloaded = client.get(metadata.json()["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.headers["content-disposition"].startswith("attachment;")
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert hashlib.sha256(downloaded.content).hexdigest() == metadata.json()["raw_sha256"]
    error(client.get(f"/api/v1/documents/{uuid4()}"), 404)
    error(client.get(f"/api/v1/snapshots/{uuid4()}"), 404)


def test_comparison_and_assistant_actual_envelopes(api_system):
    client = api_system["clients"]["a"]
    snapshot_id = str(api_system["manifest"].snapshot_id)
    comparison = client.post(
        "/api/v1/comparisons",
        headers=headers(client),
        json={
            "snapshot_id": snapshot_id,
            "bank_codes": ["sber", "vtb"],
            "metric_codes": ["account_monthly_fee"],
            "scenario": {
                "payer": "employer",
                "operation": "account_servicing",
                "currency": "RUB",
                "as_of": "2026-10-12",
            },
        },
    )
    assert comparison.status_code == 200, comparison.text
    parsed = ComparisonResult.model_validate(comparison.json())
    assert parsed.rows[0].cells[1].status == "unknown"
    request = {"snapshot_id": snapshot_id, "question": "Сколько стоит обслуживание счета Сбера?"}
    answer = client.post("/api/v1/assistant/questions", json=request, headers=headers(client))
    assert answer.status_code == 200, answer.text
    parsed_answer = AnswerEnvelope.model_validate(answer.json())
    assert parsed_answer.sources and parsed_answer.claims
    assert "100" in parsed_answer.text
    assert "storage_key" not in answer.text
    clarification = client.post(
        "/api/v1/assistant/questions",
        headers=headers(client),
        json={
            **request,
            "question": "Какой банк лучше?",
        },
    )
    assert clarification.status_code == 200 and clarification.json()["status"] == "clarification"
    insufficient = client.post(
        "/api/v1/assistant/questions",
        headers=headers(client),
        json={
            **request,
            "question": "Сколько стоит обслуживание счета ВТБ?",
            "bank_codes": ["vtb"],
        },
    )
    assert insufficient.status_code == 200 and insufficient.json()["status"] == "insufficient"
    api_system["fake"].failure = "unavailable"
    fallback = client.post("/api/v1/assistant/questions", headers=headers(client), json=request)
    assert fallback.status_code == 200 and fallback.json()["status"] == "fallback"
    assert fallback.json()["sources"] and "100" in fallback.json()["text"]


def test_revoked_permission_and_corrupt_original_block_read(api_system):
    client = api_system["clients"]["a"]
    version_id = api_system["ids"]["version"]
    with api_system["db"][0].begin() as db:
        db.get(SourcePolicy, api_system["ids"]["policy"]).collection_decision = "denied"
    error(client.get(f"/api/v1/documents/{version_id}/original"), 404)
    error(client.get(f"/api/v1/snapshots/{api_system['manifest'].snapshot_id}"), 404)
    listed = client.get("/api/v1/snapshots")
    assert listed.status_code == 200 and listed.json()["items"] == []
    with api_system["db"][0].begin() as db:
        db.get(SourcePolicy, api_system["ids"]["policy"]).collection_decision = "approved"
    path = api_system["db"][2].read_member(api_system["manifest"].snapshot_id, UUID(version_id))
    path.write_bytes(b"corrupt synthetic original")
    error(client.get(f"/api/v1/documents/{version_id}/original"), 503)


def test_admin_review_publication_freeze_and_conflicts(api_system):
    db = api_system["db"]
    _, manifest, candidate_id, evidence = setup_candidate(
        db, text=f"Обслуживание счета — 200 RUB в месяц. Fixture {uuid4().hex}."
    )
    api_system["manifests"][manifest.snapshot_id] = manifest
    client = api_system["clients"]["admin"]
    analyst = api_system["clients"]["a"]
    path = f"/api/v1/admin/candidates/{candidate_id}/reviews"
    body = {"snapshot_id": str(manifest.snapshot_id), "decision": "approved", "reason": "Checked"}
    error(analyst.post(path, json=body, headers=headers(analyst)), 403)
    error(
        analyst.get("/api/v1/admin/candidates", params={"snapshot_id": str(manifest.snapshot_id)}),
        403,
    )
    pending = client.get(
        "/api/v1/admin/candidates", params={"snapshot_id": str(manifest.snapshot_id)}
    )
    assert pending.status_code == 200 and pending.json()["items"][0]["decision"] == "pending_review"
    error(client.post(path, json=body, headers=headers(client)), 409)
    fields = confirmation(db, manifest, candidate_id, evidence).field_evidence
    response = client.post(path, json={**body, "field_evidence": fields}, headers=headers(client))
    assert response.status_code == 200 and response.json()["published"]
    with db[0]() as session:
        row = session.get(FactReview, response.json()["review_id"])
        assert row.user_id == api_system["users"]["admin"].id
        assert row.reviewer_label == api_system["users"]["admin"].login
        assert session.get(PublishedFact, response.json()["fact_id"]) is not None
    freeze_path = f"/api/v1/admin/snapshots/{manifest.snapshot_id}/freeze"
    frozen = client.post(freeze_path, headers=headers(client))
    assert frozen.status_code == 200 and frozen.json()["state"] == "frozen"
    error(client.post(freeze_path, headers=headers(client)), 409)
    error(
        client.post(path, json={**body, "reviewer_label": "forged"}, headers=headers(client)), 422
    )
    assert analyst.get(f"/api/v1/snapshots/{manifest.snapshot_id}").status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/snapshots/not-uuid",
        "/api/v1/documents/not-uuid/original",
        "/api/v1/documents/%2e%2e%2fsecret/original",
    ],
)
def test_invalid_ids_and_traversal(api_system, path):
    response = api_system["clients"]["a"].get(path)
    assert response.status_code in (404, 422)
    ApiError.model_validate(response.json())
    assert "secret" not in response.text


@pytest.mark.parametrize(
    "extra",
    [
        {"limit": 11},
        {"limit": 0},
        {"query": "x" * 1001},
        {"query": "   "},
        {"snapshot_id": "bad"},
        {"bank_codes": ["sber", "sber"]},
    ],
)
def test_query_bounds(api_system, extra):
    params = {"snapshot_id": str(api_system["manifest"].snapshot_id), "query": "100", **extra}
    response = api_system["clients"]["a"].get("/api/v1/search", params=params)
    error(response, 400 if extra.get("query") == "   " else 422)


def test_injection_payload_bounds_and_rate_limits(api_system):
    client = api_system["clients"]["a"]
    snapshot_id = str(api_system["manifest"].snapshot_id)
    assert (
        client.get(
            "/api/v1/search",
            params={"snapshot_id": snapshot_id, "query": "100'); DROP TABLE users; --"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me").status_code == 200
    error(
        client.post(
            "/api/v1/assistant/questions",
            headers=headers(client),
            json={
                "snapshot_id": snapshot_id,
                "question": "x" * 2001,
            },
        ),
        422,
    )
    oversized = client.post(
        "/api/v1/assistant/questions", headers=headers(client), content=b"x" * 65537
    )
    assert oversized.status_code == 422 and "PAYLOAD_TOO_LARGE" in oversized.text
    api_system["app"].state.runtime.question_limiter.account_limit = 1
    body = {"snapshot_id": snapshot_id, "question": "Какой банк лучше?"}
    assert (
        client.post("/api/v1/assistant/questions", json=body, headers=headers(client)).status_code
        == 200
    )
    limited = client.post("/api/v1/assistant/questions", json=body, headers=headers(client))
    error(limited, 429)
    assert limited.headers["retry-after"] == "60"
    # A's authenticated quota never becomes B's quota.
    other = api_system["clients"]["b"]
    assert (
        other.post("/api/v1/assistant/questions", json=body, headers=headers(other)).status_code
        == 200
    )


def test_parallel_user_budget_context_isolated(api_system):
    seen = []

    class CapturingFake(RoutedFake):
        async def complete(self, request):
            before = current_budget_user()
            seen.append(before)
            await asyncio.sleep(0.02)
            assert current_budget_user() == before
            return await super().complete(request)

    api_system["app"].state.runtime.llm = CapturingFake()
    body = {
        "snapshot_id": str(api_system["manifest"].snapshot_id),
        "question": "Сколько стоит обслуживание счета Сбера?",
    }

    def ask(key):
        client = api_system["clients"][key]
        assert client.get("/api/v1/auth/me").json()["id"] == api_system["users"][key].id
        response = client.post("/api/v1/assistant/questions", json=body, headers=headers(client))
        assert response.status_code == 200, response.text

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(ask, ["a", "b"]))
    assert set(seen) == {api_system["users"][key].id for key in ("a", "b")}
    assert current_budget_user() is None


def test_database_unavailable_safe_503_and_liveness(tmp_path):
    settings = Settings(
        app_env="test",
        storage_root=tmp_path,
        public_base_url=ORIGIN,
        database_url="postgresql+psycopg://bsi:CANARY@127.0.0.1:1/bsi_test",
    )
    with TestClient(create_app(settings)) as client:
        client.cookies.set("bsi-session", "x" * 43)
        response = client.get("/api/v1/auth/me")
        assert error(response, 503) == "DATABASE_UNAVAILABLE"
        assert "CANARY" not in response.text and "127.0.0.1" not in response.text
        assert client.get("/health").status_code == 200


def test_file_manifest_resolution_and_openapi(api_system, tmp_path):
    manifest = api_system["manifest"]
    root = tmp_path / "manifests"
    root.mkdir()
    (root / f"{manifest.snapshot_id}.json").write_bytes(manifest.canonical_json())
    resolved = FileManifestResolver(root)(manifest.snapshot_id)
    assert resolved.manifest_sha256 == manifest.manifest_sha256
    schema = api_system["app"].openapi()
    assert schema["paths"]["/api/v1/assistant/questions"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("AnswerEnvelope")
    for path, routes in schema["paths"].items():
        if path.startswith("/api/v1"):
            for route in routes.values():
                assert route["responses"]["422"]["content"]["application/json"]["schema"][
                    "$ref"
                ].endswith("ApiError")
    assert "ProcessingAdmission" not in schema["components"]["schemas"]
    assert ProcessingAdmission.model_fields["provider"].annotation is str


def test_login_limit_has_retry_after(api_system):
    with TestClient(api_system["app"]) as client:
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        for _ in range(5):
            error(
                client.post(
                    "/api/v1/auth/login",
                    json={"login": "unknown@synthetic.invalid", "password": "incorrect"},
                    headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
                ),
                401,
            )
        response = client.post(
            "/api/v1/auth/login",
            json={"login": "unknown@synthetic.invalid", "password": "incorrect"},
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        error(response, 429)
        assert response.headers["retry-after"] == "60"


def test_typescript_exact_openapi_and_decimal_strings():
    app = create_app(Settings(app_env="test"))
    path = Path(__file__).resolve().parents[2] / "frontend/lib/api-contracts.ts"
    assert path.read_text(encoding="utf-8") == render_typescript(app.openapi())
    amount_schema = app.openapi()["components"]["schemas"]["Scenario-Input"]["properties"][
        "payroll_total"
    ]
    assert {item["type"] for item in amount_schema["anyOf"]} == {"string", "null"}


def test_production_session_cookies(api_system):
    settings = Settings(
        app_env="production",
        storage_root=api_system["db"][1].root,
        database_url="postgresql+psycopg://unused:unused@127.0.0.1/bsi_test",
        public_base_url="https://testserver",
        session_secret="synthetic-session-secret-32-characters",
        auth_enabled=True,
        fake_identity=False,
        secure_cookies=True,
    )
    app = create_app(settings, session_factory=api_system["db"][0])
    with TestClient(app, base_url="https://testserver") as client:
        challenge = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        response = client.post(
            "/api/v1/auth/login",
            json={
                "login": api_system["users"]["a"].login,
                "password": PASSWORD,
            },
            headers={"Origin": "https://testserver", "X-CSRF-Token": challenge},
        )
        assert response.status_code == 200
        cookies = response.headers["set-cookie"]
        assert "__Host-session=" in cookies and "Secure" in cookies and "HttpOnly" in cookies
        assert "SameSite=lax" in cookies and "Domain=" not in cookies
        assert client.get("/api/v1/auth/me").status_code == 200


def test_provider_admission_budget_user_and_safe_fallback(api_system, tmp_path):
    # Only MockTransport is constructed. No real provider call can occur.
    calls = []

    def handler(request):
        calls.append(current_budget_user())
        assert "synthetic.invalid" not in request.content.decode()
        return httpx.Response(503, json={"error": "RAW_PROVIDER_ERROR_CANARY"})

    settings = Settings(
        app_env="test",
        storage_root=api_system["db"][1].root,
        llm_mode="provider",
        llm_api_key="synthetic-key",
        llm_api_base="https://api.groq.com/openai/v1",
        llm_model="openai/gpt-oss-120b",
        llm_allowed_hosts=("api.groq.com",),
        llm_max_attempts=1,
    )
    runtime = api_system["app"].state.runtime
    provider = GroqLLM(
        settings,
        PostgresTokenBudget(api_system["db"][0], daily_token_limit=100000),
        client_factory=lambda **kw: httpx.AsyncClient(**kw, transport=httpx.MockTransport(handler)),
    )
    runtime.llm = provider
    runtime.admission_root = tmp_path / "admissions"
    runtime.admission_root.mkdir()
    client = api_system["clients"]["a"]
    manifest = api_system["manifest"]
    body = {
        "snapshot_id": str(manifest.snapshot_id),
        "question": "Сколько стоит обслуживание счета Сбера?",
    }
    error(client.post("/api/v1/assistant/questions", json=body, headers=headers(client)), 403)
    assert calls == []
    path = runtime.admission_root / f"{manifest.snapshot_id}.json"
    decision = dict(
        snapshot_id=str(manifest.snapshot_id),
        manifest_sha256=manifest.manifest_sha256,
        provider="groq",
        model="openai/gpt-oss-120b",
        decision="approved",
        reviewer="Explicit synthetic test reviewer",
        basis_reference="test-only synthetic decision",
        terms_processing_retention_reference="test-only mock transport",
        corpus_reuse_reference="synthetic",
        expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    )
    path.write_text(json.dumps(decision), encoding="utf-8")
    response = client.post("/api/v1/assistant/questions", json=body, headers=headers(client))
    assert response.status_code == 200 and response.json()["status"] == "fallback"
    assert response.json()["sources"] and "RAW_PROVIDER_ERROR_CANARY" not in response.text
    assert calls and set(calls) == {api_system["users"]["a"].id}
    with api_system["db"][0]() as db:
        rows = db.scalars(
            select(LLMUsage).where(LLMUsage.user_id == api_system["users"]["a"].id)
        ).all()
        assert rows and all(row.state != "reserved" for row in rows)
    path.write_text(json.dumps({**decision, "manifest_sha256": "0" * 64}), encoding="utf-8")
    count = len(calls)
    error(client.post("/api/v1/assistant/questions", json=body, headers=headers(client)), 403)
    assert len(calls) == count
    asyncio.run(provider.aclose())


def test_question_deadline_is_safe_503(api_system):
    runtime = api_system["app"].state.runtime
    runtime.settings = runtime.settings.model_copy(update={"llm_total_timeout_seconds": 0.001})
    client = api_system["clients"]["a"]
    response = client.post(
        "/api/v1/assistant/questions",
        json={
            "snapshot_id": str(api_system["manifest"].snapshot_id),
            "question": "Сколько стоит обслуживание счета Сбера?",
        },
        headers=headers(client),
    )
    assert error(response, 503) == "REQUEST_TIMEOUT"


def test_decimal_wire_rejects_binary_numbers(api_system):
    client = api_system["clients"]["a"]
    body = {
        "snapshot_id": str(api_system["manifest"].snapshot_id),
        "bank_codes": ["sber", "vtb"],
        "metric_codes": ["account_monthly_fee"],
        "scenario": {
            "payer": "employer",
            "operation": "account_servicing",
            "currency": "RUB",
            "as_of": "2026-10-12",
            "payroll_total": "5000000.01",
        },
    }
    response = client.post("/api/v1/comparisons", json=body, headers=headers(client))
    assert response.status_code == 200
    assert response.json()["scenario_echo"]["payroll_total"] == "5000000.01"
    for amount in (5000000, 5000000.01):
        body["scenario"]["payroll_total"] = amount
        error(client.post("/api/v1/comparisons", json=body, headers=headers(client)), 422)


@pytest.mark.parametrize("question_system", [True], indirect=True)
def test_verified_api_comparison_and_assistant_sources(question_system, pipeline_db):
    _, fake, ids, manifest, _ = question_system
    factory = pipeline_db[0]
    with factory.begin() as db:
        user = AuthUser(
            login=f"verified-{uuid4().hex}@synthetic.invalid",
            password_hash=PasswordService().hash(PASSWORD),
            role="analyst",
            active=True,
        )
        db.add(user)
    settings = Settings(app_env="test", storage_root=pipeline_db[1].root, public_base_url=ORIGIN)
    app = create_app(
        settings, session_factory=factory, resolve_manifest=lambda _: manifest, llm=fake
    )
    with TestClient(app) as client:
        login(client, user.login)
        request = {
            "snapshot_id": str(manifest.snapshot_id),
            "bank_codes": ["sber", "vtb"],
            "metric_codes": ["account_monthly_fee"],
            "scenario": scenario(operation="account_maintenance", period="месяц").model_dump(
                mode="json"
            ),
        }
        comparison = client.post("/api/v1/comparisons", json=request, headers=headers(client))
        assert comparison.status_code == 200, comparison.text
        cells = comparison.json()["rows"][0]["cells"]
        assert cells[0]["status"] == "verified" and cells[0]["value"]["amount"] == "100"
        assert cells[1]["status"] == "unknown" and cells[1]["value"] is None
        question = {**request, "question": "Сравни Сбер и ВТБ по комиссиям"}
        response = client.post(
            "/api/v1/assistant/questions", json=question, headers=headers(client)
        )
        assert response.status_code == 200 and response.json()["status"] == "partial"
        answer = AnswerEnvelope.model_validate(response.json())
        assert answer.comparison.rows[0].cells[0].value.amount == 100
        assert answer.sources and all(
            source.evidence.source_version_id == UUID(ids["version"]) for source in answer.sources
        )
        for source in answer.sources:
            downloaded = client.get(source.download_url)
            assert downloaded.status_code == 200
            assert hashlib.sha256(downloaded.content).hexdigest() == source.evidence.raw_sha256


def test_expired_session_is_rechecked_during_question(api_system):
    runtime = api_system["app"].state.runtime
    user_id = api_system["users"]["a"].id

    def revoke(_request):
        with runtime.factory.begin() as db:
            user = db.get(AuthUser, user_id)
            user.active = False

    api_system["fake"].hook = revoke
    client = api_system["clients"]["a"]
    response = client.post(
        "/api/v1/assistant/questions",
        json={
            "snapshot_id": str(api_system["manifest"].snapshot_id),
            "question": "Сколько стоит обслуживание счета Сбера?",
        },
        headers=headers(client),
    )
    error(response, 401)
    assert "100 RUB" not in response.text
    other = api_system["clients"]["b"]
    assert other.get("/api/v1/auth/me").status_code == 200


def test_unexpected_exception_is_sanitized():
    app = create_app(Settings(app_env="test"))

    def fail():
        raise RuntimeError("STACK_SQL_PASSWORD_CANARY")

    app.add_api_route("/test-only-failure", fail)
    with TestClient(app) as client:
        response = client.get("/test-only-failure")
        assert error(response, 500) == "INTERNAL_ERROR"
        assert "STACK_SQL_PASSWORD_CANARY" not in response.text
