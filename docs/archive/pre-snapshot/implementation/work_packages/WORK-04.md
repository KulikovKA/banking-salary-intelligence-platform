# WORK-04 — HTML/PDF, структура документов и версии

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **High**. Status: **TODO**.

Почему этот уровень: Страницы, сноски, canonical hashes и история извлечения должны оставаться согласованными.



[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-04.md).

Dependencies: Offline checkpoint dependencies: WORK-02 and WORK-03 offline checkpoints.
Offline checkpoint gate: G0-OFFLINE. Full acceptance retains original AC and applicable live/G1/G2 requirements.

## Execution mode under ADR-006

**Mode:** offline checkpoint under G0-OFFLINE; all live work requires exact source G0-LIVE and original acceptance gates.

Offline work uses local data or explicitly synthetic fixtures only. External ingestion requests are forbidden, including redirects, subresources, parser workers, and browser renderers. Synthetic provenance is isolated from real manifests and publication. A checkpoint marked DONE does not make this WORK DONE or satisfy G1/G2. Preserve every original acceptance criterion.




## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## HTML-001 — HTML extraction с сохранением значимого текста

Reasoning: **High**. [Полное ТЗ](../tasks/HTML-001.md).

Контракт: ParseResult{pages:[],sections,chunks,quality,canonical_hash}; original blob unchanged.

1. Извлечь title/headings/main/table rows/footnotes с BeautifulSoup/lxml.
2. Удалять только согласованные nav/cookie/ads selectors, сохранять отрицания/даты/числа.
3. Нормализовать whitespace и encoding с versioned config, сохранить raw vs canonical связь.
4. Dynamic rendered DOM пометить отдельным artifact; Playwright включать только на доказанном fixture кейсе.

Ошибки: Main selector отсутствует/резко упал text coverage →partial/review; нельзя признать empty text отменой условий.

Проверки: Fixtures: table+footnote, duplicate headings, cookie banner, changed negative word, malformed HTML, script injection.

Критерий: Оформление не меняет canonical meaning; значимая сноска и отрицание сохранены; HTML не имеет PDF page.

## PDF-001 — PDF extraction постранично и контроль качества

Reasoning: **High**. [Полное ТЗ](../tasks/PDF-001.md).

Контракт: DocumentParser.parse -> ParseResult physical_page1..N, printed_label?, quality_flags.

1. Проверить license decision PyMuPDF; при отсутствии использовать proposed pdfplumber и записать решение.
2. Запускать parser в isolated subprocess с quota120s/1GiB/1000pages.
3. Извлечь каждую физическую страницу и текст таблиц, не переставлять числа без связанного header.
4. Пометить image-only/garbled/missing-page и сложные сноски как needs_ocr/partial/review.

Ошибки: Encrypted/corrupt PDF →typed error; no OCR hallucination; zero pages invalid; одна плохая страница не публикуется как complete.

Проверки: Fixtures: печатная нумерация отличается, multi-page table, footnote, image-only, corrupt, encrypted, long PDF, quota timeout.

Критерий: Каждая извлечённая страница связана с оригиналом; нет выдуманных page labels; выбранная лицензия отражена.

## DB-002 — Миграции документов, страниц и chunks

Reasoning: **High**. [Полное ТЗ](../tasks/DB-002.md).

Контракт: documents/document_versions/extraction_runs/document_pages/document_chunks по DATABASE_DESIGN.

1. Создать document family и immutable version mappings.
2. Создать extraction uniqueness по parser/config и page/ordinal constraints.
3. Добавить indexes FK и search_vector поле без premature JSON GIN.
4. Протестировать RESTRICT связей и complete extraction pointer в application query.

Ошибки: Same URL new bytes не перезаписывает prior document version; failed extraction не виден как active.

Проверки: Migration against populated0001; duplicate ordinal; invalid page; referenced blob delete denied.

Критерий: Upgrade сохраняет catalog/blobs, family/version/extraction semantics разделены.

## TXT-001 — Chunking, сноски и точная привязка evidence

Reasoning: **High**. [Полное ТЗ](../tasks/TXT-001.md).

Контракт: Chunk{text,ordinal,physical_page?,section?,footnote_links}; Unicode offsets на immutable extraction.

1. Разбить по section/page target1200–2500chars/max4000.
2. Не терять table header и footnote связи; большие таблицы делить с явными shared refs.
3. Сохранить normalized text/hash и offset mapping, не создавать фиктивные PDF страницы HTML.
4. Commit extraction completeness и chunks атомарно, не активировать partial run.

Ошибки: Footnote relation неоднозначна →quality flag; oversized связанный фрагмент не отрезать молча.

Проверки: Cross-page table/header, numbered footnotes, Cyrillic Unicode offsets, repeated headings, partial write rollback.

Критерий: Quote offsets разрешаются в exact text; все pages accounted; неоднозначности видимы downstream.

## VER-001 — Разделение raw, canonical и parser версий

Reasoning: **High**. [Полное ТЗ](../tasks/VER-001.md).

Контракт: VersionDecision{raw_changed,canonical_changed,reprocess_required,reason}; DATA_FLOW.

1. Создавать source_version только для новых bytes, сохранять fetch observations при равенстве.
2. Считать canonical hash только после полного parse с config version.
3. При новой parser/config выполнять reprocess даже unchanged raw.
4. Отделить document identity mapping от latest URL, сохранять старые extraction IDs.

Ошибки: Новый PDF по старому URL сохраняется; одинаковые bytes по другому URL сохраняют provenance; failed parse не обновляет last_successful_parse.

Проверки: Same bytes, metadata-only changed PDF, changed fee, parser upgrade, source URL relocation, reprocess retry.

Критерий: Все три причины изменения различимы; старые ответы смогут открыть прежний extraction.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-04.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
