# SNAP-18 — Реальный corpus gold и оценка S1/S2/Groq

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Human-reviewed frozen gold/tune/holdout, coverage matrix и measured acceptance report без fabricated PASS.

## Условия начала

Merged зависимости: SNAP-03, SNAP-09, SNAP-11, SNAP-14. Пока зависимость не завершена, допустим только явно
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

- `evaluation/**`
- `tools/evaluate_snapshot.py`
- `docs/reports/SNAP-18-evaluation.md`
- `docs/reports/evidence/snapshot-evaluation/**`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-18.md`.

## Реализация и ограничения

Real execution требует source-specific acquisition/storage/reuse/content approvals всех входящих originals, плюс provider processing decision для Groq run. Harness можно написать на synthetic заранее после contracts; real data не заменять. Зафиксируй набор по ACCEPTANCE_CRITERIA до final run, split document family, numerator/denominator/per-bank и all 6 pairs. Numeric extraction/evidence/conditions/retrieval/comparison метрики отдельно от coverage и LLM intent. >=20 real-model questions для S3 component, model/usage/date. Evaluation evidence хранить safe subset по разрешённой reuse policy; originals вне Git. Missing docs/key/human labels -> BLOCKED/NOT EVALUATED конкретной части, независимый harness всё равно завершить.

## Тесты и критерии приёмки

Harness fixture с заранее известными false positive/condition omission/retrieval miss -> правильные failing metrics; immutable gold hash и repeatability. S1/S2 thresholds без округления и synthetic подмены, coverage numeric >=1 и total >=2 per pair. Unsupported model claims=0 либо NO-GO report.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

Evaluation owner отдельные paths; сбор разрешений/разметка могут идти с SNAP-03 независимо. Не корректировать product thresholds/реальные tariffs для прохождения.

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
