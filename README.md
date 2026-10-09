# Banking Salary Intelligence Platform

Стартовый каркас модульного монолита для анализа публичных зарплатных предложений банков. Здесь пока есть только проверка доступности API и стартовая страница; тарифная логика и сбор банковских данных не реализованы.

## Требования

- Python 3.11 (проверялось на 3.11.9)
- [uv](https://docs.astral.sh/uv/) 0.12.24
- Node.js 24 LTS и npm 11

Версии runtime и приложений ограничены в `pyproject.toml` и `frontend/package.json`; точные версии Python/JavaScript зависимостей зафиксированы в `uv.lock` и `frontend/package-lock.json`.

## Установка

```powershell
uv sync --locked
npm --prefix frontend ci
```

## Разработка

Запустить API и интерфейс в отдельных терминалах:

```powershell
uv run uvicorn app.main:app --app-dir backend --reload
npm --prefix frontend run dev
```

- API: <http://127.0.0.1:8000/health>
- OpenAPI: <http://127.0.0.1:8000/docs>
- Frontend: <http://localhost:3000>

## Проверки

```powershell
uv run ruff check .
uv run mypy backend/app
uv run pytest
npm --prefix frontend run lint
npm --prefix frontend run typecheck
$env:NEXT_TELEMETRY_DISABLED = "1"
npm --prefix frontend run build
```

Команды не требуют внешнего API, банковских credentials или базы данных. PostgreSQL integration suite появится вместе с DB-001; SQLite не используется как его замена.

## Секреты

Скопируйте `.env.example` в `.env` только для локальной конфигурации, не добавляйте `.env` в Git. Сейчас backend не читает секреты и не подключается к внешним системам.

Лицензионные сведения прямых и транзитивных зависимостей: [inventory по lockfiles](docs/reports/license-inventory.md).
