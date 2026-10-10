# Стратегия проверок

## Уровни и изоляция

Unit: predicates (TRUE/FALSE/UNKNOWN), Decimal formulas, canonicalization, dates, context merge, claim validation, role policies. Frozen Clock для всех date tests, никакого today из host. Synthetic fixtures явно отличимы от real.

Integration: реальный PostgreSQL той же major, temp blob volume, migrations и FK/unique/transactions. SQLite не заменяет тестирование PostgreSQL locks/JSONB/FTS. HTTP mocked deterministic transport для статусов и сетевых ошибок; live official probes отдельный opt-in job без секретов в CI.

Contract: каждый BankAdapter проходит общую suite discover/classify/extract, LLM Fake/real adapter соблюдают единый DTO, OpenAPI→TypeScript compile, BlobStore put/open integrity. Golden documents фиксируются hash; новые HTML версии добавляют fixture, старые сохраняются.

E2E: browser→API→DB→archive с Fake LLM deterministic. Основной U01→U04, U02 memory, analyst publish→notification, invite→login→own history, deletion during answer, PDF physical page. Live provider smoke не блокирует offline CI, но обязателен перед provider production.

## Матрица отказов

| Внедрённая ошибка | Требуемый результат |
|---|---|
| 200 CAPTCHA вместо HTML | blocked, прежний corpus не меняется |
| 304 при отсутствующем blob | unconditional refetch, no dangling version |
| Redirect на localhost/IPv6 metadata | отказ до соединения |
| PDF text отсутствует | needs_ocr, не пустой confirmed corpus |
| Таблица разделена переносом страницы | evidence обеих страниц/сноски или review |
| Footer/banner изменён | новый raw version возможен, tariff event отсутствует |
| Число одинаково, сноска изменена | conditions_changed после review |
| Parser исправлен | correction event, не ложное объявление банка |
| Kill после blob rename до DB commit | orphan допускается, published dangling ref нет |
| Kill после publication commit до notification | replay доставляет один раз |
| Lease expires, старый worker жив | fencing блокирует commit |
| Новая future редакция | текущий запрос использует прежний effective факт |
| Unknown scope/date или конфликт | не уверенный winner |
| Удаление chat во время provider call | результат не восстанавливает chat |
| LLM malformed/unknown claim/выдуманное число | reject + safe template fallback |
| Rate budget исчерпан двумя одновременными calls | atomic reservation не превышает cap |

## Команды будущей реализации

INF-001 фиксирует реально работающие команды в README. Целевой контракт: `uv run pytest backend/tests/unit`, `uv run pytest backend/tests/integration`, `uv run pytest backend/tests/security`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run test:e2e`. До реализации это спецификация команд, а не выполненные проверки.

Каждая task добавляет только относящиеся к её поведению проверки; не дублировать implementation shape. Финальные QA задачи тестируют сквозные риски, а не повторяют все unit tests. Отчёт включает команду, окружение/image versions, fixture hashes, результат/pass/fail/skip и причину skip. Падающие security/precision tests нельзя переводить в xfail для закрытия gate.
