# TASK PROMPT FOR GPT-6 LUNA (REASONING): FACT-001

> Объединено в [WORK-06 — Тарифные факты, проверка и публикация](../work_packages/WORK-06.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **Extra High** (`xhigh`).

## Контекст проекта

Ты работаешь в Banking Salary Intelligence Platform: FastAPI/Python, PostgreSQL, Next.js/TypeScript, модульный монолит, 4 банка, RU-KDA, около30 пользователей. Реализация разрешается отдельной командой пользователя; сам факт существования этого prompt не разрешает запуск. Для этой задачи исполнитель по плану: **GPT-6 Luna — Reasoning**. Если это независимый review Astra, передай задание ей, не объявляй self-review Luna независимым.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/tasks/FACT-001.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `DATA_FLOW.md`, `SECURITY.md` в том же architecture каталоге и `docs/quality/TEST_STRATEGY.md`. Прочитай обнаруженный AGENTS.md. Центральные файлы — обязательные контракты, не справочная рекомендация.

## Задача

**FACT-001: Нормализованные DTO тарифов и applicability**. Phase A2, Epic Факты, priority Critical, complexity M.
Предпосылки: DB-003; gate **G0**. Проверь их реализацию и отчёты; не предполагай готовность по названию папки. На момент исходного проектирования приложение отсутствовало.

## Область изменений

backend/app/facts/schemas.py; backend/app/facts/normalize.py; backend/app/comparison/metrics.py. Также относящиеся tests/fixtures и `docs/reports/FACT-001.md`. Не делай рефакторинг несвязанных модулей.

## Ограничения

Сохраняй immutable originals и evidence; Decimal без float; unknown≠0; current≠latest fetched; private history owner-only. LLM не считает тарифы и не генерирует URLs/pages/dates. Provider не выбран, Fake используется до отдельного решения. Не добавляй vector DB, Kafka, Kubernetes, agent framework. Нельзя обходить защиту банков или отправлять сообщения/email. При изменении центрального контракта подготовь ADR и укажи affected tasks.

## Реализация

Контракт: FactCandidate, value discriminated union, ScopeDimension, predicate AST из DOMAIN_CONTRACTS.

1. **FACT-001.01** — Реализовать strict Pydantic DTO и Decimal string serialization.
2. **FACT-001.02** — Нормализовать comma decimals/NBSP/руб/%/period без потери оригинального текста.
3. **FACT-001.03** — Реализовать kind money/percent/range/individual/formula и metrics registry.
4. **FACT-001.04** — Валидировать geography/segment/package/date enums и AST bounds; unknown не конвертировать в any.

Ошибки и границы: Несогласованные единицы, NaN/Infinity, отрицательная комиссия, malformed AST →typed validation; free text остаётся manual.

## Тестирование

0 vs null vs individual, 0,3%=0.30, from/up-to, RUB period, unknown scope; roundtrip DTO JSON.

Проверь реальные результаты, зафиксируй команды и versions/fixtures; не выдавай непроведённую проверку за pass. Live API без согласованного provider/policy не вызывай.

## Acceptance Criteria

Нормализация воспроизводима и не добавляет недостающих дат/чисел. Выполни также общий DoD из ТЗ задачи. Если предпосылка отсутствует, укажи конкретный blocker; выполняй только независимую разрешённую часть, не симулируй production dependency.

## Отчёт

Верни список файлов, реализованное поведение, команды и результаты проверок, доказательства каждого AC, limitations и неустранённые проблемы. Сохрани `docs/reports/FACT-001.md`. Обнови статус в MASTER_PLAN и TASK_INDEX; DONE только после AC. При возможности отдельный commit в project-local Git, без родительских изменений. Не начинай следующую задачу без проверки её gate и scope текущего поручения.
