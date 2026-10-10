# SNAP-13 — Groq adapter and token reservations

Date: 2026-10-10

Base: `504c71f` (`main`; SNAP-02 and SNAP-12 are merged)

Branch: `codex/snap-13-groq`

Implementation commit: `25c224870c5d7af31a0ab7811f547306fc31db15`

Pull request: [#6](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/6)

## Result

Implemented an asynchronous Groq Chat Completions adapter for the frozen LLM Protocol,
using `openai/gpt-oss-120b` at `https://api.groq.com/openai/v1`. Fake remains the default
and the adapter accepts no tools or streaming. Provider output is strict JSON Schema,
then passes the existing local DTO, schema, and renderer-boundary validation. The adapter
returns only frozen typed `LLMError` values on provider failures; the caller can use its
deterministic/Fake fallback path without presenting a failed request as a Groq success.

Provider HTTP requests have a 20-second maximum each and a 45-second question scope.
An explicit `GroqLLM.question_scope()` accounts for a maximum of two HTTP dispatches and
shared 4,000 input / 1,000 output token ceilings across intent and explain calls. The
scope does not alter the frozen request/response contracts. Each process should wrap a
complete question in this scope when SNAP-14 wires the adapter into the assistant.
Transient retry is at most once and must fit within the shared deadline and call cap.

`PostgresTokenBudget` reserves tokens transactionally against the existing
`llm_usage` table. Advisory locks serialize global and per-user admission. The daily
window rolls at midnight Europe/Moscow. Local daily/concurrency settings are configurable
safety ceilings, not a statement of Groq entitlement. Dispatched calls with unknown usage
retain their conservative reservation; known, not-dispatched failures release it. Stale
reservations stop occupying concurrency after two minutes, while their token estimate
continues to count for that day.

## Provider documentation checked

Official Groq documentation was checked on 2026-10-10:

- The [GPT-OSS 120B model page](https://console.groq.com/docs/model/openai/gpt-oss-120b)
  lists `openai/gpt-oss-120b`, a 131,072-token context window, and 65,536 maximum output.
  The application intentionally applies lower, locally configured bounds.
- [Structured Outputs](https://console.groq.com/docs/structured-outputs) lists GPT-OSS
  120B as supporting `strict: true`; strict mode requires every object property to be
  required and every object to set `additionalProperties: false`. The adapter specializes
  dynamic contract maps from backend allowlists before sending and still validates locally.
- [Rate Limits](https://console.groq.com/docs/rate-limits) shows a high-level free-plan
  row for GPT-OSS 120B of 30 RPM, 1K RPD, 8K TPM, and 200K TPD. The same page says exact
  limits can vary and the account Limits page is authoritative. These example values are
  deliberately not encoded as guaranteed provider quotas. `Retry-After` on 429 is honored
  only when a retry fits the configured deadline; a later 429 becomes `rate_limit`.

No paid performance tier or alternate provider is configured or selected automatically.

## Changed files

- `backend/app/llm/groq.py` — bounded async adapter, endpoint validation, strict wire schema,
  error/status mapping, retry/deadline handling, safe logging, and question scope.
- `backend/app/llm/budget.py` — PostgreSQL-only atomic reservations, settlement, release,
  unknown-use retention, Moscow daily window, and request-context user binding.
- `backend/app/config.py`, `.env.example` — Groq configuration and local ceilings; Fake
  remains the default and keys remain `SecretStr`/environment-only.
- `backend/tests/test_llm_groq.py`, `backend/tests/test_llm_budget.py`,
  `backend/tests/test_config.py` — HTTP mock coverage, PostgreSQL reservation cases,
  and config validation.

No migration was needed: SNAP-02's `0004_snapshot_core` already creates `llm_usage`.
Frozen contracts, Alembic files, `MASTER_PLAN.md`, and `TASKS.json` were not changed.

## Acceptance evidence

| Requirement | Evidence | Result |
|---|---|---|
| Async adapter matches frozen Protocol and uses configured Groq model/endpoint | `GroqLLM` implements `LLMClient`; endpoint/host checks and mock request assertions | PASS |
| Strict JSON Schema plus local validation | HTTP mock checks strict mode; schema test checks closed objects/all required fields; invalid output cases | PASS |
| Typed 429/401/5xx/context/transport/timeout failures | Mock status, retry-after, disconnect, and timeout cases | PASS |
| At most one retry within deadline and question-level two-dispatch cap | 429 retry mock; `question_scope` mock proves third dispatch is rejected | PASS |
| PostgreSQL atomic daily and concurrency reservations | Dedicated PG tests for concurrent admission, unknown use, and stale crash reservation | PASS |
| Unknown provider consumption remains charged; known pre-send failure releases | `mark_unknown`/`release` states and PostgreSQL integration tests | PASS |
| No secret/request content in operational logs; redirects do not escape Groq | Secret canary log assertion; redirect mock receives one request only | PASS |
| Fake remains default; CI never invokes Groq | Config default test; every adapter test uses `httpx2.MockTransport` | PASS |
| Real Groq smoke and model quality | No key or explicitly permitted synthetic smoke payload supplied | NOT RUN |

## Checks

Dedicated PostgreSQL 18 database `bsi_snap13_test`; migrations through `0004_snapshot_core`:

- `uv run alembic -c backend/alembic.ini upgrade head` — PASS.
- `uv run alembic -c backend/alembic.ini check` — PASS, no schema drift.
- `uv run ruff check .` — PASS.
- `uv run mypy backend/app` — PASS, 43 source files.
- `uv run pytest backend/tests tools/test_bank_tls_probe.py -q` — PASS, 220 passed,
  0 failed, 0 skipped.
- `uv run python tools/validate_docs.py` — PASS, 19 prompts and DAG/status checks.
- `git diff --check` — PASS.
- Frontend lint/typecheck/build and browser E2E — NOT RUN; no frontend changes.
- Live Groq request — NOT RUN; tests use HTTP mocks only.

## Limitations and next step

The local token count before dispatch is a conservative character-based estimate; returned
provider usage settles known consumption. For an ambiguous dispatch, the full reservation
is retained. A caller that does not use `question_scope()` gets the per-completion retry
cap, while the shared two-dispatch/question cap is applied when the assistant wraps the
question. A live Groq smoke remains NOT RUN and does not block this offline adapter harness.

The integrator should update task status only after PR review/merge; S0–S3 and G1/G2 are
not claimed as passed by this implementation report.
