"""Offline local operator inspection, evidence validation, review and publication."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from app.config import Settings, SettingsError
from app.corpus.service import CorpusError, CorpusService
from app.db.base import make_session_factory
from app.evidence.service import EvidenceService
from app.evidence.validation import EvidenceError, SemanticConfirmation
from app.ingestion.errors import IngestionError
from app.ingestion.gateway import FetchGateway
from app.ingestion.service import IngestionService
from app.storage.local import LocalBlobStore


def _service() -> EvidenceService:
    settings = Settings.from_environment()
    if settings.database_url is None:
        raise EvidenceError("CONFIG_DATABASE_REQUIRED")
    factory = make_session_factory(settings.database_url.get_secret_value())
    store = LocalBlobStore(settings.storage_root, settings.source_max_bytes)
    ingestion = IngestionService(factory, settings, store, FetchGateway(settings, store))
    return EvidenceService(CorpusService(ingestion))


def _confirmation(path: Path | None) -> SemanticConfirmation | None:
    if path is None:
        return None
    try:
        with path.open("rb") as source:
            data = source.read(65537)
        if len(data) > 65536:
            raise EvidenceError("CONFIRMATION_TOO_LARGE")
        value = json.loads(data)
        if not isinstance(value, dict) or set(value) != {"field_evidence"}:
            raise EvidenceError("CONFIRMATION_INVALID")
        fields = value["field_evidence"]
        if not isinstance(fields, dict) or any(
            not isinstance(key, str)
            or not isinstance(ids, list)
            or not all(isinstance(ref_id, str) for ref_id in ids)
            for key, ids in fields.items()
        ):
            raise EvidenceError("CONFIRMATION_INVALID")
        return SemanticConfirmation(fields)
    except (OSError, ValueError, UnicodeError) as exc:
        if isinstance(exc, EvidenceError):
            raise
        raise EvidenceError("CONFIRMATION_INVALID") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "validate", "review", "publish"):
        sub = commands.add_parser(command)
        sub.add_argument("--candidate-id", type=UUID, required=True)
        if command in {"validate", "review"}:
            sub.add_argument("--confirmation", type=Path)
        if command == "review":
            sub.add_argument(
                "--decision", choices=["approved", "rejected", "needs_review"], required=True
            )
            sub.add_argument("--reviewer", required=True)
            sub.add_argument("--reason", required=True)
            sub.add_argument("--user-id", type=UUID)
        if command == "publish":
            sub.add_argument("--review-id", type=UUID, required=True)
    args = parser.parse_args(argv)
    try:
        service = _service()
        manifest = service.corpus.load_manifest(args.manifest)
        candidate_id = str(args.candidate_id)
        if args.command == "inspect":
            result = service.inspect(manifest, candidate_id)
        elif args.command == "validate":
            report = service.validate(manifest, candidate_id, _confirmation(args.confirmation))
            print(json.dumps(report.as_dict(), sort_keys=True))
            return 0 if report.valid else 1
        elif args.command == "review":
            result = {
                "review_id": service.review(
                    manifest,
                    candidate_id,
                    decision=args.decision,
                    reviewer_label=args.reviewer,
                    reason=args.reason,
                    confirmation=_confirmation(args.confirmation),
                    user_id=str(args.user_id) if args.user_id else None,
                )
            }
        else:
            result = asdict(service.publish(manifest, candidate_id, str(args.review_id)))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (EvidenceError, CorpusError, IngestionError) as exc:
        print(json.dumps({"error_code": exc.code}))
        return 1
    except SettingsError:
        print(json.dumps({"error_code": "CONFIG_INVALID"}))
        return 1
    except Exception:
        print(json.dumps({"error_code": "EVIDENCE_CLI_FAILED"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
