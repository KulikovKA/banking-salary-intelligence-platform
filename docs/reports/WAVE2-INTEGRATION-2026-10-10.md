# Вторая волна SNAP — интеграционное ревью, 10.10.2026

**Результат:** пять модулей подготовлены и проверены в общей сборке PR #8.
**Main merge: BLOCKED (GitHub API 403).** Подтверждённых merge нет.
Main остаётся `504c71fb2c9dd914231f92c06d98b623b2b41aca`.
Локальные merge в auth — подготовка совместимой сборки, не обновление main.

## Проверенное состояние GitHub

Все пять PR открыты. Исходный CI четырёх PR был зелёным; PR #8 падал на mypy
из-за отсутствующей declared/locked зависимости Argon2. После исправлений:

| PR / модуль | Проверенный head SHA | CI |
|---|---|---|
| [#9 / SNAP-03](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/9) | `a2c10e9a95da013e7315217cbca020a64dd720b9` | [PASS](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38081516872) |
| [#10 / SNAP-06](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/10) | `61535c005eb5df0045fd992f104b35f3760e2732` | [PASS](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38080538637) |
| [#6 / SNAP-13](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/6) | `27f7fa33f1623325a583d61bdcf9d9a5d9a0ab44` | [PASS](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38080451276) |
| [#7 / SNAP-05](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/7) | `406a0b84665c8115e92d8939b75f22881f5c20c5` | [PASS](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38080805149) |
| [#8 / SNAP-15, общая сборка](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/8) | `624b774cf2f96f7d3720d57139e4e3e5c09fb750` | [PASS](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38081616078) |

Последующий documentation-only commit добавляет этот отчёт и evidence; его CI
проверяется отдельно перед передачей. Code validation SHA — `624b774`.

## Итоги независимого ревью и исправления

**SNAP-03.** Исходный freeze не требовал reviewed publication, а read разрешал
original только после freeze. Добавлены staging с `extraction_run_id: null` и
`read_draft_document(manifest, index)`: до extraction проверяются exact
source/version/fetch/policy, corpus, scope/date и SHA-256 original. Materialized
member создаётся только после успешного extraction. Final freeze требует
reviewed publication для каждого exact member; разрешения проверяются внутри
freeze transaction, а не предварительной отдельной validate transaction.
Frozen read повторно сверяет extraction/source/raw hash, accepted state и права
на всю redirect chain/final URL. Тесты отклоняют подмену original pointer и
неразрешённый redirect. Ни один real grant не создан.

Sequential schema follow-up выполнен добавочной `0004a_corpus_gates`: publication
допускается в locked draft, final freeze требует готовых опубликованных members,
orphan publication отклоняется. После freeze publication закрыта. Это устраняет
цикл «freeze ждёт publication, publication ждёт freeze». Не изменены 0001–0004.
Ранние relational fixtures создают явные synthetic reviews, не автоматическое
одобрение service. Полный semantic evidence validator остаётся SNAP-09.

**SNAP-06.** Сохранены encoding/BOM/meta, Cyrillic/entities, таблицы, spans,
normalized offsets и deterministic paths без JS/subresource fetch. Исправлена
потеря footnote target внутри table cell. Добавлены depth/node/text bounds;
счётчики sibling paths исключают квадратичное сканирование предыдущих siblings.
Версия parser — `stdlib-html/2`. Субпроцессная изоляция остаётся SNAP-08.

**SNAP-13.** Исходный retry считал token allowance один раз. Теперь учитывается
каждый dispatch, UTF-8 byte allowance включает schema/framing, а retry разрешён
только внутри общего input/output/call/deadline cap. Known successful usage
заменяет estimate. Non-JSON HTTP 200 и cancellation после dispatch сохраняют
unknown reservation. Duplicate JSON keys, tool calls и truncated finish rejected.
Добавлен консервативный atomic PG short-window limiter; daily window Moscow,
concurrency и unknown/crash accounting сохранены. Transport переиспользуется,
`aclose` передан владельцу lifespan. Один provider/model, без paid fallback.
Официальные Groq structured outputs/rate-limit docs сверены; live smoke NOT RUN.

**SNAP-05.** Formula/cache разделены; отсутствующий cache остаётся None с review
flag, формулы не выполняются. Exact sheet/cell/range и отношения headers/footnotes
сохранены. Найден обход resource cap: sparse workbook мог материализовать до
50 млн ячеек через iter_rows. Добавлен rectangle bound в XML preflight до openpyxl
и loaded-dimension check. Raw numeric value/number format сохранены отдельно от
отображаемого округления. Версия parser — `openpyxl/2`. PDF dependencies сохранены.

**SNAP-15.** Добавлен и locked argon2-cffi. ORM и migration 0005 согласованы:
nullable RESTRICT user FK в fact_reviews/llm_usage, head 0005 проверяется вместе
с фактическими FK/nullable columns на PG18. Budget fixtures используют явные
synthetic identities; исторические users не выдумываются. Auth совместим с
Settings после SNAP-13; clean locked mypy проходит.

Security review: Argon2id t=3/m=64 MiB/p=4; 256-bit hash-only tokens; invite/reset
one use под row lock; reset lock order user→token; signed anonymous CSRF challenge
на login/invite/reset + exact Origin; session-bound CSRF на mutations; production
__Host-session Secure/HttpOnly/Lax/Path=/ без Domain; login/invite/reset отзывают
прежнюю browser session; idle 8h / absolute 24h; current admin роль повторно
проверяется в mutation transaction; last-admin advisory guard выдерживает race;
5/account и 20/IP в минуту с bounded memory; credentials не отражаются в 422/logs.
Reusable AuthContext dependencies переданы SNAP-16. Default production password нет.

Все изменённые paths находятся в модулях задач либо явно перечисленных выше
sequential integration fixes к schema/tests/dependencies/reports. Frozen
`backend/app/contracts/**`, main.py, frontend, FetchGateway/BlobStore/operator
implementations и migrations 0001/0002/0003/0004 сохранены. Subagents не запускались.

Промежуточные failures исправлены до итоговой приёмки: null extraction UUID,
обновлённый retry/token тест, lint line lengths после edits, невалидный PDF
container у corruption fixture, TestClient domainless duplicate-cookie fixture.
Final PASS относится к указанным финальным checks, не к этим промежуточным run.

## Интеграционные проверки общей сборки

Проверки выполнены в auth review branch, содержащей все пять модулей, **не на
merged main**. Проверки итогового main — NOT RUN: merge блокируется API 403.

| Проверка | Итог |
|---|---|
| uv sync --locked | PASS, 58 resolved packages; Argon2/PDF/XLSX сохранены |
| Полный Ruff | PASS |
| Strict mypy backend/app | PASS, 54 source files |
| Полный pytest backend/tests + tools/test_bank_tls_probe.py | PASS: **268 passed, 0 failed, 0 skipped**, без warnings |
| PG18 upgrade + Alembic check | PASS на dedicated bsi_wave2_test; clean migrations и no schema drift |
| Upgrade с 0004 + check | PASS на dedicated bsi_e2e до 0005 через 0004a |
| Existing source-recovery synthetic E2E | PASS_SYNTHETIC_ONLY; **network_requests=0** |
| Frontend lint / typecheck / build | PASS, Node 24.19.0 / npm 11.17.0 |
| docs validator / git diff --check | PASS |
| Auth identity → PG quota/user FK → mocked Groq settlement + Fake | PASS, отдельный integration test |
| Browser E2E нового UI | NOT RUN: UI не изменялся; закрытый интерфейс остаётся SNAP-17 |
| Новый PDF/XLSX/HTML→candidate pipeline | NOT RUN: это SNAP-08, реализация не начиналась |
| Live Groq / real bank acquisition | NOT RUN: нет ключа/approved payload и verified source-specific допуска |

E2E artifact: [wave2-source-e2e.json](evidence/wave2-source-e2e.json), run
`8216297f3b9849c9a70db3fd11bf93db`, accepted synthetic originals/hash chain,
archive reconcile missing/orphan = 0. Synthetic result не является real S1/S3 PASS.

## Что заблокировано и как завершить merge

GitHub connected API вернул `403 Resource not accessible by integration` на merge
PR #9 после зелёного CI и на попытку обновления title/body PR #8. Изменение PR
metadata также не выполнено. Commit/push через существующий git access успешны.
Force-push, переписывание истории, удаление веток и direct push main не выполнялись.

1. В GitHub объединить **#9 → #10 → #6 → #7 → #8**, выбирая **Create a merge commit**.
2. После каждого merge проверить merged state/SHA и дождаться зелёного CI нового
   main. Если CI упадёт — исправить до следующего merge. Не считать старый PR CI
   проверкой нового main. Сверить head SHA с таблицей и свежими checks.
3. PR #8 уже содержит reviewed commits четырёх prerequisites; merge commits
   сохраняют общую ancestry, после первых четырёх merge в diff останется auth
   integration и report. Не нужно реализовывать готовые модули заново.
4. После пятого merge fast-forward local main, подтвердить inclusion всех пяти
   heads и повторить итоговые checks именно main.
5. Только после этого применить подготовленный локальный
   `.local/wave2-post-merge-status.patch` к MASTER_PLAN/TASKS, запустить docs validator
   и закоммитить **оба файла одним commit**. Patch проверен `git apply --check`, но
   **не применён**: до merge центральные статусы не должны выдавать DONE.

Подготовленный текст для title/body PR #8 изложен в [SNAP-15.md](SNAP-15.md).
Для ручного merge дополнительное подтверждение намерения не требуется — действие
уже поручено пользователем; нужен аккаунт с доступом к кнопке merge.

## Актуальные статусы и следующая волна

SNAP-03/05/06/13/15: code/harness reviewed, CI PASS, **READY_FOR_MANUAL_MERGE**.
Авторитетные MASTER_PLAN/TASKS сохраняют **TODO** для всех пяти до actual merge.
Ни одна задача не объявлена DONE на основании только отдельной ветки.

S0 полного продукта не завершён; **S1 BLOCKED**, **S2/S3 NOT EVALUATED**,
**G1/G2 NOT PASSED**. Недопущенный corpus не мешает закончить независимый harness.

После подтверждённых merge следующая доступная coding задача — **SNAP-08**.
Технический цикл draft/extraction/publication/freeze устранён; accepted originals
можно читать до extraction через exact draft manifest без обхода permission/hash.
Оставшиеся prerequisites на main — фактические merge и итоговый CI, а не real data.
SNAP-09 следует за 08; SNAP-10 и 11 — за 09; SNAP-14 — за 10+11+13;
SNAP-16 — за 03+09+14+15. Сейчас эти новые задачи не реализовывались.
Human source decisions/labeling можно готовить отдельно без acquisition bytes.
