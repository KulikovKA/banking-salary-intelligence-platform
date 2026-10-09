# Потоки и state machines

## 1. Получение и публикация

1. cron раз в минуту вызывает enqueue_due. В короткой транзакции берутся источники с next_check_at ≤ now; unique `(source_id, scheduled_slot)` защищает от повторного cron. Следующий slot фиксируется транзакционно.
2. Worker выбирает due job через `FOR UPDATE SKIP LOCKED`, назначает lease_token и lease_until, commit. Сеть и parsing выполняются вне транзакции.
3. Fetch проверяет approved host, каждый redirect и DNS/IP, TLS, лимит 50 MiB, таймаут connect 10s/read 30s/общий 90s. По host максимум один активный запрос; начальная пауза 2s, уточнить source policy. Не более 5 redirect. HEAD не считается доказательством доступного документа.
4. 304 допустим только при наличии проверенного cached blob. Без него повторить unconditional GET. 200 с login/CAPTCHA/неожиданной страницей — source_blocked, не новая редакция.
5. Записать bytes в temp на том же volume, считать SHA-256, fsync, atomic rename в `sha256/aa/bb/<digest>`. Сохранить receipt. БД commit ссылается только на существующий blob. Одинаковые bytes переиспользуются.
6. Каждый fetch создаёт observation. Новый raw hash создаёт immutable source_version; одинаковый hash — только observation. Это не автоматически новая деловая редакция.
7. Extraction key `(source_version_id, parser_name, parser_version, config_hash)` уникален. Raw HTML остаётся неизменным; rendered DOM отдельный artifact. Canonical text игнорирует только разрешённые chrome-узлы, сохраняет числа, даты, отрицания, таблицы и сноски.
8. PDF извлекается физически постранично. Пустой/изображение-only PDF → needs_ocr, ручная обработка вне автоматического publish. Плохая таблица → review с исходной страницей.
9. Candidates сохраняются со всеми uncertainty flags. Validator проверяет Decimal, единицы, контекст, диапазоны, evidence coverage и даты. LLM не нужен для parsing.
10. В POC все числовые факты проверяет аналитик. В MVP автоматическое approval допустимо только для конкретного правила/шаблона после gold tests; новое правило, неоднозначные даты, сноски, conflicts всегда review.
11. Approval не равен publish: PublicationService под блокировкой corpus_state заново проверяет целостность и текущую ревизию. Одной транзакцией добавляет membership публикации, supersession в пределах точно указанного scope, event и outbox, повышает revision. SQL readers видят только завершённый commit.
12. Notification worker доставляет in-app уведомления по подпискам. Unique `(user_id, change_event_id, channel)` даёт exactly-once пользовательский эффект при at-least-once worker.

## Состояния

```text
job: queued -> running -> succeeded | retry_wait | failed | blocked
retry_wait -> running; running с expired lease -> retry_wait
fetch: fetched | not_modified | blocked | failed
extraction: pending -> running -> parsed | partial | needs_ocr | failed
fact: candidate -> pending_review -> approved | rejected
approved -> публикация membership; факт immutable
publication: committed (создаётся атомарно, наружу нет draft)
source availability: unknown | healthy | degraded | blocked | retired
answer: queued -> running -> completed | fallback | failed
```

Retired source не означает автоматическую отмену его условий. Revocation публикации — новое решение/событие с причиной, прежние записи доступны исторически.

## Retries и восстановление

Fetch 408/429/5xx/network: максимум 3 попытки на run, backoff 5s/30s/120s + jitter, Retry-After с cap 1h. Не держать worker спящим: retry_at в БД. 401/403/CAPTCHA → blocked без retry storm. 404 → review; повторная плановая проверка остаётся. Parser deterministic failure не гонять без изменения bytes/config. Disk full — не подтверждать job, alert и остановить ingest до освобождения места. Потерянный lease запрещает commit по fencing token, даже если старый worker закончил сеть.

Частичная запись chunks не становится active extraction. При завершении проверяются expected pages и completeness; pointer меняется атомарно. Cleanup удаляет только неприкреплённые temp/orphan artifacts старше 7 дней после сверки всех ссылок. Originals с provenance references автоматически не удаляются.

## 2. Semantic change detection

Ключ факта: bank + product/package + metric + payer/beneficiary + operation + geography + segment + organization category + contract variant + normalized applicability. Канонизация не превращает unknown в any. Значимые изменения: value/formula/unit/currency/conditions/effective range/evidence-backed withdrawal. Только title/date fetch/raw hash — технические события.

Первичная загрузка → baseline без спама о каждом тарифе. Будущая редакция → `announced`, не «уже действует». Наступление valid_from → отдельное `activated` с уникальным ключом. Изменение parser → `extraction_correction`, не банковское изменение. Исправление ранее опубликованной ошибки сохраняет old/new и ссылку на review. Текстовый diff без валидированного факта показывается аналитику как `document_changed_unclassified`.

## 3. Вопрос и память

HTTP принимает вопрос и idempotency key, проверяет owner. Фиксирует answer_run и user message одной транзакцией, возвращает 202. Worker ассистента использует отдельный тип job и приоритет, чтобы ingest не задерживал чат. UI polling 1–2s; streaming непроверенных утверждений в MVP отсутствует.

Context merge: explicit current question > confirmed structured session context > defaults RU-KDA/today. Сохраняются `focus_bank`, comparison_banks, metric codes, region, segment, package, as_of, scenario inputs. «А теперь с ВТБ» меняет comparator, сохраняет focus_bank. Если referent не единственный — clarification и context не портится. Смена даты на явное «сейчас» сбрасывает historical as_of.

Read snapshot: короткая REPEATABLE READ транзакция получает corpus_revision, facts, evidence и applicability; commit до LLM. В ответе сохраняются конкретные immutable IDs. Если corpus успел измениться — ответ честно относится к fetched revision, UI может предложить обновить. Никаких long transactions во время provider call.

Intent parser возвращает только типизированные фильтры; backend валидирует их и сам вызывает 1–5 read-only tools в фиксированном порядке, без произвольного agent loop. Сначала точные факты, затем FTS для доказательств/coverage. Для сравнения обязательны evidence обеих сторон. LLM получает уже вычисленные claims, может выбрать объяснение и порядок. Claim validator проверяет IDs, dependencies и допустимый template; renderer строит ответ, таблицу и document links. Invalid output → один safe fallback без второго LLM «судьи».

Сохранение assistant message, answer snapshot и context optimistic version выполняется транзакцией. На сессию один незавершённый вопрос; параллельный второй получает 409. Повтор первого ключа возвращает существующий run. Удаление сессии помечает running run cancelled, удаляет контекст/сообщения, commit worker после удаления запрещён.
