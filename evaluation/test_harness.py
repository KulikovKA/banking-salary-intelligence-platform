"""Adversarial evaluation oracles: defects must reduce measured quality."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation.engine import run_comparison
from evaluation.io import load_gold
from evaluation.metrics import evaluate, ratio
from evaluation.schema import Gold, Observations

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def dataset():
    raw = (FIXTURES / "synthetic-gold.json").read_bytes()
    return (
        json.loads(raw),
        json.loads((FIXTURES / "synthetic-observations.json").read_bytes()),
        hashlib.sha256(raw).hexdigest(),
    )


def score(dataset):
    g, o, h = dataset
    return evaluate(Gold.model_validate(g), Observations.model_validate(o), h)


def test_pinned_repeatable_and_separate_gates(dataset):
    first = score(dataset)
    assert first == score(dataset)
    assert first["metrics"]["value_unit_basis_period"]["numerator"] == 40
    assert first["metrics"]["retrieval_recall_at_10"]["denominator"] == 48
    assert first["counts"]["human_reviewed"] == 0
    assert first["gates"] == {
        "S0": "NOT EVALUATED",
        "S1": "BLOCKED",
        "S2": "NOT EVALUATED",
        "S3": "NOT EVALUATED",
    }
    assert all(c["status"] == "BLOCKED" for c in first["coverage"].values())
    assert len(first["per_pair"]) == 6


@pytest.mark.parametrize(
    "defect",
    [
        "fee",
        "period",
        "footnote",
        "locator",
        "hash",
        "quote",
        "missing_evidence",
        "retrieval",
        "unsupported",
        "scope",
        "date",
        "basis",
        "unit",
    ],
)
def test_known_defects(dataset, defect):
    _, o, _ = dataset
    fact = o["facts"][0]
    metric = "value_unit_basis_period"
    if defect == "fee":
        fact["value"]["amount"] = "101"
    elif defect == "period":
        fact["value"]["period"] = "year"
    elif defect == "footnote":
        fact["conditions"] = []
        metric = "conditions_recall"
    elif defect == "locator":
        o["evidence"][0]["locator"]["element_path"] = "/html/body/p[99]"
        metric = "evidence_linkage"
    elif defect == "hash":
        o["evidence"][0]["raw_sha256"] = "0" * 64
        metric = "evidence_linkage"
    elif defect == "quote":
        o["evidence"][0]["quote"] = "fabricated"
        metric = "evidence_linkage"
    elif defect == "missing_evidence":
        fact["evidence_ids"] = []
        metric = "evidence_linkage"
    elif defect == "retrieval":
        o["questions"][0]["retrieved_chunk_ids"] = []
        metric = "retrieval_recall_at_10"
    elif defect == "unsupported":
        o["questions"][0]["numbers"] = ["999"]
        assert score(dataset)["metrics"]["unsupported_claims"]["status"] == "FAIL"
        return
    elif defect == "scope":
        fact["scope"] = {"geography": "unknown"}
    elif defect == "date":
        fact["effective_date"] = None
    elif defect == "basis":
        fact["value"] = dict(kind="percent", amount="100", basis="payroll_total", period="month")
    elif defect == "unit":
        fact["value"] = dict(kind="count", amount=100, unit="employees", period="month")
    result = score(dataset)
    assert result["metrics"][metric]["numerator"] < result["metrics"][metric]["denominator"]


def test_recall_cap_and_duplicates(dataset):
    o = dataset[1]
    chunk = o["questions"][0]["retrieved_chunk_ids"][0]
    o["questions"][0]["retrieved_chunk_ids"] = ["irrelevant"] * 10 + [chunk]
    assert score(dataset)["metrics"]["retrieval_recall_at_10"]["numerator"] == 47


def test_missing_observations_are_failures(dataset):
    dataset[1]["facts"] = []
    dataset[1]["questions"] = []
    dataset[1]["comparisons"] = []
    report = score(dataset)
    assert len(report["missing"]) == 106
    assert report["metrics"]["value_unit_basis_period"]["status"] == "FAIL"
    assert report["metrics"]["deterministic_comparisons"]["status"] == "FAIL"


def test_empty_denominators_never_pass(dataset):
    dataset[0]["facts"] = []
    dataset[0]["questions"] = []
    dataset[0]["comparisons"] = []
    dataset[0]["coverage"] = []
    dataset[1]["facts"] = []
    dataset[1]["questions"] = []
    dataset[1]["comparisons"] = []
    assert score(dataset)["metrics"]["value_unit_basis_period"]["status"] == "NOT EVALUATED"


def test_no_rounding_a_failed_small_sample():
    assert ratio("value_unit_basis_period", 39, 40)["status"] == "FAIL"
    assert ratio("value_unit_basis_period", 49, 50)["status"] == "PASS"


@pytest.mark.parametrize("defect", ["kind", "hash", "revision", "duplicate", "extra"])
def test_observation_binding(dataset, defect):
    o = dataset[1]
    if defect == "kind":
        o["corpus_kind"] = "real"
        o["mode"] = "real_capture"
    elif defect == "hash":
        o["gold_sha256"] = "0" * 64
    elif defect == "revision":
        o["corpus_revision"] = 2
    elif defect == "duplicate":
        o["facts"].append(copy.deepcopy(o["facts"][0]))
    else:
        extra = copy.deepcopy(o["facts"][0])
        extra["id"] = "unexpected"
        o["facts"].append(extra)
    with pytest.raises((ValueError, ValidationError)):
        score(dataset)


def test_hash_tampering(tmp_path):
    path = tmp_path / "gold.json"
    path.write_bytes((FIXTURES / "synthetic-gold.json").read_bytes() + b"\n")
    with pytest.raises(ValueError, match="GOLD_HASH_MISMATCH"):
        load_gold(path, (FIXTURES / "synthetic-gold.sha256").read_text().strip())


def test_split_family_leakage(dataset):
    dataset[0]["facts"][0]["split"] = "tune"
    with pytest.raises(ValidationError, match="DOCUMENT_FAMILY_LEAKAGE"):
        score(dataset)


def test_gold_bytes_are_platform_independent_lf():
    raw = (FIXTURES / "synthetic-gold.json").read_bytes()
    assert b"\r\n" not in raw
    assert (
        hashlib.sha256(raw).hexdigest() == (FIXTURES / "synthetic-gold.sha256").read_text().strip()
    )


def test_invalid_gold_quote(dataset):
    dataset[0]["evidence"][0]["quote"] = "fabricated"
    with pytest.raises(ValueError, match="INVALID_GOLD_EVIDENCE"):
        score(dataset)


def test_tune_defects_excluded(dataset):
    dataset[1]["facts"][10]["value"]["amount"] = "999"
    assert score(dataset)["metrics"]["value_unit_basis_period"]["numerator"] == 40


def test_merged_engine_against_30_independent_oracles(dataset):
    gold = Gold.model_validate(dataset[0])
    for case in gold.comparisons:
        assert run_comparison(gold, case) == case.expected


@pytest.mark.parametrize("case_index", [2, 3, 4])
def test_unknown_individual_conflict_cannot_be_zero(dataset, case_index):
    dataset[1]["comparisons"][case_index]["result"]["rows"][0]["cells"][0]["status"] = "verified"
    assert score(dataset)["metrics"]["deterministic_comparisons"] == dict(
        numerator=29, denominator=30, threshold="100/100", status="FAIL"
    )


def test_provider_fallback_does_not_count_as_success(dataset):
    dataset[1]["questions"][0]["fallback"] = True
    dataset[1]["questions"][0]["model_id"] = "openai/gpt-oss-120b"
    report = score(dataset)
    assert report["metrics"]["intent_accuracy"]["numerator"] == 35
    assert report["gates"]["S3"] == "NOT EVALUATED"


def test_fixed_faulty_capture_fails_all_target_metrics(dataset):
    faulty = json.loads((FIXTURES / "synthetic-faulty-observations.json").read_bytes())
    report = evaluate(
        Gold.model_validate(dataset[0]), Observations.model_validate(faulty), dataset[2]
    )
    for metric in (
        "evidence_linkage",
        "value_unit_basis_period",
        "conditions_recall",
        "retrieval_recall_at_10",
        "deterministic_comparisons",
        "unsupported_claims",
    ):
        assert report["metrics"][metric]["status"] == "FAIL"


def test_unknown_scope_never_increases_numeric_coverage(dataset):
    dataset[0]["facts"][0]["scope"] = {"geography": "unknown"}
    report = score(dataset)
    assert report["coverage"]["sber/vtb"]["numeric_employer_cost"] == 0


def test_unknown_and_individual_observations_are_explicit(dataset):
    for index, status in ((0, "unknown"), (1, "individual")):
        value = None if status == "unknown" else dict(kind="individual", text_value="By agreement")
        dataset[0]["facts"][index].update(status=status, value=value)
        dataset[1]["facts"][index].update(status=status, value=value)
    assert score(dataset)["metrics"]["value_unit_basis_period"]["numerator"] == 40
    dataset[1]["facts"][0]["value"] = dict(kind="money", amount="0", currency="RUB", period="month")
    assert score(dataset)["metrics"]["value_unit_basis_period"]["numerator"] == 39


def test_inventory_hash_and_env_remain_literal(tmp_path):
    from evaluation.audit import inventory, read_environment

    original = tmp_path / "synthetic.html"
    original.write_bytes(b"<html><p>fixture</p></html>")
    env = tmp_path / "existing.env"
    env.write_text("LLM_API_KEY='literal$(never-execute)'\nSTORAGE_ROOT=.local/storage\n")
    assert read_environment(env)["LLM_API_KEY"] == "literal$(never-execute)"
    found = inventory([tmp_path, tmp_path])
    assert len(found) == 1
    assert found[0]["sha256"] == hashlib.sha256(original.read_bytes()).hexdigest()
