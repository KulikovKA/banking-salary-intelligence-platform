"""Deterministic, offline extraction from a previously stored HTML original."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

from app.contracts.parsing import (
    HtmlLocator,
    ParsedBlock,
    ParseDiagnostic,
    Parser,
    ParseRequest,
    ParseResult,
)

PARSER_VERSION = "stdlib-html/3"
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_TEXT_CHARS = 10_000_000
_VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
_IGNORED = {"script", "style", "nav", "noscript", "template"}
_BLOCKS = {"p", "li", "blockquote", "dt", "dd", "figcaption", "address", "pre"}
_HEADINGS = {f"h{i}" for i in range(1, 7)}
_FOOTNOTE = re.compile(r"^\s*(?:\*{1,3}|[†‡]|\d{1,2}[.)]|\[\d{1,2}\])\s*")
_CHARSET = re.compile(
    rb"<meta\b[^>]*(?:charset\s*=\s*[\"']?\s*([\w.-]+)|"
    rb"content\s*=\s*[\"'][^\"']*?charset\s*=\s*([\w.-]+))",
    re.I,
)


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str | None]
    parent: _Node | None
    path: str = ""
    children: list[_Node | str] = field(default_factory=list)
    child_counts: dict[str, int] = field(default_factory=dict)

    def text(self, *, skip_tables: bool = False) -> str:
        parts: list[str] = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            elif not (skip_tables and child.tag == "table"):
                parts.append(child.text(skip_tables=skip_tables))
        return _clean("".join(parts))


class _HtmlLimit(ValueError):
    pass


class _TreeParser(HTMLParser):
    def __init__(self, max_text_chars: int) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("document", {}, None, "/")
        self.stack = [self.root]
        self.errors: list[str] = []
        self.suppressed = 0
        self.node_count = 0
        self.text_chars = 0
        self.max_text_chars = max_text_chars

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.suppressed:
            if tag in _IGNORED:
                self.suppressed += 1
            return
        attr_map = {key.lower(): value for key, value in attrs}
        if tag in _IGNORED:
            self.suppressed = 1
            return
        implied = {
            "td": {"td", "th"},
            "th": {"td", "th"},
            "tr": {"td", "th", "tr"},
            "p": {"p"},
            "li": {"li"},
        }
        closing = implied.get(tag, set())
        if closing and len(self.stack) > 1 and self.stack[-1].tag in closing:
            self.errors.append(f"implicitly closed <{self.stack[-1].tag}> before <{tag}>")
            self.stack.pop()
        parent = self.stack[-1]
        self.node_count += 1
        if self.node_count > 200_000 or len(self.stack) >= 128:
            raise _HtmlLimit("HTML_TREE_LIMIT")
        index = parent.child_counts.get(tag, 0) + 1
        parent.child_counts[tag] = index
        node = _Node(tag, attr_map, parent)
        node.path = (
            f"{parent.path}{tag}[{index}]" if parent is not self.root else f"/{tag}[{index}]"
        )
        parent.children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.suppressed:
            if tag in _IGNORED:
                self.suppressed -= 1
            return
        match = next(
            (i for i in range(len(self.stack) - 1, 0, -1) if self.stack[i].tag == tag), None
        )
        if match is None:
            self.errors.append(f"unmatched closing tag </{tag}>")
            return
        if match != len(self.stack) - 1:
            self.errors.append(f"implicitly closed elements before </{tag}>")
        del self.stack[match:]

    def handle_data(self, data: str) -> None:
        if not self.suppressed and data:
            self.text_chars += len(data)
            if self.text_chars > self.max_text_chars:
                raise _HtmlLimit("HTML_TEXT_LIMIT")
            self.stack[-1].children.append(data)

    def unknown_decl(self, data: str) -> None:
        self.errors.append(f"unknown declaration: {data[:80]}")


class HtmlParser(Parser):
    """Parse stored bytes only; does not resolve links or load embedded resources."""

    def __init__(
        self,
        *,
        recorded_encoding: str = "utf-8",
        max_file_bytes: int = MAX_FILE_BYTES,
        max_text_chars: int = MAX_TEXT_CHARS,
    ) -> None:
        self.recorded_encoding = recorded_encoding
        self.max_file_bytes = max_file_bytes
        self.max_text_chars = max_text_chars

    def parse(self, request: ParseRequest, original_path: str) -> ParseResult:
        if request.kind != "html":
            return self._result(request, "unsupported", "HTML_KIND_REQUIRED")
        path = Path(original_path)
        try:
            with path.open("rb") as source:
                size = os.fstat(source.fileno()).st_size
                if size > self.max_file_bytes:
                    return self._result(request, "failed", "HTML_FILE_SIZE_LIMIT", f"{size} bytes")
                raw = source.read(self.max_file_bytes + 1)
        except OSError as exc:
            return self._result(request, "failed", "HTML_ORIGINAL_UNREADABLE", type(exc).__name__)
        if hashlib.sha256(raw).hexdigest() != request.raw_sha256:
            return self._result(request, "failed", "HTML_ORIGINAL_HASH_MISMATCH")
        if len(raw) > self.max_file_bytes:
            return self._result(
                request, "failed", "HTML_FILE_SIZE_LIMIT", f"> {self.max_file_bytes} bytes"
            )

        encoding, payload = _encoding(raw, self.recorded_encoding)
        try:
            decoded = payload.decode(encoding, errors="replace")
        except LookupError:
            return self._result(request, "unsupported", "HTML_ENCODING_UNSUPPORTED", encoding)
        replacement_count = decoded.count("\ufffd")
        tree = _TreeParser(self.max_text_chars)
        try:
            tree.feed(decoded)
            tree.close()
            if len(tree.stack) > 1:
                tree.errors.append(f"{len(tree.stack) - 1} unclosed element(s) at end of document")
        except _HtmlLimit as exc:
            return self._result(request, "failed", str(exc))
        except Exception as exc:  # HTMLParser is forgiving; retain parser failure diagnostics.
            return self._result(request, "failed", "HTML_PARSE_ERROR", type(exc).__name__)

        blocks = _extract_blocks(request, tree.root)
        text_size = sum(len(block.text) for block in blocks)
        if text_size > self.max_text_chars:
            return self._result(request, "failed", "HTML_TEXT_LIMIT", f"{text_size} chars")
        diagnostics = [
            ParseDiagnostic(code="HTML_MALFORMED", message=error) for error in tree.errors
        ]
        if replacement_count:
            diagnostics.append(
                ParseDiagnostic(
                    code="HTML_DECODE_REPLACEMENTS",
                    message=f"{replacement_count} replacement characters using {encoding}",
                )
            )
        if not blocks:
            return ParseResult(
                status="unsupported",
                parser_version=request.parser_version,
                diagnostics=tuple(diagnostics)
                + (
                    ParseDiagnostic(
                        code="HTML_NO_STATIC_CONTENT",
                        message="No extractable static document text or table cells.",
                    ),
                ),
            )
        canonical = json.dumps(
            [block.model_dump(mode="json") for block in blocks],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return ParseResult(
            status="ok",
            parser_version=request.parser_version,
            extraction_sha256=hashlib.sha256(canonical).hexdigest(),
            blocks=tuple(blocks),
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def _result(request: ParseRequest, status: str, code: str, message: str = "") -> ParseResult:
        return ParseResult(
            status=status,  # type: ignore[arg-type]
            parser_version=request.parser_version,
            diagnostics=(ParseDiagnostic(code=code, message=message or code),),
        )


def _extract_blocks(request: ParseRequest, root: _Node) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    node_blocks: dict[str, uuid.UUID] = {}
    active_heading: str | None = None
    table_number = 0

    def add(
        node: _Node,
        text: str,
        *,
        heading: str | None = None,
        table_id: str | None = None,
        relations: tuple[dict[str, str], ...] = (),
    ) -> None:
        if not text:
            return
        index = len(blocks)
        block_id = uuid.uuid5(
            request.source_version_id,
            f"{request.parser_version}:{node.path}:{index}:{text}",
        )
        blocks.append(
            ParsedBlock(
                block_id=block_id,
                text=text,
                locator=HtmlLocator(kind="html", element_path=node.path, heading=heading),
                heading=heading,
                table_id=table_id,
                relations=relations,
            )
        )
        node_blocks[node.path] = block_id

    def visit(node: _Node, current_heading: str | None) -> str | None:
        nonlocal table_number
        if node.tag in _HEADINGS:
            heading_text = node.text(skip_tables=True)
            if heading_text:
                current_heading = heading_text
                add(node, heading_text, heading=heading_text)
            for child in node.children:
                if isinstance(child, _Node) and child.tag == "table":
                    visit(child, current_heading)
            return current_heading
        if node.tag == "table":
            table_number += 1
            table_id = f"table-{table_number}"
            caption = next(
                (
                    child
                    for child in node.children
                    if isinstance(child, _Node) and child.tag == "caption"
                ),
                None,
            )
            if caption:
                add(
                    caption,
                    caption.text(skip_tables=True),
                    heading=current_heading,
                    table_id=table_id,
                    relations=({"type": "caption", "table_id": table_id},),
                )
            rows = [n for n in _descendants(node) if n.tag == "tr" and _nearest(n, "table") is node]
            occupied_until: dict[int, int] = {}
            row_num = 0
            for row in rows:
                row_num += 1
                col_num = 1
                for cell in (
                    c for c in row.children if isinstance(c, _Node) and c.tag in {"th", "td"}
                ):
                    while occupied_until.get(col_num, 0) >= row_num:
                        col_num += 1
                    text = cell.text(skip_tables=True)
                    span = {
                        key: str(cell.attrs[key])
                        for key in ("rowspan", "colspan")
                        if cell.attrs.get(key) not in (None, "1")
                    }
                    row_span = _span(cell.attrs.get("rowspan"))
                    col_span = _span(cell.attrs.get("colspan"))
                    rel = [
                        {
                            "type": "table_cell",
                            "table_id": table_id,
                            "row": str(row_num),
                            "column": str(col_num),
                            "cell_kind": "header" if cell.tag == "th" else "data",
                        }
                    ]
                    rel.extend(
                        {"type": "span", "name": key, "value": value}
                        for key, value in sorted(span.items())
                    )
                    for anchor in _descendants(cell):
                        if anchor.tag == "a" and _nearest(anchor, "table") is node:
                            anchor_href = anchor.attrs.get("href") or ""
                            rel.append({
                                "type": (
                                    "footnote_reference" if anchor_href.startswith("#") else "link"
                                ),
                                "href": anchor_href,
                                "element_path": anchor.path,
                                "review_required": "true",
                            })
                    if text:
                        add(
                            cell,
                            text,
                            heading=current_heading,
                            table_id=table_id,
                            relations=tuple(rel),
                        )
                    for col in range(col_num, col_num + col_span):
                        occupied_until[col] = max(
                            occupied_until.get(col, 0), row_num + row_span - 1
                        )
                    col_num += col_span
            for nested in (
                descendant
                for descendant in _descendants(node)
                if descendant.tag == "table" and _nearest(descendant, "table") is node
            ):
                visit(nested, current_heading)
            return current_heading
        if node.tag == "a":
            text = node.text(skip_tables=True)
            href = node.attrs.get("href")
            link_type = (
                "footnote_reference"
                if href and href.startswith("#") and text and text.isdigit()
                else "link"
            )
            link_relations = ({"type": link_type, "href": href or ""},)
            if text:
                add(node, text, heading=current_heading, relations=link_relations)
            return current_heading
        if node.tag in _BLOCKS:
            text = node.text(skip_tables=True)
            if text:
                role = (
                    "footnote"
                    if node.attrs.get("role") == "doc-footnote"
                    or "footnote" in (node.attrs.get("class") or "").lower()
                    or _FOOTNOTE.match(text)
                    else "text"
                )
                references = tuple(
                    {"type": "footnote_reference", "href": str(child.attrs["href"]),
                     "review_required": "true"}
                    for child in _descendants(node)
                    if child.tag == "a" and (child.attrs.get("href") or "").startswith("#")
                )
                add(node, text, heading=current_heading,
                    relations=({"type": role},) + references)
        for child in node.children:
            if isinstance(child, _Node):
                current_heading = visit(child, current_heading)
        return current_heading

    for child in root.children:
        if isinstance(child, _Node):
            active_heading = visit(child, active_heading)
    targets: dict[str, list[uuid.UUID | None]] = {}
    for node in _descendants(root):
        target_id = node.attrs.get("id")
        if target_id:
            # A fragment may point to a span inside an extracted paragraph/cell.
            owner: _Node | None = node
            while owner is not None and owner.path not in node_blocks:
                owner = owner.parent
            targets.setdefault(target_id, []).append(
                node_blocks[owner.path] if owner is not None else None
            )
    for index, block in enumerate(blocks):
        linked = []
        for relation in block.relations:
            relation = dict(relation)
            if relation.get("type") == "footnote_reference":
                matches = targets.get(unquote(relation.get("href", "")[1:]), [])
                if len(matches) == 1 and matches[0] is not None:
                    relation["related_block_id"] = str(matches[0])
            linked.append(relation)
        blocks[index] = block.model_copy(update={"relations": tuple(linked)})
    return blocks


def _descendants(node: _Node) -> list[_Node]:
    result: list[_Node] = []
    for child in node.children:
        if isinstance(child, _Node):
            result.append(child)
            result.extend(_descendants(child))
    return result


def _nearest(node: _Node, tag: str) -> _Node | None:
    parent = node.parent
    while parent is not None:
        if parent.tag == tag:
            return parent
        parent = parent.parent
    return None


def _clean(text: str) -> str:
    return " ".join(text.replace("\x00", "").split())


def _span(value: str | None) -> int:
    if value is None:
        return 1
    try:
        return min(max(int(value), 1), 1000)
    except ValueError:
        return 1


def _encoding(raw: bytes, recorded: str) -> tuple[str, bytes]:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8", raw[3:]
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le", raw[2:]
    if raw.startswith(b"\xfe\xff"):
        return "utf-16-be", raw[2:]
    match = _CHARSET.search(raw[:8192])
    if match:
        return (match.group(1) or match.group(2)).decode("ascii", "ignore"), raw
    return recorded, raw
