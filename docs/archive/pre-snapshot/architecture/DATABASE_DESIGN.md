# PostgreSQL: логическая и физическая спецификация

Это спецификация миграций, не выполненный DDL. PostgreSQL 18 — предложенная major version; pin patch/image digest в INF-001. UUID PK (приложение генерирует UUIDv4), timestamps timestamptz, effective dates date, денежные значения numeric, перечисления CHECK text для расширяемых статусов. Все FK indexed со стороны child. `created_at` server default now(); audit timestamps не меняются клиентом.

## Каталог и оригиналы

| Таблица | Поля и ограничения |
|---|---|
| banks | id PK, code UNIQUE NOT NULL, name NOT NULL, active bool |
| sources | id, bank_id FK, url NOT NULL, canonical_url, kind html/pdf/index/news, scope_hint JSONB, adapter_code/version, schedule_seconds >0, next_check_at, state, last_check_at, last_successful_check, last_successful_parse, policy_id FK; UNIQUE(bank_id,canonical_url); deactivate вместо delete |
| source_policies | id, bank_id, allowed_hosts JSONB exact host list, robots_checked_at, terms_url?, terms_checked_at, collection_decision approved/pending/denied, reviewer, reason, rate_seconds; изменения versioned новой строкой |
| source_fetches | id, source_id, job_run_id, requested_url, final_url, redirect_chain JSONB, fetched_at, http_status?, etag?, last_modified?, result, error_code?, source_version_id?; observation на каждую попытку |
| blobs | id, sha256 char(64) UNIQUE, byte_size bigint CHECK >0, media_type, storage_key UNIQUE, created_at, verified_at; immutable |
| source_versions | id, source_id, blob_id FK, first_seen_at, metadata JSONB; UNIQUE(source_id,blob_id); immutable; это версия bytes, не semantic current |
| documents | id, bank_id, family_key, title, product_code, document_kind tariff/product/news/manual, visibility public_internal, created_at; UNIQUE(bank_id,family_key) |
| document_versions | id, document_id, source_version_id, published_at?, declared_valid_from/to?, date_evidence JSONB, edition_label?, discovery_reason; UNIQUE(document_id,source_version_id) |
| extraction_runs | id, document_version_id, parser_name, parser_version, config_hash, state, canonical_sha256?, page_count?, expected_page_count?, quality JSONB, started_at, finished_at; UNIQUE(document_version_id,parser_name,parser_version,config_hash) |
| document_pages | id, extraction_run_id, physical_page integer >0, printed_label?, text, text_sha256, quality_flags JSONB; UNIQUE(extraction_run_id,physical_page) |
| document_chunks | id, extraction_run_id, page_id? FK, ordinal ≥0, section_label?, text NOT NULL, text_sha256, footnote_links JSONB, search_vector tsvector; UNIQUE(extraction_run_id,ordinal) |

Источник-индекс с несколькими PDF создаёт отдельные approved child sources; один документ может находиться по разным URL, связь сохраняется через document_versions. `family_key` назначает адаптер и подтверждает аналитик для спорного соответствия. Не сливать документы только по похожему названию. Blob dedup не устраняет provenance разных источников.

## Факты и публикации

| Таблица | Поля и ограничения |
|---|---|
| metric_definitions | code PK, value_kinds, unit, direction, required_inputs, schema_version; seed версионируется |
| tariff_facts | id, bank_id, extraction_run_id, metric_code FK, product_code, payer, operation, semantic_key, scope JSONB, value JSONB, conditions JSONB, conditions_text, valid_from/to?, effective_date_status, validation_state, extraction_method/version, flags JSONB, created_at; payload immutable после review |
| fact_evidence | id, fact_id, chunk_id, quote, quote_start/end?, role value/unit/condition/date/scope, created_at; UNIQUE(fact_id,chunk_id,role,quote_start); минимум один evidence проверяется publication transaction |
| fact_reviews | id, fact_id, decision approved/rejected/needs_changes, reviewer_id UUID nullable (FK добавляется DB-004), actor_type human/rule, rule_version?, reason, expected_fact_hash, created_at; append-only |
| corpus_state | id=1 CHECK, revision bigint ≥0; блокируется публикацией |
| publications | id, revision bigint UNIQUE, actor_id UUID nullable (FK добавляется DB-004), reason, created_at; только committed rows |
| publication_facts | publication_id, fact_id, action activate/revoke, reason; PK(publication_id,fact_id); разрешён только approved activate |
| fact_supersessions | id, publication_id, old_fact_id, new_fact_id?, scope JSONB, effective_from/to?, reason, evidence_review_id; old != new; scoped replacement, не глобальный flag |
| change_events | id, publication_id, bank_id, metric_code?, old_fact_id?, new_fact_id?, kind baseline/announced/activated/value_changed/conditions_changed/withdrawn/extraction_correction/document_changed_unclassified, detected_at, effective_at?, payload JSONB, dedup_key UNIQUE |
| outbox_events | id, event_type, aggregate_id, payload JSONB, created_at, delivered_at?, attempts, next_attempt_at, lease fields; dedup_key UNIQUE |

CHECK valid_to > valid_from когда обе известны. Структуру JSON проверяет Pydantic и DB checks на обязательные top-level поля/schema_version. SQL не хранит executable expression. Не ставить uniqueness только на semantic_key: conflicting observations нужны для review. Для идентичных кандидатов UNIQUE(extraction_run_id, semantic_key, payload_hash) с payload_hash NOT NULL; parent_fact_id nullable self-FK для исправленного кандидата, parent != id. Оба поля создаёт DB-003.

До DB-004 local POC human actor имеет reviewer_id/actor_id=null и явную метку в reason; не создавать несуществующий user UUID. DB-004 добавляет FK на users для reviewer_id/actor_id (ON DELETE SET NULL), проверяет существующие ненулевые ссылки и сохраняет исторические null. В production human review требует Principal и ненулевого действующего user ID на момент записи; rule actor — rule_version без выдуманного пользователя.

Current facts — запрос или view из publications, dates и supersessions, не изменяемый `is_current` на source_versions. Conflicts вычисляются для scenario. Для объяснимости публикация не уничтожает rejected candidates и историю решений.

## Пользователи и сессии

| Таблица | Поля и ограничения |
|---|---|
| users | id, email_normalized UNIQUE, password_hash, state invited/active/disabled, display_name?, created_at, password_changed_at |
| roles | code PK user/analyst/admin; permissions описаны SECURITY |
| user_roles | user_id, role_code; составной PK; admin не подразумевает analyst |
| invites | id, email_normalized, token_hash UNIQUE, role_codes, expires_at, consumed_at?, created_by FK; raw token не хранится |
| auth_sessions | id, user_id FK, token_hash UNIQUE, csrf_secret_hash, created_at, expires_at, last_seen_at, revoked_at? |
| password_reset_tokens | id, user_id, token_hash UNIQUE, expires_at, consumed_at; доставка администратором, не незапланированный email сервис |
| chat_sessions | id, owner_id FK, title, state active/deleting, version bigint, created_at, updated_at |
| chat_messages | id, session_id FK, sequence bigint, role user/assistant, text, answer_run_id?, created_at; UNIQUE(session_id,sequence) |
| chat_context | session_id PK/FK, schema_version, version, focus_bank?, context JSONB, updated_at |
| answer_runs | id, session_id FK, user_message_id FK?, idempotency_key, request_hash, state, corpus_revision?, data_as_of, context_version, response JSONB?, error_code?, created_at, finished_at; UNIQUE(session_id,idempotency_key) |
| answer_evidence | answer_run_id FK, evidence_id FK; PK pair; обеспечивает удержание evidence |
| comparison_runs | id, answer_run_id? FK, owner_id, scenario JSONB, corpus_revision, result JSONB, formula_version, created_at |
| llm_usage | id, answer_run_id? FK, user_id FK?, request_id UNIQUE, purpose, model_id?, reserved_tokens, input_tokens?, output_tokens?, estimate bool, cost_amount?, cost_currency?, status, created_at |
| subscriptions | id, user_id FK, bank_id? FK, metric_code? FK, enabled; filter_hash, UNIQUE(user_id,filter_hash) |
| notifications | id, user_id FK, change_event_id FK, channel=in_app, read_at?, created_at; UNIQUE(user_id,change_event_id,channel) |
| api_idempotency | user_id, route, key, request_hash, response_ref, expires_at; PK(user_id,route,key) |
| rate_limit_buckets | subject_hash, action, window_start, counter; PK triple; purge expired |

answer_evidence ссылается на fact_evidence для фактических claims. Для ответа из чистой цитаты отдельная `answer_chunk_evidence(answer_run_id,chunk_id,quote,physical_page?,section_label?)`; page/section валидируются по chunk. Ответ не подменяет метаданные новым extraction run.

## Фоновые задачи и аудит

`job_runs`: id, type, source_id?, aggregate_id?, scheduled_slot?, idempotency_key UNIQUE, payload JSONB, state, attempt, max_attempts, retry_at?, lease_token UUID?, lease_until?, heartbeat_at?, started_at?, completed_at?, error_code?, metrics JSONB. Чат, ingest и notification имеют разные type и fairness quotas; worker не делает два разных module pipelines одним handler.

`audit_logs`: id, actor_id?, actor_type, action, target_type/id, request_id, sanitized_diff JSONB, created_at. Append-only права для приложения; не писать passwords, full prompts, cookies и сырые персональные данные. `source_health_observations`: id, source_id, job_run_id, check_type, status, detail_codes, created_at. Позволяет увидеть падение качества при HTTP 200.

## Индексы

- GIN document_chunks.search_vector, конфигурация `russian` плюс отдельный simple vector для кодов/чисел при обоснованной необходимости. Индексировать completed parse, искать с bank/scope/date фильтрами.
- B-tree sources(next_check_at) WHERE state IN ('healthy','degraded','unknown'); blocked проверяется отдельным policy schedule.
- B-tree job_runs(state,retry_at), job_runs(lease_until) WHERE state='running'. Unique source schedule `(source_id,scheduled_slot,type)` для ingest; null slots у иных jobs допустимы.
- B-tree tariff_facts(bank_id,metric_code,semantic_key), tariff_facts(valid_from,valid_to), extraction_run_id; GIN scope/conditions только после EXPLAIN на реальных запросах.
- publication_facts(fact_id,publication_id), publications(revision,created_at); supersessions(old_fact_id,effective_from).
- chat_sessions(owner_id,updated_at DESC,id), chat_messages(session_id,sequence), notifications(user_id,created_at DESC,id), change_events(bank_id,detected_at DESC,id).
- Partial UNIQUE answer_runs(session_id) WHERE state IN ('queued','running') предотвращает два одновременных ответа. Идемпотентный повтор сначала ищет key.

## Удаление и миграции

RESTRICT для banks/sources/documents/versions/blobs/chunks/facts/evidence, если на них есть ссылки; каталог деактивируется. Не каскадировать удаление банка на историю. Chats → messages/context/runs/comparison_runs/answer_evidence каскадно при явном удалении собственного чата; evidence originals остаются. Usage audit после удаления chat отвязывает run/user через SET NULL и не сохраняет текст. User disable отзывает sessions; privacy erasure отдельная процедура по политике retention.

Миграции: 0001 catalog/blobs/jobs; 0002 documents/extractions; 0003 facts/evidence/publications; затем SRCH-001 создаёт отдельную ревизию `search_index` с down_revision=фактическая текущая head; 0004 auth/chat/usage с down_revision=search_index; 0005 changes/outbox/subscriptions; последующие measured indexes отдельными ревизиями. Число в имени файла — обозначение этапа, не автоматический порядок Alembic: порядок определяет down_revision. Для раннего POC достаточно первых трёх схем плюс search_index и local Principal вне production identity. Каждая task, вводящая таблицы, владеет своей ревизией, одна head. Не создавать параллельные heads и не редактировать уже применённую миграцию для позднего индекса.

Expand-contract: сначала nullable new columns/table, deploy dual-compatible readers, backfill job с checkpoint, validate constraints, затем отдельный cleanup release. Данные не пересоздавать через drop/create. Major upgrade — dump/restore rehearsal. Downgrade destructive schema не считать recovery: восстановление backup на совместимой версии и replay/повтор ingest. Fixtures не заменяют реальные данные в prod.
