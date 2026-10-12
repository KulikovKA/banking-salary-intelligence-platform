"""Offline SNAP-14 explanation harness; full question orchestration is BLOCKED.

SearchService is not merged at the base revision. This component intentionally
does not implement facts/documents/intent routing or expose an AssistantService.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from uuid import UUID

from app.contracts.api import AnswerEnvelope
from app.contracts.comparison import ComparisonResult
from app.contracts.evidence import EvidenceRef
from app.contracts.llm import ExplainResult, LLMError, LLMMessage, LLMRequest
from app.corpus.service import SnapshotManifest
from app.llm.base import OutputValidationError, validate_output
from app.llm.fake import FakeLLM

from .render import render_comparison


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
