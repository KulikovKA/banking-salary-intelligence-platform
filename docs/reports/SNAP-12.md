# SNAP-12 — LLM Protocol and deterministic Fake

- Status: implementation complete; release/product gates are not evaluated here.
- Base: `ea6ae1a2f2f174981d8706b88a6192361d56df8b` (`main`).
- Branch/worktree: `codex/snap-12-llm`, `C:\Users\Kirill\Desktop\sber ai assisnent-snap-12-llm`.
- Provider: no Groq adapter, credentials, or external requests.

## Result

Implemented a deterministic async `FakeLLM` satisfying the frozen SNAP-01 `LLMClient` Protocol. It returns the existing typed `LLMResponse` / `LLMError`, estimated usage metadata, and supports explicit fixture outcomes for timeout, rate limit, auth, unavailable, invalid output, context exceeded, and budget exceeded. Default intent is clarification; default explain output orders no claims. Explain output is restricted to backend supplied claim IDs and fixed renderer template IDs. Intent/explain responses pass the frozen Pydantic DTOs and the request's JSON schema shape checks. Malformed JSON and invalid/unknown outputs become typed `invalid_output` errors.

The Fake has no network, DB, storage, or tools. It does not generate tariff facts, URLs, or evidence and does not approve claims. Backend must provide claim IDs/templates and remains responsible for claim verification and final rendering.

## Changed files

- `backend/app/llm/base.py`
- `backend/app/llm/fake.py`
- `backend/tests/test_llm_contract.py`
- `docs/reports/SNAP-12.md`

No frozen contract, `backend/app/llm/models.py`, config, plan, or task registry changed.

## Acceptance evidence

- Same Protocol / concrete Fake typecheck: `python -m mypy backend/app` — PASS (exit 0).
- Scoped lint: `python -m ruff check backend/app/llm backend/tests/test_llm_contract.py` — PASS.
- Contract/security tests: `python -m pytest backend/tests/test_llm_contract.py -q` — PASS, 7 passed. Covers repeatability, intent DTO validation, injection-safe clarification, explain allowlists, unknown claim, unsupported template, timeout, rate_limit, auth, unavailable, context_exceeded, malformed JSON, and invalid schema output.
- `python tools/validate_docs.py` — PASS.
- `git diff --check` — PASS.
- Full `python -m ruff check .` — FAIL on 4 existing findings outside SNAP-12: UP038 at `backend/app/contracts/base.py:30`, UP038 at `backend/app/ingestion/gateway.py:137,141`, and I001 at `backend/tests/test_ingestion_postgres.py:3`.
- Full `python -m pytest backend/tests -q` — NOT RUN to completion: collection failed on unavailable environment dependencies `httpx2`, `truststore`, and `protego` (5 collection errors). No dependency installation or network use was attempted.
- PostgreSQL integration — NOT RUN; no dedicated test DB configured and relevant third-party imports are unavailable.
- Frontend checks — NOT RUN; no frontend files changed.

## Limitations / next step

The Fake supplies deterministic renderer-input behavior and provider error fixtures; a user-facing fallback envelope remains the responsibility of the later assistant/backend integration. No Groq implementation or live-provider quality claim is included. Create/merge PR after branch push and review. Commit: `e7e2acc378365f6b937aeb7f76da59c3bb5e6a22`.

