# SNAP-10 — PostgreSQL Full Text Search

## Итог

Реализован поиск по exact frozen snapshot через PostgreSQL FTS: русская
морфология и `simple` fallback используют существующий `tsvector` и GIN. Результат
всегда ограничен выбранным snapshot, актуально разрешёнными members, принятыми
source versions и успешными extraction runs. Фильтры bank/metric, rank и
детерминированный tie-break возвращают не более 10 полных chunks. Большие chunks
не обрезаются: сервис сообщает `result_exceeds_output_bound`, чтобы не скрыть
условия тарифа. Пустой поиск сообщает `absence_of_evidence`.

Цитаты к тарифным сведениям берутся только из evidence refs проверенных
`EvidenceService.read_published()` фактов; обычные найденные chunks могут иметь
пустой список evidence. Exact `snapshot_id`, `source_version_id`, `raw_sha256`,
locator и score входят в каждый `SearchHit`. Query и фильтры передаются как
SQL-параметры; input ограничен контрактом в 1000 символов, output — 10 hits по
10 000 символов каждый.

## Файлы и база

- `backend/app/search/service.py` — `SnapshotSearchService.search()` для frozen
  read Protocol и `search_with_status()` для явного статуса отсутствия/лимита.
- `backend/tests/test_snapshot_search.py` — PostgreSQL integration tests и
  воспроизводимый fixed synthetic Recall@10 harness.
- `docs/reports/SNAP-10.md` — результаты критериев и проверки.

Base commit: `790347c` (`origin/dev`, merge SNAP-09 PR #18).
Implementation commit: `f5f54910d5f8766c3f7f5c46cbaab3d1aab354dd`.
Реализация использует только существующий FTS/GIN и модели; схемы, контракты,
migrations, shared config и TASKS/MASTER_PLAN не изменялись.

## Acceptance criteria

| Критерий | Результат | Evidence |
|---|---|---|
| Русская морфология | PASS | `test_russian_morphology_and_search_vector_gin` на PostgreSQL |
| Коды, числа, специальные обозначения | PASS | `test_simple_fallback_matches_codes_numbers_and_symbols` |
| Фильтры bank и metric | PASS | `test_bank_and_metric_filters_are_applied` |
| Relevance, максимум 10 и детерминированный tie-break | PASS | `test_top_ten_ranking_and_deterministic_tie_break` повторяет запрос и проверяет порядок/число |
| Zero results → `absence_of_evidence` | PASS | `test_zero_results_has_explicit_absence_of_evidence` |
| Cross-snapshot isolation | PASS | Документ другой revision не возвращается в выбранном snapshot |
| Отзыв permission | PASS | `test_revoked_permission_blocks_search` |
| Rejected/quarantine и synthetic-to-real contamination | PASS | Соответствующие PostgreSQL tests блокируют чтение |
| Unpublished candidate не становится фактом | PASS | `test_unpublished_candidate_never_becomes_search_evidence` возвращает общий chunk без evidence ID |
| Exact source version, hash, evidence и locator | PASS | `test_hit_has_exact_version_hash_evidence_and_locator` |
| Injection и input/output bounds | PASS | Parameterized injection, 1001-char rejection и oversized chunk status проверены |
| Recall@10 harness | PASS — synthetic only | Fixed fixture: 2 query, 2/2 relevant chunks retrieved, Recall@10 = 1.0; real corpus score не выводится |
| Реальная corpus evaluation | NOT RUN | Официальный корпус четырёх банков не принят; synthetic fixture не заменяет оценку данных |

S1 остаётся BLOCKED; S2/S3 и G1/G2 не изменяются. Статус модуля не выставляется
в TASKS.json или MASTER_PLAN.md: это сделает integrator после независимого review.

## Проверки

- `uv run ruff check .` — PASS.
- `uv run mypy backend/app` — PASS, 62 source files.
- Alembic `upgrade head` на dedicated PostgreSQL database — PASS; `alembic check`
  — PASS (`No new upgrade operations detected`).
- `uv run pytest backend/tests/test_snapshot_search.py -q` — PASS, 15 tests.
- `uv run pytest backend/tests tools/test_bank_tls_probe.py -q --tb=short` — PASS,
  356 passed in 220.00s.
- `python tools/validate_docs.py` — PASS.
- Bank/Groq network — 0; fixtures synthetic and isolated in a dedicated test DB.

## Ограничения и передача

Manifest передаётся сервису через injected `manifest_provider`; SNAP-16 должен
подключить операторский manifest для явно выбранного snapshot. Для обычного поиска
пустой `SearchHit` tuple остаётся контрактом SNAP-01; слой, которому нужен typed
status, вызывает `search_with_status()`. Никакое тарифное утверждение нельзя
строить по общему document hit без связанного опубликованного факта.

Независимый review обязателен до принятия SNAP-10. Изменения, затрагивающие общие
контракты или ORM, не требовались; миграции и FTS schema остались неизменными.
