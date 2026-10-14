"""Versioned evaluation-only schema; runtime DTOs remain unchanged."""

from __future__ import annotations

from itertools import combinations
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.base import BankCode, Sha256
from app.contracts.parsing import Locator
from app.contracts.tariffs import Value

BANKS = ("sber", "vtb", "alfa", "kuban_credit")
PAIRS = tuple("/".join(pair) for pair in combinations(BANKS, 2))


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Evidence(Strict):
    id: str = Field(min_length=1)
    source_version_id: str = Field(min_length=1)
    extraction_run_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    raw_sha256: Sha256
    extraction_sha256: Sha256
    chunk_sha256: Sha256
    chunk_text: str
    quote: str = Field(min_length=1)
    quote_start: int = Field(ge=0)
    quote_end: int = Field(gt=0)
    locator: Locator


class Fact(Strict):
    id: str = Field(min_length=1)
    bank: BankCode
    family: str = Field(min_length=1)
    split: Literal["tune", "holdout"]
    human_review_id: str | None = None
    metric: str = Field(min_length=1)
    value: Value | None = None
    status: Literal["verified", "unknown", "individual", "conflict", "not_applicable"]
    payer: Literal["employer", "employee"]
    operation: str = Field(min_length=1)
    period: str | None
    scope: dict
    effective_date: str | None
    required_conditions: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = Field(min_length=1)


class Question(Strict):
    id: str = Field(min_length=1)
    banks: tuple[BankCode, ...] = Field(min_length=1, max_length=2)
    family: str = Field(min_length=1)
    split: Literal["tune", "holdout"]
    query: str = Field(min_length=1, max_length=2000)
    relevant_chunk_ids: tuple[str, ...] = Field(min_length=1)
    allowed_claims: tuple[str, ...] = ()
    allowed_numbers: tuple[str, ...] = ()
    expected_intent: Literal["compare", "facts", "documents", "clarify"]


class Comparison(Strict):
    id: str = Field(min_length=1)
    banks: tuple[BankCode, BankCode]
    family: str = Field(min_length=1)
    split: Literal["tune", "holdout"]
    request: dict
    records: tuple[dict, ...]
    expected: dict


class Coverage(Strict):
    banks: tuple[BankCode, BankCode]
    metric: str = Field(min_length=1)
    fact_ids: tuple[str, ...] = Field(min_length=2)
    comparable: bool
    numeric_employer_cost: bool


class Gold(Strict):
    schema_version: Literal[1]
    corpus_kind: Literal["synthetic", "real"]
    snapshot_id: str = Field(min_length=1)
    corpus_revision: int = Field(ge=1)
    facts: tuple[Fact, ...]
    evidence: tuple[Evidence, ...]
    questions: tuple[Question, ...]
    comparisons: tuple[Comparison, ...]
    coverage: tuple[Coverage, ...] = ()

    @model_validator(mode="after")
    def identities_and_splits(self) -> Gold:
        for group in (self.facts, self.evidence, self.questions, self.comparisons):
            if len({item.id for item in group}) != len(group):
                raise ValueError("DUPLICATE_GOLD_ID")
        families: dict[str, str] = {}
        for item in (*self.facts, *self.questions, *self.comparisons):
            if item.family in families and families[item.family] != item.split:
                raise ValueError("DOCUMENT_FAMILY_LEAKAGE")
            families[item.family] = item.split
        evidence = {item.id for item in self.evidence}
        chunks = {item.chunk_id for item in self.evidence}
        for fact in self.facts:
            if len(set(fact.evidence_ids)) != len(fact.evidence_ids):
                raise ValueError("DUPLICATE_EVIDENCE_ID")
            if not set(fact.evidence_ids) <= evidence:
                raise ValueError("GOLD_EVIDENCE_MISSING")
        for question in self.questions:
            if len(set(question.banks)) != len(question.banks):
                raise ValueError("DUPLICATE_BANK")
            if not set(question.relevant_chunk_ids) <= chunks:
                raise ValueError("RELEVANT_CHUNK_MISSING")
        for item in (*self.comparisons, *self.coverage):
            if item.banks[0] == item.banks[1]:
                raise ValueError("PAIR_REQUIRES_TWO_BANKS")
        fact_ids = {f.id for f in self.facts}
        for item in self.coverage:
            if not set(item.fact_ids) <= fact_ids:
                raise ValueError("COVERAGE_FACT_MISSING")
        return self


class ObservedFact(Strict):
    id: str
    value: Value | None
    status: Literal["verified", "unknown", "individual", "conflict", "not_applicable"]
    payer: Literal["employer", "employee"]
    operation: str
    period: str | None
    scope: dict
    effective_date: str | None
    conditions: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()


class ObservedQuestion(Strict):
    id: str
    retrieved_chunk_ids: tuple[str, ...] = ()
    claims: tuple[str, ...] = ()
    numbers: tuple[str, ...] = ()
    intent: Literal["compare", "facts", "documents", "clarify"]
    fallback: bool = False
    model_id: str | None = None
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    error: str | None = None


class ObservedComparison(Strict):
    id: str
    result: dict


class Observations(Strict):
    schema_version: Literal[1]
    corpus_kind: Literal["synthetic", "real"]
    snapshot_id: str
    corpus_revision: int = Field(ge=1)
    gold_sha256: Sha256
    mode: Literal["offline_replay", "synthetic_engine", "real_capture"]
    facts: tuple[ObservedFact, ...]
    evidence: tuple[Evidence, ...]
    questions: tuple[ObservedQuestion, ...]
    comparisons: tuple[ObservedComparison, ...]

    @model_validator(mode="after")
    def unique_ids(self) -> Observations:
        for group in (self.facts, self.evidence, self.questions, self.comparisons):
            if len({item.id for item in group}) != len(group):
                raise ValueError("DUPLICATE_OBSERVATION_ID")
        if self.corpus_kind == "real" and self.mode != "real_capture":
            raise ValueError("REAL_REQUIRES_CAPTURE")
        if self.corpus_kind == "synthetic" and self.mode == "real_capture":
            raise ValueError("SYNTHETIC_NOT_REAL_CAPTURE")
        return self
