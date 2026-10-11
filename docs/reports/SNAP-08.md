# SNAP-08 — parser and extraction integration

**Result:** implementation complete and ready for independent review. Product gates and
task statuses were not changed.

## Scope and source commits

- Initial base: `87bd5a81b0af867c2d4d6e5b7c03c5cf66b7aaf7` (`origin/main` at integration start).
- Final branch base: `4f714e2` (`origin/main`, after PRs #12 and #13 merged during this task).
- Branch: `codex/snap-08-integration`.
- Agent A runner commit: `9e4128aaac52a272c416c7b491909659c883ae32`.
- Agent B extractor commit: `72e0386212ca1f6101647952b46a5b6e8ef2daaa`.
- Both commits were cherry-picked in sequence without conflicts at the initial base. While
  integration work continued, PRs #12 and #13 merged those same commits into `origin/main`.
  The branch was rebased on the updated main; Git skipped the patch-equivalent temporary
  cherry-picks, so the final branch gets A/B from `origin/main` without duplicate commits.
  The source branches were not changed.

## Integration behavior

`ExtractionPipeline` accepts one source version from an exact draft manifest. It checks
accepted state, bank/source/policy/fetch provenance, current permission, corpus identity,
manifest hash, and local original bytes before starting the parser. It checks provenance,
permission, snapshot identity, and bytes again in the write transaction.

Successful parser output is normalized into the existing frozen tariff candidate contract.
Chunks retain text, ordinal, SHA-256, locator, relations, and search vector. Evidence rows
retain exact quote offsets and connect the source version, extraction, chunk, and original
hash. Candidates remain `pending_review`; this integration does not create reviews or
published facts. Deterministic run, candidate, chunk, and evidence identities include the
extraction scope. Replays validate the existing stored chain, and a changed parser version
creates a separate extraction revision.

Duplicate automatic and operator-mapped suggestions with the same normalized meaning are
merged with their citations. Invalid mappings and unknown or invalid values remain
diagnostics; they do not invent values. The current schema has no diagnostic persistence
table, so the pipeline and CLI return safe diagnostic code counts without storing the
diagnostics as rows.

The local CLI stages/verifies the draft document and runs only against `LocalBlobStore`.
It does not fetch URLs, call Groq, schedule work, or publish candidates. It prints IDs,
counts, safe diagnostic codes, and stable error codes without printing source text or
secrets. Explicit payer, operation, and scope may be supplied in a context JSON file; they
are not guessed.

Runner integration fixes found by the PostgreSQL tests:

- XLSX originals in content-addressed storage may have no `.xlsx` extension. The runner
  now makes a temporary byte-identical `.xlsx` copy for the worker; the parser still
  validates the original SHA-256.
- POSIX timeout cleanup kills the worker's process group even if its leader has already
  exited. Unsupported non-Linux POSIX platforms fail explicitly instead of silently
  omitting hard limits. Windows continues to use its Job Object.

## Acceptance evidence

| Criterion | Evidence | Result |
|---|---|---|
| Exact accepted original, permission, provenance, hash, and corpus are verified | PostgreSQL cases for wrong hash, revoked permission, quarantine, and synthetic-to-real manifest mismatch | PASS |
| PDF, XLSX, and HTML reach persisted candidates and evidence | `test_synthetic_original_reaches_postgres_candidate_and_exact_evidence` for all three formats | PASS |
| Chunks and evidence preserve exact chain and locators | Assertions verify chunk hashes, quote offsets, locators, source version, raw hash, and extraction hash | PASS |
| Replay is idempotent; parser-version changes are scoped | `test_repeat_is_idempotent_and_new_parser_version_has_scoped_identity` | PASS |
| Concurrent repeats create one chain | Two independent sessions and concurrent parser calls; one insert and one idempotent replay; one run/chunk/candidate chain | PASS |
| Crash, timeout, and invalid inputs do not leave partial data | Pipeline crash/timeout rollback tests; runner timeout test confirms worker and descendant termination | PASS |
| Mapping duplicates merge; invalid mappings remain visible | Deduplication/evidence test and invalid mapping diagnostic test | PASS |
| Unknown, conditional zero, individual values, and evidence roles are preserved | PostgreSQL assertions cover unknown value, conditional zero with condition evidence, and individual value | PASS |
| Extraction does not approve or publish facts | Candidate is `pending_review`; no `FactReview` or `PublishedFact` rows are created | PASS |
| Worker output and environment are bounded | Output-limit error test; worker environment excludes database, Groq, and arbitrary secret variables | PASS |
| Unsupported platforms fail explicitly | Runner test forces an unsupported POSIX platform before opening the input | PASS |

The concurrency test creates and drops a temporary PostgreSQL schema from ORM metadata so
the immutable rows do not remain in the dedicated test database. The remaining persistence
integration tests run against the dedicated database after Alembic migrations.

## Checks

- `uv run ruff check .` — **PASS**.
- `uv run mypy backend/app` — **PASS**, 58 source files.
- `uv run pytest backend/tests -q` — **PASS**, 273 passed.
- `uv run alembic -c backend/alembic.ini upgrade head` — **PASS**, dedicated PostgreSQL test
  database at migration head.
- `uv run alembic -c backend/alembic.ini check` — **PASS**, no new upgrade operations.
- `uv run python tools/validate_docs.py` — **PASS**, standalone main links, 19 prompts,
  DAG/statuses, and source decisions.
- `git diff --check` — run again before commit.
- Offline synthetic end-to-end — **PASS** through the PostgreSQL pipeline tests for PDF,
  XLSX, and HTML; no bank or Groq network calls were made.
- Windows runner process-tree timeout — **PASS** through the Job Object test. Linux
  `killpg` behavior was **NOT RUN** in this Windows environment; its platform-specific
  test runs on Linux.
- Memory exhaustion stress test — **NOT RUN**. Windows hard memory-limit setup is exercised
  by the bounded parser integration runs at the configured limit; the tests do not attempt
  to exhaust it.
- Frontend checks/browser E2E — **NOT RUN**, no frontend files changed.
- Real-source acquisition, Groq, and real-corpus evaluation — **NOT RUN**; fixtures are
  synthetic only.

## Limits and handoff

No contracts, ORM models, migrations, parser internals, registry, frontend files,
`MASTER_PLAN.md`, or `TASKS.json` were changed. No scheduler, queue, service, live source
fetch, automatic provider selection, review, or publication behavior was introduced.

Diagnostics are returned as safe counts because there is no diagnostics table in the
frozen schema. If SNAP-09 requires durable diagnostic records, that needs an explicit
schema-owner follow-up instead of a local schema fork. Candidate and evidence rows are
ready for a downstream manual-review workflow.

Gate states remain unchanged: S1 **BLOCKED**; S2/S3 **NOT EVALUATED**; G1/G2 **NOT PASSED**.
Synthetic evidence does not establish real-source permission or product acceptance.
