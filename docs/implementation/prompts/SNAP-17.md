# SNAP-17 — Интеграция и адаптация внешнего frontend

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **medium**; выбор модели свободный.

## Цель и ожидаемый результат

Принятый и адаптированный внешний frontend в Next.js, подключённый к FastAPI; FE-01–FE-04 закрыты с evidence и рабочими browser flows login/invite, snapshot/scenario, поиск/сравнение/ассистент/источники и admin review.

## Условия начала

Merged зависимости: SNAP-16. Дополнительный обязательный вход: проверяемая передача
внешнего репозитория/исходников с exact revision, зависимостями и лицензиями по
[FRONTEND_HANDOFF](../FRONTEND_HANDOFF.md). Передача пока не подтверждена.
До получения исходников и merged backend/API не начинать FE-01–FE-04, перенос,
переписывание UI или отдельный scaffold. Зафиксируй blocker и продолжай только
независимую backend-задачу по отдельному поручению. Внешний разработчик может
создавать свой frontend параллельно; эта задача не создаёт второй интерфейс.

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
- `frontend/public/**`
- `frontend/styles/**`
- `frontend/lib/client.ts`
- `frontend/next.config.ts`
- `frontend/tsconfig.json`
- `frontend/eslint.config.mjs`
- `frontend/tests/**`
- `frontend/package.json`
- `frontend/package-lock.json`

Владелец переноса — наша команда интеграции frontend; визуальное решение и
исходные компоненты передаёт внешний frontend-разработчик. Backend и
`frontend/lib/api-contracts.ts` read-only, владелец публичного API/TS DTO — SNAP-16.
Расширение owned paths после FE-01 согласуется с интегратором до редактирования.
Статусы FE и ссылки на evidence в FRONTEND_HANDOFF обновляет интегратор
последовательно после принятого отчёта; исполнитель передаёт результаты FE-01–FE-04.

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-17.md`.

## Реализация и ограничения

Выполни FE-01–FE-04 по FRONTEND_HANDOFF: проверь переданный exact revision, зависимости/лицензии/качество/безопасность и матрицу экран -> API; перенеси предоставленный код в существующую Next.js архитектуру с сохранением согласованного дизайна/компонентов и минимальным переписыванием. Удали временные клиентские расчёты тарифов, approvals и небезопасные решения. Замени product mocks типизированными FastAPI вызовами frozen TS DTO SNAP-16: auth, snapshots, search, comparison, documents, assistant, admin review/freeze. Same-origin proxy, server sessions/HttpOnly cookie, корректный Origin/CSRF; без auth token localStorage, Groq key только на backend. Покажи revision/date/coverage/missing banks/synthetic/evidence/unknown/conflict/individual/conditions/scope/fallback и typed errors 429/503. Protected originals, escaped snippets, scenario без payroll personal data. Память диалога только текущий UI, logout очищает её. Недостающие сценарии возвращай внешнему разработчику как конкретные follow-up; public API/DTO changes только через владельца SNAP-16. Второй UI с нуля и monitoring/notifications не создавать. Playwright dev dependency только для meaningful E2E.

## Тесты и критерии приёмки

FE-01–FE-04 имеют принятые отчёты с exact revision и evidence каждого AC; lint/typecheck/build green. Browser E2E на реальном FastAPI + dedicated PostgreSQL с migrations + frozen synthetic corpus + Fake: invite/login/logout, выбор snapshot/scenario, поиск, сравнение, вопросы ассистенту, открытие protected originals и admin review/freeze. Проверены RBAC/CSRF/XSS, истечение сессии, fallback/429/503/missing-input/unknown/conflict/individual и очистка диалога при logout. Bank/Groq network = 0; API integration реальная, не только mocks. Нет client secrets/тарифных расчётов/approvals; отчёт готовности фиксирует limitations и NOT RUN, synthetic не считается S1/S2/S3 PASS.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Внешний разработчик создаёт UI параллельно Backend + AI в своём репозитории; наша команда не создаёт второй frontend. SNAP-17 начинает FE-01–FE-04 только после передачи исходников и merged SNAP-16, единолично владеет переносом frontend tree/package-lock. Новые внешние revisions принимать последовательно без перезаписи соседних изменений. Backend и api-contracts.ts read-only; API/DTO follow-up владельцу SNAP-16, FE-статусы интегратору. SNAP-18 может идти параллельно на disjoint paths.

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
