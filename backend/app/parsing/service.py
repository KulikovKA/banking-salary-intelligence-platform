"""Transactional pipeline from an accepted corpus document to pending candidates."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.parsing import ParsedBlock, ParseRequest, ParseResult
from app.contracts.tariffs import ScopeDimension, TariffCandidate
from app.corpus.models import DocumentChunk, ExtractionRun, Snapshot
from app.corpus.service import CorpusError, CorpusService, ManifestDocument, SnapshotManifest
from app.ingestion.errors import IngestionError
from app.parsing.runner import (
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_MEMORY_LIMIT_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    BoundedParseError,
    run_bounded_parse,
)
from app.registry.models import Bank, Blob, Source, SourcePolicy, SourceVersion
from app.tariffs.extract import (
    EvidenceQuote,
    ExtractionContext,
    TariffSuggestion,
    extract_tariff_suggestions,
)
from app.tariffs.models import EvidenceRef
from app.tariffs.models import TariffCandidate as TariffCandidateRow
from app.tariffs.normalize import normalize_candidate

_ID_NAMESPACE = UUID("83c6c955-39d5-4d7c-a120-4fd1406ef47a")
_CONTEXT_FIELDS = {
    "payer", "operation", "period", "employer_segment", "organization_category",
    "payroll_package", "contract_variant", "geography", "valid_from", "valid_to",
    "effective_date_status",
}


class ExtractionPipelineError(RuntimeError):
    """Safe, stable error code returned to the operator."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class DiagnosticCount:
    code: str
    count: int


@dataclass(frozen=True, slots=True)
class ExtractionPipelineResult:
    extraction_id: str | None
    status: str
    chunk_count: int
    candidate_count: int
    diagnostics: tuple[DiagnosticCount, ...]
    idempotent: bool = False

    @property
    def diagnostic_count(self) -> int:
        return sum(item.count for item in self.diagnostics)


@dataclass(frozen=True, slots=True)
class _Evidence:
    id: UUID
    quote: EvidenceQuote


@dataclass(frozen=True, slots=True)
class _Candidate:
    candidate: TariffCandidate
    evidence: tuple[_Evidence, ...]


@dataclass(slots=True)
class _CandidateGroup:
    candidate: TariffCandidate
    evidence: dict[str, EvidenceQuote]
    geography_evidence: set[str]
    flags: set[str]
    requires_manual_interpretation: bool


class ExtractionPipeline:
    """Parse one exact draft-manifest original and atomically save its evidence."""

    def __init__(
        self,
        corpus: CorpusService,
        *,
        parse_runner: Callable[..., ParseResult] = run_bounded_parse,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        memory_limit_bytes: int = DEFAULT_MEMORY_LIMIT_BYTES,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> None:
        self.corpus = corpus
        self.factory: sessionmaker[Session] = corpus.factory
        self.parse_runner = parse_runner
        self.runner_options = {
            "timeout_seconds": timeout_seconds,
            "memory_limit_bytes": memory_limit_bytes,
            "max_output_bytes": max_output_bytes,
        }

    def run(
        self,
        manifest: SnapshotManifest,
        source_version_id: str | UUID,
        *,
        parser_version: str,
        operator_mapping: str | Mapping[str, object] | None = None,
        context: ExtractionContext | Mapping[str, object] | None = None,
    ) -> ExtractionPipelineResult:
        if not parser_version.strip() or len(parser_version) > 200:
            raise ExtractionPipelineError("PARSER_VERSION_INVALID")
        matches = [
            (index, item)
            for index, item in enumerate(manifest.documents)
            if str(item.source_version_id) == str(source_version_id)
        ]
        if len(matches) != 1:
            raise ExtractionPipelineError("SOURCE_VERSION_NOT_IN_MANIFEST")
        _, item = matches[0]

        # CorpusService verifies accepted state, exact source/policy/fetch/hash,
        # current permission, corpus identity, draft snapshot and stored bytes.
        original_path = self.corpus.read_draft_document(manifest, matches[0][0])
        bank_code, kind = self._verified_identity(manifest, item)
        request = ParseRequest(
            source_version_id=item.source_version_id,
            raw_sha256=item.sha256,
            kind=kind,
            corpus_kind=manifest.corpus_kind,
            parser_version=parser_version,
        )
        try:
            parsed = self.parse_runner(request, str(original_path), **self.runner_options)
        except BoundedParseError:
            raise
        except Exception as exc:
            raise ExtractionPipelineError("PARSER_EXECUTION_FAILED") from exc
        if parsed.parser_version != parser_version:
            raise ExtractionPipelineError("PARSER_VERSION_MISMATCH")
        if parsed.status != "ok":
            diagnostics = Counter(_safe_code(item.code) for item in parsed.diagnostics)
            if not diagnostics:
                diagnostics[f"PARSE_{parsed.status.upper()}"] += 1
            return ExtractionPipelineResult(
                None, parsed.status, 0, 0, _diagnostic_counts(diagnostics)
            )
        if parsed.extraction_sha256 is None:
            raise ExtractionPipelineError("EXTRACTION_HASH_REQUIRED")
        _validate_blocks(parsed.blocks)

        run_id = uuid5(
            _ID_NAMESPACE,
            f"run:{item.source_version_id}:{parser_version}:{parsed.extraction_sha256}",
        )
        safe_context = _context(context, bank_code, manifest.corpus_kind)
        try:
            suggestions = extract_tariff_suggestions(
                parsed.blocks, safe_context, operator_mapping=operator_mapping
            )
            candidates, diagnostics = _prepare_candidates(
                suggestions,
                parsed.blocks,
                run_id,
                bank_code=bank_code,
                corpus_kind=manifest.corpus_kind,
            )
        except ExtractionPipelineError:
            raise
        except Exception as exc:
            raise ExtractionPipelineError("EXTRACTION_VALIDATION_FAILED") from exc
        diagnostics.update(_safe_code(item.code) for item in parsed.diagnostics)

        try:
            idempotent = self._persist(
                manifest, item, bank_code, parsed, run_id, candidates
            )
        except (CorpusError, IngestionError, ExtractionPipelineError):
            raise
        except SQLAlchemyError as exc:
            raise ExtractionPipelineError("EXTRACTION_PERSISTENCE_FAILED") from exc
        return ExtractionPipelineResult(
            str(run_id), "ok", len(parsed.blocks), len(candidates),
            _diagnostic_counts(diagnostics), idempotent,
        )

    def _verified_identity(
        self, manifest: SnapshotManifest, item: ManifestDocument
    ) -> tuple[str, Literal["pdf", "xlsx", "html"]]:
        with self.factory() as session:
            version_id = str(item.source_version_id)
            source_id = str(item.source_id)
            version = session.get(SourceVersion, version_id)
            source = session.get(Source, source_id)
            blob = session.get(Blob, version.blob_id) if version else None
            bank = session.get(Bank, source.bank_id) if source else None
            if version is None or source is None or blob is None or bank is None:
                raise ExtractionPipelineError("PROVENANCE_UNKNOWN")
            if (
                version.source_id != source.id
                or version.content_state != "accepted"
                or source.corpus_kind != manifest.corpus_kind
                or blob.corpus_kind != manifest.corpus_kind
                or blob.sha256 != item.sha256
                or bank.code != item.bank_code
            ):
                raise ExtractionPipelineError("PROVENANCE_MISMATCH")
            if source.kind not in {"pdf", "xlsx", "html"}:
                raise ExtractionPipelineError("SOURCE_KIND_UNSUPPORTED")
            return bank.code, cast(Literal["pdf", "xlsx", "html"], source.kind)

    def _persist(
        self,
        manifest: SnapshotManifest,
        item: ManifestDocument,
        bank_code: str,
        parsed: ParseResult,
        run_id: UUID,
        candidates: tuple[_Candidate, ...],
    ) -> bool:
        assert parsed.extraction_sha256 is not None
        version_id = str(item.source_version_id)
        with self.factory.begin() as session:
            snapshot = session.scalar(
                select(Snapshot)
                .where(Snapshot.id == str(manifest.snapshot_id))
                .with_for_update()
            )
            if snapshot is None or snapshot.state != "draft":
                raise CorpusError("SNAPSHOT_NOT_DRAFT")
            if (
                snapshot.revision != manifest.revision
                or snapshot.corpus_kind != manifest.corpus_kind
            ):
                raise CorpusError("SNAPSHOT_IDENTITY_MISMATCH")
            version = session.scalar(
                select(SourceVersion).where(SourceVersion.id == version_id).with_for_update()
            )
            policy = session.scalar(
                select(SourcePolicy)
                .where(SourcePolicy.id == str(item.policy_id))
                .with_for_update()
            )
            if version is None or policy is None:
                raise CorpusError("PROVENANCE_UNKNOWN")
            # Recheck rights and bytes inside the transaction that writes evidence.
            self.corpus._validate_document(session, manifest, item, require_extraction=False)
            bank = session.scalar(
                select(Bank)
                .join(Source, Source.bank_id == Bank.id)
                .where(Source.id == str(item.source_id))
            )
            if bank is None or bank.code != bank_code:
                raise ExtractionPipelineError("PROVENANCE_MISMATCH")

            existing = session.scalar(
                select(ExtractionRun)
                .where(
                    ExtractionRun.source_version_id == version_id,
                    ExtractionRun.parser_version == parsed.parser_version,
                    ExtractionRun.extraction_sha256 == parsed.extraction_sha256,
                )
                .with_for_update()
            )
            if existing is not None:
                if (
                    existing.id != str(run_id)
                    or existing.raw_sha256 != item.sha256
                    or existing.corpus_kind != manifest.corpus_kind
                    or existing.status != "ok"
                ):
                    raise ExtractionPipelineError("EXTRACTION_IDENTITY_CONFLICT")
                _assert_replay(session, existing, parsed.blocks, candidates)
                return True

            session.add(
                ExtractionRun(
                    id=str(run_id),
                    source_version_id=version_id,
                    raw_sha256=item.sha256,
                    extraction_sha256=parsed.extraction_sha256,
                    parser_version=parsed.parser_version,
                    corpus_kind=manifest.corpus_kind,
                    status="ok",
                )
            )
            session.flush()

            chunks: dict[UUID, DocumentChunk] = {}
            for ordinal, block in enumerate(parsed.blocks):
                chunk = DocumentChunk(
                    id=str(uuid5(run_id, f"chunk:{block.block_id}")),
                    extraction_run_id=str(run_id),
                    ordinal=ordinal,
                    text=block.text,
                    text_sha256=hashlib.sha256(block.text.encode("utf-8")).hexdigest(),
                    locator=block.locator.model_dump(mode="json"),
                    relations=[dict(relation) for relation in block.relations],
                    search_vector=func.to_tsvector("simple", block.text),
                )
                chunks[block.block_id] = chunk
                session.add(chunk)
            session.flush()

            source = session.get(Source, str(item.source_id))
            if source is None or source.bank_id != bank.id:
                raise ExtractionPipelineError("PROVENANCE_MISMATCH")
            for bundle in candidates:
                payload = bundle.candidate.model_dump(mode="json")
                session.add(
                    TariffCandidateRow(
                        id=str(bundle.candidate.id),
                        extraction_run_id=str(run_id),
                        bank_id=source.bank_id,
                        metric_code=bundle.candidate.metric_code,
                        payload=payload,
                        payload_sha256=hashlib.sha256(_canonical_json(payload)).hexdigest(),
                        corpus_kind=manifest.corpus_kind,
                    )
                )
            session.flush()

            for bundle in candidates:
                for evidence in bundle.evidence:
                    block = next(
                        block for block in parsed.blocks
                        if block.block_id == evidence.quote.block_id
                    )
                    session.add(
                        EvidenceRef(
                            id=str(evidence.id),
                            candidate_id=str(bundle.candidate.id),
                            source_version_id=version_id,
                            extraction_run_id=str(run_id),
                            chunk_id=chunks[block.block_id].id,
                            raw_sha256=item.sha256,
                            extraction_sha256=parsed.extraction_sha256,
                            quote=evidence.quote.quote,
                            quote_start=evidence.quote.quote_start,
                            quote_end=evidence.quote.quote_end,
                            locator=block.locator.model_dump(mode="json"),
                            support_role=evidence.quote.support_role,
                            original_url=item.original_url,
                            acquired_at=item.acquired_at,
                        )
                    )
            session.flush()
        return False


def _prepare_candidates(
    suggestions: Sequence[TariffSuggestion],
    blocks: Sequence[ParsedBlock],
    run_id: UUID,
    *,
    bank_code: str,
    corpus_kind: str,
) -> tuple[tuple[_Candidate, ...], Counter[str]]:
    by_id = {block.block_id: block for block in blocks}
    diagnostics: Counter[str] = Counter()
    groups: dict[str, _CandidateGroup] = {}
    for index, suggestion in enumerate(suggestions):
        diagnostics.update(_safe_code(code) for code in suggestion.diagnostics)
        if suggestion.metric_code is None:
            if not suggestion.diagnostics:
                diagnostics["METRIC_UNKNOWN"] += 1
            continue

        quotes: dict[str, EvidenceQuote] = {}
        provisional: dict[str, UUID] = {}
        source_ids: dict[str, str] = {}
        for quote in suggestion.evidence:
            block = by_id.get(quote.block_id)
            if block is None:
                raise ExtractionPipelineError("EVIDENCE_BLOCK_UNKNOWN")
            if (
                quote.quote_start < 0 or quote.quote_end <= quote.quote_start
                or quote.quote_end > len(block.text)
                or block.text[quote.quote_start:quote.quote_end] != quote.quote
            ):
                raise ExtractionPipelineError("EVIDENCE_QUOTE_INVALID")
            key = _quote_key(quote)
            quotes[key] = quote
            provisional[key] = uuid5(run_id, f"evidence-provisional:{key}")
            source_ids[str(quote.evidence_id)] = str(provisional[key])

        raw = dict(suggestion.raw_candidate)
        raw["id"] = str(uuid5(run_id, f"candidate-provisional:{index}:{raw.get('id', '')}"))
        raw["bank_code"] = bank_code
        raw["corpus_kind"] = corpus_kind
        raw["evidence_ids"] = tuple(str(value) for value in provisional.values())
        geography = raw.get("geography")
        if isinstance(geography, Mapping):
            geo = dict(geography)
            geo_ids = geo.get("evidence_ids", ())
            if isinstance(geo_ids, (list, tuple)):
                geo["evidence_ids"] = tuple(
                    source_ids[str(value)] for value in geo_ids if str(value) in source_ids
                )
            raw["geography"] = geo

        result = normalize_candidate(raw)
        diagnostics.update(_safe_code(code) for code in result.flags)
        if result.candidate is None:
            if not result.flags:
                diagnostics["CANDIDATE_INVALID"] += 1
            continue
        candidate = result.candidate
        semantics = candidate.model_dump(mode="json")
        semantics["geography"] = {**semantics["geography"], "evidence_ids": []}
        for field in ("id", "evidence_ids", "validation_flags", "requires_manual_interpretation"):
            semantics.pop(field, None)
        signature = hashlib.sha256(_canonical_json(semantics)).hexdigest()
        geography_keys = {
            key for key, evidence_id in provisional.items()
            if evidence_id in candidate.geography.evidence_ids
        }
        group = groups.get(signature)
        if group is None:
            groups[signature] = _CandidateGroup(
                candidate, dict(quotes), geography_keys, set(candidate.validation_flags),
                candidate.requires_manual_interpretation,
            )
        else:
            group.evidence.update(quotes)
            group.geography_evidence.update(geography_keys)
            group.flags.update(candidate.validation_flags)
            group.requires_manual_interpretation |= candidate.requires_manual_interpretation

    output: list[_Candidate] = []
    for signature, group in sorted(groups.items()):
        candidate_id = uuid5(run_id, f"candidate:{signature}")
        quote_ids = {
            key: uuid5(run_id, f"evidence:{candidate_id}:{key}")
            for key in sorted(group.evidence)
        }
        data = group.candidate.model_dump(mode="json")
        data["id"] = str(candidate_id)
        data["evidence_ids"] = [str(quote_ids[key]) for key in sorted(quote_ids)]
        data["geography"] = {
            **data["geography"],
            "evidence_ids": [
                str(quote_ids[key]) for key in sorted(group.geography_evidence)
                if key in quote_ids
            ],
        }
        data["validation_flags"] = sorted(group.flags)
        data["requires_manual_interpretation"] = group.requires_manual_interpretation
        try:
            normalized = TariffCandidate.model_validate(data)
        except Exception as exc:
            raise ExtractionPipelineError("CANDIDATE_EVIDENCE_INVALID") from exc
        output.append(
            _Candidate(
                normalized,
                tuple(
                    _Evidence(quote_ids[key], quote)
                    for key, quote in sorted(group.evidence.items())
                ),
            )
        )
    return tuple(output), diagnostics


def _assert_replay(
    session: Session,
    run: ExtractionRun,
    blocks: Sequence[ParsedBlock],
    candidates: tuple[_Candidate, ...],
) -> None:
    chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.extraction_run_id == run.id)
        .order_by(DocumentChunk.ordinal)
    ).all()
    if len(chunks) != len(blocks):
        raise ExtractionPipelineError("EXTRACTION_REPLAY_MISMATCH")
    for ordinal, (row, block) in enumerate(zip(chunks, blocks, strict=True)):
        if (
            row.id != str(uuid5(UUID(run.id), f"chunk:{block.block_id}"))
            or row.ordinal != ordinal
            or row.text != block.text
            or row.text_sha256 != hashlib.sha256(block.text.encode()).hexdigest()
            or row.locator != block.locator.model_dump(mode="json")
            or row.relations != [dict(relation) for relation in block.relations]
        ):
            raise ExtractionPipelineError("EXTRACTION_REPLAY_MISMATCH")

    rows = session.scalars(
        select(TariffCandidateRow).where(TariffCandidateRow.extraction_run_id == run.id)
    ).all()
    expected = {
        str(bundle.candidate.id): bundle.candidate.model_dump(mode="json")
        for bundle in candidates
    }
    actual = {row.id: row.payload for row in rows}
    if actual != expected:
        raise ExtractionPipelineError("EXTRACTION_REPLAY_MISMATCH")

    refs = session.scalars(
        select(EvidenceRef).where(EvidenceRef.extraction_run_id == run.id)
    ).all()
    expected_refs = {
        (str(bundle.candidate.id), str(evidence.id), evidence.quote.quote,
         evidence.quote.quote_start, evidence.quote.quote_end, evidence.quote.support_role)
        for bundle in candidates for evidence in bundle.evidence
    }
    actual_refs = {
        (row.candidate_id, row.id, row.quote, row.quote_start, row.quote_end, row.support_role)
        for row in refs
    }
    if actual_refs != expected_refs:
        raise ExtractionPipelineError("EXTRACTION_REPLAY_MISMATCH")


def _context(
    value: ExtractionContext | Mapping[str, object] | None,
    bank_code: str,
    corpus_kind: str,
) -> ExtractionContext:
    if value is None:
        supplied: dict[str, object] = {}
    elif isinstance(value, ExtractionContext):
        supplied = {
            name: getattr(value, name)
            for name in ExtractionContext.__dataclass_fields__
            if getattr(value, name) is not None
        }
    elif isinstance(value, Mapping):
        if set(value) - (_CONTEXT_FIELDS | {"bank_code", "corpus_kind", "extra_fields"}):
            raise ExtractionPipelineError("OPERATOR_CONTEXT_INVALID")
        supplied = {key: item for key, item in value.items() if item is not None}
    else:
        raise ExtractionPipelineError("OPERATOR_CONTEXT_INVALID")
    if supplied.get("bank_code", bank_code) != bank_code:
        raise ExtractionPipelineError("OPERATOR_CONTEXT_PROVENANCE_MISMATCH")
    if supplied.get("corpus_kind", corpus_kind) != corpus_kind:
        raise ExtractionPipelineError("OPERATOR_CONTEXT_PROVENANCE_MISMATCH")
    if supplied.get("extra_fields") not in (None, {}):
        raise ExtractionPipelineError("OPERATOR_CONTEXT_INVALID")

    fields = {key: value for key, value in supplied.items() if key in _CONTEXT_FIELDS}
    for key in ("employer_segment", "organization_category", "payroll_package", "contract_variant"):
        if isinstance(fields.get(key), Mapping):
            try:
                fields[key] = ScopeDimension.model_validate(fields[key])
            except Exception as exc:
                raise ExtractionPipelineError("OPERATOR_CONTEXT_INVALID") from exc
    return ExtractionContext(
        bank_code=bank_code,
        corpus_kind=cast(Literal["real", "synthetic"], corpus_kind),
        payer=cast(Literal["employer", "employee"] | None, fields.get("payer")),
        operation=cast(str | None, fields.get("operation")),
        period=cast(str | None, fields.get("period")),
        employer_segment=cast(ScopeDimension | None, fields.get("employer_segment")),
        organization_category=cast(
            ScopeDimension | None, fields.get("organization_category")
        ),
        payroll_package=cast(ScopeDimension | None, fields.get("payroll_package")),
        contract_variant=cast(ScopeDimension | None, fields.get("contract_variant")),
        geography=cast(Mapping[str, object] | None, fields.get("geography")),
        valid_from=cast(str | None, fields.get("valid_from")),
        valid_to=cast(str | None, fields.get("valid_to")),
        effective_date_status=cast(
            Literal["explicit", "analyst_confirmed", "unknown"] | None,
            fields.get("effective_date_status"),
        ),
    )


def _validate_blocks(blocks: Sequence[ParsedBlock]) -> None:
    ids = [block.block_id for block in blocks]
    if len(ids) != len(set(ids)):
        raise ExtractionPipelineError("PARSED_BLOCK_ID_DUPLICATE")
    if any(not block.text for block in blocks):
        raise ExtractionPipelineError("PARSED_BLOCK_EMPTY")


def _quote_key(quote: EvidenceQuote) -> str:
    return hashlib.sha256(_canonical_json({
        "block_id": str(quote.block_id),
        "quote_start": quote.quote_start,
        "quote_end": quote.quote_end,
        "support_role": quote.support_role,
        "quote": quote.quote,
    })).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _safe_code(value: str) -> str:
    return "".join(
        char if char.isalnum() or char in "_:-." else "_"
        for char in value.upper()
    )[:160] or "DIAGNOSTIC_UNKNOWN"


def _diagnostic_counts(codes: Counter[str]) -> tuple[DiagnosticCount, ...]:
    return tuple(
        DiagnosticCount(code=code, count=count)
        for code, count in sorted(codes.items()) if count > 0
    )


__all__ = [
    "DiagnosticCount", "ExtractionPipeline", "ExtractionPipelineError",
    "ExtractionPipelineResult",
]
