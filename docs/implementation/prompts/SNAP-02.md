# SNAP-02 — Добавить schema snapshot и тарифного pipeline

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Добавочная 0004, ORM для extraction/chunks/snapshot/candidates/evidence/reviews/publication/usage без удаления legacy schema.

## Условия начала

Merged зависимости: SNAP-01. Пока зависимость не завершена, допустим только явно
отдельный scaffold/harness; окончательная приёмка ждёт merged implementation.

Прочитай AGENTS.md, docs/architecture/OVERVIEW.md, DOMAIN_CONTRACTS.md,
DATABASE_DESIGN.md, API_CONTRACTS.md, SECURITY.md и docs/product/ACCEPTANCE_CRITERIA.md.
Проверь актуальный код и отчёты зависимостей: DONE в плане без merged результата
не считается условием начала. Исполни только эту задачу до reviewable результата.
Работай offline с synthetic fixtures, если конкретный real/provider run не допущен.
Не создавай фиктивные разрешения, тарифы, reviewer или PASS. Не запускай scheduler,
recurring download, notifications, очереди, микросервисы или автоматический paid fallback.
Сохрани FetchGateway, LocalBlobStore, operator source recovery, E2E и миграции 0001/0002/0003.

## Файлы и ответственность

- `backend/app/corpus/models.py`
- `backend/app/tariffs/models.py`
- `backend/app/llm/models.py`
- `backend/alembic/versions/0004_snapshot_core.py`
- `backend/alembic/env.py`
- `backend/tests/test_snapshot_db.py`
- `backend/tests/test_db_contract.py`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-02.md`.

## Реализация и ограничения

Следуй DATABASE_DESIGN; foreign keys RESTRICT, uniqueness/hash/corpus/state CHECKs, frozen membership DB trigger, append-only payload/review protection. Register metadata imports. Models держи в отдельных модулях, registry не пересоздавай. llm_usage reservations готовит схему, сам provider ещё не реализуй. Решения identity в review оставь operator label + nullable user_id для SNAP-15. Создай factory fixtures отдельной PG DB.

## Тесты и критерии приёмки

На настоящем PG18 upgrade с 0002 и чистой DB, alembic check, повторный upgrade; forbidden frozen membership UPDATE/INSERT/DELETE, duplicate extraction/publication, FK invalid references. Existing 0001/0002 и ingestion tests green; test_db_contract расширяет точный ожидаемый набор.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Единственный владелец 0004/Alembic env. Можно параллельно с parser/normalization/Fake DTO modules после SNAP-01; shared contract не редактировать.

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
