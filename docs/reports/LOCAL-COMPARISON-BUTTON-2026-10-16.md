# Local comparison button fix

Scope: the existing opt-in local Groq demo. No production API, provider, database,
migration, acquisition permission, or release-gate changes.

The reported welcome action submits `Сравнить зарплатные проекты банков`.
The first diagnostic replay succeeded; the earlier intermittent 502 was not
captured with its internal validation reason. The old comparison schema allowed
citations to omit a bank, while response validation rejected that omission.
Comparison output now requires separate citation lists for every selected bank,
with IDs restricted to that bank's retrieved excerpts. Backend validation still
rejects missing, unknown, or cross-bank references. The external response format
is unchanged. No automatic provider retry or fabricated success was introduced.

Together with the preceding uncommitted retrieval fix, comparisons receive fee,
applicability/service, and limitation sections rather than document introductions.
The existing live error panel now uses dark-theme colors.

Validation:

- `uv run ruff check .`: PASS.
- `uv run mypy backend/app`: PASS, 75 source files.
- Relevant local-demo and Groq pytest suites: 40 passed, offline.
- `python tools/validate_docs.py`: PASS.
- Frontend lint, build, typecheck: PASS.
- UI browser suite: 4 passed, mocked and offline; includes clicking the exact
  comparison suggestion, retry behavior, and dark error background.
- One real browser click after restart: HTTP 200, configured Groq model,
  four banks, 12 retrieved excerpts, 8 validated citations, no browser errors.
  Local screenshot and response evidence are outside Git under `.local/ui-redesign`.

Limitations: citation validation checks provenance and bank coverage, not semantic
entailment of every sentence. The live response still included an overgeneralized
conclusion; this work does not certify tariff accuracy or bank recommendations.
PostgreSQL integrations were not run because this isolated demo change does not
use PostgreSQL.
