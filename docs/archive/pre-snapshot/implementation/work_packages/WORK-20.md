# WORK-20 — Независимый финальный аудит

Исполнитель: **Astra**. Reasoning по умолчанию: **—**. Status: **TODO**.

Почему этот уровень: Исполнитель Astra по исходному распределению ролей; Luna не проводит собственный независимый аудит.

Dependencies: [WORK-15](WORK-15.md), [WORK-16](WORK-16.md), [WORK-19](WORK-19.md)

Gates входящих этапов: G3 + G4. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-20.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## REV-001 — Независимый финальный аудит реализации

Reasoning: **—**. [Полное ТЗ](../tasks/REV-001.md).

Контракт: REVIEW_CHECKLIST; immutable commit/schema/corpus snapshot и findings template.

1. Зафиксировать release candidate и перечень accepted ADR/capability limitations.
2. Независимо проверить architecture/security/data/evidence/comparison/LLM/operations и существенные tests.
3. Записать severity/cause/files/impact/fix/retest для каждого finding.
4. Выдать NOT READY при Critical/High; real API integration учитывать только если LLM-003 завершена.

Ошибки: Отсутствующий отчёт/нет restore evidence не трактовать как pass; код авторства Luna не принимать без проверки.

Проверки: Независимая воспроизводимая выборка paths и полная checklist evidence; adversarial spot checks.

Критерий: Все пункты оценены; findings пригодны для исправления; никаких необоснованных READY.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-20.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
