# WORK-16 — ПД, лицензии и удаление данных

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **High**. Status: **TODO**.

Почему этот уровень: Согласование политики, retention и удаления после restore; reasoning не заменяет ответственного по правовым решениям.

Dependencies: [WORK-01](WORK-01.md), [WORK-14](WORK-14.md)

Gates входящих этапов: G2. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-16.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## SEC-003 — ПД, лицензии, retention и условия production

Reasoning: **High**. [Полное ТЗ](../tasks/SEC-003.md).

Контракт: SECURITY policies, retention/chat deletion/restore tombstones; пользователь и ответственные утверждают правовые решения.

1. Составить data flow inventory: accounts/chat/logs/backup/LLM и территории обработки.
2. Ответственный проверяет актуальные закон/уведомления/банковские terms и подписывает решения; не выдавать инженерный отчёт за legal opinion.
3. Проверить dependency licenses включая PDF и зафиксировать выбранную схему.
4. Реализовать retention job и deletion tombstones по утверждённым срокам, проверить no unauthorized external payload.

Ошибки: Нет утверждения срока/provider flow →соответствующая production capability BLOCKED, mock work доступна.

Проверки: Frozen clock retention boundaries, delete→backup restore→tombstone replay, public payload canaries, license inventory complete.

Критерий: Активные потоки имеют владельца/правовое решение, политика удаления реализована и проверена.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-16.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
