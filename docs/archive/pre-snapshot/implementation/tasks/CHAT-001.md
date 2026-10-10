# CHAT-001 — Хранение собственной истории и удаление

> Объединено в [WORK-11 — Личная история, память и надёжное выполнение вопросов](../work_packages/WORK-11.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **Extra High** (`xhigh`).

## Карточка

Phase: **B1**. Epic: **Чаты**. Status: **TODO**.
Priority: **Critical**. Estimated Complexity: **M** (без точных сроков).
Assigned Model: **GPT-6 Luna — Reasoning**. Gate prerequisites: **G2**.

## Назначение

Результат задачи: История личная; удалённые сообщения не читаются и не возвращаются поздним worker.

## Предпосылки и Dependencies

[AUTH-003](AUTH-003.md), [DB-004](DB-004.md)

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

- `backend/app/chats/service.py`
- `backend/app/chats/routes.py`
- `backend/app/chats/schemas.py`

Допустимы относящиеся к этой задаче tests/fixtures и запись `docs/reports/CHAT-001.md`. Центральные контракты менять только через ADR с перечнем affected tasks. Новые зависимости обосновать и закрепить в lockfile.

## Точная техническая спецификация и контракты

Owned chat CRUD/message list/delete, cursor pagination и immutable answer refs.

Соблюдать DTO schema_version=1, UUID string, ISO даты, Decimal string, typed errors. Не подменять unknown нулём, missing scope федеральным, дату скачивания датой действия. I-01…I-12 из OVERVIEW обязательны в относящейся к задаче части.

## Алгоритм и подзадачи

1. **CHAT-001.01** — Создать session/list/messages с SQL owner predicates и stable cursor.
2. **CHAT-001.02** — Сохранять user/assistant messages с sequence, AnswerEnvelope и evidence refs.
3. **CHAT-001.03** — Удалять собственный chat атомарно, отменять pending runs; usage detach.
4. **CHAT-001.04** — Записывать deletion tombstone для restore, не сохранять текст в audit.

## Обработка ошибок и границы

Чужой chat404; double delete idempotent policy; deleting session не принимает message.

Ошибки фиксировать кодом и request/job ID без secrets/полного текста чата. Не скрывать неготовую внешнюю зависимость за успешной заглушкой. Изменения должны оставлять прежние доказательства доступными.

## Тесты и фикстуры

A/B ownership всех методов, pagination ties, delete during run, evidence survives chat deletion.

Unit проверки детерминированы; SQL integration использует PostgreSQL, а не SQLite. Network/provider tests offline с Fake, live probes только по source policy. Для bug fix добавить regression по поведению. Зафиксировать fixture hashes и фактические команды в отчёте.

## Acceptance Criteria

- История личная; удалённые сообщения не читаются и не возвращаются поздним worker.
- Все перечисленные пограничные сценарии проверены; нет молчаливых failures или необъяснённых skipped blockers.
- Центральные контракты и артефакты зависимостей совместимы; требования этой задачи подтверждены ссылками на код/отчёт.

## Definition of Done

1. Изменения ограничены областью задачи; нет несогласованной новой архитектуры или provider choice.
2. Выполнены относящиеся lint/type/unit/integration/contract проверки; результаты, не только команды, записаны.
3. `docs/reports/CHAT-001.md` содержит: commit если доступен, изменённые файлы, поведение, checks/pass/fail/skip, AC evidence, ограничения и следующие риски.
4. MASTER_PLAN и TASK_INDEX обновлены синхронно: DONE только после AC; иначе IN_PROGRESS/BLOCKED с причиной и owner следующего действия.
5. Возможный Git commit создаётся только внутри project-local repository, без чужих файлов. При отсутствии корректной границы коммит не выполнять.

## Передача

[Готовый исполнительский prompt](../luna_prompts/CHAT-001.md). Исполнять в порядке [EXECUTION_ORDER](../EXECUTION_ORDER.md). Если нужна принципиальная смена scope/контракта — представить конкретный ADR пользователю, не придумывать одобрение.
