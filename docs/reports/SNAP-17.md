# SNAP-17 — Desktop Chat ↔ FastAPI Integration

Date: 12.10.2026, Europe/Moscow. Verdict: **READY FOR REVIEW**, synthetic technical
checks passed; **not DONE**. Separate scope agreement/merge and independent
acceptance remain required. No automatic merge or task-status update performed.

Base: `b440534` (fetched origin/main; merged API PR #28).
Branch: `codex/snap-17-desktop-integration`.
Worktree: `C:/Users/Kirill/Desktop/sber-snap-17-chat`.
Scope commit: `0adadd8`, separately proposed in
[PR #29](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/29).
Implementation PR targets that scope branch so its diff contains only integration;
after the integrator agrees/merges #29, retarget implementation to main.

## Scope and preserved dependencies

The user's current prompt authorizes the repository's own desktop chat rather than
the historical external frontend handoff. PR #24 is merged at `43b3841`; its
ChatShell/ChatSidebar/ChatMessage/ChatComposer/ResponseTable/presentation models
and reducer are reused. PR #28 is merged at `b440534`; SNAP-16 report/actual routers,
services and generated types were inspected. No second UI, dashboard, cabinet,
admin review screens, mobile work, scheduler or new service was introduced.
Backend, frozen contracts, migrations and generated api-contracts.ts have zero diff.
Original checkout's unfinished MASTER_PLAN/TASKS/next-env edits were not included.
No subagents were used.

The proposed CHAT-01–CHAT-04 criteria are in FRONTEND_HANDOFF and the separate
scope PR. Historical FE-01–FE-04 are preserved, not declared passed. TASKS and
MASTER_PLAN statuses remain unchanged; SNAP-16 acceptance belongs to the integrator.

Frozen API revision:
`5c88411a1e632e229a8f86a8e44c1976622a6cb018803adf3103983f0e39aeef`.
Existing pinned dependencies: Next 16.4.0, React/ReactDOM 19.3.0,
Playwright 1.64.0, Node 24/npm 11; package manifests/lockfiles unchanged.
No assets/fonts/dependencies were added. Existing package-lock inventory contains
176 package entries including optional platform packages: MIT 109, Apache-2.0 33,
LGPL-3.0-or-later 10, Apache-2.0 AND LGPL-3.0-or-later AND MIT 1,
Apache-2.0 AND LGPL-3.0-or-later 3, ISC 9, CC-BY-4.0 1, BSD-2-Clause 6,
BSD-3-Clause 2, BlueOak-1.0.0 1, 0BSD 1. Existing licensing/release review remains
applicable; this report does not infer rights to real bank documents.

## Runtime architecture and route matrix

| Existing desktop action | Same-origin API | Evidence/state |
|---|---|---|
| Open application | GET auth/me | HttpOnly server session, no persisted browser token |
| Login / accept invitation | GET auth/csrf, POST auth/login or auth/accept-invite | signed anonymous challenge cookie/header; session rotation |
| Logout | POST auth/logout | session CSRF; abort/unmount and clear all chats |
| Select frozen corpus | GET snapshots with bounded pagination | explicit selection; kind/revision/freeze date/coverage |
| Ask / compare within chat | POST assistant/questions | frozen QuestionRequest -> AnswerEnvelope/ComparisonResult |
| Open cited original | GET documents/{version}/original | strict server-provided relative UUID path; authenticated attachment |

`frontend/app/api/v1/[...path]/route.ts` is an allowlisted Node route handler, not
an arbitrary URL proxy. BACKEND_URL is server-only, must be an HTTP(S) origin
without credentials/path/query/fragment, and fails closed when absent. Forwarded
headers are not trusted. Cookie, actual browser Origin, X-CSRF-Token and content
type are passed unchanged; Origin is never synthesized. Other incoming headers
including Authorization/X-Forwarded-For are omitted. Actual POST bytes are capped
at 64 KiB, redirects are not followed, upstream wait is bounded to 50 seconds.
Only selected content/attachment/request-id/Retry-After headers and all separate
Set-Cookie headers return; responses are no-store/nosniff. Missing backend/config/
network failures produce a sanitized 503. FastAPI still owns auth/Origin/CSRF/
authorization/corpus checks and never trusts the frontend to approve evidence.

`lib/client.ts` uses generated endpoint request/response/parameter types,
same-origin credentials, a 55-second client deadline and AbortSignal. Anonymous
CSRF stays in the current request; session CSRF comes from the backend-readable
bsi-csrf cookie after login or session restore. No credential/session localStorage.
Error messages are local and fixed, never raw backend/provider messages/stacks.
Typed 400/401/403/404/409/422/429/503/network/timeout handling includes numeric
Retry-After. Invalid/reused/expired invitations and invalid login have compact
messages; 401 from protected operations clears all conversation state. Session
checks also run when returning to the focused/visible tab.

`BackendChat` adds compact auth/snapshot/question controls around the existing UI.
No latest snapshot is selected. No snapshot means no composer/question dispatch.
The optional explicit comparison scenario supplies payer/operation/RUB/date/
period/region/payroll Decimal string; missing fields remain unknown. All four banks
are selectable; advanced metric filter is explicit. Changing snapshot unmounts
and aborts the previous chat. Logout clears chats immediately even when its request
fails; failed logout remains visible and retryable. Date displays use Moscow time;
freeze/acquisition dates are not asserted to be tariff effective dates.

`BackendChatTransport` retains ChatTransport unchanged. It awaits one complete JSON
envelope, checks selected snapshot/revision, then emits immediate presentation
events. This is **not SSE or server streaming**. Abort cancels the client fetch
and rejects late UI writes; already started backend computation may finish.
Assistant text/quotes/conditions are React text, not HTML. The adapter preserves
all value/status unions, nulls/unknown bounds, Decimal precision, mandatory
conditions/missing inputs, backend claims/pairwise outputs, limitations, scenario,
revision/data_as_of and protected source quotes/locators/hashes. It performs no
tariff arithmetic, rounding or winner selection. Unknown is not zero.

Normal `/` uses the backend. Demo requires **both** CHAT_DEMO_MODE=true and
APP_ENV=test/local/development, plus `/?demo=1`; there is no automatic demo fallback
on an API failure. Existing demo/regression tests use that explicit opt-in.

## Validation and proposed AC evidence

| Check | Final result |
|---|---|
| Locked uv/npm install | PASS; lockfiles unchanged |
| Ruff | PASS, including new test harness |
| mypy backend/app | PASS, 74 files |
| Alembic upgrade/check | PASS, dedicated PG18 test DB, head 0005_auth, no drift |
| Full backend + TLS-tool regression | **PASS: 564 passed, 1 skipped, 0 failed**, 594.28s |
| Frozen OpenAPI/TS drift | PASS; unchanged generated contract |
| Frontend lint/typecheck/build | PASS; Next production build |
| Existing frontend + new adapter/client tests | **PASS: 23 passed, 0 skipped, 0 failed**, 20.7s (20 retained + 3 new) |
| Real browser/API/PG/Fake E2E | **PASS_SYNTHETIC_ONLY: 8 passed, 0 skipped, 0 failed**, 37.1s |
| Frontend bundle canary scan | PASS; 10 client JS bundles; 0 key/DB/backend-URL canary leaks |
| Production npm audit | PASS, 0 vulnerabilities |
| Full npm audit including dev | **FAIL: 4 High entries** in existing ESLint dependency chain; see limitation below |
| Docs validator / diff whitespace | PASS; 19 prompts/DAG/statuses/links |
| Bank/Groq application requests | PASS: 0; local browser allowlist + Fake + harness external-socket guard |
| Live real corpus/Groq/product acceptance | NOT RUN; no source/provider admission |
| Independent acceptance / separate scope merge | NOT RUN; integrator responsibility |

The one backend skip is `/proc` process-state inspection on Windows; no PG/search/
API integration was skipped. Development-only type/fixture/schema-collision/
locator/expected-error failures were corrected. Partial runs are not added to final
totals. No required integration test is replaced with a mock transport.

CHAT-01 evidence: exact merged base/UI/API revisions and unchanged dependencies/
contracts above; reuse diff and 20 retained regression cases.
CHAT-02 evidence: real login/invite/single-use/logout/expiry tests, HttpOnly cookie
inspection, no token localStorage, Origin/CSRF 403, 401 and conversation removal.
CHAT-03 evidence: real explicit selection/empty/question/four-bank comparison,
verified synthetic 100 RUB and three unknown cells, protected original SHA-256;
adapter tests exercise all unions/statuses/conditions/missing inputs/XSS/safe links;
fallback keeps sources; AbortController test confirms no late display. Composer
fits a 1440x900 desktop even with comparison controls open; screenshot visually
inspected. CHAT-04 evidence: the checks and distinct real/adapter coverage above.
These are proposed implementation evidence, not independent accepted AC verdicts.

The browser harness runs Next -> actual allowlisted proxy -> actual FastAPI ->
committed independent PostgreSQL connections -> parsed original/evidence/manual
review/publication/frozen synthetic fixture -> RoutedFake (existing Fake adapter).
It migrates/checks a fresh random schema in dedicated `bsi_snap17_browser_test`;
it does not substitute ORM create_all or SQLite. Retained schemas/originals are
test-only and ignored by Git. Failure controls are confined to the separate test
server on localhost and require a random test-control value. The production app
does not import/expose those controls, and the frontend proxy rejects them.
Quota windows reset only between test cases; the actual limiter is exercised.
Session expiry uses committed revocation; fallback uses Fake unavailable; 503 uses
the actual whole-question deadline. 401/403/404/429/503 are checked on real routes.
409/422/network/client-timeout presentation and all exotic value/status variants
are additionally checked at the client/adapter boundary; the full backend
regression tests the underlying real contract behaviors. Empty list reflects a
genuinely unreadable fixture; it is not a hardcoded frontend response.

Ignored artifacts: `.local/snap17-browser/fixture.json`, random test originals,
comparison.png, results/traces; `.local/frontend-chat-mvp` regression artifacts.
Fixture credentials/control values are synthetic and kept outside Git.

## Reproducible local run

Use SNAP-16's documented backend settings/operator bootstrap and exact admitted
manifest/storage roots; this UI does not seed runtime bank tariffs/users/grants.
Set backend PUBLIC_BASE_URL to the exact browser origin (scheme/host/port).
For local HTTP only, use the existing local cookie configuration. For production,
retain Secure/HttpOnly/__Host-session and HTTPS; do not disable Origin/CSRF.

```powershell
# Backend terminal: follow SNAP-16's env/bootstrap/storage/migration instructions.
$env:PUBLIC_BASE_URL = 'http://localhost:3000'
# Normal local default is Fake/offline until provider/source admission exists.
uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# Frontend terminal, same worktree:
$env:BACKEND_URL = 'http://127.0.0.1:8000'
$env:NEXT_TELEMETRY_DISABLED = '1'
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open localhost:3000, log in or manually accept an issued invitation, explicitly
select a readable frozen snapshot, then ask a question. Empty corpus is an honest
blocked question state. Backend/database/provider settings and secrets stay on
the server; never use NEXT_PUBLIC_BACKEND_URL/GROQ_API_KEY/DATABASE_URL.

To reproduce the isolated browser integration, create an empty localhost PG DB
whose name contains `snap17_browser_test` (test credentials only), build the
frontend once, then:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://bsi:bsi_local_only@127.0.0.1:5432/bsi_snap17_browser_test'
$env:APP_ENV = 'test'
$env:LLM_MODE = 'fake'
$env:INGESTION_MODE = 'offline'
Set-Location frontend
npx playwright test --config tests/integration.config.ts
# Existing offline UI/unit suite (separate run; port 3100 must be free):
npm test
```

Install Playwright Chromium if missing via the existing Playwright CLI. The test
config launches both real servers and stops them at completion. It applies/checks
all migrations, creates synthetic identities and freezes original-backed data.
No real .env, original, password or bank/Groq key is required/copied.

## Limitations and handoff

1. Scope #29 must be agreed and merged separately; independent integration review
   must accept the report before SNAP-17 DONE. No historical FE/admin/search/mobile
   criteria or real product gate is inferred from this task.
2. Existing full npm audit reports the High braces stack-exhaustion advisory
   GHSA-vfj7-8cjw-p6xm and affected micromatch/fast-glob/@next/eslint-plugin-next
   chain. Production audit is clean. npm proposes a major plugin downgrade;
   it was not automatically applied. Follow-up for the dependency/integrator owner:
   select an upstream-compatible remediation, preserve Next tooling compatibility,
   then verify audit/lint/build. This dev dependency finding remains unresolved.
3. API contracts remain synchronous JSON and stateless. Browser abort does not
   guarantee cancellation of backend computation. Durable chat and SSE require
   separate approved contract-owner work.
4. Comparison UI exposes a compact scenario subset; optional unavailable inputs
   remain explicit missing/unknown. Backend claim/condition limitations are rendered
   as supplied, including structured text; no alternate financial model is created.
5. Next proxy does not forward/trust X-Forwarded-For. Under the current API's
   single-instance in-memory limits, proxy clients share its upstream IP window;
   user-specific windows still apply. Any trusted ingress/IP contract change
   belongs to the backend owner. No cross-instance quota/load/SLA claim is made.
6. Existing CI runs lint/types/build/PG regression/source E2E; the new real browser
   harness is opt-in and run locally here. Wiring browser artifacts/PG setup into
   release CI belongs to the SNAP-19 CI owner, not a hidden workflow change here.

S0 full acceptance remains independently evaluated. **S1 BLOCKED; S2/S3 NOT
EVALUATED; historical G1/G2 NOT PASSED.** Synthetic technical readiness is not
four-bank real release readiness.
