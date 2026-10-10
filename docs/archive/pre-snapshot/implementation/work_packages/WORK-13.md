# WORK-13 — Полный пользовательский и административный интерфейс

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **Medium**. Status: **TODO**.

Почему этот уровень: UI по готовым API и состояниям; сложные asynchronous/review участки отдельно High.

Dependencies: [WORK-07](WORK-07.md), [WORK-08](WORK-08.md), [WORK-11](WORK-11.md), [WORK-12](WORK-12.md)

Gates входящих этапов: G2. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-13.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## UI-002 — Каркас кабинета, вход и навигация по ролям

Reasoning: **Medium**. [Полное ТЗ](../tasks/UI-002.md).

Контракт: Session /auth/me/login/logout + CSRF; 8 разделов USER_SCENARIOS.

1. Сделать login/invite/reset формы с generic auth errors.
2. Добавить authenticated layout/nav и роли User/Analyst/Admin.
3. Централизовать API client credentials/CSRF/401/403/429 handling и request IDs.
4. Сделать loading/error boundary и accessibility labels, не хранить session token localStorage.

Ошибки: Expired session redirect login с сохранением безопасного return path; open redirect reject.

Проверки: Login/logout/invite expired, role nav, CSRF mutation, keyboard focus,401 during page.

Критерий: Закрытый кабинет доступен только после auth; navigation не заменяет backend authorization.

## UI-003 — Чат MVP, история и context controls

Reasoning: **High**. [Полное ТЗ](../tasks/UI-003.md).

Контракт: 202 run polling, AnswerEnvelope, chat CRUD, context version.

1. Перенести POC evidence/table components в authenticated assistant.
2. Добавить session list/history/delete, context chips и clarification UX.
3. Generate idempotency key на submit, reuse при reconnect, poll с backoff.
4. Показать queued/running/fallback/partial/stale, не streaming unvalidated claims.

Ошибки: 409 сохранить question и обновить context;429 retry; offline сохранить input только в памяти страницы; deleted run не resurrect.

Проверки: Double click/reconnect, U02 pronoun, reload history, delete active run, sources remain immutable.

Критерий: Один submit соответствует одному run; вся собственная история и ограничения читаемы.

## UI-004 — Сравнения и каталог оригинальных документов

Reasoning: **Medium**. [Полное ТЗ](../tasks/UI-004.md).

Контракт: ComparisonRequest/Result, SourceCard, content endpoint Range/fragment.

1. Фильтры scenario/banks/metrics/as_of с обязательными inputs.
2. Таблица4 банков с units/payer/conditions и explicit statuses.
3. Document catalog/version selector и полный original; безопасное открытие official URL.
4. Не суммировать partial cost в UI, рендерить backend claims и freshness.

Ошибки: Unknown/individual/conflict различимы; PDF browser без fragment fallback показывает page label; HTML скачать safely.

Проверки: Four-column responsive table, page mismatch absent, old version open, missing fields clarification, keyboard table.

Критерий: Каждый существенный результат связан с правильным источником; UI не пересчитывает тарифы.

## UI-005 — Dashboard, лента изменений и настройки подписок

Reasoning: **Medium**. [Полное ТЗ](../tasks/UI-005.md).

Контракт: DashboardSummary, ChangeEvent, Subscription/Notification DTO.

1. Показать coverage/freshness по4 банкам и pending data states.
2. Развести detected/effective dates и announced/activated/correction labels.
3. Добавить фильтры feed, read/unread и subscription controls.
4. Сделать empty states без утверждения «банк не менял тарифы» при unavailable monitoring.

Ошибки: Monitoring gap показывается; duplicate notification не отображается twice; failed save settings rollback UI.

Проверки: No events vs unavailable source, future event, notification read, filter pagination, subscribe/unsubscribe.

Критерий: Лента не смешивает технические и подтверждённые тарифные изменения; настройки персональны.

## UI-006 — Панели аналитика и администратора

Reasoning: **High**. [Полное ТЗ](../tasks/UI-006.md).

Контракт: ReviewRequest/queue, source health/jobs, invites/users roles.

1. Review карточка: old/new value, scope/dates, raw quote/page/footnote и original.
2. Approve/reject/needs_changes с reason и expected version; corrections новый candidate.
3. Admin users/invites/role change и sources/policy/recheck/diagnostics.
4. Не показывать секреты и чужие chats, не добавлять silent auto-approval.

Ошибки: 409 review refresh сохранив reason; missing evidence disables approve с причиной; last admin error читаем.

Проверки: Analyst vs admin permissions, concurrent reviewer, rejected candidate not published, source blocked display.

Критерий: Ручная проверка выполнима по оригиналу; admin не получает лишние данные.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-13.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
