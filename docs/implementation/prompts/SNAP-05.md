# SNAP-05 — XLSX parser без вычисления формул

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Листы, диапазоны ячеек, merged headers и footnotes превращаются в locatable blocks.

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

- `backend/app/parsing/xlsx.py`
- `backend/tests/test_parsing_xlsx.py`
- `backend/tests/fixtures/parsing/xlsx/**`
- `pyproject.toml`
- `uv.lock`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-05.md`.

## Реализация и ограничения

Добавь openpyxl после dependency merge SNAP-04, сохрани existing check_format до parser. Не выполнять formulas/macros/external links; хранить formula и cached value отдельно, absent cache -> unknown/manual review. Ограничить sheets/cells/XML/text, отражать hidden sheets и mixed types в diagnostics. Decimal parsing не выполняет тарифную интерпретацию. Если общий parser contract недостаточен, предложи change владельцу SNAP-01, не меняй его параллельно.

## Тесты и критерии приёмки

Generated workbook с merged header, decimal comma, percent cell, footnote, hidden sheet, cached/missing formula value; точные sheet+cell locators и stable hash. ZIP bombs/external links rejected existing guard, bounded huge workbook и corrupt input.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Отдельные xlsx paths, параллельно PDF/HTML. Shared lockfiles edits только после SNAP-04 merge, не cherry-pick конфликтующие lockfiles.

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
