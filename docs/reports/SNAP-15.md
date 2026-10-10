# SNAP-15 — Auth, invitations, and server sessions

**Base:** `504c71f` (`main`, 2026-10-10)

**Branch:** `codex/snap-15-auth`

**Implementation commit:** `00cd8ed`

**Report commit:** `9dae3cd`

**Status:** implementation scaffold is reviewable; final integration remains pending the shared dependency and schema-owner changes listed below.

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
