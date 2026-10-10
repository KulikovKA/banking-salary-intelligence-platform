"""FastAPI router factory for the closed, same-origin application."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.auth.limits import LoginLimiter
from app.auth.models import AuthSession, AuthUser
from app.auth.security import PasswordService, new_secret, normalize_login, token_digest
from app.auth.service import (
    AuthError,
    accept_invitation,
    authenticate,
    change_user_access,
    create_invitation,
    issue_password_reset,
    revoke_session,
    rotate_password,
    validate_session,
)
from app.config import Settings


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class LoginBody(StrictModel):
    login: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class InviteBody(StrictModel):
    login: str = Field(min_length=3, max_length=254)
    role: Literal["admin", "analyst"] = "analyst"


class InviteAcceptBody(StrictModel):
    token: str = Field(min_length=40, max_length=100)
    password: str = Field(min_length=12, max_length=128)


class ResetIssueBody(StrictModel):
    user_id: UUID


class ResetCompleteBody(StrictModel):
    token: str = Field(min_length=40, max_length=100)
    password: str = Field(min_length=12, max_length=128)


class UserAccessBody(StrictModel):
    role: Literal["admin", "analyst"] | None = None
    active: bool | None = None


class AuthRoute(APIRoute):
    """Never echo passwords or one-time tokens in validation error input fields."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT, "AUTH_INPUT_INVALID"
                ) from None

        return handler


class AuthContext:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        settings: Settings,
        expected_origin: str | None = None,
        passwords: PasswordService | None = None,
        limiter: LoginLimiter | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.passwords = passwords or PasswordService()
        self.limiter = limiter or LoginLimiter()
        self.challenge_key = (
            settings.session_secret.get_secret_value() if settings.session_secret else new_secret()
        ).encode("utf-8")
        raw_origin = expected_origin or settings.public_base_url
        self.expected_origin: str | None
        if raw_origin:
            parsed = urlsplit(raw_origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or settings.app_env == "production"
                and parsed.scheme != "https"
            ):
                raise ValueError("AUTH_ORIGIN_INVALID")
            self.expected_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        else:
            self.expected_origin = None
        if settings.app_env == "production" and not self.expected_origin:
            raise ValueError("AUTH_ORIGIN_REQUIRED")

    @property
    def cookie_name(self) -> str:
        return "__Host-session" if self.settings.app_env == "production" else "bsi-session"

    @property
    def secure(self) -> bool:
        return self.settings.app_env == "production" or self.settings.secure_cookies

    def require_origin(self, request: Request) -> None:
        origin = request.headers.get("origin")
        if (
            not self.expected_origin
            or not origin
            or not hmac.compare_digest(origin.encode(), self.expected_origin.encode())
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "ORIGIN_REJECTED")

    def require_user(self, request: Request) -> tuple[AuthUser, AuthSession]:
        """Reusable Depends callable for SNAP-16 document/question routes."""
        with self.session_factory.begin() as db:
            identity = validate_session(
                db, request.cookies.get(self.cookie_name), datetime.now(UTC)
            )
            if identity is not None:
                db.flush()
                db.expunge(identity[0])
                db.expunge(identity[1])
        if identity is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "AUTH_REQUIRED")
        user, session = identity
        request.state.auth_user_id = user.id
        request.state.auth_role = user.role
        request.state.auth_session_id = session.id
        return identity

    def require_admin(self, request: Request) -> tuple[AuthUser, AuthSession]:
        identity = self.require_user(request)
        if identity[0].role != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "ROLE_REQUIRED")
        return identity

    def require_csrf(self, request: Request) -> tuple[AuthUser, AuthSession]:
        self.require_origin(request)
        identity = self.require_user(request)
        cookie = request.cookies.get("bsi-csrf", "")
        header = request.headers.get("x-csrf-token", "")
        if (
            not cookie
            or not header
            or not hmac.compare_digest(cookie.encode(), header.encode())
            or not hmac.compare_digest(token_digest(cookie), identity[1].csrf_hash)
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF_REJECTED")
        return identity


def create_auth_router(
    session_factory: sessionmaker[Session],
    settings: Settings,
    *,
    expected_origin: str | None = None,
    passwords: PasswordService | None = None,
    limiter: LoginLimiter | None = None,
) -> APIRouter:
    """Create the auth router and its per-process limiter; mount from SNAP-16."""
    ctx = AuthContext(
        session_factory=session_factory,
        settings=settings,
        expected_origin=expected_origin,
        passwords=passwords,
        limiter=limiter,
    )
    router = APIRouter(prefix="/api/v1/auth", tags=["auth"], route_class=AuthRoute)

    def now() -> datetime:
        return datetime.now(UTC)

    def same(left: str, right: str) -> bool:
        return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))

    require_origin = ctx.require_origin

    challenge_cookie = "__Host-login-csrf" if ctx.secure else "bsi-login-csrf"

    @router.get("/csrf")
    def csrf_challenge(response: Response) -> dict[str, str]:
        payload = f"{new_secret()}.{int(now().timestamp()) + 600}"
        signature = hmac.new(ctx.challenge_key, payload.encode(), hashlib.sha256).hexdigest()
        token = f"{payload}.{signature}"
        response.set_cookie(
            challenge_cookie,
            token,
            max_age=600,
            httponly=True,
            secure=ctx.secure,
            samesite="strict",
            path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        return {"csrf_token": token}

    def require_login_csrf(request: Request) -> None:
        require_origin(request)
        cookie = request.cookies.get(challenge_cookie, "")
        header = request.headers.get("x-csrf-token", "")
        if not cookie or len(cookie) > 200 or not same(cookie, header):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF_REJECTED")
        try:
            payload, signature = cookie.rsplit(".", 1)
            expiry = int(payload.rsplit(".", 1)[1])
        except (ValueError, IndexError):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF_REJECTED") from None
        expected = hmac.new(ctx.challenge_key, payload.encode(), hashlib.sha256).hexdigest()
        if expiry <= int(now().timestamp()) or not same(signature, expected):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF_REJECTED")

    require_user = ctx.require_user

    def require_admin(
        identity: tuple[AuthUser, AuthSession] = Depends(require_user),
    ) -> tuple[AuthUser, AuthSession]:
        if identity[0].role != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "ROLE_REQUIRED")
        return identity

    require_csrf = ctx.require_csrf

    def set_session_cookies(response: Response, raw_session: str, csrf_token: str) -> None:
        response.set_cookie(
            ctx.cookie_name,
            raw_session,
            max_age=24 * 60 * 60,
            httponly=True,
            secure=ctx.secure,
            samesite="lax",
            path="/",
        )
        response.set_cookie(
            "bsi-csrf",
            csrf_token,
            max_age=24 * 60 * 60,
            httponly=False,
            secure=ctx.secure,
            samesite="lax",
            path="/",
        )

    def clear_session_cookies(response: Response) -> None:
        response.delete_cookie(
            ctx.cookie_name, path="/", secure=ctx.secure, httponly=True, samesite="lax"
        )
        response.delete_cookie("bsi-csrf", path="/", secure=ctx.secure, samesite="lax")

    def map_auth_error(exc: AuthError) -> HTTPException:
        code = exc.code
        status_code = (
            403
            if code == "ROLE_REQUIRED"
            else 404
            if code == "USER_NOT_FOUND"
            else 409
            if code == "LAST_ADMIN"
            else 400
        )
        return HTTPException(status_code, code)

    def revoke_previous_cookie(db: Session, request: Request) -> None:
        previous = request.cookies.get(ctx.cookie_name)
        if previous:
            db.execute(
                update(AuthSession)
                .where(
                    AuthSession.token_hash == token_digest(previous),
                    AuthSession.revoked_at.is_(None),
                )
                .values(revoked_at=now())
            )

    @router.post("/login")
    def login(body: LoginBody, request: Request, response: Response) -> dict[str, object]:
        require_login_csrf(request)
        client_ip = request.client.host if request.client else "unknown"
        normalized = normalize_login(body.login)
        allowed = ctx.limiter.check_and_record(normalized, client_ip)
        with ctx.session_factory.begin() as db:
            outcome = (
                authenticate(
                    db, login=body.login, password=body.password, passwords=ctx.passwords, now=now()
                )
                if allowed
                else None
            )
            if not allowed:
                from app.auth.service import audit

                audit(db, "login_rate_limited")
            if outcome:
                revoke_previous_cookie(db, request)
        if not outcome:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS")
        user, session_token, csrf_token = outcome
        set_session_cookies(response, session_token, csrf_token)
        return {"id": user.id, "login": user.login, "role": user.role, "csrf_token": csrf_token}

    @router.post("/accept-invite")
    def accept_invite(
        body: InviteAcceptBody, request: Request, response: Response
    ) -> dict[str, object]:
        require_login_csrf(request)
        try:
            with ctx.session_factory.begin() as db:
                user, _, session_token, csrf_token = accept_invitation(
                    db,
                    token=body.token,
                    password=body.password,
                    passwords=ctx.passwords,
                    now=now(),
                )
                revoke_previous_cookie(db, request)
        except AuthError as exc:
            raise map_auth_error(exc) from None
        except IntegrityError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "INVITATION_INVALID") from None
        set_session_cookies(response, session_token, csrf_token)
        return {"id": user.id, "login": user.login, "role": user.role, "csrf_token": csrf_token}

    @router.post("/password-reset")
    def complete_password_reset(
        body: ResetCompleteBody, request: Request, response: Response
    ) -> dict[str, object]:
        require_login_csrf(request)
        try:
            with ctx.session_factory.begin() as db:
                user, session_token, csrf_token = rotate_password(
                    db,
                    reset_token=body.token,
                    password=body.password,
                    passwords=ctx.passwords,
                    now=now(),
                )
                revoke_previous_cookie(db, request)
        except AuthError as exc:
            raise map_auth_error(exc) from None
        set_session_cookies(response, session_token, csrf_token)
        return {"id": user.id, "login": user.login, "role": user.role, "csrf_token": csrf_token}

    @router.get("/me")
    def me(identity: tuple[AuthUser, AuthSession] = Depends(require_user)) -> dict[str, str]:
        user, _ = identity
        return {"id": user.id, "login": user.login, "role": user.role}

    @router.post("/logout")
    def logout(
        request: Request,
        response: Response,
        identity: tuple[AuthUser, AuthSession] = Depends(require_csrf),
    ) -> dict[str, bool]:
        user, session = identity
        with ctx.session_factory.begin() as db:
            row = db.get(AuthSession, session.id)
            if row:
                revoke_session(db, row, user.id, now())
        clear_session_cookies(response)
        return {"logged_out": True}

    @router.post("/admin/invitations", status_code=status.HTTP_201_CREATED)
    def invite(
        body: InviteBody,
        request: Request,
        identity: tuple[AuthUser, AuthSession] = Depends(require_csrf),
    ) -> dict[str, object]:
        require_admin(identity)
        try:
            with ctx.session_factory.begin() as db:
                issuer = db.get(AuthUser, identity[0].id)
                assert issuer is not None
                row, token = create_invitation(
                    db, issuer=issuer, login=body.login, role=body.role, now=now()
                )
                result: dict[str, object] = {
                    "id": row.id,
                    "login": row.login,
                    "role": row.role,
                    "expires_at": row.expires_at.isoformat(),
                    "token": token,
                }
        except AuthError as exc:
            raise map_auth_error(exc) from None
        return result

    @router.post("/admin/password-resets", status_code=status.HTTP_201_CREATED)
    def issue_reset(
        body: ResetIssueBody,
        request: Request,
        identity: tuple[AuthUser, AuthSession] = Depends(require_csrf),
    ) -> dict[str, object]:
        require_admin(identity)
        try:
            with ctx.session_factory.begin() as db:
                issuer = db.get(AuthUser, identity[0].id)
                assert issuer is not None
                row, token = issue_password_reset(
                    db, issuer=issuer, user_id=str(body.user_id), now=now()
                )
                result: dict[str, object] = {
                    "id": row.id,
                    "expires_at": row.expires_at.isoformat(),
                    "token": token,
                }
        except AuthError as exc:
            raise map_auth_error(exc) from None
        return result

    @router.patch("/admin/users/{user_id}")
    def update_user(
        user_id: UUID,
        body: UserAccessBody,
        request: Request,
        identity: tuple[AuthUser, AuthSession] = Depends(require_csrf),
    ) -> dict[str, object]:
        require_admin(identity)
        if body.role is None and body.active is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "EMPTY_ACCESS_UPDATE")
        try:
            with ctx.session_factory.begin() as db:
                actor = db.get(AuthUser, identity[0].id)
                assert actor is not None
                user = change_user_access(
                    db,
                    actor=actor,
                    user_id=str(user_id),
                    role=body.role,
                    active=body.active,
                    now=now(),
                )
                result = {
                    "id": user.id,
                    "login": user.login,
                    "role": user.role,
                    "active": user.active,
                }
        except AuthError as exc:
            raise map_auth_error(exc) from None
        return result

    return router
