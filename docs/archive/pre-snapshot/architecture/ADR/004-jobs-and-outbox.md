# ADR-004 — Надёжные jobs и уведомления в PostgreSQL

Status: proposed. Date: 2026-10-09. Approval: пользователь G0.

Context: cron может стартовать повторно, worker упасть после commit, notification delivery повториться. Для 30 пользователей отдельный брокер не нужен.

Decision: cron только enqueue; worker claim через short transaction SKIP LOCKED, lease+heartbeat+fencing; retries через retry_at. Publication пишет event/outbox в одной транзакции. Notification delivery at-least-once, user effect dedup через unique key. Разделённые процессы ingest/assistant из одного image обеспечивают fairness.

Alternatives: cron выполняет всю загрузку — нет resume; Celery/Redis — дополнительная инфраструктура без доказанной необходимости; exactly-once network promise — некорректная гарантия. Выбран простой durable DB queue.

Consequences: мониторить queue/lease, ограничить connections, purge старые jobs по policy. Не держать DB locks во время сети/parsing/LLM. Добавление брокера только при measured queue pressure.

Affected: JOB-001/002, DB-001/005, AI-003, CHG-001, NTF-001, OPS-001/003. Tests: duplicate schedule, two workers, expired lease old worker, kill после notification insert, bounded retries. Migration: новые workers не забирают job payload неизвестной schema version; draining перед incompatible handler deploy.
