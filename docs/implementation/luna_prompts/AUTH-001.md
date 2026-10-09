# TASK PROMPT FOR GPT-6 LUNA (REASONING): AUTH-001

> Объединено в [WORK-10 — Пользователи, приглашения, сессии и права доступа](../work_packages/WORK-10.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **High** (`high`).

## Контекст проекта

Ты работаешь в Banking Salary Intelligence Platform: FastAPI/Python, PostgreSQL, Next.js/TypeScript, модульный монолит, 4 банка, RU-KDA, около30 пользователей. Реализация разрешается отдельной командой пользователя; сам факт существования этого prompt не разрешает запуск. Для этой задачи исполнитель по плану: **GPT-6 Luna — Reasoning**. Если это независимый review Astra, передай задание ей, не объявляй self-review Luna независимым.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/tasks/AUTH-001.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `DATA_FLOW.md`, `SECURITY.md` в том же architecture каталоге и `docs/quality/TEST_STRATEGY.md`. Прочитай обнаруженный AGENTS.md. Центральные файлы — обязательные контракты, не справочная рекомендация.

## Задача

**AUTH-001: Приглашения, пароли и bootstrap Admin**. Phase B1, Epic Авторизация, priority Critical, complexity M.
Предпосылки: DB-004; gate **G2**. Проверь их реализацию и отчёты; не предполагай готовность по названию папки. На момент исходного проектирования приложение отсутствовало.

## Область изменений

backend/app/identity/service.py; backend/app/identity/schemas.py; infra/scripts/bootstrap_admin. Также относящиеся tests/fixtures и `docs/reports/AUTH-001.md`. Не делай рефакторинг несвязанных модулей.

## Ограничения

Сохраняй immutable originals и evidence; Decimal без float; unknown≠0; current≠latest fetched; private history owner-only. LLM не считает тарифы и не генерирует URLs/pages/dates. Provider не выбран, Fake используется до отдельного решения. Не добавляй vector DB, Kafka, Kubernetes, agent framework. Нельзя обходить защиту банков или отправлять сообщения/email. При изменении центрального контракта подготовь ADR и укажи affected tasks.

## Реализация

Контракт: Invite/reset DTO и tables, Argon2id policy SECURITY.

1. **AUTH-001.01** — Bootstrap admin с одноразовой CLI процедурой без stored default password.
2. **AUTH-001.02** — Создать invitation random256/hash/48h и consume transaction.
3. **AUTH-001.03** — Реализовать Argon2id hash/verify/calibration и password validation.
4. **AUTH-001.04** — Reset token30min через Admin, consume once, revoke sessions; ссылки возвращать однократно без email sending.

Ошибки и границы: Expired/reused token denied; enumeration generic; no secret in log; last active admin protected.

## Тестирование

Concurrent consume, bad/expired token, strong hash verify, secret log canary, password reset revocation.

Проверь реальные результаты, зафиксируй команды и versions/fixtures; не выдавай непроведённую проверку за pass. Live API без согласованного provider/policy не вызывай.

## Acceptance Criteria

Только invite registration; token raw не в DB; no public signup. Выполни также общий DoD из ТЗ задачи. Если предпосылка отсутствует, укажи конкретный blocker; выполняй только независимую разрешённую часть, не симулируй production dependency.

## Отчёт

Верни список файлов, реализованное поведение, команды и результаты проверок, доказательства каждого AC, limitations и неустранённые проблемы. Сохрани `docs/reports/AUTH-001.md`. Обнови статус в MASTER_PLAN и TASK_INDEX; DONE только после AC. При возможности отдельный commit в project-local Git, без родительских изменений. Не начинай следующую задачу без проверки её gate и scope текущего поручения.
