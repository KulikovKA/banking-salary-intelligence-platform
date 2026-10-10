# SOURCE-RECOVERY E2E — 10.10.2026

Результат: **PASS_SYNTHETIC_ONLY; REAL_SCENARIO_BLOCKED**. Полный доступный путь
проверен через `IngestionService` приложения и реальный PostgreSQL 18. Новых
банковских GET, импорта реальных originals, реальных approved grants и публикации
тарифных фактов не было. WORK-01/G1/G2 остаются непройденными.

## CI исправлен до E2E

В `test_production_rejects_fake_identity_and_insecure_cookies` был задан
Windows-путь `C:\\var\\lib\\bsi`. На Ubuntu `Path.is_absolute()` возвращал false,
и тест получал ошибку storage вместо ожидаемой ошибки авторизации. Используется
нативный абсолютный `tmp_path.resolve()`. Отдельный тест проверяет принятие
корректной production-конфигурации с таким путём. Runtime-проверка абсолютности
не ослаблена.

Исправление: `2427e0aaa1996e211fb0f59dc2c9ee804c4ae197`.
[GitHub Actions run 38069851853](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38069851853)
завершён **success**, включая backend и frontend. E2E запущен после этого.

## Проверка реальных кандидатов и допуска

Использованы два точных кандидата из исследования 10.10.2026. Локальные файлы
повторно проверены по размеру и SHA-256; в application archive не переносились.

| Кандидат | Размер | SHA-256 | Дата действия из исследования |
|---|---:|---|---|
| [Тариф зарплатного проекта](https://kk.ru/upload/iblock/3cf/2aukz7j463jptle27m62oo8frs1x862x.pdf) | 648631 | `db9c856a67767b6d1c290a48162d107fa6c99d8905b395d3b113ec1920b57bec` | 01.06.2024 |
| [Условия обслуживания работодателя](https://kk.ru/upload/iblock/973/96i8chqk1f794ldm6umaie424qnvoxhb.pdf) | 757961 | `4f935428de5678c4a4b176ff1f7c34e5ed0d635d30502a878d272fbac32e8ecb` | 29.06.2026 |

Проверены существующий [SourceAcceptanceManifest](../../tests/fixtures/manifests/sources.json),
[SRC-001](SRC-001.md), [исследование](bank-document-investigation-2026-10-10.md)
и локальные `kk-product-links.json`, `kk-tariff.json`, `kk-conditions.json`.
Связь точных PDF с официальной product page подтверждена ранее полученными
ссылками. Это подтверждение происхождения, а не выдача разрешения.

| Условие | Evidence и решение |
|---|---|
| Происхождение | Официальная страница `https://kk.ru/business/solutions/zp-project/` содержит оба точных href; локальные hashes совпадают с исследованием. |
| Robots | Исторический robots SHA-256 `57b087c698d6e11464571542c4d33b02fca45c03d123856b9f91d63286584f2d`: запреты PDF относятся к Yandex, не `*`. Для стабильного `BankSalaryResearch/0.1` кандидаты разрешены. Свежего robots GET в этом E2E не было. |
| Applicable terms / основание получения | Проверяемого документа, подтверждающего допустимость выбранного способа получения для этих URL, в evidence нет. UNKNOWN. |
| Хранение originals | Нет подтверждённого source-specific основания, границ хранения и решения ответственного. UNKNOWN. |
| Повторное использование bytes / извлечённых данных | Нет подтверждённых условий и границ использования. UNKNOWN. |
| G0-LIVE | Нет отдельного решения по точным URL, redirects, цели, частоте, сроку и отзыву. BLOCKED. |
| Manual grant | Для этих двух PDF нет отдельного согласованного получения/хранения/использования. BLOCKED. Ограниченный допуск FAQ из старого manifest относится к другому документу. |

Manifest исправлен по подтверждённым техническим фактам: устранено ошибочное
объединение robots-групп, добавлены hashes/размеры и происхождение исследовательских
originals. Статус обоих кандидатов остаётся **blocked**. Наличие HTTP 200,
robots allow, локальных bytes и поручения провести проверку не подменяет
отсутствующие основания. Фиктивные reviewer/terms/grants не созданы.

Для реального сценария ответственному нужно документировать применимые
условия/разрешение либо иное подтверждённое основание для точных URL и выбранного
способа получения, отдельно хранение и использование. Затем оформить grant с
целью, redirects, лимитами, сроком/отзывом и evidence. Для автоматической загрузки
после этого нужны fresh robots/TLS checks; для ручного пути — отдельный manual
grant и достоверные provenance/operator/acquired_at. Проверка содержания и
применимости RU-KDA/МСБ выполняется после допустимого получения отдельно.

## Фактически выполненный E2E

Новая изолированная БД `bsi_e2e` на существующем Docker PostgreSQL 18; Alembic
`0001_catalog → 0002_source_recovery`. Создан отдельный банк `syn_e2e_*` и source
`corpus_kind=synthetic`. Только manual grant для сгенерированного тестового PDF;
автоматического grant нет. `APP_ENV=test`, `INGESTION_MODE=offline`.

[Harness](../../tools/source_recovery_e2e.py) генерирует полноценный одностраничный
PDF с objects/xref/trailer и видимой надписью SYNTHETIC. Это тестовый материал,
не имитация банковского тарифа. Запуск коммитит строки, поэтому проверка
долговечности выполняется вне исходного процесса. Повторные запуски используют
разные synthetic bank/source и bytes; существующие данные не удаляются.

Run ID: `af20ce35898047c7a5e59410c0ce7063`, завершён 10.10.2026 в 20:01:44 МСК.
Source ID: `ce74fd37-a2ed-42d9-b458-5803f520f02c`.
[Машиночитаемый результат](evidence/source-recovery-e2e-2026-10-10.json).
Локальные originals/result остаются в `.local/source-recovery-e2e/<run_id>/`.

| Шаг | Фактический результат |
|---|---|
| Manual import A | `manual_imported`, SHA-256 проверен по исходным bytes; версия quarantine; HTTP NULL. |
| Повтор A | Новая observation, тот же version_id; один blob и одна версия для A. |
| Acceptance A | accepted; `current_content` возвращает A; reviewer/applicability записаны. |
| Manual import B | Новый blob и version_id; B quarantine, текущая принятая версия ещё A. |
| Неверный формат | `FORMAT_INVALID`, rejected observation; A сохранена. |
| Отсутствующий файл | `STORAGE_WRITE_FAILED`, rejected observation; A сохранена. |
| Отозванный manual grant | `POLICY_BLOCKED` до чтения отсутствующего файла; A сохранена. |
| Automatic fetch без grant | `POLICY_BLOCKED` до DNS/HTTP; нет сетевого успеха. |
| Acceptance B | B accepted и current; A остаётся accepted, bytes A неизменны. |
| Reconciliation | missing=[], orphan=[]; 2 blobs, 2 версии, 7 observations. |
| Проверка отдельным процессом | `docker compose exec db psql` прочитал обе принятые версии, sizes/hashes/reviewer после завершения harness. |

Версия A: `1e3d0764-5aac-4fd8-89b3-1e35e2747e6f`, 633 bytes,
SHA-256 `b37eac8d47015297603788719173b4f48760a1cb8d54e552e93ccf2248eabce7`.
Версия B: `662f235d-a7a3-49de-998b-a2a93bf30396`, 633 bytes,
SHA-256 `b77071af06d3d0b0f149aa13ad3b8f0753544f781ea1cc2399d8ef86d49a6750`.

Обе версии `corpus_kind=synthetic`, accepted_by=`offline-e2e-test`.
`last_successful_check` остаётся NULL; manual import не засчитан как scheduled
fetch. `current_content` может сообщать stale, поскольку сетевой мониторинг не
выполнялся. В основной БД `bsi` отдельным psql подтверждено: sources=0, blobs=0,
versions=0. Реальный корпус не изменён.

Это E2E импорта/archive/DB/content acceptance, а не доказательство live HTTP
для банка, извлечения тарифов или публикации фактов. Полный тарифный parser и
его acceptance не являются доступным этапом текущего pipeline.

## Дополнительные проверки и найденные ошибки

- Исправлена изоляция PostgreSQL-теста reconciliation: выборка всех synthetic
  blob в БД ошибочно считала чужой архив отсутствующим в локальном tmp_path.
  Выборка ограничена source_id; тест специально создаёт unrelated blob в другом
  архиве и проверяет правильную работу на непустой БД.
- Добавлен тест: повреждение archived bytes перед acceptance даёт
  `STORAGE_HASH_MISMATCH`; новая версия остаётся quarantine, предыдущая accepted
  остаётся текущей.
- Добавлен тест: повторная acceptance не перезаписывает reviewer/applicability
  уже принятой версии.
- `pytest backend/tests tools/test_bank_tls_probe.py`: **104 passed**, включая
  9 PostgreSQL tests, без skipped; запуск против непустой `bsi_e2e`.
- Ruff: PASS. mypy: PASS, 23 source files. Alembic check: PASS, no new operations.
- В CI добавлен отдельный offline synthetic E2E на `bsi_test` с committed rows
  и upload JSON artifact. Инструмент отказывается работать без test/offline и
  вне именованных test DB `bsi_test`/`bsi_e2e`.

## Повторение

Для первого запуска создать отдельную `bsi_e2e` через `createdb` в имеющемся
PostgreSQL. При повторении существующую БД сохранять. Затем:

```powershell
$env:APP_ENV = 'test'
$env:INGESTION_MODE = 'offline'
$env:DATABASE_URL = '<local PostgreSQL URL with database bsi_e2e>'
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe tools/source_recovery_e2e.py --output-root .local/source-recovery-e2e
```

Scheduler, LLM, UI, runtime live-конфигурация и архитектура не изменялись.
