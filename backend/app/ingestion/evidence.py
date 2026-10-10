"""Evidence contract for later parsers; a validated candidate is never publication."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExtractionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    source_version_id: UUID
    raw_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    extraction_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    parser_version: str = Field(min_length=1)
    corpus_kind: Literal["synthetic", "real"]
    quote: str = Field(min_length=1)
    quote_start: int = Field(ge=0)
    quote_end: int = Field(gt=0)
    physical_page: int | None = Field(default=None, ge=1)
    table_cell: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    effective_date_status: Literal["explicit", "analyst_confirmed", "unknown"] = "unknown"
    geography: Literal["federal", "regional", "unknown"] = "unknown"
    region_codes: tuple[str, ...] = ()
    employer_segment: str | None = None
    package: str | None = None
    contract_date_condition: str | None = None
    publication_state: Literal["pending_review"] = "pending_review"

    @model_validator(mode="after")
    def validate_reference(self) -> "ExtractionEvidence":
        if self.quote_end - self.quote_start != len(self.quote):
            raise ValueError("EVIDENCE_OFFSET_INVALID")
        if self.geography == "regional" and not self.region_codes:
            raise ValueError("EVIDENCE_GEOGRAPHY_INVALID")
        if self.effective_date_status == "unknown" and self.effective_from is not None:
            raise ValueError("EVIDENCE_DATE_INVALID")
        if self.effective_to and self.effective_from and self.effective_to <= self.effective_from:
            raise ValueError("EVIDENCE_DATE_INVALID")
        return self

    def check_chunk(self, immutable_chunk: str) -> None:
        if immutable_chunk[self.quote_start : self.quote_end] != self.quote:
            raise ValueError("EVIDENCE_QUOTE_INVALID")
