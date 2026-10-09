# WORK-06 — Тарифные факты, проверка и публикация

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **Extra High**. Status: **TODO**.

Почему этот уровень: Основной риск неверных тарифов: даты, scope, provenance, конфликты и атомарность публикации.



[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-06.md).

Dependencies: Offline checkpoint dependency: WORK-04. Real-corpus acceptance additionally requires WORK-05 and G1.
Offline checkpoint gate: G0-OFFLINE. Full acceptance retains original AC and applicable live/G1/G2 requirements.

## Execution mode under ADR-006

**Mode:** offline checkpoint under G0-OFFLINE; all live work requires exact source G0-LIVE and original acceptance gates.

Offline work uses local data or explicitly synthetic fixtures only. External ingestion requests are forbidden, including redirects, subresources, parser workers, and browser renderers. Synthetic provenance is isolated from real manifests and publication. A checkpoint marked DONE does not make this WORK DONE or satisfy G1/G2. Preserve every original acceptance criterion.




## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## DB-003 — Миграции фактов, evidence и публикаций

Reasoning: **Extra High**. [Полное ТЗ](../tasks/DB-003.md).

Контракт: metric_definitions/tariff_facts/fact_evidence/fact_reviews/corpus_state/publications/publication_facts/fact_supersessions.

1. Создать tables и referenced constraints; payload_hash и parent_fact_id для correction candidates.
2. Создать unique extraction+semantic_key+payload_hash и immutable publication revision.
3. Добавить metric seeds с direction и required inputs без bank-specific values.
4. Добавить транзакционные repositories и dated selection query scaffolding.

Ошибки: Не ставить UNIQUE на semantic_key без version; conflicting candidates допустимы; cascade evidence delete запрещён.

Проверки: Upgrade populated docs; duplicate candidates; invalid date interval; publication rollback; FK quote references.

Критерий: Schema допускает историю и conflict, запрещает dangling evidence и повтор кандидата.

## FACT-001 — Нормализованные DTO тарифов и applicability

Reasoning: **Extra High**. [Полное ТЗ](../tasks/FACT-001.md).

Контракт: FactCandidate, value discriminated union, ScopeDimension, predicate AST из DOMAIN_CONTRACTS.

1. Реализовать strict Pydantic DTO и Decimal string serialization.
2. Нормализовать comma decimals/NBSP/руб/%/period без потери оригинального текста.
3. Реализовать kind money/percent/range/individual/formula и metrics registry.
4. Валидировать geography/segment/package/date enums и AST bounds; unknown не конвертировать в any.

Ошибки: Несогласованные единицы, NaN/Infinity, отрицательная комиссия, malformed AST →typed validation; free text остаётся manual.

Проверки: 0 vs null vs individual, 0,3%=0.30, from/up-to, RUB period, unknown scope; roundtrip DTO JSON.

Критерий: Нормализация воспроизводима и не добавляет недостающих дат/чисел.

## FACT-002 — Извлечение кандидатов по правилам и provenance

Reasoning: **Extra High**. [Полное ТЗ](../tasks/FACT-002.md).

Контракт: Adapter.extract(ParseResult,ProductScope)->FactCandidate[] с evidence roles value/unit/condition/date/scope.

1. На размеченных банковских fixtures задать versioned extraction rules для ключевых metrics.
2. Связать значение с header/basis/footnotes, допустить несколько evidence refs.
3. Сохранять confidence только diagnostic, flags и raw quote; не публиковать автоматически.
4. Dedup кандидаты по extraction/payload hash; сохранять unsupported rows для review.

Ошибки: Оборванная сноска/две возможные единицы/неизвестный package →pending_review; no LLM requirement.

Проверки: ≥80 gold facts; precision value+unit+basis, condition recall; tests intentionally missing headers и mixed packages.

Критерий: Каждый candidate объясним quote+rule version; missing fields не выдуманы; gold metrics рассчитаны.

## FACT-003 — Валидация и решения аналитика

Reasoning: **Extra High**. [Полное ТЗ](../tasks/FACT-003.md).

Контракт: ValidationResult{eligible,flags,missing_evidence}; ReviewRequest из API_CONTRACTS.

1. Проверить quote equality/offset/page, value-unit-basis-condition coverage и effective dates.
2. Реализовать approved/rejected/needs_changes с reason/expected_hash.
3. Corrections создают новый candidate с parent; первоначальный immutable.
4. POC review через локальный CLI service, MVP route добавляется API-002; actor_type human/rule и version аудируются.

Ошибки: Stale expected_hash →409; no evidence →approve denied; confidence не разрешает missing applicability.

Проверки: Malformed quote, nonexistent page, date fetched substituted, concurrent reviews, correction preserves original.

Критерий: Нельзя одобрить некорректное evidence; решения append-only; disputed candidate не появляется в published queries.

## FACT-004 — Атомарная публикация и выбор действующих фактов

Reasoning: **Extra High**. [Полное ТЗ](../tasks/FACT-004.md).

Контракт: PublicationReceipt{revision,fact_ids}; select(Scenario,as_of,knowledge_cutoff)->FactSet.

1. Под lock corpus_state проверить approved facts/originals и создать publication members/revision одной транзакцией.
2. Вести scoped supersession/revocation с evidence, не is_current flag.
3. Реализовать selection valid interval/knowledge cutoff/region/contract и conflict/unknown/freshness.
4. Предоставить publication callback/interface для будущего change event без внешнего network side effect.

Ошибки: Параллельная публикация →retry/409; future fact не активен раньше даты; partial document не отменяет все old facts.

Проверки: Future/retroactive/unknown dates, federal+regional without override, partial replacement, two commits race, rollback evidence missing.

Критерий: Snapshot selection воспроизводим; old versions доступны; conflicted/stale данные не становятся безусловным winner.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-06.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
