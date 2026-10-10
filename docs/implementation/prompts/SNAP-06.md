# SNAP-06 — HTML parser сохранённого original

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **medium**; выбор модели свободный.

## Цель и ожидаемый результат

Static headings/tables/paragraphs/footnotes и element paths без browser/fetch.

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

- `backend/app/parsing/html.py`
- `backend/tests/test_parsing_html.py`
- `backend/tests/fixtures/parsing/html/**`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-06.md`.

## Реализация и ограничения

Используй stdlib HTMLParser или аргументированно существующий dependency. Парси сохранённые bytes с recorded encoding, deterministic whitespace/text mapping. Исключи script/style/nav шум, сохрани заголовки, таблицы, captions и footnotes; malformed DOM -> diagnostics, динамический пустой контент -> unsupported. DOM element path детерминирован, нет fetch subresources и JS.

## Тесты и критерии приёмки

Fixture с nested tables, Cyrillic/entities, rowspan/colspan, сноской, script injection и внешней картинкой: правильные blocks/locators, quote offsets stable, network calls 0. Marketing statement не становится tariff fact.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Полностью отдельные html paths; можно одновременно SNAP-02/04/05/07/12. Не менять ingestion adapters/transport.

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
