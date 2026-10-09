# TASK PROMPT FOR GPT-6 LUNA (REASONING): LOAD-001

> Объединено в [WORK-19 — Сквозная приёмка и нагрузка 30 пользователей](../work_packages/WORK-19.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **High** (`high`).

## Контекст проекта

Ты работаешь в Banking Salary Intelligence Platform: FastAPI/Python, PostgreSQL, Next.js/TypeScript, модульный монолит, 4 банка, RU-KDA, около30 пользователей. Реализация разрешается отдельной командой пользователя; сам факт существования этого prompt не разрешает запуск. Для этой задачи исполнитель по плану: **GPT-6 Luna — Reasoning**. Если это независимый review Astra, передай задание ей, не объявляй self-review Luna независимым.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/tasks/LOAD-001.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `DATA_FLOW.md`, `SECURITY.md` в том же architecture каталоге и `docs/quality/TEST_STRATEGY.md`. Прочитай обнаруженный AGENTS.md. Центральные файлы — обязательные контракты, не справочная рекомендация.

## Задача

**LOAD-001: Нагрузка 30 пользователей и пределы ресурсов**. Phase B4, Epic Приёмка MVP, priority High, complexity L.
Предпосылки: QA-003; gate **G2**. Проверь их реализацию и отчёты; не предполагай готовность по названию папки. На момент исходного проектирования приложение отсутствовало.

## Область изменений

tests/load/; docs/reports/load-report.md. Также относящиеся tests/fixtures и `docs/reports/LOAD-001.md`. Не делай рефакторинг несвязанных модулей.

## Ограничения

Сохраняй immutable originals и evidence; Decimal без float; unknown≠0; current≠latest fetched; private history owner-only. LLM не считает тарифы и не генерирует URLs/pages/dates. Provider не выбран, Fake используется до отдельного решения. Не добавляй vector DB, Kafka, Kubernetes, agent framework. Нельзя обходить защиту банков или отправлять сообщения/email. При изменении центрального контракта подготовь ADR и укажи affected tasks.

## Реализация

Контракт: 30 concurrent sessions, max5 provider calls, target latency OPERATIONS/REQUIREMENTS.

1. **LOAD-001.01** — Подготовить100k chunks corpus с корректными IDs, смешать search/compare/chat/read/ingest.
2. **LOAD-001.02** — Прогреть затем измерить30min steady +burst30 submissions и slow provider.
3. **LOAD-001.03** — Записать p50/p95/error/queue/db connections/CPU/RAM/disk и query plans.
4. **LOAD-001.04** — Устранить конкретные bottlenecks без нового сервиса, повторить затронутый сценарий.

Ошибки и границы: Queue full возвращает429/Retry-After; no silent dropped answer; Fake latency test не доказывает real provider SLA.

## Тестирование

p95 API<500ms/search-comparison<1s, deadline45s либо explicit fallback; caps hold; soak memory stable.

Проверь реальные результаты, зафиксируй команды и versions/fixtures; не выдавай непроведённую проверку за pass. Live API без согласованного provider/policy не вызывай.

## Acceptance Criteria

Цели достигнуты на указанном host либо честно отмечены ограничения для решения пользователя. Выполни также общий DoD из ТЗ задачи. Если предпосылка отсутствует, укажи конкретный blocker; выполняй только независимую разрешённую часть, не симулируй production dependency.

## Отчёт

Верни список файлов, реализованное поведение, команды и результаты проверок, доказательства каждого AC, limitations и неустранённые проблемы. Сохрани `docs/reports/LOAD-001.md`. Обнови статус в MASTER_PLAN и TASK_INDEX; DONE только после AC. При возможности отдельный commit в project-local Git, без родительских изменений. Не начинай следующую задачу без проверки её gate и scope текущего поручения.
