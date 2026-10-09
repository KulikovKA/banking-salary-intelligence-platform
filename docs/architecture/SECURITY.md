# Безопасность и границы доверия

## Угрозы и обязательные меры

| Угроза | Мера | Проверка |
|---|---|---|
| Чужой чат через UUID | Backend ownership в каждом read/write/poll/delete | user A vs B для всех объектов |
| SSRF из источника/redirect | Exact host allowlist, DNS/IP deny private/loopback/link-local/metadata/IPv6 local, revalidation every hop, no credentials in URLs | 127.0.0.1, ::1, DNS rebinding, redirects |
| Prompt injection в PDF | Untrusted evidence data, bounded structured outputs, read-only tools, no arbitrary URLs/SQL, claim templates | вредоносная сноска не меняет routing/claims |
| Stored XSS | Escaping snippets, plain Markdown allowlist без HTML, safe links; HTML originals не inline | script, SVG, javascript URL |
| CSRF/session fixation | Secure HttpOnly SameSite=Lax cookie, CSRF token + Origin check, session rotation on login/privilege change | чужой Origin и pre-login token |
| Brute force | per-IP и per-account rate limits, generic errors, audit | распределённые попытки не раскрывают email |
| Malicious/huge PDF | 50MiB cap, parser subprocess nonroot/no network, memory/time/page quotas | decompression bomb/timeout без падения API |
| Secrets in logs | Structured event codes, redaction, no payload logging | synthetic canary key отсутствует в logs |
| LLM data leak | gateway accepts normalized allowed fields, не raw history | canary email/account не выходит наружу |
| Worker race | lease fencing + transactions + unique keys | old worker не коммитит после lease loss |

FetchGateway должен проверять IP, с которым реально устанавливается соединение, а не только предварительный DNS lookup; иначе остаётся TOCTOU rebinding. Сетевой egress firewall — дополнительная защита. Playwright отдельный worker profile без внутренних routes; блокировать subresource navigation на неразрешённые хосты. Включать только когда httpx не даёт нужный публичный контент. CAPTCHA/403 не обходить.

## Идентификация

Закрытая регистрация: Admin генерирует одноразовый invitation token ≥256 random bits, сохраняет SHA-256 hash, expiry 48h; вручную передаёт ссылку. Никаких отправок email в MVP. Пароль min12/max128 символов, без silent truncation. Argon2id с параметрами, откалиброванными под host (цель 100–300ms verify и достаточная memory), записанными в security report. Проверять текущие рекомендации при реализации, не изобретать собственный hash.

Session token random256, сервер хранит hash. Proposed idle TTL 8h, absolute TTL 24h. Cookie `__Host-session`, Secure, HttpOnly, Path=/, без Domain. Секреты в Docker secrets/защищённых env files вне Git, provider key только backend/worker. Сброс пароля одноразовый 30min token от Admin, инвалидирует sessions. Последнего активного Admin нельзя отключить или лишить роли без назначения замены. Bootstrap первого admin — одноразовая CLI процедура, пароль не в default env.

Rate limits proposed: login 5/min per account и 20/min per IP; questions 6/min/user; search 60/min/user; source mutation 10/min/admin. Для 30 пользователей PostgreSQL counters достаточны; запросы и scheduler имеют разные DB pool limits. Внешние proxy headers доверять только Caddy.

## ПД и правовая готовность

Платформа не должна принимать зарплатные реестры, паспортные данные, банковские счета или документы сотрудников. Но учётные записи, IP и свободный текст чата могут содержать ПД. Предлагается хранение БД, файлов, логов и backup в РФ; минимизация email/display name; logs с pseudonymous ID. Это техническая мера, не полное подтверждение соблюдения 152-ФЗ.

До production ответственный оператор проверяет действующую редакцию 152-ФЗ (включая ст. 6, 12, 18, 18.1, 19, 21, 22), основания обработки, уведомления, локализацию, сроки хранения/удаления, доступ сотрудников и договоры с обработчиками. Поправки №23-ФЗ 2025 года меняли правила локализации; исследовательские ссылки и границы проверки в [SOURCES](../research/SOURCES.md). Старые региональные памятки не использовать как актуальное перечисление исключений.

External LLM по умолчанию выключен. В разрешённый запрос выходят публичные банковские выдержки, банковские идентификаторы и обезличенные scenario parameters. Raw user question/history не отправлять автоматически: локальный preprocessor извлекает безопасные поля; при невозможности безопасно преобразовать — уточнение/локальный fallback. Regex redaction не гарантирует отсутствие ПД; включение передачи свободного текста требует отдельного решения по поставщику, условиям хранения, территории обработки и трансграничной передаче. Ответственный фиксирует это до LLM-003.

Автоматический сбор: для каждого банка записать URLs, robots.txt, условия использования, allowed scope/rate и решение ответственного. robots.txt сам по себе не выдаёт юридического разрешения. Не авторизоваться в банковских кабинетах; не обходить защиту; не делать массовую выгрузку. При запрете/неясности источник pending/blocked, согласованный manual import официального оригинала может быть отдельно утверждён; он не считается доказательством работоспособности автоматического адаптера.

## Retention и права

Proposed: чаты 180 дней или до удаления; operational logs 30 дней; security/audit 365 дней; оригиналы и evidence до отдельной утверждённой archive policy. Это продуктовые настройки, не законные универсальные сроки. Удаление чата убирает messages, context, answer results и персональный cache; logs не содержат текста. Backups истекают через 30 дней; журнал deletion tombstones повторно применяется после restore до открытия доступа. Tombstone содержит opaque UUID и срок, без удалённого текста.

Admin доступен технический аудит, но не чужая переписка. Базовые банковские документы общие для сотрудников. Приватные договоры вне MVP. Их будущий ввод потребует organization ACL на documents→chunks→facts→search→answers и cache partitioning, а не только role check на download.
