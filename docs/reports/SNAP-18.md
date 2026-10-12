# SNAP-18 — Audit существующего corpus и evaluation harness

Дата: 13.10.2026, Europe/Moscow. Base main: `688877d` после `git fetch origin --prune`.
Ветка: `codex/snap-18-evaluation`. **READY FOR REVIEW для независимого harness;
реальная приёмка BLOCKED.** MASTER_PLAN/TASKS и SNAP-01–17 не изменены.

## A. Что есть прямо сейчас

Прочитаны README, SNAP-18 prompt, MASTER_PLAN, acceptance criteria, source recovery,
source status, architecture/domain/DB/API/security contracts и отчёты зависимостей.
README/часть architecture описывают старый scaffold; main реально содержит services,
Groq/Fake, auth, API и desktop chat. Источник состояния — merged code и миграции.

В registered worktrees и настроенном storage проверено **87 файлов, 25 уникальных
SHA-256**: 16 PDF и 71 HTML. Это synthetic test originals, parsing fixtures и
HTML test reports; реальные банковские originals в этих каталогах не найдены.
XLSX в проверенных каталогах не найден. Это ограниченная инвентаризация проекта,
не заявление об отсутствии документов на всём компьютере. Конкретный каталог
реальных документов запрошен у пользователя; ответа на момент отчёта нет.

Два известных research-only SHA-256 Кубань Кредит из SOURCE_STATUS также не найдены.
Research archive не импортировался. Файл/robots/HTTP200 не трактуется как permission.
Имена, полные пути, размеры и hashes всех найденных файлов сохранены только в
приватном `.local/snap18/private-audit.json` исходного checkout. Публичный
[safe summary](evidence/snapshot-evaluation/local-audit-summary.json) содержит
проверяемые агрегаты, без путей/секретов/текста originals.

Существующий `.env` прочитан без shell execution, копирования или публикации.
Настроенный LocalBlobStore **отсутствует**. PostgreSQL подключён успешно;
`transaction_read_only=on`, read-only repeatable-read, затем rollback.
Application DB находится на **0002_source_recovery**, не на main head 0005_auth.
Рабочая DB не мигрировалась и не изменялась.

| Банк | Найденные real originals | Accepted versions | Real parsed/published доступно | Frozen real |
|---|---:|---:|---|---|
| Сбер | 0 в проверенных roots | 0 | Нет | Нет |
| ВТБ | 0 в проверенных roots | 0 | Нет | Нет |
| Альфа-Банк | 0 в проверенных roots | 0 | Нет | Нет |
| Кубань Кредит | 0; известные research hashes не найдены | 0 | Нет | Нет |

`sources`, `source_versions`, `source_fetches`, `source_policies` — **0 rows**.
Следовательно, цепочка остановилась до регистрации источников/import; отсутствие
публикаций не свидетельствует о плохом parser. `extraction_runs`, `document_chunks`,
`tariff_candidates`, `evidence_refs`, `fact_reviews`, `published_facts`, `snapshots`,
`snapshot_members` отсутствуют: подсчёты **NOT RUN / TABLE_ABSENT**, а не фиктивный
нулевой результат SQL. Доступных реальных документов/фактов для чата — **0**.
Нельзя открыть извлечённые банковские chunks/цитаты, которых здесь ещё нет.

## B. Что удалось проверить

Добавлены только `evaluation/**`, `tools/evaluate_snapshot.py`, этот report,
[evaluation report](SNAP-18-evaluation.md) и safe synthetic evidence.

Harness проверяет JSON schema и exact byte hash, binding snapshot/revision/kind,
уникальность IDs, references и отсутствие document-family leakage. Quality metrics
на holdout: evidence linkage, value/unit/basis/period/payer/scope/date correctness,
conditions recall, Recall@10, comparison correctness, intent и unsupported structured
claims/numeric tokens. Есть exact numerator/denominator, все четыре банка/шесть пар,
minimum sample requirements, coverage, missing/skipped/blocked и provider metadata.
Пустой denominator — NOT EVALUATED; пропущенные observations уменьшают качество.

Synthetic gold: **44 facts (40 holdout + 4 tune), 40 questions (36 holdout + 4 tune),
30 comparisons**, отдельные tune/holdout document families, **0 human reviews**.
Per bank holdout: 10 facts/6 questions. Каждая из шести пар: 2 questions/5 comparisons.
Coverage намеренно содержит только 1 comparable criterion на пару и честно BLOCKED,
не имитирует недостающий второй реальный критерий.

ComparisonService реально выполнен на 30 независимо заданных synthetic golden cases:
обычная комиссия, условный zero, unknown, individual и conflicting records для всех
шести пар. Ни engine, ни frozen DTO, ни ORM/API/frontend не переписывались.
Extraction/evidence/retrieval/intent capture в gold — authored synthetic replay;
его PASS проверяет evaluator, не real tariffs/FTS/model quality. Реальные backend
parser/FTS/review/assistant/MockTransport integrations проверяются отдельным suite.

Faulty capture даёт FAIL для всех шести требуемых quality metrics: неправильная
комиссия/период, потерянные обязательные условия, неверный locator, retrieval miss,
подмена unknown/individual/conflict, неподтверждённое число/claim. Дополнительные
tests проверяют raw hash/quote/date/scope, missing observations, schema errors,
duplicate IDs, leaked families, Recall@10 cutoff, exact thresholds и repeatability.

Groq adapter/processing admission boundary присутствуют в merged main. В существующем
env ключ **задан**, model — `openai/gpt-oss-120b`, mode — **fake**. Настройки не проходят
нынешнюю validation для `LLM_MAX_INPUT_TOKENS`/`LLM_MAX_OUTPUT_TOKENS`.
Подлинность ключа не проверялась. Snapshot-specific processing admission отсутствует
в проверенном окружении вместе со storage/snapshot. Внешний run отдельно не разрешён;
**0 bank/Groq requests**, live model usage/latency/429 NOT RUN. Fake/MockTransport
не выдаются за реальный API smoke. Production settings не корректировались.

## C. Что мешает перейти на реальные тарифы

| Blocker / evidence | Действие ответственного | Необходимое подтверждение |
|---|---|---|
| Реальные файлы не найдены в worktrees/configured storage | Пользователь сообщает каталог и provenance; оператор сопоставляет hashes/URLs/dates | Хранение и local diagnostic reuse конкретных originals |
| 0 sources/policies; SOURCE_STATUS содержит pending/BLOCKED | Ответственный reviewer фиксирует exact URLs/method, acquisition/storage/reuse basis, scope/expiry/revocation | Source-specific решение настоящего reviewer; Codex не создаёт его |
| DB 0002, отсутствуют pipeline tables, storage отсутствует | Владелец окружения отдельно обновляет app DB после backup/recovery проверки и восстанавливает правильный storage | Отдельное поручение на изменение рабочей DB/settings/storage |
| 0 accepted versions/extractions/reviews/publications/frozen members | После допуска оператор import → accept_content → manifest → parsing → manual review/publication → freeze | Реальные content/review решения, immutable provenance |
| Нет human gold и real comparable fee coverage | Эксперт размечает >=40 фактов, >=24+12 вопросов, >=30 cases; >=2 criteria и >=1 numeric fee каждой паре; фиксирует split/hash | Ручная независимая разметка; неизвестное не заменять нулём |
| Provider caps invalid; нет admitted snapshot и разрешения run | Config owner проверяет caps по текущему Settings; processing reviewer выдаёт отдельное решение, пользователь разрешает bounded run | Terms/processing/retention/corpus reuse и >=20 допустимых real-model вопросов для S3 |

В актуальном Settings caps: input <=4000 и output <=1000. Это описание контракта,
не рекомендация автоматически исправить env. Не выданы grants, не изменены collection
decisions, не создан reviewer, не опубликован факт. G1/G2 остаются NOT PASSED.

Диагностические категории audit: PARSE_FAILED, NEEDS_OCR, NO_RELEVANT_CONTENT,
ZERO_CANDIDATES, ALL_CANDIDATES_REJECTED, MISSING_EVIDENCE, AMBIGUOUS_VALUE,
MISSING_CONDITION, UNKNOWN_SCOPE, UNKNOWN_DATE, CONFLICTING_TARIFFS.
Для runtime real corpus все **NOT RUN**: нет originals/import/extraction rows.
Причины исторического parsing не выдумывались; diagnostic persistence требует
schema-owner follow-up, а не новых API/DB statuses в этом PR.

## D. Итоговые оценки и проверки

| Gate | Результат | Основание |
|---|---|---|
| S0 | NOT EVALUATED целиком; harness PASS_SYNTHETIC_ONLY | API/UI/recovery/полная сквозная приёмка отдельны; frontend не менялся |
| S1 | BLOCKED | Нет допущенного четырёхбанковского frozen corpus |
| S2 | NOT EVALUATED | Нет real holdout/human gold; synthetic не заменяет их |
| S3 | NOT EVALUATED | Нет provider admission/authorized run; env invalid |

Проверки и финальные числа см. [SNAP-18-evaluation](SNAP-18-evaluation.md).
Application DB оставлена на прежней revision; отдельная random-named dedicated
PostgreSQL test DB обновлена всеми существующими Alembic migrations и проверена
на drift. SQLite не заменяет PG. Тестовые credentials не скопированы в новый env.

## E. Как посмотреть данные локально

В worktree SNAP-18 выполните PowerShell-команды:

```powershell
uv sync --locked
$existingEnv = Read-Host 'Полный путь к существующему .env'
$projectRoot = Split-Path -Parent $existingEnv
uv run python tools/evaluate_snapshot.py audit --env-file $existingEnv `
  --root $projectRoot --output .local/audit-existing-env.json
$audit = Get-Content -Raw .local/audit-existing-env.json | ConvertFrom-Json
$audit.files | Select-Object name,format,bytes,sha256,path
$audit.database.versions | Format-Table
$audit.database.extractions | Format-Table
$audit.database.chunk_counts | Format-Table
$audit.database.candidates | Format-List
$audit.database.evidence_counts | Format-Table
$audit.database.published | Format-Table
$audit.database.snapshots | Format-Table

$goldHash = (Get-Content evaluation/fixtures/synthetic-gold.sha256).Trim()
uv run python tools/evaluate_snapshot.py compare `
  --gold evaluation/fixtures/synthetic-gold.json --gold-sha256 $goldHash `
  --observations evaluation/fixtures/synthetic-observations.json `
  --output .local/evaluation/synthetic
Get-Content .local/evaluation/synthetic.md
# Inspect authored synthetic chunks/quotes, clearly separate from real data:
$gold = Get-Content -Raw evaluation/fixtures/synthetic-gold.json | ConvertFrom-Json
$gold.evidence | Select-Object chunk_id,quote,locator
$gold.facts | Select-Object bank,metric,value,status,required_conditions
```

`audit` не загружает env в shell и не запускает DB migrations. При известном ином
каталоге originals добавьте ещё один `--root`; не скачивайте documents заново.
Reports с абсолютными путями/real contents остаются вне Git. Existing desktop chat
после отдельной настройки окружения доступен обычным локальным запуском из SNAP-17;
без readable frozen corpus выбора/данных не появится. Future approved candidate
inspection использует существующий `app.evidence.cli inspect` с точным manifest;
реальную цитату и original можно открыть через authenticated API после допуска.

## Передача

READY FOR REVIEW относится к коду harness и safe evidence. Four-bank release
BLOCKED. Merge и task statuses — интегратор; этот PR их не меняет. Пользователю
нужно прежде всего указать каталог real originals/правильное окружение, затем
обеспечить настоящие approvals/review/gold. Env/DB/storage изменений и provider run
в этом поручении не выполнялось. Subagents не запускались, чужие изменения сохранены.
