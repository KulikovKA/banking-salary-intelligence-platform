"""Bounded format validation; no rendering, macros or external resource access."""

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Literal

from app.ingestion.errors import IngestionError

DocumentKind = Literal["html", "pdf", "xlsx"]
MEDIA_TYPES = {
    "html": "text/html",
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def document_kind(value: str) -> DocumentKind:
    kinds: dict[str, DocumentKind] = {
        "html": "html",
        "index": "html",
        "news": "html",
        "pdf": "pdf",
        "xlsx": "xlsx",
    }
    try:
        return kinds[value]
    except KeyError as exc:
        raise IngestionError("FORMAT_INVALID") from exc


def check_format(path: Path, kind: DocumentKind) -> None:
    with path.open("rb") as stream:
        prefix = stream.read(65536)
    if re.search(rb"user_blocked|captcha|access denied|request rejected", prefix, re.I):
        raise IngestionError("CHALLENGE")
    if kind == "pdf":
        if not prefix.startswith(b"%PDF-"):
            raise IngestionError("FORMAT_INVALID")
    elif kind == "html":
        if not re.search(rb"<!doctype\s+html|<html\b", prefix, re.I):
            raise IngestionError("FORMAT_INVALID")
    else:
        try:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                names = {e.filename for e in entries}
                if (
                    not {"[Content_Types].xml", "xl/workbook.xml"}.issubset(names)
                    or len(entries) > 10000
                    or sum(e.file_size for e in entries) > 100 * 1024 * 1024
                    or any(
                        e.flag_bits & 1
                        or ".." in e.filename.split("/")
                        or e.filename.startswith("/")
                        or "vbaproject" in e.filename.lower()
                        or "externallinks" in e.filename.lower()
                        or e.file_size / max(1, e.compress_size) > 200
                        for e in entries
                    )
                ):
                    raise IngestionError("FORMAT_INVALID")
                for entry in entries:
                    if entry.filename.endswith(".rels"):
                        if entry.file_size > 1024 * 1024:
                            raise IngestionError("FORMAT_INVALID")
                        rels = archive.read(entry)
                        if re.search(rb"<!DOCTYPE|<!ENTITY", rels, re.I):
                            raise IngestionError("FORMAT_INVALID")
                        tree = ET.fromstring(rels)
                        if any(
                            node.attrib.get("TargetMode", "").lower() == "external"
                            for node in tree.iter()
                        ):
                            raise IngestionError("FORMAT_INVALID")
        except (zipfile.BadZipFile, OSError, ET.ParseError) as exc:
            raise IngestionError("FORMAT_INVALID") from exc
