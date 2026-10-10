"""Evidence references and compatibility adapter for the ingestion evidence DTO."""

from datetime import datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .base import ContractModel, Sha256, require_aware_utc
from .parsing import Locator

if TYPE_CHECKING:
    from app.ingestion.evidence import ExtractionEvidence

SupportRole = Literal["value", "unit", "basis", "condition", "scope", "date"]


class EvidenceRef(ContractModel):
    id: UUID
    source_version_id: UUID
    extraction_run_id: UUID
    chunk_id: UUID
    raw_sha256: Sha256
    extraction_sha256: Sha256
    quote: str = Field(min_length=1)
    quote_start: int = Field(ge=0)
    quote_end: int = Field(gt=0)
    locator: Locator
    support_role: SupportRole
    original_url: str
    acquired_at: datetime

    @field_validator("acquired_at")
    @classmethod
    def validate_acquired_at(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @model_validator(mode="after")
    def validate_quote_offsets(self) -> "EvidenceRef":
        if self.quote_end - self.quote_start != len(self.quote):
            raise ValueError("EVIDENCE_OFFSET_INVALID")
        return self

    def check_chunk(self, immutable_chunk: str) -> None:
        if immutable_chunk[self.quote_start : self.quote_end] != self.quote:
            raise ValueError("EVIDENCE_QUOTE_INVALID")


def extraction_evidence_to_ref(
    evidence: "ExtractionEvidence",
    *,
    evidence_id: UUID,
    extraction_run_id: UUID,
    chunk_id: UUID,
    extraction_sha256: str,
    locator: Locator,
    support_role: SupportRole,
    original_url: str,
    acquired_at: datetime,
) -> EvidenceRef:
    """Adapt the existing ingestion DTO without replacing or mutating its contract."""
    from app.ingestion.evidence import ExtractionEvidence

    if not isinstance(evidence, ExtractionEvidence):
        raise TypeError("EXTRACTION_EVIDENCE_REQUIRED")
    if evidence.physical_page is not None and isinstance(locator, dict):
        locator = {
            "kind": "pdf",
            "physical_page": evidence.physical_page,
            "table_cell": evidence.table_cell,
        }
    return EvidenceRef(
        id=evidence_id,
        source_version_id=evidence.source_version_id,
        extraction_run_id=extraction_run_id,
        chunk_id=chunk_id,
        raw_sha256=evidence.raw_sha256,
        extraction_sha256=extraction_sha256,
        quote=evidence.quote,
        quote_start=evidence.quote_start,
        quote_end=evidence.quote_end,
        locator=locator,
        support_role=support_role,
        original_url=original_url,
        acquired_at=acquired_at,
    )


__all__ = ["EvidenceRef", "extraction_evidence_to_ref"]
