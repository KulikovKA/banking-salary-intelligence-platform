# SNAP-01 — Зафиксировать исполняемые DTO и Protocol

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Versioned DTO для всего pipeline, Parser/LLM/read service Protocol; без бизнес-реализации и миграций.

## Условия начала

Merged зависимости: Нет; можно запускать немедленно. Пока зависимость не завершена, допустим только явно
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

- `backend/app/contracts/**`
- `backend/tests/test_snapshot_contracts.py`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-01.md`.

## Реализация и ограничения

Перенеси DOMAIN_CONTRACTS/API_CONTRACTS в Pydantic extra=forbid. Discriminated unions Value/Locator; Decimal strings, scope/date/conditions constraints. Protocol parsers и async LLM не должны импортировать concrete implementations. Совместимость ExtractionEvidence сохраняй через adapter. Зафиксируй serialization fixtures и interfaces, которые используют downstream modules. Ответь на неясности nullable/unknown явным тестом, не добавлением default tariff.

## Тесты и критерии приёмки

Roundtrip всех DTO; reject float/NaN/Infinity для денежных входов, unknown fields, пустой specific scope, неверные offsets, duplicate bank codes, unsupported enums/AST. Typecheck Protocol с Fake stubs. Отдельные synthetic_a identities допустимы только test context; реальные DTO не принимают их.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Первый обязательный merge. Не менять config/main/registry/lockfiles. После merge contracts read-only для всех downstream.

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
