# Единые доменные контракты v1

Все DTO versioned, unknown fields rejected, UUID передаются строкой, даты ISO 8601, timestamp UTC с offset; UI Europe/Moscow. Decimal сериализуется строкой. Nullable ≠ omitted ≠ unknown. Не использовать NaN/Infinity. JSON ниже — синтетические примеры, не реальные банковские условия.

## Geography и применимость

`GeoScope = {kind: federal|regional|unknown, region_codes: string[], evidence_ids: UUID[]}`. Federal требует явного подтверждения области действия; отсутствие региональной оговорки само по себе не доказательство. RU-KDA — Краснодарский край. Регион URL, cookies или офиса — observation, не автоматически scope тарифа.

`ScopeDimension = {mode: any|specific|unknown, values: string[]}` используется для employer_segment, organization_category, payroll_package, contract_variant. `specific` требует непустые values, остальные — пустые. Пустой массив не означает all. Product/package идентификаторы назначаются в банковском namespace: одинаковое маркетинговое название у разных банков не общий пакет.

`Scenario` содержит region, employer_segment, organization_category, package_by_bank, contract_variant_by_bank, currency, operation, payer (`employer|employee`), beneficiary, payroll_total?, employee_count?, transfer_amount?, transfers_count?, employee_salary?, period?, as_of. Суммы ≥0, count integer ≥1, as_of обязателен после применения default today. В запросе не должно быть персональных реквизитов сотрудников.

Условия — ограниченный AST, не Python/SQL: `all/any` узлы и leaf `{field, op: eq|in|gte|gt|lte|lt, value, unit}`. Только whitelist полей Scenario; max depth 4, max 30 leaf. Единицы должны совпадать. Missing input вычисляется как UNKNOWN по трёхзначной логике. FALSE → not_applicable; UNKNOWN → needs_inputs. Свободные текстовые условия всегда сохраняются, но не исполняются; для них `requires_manual_interpretation=true` и автоматическое ранжирование запрещено.

## FactCandidate / TariffFact

```json
{
  "schema_version": 1,
  "bank_code": "synthetic_a",
  "product_code": "salary_standard",
  "metric_code": "payroll_credit_fee",
  "payer": "employer",
  "operation": "salary_credit_same_bank",
  "value": {"kind":"percent","amount":"0.30","unit":"percent","currency":null,"basis":"payroll_total","period":"per_batch"},
  "geography": {"kind":"regional","region_codes":["RU-KDA"],"evidence_ids":[]},
  "employer_segment": {"mode":"specific","values":["sme"]},
  "organization_category": {"mode":"any","values":[]},
  "payroll_package": {"mode":"specific","values":["standard"]},
  "contract_variant": {"mode":"unknown","values":[]},
  "conditions": {"schema_version":1,"all":[]},
  "conditions_text": "Тестовый пример",
  "valid_from": null,
  "valid_to": null,
  "effective_date_status": "unknown",
  "evidence_ids": [],
  "validation_flags": ["missing_evidence", "unknown_effective_date"]
}
```

Это валидный формат кандидата, но он не годится для публикации как актуального сопоставимого тарифа: отсутствуют evidence и дата, contract variant неизвестен.

Value discriminated union:

| kind | Обязательные поля | Правила |
|---|---|---|
| money | amount, currency, unit=currency, period | Decimal ≥0, например RUB |
| percent | amount, basis, period, unit=percent | `0.30` означает 0,30%, не 30%; верхняя граница определяется metric registry, не универсальный clamp |
| count | amount integer, unit, period | ≥0 |
| boolean | boolean_value | true/false — подтверждённое наличие/отсутствие |
| text | text_value | не ранжировать как число |
| range | lower/upper, unit, currency?, bounds | «от» = открытая верхняя граница, не точный тариф |
| formula | formula_kind, parameters | только разрешённые формулы |
| individual | text_value | amount=null; стоимость неизвестна |

Unknown/no_public_data — статус результата retrieval, не нулевой TariffFact. «Бесплатно при…» = money 0 плюс обязательные условия. «До …» сохраняет границу и тип, не превращается в гарантированный результат.

Registry метрик в `backend/app/comparison/metrics.py`: code, display_name, allowed value kinds/units, payer/operation, direction `lower|higher|neutral`, required_scenario_fields. Минимум: payroll_credit_fee, external_bank_transfer_fee, account_monthly_fee, employee_card_fee, cash_withdrawal_limit, transfer_limit, crediting_time, employee_privilege, premium_eligibility, integration_1c, integration_api. У cash/transfer limit отдельно channel, период и тип операции; время зачисления сравнивать только при совпадении cut-off и рабочего календаря. Boolean integration сравнивает факт наличия, не качество сервиса.

## Provenance / Evidence

`EvidenceRef = {evidence_id, fact_id?, chunk_id, document_id, source_version_id, extraction_run_id, quote, quote_start?, quote_end?, physical_page?, printed_page_label?, section_label?, original_url, fetched_at, raw_sha256}`.

Quote — подстрока immutable extracted chunk; offsets относятся к Unicode code points нормализованного текста конкретного extraction run. Для числового факта ссылка должна покрывать значение, единицу/базу и ограничения; можно несколько evidence refs (ячейка + заголовок + сноска). Не доказана связь сноски — pending_review. HTML physical_page=null; нет достоверного heading — section_label=null. PDF page ∈ [1,page_count]. Номер печатной страницы не используется как browser page.

## Даты и версии

Различать `fetched_at` (получили bytes), `observed_at` (проверили источник), `published_at` (дата автора, nullable), `valid_from/valid_to` (действие условия), `recorded_at`/`publication_revision` (когда система узнала и одобрила). Интервал действия `[valid_from, valid_to)`. Указанное банком «до 31 декабря включительно» нормализовать в valid_to=1 января, сохранить исходную формулировку.

`effective_date_status = explicit|analyst_confirmed|unknown`. Для analyst_confirmed нужно evidence/обоснование; нельзя произвольно назначить fetched_at датой начала. Неизвестная дата допускает справочную цитату со статусом unknown, но исключает однозначный current winner. Future effective facts — доступные объявленные сведения, не текущие тарифы.

История двух осей: запрос `as_of` отвечает об условиях на дату по текущему знанию; `knowledge_cutoff` ограничивает публикации тем, что знала система в тот момент. Публикации append-only. Supersession фиксирует область и интервал, не удаляет прежний факт. PDF может обновить только один раздел — другие разделы не считаются отменёнными.

Алгоритм выбора: фильтровать approved publication + ACL → knowledge_cutoff → доказанную применимость и период → учесть scoped supersession/revocation → проверить неоднозначности → freshness. Параллельные противоречащие действующие факты возвращают conflict. Правило «regional всегда важнее federal» запрещено: override нужен явно в документе/решении review.

Freshness: `last_successful_check` источника и `last_successful_parse` отдельно; proposed stale threshold 72h при 24h schedule. Действующий подтверждённый historical interval сам по себе не «устаревает», но для утверждения о сегодняшнем предложении нужен freshness. Старый документ не плох только из-за даты, свежая HTML-страница не обязательно применима.

## ComparisonRequest / Result

Request: bank_codes 2..4 unique, metric_codes 1..20, scenario, as_of, knowledge_cutoff?, include_stale=false. Result: comparison_id, corpus_revision, scenario_echo, rows[], claims[], limitations[], generated_at.

Row: metric_code, cells[{bank_code,status,value,fact_ids,evidence_ids,conditions,missing_inputs}], pairwise[{left,right,status,delta?,formula?,claim_id?}]. Status cell: verified/not_applicable/unknown/individual/conflict/stale; pairwise: better/worse/equal/not_comparable/insufficient/conflict/stale. Победитель по критерию возможен только при verified обеих сторон и одинаковой базе.

Алгоритм расчёта:

1. Сопоставить единицы, валюту, payer, operation, time basis и scenario. Нельзя сравнить плату сотрудника с платой работодателя.
2. Оценить predicates. Для неизвестных inputs вернуть их имена, а не брать 0.
3. В POC поддержать constant, percentage, percentage_clamped. Последняя `min(max(base*rate/100, min_fee), max_fee)`; отсутствующие cap/floor не заполнять нулём, соответствующий шаг пропускать. Требовать min_fee≤max_fee, одну валюту и одинаковую базу всех operands. Tiered разрешать только с явными непересекающимися bounds, исчерпывающим покрытием и режимом marginal/whole_amount из источника; иначе review.
4. Decimal precision 28; rate numeric(12,6), money numeric(20,6). Round до minor units только согласно правилам источника; при неизвестном порядке округления итог оценочный и winner при чувствительности не публикуется. Golden tests должны покрывать fee per transfer и per batch — это разные расчёты.
5. Показать отдельно fixed и variable cost. Total cost только при полном перечне применимых компонентов; иначе «известные компоненты», без общего winner.
6. Для диапазонов winner возможен лишь при непересекающихся bounds и одинаковых условиях; пересечение → not_comparable. Качественные преимущества перечисляются без общего балла.
7. Claim хранит operands fact IDs, result, formula_version, scenario hash и evidence обеих сторон.

Синтетическая проверка: 100000 RUB × 0.30/100 = 300 RUB; max(min(300,500),100)=300. 0 и unknown должны дать разные результаты. Смена обозначений банков A/B не меняет арифметику и обращает direction.

## LLMProvider и AnswerEnvelope

LLMRequest: purpose `intent|explain`, system_template_version, messages (bounded), output_schema, max_output_tokens, timeout_ms, request_id. Provider не получает DB connection, storage paths, API secrets других систем или пользовательские credentials.

LLMResponse: parsed_json, usage `{input_tokens?,output_tokens?,estimated}`, provider_request_id?, model_id?, finish_reason, latency_ms. Errors: timeout/rate_limit/auth/unavailable/invalid_output/context_exceeded. Fake реализует ту же схему и сценарии malformed, timeout, injection.

Intent JSON: intent `compare|facts|changes|documents|clarify`, bank_codes, focus_bank?, metric_codes, scenario_patch, date_mode, clarification?. Explain JSON: ordered_claim_ids, template_by_claim, limitation_codes. Arbitrary numeric prose запрещён. Линки, evidence metadata и цифры строит backend. Для свободных вопросов допустим подбор точных выдержек с источником; отсутствие ответа в фактах/цитатах → limitation.

AnswerEnvelope: schema_version, answer_id, status `answered|partial|clarification|insufficient|fallback`, text, comparison?, claims[], sources[], limitations[], context_version, corpus_revision, data_as_of, generated_at. Claim kind `fact|calculation|comparison|absence_of_evidence`, template_code, parameters из backend, supporting_fact_ids[], evidence_ids[]. Absence_of_evidence формулируется «в проверенном корпусе не найдено», не «банк не предоставляет».

Budget defaults: максимум 2 provider calls/question (intent + explanation), 0 при deterministic route; суммарный input budget 8000 и output 1500 tokens; timeout 20s/call, общий deadline 45s, max 1 retry только transient и в том же общем call/budget cap. Max 10 retrieved chunks по 2000 символов с общей обрезкой до budget, 6 последних сообщений после redaction. Не обрезать условия/сноски ради лимита: исключить весь неполный claim. 5 конкурентных calls globally, 1/user; proposed daily quota 50000 tokens/user, hard deployment quota через config.

Счётчик резервирует верхнюю оценку атомарно до вызова, reconciles actual usage после ответа. При отсутствии provider usage применяется консервативная оценка и признак estimated; деньги считаются только при утверждённой price config, иначе cost unknown. Crash после отправки запроса не освобождает резерв автоматически: неизвестное потребление сохраняется как estimated до reconciliation/конца бюджетного окна, чтобы retry не обошёл cap. Неотправленный запрос можно освободить при доказанном transport state. Идентичный public evidence explanation может кэшироваться по query/scenario/corpus/prompt/model; персональные messages в shared cache не входят.

Daily windows считаются по явно настроенной Europe/Moscow, usage timestamps хранятся в UTC. Изменение model/prompt/corpus или revocation evidence инвалидирует cache. Обязательные limitations определяются backend и не могут быть удалены LLM ради более выгодного представления одного банка.


## Source policy and corpus provenance (ADR-006)

A source-policy decision precedes retrieval and is scoped to exact scheme/host/path plus explicitly allowed redirect targets. It records the responsible decision, official relationship, applicable terms/robots, permission for acquisition, storage and reuse, purpose, rate/expiry, and revocation state. FetchGateway checks the active decision before every request; missing/unknown/expired/revoked policy is BLOCKED. Retrieval permission and content acceptance are separate events. Content acceptance records actual final URL, redirects, MIME/size/hash, document family, dates, and applicability evidence.

Manual import has its own provenance and storage/reuse approval and cannot count as automated retrieval or G1 scheduled-fetch evidence. `corpus_kind=synthetic|real` (or an equivalent enforced namespace boundary) is immutable provenance: synthetic fixtures are isolated from real publication, and real fact approval rejects synthetic provenance. No fake tariff is represented as a bank fact.
