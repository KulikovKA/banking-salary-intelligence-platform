# SNAP-19 — Сквозная приёмка и минимальная эксплуатация

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Воспроизводимый запуск/restore и окончательный S0–S3 readiness verdict на exact commit/corpus.

## Условия начала

Merged зависимости: SNAP-17, SNAP-18. Пока зависимость не завершена, допустим только явно
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

- `docs/OPERATIONS.md`
- `docs/reports/SNAP-19-release.md`
- `tools/verify_snapshot_restore.py`
- `.github/workflows/ci.yml`
- `compose.yaml`
- `README.md`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-19.md`.

## Реализация и ограничения

Собери уже готовые компоненты, не расширяй архитектуру. CI offline synthetic pipeline/auth/UI/PG/E2E/docs; real-model evaluation opt-in отдельно. PG dump+blob hash manifest restore только в новую dedicated DB/root; hashes/evidence pointers/auth доступ проверены перед открытием. 3 concurrent users и quotas/fallback, search/comparison p95/question deadline. Production env/cookie/ingress instructions, no fake identity. Final report перечисляет actual gates, limitations и конкретные blockers; ни G1/G2, ни S3 не помечать PASS без evidence. Обнови README о фактическом runnable продукте только если достигнут.

## Тесты и критерии приёмки

Все существующие и новые required checks, restore 100% linkage, explicit secret/log/XSS/access tests green, browser real-product smoke при данных/ключе. Partial technical PASS и real NO-GO разделены. Не удалять snapshots/данные тестов, не выполнять destructive downgrade.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Финальный integrator после всех merges, единственный владелец CI/compose/README на этом этапе. Общие файлы больше не правятся параллельно.

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
