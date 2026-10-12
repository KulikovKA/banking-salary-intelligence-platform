# Snapshot evaluation

Corpus: **synthetic**; revision 1; mode `offline_replay`.
Gold SHA-256: `ca3b3693006ceb0cb4c84000fea9d58fe2abfa597c31fb3243321a4e23b152d8`.

| Metric | Numerator | Denominator | Threshold | Result |
|---|---:|---:|---|---|
| evidence_linkage | 39 | 40 | 100/100 | FAIL |
| value_unit_basis_period | 38 | 40 | 98/100 | FAIL |
| conditions_recall | 37 | 40 | 95/100 | FAIL |
| retrieval_recall_at_10 | 42 | 48 | 90/100 | FAIL |
| deterministic_comparisons | 27 | 30 | 100/100 | FAIL |
| intent_accuracy | 36 | 36 | 90/100 | PASS |
| unsupported_claims | 2 | 36 | 0 | FAIL |

## per_bank

| Group | Metric | n/d | Result |
|---|---|---|---|
| sber | evidence_linkage | 9/10 | FAIL |
| sber | value_unit_basis_period | 8/10 | FAIL |
| sber | conditions_recall | 7/10 | FAIL |
| sber | retrieval_recall_at_10 | 0/6 | FAIL |
| sber | deterministic_comparisons | 0/0 | NOT EVALUATED |
| sber | intent_accuracy | 6/6 | PASS |
| sber | unsupported_claims | 2/6 | FAIL |
| vtb | evidence_linkage | 10/10 | PASS |
| vtb | value_unit_basis_period | 10/10 | PASS |
| vtb | conditions_recall | 10/10 | PASS |
| vtb | retrieval_recall_at_10 | 6/6 | PASS |
| vtb | deterministic_comparisons | 0/0 | NOT EVALUATED |
| vtb | intent_accuracy | 6/6 | PASS |
| vtb | unsupported_claims | 0/6 | PASS |
| alfa | evidence_linkage | 10/10 | PASS |
| alfa | value_unit_basis_period | 10/10 | PASS |
| alfa | conditions_recall | 10/10 | PASS |
| alfa | retrieval_recall_at_10 | 6/6 | PASS |
| alfa | deterministic_comparisons | 0/0 | NOT EVALUATED |
| alfa | intent_accuracy | 6/6 | PASS |
| alfa | unsupported_claims | 0/6 | PASS |
| kuban_credit | evidence_linkage | 10/10 | PASS |
| kuban_credit | value_unit_basis_period | 10/10 | PASS |
| kuban_credit | conditions_recall | 10/10 | PASS |
| kuban_credit | retrieval_recall_at_10 | 6/6 | PASS |
| kuban_credit | deterministic_comparisons | 0/0 | NOT EVALUATED |
| kuban_credit | intent_accuracy | 6/6 | PASS |
| kuban_credit | unsupported_claims | 0/6 | PASS |

## per_pair

| Group | Metric | n/d | Result |
|---|---|---|---|
| sber/vtb | evidence_linkage | 0/0 | NOT EVALUATED |
| sber/vtb | value_unit_basis_period | 0/0 | NOT EVALUATED |
| sber/vtb | conditions_recall | 0/0 | NOT EVALUATED |
| sber/vtb | retrieval_recall_at_10 | 4/4 | PASS |
| sber/vtb | deterministic_comparisons | 2/5 | FAIL |
| sber/vtb | intent_accuracy | 2/2 | PASS |
| sber/vtb | unsupported_claims | 0/2 | PASS |
| sber/alfa | evidence_linkage | 0/0 | NOT EVALUATED |
| sber/alfa | value_unit_basis_period | 0/0 | NOT EVALUATED |
| sber/alfa | conditions_recall | 0/0 | NOT EVALUATED |
| sber/alfa | retrieval_recall_at_10 | 4/4 | PASS |
| sber/alfa | deterministic_comparisons | 5/5 | PASS |
| sber/alfa | intent_accuracy | 2/2 | PASS |
| sber/alfa | unsupported_claims | 0/2 | PASS |
| sber/kuban_credit | evidence_linkage | 0/0 | NOT EVALUATED |
| sber/kuban_credit | value_unit_basis_period | 0/0 | NOT EVALUATED |
| sber/kuban_credit | conditions_recall | 0/0 | NOT EVALUATED |
| sber/kuban_credit | retrieval_recall_at_10 | 4/4 | PASS |
| sber/kuban_credit | deterministic_comparisons | 5/5 | PASS |
| sber/kuban_credit | intent_accuracy | 2/2 | PASS |
| sber/kuban_credit | unsupported_claims | 0/2 | PASS |
| vtb/alfa | evidence_linkage | 0/0 | NOT EVALUATED |
| vtb/alfa | value_unit_basis_period | 0/0 | NOT EVALUATED |
| vtb/alfa | conditions_recall | 0/0 | NOT EVALUATED |
| vtb/alfa | retrieval_recall_at_10 | 4/4 | PASS |
| vtb/alfa | deterministic_comparisons | 5/5 | PASS |
| vtb/alfa | intent_accuracy | 2/2 | PASS |
| vtb/alfa | unsupported_claims | 0/2 | PASS |
| vtb/kuban_credit | evidence_linkage | 0/0 | NOT EVALUATED |
| vtb/kuban_credit | value_unit_basis_period | 0/0 | NOT EVALUATED |
| vtb/kuban_credit | conditions_recall | 0/0 | NOT EVALUATED |
| vtb/kuban_credit | retrieval_recall_at_10 | 4/4 | PASS |
| vtb/kuban_credit | deterministic_comparisons | 5/5 | PASS |
| vtb/kuban_credit | intent_accuracy | 2/2 | PASS |
| vtb/kuban_credit | unsupported_claims | 0/2 | PASS |
| alfa/kuban_credit | evidence_linkage | 0/0 | NOT EVALUATED |
| alfa/kuban_credit | value_unit_basis_period | 0/0 | NOT EVALUATED |
| alfa/kuban_credit | conditions_recall | 0/0 | NOT EVALUATED |
| alfa/kuban_credit | retrieval_recall_at_10 | 4/4 | PASS |
| alfa/kuban_credit | deterministic_comparisons | 5/5 | PASS |
| alfa/kuban_credit | intent_accuracy | 2/2 | PASS |
| alfa/kuban_credit | unsupported_claims | 0/2 | PASS |

## Pair coverage

| Pair | Criteria | Numeric employer cost | Result |
|---|---:|---:|---|
| sber/vtb | 1 | 1 | BLOCKED |
| sber/alfa | 1 | 1 | BLOCKED |
| sber/kuban_credit | 1 | 1 | BLOCKED |
| vtb/alfa | 1 | 1 | BLOCKED |
| vtb/kuban_credit | 1 | 1 | BLOCKED |
| alfa/kuban_credit | 1 | 1 | BLOCKED |

## Product gates

- S0: NOT EVALUATED
- S1: BLOCKED
- S2: NOT EVALUATED
- S3: NOT EVALUATED

## Minimum sample requirements

| Requirement | Actual | Minimum | Result |
|---|---:|---:|---|
| reviewed_facts | 0 | 40 | BLOCKED |
| bank_facts | 11 | 10 | PASS |
| reviewed_facts_per_bank | 0 | 10 | BLOCKED |
| bank_questions | 7 | 6 | PASS |
| pair_questions | 2 | 2 | PASS |
| holdout_comparisons | 30 | 30 | PASS |
| family_split | 2 | 2 | PASS |

## Blocked / skipped

- S1 requires independent source approvals, accepted originals and frozen review
- S2 requires admitted real corpus and independent human-reviewed gold
- S3 requires explicit provider run authorization/admission and >=20 real questions
- Full product acceptance is outside metric replay
- Tune cases excluded from holdout metrics

Missing observations: 0.

Metrics score captured structured observations; they do not issue admissions.
