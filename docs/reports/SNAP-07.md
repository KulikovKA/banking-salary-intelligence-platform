# SNAP-07 — Tariff normalization and metric registry

**Result:** implementation ready for review; this report does not update the plan status.
**Base commit:** `ea6ae1a` (`main`).
**Branch:** `codex/snap-07-tariffs`.
**Implementation commit:** `440e3907867ec2afd1931f3d1bc7b1751b3dbc27`.
**Worktree:** `C:\Users\Kirill\Desktop\sber ai assisnent-snap-07-tariffs`.
**Scope:** `backend/app/tariffs/{__init__,metrics,normalize}.py`,
`backend/tests/test_tariff_normalization.py`, and this report.

## Behavior delivered

- Added an immutable registry for the ten v1 metrics named by `DOMAIN_CONTRACTS.md`.
  Entries define allowed value kinds and units, payer, operation, comparison direction,
  and required scenario fields. Candidate normalization rejects unknown metrics and
  incompatible payer/operation/value semantics.
- Added pure normalization from candidate mappings to the frozen SNAP-01
  `TariffCandidate`, or to deterministic diagnostic flags. No filesystem, network,
  database, LLM, or runtime service is used.
- Decimal strings accept decimal commas and grouped RUB amounts. `0,30%` becomes
  `Decimal("0.30")` percent; it is not divided by 100. Floats and malformed values
  are rejected by the existing strict decimal contract.
- Unknown amounts return `VALUE_UNKNOWN`; they never become zero. A zero fee requires
  explicit conditions wording under the frozen contract. Conditional-free wording is
  retained, marked `CONDITIONS_UNPARSED`, and sent for manual interpretation. Free
  wording without explicit RUB currency remains unknown.
- Ranges preserve decimal bounds and open-ended lower/upper limits; reversed bounds
  are rejected. Individual tariff text remains an `individual` value.
- Payer, operation, period, basis, units, geography, and scope are kept distinct.
  Missing required payer/operation/basis/currency is flagged instead of inferred.
- Conditions are validated through the frozen restricted condition AST. Invalid ASTs
  are rejected; no `eval`, SQL, or Python expression parsing is used.
- An explicitly inclusive end date is advanced by one day to the contract's exclusive
  `valid_to`. Original date wording is returned separately in `NormalizationResult`.
  Unknown dates remain unknown; future dates are preserved as supplied.
- Re-normalizing a candidate dump is idempotent.

## Acceptance evidence

| SNAP-07 criterion | Evidence | Result |
|---|---|---|
| Registry covers the contract's ten metrics | `test_registry_matches_domain_contract_metric_set_and_is_read_only` | PASS |
| Decimal comma, RUB, and 0.30% scale | decimal and RUB tests in `test_tariff_normalization.py` | PASS |
| Unknown/malformed fee never becomes zero | unknown, malformed, and zero-without-wording tests | PASS |
| Conditional free differs from unconditional free | conditional/unconditional free tests; manual flag and wording assertions | PASS |
| Range, open bounds, and individual tariff | range boundary and individual tests | PASS |
| Employer and employee payer are not mixed | payer compatibility test | PASS |
| Per-transfer and per-batch periods stay distinct | period preservation test | PASS |
| Explicit inclusive dates become exclusive; unknown/future dates stay explicit | date boundary, unknown, and future-date tests | PASS |
| Restricted AST, invalid units/metrics, and no guessed scope | AST, semantic mismatch, and unknown scope assertions | PASS |
| Normalization is deterministic/idempotent | candidate dump roundtrip test | PASS |

## Checks

- `uv run ruff check .` — **PASS**.
- `uv run mypy backend/app` — **PASS**, 35 source files checked.
- `uv run pytest backend/tests/test_tariff_normalization.py -q` — **PASS**, 22 passed.
- `python tools/validate_docs.py` — **PASS**, standalone links, 19 prompts, DAG/statuses,
  and source decisions validated.
- `git diff --check` — **PASS**.
- PostgreSQL integration — **NOT RUN**: SNAP-07 adds no persistence/schema behavior,
  and the dedicated database integration path is outside these pure normalization tests.
- Frontend lint/typecheck/build and browser E2E — **NOT RUN**: no frontend files changed.
- Bank/Groq access and real corpus evaluation — **NOT RUN**: this task uses synthetic
  fixtures only and adds no source acquisition or provider behavior.

## Limits and handoff

The normalizer returns typed candidates or flags; it does not approve, publish, compute
tariffs, infer omitted evidence, or establish real corpus acceptance. Raw inclusive-date
wording is kept in the normalization result for downstream evidence handling; the frozen
candidate contract itself has no field for raw date wording. Schema, ORM, migrations,
contracts, `MASTER_PLAN.md`, and `TASKS.json` were not changed.

Product gates remain independent: no S0/S1/S2/S3 or G1/G2 PASS is claimed. The
integrator should review/merge the branch and update only the SNAP-07 task status when
its merge and acceptance criteria are complete.
