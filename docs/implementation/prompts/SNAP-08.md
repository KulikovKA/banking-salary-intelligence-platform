# SNAP-08 — Последовательный parsing/extraction pipeline

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Accepted original -> immutable extraction/chunks -> normalized pending candidates/evidence, повторный запуск безопасен.

## Условия начала

Merged зависимости: SNAP-03, SNAP-04, SNAP-05, SNAP-06, SNAP-07. Пока зависимость не завершена, допустим только явно
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

- `backend/app/parsing/runner.py`
- `backend/app/parsing/service.py`
- `backend/app/parsing/cli.py`
- `backend/app/tariffs/extract.py`
- `backend/tests/test_extraction_pipeline.py`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-08.md`.

## Реализация и ограничения

Свяжи parser modules и SNAP-02 models, store.verify до чтения. Bounded local subprocess/no network, ресурсы/timeouts на Windows/Linux с documented fallback. CLI обрабатывает конкретную version синхронно, без job queue. Rule-based extraction keyed by metric cues/tables; неопознанные структуры требуют operator mapping/review, не guessed facts. Persist immutable chunk text/hash/locator/relations, candidates всегда pending_review, deterministic extraction key. Partial parser output не publish. Сделай маленький операторский mapping JSON с references к chunk/cell для новых шаблонов, без UI designer subsystem.

## Тесты и критерии приёмки

Synthetic PDF/XLSX/HTML до candidate в PG; repeated run idempotent, новый parser version даёт новый extraction; crash/timeout не создаёт published fact, different corpus запрещён, offsets/hash совпадают. Merged headers/footnotes сохраняют support roles.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Один integrator pipeline после merge parsers; schema/parser internals read-only. Можно параллельно завершать Groq/auth, не shared migrations.

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
