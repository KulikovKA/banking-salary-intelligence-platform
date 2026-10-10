# SNAP-09 — Evidence validation, manual review и publication

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Проверяемый validator и атомарный approved fact publication; ручной CLI review для v1.

## Условия начала

Merged зависимости: SNAP-08. Пока зависимость не завершена, допустим только явно
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

- `backend/app/evidence/validation.py`
- `backend/app/evidence/service.py`
- `backend/app/evidence/cli.py`
- `backend/tests/test_evidence_publication.py`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-09.md`.

## Реализация и ограничения

Дополнить, не заменить ExtractionEvidence. Проверяй original/extraction/text hashes, FK ancestry, substring offsets, actual locator, support value/unit/basis/period/conditions/scope/date. Technical quote match не доказывает смысл: manual reviewer обязан подтвердить semantic support. Uncertain footnote/unknown applicability не verified. Append-only review reason/identity, rejected/needs_review excluded; publish draft snapshot member с row locks/unique keys, synthetic->real reject. Revocation проверять на read/freeze; исправление в новой snapshot revision.

## Тесты и критерии приёмки

Real URL с неподдерживающей цитатой, подмена числа/единицы/сноски, wrong page/cell/hash/extraction/source, synthetic provenance, revoked grant -> reject. Concurrent publish один результат; raw candidate не searchable as fact. Valid approved unknown-date quote сохранена с limitation, не current winner.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Evidence owner без изменения нормализатора/ORM. Search/Comparison начинают после merge опубликованных read interfaces; auth/provider независимы.

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
