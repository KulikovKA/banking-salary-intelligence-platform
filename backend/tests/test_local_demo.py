"""Offline tests for the separate local entrypoint and public-only provider payload."""

import asyncio
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import httpx2 as httpx
import pytest
from fastapi import HTTPException

from app.local_demo import (
    DemoService,
    Question,
    Snippet,
    create_app,
    load_documents,
    load_inventory,
    public_query,
    retrieve,
    section_role,
)


def snippet(bank: str = "vtb") -> Snippet:
    return Snippet(
        "Sabcdef",
        bank,
        "original.pdf",
        "https://example.test/doc",
        "a" * 64,
        "страница 1",
        "Подключение зарплатного проекта. Комиссия определяется договором.",
    )


def test_entrypoint_requires_opt_in_and_rejects_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVE_DEMO_ENABLED", raising=False)
    with pytest.raises(RuntimeError, match="OPT_IN"):
        create_app()
    monkeypatch.setenv("LIVE_DEMO_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="OPT_IN"):
        create_app()


def test_public_topic_omits_private_input_and_bank_filter_has_no_fallback() -> None:
    query, banks = public_query("ВТБ подключение для Иванова, счёт 12345678901234567890 SECRET")
    assert "Иванов" not in query and "123456" not in query and "SECRET" not in query
    assert banks == {"vtb"}
    assert retrieve([snippet()], query, {"sber"}) == []


def test_no_consent_no_call_and_invalid_citation_rejected() -> None:
    async def run() -> None:
        service = DemoService("secret-canary", [snippet()])
        calls = []

        async def respond(request: httpx.Request) -> httpx.Response:
            calls.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "answer": "Тариф 0 [Sabcdef]",
                                        "source_ids": ["Sunknown"],
                                    }
                                )
                            }
                        }
                    ]
                },
            )

        await service.client.aclose()
        service.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            with pytest.raises(HTTPException) as rejected:
                await service.answer(Question(question="ВТБ"))
            assert rejected.value.status_code == 403 and not calls
            with pytest.raises(HTTPException) as invalid:
                await service.answer(Question(question="ВТБ SECRET", allow_public_text=True))
            assert invalid.value.detail == "GROQ_CITATION_INVALID_NO_RETRY"
            assert len(calls) == 1
            assert "SECRET" not in json.dumps(calls)
        finally:
            await service.client.aclose()

    asyncio.run(run())


def test_provider_error_is_not_fake_success_or_retry() -> None:
    async def run() -> None:
        service = DemoService("secret-canary", [snippet()])
        await service.client.aclose()
        service.client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(401, json={"error": "secret-canary"})
            )
        )
        try:
            with pytest.raises(HTTPException) as error:
                await service.answer(Question(question="ВТБ", allow_public_text=True))
            assert error.value.detail == "GROQ_HTTP_401_NO_RETRY"
            assert service.calls == 1
        finally:
            await service.client.aclose()

    asyncio.run(run())


def test_modified_original_is_rejected_before_parsing(tmp_path: Path) -> None:
    original = tmp_path / "original.pdf"
    original.write_bytes(b"changed bytes")
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps(
            [
                {
                    "path": str(original),
                    "sha256": "a" * 64,
                    "bank_code": "vtb",
                    "kind": "pdf",
                    "original_url": "https://example.test/doc",
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="HASH_MISMATCH"):
        load_inventory(inventory)


def test_loopback_token_host_and_exact_fragment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVE_DEMO_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "poc")
    monkeypatch.setenv("LLM_API_KEY", "test-only-key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("LIVE_DEMO_TOKEN", "t" * 32)
    monkeypatch.setenv("LIVE_DEMO_INVENTORY", "unused-in-test")
    monkeypatch.delenv("LIVE_DEMO_DOCUMENTS", raising=False)
    monkeypatch.setattr("app.local_demo.load_inventory", lambda _: [snippet()])

    async def run() -> None:
        app = create_app()
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1234)),
                base_url="http://127.0.0.1:8010",
            ) as client:
                assert (await client.get("/local-demo/status")).status_code == 403
                client.headers["X-Live-Demo-Token"] = "t" * 32
                assert (await client.get("/local-demo/status")).status_code == 200
                assert (
                    await client.get("/local-demo/status", headers={"Host": "evil.test"})
                ).status_code == 403
                result = await client.get("/local-demo/fragment?id=Sabcdef")
                assert snippet().text in result.text
                assert "text/plain" in result.headers["content-type"]
                assert (await client.get("/local-demo/fragment?id=../../.env")).status_code == 404
                rejected = await client.post("/local-demo/questions", json={"question": "ВТБ"})
                assert rejected.status_code == 403
                assert app.state.demo.calls == 0
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, client=("192.0.2.1", 1234)),
                base_url="http://127.0.0.1:8010",
                headers={"X-Live-Demo-Token": "t" * 32},
            ) as remote:
                assert (await remote.get("/local-demo/status")).status_code == 403

    asyncio.run(run())


def test_knowledge_documents_preserve_provenance_and_reject_tampering(tmp_path: Path) -> None:
    text = "# Наш документ\n\n## Условия\nИндивидуальная комиссия; точная ставка неизвестна."
    path = tmp_path / "alfa.md"
    path.write_bytes(text.encode("utf-8"))
    manifest = {
        "files": [
            {
                "relative_path": "alfa.md",
                "kind": "md",
                "bank_code": "alfa",
                "provenance_type": "analytical_compilation",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        ]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    loaded = load_documents(tmp_path)
    assert loaded and all(s.bank == "alfa" for s in loaded)
    assert all(s.source_type == "research_summary" and s.document_text == text for s in loaded)
    assert all(s.text in text and s.url.startswith("/api/local-demo/document?id=") for s in loaded)
    path.write_text("changed", encoding="utf-8")
    with pytest.raises(RuntimeError, match="DOCUMENT_HASH_MISMATCH"):
        load_documents(tmp_path)


def comparison_corpus() -> list[Snippet]:
    items = []
    for index, bank in enumerate(("alfa", "kuban_credit", "sber", "vtb")):
        for role, text in (
            ("metadata", "Зарплатный проект банка. Аналитический документ, дата исследования."),
            ("fee", "Комиссия работодателя за зачисление определяется договором."),
            ("conditions", "Дополнительная плата за выплаты нерезидентам неизвестна."),
            ("limitations", "Ежемесячное обслуживание и полная стоимость UNKNOWN."),
        ):
            items.append(
                replace(
                    snippet(bank),
                    id=f"S{index}{role}",
                    text=text,
                    source_type="research_summary",
                    section_role=role,
                )
            )
    return items


def test_four_bank_comparison_selects_fees_and_conditions_instead_of_document_titles() -> None:
    query, banks = public_query(
        "сравни альфа банк,сбер ,втб и кубань кредит и скажи у кого выгоднее зарплатный проект"
    )
    assert banks == {"alfa", "sber", "vtb", "kuban_credit"}
    selected = retrieve(comparison_corpus(), query, banks)
    assert len(selected) == 12 and sum(len(s.text) for s in selected) <= 6000
    for bank in banks:
        assert {s.section_role for s in selected if s.bank == bank} == {
            "fee",
            "conditions",
            "limitations",
        }
    assert section_role("Сбербанк", introduction=True) == "metadata"
    assert section_role("Комиссия работодателя за зачисление") == "fee"
    assert "сопоставить" in public_query("Какой банк выгоднее?")[0]


@pytest.mark.parametrize("invalid", [None, "missing_bank", "wrong_bank", "unknown_id"])
@pytest.mark.parametrize("question", [
    "Сравни Сбер, ВТБ, Альфа и Кубань Кредит",
    "Сравнить зарплатные проекты банков",
])
def test_comparison_provider_receives_business_sections_and_must_cover_every_bank(
    invalid: str | None, question: str,
) -> None:
    async def run() -> None:
        service = DemoService("test-key", comparison_corpus())
        calls = []

        def respond(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            prompt = json.loads(body["messages"][1]["content"])
            calls.append(prompt)
            assert prompt["task"] == "compare_banks"
            assert len(prompt["snippets"]) == 12
            assert all("Аналитический документ" not in s["text"] for s in prompt["snippets"])
            schema = body["response_format"]["json_schema"]["schema"]["properties"]["source_ids"]
            assert set(schema["required"]) == {"sber", "alfa", "vtb", "kuban_credit"}
            ids = {
                bank: [definition["items"]["enum"][0]]
                for bank, definition in schema["properties"].items()
            }
            if invalid == "missing_bank":
                del ids["sber"]
            elif invalid == "wrong_bank":
                ids["sber"] = ids["alfa"]
            elif invalid == "unknown_id":
                ids["sber"] = ["Snot-in-context"]
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "answer": "Условия и комиссии зависят от договора.",
                                        "source_ids": ids,
                                    }
                                )
                            }
                        }
                    ]
                },
            )

        await service.client.aclose()
        service.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            request = Question(
                question=question, allow_public_text=True
            )
            if invalid:
                with pytest.raises(HTTPException, match="GROQ_OUTPUT_OR_CITATION_INVALID"):
                    await service.answer(request)
            else:
                result = await service.answer(request)
                assert len(result["citations"]) == 4
                assert result["missing_banks"] == []
            assert len(calls) == 1
        finally:
            await service.client.aclose()

    asyncio.run(run())
