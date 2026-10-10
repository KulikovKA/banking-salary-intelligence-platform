# SNAP-11 — Детерминированный Comparison Engine

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Rows/pairwise/claims с evidence; Decimal стоимость и честные insufficient/conflict.

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

- `backend/app/comparison/service.py`
- `backend/app/comparison/calculations.py`
- `backend/tests/test_comparison_golden.py`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-11.md`.

## Реализация и ограничения

Фильтр snapshot+approved+policy+as_of+scope, AST три значения, registry из SNAP-07. Совместимость payer/operation/basis/unit/currency/period; constant/percentage/clamped, known components отдельно от total. Не выводить winner при unknown rounding/date/scope, overlapping ranges/conflicts/individual. Объяснимый claim operands/formula_version/scenario hash/evidence обеих сторон. Общий weighted score запрещён.

## Тесты и критерии приёмки

>=30 synthetic golden cases: 100000*0.30/100=300; caps/floors; per-transfer/per-batch; zero vs unknown; conflicting dates/scopes; missing inputs; future/outdated interval; partial costs; bank permutation symmetry. LLM никогда не используется в calculations; numeric roundtrip точен.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Параллельно search, полностью comparison paths; tariff metrics registry read-only. Real pair coverage оценивает SNAP-18, не синтетические golden tests.

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
