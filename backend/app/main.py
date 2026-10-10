"""Minimal API entry point; business routes are introduced by later work packages."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Validate runtime configuration before serving requests."""
    get_settings()
    yield


app = FastAPI(
    title="Banking Salary Intelligence Platform",
    version="0.1.0",
    description="Evidence-backed analysis of public salary project offers.",
    lifespan=lifespan,
)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    """Return process liveness without claiming database or provider readiness."""
    return {"status": "ok"}
