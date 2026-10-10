# WORK-11 — Личная история, память и надёжное выполнение вопросов

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **Extra High**. Status: **TODO**.

Почему этот уровень: Гонки удаления/ответа, snapshot consistency, budgets и повторные запросы.

Dependencies: [WORK-03](WORK-03.md), [WORK-08](WORK-08.md), [WORK-10](WORK-10.md)

Gates входящих этапов: G2. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-11.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## LLM-002 — Gateway, budgets, redaction и отказоустойчивость

Reasoning: **Extra High**. [Полное ТЗ](../tasks/LLM-002.md).

Контракт: LLMRequest/Response, calls<=2/question, tokens/deadline/concurrency DOMAIN_CONTRACTS.

1. Собирать allowed normalized payload и не пересылать raw user history.
2. Атомарно reserve/reconcile tokens, per-user/global quota и concurrency5.
3. Применить total45s deadline, transient retry внутри caps, circuit breaker и safe cache key.
4. Usage absent →estimated, prices absent→unknown cost; invalid structured output typed error.

Ошибки: Budget exceeded fallback; unsafe free text clarification; provider secret/config error no repeated retries.

Проверки: Concurrent reservation, timeout/circuit, cancel, unknown usage, raw email/account canaries, cache corpus invalidation.

Критерий: Hard caps не превышены гонкой; запрещённые поля не выходят; mock tests покрывают provider outages.

## CHAT-001 — Хранение собственной истории и удаление

Reasoning: **Extra High**. [Полное ТЗ](../tasks/CHAT-001.md).

Контракт: Owned chat CRUD/message list/delete, cursor pagination и immutable answer refs.

1. Создать session/list/messages с SQL owner predicates и stable cursor.
2. Сохранять user/assistant messages с sequence, AnswerEnvelope и evidence refs.
3. Удалять собственный chat атомарно, отменять pending runs; usage detach.
4. Записывать deletion tombstone для restore, не сохранять текст в audit.

Ошибки: Чужой chat404; double delete idempotent policy; deleting session не принимает message.

Проверки: A/B ownership всех методов, pagination ties, delete during run, evidence survives chat deletion.

Критерий: История личная; удалённые сообщения не читаются и не возвращаются поздним worker.

## CHAT-002 — Структурированная память и разрешение ссылок

Reasoning: **Extra High**. [Полное ТЗ](../tasks/CHAT-002.md).

Контракт: Context schema/version/focus_bank из DATA_FLOW; optimistic context version.

1. Merge explicit question > confirmed context > defaults.
2. Обработать focus/comparator, reset as_of now и explicit historical dates.
3. Передавать только bounded recent context и безопасные normalized fields, не старые тарифные числа.
4. Version conflict сохраняет input и требует retry/clarify, uncertain referent не обновляет focus.

Ошибки: Ambiguous pronoun →clarification; stale history never fact source; deletion removes context.

Проверки: Сбер→Альфа затем «его с ВТБ»; два кандидата referent; historical→now; tariff changed after old answer.

Критерий: Память сохраняет выбор, а факты всегда перечитываются; concurrency не затирает context.

## AI-003 — Асинхронный ответ и сохранение согласованного snapshot

Reasoning: **Extra High**. [Полное ТЗ](../tasks/AI-003.md).

Контракт: POST questions202 / GET answer-runs, idempotency key, AnswerEnvelope.

1. В одной транзакции создать user message/run/job, same-key replay возвращает run.
2. Снять REPEATABLE READ facts/evidence/corpus revision и закрыть transaction до LLM.
3. Выполнить safe intent→tools→comparison→renderer через gateway.
4. Транзакционно сохранить assistant/context если session active и expected version совпадает; bounded queue/backpressure.

Ошибки: Worker retry не дублирует message/provider reservation; deleted session rejects result; provider timeout template fallback.

Проверки: Double click/reconnect, corpus changes during LLM, delete during call, parallel question409, DB failure before save, queue full429.

Критерий: Один вопрос имеет один результат; snapshot воспроизводим, нет long DB transaction during network.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-11.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
