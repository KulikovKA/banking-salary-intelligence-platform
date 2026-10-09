# LOAD-001 — Нагрузка 30 пользователей и пределы ресурсов

> Объединено в [WORK-19 — Сквозная приёмка и нагрузка 30 пользователей](../work_packages/WORK-19.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **High** (`high`).

## Карточка

Phase: **B4**. Epic: **Приёмка MVP**. Status: **TODO**.
Priority: **High**. Estimated Complexity: **L** (без точных сроков).
Assigned Model: **GPT-6 Luna — Reasoning**. Gate prerequisites: **G2**.

## Назначение

Результат задачи: Цели достигнуты на указанном host либо честно отмечены ограничения для решения пользователя.

## Предпосылки и Dependencies

[QA-003](QA-003.md)

Перед стартом проверить фактические результаты зависимостей и их отчёты; запись TODO не является подтверждением готовности. Сейчас разрешено только проектирование. Для задач B* обязательна пользовательская приёмка G2.

## Входные данные

- [OVERVIEW.md](../../architecture/OVERVIEW.md)
- [DOMAIN_CONTRACTS.md](../../architecture/DOMAIN_CONTRACTS.md)
- [DATABASE_DESIGN.md](../../architecture/DATABASE_DESIGN.md)
- [API_CONTRACTS.md](../../architecture/API_CONTRACTS.md)
- [DATA_FLOW.md](../../architecture/DATA_FLOW.md)
- [SECURITY.md](../../architecture/SECURITY.md)
- [TEST_STRATEGY.md](../../quality/TEST_STRATEGY.md)

Дополнительно: [проверка внешних источников](../../research/SOURCES.md), артефакты перечисленных зависимостей и актуальный [MASTER_PLAN](../MASTER_PLAN.md). Реальные документы берутся из approved manifest с SHA-256; synthetic fixtures явно маркируются и не публикуются как банковские сведения.

## Файлы и модули

- `tests/load/`
- `docs/reports/load-report.md`

Допустимы относящиеся к этой задаче tests/fixtures и запись `docs/reports/LOAD-001.md`. Центральные контракты менять только через ADR с перечнем affected tasks. Новые зависимости обосновать и закрепить в lockfile.

## Точная техническая спецификация и контракты

30 concurrent sessions, max5 provider calls, target latency OPERATIONS/REQUIREMENTS.

Соблюдать DTO schema_version=1, UUID string, ISO даты, Decimal string, typed errors. Не подменять unknown нулём, missing scope федеральным, дату скачивания датой действия. I-01…I-12 из OVERVIEW обязательны в относящейся к задаче части.

## Алгоритм и подзадачи

1. **LOAD-001.01** — Подготовить100k chunks corpus с корректными IDs, смешать search/compare/chat/read/ingest.
2. **LOAD-001.02** — Прогреть затем измерить30min steady +burst30 submissions и slow provider.
3. **LOAD-001.03** — Записать p50/p95/error/queue/db connections/CPU/RAM/disk и query plans.
4. **LOAD-001.04** — Устранить конкретные bottlenecks без нового сервиса, повторить затронутый сценарий.

## Обработка ошибок и границы

Queue full возвращает429/Retry-After; no silent dropped answer; Fake latency test не доказывает real provider SLA.

Ошибки фиксировать кодом и request/job ID без secrets/полного текста чата. Не скрывать неготовую внешнюю зависимость за успешной заглушкой. Изменения должны оставлять прежние доказательства доступными.

## Тесты и фикстуры

p95 API<500ms/search-comparison<1s, deadline45s либо explicit fallback; caps hold; soak memory stable.

Unit проверки детерминированы; SQL integration использует PostgreSQL, а не SQLite. Network/provider tests offline с Fake, live probes только по source policy. Для bug fix добавить regression по поведению. Зафиксировать fixture hashes и фактические команды в отчёте.

## Acceptance Criteria

- Цели достигнуты на указанном host либо честно отмечены ограничения для решения пользователя.
- Все перечисленные пограничные сценарии проверены; нет молчаливых failures или необъяснённых skipped blockers.
- Центральные контракты и артефакты зависимостей совместимы; требования этой задачи подтверждены ссылками на код/отчёт.

## Definition of Done

1. Изменения ограничены областью задачи; нет несогласованной новой архитектуры или provider choice.
2. Выполнены относящиеся lint/type/unit/integration/contract проверки; результаты, не только команды, записаны.
3. `docs/reports/LOAD-001.md` содержит: commit если доступен, изменённые файлы, поведение, checks/pass/fail/skip, AC evidence, ограничения и следующие риски.
4. MASTER_PLAN и TASK_INDEX обновлены синхронно: DONE только после AC; иначе IN_PROGRESS/BLOCKED с причиной и owner следующего действия.
5. Возможный Git commit создаётся только внутри project-local repository, без чужих файлов. При отсутствии корректной границы коммит не выполнять.

## Передача

[Готовый исполнительский prompt](../luna_prompts/LOAD-001.md). Исполнять в порядке [EXECUTION_ORDER](../EXECUTION_ORDER.md). Если нужна принципиальная смена scope/контракта — представить конкретный ADR пользователю, не придумывать одобрение.
