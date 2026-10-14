"""Local research diagnostic boundaries, using only authored synthetic bytes."""

import hashlib
import json

import pytest

from evaluation.diagnostics import diagnose_research


def test_smoke_is_private_and_preserves_original(tmp_path):
    original = tmp_path / "original.html"
    content = b"<html><body><h1>Synthetic fee</h1><p>100 RUB per month</p></body></html>"
    original.write_bytes(content)
    output = tmp_path / ".local" / "diagnostic.json"
    result = diagnose_research(original, "sber", output, admitted=True)
    assert result["parse_status"] == "ok"
    assert result["diagnostic_only"] is True
    assert result["persisted_source_version_id"] is None
    assert result["publication_count"] == 0
    assert result["raw_sha256"] == hashlib.sha256(content).hexdigest()
    assert original.read_bytes() == content
    assert "original_path" not in result and "parse_result" not in result
    private = json.loads(output.read_text(encoding="utf-8"))
    assert private["parse_result"]["blocks"]
    assert "100 RUB" in output.read_text(encoding="utf-8")


@pytest.mark.parametrize("case", ["no_admission", "public_output", "overwrite_original"])
def test_no_parse_without_admission_or_safe_output(tmp_path, case):
    original = tmp_path / ".local" / "original.html"
    original.parent.mkdir()
    original.write_bytes(b"<html><p>synthetic</p></html>")
    output = tmp_path / ".local" / "diagnostic.json"
    if case == "public_output":
        output = tmp_path / "public.json"
    elif case == "overwrite_original":
        output = original
    with pytest.raises(ValueError):
        diagnose_research(original, "sber", output, admitted=case != "no_admission")
    assert original.read_bytes() == b"<html><p>synthetic</p></html>"


def test_chunk_offsets_can_validate_without_semantic_approval(tmp_path):
    original = tmp_path / "original.html"
    original.write_text(
        "<html><body><p>Комиссия за зачисление зарплаты 0,3 %</p></body></html>", encoding="utf-8"
    )
    result = diagnose_research(
        original, "sber", tmp_path / ".local" / "capture.json", admitted=True
    )
    assert result["suggestions"] > 0
    assert result["diagnostic_evidence_quotes"] > 0
    assert result["invalid_chunk_quote_offsets"] == 0
    assert result["normalized_candidates"] == 0
    assert result["normalization_flags"]["PAYER_UNKNOWN"] > 0
