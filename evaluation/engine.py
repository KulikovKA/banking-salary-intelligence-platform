"""Exercise the merged ComparisonService on synthetic records only, without a DB."""

import asyncio
from datetime import UTC, datetime

from app.comparison.service import ComparisonService
from app.contracts.comparison import ComparisonRequest, ComparisonResult
from app.corpus.service import SnapshotManifest
from evaluation.schema import Comparison, Gold


def project_result(result: ComparisonResult) -> dict:
    """Stable financial output; excludes clock, generated IDs and narrative serialization."""
    return {
        "rows": [
            {
                "metric": row.metric_code,
                "cells": [
                    {
                        "bank": c.bank_code,
                        "status": c.status,
                        "value": c.value.model_dump(mode="json") if c.value else None,
                        "missing_inputs": list(c.missing_inputs),
                    }
                    for c in row.cells
                ],
                "pairs": [
                    {
                        "left": p.left,
                        "right": p.right,
                        "status": p.status,
                        "delta": str(p.delta) if p.delta is not None else None,
                    }
                    for p in row.pairwise
                ],
            }
            for row in result.rows
        ]
    }


def run_comparison(gold: Gold, case: Comparison) -> dict:
    if gold.corpus_kind != "synthetic":
        raise ValueError("ENGINE_FIXTURE_SYNTHETIC_ONLY")
    manifest = SnapshotManifest.model_validate(
        dict(
            snapshot_id=gold.snapshot_id,
            revision=gold.corpus_revision,
            corpus_kind="synthetic",
            region="RU-KDA",
            employer_segment="SME",
            documents=[
                dict(
                    bank_code="sber",
                    source_id="00000000-0000-0000-0000-000000000001",
                    source_version_id="00000000-0000-0000-0000-000000000002",
                    source_fetch_id="00000000-0000-0000-0000-000000000003",
                    policy_id="00000000-0000-0000-0000-000000000004",
                    extraction_run_id="00000000-0000-0000-0000-000000000005",
                    sha256="1" * 64,
                    acquisition_method="manual",
                    original_url="https://example.com/synthetic.html",
                    final_url="https://example.com/synthetic.html",
                    acquired_at="2026-10-12T00:00:00Z",
                    scope={},
                    document_type="synthetic",
                )
            ],
            missing_documents=[
                dict(bank_code=b, document_type="synthetic", reason="fixture")
                for b in ("vtb", "alfa", "kuban_credit")
            ],
        )
    )

    class Reader:
        def read_published(self, _manifest):
            return case.records

    request = ComparisonRequest.model_validate(case.request)
    service = ComparisonService(
        Reader(), lambda _: manifest, clock=lambda: datetime(2026, 10, 12, tzinfo=UTC)
    )
    return project_result(asyncio.run(service.compare(request)))
