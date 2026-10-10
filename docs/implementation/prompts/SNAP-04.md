# SNAP-04 — PDF parser с page/table evidence

Готовый исполнительский промпт: выдай весь этот файл Codex вместе с репозиторием.
Рекомендуемый reasoning effort: **high**; выбор модели свободный.

## Цель и ожидаемый результат

Offline pdfplumber parser выдаёт immutable blocks с физическими страницами, таблицами/сносками и diagnostics.

## Условия начала

Merged зависимости: SNAP-01. Пока зависимость не завершена, допустим только явно
отдельный scaffold/harness; окончательная приёмка ждёт merged implementation.

Прочитай AGENTS.md, docs/architecture/OVERVIEW.md, DOMAIN_CONTRACTS.md,
DATABASE_DESIGN.md, API_CONTRACTS.md, SECURITY.md и docs/product/ACCEPTANCE_CRITERIA.md.
Проверь актуальный код и отчёты зависимостей: DONE в плане без merged результата
не считается условием начала. Исполни только эту задачу до reviewable результата.
Работай offline с synthetic fixtures, если конкретный real/provider run не допущен.
Не создавай фиктивные разрешения, тарифы, reviewer или PASS. Не запускай scheduler,
recurring download, notifications, очереди, микросервисы или автоматический paid fallback.
Сохрани FetchGateway, LocalBlobStore, source recovery, E2E и миграции 0001/0002.

## Файлы и ответственность

- `backend/app/parsing/pdf.py`
- `backend/tests/test_parsing_pdf.py`
- `backend/tests/fixtures/parsing/pdf/**`
- `pyproject.toml`
- `uv.lock`

Остальные модули read-only. Если требуется общий контракт/schema/config change,
подготовь точный запрос владельцу и дождись sequential merge; не правь чужие
файлы конкурентно. Report задачи — `docs/reports/SNAP-04.md`.

## Реализация и ограничения

Добавь pdfplumber/pdfminer.six с лицензионным inventory delta в report. Используй Parser Protocol. Локальный verified original; сохранение headers/footnotes/relations, printed label отдельно от physical page. Scan-only -> needs_ocr, encrypted/corrupt/over quota -> typed status. Resource bounded subprocess совместно с pipeline runner позднее; сам parser не делает сеть. Никакого OCR/PyMuPDF/LLM extraction на этом этапе.

## Тесты и критерии приёмки

Generated multi-page PDF с текстом, таблицей, сноской; каждый quote воспроизводится по locator, parser version/hash стабилен; scan/encrypted/corrupt/page quota cases; не потеряны условия, неподтверждённые relations flagged. No egress test. Unit парсера не зависит от банковских originals.

Выполни ruff/mypy для backend и релевантные pytest (PG integration на dedicated
DB с migrations); frontend lint/typecheck/build при изменении frontend. Проверь
`python tools/validate_docs.py`. Пропуск проверки укажи как NOT RUN с причиной,
не как PASS. Новые тесты проверяют риск/доменный контракт, а не копируют реализацию.

## Параллелизм

PDF owner временно единственный владелец pyproject/uv.lock. Dependency commit merge первым; SNAP-05 ждёт этот merge только для dependency edits, остальную работу ведёт отдельно.

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
