# Реорганизация плана под внешний frontend — 11.10.2026

Результат: наша команда отвечает за Backend/PostgreSQL/тарифы/search/comparison/
Groq/ассистент/auth/security/API и интеграционные тесты. Внешний разработчик
создаёт UI; SNAP-17 принимает и адаптирует его предоставленный код, подключает
к FastAPI и проверяет интеграцию. Создание второго frontend с нуля исключено.

Base: `05000b39cb57a0679cb2aab7797bf437128ae601`; локальный HEAD и удалённый
`main` совпадали при начале задачи. Ветка: `codex/external-frontend-plan`.
Это отдельная задача изменения плана, не выполнение SNAP-08/16/17/19 или FE.

Прочитаны README/AGENTS, MASTER_PLAN/TASKS, prompts SNAP-16/17/19,
API_CONTRACTS, ACCEPTANCE_CRITERIA и docs validator. Старые report статусы
второй волны не приняты за актуальные: verified merge ancestry corrections
`624b774` и `af32b82`, код auth/corpus/HTML и integration tests находятся в main;
production `main.py` содержит только `/health`, UI остаётся starter page.
Повторная функциональная приёмка completed модулей в этот docs-only scope не входит.

## Изменённые файлы

- [AGENTS.md](../../AGENTS.md): владельцы Backend/UI и обязательные входы FE.
- [MASTER_PLAN.md](../implementation/MASTER_PLAN.md): ответственность, backend
  приоритет и последовательность интеграции, сохранённые 19 задач и 10 DONE.
- [TASKS.json](../implementation/TASKS.json): SNAP-17 title/outcome/implementation/
  acceptance/owned_paths/parallelism; SNAP-16 handoff и SNAP-19 integration AC.
- [SNAP-16.md](../implementation/prompts/SNAP-16.md): стабильный OpenAPI/TS client
  contract и synthetic примеры auth/CSRF/состояний/ошибок без требования дизайна.
- [SNAP-17.md](../implementation/prompts/SNAP-17.md): интеграция переданных
  исходников вместо самостоятельной разработки UI, входные условия и FE evidence.
- [SNAP-19.md](../implementation/prompts/SNAP-19.md): финальная приёмка ждёт
  принятой интеграции SNAP-17/FE-01–FE-04 и SNAP-18.
- [FRONTEND_HANDOFF.md](../implementation/FRONTEND_HANDOFF.md): входной пакет,
  tracker FE-01–FE-04, владельцы, зависимости, AC и ожидаемые evidence.
- Этот report: scope, проверки, последовательность и оставшиеся зависимости.

Backend/frontend runtime, публичные DTO/API, миграции, locks и validator не
изменены. Существующее чужое изменение `frontend/next-env.d.ts` исключено из
commit; исходники внешнего frontend не получены и фиктивный репозиторий не создан.

## Последовательность и приёмка изменений плана

**SNAP-08 -> SNAP-09 -> (SNAP-10 и SNAP-11) -> SNAP-14 -> SNAP-16**.
После переданных исходников и merged SNAP-16: **SNAP-17 / FE-01 приёмка ->
FE-02 перенос/адаптация -> FE-03 подключение -> FE-04 проверки**.
Внешняя разработка UI может идти параллельно backend. SNAP-18 сохраняет свои
зависимости и disjoint paths; **SNAP-19 ждёт SNAP-17 и SNAP-18**.

DAG/статусы не менялись. Все десять DONE сохранены целиком:
01/02/03/04/05/06/07/12/13/15. Единственная доступная TODO — SNAP-08.
SNAP-17 остаётся TODO; FE tracker фиксирует четыре BLOCKED по отсутствующим
входам. По каждому FE есть владелец, dependencies, AC, причина и поле evidence.
SNAP-16 владеет API/TS DTO, SNAP-17 имеет один frontend tree/lockfile owner;
контрактные изменения требуют обоснованного follow-up и согласованного merge.

## Проверки

| Проверка | Результат |
|---|---|
| `python tools/validate_docs.py` | PASS: относительные ссылки, ровно 19 SNAP, DAG/statuses, plan/registry/prompt и source decisions |
| `uv run --offline ruff check .` | PASS: All checks passed |
| `uv run --offline mypy backend/app` | PASS: 54 source files, 0 issues |
| Сверка реестра с base через Python assertions | PASS: 19 IDs; 10 DONE unchanged целиком; все deps/status/effort/prompt unchanged; owned paths присутствуют в prompts; только SNAP-08 ready; 4 FE BLOCKED; runtime edits отсутствуют |
| `git diff --check` | PASS: whitespace errors = 0 |
| pytest / PG integrations / Alembic / synthetic E2E | NOT RUN: 0 tests/runs, изменены только план/инструкции/report; runtime/schema не менялись |
| Frontend lint/typecheck/build / browser E2E | NOT RUN: 0 runs, UI не реализуется/не меняется, внешний код отсутствует |
| Live bank acquisition / real Groq | NOT RUN: 0 runs, вне задачи; source/provider gates не обойдены |

Backend lint/typecheck использовали существующую offline среду; новые
зависимости не добавлены. Функциональные NOT RUN не обозначаются PASS; docs
проверки не доказывают готовность нового pipeline/UI или реального продукта.

## Оставшиеся зависимости

1. Выполнить отдельно SNAP-08/09/10/11/14/16 на их merged prerequisites.
2. Получить exact внешний frontend revision, исходники, зависимости/lockfile,
   лицензии/права на использование, дизайн и список экранов/состояний/дефектов.
3. Принять FE-01–FE-04 с evidence на реальном FastAPI/PG и synthetic/Fake;
   source transfer и будущие API — обязательные входы, не утверждение готовности.
4. Для real acceptance нужны допущенный frozen corpus, gold/evaluation SNAP-18,
   provider key/reuse admission и реальные run artifacts.

S1 BLOCKED; S2/S3 NOT EVALUATED; G1/G2 NOT PASSED. Полный S0 ещё не завершён.
Этот report подтверждает реорганизацию плана; SNAP/FE исполнение не начато.
