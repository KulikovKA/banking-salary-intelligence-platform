# SNAP-14 — Evidence-first ассистент и renderer

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Question -> structured intent -> retrieval/comparison -> validated claims -> AnswerEnvelope, fallback без hallucination.

## Условия начала

Merged зависимости: SNAP-10, SNAP-11, SNAP-13. Пока зависимость не завершена, допустим только явно
отдельный scaffold/harness; окончательная приёмка ждёт merged implementation.

Прочитай AGENTS.md, docs/architecture/OVERVIEW.md, DOMAIN_CONTRACTS.md,
DATABASE_DESIGN.md, API_CONTRACTS.md, SECURITY.md и docs/product/ACCEPTANCE_CRITERIA.md.
Проверь актуальный код и отчёты зависимостей: DONE в плане без merged результата
не считается условием начала. Исполни только эту задачу до reviewable результата.
Работай offline с synthetic fixtures, если конкретный real/provider run не допущен.
Не создавай фиктивные разрешения, тарифы, reviewer или PASS. Не запускай scheduler,
recurring download, notifications, очереди, микросервисы или автоматический paid fallback.
Сохрани FetchGateway, LocalBlobStore, operator source recovery, E2E и миграции 0001/0002/0003.

## Файлы и ответственность

- `backend/app/assistant/service.py`
- `backend/app/assistant/render.py`
- `backend/app/assistant/privacy.py`
- `backend/tests/test_assistant_answers.py`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-14.md`.

## Реализация и ограничения

Сначала validate snapshot/read access; bounded question/scenario, minimization/redaction, unclear sensitive free text -> local clarification. Intent не может запускать URLs/SQL/tools. Claims создаются backend; explain допускает только order/template IDs. Backend рендерит цифры/date/links/limitations; никаких непроверенных LLM statements. Не обрезать footnotes ради budget — исключать неполный claim. Deadline propagation, provider error deterministic fallback. Stateless v1; не добавлять chat persistence/agents.

## Тесты и критерии приёмки

Direct fee question, scenario comparison, missing scenario, documents lookup, outside scope; tampered numeric output/real URL wrong claim/injected footnote -> reject; no evidence -> insufficient; 429 -> fallback с теми же доказательствами. Canary PII не попадает в mock outgoing payload. Corpus/model/status видны в ответе.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Assistant-only modules; API/UI интеграторы ждут stable envelope. Не менять engine/provider/contracts самостоятельно.

Используй отдельную ветку/worktree при реальном параллельном запуске. Не spawn
других агентов без отдельного поручения. Общие lockfiles/миграции/main.py интегрируй
последовательно. Не коммить другой worktree или чужие незавершённые изменения.

## Завершение и передача

Сохрани report: итоговое поведение, изменённые файлы, проверки с числами и
PASS/FAIL/NOT RUN, evidence для каждого AC, ограничения, следующий шаг.
В report укажи base commit; commit результата добавить после commit если доступен.
Не обновляй MASTER_PLAN/TASKS.json параллельно: передай интегратору итоговый статус.
Интегратор обновляет только status задачи (DONE при всех её AC, иначе IN_PROGRESS
или BLOCKED с причиной), сохраняет порядок/зависимости и запускает docs validator.
Если задача уже выполнена, проверь AC и закрой только оставшиеся пробелы, без
переписывания работающего кода. Product gates считаются отдельно от DONE модуля.
