"""Authenticated routes delegate domain decisions to merged services."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.routing import APIRoute
from sqlalchemy import select
from starlette.responses import Response

from app.assistant.service import AssistantService
from app.auth.api import create_auth_router
from app.auth.models import AuthSession, AuthUser
from app.contracts.api import AnswerEnvelope, QuestionRequest
from app.contracts.base import BankCode
from app.contracts.comparison import ComparisonRequest, ComparisonResult
from app.contracts.corpus import SearchRequest
from app.contracts.tariffs import TariffCandidate as CandidateDTO
from app.corpus.models import Snapshot, SnapshotMember
from app.corpus.service import CorpusError, SnapshotManifest
from app.evidence.validation import SemanticConfirmation
from app.llm.budget import reset_budget_user, set_budget_user
from app.registry.models import Blob, SourceVersion
from app.tariffs.models import FactReview, TariffCandidate

from .composition import ManifestResolver, Runtime
from .errors import ERROR_RESPONSES
from .models import (
    CandidatePage,
    CandidateView,
    CsrfChallenge,
    DocumentView,
    FreezeResult,
    Identity,
    InvitationResult,
    LoginResult,
    LogoutResult,
    ReviewBody,
    ReviewResult,
    SearchResult,
    SnapshotPage,
    SnapshotView,
)

IdentityTuple = tuple[AuthUser, AuthSession]


def create_router(runtime: Runtime) -> APIRouter:
    router = APIRouter(responses=ERROR_RESPONSES)
    auth_router = create_auth_router(
        runtime.factory, runtime.settings, limiter=runtime.login_limiter
    )
    auth_models = {
        "/csrf": CsrfChallenge,
        "/login": LoginResult,
        "/logout": LogoutResult,
        "/accept-invite": LoginResult,
        "/me": Identity,
        "/admin/invitations": InvitationResult,
    }
    # Reuse existing auth security closures; mount invitations at the frozen API path.
    for route in auth_router.routes:
        if not isinstance(route, APIRoute):
            continue
        suffix = route.path.removeprefix("/api/v1/auth")
        if suffix not in auth_models:
            continue
        path = "/api/v1/admin/invitations" if suffix == "/admin/invitations" else route.path
        router.add_api_route(
            path,
            route.endpoint,
            methods=list(route.methods or ()),
            tags=route.tags,
            response_model=auth_models[suffix],
            status_code=route.status_code,
            route_class_override=type(route),
        )

    def user(request: Request) -> IdentityTuple:
        return runtime.auth.require_user(request)

    def csrf(request: Request) -> IdentityTuple:
        return runtime.auth.require_csrf(request)

    user_dep = Depends(user)
    csrf_dep = Depends(csrf)

    def admin(identity: IdentityTuple = user_dep) -> IdentityTuple:
        if identity[0].role != "admin":
            raise HTTPException(403, "ROLE_REQUIRED")
        return identity

    def admin_csrf(identity: IdentityTuple = csrf_dep) -> IdentityTuple:
        if identity[0].role != "admin":
            raise HTTPException(403, "ROLE_REQUIRED")
        return identity

    admin_dep = Depends(admin)
    admin_csrf_dep = Depends(admin_csrf)

    def resolver_for(identity: IdentityTuple) -> ManifestResolver:
        def resolve(snapshot_id: UUID) -> SnapshotManifest:
            runtime.check_identity(identity)
            manifest = runtime.resolve_manifest(snapshot_id)
            with runtime.factory() as db:
                row = db.get(Snapshot, str(snapshot_id))
                if row is None or row.state != "frozen":
                    raise HTTPException(404, "OBJECT_UNAVAILABLE")
            runtime.evidence.read_published(manifest)
            return manifest

        return resolve

    def throttle(request: Request, identity: IdentityTuple, *, question: bool = False) -> None:
        limiter = runtime.question_limiter if question else runtime.read_limiter
        ip = request.client.host if request.client else "unknown"
        if not limiter.check_and_record(identity[0].id, ip):
            raise HTTPException(429, "RATE_LIMITED", headers={"Retry-After": "60"})

    def snapshot_view(manifest: SnapshotManifest) -> SnapshotView:
        with runtime.factory() as db:
            row = db.get(Snapshot, str(manifest.snapshot_id))
            if row is None:
                raise HTTPException(404, "OBJECT_UNAVAILABLE")
            return SnapshotView.model_validate(
                {
                    "id": row.id,
                    "revision": row.revision,
                    "corpus_kind": row.corpus_kind,
                    "state": row.state,
                    "created_at": row.created_at,
                    "frozen_at": row.frozen_at,
                    "manifest_sha256": row.manifest_sha256,
                    "region": manifest.region,
                    "employer_segment": manifest.employer_segment,
                    "bank_codes": sorted({item.bank_code for item in manifest.documents}),
                    "document_count": len(manifest.documents),
                    "missing_banks": sorted(
                        {item.bank_code for item in manifest.missing_documents}
                    ),
                }
            )

    @router.get("/api/v1/snapshots", response_model=SnapshotPage, tags=["snapshots"])
    def snapshots(
        request: Request,
        offset: int = Query(0, ge=0, le=100000),
        limit: int = Query(20, ge=1, le=100),
        identity: IdentityTuple = user_dep,
    ) -> SnapshotPage:
        throttle(request, identity)
        with runtime.factory() as db:
            ids = tuple(
                db.scalars(
                    select(Snapshot.id)
                    .where(Snapshot.state == "frozen")
                    .order_by(Snapshot.revision)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
        resolve = resolver_for(identity)
        items = []
        for value in ids[:limit]:
            try:
                items.append(snapshot_view(resolve(UUID(value))))
            except HTTPException as exc:
                if exc.status_code != 404:
                    raise
            except CorpusError as exc:
                if "PERMISSION" not in exc.code:
                    raise
        return SnapshotPage(
            items=tuple(items),
            offset=offset,
            limit=limit,
            next_offset=offset + limit if len(ids) > limit else None,
        )

    @router.get("/api/v1/snapshots/{snapshot_id}", response_model=SnapshotView, tags=["snapshots"])
    def snapshot(
        snapshot_id: UUID, request: Request, identity: IdentityTuple = user_dep
    ) -> SnapshotView:
        throttle(request, identity)
        return snapshot_view(resolver_for(identity)(snapshot_id))

    @router.get("/api/v1/search", response_model=SearchResult, tags=["search"])
    async def search(
        request: Request,
        snapshot_id: UUID,
        query: str = Query(min_length=1, max_length=1000),
        limit: int = Query(10, ge=1, le=10),
        bank_codes: Annotated[list[BankCode] | None, Query(max_length=4)] = None,
        metric_codes: Annotated[list[str] | None, Query(max_length=20)] = None,
        identity: IdentityTuple = user_dep,
    ) -> SearchResult:
        throttle(request, identity)
        dto = SearchRequest(
            snapshot_id=snapshot_id,
            query=query,
            limit=limit,
            bank_codes=tuple(bank_codes) if bank_codes is not None else None,
            metric_codes=tuple(metric_codes) if metric_codes is not None else None,
        )
        service = runtime.search(resolver_for(identity))
        outcome = await asyncio.to_thread(lambda: asyncio.run(service.search_with_status(dto)))
        return SearchResult(
            status=outcome.status,
            hits=outcome.hits,
            absence_of_evidence=outcome.absence_of_evidence,
            omitted_oversize=outcome.omitted_oversize,
        )

    @router.post("/api/v1/comparisons", response_model=ComparisonResult, tags=["comparisons"])
    async def compare(
        body: ComparisonRequest,
        request: Request,
        identity: IdentityTuple = csrf_dep,
    ) -> ComparisonResult:
        throttle(request, identity)
        service = runtime.comparison(resolver_for(identity))
        async with asyncio.timeout(runtime.settings.llm_total_timeout_seconds):
            return await asyncio.to_thread(lambda: asyncio.run(service.compare(body)))

    @router.post("/api/v1/assistant/questions", response_model=AnswerEnvelope, tags=["assistant"])
    async def question(
        body: QuestionRequest,
        request: Request,
        identity: IdentityTuple = csrf_dep,
    ) -> AnswerEnvelope:
        throttle(request, identity, question=True)
        resolve = resolver_for(identity)

        def access(current: SnapshotManifest) -> None:
            runtime.check_identity(identity)
            runtime.check_processing(current)

        service = AssistantService(
            runtime.llm,
            runtime.search(resolve),
            runtime.comparison(resolve),
            runtime.evidence,
            resolve,
            check_read_access=access,
            provider_processing_allowed=True,
            timeout_ms=int(runtime.settings.llm_total_timeout_seconds * 1000),
            call_timeout_ms=int(runtime.settings.llm_call_timeout_seconds * 1000),
        )
        token = set_budget_user(identity[0].id)
        try:
            return await service.answer(body, request_id=request.state.request_id)
        finally:
            reset_budget_user(token)

    def document(version_id: UUID, identity: IdentityTuple) -> tuple[DocumentView, bytes]:
        runtime.check_identity(identity)
        with runtime.factory() as db:
            ids = tuple(
                db.scalars(
                    select(SnapshotMember.snapshot_id)
                    .join(Snapshot, Snapshot.id == SnapshotMember.snapshot_id)
                    .where(
                        SnapshotMember.source_version_id == str(version_id),
                        Snapshot.state == "frozen",
                    )
                    .order_by(Snapshot.revision)
                    .limit(100)
                )
            )
        for value in ids:
            try:
                manifest = resolver_for(identity)(UUID(value))
            except HTTPException as exc:
                if exc.status_code == 404:
                    continue
                raise
            except CorpusError as exc:
                if "PERMISSION" in exc.code:
                    continue
                raise
            item = next(
                (item for item in manifest.documents if item.source_version_id == version_id), None
            )
            if item is None:
                continue
            path = runtime.corpus.read_member(manifest.snapshot_id, version_id)
            # Return verified bytes, avoiding FileResponse's later reopen boundary.
            with path.open("rb") as stream:
                data = stream.read(runtime.settings.source_max_bytes + 1)
            with runtime.factory() as db:
                version = db.get(SourceVersion, str(version_id))
                blob = db.get(Blob, version.blob_id) if version is not None else None
                if (
                    blob is None
                    or len(data) != blob.byte_size
                    or (
                        hashlib.sha256(data).hexdigest() != item.sha256
                        or blob.sha256 != item.sha256
                    )
                ):
                    raise CorpusError("STORAGE_HASH_MISMATCH")
                metadata = DocumentView(
                    source_version_id=version_id,
                    snapshot_id=manifest.snapshot_id,
                    corpus_revision=manifest.revision,
                    corpus_kind=manifest.corpus_kind,
                    bank_code=item.bank_code,
                    document_type=item.document_type,
                    raw_sha256=item.sha256,
                    byte_size=blob.byte_size,
                    media_type=blob.media_type,
                    acquired_at=item.acquired_at,
                    download_url=f"/api/v1/documents/{version_id}/original",
                )
            resolver_for(identity)(manifest.snapshot_id)
            return metadata, data
        raise HTTPException(404, "OBJECT_UNAVAILABLE")

    @router.get("/api/v1/documents/{version_id}", response_model=DocumentView, tags=["documents"])
    def metadata(
        version_id: UUID, request: Request, identity: IdentityTuple = user_dep
    ) -> DocumentView:
        throttle(request, identity)
        return document(version_id, identity)[0]

    @router.get(
        "/api/v1/documents/{version_id}/original",
        tags=["documents"],
        response_class=Response,
        responses={200: {"content": {"application/octet-stream": {}}}},
    )
    def original(
        version_id: UUID, request: Request, identity: IdentityTuple = user_dep
    ) -> Response:
        throttle(request, identity)
        _, data = document(version_id, identity)
        return Response(
            data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{version_id}.bin"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    def draft(snapshot_id: UUID, identity: IdentityTuple) -> SnapshotManifest:
        runtime.check_identity(identity, admin=True)
        manifest = runtime.resolve_manifest(snapshot_id)
        with runtime.factory() as db:
            row = db.get(Snapshot, str(snapshot_id))
            if row is None:
                raise HTTPException(404, "OBJECT_UNAVAILABLE")
            if row.state != "draft":
                raise HTTPException(409, "STATE_CONFLICT")
        return manifest

    @router.get("/api/v1/admin/candidates", response_model=CandidatePage, tags=["admin"])
    def candidates(
        snapshot_id: UUID,
        request: Request,
        offset: int = Query(0, ge=0, le=100000),
        limit: int = Query(20, ge=1, le=100),
        identity: IdentityTuple = admin_dep,
    ) -> CandidatePage:
        throttle(request, identity)
        runtime.check_identity(identity, admin=True)
        manifest = runtime.resolve_manifest(snapshot_id)
        with runtime.factory() as db:
            snapshot_row = db.get(Snapshot, str(snapshot_id))
            if snapshot_row is None or snapshot_row.state == "revoked":
                raise HTTPException(404, "OBJECT_UNAVAILABLE")
            if (
                snapshot_row.revision != manifest.revision
                or snapshot_row.corpus_kind != manifest.corpus_kind
            ):
                raise CorpusError("SNAPSHOT_IDENTITY_MISMATCH")
            if (
                snapshot_row.state == "frozen"
                and snapshot_row.manifest_sha256 != manifest.manifest_sha256
            ):
                raise CorpusError("SNAPSHOT_MANIFEST_MISMATCH")
        runtime.corpus.validate(manifest)
        with runtime.factory() as db:
            rows = db.scalars(
                select(TariffCandidate)
                .where(
                    TariffCandidate.extraction_run_id.in_(
                        [str(item.extraction_run_id) for item in manifest.documents]
                    )
                )
                .order_by(TariffCandidate.id)
                .offset(offset)
                .limit(limit + 1)
            ).all()
            items = []
            for row in rows[:limit]:
                review = db.scalar(
                    select(FactReview)
                    .where(
                        FactReview.candidate_id == row.id,
                        FactReview.validation["snapshot_id"].as_string() == str(snapshot_id),
                    )
                    .order_by(FactReview.created_at.desc(), FactReview.id.desc())
                    .limit(1)
                )
                items.append(
                    CandidateView.model_validate(
                        {
                            "candidate": CandidateDTO.model_validate(row.payload),
                            "decision": review.decision if review else "pending_review",
                            "review_id": review.id if review else None,
                        }
                    )
                )
        return CandidatePage(
            items=tuple(items),
            offset=offset,
            limit=limit,
            next_offset=offset + limit if len(rows) > limit else None,
        )

    @router.post(
        "/api/v1/admin/candidates/{candidate_id}/reviews",
        response_model=ReviewResult,
        tags=["admin"],
    )
    def review(
        candidate_id: UUID,
        body: ReviewBody,
        request: Request,
        identity: IdentityTuple = admin_csrf_dep,
    ) -> ReviewResult:
        throttle(request, identity)
        manifest = draft(body.snapshot_id, identity)
        confirmation = (
            SemanticConfirmation(
                {
                    key: tuple(str(ref) for ref in values)
                    for key, values in body.field_evidence.items()
                }
            )
            if body.field_evidence is not None
            else None
        )
        review_id = runtime.evidence.review(
            manifest,
            str(candidate_id),
            decision=body.decision,
            reviewer_label=identity[0].login,
            reason=body.reason,
            confirmation=confirmation,
            user_id=identity[0].id,
        )
        fact_id = None
        if body.decision == "approved":
            runtime.check_identity(identity, admin=True)
            fact_id = runtime.evidence.publish(manifest, str(candidate_id), review_id).fact_id
        return ReviewResult(
            review_id=UUID(review_id),
            fact_id=UUID(fact_id) if fact_id else None,
            published=fact_id is not None,
        )

    @router.post(
        "/api/v1/admin/snapshots/{snapshot_id}/freeze", response_model=FreezeResult, tags=["admin"]
    )
    def freeze(
        snapshot_id: UUID, request: Request, identity: IdentityTuple = admin_csrf_dep
    ) -> FreezeResult:
        throttle(request, identity)
        manifest = draft(snapshot_id, identity)
        return FreezeResult.model_validate(runtime.corpus.freeze(manifest))

    return router
