# SNAP-12 — LLM Protocol, Fake и bounded renderer inputs

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **medium**; выбор модели свободный.

## Цель и ожидаемый результат

Тот же async provider interface для Fake/Groq с typed errors и сценариями injection/timeout/malformed.

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

- `backend/app/llm/base.py`
- `backend/app/llm/fake.py`
- `backend/tests/test_llm_contract.py`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-12.md`.

## Реализация и ограничения

Implement SNAP-01 Protocol, structured intent/explain, no DB/storage/tools в provider. Fake deterministic fixtures, error injections и usage fields. Contract tests задают allowed claims/templates и schema validation. Fake не должен автоматически выдавать verified claim из fixture question без evidence. Не реализуй Groq/config/assistant в этом commit.

## Тесты и критерии приёмки

Success plus timeout/rate_limit/auth/unavailable/context_exceeded/invalid JSON/unknown claim/unsupported templates; deterministic repeat и no network. Typecheck concrete Fake satisfies Protocol.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Можно сразу после SNAP-01 одновременно со schema/parsers/normalize. Отдельные llm base/fake paths, не llm models.py SNAP-02.

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
