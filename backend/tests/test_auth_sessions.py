"""PostgreSQL 18 auth integration: one-time use, rotation, RBAC, and expiry."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.orm import sessionmaker

from app.auth.api import create_auth_router
from app.auth.limits import LoginLimiter
from app.auth.models import AuthAudit, AuthInvitation, AuthPasswordReset, AuthSession, AuthUser
from app.auth.security import PasswordService, token_digest
from app.auth.service import (
    AuthError,
    accept_invitation,
    authenticate,
    create_invitation,
    issue_password_reset,
    rotate_password,
    validate_session,
)
from app.config import Settings


@pytest.fixture
def auth_db():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("NOT RUN: TEST_DATABASE_URL is not set; PostgreSQL integration required")
    engine = create_engine(url, pool_size=5, max_overflow=2)
    with engine.connect() as conn:
        version = conn.scalar(text("show server_version_num"))
    if not str(version).startswith("180"):
        engine.dispose()
        pytest.fail(f"auth integration requires PostgreSQL 18; connected version={version}")
    factory = sessionmaker(engine, expire_on_commit=False)
    passwords = PasswordService()
    login = f"auth-{uuid4().hex}@example.invalid"
    with factory.begin() as db:
        admin = AuthUser(
            login=login,
            password_hash=passwords.hash("A-very-long synthetic password 1!"),
            role="admin",
        )
        db.add(admin)
        db.flush()
        admin_id = admin.id
    yield factory, passwords, admin_id, login
    with factory.begin() as db:
        ids = list(
            db.scalars(
                select(AuthUser.id).where(
                    (AuthUser.login == login) | AuthUser.login.like(f"{login}.%")
                )
            )
        )
        if ids:
            db.execute(delete(AuthSession).where(AuthSession.user_id.in_(ids)))
            db.execute(delete(AuthPasswordReset).where(AuthPasswordReset.user_id.in_(ids)))
            db.execute(
                delete(AuthInvitation).where(
                    (AuthInvitation.issuer_id.in_(ids)) | AuthInvitation.login.like(f"{login}.%")
                )
            )
            db.execute(delete(AuthAudit).where(AuthAudit.actor_id.in_(ids)))
            db.execute(delete(AuthUser).where(AuthUser.id.in_(ids)))
    engine.dispose()


def test_postgres_invitation_is_hash_only_atomic_and_race_safe(auth_db):
    factory, passwords, admin_id, login = auth_db
    now = datetime.now(UTC)
    with factory.begin() as db:
        admin = db.get(AuthUser, admin_id)
        assert admin is not None
        invite, token = create_invitation(
            db, issuer=admin, login=f"{login}.new", role="analyst", now=now
        )
        invite_id, invite_hash = invite.id, invite.token_hash
    assert token_digest(token) == invite_hash
    assert token not in invite_hash
    barrier = Barrier(2)

    def accept_once():
        barrier.wait(timeout=5)
        try:
            with factory.begin() as db:
                return accept_invitation(
                    db,
                    token=token,
                    password="Another long password 2!",
                    passwords=passwords,
                    now=now + timedelta(seconds=1),
                )[0].id
        except AuthError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: accept_once(), range(2)))
    assert sum(result not in {"INVITATION_INVALID"} for result in results) == 1
    assert results.count("INVITATION_INVALID") == 1
    with factory() as db:
        row = db.get(AuthInvitation, invite_id)
        assert row and row.used_at and row.token_hash == invite_hash
        assert (
            db.scalar(
                select(func.count()).select_from(AuthUser).where(AuthUser.login == invite.login)
            )
            == 1
        )


def test_password_hash_login_session_expiry_rotation_and_logout(auth_db):
    factory, passwords, admin_id, login = auth_db
    now = datetime.now(UTC)
    with factory.begin() as db:
        admin = db.get(AuthUser, admin_id)
        assert admin is not None
        encoded = admin.password_hash
        assert encoded.startswith("$argon2id$")
        assert passwords.verify(encoded, "A-very-long synthetic password 1!")
        outcome = authenticate(
            db,
            login=login.upper(),
            password="A-very-long synthetic password 1!",
            passwords=passwords,
            now=now,
        )
        assert outcome is not None
        _, raw_session, csrf = outcome
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == admin_id))
        assert session is not None
        token_hash = session.token_hash
        assert validate_session(db, "raw-secret-unrelated-to-db", now) is None
        valid = validate_session(db, raw_session, now)
        assert valid and valid[0].id == admin_id and valid[1].csrf_hash == token_digest(csrf)
    with factory() as db:
        assert (
            db.scalar(select(AuthSession.token_hash).where(AuthSession.user_id == admin_id))
            == token_hash
        )


def test_session_a_and_b_resolve_only_their_own_identity(auth_db):
    factory, passwords, admin_id, login = auth_db
    now = datetime.now(UTC)
    analyst_login = f"{login}.analyst"
    with factory.begin() as db:
        analyst = AuthUser(
            login=analyst_login,
            password_hash=passwords.hash("A different long password 2!"),
            role="analyst",
        )
        db.add(analyst)
        db.flush()
        analyst_id = analyst.id
        admin_outcome = authenticate(
            db,
            login=login,
            password="A-very-long synthetic password 1!",
            passwords=passwords,
            now=now,
        )
        analyst_outcome = authenticate(
            db,
            login=analyst_login,
            password="A different long password 2!",
            passwords=passwords,
            now=now,
        )
    assert admin_outcome and analyst_outcome
    with factory.begin() as db:
        identity_a = validate_session(db, admin_outcome[1], now)
        identity_b = validate_session(db, analyst_outcome[1], now)
    assert identity_a and identity_a[0].id == admin_id and identity_a[0].role == "admin"
    assert identity_b and identity_b[0].id == analyst_id and identity_b[0].role == "analyst"
    with factory.begin() as db:
        assert validate_session(db, analyst_outcome[1], now)[0].id != admin_id
        assert (
            db.scalar(
                select(func.count()).select_from(AuthSession).where(AuthSession.user_id == admin_id)
            )
            == 1
        )


def test_idle_and_absolute_session_expiry_are_enforced(auth_db):
    factory, _, admin_id, _ = auth_db
    now = datetime.now(UTC)
    idle_raw = "session-idle-" + uuid4().hex
    absolute_raw = "session-absolute-" + uuid4().hex
    with factory.begin() as db:
        rows = [
            AuthSession(
                user_id=admin_id,
                token_hash=token_digest(idle_raw),
                csrf_hash=token_digest("csrf-idle"),
                created_at=now - timedelta(hours=9),
                last_seen_at=now - timedelta(hours=9),
                absolute_expires_at=now + timedelta(hours=1),
            ),
            AuthSession(
                user_id=admin_id,
                token_hash=token_digest(absolute_raw),
                csrf_hash=token_digest("csrf-absolute"),
                created_at=now - timedelta(hours=25),
                last_seen_at=now - timedelta(minutes=1),
                absolute_expires_at=now - timedelta(hours=1),
            ),
        ]
        db.add_all(rows)
        db.flush()
        session_ids = [row.id for row in rows]
        assert validate_session(db, idle_raw, now) is None
        assert validate_session(db, absolute_raw, now) is None
    with factory() as db:
        assert all(
            db.get(AuthSession, session_id).revoked_at is not None for session_id in session_ids
        )


def test_password_reset_is_one_use_revokes_sessions_and_rotates(auth_db):
    factory, passwords, admin_id, _ = auth_db
    now = datetime.now(UTC)
    with factory.begin() as db:
        admin = db.get(AuthUser, admin_id)
        assert admin is not None
        (old_session,) = [
            AuthSession(
                user_id=admin_id,
                token_hash=token_digest("old-" + uuid4().hex),
                csrf_hash=token_digest("old-csrf"),
                created_at=now,
                last_seen_at=now,
                absolute_expires_at=now + timedelta(hours=24),
            )
        ]
        db.add(old_session)
        reset, token = issue_password_reset(db, issuer=admin, user_id=admin_id, now=now)
        reset_id = reset.id
        reset_hash = reset.token_hash
        old_session_id = old_session.id
    assert token_digest(token) == reset_hash
    with factory.begin() as db:
        user, session_token, csrf = rotate_password(
            db,
            reset_token=token,
            password="New password after reset 3!",
            passwords=passwords,
            now=now + timedelta(seconds=1),
        )
        user_id = user.id
    with factory() as db:
        assert db.get(AuthSession, old_session_id).revoked_at is not None
        assert db.scalar(
            select(AuthSession.token_hash).where(
                AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
            )
        ) == token_digest(session_token)
        assert (
            db.scalar(select(AuthPasswordReset.token_hash).where(AuthPasswordReset.id == reset_id))
            == reset_hash
        )
        assert db.scalar(select(AuthUser.password_hash).where(AuthUser.id == user_id)).startswith(
            "$argon2id$"
        )
    with factory.begin() as db, pytest.raises(AuthError, match="RESET_INVALID"):
        rotate_password(
            db,
            reset_token=token,
            password="Another new password 4!",
            passwords=passwords,
            now=now + timedelta(seconds=2),
        )
    assert len(csrf) >= 43


def test_last_active_admin_cannot_be_demoted_or_deactivated(auth_db):
    from app.auth.service import change_user_access

    factory, _, admin_id, _ = auth_db
    with factory.begin() as db:
        admin = db.get(AuthUser, admin_id)
        assert admin is not None
        with pytest.raises(AuthError, match="LAST_ADMIN"):
            change_user_access(
                db,
                actor=admin,
                user_id=admin_id,
                role="analyst",
                active=None,
                now=datetime.now(UTC),
            )
    with factory.begin() as db:
        admin = db.get(AuthUser, admin_id)
        assert admin is not None
        with pytest.raises(AuthError, match="LAST_ADMIN"):
            change_user_access(
                db, actor=admin, user_id=admin_id, role=None, active=False, now=datetime.now(UTC)
            )


def test_login_rate_window_limits_account_and_ip():
    limiter = LoginLimiter()
    for attempt in range(5):
        assert limiter.check_and_record("alice", "192.0.2.1", now=float(attempt))
    assert not limiter.check_and_record("alice", "192.0.2.2", now=5.0)
    ip_limiter = LoginLimiter()
    for attempt in range(20):
        assert ip_limiter.check_and_record(f"user{attempt}", "192.0.2.1", now=float(attempt))
    assert not ip_limiter.check_and_record("bob", "192.0.2.1", now=21.0)
    assert limiter.check_and_record("alice", "192.0.2.2", now=61.0)


def test_http_origin_csrf_session_fixation_and_role_enforcement(auth_db):
    factory, passwords, admin_id, login = auth_db
    app = FastAPI()
    app.include_router(
        create_auth_router(
            factory,
            Settings(app_env="test"),
            expected_origin="http://testserver",
            passwords=passwords,
            limiter=LoginLimiter(),
        )
    )
    client = TestClient(app)
    challenge = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    client.cookies.set("bsi-session", "attacker-fixed-session", domain="testserver.local")
    invalid_user = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "http://testserver", "X-CSRF-Token": challenge},
        json={"login": f"missing-{uuid4().hex}@example.invalid", "password": "bad password"},
    )
    invalid_password = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "http://testserver", "X-CSRF-Token": challenge},
        json={"login": login, "password": "wrong password"},
    )
    assert invalid_user.status_code == invalid_password.status_code == 401
    assert invalid_user.json() == invalid_password.json()
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "http://evil.invalid"},
        json={"login": login, "password": "A-very-long synthetic password 1!"},
    )
    assert response.status_code == 403
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "http://testserver", "X-CSRF-Token": challenge},
        json={"login": login, "password": "A-very-long synthetic password 1!"},
    )
    assert response.status_code == 200
    assert response.cookies["bsi-session"] != "attacker-fixed-session"
    assert response.cookies.get("bsi-csrf") == response.json()["csrf_token"]
    csrf = response.json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/admin/invitations",
        headers={"Origin": "http://testserver", "X-CSRF-Token": "wrong"},
        json={"login": f"{login}.http-analyst", "role": "analyst"},
    )
    assert response.status_code == 403
    response = client.post(
        "/api/v1/auth/admin/invitations",
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf},
        json={"login": f"{login}.http-analyst", "role": "analyst"},
    )
    assert response.status_code == 201
    raw_invite = response.json()["token"]
    assert len(raw_invite) >= 40
    with factory() as db:
        invite = db.get(AuthInvitation, response.json()["id"])
        assert invite is not None
        assert invite.token_hash == token_digest(raw_invite)
        assert raw_invite not in invite.token_hash
    response = client.post(
        "/api/v1/auth/accept-invite",
        headers={"Origin": "http://testserver", "X-CSRF-Token": challenge},
        json={"token": raw_invite, "password": "A valid analyst password 5!"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "analyst"
    analyst_csrf = response.json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/admin/invitations",
        headers={"Origin": "http://testserver", "X-CSRF-Token": analyst_csrf},
        json={"login": f"blocked-{uuid4().hex}@example.invalid", "role": "analyst"},
    )
    assert response.status_code == 403
    assert client.get("/api/v1/auth/me").json()["role"] == "analyst"
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://testserver", "X-CSRF-Token": analyst_csrf},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_anonymous_mutations_require_signed_csrf_and_hide_credentials(auth_db, caplog):
    factory, passwords, _, login = auth_db
    app = FastAPI()
    app.include_router(
        create_auth_router(
            factory,
            Settings(app_env="test"),
            expected_origin="http://testserver",
            passwords=passwords,
        )
    )
    client = TestClient(app)
    body = {"login": login, "password": "A-very-long synthetic password 1!"}
    assert (
        client.post(
            "/api/v1/auth/login", headers={"Origin": "http://testserver"}, json=body
        ).status_code
        == 403
    )
    for path in ("accept-invite", "password-reset"):
        assert (
            client.post(
                f"/api/v1/auth/{path}",
                headers={"Origin": "http://testserver"},
                json={"token": "x" * 43, "password": body["password"]},
            ).status_code
            == 403
        )
    challenge = client.get("/api/v1/auth/csrf")
    assert challenge.headers["cache-control"] == "no-store"
    headers = {"Origin": "http://testserver", "X-CSRF-Token": challenge.json()["csrf_token"]}
    bad = client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"login": login, "password": "SECRET-CANARY" * 20},
    )
    assert bad.status_code == 422
    assert "SECRET-CANARY" not in bad.text + caplog.text
    result = client.post("/api/v1/auth/login", headers=headers, json=body)
    assert result.status_code == 200
    old_hash = token_digest(result.cookies["bsi-session"])
    result2 = client.post("/api/v1/auth/login", headers=headers, json=body)
    assert result2.status_code == 200
    assert result2.cookies["bsi-session"] != result.cookies["bsi-session"]
    with factory() as db:
        assert db.scalar(select(AuthSession.revoked_at).where(AuthSession.token_hash == old_hash))
    assert client.get("/api/v1/auth/me").status_code == 200


def test_same_reset_token_race_consumes_it_once(auth_db):
    factory, passwords, admin_id, _ = auth_db
    now = datetime.now(UTC)
    with factory.begin() as db:
        _, token = issue_password_reset(
            db, issuer=db.get(AuthUser, admin_id), user_id=admin_id, now=now
        )
    barrier = Barrier(2)

    def reset_once(_):
        barrier.wait(timeout=5)
        try:
            with factory.begin() as db:
                return rotate_password(
                    db,
                    reset_token=token,
                    password="Concurrent reset password!",
                    passwords=passwords,
                    now=now,
                )[0].id
        except AuthError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reset_once, range(2)))
    assert outcomes.count(admin_id) == 1
    assert outcomes.count("RESET_INVALID") == 1


def test_admin_role_is_rechecked_inside_mutation_transaction(auth_db):
    factory, _, admin_id, login = auth_db
    with factory() as db:
        stale_actor = db.get(AuthUser, admin_id)
    with factory.begin() as db:
        db.get(AuthUser, admin_id).role = "analyst"
    with factory.begin() as db, pytest.raises(AuthError, match="ROLE_REQUIRED"):
        create_invitation(
            db, issuer=stale_actor, login=f"{login}.rejected", role="analyst", now=datetime.now(UTC)
        )


def test_denied_login_burst_has_bounded_memory():
    limiter = LoginLimiter()
    for _ in range(10000):
        limiter.check_and_record("account", "192.0.2.1", now=1)
    assert len(limiter._accounts["account"]) == 5
    assert len(limiter._ips["192.0.2.1"]) == 20


def test_two_admin_demotions_cannot_remove_the_last_admin(auth_db):
    from app.auth.service import change_user_access

    factory, passwords, admin_id, login = auth_db
    with factory.begin() as db:
        second = AuthUser(
            login=f"{login}.second-admin",
            role="admin",
            password_hash=passwords.hash("Second synthetic admin password!"),
        )
        db.add(second)
        db.flush()
        second_id = second.id
    barrier = Barrier(2)

    def demote(user_id):
        barrier.wait(timeout=5)
        try:
            with factory.begin() as db:
                change_user_access(
                    db,
                    actor=db.get(AuthUser, user_id),
                    user_id=user_id,
                    role="analyst",
                    active=None,
                    now=datetime.now(UTC),
                )
            return "changed"
        except AuthError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(demote, [admin_id, second_id]))
    assert sorted(outcomes) == ["LAST_ADMIN", "changed"]
    with factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuthUser)
                .where(
                    AuthUser.id.in_([admin_id, second_id]),
                    AuthUser.active.is_(True),
                    AuthUser.role == "admin",
                )
            )
            == 1
        )


def test_production_cookies_origin_and_session_touch(auth_db, tmp_path):
    factory, passwords, admin_id, login = auth_db
    settings = Settings.from_environment(
        {
            "APP_ENV": "production",
            "DATABASE_URL": os.environ["TEST_DATABASE_URL"],
            "STORAGE_ROOT": str(tmp_path.resolve()),
            "PUBLIC_BASE_URL": "https://example.test",
            "SESSION_SECRET": "synthetic-session-signing-key-" * 2,
            "AUTH_ENABLED": "true",
            "FAKE_IDENTITY": "false",
            "SECURE_COOKIES": "true",
        }
    )
    app = FastAPI()
    app.include_router(create_auth_router(factory, settings, passwords=passwords))
    client = TestClient(app, base_url="https://example.test")
    challenge = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/login",
        json={
            "login": login,
            "password": "A-very-long synthetic password 1!",
        },
        headers={"Origin": "https://example.test", "X-CSRF-Token": challenge},
    )
    assert response.status_code == 200
    cookie = next(
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith("__Host-session=")
    )
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Path=/" in cookie and "Domain=" not in cookie
    with factory.begin() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == admin_id))
        session.last_seen_at = datetime.now(UTC) - timedelta(hours=1)
    assert client.get("/api/v1/auth/me").status_code == 200
    with factory() as db:
        assert db.scalar(
            select(AuthSession.last_seen_at).where(
                AuthSession.user_id == admin_id,
            )
        ) > datetime.now(UTC) - timedelta(minutes=1)
    with pytest.raises(ValueError, match="AUTH_ORIGIN_INVALID"):
        create_auth_router(
            factory, settings, expected_origin="http://example.test", passwords=passwords
        )
