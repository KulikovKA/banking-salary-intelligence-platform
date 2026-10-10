# Доменные контракты snapshot v1 (план)

Единый источник контрактов для SNAP-01. Это целевой интерфейс, не заявление
о наличии модулей. DTO: Pydantic, extra=forbid, schema_version=1, UUID strings,
Decimal strings, ISO dates, UTC timestamps с offset. UI отображает Europe/Moscow.
Unknown/null не равно нулю, пустому значению или all. Bank codes только
`sber|vtb|alfa|kuban_credit`; synthetic identities разрешены только test namespace.

## Corpus и Parsing

`Snapshot={id, revision, corpus_kind, state:draft|frozen|revoked, created_at,
frozen_at?, manifest_sha256}`. Membership у frozen append-only; исправление —
новый snapshot. Отзыв прав помечает доступ blocked даже для frozen snapshot;
не удаляет audit и не переписывает оригинал. Смена текущего snapshot явная.

`SnapshotMember={snapshot_id, source_version_id, extraction_run_id}`: только
accepted source_version, успешный extraction, согласованный corpus_kind.
Реальный snapshot не принимает synthetic source/blob/chunk/fact.

`ParseRequest={source_version_id, raw_sha256, kind:pdf|xlsx|html, corpus_kind,
parser_version}`; parser получает проверенный локальный original, без URL fetch.
`ParseResult={status:ok|needs_ocr|unsupported|failed, extraction_sha256,
parser_version, blocks[], diagnostics[]}`. `ParsedBlock={block_id, text,
locator, heading?, table_id?, relations[]}`; canonical serialization и text/hash
детерминированы на одинаковых bytes+parser version. Только ok может стать evidence.
relations связывают cell/header/footnote, непроверенная связь требует review.
Locator union: PDF `{physical_page>=1, bbox?, table_cell?}`; XLSX
`{sheet, cell_range, formula?, cached_value?}`; HTML `{element_path, heading?}`.
Макросы/формулы/JS не выполнять; внешние ресурсы/links не загружать.

`ExtractionRun={id, source_version_id, raw_sha256, extraction_sha256,
parser_version, corpus_kind, status, created_at}`; `Chunk={id, extraction_run_id,
ordinal, text, text_sha256, locator, relations}`. Нормализация текста фиксируется
версией parser; offsets — Unicode code points именно immutable Chunk.text.

## TariffCandidate и Evidence

`ScopeDimension={mode:any|specific|unknown, values[]}`: specific непустой,
остальные пусты. Any/federal должны подтверждаться источником; отсутствие
оговорок не доказывает федеральность. Geography `{kind:federal|regional|unknown,
region_codes[], evidence_ids[]}`, для regional нужны коды, например RU-KDA.

`Scenario={region?, employer_segment?, organization_category?, package_by_bank?,
contract_variant_by_bank?, payer:employer|employee, operation, currency,
payroll_total?, employee_count?, transfer_amount?, transfers_count?, period?, as_of}`.
Суммы неотрицательны, counts >=1; реквизиты/ФИО сотрудников не принимаются.
Missing input — UNKNOWN. as_of обязателен в engine; UI/API может задать сегодняшнюю
дату явно с отображением пользователю, но не выводит действие тарифа из fetch date.

`TariffCandidate={id, bank_code, metric_code, value, payer, operation, period,
geography, employer_segment, organization_category, payroll_package,
contract_variant, conditions, conditions_text, requires_manual_interpretation,
valid_from?, valid_to?, effective_date_status:explicit|analyst_confirmed|unknown,
evidence_ids[], validation_flags[], corpus_kind}`. Всегда pending_review.

Value discriminated union:

| kind | Поля / смысл |
|---|---|
| money | amount Decimal, currency, unit=currency, period |
| percent | amount Decimal, unit=percent, basis, period; `0.30` = 0,30% |
| count | integer amount, unit, period |
| boolean / text | boolean_value / text_value, без числового ранжирования текста |
| range | lower?, upper?, inclusive bounds, unit, currency?, basis?, period |
| formula | constant/percentage/percentage_clamped, parameters, basis, currency, period |
| individual | text_value, amount отсутствует; нельзя подменять нулём |

«Бесплатно при…» — 0 с обязательными условиями; «от» — range, не точная цена.
Условия AST: all/any, leaves `{field,op:eq|in|gte|gt|lte|lt,value,unit}`;
whitelist Scenario, max depth 4, 30 leaves. Неисполняемый текст сохраняется и
блокирует winner. Нормализация не угадывает units/basis/date/scope.

`EvidenceRef={id, source_version_id, extraction_run_id, chunk_id, raw_sha256,
extraction_sha256, quote, quote_start, quote_end, locator, support_role:
value|unit|basis|condition|scope|date, original_url, acquired_at}`.
Для числового факта полный набор refs покрывает число, единицы/базу, обязательные
условия, scope и даты. Несколько refs допустимы для cell/header/footnote.
Проверяются bytes hash, extraction hash, refs принадлежность одному происхождению,
точная substring и locator. PDF page <= actual page_count; XLSX range должен
существовать; HTML path должен относиться к сохранённому DOM. Обоснование
analyst_confirmed хранится в review; неизвестная дата остаётся unknown.
Существующий `ingestion.evidence.ExtractionEvidence` сохраняется; новый validator
дополняет его проверками происхождения и фактической поддержки, а не заменяет.

`Review={id,candidate_id,decision:approved|rejected|needs_review,reviewer_id,
reason,evidence_validation,created_at}` append-only.
`PublishedFact={id,candidate_id,review_id,snapshot_id}`: review approved + evidence
valid + допустимый corpus; publish атомарный и идемпотентный. Approved fact с
unknown date/scope может быть справочной цитатой, но не verified current price.
Ошибочная публикация корректируется новой revision/revocation, не UPDATE fact.

## Метрики, поиск и сравнение

Registry в `tariffs/metrics.py`: code, title, allowed kinds/units, payer, operation,
direction lower|higher|neutral, required_scenario_fields. Минимум для v1:
payroll_credit_fee, external_bank_transfer_fee, account_monthly_fee,
employee_card_fee, cash_withdrawal_limit, transfer_limit, crediting_time,
employee_privilege, integration_1c, integration_api. Это критерии для coverage,
не утверждение, что документы содержат все значения.

`SearchRequest={snapshot_id,query,bank_codes?,metric_codes?,limit<=10}`.
`SearchHit={chunk_id,text,locator,evidence_ids,source_version_id,raw_sha256,
snapshot_id,score}`. Только frozen readable members; rejected/quarantine excluded.
Отсутствие сведений = «в проверенном корпусе не найдено», не «банк не предоставляет».

`ComparisonRequest={snapshot_id,bank_codes:2..4 unique,metric_codes:1..20,
scenario}`. `ComparisonResult={id,snapshot_id,corpus_revision,scenario_echo,
rows[],claims[],limitations[],generated_at}`. Row содержит metric_code,
cells `{bank_code,status,value?,fact_ids,evidence_ids,missing_inputs,conditions}`
и pairwise `{left,right,status,delta?,formula?,claim_id?}`.
Cell status verified|not_applicable|unknown|individual|conflict|blocked;
pairwise better|worse|equal|not_comparable|insufficient|conflict.

Winner только при совместимой currency/unit/period/payer/operation/basis,
доказанной scope/date applicability и истинных условиях обеих сторон. Интервал
действия `[valid_from,valid_to)`; acquired_at не valid_from. Future исключается
для более раннего as_of. Overlapping contradictory facts -> conflict, latest
fetch/regional не wins автоматически. Snapshot фиксирует knowledge revision;
полноценный knowledge_cutoff/bitemporal API в v1 не нужен.

Decimal precision 28, money numeric(20,6), rates numeric(12,6), без float.
percentage = base*rate/100, clamped = min(max(value,min_fee),max_fee), пропуск
неуказанного bound. Fees per transfer и per batch различаются. Rounding только
по подтверждённому правилу; иначе estimation + limitation, без чувствительного
winner. «Известные компоненты» вместо total cost при неполной стоимости.
Ranges с пересечением/individual/неясные tiered — not_comparable. Общего рейтинга
банков нет. Claim содержит operands fact IDs, formula_version, scenario hash,
computed result и evidence обеих сторон.

## LLM и AnswerEnvelope

`LLMRequest={purpose:intent|explain,template_version,messages,output_schema,
max_output_tokens,timeout_ms,request_id}`; `LLMResponse={parsed_json,usage,
provider_request_id?,model_id,finish_reason,latency_ms}`. Errors:
timeout|rate_limit|auth|unavailable|invalid_output|context_exceeded|budget_exceeded.
Fake и Groq имеют одинаковый async Protocol. Reasoning traces не сохраняются
и не показываются. `LLM_MODE=fake|provider` остаётся существующим config contract.

Intent: `{intent:compare|facts|documents|clarify,bank_codes,metric_codes,
scenario_patch,clarification?}`. Explain: `{ordered_claim_ids,template_by_claim}`;
неизвестные IDs/шаблоны, invented numbers/URL запрещены. Backend вычисляет claims,
рендерит числа, даты, ограничения и ссылки. Fallback работает при любой LLM ошибке.

`AnswerEnvelope={schema_version,id,status:answered|partial|clarification|
insufficient|fallback,snapshot_id,corpus_revision,text,comparison?,claims[],
sources[],limitations[],data_as_of,generated_at}`. Claim kinds fact|calculation|
comparison|absence_of_evidence. Сервер строит sources с authenticated download URL;
LLM не выбирает произвольные документы/URL/SQL и не изменяет mandatory limitations.
В v1 question stateless: scenario и bounded вопрос; session — только auth.
История диалога хранится в UI памяти без долговременной server chat subsystem.
