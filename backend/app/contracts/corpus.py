"""Read-side snapshot and extraction contracts."""

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, field_validator

from .base import BANK_CODES, BankCode, ContractModel, CorpusKind, Sha256, require_aware_utc


class Snapshot(ContractModel):
    id: UUID
    revision: int = Field(ge=1)
    corpus_kind: CorpusKind
    state: Literal["draft", "frozen", "revoked"]
    created_at: datetime
    frozen_at: datetime | None = None
    manifest_sha256: Sha256 | None = None

    @field_validator("created_at", "frozen_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)


class SnapshotMember(ContractModel):
    snapshot_id: UUID
    source_version_id: UUID
    extraction_run_id: UUID


class SearchRequest(ContractModel):
    snapshot_id: UUID
    query: str = Field(min_length=1, max_length=1000)
    bank_codes: tuple[BankCode, ...] | None = Field(default=None, min_length=1, max_length=4)
    metric_codes: tuple[str, ...] | None = Field(default=None, min_length=1, max_length=20)
    limit: int = Field(default=10, ge=1, le=10)

    @field_validator("bank_codes")
    @classmethod
    def validate_bank_filter(
        cls, values: tuple[BankCode, ...] | None
    ) -> tuple[BankCode, ...] | None:
        if values is not None and (
            len(set(values)) != len(values) or not set(values) <= set(BANK_CODES)
        ):
            raise ValueError("BANK_CODES_INVALID")
        return values

    @field_validator("metric_codes")
    @classmethod
    def validate_metric_filter(cls, values: tuple[str, ...] | None) -> tuple[str, ...] | None:
        import re

        if values is not None and (
            len(set(values)) != len(values)
            or any(not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", code) for code in values)
        ):
            raise ValueError("METRIC_CODES_INVALID")
        return values


class SearchHit(ContractModel):
    chunk_id: UUID
    text: str
    locator: "Locator"
    evidence_ids: tuple[UUID, ...]
    source_version_id: UUID
    raw_sha256: Sha256
    snapshot_id: UUID
    score: float = Field(ge=0, allow_inf_nan=False)


from .parsing import Locator  # noqa: E402

SearchHit.model_rebuild()


class SnapshotReadService(Protocol):
    """Read only frozen, currently authorized corpus members."""

    async def get_snapshot(self, snapshot_id: UUID) -> Snapshot: ...

    async def search(self, request: SearchRequest) -> tuple[SearchHit, ...]: ...


__all__ = ["SearchHit", "SearchRequest", "Snapshot", "SnapshotMember", "SnapshotReadService"]
