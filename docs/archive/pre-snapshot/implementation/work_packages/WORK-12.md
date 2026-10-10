# WORK-12 — Мониторинг изменений, уведомления и полный API

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **High**. Status: **TODO**.

Почему этот уровень: Транзакционные события, future activation, дедупликация и согласованность REST контрактов.

Dependencies: [WORK-03](WORK-03.md), [WORK-06](WORK-06.md), [WORK-10](WORK-10.md), [WORK-11](WORK-11.md)

Gates входящих этапов: G2. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-12.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## DB-005 — Миграции событий, outbox, подписок и аудита

Reasoning: **High**. [Полное ТЗ](../tasks/DB-005.md).

Контракт: change_events/outbox_events/subscriptions/notifications/audit_logs/source_health_observations.

1. Создать events old/new facts и typed kind/dedup key.
2. Создать outbox delivery leases и unique user/event/channel.
3. Добавить indexes bank/date и user/unread, append-only audit privileges.
4. Проверить forward migration existing corpus, без генерации спама baseline.

Ошибки: FK loss запрещена; replay events unique; migration не создаёт fake historic change timestamps.

Проверки: Unique notification race, audit update denied app role, upgrade existing facts, baseline no mass events.

Критерий: Schema обеспечивает transactional event creation и повторяемую доставку.

## CHG-001 — Содержательный diff и активация будущих условий

Reasoning: **High**. [Полное ТЗ](../tasks/CHG-001.md).

Контракт: ChangeEvent kind/dedup/effective_at vs detected_at; DATA_FLOW.

1. Сравнивать published facts по semantic key/scope и normalized value/conditions/dates.
2. Включить events+outbox в ту же publication transaction.
3. Отделить baseline, announced/activated, correction и unclassified document change.
4. Добавить scheduled activation unique event при наступлении даты и ревокацию с review reason.

Ошибки: Исчезновение строки не withdrawn без evidence; raw-only diff не тарифное событие; future condition не current.

Проверки: Cosmetic change, footnote change, same rate new condition, future activation twice, parser fix, partial parsing disappearance.

Критерий: Tariff events только подтверждённые; repeated worker не дублирует activation.

## NTF-001 — Подписки и идемпотентные уведомления внутри сайта

Reasoning: **High**. [Полное ТЗ](../tasks/NTF-001.md).

Контракт: Subscription filters bank/metric, notifications own-only, channel=in_app.

1. Создать owned CRUD subscriptions с canonical filter hash.
2. Outbox worker выбирает committed events, применяет filters и inserts on conflict do nothing.
3. Read/unread notifications, cursor stable, baseline suppressed.
4. Retry failed delivery с leases и metrics; не отправлять email/SMS.

Ошибки: Crash after insert before ack не создаёт дубль; disabled subscription не получает новые события; чужой notification404.

Проверки: Duplicate subscriptions, outbox retry/kill, same user multiple filters, unsubscribe race documented, ownership.

Критерий: Один event максимум одна карточка пользователю; внешних отправок нет.

## JOB-002 — Диагностика парсеров и freshness

Reasoning: **High**. [Полное ТЗ](../tasks/JOB-002.md).

Контракт: SourceHealth observations last_check/successful_fetch/parse/review age separately.

1. Записывать HTTP/parse/coverage health и count/ratio drift по adapter.
2. Вычислять stale72h отдельно от effective dates, показывать last-known-good.
3. Создать recheck action с idempotency и bounded jobs; retired source не стирает facts.
4. Добавить alert states3 failures/72h/review2days/disk thresholds.

Ошибки: HTTP200 с пустым extraction unhealthy; source block не tight retry; stale label не меняет historic evidence.

Проверки: Frozen clock staleness boundary, count drop, failed parse with fetched bytes, recheck spam dedup.

Критерий: Admin отличает доступность источника от успешной обработки; freshness доступна UI.

## API-002 — REST MVP: review, администрация и сводки

Reasoning: **High**. [Полное ТЗ](../tasks/API-002.md).

Контракт: Полная endpoint matrix API_CONTRACTS, error/pagination/version/idempotency contracts.

1. Подключить remaining endpoints dashboard/facts/changes/review/admin users/sources/jobs.
2. Review route использует existing service и actor from Principal; source mutations require policy.
3. Обновить generated OpenAPI types и API client error mapping.
4. Проверить no route bypass, unsupported query fields и size limits.

Ошибки: Concurrent review/source edits409; dangerous URL422; stats queries не выдают чужие chat metadata.

Проверки: OpenAPI contract snapshots, role matrix, pagination ties, idempotency conflict, malformed filters.

Критерий: Все заявленные MVP endpoints существуют и авторизованы; frontend types генерируются из одной схемы.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-12.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
