# SNAP-16 / SNAP-17 — закрытие merged задач

Дата: 12.10.2026 (Europe/Moscow).
Проверенный main: `155c3bde04e1d433b511d812c57669474c8ed2ce`.

SNAP-16 и SNAP-17 закрыты как **DONE по явному поручению пользователя после
merge и проверки CI**. Это решение о закрытии модулей по текущему chat-only scope;
новый независимый аудит или повторный прогон runtime tests не заявляется.
Оставленные pending статусы в исторических [SNAP-16](SNAP-16.md) и
[SNAP-17](SNAP-17.md) superseded этой записью.

- SNAP-16 API: [PR #28](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/28),
  implementation `d538928177620dc99c9d9e115b459fd411970e37`.
- Отдельное согласование chat-only scope: [PR #29](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/29).
- SNAP-17 integration: implementation `de2fe9496f1dcd2b6022e8dd18067751dbae9e0c`,
  report `9c3585ed665592205bf9de35b82655cdf26251c1`.
  [PR #30](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/30)
  сначала merged в scope-ветку; [PR #31](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/31)
  перенёс эту реализацию в main.

Git ancestry подтверждает обе реализации в main; полное дерево main совпадает
с проверенным деревом `9c3585e`. Основной frontend использует BackendChat;
DemoChatTransport остаётся только для явного development opt-in. Backend/frozen
DTO не изменялись при frontend-интеграции.

## Проверенная техническая база

[Post-merge CI main](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38301764578)
на `155c3bd` завершён **PASS**, backend и frontend successful:

- Backend/TLS regression: **565 passed, 0 skipped, 0 failed**, 194.25s.
- Ruff, mypy, Alembic upgrade/check, docs validator: PASS.
- Frontend lint/typecheck/build: PASS.
- Existing source-recovery E2E: PASS_SYNTHETIC_ONLY, network_requests = 0.

На идентичном дереве кода зафиксированы локальные результаты SNAP-17:
**23 frontend tests passed** и **8 real browser E2E passed**, без skips/failures.
Browser цепочка: Next -> same-origin proxy -> реальный FastAPI -> migrated
dedicated PostgreSQL -> original-backed frozen synthetic corpus -> Fake.
Проверены login/invite/logout/expiry/Origin/CSRF, явный snapshot, вопрос/таблица/
protected original hash, insufficient/fallback/empty/429/503, XSS и client abort.
Adapter/client cases проверяют все status/value unions и остальные typed errors.
10 client bundles: 0 server-only canary leaks; bank/Groq calls = 0.
Windows backend regression: 564 passed, 1 Linux-specific /proc skip;
Linux CI выше выполнил этот тест без skip.

Исторические FE-01–FE-04 внешнего frontend не объявляются выполненными. Закрыт
пользовательский scope собственного desktop AI-chat по CHAT-01–CHAT-04, отдельное
scope-согласование merged через #29. Кабинет/dashboard/admin review UI/mobile
и новая frontend-реализация не добавлены.

## Сохранённые ограничения

Из отчётов сохраняются финансовые/контрактные ограничения Comparison Engine,
синхронный JSON вместо SSE, отсутствие гарантированной backend cancellation,
single-instance quotas и общая upstream IP window у proxy. Реальный corpus,
provider processing/reuse admissions и real Groq evaluation не выполнены.

Production npm audit: 0 vulnerabilities. **4 High dev audit entries** в существующей
цепочке braces/micromatch/fast-glob/@next/eslint-plugin-next остаются открытым
follow-up владельцу зависимостей/интегратору; закрытие задачи не является их fix.
Включение browser harness в release CI и финальный restore/load readiness — SNAP-19.

TASKS/MASTER_PLAN обновлены одним integrator commit: 17 DONE, SNAP-18/19 TODO.
Runtime/контракты/DB/lockfiles не менялись. Тяжёлые проверки не повторены для
изменения документации; docs validator и diff whitespace проверяются отдельно.

**S1 BLOCKED; S2/S3 NOT EVALUATED; G1/G2 NOT PASSED**. Полный S0 и release readiness
по-прежнему оцениваются отдельно; module DONE не является product gate PASS.
