# SNAP-16 — FastAPI routers и composition root

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Маршруты API_CONTRACTS, injected services/auth, OpenAPI и стабильный frontend client contract.

## Условия начала

Merged зависимости: SNAP-03, SNAP-09, SNAP-14, SNAP-15. Пока зависимость не завершена, допустим только явно
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

- `backend/app/api/**`
- `backend/app/main.py`
- `backend/tests/test_snapshot_api.py`
- `frontend/lib/api-contracts.ts`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-16.md`.

## Реализация и ограничения

Собери existing FastAPI app без переписывания ingestion. Каждый protected route проверяет session/role; unsafe requests CSRF. Download только член readable snapshot, verify original hash, attachment/nosniff, no arbitrary storage key/path. Admin review/freeze вызывают сервисы, не bypass validation. Bounded sync question/comparison, uniform typed error envelope. Stable generated/manual typed TS DTO без secrets. Передай внешнему frontend стабильный OpenAPI/TS контракт и synthetic request/response примеры auth/CSRF, snapshot/search/comparison/documents/assistant, unknown/conflict/individual/fallback и ошибок 429/503; примеры сохраняй в report SNAP-16 без реальных данных. Визуальную реализацию определяет внешний разработчик. Публичные DTO/API не менять без обоснованного follow-up и согласования владельца. Health semantics остаётся liveness; no ingest upload/scheduler/job poll endpoints.

## Тесты и критерии приёмки

API fixtures real PG + Fake: health, login/logout/invite, protected reads, analyst denial admin mutation, wrong Origin, snapshot freeze conflict, source revoked download, traversal, unknown object, limits 429, insufficient/fallback envelope 200. OpenAPI/TS DTO match; в report зафиксированы revision контракта, правила cookie/Origin/CSRF, typed errors и synthetic примеры для FE-01–FE-04. Existing health tests green.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Единственный main.py/API composition owner. frontend/lib/api-contracts.ts merge перед интеграцией внешнего UI; внешний разработчик и SNAP-17 используют контракт без конкурирующих DTO. SNAP-16 не разрабатывает страницы/дизайн; передача API описана в FRONTEND_HANDOFF.

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
