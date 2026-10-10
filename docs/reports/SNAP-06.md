# SNAP-06 — HTML parser report

## Result

Implemented an offline parser for an already stored HTML original. It verifies the
original SHA-256, decodes BOM/meta/recorded encodings, and extracts static headings,
paragraph-like text, captions, table cells, footnotes, and anchor text. Every block
has a deterministic `HtmlLocator.element_path`; table blocks carry row/column,
header/data, span, caption, and link relations. Text is whitespace-normalized with
Unicode code-point offsets measured against the resulting immutable block text.
The parser does not create tariff facts: marketing copy remains ordinary evidence
text for later review.

`script`, `style`, `nav`, `noscript`, and `template` content is excluded. Links and
image sources are never resolved. Parsing uses only Python's standard library and
the supplied local file. Common malformed table markup is recovered with a
diagnostic; empty or script-only pages return `unsupported`.

## Scope and base

- Base: `main` commit `504c71f`.
- Branch/worktree: `codex/snap-06-html` / `C:\Users\Kirill\Desktop\sber-ai-assisnent-snap-06-html`.
- Shared Parser Protocol and DTOs were not changed.
- Plan statuses were not changed.

## Changed files

- `backend/app/parsing/html.py`
- `backend/tests/test_parsing_html.py`
- `backend/tests/fixtures/parsing/html/complex.html`
- `backend/tests/fixtures/parsing/html/malformed.html`
- `backend/tests/fixtures/parsing/html/empty-dynamic.html`
- `docs/reports/SNAP-06.md`

## Acceptance evidence

| Criterion | Result | Evidence |
|---|---|---|
| Cyrillic and HTML entities | PASS | `complex.html` preserves Cyrillic, `&nbsp;`, punctuation, and exact numeric strings after documented whitespace normalization. |
| Headings, text, captions, footnotes, links | PASS | Synthetic extraction asserts each class; link destinations are metadata only and are not requested. |
| rowspan/colspan and nested tables | PASS | Assertions cover span metadata, shifted columns in a later row, two distinct table IDs, and nested-cell content. |
| Stable locators and quote offsets | PASS | Parsing identical bytes twice yields identical block IDs, element paths, and extraction hash; quote offsets are checked against Unicode `block.text`. |
| Excluded active/ancillary content and no network | PASS | Fixture includes script, nav, and external image; socket connection entry points are patched to fail if called. Excluded text is absent. |
| Marketing claims are not tariff facts | PASS | Parser output consists only of `ParsedBlock` evidence; test confirms marketing text is retained as ordinary text and no candidate/fact is emitted. |
| Malformed and dynamic content | PASS | Malformed fixture yields usable cell text plus `HTML_MALFORMED`; script-only fixture returns `unsupported` with `HTML_NO_STATIC_CONTENT`. |
| Encoding and original integrity | PASS | Windows-1251 declared in the fixture is decoded; a wrong source hash returns `failed`. |

## Checks

| Check | Result |
|---|---|
| `uv run ruff check .` | PASS |
| `uv run mypy backend/app` | PASS — 42 source files |
| `uv run pytest backend/tests/test_parsing_html.py backend/tests/test_parsing_pdf.py -q` | PASS — 10 tests |
| `python tools/validate_docs.py` | PASS — standalone main links, 19 prompts, DAG/statuses, source decisions |
| PostgreSQL integration | NOT RUN — parser unit tests require no database and no schema interaction |
| Frontend lint/typecheck/build | NOT RUN — no frontend paths changed |

## Limits and follow-up

This parser intentionally handles static HTML with a small standard-library tree
builder, not browser rendering or full HTML5 error recovery. It does not execute
JavaScript, inspect computed visibility, resolve external resources, or infer tariff
semantics. Offsets are derived from normalized immutable block text because the
frozen ParsedBlock contract has no offset field. The extraction pipeline can create
quote start/end offsets directly against that block text.

Implementation commit: `5bfa65cfd652279c43678b0323051085a8167ee8`.

## Integrator review corrections (2026-10-10)

Table-cell anchors previously lost their footnote target metadata; v2 retains
target/path and marks the relationship for review. Deep untrusted markup could
raise RecursionError during block extraction; tree depth/nodes/text are now
bounded before traversal. Sibling path indexing uses counters instead of scanning
all previous siblings. Parser version advances to `stdlib-html/2` because evidence
serialization changed. No network or JS was introduced.

Checks: HTML/PDF regressions 12 passed; Ruff/docs PASS. One intermediate mypy
variable-type error was corrected before the final mypy check.
