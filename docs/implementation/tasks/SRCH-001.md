# SRCH-001 — PostgreSQL FTS с фильтрами и оценкой поиска

> Объединено в [WORK-07 — Полнотекстовый поиск и детерминированные сравнения](../work_packages/WORK-07.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **Extra High** (`xhigh`).

## Карточка

Phase: **A2**. Epic: **Поиск**. Status: **TODO**.
Priority: **High**. Estimated Complexity: **M** (без точных сроков).
Assigned Model: **GPT-6 Luna — Reasoning**. Gate prerequisites: **G0**.

## Назначение

Результат задачи: Результаты открывают правильную версию; SQL injection невозможен через query string; metrics report сохранён.

## Предпосылки и Dependencies

[TXT-001](TXT-001.md), [FACT-004](FACT-004.md)

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

- `backend/app/search/service.py`
- `backend/app/search/synonyms.py`
- `backend/alembic/versions/`

Допустимы относящиеся к этой задаче tests/fixtures и запись `docs/reports/SRCH-001.md`. Центральные контракты менять только через ADR с перечнем affected tasks. Новые зависимости обосновать и закрепить в lockfile.

## Точная техническая спецификация и контракты

SearchQuery{q,banks,as_of,scope,limit}; SearchResult{chunks,coverage}; snippets не authoritative facts.

Соблюдать DTO schema_version=1, UUID string, ISO даты, Decimal string, typed errors. Не подменять unknown нулём, missing scope федеральным, дату скачивания датой действия. I-01…I-12 из OVERVIEW обязательны в относящейся к задаче части.

## Алгоритм и подзадачи

1. **SRCH-001.01** — Построить russian tsvector с title/section weights и GIN.
2. **SRCH-001.02** — Использовать parameterized websearch_to_tsquery, bounded query/limit; bank/date/visibility filters до выдачи.
3. **SRCH-001.03** — Добавить explicit aliases и salary synonyms, вернуть chunk/evidence IDs и physical_page.
4. **SRCH-001.04** — Измерить Recall@10 на gold queries и EXPLAIN; не добавлять pgvector без trigger.

## Обработка ошибок и границы

Stopwords/empty query →clarify; unsupported bank reject; stale chunks явно отмечены; ts_headline output escape.

Ошибки фиксировать кодом и request/job ID без secrets/полного текста чата. Не скрывать неготовую внешнюю зависимость за успешной заглушкой. Изменения должны оставлять прежние доказательства доступными.

## Тесты и фикстуры

Russian inflections, bank aliases, numeric criterion, longPDF, no result, HTML injection, per-bank Recall@10.

Unit проверки детерминированы; SQL integration использует PostgreSQL, а не SQLite. Network/provider tests offline с Fake, live probes только по source policy. Для bug fix добавить regression по поведению. Зафиксировать fixture hashes и фактические команды в отчёте.

## Acceptance Criteria

- Результаты открывают правильную версию; SQL injection невозможен через query string; metrics report сохранён.
- Все перечисленные пограничные сценарии проверены; нет молчаливых failures или необъяснённых skipped blockers.
- Центральные контракты и артефакты зависимостей совместимы; требования этой задачи подтверждены ссылками на код/отчёт.

## Definition of Done

1. Изменения ограничены областью задачи; нет несогласованной новой архитектуры или provider choice.
2. Выполнены относящиеся lint/type/unit/integration/contract проверки; результаты, не только команды, записаны.
3. `docs/reports/SRCH-001.md` содержит: commit если доступен, изменённые файлы, поведение, checks/pass/fail/skip, AC evidence, ограничения и следующие риски.
4. MASTER_PLAN и TASK_INDEX обновлены синхронно: DONE только после AC; иначе IN_PROGRESS/BLOCKED с причиной и owner следующего действия.
5. Возможный Git commit создаётся только внутри project-local repository, без чужих файлов. При отсутствии корректной границы коммит не выполнять.

## Передача

[Готовый исполнительский prompt](../luna_prompts/SRCH-001.md). Исполнять в порядке [EXECUTION_ORDER](../EXECUTION_ORDER.md). Если нужна принципиальная смена scope/контракта — представить конкретный ADR пользователю, не придумывать одобрение.
