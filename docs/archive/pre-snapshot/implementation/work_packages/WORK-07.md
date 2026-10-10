# WORK-07 — Полнотекстовый поиск и детерминированные сравнения

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **Extra High**. Status: **TODO**.

Почему этот уровень: Проверка сопоставимости, Decimal, условия, диапазоны, доказательства обеих сторон.



[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-07.md).

Dependencies: Offline and full acceptance dependencies: WORK-04 and WORK-06.
Offline checkpoint gate: G0-OFFLINE. Full acceptance retains original AC and applicable live/G1/G2 requirements.

## Execution mode under ADR-006

**Mode:** offline checkpoint under G0-OFFLINE; all live work requires exact source G0-LIVE and original acceptance gates.

Offline work uses local data or explicitly synthetic fixtures only. External ingestion requests are forbidden, including redirects, subresources, parser workers, and browser renderers. Synthetic provenance is isolated from real manifests and publication. A checkpoint marked DONE does not make this WORK DONE or satisfy G1/G2. Preserve every original acceptance criterion.




## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## SRCH-001 — PostgreSQL FTS с фильтрами и оценкой поиска

Reasoning: **Extra High**. [Полное ТЗ](../tasks/SRCH-001.md).

Контракт: SearchQuery{q,banks,as_of,scope,limit}; SearchResult{chunks,coverage}; snippets не authoritative facts.

1. Построить russian tsvector с title/section weights и GIN.
2. Использовать parameterized websearch_to_tsquery, bounded query/limit; bank/date/visibility filters до выдачи.
3. Добавить explicit aliases и salary synonyms, вернуть chunk/evidence IDs и physical_page.
4. Измерить Recall@10 на gold queries и EXPLAIN; не добавлять pgvector без trigger.

Ошибки: Stopwords/empty query →clarify; unsupported bank reject; stale chunks явно отмечены; ts_headline output escape.

Проверки: Russian inflections, bank aliases, numeric criterion, longPDF, no result, HTML injection, per-bank Recall@10.

Критерий: Результаты открывают правильную версию; SQL injection невозможен через query string; metrics report сохранён.

## CMP-001 — Совместимость предложений и трёхзначные условия

Reasoning: **Extra High**. [Полное ТЗ](../tasks/CMP-001.md).

Контракт: Scenario/ComparisonRequest и compatible FactSet из DOMAIN_CONTRACTS.

1. Оценить bounded AST с TRUE/FALSE/UNKNOWN, собрать missing_inputs.
2. Проверить payer/operation/unit/period/currency/date/scope/package.
3. Вернуть typed cell statuses для individual/no_data/conflict/stale/not_applicable.
4. Не ранжировать качественные метрики по произвольному score и не делать default winner.

Ошибки: Unknown input не0, region unknown неfederal; range overlap не exact equality.

Проверки: Truth table all/any, missing salary, employer vs employee, package mismatch, individual, conflicting current facts.

Критерий: Несовместимые предложения никогда не дают численного преимущества; missing inputs перечислены.

## CMP-002 — Детерминированные формулы и доказательства обеих сторон

Reasoning: **Extra High**. [Полное ТЗ](../tasks/CMP-002.md).

Контракт: ComparisonResult rows/pairwise/claims; formula_version, scenario_hash, operand fact/evidence IDs.

1. Реализовать constant/percentage/clamped Decimal и явно оговорённые tiers.
2. Применять source rounding rules; разделять per_batch/per_transfer и known components/total.
3. Создать claim для каждого сравнения с operands обеих сторон и direction registry.
4. Сериализовать результаты без float, stable ordering и neutral bank naming.

Ошибки: Division/base unknown, range overlap, rounding ambiguity →not_comparable/insufficient; missing evidence suppress winner.

Проверки: 30 golden calculations; 100000×0.30%=300; caps/floors; tier boundary; bank label swap; missing component total.

Критерий: 100% golden arithmetic/status; ни одно преимущество без доказательств обоих банков.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-07.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
