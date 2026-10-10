# SOURCE-RECOVERY — implementation report

Дата: 10.10.2026. Исполнитель: Sol. База: `0454a1414af090ad54343e3ae0d6582a9c8435bf`.

Результат: реализован и проверен программный фундамент получения originals. Режим по умолчанию — offline; реальных банковских запросов, импорта исследовательского корпуса и выдачи G0-LIVE в этой работе не было. WORK-01/G1/G2 не завершены. Коммит этой реализации доступен через `git log --grep="Implement source recovery"`; SHA сообщается отдельно после push.

## Статусы этапов

| Этап | Статус | Код и доказательства |
|---|---|---|
| 1. TLS / robots | IMPLEMENTED / TESTED | `ingestion/tls.py`, `robots.py`. System/certifi SSLContext, дополнительный валидный CA, chain/hostname verification. OpenSSL MemoryBIO проверяет доверенную цепочку, неверный hostname и неизвестный CA без сокетов. Группы UA, wildcard, `$`, 403/WAF/invalid robots проверены. |
| 2. FetchGateway | IMPLEMENTED / TESTED OFFLINE | `policy.py`, `gateway.py`, `transport.py`, `errors.py`. Exact grants до DNS/send и на каждом redirect; IP pinning с исходным SNI; проверки реального peer до HTTP; public-only IPv4/IPv6; отказ для metadata, tunnel/mapped IPv6. Offline/CI не создают live transport. |
| 3. Архив и история | IMPLEMENTED / TESTED ON POSTGRESQL | `storage/local.py`, `ingestion/service.py`, migration `0002_source_recovery`. SHA-256, streaming, fsync, atomic no-clobber publish, дедупликация, карантин, observations, версии, предыдущая принятая редакция, stale. |
| 4. Discovery / форматы | IMPLEMENTED / TESTED | `adapters.py`, `formats.py`. Kuban/VTB HTML-link discovery на синтетических fixtures, PDF/XLSX candidates всегда pending. XLSX: bounded ZIP validation, запрет macros/external relationships/unsafe paths/compression bombs. Тарифные значения не извлекаются маркетинговым адаптером. |
| 5. Ручной импорт | IMPLEMENTED / TESTED | `service.import_file`, операторский `cli.py`. Отдельный manual grant; provenance/approved storage-reuse/дата/operator/hash; quarantine. Result=`manual_imported`, method=`manual`, HTTP status NULL, last_successful_check не обновляется. Отказ до чтения файла при недопустимом импорте. |
| 6. Интеграция | IMPLEMENTED / TESTED | Ruff, mypy, pytest; реальный PostgreSQL 18, миграции и `alembic check`; backend image собирается с `--no-dev`, локальный `/health` отвечает. CI содержит PostgreSQL service и offline env. |

## Реализация и ограничения контракта

`AcquisitionPolicy` требует reviewer, official relationship, acquisition/storage/reuse basis, terms evidence, purpose, expiry, exact URLs и метод. `SourcePolicy.acquisition_config` хранит независимые `automatic` и `manual` grants. Старые policy с пустым конфигом остаются blocked; банк-only seed не выдаёт разрешений. Данные grants перепроверяются из БД перед отправкой и после DNS/wait/TLS. Каждая отправка сохраняет snapshot approval и его hash, URL, pinned IP, время и status. Raw robots (base64), SHA-256, timestamp, UA и matched group сохраняются в audit metadata.

HTTPX2 используется через собственный BaseTransport на stdlib HTTPSConnection: DNS резолвится до соединения, TCP соединяется по выбранному публичному IP, сертификат проверяется против исходного hostname. Второй DNS lookup внутри соединения отсутствует. Peer проверяется до TLS и до HTTP; ошибочное соединение закрывается. DNS wait, TCP/TLS, reads и общий HTTP deadline ограничены; общий deadline также прерывает socket при медленной передаче заголовков. Cookies не переиспользуются; env proxy отключён. Транспорт прямой: proxy support не включён.

Неизвестный robots/403/HTML challenge — отказ, не allow-all. Redirect robots не следует автоматически: точный robots URL нового host должен быть в grant. На target redirect проверяются отдельный список разрешённых переходов и robots нового host. Максимум пять redirects, один активный fetch на host в процессе; PostgreSQL advisory locks дополнительно сериализуют хосты между service workers. Rate учитывается на каждую отправку и по сохранённым observations между процессами.

URL-контракт намеренно консервативный: только canonical HTTPS DNS hostname, port 443, без userinfo, query, fragment, percent-encoded path, traversal и IP literal. Нуждающиеся в query/encoded path источники требуют отдельного расширения валидатора с тестами. Несоответствующий MIME отвергается; PDF magic и XLSX container проверяются отдельно. Максимум original 50 MiB; robots 512 KiB; XLSX uncompressed total 100 MiB и 10000 entries.

Retry возвращается как `AcquisitionOutcome.retry_at` и сохраняется в observation. Только transient timeout/EOF/network/5xx/429/busy/rate failures допускают повтор; Retry-After не уменьшается jitter/backoff. Число попыток ограничено параметром attempt и MAX_JOB_ATTEMPTS. Автоматического sleep/retry-loop загрузки, scheduler или нового worker daemon не добавлено: существующая очередь JobRun должна передавать реальный номер попытки и вызывать service заново, что повторно проверит текущую policy. Постоянные TLS/robots/policy/403/format failures не получают retry slot.

Архив физически разделён на `real/` и `synthetic/`. Unique blob key — `(corpus_kind, sha256)`, receipt привязан к namespace и hash. Опубликованный файл никогда не перезаписывается: completed temp атомарно связывается с конечным content-addressed именем, существующий файл проверяется. На POSIX синхронизируется directory; Windows uses completed-file fsync + atomic hard-link publish. Root должен принадлежать только service account, hard links должны поддерживаться filesystem. Неподдерживаемая операция fail closed; symlink/reparse path и traversal блокируются. `reconcile` ничего не удаляет.

Файл завершается и проверяется **до** DB registration. DB rollback может оставить complete orphan, но не committed reference на partial file. Crash-orphans доступны read-only reconciliation. Same hash: новый observation, прежний blob/version. 304 принимается только с присутствующим hash-verified cached original и условными headers. `Blob.verified_at` — проверка целостности; `SourceVersion.content_state=accepted` — отдельная content acceptance, а не публикация тарифа. Ошибка fetch не заменяет предыдущую принятую редакцию; current_content возвращает stale при degraded/blocked или превышении freshness threshold.

`ExtractionEvidence` добавляет контракт для следующих parser tasks: immutable original/extraction hashes, parser_version, точная quote/offset, page/cell, dates/scope/contract condition. Unknown не превращается в federal/zero/current; состояние только pending_review. Полный PDF/XLSX parser, tariff extraction, публикация фактов и UI approval не входят в эту подсистему и здесь не объявляются реализованными.

## Проверки

Фактически выполнены:

```powershell
.\.tools\uv\bin\uv.exe lock --check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check backend
.\.venv\Scripts\python.exe -m mypy backend/app
$env:TEST_DATABASE_URL = 'postgresql+psycopg://bsi:bsi_local_only@127.0.0.1:5432/bsi'
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
docker compose --profile local up -d --build backend
curl.exe --fail http://127.0.0.1:8000/health
```

- Backend pytest: **91 passed**, включая **7 реальных PostgreSQL integration tests**, без skipped.
- Итоговый combined run `pytest backend/tests tools/test_bank_tls_probe.py`: **101 passed** (включает 10 прежних диагностических regressions).
- Ruff check / format: PASS. mypy: PASS, 23 source files.
- Alembic: head `0002_source_recovery` применена. `alembic check`: no new upgrade operations detected.
- PostgreSQL integration подтверждает: same hash dedup + отдельные attempts; quarantine до review; новая редакция не заменяет previous accepted; отказ сохраняет last-good со stale; manual provenance без automatic success; denied/real-in-offline import до file read; cross-connection host lock; rollback без committed file references.
- Archive tests: concurrent writers, cleanup temporary files, namespace separation, corrupted existing blob, injected atomic-publish failure, size/format rejection.
- Security tests: private/link-local/loopback/metadata IPv4/IPv6, rebinding между запросами, peer mismatch, revoked policy после DNS, redirects до target IO, hostname/chain, EOF/timeout, robots, 304, WAF200, 429, 5xx, host concurrency и rate cap.
- Backend production image built and started, health response `{"status":"ok"}`. CLI help работает и на Windows, и в Linux image.
- NOT RUN: bank live acceptance / scheduled three-day checks / G1/G2; отсутствует G0-LIVE. Frontend checks не запускались — frontend не менялся. GitHub CI после push выполняется отдельно и не подменяется локальными результатами.

## Найденные и исправленные ошибки

1. Compose использовал `/var/lib/postgresql/data` для postgres:18, из-за чего entrypoint завершался с ошибкой. Mount изменён на `/var/lib/postgresql`; перед запуском подтверждён пустой ранее созданный volume. Volume не удалялся, существующие данные не уничтожались.
2. Concurrent Windows hard-link publication выявил нестабильный resolve leaf через временный alias. Проверяются canonical parent directories, symlink/reparse components и hash самого файла. Конкурентный тест проходит.
3. При переносе HTTP client в runtime убрана лишняя dev-only запись; production image содержит httpx2/truststore/certifi/protego/cryptography.
4. Raw HTTP 200 robots нельзя принимать без проверки содержания; ложный allow-all для WAF исключён. Границы Yandex/* проверены отдельным regression.
5. Обрыв HTTP body до Content-Length отвергается до archive/DB commit: truncated original не регистрируется даже при правильном PDF magic.

## Изменённые файлы

- Новые `backend/app/ingestion/{tls,robots,policy,transport,gateway,errors,formats,adapters,evidence,service,cli}.py`.
- Новые `backend/app/storage/{__init__,local}.py`.
- `backend/app/config.py`, `backend/app/registry/models.py`, migration `0002_source_recovery.py`.
- Семь ingestion test modules, включая MemoryBIO TLS test module.
- `.env.example`, `.gitignore`, `pyproject.toml`, `uv.lock`, `compose.yaml`, backend job `.github/workflows/ci.yml`.
- Этот report и `docs/implementation/SOURCE_RECOVERY_USAGE.md`.

Архитектура, MASTER_PLAN, прежний исследовательский отчёт и source manifest не переписаны. Private originals/CA/keys не добавлены в Git. Downgrade новой миграции намеренно запрещён: схлопывание namespaces и истории требует отдельно проверенного плана миграции данных.

## Переход к реальным документам

1. Создать точный source-specific grant отдельно для automatic или manual: reviewer/evidence, storage/reuse, terms/robots, expiry, лимиты, target и robots URLs, allowed redirects. Все четыре банка по-прежнему без G0-LIVE.
2. Настроить CA вне Git/image и read-only mount при необходимости. Включение `INGESTION_MODE=live` само по себе не одобряет source.
3. Кубань: robots-compatible PDF получение после допуска. ВТБ: manual/согласованный канал для запрещённых robots PDF/XLSX. Альфа/Сбер: manual или разрешённый канал; TLS fix не обходит WAF.
4. Выполнить content acceptance с датами/МСБ/RU-KDA/пакетом/условиями конкретного договора. Затем parser/evidence/human publication и отдельно настоящие G1/G2 проверки.
