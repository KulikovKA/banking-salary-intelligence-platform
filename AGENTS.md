# Codex: Banking Salary Intelligence Platform

## Источники истины

Прочитай README.md, docs/implementation/MASTER_PLAN.md и один SNAP prompt.
Архитектура/контракты/DB/API/security в docs/architecture, release criteria —
docs/product/ACCEPTANCE_CRITERIA.md. Ветка archive — история, не runtime dependency main.
Фактическая реализация определяется кодом и миграциями; планируемые модули
не считать выполненными. Report предыдущего шага проверяй по merged code/tests.

## Обязательные границы

- FastAPI modular monolith + PostgreSQL + Next.js + local originals.
- Snapshot corpus; без scheduler/recurring fetch/change notifications/outbox,
  очередей, Redis/Celery/vector DB и новых сервисов.
- Сохранять FetchGateway/BlobStore/operator ingestion/tests/E2E/0001/0002/0003; additive migrations.
- Основной provider Groq `openai/gpt-oss-120b`, Fake для CI. Не заменять provider
  и не переходить на paid tier автоматически.
- Offline tests/CI не обращаются к банкам/Groq. Real source bytes только после
  проверяемого acquisition/storage/reuse допуска выбранного метода.
- Manual grants не G0-LIVE; synthetic не real; HTTP200/robots/local file не permission.
- G1/G2 не пройдены, S0–S3 независимы; не подменять blocked/NOT RUN фиктивным PASS.
- Evidence chain original/hash -> extraction/chunk/locator -> candidate -> manual
  review -> publication -> claim обязательна. LLM не вычисляет тариф и не approves.
- Decimal, explicit unknown/individual/conflict/conditions/scope/date. Unknown не 0.
- Секреты/учётные данные/реальные originals/зарплатные персональные сведения вне Git.

## Выполнение и параллелизм

Один prompt = одна задача. Соблюдай owned_paths; контракты freeze после SNAP-01.
Не запускать subagents без явного поручения на делегирование. Параллельные Codex
запуски только в отдельных branches/worktrees с disjoint paths. Общие
lockfiles/Alembic env/config/main/TS DTO интегрирует один владелец по MASTER_PLAN.
Never overwrite соседние изменения. Изменение public contract/schema — конкретный
follow-up владельцу, а не hidden local fork. Report каждой задачи отдельный.
TASKS.json/MASTER_PLAN statuses обновляет integrator после merge одним commit.
DONE только с выполненными AC; blocked data не мешает закончить независимый harness.

## Проверки

`uv run ruff check .`, `uv run mypy backend/app`, relevant pytest. PG integrations
на dedicated test DB после Alembic upgrade/check; не подменять SQLite. Existing
unit transaction helper SQLite test сохраняется. Synthetic E2E offline,
`python tools/validate_docs.py`, frontend lint/typecheck/build и meaningful
browser E2E после UI реализации. Skip/FAIL укажи с причиной и числами.
Не расширять/repeat проверки без новых изменений или unresolved failure.
Commit/push выполняй по поручению пользователя; не включай чужие файлы.
