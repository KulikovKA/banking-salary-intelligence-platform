"""Fixed thresholds, exact integer ratios, missing observations never count as correct."""

from __future__ import annotations

import hashlib
import math
from itertools import combinations

from evaluation.schema import BANKS, PAIRS, Evidence, Gold, Observations

THRESHOLDS = {
    "evidence_linkage": (100, 100),
    "value_unit_basis_period": (98, 100),
    "conditions_recall": (95, 100),
    "retrieval_recall_at_10": (90, 100),
    "deterministic_comparisons": (100, 100),
    "intent_accuracy": (90, 100),
}
DIAGNOSTICS = (
    "PARSE_FAILED",
    "NEEDS_OCR",
    "NO_RELEVANT_CONTENT",
    "ZERO_CANDIDATES",
    "ALL_CANDIDATES_REJECTED",
    "MISSING_EVIDENCE",
    "AMBIGUOUS_VALUE",
    "MISSING_CONDITION",
    "UNKNOWN_SCOPE",
    "UNKNOWN_DATE",
    "CONFLICTING_TARIFFS",
)


def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [canonical(v) for v in value]
    return value


def value_key(value):
    if value is None:
        return None
    payload = value.model_dump(mode="python")
    # Pydantic stores monetary amounts as Decimal; equality is exact, never float.
    return canonical(payload)


def valid_evidence(item: Evidence) -> bool:
    return (
        item.quote_end > item.quote_start
        and item.quote_end <= len(item.chunk_text)
        and item.chunk_text[item.quote_start : item.quote_end] == item.quote
        and hashlib.sha256(item.chunk_text.encode()).hexdigest() == item.chunk_sha256
    )


def ratio(name, numerator, denominator):
    threshold = THRESHOLDS[name]
    return {
        "numerator": numerator,
        "denominator": denominator,
        "threshold": f"{threshold[0]}/{threshold[1]}",
        "status": "NOT EVALUATED"
        if denominator == 0
        else "PASS"
        if numerator * threshold[1] >= denominator * threshold[0]
        else "FAIL",
    }


def pair_key(banks):
    return "/".join(bank for bank in BANKS if bank in banks)


def evaluate(gold: Gold, observations: Observations, gold_sha256: str) -> dict:
    if (
        observations.gold_sha256 != gold_sha256
        or observations.corpus_kind != gold.corpus_kind
        or observations.snapshot_id != gold.snapshot_id
        or observations.corpus_revision != gold.corpus_revision
    ):
        raise ValueError("OBSERVATION_PROVENANCE_MISMATCH")
    for expected, observed in (
        (gold.facts, observations.facts),
        (gold.evidence, observations.evidence),
        (gold.questions, observations.questions),
        (gold.comparisons, observations.comparisons),
    ):
        if not {x.id for x in observed} <= {x.id for x in expected}:
            raise ValueError("UNEXPECTED_OBSERVATION_ID")
    if any(not valid_evidence(item) for item in gold.evidence):
        raise ValueError("INVALID_GOLD_EVIDENCE")
    expected_evidence = {e.id: e for e in gold.evidence}
    actual_evidence = {e.id: e for e in observations.evidence}
    facts = {f.id: f for f in observations.facts}
    questions = {q.id: q for q in observations.questions}
    comparisons = {c.id: c for c in observations.comparisons}
    buckets = {"overall": [], **{b: [] for b in BANKS}, **{p: [] for p in PAIRS}}
    missing = []

    def add(group, name, numerator, denominator):
        for key in ("overall", group):
            buckets[key].append((name, numerator, denominator))

    for fact in gold.facts:
        if fact.split != "holdout":
            continue
        actual = facts.get(fact.id)
        if actual is None:
            missing.append({"kind": "fact", "id": fact.id})
        support = bool(actual) and set(actual.evidence_ids) == set(fact.evidence_ids)
        support = support and all(
            eid in actual_evidence
            and actual_evidence[eid] == expected_evidence[eid]
            and valid_evidence(actual_evidence[eid])
            for eid in fact.evidence_ids
        )
        correct = bool(actual) and (
            value_key(actual.value) == value_key(fact.value)
            and actual.status == fact.status
            and actual.payer == fact.payer
            and actual.operation == fact.operation
            and actual.period == fact.period
            and actual.scope == fact.scope
            and actual.effective_date == fact.effective_date
        )
        add(fact.bank, "evidence_linkage", int(support), 1)
        add(fact.bank, "value_unit_basis_period", int(correct), 1)
        add(
            fact.bank,
            "conditions_recall",
            len(set(fact.required_conditions) & set(actual.conditions if actual else ())),
            len(set(fact.required_conditions)),
        )
    unsupported = 0
    for question in gold.questions:
        if question.split != "holdout":
            continue
        actual = questions.get(question.id)
        group = question.banks[0] if len(question.banks) == 1 else pair_key(question.banks)
        if actual is None:
            missing.append({"kind": "question", "id": question.id})
        retrieved = actual.retrieved_chunk_ids[:10] if actual else ()
        add(
            group,
            "retrieval_recall_at_10",
            len(set(retrieved) & set(question.relevant_chunk_ids)),
            len(set(question.relevant_chunk_ids)),
        )
        add(
            group,
            "intent_accuracy",
            int(
                bool(actual)
                and not actual.fallback
                and not actual.error
                and actual.intent == question.expected_intent
            ),
            1,
        )
        bad = (
            (
                len([c for c in actual.claims if c not in question.allowed_claims])
                + len([n for n in actual.numbers if n not in question.allowed_numbers])
            )
            if actual
            else 0
        )
        unsupported += bad
        add(group, "unsupported_claims", bad, 1)
    for comparison in gold.comparisons:
        if comparison.split != "holdout":
            continue
        actual = comparisons.get(comparison.id)
        if actual is None:
            missing.append({"kind": "comparison", "id": comparison.id})
        add(
            pair_key(comparison.banks),
            "deterministic_comparisons",
            int(bool(actual) and actual.result == comparison.expected),
            1,
        )
    breakdown = {}
    for group, entries in buckets.items():
        metrics = {}
        for name in THRESHOLDS:
            selected = [(n, d) for m, n, d in entries if m == name]
            metrics[name] = ratio(name, sum(n for n, _ in selected), sum(d for _, d in selected))
        claims = [(n, d) for m, n, d in entries if m == "unsupported_claims"]
        metrics["unsupported_claims"] = dict(
            numerator=sum(n for n, _ in claims),
            denominator=sum(d for _, d in claims),
            threshold="0",
            status="NOT EVALUATED"
            if not claims
            else "PASS"
            if sum(n for n, _ in claims) == 0
            else "FAIL",
        )
        breakdown[group] = metrics
    coverage = {}
    by_id = {f.id: f for f in gold.facts}
    for pair in combinations(BANKS, 2):
        comparable, numeric = set(), set()
        for item in gold.coverage:
            if set(item.banks) != set(pair):
                continue
            refs = [by_id[fid] for fid in item.fact_ids]
            if (
                not item.comparable
                or {f.bank for f in refs} != set(pair)
                or any(f.status != "verified" or f.metric != item.metric for f in refs)
                or any(
                    f.scope != refs[0].scope
                    or f.period != refs[0].period
                    or f.payer != refs[0].payer
                    or f.operation != refs[0].operation
                    or f.effective_date != refs[0].effective_date
                    or f.required_conditions != refs[0].required_conditions
                    for f in refs
                )
                or any(not f.effective_date or "unknown" in str(f.scope) for f in refs)
                or any(
                    tuple(
                        getattr(f.value, name, None)
                        for name in ("currency", "unit", "basis", "period")
                    )
                    != tuple(
                        getattr(refs[0].value, name, None)
                        for name in ("currency", "unit", "basis", "period")
                    )
                    for f in refs
                )
            ):
                continue
            comparable.add(item.metric)
            if item.numeric_employer_cost and all(
                f.payer == "employer"
                and f.value is not None
                and f.value.kind in {"money", "percent", "formula"}
                for f in refs
            ):
                numeric.add(item.metric)
        coverage[pair_key(pair)] = dict(
            comparable=len(comparable),
            numeric_employer_cost=len(numeric),
            status="PASS" if len(comparable) >= 2 and numeric else "BLOCKED",
        )
    counts = dict(
        facts=len(gold.facts),
        questions=len(gold.questions),
        comparisons=len(gold.comparisons),
        human_reviewed=sum(bool(f.human_review_id) for f in gold.facts),
        per_bank={
            b: {
                "facts": sum(f.bank == b for f in gold.facts),
                "questions": sum(q.banks == (b,) for q in gold.questions),
            }
            for b in BANKS
        },
        per_pair={p: sum(pair_key(q.banks) == p for q in gold.questions) for p in PAIRS},
    )
    requirements = [
        "S1 requires independent source approvals, accepted originals and frozen review",
        "S2 requires admitted real corpus and independent human-reviewed gold",
        "S3 requires explicit provider run authorization/admission and >=20 real questions",
    ]
    sample_requirements = {
        "reviewed_facts": {"actual": counts["human_reviewed"], "minimum": 40},
        "bank_facts": {
            "actual": min(c["facts"] for c in counts["per_bank"].values()),
            "minimum": 10,
        },
        "reviewed_facts_per_bank": {
            "actual": min(
                sum(f.bank == bank and bool(f.human_review_id) for f in gold.facts)
                for bank in BANKS
            ),
            "minimum": 10,
        },
        "bank_questions": {
            "actual": min(c["questions"] for c in counts["per_bank"].values()),
            "minimum": 6,
        },
        "pair_questions": {"actual": min(counts["per_pair"].values()), "minimum": 2},
        "holdout_comparisons": {
            "actual": sum(c.split == "holdout" for c in gold.comparisons),
            "minimum": 30,
        },
        "family_split": {"actual": len({f.split for f in gold.facts}), "minimum": 2},
    }
    for requirement in sample_requirements.values():
        requirement["status"] = (
            "PASS" if requirement["actual"] >= requirement["minimum"] else "BLOCKED"
        )
    holdout_ids = {q.id for q in gold.questions if q.split == "holdout"}
    provider_questions = [q for q in observations.questions if q.id in holdout_ids and q.model_id]
    latencies = sorted(q.latency_ms for q in provider_questions if q.latency_ms is not None)
    return dict(
        schema_version=1,
        corpus_kind=gold.corpus_kind,
        snapshot_id=gold.snapshot_id,
        corpus_revision=gold.corpus_revision,
        gold_sha256=gold_sha256,
        observation_mode=observations.mode,
        counts=counts,
        sample_requirements=sample_requirements,
        metrics=breakdown["overall"],
        per_bank={b: breakdown[b] for b in BANKS},
        per_pair={p: breakdown[p] for p in PAIRS},
        coverage=coverage,
        missing=missing,
        unsupported_claims=unsupported,
        gates={
            "S0": "NOT EVALUATED",
            "S1": "BLOCKED",
            "S2": "NOT EVALUATED",
            "S3": "NOT EVALUATED",
        },
        blocked=requirements,
        skipped=[
            "Full product acceptance is outside metric replay",
            "Tune cases excluded from holdout metrics",
        ],
        provider={
            "attempted": len(provider_questions),
            "fallbacks": sum(q.fallback for q in provider_questions),
            "errors": sum(q.error is not None for q in provider_questions),
            "rate_limit_errors": sum(q.error == "rate_limit" for q in provider_questions),
            "models": sorted({q.model_id for q in provider_questions}),
            "prompt_tokens": sum(q.prompt_tokens or 0 for q in provider_questions),
            "completion_tokens": sum(q.completion_tokens or 0 for q in provider_questions),
            "usage_missing": sum(
                q.prompt_tokens is None or q.completion_tokens is None for q in provider_questions
            ),
            "latency_samples": len(latencies),
            "latency_p95_ms": latencies[math.ceil(len(latencies) * 0.95) - 1]
            if latencies
            else None,
            "fallback_rate": {
                "numerator": sum(q.fallback for q in provider_questions),
                "denominator": len(provider_questions),
            },
        },
        note="Metrics score captured structured observations; they do not issue admissions.",
    )


def markdown(report: dict) -> str:
    lines = [
        "# Snapshot evaluation",
        "",
        f"Corpus: **{report['corpus_kind']}**; "
        f"revision {report['corpus_revision']}; mode `{report['observation_mode']}`.",
        f"Gold SHA-256: `{report['gold_sha256']}`.",
        "",
        "| Metric | Numerator | Denominator | Threshold | Result |",
        "|---|---:|---:|---|---|",
    ]
    for name, metric in report["metrics"].items():
        lines.append(
            f"| {name} | {metric['numerator']} | {metric['denominator']} | "
            f"{metric['threshold']} | {metric['status']} |"
        )
    for heading in ("per_bank", "per_pair"):
        lines.extend(
            ["", f"## {heading}", "", "| Group | Metric | n/d | Result |", "|---|---|---|---|"]
        )
        for group, metrics in report[heading].items():
            for name, metric in metrics.items():
                lines.append(
                    f"| {group} | {name} | {metric['numerator']}/"
                    f"{metric['denominator']} | {metric['status']} |"
                )
    lines.extend(
        [
            "",
            "## Pair coverage",
            "",
            "| Pair | Criteria | Numeric employer cost | Result |",
            "|---|---:|---:|---|",
        ]
    )
    for pair, row in report["coverage"].items():
        lines.append(
            f"| {pair} | {row['comparable']} | {row['numeric_employer_cost']} | {row['status']} |"
        )
    lines.extend(["", "## Product gates", ""])
    lines.extend(f"- {gate}: {status}" for gate, status in report["gates"].items())
    lines.extend(
        [
            "",
            "## Minimum sample requirements",
            "",
            "| Requirement | Actual | Minimum | Result |",
            "|---|---:|---:|---|",
        ]
    )
    for name, row in report["sample_requirements"].items():
        lines.append(f"| {name} | {row['actual']} | {row['minimum']} | {row['status']} |")
    lines.extend(["", "## Blocked / skipped", ""])
    lines.extend(f"- {reason}" for reason in (*report["blocked"], *report["skipped"]))
    lines.extend(["", f"Missing observations: {len(report['missing'])}.", "", report["note"], ""])
    return "\n".join(lines)
