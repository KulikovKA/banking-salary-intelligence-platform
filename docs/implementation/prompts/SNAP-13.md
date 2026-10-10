# SNAP-13 — GroqCloud Free adapter и quotas

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Provider openai/gpt-oss-120b через Groq, HTTP mocks в CI, reservation limits и безопасный fallback errors.

## Условия начала

Merged зависимости: SNAP-02, SNAP-12. Пока зависимость не завершена, допустим только явно
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

- `backend/app/llm/groq.py`
- `backend/app/llm/budget.py`
- `backend/app/config.py`
- `.env.example`
- `backend/tests/test_llm_groq.py`
- `backend/tests/test_llm_budget.py`
- `backend/tests/test_config.py`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-13.md`.

## Реализация и ограничения

Проверить актуальные official Groq models/structured outputs/rate limits docs, указать ссылки/дату в report. HTTPS api.groq.com/openai/v1, reuse httpx2 client с allowlist/no redirect/timeout; добавить только нужные quota config. Существующий LLM_MODE=fake|provider и SecretStr сохраняй. Strict JSON schema + local validation, no tool use; reasoning traces не логировать. До 2 calls/question, input<=4000/output<=1000 tokens total, max20s/call/45s overall, один concurrent provider call глобально initial, per-user один. Лимиты аккаунта authoritative, configurable ceilings, atomic PG daily budget/window Europe/Moscow, rate counters и Retry-After. Не отправленный запрос освобождает reservation, ambiguous sent usage остаётся estimated. Retry максимум один transient ВНУТРИ общего call/token/deadline cap; 429 долгий -> fallback. Только opt-in smoke с ключом и разрешённым payload, не real corpus автоматически.

## Тесты и критерии приёмки

HTTP mock valid/invalid/429 retry-after/5xx/401/timeout/context, exhausted quota/concurrent reservations/unknown usage/crash; секрет canary отсутствует в logs, endpoint escape/redirect rejected, production validation green. Real model smoke NOT RUN если ключа/допуска нет; Fake success не объявляй Groq PASS.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Владеет config.py и .env.example временно; SNAP-15 не редактирует их параллельно. Нет dependency edits SDK по умолчанию, использовать existing transport library.

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
