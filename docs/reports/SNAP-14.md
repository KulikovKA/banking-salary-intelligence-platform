# SNAP-14 — independent privacy / answer harness

Date: 2026-10-11 (Europe/Moscow). Status: **BLOCKED** for full SNAP-14.
The independent components below are reviewable; they are not a working question
assistant and must not be marked DONE.

Base main: `af807da2725edc1ac87e067c05b89722ef8fc99f`.
Branch/worktree: `codex/snap-14-assistant`, separate from the user's dirty workspace.
Implementation SHA: `e399ccacbf5f6baa27200c900cf97cc23268ae27`.
Draft pull request: [#23](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/23).
Branch pushed; no merge performed. The connector could not create a PR (integration
403); the existing authorized Git credential successfully created the draft via API.

## Dependency verification

`git fetch origin --prune` completed before creating the worktree. The merged main
tree has **no `backend/app/search/service.py` and no SearchService implementation**.
SNAP-10 is absent from merged runtime/report code and its merged task status is TODO.
The original workspace's local DONE status cannot substitute for merged code.
No SNAP-10 changes were copied, cherry-picked, or reimplemented.

SNAP-09 EvidenceService.read_published is merged (`609482f`, PR #17); it verifies
frozen manifest/composition, current policy and originals, reviewed proof and refs.
SNAP-11 ComparisonService is merged (`c4ce391`, PR #20), including golden tests and
its existing structured-Claim/component/rounding limitations. SNAP-12 Fake is merged;
SNAP-13 Groq and corrected per-dispatch budgeting are merged (`25c2248`, `27f7fa3`).
Their reports were checked against runtime code and included in regression testing.

[Base main CI](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38153363416)
completed successfully on the exact full base SHA. The connector returned no runs;
unauthenticated REST inspection was rate-limited. Authenticated read using the
existing Git credential confirmed this run without exposing the credential.

## Implemented independent components

- `privacy.py`: fail-closed closed-grammar minimization into canonical intent hints,
  bank codes and a metric label. Arbitrary wording produces a local clarification.
  Raw question, Scenario strings, filters, names, account numbers, payroll details,
  secrets and document prose are never copied into outgoing payloads. This is not
  a claim that regex redaction makes arbitrary free text safe. Supported wording
  includes direct fee, pairwise, document-reference and ambiguous-best questions;
  recognizing wording does not execute retrieval or answer the question.
- `render.py`: renders an already authorized Comparison Engine result into the frozen
  AnswerEnvelope. Russian status descriptions, Decimal values without calculations
  or rounding, scenario date, revision/corpus label, all conditions/limitations and
  protected relative original paths remain backend-owned. Exact manifest/source/
  extraction/raw hash/acquisition URL/date and corpus-kind checks reject mismatches.
  Missing refs exclude the whole result rather than clipping a footnote. Unknown,
  individual and conflicting cells do not become zero or an overall winner.
  HTML/Markdown control characters in prose are escaped; structured evidence and
  conditions remain intact data that the downstream UI must also render as text.
- `service.py`: deliberately named **ComparisonAnswerHarness**, supports Fake only
  and has no AssistantService, HTTP endpoint, intent invocation or search substitute.
  Its caller must provide a current frozen-read/access guard and trusted engine
  result/validated refs. The guard runs before model work and after a delayed model
  response. Outgoing explain payload has only opaque backend claim IDs/template IDs.
  Existing SNAP-12 validation is repeated even for an adapter returning unvalidated
  output. Reordering cannot omit claims. Extra numeric/prose/URL fields, unknown IDs
  and unsafe templates are rejected; typed errors/deadline produce the same engine
  result and evidence with fallback status. Insufficient data remains insufficient.
  Metadata explicitly identifies Fake/offline, never an untrusted model ID.

Templates are validated as an allowlist; this harness currently uses a fixed server
layout and orders the envelope claims only. It does not implement semantic template
selection or the complete question -> intent -> search/comparison pipeline.

## Acceptance matrix

| Requested criterion | Evidence / current verdict |
|---|---|
| Direct fee question | Closed-grammar minimization tested; end-to-end answer NOT RUN / BLOCKED by SNAP-10 |
| Pairwise / 80-employees contextual scenario | Existing engine regression plus independent result rendering; question orchestration NOT RUN / BLOCKED |
| Missing scenario / ambiguous best | Canonical clarify hint or local clarification tested; final question clarification route NOT RUN |
| Document retrieval | Canonical document hint and deterministic relative source paths; SearchService retrieval and protected HTTP download NOT RUN |
| Out of scope | Arbitrary wording refused locally with no outgoing payload; complete domain routing NOT RUN |
| Unknown applicability | Original-backed PG published unknown scope/date stays insufficient; unit uncertain-cell rendering does not invent zero/current price |
| Missing evidence / incomplete footnote | Entire result excluded, no numeric prose/claims/sources |
| Conflicting / individual tariffs | Renderer retains explicit statuses and individual text; engine conflict/individual goldens included in regression |
| Fabricated URL / cross-snapshot refs | Provenance, raw hash, extraction, source version, revision, snapshot and synthetic-to-real mismatch rejection tests |
| Changed LLM number / prose / wrong claim | Unvalidated fake adapter returns extra amount/URL/text/unknown ID/unsafe template; local validation forces fallback |
| Injected footnote / PII canaries | Raw condition is escaped/preserved locally, never copied to outgoing messages/schema; Scenario and arbitrary question canaries excluded |
| Timeout / 429 / invalid JSON | All seven typed error fixtures, malformed JSON, and actual wait_for cancellation tested; no provider network |
| Deterministic fallback | Fixed generated_at repeated rendering equal; engine comparison/claims/evidence preserved on model failures |
| Snapshot access and revocation | Guard-before-model and guard-after-model tests; actual PG policy revoke blocks repeated authorized read |
| Full Groq intent/explain / quotas / real corpus | NOT RUN. Groq is explicitly rejected by the offline harness; full composition remains pending |

The tests are independent safety-component evidence, not a fabricated PASS for
blocked end-to-end AC. Pure rendering is not an authorization/evidence validator:
the future orchestrator must obtain results exclusively through published reads,
resolve exact refs from the DB, verify them against the reviewed proof/chunks and
apply session authorization. Clients/models must never supply these trusted inputs.

## Configuration and validation

Existing `.env` was found in the original workspace. It was neither copied, modified
nor committed. Settings validation reports invalid `LLM_MAX_INPUT_TOKENS` and
`LLM_MAX_OUTPUT_TOKENS`; values are intentionally omitted. The current Settings
ceilings are 4000 input / 1000 output. No provider call was authorized or made.
Tests safely load only the existing DB configuration in memory, replace the DB
name with a newly created dedicated DB and force test/offline/Fake process settings.
No new `.env`, secret artifact or bank original was created.

Dedicated PostgreSQL 18.6: `bsi_snap14_test_20261011`, separate from application and
other task DBs. All existing Alembic migrations applied through `0005_auth`.

- `uv sync --locked`: PASS; dependency files unchanged.
- Alembic upgrade head: PASS; Alembic check: PASS, no new upgrade operations.
- `uv run ruff check .`: PASS.
- `uv run mypy backend/app`: PASS, 66 source files.
- Relevant new suite on migrated PostgreSQL: **46 passed, 0 skipped** (6.75s),
  including one actual original/review/publication/frozen-read/engine/render/revoke test.
- Full backend + TLS probe regression: **483 passed, 1 skipped** (235.69s).
  The existing `/proc` process-state check is Linux-specific and skipped on Windows;
  this is an explicit platform skip, not PASS for that check. All PG tests ran.
- `uv run python tools/validate_docs.py`: PASS, 19 prompts, links, DAG/status checks.
- Base CI: PASS on the exact base commit linked above. At this report update,
  [branch CI](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38155051033)
  for `95d254d13fd1b59da9c008e85f54fa07b88ed8f3` is in progress, not claimed PASS.
- `git diff --cached --check`: PASS; staged paths are exactly the five owned files.

Development failures were corrected before review: an inferred status needed a
Literal annotation; empty known-component calculations have null computed_result
and are not numeric facts; Windows asyncio creates a loop-local socketpair before
the egress-denial test body; the existing review helper returns an ID string.
An initial no-DB unit run's skip is superseded by the final migrated PG run.
Overlapping test counts are not added together.

NOT RUN: frontend lint/typecheck/build/browser E2E (no frontend edits), full question
E2E (missing search dependency), standalone source-recovery E2E repeat (ingestion
unchanged and complete backend regression covers existing tests), real corpus/
bank/Groq requests and real-model quality evaluation. No scheduler, migration,
DTO, config, lockfile, frontend, TASKS.json or MASTER_PLAN edit was made.

## Required handoff before completing SNAP-14

1. SNAP-10 owner/integrator: merge the existing SearchService, relevant PostgreSQL
   tests and report into main; supply its accepted exact revision. Local DONE alone
   does not meet the start condition. Do not close SNAP-14 from this draft harness.
2. Resume SNAP-14 on that merged base: wire published-read access, privacy/intent,
   metric whitelist and typed bounded Scenario patch validation, facts/documents
   retrieval, scenario comparison and local clarification. Resolve reviewed exact
   EvidenceRefs and propagate the complete request deadline. Integrate existing
   Groq question_scope and authenticated budget user only after a verified processing
   decision; preserve shared call/token caps. Add actual direct/pairwise/scenario/
   missing-scenario/documents/out-of-scope PG question tests.
3. Frozen contract owner / SNAP-16: separately decide optional corpus_kind/model
   metadata fields and typed Claim operands/applicability/sufficiency (SNAP-11's
   existing follow-up). Current fields stay unchanged; corpus/model appear in text.
   Authenticated download URLs are deterministic targets; an endpoint and functioning
   downloadable original require SNAP-16, not this helper.
4. Product wording/layout: complete readable Russian explanations of engine condition
   JSON and less common value unions. Raw structured conditions remain available and
   are not silently shortened to meet a model budget. Current fixed layout is a harness.

Product gates: full S0 not completed; **S1 BLOCKED; S2/S3 NOT EVALUATED;
historical G1/G2 NOT PASSED**. Synthetic component tests do not accept real data.
