# PostgreSQL: реализованное и планируемое

## Уже реализовано — не пересоздавать

Источник истины: `backend/app/registry/models.py`, Alembic
`0001_catalog.py` и `0002_source_recovery.py`.

| Таблица | Содержание / ограничения |
|---|---|
| banks | UUID PK, unique code; seed ровно четыре identity, без тарифов/grants |
| source_policies | bank FK, allowed_hosts, acquisition_config automatic/manual, decision/reviewer/reason |
| sources | bank/policy FK, unique bank+canonical URL, kind/scope/state, corpus_kind |
| blobs | immutable SHA-256, bytes/MIME/storage_key, unique corpus_kind+sha256 |
| source_versions | source/blob FK, unique source+blob, quarantine/accepted/rejected, acceptance metadata |
| source_fetches | observations, exact URLs/redirects, result/method/audit; manual HTTP status NULL |
| job_runs | existing idempotency/lease/retry schema/helper; v1 не запускает scheduler |

schedule_seconds, next_check_at, due index, stale/lease config сохраняются как
legacy совместимость. Это не требование запускать scheduling. Изначальные
миграции не редактировать; тест `test_db_contract.py` сейчас проверяет точный
набор таблиц — SNAP-02 должен осмысленно расширить ожидание, не удалить проверку.

## SNAP-02 — добавочная revision 0003 (план)

| Таблица | Ключевые поля и правила |
|---|---|
| snapshots | id, revision unique, corpus_kind, state, created/frozen_at, manifest_sha256 |
| extraction_runs | id, source_version FK RESTRICT, raw/extraction SHA, parser_version, status, corpus_kind; unique version+parser_version+extraction hash |
| document_chunks | id, extraction FK RESTRICT, ordinal, immutable text+hash, locator/relations JSONB, search_vector; unique extraction+ordinal |
| snapshot_members | snapshot/source_version/extraction FK RESTRICT, composite PK snapshot+version, unique snapshot+extraction |
| tariff_candidates | id, extraction FK, bank FK, metric code, canonical payload JSONB, corpus_kind, created_at; immutable candidate payload |
| evidence_refs | id, candidate/chunk FK RESTRICT, exact quote offsets, support_role, locator/hashes; CHECK nonnegative offsets/end>start |
| fact_reviews | id, candidate FK RESTRICT, reviewer identity, decision, reason, validation JSONB, created_at; append-only |
| published_facts | id, snapshot/candidate/review FKs RESTRICT, unique snapshot+candidate; approved review only |
| llm_usage | request_id, user identity nullable initially, window, reserved/actual tokens, estimated, state, model; atomic budget reservation |

Candidates payload содержит value union, Decimal strings, applicability и conditions
по DOMAIN_CONTRACTS; один JSONB canonical payload уменьшает дублирование полей.
Для фильтрации bank/metric/extraction/corpus_kind — typed columns, payload consistency
проверяется сервисом. Денежные вычисления Decimal; если вводятся typed numeric
поля, money numeric(20,6), rate numeric(12,6), никогда float.
GIN search_vector с русской конфигурацией и fallback simple для кодов/чисел;
индексы extraction source FK, chunks extraction ordinal, candidate bank+metric,
published snapshot, evidence candidate/chunk и reviews candidate+created_at.

Все межтабличные corpus/provenance проверки и frozen state transition идут через
один transaction service + row lock snapshot. До freeze оригиналы/hashes и approved
members перепроверяются; insert/update membership frozen отклоняется также DB
trigger. Raw SQL не должен обходить immutable frozen membership. Snapshot state
допускает draft->frozen->revoked, не возврат draft. Publish real rejects synthetic
на каждом уровне. Отзыв source policy блокирует read, даже frozen.
DB reference коммитится после atomic blob write; orphan возможен и виден reconcile.

## SNAP-15 — отдельная revision 0004 (план)

users (unique normalized login, password_hash, role analyst|admin, active),
invitations (token_hash unique, expiry, used_at, issuer FK),
sessions (token_hash unique, user FK, created_at, last_seen_at, absolute_expiry,
revoked_at), auth_audit (event code, actor ID, timestamp; без паролей/текста).
FK reviewer/user и llm_usage.user_id добавляются без выдуманных historical users:
операторский identity в ранних review остаётся явно отличим от user FK.

Revision 0003 принадлежит только SNAP-02, 0004 только SNAP-15; downstream tasks
используют готовые модели. Если схема требует коррекции, отдельная follow-up
задача единственному владельцу миграций после merge. Alembic env импортирует
все model modules; migration upgrade + alembic check на PostgreSQL обязательны.
Не заменять PG SQLite в domain integration (существующий unit transaction helper
test на SQLite сохраняется). Downgrade с потерей evidence не выполнять на данных.

В v1 нет новых таблиц notifications/events/outbox/change tracking/chat memory.
Backup: согласованные pg_dump + blob manifest/hashes, restore в отдельной DB/root,
проверка ссылки original->chunk->fact до открытия read access.
