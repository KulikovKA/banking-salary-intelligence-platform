# WORK-18 — Backup, восстановление и production-развёртывание

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **High**. Status: **TODO**.

Почему этот уровень: Согласованность DB/blob backup, миграции и проверенный rollback; сбои целостности расследовать на Extra High.

Dependencies: [WORK-03](WORK-03.md), [WORK-14](WORK-14.md), [WORK-15](WORK-15.md), [WORK-16](WORK-16.md)

Gates входящих этапов: G2. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-18.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## OPS-002 — Согласованные backup и восстановление

Reasoning: **High**. [Полное ТЗ](../tasks/OPS-002.md).

Контракт: RPO24h/RTO4h proposed и OPERATIONS paired DB/blob manifest.

1. Создать backup под maintenance barrier публикаций, DB dump+blob manifest+checksums.
2. Шифровать и переносить в отдельное approved storage в РФ, rotate≤30days.
3. Восстановить isolated DB/storage, проверить100% referenced hashes и schema.
4. Применить deletion tombstones до открытия доступа, измерить recovery time, описать runbook.

Ошибки: Missing key/blob/failed checksum →restore NOT READY; копия на том же диске не считается backup.

Проверки: Restore populated chats/facts/events; intentionally missing blob; deletion before restore; encrypted backup access; timings.

Критерий: Восстановление действительно выполнено, RPO/RTO измерены и evidence цело.

## OPS-003 — Production Compose, миграции и rollback rehearsal

Reasoning: **High**. [Полное ТЗ](../tasks/OPS-003.md).

Контракт: OPERATIONS topology, pinned images, no public DB, single migration runner.

1. Собрать production profiles proxy/frontend/api/workers/scheduler/db и storage permissions.
2. Readiness/health, resource limits, secrets, nonroot и TLS config.
3. Прогнать upgrade populated DB с one-shot migration lock и smoke.
4. Проверить compatible code rollback и аварийный restore путь, записать exact commands.

Ошибки: Migration fail не запускает incompatible API; missing secret startup fail; fake identity forbidden prod.

Проверки: Clean deploy, host restart jobs recover, upgrade+rollback, public port scan, archive RO API, schema readiness.

Критерий: Развёртывание воспроизводимо без потери данных; rollback проверен на staging.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-18.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
