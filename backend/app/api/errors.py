"""Uniform, secret-safe HTTP failures and bounded request bodies."""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.contracts.api import ApiError, ApiErrorDetail
from app.corpus.service import CorpusError
from app.evidence.validation import EvidenceError
from app.ingestion.errors import IngestionError

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: {"model": ApiError} for code in (400, 401, 403, 404, 409, 422, 429, 503)
}


def error_response(
    request_id: UUID, status: int, code: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    envelope = ApiError(
        error=ApiErrorDetail(
            code=code, message=code.replace("_", " ").capitalize(), request_id=request_id
        )
    )
    return JSONResponse(envelope.model_dump(mode="json"), status_code=status, headers=headers)


class BoundaryMiddleware:
    """Cap actual body bytes, including chunked bodies; never trust client request IDs."""

    def __init__(self, app: ASGIApp, max_bytes: int = 65_536) -> None:
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid4()
        scope.setdefault("state", {})["request_id"] = request_id
        started = False

        async def safe_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                managed = {b"x-request-id", b"cache-control", b"x-content-type-options"}
                headers = [item for item in message.get("headers", []) if item[0] not in managed]
                headers.extend(
                    [
                        (b"x-request-id", str(request_id).encode()),
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                    ]
                )
                message["headers"] = headers
            await send(message)

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                await error_response(request_id, 422, "PAYLOAD_TOO_LARGE")(
                    scope, receive, safe_send
                )
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        try:
            await self.app(scope, replay, safe_send)
        except Exception:
            if not started:
                await error_response(request_id, 500, "INTERNAL_ERROR")(scope, replay, safe_send)


def install_errors(app: FastAPI) -> None:
    async def handle(request: Request, exc: Exception) -> Response:
        status, code, headers = 500, "INTERNAL_ERROR", None
        if isinstance(exc, HTTPException):
            status = exc.status_code
            code = (
                exc.detail
                if isinstance(exc.detail, str) and exc.detail.isupper()
                else ("NOT_FOUND" if status == 404 else "REQUEST_REJECTED")
            )
            headers = dict(exc.headers) if exc.headers else None
        elif isinstance(exc, (RequestValidationError, ValidationError)):
            status, code = 422, "DTO_INVALID"
        elif isinstance(exc, SQLAlchemyError):
            status, code = 503, "DATABASE_UNAVAILABLE"
        elif isinstance(exc, TimeoutError):
            status, code = 503, "REQUEST_TIMEOUT"
        elif isinstance(exc, (CorpusError, EvidenceError, IngestionError)):
            original = exc.code
            if "UNKNOWN" in original or "PERMISSION" in original:
                status, code = 404, "OBJECT_UNAVAILABLE"
            elif original in {
                "SNAPSHOT_NOT_DRAFT",
                "PUBLISHED_CANDIDATE_IMMUTABLE",
                "SNAPSHOT_FREEZE_CONFLICT",
                "PUBLICATION_REVIEW_CONFLICT",
            }:
                status, code = 409, "STATE_CONFLICT"
            elif isinstance(exc, EvidenceError) and original in {
                "SEMANTIC_CONFIRMATION_REQUIRED",
                "FIELD_EVIDENCE_INVALID",
                "REVIEW_IDENTITY_OR_REASON_REQUIRED",
                "APPROVED_REVIEW_REQUIRED",
            }:
                status, code = 409, "REVIEW_VALIDATION_FAILED"
            else:
                status, code = 503, "CORPUS_UNREADABLE"
        elif isinstance(exc, ValueError):
            if str(exc) in {"SEARCH_QUERY_INVALID", "COMPARISON_METRIC_UNKNOWN"}:
                status, code = 400, "QUERY_INVALID"
            else:
                status, code = 503, "CORPUS_UNREADABLE"
        return error_response(request.state.request_id, status, code, headers)

    handler: Callable[[Request, Exception], Awaitable[Response]] = handle
    for error_type in (
        HTTPException,
        RequestValidationError,
        ValidationError,
        SQLAlchemyError,
        CorpusError,
        EvidenceError,
        IngestionError,
        TimeoutError,
        ValueError,
        Exception,
    ):
        app.add_exception_handler(error_type, handler)
    app.add_middleware(BoundaryMiddleware)
