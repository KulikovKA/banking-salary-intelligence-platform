from uuid import uuid4

import pytest

from app.ingestion.evidence import ExtractionEvidence


def test_unknown_evidence_stays_pending_and_quote_is_checked():
    evidence = ExtractionEvidence(
        source_version_id=uuid4(),
        raw_sha256="a" * 64,
        extraction_sha256="b" * 64,
        parser_version="synthetic-v1",
        corpus_kind="synthetic",
        quote="synthetic",
        quote_start=0,
        quote_end=9,
    )
    assert evidence.publication_state == "pending_review"
    assert evidence.geography == "unknown" and evidence.effective_from is None
    evidence.check_chunk("synthetic document")
    with pytest.raises(ValueError, match="EVIDENCE_QUOTE_INVALID"):
        evidence.check_chunk("different document")
