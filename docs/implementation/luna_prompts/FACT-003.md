# TASK PROMPT FOR GPT-6 LUNA (REASONING): FACT-003

> Объединено в [WORK-06 — Тарифные факты, проверка и публикация](../work_packages/WORK-06.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **Extra High** (`xhigh`).

## Контекст проекта

Ты работаешь в Banking Salary Intelligence Platform: FastAPI/Python, PostgreSQL, Next.js/TypeScript, модульный монолит, 4 банка, RU-KDA, около30 пользователей. Реализация разрешается отдельной командой пользователя; сам факт существования этого prompt не разрешает запуск. Для этой задачи исполнитель по плану: **GPT-6 Luna — Reasoning**. Если это независимый review Astra, передай задание ей, не объявляй self-review Luna независимым.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/tasks/FACT-003.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `DATA_FLOW.md`, `SECURITY.md` в том же architecture каталоге и `docs/quality/TEST_STRATEGY.md`. Прочитай обнаруженный AGENTS.md. Центральные файлы — обязательные контракты, не справочная рекомендация.

## Задача

**FACT-003: Валидация и решения аналитика**. Phase A2, Epic Факты, priority Critical, complexity M.
Предпосылки: FACT-002; gate **G0**. Проверь их реализацию и отчёты; не предполагай готовность по названию папки. На момент исходного проектирования приложение отсутствовало.

## Область изменений

backend/app/facts/validate.py; backend/app/facts/review.py. Также относящиеся tests/fixtures и `docs/reports/FACT-003.md`. Не делай рефакторинг несвязанных модулей.

## Ограничения

Сохраняй immutable originals и evidence; Decimal без float; unknown≠0; current≠latest fetched; private history owner-only. LLM не считает тарифы и не генерирует URLs/pages/dates. Provider не выбран, Fake используется до отдельного решения. Не добавляй vector DB, Kafka, Kubernetes, agent framework. Нельзя обходить защиту банков или отправлять сообщения/email. При изменении центрального контракта подготовь ADR и укажи affected tasks.

## Реализация

Контракт: ValidationResult{eligible,flags,missing_evidence}; ReviewRequest из API_CONTRACTS.

1. **FACT-003.01** — Проверить quote equality/offset/page, value-unit-basis-condition coverage и effective dates.
2. **FACT-003.02** — Реализовать approved/rejected/needs_changes с reason/expected_hash.
3. **FACT-003.03** — Corrections создают новый candidate с parent; первоначальный immutable.
4. **FACT-003.04** — POC review через локальный CLI service, MVP route добавляется API-002; actor_type human/rule и version аудируются.

Ошибки и границы: Stale expected_hash →409; no evidence →approve denied; confidence не разрешает missing applicability.

## Тестирование

Malformed quote, nonexistent page, date fetched substituted, concurrent reviews, correction preserves original.

Проверь реальные результаты, зафиксируй команды и versions/fixtures; не выдавай непроведённую проверку за pass. Live API без согласованного provider/policy не вызывай.

## Acceptance Criteria

Нельзя одобрить некорректное evidence; решения append-only; disputed candidate не появляется в published queries. Выполни также общий DoD из ТЗ задачи. Если предпосылка отсутствует, укажи конкретный blocker; выполняй только независимую разрешённую часть, не симулируй production dependency.

## Отчёт

Верни список файлов, реализованное поведение, команды и результаты проверок, доказательства каждого AC, limitations и неустранённые проблемы. Сохрани `docs/reports/FACT-003.md`. Обнови статус в MASTER_PLAN и TASK_INDEX; DONE только после AC. При возможности отдельный commit в project-local Git, без родительских изменений. Не начинай следующую задачу без проверки её gate и scope текущего поручения.
