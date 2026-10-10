# Trust boundaries snapshot v1

Существующие policy/TLS/robots/IP/redirect/size checks сохраняются.
Source-specific acquisition, storage и reuse basis проверяются до получения bytes;
manual grant отдельно от automatic. Публичный URL, HTTP 200, robots allow и наличие
исследовательского файла не являются approval. Нет неизвестных/подставных reviewer.
Offline/test/CI запрещает ingestion egress; parser не делает сеть или subresources.
Real import в существующем service требует ingestion_mode=live и manual grant:
это legacy имя режима, а не выдача automatic fetch допуска.

## Документы и доказательства

50 MiB existing source cap, ограниченные pages/cells/XML/text/time/memory в parser.
Subprocess без сети, только конкретный read-only original; timeout возвращает
failed/needs_ocr. HTML scripts/styles исключаются, original отдаётся attachment,
не отображается на origin. XLSX macros/external relationships/formulas не исполнять.
Untrusted document text не может изменить prompts, доступ, policy или computation.
Escaped plain text и safe links в Next.js, без arbitrary HTML rendering.
Facts publish только после evidence validation и ручного review; revoked права
блокируют read/cache. Synthetic и real DB/storage namespaces не смешиваются.

## Авторизация (SNAP-15)

Закрытые приглашения, без публичной регистрации/email infrastructure.
Admin bootstrap CLI: пароль из защищённого stdin, без default credentials.
Argon2id, существующая библиотека, параметры проверить по официальным рекомендациям
при реализации и зафиксировать; пароли 12..128, без silent truncation.
Invite/session random >=256 bits, только SHA-256 token hashes в DB. Invite TTL 48h,
one use с row lock. Server sessions: idle 8h, absolute 24h, rotation login/invite,
revoke/logout. Production `__Host-session`: Secure, HttpOnly, SameSite=Lax, Path=/,
без Domain. Local HTTP cookie с отдельным dev именем; production validation не ослаблять.
CSRF token + Origin checks на unsafe methods, включая login/invite; exact CORS если
same-origin невозможен. Roles analyst/admin; admin mutations отдельно, API endpoints
каждый используют dependency. Последнего active admin не удалить/понизить.
Login limits 5/min account и 20/min IP, generic errors; trust proxy headers только
от configured ingress. Tests фиксации/expiration/concurrent token use/CSRF/A-vs-B.
Fake identity только explicit test/local harness, production запрещён.

## Groq и персональные сведения

Provider key только backend SecretStr/env, no logs/frontend. Основной transport
allowlist `api.groq.com`, HTTPS, без редиректов. Не отправлять raw chat/history,
ФИО, payroll registers, account identifiers. Внешний intent принимает bounded
обезличенный вопрос после minimization; если очистку нельзя обосновать, локальное
уточнение/structured scenario и deterministic route. Regex не доказательство
безопасности. Public snippets/scenario разрешаются к отправке только после
фиксированного решения о provider processing и reuse corpus.

Groq Free — целевой provider, а не разрешение передачи любых данных. До включения
на реальных данных ответственный фиксирует terms/processing/retention decision;
до этого adapter и smoke на synthetic/публичном разрешённом тесте можно реализовать.
Изменение поставщика/платный fallback не автоматическое. Нет browser/tool use у LLM.
Structured JSON проверяется локально; произвольная цифра/URL/claim rejected.
Timeout/429/budget -> deterministic fallback, не endless retries.

Не заявлять legal compliance на основании этих технических мер. Сведения о
разрешениях и исторических исследованиях сохраняются в отчётах/архиве.
Минимизировать учётные данные, operational logs 30 дней, auth audit 365 дней как
проектные значения для подтверждения оператором, без question payload logging.
Backup защищён тем же доступом, restore сначала закрытый; секреты вне Git.
