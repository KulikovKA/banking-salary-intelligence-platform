"""Opt-in localhost browser harness: migrated dedicated PG, real services, synthetic/Fake only."""

import asyncio
import json
import os
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "backend/tests")]

import uvicorn  # noqa: E402
from fastapi import HTTPException, Request  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.schema import CreateSchema  # noqa: E402
from test_assistant_answers import RoutedFake, question_system  # noqa: E402

from app.auth.models import AuthSession, AuthUser  # noqa: E402
from app.auth.security import PasswordService  # noqa: E402
from app.auth.service import create_invitation  # noqa: E402
from app.config import Settings  # noqa: E402
from app.corpus.service import CorpusService  # noqa: E402
from app.ingestion.gateway import FetchGateway  # noqa: E402
from app.ingestion.service import IngestionService  # noqa: E402
from app.main import create_app  # noqa: E402
from app.parsing.service import ExtractionPipeline  # noqa: E402
from app.storage.local import LocalBlobStore  # noqa: E402


def main():
    raw = os.environ.get("TEST_DATABASE_URL", "")
    url = make_url(raw)
    if (
        url.get_backend_name() != "postgresql"
        or not url.database
        or "snap17_browser_test" not in url.database
        or url.host not in {"127.0.0.1", "localhost"}
    ):
        raise RuntimeError("Dedicated localhost snap17_browser_test PostgreSQL required")
    if os.environ.get("APP_ENV") != "test" or os.environ.get("LLM_MODE") != "fake":
        raise RuntimeError("Explicit test/Fake environment required")
    schema = f"snap17_{uuid4().hex}"
    bootstrap_engine = create_engine(url)
    with bootstrap_engine.begin() as session:
        session.execute(CreateSchema(schema))
    bootstrap_engine.dispose()
    env = dict(
        os.environ, DATABASE_URL=raw, INGESTION_MODE="offline", PGOPTIONS=f"-csearch_path={schema}"
    )
    for action in ("upgrade", "check"):
        command = [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", action]
        subprocess.run(
            command + (["head"] if action == "upgrade" else []), cwd=ROOT, env=env, check=True
        )
    local = ROOT / ".local/snap17-browser"
    local.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url.update_query_dict({"options": f"-csearch_path={schema}"}), pool_pre_ping=True
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    store = LocalBlobStore(local / f"synthetic-originals-{uuid4().hex}")
    settings = Settings(
        app_env="test",
        storage_root=store.root,
        public_base_url="http://127.0.0.1:3100",
        ingestion_mode="offline",
        llm_mode="fake",
        auth_enabled=True,
        fake_identity=False,
    )
    corpus = CorpusService(
        IngestionService(factory, settings, store, FetchGateway(settings, store))
    )
    db = factory, store, corpus, ExtractionPipeline(corpus)
    _, fake, ids, manifest, _ = question_system.__wrapped__(db, SimpleNamespace(param=True))
    (store.root / "manifests").mkdir()
    (store.root / "manifests" / f"{manifest.snapshot_id}.json").write_bytes(
        manifest.canonical_json()
    )
    password = "Synthetic-browser-password-17!"
    with factory.begin() as session:
        user = AuthUser(
            login=f"browser-{uuid4().hex}@synthetic.invalid",
            password_hash=PasswordService().hash(password),
            role="admin",
            active=True,
        )
        session.add(user)
        session.flush()
        _, invitation = create_invitation(
            session,
            issuer=user,
            login=f"invite-{uuid4().hex}@synthetic.invalid",
            role="analyst",
            now=datetime.now(UTC),
        )
    state = {"empty": False, "egress_attempts": 0}
    control = uuid4().hex

    def resolve(snapshot_id):
        if state["empty"] or snapshot_id != manifest.snapshot_id:
            raise HTTPException(404, "OBJECT_UNAVAILABLE")
        return manifest

    app = create_app(settings, session_factory=factory, resolve_manifest=resolve, llm=fake)
    runtime = app.state.runtime
    original_connect = socket.socket.connect

    def connect(sock, address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            state["egress_attempts"] += 1
            raise RuntimeError("Browser harness blocks external network")
        return original_connect(sock, address)

    socket.socket.connect = connect

    @app.post("/__test/control")
    async def configure(request: Request):
        if request.headers.get("x-test-control") != control:
            raise HTTPException(403)
        action = (await request.json())["action"]
        if action == "reset":
            # Independent test cases get fresh windows; backend production limits remain unchanged.
            with runtime.login_limiter._lock:
                runtime.login_limiter._accounts.clear()
                runtime.login_limiter._ips.clear()
        if action == "expire":
            with factory.begin() as session:
                for row in session.scalars(
                    select(AuthSession).where(AuthSession.user_id == user.id)
                ):
                    row.revoked_at = datetime.now(UTC)
        else:
            state["empty"] = action == "empty"

            class SlowFake(RoutedFake):
                async def complete(self, request):
                    await asyncio.sleep(3)
                    return await super().complete(request)

            runtime.llm = (
                SlowFake()
                if action == "slow"
                else RoutedFake(failure="unavailable")
                if action == "fallback"
                else fake
            )
            runtime.settings = settings.model_copy(
                update={
                    "llm_total_timeout_seconds": 0.001 if action == "timeout" else 45.0,
                }
            )
            # Clear only in-memory harness quota windows by replacing the existing limiter type.
            for name in ("read_limiter", "question_limiter"):
                limiter = getattr(runtime, name)
                setattr(
                    runtime,
                    name,
                    type(limiter)(
                        account_limit=1
                        if action == "rate"
                        else (10 if name == "question_limiter" else 60),
                        ip_limit=30 if name == "question_limiter" else 120,
                    ),
                )
        return state

    @app.get("/__test/evidence")
    def evidence(request: Request):
        if request.headers.get("x-test-control") != control:
            raise HTTPException(403)
        return dict(
            state,
            llm_mode="fake",
            corpus_kind="synthetic",
            source_hash=manifest.documents[0].sha256,
        )

    (local / "fixture.json").write_text(
        json.dumps(
            dict(
                login=user.login,
                password=password,
                invitation=invitation,
                control=control,
                snapshot_id=str(manifest.snapshot_id),
                version_id=ids["version"],
                revision=manifest.revision,
                schema=schema,
                source_hash=manifest.documents[0].sha256,
            )
        ),
        encoding="utf-8",
    )
    try:
        uvicorn.run(app, host="127.0.0.1", port=8007, log_level="warning")
    finally:
        socket.socket.connect = original_connect
        engine.dispose()


if __name__ == "__main__":
    main()
