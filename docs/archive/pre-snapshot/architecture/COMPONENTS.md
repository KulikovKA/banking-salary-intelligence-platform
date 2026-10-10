# Компоненты и ответственность

| Модуль | Вход → выход | Владелец данных | Недопустимые зависимости |
|---|---|---|---|
| config | env/secrets → validated Settings | конфигурация процесса | сеть при import |
| identity | credentials/invites → Principal | users, sessions, roles | LLM |
| registry | approved URLs → due sources | banks, sources, source_policies | произвольный fetch URL из чата |
| ingestion | source/job → fetch observation + blob | jobs, fetches, source_versions | AI availability |
| processing | blob/parser version → pages/chunks/candidates | extraction_runs, chunks | перезапись originals |
| facts | candidates/review → publication | tariff_facts, evidence, reviews | внешний LLM как истина |
| search | scoped query → ranked chunks | производные FTS поля | самостоятельная публикация facts |
| comparison | scenario + verified facts → typed rows/claims | comparison_runs | LLM arithmetic |
| assistant | question/context → verified AnswerEnvelope | answer_runs, claims | произвольный SQL/URL/tool |
| chats | owned session → messages/context | chats | ownership только во frontend |
| changes | publications → events/notifications | change_events, outbox | уведомления о raw diff как тарифе |
| documents | authorized document UUID → metadata/stream | read-only originals | файловый путь от клиента |
| operations | metrics/jobs → health/diagnostics | job logs, audit | сырые тексты чатов в logs |

## Внутренние интерфейсы

Интерфейсы Python Protocol; DTO Pydantic с `extra=forbid`, явной schema_version. Доменные объекты не привязаны к HTTP и ORM session. Transaction boundary находится в application service. Repository не вызывает commit самостоятельно.

```text
BankAdapter.discover(SourceConfig, FetchGateway) -> list[DiscoveredLink]
BankAdapter.classify(FetchArtifact) -> DocumentDescriptor
BankAdapter.extract(ParseResult, ProductScope) -> list[FactCandidate]
FetchGateway.fetch(ApprovedUrl, ConditionalHeaders) -> FetchResult
BlobStore.put(stream, expected_type) -> BlobReceipt
BlobStore.open(blob_id) -> byte stream
DocumentParser.parse(blob, parser_config) -> ParseResult
FactValidator.validate(candidate, evidence, scope) -> ValidationResult
PublicationService.publish(review_id, expected_revision) -> PublicationReceipt
FactRepository.select(Scenario, as_of, knowledge_cutoff) -> FactSet
SearchService.search(SearchQuery, Principal) -> SearchResult
ComparisonService.compare(ComparisonRequest, FactSet) -> ComparisonResult
LLMProvider.generate(LLMRequest) -> LLMResponse
AssistantService.answer(QuestionRequest, Principal) -> AnswerEnvelope
```

`FetchGateway` единственный сетевой вход к банковским ресурсам, и discovery использует его же. Адаптер возвращает ссылки-кандидаты; не добавляет автоматически новый домен в разрешённые. `BlobStore` не принимает пользовательские относительные пути. Смена local на object storage не меняет `document_id` и evidence IDs.

## Обязательные коды ошибок

Domain: `unsupported_scope`, `unknown_effective_date`, `incomplete_evidence`, `conflicting_facts`, `not_comparable`, `stale_source`. Это результат данных, обычно HTTP 200 с явным status.

Infrastructure: `fetch_timeout`, `source_blocked`, `invalid_mime`, `parse_failed`, `needs_ocr`, `storage_full`, `lease_lost`, `provider_timeout`, `budget_exceeded`, `invalid_provider_output`. Ошибка не преобразуется в «бесплатно» или «условие отсутствует».

API: `unauthenticated`, `forbidden`, `not_found`, `version_conflict`, `validation_error`, `rate_limited`, `temporarily_unavailable`. Внешний ответ не содержит traceback, SQL или API key.
