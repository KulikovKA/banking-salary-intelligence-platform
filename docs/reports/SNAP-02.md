# SNAP-02 — PostgreSQL snapshot schema

**Результат:** schema, ORM и интеграционная проверка SNAP-02 реализованы. Этот
результат подтверждает технические DB-контракты на synthetic fixtures и не
является приёмкой реального корпуса или PASS для S0–S3/G1–G2.

**База:** `ea6ae1a2f2f174981d8706b88a6192361d56df8b` (`main`, актуальный
`origin/main` на начало задачи). **Ветка:** `codex/snap-02-db`.

## Изменения

- Добавлена аддитивная `0004_snapshot_core.py`: extraction runs, immutable
  chunks, snapshots/membership, tariff candidates, evidence, append-only review
  и publication, а также таблица LLM usage reservations. Legacy-таблицы и
  миграции 0001–0003 не изменялись.
- Добавлены ORM в `corpus/models.py`, `tariffs/models.py`, `llm/models.py`;
  `alembic/env.py` регистрирует новую metadata рядом с существующим registry.
- DB constraints и триггеры ограничивают hash/state/corpus, происхождение
  extraction/evidence, exact quote offsets, frozen membership и допустимую
  публикацию. Candidate payload, extraction/chunk/evidence, review и published
  row нельзя изменить или удалить. Membership trigger берёт блокировку строки
  snapshot, чтобы сериализовать изменение состава с freeze.
- Тариф хранится как canonical JSONB payload и `payload_sha256`, с typed
  bank/metric/extraction/corpus колонками. Для Decimal значения передаются
  строками; SQL не приводит суммы к float.
- Usage хранит резерв, фактические prompt/completion/total tokens, estimated,
  состояние, model и nullable `user_id`. Provider и reservation service не
  добавлялись. Review сохраняет operator label и nullable `user_id` без
  выдуманной identity.
- `test_db_contract.py` расширяет точный набор ORM таблиц; новые DB tests
  используют выделенную PostgreSQL test DB и откатывают synthetic fixture rows.

## Проверки

| Проверка | Результат / evidence |
|---|---|
| Чистый PostgreSQL 18.6: `alembic upgrade head` | PASS, `bsi_snap02_clean`, revision `0004_snapshot_core` |
| Совместимость с legacy 0002 | PASS: `bsi_snap02_legacy` поднята до `0002_source_recovery`, затем до head |
| Повторный `alembic upgrade head` | PASS, без повторного DDL |
| `alembic check` на чистой и legacy DB | PASS: `No new upgrade operations detected` на обеих |
| `test_snapshot_db.py` на PostgreSQL 18 | PASS, 6 тестов: provenance/review/publication/usage; запреты frozen INSERT/UPDATE/DELETE; duplicate extraction/publication; invalid FK/quote; unsettled usage |
| `test_ingestion_postgres.py` | PASS, 9 тестов на той же выделенной PG DB |
| `uv run pytest backend/tests tools/test_bank_tls_probe.py` | PASS, 126 passed, 0 failed, 0 skipped |
| `uv run ruff check .` | PASS |
| `uv run mypy backend/app` | PASS, 35 source files |
| `python tools/validate_docs.py` | PASS |
| `git diff --check` | PASS |
| Frontend lint/typecheck/build | NOT RUN: frontend SNAP-02 не меняет |
| Synthetic E2E | NOT RUN: задача меняет только persistence schema; существующий ingestion PostgreSQL набор выполнен |

## Границы и передача

Все DB fixtures синтетические; реальные source bytes, grants, тарифы и reviewer
не создавались. G1/G2 не менялись; этот отчёт не заявляет прохождение S0–S3.
Downgrade 0004 намеренно запрещён с сообщением
`SNAPSHOT_EVIDENCE_DOWNGRADE_REQUIRES_REVIEW`, чтобы не удалять audit/evidence.

Следующий потребительский шаг — SNAP-03/SNAP-09 использовать готовую schema и
сервисные проверки; status в `MASTER_PLAN.md` и `TASKS.json` оставлен integrator.

Commit и PR будут добавлены после их создания.
