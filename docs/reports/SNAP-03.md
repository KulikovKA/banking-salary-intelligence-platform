# SNAP-03 — операторский manifest и freeze service

**Результат:** реализованы manifest validation, точный выбор accepted source version, draft membership, идемпотентный freeze и read gate для frozen snapshot. Это техническая приёмка harness, не приёмка real corpus и не S1 PASS.

**База:** `504c71fb2c9dd914231f92c06d98b623b2b41aca` (`main`). **Ветка:** `codex/snap-03-corpus`; отдельный worktree `C:\Users\Kirill\Desktop\sber-ai-snap-03`.

## Изменения

- `backend/app/corpus/service.py` проверяет фиксированный набор банков, непустой и однозначный состав, реестр отсутствующих документов, точные source/version/acquisition/policy/extraction IDs, acquisition method/URLs/time, accepted scope/date metadata, hash БД и SHA-256 оригинала в существующем `LocalBlobStore`.
- Admission проверяет текущую `SourcePolicy`, точный `AcquisitionPolicy` method/source/corpus/host allowlist, `SourceFetch` provenance и успешный extraction. Quarantine, fictitious version, missing/corrupt original, неправильный hash, истёкшее или revoked permission блокируются. Real snapshot нельзя заморозить с отсутствующим хотя бы одним банком; partial synthetic snapshots изолированы для harness.
- `add_version` создаёт draft и добавляет только выбранную версию; повторное добавление идемпотентно. `freeze` сверяет весь состав с manifest, считает стабильный SHA-256 канонического JSON, фиксирует membership один раз и принимает точный повторный freeze без дубликатов. Frozen read требует точного snapshot membership, текущего разрешения и повторной проверки stored bytes.
- `backend/app/corpus/cli.py`: `validate --manifest` — dry-run, `add-version --manifest --document-index`, `freeze --manifest`. Команды используют существующий `IngestionService`/`LocalBlobStore`; gateway создаётся в offline режиме и не вызывается.
- `manifests/snapshot.schema.json` задаёт строгую структуру; `manifests/snapshot.example.json` — отдельный synthetic пример с фиктивными IDs и missing registry для остальных банков.
- `backend/tests/test_snapshot_corpus.py` проверяет ошибку пустого корпуса, wrong hash, quarantine, отсутствующий original, hash corruption после freeze, fictitious version, exact composition, повторный freeze и отзыв прав по решению и grant.
- Реальный source coverage и blockers: [`SNAP-03-source-status.md`](SNAP-03-source-status.md). Ни один real original не импортирован; `MASTER_PLAN.md` и `TASKS.json` не менялись.

## Проверки

| Проверка | Результат |
|---|---|
| `alembic upgrade head` на отдельной PostgreSQL 18 DB `bsi_snap03_test` | PASS, revision `0004_snapshot_core`; миграции не менялись |
| `alembic check` | PASS, `No new upgrade operations detected` |
| `backend/tests/test_snapshot_corpus.py` на PostgreSQL | PASS, 9 passed |
| `backend/tests` на PostgreSQL | PASS, 197 passed, 0 failed, 0 skipped |
| `uv run ruff check .` | PASS |
| `uv run mypy backend/app` | PASS, 43 source files |
| `python tools/validate_docs.py` | PASS |
| `git diff --check` | PASS перед подготовкой отчёта; итоговый check повторить перед commit |
| Frontend lint/typecheck/build и browser E2E | NOT RUN: SNAP-03 не меняет frontend/UI |
| Новая live acquisition или real S1 | NOT RUN / BLOCKED: отсутствуют проверенные source-specific permissions; см. source status |

## Приёмка и ограничения

Synthetic PostgreSQL harness подтверждает composition/freeze/read invariants и не доказывает качество реальных данных, законность acquisition/reuse или readiness S1. S1 остаётся `BLOCKED`, G1/G2 — `NOT PASSED`. Текущая schema SNAP-02 не хранит полный manifest JSON в PostgreSQL: база фиксирует membership и hash, оператор сохраняет manifest как immutable run artifact.

**Implementation commit:** `194fd03da7465ed16dbe97461c2ac5ba6505179d`. **PR:** будет добавлен после публикации.
