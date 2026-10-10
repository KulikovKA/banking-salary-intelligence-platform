# Отчёт WORK-02 — окружение и базовая БД

**Статус:** IN_PROGRESS. **Дата:** 2026-10-09. **Причина:** INF-001 DONE; INF-002/DB-001 реализованы только в offline scope, но PostgreSQL runtime проверки не проведены из-за выключенного Docker daemon. Formal G0/dependency не переписывали; draft ADR-006 ожидает review Astra и решения владельца.

## Этапы

| Этап | Статус | Evidence / оставшееся |
|---|---|---|
| INF-001 | DONE | `docs/reports/INF-001.md` |
| INF-002 | IN_PROGRESS | Config, Compose, Dockerfile и tests готовы; Compose config/lint/type/unit проходят. PostgreSQL/backend container startup и DB health check требуют работающий Docker daemon. |
| DB-001 | IN_PROGRESS | 7-table metadata, `0001_catalog`, bank-only seed, transaction/job helpers готовы; Alembic head и PostgreSQL static SQL проходят. Runtime PostgreSQL integration ожидает daemon. |

## Проверки этой итерации

- `uv lock --check` — PASS.
- `uv sync --locked` — PASS.
- `uv run --locked pytest` — PASS: 15 tests.
- `uv run --locked ruff check .` — PASS после исправления промежуточной import-sort ошибки.
- `uv run --locked mypy backend/app` — PASS, no issues in 10 source files.
- `uv run --locked alembic -c backend/alembic.ini heads` — PASS, одна head `0001_catalog`.
- `uv run --locked alembic -c backend/alembic.ini upgrade head --sql` — PASS, offline PostgreSQL SQL generation.
- `docker compose --profile local config --quiet` — PASS.
- `npm run lint --prefix frontend` — PASS.
- `npm run typecheck --prefix frontend` — PASS.
- `npm run build --prefix frontend` — PASS, static routes `/` и `/_not-found`.
- `docker info` — FAIL/BLOCKED: Docker engine named pipe отсутствует. Из-за этого не выполнены `docker compose up`, PostgreSQL health, live Alembic upgrade и PG constraint tests.

## Граница разрешения

Использовались только локальные схемы и synthetic unit data. Новые PDF Кубань Кредит не загружались; ВТБ/Альфа live network не проверялись в рамках разработки. WORK-01/SRC-001 остаётся BLOCKED. ADR-006 предложен отдельно и не считается принятым.

## Следующее действие

Техническое: запустить Docker Desktop/daemon, затем выполнить PostgreSQL integration и обновить DB-001/WORK-02 status по факту. Человеческое: Astra review и решение владельца по G0 split; это не требуется для дальнейшей офлайн-реализации, но требуется до изменения formal dependency/gate policy.
