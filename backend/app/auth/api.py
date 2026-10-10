"""FastAPI router factory for the closed, same-origin application."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.auth.limits import LoginLimiter
from app.auth.models import AuthSession, AuthUser
from app.auth.security import PasswordService, normalize_login, token_digest
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
    user_id: str = Field(min_length=36, max_length=36)


class ResetCompleteBody(StrictModel):
    token: str = Field(min_length=40, max_length=100)
    password: str = Field(min_length=12, max_length=128)


class UserAccessBody(StrictModel):
    role: Literal["admin", "analyst"] | None = None
    active: bool | None = None


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
        raw_origin = expected_origin or settings.public_base_url
        self.expected_origin: str | None
        if raw_origin:
            parsed = urlsplit(raw_origin)
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
    router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

    def now() -> datetime:
        return datetime.now(UTC)

    def require_origin(request: Request) -> None:
        origin = request.headers.get("origin")
        if (
            not ctx.expected_origin
            or not origin
            or not hmac.compare_digest(origin.rstrip("/"), ctx.expected_origin)
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "ORIGIN_REJECTED")

    def require_user(request: Request) -> tuple[AuthUser, AuthSession]:
        with ctx.session_factory.begin() as db:
            identity = validate_session(db, request.cookies.get(ctx.cookie_name), now())
        if identity is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "AUTH_REQUIRED")
        else:
            user, session = identity
            request.state.auth_user_id = user.id
            request.state.auth_role = user.role
            request.state.auth_session_id = session.id
            return user, session

    def require_admin(
        identity: tuple[AuthUser, AuthSession] = Depends(require_user),
    ) -> tuple[AuthUser, AuthSession]:
        if identity[0].role != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "ROLE_REQUIRED")
        return identity

    def require_csrf(
        request: Request, identity: tuple[AuthUser, AuthSession] = Depends(require_user)
    ) -> tuple[AuthUser, AuthSession]:
        require_origin(request)
        cookie_token = request.cookies.get("bsi-csrf", "")
        header_token = request.headers.get("x-csrf-token", "")
        if (
            not cookie_token
            or not header_token
            or not hmac.compare_digest(cookie_token, header_token)
            or not hmac.compare_digest(token_digest(cookie_token), identity[1].csrf_hash)
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF_REJECTED")
        return identity

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
        status_code = 404 if code in {"USER_NOT_FOUND"} else 409 if code == "LAST_ADMIN" else 400
        return HTTPException(status_code, code)

    @router.post("/login")
    def login(body: LoginBody, request: Request, response: Response) -> dict[str, object]:
        require_origin(request)
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
        if not outcome:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS")
        user, session_token, csrf_token = outcome
        set_session_cookies(response, session_token, csrf_token)
        return {"id": user.id, "login": user.login, "role": user.role, "csrf_token": csrf_token}

    @router.post("/accept-invite")
    def accept_invite(
        body: InviteAcceptBody, request: Request, response: Response
    ) -> dict[str, object]:
        require_origin(request)
        try:
            with ctx.session_factory.begin() as db:
                user, _, session_token, csrf_token = accept_invitation(
                    db,
                    token=body.token,
                    password=body.password,
                    passwords=ctx.passwords,
                    now=now(),
                )
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
        require_origin(request)
        try:
            with ctx.session_factory.begin() as db:
                user, session_token, csrf_token = rotate_password(
                    db,
                    reset_token=body.token,
                    password=body.password,
                    passwords=ctx.passwords,
                    now=now(),
                )
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
                    db, issuer=issuer, user_id=body.user_id, now=now()
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
        user_id: str,
        body: UserAccessBody,
        request: Request,
        identity: tuple[AuthUser, AuthSession] = Depends(require_csrf),
    ) -> dict[str, object]:
        require_admin(identity)
        if body.role is None and body.active is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "EMPTY_ACCESS_UPDATE")
        try:
            with ctx.session_factory.begin() as db:
                actor = db.get(AuthUser, identity[0].id)
                assert actor is not None
                user = change_user_access(
                    db,
                    actor=actor,
                    user_id=user_id,
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
