# WORK-15 — Проверка авторизации, SSRF и prompt injection

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **Extra High**. Status: **TODO**.

Почему этот уровень: Нужны adversarial сценарии, анализ обходов и проверка отсутствия запрещённых эффектов.

Dependencies: [WORK-11](WORK-11.md), [WORK-13](WORK-13.md), [WORK-14](WORK-14.md)

Gates входящих этапов: G2. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-15.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## SEC-001 — Матрица авторизации и adversarial API тесты

Reasoning: **Extra High**. [Полное ТЗ](../tasks/SEC-001.md).

Контракт: Каждый endpoint API_CONTRACTS × anonymous/userA/userB/analyst/admin/disabled.

1. Создать fixtures разных владельцев и additive roles.
2. Проверить list/read/write/delete/poll/file/download и session revoke.
3. Проверить CSRF/session fixation/rate limits/last-admin и invite races.
4. Исправлять обнаруженные defects в owning module с regression test, сохранить evidence отчёта.

Ошибки: Любой cross-user exposure Critical и release block; skipped route считается gap.

Проверки: Полная автоматически сверенная endpoint inventory matrix и browser auth сценарии.

Критерий: Нет неизвестных или непроверенных routes; все prohibited accesses отвергнуты.

## SEC-002 — SSRF, prompt injection и вредоносные документы

Reasoning: **Extra High**. [Полное ТЗ](../tasks/SEC-002.md).

Контракт: Threat matrix SECURITY и typed tool/claim boundaries.

1. Создать malicious HTML/PDF/footnote fixtures и fake DNS/redirect transport.
2. Проверить actual peer IP policy, IPv6/local/private/metadata, dangerous subresources.
3. Проверить source instructions не меняют tools/output и не exfiltrate.
4. Проверить XSS escaped snippets, unsafe links, parser memory/time quotas и safe fallback.

Ошибки: Нельзя выдавать clean bill только по system prompt; sandbox escape/SSRF/invented claim release blocker.

Проверки: Injection asks secrets, hidden text, fake citations, malicious URL, decompression/timeout tests; verify zero forbidden side effects.

Критерий: Весь attack suite без запрещённых effects; high issues устранены.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-15.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
