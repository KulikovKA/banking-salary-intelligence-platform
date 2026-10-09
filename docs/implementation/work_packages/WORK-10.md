# WORK-10 — Пользователи, приглашения, сессии и права доступа

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **High**. Status: **TODO**.

Почему этот уровень: Безопасность сессий и владения объектами; сложные обходы доступа проверяются позже на Extra High.

Dependencies: [WORK-06](WORK-06.md), [WORK-08](WORK-08.md), [WORK-09](WORK-09.md)

Gates входящих этапов: G2. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-10.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## DB-004 — Миграции auth, чатов, usage и idempotency

Reasoning: **High**. [Полное ТЗ](../tasks/DB-004.md).

Контракт: users/roles/user_roles/invites/auth_sessions/password_reset_tokens/chat*/answer*/comparison_runs/llm_usage/api_idempotency/rate_limit_buckets.

1. Создать таблицы и ownership FK, role seeds без default password.
2. Создать one-active-answer partial unique и per-session idempotency.
3. Добавить answer evidence/chunk refs и deletion/SET NULL semantics.
4. Проверить миграцию populated POC database и backup-before-upgrade instructions.

Ошибки: Duplicate emails normalize; не вводить ownership nullable в production; delete chat не удаляет shared evidence.

Проверки: Cross FK, two active runs conflict, same key different request hash detection, cascade only own chat artifacts.

Критерий: POC facts сохраняются; schema поддерживает auth/async chats без дублирования originals.

## AUTH-001 — Приглашения, пароли и bootstrap Admin

Reasoning: **High**. [Полное ТЗ](../tasks/AUTH-001.md).

Контракт: Invite/reset DTO и tables, Argon2id policy SECURITY.

1. Bootstrap admin с одноразовой CLI процедурой без stored default password.
2. Создать invitation random256/hash/48h и consume transaction.
3. Реализовать Argon2id hash/verify/calibration и password validation.
4. Reset token30min через Admin, consume once, revoke sessions; ссылки возвращать однократно без email sending.

Ошибки: Expired/reused token denied; enumeration generic; no secret in log; last active admin protected.

Проверки: Concurrent consume, bad/expired token, strong hash verify, secret log canary, password reset revocation.

Критерий: Только invite registration; token raw не в DB; no public signup.

## AUTH-002 — Сессии, CSRF и лимиты входа

Reasoning: **High**. [Полное ТЗ](../tasks/AUTH-002.md).

Контракт: Login/logout/me, __Host-session, CSRF/Origin, idle8h/absolute24h.

1. Создать opaque session token/hash, rotation/revocation/expiry.
2. Установить Secure/HttpOnly/SameSite cookie и csrf validation.
3. Добавить account/IP rate buckets и generic login errors.
4. Проверить trusted proxy headers, disabled user и role change session revocation.

Ошибки: Cookie missing/expired401; foreign Origin403; bad credentials одинаковый ответ; bucket DB error fail closed for login.

Проверки: Session fixation, CSRF, Origin bypass, expiry frozen clock, brute force429, logout reuse, disabled user.

Критерий: Закрытые endpoints не доступны без session; cookies и limits соответствуют контракту.

## AUTH-003 — RBAC и object ownership во всех сервисах

Reasoning: **High**. [Полное ТЗ](../tasks/AUTH-003.md).

Контракт: Principal + additive user/analyst/admin roles, ownership API_CONTRACTS.

1. Заменить POC principal production dependency на session auth.
2. Применить permission matrix к routes/services, включая streaming/poll/list.
3. Не давать Admin ownership bypass на чаты; analyst approval отдельно от admin.
4. Добавить endpoint inventory test, POC routes выключены production.

Ошибки: Foreign object404; role forbidden403; revoked session401; забытый endpoint считается test failure.

Проверки: Все роли×методы, guessed UUID, foreign content/poll/list/delete; Admin без analyst не approve.

Критерий: Authorization enforced backend на каждом endpoint; UI checks не единственная защита.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-10.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
