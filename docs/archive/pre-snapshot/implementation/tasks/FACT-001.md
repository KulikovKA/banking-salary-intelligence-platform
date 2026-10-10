# FACT-001 — Нормализованные DTO тарифов и applicability

> Объединено в [WORK-06 — Тарифные факты, проверка и публикация](../work_packages/WORK-06.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **Extra High** (`xhigh`).


## ADR-006 execution mode

**Mode:** `offline` under G0-OFFLINE for local/synthetic work, with no external ingestion egress; live/acceptance requires source-specific G0-LIVE and original gates.

A completed offline checkpoint is evidence for that checkpoint only; it does not complete the WORK block or accept G1/G2. Synthetic evidence cannot be published as real bank facts.

Offline mode follows TASK_INDEX.offline_deps; the card's full deps remain for live/acceptance and do not block the synthetic checkpoint. Do not claim its original live acceptance criteria passed.

## Карточка

Phase: **A2**. Epic: **Факты**. Status: **TODO**.
Priority: **Critical**. Estimated Complexity: **M** (без точных сроков).
Gate prerequisites: **G0-OFFLINE for the checkpoint; real-corpus acceptance retains original gates**. Verify dependencies and evidence; a TODO record is not proof of completion.

## Назначение

Результат задачи: Нормализация воспроизводима и не добавляет недостающих дат/чисел.

## Предпосылки и Dependencies

[DB-003](DB-003.md)

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

- `backend/app/facts/schemas.py`
- `backend/app/facts/normalize.py`
- `backend/app/comparison/metrics.py`

Допустимы относящиеся к этой задаче tests/fixtures и запись `docs/reports/FACT-001.md`. Центральные контракты менять только через ADR с перечнем affected tasks. Новые зависимости обосновать и закрепить в lockfile.

## Точная техническая спецификация и контракты

FactCandidate, value discriminated union, ScopeDimension, predicate AST из DOMAIN_CONTRACTS.

Соблюдать DTO schema_version=1, UUID string, ISO даты, Decimal string, typed errors. Не подменять unknown нулём, missing scope федеральным, дату скачивания датой действия. I-01…I-12 из OVERVIEW обязательны в относящейся к задаче части.

## Алгоритм и подзадачи

1. **FACT-001.01** — Реализовать strict Pydantic DTO и Decimal string serialization.
2. **FACT-001.02** — Нормализовать comma decimals/NBSP/руб/%/period без потери оригинального текста.
3. **FACT-001.03** — Реализовать kind money/percent/range/individual/formula и metrics registry.
4. **FACT-001.04** — Валидировать geography/segment/package/date enums и AST bounds; unknown не конвертировать в any.

## Обработка ошибок и границы

Несогласованные единицы, NaN/Infinity, отрицательная комиссия, malformed AST →typed validation; free text остаётся manual.

Ошибки фиксировать кодом и request/job ID без secrets/полного текста чата. Не скрывать неготовую внешнюю зависимость за успешной заглушкой. Изменения должны оставлять прежние доказательства доступными.

## Тесты и фикстуры

0 vs null vs individual, 0,3%=0.30, from/up-to, RUB period, unknown scope; roundtrip DTO JSON.

Unit проверки детерминированы; SQL integration использует PostgreSQL, а не SQLite. Network/provider tests offline с Fake, live probes только по source policy. Для bug fix добавить regression по поведению. Зафиксировать fixture hashes и фактические команды в отчёте.

## Acceptance Criteria

- Нормализация воспроизводима и не добавляет недостающих дат/чисел.
- Все перечисленные пограничные сценарии проверены; нет молчаливых failures или необъяснённых skipped blockers.
- Центральные контракты и артефакты зависимостей совместимы; требования этой задачи подтверждены ссылками на код/отчёт.

## Definition of Done

1. Изменения ограничены областью задачи; нет несогласованной новой архитектуры или provider choice.
2. Выполнены относящиеся lint/type/unit/integration/contract проверки; результаты, не только команды, записаны.
3. `docs/reports/FACT-001.md` содержит: commit если доступен, изменённые файлы, поведение, checks/pass/fail/skip, AC evidence, ограничения и следующие риски.
4. MASTER_PLAN и TASK_INDEX обновлены синхронно: DONE только после AC; иначе IN_PROGRESS/BLOCKED с причиной и owner следующего действия.
5. Возможный Git commit создаётся только внутри project-local repository, без чужих файлов. При отсутствии корректной границы коммит не выполнять.

## Передача

[Готовый исполнительский prompt](../luna_prompts/FACT-001.md). Исполнять в порядке [EXECUTION_ORDER](../EXECUTION_ORDER.md). Если нужна принципиальная смена scope/контракта — представить конкретный ADR пользователю, не придумывать одобрение.
