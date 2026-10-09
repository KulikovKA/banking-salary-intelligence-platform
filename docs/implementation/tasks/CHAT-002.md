# CHAT-002 — Структурированная память и разрешение ссылок

> Объединено в [WORK-11 — Личная история, память и надёжное выполнение вопросов](../work_packages/WORK-11.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **Extra High** (`xhigh`).

## Карточка

Phase: **B1**. Epic: **Чаты**. Status: **TODO**.
Priority: **Critical**. Estimated Complexity: **M** (без точных сроков).
Assigned Model: **GPT-6 Luna — Reasoning**. Gate prerequisites: **G2**.

## Назначение

Результат задачи: Память сохраняет выбор, а факты всегда перечитываются; concurrency не затирает context.

## Предпосылки и Dependencies

[CHAT-001](CHAT-001.md), [AI-001](AI-001.md)

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

- `backend/app/chats/context.py`

Допустимы относящиеся к этой задаче tests/fixtures и запись `docs/reports/CHAT-002.md`. Центральные контракты менять только через ADR с перечнем affected tasks. Новые зависимости обосновать и закрепить в lockfile.

## Точная техническая спецификация и контракты

Context schema/version/focus_bank из DATA_FLOW; optimistic context version.

Соблюдать DTO schema_version=1, UUID string, ISO даты, Decimal string, typed errors. Не подменять unknown нулём, missing scope федеральным, дату скачивания датой действия. I-01…I-12 из OVERVIEW обязательны в относящейся к задаче части.

## Алгоритм и подзадачи

1. **CHAT-002.01** — Merge explicit question > confirmed context > defaults.
2. **CHAT-002.02** — Обработать focus/comparator, reset as_of now и explicit historical dates.
3. **CHAT-002.03** — Передавать только bounded recent context и безопасные normalized fields, не старые тарифные числа.
4. **CHAT-002.04** — Version conflict сохраняет input и требует retry/clarify, uncertain referent не обновляет focus.

## Обработка ошибок и границы

Ambiguous pronoun →clarification; stale history never fact source; deletion removes context.

Ошибки фиксировать кодом и request/job ID без secrets/полного текста чата. Не скрывать неготовую внешнюю зависимость за успешной заглушкой. Изменения должны оставлять прежние доказательства доступными.

## Тесты и фикстуры

Сбер→Альфа затем «его с ВТБ»; два кандидата referent; historical→now; tariff changed after old answer.

Unit проверки детерминированы; SQL integration использует PostgreSQL, а не SQLite. Network/provider tests offline с Fake, live probes только по source policy. Для bug fix добавить regression по поведению. Зафиксировать fixture hashes и фактические команды в отчёте.

## Acceptance Criteria

- Память сохраняет выбор, а факты всегда перечитываются; concurrency не затирает context.
- Все перечисленные пограничные сценарии проверены; нет молчаливых failures или необъяснённых skipped blockers.
- Центральные контракты и артефакты зависимостей совместимы; требования этой задачи подтверждены ссылками на код/отчёт.

## Definition of Done

1. Изменения ограничены областью задачи; нет несогласованной новой архитектуры или provider choice.
2. Выполнены относящиеся lint/type/unit/integration/contract проверки; результаты, не только команды, записаны.
3. `docs/reports/CHAT-002.md` содержит: commit если доступен, изменённые файлы, поведение, checks/pass/fail/skip, AC evidence, ограничения и следующие риски.
4. MASTER_PLAN и TASK_INDEX обновлены синхронно: DONE только после AC; иначе IN_PROGRESS/BLOCKED с причиной и owner следующего действия.
5. Возможный Git commit создаётся только внутри project-local repository, без чужих файлов. При отсутствии корректной границы коммит не выполнять.

## Передача

[Готовый исполнительский prompt](../luna_prompts/CHAT-002.md). Исполнять в порядке [EXECUTION_ORDER](../EXECUTION_ORDER.md). Если нужна принципиальная смена scope/контракта — представить конкретный ADR пользователю, не придумывать одобрение.
