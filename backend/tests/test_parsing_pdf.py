"""Risk-focused tests for the offline PDF parser using generated synthetic files."""

from __future__ import annotations

import hashlib
import socket
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pdfplumber
import pytest
from PIL import Image

from app.contracts.parsing import ParseRequest
from app.parsing.pdf import PARSER_VERSION, PdfParser


def _request(path: Path, *, parser_version: str = PARSER_VERSION) -> ParseRequest:
    return ParseRequest(
        source_version_id=uuid4(),
        raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        kind="pdf",
        corpus_kind="synthetic",
        parser_version=parser_version,
    )


def _pdf_bytes(pages: list[str], *, encrypted: bool = False) -> bytes:
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    page_ids = [5 + 2 * index for index in range(len(pages))]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids).encode()
    objects.append(b"<< /Type /Pages /Kids [" + kids + f"] /Count {len(pages)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /ProcSet [/PDF /Text] >>")
    for index, content in enumerate(pages):
        page_id = page_ids[index]
        stream_id = page_id + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>".encode()
        )
        stream = content.encode("ascii")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    if encrypted:
        # A Standard security handler without a matching password exercises the encrypted path.
        objects.append(
            b"<< /Filter /Standard /V 1 /R 2 /O (01234567890123456789012345678901) "
            b"/U (01234567890123456789012345678901) /P -4 >>"
        )
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R".encode()
    if encrypted:
        trailer += f" /Encrypt {len(objects)} 0 R".encode()
    data.extend(trailer + f" >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(data)


def _text(value: str, x: int, y: int, size: int = 11) -> str:
    escaped = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"BT /F1 {size} Tf {x} {y} Td ({escaped}) Tj ET\n"


def _sample_pdf() -> bytes:
    page1 = _text("Project tariff", 60, 760, 18)
    page1 += _text("Salary project fee conditions apply", 60, 725)
    page1 += "60 600 m 550 600 l 550 540 l 60 540 l h S\n"
    page1 += "250 600 m 250 540 l S\n60 570 m 550 570 l S\n"
    page1 += _text("Service", 70, 580)
    page1 += _text("Employer fee", 260, 580)
    page1 += _text("Payroll credit", 70, 550)
    page1 += _text("0 RUB if monthly payroll exceeds 100000 RUB [1]", 260, 550)
    page1 += _text("1) Fee waiver requires salary credits each month", 60, 500)
    page1 += _text("Page 1 of 2", 270, 25)
    page2 = _text("Additional conditions", 60, 760, 18)
    page2 += _text("Employer pays a 1 percent fee for expedited transfers", 60, 720)
    page2 += _text("Page 1", 270, 25)
    return _pdf_bytes([page1, page2])


def _image_only_pdf() -> bytes:
    jpeg = BytesIO()
    Image.new("RGB", (2, 2), "white").save(jpeg, format="JPEG")
    image = jpeg.getvalue()
    content = b"q 612 0 0 792 0 0 cm /Im1 Do Q"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [5 0 R] /Count 1 >>",
        b"<< /ProcSet [/PDF /ImageC] >>",
        b"<< >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /XObject << /Im1 6 0 R >> >> /Contents 7 0 R >>",
        f"<< /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceRGB "
        f"/BitsPerComponent 8 /Filter /DCTDecode /Length {len(image)} >>\nstream\n".encode()
        + image
        + b"\nendstream",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(data)


def _parse_bytes(tmp_path: Path, data: bytes, **parser_args: int):
    path = tmp_path / "synthetic.pdf"
    path.write_bytes(data)
    return PdfParser(**parser_args).parse(_request(path), str(path))


def test_extracts_multi_page_text_table_headers_conditions_and_locators(tmp_path: Path) -> None:
    result = _parse_bytes(tmp_path, _sample_pdf())

    assert result.status == "ok"
    assert result.extraction_sha256
    assert {block.locator.physical_page for block in result.blocks} == {1, 2}
    by_text = {block.text: block for block in result.blocks}
    quote = "0 RUB if monthly payroll exceeds 100000 RUB [1]"
    assert quote in by_text
    condition = by_text["1) Fee waiver requires salary credits each month"]
    assert condition.relations == ({"type": "footnote", "marker": "1", "review_required": "true"},)
    cell = by_text[quote]
    assert cell.locator.kind == "pdf"
    assert cell.locator.physical_page == 1
    assert cell.locator.table_cell
    assert cell.table_id == "p1-t1"
    assert cell.locator.bbox is not None
    path = tmp_path / "synthetic.pdf"
    with pdfplumber.open(path) as pdf:
        located_quote = (
            pdf.pages[cell.locator.physical_page - 1].crop(cell.locator.bbox).extract_text()
        )
    assert located_quote is not None and quote in located_quote
    assert {
        relation["value"] for relation in cell.relations if relation["type"] == "column_header"
    } == {"Employer fee"}
    footnote = by_text["1) Fee waiver requires salary credits each month"]
    assert any(
        relation["related_block_id"] == str(footnote.block_id)
        and relation["review_required"] == "true"
        for relation in cell.relations
        if relation["type"] == "footnote_reference"
    )
    assert footnote.heading == "Project tariff"
    assert any(
        relation == {"type": "printed_page_label", "value": "Page 1 of 2"}
        for block in result.blocks
        for relation in block.relations
    )
    assert all(block.locator.physical_page not in (0, 3) for block in result.blocks)
    assert any(
        diagnostic.code == "PDF_FOOTNOTE_RELATION_UNVERIFIED" for diagnostic in result.diagnostics
    )


def test_extraction_ids_and_hash_are_stable_and_raw_hash_is_verified(tmp_path: Path) -> None:
    data = _sample_pdf()
    first = _parse_bytes(tmp_path, data)
    second = _parse_bytes(tmp_path, data)
    assert first.extraction_sha256 == second.extraction_sha256
    assert [block.block_id for block in first.blocks] == [block.block_id for block in second.blocks]

    path = tmp_path / "other.pdf"
    path.write_bytes(data + b" ")
    request = _request(path)
    bad_request = request.model_copy(update={"raw_sha256": "0" * 64})
    result = PdfParser().parse(bad_request, str(path))
    assert result.status == "failed"
    assert result.diagnostics[0].code == "PDF_ORIGINAL_HASH_MISMATCH"


def test_scan_only_encrypted_corrupt_and_quota_documents_are_typed(tmp_path: Path) -> None:
    scan = _parse_bytes(tmp_path, _image_only_pdf())
    assert scan.status == "needs_ocr"
    assert any(diagnostic.code == "PDF_NO_EXTRACTABLE_TEXT" for diagnostic in scan.diagnostics)

    encrypted = _parse_bytes(tmp_path, _pdf_bytes([_text("secret", 50, 700)], encrypted=True))
    assert encrypted.status == "unsupported"
    assert encrypted.diagnostics[0].code == "PDF_ENCRYPTED"

    corrupt = _parse_bytes(tmp_path, b"%PDF-not a document")
    assert corrupt.status == "failed"
    assert corrupt.diagnostics[0].code in {"PDF_CORRUPT_OR_UNREADABLE", "PDF_PARSE_ERROR"}

    over_pages = _parse_bytes(
        tmp_path, _pdf_bytes([_text("one", 50, 700), _text("two", 50, 700)]), max_pages=1
    )
    assert over_pages.status == "failed"
    assert over_pages.diagnostics[0].code == "PDF_PAGE_LIMIT"

    over_text = _parse_bytes(tmp_path, _sample_pdf(), max_text_chars=20)
    assert over_text.status == "failed"
    assert over_text.diagnostics[0].code == "PDF_TEXT_LIMIT"

    over_cells = _parse_bytes(tmp_path, _sample_pdf(), max_table_cells=1)
    assert over_cells.status == "failed"
    assert over_cells.diagnostics[0].code == "PDF_TABLE_CELL_LIMIT"

    over_bytes = _parse_bytes(tmp_path, _sample_pdf(), max_file_bytes=10)
    assert over_bytes.status == "failed"
    assert over_bytes.diagnostics[0].code == "PDF_FILE_SIZE_LIMIT"


def test_local_parser_does_not_open_network_connections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("PDF parser attempted network access")

    monkeypatch.setattr(socket.socket, "connect", deny_connect)
    result = _parse_bytes(tmp_path, _sample_pdf())
    assert result.status == "ok"


def test_printed_page_label_is_not_used_as_physical_page_number(tmp_path: Path) -> None:
    result = _parse_bytes(tmp_path, _sample_pdf())
    labels = [
        relation["value"]
        for block in result.blocks
        for relation in block.relations
        if relation["type"] == "printed_page_label"
    ]
    assert labels == ["Page 1 of 2", "Page 1"]
    page_two_label_block = next(
        block
        for block in result.blocks
        if any(relation.get("value") == "Page 1" for relation in block.relations)
    )
    assert page_two_label_block.locator.physical_page == 2
