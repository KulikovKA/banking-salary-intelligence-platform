# SNAP-07 — Нормализация тарифов и registry метрик

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Pure normalization raw candidate fields -> typed TariffCandidate или flags; без публикации.

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
Сохрани FetchGateway, LocalBlobStore, source recovery, E2E и миграции 0001/0002.

## Файлы и ответственность

- `backend/app/tariffs/normalize.py`
- `backend/app/tariffs/metrics.py`
- `backend/tests/test_tariff_normalization.py`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-07.md`.

## Реализация и ограничения

Реализуй registry DOMAIN_CONTRACTS и Decimal parsing RUB/%/period/basis/payer/operation. Сохрани условия, range/individual, any/specific/unknown; date normalization inclusive end -> exclusive с original wording. Restricted AST, no eval/SQL/Python. Не угадывать заголовок/сноску или scope/date; недостаточный evidence -> flag. Алгоритм не делает IO и не нуждается в реальных документах.

## Тесты и критерии приёмки

0.30%=0.30, decimal comma, conditional free vs unknown, from/up-to, individual, per batch vs per transfer, employer vs employee, future/unknown dates, invalid AST/units/range. Idempotent normalization; malformed values never become zero.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Отдельные tariff pure modules, параллельно schema/parsers/Fake/auth после контрактов. Не править ORM/migrations/contracts.

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
