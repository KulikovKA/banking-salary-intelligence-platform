# Независимый финальный аудит

Этот аудит запланирован, но не выполнен: приложения пока нет. Исполнитель будущего независимого аудита — Astra, отдельно от Luna, реализовавшей код. Не присваивать READY на основании наличия документации.

- [ ] Зафиксированы commit, image digests, schema revision, corpus snapshot и согласованные ADR.
- [ ] Границы монолита соблюдены, нет скрытых прямых обращений UI к DB/LLM/storage.
- [ ] Все 4 adapters проверены на real frozen documents и разрешённых live probes.
- [ ] Официальность доменов подтверждена, нет сторонних зеркал, source policies действуют.
- [ ] Immutable archive проверен по SHA-256; публикация без blob невозможна.
- [ ] Физическая страница PDF и печатная метка не перепутаны; HTML без выдуманных страниц.
- [ ] DB constraints, FK, migrations, indexes и query plans проверены; нет destructive upgrade.
- [ ] Dates: fetched/published/effective/recorded не смешиваются; future/retroactive/unknown cases green.
- [ ] Regional/federal override обоснован; individual/unknown не равны нулю.
- [ ] Comparison нейтрален к названиям банков, Decimal и rounding корректны, обе стороны доказаны.
- [ ] Partial extraction не отменяет тариф; parser correction отличается от bank change.
- [ ] Review/publish atomic, retries/fencing/idempotency не создают дублей.
- [ ] Sources/claims validation проверяет смысл, а не только существующий URL.
- [ ] LLM provider заменяем, secrets вне frontend, budgets атомарны, fallback работает.
- [ ] Prompt injection не вызывает запись, arbitrary SQL/fetch или выдачу секретов.
- [ ] SSRF/rebinding/redirect/HTML XSS и parser limits проверены.
- [ ] Invite/reset/session/CSRF/rate limits и last-admin защита работают.
- [ ] Каждая роль/endpoint и cross-user read/write/list/poll/delete/file проверены.
- [ ] Context не возвращает устаревшие цифры; historical questions явно маркированы.
- [ ] Delete chat/retention/restore tombstones не возвращают удалённую историю.
- [ ] UI показывает loading/offline/stale/partial/conflict/fallback; unknown cells не нулевые.
- [ ] Subscriptions/notification dedup, future activated event и baseline suppression работают.
- [ ] Logs не содержат payloads/secrets/ПД; token/cost отчёты честно отмечают estimate.
- [ ] 30-session load измерен, queues bounded, ingest не блокирует чат.
- [ ] Compose воспроизводим, API private, health/readiness точны, backup восстановлен и проверен.
- [ ] Правовые и лицензионные вопросы активных потоков закрыты ответственными.
- [ ] Quality reports содержат counts/fixture hashes, holdout независим, нет скрытых skipped blockers.
- [ ] Документация запуска/восстановления и известные ограничения соответствуют release.

Finding template: `ID | severity Critical/High/Medium/Low | symptom | root cause | affected files:lines | impact | minimal reproduction | fix | verification | owner | status`. Critical: утечка/потеря данных/неавторизованная публикация; High: неверные подтверждённые тарифы, broken evidence, обход auth; Medium: ограничение с безопасной деградацией; Low: локальное удобство.

Цикл: REV-001 report → REV-002 Luna fixes с отдельными regression cases → REV-003 Astra retest. `READY FOR MVP` — все обязательные gates и активные возможности проверены; `READY WITH LIMITATIONS` — только явно принятые пользователем некритичные ограничения (например Fake LLM), без Critical/High; `NOT READY` — оставшиеся blockers или отсутствующие доказательства. Если fixes не нужны, REV-002 оформляет no-op с причиной, не изобретает изменения.
