# Разделение веток — 10.10.2026

`archive` создана на `02cd6c8e00e9f84c0528460c7a42835f95a41499` до удаления файлов;
GitHub remote ref и branch API подтвердили этот SHA. Tree SHA:
`63c8d4bcd0d68107243d10f80f25ba4f3c70cb7c`. Все parent commits сохраняются;
force-push/rebase/reset history не выполнялись.

- [archive: полный предыдущий снимок](https://github.com/KulikovKA/banking-salary-intelligence-platform/tree/archive)
- [main: snapshot v1](https://github.com/KulikovKA/banking-salary-intelligence-platform/tree/main)
- [Пофайловый список удалений](evidence/main-cleanup-deletions.json)

## Удалено из main

Всё `docs/archive/` (212 файлов) и 14 исторических reports/evidence: DB-001,
INF-001/002, WORK-01/02, SRC-001, SOURCE-RECOVERY, source-feasibility,
bank-document-investigation, SOURCE-RECOVERY-E2E, SNAPSHOT-REBASE и три прежних
JSON artifacts (source E2E, rebase E2E, document audit). Они остаются в archive.
Точный перечень/old normalized hashes находится в deletion JSON.
В main сохранены license inventory и текущие source decisions; новая concise
SOURCE_STATUS и исправленные duplicated summaries manifest не выдают grants.

Удалён `backend/app/ingestion/jobs.py` — ни runtime, ни tests его не использовали.
Удалены JobRun ORM, source scheduling columns/due index и SourceFetch.job_run_id
из active ORM. Удалены worker lease/heartbeat/source stale settings, старое имя
MAX_JOB_ATTEMPTS; новая FETCH_MAX_ATTEMPTS относится только к operator attempts.
`current_content()` возвращает accepted version ID/None без 72h stale tuple.
Retry-After, transient errors, source/host locks сохраняются: это необходимые
ограничения безопасного разового fetch, без автоматического retry dispatcher.

Отдельных scheduler/change-tracking/notification runtime modules, микросервисов,
Redis/Celery и связанных dependencies в коде не было. Lockfiles/dependencies не
изменены: все установленные runtime библиотеки используются текущей основой;
cryptography также нужна scoped CA validation, а не мониторингу.

## Сохранность БД

0001/0002 не переписаны. Добавлена `0003_operator_only`: только DB DEFAULT=1
для оставшегося physical sources.schedule_seconds; существующие значения не
изменяются. Старые physical job_runs, scheduler columns, job_run_id и audit data
остаются в БД без runtime mappings. Это сохранность данных по требованию владельца,
а не поддержка прежней архитектуры. Migration autogenerate исключает только
explicit retired objects absent from metadata; unrelated drift видим и протестирован.
Новых source rows не нужно знать о scheduler, поскольку DB подставляет inert value.
Планируемые revisions SNAP-02/15 перенумерованы в 0004_snapshot_core/0005_auth,
все 19 prompts/TASKS.json/MASTER_PLAN согласованы, зависимости/statuses не изменены.

## Самостоятельность main

Нет local archive files/required links/imports. Validator проверяет local links,
19 prompts, registry content/status/DAG и текущий source manifest; не открывает
ветку archive и не читает её inventory. Исторические ссылки — только внешняя
справка. Source manifest хранит decisions/hashes/provenance, не используется как
runtime approved policy. Текущие реальные bank acquisition/storage/reuse grants
не созданы; G1/G2 NOT PASSED, S1 BLOCKED, S2/S3 NOT EVALUATED.

```text
AGENTS.md / README.md / MASTER_PLAN.md / compose.yaml / lockfiles
backend/
  app/{db,registry,ingestion,storage}/ + config.py + main.py
  alembic/versions/0001_catalog.py,0002_source_recovery.py,0003_operator_only.py
  tests/
frontend/                         # независимый Next.js scaffold
docs/
  architecture/ + ADR/007-snapshot-monolith.md
  implementation/{MASTER_PLAN.md,TASKS.json,SOURCE_RECOVERY_USAGE.md,prompts/}
  product/ACCEPTANCE_CRITERIA.md
  research/SOURCE_STATUS.md
  reports/{license-inventory.*,MAIN-CLEANUP-2026-10-10.md,evidence/}
tests/fixtures/manifests/sources.json
tools/{bank_tls_probe.py,inspect_bank_chain.ps1,source_recovery_e2e.py,validate_docs.py}
.github/workflows/ci.yml
```

## Проверки

- Ruff PASS, mypy PASS (23 runtime modules); imports/DAG/local links/19 prompt
  content/registry/source decisions PASS. Исходные 0001/0002 и lockfiles без diff.
- Existing PostgreSQL 18.6 `bsi_e2e`: upgrade 0002->0003 и Alembic check PASS.
  До/после совпали все counts, source schedule values, blob hashes и job rows:
  [preservation result](evidence/operator-migration-preservation.json).
- Fresh dedicated `bsi_test`: полный upgrade 0001->0002->0003 и Alembic check
  PASS. Pytest backend + TLS tool: **105 passed, 0 skipped**. Проверка head
  следует ScriptDirectory вместо устаревшего literal 0002; отдельно проверены
  physical audit data retention/default и видимость unrelated schema drift.
- Synthetic E2E PASS_SYNTHETIC_ONLY: two versions/blobs, seven observations,
  no missing/orphan, bank network requests=0. [result](evidence/main-cleanup-source-e2e.json).
  Тарифное ядро/real corpus/Groq acceptance этим не объявляются готовыми.
- Next.js lint/typecheck/production build PASS; frontend source/lockfiles не менялись.
- Самостоятельный экспорт staged main tree: docs archive/queue helper отсутствуют,
  CLI/imports/docs PASS, реальный uvicorn startup и HTTP /health=`ok`, повторный
  pytest на exported code: **105 passed, 0 skipped**. Дополнительные файлы ветки
  archive не использовались; зависимости — обычный установленный virtualenv.
- Git diff whitespace PASS, включая staged checks. Archive CI на сохранённом
  02cd6c8: [success](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38072530741).
  GitHub Actions main проверяется после push на новом commit SHA; итог и ссылка
  передаются отдельно, без подмены queued статусом PASS.
