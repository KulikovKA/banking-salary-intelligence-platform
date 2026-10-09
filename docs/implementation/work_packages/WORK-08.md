# WORK-08 — Ассистент POC, Fake LLM, API и минимальный экран

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **High**. Status: **TODO**.

Почему этот уровень: Вертикальный сценарий вопрос→проверенный claim→полный оригинал. Для AI-002 отдельно назначен Extra High.

Dependencies: [WORK-04](WORK-04.md), [WORK-06](WORK-06.md), [WORK-07](WORK-07.md)

Gates входящих этапов: G0. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-08.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## LLM-001 — Провайдерский Protocol и Fake LLM

Reasoning: **High**. [Полное ТЗ](../tasks/LLM-001.md).

Контракт: LLMRequest/Response/Error из DOMAIN_CONTRACTS; final provider/model unspecified.

1. Определить interface generate и capability metadata для structured output/token counting.
2. Создать deterministic Fake scenarios intent/explain/timeout/malformed/unknown_claim.
3. Подключить mode=fake config, provider mode fail если не выбран adapter.
4. Создать contract tests не зависящие от сети или API key.

Ошибки: Unsupported output schema/finish_reason truncation →invalid_output; Fake явно маркирован, не симулирует реальный quality score.

Проверки: Valid JSON roundtrip, missing fields, malicious tool proposal, timeout, usage absent estimate.

Критерий: Offline suite работает без секретов; замена provider не требует изменения comparison/parser.

## AI-001 — Intent и безопасные read-only инструменты

Reasoning: **High**. [Полное ТЗ](../tasks/AI-001.md).

Контракт: Intent DTO и инструменты search_documents/get_tariff_facts/compare_banks/get_recent_changes/get_document_metadata.

1. Добавить deterministic routes для явных filters и Fake intent для POC.
2. Проверить bank/metric enums, scenario bounds, max tool calls5.
3. Связать инструменты с application services без произвольного SQL/URL и write methods.
4. Changes tool до CHG-001 возвращает capability unavailable, не пустую фиктивную историю.

Ошибки: Unsupported intent →clarification; user/source instruction не расширяет tool allowlist; arbitrary URL reject.

Проверки: Compare prompt, missing bank, ambiguous scope, injection requesting filesystem/network, invalid tool arguments.

Критерий: Инструменты читают только разрешённые данные; POC intent не требует real API.

## AI-002 — Claim validation и evidence-first renderer

Reasoning: **Extra High**. [Полное ТЗ](../tasks/AI-002.md).

Контракт: Explain JSON ordered_claim_ids/template_by_claim; AnswerEnvelope и citations backend-owned.

1. Создать registry templates для facts/comparison/limitations и typed parameters.
2. Проверить все claim IDs, operands, allowed templates, evidence page/quote/applicability.
3. Собрать text/table/links из backend data; LLM выбирает допустимый порядок.
4. На invalid output вернуть deterministic table+limitations без второго judge call.

Ошибки: Existing URL без supporting claim не проходит; unknown claim/свободная цифра/выдуманная дата →reject.

Проверки: Spoofed citation, swapped bank value, wrong page, future fact, extra sentence claiming winner, malicious evidence instruction.

Критерий: Все существенные предложения отображают проверенные claims; unknown не ноль; поддельное утверждение не выходит.

## DOC-001 — API метаданных и полный оригинал по UUID

Reasoning: **High**. [Полное ТЗ](../tasks/DOC-001.md).

Контракт: GET documents/version content/evidence из API_CONTRACTS, Principal interface с local POC principal.

1. Выдать metadata document/version/source URL/fetched/effective/page fields.
2. Реализовать stream/Range/ETag полного PDF через BlobStore.
3. HTML original attachment, escaped text preview, safe filename/nosniff.
4. Проверять access policy dependency; POC principal только loopback, MVP замена в AUTH-003.

Ошибки: Missing blob →503+operator alert, не redirect на случайный current file; invalid range416; path rejected.

Проверки: PDF hash bytes equality,206/416, correct page fragment, HTML script inert, unknown id404, original unavailable.

Критерий: Открывается именно цитированная версия целиком; PDF page основана на physical_page.

## API-001 — POC routes сравнения, поиска и вопроса

Reasoning: **High**. [Полное ТЗ](../tasks/API-001.md).

Контракт: Внутренний POC /poc/questions синхронный AnswerEnvelope; остальные DTO/API v1 неизменны.

1. Соединить intent→snapshot retrieval→comparison→Fake explanation→validated renderer.
2. Добавить comparisons/search/documents endpoints и common errors.
3. Ограничить POC routes loopback и отключить при APP_ENV=production.
4. Сгенерировать OpenAPI types для минимального UI, не создавать полную auth/history раньше POC.

Ошибки: DB/storage unavailable503; source lack →AnswerEnvelope insufficient; Fake timeout→fallback; question>4000 rejected.

Проверки: API contract happy/unknown/conflict/fallback; production POC route absent; snapshot facts not mixed revisions.

Критерий: Один реальный question→источники сценарий проходит с Fake без network API.

## UI-001 — Минимальный экран POC: вопрос, таблица, оригинал

Reasoning: **High**. [Полное ТЗ](../tasks/UI-001.md).

Контракт: POC AnswerEnvelope/OpenAPI generated types; без полноценного кабинета.

1. Сделать один экран question input с явными bank/region/date filters.
2. Показать typed table statuses/conditions и citations для каждой стороны.
3. Добавить loading/error/fallback/empty states и full-source action.
4. Маркировать Fake и дату данных; не добавлять dashboard/admin до G2.

Ошибки: Network error сохраняет введённый текст; unknown cell не blank price; no source не clickable invented link.

Проверки: Component tests statuses; browser question→comparison→archived PDF; keyboard labels.

Критерий: POC пользователь видит таблицу и открывает полный доказательный документ; real API не требуется.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-08.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
