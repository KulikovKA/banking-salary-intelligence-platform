# MASTER PLAN — snapshot v1

Цель: работающий closed AI-ассистент по четырём банкам на фиксированном официальном
корпусе. [Архитектура](../architecture/OVERVIEW.md),
[приёмка S0–S3](../product/ACCEPTANCE_CRITERIA.md), [Codex](../../AGENTS.md).
Машиночитаемый реестр: [TASKS.json](TASKS.json); executable prompts — таблица ниже.
WORK/TASK/luna пакетов в main нет: они сохранены в ветке archive.

## Реализованная основа и blockers

Каталог/0001/0002/0003, config, FetchGateway/TLS/robots/transport, immutable BlobStore,
operator fetch/import/accept_content, discoveries ВТБ/Кубань Кредит, evidence DTO,
synthetic PG E2E и CI уже существуют. Не переписывать их.
Стартовый API/UI есть, бизнес-сервисы ещё нет. New tasks TODO — не утверждение,
что уже работающие ingestion компоненты отсутствуют.
Ни один новый real source grant этой итерацией не выдан. Официальный corpus
четырёх банков не принят. Historical G1/G2 NOT PASSED. S1 BLOCKED,
S2/S3 NOT EVALUATED; полный S0 ждёт реализации нового pipeline.

## Задачи и последовательность

Номера — безопасный default последовательный порядок. Каждая карточка содержит
конкретные owned paths, implementation, tests, AC, effort и ограничения.
При исполнении без параллелизма выдавай один файл целиком и проверяй его отчёт.

| Prompt | Результат | Merged зависимости | Effort | Status |
|---|---|---|---|---|
| [SNAP-01](prompts/SNAP-01.md) | Зафиксировать исполняемые DTO и Protocol | — | high | DONE |
| [SNAP-02](prompts/SNAP-02.md) | Добавить schema snapshot и тарифного pipeline | SNAP-01 | high | TODO |
| [SNAP-03](prompts/SNAP-03.md) | Операторский corpus manifest и freeze service | SNAP-02 | high | TODO |
| [SNAP-04](prompts/SNAP-04.md) | PDF parser с page/table evidence | SNAP-01 | high | TODO |
| [SNAP-05](prompts/SNAP-05.md) | XLSX parser без вычисления формул | SNAP-01 | high | TODO |
| [SNAP-06](prompts/SNAP-06.md) | HTML parser сохранённого original | SNAP-01 | medium | TODO |
| [SNAP-07](prompts/SNAP-07.md) | Нормализация тарифов и registry метрик | SNAP-01 | high | TODO |
| [SNAP-08](prompts/SNAP-08.md) | Последовательный parsing/extraction pipeline | SNAP-03, SNAP-04, SNAP-05, SNAP-06, SNAP-07 | high | TODO |
| [SNAP-09](prompts/SNAP-09.md) | Evidence validation, manual review и publication | SNAP-08 | high | TODO |
| [SNAP-10](prompts/SNAP-10.md) | PostgreSQL FTS по frozen corpus | SNAP-09 | medium | TODO |
| [SNAP-11](prompts/SNAP-11.md) | Детерминированный Comparison Engine | SNAP-09 | high | TODO |
| [SNAP-12](prompts/SNAP-12.md) | LLM Protocol, Fake и bounded renderer inputs | SNAP-01 | medium | TODO |
| [SNAP-13](prompts/SNAP-13.md) | GroqCloud Free adapter и quotas | SNAP-02, SNAP-12 | high | TODO |
| [SNAP-14](prompts/SNAP-14.md) | Evidence-first ассистент и renderer | SNAP-10, SNAP-11, SNAP-13 | high | TODO |
| [SNAP-15](prompts/SNAP-15.md) | Приглашения, auth и server sessions | SNAP-02 | high | TODO |
| [SNAP-16](prompts/SNAP-16.md) | FastAPI routers и composition root | SNAP-03, SNAP-09, SNAP-14, SNAP-15 | high | TODO |
| [SNAP-17](prompts/SNAP-17.md) | Next.js закрытый интерфейс ассистента | SNAP-16 | medium | TODO |
| [SNAP-18](prompts/SNAP-18.md) | Реальный corpus gold и оценка S1/S2/Groq | SNAP-03, SNAP-09, SNAP-11, SNAP-14 | high | TODO |
| [SNAP-19](prompts/SNAP-19.md) | Сквозная приёмка и минимальная эксплуатация | SNAP-17, SNAP-18 | high | TODO |

Только TASKS.json и эта таблица отражают активные статусы. Интегратор обновляет
их одним commit после принятого отчёта; валидатор проверяет совпадение и DAG.
DONE модуля не означает S1/S2/S3 PASS. При data blocker module harness можно
закончить, а real acceptance остаётся NOT EVALUATED/BLOCKED в report.

## Параллельные волны без конфликтов

1. SNAP-01 — первым, frozen public DTO/Protocol; downstream не редактируют contracts.
2. После 01: SNAP-02 (schema), 04 (PDF), 05 (XLSX), 06 (HTML), 07 (normalization),
   12 (Fake) по независимым paths. Shared dependencies: 04 первым коммитит
   pyproject/uv.lock, затем 05; отдельные parser modules можно писать одновременно.
3. После 02: SNAP-03 corpus/source readiness и SNAP-15 auth. После 02+12:
   SNAP-13 Groq. Auth migration/lockfile merge после schema/parser merges;
   config.py принадлежит 13, auth пользуется существующим Settings.
4. SNAP-08 интегрирует parsers/corpus/normalize; затем 09 evidence.
5. После 09 одновременно SNAP-10 search и 11 comparison. SNAP-14 assistant
   после 10+11+13. Auth может выполняться всё это время.
6. SNAP-16 API composition после 03+09+14+15; затем 17 Next.js. SNAP-18 eval
   после 03+09+11+14 параллельно API/UI на отдельных paths. Source approval и
   human labeling готовятся раньше; real eval ждёт допущенного real corpus.
7. SNAP-19 финальная интеграция/restore/S0–S3 после 17+18.

Один владелец на file tree, отдельные branches/worktrees, один integrator merge.
Планируемые миграции 0004/0005 и Alembic env никогда не редактируются одновременно;
downstream schema fixes — отдельная follow-up schema owner. Не обновлять task
statuses/report индексы из разных worktrees одновременно. UI DTO владеет 16,
UI consumes. CI/compose/README изменяет 19 в финальной волне.

## Что запускать сейчас

Полностью без предпосылок — **SNAP-01**. Одновременно можно собирать human
source decisions/coverage по отчётам, не выдавая grants и не получая новые bytes
до допуска. Остальные coding prompts начинают после соответствующих merges;
04/05/06/07/12 доступны сразу после 01, 02 тоже. Уже работающий offline E2E
можно запускать сейчас независимо от документации/данных. Snapshot changes
не требуют сначала пройти historical G2 для разработки auth/API/UI.

## Общее Definition of Done

Scoped reviewable code, relevant lint/type/unit/real PG/contract checks, report
с evidence и честными NOT RUN; existing regression checks green; no new infra.
Preserve originals/permissions/reports. Groq integration default fake в CI,
реальные provider/data gates только по настоящим run artifacts.
