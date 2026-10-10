# FastAPI /api/v1 (план SNAP-16)

Сейчас работает только GET /health (process liveness). Все маршруты ниже целевые,
реализуются после сервисов. Same-origin frontend proxy, JSON DTO из SNAP-01,
UTC timestamps/Decimal strings, bounded payloads и pagination.

| Route | Доступ / результат |
|---|---|
| GET /health | anonymous, без DB/provider readiness claims |
| POST /api/v1/auth/login | credentials -> session cookie; generic failure |
| POST /api/v1/auth/logout | session + CSRF, revoke current session |
| POST /api/v1/auth/accept-invite | одноразовый token + пароль; session rotation |
| GET /api/v1/auth/me | current identity/role |
| POST /api/v1/admin/invitations | admin + CSRF; manual share token, без email |
| GET /api/v1/snapshots | analyst/admin, readable frozen revisions + coverage |
| GET /api/v1/snapshots/{id} | status/manifest без secret policy fields |
| GET /api/v1/search | session, snapshot_id/query/filter, limit<=10 |
| POST /api/v1/comparisons | session + CSRF, ComparisonRequest -> ComparisonResult |
| POST /api/v1/assistant/questions | session + CSRF, {snapshot_id,question<=2000 chars,scenario?,bank_codes?,metric_codes?} -> AnswerEnvelope |
| GET /api/v1/documents/{version_id} | session, readable snapshot membership and policy; safe metadata |
| GET /api/v1/documents/{version_id}/original | same check, attachment + nosniff, verified hash, no storage path |
| GET /api/v1/admin/candidates | admin; paginated pending/review state |
| POST /api/v1/admin/candidates/{id}/reviews | admin + CSRF; decision/reason, validate evidence |
| POST /api/v1/admin/snapshots/{id}/freeze | admin + CSRF; validation report -> frozen or typed error |

Ingestion/parser batch выполняется CLI; arbitrary URL fetch/upload из public API
не вводить. Review endpoint не позволяет менять payload candidate.
Question/comparison — ограниченный синхронный запрос, без 202 jobs/polling/SSE.
Provider deadline общий; при ошибке возвращается успешный typed fallback envelope,
когда backend может дать доказательный ответ. Нет ответа -> insufficient/clarification.

Ошибки: `{error:{code,message,request_id,details?}}`, без credentials/paths/raw stack.
400 invalid query, 401 missing session, 403 role/CSRF, 404 unknown or inaccessible
document, 409 frozen snapshot/conflicting publish, 422 DTO validation,
429 user/provider budget limit (Retry-After), 503 DB/unreadable corpus.
Недостаток данных в сравнении — cells/limitations, не HTTP 500.
Provider error -> fallback + limitation, auth key ошибку не раскрывать клиенту.

Snapshot_id обязателен: backend не подставляет latest document. UI выбирает
revision явно. Ссылки строит backend, download повторно проверяет policy/membership.
API contract tests используют Fake, real PG и identities A/B/admin; Groq/bank network
исключён из CI. Admin не имеет доступа к чужим сообщениям; durable chats в v1 нет.
