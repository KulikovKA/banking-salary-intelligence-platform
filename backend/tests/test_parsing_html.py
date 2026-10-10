"""Risk-focused tests for static HTML evidence extraction."""

from __future__ import annotations

import hashlib
import socket
from pathlib import Path
from uuid import uuid4

from app.contracts.parsing import ParseRequest
from app.parsing.html import PARSER_VERSION, HtmlParser

FIXTURES = Path(__file__).parent / "fixtures" / "parsing" / "html"


def _request(path: Path, *, parser_version: str = PARSER_VERSION) -> ParseRequest:
    return ParseRequest(
        source_version_id=uuid4(),
        raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        kind="html",
        corpus_kind="synthetic",
        parser_version=parser_version,
    )


def test_extracts_cyrillic_tables_spans_nested_table_footnote_and_links_without_network(
    monkeypatch,
) -> None:
    def deny_network(*_args, **_kwargs):
        raise AssertionError("HTML parser must never access network")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(socket.socket, "connect", deny_network)
    fixture = FIXTURES / "complex.html"
    request = _request(fixture)
    result = HtmlParser().parse(request, str(fixture))

    assert result.status == "ok"
    texts = [block.text for block in result.blocks]
    assert "Условия зарплатного проекта" in texts
    assert "Комиссия за перевод — 0,25% при сумме от 100 000 ₽1." in texts
    assert "Тарифы работодателя" in texts
    assert "15 ₽ за перевод" in texts
    assert "Только по договору" in texts
    assert "1) Комиссия применяется только при подключении пакета «Бизнес»." in texts
    assert "Сохранённая ссылка" in texts
    assert not any("999" in text or "777" in text or "не загружать" in text for text in texts)

    spanning_header = next(b for b in result.blocks if b.text == "Операция")
    assert {
        r.get("name"): r.get("value") for r in spanning_header.relations if r["type"] == "span"
    } == {"rowspan": "2"}
    spanning_group = next(b for b in result.blocks if b.text == "Комиссия")
    assert {
        r.get("name"): r.get("value") for r in spanning_group.relations if r["type"] == "span"
    } == {"colspan": "2"}
    tables = {block.table_id for block in result.blocks if block.table_id}
    assert len(tables) == 2
    standard_header = next(b for b in result.blocks if b.text == "Стандарт")
    urgent_header = next(b for b in result.blocks if b.text == "Срочный")
    assert standard_header.relations[0]["column"] == "2"
    assert urgent_header.relations[0]["column"] == "3"
    assert (
        next(b for b in result.blocks if b.text == "1").relations[0]["type"] == "footnote_reference"
    )
    assert next(b for b in result.blocks if b.text == "Сохранённая ссылка").relations == (
        {"type": "link", "href": "https://example.invalid/tariff.pdf"},
    )
    assert (
        next(b for b in result.blocks if b.text.startswith("1) Комиссия")).relations[0]["type"]
        == "footnote"
    )
    assert all(b.locator.element_path.startswith("/") for b in result.blocks)
    # A marketing statement remains ordinary source text; this parser creates no tariff facts.
    assert "Маркетинговое обещание: выгодные условия для бизнеса." in texts


def test_extraction_hash_locators_and_quote_offsets_are_stable(tmp_path: Path) -> None:
    original = FIXTURES / "complex.html"
    raw = original.read_bytes()
    path = tmp_path / "same.html"
    path.write_bytes(raw)
    request = _request(path)
    first = HtmlParser().parse(request, str(path))
    second = HtmlParser().parse(request, str(path))
    assert first.extraction_sha256 == second.extraction_sha256
    assert [(b.block_id, b.locator.element_path) for b in first.blocks] == [
        (b.block_id, b.locator.element_path) for b in second.blocks
    ]
    quote = "0,25% при сумме от 100 000 ₽1."
    block = next(b for b in first.blocks if quote in b.text)
    start = block.text.index(quote)
    assert block.text[start : start + len(quote)] == quote


def test_malformed_html_keeps_content_and_reports_diagnostics() -> None:
    fixture = FIXTURES / "malformed.html"
    result = HtmlParser().parse(_request(fixture), str(fixture))
    assert result.status == "ok"
    assert any(block.text == "3 ₽" for block in result.blocks)
    assert any(d.code == "HTML_MALFORMED" for d in result.diagnostics)


def test_dynamic_empty_document_is_unsupported() -> None:
    fixture = FIXTURES / "empty-dynamic.html"
    result = HtmlParser().parse(_request(fixture), str(fixture))
    assert result.status == "unsupported"
    assert result.blocks == ()
    assert any(d.code == "HTML_NO_STATIC_CONTENT" for d in result.diagnostics)


def test_recorded_legacy_encoding_and_original_hash_are_respected(tmp_path: Path) -> None:
    data = '<html><meta charset="windows-1251"><body><p>Комиссия 7,5 руб.</p></body></html>'.encode(
        "cp1251"
    )
    path = tmp_path / "legacy.html"
    path.write_bytes(data)
    result = HtmlParser().parse(_request(path), str(path))
    assert result.status == "ok"
    assert any(b.text == "Комиссия 7,5 руб." for b in result.blocks)

    wrong = _request(path).model_copy(update={"raw_sha256": "0" * 64})
    mismatch = HtmlParser().parse(wrong, str(path))
    assert mismatch.status == "failed"
    assert mismatch.diagnostics[0].code == "HTML_ORIGINAL_HASH_MISMATCH"


def test_deep_untrusted_tree_fails_with_diagnostic(tmp_path: Path) -> None:
    path = tmp_path / "deep.html"
    path.write_text("<div>" * 200 + "<p>fee</p>" + "</div>" * 200)
    result = HtmlParser().parse(_request(path), str(path))
    assert result.status == "failed"
    assert result.blocks == ()
    assert result.diagnostics[0].code == "HTML_TREE_LIMIT"


def test_table_cell_retains_footnote_target_without_fetch(tmp_path: Path) -> None:
    path = tmp_path / "note.html"
    path.write_text('<table><tr><td>Fee 1<a href="#note">*</a></td></tr></table>'
                    '<p id="note" role="doc-footnote">* Subject to package</p>')
    result = HtmlParser().parse(_request(path), str(path))
    assert result.status == "ok"
    cell = next(block for block in result.blocks if block.table_id)
    assert any(r["type"] == "footnote_reference" and r["href"] == "#note"
               for r in cell.relations)
