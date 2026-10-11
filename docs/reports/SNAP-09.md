# SNAP-09 — Evidence validation, review и publication

Дата: 11.10.2026 (Europe/Moscow).
Base commit: `09006c635b4f35f5070beb58ce8b9b19dfafc781`.
Ветка/worktree: `codex/snap-09-evidence`,
`C:/Users/Kirill/Desktop/sber-ai-snap-09-evidence`.
Результат: implementation complete and ready for independent review; checks ниже.
Implementation commit: `609482fd2b59fd3cb749d24b301c0951cbc245b2`.
По отдельному поручению пользователя commit/push выполнены в ветку
`codex/snap-09-evidence`. TASKS.json/MASTER_PLAN и product gates не менялись.

SNAP-08 действительно merged через PR #15/#16; исходный report сопоставлен с
кодом. Прочитаны AGENTS, README, MASTER_PLAN, SNAP-09 prompt, архитектурные
контракты и продуктовые AC. Работа выполнена последовательно, без subagents.

## Реализация

Изменены только owned paths:

- `backend/app/evidence/validation.py`
- `backend/app/evidence/service.py`
- `backend/app/evidence/cli.py`
- `backend/tests/test_evidence_publication.py`
- Этот report.

DTO/ORM/миграции/parser internals/normalizer/FetchGateway/BlobStore/auth/API/UI
read-only и сохранены. Новых сервисов, scheduler, queues, provider calls нет.

### Technical evidence

`EvidenceValidator` проверяет exact candidate payload hash, metric/payer/operation
семантику registry, source/version/fetch/policy/bank/corpus/URLs/acquired_at,
accepted original и текущие acquisition/storage/reuse права через CorpusService.
`store.verify()` выполняется до чтения оригинала.

Original заново разбирается существующим bounded offline subprocess. Проверяются
parser version, extraction hash и canonical hash всех actual ParsedBlocks.
Сохранённые chunks должны совпасть с actual blocks: deterministic ID, ordinal,
text/hash, locator и relations. Так wrong physical page/bbox/table cell, sheet/
range и HTML path не проходят только за счёт syntactically valid locator.

Evidence refs должны точно совпадать с candidate.evidence_ids и принадлежать
тому же run/version/chunk/raw/extraction hash. Проверяются offsets, substring,
locator, acquisition URL/time. Existing ExtractionEvidence/check_chunk сохранён
и вызывается наряду с новым frozen EvidenceRef DTO; прежний контракт не заменён.
Footnote relation требует actual target и condition ref для него.

### Semantic review

Technical match сам по себе даёт `valid=false` и SEMANTIC_CONFIRMATION_REQUIRED.
Оператор явно подаёт JSON с evidence IDs по required fields: value, unit/basis/
period/conditions, metric/payer/operation, известные geography/scope/date.
Полный набор полей вычисляется validator, а не принимается как boolean approve.
Для interpretation/relations требуется подтверждение всех refs цепочки.

Conservative lexical checks сверяют конкретные числа, валюту/единицы, basis,
period, conditions text/числовые AST thresholds и даты с выбранными цитатами.
Поддержка arbitrary natural-language semantics автоматически не утверждается:
смысл метрики, плательщика, операции, scope и связи обязан проверить человек.
`reviewer_label` и reason обязательны; user_id, если указан, должен относиться
к существующему active admin. Local CLI operator label явно отличается от user FK;
реальные reviewer identities или human gold не выдумывались.

Review хранит append-only decision/reason/identity и validation proof:
candidate hash, run/raw/extraction/parser identity, hashes refs, field_evidence,
snapshot_id, limitations и eligible_for_comparison. Rejected/needs_review не
создают publication grant. Последний review учитывается отдельно для snapshot.
После publication review в той же revision запрещён; коррекция — новая revision.

### Publication/read

`publish()` блокирует snapshot/candidate/source version/source/policy rows,
повторно проверяет original/rights/evidence и сохранённое review proof.
Membership и PublishedFact вставляются атомарно в draft, с existing unique keys
и DB guards. Ошибка после membership flush откатывает обе записи, сохраняя review.
Concurrent/repeated publish возвращают один fact; frozen/revoked/corpus mismatch
не дают новую публикацию. Старый review нельзя перенести в другой snapshot.

`read_published(manifest)` — минимальный интерфейс для SNAP-10/11: только exact
frozen manifest/members и PublishedFact с matching approved review/proof.
Raw candidates остаются pending_review и не выдаются как facts. Read проверяет
current rights/original hashes и immutable candidate/ref proof. Existing
CorpusService.freeze повторно проверяет права и reviewed exact membership.

Unknown scope/date/period, individual/text/boolean и unparsed conditions явно
сохраняют limitations. Они не становятся zero/current winner. Review-only flags
могут быть сняты только explicit whole-chain semantic confirmation; неизвестные
значения и неисполняемые conditions так не снимаются. Eligible_for_comparison —
готовность подтверждённых полей, не вычисление тарифа, winner или обещание current
price на произвольную дату. Scenario/date applicability оценивает SNAP-11.

## CLI

Рабочие команды (с PYTHONPATH=backend и DATABASE_URL/storage configuration):

```powershell
uv run python -m app.evidence.cli --manifest manifest.json inspect --candidate-id UUID
uv run python -m app.evidence.cli --manifest manifest.json validate --candidate-id UUID
uv run python -m app.evidence.cli --manifest manifest.json validate --candidate-id UUID --confirmation confirmation.json
uv run python -m app.evidence.cli --manifest manifest.json review --candidate-id UUID --decision approved --reviewer ACTUAL_OPERATOR --reason "Actual checked interpretation" --confirmation confirmation.json
uv run python -m app.evidence.cli --manifest manifest.json publish --candidate-id UUID --review-id UUID
```

`inspect` показывает permitted candidate/quotes/locators и required_fields.
Confirmation file ограничен 64 KiB и содержит только `field_evidence`:

```json
{"field_evidence":{"value":["VALUE_REF_UUID"],"unit":["UNIT_REF_UUID"],"metric":["SCOPE_REF_UUID"],"payer":["SCOPE_REF_UUID"],"operation":["SCOPE_REF_UUID"],"interpretation":["ALL_REF_UUIDS_REQUIRED"]}}
```

Это иллюстрация формы, не готовое approval: использовать только реальные IDs
из inspect и все required fields. `interpretation`/`relations` перечисляют каждый
ref; known scope/date/basis/period/conditions требуют своих refs. Неизвестная дата
не подставляется из acquired_at. CLI возвращает nonzero для invalid/pending
validation и безопасные error_code вместо credentials/paths/stack traces.

## Evidence AC

| AC | Evidence |
|---|---|
| Real-looking URL с неподдерживающей цитатой отклоняется | Synthetic ref с official-looking URL fails provenance; identical original quote с invented amount/currency/condition fails semantic support |
| Wrong quote/offset/hash/extraction/source/page/cell/HTML path | 12 independent validator tamper cases, actual reparse/chunk comparison |
| Footnote/conditions/unit/basis/period/date support | Footnote substitution fails; period/date/basis и gte/eq/in thresholds rejects unsupported values |
| Synthetic provenance, revoked grant | Synthetic->real manifest fails; review/publish/read/freeze проверяют revoked policy |
| Concurrent publication один результат | Independent sessions on PostgreSQL schema migrated through Alembic upgrade/check; one fact + idempotent replay |
| Raw/rejected/needs_review не searchable as fact | read_published requires frozen reviewed publication; rejected/pending cannot publish, draft read denied |
| Approved unknown-date quote с limitation | PDF/XLSX/HTML проходят review->publish->freeze->read, DATE_UNKNOWN retained and eligibility false |
| Fully supported fact после manual review | Separate explicitly synthetic analyst proposal checks known scope/date/period and whole-chain confirmation; eligibility positive without mutating extracted candidate |
| Append-only identity/reason/review; rollback | Missing reason/reviewer/unknown user rejected, immutable review DB trigger preserved, publication fault rolls back member/fact |
| Manual CLI и downstream handoff | End-to-end CLI inspect/validate/review/publish case; exact frozen read interface |

Adversarial stored-row substitutions use SQLAlchemy committed identity-map values
без flush, чтобы проверить сам validator независимо от existing DB guards.
Это не обход immutability в production. Concurrent test создаёт временную schema
на dedicated DB, применяет все настоящие migrations/check и удаляет schema.
ORM create_all вместо migration в этом тесте не используется.

## Checks

- uv sync --locked — PASS.
- Ruff — PASS.
- mypy — PASS, 61 source files.
- Windows dedicated DB `bsi_snap09_regression_test`: Alembic upgrade head/check — PASS,
  head 0005_auth, No new upgrade operations detected.
- Полный Windows backend + tools/test_bank_tls_probe.py — PASS,
  **338 passed, 0 skipped**, 204.19 s.
- Linux isolated PostgreSQL 18: Alembic upgrade/check — PASS;
  SNAP-09 suite до последних дополнительных semantic cases — PASS,
  **34 passed, 0 skipped**, 137.86 s.
- После расширения eq/in checks — Windows и Linux relevant subset PASS,
  **6 passed** на каждой платформе.
- Финальный suite с whole-chain flags и positive eligibility — PASS:
  **37 passed, 0 skipped** на Windows (160.96 s) и
  **37 passed, 0 skipped** на Linux (157.24 s).
- Docs validator / git diff --check — PASS; повторены после report.

Числа перекрывающихся запусков не суммируются. Полный suite не выдаётся за проверку
новых cases, добавленных после его запуска: финальный relevant suite указан отдельно.
Windows DB отдельна от app DB; Linux использует временный DB container и внутреннюю
Docker network без внешнего egress. Test originals synthetic, банки/Groq не вызываются.
Временный Linux DB container и его внутренняя network удалены после проверки;
existing app DB/container не менялись.

NOT RUN на момент локальной валидации до commit/push: GitHub CI новой revision,
реальные acquisition/provider/
corpus/gold evaluations, frontend lint/typecheck/build/browser E2E (frontend не менялся),
нагрузочная оценка на реальном corpus. Полный S0 и продуктовая готовность не заявлены.
Повтор existing source-recovery E2E не требовался: ingestion не менялся; общий regression
suite и новые PDF/XLSX/HTML publication E2E покрывают затронутую цепочку.

## Передача и ограничения

После merge — независимая приёмка и отдельное обновление SNAP-09 status интегратором.
SNAP-10/11/16 здесь не реализованы. Public API/RBAC wrapper ещё должен быть создан
SNAP-16; local operator CLI не объявляется HTTP authorization boundary.

Reparse старой extraction после изменения конкретного parser implementation может
дать EXTRACTION_HASH_MISMATCH. Fail closed: immutable rows не переписываются;
оператор создаёт новую processing/candidate/snapshot revision. Reparse является
bounded synchronous operator work; API не должен запускать большие parsing batches.
Frozen read использует approved immutable proof и текущую permission/original verify,
а не запускает parser заново для каждого read. Semantic confirmation — human
attestation, не автоматическая natural-language proof или замена real human gold.

Product gates неизменны: **S1 BLOCKED; S2/S3 NOT EVALUATED; G1/G2 NOT PASSED**.
