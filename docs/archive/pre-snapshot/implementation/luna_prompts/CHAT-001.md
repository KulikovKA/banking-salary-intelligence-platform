# TASK PROMPT FOR GPT-6 LUNA (REASONING): CHAT-001

> Объединено в [WORK-11 — Личная история, память и надёжное выполнение вопросов](../work_packages/WORK-11.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **Extra High** (`xhigh`).

## Контекст проекта

Ты работаешь в Banking Salary Intelligence Platform: FastAPI/Python, PostgreSQL, Next.js/TypeScript, модульный монолит, 4 банка, RU-KDA, около30 пользователей. Реализация разрешается отдельной командой пользователя; сам факт существования этого prompt не разрешает запуск. Для этой задачи исполнитель по плану: **GPT-6 Luna — Reasoning**. Если это независимый review Astra, передай задание ей, не объявляй self-review Luna независимым.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/tasks/CHAT-001.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `DATA_FLOW.md`, `SECURITY.md` в том же architecture каталоге и `docs/quality/TEST_STRATEGY.md`. Прочитай обнаруженный AGENTS.md. Центральные файлы — обязательные контракты, не справочная рекомендация.

## Задача

**CHAT-001: Хранение собственной истории и удаление**. Phase B1, Epic Чаты, priority Critical, complexity M.
Предпосылки: AUTH-003, DB-004; gate **G2**. Проверь их реализацию и отчёты; не предполагай готовность по названию папки. На момент исходного проектирования приложение отсутствовало.

## Область изменений

backend/app/chats/service.py; backend/app/chats/routes.py; backend/app/chats/schemas.py. Также относящиеся tests/fixtures и `docs/reports/CHAT-001.md`. Не делай рефакторинг несвязанных модулей.

## Ограничения

Сохраняй immutable originals и evidence; Decimal без float; unknown≠0; current≠latest fetched; private history owner-only. LLM не считает тарифы и не генерирует URLs/pages/dates. Provider не выбран, Fake используется до отдельного решения. Не добавляй vector DB, Kafka, Kubernetes, agent framework. Нельзя обходить защиту банков или отправлять сообщения/email. При изменении центрального контракта подготовь ADR и укажи affected tasks.

## Реализация

Контракт: Owned chat CRUD/message list/delete, cursor pagination и immutable answer refs.

1. **CHAT-001.01** — Создать session/list/messages с SQL owner predicates и stable cursor.
2. **CHAT-001.02** — Сохранять user/assistant messages с sequence, AnswerEnvelope и evidence refs.
3. **CHAT-001.03** — Удалять собственный chat атомарно, отменять pending runs; usage detach.
4. **CHAT-001.04** — Записывать deletion tombstone для restore, не сохранять текст в audit.

Ошибки и границы: Чужой chat404; double delete idempotent policy; deleting session не принимает message.

## Тестирование

A/B ownership всех методов, pagination ties, delete during run, evidence survives chat deletion.

Проверь реальные результаты, зафиксируй команды и versions/fixtures; не выдавай непроведённую проверку за pass. Live API без согласованного provider/policy не вызывай.

## Acceptance Criteria

История личная; удалённые сообщения не читаются и не возвращаются поздним worker. Выполни также общий DoD из ТЗ задачи. Если предпосылка отсутствует, укажи конкретный blocker; выполняй только независимую разрешённую часть, не симулируй production dependency.

## Отчёт

Верни список файлов, реализованное поведение, команды и результаты проверок, доказательства каждого AC, limitations и неустранённые проблемы. Сохрани `docs/reports/CHAT-001.md`. Обнови статус в MASTER_PLAN и TASK_INDEX; DONE только после AC. При возможности отдельный commit в project-local Git, без родительских изменений. Не начинай следующую задачу без проверки её gate и scope текущего поручения.
