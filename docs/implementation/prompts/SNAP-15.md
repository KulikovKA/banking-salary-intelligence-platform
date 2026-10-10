# SNAP-15 — Приглашения, auth и server sessions

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Admin bootstrap/invite login, Argon2id passwords, DB sessions, RBAC/CSRF dependencies.

## Условия начала

Merged зависимости: SNAP-02. Пока зависимость не завершена, допустим только явно
отдельный scaffold/harness; окончательная приёмка ждёт merged implementation.

Прочитай AGENTS.md, docs/architecture/OVERVIEW.md, DOMAIN_CONTRACTS.md,
DATABASE_DESIGN.md, API_CONTRACTS.md, SECURITY.md и docs/product/ACCEPTANCE_CRITERIA.md.
Проверь актуальный код и отчёты зависимостей: DONE в плане без merged результата
не считается условием начала. Исполни только эту задачу до reviewable результата.
Работай offline с synthetic fixtures, если конкретный real/provider run не допущен.
Не создавай фиктивные разрешения, тарифы, reviewer или PASS. Не запускай scheduler,
recurring download, notifications, очереди, микросервисы или автоматический paid fallback.
Сохрани FetchGateway, LocalBlobStore, source recovery, E2E и миграции 0001/0002.

## Файлы и ответственность

- `backend/app/auth/**`
- `backend/alembic/versions/0004_auth.py`
- `backend/alembic/env.py`
- `backend/tests/test_auth_sessions.py`
- `pyproject.toml`
- `uv.lock`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-15.md`.

## Реализация и ограничения

Следуй SECURITY, official password hashing docs проверить при реализации. Add argon2-cffi после parser dependency merges. Dedicated auth 0004 после 0003, integrate metadata sequentially. Один use invite/reset при row lock, rotation/expiry/revoke, last-admin guard, login rate limits, no email infrastructure. Expose FastAPI dependency/router factory для SNAP-16, не менять main.py. Production Settings сохраняй, auth local HTTP cookie и test identity контролируемо; config changes согласовать с SNAP-13 после его merge. Не сохранять chat data.

## Тесты и критерии приёмки

Actual PG invite race, hash-only tokens, password check/rotation/logout/idle+absolute expiry; admin vs analyst, session A/B, CSRF/Origin/session fixation, brute-force generic responses, last admin guard. Migration check и existing production config tests. Нет default production password.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Основной auth код параллельно pipeline/search/comparison/LLM; migration env/lockfiles edits после SNAP-02/04/05 merge, config.py не трогать до SNAP-13. Один владелец auth revision.

Используй отдельную ветку/worktree при реальном параллельном запуске. Не spawn
других агентов без отдельного поручения. Общие lockfiles/миграции/main.py интегрируй
последовательно. Не коммить другой worktree или чужие незавершённые изменения.

## Завершение и передача

Сохрани report: итоговое поведение, изменённые файлы, проверки с числами и
PASS/FAIL/NOT RUN, evidence для каждого AC, ограничения, следующий шаг.
В report укажи base commit; commit результата добавить после commit если доступен.
Не обновляй MASTER_PLAN/TASKS.json параллельно: передай интегратору итоговый статус.
Интегратор обновляет только status задачи (DONE при всех её AC, иначе IN_PROGRESS
или BLOCKED с причиной), сохраняет порядок/зависимости и запускает docs validator.
Если задача уже выполнена, проверь AC и закрой только оставшиеся пробелы, без
переписывания работающего кода. Product gates считаются отдельно от DONE модуля.
