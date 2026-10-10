"""Parser inputs, outputs, locator variants, and parser Protocol."""

from datetime import datetime
from typing import Annotated, Literal, Protocol, TypeAlias
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .base import ContractModel, CorpusKind, NonEmpty, Sha256, require_aware_utc


class PdfLocator(ContractModel):
    kind: Literal["pdf"]
    physical_page: int = Field(ge=1)
    bbox: (
        tuple[
            Annotated[float, Field(allow_inf_nan=False)],
            Annotated[float, Field(allow_inf_nan=False)],
            Annotated[float, Field(allow_inf_nan=False)],
            Annotated[float, Field(allow_inf_nan=False)],
        ]
        | None
    ) = None
    table_cell: str | None = None


class XlsxLocator(ContractModel):
    kind: Literal["xlsx"]
    sheet: NonEmpty
    cell_range: NonEmpty
    formula: str | None = None
    cached_value: str | None = None


class HtmlLocator(ContractModel):
    kind: Literal["html"]
    element_path: NonEmpty
    heading: str | None = None


Locator: TypeAlias = Annotated[PdfLocator | XlsxLocator | HtmlLocator, Field(discriminator="kind")]


class ParseRequest(ContractModel):
    source_version_id: UUID
    raw_sha256: Sha256
    kind: Literal["pdf", "xlsx", "html"]
    corpus_kind: CorpusKind
    parser_version: NonEmpty


class ParsedBlock(ContractModel):
    block_id: UUID
    text: str
    locator: Locator
    heading: str | None = None
    table_id: str | None = None
    relations: tuple[dict[str, str], ...] = ()


class ParseDiagnostic(ContractModel):
    code: NonEmpty
    message: str
    block_id: UUID | None = None


class ParseResult(ContractModel):
    status: Literal["ok", "needs_ocr", "unsupported", "failed"]
    extraction_sha256: Sha256 | None = None
    parser_version: NonEmpty
    blocks: tuple[ParsedBlock, ...] = ()
    diagnostics: tuple[ParseDiagnostic, ...] = ()

    @model_validator(mode="after")
    def validate_status_hash(self) -> "ParseResult":
        if self.status == "ok" and self.extraction_sha256 is None:
            raise ValueError("PARSE_OK_REQUIRES_EXTRACTION_HASH")
        return self


class Parser(Protocol):
    """Offline parser interface. Implementations receive verified local originals."""

    def parse(self, request: ParseRequest, original_path: str) -> ParseResult: ...


class ExtractionRun(ContractModel):
    id: UUID
    source_version_id: UUID
    raw_sha256: Sha256
    extraction_sha256: Sha256
    parser_version: NonEmpty
    corpus_kind: CorpusKind
    status: Literal["ok", "needs_ocr", "unsupported", "failed"]
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class Chunk(ContractModel):
    id: UUID
    extraction_run_id: UUID
    ordinal: int = Field(ge=0)
    text: str
    text_sha256: Sha256
    locator: Locator
    relations: tuple[dict[str, str], ...] = ()
