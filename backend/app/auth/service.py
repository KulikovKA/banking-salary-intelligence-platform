"""Transactional auth operations. Callers own one SQLAlchemy transaction per request."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.auth.models import AuthAudit, AuthInvitation, AuthPasswordReset, AuthSession, AuthUser
from app.auth.security import PasswordService, new_secret, normalize_login, token_digest

INVITE_TTL = timedelta(hours=48)
RESET_TTL = timedelta(minutes=30)
SESSION_IDLE_TTL = timedelta(hours=8)
SESSION_ABSOLUTE_TTL = timedelta(hours=24)
ADMIN_GUARD_LOCK = 734_150_015


class AuthError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def audit(
    db: Session, event: str, actor_id: str | None = None, subject_id: str | None = None
) -> None:
    db.add(AuthAudit(event_code=event, actor_id=actor_id, subject_id=subject_id))


def make_session(db: Session, user: AuthUser, now: datetime) -> tuple[AuthSession, str, str]:
    raw_session = new_secret()
    raw_csrf = new_secret()
    row = AuthSession(
        user_id=user.id,
        token_hash=token_digest(raw_session),
        csrf_hash=token_digest(raw_csrf),
        created_at=now,
        last_seen_at=now,
        absolute_expires_at=now + SESSION_ABSOLUTE_TTL,
    )
    db.add(row)
    return row, raw_session, raw_csrf


def bootstrap_admin(db: Session, login: str, password: str, passwords: PasswordService) -> AuthUser:
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADMIN_GUARD_LOCK})
    if db.scalar(select(func.count()).select_from(AuthUser)):
        raise AuthError("BOOTSTRAP_ALREADY_INITIALIZED")
    normalized = normalize_login(login)
    _validate_login(normalized)
    user = AuthUser(login=normalized, password_hash=passwords.hash(password), role="admin")
    db.add(user)
    db.flush()
    audit(db, "admin_bootstrapped", user.id, user.id)
    return user


def create_invitation(
    db: Session, *, issuer: AuthUser, login: str, role: str, now: datetime
) -> tuple[AuthInvitation, str]:
    normalized = normalize_login(login)
    _validate_login(normalized)
    _validate_role(role)
    if db.scalar(select(AuthUser.id).where(AuthUser.login == normalized)):
        raise AuthError("LOGIN_UNAVAILABLE")
    token = new_secret()
    row = AuthInvitation(
        login=normalized,
        role=role,
        token_hash=token_digest(token),
        issuer_id=issuer.id,
        created_at=now,
        expires_at=now + INVITE_TTL,
    )
    db.add(row)
    db.flush()
    audit(db, "invitation_created", issuer.id, row.id)
    return row, token


def accept_invitation(
    db: Session, *, token: str, password: str, passwords: PasswordService, now: datetime
) -> tuple[AuthUser, AuthInvitation, str, str]:
    row = db.scalar(
        select(AuthInvitation)
        .where(AuthInvitation.token_hash == token_digest(token))
        .with_for_update()
    )
    if not row or row.used_at or row.revoked_at or row.expires_at <= now:
        raise AuthError("INVITATION_INVALID")
    if db.scalar(select(AuthUser.id).where(AuthUser.login == row.login)):
        raise AuthError("INVITATION_INVALID")
    user = AuthUser(login=row.login, password_hash=passwords.hash(password), role=row.role)
    db.add(user)
    db.flush()
    row.used_at = now
    _, raw_session, csrf = make_session(db, user, now)
    audit(db, "invitation_accepted", user.id, row.id)
    return user, row, raw_session, csrf


def authenticate(
    db: Session, *, login: str, password: str, passwords: PasswordService, now: datetime
) -> tuple[AuthUser, str, str] | None:
    normalized = normalize_login(login)
    user = db.scalar(select(AuthUser).where(AuthUser.login == normalized).with_for_update())
    hash_to_check = user.password_hash if user else passwords.dummy_hash
    password_matches = passwords.verify(hash_to_check, password)
    valid = bool(user and user.active and password_matches)
    if not valid:
        audit(db, "login_failed")
        return None
    assert user is not None
    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash(password)
    _, session_token, csrf_token = make_session(db, user, now)
    audit(db, "login_succeeded", user.id, user.id)
    return user, session_token, csrf_token


def validate_session(
    db: Session, token: str | None, now: datetime
) -> tuple[AuthUser, AuthSession] | None:
    if not token:
        return None
    row = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_digest(token)).with_for_update()
    )
    if not row or row.revoked_at:
        return None
    if row.absolute_expires_at <= now or row.last_seen_at + SESSION_IDLE_TTL <= now:
        row.revoked_at = now
        return None
    user = db.scalar(select(AuthUser).where(AuthUser.id == row.user_id, AuthUser.active.is_(True)))
    if not user:
        row.revoked_at = now
        return None
    # Update on each request; idle expiry stays bounded by the absolute cap.
    row.last_seen_at = now
    return user, row


def rotate_password(
    db: Session, *, reset_token: str, password: str, passwords: PasswordService, now: datetime
) -> tuple[AuthUser, str, str]:
    row = db.scalar(
        select(AuthPasswordReset)
        .where(AuthPasswordReset.token_hash == token_digest(reset_token))
        .with_for_update()
    )
    if not row or row.used_at or row.revoked_at or row.expires_at <= now:
        raise AuthError("RESET_INVALID")
    user = db.scalar(select(AuthUser).where(AuthUser.id == row.user_id).with_for_update())
    if not user or not user.active:
        raise AuthError("RESET_INVALID")
    user.password_hash = passwords.hash(password)
    row.used_at = now
    db.execute(
        update(AuthPasswordReset)
        .where(
            AuthPasswordReset.user_id == user.id,
            AuthPasswordReset.id != row.id,
            AuthPasswordReset.used_at.is_(None),
            AuthPasswordReset.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    _, session_token, csrf_token = make_session(db, user, now)
    audit(db, "password_reset_completed", user.id, row.id)
    return user, session_token, csrf_token


def issue_password_reset(
    db: Session, *, issuer: AuthUser, user_id: str, now: datetime
) -> tuple[AuthPasswordReset, str]:
    user = db.scalar(select(AuthUser).where(AuthUser.id == user_id, AuthUser.active.is_(True)))
    if not user:
        raise AuthError("USER_NOT_FOUND")
    token = new_secret()
    row = AuthPasswordReset(
        user_id=user.id,
        issuer_id=issuer.id,
        token_hash=token_digest(token),
        created_at=now,
        expires_at=now + RESET_TTL,
    )
    db.execute(
        update(AuthPasswordReset)
        .where(
            AuthPasswordReset.user_id == user.id,
            AuthPasswordReset.used_at.is_(None),
            AuthPasswordReset.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.add(row)
    db.flush()
    audit(db, "password_reset_issued", issuer.id, user.id)
    return row, token


def revoke_session(db: Session, row: AuthSession, user_id: str, now: datetime) -> None:
    if row.user_id == user_id and row.revoked_at is None:
        row.revoked_at = now
        audit(db, "session_revoked", user_id, row.id)


def change_user_access(
    db: Session,
    *,
    actor: AuthUser,
    user_id: str,
    role: str | None,
    active: bool | None,
    now: datetime,
) -> AuthUser:
    _validate_role(role) if role is not None else None
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADMIN_GUARD_LOCK})
    user = db.scalar(select(AuthUser).where(AuthUser.id == user_id).with_for_update())
    if not user:
        raise AuthError("USER_NOT_FOUND")
    was_admin = user.role == "admin" and user.active
    becomes_admin = (role or user.role) == "admin" and (
        active if active is not None else user.active
    )
    if was_admin and not becomes_admin:
        count = db.scalar(
            select(func.count())
            .select_from(AuthUser)
            .where(AuthUser.role == "admin", AuthUser.active.is_(True))
        )
        if count is None or count <= 1:
            raise AuthError("LAST_ADMIN")
    if role is not None:
        user.role = role
    if active is not None:
        user.active = active
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    audit(db, "user_access_changed", actor.id, user.id)
    return user


def _validate_login(login: str) -> None:
    if not 3 <= len(login) <= 254 or any(ord(char) < 32 for char in login):
        raise AuthError("LOGIN_INVALID")


def _validate_role(role: str | None) -> None:
    if role not in {"admin", "analyst"}:
        raise AuthError("ROLE_INVALID")
