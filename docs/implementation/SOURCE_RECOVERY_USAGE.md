# Использование source recovery

Дефолт — offline. `SourcePolicy.acquisition_config={}` ничего не разрешает. Не импортировать реальные файлы из исследовательского архива как approved corpus автоматически.

## Запуск

```powershell
.\.tools\uv\bin\uv.exe sync --locked
docker compose --profile local up -d db
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
$env:PYTHONPATH = (Resolve-Path backend).Path
.\.venv\Scripts\python.exe -m app.ingestion.cli --help
```

Source регистрируется существующим ORM каталогом. Для `html/index/news` формат original — HTML; для pdf/xlsx — соответствующий формат. Source.corpus_kind и blob namespace согласованы. Discovery возвращает candidates с decision=pending, не создаёт approve.

`SourcePolicy.acquisition_config` содержит независимые ключи `automatic` и `manual`. Значение каждого — JSON `AcquisitionPolicy.model_dump(mode="json")`: source_id, decision, allowed_urls, redirect_urls, method, corpus_kind, reviewer, official_relationship, acquisition_basis, storage_basis, reuse_basis, terms_evidence, purpose, expires_at, revoked, rate_seconds. Row.collection_decision также должен быть approved; bank/source связи и allowed_hosts должны совпадать с grant. Банк-only seed не содержит таких записей. Не использовать fictitious reviewer/basis для real corpus.

Для automatic явно допустить exact target и `https://host/robots.txt`. Rate — интервал **между отдельными запросами**. Scheduling fields отсутствуют в active ORM; миграция 0003 оставляет старый physical column с инертным DB default для новых rows. Robots redirects неизвестны и не следуют автоматически. Target redirects должны быть отдельно перечислены; новый host должен иметь собственный разрешённый robots URL.

## Операторский CLI

После source-specific допуска и настройки окружения:

```powershell
# DATABASE_URL и STORAGE_ROOT задаются локально; credentials не печатаются.
# Real retrieval/import требует live mode и отдельного approved grant.
$env:INGESTION_MODE = 'live'
$env:BANK_FETCH_EXTRA_CA_FILE = 'C:\approved-certs\root.crt'

.\.venv\Scripts\python.exe -m app.ingestion.cli fetch --source-id <UUID>

.\.venv\Scripts\python.exe -m app.ingestion.cli import-file `
  --source-id <UUID> --file 'C:\approved-originals\document.pdf' `
  --operator '<responsible operator>' `
  --original-url 'https://approved-host/exact-path.pdf' `
  --final-url 'https://approved-host/exact-path.pdf' `
  --acquired-at '2026-10-10T12:00:00+03:00'
```

Это шаблоны команд, они здесь не выполнялись на реальном источнике. Caller должен указать реальную дату получения; дата не назначается датой действия документа. CLI не устанавливает CA в ОС и не выдаёт approval. Все responses сохраняются в quarantine; `service.accept_content` — отдельный явный review. Content acceptance не публикует тарифные факты.

## Python API

`IngestionService(factory, settings, store, gateway)`:

- `fetch_source(source_id, attempt=1)` → observation/version/result/error_code/retry_at. FETCH_MAX_ATTEMPTS ограничивает явные попытки (default 3); старой MAX_JOB_ATTEMPTS настройки нет. В snapshot v1 оператор выполняет отдельную попытку; retry_at — подсказка, не запланированная job. Повторный вызов перечитывает active grant. Сам service не запускает retry-loop или worker daemon.
- `import_file(...)` → `manual_imported`, method manual, HTTP NULL; denied attempts получают отдельный rejected manual observation.
- `accept_content(version_id, reviewer=..., applicability=...)` → перевод quarantine в accepted с hash verification; не публикация тарифа.
- `current_content(source_id)` → last accepted version ID либо None для operator inspection. Failed/new quarantined fetch не стирает old accepted. Snapshot reader из SNAP-03 отдельно проверяет exact frozen membership, rights и applicability; periodic freshness/stale logic отсутствует.
- `LocalBlobStore.reconcile(referenced_keys)` → missing/orphan report, без удаления.

Gateway Fake transport допускается только в APP_ENV=test для synthetic corpus и требует fake resolver. Production transport невозможно подменить на произвольный HTTP transport через конструктор Gateway. Root должен принадлежать service account; originals открываются как файлы, HTML не рендерится и subresources не загружаются.

## Проверки

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://bsi:bsi_local_only@127.0.0.1:5432/bsi'
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
```

PostgreSQL tests используют внешний rollback/synthetic namespace, не удаляют schema и не обращаются к банкам. CI устанавливает offline/test режим и отдельную PostgreSQL service DB.
