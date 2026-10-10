"""Local operator command for one accepted source version."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from app.config import Settings, SettingsError
from app.corpus.service import CorpusError, CorpusService
from app.db.base import make_session_factory
from app.ingestion.errors import IngestionError
from app.ingestion.gateway import FetchGateway
from app.ingestion.service import IngestionService
from app.parsing.runner import BoundedParseError
from app.parsing.service import ExtractionPipeline, ExtractionPipelineError
from app.storage.local import LocalBlobStore


def _services() -> tuple[CorpusService, ExtractionPipeline]:
    settings = Settings.from_environment()
    if settings.database_url is None:
        raise ExtractionPipelineError("CONFIG_DATABASE_REQUIRED")
    factory = make_session_factory(settings.database_url.get_secret_value())
    store = LocalBlobStore(settings.storage_root, settings.source_max_bytes)
    # Pipeline uses only the stored original; the gateway is never called.
    ingestion = IngestionService(factory, settings, store, FetchGateway(settings, store))
    corpus = CorpusService(ingestion)
    return corpus, ExtractionPipeline(corpus)


def _read_json_mapping(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
        value = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtractionPipelineError("OPERATOR_MAPPING_INVALID_JSON") from exc
    if not isinstance(value, dict):
        raise ExtractionPipelineError("OPERATOR_MAPPING_SCHEMA_INVALID")
    return text


def _read_context(path: Path) -> dict[str, object]:
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtractionPipelineError("OPERATOR_CONTEXT_INVALID") from exc
    if not isinstance(value, dict):
        raise ExtractionPipelineError("OPERATOR_CONTEXT_INVALID")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-version-id", type=UUID, required=True)
    parser.add_argument("--parser-version", required=True)
    parser.add_argument("--operator-mapping", type=Path)
    parser.add_argument(
        "--context",
        type=Path,
        help="optional JSON with explicit payer/operation and scope context",
    )
    args = parser.parse_args(argv)
    try:
        corpus, pipeline = _services()
        manifest = corpus.load_manifest(args.manifest)
        matches = [
            index for index, item in enumerate(manifest.documents)
            if item.source_version_id == args.source_version_id
        ]
        if len(matches) != 1:
            raise ExtractionPipelineError("SOURCE_VERSION_NOT_IN_MANIFEST")
        # Create or verify the draft staging row before parsing this exact document.
        corpus.add_version(manifest, matches[0])
        mapping = _read_json_mapping(args.operator_mapping) if args.operator_mapping else None
        context = _read_context(args.context) if args.context else None
        result = pipeline.run(
            manifest,
            args.source_version_id,
            parser_version=args.parser_version,
            operator_mapping=mapping,
            context=context,
        )
        print(json.dumps({
            "extraction_id": result.extraction_id,
            "status": result.status,
            "chunk_count": result.chunk_count,
            "candidate_count": result.candidate_count,
            "diagnostic_count": result.diagnostic_count,
            "diagnostics": [
                {"code": item.code, "count": item.count}
                for item in result.diagnostics
            ],
            "idempotent": result.idempotent,
        }, sort_keys=True))
        return 0 if result.status == "ok" else 1
    except (ExtractionPipelineError, CorpusError, IngestionError, BoundedParseError) as exc:
        print(json.dumps({
            "error_code": getattr(exc, "code", str(exc)),
        }, sort_keys=True))
        return 1
    except SettingsError as exc:
        print(json.dumps({"error_code": str(exc).split(":", 1)[0]}, sort_keys=True))
        return 1
    except Exception:
        print(json.dumps({"error_code": "EXTRACTION_CLI_FAILED"}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
