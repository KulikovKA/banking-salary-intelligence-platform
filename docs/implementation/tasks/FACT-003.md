# FACT-003 — Валидация и решения аналитика

> Объединено в [WORK-06 — Тарифные факты, проверка и публикация](../work_packages/WORK-06.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **Extra High** (`xhigh`).

## Карточка

Phase: **A2**. Epic: **Факты**. Status: **TODO**.
Priority: **Critical**. Estimated Complexity: **M** (без точных сроков).
Assigned Model: **GPT-6 Luna — Reasoning**. Gate prerequisites: **G0**.

## Назначение

Результат задачи: Нельзя одобрить некорректное evidence; решения append-only; disputed candidate не появляется в published queries.

## Предпосылки и Dependencies

[FACT-002](FACT-002.md)

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

- `backend/app/facts/validate.py`
- `backend/app/facts/review.py`

Допустимы относящиеся к этой задаче tests/fixtures и запись `docs/reports/FACT-003.md`. Центральные контракты менять только через ADR с перечнем affected tasks. Новые зависимости обосновать и закрепить в lockfile.

## Точная техническая спецификация и контракты

ValidationResult{eligible,flags,missing_evidence}; ReviewRequest из API_CONTRACTS.

Соблюдать DTO schema_version=1, UUID string, ISO даты, Decimal string, typed errors. Не подменять unknown нулём, missing scope федеральным, дату скачивания датой действия. I-01…I-12 из OVERVIEW обязательны в относящейся к задаче части.

## Алгоритм и подзадачи

1. **FACT-003.01** — Проверить quote equality/offset/page, value-unit-basis-condition coverage и effective dates.
2. **FACT-003.02** — Реализовать approved/rejected/needs_changes с reason/expected_hash.
3. **FACT-003.03** — Corrections создают новый candidate с parent; первоначальный immutable.
4. **FACT-003.04** — POC review через локальный CLI service, MVP route добавляется API-002; actor_type human/rule и version аудируются.

## Обработка ошибок и границы

Stale expected_hash →409; no evidence →approve denied; confidence не разрешает missing applicability.

Ошибки фиксировать кодом и request/job ID без secrets/полного текста чата. Не скрывать неготовую внешнюю зависимость за успешной заглушкой. Изменения должны оставлять прежние доказательства доступными.

## Тесты и фикстуры

Malformed quote, nonexistent page, date fetched substituted, concurrent reviews, correction preserves original.

Unit проверки детерминированы; SQL integration использует PostgreSQL, а не SQLite. Network/provider tests offline с Fake, live probes только по source policy. Для bug fix добавить regression по поведению. Зафиксировать fixture hashes и фактические команды в отчёте.

## Acceptance Criteria

- Нельзя одобрить некорректное evidence; решения append-only; disputed candidate не появляется в published queries.
- Все перечисленные пограничные сценарии проверены; нет молчаливых failures или необъяснённых skipped blockers.
- Центральные контракты и артефакты зависимостей совместимы; требования этой задачи подтверждены ссылками на код/отчёт.

## Definition of Done

1. Изменения ограничены областью задачи; нет несогласованной новой архитектуры или provider choice.
2. Выполнены относящиеся lint/type/unit/integration/contract проверки; результаты, не только команды, записаны.
3. `docs/reports/FACT-003.md` содержит: commit если доступен, изменённые файлы, поведение, checks/pass/fail/skip, AC evidence, ограничения и следующие риски.
4. MASTER_PLAN и TASK_INDEX обновлены синхронно: DONE только после AC; иначе IN_PROGRESS/BLOCKED с причиной и owner следующего действия.
5. Возможный Git commit создаётся только внутри project-local repository, без чужих файлов. При отсутствии корректной границы коммит не выполнять.

## Передача

[Готовый исполнительский prompt](../luna_prompts/FACT-003.md). Исполнять в порядке [EXECUTION_ORDER](../EXECUTION_ORDER.md). Если нужна принципиальная смена scope/контракта — представить конкретный ADR пользователю, не придумывать одобрение.
