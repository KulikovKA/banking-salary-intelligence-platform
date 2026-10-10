# Snapshot rebase — 10.10.2026

Base commit: `a8c0fa3`. Цель итерации — документация и исполняемый план минимального
AI-продукта; бизнес-код ещё не реализован и не объявлен готовым.

## Аудит и решения

Проверены все 223 исходных файла docs (219 Markdown, 4 JSON), root README/MASTER_PLAN,
architecture/ADR/requirements/tasks/prompts, existing Python/Next.js scaffold,
каталог/миграции/ingestion и CI/E2E. Реализация содержит семь PG tables, source
recovery и health endpoint, но не тарифное ядро/полноценный parsing/LLM/auth/UI.

Новая архитектура: операторский initial acquisition/import -> immutable originals ->
PDF/XLSX/HTML extraction -> normalization -> evidence/manual review -> frozen corpus ->
FTS/comparison -> constrained LLM/Fake -> authenticated API/Next.js.
Scheduler/regular fetch/change tracking/notifications/queues вне scope. Existing
jobs/schema/stale fields сохранены; новый snapshot reader не зависит от 72h checks.

Основной LLM: `openai/gpt-oss-120b` через GroqCloud Free. Проверены official
[models](https://console.groq.com/docs/models),
[API reference](https://console.groq.com/docs/api-reference),
[structured outputs](https://console.groq.com/docs/structured-outputs) и
[rate limits](https://console.groq.com/docs/rate-limits) 10.10.2026.
План предусматривает structured JSON, локальную validation, bounded quotas и fallback;
лимиты аккаунта проверяются при реализации/запуске, здесь SLA не заявлен.
Нет Groq calls/ключей и новых банковских requests в этой итерации.

## Судьба документов

Пофайловый [inventory](evidence/snapshot-document-audit-2026-10-10.json) содержит
225 entries (223 docs + 2 root), old SHA-256 и destinations:

- 211 прежних артефактов архивированы в `docs/archive/pre-snapshot/`, включая
  старые root README/MASTER_PLAN и все поколения WORK/TASK/luna plans/prompts,
  ADR-001..006, product gates, architecture/research/quality specifications.
- 14 сохранены на прежних путях: 11 Markdown reports, license JSON, source E2E
  JSON evidence и working SOURCE_RECOVERY_USAGE runbook. Runbook уточнён:
  operator attempts без JobRun/scheduler, legacy stale отдельно от snapshot reads.
- Навсегда удалённых исторических документов — 0. Exact duplicate files — 0;
  смысловые дубли plans/backlogs удалены из активной навигации посредством архива.
- Active README/architecture/acceptance/plan заменены snapshot спецификацией;
  исходные версии находятся в archive. Local Markdown links перенаправлены
  по mapping; содержание отчётов/исторические approval статусы не изменены.

Исходный код, tests, tools source recovery, lockfiles, migrations, source manifest,
bank permission evidence не удалялись и не редактировались. Новые служебные изменения:
AGENTS.md, docs validator, commented Groq config example и CI docs validation.
Архивный TASK_INDEX/WORK_INDEX JSON сохранён побайтно, не является активным планом.

## Активная структура

```text
README.md / MASTER_PLAN.md / AGENTS.md
docs/
  README.md
  architecture/
    OVERVIEW.md                 # стек + поток + реализованное/план
    DOMAIN_CONTRACTS.md
    DATABASE_DESIGN.md
    API_CONTRACTS.md
    SECURITY.md
    ADR/007-snapshot-monolith.md
  implementation/
    MASTER_PLAN.md
    TASKS.json
    SOURCE_RECOVERY_USAGE.md
    prompts/SNAP-01.md ... SNAP-19.md
  product/ACCEPTANCE_CRITERIA.md
  reports/                     # исторические и новые проверки, evidence/
  archive/README.md
  archive/pre-snapshot/        # предыдущая архитектура/планы/ADR/research
```

19 ready-to-run prompts содержат goal/outcome, paths, dependencies, implementation,
constraints, tests/AC, effort, parallel ownership и report handoff. DAG проверяется
валидатором. Сейчас полностью доступен SNAP-01; после него schema/parsers/normalization/
Fake независимы. Источники допускаются отдельно; auth/API/UI не ждут historical G2.
Shared migrations/lockfiles/config/main/status files имеют одного integrator.

## Проверки этой итерации

- Ruff: PASS; mypy: PASS (23 existing backend source files).
- Backend без DB env: 95 passed, 9 skipped (явно нет TEST_DATABASE_URL).
- PostgreSQL 18.6, dedicated existing `bsi_e2e`: Alembic upgrade head + check PASS,
  новых upgrade operations нет; backend + TLS tool tests: **104 passed, 0 skipped**.
- Existing synthetic source recovery E2E повторён: **PASS_SYNTHETIC_ONLY**,
  network requests 0, two blobs/versions, seven observations, no missing/orphan.
  [Новый result.json](evidence/snapshot-rebase-source-e2e-2026-10-10.json).
  Real scenario BLOCKED, automatic grants/real imports отсутствуют.
- Frontend ESLint/typecheck/production build: PASS (Next.js 16.4.0).
- Documentation validator: PASS, все local Markdown links (включая архив),
  19 prompts, acyclic dependency DAG, prompt/plan/registry consistency и сохранность
  архивных JSON evidence (нормализация LF/CRLF учитывается).
  Git diff whitespace: PASS, включая staged changes.
- Проверка всех 224 исторических файлов (кроме намеренно уточнённого working
  runbook): содержание сохранено, различаются только перенаправленные Markdown
  link destinations и стандартные переводы строк. Backend/frontend/tests/migrations
  и lockfiles не имеют diff к base commit.

G1/G2 не пройдены. Snapshot S1 BLOCKED; S2/S3 NOT EVALUATED; полный S0 ещё требует
новых компонентов. Архитектурное поручение не является source/provider processing
approval. S0–S3 критерии заданы отдельно, никакого real-model PASS не заявлено.
