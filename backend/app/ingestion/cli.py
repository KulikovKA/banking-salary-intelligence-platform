"""Explicit operator commands; no scheduler, approvals or live sources are seeded."""

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.db.base import make_session_factory
from app.ingestion.errors import IngestionError
from app.ingestion.gateway import FetchGateway
from app.ingestion.service import IngestionService
from app.storage.local import LocalBlobStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch")
    fetch.add_argument("--source-id", required=True)
    fetch.add_argument("--attempt", type=int, default=1)
    manual = commands.add_parser("import-file")
    manual.add_argument("--source-id", required=True)
    manual.add_argument("--file", type=Path, required=True)
    manual.add_argument("--operator", required=True)
    manual.add_argument("--original-url", required=True)
    manual.add_argument("--final-url", required=True)
    manual.add_argument("--acquired-at", required=True, help="ISO timestamp with UTC offset")
    args = parser.parse_args()
    try:
        settings = Settings.from_environment()
        if not settings.database_url:
            raise IngestionError("CONFIG_DATABASE_REQUIRED")
        factory = make_session_factory(settings.database_url.get_secret_value())
        store = LocalBlobStore(settings.storage_root, settings.source_max_bytes)
        service = IngestionService(factory, settings, store, FetchGateway(settings, store))
        if args.command == "fetch":
            outcome = service.fetch_source(args.source_id, attempt=args.attempt)
        else:
            outcome = service.import_file(
                args.source_id,
                args.file,
                operator=args.operator,
                original_url=args.original_url,
                final_url=args.final_url,
                acquired_at=datetime.fromisoformat(args.acquired_at),
            )
        print(json.dumps(asdict(outcome), default=str))
        return 1 if outcome.error_code else 0
    except IngestionError as exc:
        print(json.dumps({"error_code": exc.code}))
        return 1
    except Exception:
        print(json.dumps({"error_code": "INGESTION_CONFIG_OR_DATABASE_ERROR"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
