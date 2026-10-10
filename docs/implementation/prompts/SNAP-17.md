# SNAP-17 — Next.js закрытый интерфейс ассистента

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **medium**; выбор модели свободный.

## Цель и ожидаемый результат

Login/invite, выбор snapshot/scenario, вопрос/сравнение/источники, admin review; рабочий end-to-end browser flow.

## Условия начала

Merged зависимости: SNAP-16. Пока зависимость не завершена, допустим только явно
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

- `frontend/app/**`
- `frontend/components/**`
- `frontend/lib/client.ts`
- `frontend/next.config.ts`
- `frontend/tests/**`
- `frontend/package.json`
- `frontend/package-lock.json`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-17.md`.

## Реализация и ограничения

Используй существующий Next.js scaffold и API contracts, same-origin proxy, HttpOnly cookie без provider key/token localStorage. Экран показывает corpus revision/date/missing banks/synthetic/fallback/unknown/individual/conflict. Source citation открывает protected attachment, snippets escaped. Scenario forms payer/region/segment/amount, не запрашивают payroll personal data. Минимальный admin candidates/review/freeze; no monitoring/dashboard уведомлений. Память диалога только текущий UI, logout очищает её. Добавь Playwright как dev dependency только для meaningful E2E.

## Тесты и критерии приёмки

Lint/tsc/build; browser login -> choose synthetic snapshot -> compare -> inspect citation -> logout; invited analyst cannot admin; fallback/429/missing-input/unknown/conflict states и malicious snippet XSS. Tests без bank/Groq network; API integration реальная, не только screenshot mocks.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Frontend owner, backend read-only. Можно предварительно оформить компоненты на frozen TS DTO после SNAP-16, full acceptance ждёт API. Не менять api-contracts.ts без согласования SNAP-16.

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
