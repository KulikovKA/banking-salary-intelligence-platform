# TASK PROMPT FOR GPT-6 LUNA (REASONING): SRCH-001

> Объединено в [WORK-07 — Полнотекстовый поиск и детерминированные сравнения](../work_packages/WORK-07.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **Extra High** (`xhigh`).

## Контекст проекта

Ты работаешь в Banking Salary Intelligence Platform: FastAPI/Python, PostgreSQL, Next.js/TypeScript, модульный монолит, 4 банка, RU-KDA, около30 пользователей. Реализация разрешается отдельной командой пользователя; сам факт существования этого prompt не разрешает запуск. Для этой задачи исполнитель по плану: **GPT-6 Luna — Reasoning**. Если это независимый review Astra, передай задание ей, не объявляй self-review Luna независимым.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/tasks/SRCH-001.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `DATA_FLOW.md`, `SECURITY.md` в том же architecture каталоге и `docs/quality/TEST_STRATEGY.md`. Прочитай обнаруженный AGENTS.md. Центральные файлы — обязательные контракты, не справочная рекомендация.

## Задача

**SRCH-001: PostgreSQL FTS с фильтрами и оценкой поиска**. Phase A2, Epic Поиск, priority High, complexity M.
Предпосылки: TXT-001, FACT-004; gate **G0**. Проверь их реализацию и отчёты; не предполагай готовность по названию папки. На момент исходного проектирования приложение отсутствовало.

## Область изменений

backend/app/search/service.py; backend/app/search/synonyms.py; backend/alembic/versions/. Также относящиеся tests/fixtures и `docs/reports/SRCH-001.md`. Не делай рефакторинг несвязанных модулей.

## Ограничения

Сохраняй immutable originals и evidence; Decimal без float; unknown≠0; current≠latest fetched; private history owner-only. LLM не считает тарифы и не генерирует URLs/pages/dates. Provider не выбран, Fake используется до отдельного решения. Не добавляй vector DB, Kafka, Kubernetes, agent framework. Нельзя обходить защиту банков или отправлять сообщения/email. При изменении центрального контракта подготовь ADR и укажи affected tasks.

## Реализация

Контракт: SearchQuery{q,banks,as_of,scope,limit}; SearchResult{chunks,coverage}; snippets не authoritative facts.

1. **SRCH-001.01** — Построить russian tsvector с title/section weights и GIN.
2. **SRCH-001.02** — Использовать parameterized websearch_to_tsquery, bounded query/limit; bank/date/visibility filters до выдачи.
3. **SRCH-001.03** — Добавить explicit aliases и salary synonyms, вернуть chunk/evidence IDs и physical_page.
4. **SRCH-001.04** — Измерить Recall@10 на gold queries и EXPLAIN; не добавлять pgvector без trigger.

Ошибки и границы: Stopwords/empty query →clarify; unsupported bank reject; stale chunks явно отмечены; ts_headline output escape.

## Тестирование

Russian inflections, bank aliases, numeric criterion, longPDF, no result, HTML injection, per-bank Recall@10.

Проверь реальные результаты, зафиксируй команды и versions/fixtures; не выдавай непроведённую проверку за pass. Live API без согласованного provider/policy не вызывай.

## Acceptance Criteria

Результаты открывают правильную версию; SQL injection невозможен через query string; metrics report сохранён. Выполни также общий DoD из ТЗ задачи. Если предпосылка отсутствует, укажи конкретный blocker; выполняй только независимую разрешённую часть, не симулируй production dependency.

## Отчёт

Верни список файлов, реализованное поведение, команды и результаты проверок, доказательства каждого AC, limitations и неустранённые проблемы. Сохрани `docs/reports/SRCH-001.md`. Обнови статус в MASTER_PLAN и TASK_INDEX; DONE только после AC. При возможности отдельный commit в project-local Git, без родительских изменений. Не начинай следующую задачу без проверки её gate и scope текущего поручения.
