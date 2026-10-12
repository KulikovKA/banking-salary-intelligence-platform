"""Author fixed synthetic oracles. Expected comparison outcomes never call the engine."""

import hashlib
from copy import deepcopy
from itertools import combinations
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from evaluation.io import write_json
from evaluation.schema import BANKS


def uid(label):
    return str(uuid5(NAMESPACE_URL, "snap18-synthetic:" + label))


def money(amount):
    return dict(
        schema_version=1,
        kind="money",
        amount=str(amount),
        currency="RUB",
        unit="currency",
        period="month",
    )


def build():
    snapshot = uid("snapshot")
    facts, evidence, questions, comparisons, coverage = [], [], [], [], []
    for bank in BANKS:
        for index in range(11):
            label = f"{bank}:{index}"
            text = f"Synthetic {label}: employer fee 100 RUB monthly; payroll contract required."
            digest = hashlib.sha256(text.encode()).hexdigest()
            evidence.append(
                dict(
                    id=uid("e:" + label),
                    source_version_id=uid("v:" + bank),
                    extraction_run_id=uid("r:" + bank),
                    chunk_id=uid("c:" + label),
                    raw_sha256=digest,
                    extraction_sha256=digest,
                    chunk_sha256=digest,
                    chunk_text=text,
                    quote=text,
                    quote_start=0,
                    quote_end=len(text),
                    locator=dict(kind="html", element_path=f"/html/body/p[{index + 1}]"),
                )
            )
            facts.append(
                dict(
                    id=uid("f:" + label),
                    bank=bank,
                    family=bank + ("-tune" if index == 10 else "-holdout"),
                    split="tune" if index == 10 else "holdout",
                    human_review_id=None,
                    metric="payroll_credit_fee",
                    value=money(100),
                    status="verified",
                    payer="employer",
                    operation="payroll_credit",
                    period="month",
                    scope={"geography": "federal", "segment": "any"},
                    effective_date="2026-01-01",
                    required_conditions=["payroll_contract"],
                    evidence_ids=[evidence[-1]["id"]],
                )
            )
        for index in range(7):
            questions.append(
                dict(
                    id=uid(f"q:{bank}:{index}"),
                    banks=[bank],
                    family=bank + ("-tune" if index == 6 else "-holdout"),
                    split="tune" if index == 6 else "holdout",
                    query=f"Synthetic employer fee question {index} for {bank}",
                    relevant_chunk_ids=[uid(f"c:{bank}:{index}")],
                    allowed_claims=[uid(f"f:{bank}:{index}")],
                    allowed_numbers=["100"],
                    expected_intent="facts",
                )
            )
    scenario = dict(
        payer="employer",
        operation="payroll_credit",
        currency="RUB",
        payroll_total="100000",
        period="month",
        as_of="2026-10-12",
    )

    def record(bank, value, label):
        ref = uid("engine-e:" + label)
        return dict(
            fact_id=uid("engine-f:" + label),
            review_id=uid("engine-review:" + label),
            snapshot_id=snapshot,
            evidence_ids=[ref],
            eligible_for_comparison=True,
            limitations=[],
            candidate=dict(
                id=uid("engine-c:" + label),
                bank_code=bank,
                metric_code="payroll_credit_fee",
                value=value,
                payer="employer",
                operation="payroll_credit",
                period=None,
                conditions=dict(kind="leaf", field="payroll_total", op="gte", value="0")
                if value.get("amount") == "0"
                else None,
                geography=dict(kind="federal", evidence_ids=[ref]),
                employer_segment=dict(mode="any"),
                organization_category=dict(mode="any"),
                payroll_package=dict(mode="any"),
                contract_variant=dict(mode="any"),
                valid_from="2026-01-01",
                effective_date_status="explicit",
                evidence_ids=[ref],
                corpus_kind="synthetic",
            ),
        )

    for left, right in combinations(BANKS, 2):
        pair = left + "/" + right
        for index in range(2):
            questions.append(
                dict(
                    id=uid(f"q:{pair}:{index}"),
                    banks=[left, right],
                    family=pair + "-holdout",
                    split="holdout",
                    query=f"Synthetic comparison question {index} for {pair}",
                    relevant_chunk_ids=[uid(f"c:{left}:{index}"), uid(f"c:{right}:{index}")],
                    allowed_claims=[uid(f"f:{left}:{index}"), uid(f"f:{right}:{index}")],
                    allowed_numbers=["100"],
                    expected_intent="compare",
                )
            )
        for case in ("money", "zero", "unknown", "individual", "conflict"):
            value = money(0 if case == "zero" else 100)
            if case == "individual":
                value = dict(
                    schema_version=1,
                    kind="individual",
                    text_value="Synthetic individually agreed price",
                )
            records = [record(right, money(200), pair + ":right:" + case)]
            if case != "unknown":
                records.insert(0, record(left, value, pair + ":left:" + case))
            if case == "conflict":
                records.insert(1, record(left, money(150), pair + ":conflict"))
            status = case if case in ("unknown", "individual", "conflict") else "verified"
            pair_status = {
                "money": "better",
                "zero": "better",
                "unknown": "insufficient",
                "individual": "insufficient",
                "conflict": "conflict",
            }[case]
            comparisons.append(
                dict(
                    id=uid("comparison:" + pair + ":" + case),
                    banks=[left, right],
                    family=pair + "-holdout",
                    split="holdout",
                    records=records,
                    request=dict(
                        snapshot_id=snapshot,
                        bank_codes=[left, right],
                        metric_codes=["payroll_credit_fee"],
                        scenario=scenario,
                    ),
                    expected=dict(
                        rows=[
                            dict(
                                metric="payroll_credit_fee",
                                cells=[
                                    dict(
                                        bank=left,
                                        status=status,
                                        value=None if case in ("unknown", "conflict") else value,
                                        missing_inputs=[],
                                    ),
                                    dict(
                                        bank=right,
                                        status="verified",
                                        value=money(200),
                                        missing_inputs=[],
                                    ),
                                ],
                                pairs=[
                                    dict(
                                        left=left,
                                        right=right,
                                        status=pair_status,
                                        delta="-100"
                                        if case == "money"
                                        else "-200"
                                        if case == "zero"
                                        else None,
                                    )
                                ],
                            )
                        ]
                    ),
                )
            )
        coverage.append(
            dict(
                banks=[left, right],
                metric="payroll_credit_fee",
                fact_ids=[uid(f"f:{left}:0"), uid(f"f:{right}:0")],
                comparable=True,
                numeric_employer_cost=True,
            )
        )
    gold = dict(
        schema_version=1,
        corpus_kind="synthetic",
        snapshot_id=snapshot,
        corpus_revision=1,
        facts=facts,
        evidence=evidence,
        questions=questions,
        comparisons=comparisons,
        coverage=coverage,
    )
    observations = dict(
        schema_version=1,
        corpus_kind="synthetic",
        snapshot_id=snapshot,
        corpus_revision=1,
        gold_sha256="0" * 64,
        mode="synthetic_engine",
        facts=[
            {
                **{
                    k: f[k]
                    for k in (
                        "id",
                        "value",
                        "status",
                        "payer",
                        "operation",
                        "period",
                        "scope",
                        "effective_date",
                        "evidence_ids",
                    )
                },
                "conditions": f["required_conditions"],
            }
            for f in facts
        ],
        evidence=evidence,
        questions=[
            dict(
                id=q["id"],
                retrieved_chunk_ids=q["relevant_chunk_ids"],
                claims=q["allowed_claims"],
                numbers=q["allowed_numbers"],
                intent=q["expected_intent"],
            )
            for q in questions
        ],
        comparisons=[dict(id=c["id"], result=c["expected"]) for c in comparisons],
    )
    return gold, observations


def main():
    root = Path(__file__).parent / "fixtures"
    gold, observations = build()
    write_json(root / "synthetic-gold.json", gold)
    digest = hashlib.sha256((root / "synthetic-gold.json").read_bytes()).hexdigest()
    (root / "synthetic-gold.sha256").write_text(digest + "\n", encoding="ascii", newline="\n")
    observations["gold_sha256"] = digest
    write_json(root / "synthetic-observations.json", observations)
    faulty = deepcopy(observations)
    faulty["mode"] = "offline_replay"
    faulty["facts"][0]["value"]["amount"] = "101"
    faulty["facts"][1]["value"]["period"] = "year"
    for index in range(3):
        faulty["facts"][index]["conditions"] = []
    faulty["evidence"][0]["locator"]["element_path"] = "/html/body/p[999]"
    for index in range(6):
        faulty["questions"][index]["retrieved_chunk_ids"] = []
    faulty["questions"][0]["numbers"] = ["999"]
    faulty["questions"][0]["claims"] = ["invented-claim"]
    for index in (2, 3, 4):
        faulty["comparisons"][index]["result"]["rows"][0]["cells"][0]["status"] = "verified"
    write_json(root / "synthetic-faulty-observations.json", faulty)


if __name__ == "__main__":
    main()
