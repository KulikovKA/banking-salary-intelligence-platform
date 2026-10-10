# ADR-007 — фиксированный корпус и минимальный модульный монолит

Дата: 10.10.2026. Статус: выбран для исполнения по явному поручению владельца
в этой итерации. Это решение об архитектуре; разрешений на банковские источники
и PASS каких-либо data gates оно не выдаёт.

Контекст: работающий source recovery уже есть, однако старый план делает auth/UI
зависимыми от реального G2 и проектирует постоянный мониторинг до работающего
ассистента. Текущая цель — snapshot из официальных документов четырёх банков.

Решение: FastAPI + PostgreSQL + Next.js; local BlobStore; операторский ingestion
и последовательная обработка; evidence-first facts и детерминированное сравнение;
основная модель `openai/gpt-oss-120b` в GroqCloud Free с Fake в тестах.
Scheduler, recurring acquisition, изменения/уведомления и outbox отложены.
Альтернативы: прежний monitoring MVP — лишний critical path; только шаблонный бот —
полезный fallback, но не выполняет требование реального LLM ассистента.

Предыдущие [ADR](https://github.com/KulikovKA/banking-salary-intelligence-platform/blob/02cd6c8e00e9f84c0528460c7a42835f95a41499/docs/archive/pre-snapshot/architecture/ADR/README.md) сохраняются
неизменными по смыслу, включая исторические proposed/accepted статусы.
ADR-001/002/003/005: переносим принципы provenance, временной применимости,
constrained claims и originals вне БД в активные контракты, без переноса outbox
и полной bitemporal платформы. ADR-004: jobs/outbox вне активного scope, существующие
physical audit data сохраняются в БД, queue helper/runtime ORM удалены. ADR-006: source-specific approval, offline egress ban,
отдельный manual grant, corpus isolation сохраняются. Его WORK-зависимости заменены
новым SNAP DAG; исторические G1/G2 не пройдены и не переименованы в PASS.

Последствия: меньше инфраструктуры и задач; асинхронный import UI/OCR не обещаем.
Работа с synthetic проходит S0, реальная полнота/качество — S1/S2, а authenticated
Groq UI — S3. Недостаток документов возвращает NO-GO четырёхбанковского продукта,
при этом разрешает продолжать независимую разработку.

Миграция: только добавочные Alembic revisions, старые originals/tests/migrations
не удалять. Legacy DB objects не управляют frozen snapshot; stale/worker config удалена. Откат —
возврат планирования, а не ослабление policy/evidence checks. Verification:
docs validator, существующие backend/frontend/PG/E2E и отдельные SNAP acceptance
tests по мере реализации. [Разделение веток](../../reports/MAIN-CLEANUP-2026-10-10.md).
