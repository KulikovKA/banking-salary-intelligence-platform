# SNAP-11 — Deterministic Comparison Engine

Date: 2026-10-11. Base: `790347c` (`origin/dev`, SNAP-09 acceptance merge).
Branch: `codex/snap-11-comparison`; isolated worktree `C:/Users/Kirill/Desktop/sber-snap-11`.
Implementation delivered for independent review; **not DONE**. No SNAP-14 work.

## Dependency and scope evidence

SNAP-09 implementation `609482f` was merged by PR #17 (`83b4b50`), followed by
independent acceptance in `docs/reports/SNAP-09-accepted.md`, acceptance commit
`5dcf698` and PR #18 (`790347c`). Actual `EvidenceService.read_published`, its
validation/publication code and PostgreSQL tests were inspected and exercised.
`origin/dev` exists. No dependency on archive or the parallel SNAP-10 branch.

Read README, AGENTS, MASTER_PLAN, TASKS, full SNAP-11 prompt, architecture/domain,
database/API/security contracts, acceptance criteria, SNAP-07 normalizer/registry,
Scenario/Comparison DTO and SNAP-09 code. Changed only:

- `backend/app/comparison/calculations.py`
- `backend/app/comparison/service.py`
- `backend/tests/test_comparison_golden.py`
- this report

No shared DTO, registry, normalizer, evidence service, ORM, migration, lockfile,
frontend or task-status edits. Neighbouring uncommitted files remain untouched.

## Architecture and applicability

`ComparisonService(reader, resolve_manifest, clock=...)` implements the frozen async
comparison interface. Composition injects SNAP-09 EvidenceService and a manifest
resolver; every comparison calls `read_published` again, without a result cache.
The resolver must return the exact requested manifest. SNAP-09 checks frozen
identity/hash/membership, current acquisition/storage/reuse rights, accepted
originals, extraction provenance, immutable candidate/evidence hashes and the
latest approved snapshot-scoped semantic review. Additional read-envelope checks
reject mismatched snapshot/corpus/evidence, absent review IDs and duplicate facts.
The engine neither queries raw candidates nor substitutes latest fetched documents.

All condition operators are interpreted locally, without eval, SQL or LLM. Kleene
logic: ALL is FALSE if any child is FALSE, otherwise UNKNOWN if any child is UNKNOWN;
ANY is TRUE if any child is TRUE, otherwise UNKNOWN if any child is UNKNOWN.
Missing input, invalid type/unit, unparsed condition, unknown geography or scope,
and unknown effective date remain UNKNOWN. String domains have equality/membership,
not invented lexical ordering. Numeric/date thresholds have typed comparisons.

Dates use `[valid_from, valid_to)`. Future/expired/false-condition/wrong-payer/wrong-
operation facts are inapplicable, with exclusion evidence retained. A matching
known price cannot hide an alternative with UNKNOWN applicability. Differing live
values produce conflict; identical Decimal values of different scale are deduplicated
semantically while retaining all fact/evidence links. SNAP-09 eligibility can discharge
the preserved extraction manual-review flag; it cannot discharge unparsed conditions,
unknown scope/date or missing scenario inputs.

Registry kind, payer, operation, direction and required scenario fields are reused.
Pairwise compatibility includes payer, operation, currency, unit, horizon and original
basis; conversion to money does not erase an incompatible basis. Ranges and individual
prices do not become point estimates. Separate numeric metric comparison respects
lower/higher direction; there is no weighted score or overall winner.

## Arithmetic

Financial arithmetic uses local Decimal precision 28 and traps Inexact; ambient
Decimal context is preserved. No binary float, implicit quantization or guessed
rounding rule. Intermediate precision overflow yields unknown, not silently rounded
money. Results retain Decimal strings through the frozen DTO roundtrip.

| Value | Formula |
|---|---|
| fixed / constant | `amount * multiplier` |
| percentage | `base * rate / 100 * multiplier` |
| percentage_clamped | `min(max(base * rate / 100, min_fee), max_fee) * multiplier` |
| pairwise | `left - right`, interpreted using metric direction |
| known cost components | sum of compatible known components in an explicit component set |

`0.30` means 0.30%; `100000 * 0.30 / 100 = 300`. Supported scenario bases are
`payroll_total` and `transfer_amount`. Negative fee rates/bounds are rejected for
calculation. `per_transfer` fees multiply by transfers_count; the floor/ceiling
applies to each transfer **before** multiplication. `transfer_amount` denotes a
single homogeneous transfer amount. Multiple transfers without explicit per-transfer
granularity remain unknown. Heterogeneous transfers cannot be supplied by Scenario v1.

`per_batch` is supported for an explicitly selected single-batch horizon. A periodic
scenario with a batch fee requires an unavailable batch_count and is unknown;
transfers_count and employee_count never stand in for batch_count. Other periods
must match exactly; there is no month/year conversion or currency conversion.

Money with fractional kopecks remains an unrounded estimate and cannot rank banks.
Per-transfer rounding uncertainty is tested on the unit fee before multiplication,
even when the aggregate lands on an exact kopeck. Non-RUB minor-unit/rounding rules
are absent from this contract and do not produce verified calculated cost.

`sum_known_components` receives explicit named independent components and the
required component set. It supports fixed + percentage (50 + 300 = 350), partial
known cost (300 with the fixed component missing), and empty unknown cost (None,
not zero). Different payer/operation/currency/unit/horizon cannot be summed.
Service subtotal claims always say `known_components_only`; even when all requested
fees are known, request coverage is not proof of complete bank-project cost.

## Claims and reproducibility

Every cell and pair has a claim, including absent/inapplicable/insufficient/conflicting
data. Claims carry source fact IDs, relevant evidence IDs, formula version
`comparison-decimal-v1`, canonical SHA-256 scenario hash and Decimal computed result.
`Claim.text` carries deterministic JSON text containing source values, original
operands, formula, scope/date/conditions, applicability truth, missing inputs and
sufficiency. Pairwise claims include both banks' operands, cell statuses and comparison
signatures; all available evidence from both sides is retained. An absent bank has no
fabricated evidence ID. Invalid/absent data never supports a winner.

The frozen Claim DTO has no separate operands/applicability/sufficiency fields;
JSON text is content inside its existing text field, not a new wire DTO or mandatory
downstream parser contract. A structured Claim extension requires the follow-up below.
UUID5 claim/result IDs are reproducible for identical request/publication/manifest;
generated_at is provided by the clock. Scenario hashing ignores bank selection order,
mapping key order and Decimal trailing-zero scale. Bank permutation reverses numeric
delta/direction and retains the evidence set.

## AC evidence and contract follow-ups

| Requirement | Evidence / result |
|---|---|
| Decimal fixed/percent/clamped/per-transfer/per-batch | independent arithmetic golden oracles |
| >=30 independent synthetic goldens | 71 parametrized arithmetic/applicability/AST/pairwise cases, plus independent invariants and guards |
| unknown/free/individual/conflict/date/scope/input safety | applicability, guard, conflicting-alternative and absence tests |
| fixed + percentage / partial known costs | explicit component helper goldens; public composition limitation below |
| pairwise/evidence/explanation | symmetric bank order, all six four-bank pairs, claim operands and DTO roundtrip |
| published frozen facts and isolation | 3 real migrated PostgreSQL integration tests, including two snapshot-specific reviews/publications of one candidate |
| approved numeric fact | original-backed synthetic analyst proposal -> semantic/manual review -> publish/freeze -> Decimal 100 and exact evidence IDs |
| denied/draft/current rights | draft rejected; published unknown date stays unknown; policy revocation blocks a repeated comparison |
| no LLM numeric computation | calculations/service import no provider/LLM; offline regression and synthetic E2E |

Concrete sequential follow-up to SNAP-01 contract owner, with SNAP-07/09/16 owners
integrating only after contract review/merge:

1. Add an evidence-backed independent fee-component identity/composition contract
   and mandatory cost-component coverage by operation/payer/horizon. Two published
   `payroll_credit_fee` values currently encode alternatives and must conflict;
   they cannot safely be declared fixed + percentage components. Internal arithmetic
   supports the sum, but end-to-end composition/full-cost comparison is **BLOCKED**
   by the frozen public representation. No local registry or DTO fork was introduced.
2. Extend Scenario with batch_count and optional bounded transfer amounts when
   heterogeneous transfers are required. Specify whether caps apply per transfer,
   batch or horizon, and add evidence-backed fee multiplicity for per-card/per-employee
   costs. Existing fields cannot express these cases without guessing.
3. Add reviewed rounding mode, quantum and rounding stage to tariff facts, including
   source evidence. Until then fractional-unit estimates cannot produce a winner.
4. Decide a FormulaValue representation for one-sided min/max bounds; the current
   percentage_clamped validator requires both min_fee and max_fee. The current engine
   supports exactly that frozen formula; it does not invent an absent bound.
5. Add typed operands, applicability and sufficiency fields to Claim if downstream
   consumers need separately structured metadata, rather than existing text content.
   Additional arbitrary scenario conditions also need a reviewed whitelist extension.

These follow-ups are scoped limitations, not completed AC or fabricated PASS. The
existing representable comparison engine is reviewable independently. SNAP-11 remains
pending independent acceptance; integrator owns MASTER_PLAN/TASKS status updates.

## Validation

Dedicated PostgreSQL 18 database `bsi_snap11_test`; separate E2E database
`bsi_snap11_e2e_test`. Both newly created, separate from SNAP-10 and product data.
No SQLite substitution. No originals, credentials or local artifacts added to Git.

- Ruff: PASS (`uv run ruff check .`).
- mypy: PASS, 63 source files (`uv run mypy backend/app`).
- Alembic clean upgrade through 0005_auth and check: PASS, no schema drift.
- Golden + PostgreSQL comparison tests: PASS, **96 passed, 0 skipped**, including
  **3 real PostgreSQL integrations** (`uv run pytest backend/tests/test_comparison_golden.py -q`).
- Regression `uv run pytest backend/tests tools/test_bank_tls_probe.py`: final
  **437 passed, 0 skipped**, 233.42s. Initial run before the last refinements:
  **433 passed, 0 skipped**. Overlapping runs are not added together.
- Docs validator: PASS, all 19 prompts, links, DAG/statuses and source decisions.
- Existing synthetic source-recovery E2E: PASS_SYNTHETIC_ONLY, network_requests=0,
  missing/orphan blobs=0; run `94ca783fa51d40cca6b55101d690dd9e`. Called the existing
  harness directly with its session factory against the separately migrated isolated
  test database; CLI's fixed-name DB allowlist was not edited. Local artifact:
  `.local/snap11-e2e/94ca783fa51d40cca6b55101d690dd9e/result.json` (ignored).
- Frontend lint/typecheck/build/browser E2E: NOT RUN; no frontend changes or accepted
  external UI implementation in this task.
- Real bank/provider evaluation and real pair coverage: NOT RUN; source/provider
  approvals and human real gold absent; SNAP-18 owns those evaluations.

S1 BLOCKED; S2/S3 NOT EVALUATED; historical G1/G2 NOT PASSED. Technical synthetic
checks do not imply complete S0 or four-bank product acceptance.
