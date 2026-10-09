"""Minimal API entry point; business routes are introduced by later work packages."""

from fastapi import FastAPI

app = FastAPI(
    title="Banking Salary Intelligence Platform",
    version="0.1.0",
    description="Evidence-backed analysis of public salary project offers.",
)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    """Return process liveness without claiming database or provider readiness."""
    return {"status": "ok"}
