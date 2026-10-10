# SNAP-12 — typed offline Fake LLM

## Result and integration base

SNAP-12 is implemented, reviewed, and merged into main; the first four-task wave is complete.
Original base: `ea6ae1a2f2f174981d8706b88a6192361d56df8b`.
Existing branch: `codex/snap-12-llm`; PR: [#5](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/5).
Synchronized with `main` at `4c56949` via merge `7c9ab6e`; no conflicts.
The merged SNAP-02/04/07 code, migrations, and dependency lockfiles are preserved.

## Behavior and review findings

- `FakeLLM.complete` implements the frozen async `LLMClient` Protocol and returns
  `LLMResponse | LLMError`. `FakeFixture.error` uses a closed `Literal` union matching
  the frozen error codes; no casts, suppression, or broader error type is used.
- Explicit fixtures are selected by request ID, never by untrusted question/document
  instructions. Fixtures are copied on construction so caller mutation cannot change
  subsequent results. Unmatched intent asks for clarification; unmatched explain returns
  no claims, even when a question or backend allowlist names a claim.
- Successful structured JSON is checked against `IntentResult` / `ExplainResult` and
  the caller's schema. The local validator supports the bounded subset used by these
  frozen DTOs: object/array/scalar types, required/extra fields, enum/const, local `$defs`
  refs, `anyOf`, nested properties/items, bounds, uniqueness, patterns and UUID/date formats.
  Unsupported keywords and remote refs fail closed; this is not a general JSON Schema
  engine. Validation also covers normalized output/defaults. Non-finite numbers and
  non-JSON objects are rejected.
- Explain can only reorder backend-provided claim IDs and select the supported
  `claim_fact`, `claim_comparison`, `claim_absence` templates permitted by that caller.
  Unknown/duplicate IDs, templates for unordered claims, invented templates, text,
  numbers, URLs, and malformed allowlists are rejected. The backend remains responsible
  for evidence verification and final rendering; an allowlisted ID is not proof of approval.
- All seven frozen provider error codes have deterministic fixtures. A delay exceeding
  the request deadline returns `timeout` immediately. Malformed raw JSON returns
  `invalid_output`. Rate limit returns a deterministic retry-after; there is no retry loop.
- Usage records an explicitly estimated prompt/completion/total count, a Fake model ID,
  and deterministic latency metadata. No reasoning trace, request text, credentials,
  database, storage, tools, or provider transport is stored or used by the Fake.

The old CI failure was mypy's `str` argument at `fake.py:60`; it is corrected with the
`Literal` fixture type. The earlier report's global Python checks did not represent the
locked CI environment and its mypy PASS was incorrect. The locked uv results below
supersede the original 7-test/global-environment report.

## Files

`backend/app/llm/base.py`, `backend/app/llm/fake.py`,
`backend/tests/test_llm_contract.py`, and this report.
Frozen contracts, `llm/models.py`, configuration, other SNAP implementations, and
migration/dependency files have no SNAP-12 edits.

## Acceptance evidence

| Requirement | Evidence | Result |
|---|---|---|
| Concrete Fake satisfies async Protocol | Typed `LLMClient` assignment in tests; strict mypy on app and the test module | PASS |
| Intent and explain success / schema validation | Frozen DTO schemas and roundtrips; nested type/enum/const/bound constraints | PASS |
| timeout/rate_limit/auth/unavailable/context_exceeded | Parametrized typed failure fixtures, immediate deadline test, no retry loop | PASS |
| invalid_output/budget_exceeded | Additional frozen failure fixtures and malformed/raw/nonfinite JSON cases | PASS |
| Backend claim/template boundaries | Unknown/duplicate ID, unordered mapping, extra text/link/tariff, unsupported template and malformed allowlist cases | PASS |
| Deterministic repeat / usage | Equal complete responses on repeated input; stable Fake metadata; accounting identity | PASS |
| Prompt injection / no network | Socket connect/create_connection/DNS denied during intent/explain and failure calls; hostile user/document instructions leave safe outputs | PASS |
| Fixture question cannot create verified claim without backend evidence | Default explain returns empty ordering despite backend allowlist and hostile question | PASS |

## Executed checks

Locked Python 3.11 environment (`uv sync --locked`), PostgreSQL 18.6 container.
Dedicated newly created DB `bsi_snap12_test`; no SQLite replacement for integration.

- `uv run ruff check .` — PASS, full repository.
- `uv run mypy backend/app backend/tests/test_llm_contract.py` — PASS, 42 source files;
  includes the entire backend and the concrete Protocol harness.
- `uv run alembic -c backend/alembic.ini upgrade head` — PASS on clean dedicated DB,
  revisions `0001_catalog` through `0004_snapshot_core`.
- `uv run alembic -c backend/alembic.ini check` — PASS, no new upgrade operations.
- `uv run pytest backend/tests tools/test_bank_tls_probe.py -q` — PASS, 198 passed,
  0 failed, 0 skipped; includes 45 LLM cases, 9 ingestion PG cases and 6 snapshot PG cases.
- `uv run python tools/validate_docs.py` — PASS, 19 prompts, DAG/status consistency.
- Synthetic source recovery E2E on dedicated `bsi_e2e` — PASS_SYNTHETIC_ONLY;
  run `645ddae0194f4255a4d89e28b9ca3761`, `network_requests=0`;
  local result `.local/snap12-e2e/645ddae0194f4255a4d89e28b9ca3761/result.json`.
- `git diff --check` — PASS.
- Local frontend/browser checks — NOT RUN: no UI edits. The repository CI checks
  frontend lint/typecheck/build separately before merge.
- Real bank/Groq/provider evaluation — NOT RUN: no credentials or real-data permission.

## Integration and next step

Review: frozen interfaces, new ORM coexistence, request/response serialization, usage,
error narrowing, claim/template boundaries, malformed data and injection reviewed with
no unresolved SNAP-12 issue after the checks above. The user-facing fallback envelope
belongs to SNAP-14; SNAP-12 supplies typed failure/fallback scenarios without an assistant.
Groq adapter/quotas remain SNAP-13. S0 is not complete and S1 remains BLOCKED;
S2/S3 remain NOT EVALUATED, G1/G2 NOT PASSED. CI and merge evidence will be recorded
in the final integration response; task statuses are updated only after the PR merge.


## Completed merge evidence

- Implementation fix: [2136b14](https://github.com/KulikovKA/banking-salary-intelligence-platform/commit/2136b149991ed9f0c900f82d1a16e74543e876ff).
- PR [#5](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/5)
  merged after backend and frontend CI passed; no outstanding review threads or changes requested.
  Review was performed locally by the implementing agent; no separate human approval is recorded.
- Green PR CI: [run 38076573502](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38076573502).
- Main merge: [f9ea7d1](https://github.com/KulikovKA/banking-salary-intelligence-platform/commit/f9ea7d1635dd1855e51439839921c7367c11be45).
- Integrator updates only the statuses of merged SNAP-02, SNAP-04, SNAP-07 and SNAP-12
  to DONE in the active plan/registry, preserving task order, dependencies and product gates.
- Next independent work: SNAP-03, SNAP-05, SNAP-06, SNAP-13 and SNAP-15;
  SNAP-05 owns the next parser dependency/lockfile update. SNAP-13 implements the
  Groq Free adapter after this Fake boundary. Real source/provider permissions remain separate.
