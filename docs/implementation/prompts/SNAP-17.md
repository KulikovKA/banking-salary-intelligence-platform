# SNAP-17 ? Desktop Chat ? FastAPI Integration

Reasoning: high. Read README, MASTER_PLAN, API_CONTRACTS, SECURITY and acceptance
criteria. User scope supersedes the historical external-frontend plan: reuse the
merged PR #24 desktop chat and SNAP-16 API from PR #28; do not wait for an external
frontend or build another UI. No dashboard/admin review UI/cabinet/mobile work.

Prepare the separate scope proposal in MASTER_PLAN/TASKS/FRONTEND_HANDOFF first;
new chat-only criteria require agreement and separate merge before formal closure.
Do not mark historical FE-01?FE-04 passed or SNAP-17 DONE. SNAP-16 acceptance/status
belongs to the integrator after code/report/CI verification.

Owned paths: frontend/app/**, components/**, styles/**, lib/client.ts, lib/chat/**,
tests/**, next.config.ts and existing frontend config/lockfiles when necessary;
report docs/reports/SNAP-17.md. Backend and generated api-contracts.ts read-only.
Public contract follow-up goes to SNAP-16 owner; no hidden DTO/schema fork.

Implement server-only same-origin proxy preserving cookie and browser Origin.
Compact login/invite/me/session-CSRF/logout/expiry; HttpOnly sessions, no stored
browser credentials, clear chats on logout/expiry. Explicit frozen snapshot
selection with corpus kind/revision/date/coverage; no implicit latest. Empty state
blocks questions. BackendChatTransport POST questions -> AnswerEnvelope using
frozen types; retain demo only explicit development. JSON is not SSE; abort only
promises cancellation of client request. Preserve all bank/value/status unions,
conditions/missing inputs/limitations/claims/safe protected originals/revision/date;
no frontend tariff computation/winner and unknown is not zero. Typed safe errors
401/403/404/409/422/429 Retry-After/503/timeout/network.

Retain existing tests and add real browser Next -> proxy -> FastAPI -> dedicated
migrated PostgreSQL -> synthetic frozen corpus -> Fake E2E. Cover auth/invite,
expiry/logout, Origin/CSRF, snapshots/question/table/originals/fallback/empty/error,
XSS, zero bank/Groq calls and no frontend secrets. Run frontend lint/typecheck/build,
ruff/mypy/relevant PG pytest and docs validator. Report exact counts and honest
FAIL/SKIP/NOT RUN; synthetic never proves real gates.

Use isolated branch/worktree from current origin/main; no subagents or neighbor
overwrite. Prepare scoped commits, push and PR without merge when authorized.
Report base/revisions/architecture/local run/AC evidence/limitations; independent
acceptance and separately merged criteria are required for DONE.

## Registry fields (scope proposal)

Existing PR #24 desktop chat connected to SNAP-16; proposed chat-only criteria pending separate integrator agreement/merge and independent acceptance.

Reuse existing ChatShell/sidebar/messages/composer/table/reducer. Server-only same-origin proxy; login/invite/logout/expiry/CSRF; explicit frozen snapshot; typed BackendChatTransport and evidence-preserving AnswerEnvelope/ComparisonResult adapter. Demo only explicit development mode. No second UI, dashboard, admin review UI, cabinet or mobile adaptation. Backend/frozen DTO read-only.

Proposed chat-only AC in FRONTEND_HANDOFF require separate agreement/merge before formal closure. Real browser Next.js -> FastAPI -> dedicated migrated PostgreSQL -> synthetic frozen snapshot -> Fake E2E: auth/CSRF/Origin/snapshot/question/table/documents/fallback/empty/errors/XSS. Lint/typecheck/build, regression and docs checks; no secrets or bank/Groq network. Historical FE criteria are not automatically DONE.

Single frontend owner, isolated branch/worktree; no subagents. Existing merged PR #24 replaces external handoff requirement under user-approved scope. Backend/api-contracts.ts read-only. Integrator owns task statuses after acceptance.
