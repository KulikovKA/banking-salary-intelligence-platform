# SNAP-08 — исправление дефектов финальной приёмки

Дата: 11.10.2026 (Europe/Moscow).
Base: `e7218b214db016d8a8d8a3f72e56d22f42c26542`.
Ветка: `codex/snap-08-final-review`.
Исходная независимая приёмка: [SNAP-08-final-acceptance.md](SNAP-08-final-acceptance.md).

Все пять обнаруженных дефектов исправлены и подтверждены regression tests.
Исправленная рабочая копия проходит технические критерии SNAP-08 на synthetic.
Merged main ещё содержит исходные дефекты; его историческое решение **BLOCKED**
не подменено результатами незамерженной рабочей копии. DONE/status PR следует
оформить после merge исправлений, в соответствии с AGENTS/MASTER_PLAN.

## Изменения

- H1: exact-value extractor отклоняет отрицание бесплатности, отрицательный знак,
  диапазоны/границы и несколько значений. Auto и operator mapping используют
  целую исходную cell/фразу для этой проверки. Неподдержанное значение возвращает
  diagnostic и не превращается в точную цену/ноль; исходные chunks/refs успешных
  запусков остаются immutable. Range inference не добавлялся.
- H2: candidate evidence содержит immutable row-label/actual-header blocks с
  точными offsets/locators. Текст relation не используется как quote из value-cell.
  Неоднозначная привязка header возвращает diagnostic. Полная исходная фраза
  auto text suggestion также прикрепляется как scope support.
- H3: XLSX возвращает заменённые linked blocks в общий ParseResult до canonical
  hashing. HTML разрешает локальные fragment targets в actual extracted blocks,
  включая encoded Unicode IDs и anchors внутри paragraph/cell. Missing/duplicate
  targets остаются unresolved. Extractor проходит footnotes используемых row
  labels/headers/value blocks, включая связанные notes, и сохраняет condition
  refs с review-required flags. Unresolved references не дают numeric candidate.
- M1: invalid mapping, missing обязательный context и candidate-less output
  возвращают failed result с diagnostic counts без записи extraction chain.
  Оператор может исправить input и повторить тот же parser_version; успешный
  повтор остаётся идемпотентным. CLI уже возвращает nonzero для failed result.
  Это намеренное изменение прежнего тестового поведения, допускавшего запись
  автоматического candidate при invalid mapping.
- M2: POSIX finally завершает process group даже после exit leader. Windows
  Job Object закрывается один раз; повторное использование закрытого handle
  устранено. Timeout, success и crash descendants проверены на обеих платформах.

HTML/XLSX parser versions повышены до `stdlib-html/3` и `openpyxl/3`, поскольку
изменились canonical relations/blocks. Это фактическая версия parser output,
а не фиктивный обход operator mapping repair. DTO, ORM, schema, migrations,
FetchGateway/BlobStore/normalizer/public contracts не менялись. Разрешение исправить
parser internals следует из отдельного поручения пользователя «исправь дефекты»
после отчёта H3; работа выполнена последовательно в одном worktree без subagents.

Изменение уже успешно сохранённого candidate set по-прежнему отклоняется replay
validation: исправление не выполняет UPDATE/DELETE immutable rows и не вводит
скрытую версию schema/config. Старые успешные extraction chains не переписываются.
Обработка legacy chains, если replay ожидает другую evidence после обновления
extractor, требует явной новой processing revision, а не ослабления replay check.

## Проверки

| Проверка | Результат |
|---|---|
| Ruff | PASS, `uv run ruff check .` |
| mypy | PASS, 58 source files |
| Windows dedicated PostgreSQL upgrade/check | PASS, head `0005_auth`, no new operations |
| Windows полный backend + tools/test_bank_tls_probe.py | PASS, **302 passed, 0 skipped**, 69.04 s |
| Windows после последних HTML target изменений: acceptance regressions + HTML parser | PASS, **26 passed, 0 skipped**, 29.81 s |
| Linux dedicated PostgreSQL upgrade/check | PASS, новая isolated test DB, head `0005_auth`, no new operations |
| Linux acceptance + extraction pipeline + runner + PDF/HTML/XLSX + normalizer | PASS, **77 passed, 0 skipped**, 45.87 s |
| Linux standalone process probe | PASS: timeout/success/crash; descendant_alive=false во всех трёх случаях |
| Docs validator | PASS после добавления отчёта |
| git diff --check | PASS |

Числа двух Windows запусков не суммируются: второй запуск покрывает последние
изменения HTML и дополнительные случаи, а полный набор уже прошёл до них.
Новых runtime изменений после последней проверки соответствующего модуля не было.

Windows использует новую DB `bsi_snap08_acceptance_test` исходной приёмки.
Linux использовал PostgreSQL 18 в отдельном временном контейнере и Docker network
`--internal`, без внешнего egress. Dependencies устанавливались из uv.lock до
изолированного run; tests не обращались к банкам/Groq. Изолированный Linux test DB
container остановлен/удалён после проверки. Existing DB контейнер не менялся.

Независимые проверки покрывают первоначальные 9 failures, rollback после candidate
flush, отзыв permission во время parsing, исправление mapping/context без смены
parser version, диапазон с тире/границу, missing/duplicate/Unicode HTML targets,
condition refs для XLSX footnote на label и value cell, header evidence и
worker descendants при success/crash. Existing PG tests сохраняют idempotency,
concurrent replay, provenance/hash/corpus gates, PDF/XLSX/HTML ancestry,
unknown/individual/conditional zero и отсутствие review/publication.

NOT RUN на момент локальной валидации: GitHub CI новой revision,
полный Linux backend suite вне перечисленных 77 cases, memory-exhaustion stress,
frontend/browser E2E (frontend не менялся), real corpus/Groq (нет допуска).
Existing source-recovery E2E не повторялся: ingestion не менялся, исходная приёмка
подтвердила PASS_SYNTHETIC_ONLY с network_requests=0. Зелёный CI base commit не
объявляется CI исправлений.

## Передача

Runtime fixes: `parsing/{runner,service,html,xlsx}.py`, `tariffs/extract.py`.
Regression coverage: existing `test_extraction_pipeline.py`,
`test_parsing_runner.py`, новый `test_snap08_acceptance_review.py` и
`tools/snap08_process_review.py`. Отчёт исходной приёмки сохранён как historical
assessment указанного base commit и связан с этим follow-up.

Рабочая копия находится в `C:/Users/Kirill/Desktop/sber-ai-snap-08-final-review`.
По отдельному поручению пользователя исправления оформляются commit и push
ветки `codex/snap-08-final-review`; PR пользователь открывает самостоятельно.
Результат GitHub CI после push проверяется отдельно от локальных результатов.
TASKS.json/MASTER_PLAN не менялись;
не выставлен преждевременный DONE до merge. SNAP-09 не начинался.

Product gates неизменны: **S1 BLOCKED; S2/S3 NOT EVALUATED; G1/G2 NOT PASSED**.
