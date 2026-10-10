# SNAP-15 — Auth, invitations, and server sessions

**Base:** `504c71f` (`main`, 2026-10-10)

**Branch:** `codex/snap-15-auth`

**Implementation commit:** `00cd8ed`

**Report commit:** `9dae3cd`

**Status:** integrator corrections and offline verification complete; GitHub merge remains blocked by integration API 403. The original findings below are historical and are resolved by the integrator section at the end.

## Implemented

- Added `backend/app/auth/` with SQLAlchemy models, Argon2id password service,
  one-time invite/reset operations, server sessions, a single-process login
  limiter, router/dependency factory, and an explicit first-admin CLI.
- Added Alembic `0005_auth` after `0004_snapshot_core`. The schema includes
  `users`, `invitations`, `password_resets`, `sessions`, and `auth_audit`.
  Secrets are random 256-bit values; only SHA-256 digests are persisted.
- Invitations expire after 48 hours and resets after 30 minutes; both are one-use
  under PostgreSQL row locks. Password reset invalidates prior sessions and
  creates a new session. Sessions enforce 8-hour idle and 24-hour absolute expiry.
- Login uses generic failures, a dummy Argon2 check for unknown accounts, and
  5 attempts/minute per normalized account plus 20/minute per client IP. Proxy
  headers are not trusted. The limiter is process-local for the one-instance v1.
- Unsafe routes verify exact Origin. Authenticated mutations also verify a
  session-bound double-submit CSRF token. Production uses `__Host-session`
  (`Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`); local HTTP uses a separate
  cookie name. No public signup or email delivery was added.
- First admin creation is an explicit CLI operation that reads and confirms a
  password using protected stdin. It refuses a non-empty user table; no default
  production password or fake identity path was added.
- Argon2id uses the RFC 9106 low-memory profile (`t=3`, `m=64 MiB`, `p=4`) and
  `argon2-cffi`'s Argon2id implementation. See the [argon2-cffi parameter
  guidance](https://argon2-cffi.readthedocs.io/en/stable/parameters.html) and
  [RFC 9106](https://www.rfc-editor.org/rfc/rfc9106.html).

## Acceptance evidence

| Requirement | Evidence |
|---|---|
| Invite one-use race and hash-only tokens | PostgreSQL 18 integration test runs two concurrent accepts; exactly one succeeds. DB stores the digest only. |
| Password verification and reset | Argon2id hash prefix/verification tested; reset consumes token, revokes old sessions, creates a new session, and rejects reuse. |
| Session fixation, rotation, expiry, logout | HTTP test submits a fixed attacker cookie and receives a new session; invite acceptance rotates into a new session; idle and absolute expiry revoke; logout makes `/me` return 401. |
| Analyst/admin and A/B identity separation | Analyst is denied admin invitation route; separate PostgreSQL sessions resolve to their own user/role only. |
| CSRF and Origin | Wrong Origin and wrong CSRF token are rejected; exact same-origin requests succeed. |
| Brute-force behavior | Account/IP limits tested at 5/20 per minute; missing-user and wrong-password responses are identical. |
| Last administrator | Demotion and deactivation of the only active admin both return `LAST_ADMIN`. |
| PostgreSQL migration | PostgreSQL 18 `upgrade head` and `alembic check` pass on `bsi_auth_test`. |
| Offline scope | Tests use synthetic users and `.invalid` logins; no bank or LLM network access. |

## Checks

- `uv run ruff check .` — PASS.
- `uv run mypy backend/app` — PASS, 48 source files.
- `uv run pytest backend/tests/test_auth_sessions.py backend/tests/test_db_contract.py -q` — PASS, 13 tests on PostgreSQL 18.
- `uv run alembic -c backend/alembic.ini upgrade head` — PASS on PostgreSQL 18.
- `uv run alembic -c backend/alembic.ini check` — PASS, no model/schema drift.
- `python tools/validate_docs.py` — PASS.
- Full `backend/tests` run — 195 passed, 1 failed: the existing
  `backend/tests/test_snapshot_db.py::test_snapshot_schema_runs_on_postgresql_18`
  asserts the head is `0004_snapshot_core`, which is stale after adding `0005`.
  Its owner should update the assertion to the current Alembic head. It was left
  unchanged because SNAP-15 marks other modules read-only.
- Frontend checks — NOT RUN; no frontend files changed.

The repository's `pyproject.toml` and `uv.lock` still do not include
`argon2-cffi`. For local verification only, it was installed into this worktree's
`.venv`; no dependency manifest or lockfile was edited. A clean `uv sync --locked`
environment therefore cannot run the auth tests yet. Merge SNAP-05 first, then
add/lock `argon2-cffi` and rerun the checks before treating this PR as complete.

## Sequential integration requests

1. **SNAP-05 owner:** after its merge, add `argon2-cffi` to `pyproject.toml` and
   `uv.lock`; rerun the auth tests from a clean locked environment.
2. **Schema/model owner:** SNAP-15's design calls for nullable user FKs on
   `fact_reviews.user_id` and `llm_usage.user_id`. Those active ORM modules are
   outside SNAP-15's owned paths, so this branch does not edit them or add
   migration-only FKs that would make Alembic report drift. Add the ORM FKs and
   integrate the two FK operations into `0005_auth` sequentially, then rerun
   PostgreSQL migration checks.
3. **Migration test owner:** update the hard-coded `0004_snapshot_core` head
   expectation in `test_snapshot_db.py` after `0005` integration.
4. **SNAP-13 owner:** after its `config.py` merge, rebase and check the auth
   router's use of `public_base_url`, `app_env`, and `secure_cookies`; this
   branch does not modify `config.py`.

`MASTER_PLAN.md` and `TASKS.json` were not changed. Module status should remain
`IN_PROGRESS` until the sequential dependencies and regression expectation are
integrated and the locked-environment test suite is green. S0/S1/S2/S3 product
gates are not assessed by this auth module report.

## Push and PR handoff

The branch was pushed to `origin/codex/snap-15-auth`. Draft PR creation was
attempted but GitHub returned `403 Resource not accessible by integration`.
The browser automation fallback could not connect to its Windows native pipe
after the prescribed retry/reset (`file not found`, OS error 2). No PR was
created. Open the [compare page](https://github.com/KulikovKA/banking-salary-intelligence-platform/compare/main...codex/snap-15-auth?expand=1)
to create the draft PR; use the blockers above as its review checklist.

## Integrator completion (2026-10-10)

Base main remains `504c71f`; GitHub API denied merge of PR #9 with 403. To make
PR #8 reviewable against the intended combined result, the reviewed corpus, HTML,
Groq and XLSX branch heads were merged locally into the auth review branch without
rewriting history. These are preparation merges, not claims of main integration.
Use the merge order #9, #10, #6, #7, #8; use merge commits to retain shared ancestry.

### Resolved shared blockers

- `argon2-cffi` is declared and locked, preserving pdfplumber/openpyxl and stubs.
- `0005_auth` follows additive `0004a_corpus_gates`, with matching nullable RESTRICT
  user FKs on fact_reviews and llm_usage; no historical user is invented.
- PostgreSQL schema tests assert head 0005, PostgreSQL 18, nullable columns and
  actual FK targets/delete behavior. Budget tests now create explicit disabled
  synthetic identities rather than random nonexistent FK values.
- Strict mypy passes from a locked environment; auth uses the post-SNAP-13 Settings.

### Security review and corrections

Argon2id uses t=3, m=65536 KiB, p=4, 12..128-character passwords and random
256-bit invite/reset/session tokens. Only token hashes are persisted. The
[official parameter guidance](https://argon2-cffi.readthedocs.io/en/stable/parameters.html)
was rechecked on 2026-10-10. No default production password is provided.

Login/invite/reset previously checked only Origin. The router now exposes
`GET /api/v1/auth/csrf`, issuing a signed 10-minute browser challenge with no-store.
These anonymous mutations require its matching cookie and X-CSRF-Token plus exact
Origin. Authenticated mutations keep session-bound CSRF. Production sessions are
__Host-session, Secure/HttpOnly/Lax/Path=/ without Domain; production rejects an
HTTP Origin override. Validation errors omit credential/token input values.

Successful login/invite/reset revokes the previous browser session and creates
new session/CSRF secrets. Idle 8h and absolute 24h expiry remain; session touch is
flushed before detached identity return. AuthContext exposes reusable user/admin/
CSRF dependencies for SNAP-16. Mutations recheck current admin role/active state
inside their transaction. Last-admin advisory locking survives concurrent demotion.
Reset consumption locks user before reset rows, matching issuance/revocation order
and preventing reverse-order deadlocks. Invite/reset same-token races allow one
consumer. The login limiter retains 5/account and 20/IP per minute with bounded
buckets/deques and fails closed when active key capacity is full.

Tests cover production cookies, session touch/rotation, CSRF, credential canaries,
stale admin identity, reset race, last-admin race and login-burst memory bounds.
The HTTP fixation fixture uses the browser's host-scoped cookie rather than a
TestClient-only domainless duplicate.

### Final validation

- Locked sync, Ruff, strict mypy (54 source files), docs validator: PASS.
- Full backend + TLS-tool pytest on dedicated PostgreSQL 18 bsi_wave2_test:
  **268 passed, 0 failed, 0 skipped**, no warnings.
- Alembic upgrade/check: PASS on bsi_wave2_test; upgrade from 0004 and check on
  bsi_e2e: PASS. 0001?0004 files are unchanged.
- Source recovery E2E: PASS_SYNTHETIC_ONLY, network_requests=0; evidence is copied
  to the wave-two integration report. This is not the deferred SNAP-08 pipeline.
- Frontend lint/typecheck/build: PASS. Browser E2E NOT RUN: no UI implementation
  changed and the closed assistant interface remains SNAP-17.
- New integration test verifies authenticated identity -> actual PG user FK and
  quota reservation -> mocked Groq settlement, plus Fake compatibility.
- Live Groq/real bank acquisition/S1: NOT RUN/BLOCKED; no credentials/payload
  approval or source-specific real acquisition/storage/reuse decision supplied.

### Concrete downstream handoff

SNAP-16 must fetch the anonymous CSRF challenge before login/invite/reset, supply
X-CSRF-Token, mount the router/dependencies, bind authenticated user to Groq budget,
and close the reused Groq client in lifespan. Existing public DTO/Protocols and
main.py are unchanged. SNAP-08 consumes CorpusService.read_draft_document on a
staged manifest; final SnapshotMember is added only after successful extraction.

MASTER_PLAN/TASKS statuses remain unchanged until verified main merge. S1 BLOCKED,
S2/S3 NOT EVALUATED and G1/G2 NOT PASSED. No new task implementation was started.
