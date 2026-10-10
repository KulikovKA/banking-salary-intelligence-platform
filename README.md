# Banking Salary Intelligence Platform

Первая версия — AI-ассистент для доказательного сравнения зарплатных проектов Сбера,
ВТБ, Альфа-Банка и Кубань Кредит на фиксированном наборе официальных документов.
FastAPI + PostgreSQL + Next.js; основная LLM — `openai/gpt-oss-120b` через GroqCloud Free,
Fake LLM — для тестов. Scheduler, регулярное скачивание, мониторинг и уведомления
вне активного scope.

Уже реализованы каталог, миграции `0001`/`0002`, policy-gated FetchGateway,
LocalBlobStore, операторский fetch/import и synthetic E2E. API пока содержит `/health`,
frontend — стартовую страницу. Парсинг содержания, тарифы, сравнение, поиск, LLM и auth
предстоит реализовать. Реальный корпус четырёх банков ещё не принят;
исторические G1/G2 не пройдены. Synthetic E2E не доказывает готовность продукта.

- [Карта документации](docs/README.md)
- [План и готовые промпты Codex](docs/implementation/MASTER_PLAN.md)
- [Snapshot-приёмка](docs/product/ACCEPTANCE_CRITERIA.md)
- [Инструкции Codex](AGENTS.md)
- [Получение и разрешённый импорт](docs/implementation/SOURCE_RECOVERY_USAGE.md)
- [Последний source E2E и блокеры](docs/reports/SOURCE-RECOVERY-E2E-2026-10-10.md)

## Локальный запуск

Python 3.11 (поддерживаемый диапазон указан в pyproject.toml), Node 24/npm 11.
Версии зависимостей зафиксированы в `uv.lock` и `frontend/package-lock.json`.
Если uv отсутствует в PATH, используйте `.\.tools\uv\bin\uv.exe`.

```powershell
uv sync --locked
npm --prefix frontend ci
docker compose --profile local up -d db
$env:DATABASE_URL = 'postgresql+psycopg://bsi:bsi_local_only@127.0.0.1:5432/bsi'
uv run alembic -c backend/alembic.ini upgrade head
uv run uvicorn app.main:app --app-dir backend --reload
# В другом терминале:
npm --prefix frontend run dev
```

API: <http://127.0.0.1:8000/health>, OpenAPI: <http://127.0.0.1:8000/docs>,
frontend: <http://localhost:3000>. `.env.example` — шаблон; приложение читает env
процесса и не загружает `.env` автоматически. Секреты не коммитить.
По умолчанию ingestion offline, LLM fake; provider adapter ещё не реализован.

## Проверки

```powershell
uv run ruff check .
uv run mypy backend/app
uv run pytest backend/tests tools/test_bank_tls_probe.py
python tools/validate_docs.py
npm --prefix frontend run lint
npm --prefix frontend run typecheck
$env:NEXT_TELEMETRY_DISABLED = '1'
npm --prefix frontend run build
```

PostgreSQL integration включается через `TEST_DATABASE_URL` на отдельной test DB
с применёнными миграциями; без неё 9 текущих integration tests пропускаются.
Для alembic также задайте `DATABASE_URL`. Synthetic E2E требует `APP_ENV=test`,
`INGESTION_MODE=offline`, `PYTHONPATH=backend` и DB `bsi_test` либо `bsi_e2e`:
`python tools/source_recovery_e2e.py --output-root .local/source-e2e`.
Проверки не требуют запросов к банкам или Groq.

[Лицензионный inventory](docs/reports/license-inventory.md) сохранён вместе с
историческими [отчётами](docs/reports/) и [архивом проектирования](docs/archive/README.md).
