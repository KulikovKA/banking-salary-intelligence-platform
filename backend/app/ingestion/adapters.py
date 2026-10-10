"""Discovery only: no IO, no approval, no tariff inference from marketing HTML."""

import re
from dataclasses import dataclass, replace
from datetime import date
from html.parser import HTMLParser
from typing import Literal
from urllib.parse import urljoin, urlsplit

from app.ingestion.formats import DocumentKind
from app.ingestion.policy import validate_url


@dataclass(frozen=True)
class DocumentCandidate:
    url: str
    title: str
    kind: DocumentKind
    effective_date_candidate: date | None
    section: Literal["current", "archive", "unknown"]
    decision: Literal["pending"] = "pending"
    adapter_code: str = ""
    adapter_version: str = "1"
    bank_code: str = ""


class LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.href: str | None = None
        self.parts: list[str] = []
        self.section: Literal["current", "archive", "unknown"] = "unknown"
        self.candidates: list[DocumentCandidate] = []
        self.sections: list[tuple[str, Literal["current", "archive", "unknown"]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.parts = []
        if tag in ("section", "div"):
            self.sections.append((tag, self.section))
            marker = " ".join(value or "" for key, value in attrs if key in ("class", "id"))
            if "archive" in marker.lower():
                self.section = "archive"
            elif "current" in marker.lower():
                self.section = "current"

    def handle_data(self, data: str) -> None:
        if self.href is not None:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("section", "div") and self.sections and self.sections[-1][0] == tag:
            self.section = self.sections.pop()[1]
        if tag != "a" or self.href is None:
            return
        url = urljoin(self.base_url, self.href)
        title = " ".join(" ".join(self.parts).split())
        self.href = None
        suffix = urlsplit(url).path.lower().rsplit(".", 1)[-1]
        if suffix not in ("pdf", "xlsx"):
            return
        try:
            validate_url(url)
        except Exception:
            return
        match = re.search(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", title)
        effective = None
        if match:
            try:
                effective = date(int(match[3]), int(match[2]), int(match[1]))
            except ValueError:
                pass
        kind: DocumentKind = "pdf" if suffix == "pdf" else "xlsx"
        self.candidates.append(DocumentCandidate(url, title, kind, effective, self.section))


def discover_documents(
    bank: Literal["kuban_credit", "vtb"], base_url: str, html: str
) -> list[DocumentCandidate]:
    validate_url(base_url)
    parser = LinkParser(base_url)
    parser.feed(html)
    adapter_code = {"kuban_credit": "kuban_credit.salary_links", "vtb": "vtb.salary_documents"}[
        bank
    ]
    return list(
        {
            candidate.url: replace(candidate, bank_code=bank, adapter_code=adapter_code)
            for candidate in parser.candidates
        }.values()
    )
