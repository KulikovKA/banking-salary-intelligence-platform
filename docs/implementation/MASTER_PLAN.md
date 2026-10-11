# MASTER PLAN — snapshot v1

Цель: работающий closed AI-ассистент по четырём банкам на фиксированном официальном
корпусе. [Архитектура](../architecture/OVERVIEW.md),
[приёмка S0–S3](../product/ACCEPTANCE_CRITERIA.md), [Codex](../../AGENTS.md).
Машиночитаемый реестр: [TASKS.json](TASKS.json); executable prompts — таблица ниже.
WORK/TASK/luna пакетов в main нет: они сохранены в ветке archive.

## Распределение ответственности

Наша команда: FastAPI и backend services; PostgreSQL и additive migrations;
парсинг, извлечение, нормализация и ручная проверка тарифов; поиск и Comparison
Engine; Groq `openai/gpt-oss-120b` и evidence-first AI-ассистент; авторизация,
безопасность, API, backend и интеграционные тесты.

Внешний frontend-разработчик: дизайн, страницы и компоненты, личный кабинет,
страницы сравнения банков, UI чата и визуализация ответов, адаптивность и
пользовательские сценарии. Он может создавать frontend параллельно backend.
Наша команда позже принимает, при необходимости адаптирует и подключает этот
код к FastAPI в существующей Next.js архитектуре; второй frontend с нуля не создаёт.

Передача исходников пока не подтверждена. [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md)
содержит FE-01–FE-04 как отслеживаемые подзадачи SNAP-17, их владельцев,
входные зависимости, блокеры и AC. Это не новые SNAP-ID: остаются ровно 19 задач.

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
| [SNAP-02](prompts/SNAP-02.md) | Добавить schema snapshot и тарифного pipeline | SNAP-01 | high | DONE |
| [SNAP-03](prompts/SNAP-03.md) | Операторский corpus manifest и freeze service | SNAP-02 | high | DONE |
| [SNAP-04](prompts/SNAP-04.md) | PDF parser с page/table evidence | SNAP-01 | high | DONE |
| [SNAP-05](prompts/SNAP-05.md) | XLSX parser без вычисления формул | SNAP-01 | high | DONE |
| [SNAP-06](prompts/SNAP-06.md) | HTML parser сохранённого original | SNAP-01 | medium | DONE |
| [SNAP-07](prompts/SNAP-07.md) | Нормализация тарифов и registry метрик | SNAP-01 | high | DONE |
| [SNAP-08](prompts/SNAP-08.md) | Последовательный parsing/extraction pipeline | SNAP-03, SNAP-04, SNAP-05, SNAP-06, SNAP-07 | high | DONE |
| [SNAP-09](prompts/SNAP-09.md) | Evidence validation, manual review и publication | SNAP-08 | high | DONE |
| [SNAP-10](prompts/SNAP-10.md) | PostgreSQL FTS по frozen corpus | SNAP-09 | medium | TODO |
| [SNAP-11](prompts/SNAP-11.md) | Детерминированный Comparison Engine | SNAP-09 | high | DONE |
| [SNAP-12](prompts/SNAP-12.md) | LLM Protocol, Fake и bounded renderer inputs | SNAP-01 | medium | DONE |
| [SNAP-13](prompts/SNAP-13.md) | GroqCloud Free adapter и quotas | SNAP-02, SNAP-12 | high | DONE |
| [SNAP-14](prompts/SNAP-14.md) | Evidence-first ассистент и renderer | SNAP-10, SNAP-11, SNAP-13 | high | TODO |
| [SNAP-15](prompts/SNAP-15.md) | Приглашения, auth и server sessions | SNAP-02 | high | DONE |
| [SNAP-16](prompts/SNAP-16.md) | FastAPI routers и composition root | SNAP-03, SNAP-09, SNAP-14, SNAP-15 | high | TODO |
| [SNAP-17](prompts/SNAP-17.md) | Интеграция и адаптация внешнего frontend | SNAP-16 | medium | TODO |
| [SNAP-18](prompts/SNAP-18.md) | Реальный corpus gold и оценка S1/S2/Groq | SNAP-03, SNAP-09, SNAP-11, SNAP-14 | high | TODO |
| [SNAP-19](prompts/SNAP-19.md) | Сквозная приёмка и минимальная эксплуатация | SNAP-17, SNAP-18 | high | TODO |

Только TASKS.json и эта таблица отражают активные статусы. Интегратор обновляет
их одним commit после принятого отчёта; валидатор проверяет совпадение и DAG.
DONE модуля не означает S1/S2/S3 PASS. При data blocker module harness можно
закончить, а real acceptance остаётся NOT EVALUATED/BLOCKED в report.
Всего 13 DONE; SNAP-17 остаётся TODO до отдельного поручения и выполнения
входных условий. Отсутствие внешних исходников блокирует FE-подзадачи, но не
независимую разработку Backend + AI.

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
6. SNAP-16 API composition после 03+09+14+15: стабильный OpenAPI/TS client contract,
   auth/CSRF, ошибки и synthetic примеры для внешнего frontend без навязывания
   визуальной реализации. Затем SNAP-17: FE-01 приёмка -> FE-02 перенос/адаптация
   -> FE-03 подключение -> FE-04 интеграционные проверки. Вход FE-01–FE-04 требует
   переданных исходников и merged SNAP-16; scaffolding второго UI не допускается.
   SNAP-18 eval после 03+09+11+14 параллельно API/интеграции на отдельных paths.
   Source approval и human labeling готовятся раньше; real eval ждёт допущенного
   real corpus.
7. SNAP-19 финальная интеграция/restore/S0–S3 после 17+18, включая принятые
   FE-01–FE-04 и browser E2E внешнего frontend. Разработка UI с нуля не входит в 19.

Один владелец на file tree, отдельные branches/worktrees, один integrator merge.
Планируемые миграции 0004/0005 и Alembic env никогда не редактируются одновременно;
downstream schema fixes — отдельная follow-up schema owner. Не обновлять task
statuses/report индексы из разных worktrees одновременно. UI DTO владеет 16,
внешний UI и SNAP-17 их используют без конкурирующего schema/DTO fork. Любое
изменение публичного API требует обоснованного follow-up и согласованного merge
владельца. На переносе frontend tree и package-lock имеет одного владельца
SNAP-17; внешние изменения принимаются последовательной передачей exact revision.
CI/compose/README изменяет 19 в финальной волне.

## Что запускать сейчас

SNAP-08 принят после merge исправлений PR #15; [решение приёмки](../reports/SNAP-08-accepted.md).
SNAP-09 merged через PR #17; [решение приёмки](../reports/SNAP-09-accepted.md).
SNAP-11 merged через PR #20 в main и закрыт по поручению пользователя;
[запись закрытия](../reports/SNAP-11-accepted.md). Ограничения frozen contract сохраняются.
Следующая доступная кодовая задача — **SNAP-10**; SNAP-14 ждёт его приёмки.
Draft original доступен до extraction через проверяемый операторский manifest;
final freeze выполняется после reviewed publication. SNAP-09 следует за 08,
SNAP-10 и 11 — за 09, SNAP-14 — за 10+11+13, SNAP-16 — после 14 и остальных
зависимостей. Приоритет: **10 -> 14 -> 16**. После переданных
исходников и готового API: **17 / FE-01 -> FE-02 -> FE-03 -> FE-04**; финальная
приёмка **19** ждёт **17 и 18**. Новые задачи требуют отдельного поручения.
Human source review можно готовить независимо; real bytes остаются blocked до
source-specific acquisition/storage/reuse допуска. G1/G2 и S1/S2/S3 не изменяются
от технических synthetic проверок.

## Общее Definition of Done

Scoped reviewable code, relevant lint/type/unit/real PG/contract checks, report
с evidence и честными NOT RUN; existing regression checks green; no new infra.
Preserve originals/permissions/reports. Groq integration default fake в CI,
реальные provider/data gates только по настоящим run artifacts.
