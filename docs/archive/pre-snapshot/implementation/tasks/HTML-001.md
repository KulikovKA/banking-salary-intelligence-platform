# HTML-001 — HTML extraction с сохранением значимого текста

> Объединено в [WORK-04 — HTML/PDF, структура документов и версии](../work_packages/WORK-04.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **High** (`high`).


## ADR-006 execution mode

**Mode:** `offline` under G0-OFFLINE for local/synthetic work, with no external ingestion egress; live/acceptance requires source-specific G0-LIVE and original gates.

A completed offline checkpoint is evidence for that checkpoint only; it does not complete the WORK block or accept G1/G2. Synthetic evidence cannot be published as real bank facts.

Offline mode follows TASK_INDEX.offline_deps; the card's full deps remain for live/acceptance and do not block the synthetic checkpoint. Do not claim its original live acceptance criteria passed.

## Карточка

Phase: **A1**. Epic: **Обработка**. Status: **TODO**.
Priority: **High**. Estimated Complexity: **M** (без точных сроков).
Gate prerequisites: **G0-OFFLINE for the checkpoint; real-corpus acceptance retains original gates**. Verify dependencies and evidence; a TODO record is not proof of completion.

## Назначение

Результат задачи: Оформление не меняет canonical meaning; значимая сноска и отрицание сохранены; HTML не имеет PDF page.

## Предпосылки и Dependencies

[NET-001](NET-001.md)

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

- `backend/app/processing/contracts.py`
- `backend/app/processing/html.py`

Допустимы относящиеся к этой задаче tests/fixtures и запись `docs/reports/HTML-001.md`. Центральные контракты менять только через ADR с перечнем affected tasks. Новые зависимости обосновать и закрепить в lockfile.

## Точная техническая спецификация и контракты

ParseResult{pages:[],sections,chunks,quality,canonical_hash}; original blob unchanged.

Соблюдать DTO schema_version=1, UUID string, ISO даты, Decimal string, typed errors. Не подменять unknown нулём, missing scope федеральным, дату скачивания датой действия. I-01…I-12 из OVERVIEW обязательны в относящейся к задаче части.

## Алгоритм и подзадачи

1. **HTML-001.01** — Извлечь title/headings/main/table rows/footnotes с BeautifulSoup/lxml.
2. **HTML-001.02** — Удалять только согласованные nav/cookie/ads selectors, сохранять отрицания/даты/числа.
3. **HTML-001.03** — Нормализовать whitespace и encoding с versioned config, сохранить raw vs canonical связь.
4. **HTML-001.04** — Dynamic rendered DOM пометить отдельным artifact; Playwright включать только на доказанном fixture кейсе.

## Обработка ошибок и границы

Main selector отсутствует/резко упал text coverage →partial/review; нельзя признать empty text отменой условий.

Ошибки фиксировать кодом и request/job ID без secrets/полного текста чата. Не скрывать неготовую внешнюю зависимость за успешной заглушкой. Изменения должны оставлять прежние доказательства доступными.

## Тесты и фикстуры

Fixtures: table+footnote, duplicate headings, cookie banner, changed negative word, malformed HTML, script injection.

Unit проверки детерминированы; SQL integration использует PostgreSQL, а не SQLite. Network/provider tests offline с Fake, live probes только по source policy. Для bug fix добавить regression по поведению. Зафиксировать fixture hashes и фактические команды в отчёте.

## Acceptance Criteria

- Оформление не меняет canonical meaning; значимая сноска и отрицание сохранены; HTML не имеет PDF page.
- Все перечисленные пограничные сценарии проверены; нет молчаливых failures или необъяснённых skipped blockers.
- Центральные контракты и артефакты зависимостей совместимы; требования этой задачи подтверждены ссылками на код/отчёт.

## Definition of Done

1. Изменения ограничены областью задачи; нет несогласованной новой архитектуры или provider choice.
2. Выполнены относящиеся lint/type/unit/integration/contract проверки; результаты, не только команды, записаны.
3. `docs/reports/HTML-001.md` содержит: commit если доступен, изменённые файлы, поведение, checks/pass/fail/skip, AC evidence, ограничения и следующие риски.
4. MASTER_PLAN и TASK_INDEX обновлены синхронно: DONE только после AC; иначе IN_PROGRESS/BLOCKED с причиной и owner следующего действия.
5. Возможный Git commit создаётся только внутри project-local repository, без чужих файлов. При отсутствии корректной границы коммит не выполнять.

## Передача

[Готовый исполнительский prompt](../luna_prompts/HTML-001.md). Исполнять в порядке [EXECUTION_ORDER](../EXECUTION_ORDER.md). Если нужна принципиальная смена scope/контракта — представить конкретный ADR пользователю, не придумывать одобрение.
