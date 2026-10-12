"""FastAPI composition root for the closed snapshot application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.api.composition import ManifestResolver, Runtime
from app.api.errors import install_errors
from app.api.routes import create_router
from app.api.schema import wire_schema
from app.config import Settings, get_settings
from app.contracts.llm import LLMClient


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: sessionmaker[Session] | None = None,
    resolve_manifest: ManifestResolver | None = None,
    llm: LLMClient | None = None,
    admission_root: Path | None = None,
) -> FastAPI:
    runtime = Runtime(
        settings or get_settings(),
        factory=session_factory,
        resolve_manifest=resolve_manifest,
        llm=llm,
        admission_root=admission_root,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await runtime.close()

    application = FastAPI(
        title="Banking Salary Intelligence Platform",
        version="1.0.0",
        description="Authenticated evidence-backed snapshot API. Decimal values are strings.",
        lifespan=lifespan,
    )
    application.state.runtime = runtime
    install_errors(application)
    application.include_router(create_router(runtime))

    @application.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        """Process liveness, independent of database/provider readiness."""
        return {"status": "ok"}

    application.openapi_schema = wire_schema(application.openapi())
    return application


app = create_app()
