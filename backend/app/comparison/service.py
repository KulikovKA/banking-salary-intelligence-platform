"""Evidence-backed comparison over an explicitly resolved frozen manifest."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import DecimalException, Inexact, localcontext
from itertools import combinations
from typing import Protocol
from uuid import UUID, uuid5

from app.comparison.calculations import (
    FORMULA_VERSION,
    Calculation,
    Truth,
    applicability,
    calculate,
    sum_known_components,
)
from app.contracts.base import BankCode
from app.contracts.comparison import (
    Claim,
    ComparisonCell,
    ComparisonRequest,
    ComparisonResult,
    ComparisonRow,
    PairwiseResult,
)
from app.contracts.tariffs import IndividualValue, TariffCandidate
from app.corpus.service import SnapshotManifest
from app.tariffs.metrics import METRICS, MetricDefinition

_NAMESPACE = UUID("cd9a6690-c207-49ce-b8c6-4ffb26ecdb43")


class PublishedReader(Protocol):
    def read_published(self, manifest: SnapshotManifest) -> tuple[dict[str, object], ...]: ...


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def scenario_hash(request: ComparisonRequest) -> str:
    # Decimal trailing zeros are not different financial scenarios.
    payload = request.scenario.model_dump(mode="json")
    for name in ("payroll_total", "transfer_amount"):
        amount = getattr(request.scenario, name)
        if amount is not None:
            payload[name] = (
                format(amount, "f").rstrip("0").rstrip(".")
                if "." in format(amount, "f")
                else format(amount, "f")
            )
    return hashlib.sha256(_json(payload).encode()).hexdigest()


@dataclass(frozen=True)
class _Fact:
    id: UUID
    candidate: TariffCandidate
    eligible: bool
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class _Cell:
    dto: ComparisonCell
    calculation: Calculation | None
    operands: tuple[dict[str, object], ...]


def _applicability_detail(fact: _Fact, truth: Truth) -> dict[str, object]:
    candidate = fact.candidate
    return {
        "fact_id": str(fact.id),
        "payer": candidate.payer,
        "operation": candidate.operation,
        "period": candidate.period,
        "scope": {
            name: getattr(candidate, name).model_dump(mode="json")
            for name in (
                "geography",
                "employer_segment",
                "organization_category",
                "payroll_package",
                "contract_variant",
            )
        },
        "valid_from": candidate.valid_from.isoformat() if candidate.valid_from else None,
        "valid_to": candidate.valid_to.isoformat() if candidate.valid_to else None,
        "conditions": candidate.conditions.model_dump(mode="json")
        if candidate.conditions
        else None,
        "conditions_text": candidate.conditions_text,
        "truth": truth.value,
    }


def _cell(
    bank: BankCode, metric: MetricDefinition, facts: tuple[_Fact, ...], request: ComparisonRequest
) -> _Cell:
    applicable = []
    for fact in facts:
        # SNAP-09 eligibility clears the manual-interpretation flag only after
        # whole-chain human confirmation. Unparsed text still remains UNKNOWN.
        reviewed_candidate = (
            fact.candidate.model_copy(update={"requires_manual_interpretation": False})
            if fact.eligible
            else fact.candidate
        )
        truth, missing = applicability(reviewed_candidate, request.scenario)
        if truth is not Truth.FALSE:
            applicable.append((fact, truth, missing))
    if not applicable:
        if not facts:
            return _Cell(ComparisonCell(bank_code=bank, status="unknown"), None, ())
        # Retain exclusion evidence so a past/future/false-condition claim is
        # distinguishable from absence of evidence in the selected snapshot.
        return _Cell(
            ComparisonCell(
                bank_code=bank,
                status="not_applicable",
                fact_ids=tuple(fact.id for fact in facts),
                evidence_ids=tuple(
                    sorted({ref for fact in facts for ref in fact.candidate.evidence_ids}, key=str)
                ),
                conditions=_json([_applicability_detail(fact, Truth.FALSE) for fact in facts]),
            ),
            None,
            tuple(
                {
                    "fact_id": str(fact.id),
                    "source_value": fact.candidate.value.model_dump(mode="json"),
                }
                for fact in facts
            ),
        )
    ids = tuple(sorted({fact.id for fact, _, _ in applicable}, key=str))
    evidence = tuple(
        sorted({ref for fact, _, _ in applicable for ref in fact.candidate.evidence_ids}, key=str)
    )
    conditions = _json([_applicability_detail(fact, truth) for fact, truth, _ in applicable])
    calculations = [
        (fact, truth, missing, calculate(fact.candidate, request.scenario))
        for fact, truth, missing in applicable
    ]
    operands: tuple[dict[str, object], ...] = tuple(
        {
            "fact_id": str(fact.id),
            "source_value": fact.candidate.value.model_dump(mode="json"),
            "operands": calc.operands,
            "formula": calc.formula,
            "limitations": fact.limitations + calc.limitations,
        }
        for fact, _, _, calc in calculations
    )

    def result(
        status: str,
        value: object = None,
        missing: tuple[str, ...] = (),
        calc: Calculation | None = None,
    ) -> _Cell:
        dto = ComparisonCell.model_validate(
            {
                "bank_code": bank,
                "status": status,
                "value": value,
                "fact_ids": ids,
                "evidence_ids": evidence,
                "conditions": conditions,
                "missing_inputs": tuple(sorted(set(missing))),
            }
        )
        return _Cell(dto, calc, operands)

    # Multiple live values are alternatives, not additive cost components.
    # The frozen DTO has no component identity / additive composition contract.
    first = applicable[0][0].candidate
    contradictory = any(
        fact.candidate.value != first.value or fact.candidate.period != first.period
        for fact, _, _ in applicable
    )
    if contradictory and all(truth is Truth.TRUE for _, truth, _ in applicable):
        return result("conflict")
    unknown = tuple(
        field
        for _, truth, missing, _ in calculations
        if truth is Truth.UNKNOWN
        for field in missing
    )
    if unknown:
        return result("unknown", missing=unknown)
    if contradictory:
        return result("unknown", missing=("alternative_applicability",))
    fact, _, _, calc = calculations[0]
    if isinstance(fact.candidate.value, IndividualValue):
        return result("individual", fact.candidate.value)
    if any(not item.eligible for item, _, _ in applicable):
        return result(
            "unknown",
            missing=tuple(code for item, _, _ in applicable for code in item.limitations)
            or ("review_eligibility",),
        )
    missing = (
        tuple(
            field
            for field in metric.required_scenario_fields
            if getattr(request.scenario, field) is None
        )
        + calc.missing
    )
    if missing:
        return result("unknown", missing=missing)
    if calc.value is None or calc.limitations:
        return result("unknown", calc.value, calc.limitations, calc)
    return result("verified", calc.value, calc=calc)


class ComparisonService:
    """Composition root supplies an authorized manifest resolver and SNAP-09.

    No current/latest document lookup or cache bypassing revocation is used.
    The sync read is intentionally bounded by the selected frozen corpus; API
    composition should execute this service in a worker thread when appropriate.
    """

    def __init__(
        self,
        reader: PublishedReader,
        resolve_manifest: Callable[[UUID], SnapshotManifest],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.reader = reader
        self.resolve_manifest = resolve_manifest
        self.clock = clock or (lambda: datetime.now(UTC))

    async def compare(self, request: ComparisonRequest) -> ComparisonResult:
        for code in request.metric_codes:
            if code not in METRICS:
                raise ValueError("COMPARISON_METRIC_UNKNOWN")
        manifest = self.resolve_manifest(request.snapshot_id)
        if manifest.snapshot_id != request.snapshot_id:
            raise ValueError("COMPARISON_SNAPSHOT_MISMATCH")
        raw = self.reader.read_published(manifest)
        facts = []
        seen: set[UUID] = set()
        for record in raw:
            candidate = TariffCandidate.model_validate(record["candidate"])
            fact_id = UUID(str(record["fact_id"]))
            evidence_ids = record["evidence_ids"]
            if not isinstance(evidence_ids, (list, tuple)):
                raise ValueError("COMPARISON_PUBLISHED_PROVENANCE_INVALID")
            if (
                str(record["snapshot_id"]) != str(request.snapshot_id)
                or candidate.corpus_kind != manifest.corpus_kind
                or not record.get("review_id")
                or fact_id in seen
                or set(evidence_ids) != {str(ref) for ref in candidate.evidence_ids}
            ):
                raise ValueError("COMPARISON_PUBLISHED_PROVENANCE_INVALID")
            seen.add(fact_id)
            metric = METRICS.get(candidate.metric_code)
            if (
                metric is None
                or candidate.value.kind not in metric.allowed_kinds
                or (
                    candidate.payer not in metric.payer
                    or candidate.operation not in metric.operation
                )
            ):
                raise ValueError("COMPARISON_PUBLISHED_METRIC_INVALID")
            limitations = record.get("limitations", ())
            if not isinstance(limitations, (tuple, list)) or not all(
                isinstance(item, str) for item in limitations
            ):
                raise ValueError("COMPARISON_PUBLISHED_LIMITATIONS_INVALID")
            facts.append(
                _Fact(
                    fact_id,
                    candidate,
                    record.get("eligible_for_comparison") is True,
                    tuple(limitations),
                )
            )
        facts.sort(key=lambda item: str(item.id))
        hash_value = scenario_hash(request)
        rows: list[ComparisonRow] = []
        claims: list[Claim] = []
        known: dict[BankCode, dict[str, Calculation]] = {bank: {} for bank in request.bank_codes}
        known_cells: dict[BankCode, list[_Cell]] = {bank: [] for bank in request.bank_codes}

        def claim(
            kind: str,
            text: dict[str, object],
            cells: tuple[_Cell, ...],
            computed: str | None = None,
        ) -> UUID:
            content = _json(text)
            identity = uuid5(_NAMESPACE, f"{manifest.manifest_sha256}:{hash_value}:{content}")
            claims.append(
                Claim.model_validate(
                    {
                        "id": identity,
                        "kind": kind,
                        "text": content,
                        "fact_ids": tuple(
                            sorted({ref for cell in cells for ref in cell.dto.fact_ids}, key=str)
                        ),
                        "evidence_ids": tuple(
                            sorted(
                                {ref for cell in cells for ref in cell.dto.evidence_ids}, key=str
                            )
                        ),
                        "formula_version": FORMULA_VERSION,
                        "scenario_hash": hash_value,
                        "computed_result": computed,
                    }
                )
            )
            return identity

        for code in request.metric_codes:
            metric = METRICS[code]
            cells = tuple(
                _cell(
                    bank,
                    metric,
                    tuple(
                        fact
                        for fact in facts
                        if fact.candidate.bank_code == bank and fact.candidate.metric_code == code
                    ),
                    request,
                )
                for bank in request.bank_codes
            )
            for cell in cells:
                calc = cell.calculation
                if code.endswith("_fee"):
                    known_cells[cell.dto.bank_code].append(cell)
                claim(
                    "calculation"
                    if calc and calc.amount is not None
                    else "fact"
                    if cell.dto.fact_ids
                    else "absence_of_evidence",
                    {
                        "metric_code": code,
                        "bank_code": cell.dto.bank_code,
                        "sufficiency": cell.dto.status,
                        "operands": cell.operands,
                        "applicability": cell.dto.conditions,
                        "missing_inputs": cell.dto.missing_inputs,
                        "formula": calc.formula if calc else None,
                    },
                    (cell,),
                    str(calc.amount) if calc and calc.amount is not None else None,
                )
                if (
                    code.endswith("_fee")
                    and calc
                    and calc.sufficient
                    and cell.dto.status == "verified"
                ):
                    known[cell.dto.bank_code][code] = calc
            pairs = []
            for left, right in combinations(cells, 2):
                status = "insufficient"
                delta = None
                a, b = left.calculation, right.calculation
                if "conflict" in {left.dto.status, right.dto.status}:
                    status = "conflict"
                elif "not_applicable" in {left.dto.status, right.dto.status}:
                    status = "not_comparable"
                elif left.dto.status == right.dto.status == "verified" and a and b:
                    if a.signature != b.signature or a.amount is None or b.amount is None:
                        status = "not_comparable"
                    else:
                        # Use the same precision/trap policy as financial evaluation.
                        try:
                            with localcontext() as context:
                                context.prec = 28
                                context.traps[Inexact] = True
                                delta = a.amount - b.amount
                            if delta == 0:
                                status = "equal"
                            elif metric.direction == "neutral":
                                status = "not_comparable"
                                delta = None
                            else:
                                better = delta < 0 if metric.direction == "lower" else delta > 0
                                status = "better" if better else "worse"
                        except DecimalException:
                            status = "insufficient"
                identity = claim(
                    "comparison",
                    {
                        "metric_code": code,
                        "left": left.dto.bank_code,
                        "right": right.dto.bank_code,
                        "sufficiency": status,
                        "operands": [left.operands, right.operands],
                        "applicability": [left.dto.conditions, right.dto.conditions],
                        "cell_statuses": [left.dto.status, right.dto.status],
                        "compatibility": [a.signature if a else None, b.signature if b else None],
                        "formula": "left - right",
                        "direction": metric.direction,
                    },
                    (left, right),
                    str(delta) if delta is not None else None,
                )
                pairs.append(
                    PairwiseResult.model_validate(
                        {
                            "left": left.dto.bank_code,
                            "right": right.dto.bank_code,
                            "status": status,
                            "delta": delta,
                            "formula": "left - right" if delta is not None else None,
                            "claim_id": identity,
                        }
                    )
                )
            rows.append(
                ComparisonRow(
                    metric_code=code, cells=tuple(cell.dto for cell in cells), pairwise=tuple(pairs)
                )
            )
        required = tuple(code for code in request.metric_codes if code.endswith("_fee"))
        if required:
            for bank in request.bank_codes:
                subtotal = sum_known_components(known[bank], required)
                claim(
                    "calculation",
                    {
                        "bank_code": bank,
                        "sufficiency": "known_components_only",
                        "operands": {code: calc.operands for code, calc in known[bank].items()},
                        "formula": "sum(compatible known requested fee components)",
                        "requested_components": required,
                        "missing_components": subtotal.missing_components,
                        "applicability": [cell.dto.conditions for cell in known_cells[bank]],
                        "limitation": (
                            "Full cost component coverage is not defined by the frozen contract."
                        ),
                    },
                    tuple(known_cells[bank]),
                    str(subtotal.amount) if subtotal.amount is not None else None,
                )
        identity = uuid5(
            _NAMESPACE,
            f"{manifest.manifest_sha256}:{hash_value}:{_json(request.model_dump(mode='json'))}",
        )
        limitations = [
            f"corpus_kind={manifest.corpus_kind}",
            "Pairwise results concern individual metrics; no overall bank winner.",
        ]
        if required:
            limitations.append("Known components are partial costs, never a complete total.")
        for row in rows:
            for dto_cell in row.cells:
                if dto_cell.status != "verified":
                    limitations.append(
                        f"{row.metric_code}:{dto_cell.bank_code}:{dto_cell.status}:"
                        + ",".join(dto_cell.missing_inputs)
                    )
        return ComparisonResult(
            id=identity,
            snapshot_id=request.snapshot_id,
            corpus_revision=manifest.revision,
            scenario_echo=request.scenario,
            rows=tuple(rows),
            claims=tuple(claims),
            limitations=tuple(limitations),
            generated_at=self.clock(),
        )
