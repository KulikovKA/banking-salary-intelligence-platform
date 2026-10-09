# WORK-03 — Архив, безопасная загрузка и фоновые задания

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **Extra High**. Status: **TODO**.

Почему этот уровень: Согласованность файлов и БД, SSRF, гонки leases и восстановление после сбоя.



[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-03.md).

Dependencies: Offline checkpoint dependency: WORK-02 offline checkpoint.
Offline checkpoint gate: G0-OFFLINE. Full acceptance retains original AC and applicable live/G1/G2 requirements.

## Execution mode under ADR-006

**Mode:** offline checkpoint under G0-OFFLINE; all live work requires exact source G0-LIVE and original acceptance gates.

Offline work uses local data or explicitly synthetic fixtures only. External ingestion requests are forbidden, including redirects, subresources, parser workers, and browser renderers. Synthetic provenance is isolated from real manifests and publication. A checkpoint marked DONE does not make this WORK DONE or satisfy G1/G2. Preserve every original acceptance criterion.




## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## STO-001 — Неизменяемое файловое хранилище оригиналов

Reasoning: **Extra High**. [Полное ТЗ](../tasks/STO-001.md).

Контракт: BlobStore.put(stream)->BlobReceipt{id,sha256,size,type}; open(blob_id)->stream.

1. Потоково писать temp в том же volume, ограничить размер и hash bytes.
2. Выполнить fsync/atomic rename, затем зарегистрировать blob в БД; reuse digest.
3. Разрешать чтение только через DB key, не path от пользователя.
4. Сделать read-only reconciliation report missing/orphan; cleanup только orphan старше7дней без ссылок.

Ошибки: Disk full/kill/invalid MIME не создаёт published metadata; path traversal и symlink escape reject; racing same hash безопасен.

Проверки: Roundtrip binary hash; concurrent identical put; injected write/rename/commit failure; traversal; reconciliation missing referenced blob.

Критерий: Оригинал никогда не перезаписывается; race даёт один blob; ни один committed ref не указывает на partial file.

## NET-001 — Безопасный FetchGateway с условными запросами

Reasoning: **Extra High**. [Полное ТЗ](../tasks/NET-001.md).

Контракт: ApprovedUrl+ConditionalHeaders -> FetchResult{status,headers,redirects,blob?,error}.

1. Проверять scheme/host/userinfo/port/DNS и реальный peer IP каждого redirect.
2. Применить size50MiB/timeouts/redirect5/per-host concurrency1 и policy rate.
3. Обработать ETag/Last-Modified, 304 только при cached blob; MIME/HTML markers.
4. Сохранять каждую observation и error code; transient retry отдавать scheduler через retry_at.

Ошибки: 429 учитывает Retry-After; 403/CAPTCHA blocked без bypass; HTML error200 не становится PDF; не читать internal IP.

Проверки: Mock HTTP 200/304/404/429/500/timeouts/oversize/wrong MIME; redirect→localhost/IPv6/metadata; cache missing304.

Критерий: Ни один forbidden destination не получает запрос; observation сохранены; repeat304 не дублирует version.

## JOB-001 — Cron enqueue, leases и повтор фоновых задач

Reasoning: **Extra High**. [Полное ТЗ](../tasks/JOB-001.md).

Контракт: JobRun state machine DATA_FLOW; unique scheduled_slot, lease_token, heartbeat, retry_at.

1. enqueue_due транзакционно фиксирует slot и next_check_at.
2. Claim SKIP LOCKED, commit до сети, heartbeat30s/lease180s.
3. Выполнить dispatch по type и проверять fencing token при каждом commit результата.
4. Retry 3 attempts с backoff/jitter; expired lease requeue; deterministic failure blocked до изменения входа.

Ошибки: Два scheduler/worker не выполняют одну публикацию; старый worker после lease expiry не пишет; process crash оставляет recoverable job.

Проверки: Два DB connections claim race; frozen clock expiry; kill worker; Retry-After cap; duplicate enqueue; no sleeping transaction.

Критерий: Повтор запуска не создаёт duplicate jobs; истёкшая lease восстанавливается; all transitions проверены.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-03.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
