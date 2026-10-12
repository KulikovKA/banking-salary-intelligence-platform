# SNAP-18 — Измеренная оценка

Дата: 13.10.2026, Europe/Moscow. Base `688877d`.
Это оценка независимого harness и synthetic backend regression. Real S1 BLOCKED,
S2/S3 NOT EVALUATED; полный S0 отдельно от компонента evaluator.

## Зафиксированные artifacts

- [Gold + exact byte hash](../../evaluation/fixtures/synthetic-gold.sha256)
- [Synthetic gold](../../evaluation/fixtures/synthetic-gold.json)
- [Positive captured observations](../../evaluation/fixtures/synthetic-observations.json)
- [Faulty captured observations](../../evaluation/fixtures/synthetic-faulty-observations.json)
- [Positive measured JSON](evidence/snapshot-evaluation/synthetic.json),
  [Markdown](evidence/snapshot-evaluation/synthetic.md)
- [Faulty measured JSON](evidence/snapshot-evaluation/synthetic-faulty.json),
  [Markdown](evidence/snapshot-evaluation/synthetic-faulty.md)
- [Private audit safe summary](evidence/snapshot-evaluation/local-audit-summary.json)

Gold/schema/capture hashes записаны в JSON. Comparison output имеет собственный
effective capture hash; исходный input capture hash сохранён отдельно. Два запуска
с тем же gold hash воспроизводят одинаковые результаты; clock/output IDs не
влияют на финансовую проекцию. Gold не переименован в real, human reviews — 0.

## Holdout metrics

Thresholds взяты из ACCEPTANCE_CRITERIA до измерения, сравниваются integer ratios.
Intent — отдельная проверка synthetic capture, не successful Groq metric.

| Метрика | Positive synthetic | Faulty synthetic | Threshold |
|---|---|---|---|
| Original/evidence reference linkage | 40/40 PASS | 39/40 FAIL | 100% |
| Value/unit/basis/period (+payer/scope/date) | 40/40 PASS | 38/40 FAIL | >=98% |
| Required conditions recall | 40/40 PASS | 37/40 FAIL | >=95% |
| Retrieval Recall@10 | 48/48 PASS | 42/48 FAIL | >=90% |
| Deterministic comparisons | 30/30 PASS | 27/30 FAIL | 100% |
| Intent/clarification correctness | 36/36 PASS | 36/36 PASS | >=90% |
| Unsupported structured claims/numbers | 0/36 PASS | 2/36 FAIL | 0 |

Evidence metric checks expected chain identity/hash, exact chunk substring/hash and
locator against frozen gold. It does not authenticate real originals from arbitrary
JSON. Replay retrieval/intent/extraction observations are authored fixtures; only
`compare` executes the actual engine for those 30 financial results. Independent
original review and admitted runtime capture are prerequisites for real scores.
Free-prose unsupported assertions require independent capture annotation; this
harness checks structured claim IDs/numeric tokens, not semantic model judging.

В каждом банке holdout 10 facts и 6 questions; в каждой паре 2 questions (4 relevant
chunks) и 5 comparison cases. Точные breakdown доступны в JSON/Markdown выше.
На каждой паре synthetic coverage — **1 comparable / 1 numeric criterion**;
минимум 2 total не достигнут: **BLOCKED все 6 пар**. Real numeric coverage —
**NOT EVALUATED**, а не синтетическая таблица PASS.

Tune: 4 дополнительных facts и 4 questions из других families. Они не входят
в quality denominators. Недостающие observed cases дают FAIL; пустые метрики —
NOT EVALUATED. Minimum human reviewed facts/per-bank floors показывают BLOCKED.

## Проверки

| Check | Результат |
|---|---|
| Locked uv install | PASS; pyproject/uv.lock без diff |
| Evaluation adversarial/unit tests | PASS: 37 passed, 0 skipped, 0 failed |
| Synthetic actual ComparisonService | PASS: 30 independent golden cases |
| Positive CLI | PASS, exit 0 |
| Faulty CLI | Expected FAIL, exit 1, шесть quality metrics FAIL |
| Ruff | PASS |
| mypy backend/app | PASS: 74 files |
| Dedicated PostgreSQL Alembic upgrade/check | PASS: head 0005_auth, no drift |
| Backend + TLS-tool regression | PASS: 564 passed, 1 skipped, 0 failed; 505.82s |
| Docs validator / whitespace | PASS |
| Gold portability / Git blob hash | PASS: byte-pinned LF preserved across Windows/Linux |
| Frontend lint/typecheck/build/browser E2E | NOT RUN: frontend/API/contracts не менялись |
| Real parser/real tariff/real gold | NOT RUN: 0 sources/versions, нет допущенных originals |
| Live Groq / >=20 real-model evaluation | NOT RUN: admission/run authorization нет, env caps invalid |
| Remote PR CI | NOT RUN локально / status не проверялся; local validation выше |
| Load/recovery/full S0/S3 | NOT RUN: отдельная SNAP-19 приёмка |

Test DB создана отдельно с именем `bsi_snap18_test_*`; runtime database, policies,
originals и provider admissions не изменялись. Backend test env задаётся только
в дочернем процессе из existing `.env` DB credentials и нового test DB имени;
ключи/credentials не выводились и не копировались в новый env. Existing SQLite
unit transaction helper сохранён; все PG integrations выполняются на PostgreSQL.
Единственный skip — Linux-specific `/proc` process state на Windows; ни одна
PostgreSQL/search/API integration не пропущена. Harness и backend totals —
отдельные suites, повторные промежуточные проверки не суммируются.

`evaluation` tests не входят в нынешний default `pytest` testpaths/CI. Команда
`uv run pytest evaluation -q` обязательна для review; SNAP-19 CI owner должен
последовательно подключить её к release workflow. Workflow/lockfile здесь не менялись.

Development checks: сначала schema fixture zero fee требовал обязательного condition;
исправлен synthetic scenario fixture с явным payroll_total>=0. Полная value projection
включает frozen DTO schema_version. Ruff formatting исправлен до финальных проверок.
Ранний docs validator обнаружил ещё не созданный evaluation report; final check
выполняется после появления всех artifacts. Эти промежуточные результаты не
суммируются с окончательными test totals и не скрываются как PASS.
Перед окончательным frozen run JSON authoring переведён на LF и добавлен scoped
evaluation/.gitattributes: core.autocrlf не должен менять exact gold hash между
Windows и Linux. Gold/captures/evidence regenerated до финальных runs; содержание
oracles и product thresholds не изменялось.

## Приёмка

Harness **READY FOR REVIEW**, product **BLOCKED**.
S0 NOT EVALUATED целиком; S1 BLOCKED; S2/S3 NOT EVALUATED. Полный порядок
следующих действий, evidence blockers и команды просмотра —
[SNAP-18 audit report](SNAP-18.md). Task statuses/merge остаются за интегратором.
