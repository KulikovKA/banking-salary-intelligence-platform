# TASK PROMPT FOR GPT-6 LUNA (REASONING): FACT-002

> Объединено в [WORK-06 — Тарифные факты, проверка и публикация](../work_packages/WORK-06.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **Extra High** (`xhigh`).


## ADR-006 execution mode

**Mode:** `offline` under G0-OFFLINE for local/synthetic work, with no external ingestion egress; live/acceptance requires source-specific G0-LIVE and original gates.

A completed offline checkpoint is evidence for that checkpoint only; it does not complete the WORK block or accept G1/G2. Synthetic evidence cannot be published as real bank facts.

Offline mode follows TASK_INDEX.offline_deps; the card's full deps remain for live/acceptance and do not block the synthetic checkpoint. Do not claim its original live acceptance criteria passed.

## Контекст проекта

Ты работаешь в Banking Salary Intelligence Platform: FastAPI/Python, PostgreSQL, Next.js/TypeScript, модульный монолит, 4 банка, RU-KDA, около30 пользователей. Реализация разрешается отдельной командой пользователя; сам факт существования этого prompt не разрешает запуск. Для этой задачи исполнитель по плану: **GPT-6 Luna — Reasoning**. Если это независимый review Astra, передай задание ей, не объявляй self-review Luna независимым.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/tasks/FACT-002.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `DATA_FLOW.md`, `SECURITY.md` в том же architecture каталоге и `docs/quality/TEST_STRATEGY.md`. Прочитай обнаруженный AGENTS.md. Центральные файлы — обязательные контракты, не справочная рекомендация.

## Задача

**FACT-002: Извлечение кандидатов по правилам и provenance**. Phase A2, Epic Факты, priority Critical, complexity L.
Gate prerequisites: **G0-OFFLINE for checkpoint; live acceptance requires source-specific G0-LIVE and original gates**. Verify dependencies and evidence; a TODO record is not proof of completion.

## Область изменений

backend/app/facts/extract.py; backend/app/ingestion/adapters/; tests/gold/facts.jsonl. Также относящиеся tests/fixtures и `docs/reports/FACT-002.md`. Не делай рефакторинг несвязанных модулей.

## Ограничения

Сохраняй immutable originals и evidence; Decimal без float; unknown≠0; current≠latest fetched; private history owner-only. LLM не считает тарифы и не генерирует URLs/pages/dates. Provider не выбран, Fake используется до отдельного решения. Не добавляй vector DB, Kafka, Kubernetes, agent framework. Нельзя обходить защиту банков или отправлять сообщения/email. При изменении центрального контракта подготовь ADR и укажи affected tasks.

## Реализация

Контракт: Adapter.extract(ParseResult,ProductScope)->FactCandidate[] с evidence roles value/unit/condition/date/scope.

1. **FACT-002.01** — На размеченных банковских fixtures задать versioned extraction rules для ключевых metrics.
2. **FACT-002.02** — Связать значение с header/basis/footnotes, допустить несколько evidence refs.
3. **FACT-002.03** — Сохранять confidence только diagnostic, flags и raw quote; не публиковать автоматически.
4. **FACT-002.04** — Dedup кандидаты по extraction/payload hash; сохранять unsupported rows для review.

Ошибки и границы: Оборванная сноска/две возможные единицы/неизвестный package →pending_review; no LLM requirement.

## Тестирование

≥80 gold facts; precision value+unit+basis, condition recall; tests intentionally missing headers и mixed packages.

Проверь реальные результаты, зафиксируй команды и versions/fixtures; не выдавай непроведённую проверку за pass. Live API без согласованного provider/policy не вызывай.

## Acceptance Criteria

Каждый candidate объясним quote+rule version; missing fields не выдуманы; gold metrics рассчитаны. Выполни также общий DoD из ТЗ задачи. Если предпосылка отсутствует, укажи конкретный blocker; выполняй только независимую разрешённую часть, не симулируй production dependency.

## Отчёт

Верни список файлов, реализованное поведение, команды и результаты проверок, доказательства каждого AC, limitations и неустранённые проблемы. Сохрани `docs/reports/FACT-002.md`. Обнови статус в MASTER_PLAN и TASK_INDEX; DONE только после AC. При возможности отдельный commit в project-local Git, без родительских изменений. Не начинай следующую задачу без проверки её gate и scope текущего поручения.
