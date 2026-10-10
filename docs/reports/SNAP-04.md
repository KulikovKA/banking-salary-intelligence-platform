# SNAP-04 — PDF parser report

**Result:** offline PDF parser and synthetic test harness implemented. This module result does not change S0–S3, G1/G2, source permissions, or product acceptance.

**Base:** `ea6ae1a2f2f174981d8706b88a6192361d56df8b` (`main`).  
**Branch:** `codex/snap-04-pdf`.  
**Commit:** recorded in Git after the implementation/report are committed.

## Behaviour

- `PdfParser` implements the frozen `Parser` Protocol and accepts only a local path. It verifies the full original SHA-256 against `ParseRequest` before opening it; no URL, network, OCR, LLM, or PDF renderer is used by the parser.
- Immutable `ParsedBlock`s preserve page text line-by-line and table content cell-by-cell. PDF locators use one-based physical page numbers, page-space bounding boxes, and row/column cell coordinates. Stable UUID5 block IDs and canonical JSON extraction hashes repeat for the same bytes and parser version.
- Ruled tables retain header cells and emit review-required header relations for data cells. The parser keeps text inside a detected table if cell assignment is uncertain and emits `PDF_TABLE_TEXT_UNASSIGNED`, instead of silently dropping it. Conditions in table cells and page text remain verbatim after whitespace normalization.
- Detected footnote markers and references are preserved with `review_required=true`; inferred links also emit `PDF_FOOTNOTE_RELATION_UNVERIFIED`. The parser does not assert that a visual association is correct.
- Common English/Russian printed page labels are retained as `printed_page_label` relations on their text blocks. They do not replace `PdfLocator.physical_page`; the test fixture deliberately uses printed label “Page 1” on physical page 2.
- Image-only pages return `needs_ocr`; a mixed text/image document returns `ok` with scan diagnostics. Encrypted PDFs return `unsupported`; corrupt/unreadable input and configured resource limit excesses return `failed` with distinct diagnostic codes.
- Parser limits: original bytes 50 MiB, 500 physical pages, 10,000,000 extracted text characters, and 100,000 nonempty table cells. OS-level memory/CPU isolation and wall timeout belong to the future pipeline runner; this synchronous parser does not claim to enforce those limits.

## Files

- `backend/app/parsing/pdf.py` — parser, deterministic IDs/hash, locators and diagnostics.
- `backend/tests/test_parsing_pdf.py` — generated multi-page, encrypted, corrupt, image-only, and quota PDFs; no bank originals are used.
- `pyproject.toml`, `uv.lock` — pinned compatible `pdfplumber` dependency and its `pdfminer.six` dependency tree.
- `docs/reports/SNAP-04.md` — this report.

## Dependency license inventory delta

Resolved by `uv.lock` and inspected in installed distribution metadata/license files:

| Distribution | Locked version | License evidence |
|---|---:|---|
| pdfplumber | 0.11.10 | MIT classifier and bundled MIT license |
| pdfminer.six | 20260107 | bundled MIT license; no SPDX/license classifier in the package metadata |
| pypdfium2 (transitive) | 5.14.0 | BSD-3-Clause and Apache-2.0; distribution also carries third-party component notices |
| Pillow (transitive) | 12.3.0 | bundled Pillow license text; package metadata has no SPDX/license classifier |

The existing `docs/reports/license-inventory.*` was not rewritten. This is a metadata/license-file delta for the added dependency tree, not a legal determination; pypdfium2 is not called by this parser.

## Acceptance evidence

| Criterion | Evidence | Result |
|---|---|---|
| Multi-page PDF, physical pages, text/table/header/condition/footnote evidence | Generated two-page fixture; asserts physical pages 1 and 2, extracted cell/header and full conditional quote, footnote relation flagged for review | PASS |
| Locator reproduces a quoted table cell; stable parser version/hash/IDs | Reopens the generated PDF, crops by emitted bbox and checks the full quote; repeats parse and compares extraction hash and block IDs | PASS |
| Printed label remains distinct from physical page | Page 2 carries printed “Page 1”; relation retains it while locator remains physical page 2 | PASS |
| Scanned, encrypted, corrupt, and over-quota inputs have typed outcomes | Generated image-only page, encrypted PDF, invalid PDF, page/text/table-cell/file-size limit cases | PASS |
| Offline/no-egress parser | Test denies socket connections while parsing generated local bytes | PASS |
| No condition loss from uncertain table-cell assignment | Unassigned text inside detected table is retained as a block with review diagnostic; conditions are asserted from fixture | PASS |
| Full extraction subprocess CPU/memory/time isolation | Requires the later pipeline runner; parser-side byte/page/text/cell caps are implemented | NOT RUN / deferred to pipeline runner |
| Printed-label field in shared locator DTO | Frozen `PdfLocator` has no printed-label field. Label is available losslessly in block relations. No contract changed. | Follow-up requirement below |

### Exact frozen-contract follow-up

If downstream evidence locators must carry printed labels after block relations are discarded, extend `PdfLocator` with an optional `printed_page_label: str | None` field and preserve it through `Chunk` and `EvidenceRef`. Until the contract owner accepts that additive DTO change, this parser stores the label in `ParsedBlock.relations` and keeps physical page in `locator.physical_page`.

## Checks

- `uv run ruff check .` — PASS.
- `uv run mypy backend/app` — PASS, 33 source files.
- `uv run pytest backend/tests -q` — 106 passed, 9 skipped. The 9 PostgreSQL integration cases are **NOT RUN** because `TEST_DATABASE_URL` is unset; no SQLite replacement was used.
- `uv run python tools/validate_docs.py` — PASS: standalone main links, 19 snapshot prompts, DAG/statuses and source decisions.
- PDF-specific `uv run pytest backend/tests/test_parsing_pdf.py -q` — 5 passed.
- Frontend checks — NOT RUN; frontend was not changed.
- Bank, Groq, and real-original requests — none.

## Limitations and next step

Table detection currently uses ruled-line geometry. Borderless tables remain preserved as page text but may not have cell/header relations. Footnote and printed-label recognition is heuristic and requires review where the parser emits a relation diagnostic. The S0 synthetic acceptance gate is not claimed as complete: the rest of the new pipeline and product acceptance gates are outside SNAP-04. The pipeline-runner owner should execute this parser in a resource-limited local subprocess before processing untrusted large originals.
