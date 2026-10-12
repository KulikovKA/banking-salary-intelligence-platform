"""Stateless evidence-first question orchestration and legacy offline harness."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import UUID, uuid5

from pydantic import ValidationError
from sqlalchemy import select

from app.contracts.api import AnswerEnvelope, QuestionRequest
from app.contracts.base import BANK_CODES, BankCode
from app.contracts.comparison import ComparisonRequest, ComparisonResult
from app.contracts.comparison import ComparisonService as ComparisonProtocol
from app.contracts.corpus import SearchHit, SearchRequest
from app.contracts.evidence import EvidenceRef
from app.contracts.llm import (
    ExplainResult,
    IntentResult,
    LLMClient,
    LLMError,
    LLMMessage,
    LLMRequest,
)
from app.contracts.tariffs import Scenario, TariffCandidate
from app.corpus.service import SnapshotManifest
from app.evidence.service import EvidenceService
from app.llm.base import OutputValidationError, validate_output
from app.llm.budget import current_budget_user
from app.llm.fake import FakeLLM
from app.llm.groq import GroqLLM
from app.tariffs.metrics import METRICS
from app.tariffs.models import EvidenceRef as RefRow

from .privacy import minimize_question
from .render import render_comparison, render_facts, render_notice


class SearchReader(Protocol):
    async def search(self, request: SearchRequest) -> tuple[SearchHit, ...]: ...


_REQUEST_NAMESPACE = UUID("dbd16d89-9a43-4385-a0f3-26bd26135478")
_SEARCH_TERMS = {
    "payroll_credit_fee": "зарплат",
    "account_monthly_fee": "обслуживание",
    "external_bank_transfer_fee": "перевод",
    "employee_card_fee": "карт",
    "cash_withdrawal_limit": "наличных",
    "transfer_limit": "перевод",
    "crediting_time": "зачисление",
}


class AssistantService:
    """Composition supplies session access and the existing search/engine/read services.

    Provider processing must be explicitly admitted by the composition owner.
    Only canonical labels and opaque claim IDs leave this process; no corpus
    prose, scenario strings, amounts or raw questions are sent to a provider.
    """

    def __init__(
        self,
        llm: LLMClient,
        search: SearchReader,
        comparison: ComparisonProtocol,
        evidence: EvidenceService,
        resolve_manifest: Callable[[UUID], SnapshotManifest],
        *,
        check_read_access: Callable[[SnapshotManifest], None],
        provider_processing_allowed: bool = False,
        timeout_ms: int = 45_000,
        call_timeout_ms: int = 20_000,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not 1 <= timeout_ms <= 45_000 or not 1 <= call_timeout_ms <= 20_000:
            raise ValueError("ASSISTANT_TIMEOUT_INVALID")
        if isinstance(llm, GroqLLM) and not provider_processing_allowed:
            raise ValueError("ASSISTANT_PROVIDER_PROCESSING_NOT_ADMITTED")
        self.llm, self.search, self.comparison, self.evidence = llm, search, comparison, evidence
        self.resolve_manifest, self.check_read_access = resolve_manifest, check_read_access
        self.timeout_ms, self.call_timeout_ms = timeout_ms, call_timeout_ms
        self.clock = clock or (lambda: datetime.now(UTC))

    def _read(
        self, manifest: SnapshotManifest
    ) -> tuple[tuple[dict[str, object], ...], tuple[EvidenceRef, ...]]:
        self.check_read_access(manifest)
        records = self.evidence.read_published(manifest)
        ids = {
            str(ref)
            for item in records
            for ref in TariffCandidate.model_validate(item["candidate"]).evidence_ids
        }
        with self.evidence.factory() as session:
            rows = session.scalars(
                select(RefRow).where(RefRow.id.in_(ids)).order_by(RefRow.id)
            ).all()
            refs = tuple(
                EvidenceRef.model_validate(
                    {
                        name: getattr(row, name)
                        for name in EvidenceRef.model_fields
                        if name != "schema_version"
                    }
                )
                for row in rows
            )
        # A second proof check closes the separate ref-query boundary.
        if (
            self.evidence.read_published(manifest) != records
            or {str(ref.id) for ref in refs} != ids
        ):
            raise ValueError("ASSISTANT_EVIDENCE_CHANGED")
        return records, refs

    async def _model(self, request: LLMRequest, deadline: float) -> dict[str, object] | None:
        remaining = min(self.call_timeout_ms, int((deadline - time.monotonic()) * 1000))
        if remaining < 1:
            return None
        request = request.model_copy(update={"timeout_ms": remaining})
        try:
            response = await asyncio.wait_for(self.llm.complete(request), remaining / 1000)
            if isinstance(response, LLMError):
                return None
            return validate_output(request, response.parsed_json)
        except (TimeoutError, OutputValidationError, ValidationError):
            return None

    async def answer(self, request: QuestionRequest, *, request_id: UUID) -> AnswerEnvelope:
        # Includes authorization, DB retrieval, both model calls and final read.
        deadline = time.monotonic() + self.timeout_ms / 1000
        async with asyncio.timeout(self.timeout_ms / 1000), AsyncExitStack() as stack:
            manifest = await asyncio.to_thread(self.resolve_manifest, request.snapshot_id)
            if manifest.snapshot_id != request.snapshot_id:
                raise ValueError("ASSISTANT_SNAPSHOT_MISMATCH")
            records, refs = await asyncio.to_thread(self._read, manifest)
            as_of = request.scenario.as_of if request.scenario else self.clock().date()
            minimized = minimize_question(request)
            if minimized.payload is None:
                return render_notice(manifest, as_of, minimized.clarification or "Уточните запрос.")
            hints = json.loads(minimized.payload)
            banks = request.bank_codes or cast(tuple[BankCode, ...], tuple(hints["bank_codes"]))
            metrics = request.metric_codes or tuple(hints["metric_codes"])
            if not set(metrics) <= METRICS.keys():
                return render_notice(manifest, as_of, "Выберите поддерживаемый критерий сравнения.")
            mode = hints["intent_hint"]
            if mode == "compare" and not banks and minimized.scenario_patch:
                banks = cast(tuple[BankCode, ...], BANK_CODES)
            if mode == "clarify" or not metrics or (mode == "compare" and len(banks) < 2):
                return render_notice(
                    manifest,
                    as_of,
                    "Укажите банки, критерий и параметры сценария; "
                    "общий лучший банк не определяется.",
                )
            if mode == "facts" and not banks:
                return render_notice(manifest, as_of, "Укажите банк.")
            patch = minimized.scenario_patch or {}
            scenario = request.scenario
            if scenario is not None:
                # Structured input is authoritative; contradictory text is unclear.
                payload = scenario.model_dump(mode="json")
                if any(
                    payload[key] is not None and str(payload[key]) != str(value)
                    for key, value in patch.items()
                ):
                    return render_notice(
                        manifest, as_of, "Параметры вопроса и сценария расходятся; уточните их."
                    )
                payload.update(patch)
            else:
                metric = METRICS[metrics[0]]
                payload = dict(
                    payer=metric.payer[0],
                    operation=metric.operation[0],
                    currency="RUB",
                    as_of=as_of.isoformat(),
                )
                payload.update(patch)
            scenario = Scenario.model_validate(payload)
            if isinstance(self.llm, GroqLLM):
                if current_budget_user() is None:
                    raise ValueError("ASSISTANT_AUTHENTICATED_BUDGET_USER_REQUIRED")
                await stack.enter_async_context(self.llm.question_scope())
            # Strictly bind each slot to locally admitted input. LLM may clarify,
            # but cannot change intent, bank, metric, date, amounts or scope.
            schema = IntentResult.model_json_schema()
            properties = schema["properties"]
            properties["intent"] = {"type": "string", "enum": [mode, "clarify"]}
            properties["bank_codes"] = {
                "type": "array",
                "items": {"type": "string", "enum": list(banks or BANK_CODES)},
                "uniqueItems": True,
            }
            properties["metric_codes"] = {
                "type": "array",
                "items": {"type": "string", "enum": list(metrics)},
                "uniqueItems": True,
            }
            # No sensitive scenario details sent, even in output schema.
            properties["scenario_patch"] = {"type": "object", "additionalProperties": False}
            intent_request = LLMRequest(
                purpose="intent",
                template_version="snap14-intent-v2",
                messages=(
                    LLMMessage(
                        role="system",
                        content="Select the supplied bounded domain intent. "
                        "Do not add facts or scenario values.",
                    ),
                    LLMMessage(
                        role="user",
                        content=json.dumps(
                            {"intent_hint": mode, "bank_codes": banks, "metric_codes": metrics}
                        ),
                    ),
                ),
                output_schema=schema,
                max_output_tokens=300,
                timeout_ms=self.call_timeout_ms,
                request_id=uuid5(_REQUEST_NAMESPACE, f"{request_id}:intent"),
            )
            output = await self._model(intent_request, deadline)
            fallback = output is None
            needs_clarification = False
            if output is not None:
                intent = IntentResult.model_validate(output)
                if intent.scenario_patch or (
                    intent.intent != "clarify"
                    and (
                        intent.intent != mode
                        or intent.bank_codes != banks
                        or intent.metric_codes != metrics
                    )
                ):
                    fallback = True
                elif intent.intent == "clarify" and not isinstance(self.llm, FakeLLM):
                    needs_clarification = True
                elif intent.intent == "clarify":
                    # Default Fake intentionally clarifies; local canonical route
                    # still permits offline end-to-end exercise and honest fallback.
                    fallback = True
            # Revalidate after the intent delay, before touching retrieved content.
            current, current_refs = await asyncio.to_thread(self._read, manifest)
            if (current, current_refs) != (records, refs):
                raise ValueError("ASSISTANT_EVIDENCE_CHANGED")
            if needs_clarification:
                return render_notice(manifest, as_of, "Уточните банки, критерий и сценарий.")
            comparison = None
            selected: tuple[tuple[UUID, TariffCandidate, bool], ...] = ()
            fact_limitations: list[str] = []
            if mode == "compare":
                comparison = await asyncio.to_thread(
                    asyncio.run,
                    self.comparison.compare(
                        ComparisonRequest(
                            snapshot_id=request.snapshot_id,
                            bank_codes=banks,
                            metric_codes=metrics,
                            scenario=scenario,
                        )
                    ),
                )
                baseline = render_comparison(manifest, comparison, refs, fallback=fallback)
            else:
                hits: list[SearchHit] = []
                for metric_code in metrics:
                    found = await asyncio.to_thread(
                        asyncio.run,
                        self.search.search(
                            SearchRequest(
                                snapshot_id=request.snapshot_id,
                                query=_SEARCH_TERMS.get(metric_code, metric_code),
                                bank_codes=banks or None,
                                metric_codes=(metric_code,),
                                limit=10,
                            )
                        ),
                    )
                    hits.extend(found)
                allowed_refs = {ref.id: ref for ref in refs}
                matched: set[UUID] = set()
                for hit in hits:
                    if hit.snapshot_id != manifest.snapshot_id:
                        raise ValueError("ASSISTANT_SEARCH_SNAPSHOT_MISMATCH")
                    for ref_id in hit.evidence_ids:
                        ref = allowed_refs.get(ref_id)
                        if ref is None or (
                            ref.chunk_id,
                            ref.source_version_id,
                            ref.raw_sha256,
                            ref.locator,
                        ) != (hit.chunk_id, hit.source_version_id, hit.raw_sha256, hit.locator):
                            raise ValueError("ASSISTANT_SEARCH_EVIDENCE_INVALID")
                        matched.add(ref_id)
                selected_list = []
                for item in records:
                    candidate = TariffCandidate.model_validate(item["candidate"])
                    if (
                        candidate.metric_code in metrics
                        and (not banks or candidate.bank_code in banks)
                        and matched.intersection(candidate.evidence_ids)
                    ):
                        selected_list.append(
                            (
                                UUID(str(item["fact_id"])),
                                candidate,
                                item.get("eligible_for_comparison") is True,
                            )
                        )
                        limitations = item.get("limitations", ())
                        if not isinstance(limitations, (list, tuple)) or not all(
                            isinstance(value, str) for value in limitations
                        ):
                            raise ValueError("ASSISTANT_PUBLISHED_LIMITATIONS_INVALID")
                        fact_limitations.extend(limitations)
                selected = tuple(selected_list)
                baseline = render_facts(
                    manifest,
                    scenario,
                    selected,
                    refs,
                    documents=mode == "documents",
                    fallback=fallback,
                    fact_limitations=tuple(dict.fromkeys(fact_limitations)),
                )
            explanation = None
            if baseline.claims and len(baseline.claims) <= 50 and baseline.status != "insufficient":
                explain_schema = ExplainResult.model_json_schema()
                explain_schema["allowed_claim_ids"] = [str(claim.id) for claim in baseline.claims]
                explain_schema["allowed_templates"] = [
                    "claim_fact",
                    "claim_comparison",
                    "claim_absence",
                ]
                output = await self._model(
                    LLMRequest(
                        purpose="explain",
                        template_version="snap14-explain-v2",
                        messages=(
                            LLMMessage(
                                role="user",
                                content=json.dumps(
                                    {
                                        "claim_ids": explain_schema["allowed_claim_ids"],
                                        "template_ids": explain_schema["allowed_templates"],
                                    }
                                ),
                            ),
                        ),
                        output_schema=explain_schema,
                        max_output_tokens=300,
                        timeout_ms=self.call_timeout_ms,
                        request_id=uuid5(_REQUEST_NAMESPACE, f"{request_id}:explain"),
                    ),
                    deadline,
                )
                if output is None:
                    fallback = True
                else:
                    explanation = ExplainResult.model_validate(output)
            # No stale evidence after explain or a provider timeout/429.
            final_records, final_refs = await asyncio.to_thread(self._read, manifest)
            if (final_records, final_refs) != (records, refs):
                raise ValueError("ASSISTANT_EVIDENCE_CHANGED")
            answer = (
                render_comparison(
                    manifest, comparison, refs, explanation=explanation, fallback=fallback
                )
                if comparison is not None
                else render_facts(
                    manifest,
                    scenario,
                    selected,
                    refs,
                    documents=mode == "documents",
                    explanation=explanation,
                    fallback=fallback,
                    fact_limitations=tuple(dict.fromkeys(fact_limitations)),
                )
            )
            model = (
                "Groq openai/gpt-oss-120b"
                if isinstance(self.llm, GroqLLM)
                else "Fake (offline)"
                if isinstance(self.llm, FakeLLM)
                else "LLM Protocol"
            )
            return answer.model_copy(
                update={"text": f"Модель: {model}.\nСтатус: {answer.status}.\n" + answer.text}
            )


class ComparisonAnswerHarness:
    """Only Fake is supported until full provider/input/access composition exists."""

    def __init__(self, llm: FakeLLM) -> None:
        if not isinstance(llm, FakeLLM):
            raise TypeError("ASSISTANT_OFFLINE_HARNESS_REQUIRES_FAKE")
        self.llm = llm

    async def answer(
        self,
        manifest: SnapshotManifest,
        comparison: ComparisonResult,
        evidence: tuple[EvidenceRef, ...],
        *,
        check_read_access: Callable[[SnapshotManifest], None],
        request_id: UUID,
        timeout_ms: int = 20_000,
    ) -> AnswerEnvelope:
        # The supplied guard must recheck frozen membership, rights and hashes;
        # exceptions propagate before any model invocation or content rendering.
        check_read_access(manifest)
        baseline = render_comparison(manifest, comparison, evidence)
        if baseline.status == "insufficient":
            return baseline.model_copy(update={"text": "Модель: Fake (offline).\n" + baseline.text})
        if not 1 <= timeout_ms <= 20_000:
            raise ValueError("ASSISTANT_TIMEOUT_INVALID")
        schema = ExplainResult.model_json_schema()
        schema["allowed_claim_ids"] = [str(claim.id) for claim in baseline.claims]
        schema["allowed_templates"] = ["claim_fact", "claim_comparison", "claim_absence"]
        request = LLMRequest(
            purpose="explain",
            template_version="snap14-offline-explain-v1",
            messages=(
                LLMMessage(
                    role="user",
                    content=json.dumps(
                        {
                            "claim_ids": schema["allowed_claim_ids"],
                            "template_ids": schema["allowed_templates"],
                        },
                        sort_keys=True,
                    ),
                ),
            ),
            output_schema=schema,
            max_output_tokens=1000,
            timeout_ms=timeout_ms,
            request_id=request_id,
        )
        explanation = None
        fallback = False
        try:
            response = await asyncio.wait_for(self.llm.complete(request), timeout_ms / 1000)
            if isinstance(response, LLMError):
                fallback = True
            else:
                explanation = ExplainResult.model_validate(
                    validate_output(
                        request,
                        response.parsed_json,
                    )
                )
        except (TimeoutError, OutputValidationError):
            fallback = True
        # Recheck revocation even if the guard was valid before a delayed response.
        check_read_access(manifest)
        answer = render_comparison(
            manifest,
            comparison,
            evidence,
            explanation=explanation,
            fallback=fallback,
        )
        # Fixed harness metadata; untrusted response.model_id never enters prose.
        return answer.model_copy(update={"text": "Модель: Fake (offline).\n" + answer.text})
