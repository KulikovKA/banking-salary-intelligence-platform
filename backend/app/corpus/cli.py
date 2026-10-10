"""Explicit operator CLI for validating, composing, and freezing snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import Settings
from app.corpus.service import CorpusError, CorpusService
from app.db.base import make_session_factory
from app.ingestion.errors import IngestionError
from app.ingestion.gateway import FetchGateway
from app.ingestion.service import IngestionService
from app.storage.local import LocalBlobStore


def _service() -> CorpusService:
    settings = Settings.from_environment()
    if settings.database_url is None:
        raise CorpusError("CONFIG_DATABASE_REQUIRED")
    factory = make_session_factory(settings.database_url.get_secret_value())
    store = LocalBlobStore(settings.storage_root, settings.source_max_bytes)
    # Corpus commands never call the gateway; keep the established offline composition.
    ingestion = IngestionService(factory, settings, store, FetchGateway(settings, store))
    return CorpusService(ingestion)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "add-version", "freeze"):
        command = commands.add_parser(name)
        command.add_argument("--manifest", type=Path, required=True)
        if name == "add-version":
            command.add_argument("--document-index", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        service = _service()
        manifest = service.load_manifest(args.manifest)
        if args.command == "validate":
            result = service.validate(manifest)
            result["dry_run"] = True
        elif args.command == "add-version":
            result = service.add_version(manifest, args.document_index)
        else:
            result = service.freeze(manifest)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (CorpusError, IngestionError) as exc:
        print(json.dumps({"error_code": getattr(exc, "code", str(exc))}, sort_keys=True))
        return 1
    except Exception:
        print(json.dumps({"error_code": "CORPUS_CONFIG_OR_DATABASE_ERROR"}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
