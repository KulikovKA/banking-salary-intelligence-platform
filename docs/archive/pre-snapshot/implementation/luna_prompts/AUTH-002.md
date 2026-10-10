# TASK PROMPT FOR GPT-6 LUNA (REASONING): AUTH-002

> Объединено в [WORK-10 — Пользователи, приглашения, сессии и права доступа](../work_packages/WORK-10.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **High** (`high`).

## Контекст проекта

Ты работаешь в Banking Salary Intelligence Platform: FastAPI/Python, PostgreSQL, Next.js/TypeScript, модульный монолит, 4 банка, RU-KDA, около30 пользователей. Реализация разрешается отдельной командой пользователя; сам факт существования этого prompt не разрешает запуск. Для этой задачи исполнитель по плану: **GPT-6 Luna — Reasoning**. Если это независимый review Astra, передай задание ей, не объявляй self-review Luna независимым.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/tasks/AUTH-002.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `DATA_FLOW.md`, `SECURITY.md` в том же architecture каталоге и `docs/quality/TEST_STRATEGY.md`. Прочитай обнаруженный AGENTS.md. Центральные файлы — обязательные контракты, не справочная рекомендация.

## Задача

**AUTH-002: Сессии, CSRF и лимиты входа**. Phase B1, Epic Авторизация, priority Critical, complexity M.
Предпосылки: AUTH-001; gate **G2**. Проверь их реализацию и отчёты; не предполагай готовность по названию папки. На момент исходного проектирования приложение отсутствовало.

## Область изменений

backend/app/identity/routes.py; backend/app/identity/sessions.py; backend/app/identity/rate_limits.py. Также относящиеся tests/fixtures и `docs/reports/AUTH-002.md`. Не делай рефакторинг несвязанных модулей.

## Ограничения

Сохраняй immutable originals и evidence; Decimal без float; unknown≠0; current≠latest fetched; private history owner-only. LLM не считает тарифы и не генерирует URLs/pages/dates. Provider не выбран, Fake используется до отдельного решения. Не добавляй vector DB, Kafka, Kubernetes, agent framework. Нельзя обходить защиту банков или отправлять сообщения/email. При изменении центрального контракта подготовь ADR и укажи affected tasks.

## Реализация

Контракт: Login/logout/me, __Host-session, CSRF/Origin, idle8h/absolute24h.

1. **AUTH-002.01** — Создать opaque session token/hash, rotation/revocation/expiry.
2. **AUTH-002.02** — Установить Secure/HttpOnly/SameSite cookie и csrf validation.
3. **AUTH-002.03** — Добавить account/IP rate buckets и generic login errors.
4. **AUTH-002.04** — Проверить trusted proxy headers, disabled user и role change session revocation.

Ошибки и границы: Cookie missing/expired401; foreign Origin403; bad credentials одинаковый ответ; bucket DB error fail closed for login.

## Тестирование

Session fixation, CSRF, Origin bypass, expiry frozen clock, brute force429, logout reuse, disabled user.

Проверь реальные результаты, зафиксируй команды и versions/fixtures; не выдавай непроведённую проверку за pass. Live API без согласованного provider/policy не вызывай.

## Acceptance Criteria

Закрытые endpoints не доступны без session; cookies и limits соответствуют контракту. Выполни также общий DoD из ТЗ задачи. Если предпосылка отсутствует, укажи конкретный blocker; выполняй только независимую разрешённую часть, не симулируй production dependency.

## Отчёт

Верни список файлов, реализованное поведение, команды и результаты проверок, доказательства каждого AC, limitations и неустранённые проблемы. Сохрани `docs/reports/AUTH-002.md`. Обнови статус в MASTER_PLAN и TASK_INDEX; DONE только после AC. При возможности отдельный commit в project-local Git, без родительских изменений. Не начинай следующую задачу без проверки её gate и scope текущего поручения.
