# WORK-02 — Окружение, репозиторий и базовая БД

Status: **IN_PROGRESS** ? INF-001 complete; INF-002/DB-001 admitted under G0-OFFLINE; PostgreSQL runtime integration awaits Docker daemon. ADR-006 is approved with changes; no source has G0-LIVE.

Почему этот уровень: Работа по готовой структуре и схеме; при изменении миграционного контракта повысить до High.
Full offline setup/schema acceptance is local; source policy is required only for subsequent live retrieval.




Dependencies: Offline checkpoint dependencies: none. WORK-01 is not a dependency of WORK-02.
Offline checkpoint gate: G0-OFFLINE. Full acceptance retains original AC and applicable live/G1/G2 requirements.

## Execution mode under ADR-006

**Mode:** offline checkpoint under G0-OFFLINE; all live work requires exact source G0-LIVE and original acceptance gates.

Offline work uses local data or explicitly synthetic fixtures only. External ingestion requests are forbidden, including redirects, subresources, parser workers, and browser renderers. Synthetic provenance is isolated from real manifests and publication. A checkpoint marked DONE does not make this WORK DONE or satisfy G1/G2. Preserve every original acceptance criterion.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-02.md).



## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## INF-001 — Изолированный репозиторий и воспроизводимые инструменты

Reasoning: **Medium**. [Полное ТЗ](../tasks/INF-001.md).

Контракт: Структура PROJECT_STRUCTURE; команды lint/typecheck/test/build в README.

1. Повторно проверить cwd и Git root; создать project-local Git boundary, не добавлять родительские файлы.
2. Зафиксировать совместимые версии Python/FastAPI/Pydantic/SQLAlchemy и Node/Next/React/TypeScript в lockfiles.
3. Создать минимальные app entrypoints и тестовый runner без бизнес-логики.
4. Настроить lint/typecheck и локальный CI workflow, записать license inventory и команды.

Ошибки: Нет runtime/Docker → отчёт о prerequisite; не устанавливать глобально случайные версии и не коммитить secrets.

Проверки: Чистое разрешение lockfiles, import backend, frontend production build; git root внутри workspace; secret canary отсутствует в tracked files.

Критерий: Clean setup воспроизводится из README; нет изменений вне проекта; зависимости pinned.

## INF-002 — Validated config и локальное окружение POC

Reasoning: **Medium**. [Полное ТЗ](../tasks/INF-002.md).

Контракт: Settings из OPERATIONS; APP_ENV=poc|test|production; DATABASE_URL secret.

1. Описать Settings с типами, пределами и обязательными production fields.
2. Добавить локальный PostgreSQL и backend Compose profile с 127.0.0.1 binding.
3. Разделить secret и public config, не раскрывать values в exception.
4. Fail startup при fake identity в production, неверном STORAGE_ROOT или незаданном provider model в provider mode.

Ошибки: Невалидный env → startup error code без секретного значения; production не получает unsafe defaults.

Проверки: Табличные config tests для отсутствующих secrets, negative limits, production auth bypass и fake/provider; health локального DB.

Критерий: Ошибки конфигурации обнаруживаются до обработки запросов; example env не содержит секретов.

## DB-001 — Миграции каталога, blobs и job queue

Reasoning: **Medium**. [Полное ТЗ](../tasks/DB-001.md).

Контракт: banks/sources/source_policies/blobs/source_versions/source_fetches/job_runs по DATABASE_DESIGN.

1. Создать Alembic environment с одной head.
2. Создать PK/FK/check/unique и due/lease indexes; source_fetches связывать с job/source version.
3. Добавить bank code seed без вымышленных тарифов, sources только из approved manifest.
4. Создать transaction/session helpers с explicit application commit.

Ошибки: Повтор seed не дублирует bank/source; canonical URL collision не переassign bank; failed migration rollback.

Проверки: Upgrade empty PostgreSQL и повтор command; duplicate hash/source/job key violations; invalid FK rejection; rollback failed transaction.

Критерий: Schema соответствует контракту, seed четырёх bank codes идемпотентен, migration SQL reviewed.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-02.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
