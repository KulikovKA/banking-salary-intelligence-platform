"""Deterministic, offline PDF text and table extraction."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect
from pdfminer.pdfparser import PDFSyntaxError
from pdfplumber.utils.exceptions import PdfminerException

from app.contracts.parsing import (
    ParsedBlock,
    ParseDiagnostic,
    Parser,
    ParseRequest,
    ParseResult,
    PdfLocator,
)

PARSER_VERSION = "pdfplumber/1"
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_PAGES = 500
MAX_TEXT_CHARS = 10_000_000
MAX_TABLE_CELLS = 100_000
_FOOTNOTE = re.compile(r"^\s*(?:\*{1,3}|[†‡]|(\d{1,2})[.)]|\[(\d{1,2})\])\s+")
_PAGE_LABEL = re.compile(
    r"(?i)^\s*(?:(?:page|стр(?:аница)?\.?)\s*)?(\d{1,4})"
    r"(?:\s*(?:из|/|of)\s*\d{1,4})?\s*$"
)


class PdfParser(Parser):
    """Parse a previously verified local PDF; never follows links or accesses a network."""

    def __init__(
        self,
        *,
        max_file_bytes: int = MAX_FILE_BYTES,
        max_pages: int = MAX_PAGES,
        max_text_chars: int = MAX_TEXT_CHARS,
        max_table_cells: int = MAX_TABLE_CELLS,
    ) -> None:
        self.max_file_bytes = max_file_bytes
        self.max_pages = max_pages
        self.max_text_chars = max_text_chars
        self.max_table_cells = max_table_cells

    def parse(self, request: ParseRequest, original_path: str) -> ParseResult:
        if request.kind != "pdf":
            return self._result(request, "unsupported", "PDF_KIND_REQUIRED")
        path = Path(original_path)
        try:
            with path.open("rb") as original:
                size = os.fstat(original.fileno()).st_size
                if size > self.max_file_bytes:
                    return self._result(request, "failed", "PDF_FILE_SIZE_LIMIT", f"{size} bytes")
                digest = _sha256_stream(original)
                if digest != request.raw_sha256:
                    return self._result(request, "failed", "PDF_ORIGINAL_HASH_MISMATCH")
                original.seek(0)
                with pdfplumber.open(original, pages=None, laparams=None) as pdf:
                    page_count = len(pdf.pages)
                    if page_count > self.max_pages:
                        return self._result(
                            request,
                            "failed",
                            "PDF_PAGE_LIMIT",
                            f"{page_count} pages exceeds {self.max_pages}",
                        )
                    return self._extract(request, pdf.pages)
        except PDFPasswordIncorrect:
            return self._result(request, "unsupported", "PDF_ENCRYPTED")
        except PdfminerException as exc:
            if exc.args and isinstance(exc.args[0], PDFPasswordIncorrect):
                return self._result(request, "unsupported", "PDF_ENCRYPTED")
            return self._result(request, "failed", "PDF_PARSE_ERROR", type(exc).__name__)
        except (PDFSyntaxError, ValueError, OSError) as exc:
            return self._result(request, "failed", "PDF_CORRUPT_OR_UNREADABLE", type(exc).__name__)
        except Exception as exc:  # pdfminer raises several parser-specific exception types
            return self._result(request, "failed", "PDF_PARSE_ERROR", type(exc).__name__)

    def _extract(self, request: ParseRequest, pages: Any) -> ParseResult:
        blocks: list[ParsedBlock] = []
        diagnostics: list[ParseDiagnostic] = []
        text_count = 0
        table_cell_count = 0
        previous_heading: str | None = None

        for physical_page, page in enumerate(pages, start=1):
            table_settings = {
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "snap_tolerance": 3,
                "join_tolerance": 3,
                "intersection_tolerance": 3,
            }
            tables = page.find_tables(table_settings=table_settings)
            page_tables: list[tuple[Any, list[list[str | None]]]] = []
            for _table_index, table in enumerate(tables, start=1):
                rows = table.extract() or []
                cleaned = [[_clean(cell) or None for cell in row] for row in rows]
                if not any(cell for row in cleaned for cell in row):
                    continue
                page_tables.append((table, cleaned))

            words = page.extract_words(
                keep_blank_chars=False, use_text_flow=False, extra_attrs=["fontname", "size"]
            )
            table_tokens = {
                token
                for _table, rows in page_tables
                for row in rows
                for cell in row
                if cell
                for token in cell.split()
            }
            raw_text = page.extract_text(layout=False) or ""
            text_count += len(raw_text)
            if text_count > self.max_text_chars:
                return self._limit_result(request, "PDF_TEXT_LIMIT", blocks, diagnostics)
            unmatched_table_words = [
                word
                for word in words
                if any(_inside(word, table.bbox) for table, _ in page_tables)
                and _clean(str(word.get("text", ""))) not in table_tokens
            ]
            unmatched_ids = {id(word) for word in unmatched_table_words}
            body_words = [
                word
                for word in words
                if not any(_inside(word, table.bbox) for table, _ in page_tables)
                or id(word) in unmatched_ids
            ]
            label = _printed_label(raw_text.splitlines())
            font_sizes = sorted(
                float(word["size"]) for word in words if word.get("size") is not None
            )
            page_median_size = font_sizes[len(font_sizes) // 2] if font_sizes else 0.0
            if not raw_text.strip() and not page_tables:
                diagnostics.append(
                    ParseDiagnostic(
                        code="PDF_PAGE_NO_TEXT",
                        message=(
                            f"Physical page {physical_page} has no extractable text; "
                            "OCR is not run."
                        ),
                    )
                )

            for line_words in _group_words_by_line(body_words):
                body_text = _words_to_text(line_words)
                if not body_text:
                    continue
                heading = _heading_from_words(line_words, page_median_size)
                if heading:
                    previous_heading = heading
                relations: list[dict[str, str]] = []
                if label and _clean(body_text) == label:
                    relations.append({"type": "printed_page_label", "value": label})
                if any(id(word) in unmatched_ids for word in line_words):
                    relations.append({"type": "unmatched_table_text", "review_required": "true"})
                footnote_marker = _leading_marker(body_text)
                if footnote_marker:
                    relations.append(
                        {"type": "footnote", "marker": footnote_marker, "review_required": "true"}
                    )
                block = self._block(
                    request,
                    physical_page,
                    body_text,
                    _bbox_for_words(line_words),
                    heading=previous_heading,
                    relations=relations,
                    ordinal=len(blocks),
                )
                blocks.append(block)
                if any(id(word) in unmatched_ids for word in line_words):
                    diagnostics.append(
                        ParseDiagnostic(
                            code="PDF_TABLE_TEXT_UNASSIGNED",
                            message=(
                                "Text inside a detected table was retained separately because "
                                "cell assignment was uncertain."
                            ),
                            block_id=block.block_id,
                        )
                    )

            for table_index, (table, rows) in enumerate(page_tables, start=1):
                table_id = f"p{physical_page}-t{table_index}"
                headers = rows[0] if len(rows) > 1 else []
                for row_index, row in enumerate(rows):
                    for col_index, cell in enumerate(row):
                        if not cell:
                            continue
                        table_cell_count += 1
                        if table_cell_count > self.max_table_cells:
                            return self._limit_result(
                                request, "PDF_TABLE_CELL_LIMIT", blocks, diagnostics
                            )
                        relations = [
                            {
                                "type": "table_cell",
                                "row": str(row_index + 1),
                                "column": str(col_index + 1),
                            }
                        ]
                        if row_index == 0 and len(rows) > 1:
                            relations.append({"type": "table_header", "value": "true"})
                        elif col_index < len(headers) and headers[col_index]:
                            relations.append(
                                {
                                    "type": "column_header",
                                    "value": headers[col_index] or "",
                                    "review_required": "true",
                                }
                            )
                        marker = _leading_marker(cell)
                        if marker:
                            relations.append(
                                {
                                    "type": "footnote_marker",
                                    "value": marker,
                                    "review_required": "true",
                                }
                            )
                        block = self._block(
                            request,
                            physical_page,
                            cell,
                            _table_cell_bbox(table, row_index, col_index),
                            heading=previous_heading,
                            table_id=table_id,
                            table_cell=f"r{row_index + 1}c{col_index + 1}",
                            relations=relations,
                            ordinal=len(blocks),
                        )
                        blocks.append(block)

            # Keep candidate footnote links, but flag every inferred relation for review.
            page_text_blocks = [
                block
                for block in blocks
                if isinstance(block.locator, PdfLocator)
                and block.locator.physical_page == physical_page
            ]
            markers = sorted(
                {
                    (marker, block.block_id)
                    for block in page_text_blocks
                    if (marker := _leading_marker(block.text)) is not None
                }
            )
            for marker, note_id in markers:
                diagnostics.append(
                    ParseDiagnostic(
                        code="PDF_FOOTNOTE_RELATION_UNVERIFIED",
                        message=(
                            f"Footnote marker {marker} needs manual confirmation "
                            "against its reference."
                        ),
                        block_id=note_id,
                    )
                )
            for block in page_text_blocks:
                if _leading_marker(block.text):
                    continue
                relations = list(block.relations)
                for marker, note_id in markers:
                    if _contains_marker_reference(block.text, marker):
                        relations.append(
                            {
                                "type": "footnote_reference",
                                "marker": marker,
                                "related_block_id": str(note_id),
                                "review_required": "true",
                            }
                        )
                        diagnostics.append(
                            ParseDiagnostic(
                                code="PDF_FOOTNOTE_RELATION_UNVERIFIED",
                                message=(
                                    f"Footnote marker {marker} relation needs manual confirmation."
                                ),
                                block_id=block.block_id,
                            )
                        )
                if len(relations) != len(block.relations):
                    blocks[blocks.index(block)] = block.model_copy(
                        update={"relations": tuple(relations)}
                    )

        if not blocks:
            return ParseResult(
                status="needs_ocr",
                parser_version=request.parser_version,
                diagnostics=tuple(diagnostics)
                + (
                    ParseDiagnostic(
                        code="PDF_NO_EXTRACTABLE_TEXT",
                        message="No text or tables found; OCR is not run.",
                    ),
                ),
            )
        if any(diagnostic.code == "PDF_PAGE_NO_TEXT" for diagnostic in diagnostics):
            diagnostics.append(
                ParseDiagnostic(
                    code="PDF_MIXED_TEXT_AND_SCAN",
                    message="One or more pages have no extractable text; OCR is not run.",
                )
            )
        canonical = json.dumps(
            [block.model_dump(mode="json") for block in blocks],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return ParseResult(
            status="ok",
            extraction_sha256=hashlib.sha256(canonical).hexdigest(),
            parser_version=request.parser_version,
            blocks=tuple(blocks),
            diagnostics=tuple(diagnostics),
        )

    def _block(
        self,
        request: ParseRequest,
        page: int,
        text: str,
        bbox: tuple[float, float, float, float] | None,
        *,
        heading: str | None,
        ordinal: int,
        table_id: str | None = None,
        table_cell: str | None = None,
        relations: list[dict[str, str]],
    ) -> ParsedBlock:
        identity = f"{request.raw_sha256}:{request.parser_version}:{page}:{ordinal}:{text}"
        return ParsedBlock(
            block_id=uuid.uuid5(uuid.NAMESPACE_URL, identity),
            text=text,
            locator=PdfLocator(kind="pdf", physical_page=page, bbox=bbox, table_cell=table_cell),
            heading=heading,
            table_id=table_id,
            relations=tuple(relations),
        )

    @staticmethod
    def _result(
        request: ParseRequest,
        status: str,
        code: str,
        message: str = "",
    ) -> ParseResult:
        return ParseResult(
            status=status,  # type: ignore[arg-type]
            parser_version=request.parser_version,
            diagnostics=(ParseDiagnostic(code=code, message=message or code),),
        )

    def _limit_result(
        self,
        request: ParseRequest,
        code: str,
        blocks: list[ParsedBlock],
        diagnostics: list[ParseDiagnostic],
    ) -> ParseResult:
        return ParseResult(
            status="failed",
            parser_version=request.parser_version,
            blocks=tuple(blocks),
            diagnostics=tuple(diagnostics)
            + (
                ParseDiagnostic(
                    code=code, message="Configured PDF extraction resource limit exceeded."
                ),
            ),
        )


def _sha256_stream(source: Any) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _clean(value: str | None) -> str:
    return " ".join((value or "").replace("\x00", "").split())


def _inside(word: dict[str, Any], bbox: tuple[float, float, float, float]) -> bool:
    x0, top, x1, bottom = bbox
    return (
        float(word["x0"]) >= x0
        and float(word["x1"]) <= x1
        and float(word["top"]) >= top
        and float(word["bottom"]) <= bottom
    )


def _words_to_text(words: list[dict[str, Any]]) -> str:
    # Joining positioned words avoids pdfminer reintroducing table text from extract_text.
    return " ".join(
        _clean(str(word.get("text", ""))) for word in words if _clean(str(word.get("text", "")))
    )


def _bbox_for_words(words: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    if not words:
        return None
    return (
        min(float(word["x0"]) for word in words),
        min(float(word["top"]) for word in words),
        max(float(word["x1"]) for word in words),
        max(float(word["bottom"]) for word in words),
    )


def _heading_from_words(words: list[dict[str, Any]], page_median_size: float) -> str | None:
    if not words:
        return None
    sizes = [float(word.get("size", 0)) for word in words if word.get("size")]
    if not sizes:
        return None
    first_line = [
        word for word in words if float(word["top"]) <= min(float(w["top"]) for w in words) + 3
    ]
    candidate = _words_to_text(first_line)
    bold = any("bold" in str(word.get("fontname", "")).lower() for word in words)
    if candidate and (max(sizes) >= page_median_size * 1.2 or bold or candidate.isupper()):
        return candidate
    return None


def _printed_label(lines: list[str]) -> str | None:
    for line in reversed(lines[-3:]):
        match = _PAGE_LABEL.match(line)
        if match:
            return _clean(line)
    return None


def _leading_marker(text: str) -> str | None:
    match = _FOOTNOTE.match(text)
    return (match.group(1) or match.group(2) or "*") if match else None


def _contains_marker_reference(text: str, marker: str) -> bool:
    if marker == "*":
        return "*" in text
    superscripts = {"1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵"}
    return f"[{marker}]" in text or f"^{marker}" in text or superscripts.get(marker, "\0") in text


def _table_cell_bbox(
    table: Any, row_index: int, col_index: int
) -> tuple[float, float, float, float]:
    if row_index < len(table.rows) and col_index < len(table.rows[row_index].cells):
        cell = table.rows[row_index].cells[col_index]
        if cell is not None and len(cell) == 4:
            return (float(cell[0]), float(cell[1]), float(cell[2]), float(cell[3]))
    bbox = table.bbox
    return (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))


def _group_words_by_line(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    lines: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda item: (float(item["top"]), float(item["x0"]))):
        if not lines or abs(float(word["top"]) - float(lines[-1][0]["top"])) > 3:
            lines.append([word])
        else:
            lines[-1].append(word)
    return lines
