# WORK-01 — Источники и границы покрытия

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **High**. Status: **BLOCKED** — источники и один справочный original инвентаризированы; bank-side permission/terms/rate limits автоматического сбора не подтверждены, полный employer tariff/conditions набор по четырём банкам не получен. Отчёты: [SRC-001](../../../../reports/SRC-001.md), [WORK-01](../../../../reports/WORK-01.md).

Почему этот уровень: Нужно различить официальность, применимость и достаточность условий; правовое решение остаётся у ответственного.



[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-01.md).

Dependencies: Source retrieval is blocked; no source-specific G0-LIVE exists.
Offline checkpoint gate: G0-OFFLINE. Full acceptance retains original AC and applicable live/G1/G2 requirements.

## Execution mode under ADR-006

**Mode:** live/acceptance for source manifest decisions; current source status remains BLOCKED and no target request is permitted without G0-LIVE(source).

Offline work uses local data or explicitly synthetic fixtures only. External ingestion requests are forbidden, including redirects, subresources, parser workers, and browser renderers. Synthetic provenance is isolated from real manifests and publication. A checkpoint marked DONE does not make this WORK DONE or satisfy G1/G2. Preserve every original acceptance criterion.




## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## SRC-001 — Инвентаризация официальных источников и допустимости сбора

Reasoning: **High**. [Полное ТЗ](../tasks/SRC-001.md).

Контракт: SourceAcceptanceManifest по docs/research/SOURCES.md; одна запись на URL, policy decision и coverage на банк.

1. Проверить стартовые URLs по официальным страницам и записать final URL/redirect chain.
2. Найти для каждого банка product page, тарифный PDF и правила/условия, различить manual/news/tariff.
3. Записать robots.txt, terms URL, ограничения частоты и решение ответственного; не объявлять robots разрешением.
4. Сохранить matrix банк×метрика×регион×пакет с unknown; приложить SHA-256 доступных оригиналов в разрешённое fixture storage.

Ошибки: 403/CAPTCHA/неясные права → blocked source и причина; сторонний mirror исключить; не заменять тариф справочником API.

Проверки: Ручная сверка минимум одного tariff/conditions документа на каждый банк; проверить URL и даты, повторить GET с целевого host; документы с неизвестной датой пометить.

Критерий: Четыре банковские строки с доказательствами официальности и решениями policy; пробелы покрытия перечислены, ни один непроверенный URL не approved.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-01.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
