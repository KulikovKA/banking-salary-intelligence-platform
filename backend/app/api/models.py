"""API-owned read views; domain DTOs remain frozen."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.auth.api import StrictModel
from app.contracts.base import BankCode, ContractModel
from app.contracts.corpus import SearchHit, Snapshot
from app.contracts.tariffs import TariffCandidate


class Identity(StrictModel):
    id: UUID
    login: str
    role: Literal["admin", "analyst"]


class LoginResult(Identity):
    csrf_token: str


class CsrfChallenge(StrictModel):
    csrf_token: str


class LogoutResult(StrictModel):
    logged_out: bool


class InvitationResult(StrictModel):
    id: UUID
    login: str
    role: Literal["admin", "analyst"]
    expires_at: datetime
    token: str


class SnapshotView(Snapshot):
    region: str
    employer_segment: str
    bank_codes: tuple[BankCode, ...]
    document_count: int
    missing_banks: tuple[BankCode, ...]


class SnapshotPage(ContractModel):
    items: tuple[SnapshotView, ...]
    offset: int
    limit: int
    next_offset: int | None


class SearchResult(ContractModel):
    status: str
    hits: tuple[SearchHit, ...]
    absence_of_evidence: bool
    omitted_oversize: bool


class DocumentView(ContractModel):
    source_version_id: UUID
    snapshot_id: UUID
    corpus_revision: int
    corpus_kind: Literal["real", "synthetic"]
    bank_code: BankCode
    document_type: str
    raw_sha256: str
    byte_size: int
    media_type: str
    acquired_at: datetime
    download_url: str


class CandidateView(ContractModel):
    candidate: TariffCandidate
    decision: Literal["approved", "rejected", "needs_review", "pending_review"]
    review_id: UUID | None


class CandidatePage(ContractModel):
    items: tuple[CandidateView, ...]
    offset: int
    limit: int
    next_offset: int | None


class ReviewBody(StrictModel):
    snapshot_id: UUID
    decision: Literal["approved", "rejected", "needs_review"]
    reason: str = Field(min_length=1, max_length=2000)
    field_evidence: dict[str, tuple[UUID, ...]] | None = Field(default=None, max_length=30)


class ReviewResult(ContractModel):
    review_id: UUID
    fact_id: UUID | None
    published: bool


class FreezeResult(ContractModel):
    snapshot_id: UUID
    state: Literal["frozen"]
    manifest_sha256: str
    idempotent: bool
