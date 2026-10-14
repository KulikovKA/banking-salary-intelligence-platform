"""Explicitly admitted local research smoke: no DB, storage, publication or provider."""

import hashlib
from collections import Counter
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.contracts.parsing import ParseRequest
from app.parsing.html import PARSER_VERSION as HTML_VERSION
from app.parsing.pdf import PARSER_VERSION as PDF_VERSION
from app.parsing.runner import run_bounded_parse
from app.parsing.xlsx import PARSER_VERSION as XLSX_VERSION
from app.tariffs.extract import ExtractionContext, extract_tariff_suggestions
from app.tariffs.normalize import normalize_candidate
from evaluation.io import write_json


def diagnose_research(path: Path, bank: str, output: Path, *, admitted: bool = False) -> dict:
    if not admitted:
        raise ValueError("LOCAL_RESEARCH_DIAGNOSTIC_ADMISSION_REQUIRED")
    if ".local" not in output.resolve().parts:
        raise ValueError("RESEARCH_DIAGNOSTIC_OUTPUT_MUST_BE_PRIVATE")
    if output.resolve() == path.resolve():
        raise ValueError("DIAGNOSTIC_CANNOT_OVERWRITE_ORIGINAL")
    if bank not in {"sber", "vtb", "alfa", "kuban_credit"}:
        raise ValueError("DIAGNOSTIC_BANK_INVALID")
    kind = path.suffix.lower().removeprefix(".")
    if kind not in {"pdf", "html", "xlsx"}:
        raise ValueError("DIAGNOSTIC_FORMAT_INVALID")
    if path.stat().st_size > 52_428_800:
        raise ValueError("DIAGNOSTIC_ORIGINAL_TOO_LARGE")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    parser_version = {"pdf": PDF_VERSION, "html": HTML_VERSION, "xlsx": XLSX_VERSION}[kind]
    # This UUID is a local diagnostic request identity, NOT a SourceVersion DB ID.
    request = ParseRequest(
        source_version_id=uuid5(NAMESPACE_URL, "research-diagnostic:" + digest),
        raw_sha256=digest,
        kind=kind,
        corpus_kind="real",
        parser_version=parser_version,
    )
    result = run_bounded_parse(request, path, timeout_seconds=60)
    suggestions = extract_tariff_suggestions(
        result.blocks, ExtractionContext(bank_code=bank, corpus_kind="real")
    )
    by_id = {block.block_id: block for block in result.blocks}
    evidence_count = 0
    invalid_quotes = 0
    normalized = []
    private_suggestions = []
    for suggestion in suggestions:
        normalization = normalize_candidate(suggestion.raw_candidate)
        normalized.append(normalization)
        for quote in suggestion.evidence:
            evidence_count += 1
            block = by_id.get(quote.block_id)
            invalid_quotes += int(
                block is None or block.text[quote.quote_start : quote.quote_end] != quote.quote
            )
        private_suggestions.append(
            dict(
                metric_code=suggestion.metric_code,
                raw_candidate=dict(suggestion.raw_candidate),
                diagnostics=list(suggestion.diagnostics),
                normalization_flags=list(normalization.flags),
                evidence=[
                    dict(
                        block_id=str(q.block_id),
                        quote=q.quote,
                        quote_start=q.quote_start,
                        quote_end=q.quote_end,
                        support_role=q.support_role,
                        locator=by_id[q.block_id].locator.model_dump(mode="json"),
                    )
                    for q in suggestion.evidence
                    if q.block_id in by_id
                ],
            )
        )
    summary = dict(
        schema_version=1,
        diagnostic_only=True,
        bank=bank,
        corpus_kind="real",
        raw_sha256=digest,
        byte_size=len(raw),
        format=kind,
        parser_version=result.parser_version,
        parse_status=result.status,
        extraction_sha256=result.extraction_sha256,
        blocks=len(result.blocks),
        tables=len({b.table_id for b in result.blocks if b.table_id}),
        table_blocks=sum(b.table_id is not None for b in result.blocks),
        heading_blocks=sum(bool(b.heading) for b in result.blocks),
        relations=dict(
            Counter(r.get("type", "unknown") for b in result.blocks for r in b.relations)
        ),
        parser_diagnostics=dict(Counter(d.code for d in result.diagnostics)),
        suggestions=len(suggestions),
        diagnostic_evidence_quotes=evidence_count,
        invalid_chunk_quote_offsets=invalid_quotes,
        normalized_candidates=sum(n.ok for n in normalized),
        normalization_flags=dict(Counter(flag for n in normalized for flag in n.flags)),
        suggestion_diagnostics=dict(Counter(flag for s in suggestions for flag in s.diagnostics)),
        publication_count=0,
        persisted_source_version_id=None,
        persisted_extraction_run_id=None,
        snapshot_membership=None,
        note="Research smoke only; quote offsets verify parser chunks, not semantic "
        "tariff support or admission to a working corpus.",
    )
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("RESEARCH_ORIGINAL_CHANGED_DURING_DIAGNOSTIC")
    write_json(
        output,
        dict(
            summary=summary,
            original_path=str(path.resolve()),
            parse_result=result.model_dump(mode="json"),
            suggestions=private_suggestions,
        ),
    )
    return summary
