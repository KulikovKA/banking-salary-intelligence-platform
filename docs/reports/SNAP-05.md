# SNAP-05: XLSX parser delivery

## Result

Implemented a deterministic offline XLSX parser using openpyxl, compatible with the frozen SNAP-01 `Parser` protocol. The parser verifies the original SHA-256 and existing ingestion format policy before opening a workbook. It never evaluates formulas, macros, or external links.

Base: `main` at `504c71f` (includes merged SNAP-04). Branch: `codex/snap-05-xlsx`.

## Changed files

- `backend/app/parsing/xlsx.py`: bounded XLSX extraction, deterministic block IDs and extraction hash, exact sheet/cell/range locators, formula and cached-value fields, tables, merged headers, footnotes, hidden-sheet and mixed-type diagnostics.
- `backend/tests/test_parsing_xlsx.py`: synthetic workbook coverage for Russian text and decimal-comma strings, percentage formatting, tables, merged headings, footnotes, hidden sheets, formulas with and without cached values, stable hashes, corrupt archives, external relationships, ZIP bombs, file/cell/dimension limits.
- `pyproject.toml`, `uv.lock`: openpyxl runtime dependency and openpyxl typing stubs for development checks.

## Acceptance evidence

| Criterion | Result | Evidence |
|---|---|---|
| Parser Protocol and local-original hash check | PASS | `XlsxParser` implements `Parser`; mismatch test returns `XLSX_ORIGINAL_HASH_MISMATCH`. |
| Sheets, cells, merged ranges, tables and locators | PASS | Synthetic workbook asserts sheet names, `B3`, merged `A1:B1`, table range `A2:B4`, and exact formula locator. |
| Hidden sheets and mixed types | PASS | Hidden sheet content is retained and hidden/mixed-column diagnostics are asserted. |
| Footnotes and uncertain relationships | PASS | Marker and candidate relation are preserved with manual-review diagnostics. |
| Formula handling | PASS | Formula stays in `locator.formula`; cached result is preserved separately; missing cache stays `None` and is flagged. |
| Macros/external links and resource abuse | PASS | Existing `check_format` rejects external relationships and macro/unsafe package entries; tests cover external links, corrupt ZIP, ZIP bomb, file size, cell count, and dimensions. |
| Percentages and Russian-language values | PASS | Numeric percent formatting and a Russian decimal-comma string remain distinct, unchanged extracted text. |
| Determinism | PASS | Repeated parsing yields the same extraction hash and block IDs. |

## Checks

- `uv run ruff check .` — PASS.
- `uv run mypy backend/app` — PASS.
- `uv run pytest backend/tests -q` — 178 passed, 15 skipped on the full run. All 15 skips are PostgreSQL integration tests because `TEST_DATABASE_URL` is not configured. The XLSX-specific suite passes all 5 tests after final parser changes.
- `python tools/validate_docs.py` — PASS after the report was added.
- PostgreSQL integration checks — NOT RUN; dedicated test database URL unavailable.
- Frontend checks — NOT RUN; frontend was not changed.

## Boundaries and next step

Only synthetic fixtures were used; no real originals, bank access, or provider calls were involved. This parser result does not claim product S0/S1/S2/S3 acceptance. The integrator should update task status after merge; `MASTER_PLAN.md` and `TASKS.json` were intentionally left unchanged.

Implementation commit: `6fcf51d9e7f3efad2bd199d01bd4ff5817e26c8b`.

## Integrator review corrections (2026-10-10)

Sparse workbooks could pass the populated-cell cap while iter_rows materialized
up to 50 million empty cells. The v2 parser bounds worksheet dimensions and the
sum of materialized rectangles in XML preflight, before opening with openpyxl;
it also checks loaded dimensions. Numeric cells now retain raw numeric value
and number format in evidence relations so display rounding cannot erase the
underlying precision. Formula/cache behavior, exact locators, PDF dependencies
and frozen DTO/Protocols are preserved.

Locked sync/Ruff/mypy PASS. The existing cell-limit assertion now expects the
earlier rectangle-limit failure. New sparse-workbook and percent-precision tests
exercise the actual risks; final parser checks are recorded by the integrator.
