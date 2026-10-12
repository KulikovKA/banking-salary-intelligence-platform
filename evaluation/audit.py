"""Read-only local inventory. Output contains private paths: keep it outside Git."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from sqlalchemy import create_engine, text

from app.config import Settings, SettingsError


def read_environment(path: Path) -> dict[str, str]:
    """Parse literal KEY=value settings without shell evaluation or interpolation."""
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.removeprefix("export ").partition("=")
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key.strip()):
            raise ValueError("ENV_LITERAL_ASSIGNMENT_REQUIRED")
        value = value.strip()
        if value[:1] in ("'", '"'):
            if value[-1:] != value[:1]:
                raise ValueError("ENV_UNCLOSED_QUOTE")
            value = value[1:-1]
        values[key.strip()] = value
    return values


def inventory(roots: list[Path]) -> list[dict]:
    found = {}
    excluded = {".git", ".venv", "node_modules", ".next", "__pycache__", ".tools"}
    for root in roots:
        if not root.exists():
            continue
        for directory, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [
                d for d in dirs if d not in excluded and not (Path(directory) / d).is_symlink()
            ]
            for name in names:
                path = Path(directory) / name
                if path.is_symlink() or not (
                    path.suffix.lower() in {".pdf", ".html", ".xlsx"}
                    or re.fullmatch(r"[a-f0-9]{64}", name)
                ):
                    continue
                resolved = str(path.resolve())
                if resolved in found:
                    continue
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    first = stream.read(65536)
                    digest.update(first)
                    for chunk in iter(lambda: stream.read(65536), b""):
                        digest.update(chunk)
                kind = (
                    "pdf"
                    if first.startswith(b"%PDF-")
                    else "xlsx"
                    if first.startswith(b"PK")
                    else "html"
                )
                found[resolved] = dict(
                    path=resolved,
                    name=name,
                    format=kind,
                    bytes=path.stat().st_size,
                    sha256=digest.hexdigest(),
                )
    return sorted(found.values(), key=lambda row: row["path"])


def database_audit(url: str) -> dict:
    """Enforce PostgreSQL read-only repeatable-read at the server, then rollback."""
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    if engine.dialect.name != "postgresql":
        engine.dispose()
        raise ValueError("POSTGRESQL_REQUIRED")
    queries = {
        "migration": "SELECT version_num FROM alembic_version",
        "schemas": "SELECT schema_name FROM information_schema.schemata "
        "WHERE schema_name NOT LIKE 'pg_%' AND schema_name!='information_schema'",
        "tables": "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema=current_schema() ORDER BY table_name",
        "versions": "SELECT sv.id, b.code bank, s.corpus_kind, s.kind, sv.content_state, "
        "sv.first_seen_at, sv.accepted_at, bl.sha256, bl.byte_size, bl.storage_key, "
        "s.url, s.policy_id FROM source_versions sv JOIN sources s ON "
        "s.id=sv.source_id JOIN banks b ON b.id=s.bank_id "
        "JOIN blobs bl ON bl.id=sv.blob_id ORDER BY sv.id",
        "policies": "SELECT id, collection_decision, acquisition_config FROM source_policies",
        "sources": "SELECT s.id,b.code bank,s.kind,s.corpus_kind,s.policy_id FROM sources s "
        "JOIN banks b ON b.id=s.bank_id ORDER BY s.id",
        "fetches": "SELECT source_id,source_version_id,fetched_at,acquisition_method,result, "
        "requested_url,final_url FROM source_fetches ORDER BY fetched_at",
        "extractions": "SELECT id, source_version_id, corpus_kind, status, parser_version, "
        "raw_sha256, extraction_sha256 FROM extraction_runs ORDER BY id",
        "snapshots": "SELECT id,revision,corpus_kind,state,manifest_sha256 FROM snapshots",
        "members": "SELECT snapshot_id,source_version_id,extraction_run_id FROM snapshot_members",
        "candidates": "SELECT id,extraction_run_id,corpus_kind,metric_code,payload "
        "FROM tariff_candidates ORDER BY id",
        "chunk_counts": "SELECT extraction_run_id,count(*) count FROM document_chunks "
        "GROUP BY extraction_run_id",
        "evidence_counts": "SELECT candidate_id,count(*) count FROM evidence_refs "
        "GROUP BY candidate_id",
        "reviews": "SELECT candidate_id,decision,count(*) count FROM fact_reviews "
        "GROUP BY candidate_id,decision",
        "published": "SELECT snapshot_id,candidate_id,review_id FROM published_facts",
        "broken_evidence": "SELECT e.candidate_id,count(*) count FROM evidence_refs e "
        "JOIN document_chunks c ON c.id=e.chunk_id "
        "JOIN extraction_runs r ON r.id=c.extraction_run_id WHERE "
        "e.extraction_run_id!=r.id OR e.source_version_id!=r.source_version_id "
        "OR e.raw_sha256!=r.raw_sha256 "
        "OR e.extraction_sha256!=r.extraction_sha256 OR e.locator!=c.locator "
        "OR e.quote!=substring(c.text FROM e.quote_start+1 "
        "FOR e.quote_end-e.quote_start) GROUP BY e.candidate_id",
    }
    result: dict = {}
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
            connection.exec_driver_sql("SET LOCAL statement_timeout = '15s'")
            result["read_only"] = connection.exec_driver_sql("SHOW transaction_read_only").scalar()
            tables = {r[0] for r in connection.execute(text(queries["tables"]))}
            for key, query in queries.items():
                table = re.search(r"FROM ([a-z_]+)", query)
                if table and table.group(1) not in tables and key not in {"schemas", "tables"}:
                    result[key] = {"status": "NOT RUN", "reason": "TABLE_ABSENT"}
                else:
                    result[key] = [dict(row) for row in connection.execute(text(query)).mappings()]
            connection.rollback()
    finally:
        engine.dispose()
    return result


def write_private_audit(env_file: Path, roots: list[Path], output: Path) -> dict:
    env = read_environment(env_file)
    storage = Path(env.get("STORAGE_ROOT", ".local/storage"))
    if not storage.is_absolute():
        storage = env_file.parent / storage
    report = {
        "files": inventory([*roots, storage]),
        "storage_exists": storage.exists(),
        "provider": {
            "mode": env.get("LLM_MODE", "fake"),
            "model": env.get("LLM_MODEL"),
            "key_present": bool(env.get("LLM_API_KEY")),
        },
    }
    try:
        Settings.from_environment({**env, "LLM_MODE": "provider"})
        report["provider"]["configuration_check"] = "PASS_SYNTAX_ONLY"
    except SettingsError:
        report["provider"]["configuration_check"] = "INVALID_OR_INCOMPLETE"
    if env.get("DATABASE_URL"):
        try:
            report["database"] = database_audit(env["DATABASE_URL"])
        except Exception as exc:
            # DB exceptions can expose credentials, connection strings and SQL values.
            report["database"] = {"status": "NOT RUN", "error_class": type(exc).__name__}
    else:
        report["database"] = {"status": "NOT RUN", "reason": "DATABASE_URL_MISSING"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return report
