# SNAP-08 — независимая финальная приёмка

Дата: 11.10.2026 (Europe/Moscow). Решение: **BLOCKED**.
Проверенный commit: `e7218b214db016d8a8d8a3f72e56d22f42c26542`.
GitHub API подтвердил merge [PR #14](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/14)
именно в этот commit; `origin/main` при приёмке совпадал с ним.
Worktree: `C:/Users/Kirill/Desktop/sber-ai-snap-08-final-review`,
ветка `codex/snap-08-final-review`. Реализация не изменялась.

Этот отчёт фиксирует историческую приёмку указанного merged commit.
Последующее поручение пользователя на исправление выполнено отдельно;
актуальные изменения и проверки: [SNAP-08-remediation.md](SNAP-08-remediation.md).

Найдены **3 High и 2 Medium** дефекта. Critical и Low не выявлены.
Зелёный существующий CI не покрывает найденные случаи. Все кандидаты остаются
pending_review; дефекты не являются доказательством уже опубликованных неверных фактов.
Но ложные значения и неполная evidence chain нарушают AC самого SNAP-08.

Прочитаны AGENTS, README, MASTER_PLAN, SNAP-08 prompt/report, архитектурные
OVERVIEW/DOMAIN_CONTRACTS/DATABASE_DESIGN/API_CONTRACTS/SECURITY, продуктовые AC,
DTO, ORM, миграционные guards, normalizer, CorpusService, parser/runner/pipeline/CLI
и тесты. SNAP-09 prompt использован только для проверки входного интерфейса;
реализация SNAP-09 не начиналась.

## Дефекты и минимальные исправления

### H1 — High: неподдержанные точные значения и ложный ноль

Файлы: `backend/app/tariffs/extract.py:355` (`_extract_text`),
`:506` (`_value_shape`), `:541` (`_value_matches`), `:178` (`_mapped_rule`).

Подтверждено реальным parsing и PostgreSQL persistence:

| Original text / метод | Записанный candidate.value | Требуемое поведение |
|---|---|---|
| «Обслуживание счета от 100 RUB в месяц.» / auto | money 100 | Range с нижней границей либо diagnostic/manual mapping; не точная цена |
| «Обслуживание счета в месяц — не бесплатно.» / auto | money 0, conditions_text «бесплатно» | Unknown/diagnostic; отрицание не означает нулевую цену |
| «100 RUB или 200 RUB» / mapped block | money 100 | Неоднозначность, а не выбор первой цены |
| «Обслуживание счета -100 RUB в месяц.» / auto | money +100 | Сохранить знак для validation либо diagnostic; не превращать отрицательное значение в положительное |

Причина: regex выделяет сумму без qualifiers/отрицания/знака; auto передаёт в
value-shaping уже усечённую substring. Mapping передаёт всю cell, но `_value_shape`
делает первый `search`, не проверяя остальные значения. Evidence может технически
совпадать с substring и при этом не поддерживать полученное значение.

Минимальное безопасное исправление: до формирования numeric suggestion проверять
контекст целой cell/фразы, знак, negation, диапазоны и альтернативы. Для
неподдержанных конструкций возвращать diagnostic с исходной evidence, без money
candidate. Поддержку range можно добавить отдельно в существующий union; она
не обязательна для безопасного отказа. Не менять normalizer/DTO и не пытаться
устранить это только на стадии review. Четыре regression cases в audit suite FAIL.

### H2 — High: merged header определяет метрику, но не входит в EvidenceRef

Файл: `backend/app/tariffs/extract.py:260`, особенно `:329–347` (`_extract_table`).

XLSX: merged `A1:B1` = «Обслуживание счета в месяц», таблица `A2:B3`,
`B3` = «100 RUB». Candidate account_monthly_fee создаётся благодаря merged header,
но его refs содержат только value «100 RUB» и unit «RUB» с locator `B3`.
Evidence для `A1:B1` отсутствует. Relations и весь header chunk сохранены,
но это не заменяет связи candidate -> supporting evidence.

Причина: `header_blocks` используется только как boolean review flag.
Extractor не добавляет цитату из фактического header block и не сохраняет
связь candidate с ячейкой, определившей смысл метрики. Аналогично важные
metric-label cells строки не становятся support автоматически.

Минимальное исправление: разрешать используемые column/merged headers в immutable
blocks и добавлять exact support refs (например, scope/соответствующая unit/basis
роль). При неоднозначной привязке — diagnostic/manual mapping вместо candidate
с неполной supporting chain. Не создавать quote из одного только relation.value
с locator value-cell. Regression merged-header case FAIL.

### H3 — High: footnotes теряются между parser и extractor

Файлы: `backend/app/parsing/xlsx.py:372`, `:530–567`;
`backend/app/parsing/html.py:346–356`;
`backend/app/tariffs/extract.py:395` (`_with_linked_footnotes`).

В XLSX обе реальные конструкции — marker на value-cell и marker на metric-label
cell — дают candidate без condition EvidenceRef для `A4` («* При поддержании
остатка.»). В HTML таблица с `100 RUB<a href="#note">*</a>` и локальной
`<p id="note" role="doc-footnote">...` тоже даёт только value/unit refs.

Причины:

- XLSX `_link_footnotes(sheet_blocks)` заменяет элементы локального списка
  `sheet_blocks` через model_copy, а общий `blocks`, используемый в ParseResult
  и extraction hash, продолжает содержать старые объекты без этих relations.
- HTML parser сохраняет `href`/element_path anchor, а extractor ищет только
  `related_block_id`; фактический локальный target не разрешается.
- Extractor проходит footnote relations только на уже выбранных supports;
  ссылка на metric-label/header cell также должна учитываться.

Минимальные follow-up владельцам: SNAP-05 — вернуть linked blocks в общий result
перед canonical hash; SNAP-06 — детерминированно связать local fragment с target
block без fetch; SNAP-08 — проходить связанные supports всей используемой
строки/header и сохранять exact condition refs с review-required flag.
При неразрешимой ссылке безопасно остановить numeric suggestion с diagnostic.
Parser files read-only для SNAP-08: исправлять отдельным последовательным merge
владельцев, без скрытого изменения frozen DTO/schema. Все три footnote cases FAIL.

### M1 — Medium: исправленный mapping конфликтует с ранее записанным extraction

Файл: `backend/app/parsing/service.py:168–172`, `:278–290`, `:506–514`.

Первый запуск для «100 RUB» с missing mapped block возвращает diagnostic,
status ok, candidate_count 0 и сохраняет immutable extraction. После исправления
mapping тот же original/parser_version/extraction_hash даёт
`EXTRACTION_REPLAY_MISMATCH`: candidate set изменился, run_id остался тем же.
Аналогичен риск первого запуска без обязательного context и последующего уточнения.
Это не случайная UUID-коллизия, а отсутствующая идентичность candidate extraction
configuration. Неизменённые повторные/конкурентные запуски работают правильно.

Минимальное исправление для воспроизведённого сценария: не финализировать successful
chain при invalid mapping/missing обязательном context; возвращать repairable
ошибку до `_persist`. Для изменения уже успешно принятого mapping нужна явная
версия candidate extraction configuration, согласованная с владельцем контракта/
схемы. Не обходить проблему выдуманной новой версией parser и не UPDATE immutable
candidate. Regression correction case FAIL.

### M2 — Medium: Linux оставляет descendants после success/crash leader

Файл: `backend/app/parsing/runner.py:248–263`.

Контролируемая Linux-проба существующего runner, в Docker `--network none`,
запускает sleeping descendant из тестового bootstrap. Результат:

| Завершение worker | Outcome | Descendant alive после возврата |
|---|---|---|
| timeout | PARSE_TIMEOUT | false |
| success | ok | true |
| crash | PARSE_WORKER_CRASH | true |

Проба завершила оставшихся descendants сама. Это проверка lifecycle runner с
тестовым bootstrap, а не утверждение, что текущие trusted parsers создают subprocess.

Причина: except/finally вызывают cleanup только при `process.poll() is None`.
На Linux exited leader не означает exited process group. Windows закрывает Job
Object в finally и такого поведения в выполненном Windows timeout test не показал.

Минимальное исправление: завершать созданную POSIX process group во всех exit paths,
включая exited leader; сохранить обработку ProcessLookupError и reap прямого
worker. Добавить success/crash descendant regressions наряду с timeout.
Существующие ограничения memory/CPU/file-size/env/shell=False не отменяют этот дефект.

## Проверенные свойства и AC

| Проверка | Решение / основание |
|---|---|
| Provenance, accepted version, permission до обработки, store.verify | PASS: CorpusService проверяет source/version/fetch/policy/bank/corpus/URL/date/hash/rights; verify вызывается до parser. Повторная проверка в write transaction есть. PG cases wrong hash/revoked/quarantine/corpus mismatch зелёные |
| Точные offsets/hash/locator и ancestry записанных refs | PASS для сохранённых refs в PDF/XLSX/HTML PG cases и migration guards. Семантическая полнота refs FAIL по H1/H2/H3 |
| Повторные и конкурентные запуски | PASS для одинаковых inputs: snapshot/version row locks, unique extraction key, replay validation. Изменение mapping блокируется по M1 |
| IDs source_version/parser_version/extraction | В run UUID входят все три компонента; child IDs scoped run UUID. Изменение parser_version протестировано. Очевидных межверсионных коллизий не найдено; отдельный same-bytes/different-source PG stress case NOT RUN |
| Транзакция и rollback | PASS: единый factory.begin для extraction/chunks/candidates/refs. Независимая ошибка before_flush EvidenceRef после записи кандидата откатывает все четыре таблицы; parser crash/timeout тоже не оставляют chain |
| Отзыв permission во время parsing | PASS: независимый PG test отозвал policy после parse; перед write получен PERMISSION_REVOKED и extraction отсутствует |
| Windows/Linux bounded subprocess | Windows parser runs и worker/descendant timeout PASS. Linux lifecycle timeout PASS, success/crash cleanup FAIL по M2. Нет shell execution; env не передаёт DB/Groq/application secrets |
| Unknown/individual/conditional zero | Базовые PG случаи PASS, unknown не становится 0. Negation/range/ambiguous/sign handling FAIL по H1 |
| Diagnostic proposals и mapping | Без metric/value остаются safe diagnostic counts, не published facts; mapping не исполняет код. Repairability FAIL по M1; диагностик без persistence честно документирован |
| Synthetic PDF/XLSX/HTML до pending candidates в PG | PASS существующих integration cases; partial failed/needs_ocr output не persist. Все кандидаты pending_review, review/publication отсутствуют |
| Merged headers/footnotes сохраняют support roles | FAIL H2/H3, поэтому полная SNAP-08 acceptance не достигнута |
| Готовность для SNAP-09 | DTO/ORM/immutable chain пригодны для downstream validation, но evidence семантически неполна и значения искажаются. NOT READY до исправления High findings |

Replay дополнительно проверяет chunks, candidate payloads и часть evidence fields;
полная независимая проверка original/extraction hashes, locator validity и semantic
support принадлежит SNAP-09. Техническое substring match не считается semantic PASS.
Текущие parsers доверенные и offline; socket monkeypatch — defense in depth, не OS
network/filesystem sandbox, что прямо отмечено в runner документации.

## Выполненные проверки

Dedicated новая DB: `bsi_snap08_acceptance_test`, PostgreSQL существующего local
container; база приложения и прежние test DB не изменялись. SQLite не использовался
в domain integrations; существующий unit transaction-helper test сохранён.

| Проверка | Результат |
|---|---|
| uv sync --locked | PASS |
| uv run ruff check . | PASS, включая новые review probes |
| uv run mypy backend/app | PASS, 58 source files |
| Alembic upgrade head на новой dedicated DB | PASS, 0001 -> 0005_auth через 0004a |
| Alembic check | PASS, No new upgrade operations detected |
| uv run pytest backend/tests tools/test_bank_tls_probe.py -q на merged code до добавления audit tests | PASS, **283 passed, 0 skipped**, 43.10 s |
| Независимые PG acceptance regressions | FAIL: **9 failed, 2 passed, 0 skipped**, 11 cases. Failures: четыре value cases, header, mapping repair, две XLSX footnotes, одна HTML footnote. Passed: write rollback и mid-parse permission revoke |
| Linux lifecycle probe | Timeout PASS; success/crash descendant cleanup FAIL. Контейнер без сети; полный Linux parser suite локально NOT RUN |
| Existing synthetic source recovery E2E | PASS_SYNTHETIC_ONLY, network_requests=0, missing/orphan blobs=0 |
| python tools/validate_docs.py через uv Python | PASS; после отчёта повторён |
| git diff --check | PASS |

Source-recovery E2E вызван через существующую `run_synthetic_e2e(factory, output_root)`
на новой isolated DB, чтобы не писать в ранее существующие bsi_test/bsi_e2e.
CLI E2E имеет whitelist этих двух имён; guard и исходники не менялись.
Artifact: `.local/source-recovery-acceptance/037feccad6a84492a8dbe30b7b51a1f9/result.json`.

[CI итогового main](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38097368777):
GitHub REST API подтвердил head_sha exact commit, event push, completed/success.
Backend и frontend jobs success; step statuses включают Ruff, mypy, Alembic
upgrade/check, pytest, docs validator, synthetic E2E, frontend lint/typecheck/build.
Логи CI с отдельными числовыми результатами pytest не скачивались; указанные выше
числа — локальные результаты, а не предположение по зелёному значку.

NOT RUN: memory-exhaustion stress; полный локальный Linux parser/PG suite;
frontend checks локально и browser E2E (UI не менялся); real sources/Groq/real-corpus
eval (нет допуска, только synthetic). Browser E2E не приписан зелёному CI.

## Воспроизведение и handoff

Добавлены только этот независимый report и:

- `backend/tests/test_snap08_acceptance_review.py` — исполняемые PG regressions.
- `tools/snap08_process_review.py` — Linux lifecycle probe с контролируемым bootstrap.

PG regressions: задать TEST_DATABASE_URL на dedicated migrated test DB и выполнить
`uv run pytest backend/tests/test_snap08_acceptance_review.py -q --tb=short`.
Linux probe: PYTHONPATH должен указывать на backend; запускать Python с Pydantic
в Linux контейнере без сети. Probe использует source runner из этого worktree,
не код runner из старого Docker image, и сам очищает тестовых descendants.

Runtime, contracts, ORM, migrations, original SNAP-08 report, TASKS.json,
MASTER_PLAN и прочие статусы/зависимости не изменены. Статус SNAP-08 в обоих
реестрах оставлен TODO: условие пользователя для DONE/отдельного status commit/PR
не выполнено. Commit/push/PR не создавались. Не включать эти expected-failing
regressions в main без согласованного исправления; они оставлены для review.

Следующий шаг — минимальные fixes SNAP-08 и последовательные parser-owner
follow-ups H3, затем повтор только затронутых проверок и финальная приёмка.
SNAP-09 в этом поручении не выполнялся.

Продуктовые gates неизменны: **S1 BLOCKED; S2/S3 NOT EVALUATED; G1/G2 NOT PASSED**.
