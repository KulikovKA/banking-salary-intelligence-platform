# SNAP-10 — PostgreSQL FTS по frozen corpus

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **medium**; выбор модели свободный.

## Цель и ожидаемый результат

Текстовый поиск с bank/metric filters и точными source/evidence locators.

## Условия начала

Merged зависимости: SNAP-09. Пока зависимость не завершена, допустим только явно
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

- `backend/app/search/service.py`
- `backend/tests/test_snapshot_search.py`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-10.md`.

## Реализация и ограничения

Используй existing snapshot read service и PG tsvector/GIN, русский плюс simple fallback; limit<=10, deterministic tie-break. Search только readable frozen members, исключает rejected/quarantine/revoked/synthetic в real namespace. Snippets не отделяй от обязательных условий. Для общего document поиска цитата допустима, но не тарифное утверждение без published fact. Нет embeddings/vector infra.

## Тесты и критерии приёмки

PG Cyrillic morphology, numbers/codes, per-bank filter, correct top10 relevance fixed fixtures; no cross-snapshot leakage; zero hits -> explicit absence_of_evidence. Query input parameterized и bounded. Recall@10 harness отдельно от fake scores.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Параллельно SNAP-11 после SNAP-09, отдельный search/service.py; не менять FTS schema без follow-up schema owner.

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
