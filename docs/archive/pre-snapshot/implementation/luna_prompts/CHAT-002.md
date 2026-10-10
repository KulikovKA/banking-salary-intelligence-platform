# TASK PROMPT FOR GPT-6 LUNA (REASONING): CHAT-002

> Объединено в [WORK-11 — Личная история, память и надёжное выполнение вопросов](../work_packages/WORK-11.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **Extra High** (`xhigh`).

## Контекст проекта

Ты работаешь в Banking Salary Intelligence Platform: FastAPI/Python, PostgreSQL, Next.js/TypeScript, модульный монолит, 4 банка, RU-KDA, около30 пользователей. Реализация разрешается отдельной командой пользователя; сам факт существования этого prompt не разрешает запуск. Для этой задачи исполнитель по плану: **GPT-6 Luna — Reasoning**. Если это независимый review Astra, передай задание ей, не объявляй self-review Luna независимым.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/tasks/CHAT-002.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `DATA_FLOW.md`, `SECURITY.md` в том же architecture каталоге и `docs/quality/TEST_STRATEGY.md`. Прочитай обнаруженный AGENTS.md. Центральные файлы — обязательные контракты, не справочная рекомендация.

## Задача

**CHAT-002: Структурированная память и разрешение ссылок**. Phase B1, Epic Чаты, priority Critical, complexity M.
Предпосылки: CHAT-001, AI-001; gate **G2**. Проверь их реализацию и отчёты; не предполагай готовность по названию папки. На момент исходного проектирования приложение отсутствовало.

## Область изменений

backend/app/chats/context.py. Также относящиеся tests/fixtures и `docs/reports/CHAT-002.md`. Не делай рефакторинг несвязанных модулей.

## Ограничения

Сохраняй immutable originals и evidence; Decimal без float; unknown≠0; current≠latest fetched; private history owner-only. LLM не считает тарифы и не генерирует URLs/pages/dates. Provider не выбран, Fake используется до отдельного решения. Не добавляй vector DB, Kafka, Kubernetes, agent framework. Нельзя обходить защиту банков или отправлять сообщения/email. При изменении центрального контракта подготовь ADR и укажи affected tasks.

## Реализация

Контракт: Context schema/version/focus_bank из DATA_FLOW; optimistic context version.

1. **CHAT-002.01** — Merge explicit question > confirmed context > defaults.
2. **CHAT-002.02** — Обработать focus/comparator, reset as_of now и explicit historical dates.
3. **CHAT-002.03** — Передавать только bounded recent context и безопасные normalized fields, не старые тарифные числа.
4. **CHAT-002.04** — Version conflict сохраняет input и требует retry/clarify, uncertain referent не обновляет focus.

Ошибки и границы: Ambiguous pronoun →clarification; stale history never fact source; deletion removes context.

## Тестирование

Сбер→Альфа затем «его с ВТБ»; два кандидата referent; historical→now; tariff changed after old answer.

Проверь реальные результаты, зафиксируй команды и versions/fixtures; не выдавай непроведённую проверку за pass. Live API без согласованного provider/policy не вызывай.

## Acceptance Criteria

Память сохраняет выбор, а факты всегда перечитываются; concurrency не затирает context. Выполни также общий DoD из ТЗ задачи. Если предпосылка отсутствует, укажи конкретный blocker; выполняй только независимую разрешённую часть, не симулируй production dependency.

## Отчёт

Верни список файлов, реализованное поведение, команды и результаты проверок, доказательства каждого AC, limitations и неустранённые проблемы. Сохрани `docs/reports/CHAT-002.md`. Обнови статус в MASTER_PLAN и TASK_INDEX; DONE только после AC. При возможности отдельный commit в project-local Git, без родительских изменений. Не начинай следующую задачу без проверки её gate и scope текущего поручения.
