# WORK-17 — Подключение выбранного LLM API

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **High**. Status: **TODO**.

Почему этот уровень: Сетевые ошибки, structured output, usage и реальная evaluation; выбор провайдера остаётся за пользователем.

Dependencies: [WORK-09](WORK-09.md), [WORK-11](WORK-11.md), [WORK-16](WORK-16.md)

Gates входящих этапов: G2 + решение пользователя о provider. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-17.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## LLM-003 — Адаптер выбранного пользователем API и real evaluation

Reasoning: **High**. [Полное ТЗ](../tasks/LLM-003.md).

Контракт: Окончательный выбор поставщика/модели пользователем + LLMProvider Protocol; не закреплён заранее.

1. Получить recorded provider/model/data-policy decision и API credentials через secrets.
2. Реализовать provider transport и strict structured-output parsing, usage metadata, typed errors.
3. Прогнать общую adapter suite и bounded smoke с разрешённым payload.
4. Повторить frozen real evaluation/latency/tokens/cost, записать model/config/prompt versions.

Ошибки: Не выбран API →BLOCKED именно этой задачи; Fake не считать production model; auth errors без retry storm.

Проверки: Transport mock429/5xx/timeout/malformed/truncation; real holdout3 runs для flaky cases; no unsupported claims.

Критерий: Утверждённый provider проходит contracts и evaluation; иначе feature остаётся выключенной.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-17.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
