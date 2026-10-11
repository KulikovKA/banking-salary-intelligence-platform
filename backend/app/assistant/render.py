"""Independent server renderer for an already authorized Comparison Engine result.

This is not an evidence validator or a snapshot access service. The caller must
read through EvidenceService and supply the exact, validated refs after checking
current rights. No client or model may supply comparison/manifest/evidence here.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from html import escape
from typing import Literal
from uuid import UUID, uuid5

from app.contracts.api import AnswerEnvelope, AnswerSource
from app.contracts.comparison import ComparisonResult
from app.contracts.evidence import EvidenceRef
from app.contracts.llm import ExplainResult
from app.contracts.tariffs import MoneyValue, PercentValue, Value
from app.corpus.service import SnapshotManifest

_NAMESPACE = UUID("06888728-ae2a-4c1b-ad71-257da02dcf2c")
_BANKS = {"sber": "Сбер", "vtb": "ВТБ", "alfa": "Альфа-Банк", "kuban_credit": "Кубань Кредит"}
_STATUS = {
    "verified": "подтверждено для указанного сценария",
    "unknown": "применимость или значение неизвестны",
    "individual": "индивидуальные условия",
    "conflict": "противоречащие тарифы; победитель не определён",
    "blocked": "данных недостаточно",
    "not_applicable": "не применимо к указанному сценарию",
}
_PAIRS = {
    "better": "первый банк выгоднее по этому критерию",
    "worse": "второй банк выгоднее по этому критерию",
    "equal": "значения равны",
    "not_comparable": "условия несопоставимы",
    "insufficient": "недостаточно данных для сравнения",
    "conflict": "сравнение заблокировано противоречиями",
}


def _plain(text: str) -> str:
    # Text remains data even if a consumer mistakenly uses Markdown or HTML.
    result = escape(text, quote=True)
    for character in ("\\", "`", "*", "_", "[", "]", "(", ")", "#", "!"):
        result = result.replace(character, "\\" + character)
    return result


def _value(value: Value) -> str:
    if isinstance(value, MoneyValue):
        return f"{value.amount} {value.currency}; период: {_plain(value.period or 'не указан')}"
    if isinstance(value, PercentValue):
        return (
            f"{value.amount}%; база: {_plain(value.basis)}; "
            f"период: {_plain(value.period or 'не указан')}"
        )
    # Preserve every field for less common unions; no arithmetic or rounding.
    return _plain(json.dumps(value.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))


def render_comparison(
    manifest: SnapshotManifest,
    comparison: ComparisonResult,
    evidence: tuple[EvidenceRef, ...],
    *,
    explanation: ExplainResult | None = None,
    fallback: bool = False,
    generated_at: datetime | None = None,
) -> AnswerEnvelope:
    """Render trusted engine values, never model prose/numbers/links.

    Incomplete evidence drops the entire result, including footnotes and numbers,
    instead of silently trimming a condition. Full access/hash/quote validation
    belongs to the upstream read service and is required before invoking this.
    """
    if (comparison.snapshot_id, comparison.corpus_revision) != (
        manifest.snapshot_id,
        manifest.revision,
    ):
        raise ValueError("ASSISTANT_SNAPSHOT_MISMATCH")
    if f"corpus_kind={manifest.corpus_kind}" not in comparison.limitations:
        raise ValueError("ASSISTANT_CORPUS_KIND_MISMATCH")
    docs = {item.source_version_id: item for item in manifest.documents}
    refs = {item.id: item for item in evidence}
    if len(refs) != len(evidence):
        raise ValueError("ASSISTANT_DUPLICATE_EVIDENCE")
    for ref in evidence:
        doc = docs.get(ref.source_version_id)
        if doc is None or (
            ref.extraction_run_id != doc.extraction_run_id
            or ref.raw_sha256 != doc.sha256
            or ref.original_url != doc.original_url
            or ref.acquired_at != doc.acquired_at
        ):
            raise ValueError("ASSISTANT_EVIDENCE_PROVENANCE_MISMATCH")
    ids = {item.id for item in comparison.claims}
    if len(ids) != len(comparison.claims):
        raise ValueError("ASSISTANT_DUPLICATE_CLAIM")
    if explanation is not None:
        if (
            len(set(explanation.ordered_claim_ids)) != len(explanation.ordered_claim_ids)
            or not set(explanation.ordered_claim_ids) <= ids
            or not set(explanation.template_by_claim) <= set(explanation.ordered_claim_ids)
            or any(
                item not in {"claim_fact", "claim_comparison", "claim_absence"}
                for item in explanation.template_by_claim.values()
            )
        ):
            raise ValueError("ASSISTANT_EXPLANATION_INVALID")
    needed = {ref for claim in comparison.claims for ref in claim.evidence_ids}
    needed.update(ref for row in comparison.rows for cell in row.cells for ref in cell.evidence_ids)
    incomplete = (
        not needed <= refs.keys()
        or any(
            (claim.kind == "fact" or claim.computed_result is not None)
            and (not claim.fact_ids or not claim.evidence_ids)
            for claim in comparison.claims
        )
        or any(
            cell.status == "verified" and not cell.fact_ids
            for row in comparison.rows
            for cell in row.cells
        )
    )
    limitations = list(comparison.limitations)
    limitations.append(
        "Показаны отдельные критерии; общий рейтинг и полнота стоимости не заявлены."
    )
    if manifest.missing_documents:
        limitations.append(
            "В корпусе отсутствуют документы: "
            + ", ".join(_BANKS[item.bank_code] for item in manifest.missing_documents)
            + "."
        )
    if incomplete:
        limitations.append("Неполные доказательства: результат исключён целиком.")
    if fallback:
        limitations.append("LLM недоступна или её ответ отклонён; использован серверный fallback.")
    claims = () if incomplete else comparison.claims
    if explanation is not None and not incomplete:
        order = {value: index for index, value in enumerate(explanation.ordered_claim_ids)}
        # LLM omission cannot hide mandatory claims, conditions or limitations.
        claims = tuple(sorted(claims, key=lambda item: order.get(item.id, len(order))))
    lines = [
        f"Корпус: {manifest.corpus_kind}; revision: {manifest.revision}; "
        f"дата сценария: {comparison.scenario_echo.as_of.isoformat()}.",
    ]
    verified = any(cell.status == "verified" for row in comparison.rows for cell in row.cells)
    partial = any(cell.status != "verified" for row in comparison.rows for cell in row.cells)
    if incomplete or not comparison.rows:
        lines.append("В проверенном корпусе недостаточно доказательств для ответа.")
    else:
        for row in comparison.rows:
            lines.append(f"Критерий: {_plain(row.metric_code)}.")
            for cell in row.cells:
                lines.append(f"{_BANKS[cell.bank_code]}: {_STATUS[cell.status]}.")
                if cell.value is not None and cell.status in {"verified", "individual"}:
                    lines.append("Значение: " + _value(cell.value) + ".")
                if cell.conditions:
                    lines.append("Условия и применимость: " + _plain(cell.conditions))
                if cell.missing_inputs:
                    lines.append(
                        "Требуется уточнить: "
                        + ", ".join(_plain(item) for item in cell.missing_inputs)
                    )
            for pair in row.pairwise:
                lines.append(f"{_BANKS[pair.left]} / {_BANKS[pair.right]}: {_PAIRS[pair.status]}.")
                if pair.delta is not None:
                    lines.append(f"Разница по Comparison Engine: {pair.delta}.")
                if pair.formula:
                    lines.append("Формула: " + _plain(pair.formula))
    lines.extend("Ограничение: " + _plain(item) for item in limitations)
    status: Literal["insufficient", "fallback", "partial", "answered"] = (
        "insufficient"
        if incomplete or not verified
        else ("fallback" if fallback else "partial" if partial else "answered")
    )
    return AnswerEnvelope(
        id=uuid5(_NAMESPACE, f"{comparison.id}:{status}"),
        status=status,
        snapshot_id=manifest.snapshot_id,
        corpus_revision=manifest.revision,
        text="\n".join(lines),
        comparison=None if incomplete else comparison,
        claims=claims,
        sources=()
        if incomplete
        else tuple(
            AnswerSource(
                evidence=refs[item],
                download_url=f"/api/v1/documents/{refs[item].source_version_id}/original",
            )
            for item in sorted(needed, key=str)
        ),
        limitations=tuple(limitations),
        data_as_of=comparison.scenario_echo.as_of,
        generated_at=generated_at or datetime.now(UTC),
    )
