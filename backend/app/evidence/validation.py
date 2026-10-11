"""Original-backed evidence checks plus explicit human semantic confirmation."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID, uuid5

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.evidence import EvidenceRef as RefDTO
from app.contracts.parsing import ParseRequest, ParseResult
from app.contracts.tariffs import (
    ConditionGroup,
    CountValue,
    IndividualValue,
    MoneyValue,
    PercentValue,
    TextValue,
)
from app.contracts.tariffs import TariffCandidate as CandidateDTO
from app.corpus.models import DocumentChunk, ExtractionRun
from app.corpus.service import CorpusError, CorpusService, SnapshotManifest
from app.ingestion.errors import IngestionError
from app.ingestion.evidence import ExtractionEvidence
from app.parsing.runner import BoundedParseError, run_bounded_parse
from app.registry.models import Bank, Blob, Source, SourceVersion
from app.tariffs.metrics import get_metric
from app.tariffs.models import EvidenceRef, TariffCandidate


class EvidenceError(ValueError):
    """Stable error code; never contains original text or credentials."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SemanticConfirmation:
    """Operator-selected refs supporting each field, not an automatic approval."""

    field_evidence: Mapping[str, Sequence[str]]


@dataclass(frozen=True)
class ValidationReport:
    technical_valid: bool
    semantic_confirmed: bool
    errors: tuple[str, ...]
    limitations: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()
    eligible_for_comparison: bool = False
    proof: Mapping[str, object] | None = None

    @property
    def valid(self) -> bool:
        return self.technical_valid and self.semantic_confirmed and not self.errors

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "valid": self.valid,
            "technical_valid": self.technical_valid,
            "semantic_confirmed": self.semantic_confirmed,
            "errors": list(self.errors),
            "limitations": list(self.limitations),
            "required_fields": list(self.required_fields),
            "eligible_for_comparison": self.eligible_for_comparison,
            "proof": dict(self.proof or {}),
        }


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class EvidenceValidator:
    def __init__(
        self, corpus: CorpusService, *, parse_runner: Callable[..., ParseResult] = run_bounded_parse
    ) -> None:
        self.corpus = corpus
        self.parse_runner = parse_runner

    def validate(
        self,
        session: Session,
        manifest: SnapshotManifest,
        candidate_id: str,
        confirmation: SemanticConfirmation | None = None,
    ) -> ValidationReport:
        try:
            candidate, refs, proof, uncertain = self._technical(session, manifest, candidate_id)
        except (EvidenceError, CorpusError, IngestionError, BoundedParseError) as exc:
            return ValidationReport(False, False, (exc.code,))
        except (ValidationError, ValueError, TypeError, KeyError):
            return ValidationReport(False, False, ("EVIDENCE_CONTRACT_INVALID",))
        required, limitations = _requirements(candidate, uncertain)
        if confirmation is None:
            return ValidationReport(
                True,
                False,
                ("SEMANTIC_CONFIRMATION_REQUIRED",),
                limitations,
                tuple(required),
                proof=proof,
            )
        try:
            fields = _confirmation(confirmation, required, refs)
            _support_values(candidate, fields, refs)
        except EvidenceError as exc:
            return ValidationReport(
                True, False, (exc.code,), limitations, tuple(required), proof=proof
            )
        except (TypeError, ValueError):
            return ValidationReport(
                True,
                False,
                ("SEMANTIC_CONFIRMATION_INVALID",),
                limitations,
                tuple(required),
                proof=proof,
            )
        proof["field_evidence"] = fields
        # These two checks are discharged only by explicit whole-chain human
        # confirmation. Unknown applicability/unparsed conditions remain blocked.
        limitations = tuple(
            code
            for code in limitations
            if code not in {"MANUAL_INTERPRETATION_REQUIRED", "RELATIONS_REQUIRE_REVIEW"}
        )
        return ValidationReport(
            True, True, (), limitations, tuple(required), not limitations, proof
        )

    def _technical(
        self,
        session: Session,
        manifest: SnapshotManifest,
        candidate_id: str,
    ) -> tuple[CandidateDTO, dict[str, RefDTO], dict[str, object], bool]:
        row = session.get(TariffCandidate, candidate_id)
        if row is None:
            raise EvidenceError("CANDIDATE_UNKNOWN")
        candidate = CandidateDTO.model_validate(row.payload)
        metric = get_metric(candidate.metric_code)
        if (
            metric is None
            or candidate.value.kind not in metric.allowed_kinds
            or candidate.payer not in metric.payer
            or candidate.operation not in metric.operation
        ):
            raise EvidenceError("METRIC_SEMANTICS_MISMATCH")
        value_period = getattr(candidate.value, "period", None)
        if candidate.period and value_period and candidate.period != value_period:
            raise EvidenceError("PERIOD_CONFLICT")
        if str(candidate.id) != row.id or canonical_hash(row.payload) != row.payload_sha256:
            raise EvidenceError("CANDIDATE_PAYLOAD_HASH_MISMATCH")
        run = session.get(ExtractionRun, row.extraction_run_id)
        if run is None or run.status != "ok":
            raise EvidenceError("EXTRACTION_NOT_READY")
        matches = [
            item
            for item in manifest.documents
            if str(item.source_version_id) == run.source_version_id
            and str(item.extraction_run_id) == run.id
        ]
        if len(matches) != 1:
            raise EvidenceError("CANDIDATE_NOT_IN_MANIFEST")
        item = matches[0]
        self.corpus._validate_document(session, manifest, item)
        version = session.get(SourceVersion, run.source_version_id)
        source = session.get(Source, str(item.source_id))
        blob = session.get(Blob, version.blob_id) if version else None
        bank = session.get(Bank, row.bank_id)
        if version is None or source is None or blob is None or bank is None:
            raise EvidenceError("PROVENANCE_UNKNOWN")
        if (
            row.bank_id != source.bank_id
            or candidate.bank_code != bank.code
            or row.metric_code != candidate.metric_code
            or row.corpus_kind != candidate.corpus_kind
            or row.corpus_kind != run.corpus_kind
            or run.corpus_kind != manifest.corpus_kind
        ):
            raise EvidenceError("CANDIDATE_PROVENANCE_MISMATCH")
        path = self.corpus.store.verify(self.corpus.ingestion._receipt(blob))
        request = ParseRequest(
            source_version_id=UUID(version.id),
            raw_sha256=blob.sha256,
            kind=cast(Literal["pdf", "xlsx", "html"], source.kind),
            corpus_kind=run.corpus_kind,
            parser_version=run.parser_version,
        )
        parsed = self.parse_runner(request, str(path))
        if (
            parsed.status != "ok"
            or parsed.parser_version != run.parser_version
            or parsed.extraction_sha256 != run.extraction_sha256
            or canonical_hash([b.model_dump(mode="json") for b in parsed.blocks])
            != run.extraction_sha256
        ):
            raise EvidenceError("EXTRACTION_HASH_MISMATCH")
        chunks = session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.extraction_run_id == run.id)
            .order_by(DocumentChunk.ordinal)
        ).all()
        if len(chunks) != len(parsed.blocks):
            raise EvidenceError("EXTRACTION_CHUNKS_MISMATCH")
        by_chunk = {}
        by_block = {}
        for ordinal, (chunk, block) in enumerate(zip(chunks, parsed.blocks, strict=True)):
            if (
                chunk.ordinal != ordinal
                or chunk.id != str(uuid5(UUID(run.id), f"chunk:{block.block_id}"))
                or chunk.text != block.text
                or chunk.text_sha256 != hashlib.sha256(chunk.text.encode()).hexdigest()
                or chunk.locator != block.locator.model_dump(mode="json")
                or chunk.relations != list(block.relations)
            ):
                raise EvidenceError("CHUNK_OR_ACTUAL_LOCATOR_MISMATCH")
            by_chunk[chunk.id] = chunk
            by_block[str(block.block_id)] = chunk.id
        rows = session.scalars(select(EvidenceRef).where(EvidenceRef.candidate_id == row.id)).all()
        if {ref.id for ref in rows} != {str(ref_id) for ref_id in candidate.evidence_ids}:
            raise EvidenceError("CANDIDATE_EVIDENCE_SET_MISMATCH")
        refs: dict[str, RefDTO] = {}
        for ref in rows:
            ref_chunk = by_chunk.get(ref.chunk_id)
            if (
                ref_chunk is None
                or ref.extraction_run_id != run.id
                or ref.source_version_id != version.id
                or ref.raw_sha256 != run.raw_sha256
                or ref.extraction_sha256 != run.extraction_sha256
                or ref.locator != ref_chunk.locator
                or ref.original_url != item.original_url
                or ref.acquired_at != item.acquired_at
            ):
                raise EvidenceError("EVIDENCE_PROVENANCE_MISMATCH")
            dto = RefDTO.model_validate(
                {
                    name: getattr(ref, name)
                    for name in RefDTO.model_fields
                    if name != "schema_version"
                }
            )
            dto.check_chunk(ref_chunk.text)
            legacy = ExtractionEvidence(
                source_version_id=dto.source_version_id,
                raw_sha256=dto.raw_sha256,
                extraction_sha256=dto.extraction_sha256,
                parser_version=run.parser_version,
                corpus_kind=candidate.corpus_kind,
                quote=dto.quote,
                quote_start=dto.quote_start,
                quote_end=dto.quote_end,
                physical_page=(dto.locator.physical_page if dto.locator.kind == "pdf" else None),
            )
            legacy.check_chunk(ref_chunk.text)
            refs[ref.id] = dto
        cited_chunks = {str(ref.chunk_id) for ref in refs.values()}
        uncertain = False
        for chunk_id in cited_chunks:
            for relation in by_chunk[chunk_id].relations:
                uncertain |= relation.get("review_required") == "true"
                if relation.get("type") == "footnote_reference":
                    target = by_block.get(relation.get("related_block_id", ""))
                    if target is None or not any(
                        str(ref.chunk_id) == target and ref.support_role == "condition"
                        for ref in refs.values()
                    ):
                        raise EvidenceError("FOOTNOTE_SUPPORT_MISSING")
        return (
            candidate,
            refs,
            {
                "candidate_id": row.id,
                "candidate_sha256": row.payload_sha256,
                "extraction_run_id": run.id,
                "raw_sha256": run.raw_sha256,
                "extraction_sha256": run.extraction_sha256,
                "parser_version": run.parser_version,
                "evidence": {
                    key: canonical_hash(ref.model_dump(mode="json"))
                    for key, ref in sorted(refs.items())
                },
            },
            uncertain,
        )


def _requirements(
    candidate: CandidateDTO, uncertain: bool
) -> tuple[dict[str, set[str]], tuple[str, ...]]:
    required = {
        "value": {"value"},
        "metric": {"value", "scope"},
        "payer": {"value", "scope"},
        "operation": {"value", "scope"},
    }
    limitations = []
    value = candidate.value
    if value.kind in {"money", "percent", "count", "range", "formula"}:
        required["unit"] = {"unit", "value"}
        if not candidate.period and not getattr(value, "period", None):
            limitations.append("PERIOD_UNKNOWN")
    if getattr(value, "basis", None):
        required["basis"] = {"basis", "value"}
    elif value.kind == "formula" and value.formula != "constant":
        limitations.append("BASIS_UNKNOWN")
    if candidate.period or getattr(value, "period", None):
        required["period"] = {"unit", "basis", "condition", "scope", "value"}
    if candidate.conditions is not None or candidate.conditions_text:
        required["conditions"] = {"condition", "value"}
        if candidate.conditions is None and candidate.conditions_text not in {
            "бесплатно",
            "free",
            "без комиссии",
        }:
            limitations.append("CONDITIONS_UNPARSED")
    if candidate.geography.kind == "unknown":
        limitations.append("GEOGRAPHY_UNKNOWN")
    else:
        required["geography"] = {"scope"}
    for name in (
        "employer_segment",
        "organization_category",
        "payroll_package",
        "contract_variant",
    ):
        if getattr(candidate, name).mode == "unknown":
            limitations.append(f"SCOPE_UNKNOWN:{name}")
        else:
            required[name] = {"scope"}
    if candidate.valid_from is None:
        limitations.append("DATE_UNKNOWN")
    else:
        required["date"] = {"date"}
    if candidate.requires_manual_interpretation:
        required["interpretation"] = {"value", "condition", "scope", "unit", "basis", "date"}
        limitations.append("MANUAL_INTERPRETATION_REQUIRED")
    if uncertain:
        required["relations"] = {"value", "condition", "scope", "unit", "basis", "date"}
        limitations.append("RELATIONS_REQUIRE_REVIEW")
    if value.kind in {"individual", "text", "boolean"}:
        limitations.append("NON_NUMERIC_VALUE")
    return required, tuple(limitations)


def _confirmation(
    confirmation: SemanticConfirmation,
    required: Mapping[str, set[str]],
    refs: Mapping[str, RefDTO],
) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    if set(confirmation.field_evidence) != set(required):
        raise EvidenceError("SEMANTIC_FIELDS_INCOMPLETE")
    for field, allowed_roles in required.items():
        ids = confirmation.field_evidence[field]
        if isinstance(ids, str) or not ids or len(ids) > len(refs):
            raise EvidenceError("SEMANTIC_EVIDENCE_INVALID")
        if any(
            not isinstance(key, str)
            or key not in refs
            or refs[key].support_role not in allowed_roles
            for key in ids
        ):
            raise EvidenceError("SEMANTIC_EVIDENCE_INVALID")
        fields[field] = sorted(set(ids))
        if field in {"relations", "interpretation"} and set(ids) != set(refs):
            raise EvidenceError("SEMANTIC_CHAIN_CONFIRMATION_INCOMPLETE")
    return fields


_NUMBER = re.compile(r"(?<![\w\d])\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?(?!\d)")


def _text(value: str) -> str:
    return " ".join(value.casefold().split())


def _support_values(
    candidate: CandidateDTO,
    fields: Mapping[str, Sequence[str]],
    refs: Mapping[str, RefDTO],
) -> None:
    def support(field: str) -> str:
        return " ".join(refs[key].quote for key in fields[field])

    quote = support("value")
    numbers = {
        Decimal(m.group().replace(" ", "").replace("\u00a0", "").replace(",", "."))
        for m in _NUMBER.finditer(quote)
    }
    value = candidate.value
    expected: list[Decimal] = []
    if isinstance(value, (MoneyValue, PercentValue, CountValue)):
        expected.append(Decimal(value.amount))
    elif value.kind == "range":
        expected.extend(bound for bound in (value.lower, value.upper) if bound is not None)
        if not re.search(r"\b(?:от|до|from|up to)\b|[–—<>≤≥]", quote, re.I):
            raise EvidenceError("VALUE_RANGE_NOT_SUPPORTED")
    elif value.kind == "formula":
        expected.extend(value.parameters.values())
    elif isinstance(value, (TextValue, IndividualValue)):
        if _text(value.text_value) not in _text(quote):
            raise EvidenceError("VALUE_NOT_SUPPORTED")
    elif value.kind == "boolean":
        words = r"\b(?:да|yes|true)\b" if value.boolean_value else r"\b(?:нет|no|false)\b"
        if not re.search(words, quote, re.I):
            raise EvidenceError("VALUE_NOT_SUPPORTED")
    if (
        value.kind == "money"
        and value.amount == 0
        and re.search(r"\bбесплатно\b|без комиссии|\bfree\b", quote, re.I)
        and not re.search(r"\bне\b|\bnot\b", quote, re.I)
    ):
        numbers.add(Decimal(0))
    if any(number not in numbers for number in expected):
        raise EvidenceError("VALUE_NOT_SUPPORTED")
    if value.kind in {"money", "percent", "count"} and re.search(
        r"(?<!\w)[−-]\s*\d|\b(?:от|до|не бесплатно|not free)\b|[<>≤≥]", quote, re.I
    ):
        raise EvidenceError("VALUE_QUALIFIER_NOT_SUPPORTED")
    if "unit" in fields:
        unit_text = support("unit")
        currency = getattr(value, "currency", None)
        unit = getattr(value, "unit", None)
        token = currency or unit
        if token == "RUB":
            found = bool(re.search(r"₽|\bруб\w*|\bRUB\b", unit_text, re.I))
        elif token == "percent" or (value.kind == "formula" and not currency):
            found = "%" in unit_text
        else:
            found = bool(token and _text(str(token)) in _text(unit_text))
        if not found:
            raise EvidenceError("UNIT_NOT_SUPPORTED")
        if value.kind == "formula" and value.formula != "constant" and "%" not in unit_text:
            raise EvidenceError("UNIT_NOT_SUPPORTED")
    for field in ("basis", "period"):
        if field in fields:
            expected_text = getattr(value, field, None) or getattr(candidate, field, None)
            if not expected_text or _text(expected_text) not in _text(support(field)):
                raise EvidenceError(f"{field.upper()}_NOT_SUPPORTED")
    if candidate.conditions_text and "conditions" in fields:
        if _text(candidate.conditions_text) not in _text(support("conditions")):
            raise EvidenceError("CONDITIONS_NOT_SUPPORTED")
    if candidate.conditions is not None:
        condition_numbers = {
            Decimal(m.group().replace(" ", "").replace("\u00a0", "").replace(",", "."))
            for m in _NUMBER.finditer(support("conditions"))
        }
        stack = [candidate.conditions]
        while stack:
            node = stack.pop()
            if isinstance(node, ConditionGroup):
                stack.extend(node.conditions)
            elif node.op in {"gt", "gte", "lt", "lte"} or node.field in {
                "payroll_total",
                "transfer_amount",
                "employee_count",
                "transfers_count",
            }:
                values = node.value if isinstance(node.value, tuple) else (node.value,)
                for threshold_value in values:
                    try:
                        threshold = Decimal(str(threshold_value))
                    except Exception as exc:
                        raise EvidenceError("CONDITIONS_NOT_SUPPORTED") from exc
                    if threshold not in condition_numbers:
                        raise EvidenceError("CONDITIONS_NOT_SUPPORTED")
    if "date" in fields:
        date_text = support("date")
        dates = [candidate.valid_from]
        if candidate.valid_to:
            dates.append(candidate.valid_to)
        for date in dates:
            assert date is not None
            choices = {date.isoformat(), date.strftime("%d.%m.%Y")}
            if date == candidate.valid_to:
                inclusive = date - timedelta(days=1)
                choices |= {inclusive.isoformat(), inclusive.strftime("%d.%m.%Y")}
            if not any(choice in date_text for choice in choices):
                raise EvidenceError("DATE_NOT_SUPPORTED")
