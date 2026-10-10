# SNAP-01 — Executable DTO and Protocol

**Result:** implementation ready for review; this report does not mark the plan task DONE.
**Base commit:** `2432028412ca632a96a7e6df465702b6f0baeed0` (`main` at branch creation).
**Branch:** `codex/snap-01-contracts`.
**Scope:** `backend/app/contracts/**` and `backend/tests/test_snapshot_contracts.py` only, plus this required report.

## Behavior delivered

- Added immutable Pydantic v2 contracts with `schema_version=1`, `extra="forbid"`, and explicit nullable/unknown representations.
- Added discriminated value and locator unions; decimal wire values remain strings, floats and non-finite values are rejected for monetary inputs.
- Added scope, geography, dates, condition AST, evidence offsets/provenance, comparison, answer, parser, snapshot read, and LLM request/response/error DTOs.
- Added structural `Protocol` interfaces for offline parsers, async LLM clients, comparison, and snapshot read services. No parser or LLM implementation was added.
- Added an adapter from the existing `ingestion.evidence.ExtractionEvidence`; the ingestion DTO and implementation were left unchanged.
- Real bank-code fields accept only the four canonical codes. `synthetic_a` / `synthetic_b` identities exist only in an explicit test-fixture model and are rejected by the real DTOs.
- Answer sources carry a constrained authenticated-original download route alongside evidence; LLM DTOs do not select arbitrary URLs or claims.

## Acceptance evidence

| SNAP-01 criterion | Evidence | Result |
|---|---|---|
| Roundtrip versioned DTOs and serialization | `test_all_pipeline_dtos_roundtrip`, discriminated-value and locator roundtrip tests | PASS |
| Reject float, NaN, Infinity and unknown input fields | `test_decimal_wire_roundtrip_and_money_float_rejection`, unknown-field assertions | PASS |
| Reject empty specific scope and invalid offsets | `test_reject_unknown_fields_invalid_offsets_scopes_and_dates` | PASS |
| Reject duplicate bank codes and synthetic identities in domain DTOs | `test_reject_duplicate_banks_unknown_real_identity_and_bad_conditions` | PASS |
| Reject unsupported condition fields/operators, malformed AST and excessive depth | condition-AST assertions in `test_reject_duplicate_banks_unknown_real_identity_and_bad_conditions` | PASS |
| Typecheck Protocols against Fake structural stubs | `test_protocols_accept_structural_fake_stubs`; mypy checked app and contract test | PASS |
| Keep existing `ExtractionEvidence` compatible through an adapter | `test_existing_ingestion_evidence_adapts_without_changing_its_contract` | PASS |
| Preserve ingestion/storage/migrations and avoid business implementation | Git diff is limited to contracts, contract tests, and report; no ingestion, storage, migration, config, or runtime composition edits | PASS |

## Checks

- `uv run ruff check .` — **PASS**.
- `uv run mypy backend/app backend/tests/test_snapshot_contracts.py` — **PASS**, 33 source files checked.
- `uv run pytest backend/tests -q` — **PASS**, 101 passed, 9 skipped.
- `python tools/validate_docs.py` — **PASS**, standalone links, 19 prompts, dependency DAG/statuses, and source decisions validated.
- PostgreSQL integration — **NOT RUN**: the 9 existing tests skip because `TEST_DATABASE_URL` is unset. SNAP-01 adds no database schema or integration behavior.
- Frontend lint/typecheck/build and browser E2E — **NOT RUN**: no frontend files or UI behavior changed.
- Bank/Groq network or real corpus/provider evaluation — **NOT RUN**: outside SNAP-01; no source permissions or provider run were introduced.

## Limits and handoff

This change freezes contracts and interfaces only. It does not implement parsing, tariff normalization, evidence validation/publication, corpus reads, comparison calculations, LLM behavior, API routes, or persistence. The protocol stubs are test-only.

Product gates remain independent: the report does not claim S0 completion; S1 remains blocked on accepted real corpus and permissions; S2/S3 remain not evaluated; historical G1/G2 remain not passed. MASTER_PLAN.md and TASKS.json were intentionally not edited; the integrator owns status updates after merge.

**Next step:** review and merge SNAP-01, then treat contracts as frozen for downstream tasks.
