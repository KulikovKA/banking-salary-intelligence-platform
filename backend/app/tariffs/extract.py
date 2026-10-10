"""Deterministic, evidence-grounded tariff suggestions from parsed blocks.

This module deliberately stops before persistence and publication. It recognizes a
small set of explicit tariff cues and sends ambiguous structures to manual review.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal, TypeAlias, cast

from app.contracts.parsing import ParsedBlock
from app.contracts.tariffs import ScopeDimension
from app.tariffs.metrics import METRICS

SupportRole: TypeAlias = Literal["value", "unit", "basis", "condition", "scope", "date"]
_NS = uuid.UUID("6f5f9e37-34ec-4f60-9493-f347c180eb9b")
_RUB = re.compile(
    r"(?<!\w)(\d[\d\s\u00a0]*(?:[,.]\d+)?)\s*(?:₽|руб(?:\.|лей|ля|ль)?|RUB)(?!\w)", re.I
)
_PERCENT = re.compile(r"(?<!\w)(\d+(?:[,.]\d+)?)\s*%")
_NUMBER = re.compile(r"(?<![\w/])\d+(?:[,.]\d+)?(?![\w/])")
_FREE = re.compile(r"\bбесплатно\b|без\s+комиссии|\bfree\b", re.I)
_INDIVIDUAL = re.compile(r"индивидуальн\w*|по\s+согласован\w*|по\s+запросу", re.I)
_CONDITION = re.compile(r"\b(?:при|если|только\s+при|за\s+исключением|кроме)\b", re.I)
_DATE = re.compile(r"\b(?:с|по|до|действует\s+с)\s+\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4}\b", re.I)


@dataclass(frozen=True, slots=True)
class ExtractionContext:
    """Verified document context explicitly supplied by the calling pipeline.

    Values are copied only when present. In particular, bank, payer, operation,
    scope and dates are never inferred from the document name or parser metadata.
    """

    bank_code: str | None = None
    corpus_kind: Literal["real", "synthetic"] | None = None
    payer: Literal["employer", "employee"] | None = None
    operation: str | None = None
    period: str | None = None
    employer_segment: ScopeDimension | None = None
    organization_category: ScopeDimension | None = None
    payroll_package: ScopeDimension | None = None
    contract_variant: ScopeDimension | None = None
    geography: Mapping[str, object] | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    effective_date_status: Literal["explicit", "analyst_confirmed", "unknown"] | None = None
    extra_fields: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class EvidenceQuote:
    evidence_id: uuid.UUID
    block_id: uuid.UUID
    quote: str
    quote_start: int
    quote_end: int
    support_role: SupportRole


@dataclass(frozen=True, slots=True)
class TariffSuggestion:
    """A reviewable extraction proposal; never a persisted tariff fact."""

    metric_code: str | None
    raw_candidate: Mapping[str, object]
    evidence: tuple[EvidenceQuote, ...]
    diagnostics: tuple[str, ...]
    requires_manual_interpretation: bool


@dataclass(frozen=True, slots=True)
class _Support:
    block: ParsedBlock
    role: SupportRole
    start: int = 0
    end: int | None = None

    @property
    def quote(self) -> str:
        return self.block.text[self.start : self.end]


def extract_tariff_suggestions(
    blocks: Sequence[ParsedBlock],
    context: ExtractionContext | Mapping[str, object],
    operator_mapping: str | Mapping[str, object] | None = None,
) -> tuple[TariffSuggestion, ...]:
    """Produce deterministic tariff suggestions from immutable parser blocks.

    ``operator_mapping`` is a small JSON object (or JSON string) with a ``rules``
    list. Each rule names an existing ``metric_code`` and references existing
    blocks by UUID or exact XLSX cell locator. Unknown keys, metrics, ambiguous
    locators, or missing references become diagnostic suggestions; mapping
    content is never executed as code.
    """

    normalized_context = _context(context)
    by_id = {str(block.block_id): block for block in blocks}
    suggestions: list[TariffSuggestion] = []
    if operator_mapping is not None:
        parsed, error = _mapping(operator_mapping)
        if error:
            return (_diagnostic_suggestion(error, normalized_context),)
        assert parsed is not None
        for index, rule in enumerate(cast(list[dict[str, object]], parsed["rules"])):
            result = _mapped_rule(rule, by_id, normalized_context, index)
            suggestions.append(result)

    table_groups: dict[str, list[ParsedBlock]] = defaultdict(list)
    text_blocks: list[ParsedBlock] = []
    for block in blocks:
        if block.table_id:
            table_groups[block.table_id].append(block)
        elif not _has_relation(block, {"footnote", "link"}):
            text_blocks.append(block)
    for table_id, group in sorted(table_groups.items()):
        suggestions.extend(_extract_table(table_id, group, normalized_context, by_id))
    for block in text_blocks:
        suggestion = _extract_text(block, normalized_context, by_id)
        if suggestion is not None:
            suggestions.append(suggestion)
    return tuple(suggestions)


def _context(value: ExtractionContext | Mapping[str, object]) -> dict[str, object]:
    if isinstance(value, ExtractionContext):
        result = (
            {key: val for key, val in value.__dict__.items() if val is not None}
            if hasattr(value, "__dict__")
            else {
                name: getattr(value, name)
                for name in ExtractionContext.__dataclass_fields__
                if getattr(value, name) is not None
            }
        )
        extra = result.pop("extra_fields", None)
        if isinstance(extra, Mapping):
            result.update(extra)
        for key in (
            "employer_segment",
            "organization_category",
            "payroll_package",
            "contract_variant",
        ):
            if isinstance(result.get(key), ScopeDimension):
                result[key] = result[key].model_dump(mode="json")
        return result
    allowed = set(ExtractionContext.__dataclass_fields__)
    if any(key not in allowed for key in value):
        return {}
    return {key: item for key, item in value.items() if item is not None and key != "extra_fields"}


def _mapping(value: str | Mapping[str, object]) -> tuple[dict[str, object] | None, str | None]:
    try:
        data = json.loads(value) if isinstance(value, str) else dict(value)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, "OPERATOR_MAPPING_INVALID_JSON"
    if not isinstance(data, dict) or set(data) != {"version", "rules"} or data.get("version") != 1:
        return None, "OPERATOR_MAPPING_SCHEMA_INVALID"
    rules = data.get("rules")
    if not isinstance(rules, list) or not rules:
        return None, "OPERATOR_MAPPING_RULES_REQUIRED"
    if any(not isinstance(rule, dict) for rule in rules):
        return None, "OPERATOR_MAPPING_RULE_INVALID"
    return data, None


def _mapped_rule(
    rule: Mapping[str, object],
    by_id: Mapping[str, ParsedBlock],
    context: Mapping[str, object],
    index: int,
) -> TariffSuggestion:
    allowed = {
        "metric_code",
        "value_block_id",
        "value_cell",
        "unit_block_id",
        "unit_cell",
        "basis_block_id",
        "basis_cell",
        "condition_block_ids",
        "condition_cells",
        "scope_block_ids",
        "scope_cells",
        "date_block_ids",
        "date_cells",
    }
    if set(rule) - allowed or not isinstance(rule.get("metric_code"), str):
        return _diagnostic_suggestion("OPERATOR_MAPPING_RULE_INVALID", context, index)
    metric = str(rule["metric_code"])
    if metric not in METRICS:
        return _diagnostic_suggestion("OPERATOR_MAPPING_METRIC_UNKNOWN", context, index)
    role_keys: tuple[tuple[str, str, SupportRole], ...] = (
        ("value_block_id", "value_cell", "value"),
        ("unit_block_id", "unit_cell", "unit"),
        ("basis_block_id", "basis_cell", "basis"),
    )
    supports: list[_Support] = []
    for id_key, cell_key, role in role_keys:
        if id_key in rule and cell_key in rule:
            return _diagnostic_suggestion("OPERATOR_MAPPING_REFERENCE_AMBIGUOUS", context, index)
        reference = rule.get(id_key, rule.get(cell_key))
        if reference is not None:
            block = _resolve_reference(reference, by_id)
            if block is None:
                return _diagnostic_suggestion("OPERATOR_MAPPING_REFERENCE_MISSING", context, index)
            supports.append(_Support(block, role))
    for id_key, cell_key, role in (
        ("condition_block_ids", "condition_cells", "condition"),
        ("scope_block_ids", "scope_cells", "scope"),
        ("date_block_ids", "date_cells", "date"),
    ):
        if id_key in rule and cell_key in rule:
            return _diagnostic_suggestion("OPERATOR_MAPPING_REFERENCE_AMBIGUOUS", context, index)
        refs = rule.get(id_key, rule.get(cell_key, []))
        if not isinstance(refs, list):
            return _diagnostic_suggestion("OPERATOR_MAPPING_REFERENCE_INVALID", context, index)
        for reference in refs:
            block = _resolve_reference(reference, by_id)
            if block is None:
                return _diagnostic_suggestion("OPERATOR_MAPPING_REFERENCE_MISSING", context, index)
            supports.append(_Support(block, role))
    value_support = next((s for s in supports if s.role == "value"), None)
    if value_support is None:
        return _diagnostic_suggestion("OPERATOR_MAPPING_VALUE_REQUIRED", context, index, metric)
    return _make_suggestion(
        metric, value_support.quote, supports, context, index, forced_review=True
    )


def _resolve_reference(reference: object, by_id: Mapping[str, ParsedBlock]) -> ParsedBlock | None:
    if isinstance(reference, str):
        return by_id.get(reference)
    if not isinstance(reference, Mapping) or set(reference) != {"sheet", "cell_range"}:
        return None
    sheet, cell_range = reference.get("sheet"), reference.get("cell_range")
    if not isinstance(sheet, str) or not isinstance(cell_range, str):
        return None
    matches = [
        block
        for block in by_id.values()
        if block.locator.kind == "xlsx"
        and block.locator.sheet == sheet
        and block.locator.cell_range == cell_range
    ]
    return matches[0] if len(matches) == 1 else None


def _extract_table(
    table_id: str,
    blocks: Sequence[ParsedBlock],
    context: Mapping[str, object],
    by_id: Mapping[str, ParsedBlock],
) -> list[TariffSuggestion]:
    table_metrics = {
        metric
        for block in blocks
        for metric in (
            _metric_for(
                " ".join(
                    (
                        block.heading or "",
                        block.text,
                        _relation_value(block, "column_header") or "",
                        _relation_value(block, "merged_header") or "",
                    )
                )
            ),
        )
        if metric is not None
    }
    table_metric = next(iter(table_metrics)) if len(table_metrics) == 1 else None
    rows: dict[str, list[ParsedBlock]] = defaultdict(list)
    for block in blocks:
        row = _relation_field(block, "table_cell", "row")
        if row is None:
            row = _locator_row(block)
        if row is not None:
            rows[row].append(block)
    result: list[TariffSuggestion] = []
    for row, cells in sorted(rows.items(), key=lambda item: _row_sort(item[0])):
        if all(
            _has_relation(cell, {"table_header"})
            or _relation_field(cell, "table_cell", "cell_kind") == "header"
            for cell in cells
        ):
            continue
        header_text = " ".join(
            value
            for block in cells
            for value in (
                _relation_value(block, "column_header"),
                _relation_value(block, "merged_header"),
            )
            if value
        )
        line = " ".join(block.text for block in cells)
        metric = _metric_for(header_text + " " + line)
        metric_from_table_header = metric is None
        if metric is None:
            metric = table_metric
        if metric is None:
            if row == min(rows, key=_row_sort):
                code = "TABLE_METRIC_UNKNOWN" if not table_metrics else "TABLE_METRIC_AMBIGUOUS"
                result.append(_diagnostic_suggestion(code, context, table_id))
            continue
        value_block, value_match = _find_value(cells)
        if value_block is None:
            result.append(
                _diagnostic_suggestion("TABLE_VALUE_UNKNOWN", context, table_id + ":" + row, metric)
            )
            continue
        start, end, raw_value = value_match
        supports = [_Support(value_block, "value", start, end)]
        unit_support = _inline_unit(value_block, start, end)
        if unit_support is not None:
            supports.append(unit_support)
        header_blocks = [
            block
            for block in cells
            if _relation_value(block, "column_header") or _relation_value(block, "merged_header")
        ]
        for block in cells:
            if _CONDITION.search(block.text):
                supports.append(_Support(block, "condition"))
            if _DATE.search(block.text):
                supports.append(_Support(block, "date"))
        supports, linked_review = _with_linked_footnotes(supports, by_id)
        # Header associations are parser-derived and explicitly review-required.
        review = (
            metric_from_table_header
            or linked_review
            or bool(header_blocks)
            or any(
                rel.get("review_required") == "true" for block in cells for rel in block.relations
            )
        )
        result.append(
            _make_suggestion(metric, raw_value, supports, context, table_id + ":" + row, review)
        )
    return result


def _extract_text(
    block: ParsedBlock,
    context: Mapping[str, object],
    by_id: Mapping[str, ParsedBlock],
) -> TariffSuggestion | None:
    metric = _metric_for((block.heading or "") + " " + block.text)
    if metric is None:
        return None
    matches = _value_matches(block.text)
    if len(matches) > 1:
        return _diagnostic_suggestion(
            "TEXT_VALUE_AMBIGUOUS", context, block.block_id, metric, block
        )
    match = matches[0] if matches else None
    if match is None:
        return _diagnostic_suggestion("TEXT_VALUE_UNKNOWN", context, block.block_id, metric, block)
    start, end, raw_value = match
    supports = [_Support(block, "value", start, end)]
    unit_support = _inline_unit(block, start, end)
    if unit_support is not None:
        supports.append(unit_support)
    if _CONDITION.search(block.text):
        supports.append(_Support(block, "condition"))
    if _DATE.search(block.text):
        supports.append(_Support(block, "date"))
    if "%" in raw_value:
        # A neighboring sentence may state the percentage basis; preserve it only
        # as evidence and require review unless an explicit basis was provided.
        basis = re.search(r"(?:от|сумм[ыа])\s+[^,;.]+", block.text, re.I)
        if basis:
            supports.append(_Support(block, "basis", basis.start(), basis.end()))
    supports, linked_review = _with_linked_footnotes(supports, by_id)
    return _make_suggestion(
        metric, raw_value, supports, context, block.block_id, forced_review=linked_review
    )


def _with_linked_footnotes(
    supports: Sequence[_Support], by_id: Mapping[str, ParsedBlock]
) -> tuple[list[_Support], bool]:
    expanded = list(supports)
    review_required = False
    seen = {item.block.block_id for item in expanded}
    for item in supports:
        for relation in item.block.relations:
            if relation.get("type") != "footnote_reference":
                continue
            related_id = relation.get("related_block_id")
            related = by_id.get(related_id or "")
            review_required = True
            if related is not None and related.block_id not in seen:
                expanded.append(_Support(related, "condition"))
                seen.add(related.block_id)
    return expanded, review_required


def _make_suggestion(
    metric: str,
    raw_value: str,
    supports: Sequence[_Support],
    context: Mapping[str, object],
    key: object,
    forced_review: bool = False,
) -> TariffSuggestion:
    evidence: list[EvidenceQuote] = []
    for item in supports:
        quote = item.quote
        if not quote:
            continue
        evidence_id = uuid.uuid5(
            _NS, f"{item.block.block_id}:{item.role}:{item.start}:{item.start + len(quote)}:{quote}"
        )
        evidence.append(
            EvidenceQuote(
                evidence_id,
                item.block.block_id,
                quote,
                item.start,
                item.start + len(quote),
                item.role,
            )
        )
    unique_evidence = tuple(dict((item.evidence_id, item) for item in evidence).values())
    candidate: dict[str, object] = {
        "id": str(
            uuid.uuid5(
                _NS,
                f"{key}:{metric}:{raw_value}:"
                + ",".join(str(item.evidence_id) for item in unique_evidence),
            )
        ),
        "metric_code": metric,
        "value": raw_value,
        "evidence_ids": tuple(str(item.evidence_id) for item in unique_evidence),
        "geography": {"kind": "unknown", "region_codes": [], "evidence_ids": []},
        "employer_segment": {"mode": "unknown", "values": []},
        "organization_category": {"mode": "unknown", "values": []},
        "payroll_package": {"mode": "unknown", "values": []},
        "contract_variant": {"mode": "unknown", "values": []},
        "effective_date_status": "unknown",
        "requires_manual_interpretation": True,
        "validation_flags": [],
    }
    candidate.update(context)
    if context.get("valid_from") and "effective_date_status" not in context:
        candidate["effective_date_status"] = "explicit"
    diagnostics: list[str] = []
    value, value_flags = _value_shape(raw_value, supports)
    candidate["value"] = value if value is not None else raw_value
    diagnostics.extend(value_flags)
    if value is None:
        diagnostics.append("VALUE_NEEDS_NORMALIZATION_REVIEW")
    if value and value.get("kind") == "percent" and not value.get("basis"):
        diagnostics.append("PERCENT_BASIS_UNKNOWN")
    conditions = [item.quote for item in unique_evidence if item.support_role == "condition"]
    if conditions:
        candidate["conditions_text"] = " ".join(conditions)
        diagnostics.append("CONDITIONS_UNPARSED")
    elif _FREE.search(raw_value):
        candidate["conditions_text"] = raw_value
    if (
        value
        and value.get("kind") == "money"
        and value.get("amount") in {"0", "0.0", "0.00"}
        and not conditions
    ):
        diagnostics.append("ZERO_FEE_CONDITIONS_UNKNOWN")
    dates = [item.quote for item in unique_evidence if item.support_role == "date"]
    if dates and not context.get("valid_from"):
        candidate["valid_from_text"] = " ".join(dates)
        diagnostics.append("DATE_NEEDS_REVIEW")
    if any(item.support_role == "scope" for item in unique_evidence):
        diagnostics.append("SCOPE_NEEDS_REVIEW")
    if forced_review:
        diagnostics.append("OPERATOR_MAPPING_REQUIRES_REVIEW")
    missing = [
        name for name in ("bank_code", "corpus_kind", "payer", "operation") if name not in candidate
    ]
    if missing:
        diagnostics.append("CONTEXT_MISSING:" + ",".join(missing))
    candidate["requires_manual_interpretation"] = bool(forced_review or diagnostics or missing)
    candidate["validation_flags"] = list(dict.fromkeys(diagnostics))
    return TariffSuggestion(
        metric,
        candidate,
        unique_evidence,
        tuple(dict.fromkeys(diagnostics)),
        candidate["requires_manual_interpretation"] is True,
    )


def _value_shape(
    raw: str, supports: Sequence[_Support]
) -> tuple[dict[str, object] | None, list[str]]:
    basis = next((item.quote.strip() for item in supports if item.role == "basis"), None)
    unit = next((item.quote.strip() for item in supports if item.role == "unit"), None)
    value_text = raw if _RUB.search(raw) or _PERCENT.search(raw) else f"{raw} {unit or ''}"
    match = _RUB.search(value_text)
    if match:
        amount = _decimal_text(match.group(1))
        return (
            ({"kind": "money", "amount": amount, "currency": "RUB"}, [])
            if amount is not None
            else (None, ["VALUE_INVALID"])
        )
    match = _PERCENT.search(value_text)
    if match:
        amount = _decimal_text(match.group(1))
        if amount is None:
            return None, ["VALUE_INVALID"]
        value: dict[str, object] = {"kind": "percent", "amount": amount}
        if basis:
            value["basis"] = basis
        return value, []
    if _FREE.search(raw):
        conditional = any(item.role == "condition" for item in supports)
        flags = ["FREE_CONDITIONS_REVIEW"] if conditional else []
        return {"kind": "money", "amount": "0", "currency": "RUB"}, flags
    if _INDIVIDUAL.search(raw):
        return {"kind": "individual", "text_value": raw.strip()}, []
    match = _NUMBER.search(raw)
    if match:
        return None, ["VALUE_UNIT_UNKNOWN"]
    return None, ["VALUE_UNKNOWN"]


def _value_matches(text: str) -> list[tuple[int, int, str]]:
    matches = [
        (match.start(), match.end(), match.group(0))
        for pattern in (_RUB, _PERCENT, _FREE, _INDIVIDUAL)
        for match in pattern.finditer(text)
    ]
    return sorted(set(matches), key=lambda item: (item[0], item[1]))


def _inline_unit(block: ParsedBlock, start: int, end: int) -> _Support | None:
    value = block.text[start:end]
    match = re.search(r"₽|руб(?:\.|лей|ля|ль)?|RUB|%", value, re.I)
    if match is None:
        return None
    return _Support(block, "unit", start + match.start(), start + match.end())


def _find_value(cells: Sequence[ParsedBlock]) -> tuple[ParsedBlock | None, tuple[int, int, str]]:
    matches: list[tuple[ParsedBlock, tuple[int, int, str]]] = []
    for block in cells:
        for match in _value_matches(block.text):
            matches.append((block, match))
    if len(matches) != 1:
        return None, (0, 0, "")
    return matches[0]


def _metric_for(text: str) -> str | None:
    normalized = " ".join(text.lower().replace("ё", "е").split())
    patterns = (
        (
            "payroll_credit_fee",
            r"комисс\w*.{0,45}(?:зачислен\w*|перечислен\w*|выплат\w*).{0,35}(?:зарплат\w*|заработн\w*)|(?:зачислен\w*|выплат\w*).{0,35}(?:зарплат\w*|заработн\w*)",
        ),
        (
            "external_bank_transfer_fee",
            r"(?:внешн\w*.{0,20})?(?:межбанк\w*|друг\w* банк\w*|сторонн\w* банк\w*)"
            r".{0,35}(?:перевод\w*|комисс\w*)|перевод\w*.{0,25}друг\w* банк\w*",
        ),
        (
            "account_monthly_fee",
            r"(?:обслуживан\w*.{0,20}счет\w*|счет\w*.{0,20}обслуживан\w*).{0,35}(?:месяц|ежемесяч\w*|₽|руб)",
        ),
        (
            "employee_card_fee",
            r"(?:выпуск|обслуживан|изготовлен)\w*.{0,25}карт\w*|карт\w*.{0,25}(?:выпуск|обслуживан)\w*",
        ),
        (
            "cash_withdrawal_limit",
            r"лимит.{0,30}(?:снят\w*|выдач\w*).{0,20}наличн\w*|снят\w*.{0,25}наличн\w*",
        ),
        ("transfer_limit", r"лимит.{0,30}перевод\w*|максимальн\w*.{0,20}перевод\w*"),
        (
            "crediting_time",
            r"срок.{0,25}(?:зачислен\w*|перечислен\w*).{0,20}"
            r"(?:зарплат\w*|средств\w*)|срок зачислен\w*",
        ),
        ("employee_privilege", r"привилег\w*|льгот\w*.{0,20}сотрудник\w*"),
        (
            "integration_1c",
            r"(?:интеграц\w*|обмен|интерфейс).{0,25}(?:1с|1c)|(?:1с|1c).{0,25}(?:интеграц\w*|обмен)",
        ),
        (
            "integration_api",
            r"(?:интеграц\w*|подключен\w*).{0,25}api|api.{0,25}(?:интеграц\w*|подключен\w*)",
        ),
    )
    found = [code for code, pattern in patterns if re.search(pattern, normalized, re.I)]
    return found[0] if len(found) == 1 else None


def _relation_value(block: ParsedBlock, relation_type: str) -> str | None:
    for relation in block.relations:
        if relation.get("type") == relation_type:
            return relation.get("value")
    return None


def _relation_field(block: ParsedBlock, relation_type: str, field: str) -> str | None:
    for relation in block.relations:
        if relation.get("type") == relation_type:
            return relation.get(field)
    return None


def _has_relation(block: ParsedBlock, names: set[str]) -> bool:
    return any(relation.get("type") in names for relation in block.relations)


def _locator_row(block: ParsedBlock) -> str | None:
    locator = block.locator
    if locator.kind == "xlsx":
        match = re.match(r"\$?[A-Z]+\$?(\d+)", locator.cell_range, re.I)
        return match.group(1) if match else None
    return None


def _row_sort(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (0, value)


def _decimal_text(value: str) -> str | None:
    normalized = value.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        number = Decimal(normalized)
    except InvalidOperation:
        return None
    return format(number, "f") if number.is_finite() else None


def _diagnostic_suggestion(
    code: str,
    context: Mapping[str, object],
    key: object = "diagnostic",
    metric: str | None = None,
    block: ParsedBlock | None = None,
) -> TariffSuggestion:
    evidence: tuple[EvidenceQuote, ...] = ()
    if block is not None and block.text:
        evidence = (
            EvidenceQuote(
                uuid.uuid5(_NS, f"{block.block_id}:scope:0:{len(block.text)}:{block.text}"),
                block.block_id,
                block.text,
                0,
                len(block.text),
                "scope",
            ),
        )
    raw: dict[str, object] = {
        "id": str(uuid.uuid5(_NS, f"{key}:{code}")),
        "validation_flags": [code],
        "requires_manual_interpretation": True,
    }
    raw.update(context)
    return TariffSuggestion(metric, raw, evidence, (code,), True)


__all__ = [
    "EvidenceQuote",
    "ExtractionContext",
    "TariffSuggestion",
    "extract_tariff_suggestions",
]
