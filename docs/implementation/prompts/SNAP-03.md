# SNAP-03 — Операторский corpus manifest и freeze service

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Ручное формирование draft/frozen corpus из exact accepted versions; реестр coverage/blockers четырёх банков, без выдуманных approval.

## Условия начала

Merged зависимости: SNAP-02. Пока зависимость не завершена, допустим только явно
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

- `backend/app/corpus/service.py`
- `backend/app/corpus/cli.py`
- `manifests/snapshot.schema.json`
- `manifests/snapshot.example.json`
- `backend/tests/test_snapshot_corpus.py`
- `docs/reports/SNAP-03-source-status.md`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-03.md`.

## Реализация и ограничения

Переиспользуй IngestionService/FetchGateway/BlobStore. Manifest хранит references к реальным решениям, hashes, exact source/version/method/scope/date и missing banks, но не secrets. Synthetic example отдельно от real manifest. CLI dry-run validation, add accepted version и freeze после approved published facts/extractions; service read проверяет exact snapshot membership и revocation без periodic freshness/stale. Freeze materialized membership только после готовности downstream records; ранние tests используют explicit fixtures. Для источников сначала прочти docs/research/SOURCE_STATUS.md и tests/fixtures/manifests/sources.json, не импортируй исследовательские bytes без отдельного допуска. Real acquisition остаётся blocked до записи ответственного.

## Тесты и критерии приёмки

Empty/mixed corpus/fictitious admission/missing original/wrong hash/quarantine rejected; legacy fetch/manual idempotency остаётся; membership deterministic manifest hash, freeze retry без duplicate; revoked rights block read. Real S1 пока NO-GO с перечнем missing basis, synthetic freeze не проходит real gate.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Отдельный corpus owner; параллельно SNAP-04..07/12/15. Не менять existing grants/manifest задним числом; human source review может идти независимо от разработки.

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
