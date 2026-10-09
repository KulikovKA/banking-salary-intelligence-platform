# TASK PROMPT FOR GPT-6 LUNA (REASONING): AUTH-003

> Объединено в [WORK-10 — Пользователи, приглашения, сессии и права доступа](../work_packages/WORK-10.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **High** (`high`).

## Контекст проекта

Ты работаешь в Banking Salary Intelligence Platform: FastAPI/Python, PostgreSQL, Next.js/TypeScript, модульный монолит, 4 банка, RU-KDA, около30 пользователей. Реализация разрешается отдельной командой пользователя; сам факт существования этого prompt не разрешает запуск. Для этой задачи исполнитель по плану: **GPT-6 Luna — Reasoning**. Если это независимый review Astra, передай задание ей, не объявляй self-review Luna независимым.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/tasks/AUTH-003.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `DATA_FLOW.md`, `SECURITY.md` в том же architecture каталоге и `docs/quality/TEST_STRATEGY.md`. Прочитай обнаруженный AGENTS.md. Центральные файлы — обязательные контракты, не справочная рекомендация.

## Задача

**AUTH-003: RBAC и object ownership во всех сервисах**. Phase B1, Epic Авторизация, priority Critical, complexity L.
Предпосылки: AUTH-002, DOC-001; gate **G2**. Проверь их реализацию и отчёты; не предполагай готовность по названию папки. На момент исходного проектирования приложение отсутствовало.

## Область изменений

backend/app/identity/permissions.py; backend/app/documents/routes.py; backend/app/main.py. Также относящиеся tests/fixtures и `docs/reports/AUTH-003.md`. Не делай рефакторинг несвязанных модулей.

## Ограничения

Сохраняй immutable originals и evidence; Decimal без float; unknown≠0; current≠latest fetched; private history owner-only. LLM не считает тарифы и не генерирует URLs/pages/dates. Provider не выбран, Fake используется до отдельного решения. Не добавляй vector DB, Kafka, Kubernetes, agent framework. Нельзя обходить защиту банков или отправлять сообщения/email. При изменении центрального контракта подготовь ADR и укажи affected tasks.

## Реализация

Контракт: Principal + additive user/analyst/admin roles, ownership API_CONTRACTS.

1. **AUTH-003.01** — Заменить POC principal production dependency на session auth.
2. **AUTH-003.02** — Применить permission matrix к routes/services, включая streaming/poll/list.
3. **AUTH-003.03** — Не давать Admin ownership bypass на чаты; analyst approval отдельно от admin.
4. **AUTH-003.04** — Добавить endpoint inventory test, POC routes выключены production.

Ошибки и границы: Foreign object404; role forbidden403; revoked session401; забытый endpoint считается test failure.

## Тестирование

Все роли×методы, guessed UUID, foreign content/poll/list/delete; Admin без analyst не approve.

Проверь реальные результаты, зафиксируй команды и versions/fixtures; не выдавай непроведённую проверку за pass. Live API без согласованного provider/policy не вызывай.

## Acceptance Criteria

Authorization enforced backend на каждом endpoint; UI checks не единственная защита. Выполни также общий DoD из ТЗ задачи. Если предпосылка отсутствует, укажи конкретный blocker; выполняй только независимую разрешённую часть, не симулируй production dependency.

## Отчёт

Верни список файлов, реализованное поведение, команды и результаты проверок, доказательства каждого AC, limitations и неустранённые проблемы. Сохрани `docs/reports/AUTH-003.md`. Обнови статус в MASTER_PLAN и TASK_INDEX; DONE только после AC. При возможности отдельный commit в project-local Git, без родительских изменений. Не начинай следующую задачу без проверки её gate и scope текущего поручения.
