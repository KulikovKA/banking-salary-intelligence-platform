# Развёртывание и эксплуатация

## Предложенная топология

Docker Compose на одном Linux host: `proxy` (Caddy), `frontend` (Next.js production), `api`, `worker-ingest`, `worker-assistant`, `scheduler`, `db`, одноразовый `migrate`, периодический `backup`. Все Python процессы из одного pinned image. Раздельные worker процессы предотвращают блокирование вопросов долгим PDF. Это один кодовый продукт, без брокера/Redis.

Публичные порты только 443 и при необходимости 80 для ACME redirect; DB наружу не публикуется. API и Next.js внутри bridge network. Ingest storage volume RW, API read-only; DB volume отдельно. Nonroot, read_only rootfs где возможно, tmpfs для temp, no Docker socket. Health checks и restart unless-stopped. Для POC ports bind 127.0.0.1, fake identity невозможна при APP_ENV=production.

Начальный sizing для замера, не обещание: 4 vCPU, 8 GiB RAM, 100 GiB SSD. Parser subprocess лимит 1GiB/120s/1000 pages; превышение → manual_review. API pool 5+5 overflow, два workers pools по 3, суммарно <40 DB connections. Одновременно 1 PDF parse и 5 LLM calls, очереди ограничены (max20 активных/ожидающих answers); остальным 429/Retry-After. Скорректировать по LOAD-001.

## Config contract

Validated Settings: APP_ENV, DATABASE_URL secret, STORAGE_ROOT, PUBLIC_BASE_URL, SESSION settings, SOURCE_MAX_BYTES=52428800, FETCH timeouts, WORKER_LEASE_SECONDS=180, HEARTBEAT_SECONDS=30, MAX_JOB_ATTEMPTS=3, SOURCE_STALE_HOURS=72, LLM_MODE=fake|provider, LLM_MODEL optional, LLM_API_BASE allowlisted, LLM_API_KEY secret, LLM_BUDGET settings, RETENTION days. В production обязательны TLS origin, secure cookies, auth enabled; fake identity запрещён, fake LLM разрешён только с видимой отметкой. Провайдерская модель не имеет default.

## Наблюдаемость

Structured JSON logs: timestamp, level, event_code, request_id, job_id, source_id, duration_ms, error_code. Не логировать raw URLs с query secrets, cookie, content, prompt или password. Метрики: fetch_success_ratio отдельно parse_success_ratio; source_age_seconds; review_pending_age; job queue/lease expired; corpus_revision; evidence_missing_count; invalid_claim_output_count; llm calls/tokens/reservations/timeouts; API p95; blob disk free; backup_age и restore test date.

Proposed alerts: source stale >72h; 3 подряд failed jobs; review старше 2 рабочих дней; backup >26h; free disk <20% warning/<10% stop ingest; любой missing published blob critical; any cross-user test failure release blocker. Alerts MVP — admin dashboard и host monitoring hook; не обещать email/Slack без отдельной интеграции. Daily operator checklist охватывает источники четырёх банков, очередь review, backup и бюджеты.

## Backup / restore

Цели: RPO ≤24h, RTO ≤4h. Daily logical PostgreSQL dump + blob manifest/checksums + конфиги без открытых secrets, шифрование backup и отдельное хранилище в РФ. Нельзя считать копию на том же SSD резервной.

Согласованность: остановить публикации/ingest на время фиксации DB snapshot и blob manifest (чат может продолжать работу, если выбран dump snapshot consistent). Сначала immutable blobs до manifest watermark, затем DB snapshot с соответствующими refs; проще для MVP короткое maintenance window и согласованная пара. Зафиксировать manifest generation и corpus revision. Restore в изолированную среду: DB+blobs, FK/schema validation, 100% referenced blob existence/hash, deletion tombstones, smoke queries, затем открыть доступ. Новые blobs после dump могут быть лишними, пропавших ссылочных blobs быть не должно.

Backup retention proposed: 7 daily +4 weekly, максимальный срок персональных backup 30 дней. Точную ротацию согласовать так, чтобы weekly не переживали 30 дней. Ключ расшифрования отдельно. Раз в месяц restore rehearsal, перед release — обязательный успешный.

## Deploy / rollback

CI: format/lint/type/unit → PostgreSQL integration → OpenAPI compatibility → build images → E2E fixtures. Tags immutable, зависимости lockfile, vulnerability/license report. Production deployment после gates: backup, maintenance если нужны incompatible changes, migration one-shot с DB lock, readiness, smoke, переключение traffic. Rollback code разрешён только при backward-compatible schema; destructive downgrade не запускать. Восстановление новой БД из backup и проверка evidence — отдельный аварийный сценарий с измеренными RPO/RTO.

## Runbooks

- Банк недоступен: оставить last-known-good, отметить stale, изучить status без обхода защиты, next scheduled retry; не удалять facts.
- HTML layout drift: отключить auto-publish данного adapter version, сохранить bytes, завести новую fixture, исправить parser, reprocess, review diff.
- PDF broken: сохранить fetch audit, не индексировать garbage; показать ошибку admin и предыдущую публикацию.
- LLM outage/quota: template fallback, provider circuit-open на 60s после 3 transient ошибок; source workers продолжают работу.
- DB down: API 503, никакой фиктивной успешной записи; jobs retry после восстановления.
- Disk full: stop new ingest, сохранить работоспособность read API, проверить retention, не удалять evidence вручную.
- Ошибочно одобренный тариф: revoke новой публикацией, invalidation corpus cache, corrective event; старые ответы сохраняют дату и метку отозванного evidence.
