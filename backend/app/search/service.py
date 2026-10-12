"""PostgreSQL full text search over one currently readable frozen snapshot."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, or_, select

from app.contracts.corpus import SearchHit, SearchRequest
from app.corpus.models import DocumentChunk, ExtractionRun, Snapshot, SnapshotMember
from app.corpus.service import CorpusError, CorpusService, SnapshotManifest
from app.evidence.service import EvidenceService
from app.registry.models import Bank, Blob, Source, SourcePolicy, SourceVersion
from app.tariffs.models import EvidenceRef, FactReview, PublishedFact, TariffCandidate

MAX_QUERY_CHARS = 1000
MAX_RESULTS = 10
MAX_RESULT_TEXT_CHARS = 10_000


@dataclass(frozen=True, slots=True)
class SearchOutcome:
    """Internal status wrapper so callers can render an explicit empty result."""

    status: str
    hits: tuple[SearchHit, ...]
    absence_of_evidence: bool
    omitted_oversize: bool = False


ManifestProvider = Callable[[UUID], SnapshotManifest]


class SnapshotSearchService:
    """Search only exact members admitted by the selected frozen manifest.

    The provider supplies the operator controlled manifest for a requested ID.
    ``read_published`` revalidates its exact membership, latest review, provenance,
    evidence proof, current permission, and stored originals before each query.
    """

    def __init__(
        self,
        corpus: CorpusService,
        evidence: EvidenceService,
        manifest_provider: ManifestProvider,
    ) -> None:
        self.corpus = corpus
        self.evidence = evidence
        self.factory = corpus.factory
        self.manifest_provider = manifest_provider

    async def search(self, request: SearchRequest) -> tuple[SearchHit, ...]:
        """Frozen SnapshotReadService contract; empty tuple means no evidence found."""
        return (await self.search_with_status(request)).hits

    async def search_with_status(self, request: SearchRequest) -> SearchOutcome:
        """Return a typed absence signal alongside bounded hits for renderers."""
        if not isinstance(request, SearchRequest):
            raise TypeError("SEARCH_REQUEST_REQUIRED")
        query_text = request.query.strip()
        if not query_text or len(query_text) > MAX_QUERY_CHARS:
            raise ValueError("SEARCH_QUERY_INVALID")
        manifest = self.manifest_provider(request.snapshot_id)
        if manifest.snapshot_id != request.snapshot_id or manifest.corpus_kind not in {
            "real",
            "synthetic",
        }:
            raise CorpusError("SNAPSHOT_IDENTITY_MISMATCH")

        # This validates that tariff citations come from currently published facts.
        # Generic document hits may have no tariff fact and remain ordinary excerpts.
        published = self.evidence.read_published(manifest)
        candidate_ids: list[str] = []
        for item in published:
            candidate = item.get("candidate")
            if isinstance(candidate, dict) and isinstance(candidate.get("id"), str):
                candidate_ids.append(candidate["id"])
        published_candidate_ids = tuple(candidate_ids)
        allowed_evidence = self._published_evidence_by_chunk(published_candidate_ids)

        with self.factory() as session:
            snapshot = session.get(Snapshot, str(request.snapshot_id))
            if (
                snapshot is None
                or snapshot.state != "frozen"
                or snapshot.revision != manifest.revision
                or snapshot.corpus_kind != manifest.corpus_kind
                or snapshot.manifest_sha256 != manifest.manifest_sha256
            ):
                raise CorpusError("SNAPSHOT_NOT_READABLE")

            russian_query = func.plainto_tsquery("russian", query_text)
            simple_query = func.plainto_tsquery("simple", query_text)
            vector = DocumentChunk.search_vector
            rank = func.greatest(
                func.ts_rank_cd(vector, russian_query),
                func.ts_rank_cd(vector, simple_query),
            )

            stmt = (
                select(
                    DocumentChunk,
                    ExtractionRun,
                    SourceVersion,
                    Blob,
                    Bank.code.label("bank_code"),
                    rank.label("rank"),
                )
                .join(ExtractionRun, ExtractionRun.id == DocumentChunk.extraction_run_id)
                .join(SnapshotMember, SnapshotMember.extraction_run_id == ExtractionRun.id)
                .join(Snapshot, Snapshot.id == SnapshotMember.snapshot_id)
                .join(SourceVersion, SourceVersion.id == SnapshotMember.source_version_id)
                .join(Source, Source.id == SourceVersion.source_id)
                .join(Bank, Bank.id == Source.bank_id)
                .join(SourcePolicy, SourcePolicy.id == Source.policy_id)
                .join(Blob, Blob.id == SourceVersion.blob_id)
                .where(
                    Snapshot.id == str(request.snapshot_id),
                    Snapshot.state == "frozen",
                    Snapshot.corpus_kind == manifest.corpus_kind,
                    ExtractionRun.corpus_kind == manifest.corpus_kind,
                    ExtractionRun.status == "ok",
                    Source.corpus_kind == manifest.corpus_kind,
                    Blob.corpus_kind == manifest.corpus_kind,
                    SourceVersion.content_state == "accepted",
                    SourcePolicy.collection_decision == "approved",
                    or_(vector.op("@@")(russian_query), vector.op("@@")(simple_query)),
                )
            )
            if request.bank_codes:
                stmt = stmt.where(Bank.code.in_(request.bank_codes))
            if request.metric_codes:
                stmt = (
                    stmt.join(
                        EvidenceRef,
                        EvidenceRef.chunk_id == DocumentChunk.id,
                    )
                    .join(TariffCandidate, TariffCandidate.id == EvidenceRef.candidate_id)
                    .join(PublishedFact, PublishedFact.candidate_id == TariffCandidate.id)
                    .join(FactReview, FactReview.id == PublishedFact.review_id)
                    .where(
                        PublishedFact.snapshot_id == Snapshot.id,
                        TariffCandidate.metric_code.in_(request.metric_codes),
                        TariffCandidate.corpus_kind == manifest.corpus_kind,
                        FactReview.decision == "approved",
                        FactReview.validation["valid"].as_boolean().is_(True),
                    )
                )
            oversized = session.scalar(
                stmt.with_only_columns(DocumentChunk.id)
                .where(func.char_length(DocumentChunk.text) > MAX_RESULT_TEXT_CHARS)
                .distinct()
                .limit(1)
            ) is not None
            rows = cast(
                Sequence[tuple[DocumentChunk, ExtractionRun, SourceVersion, Blob, str, float]],
                session.execute(
                    stmt.distinct()
                    .where(func.char_length(DocumentChunk.text) <= MAX_RESULT_TEXT_CHARS)
                    .order_by(
                        rank.desc(), SourceVersion.id, DocumentChunk.ordinal, DocumentChunk.id
                    )
                    .limit(min(request.limit, MAX_RESULTS))
                ).all(),
            )

            hits: list[SearchHit] = []
            for chunk, extraction, version, _blob, _bank_code, score in rows:
                hits.append(
                    SearchHit(
                        chunk_id=UUID(chunk.id),
                        text=chunk.text,
                        locator=cast(Any, chunk.locator),
                        evidence_ids=tuple(
                            UUID(value) for value in allowed_evidence.get(chunk.id, ())
                        ),
                        source_version_id=UUID(version.id),
                        raw_sha256=extraction.raw_sha256,
                        snapshot_id=request.snapshot_id,
                        score=float(score),
                    )
                )
            result = tuple(hits)
        absence = not result and not oversized
        return SearchOutcome(
            status=(
                "results"
                if result
                else "result_exceeds_output_bound"
                if oversized
                else "absence_of_evidence"
            ),
            hits=result,
            absence_of_evidence=absence,
            omitted_oversize=oversized,
        )

    def _published_evidence_by_chunk(
        self, candidate_ids: tuple[str, ...]
    ) -> dict[str, tuple[str, ...]]:
        if not candidate_ids:
            return {}
        with self.factory() as session:
            rows = session.execute(
                select(EvidenceRef.chunk_id, EvidenceRef.id)
                .join(TariffCandidate, TariffCandidate.id == EvidenceRef.candidate_id)
                .join(PublishedFact, PublishedFact.candidate_id == TariffCandidate.id)
                .where(TariffCandidate.id.in_(candidate_ids))
                .order_by(EvidenceRef.chunk_id, EvidenceRef.id)
            ).all()
        grouped: dict[str, list[str]] = {}
        for chunk_id, evidence_id in rows:
            grouped.setdefault(chunk_id, []).append(evidence_id)
        return {chunk: tuple(ids) for chunk, ids in grouped.items()}
