# REST API v1

Prefix `/api/v1`. Единственный источник генерируемых TypeScript types — FastAPI OpenAPI после реализации. До этого этот документ и DOMAIN_CONTRACTS нормативны. API same-origin через reverse proxy, cookies, JSON UTF-8. CORS off по умолчанию. GET не изменяет состояние. Все mutation требуют CSRF, кроме token-based invite acceptance/login с Origin check и rate limit.

## Общие правила

`Principal={user_id,roles,session_id}` получается только из backend auth dependency. Параметр user_id клиента не определяет владельца. Object lookup включает owner predicate. Для чужого chat/document/run — 404. List ownership фильтруется в SQL до pagination.

Error: `{error:{code,message,details:[{field,code}],request_id}}`; 400 malformed, 401 auth, 403 permission, 404 unknown/foreign object, 409 concurrency/idempotency mismatch, 413 body too large, 422 DTO validation, 429 rate with Retry-After, 503 infrastructure. Документ/факт «не найден в корпусе» — успешный ответ с domain status, не 500.

Cursor pagination: opaque base64url `{sort_key,id}` c server validation, default 25/max100, stable order; `{items,next_cursor}`. Dates from inclusive/to exclusive. request_id возвращается в X-Request-ID. Mutable resources PATCH используют If-Match/version и 409 при устаревшей версии. Idempotency-Key на create question/compare/invite/review/recheck, UUID либо 16..128 ASCII; same key+different body →409.

## Endpoints и доступ

| Метод / путь | Доступ | Request → response |
|---|---|---|
| POST /auth/login | anonymous limited | email,password → user summary + Set-Cookie; generic invalid_credentials |
| POST /auth/logout | authenticated | {} →204; revoke session |
| GET /auth/me | authenticated | →id,display_name,roles,csrf_token |
| POST /auth/invites/accept | one-use token | token,password →201 user; token consumed атомарно |
| POST /auth/password-reset/consume | one-use token | token,new_password →204; revoke all sessions |
| GET /banks | user | →bank summaries |
| POST /comparisons | user | ComparisonRequest →200 ComparisonResult, persisted owner run |
| GET /comparisons/{id} | owner | →immutable ComparisonResult |
| GET /facts | user | bank_codes,metrics,as_of,scenario filters →cells + coverage statuses; только published |
| GET /documents | user | bank,kind,q,date filters →versioned metadata |
| GET /documents/{id} | user | →document metadata + versions; дата неизвестна =null |
| GET /document-versions/{id}/content | user | →original bytes, ETag sha256, Accept-Ranges; validates Range/206/416 |
| GET /document-versions/{id}/evidence | user | →chunk snippets, verified page/section refs |
| GET /search | user | q(1..500 chars),banks,as_of,limit<=20 →ranked snippets; discovery result не fact |
| POST /chats | user | title? →201 owned session |
| GET /chats | owner | →paginated sessions |
| GET /chats/{id}/messages | owner | cursor →messages with preserved AnswerEnvelope |
| DELETE /chats/{id} | owner | →204 after transactional deletion/cancellation |
| POST /chats/{id}/questions | owner | text(1..4000 chars),context_version →202 run_id,status_url |
| GET /answer-runs/{id} | owner | →state + AnswerEnvelope if terminal |
| GET /changes | user | banks,metrics,detected_from/to,effective_from/to →events |
| GET/POST /subscriptions | owner | filters →owned subscription |
| PATCH/DELETE /subscriptions/{id} | owner | enabled/version →result/204 |
| GET /notifications | owner | unread?,cursor →items |
| POST /notifications/{id}/read | owner | {} →204 idempotent |
| GET /dashboard | user | →coverage,freshness,counts,recent approved events; no synthetic winners |
| GET /analyst/review-queue | analyst | filters →candidate/document issues with originals |
| GET /analyst/facts/{id} | analyst | →candidate,provenance,validation flags,prior reviews |
| POST /analyst/facts/{id}/reviews | analyst | decision,reason,expected_hash,expected_revision →201 review/publication result |
| GET/POST /admin/invites | admin | email,roles →invitation link shown once; no automatic sending |
| POST /admin/users/{id}/disable | admin | reason →204 and session revocation |
| PUT /admin/users/{id}/roles | admin | roles,version →user; last active admin protection |
| POST /admin/users/{id}/password-reset | admin | reason →one-use reset link |
| GET/POST/PATCH /admin/sources[/{id}] | admin | registry fields/policy ref →source; bank URLs validated |
| POST /admin/sources/{id}/recheck | admin | reason →202 job; dedup pending |
| GET /admin/jobs | admin | type,state,source →sanitized diagnostics |
| GET /admin/metrics-summary | admin | →health,queue,freshness,budget,storage summaries |
| GET /health/live | internal/proxy | process-only 200 |
| GET /health/ready | internal/proxy | DB/schema/storage readiness 200/503, no secrets |

Admin не читает analyst endpoints без роли analyst. Analyst не меняет source policy. User/analyst/admin permissions are additive; все authenticated имеют базовые user права, но не ownership bypass.

## Документы

Source card: title, bank, version_id, physical_page?, section_label?, declared_effective_date?, fetched_at, last_checked_at, original_url, archive_url. Archive URL backend-owned `/api/v1/document-versions/{id}/content#page=3`. Fragment генерируется только для проверенной страницы. Архив отдаёт полный PDF, не вырезку.

PDF `Content-Type: application/pdf`, безопасный Content-Disposition filename, nosniff, ETag. HTML оригинал — attachment `application/octet-stream` или на отдельном sandbox origin без credentials; inline активный HTML на app origin запрещён. UI показывает escaped extracted text/section и ссылку «Скачать оригинал HTML». Официальный внешний URL открывается с noopener/noreferrer; доступность внешней страницы не гарантируется, архив сохраняет доказательство.

## Пример asynchronous question

```json
{"text":"Сравни Сбер и ВТБ по комиссии за зачисление","context_version":2}
```

202: `{"run_id":"<uuid>","state":"queued","status_url":"/api/v1/answer-runs/<uuid>"}`. Повтор с тем же ключом возвращает тот же run и сохранённый результат, не новый вызов LLM. Polling недоступен → UI сохраняет run_id, восстанавливается после reconnect. Ответ со статусом partial обязан содержать limitations и непустое объяснение неизвестных ячеек.

## Форматы review

`{decision:"approve|reject|needs_changes",reason:string(10..2000),expected_fact_hash:string,expected_revision:int,corrections?:FactCandidate}`. Corrections создают новый candidate с parent_fact_id, старый не переписывается. Для approve с corrections сначала валидируется новый candidate; публикация только если все evidence и scope достаточны. Authoritative contract date override требует отдельного evidence role=date. Concurrent approve → 409 или тот же idempotent результат, не двойное событие.
