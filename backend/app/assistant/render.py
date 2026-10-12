"""Independent server renderer for an already authorized Comparison Engine result.

This is not an evidence validator or a snapshot access service. The caller must
read through EvidenceService and supply the exact, validated refs after checking
current rights. No client or model may supply comparison/manifest/evidence here.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from html import escape
from typing import Literal
from uuid import UUID, uuid5

from app.contracts.api import AnswerEnvelope, AnswerSource
from app.contracts.comparison import Claim, ComparisonResult
from app.contracts.evidence import EvidenceRef
from app.contracts.llm import ExplainResult
from app.contracts.tariffs import MoneyValue, PercentValue, Scenario, TariffCandidate, Value
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


def render_notice(
    manifest: SnapshotManifest,
    as_of: date,
    text: str,
    *,
    status: Literal["clarification", "insufficient"] = "clarification",
) -> AnswerEnvelope:
    return AnswerEnvelope(
        id=uuid5(_NAMESPACE, f"{manifest.manifest_sha256}:{status}:{text}"),
        status=status,
        snapshot_id=manifest.snapshot_id,
        corpus_revision=manifest.revision,
        text=f"Корпус: {manifest.corpus_kind}; revision: {manifest.revision}.\n{text}",
        data_as_of=as_of,
        generated_at=datetime.now(UTC),
    )


def render_facts(
    manifest: SnapshotManifest,
    scenario: Scenario,
    facts: tuple[tuple[UUID, TariffCandidate, bool], ...],
    evidence: tuple[EvidenceRef, ...],
    *,
    documents: bool = False,
    fallback: bool = False,
    explanation: ExplainResult | None = None,
    fact_limitations: tuple[str, ...] = (),
) -> AnswerEnvelope:
    """Published source values, never a scenario price or LLM-authored prose."""
    from app.comparison.calculations import Truth, applicability

    refs = {ref.id: ref for ref in evidence}
    docs = {doc.source_version_id: doc for doc in manifest.documents}
    claims = []
    lines = [
        f"Корпус: {manifest.corpus_kind}; revision: {manifest.revision}; "
        f"дата сценария: {scenario.as_of.isoformat()}."
    ]
    limitations = [
        "Значения из опубликованных документов; полная стоимость и общий рейтинг не заявлены."
    ]
    limitations.extend(fact_limitations)
    used: set[UUID] = set()
    partial = False
    signatures: dict[tuple[str, str], set[str]] = {}
    for _, candidate, eligible in facts:
        checked = candidate.model_copy(update={"requires_manual_interpretation": False})
        truth, _ = applicability(checked, scenario)
        if eligible and truth is Truth.TRUE:
            signatures.setdefault((candidate.bank_code, candidate.metric_code), set()).add(
                candidate.value.model_dump_json()
            )
    for fact_id, candidate, eligible in facts:
        if candidate.corpus_kind != manifest.corpus_kind:
            raise ValueError("ASSISTANT_CORPUS_KIND_MISMATCH")
        for ref_id in candidate.evidence_ids:
            ref = refs.get(ref_id)
            doc = docs.get(ref.source_version_id) if ref else None
            if (
                ref is None
                or doc is None
                or (
                    ref.raw_sha256 != doc.sha256
                    or ref.extraction_run_id != doc.extraction_run_id
                    or ref.original_url != doc.original_url
                    or ref.acquired_at != doc.acquired_at
                )
            ):
                return render_notice(
                    manifest,
                    scenario.as_of,
                    "Недостаточно проверенных доказательств.",
                    status="insufficient",
                )
        checked = (
            candidate.model_copy(update={"requires_manual_interpretation": False})
            if eligible
            else candidate
        )
        truth, missing = applicability(checked, scenario)
        conflicting = len(signatures.get((candidate.bank_code, candidate.metric_code), set())) > 1
        partial |= truth is not Truth.TRUE or not eligible or conflicting
        detail = candidate.model_dump(mode="json")
        detail["applicability_status"] = truth.value
        detail["missing_inputs"] = list(missing)
        detail["conflict"] = conflicting
        claim = Claim(
            id=uuid5(
                _NAMESPACE, f"{manifest.manifest_sha256}:{fact_id}:{scenario.model_dump_json()}"
            ),
            kind="fact",
            text=json.dumps(detail, ensure_ascii=False, sort_keys=True),
            fact_ids=(fact_id,),
            evidence_ids=candidate.evidence_ids,
        )
        claims.append(claim)
        used.update(candidate.evidence_ids)
        lines.append(
            f"{_BANKS[candidate.bank_code]}: опубликованное значение "
            f"{_plain(candidate.metric_code)}."
        )
        if conflicting:
            lines.append(
                "Конфликт опубликованных значений; выбор тарифа и победитель не определены."
            )
        if not documents:
            lines.append("Значение в документе: " + _value(candidate.value) + ".")
        lines.append(
            "Применимость: "
            + (
                "подтверждена"
                if truth is Truth.TRUE and eligible
                else "не применимо к сценарию"
                if truth is Truth.FALSE
                else "неизвестна"
            )
            + "."
        )
        # Preserve all source scope/date/conditions, with no clipping for budget.
        context = {
            key: value
            for key, value in detail.items()
            if key not in {"value", "id", "evidence_ids"}
        }
        lines.append(
            "Условия, область и даты: "
            + _plain(json.dumps(context, ensure_ascii=False, sort_keys=True))
        )
    if not claims:
        return render_notice(
            manifest,
            scenario.as_of,
            "В выбранном корпусе не найдено подтверждённых сведений.",
            status="insufficient",
        )
    if explanation:
        order = {value: index for index, value in enumerate(explanation.ordered_claim_ids)}
        claims.sort(key=lambda claim: order.get(claim.id, len(order)))
    if fallback:
        limitations.append("LLM недоступна или её ответ отклонён; использован серверный fallback.")
    if manifest.missing_documents:
        limitations.append(
            "Корпус неполный; отсутствуют документы банков: "
            + ", ".join(_BANKS[item.bank_code] for item in manifest.missing_documents)
            + "."
        )
    lines.extend("Ограничение: " + _plain(item) for item in limitations)
    return AnswerEnvelope(
        id=uuid5(
            _NAMESPACE,
            f"{manifest.manifest_sha256}:{scenario.model_dump_json()}:"
            f"{[str(c.id) for c in claims]}",
        ),
        status="fallback" if fallback else "partial" if partial else "answered",
        snapshot_id=manifest.snapshot_id,
        corpus_revision=manifest.revision,
        text="\n".join(lines),
        claims=tuple(claims),
        sources=tuple(
            AnswerSource(
                evidence=refs[key],
                download_url=f"/api/v1/documents/{refs[key].source_version_id}/original",
            )
            for key in sorted(used, key=str)
        ),
        limitations=tuple(limitations),
        data_as_of=scenario.as_of,
        generated_at=datetime.now(UTC),
    )
