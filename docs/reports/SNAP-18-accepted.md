# SNAP-18 — Post-merge приёмка harness и аудита

Дата: **14.10.2026, Europe/Moscow**. Пользователь поручил проверить merge и,
если проверки успешны, изменить статус в master plan. **SNAP-18 DONE** для
независимого evaluation harness и аудита; это не PASS реальной product acceptance.

## Проверенный merged результат

[PR #33](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/33)
merged в main: `bce9658c05ac12e8bb39b7e01ffd298bf6ef0990`.
Implementation head: `2e884d7473638de43ace071070b6f48a521a497a`.
Дерево merged main совпадает с implementation head: `git diff 2e884d7 bce9658`
пустой. Проверены actual evaluation modules, fixtures, scoped LF attributes,
CLI, CI workflow и [audit](SNAP-18.md)/[evaluation report](SNAP-18-evaluation.md).

Область приёмки соответствует правилу MASTER_PLAN: независимый module harness
можно закончить при data blocker, а real acceptance остаётся BLOCKED/NOT EVALUATED.
Frozen contracts/API/ORM/migrations/settings/frontend не изменены.

## Проверки на merged main

| Проверка | Результат |
|---|---|
| [CI main](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38552955101) | PASS, completed/success, точный merge SHA |
| CI backend | PASS: Ruff/mypy/docs, PostgreSQL Alembic upgrade/check, regression и offline source E2E |
| CI frontend | PASS: lint/typecheck/build |
| `pytest evaluation -q` | PASS: **42 passed, 0 skipped**, 6.64s |
| Positive CLI с pinned gold hash | PASS, exit 0; реально выполняет 30 ComparisonService golden cases |
| Faulty capture CLI | Ожидаемый FAIL, exit 1; known defects снижают соответствующие метрики |
| JSON report repeatability | PASS: оба post-merge reports точно равны committed evidence JSON |
| `ruff check .` | PASS |
| `mypy backend/app` | PASS: 74 source files |
| Docs validator / diff whitespace | PASS при подготовке status commit |

Existing CI пока не запускает `evaluation` test directory: поэтому 42 tests и оба
CLI воспроизведены отдельно локально на merged main. Подключение evaluation/browser
harness к release CI остаётся follow-up SNAP-19. Полный локальный backend/PG suite
не повторялся: runtime tree неизменён, полный suite на merge SHA прошёл в CI.
Исторические overlapping test totals из implementation report не суммируются.
Real originals/provider runs/working DB mutations в этой приёмке **NOT RUN**.

## Сохранённые ограничения

Исследовательский аудит обнаружил шесть originals, парсинг 6/6 successful локально:
2654 parser blocks, 202 extraction suggestions, 191 diagnostic chunk quotes.
Это не DB chunks/published facts: нормализованных кандидатов/публикаций 0;
контекст payer/operation/applicability не угадывался. Safe summary не содержит
original text/quotes/private paths, full outputs остаются вне Git.

Рабочая DB из existing env в audit — revision 0002, 0 sources/versions/policies;
pipeline tables и configured storage отсутствуют. Нужны настоящие application
acquisition/storage/reuse approvals, content acceptance, review/publication/freeze,
документы недостающих банков и независимый human-reviewed gold. Provider admission
и >=20 real-model questions не выполнены; env token caps требуют отдельного owner
follow-up. Локальная diagnostic authorization не превращается в application grant.

**S0 NOT EVALUATED целиком; S1 BLOCKED; S2/S3 NOT EVALUATED;
исторические G1/G2 NOT PASSED.** Synthetic метрики и статус DONE не изменяют gates.

TASKS.json/MASTER_PLAN обновляются одним integrator commit: **18 DONE**, SNAP-19
остаётся TODO. Dependency order, task IDs и contracts сохранены. Исходный checkout
с чужими unfinished MASTER_PLAN/TASKS/next-env изменениями не затронут.
