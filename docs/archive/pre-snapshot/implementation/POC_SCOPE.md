# Stage A — POC

Цель: доказать доступность и достаточность официальных данных, их воспроизводимое извлечение и возможность честного сравнения с открываемыми оригиналами до вложений в полный сайт.

## Execution modes and evidence

Offline POC development is admitted under G0-OFFLINE using explicitly marked synthetic fixtures. Offline/test/CI forbids external ingestion requests, including redirects, subresources, parser workers, and browser workers. The synthetic corpus is isolated in a test namespace/storage/database; production manifests and publication reject synthetic provenance. Synthetic tariff values are never bank facts.

G0-LIVE(source) is required before any automated request to an exact host/path. SRC-001 records the decision on acquisition, storage, and reuse before retrieval. Retrieved content then receives a separate content/evidence review. Manual import requires a separate provenance/storage/reuse decision and never counts toward G1. An offline checkpoint does not complete its WORK block or pass G1/G2.

## Входит

- Четыре банка, официальный approved source manifest с provenance и отдельным решением допустимости сбора.
- Один локальный пользователь без публичного доступа, POC routes bind loopback. Actor ручной проверки — фиксированный local analyst с actor_type=human, до создания production users reviewer_id nullable и reviewer label в review reason; это не production authentication.
- Неизменяемые оригиналы, byte/canonical/parser versions, text страницы/sections и связанные сноски.
- Нормализация, ручное одобрение числовых facts, publication revision и scope/date selection.
- PostgreSQL FTS, детерминированные сравнения, evidence обеих сторон, full PDF page link.
- Fake LLM Protocol, typed intent/explanation и безопасные шаблоны фактических утверждений.
- Один экран вопроса, таблицы и источников. История в браузере только временная; persistent personal chats — MVP.
- Проверка источников G1 и качества ядра G2 с реальными документами и holdout.

## Пределы API POC

`/poc/questions` синхронный, localhost-only и полностью отсутствует в production. Shared `/api/v1/search`, `/comparisons`, `/documents` используют тот же контракт DTO и injectable Principal. До DB-004 POC comparison result не сохраняется как пользовательский comparison_run; ID эфемерный, GET persisted comparison не включён. Это явное ограничение POC, не альтернативная MVP schema.

POC approval CLI вызывает тот же FactValidator/PublicationService, который позднее использует Analyst REST. Никаких прямых SQL UPDATE approved без validation. Изменения publication пока не доставляют уведомления; DB-005 и CHG-001 включают events/outbox для последующих публикаций. Первоначальные facts при переходе становятся baseline и не порождают искусственную ленту изменений.

## Не входит

Полный кабинет, invite registration, сохранённые личные чаты, внешние уведомления, реальный provider по умолчанию, OCR production, private contracts, HA инфраструктура. Инфраструктурные security меры fetch/parser обязательны уже в POC: loopback не защищает от SSRF к внутренним ресурсам.

## Условия остановки и передачи в MVP

G1: не удалось стабильно получить условия одного банка или решение по сбору отсутствует → отчёт NO-GO и решение пользователя о scope. G2: insufficient evidence/coverage или ошибки вычислений → исправление ядра, не строительство остальных UI экранов. Не «подгонять» тарифы и не смешивать public individual с реальной договорной ценой.

Успешная передача: G1/G2 отчёты приняты, corpus manifest/gold/revision воспроизводимы, schema/data могут мигрировать без очистки, backlog B1–B4 становится доступен после пользовательского разрешения этапа.
