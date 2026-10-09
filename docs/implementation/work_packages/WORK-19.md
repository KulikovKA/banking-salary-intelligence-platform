# WORK-19 — Сквозная приёмка и нагрузка 30 пользователей

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **High**. Status: **TODO**.

Почему этот уровень: Проверка взаимодействия модулей и измерение узких мест; недоказанные показатели не считать pass.

Dependencies: [WORK-13](WORK-13.md), [WORK-18](WORK-18.md)

Gates входящих этапов: G2. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-19.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## QA-003 — Сквозная приёмка функционального MVP

Reasoning: **High**. [Полное ТЗ](../tasks/QA-003.md).

Контракт: USER_SCENARIOS U01–U12, TEST_STRATEGY, G3/G4.

1. Прогнать invite→question→comparison→original→followup→history→delete.
2. Прогнать ingest→review→publication→event→subscription notification.
3. Внедрить source outage/LLM timeout/network reconnect/partial parse/concurrent review.
4. Сверить all R01–R17 coverage, документировать Fake vs real capabilities и gaps.

Ошибки: Любое invented number/cross-user/dangling source blocker; real API absent не скрывать mock label.

Проверки: Browser/API/DB integration все U scenarios; frozen fixtures and deterministic Fake; real smoke separate if selected.

Критерий: Сквозные P0 scenarios green; evidence/report воспроизводим, skips обоснованы.

## LOAD-001 — Нагрузка 30 пользователей и пределы ресурсов

Reasoning: **High**. [Полное ТЗ](../tasks/LOAD-001.md).

Контракт: 30 concurrent sessions, max5 provider calls, target latency OPERATIONS/REQUIREMENTS.

1. Подготовить100k chunks corpus с корректными IDs, смешать search/compare/chat/read/ingest.
2. Прогреть затем измерить30min steady +burst30 submissions и slow provider.
3. Записать p50/p95/error/queue/db connections/CPU/RAM/disk и query plans.
4. Устранить конкретные bottlenecks без нового сервиса, повторить затронутый сценарий.

Ошибки: Queue full возвращает429/Retry-After; no silent dropped answer; Fake latency test не доказывает real provider SLA.

Проверки: p95 API<500ms/search-comparison<1s, deadline45s либо explicit fallback; caps hold; soak memory stable.

Критерий: Цели достигнуты на указанном host либо честно отмечены ограничения для решения пользователя.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-19.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
