# TASK PROMPT FOR GPT-6 LUNA (REASONING): FACT-004

> Объединено в [WORK-06 — Тарифные факты, проверка и публикация](../work_packages/WORK-06.md). Это внутренний этап общего задания, не отдельный запуск. Исполнитель: GPT-6 Luna. Reasoning: **Extra High** (`xhigh`).

## Контекст проекта

Ты работаешь в Banking Salary Intelligence Platform: FastAPI/Python, PostgreSQL, Next.js/TypeScript, модульный монолит, 4 банка, RU-KDA, около30 пользователей. Реализация разрешается отдельной командой пользователя; сам факт существования этого prompt не разрешает запуск. Для этой задачи исполнитель по плану: **GPT-6 Luna — Reasoning**. Если это независимый review Astra, передай задание ей, не объявляй self-review Luna независимым.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/tasks/FACT-004.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `DATA_FLOW.md`, `SECURITY.md` в том же architecture каталоге и `docs/quality/TEST_STRATEGY.md`. Прочитай обнаруженный AGENTS.md. Центральные файлы — обязательные контракты, не справочная рекомендация.

## Задача

**FACT-004: Атомарная публикация и выбор действующих фактов**. Phase A2, Epic Факты, priority Critical, complexity L.
Предпосылки: FACT-003, VER-001; gate **G0**. Проверь их реализацию и отчёты; не предполагай готовность по названию папки. На момент исходного проектирования приложение отсутствовало.

## Область изменений

backend/app/facts/publication.py; backend/app/facts/repository.py. Также относящиеся tests/fixtures и `docs/reports/FACT-004.md`. Не делай рефакторинг несвязанных модулей.

## Ограничения

Сохраняй immutable originals и evidence; Decimal без float; unknown≠0; current≠latest fetched; private history owner-only. LLM не считает тарифы и не генерирует URLs/pages/dates. Provider не выбран, Fake используется до отдельного решения. Не добавляй vector DB, Kafka, Kubernetes, agent framework. Нельзя обходить защиту банков или отправлять сообщения/email. При изменении центрального контракта подготовь ADR и укажи affected tasks.

## Реализация

Контракт: PublicationReceipt{revision,fact_ids}; select(Scenario,as_of,knowledge_cutoff)->FactSet.

1. **FACT-004.01** — Под lock corpus_state проверить approved facts/originals и создать publication members/revision одной транзакцией.
2. **FACT-004.02** — Вести scoped supersession/revocation с evidence, не is_current flag.
3. **FACT-004.03** — Реализовать selection valid interval/knowledge cutoff/region/contract и conflict/unknown/freshness.
4. **FACT-004.04** — Предоставить publication callback/interface для будущего change event без внешнего network side effect.

Ошибки и границы: Параллельная публикация →retry/409; future fact не активен раньше даты; partial document не отменяет все old facts.

## Тестирование

Future/retroactive/unknown dates, federal+regional without override, partial replacement, two commits race, rollback evidence missing.

Проверь реальные результаты, зафиксируй команды и versions/fixtures; не выдавай непроведённую проверку за pass. Live API без согласованного provider/policy не вызывай.

## Acceptance Criteria

Snapshot selection воспроизводим; old versions доступны; conflicted/stale данные не становятся безусловным winner. Выполни также общий DoD из ТЗ задачи. Если предпосылка отсутствует, укажи конкретный blocker; выполняй только независимую разрешённую часть, не симулируй production dependency.

## Отчёт

Верни список файлов, реализованное поведение, команды и результаты проверок, доказательства каждого AC, limitations и неустранённые проблемы. Сохрани `docs/reports/FACT-004.md`. Обнови статус в MASTER_PLAN и TASK_INDEX; DONE только после AC. При возможности отдельный commit в project-local Git, без родительских изменений. Не начинай следующую задачу без проверки её gate и scope текущего поручения.
