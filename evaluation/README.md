# Snapshot evaluation

This module scores immutable, captured observations against a byte-pinned gold
dataset. It does not import documents, grant rights, approve facts, freeze
snapshots, send questions to Groq, or certify product gates. Runtime contracts,
parsers, search and comparison remain owned by their existing modules.

`schema.py` and the exported [gold schema](gold.schema.json) and
[observations schema](observations.schema.json) define the capture format. Gold
contains independently reviewed facts, exact evidence/chunk/locator expectations,
questions/relevant chunks, comparison input records and independently specified
stable expected results. Real human review IDs must refer to actual review records.
The synthetic fixture deliberately has **zero human reviews**. Scope, date,
status, Decimal value, payer, operation, period and required conditions are explicit.

Facts, questions and comparisons have a `family` and `split`. A document family
cannot occur in both tune and holdout. All quality metrics score holdout only;
minimum dataset sizes and all six pair coverage are reported separately. An
unknown/individual/conflict value never contributes numeric employer cost coverage.
The coverage entry records the analyst's applicability decision; the evaluator
also checks referenced banks, statuses, common scope/date/conditions and value
dimensions. It is not an independent semantic review of originals.

Gold SHA-256 is calculated over exact file bytes, including whitespace. Freeze
and independently record the hash before final capture. Observations bind to
that hash. Generated JSON uses LF with scoped Git attributes so checkout on
Windows/Linux preserves pinned bytes. Observations additionally bind to
that hash, snapshot ID, revision and corpus kind. Missing observations count as
incorrect; duplicates, unknown IDs and binding mismatches are rejected. No zero
denominator returns PASS. Integer cross multiplication decides thresholds without
rounding. Condition recall and retrieval recall are micro averages; repeated hits
do not increase recall and only the first ten ranks count.

`run` scores a capture. `compare` executes the existing merged ComparisonService
using synthetic records and a fixed clock. Its reader is a synthetic fixture
double, not an accepted publication service. Expected comparison outputs were
authored without calling the engine. Stable projections include complete value
DTOs, statuses, missing inputs and pairwise deltas; clock/IDs/narrative are excluded.
The effective observations hash records the actual engine output separately from
the input capture hash.

The positive synthetic capture authors extraction/evidence/retrieval/intent
observations; those scores test the **evaluator**, not extraction/FTS/model quality.
Actual parsing, evidence, PostgreSQL FTS, assistant and provider-error integrations
are checked by the existing backend regression suite. No real-model success is
inferred from MockTransport or Fake.

Unsupported claims/numbers are assessed against the gold's allowed structured
claim IDs and numeric tokens. This is not a free-prose semantic hallucination
detector. A real capture owner must independently annotate those lists from all
rendered assertions and numbers, and document the capture/review provenance.
Real-model observations may record model ID, tokens, latency, error and fallback;
fallback/error never counts as a correct model intent. Raw sensitive questions,
reasoning traces, keys and undisclosed originals must not be captured.

`audit` reads literal settings from the existing env file without copying or
printing them. It searches only explicitly supplied roots plus configured
storage, hashes local files and uses a PostgreSQL repeatable-read read-only
transaction. It rolls back and never upgrades the application DB. Its private
output must be inside an ignored `.local` directory. SQL failure messages are
replaced with exception classes. A missing table is NOT RUN, not a zero count.

Run from the worktree in PowerShell:

```powershell
uv sync --locked
$goldHash = (Get-Content evaluation/fixtures/synthetic-gold.sha256).Trim()
uv run python tools/evaluate_snapshot.py compare `
  --gold evaluation/fixtures/synthetic-gold.json --gold-sha256 $goldHash `
  --observations evaluation/fixtures/synthetic-observations.json `
  --output .local/evaluation/synthetic
uv run python tools/evaluate_snapshot.py run `
  --gold evaluation/fixtures/synthetic-gold.json --gold-sha256 $goldHash `
  --observations evaluation/fixtures/synthetic-faulty-observations.json `
  --output .local/evaluation/faulty
# Expected exit codes: positive 0; faulty 1; invalid/schema/hash/provenance 2.
uv run pytest evaluation -q
```

Use `--allow-real-local-output` only after independently documented local
storage/reuse admission; it is an operator acknowledgement, not permission creation
or verification. Real input/output stays outside Git, in `.local`. Product gate
statuses remain external acceptance work even when capture metrics pass. This
module intentionally cannot automatically declare S1/S2/S3 PASS from JSON labels.
`build_synthetic.py` is an authoring utility, not part of final evaluation; changing
gold requires a new frozen hash/review and new capture, not threshold adjustment.
