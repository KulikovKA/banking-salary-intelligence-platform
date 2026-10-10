# WORK-14 — Логи, метрики и эксплуатационный аудит

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **Medium**. Status: **TODO**.

Почему этот уровень: Фиксированный набор метрик и событий; секреты и пользовательский текст в логах запрещены.

Dependencies: [WORK-12](WORK-12.md)

Gates входящих этапов: G2. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-14.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## OPS-001 — Структурированные логи, метрики и аудит

Reasoning: **Medium**. [Полное ТЗ](../tasks/OPS-001.md).

Контракт: OPERATIONS log fields/metrics/alerts; append-only audit schema.

1. Добавить request/job correlation IDs и sanitized structured logging.
2. Собирать queue/latency/freshness/evidence/LLM budget/storage/backup metrics.
3. Audit для login failures/roles/source policy/review/publication, no payload text.
4. Админ summary с thresholds и отделённой internal readiness.

Ошибки: Logging sink failure не раскрывает payload; metrics label cardinality bounded; secrets redacted.

Проверки: Synthetic key/email in failure paths absent logs, audit immutability, health DB down503, coverage counts.

Критерий: Операционные сбои диагностируемы без чтения персональных сообщений.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-14.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
