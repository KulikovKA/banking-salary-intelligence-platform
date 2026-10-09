# WORK-09 — Оценка ядра и приёмка POC G2

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **High**. Status: **TODO**.

Почему этот уровень: Анализ качества, покрытия и ошибок holdout; нельзя принять красивые ответы при нехватке источников.

Dependencies: [WORK-05](WORK-05.md), [WORK-08](WORK-08.md)

Gates входящих этапов: G1. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-09.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## QA-002 — Gate G2: оценка технического ядра POC

Reasoning: **High**. [Полное ТЗ](../tasks/QA-002.md).

Контракт: EVALUATION_PLAN и G2 ACCEPTANCE_CRITERIA.

1. Подготовить human-reviewed gold/tune/holdout по document families и coverage matrix.
2. Измерить precision/condition recall/Recall@10/evidence/comparison/abstention раздельно.
3. Запустить 30 gold comparisons и failure/injection cases POC.
4. Оформить GO/NO-GO с counts/ошибками/минимум3 metrics на пару и получить приёмку пользователя.

Ошибки: Нулевой denominator NOT EVALUATED; не снижать порог автоматически; incomplete real corpus не заменить synthetic.

Проверки: Все G2 thresholds, per-bank breakdown, original linkage100%, no invented numbers, rerun frozen fixtures.

Критерий: Доказано ядро или честно зафиксирован NO-GO; полный MVP начинается только после G2.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-09.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
