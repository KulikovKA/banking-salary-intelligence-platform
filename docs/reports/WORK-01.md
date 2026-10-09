# WORK-01 — Источники и границы покрытия

**Статус:** BLOCKED. **Дата checkpoint:** 2026-10-09. **Внутренний этап:** SRC-001.

Публичные URL-кандидаты собраны по четырём банкам и внесены в discovery-only manifest. Ни один URL не получил approved policy decision. Покрытие 11 метрик для RU-KDA, пакет и географическая применимость остаются `unknown` по каждому банку. Тарифные originals не скачивались и не сохранялись; SHA-256 не заявлены.

Работа остановлена до решения назначенного владельца G0/source policy: подтверждения разрешённых доменов и URL, проверки robots/terms, установки request rate и выбора разрешённого хранилища originals. Актуальные тарифы и условия не сверены по оригиналам, поэтому SRC-001 и WORK-01 не DONE.

Подробные URL, результаты запросов, разбор по банкам, критерии приёмки, проверки и следующий владелец описаны в [отчёте SRC-001](SRC-001.md) и [source feasibility](source-feasibility.md). Машиночитаемые наблюдения без разрешённых seed URL находятся в [`tests/fixtures/manifests/sources.json`](../../tests/fixtures/manifests/sources.json).

## Files

- `docs/reports/WORK-01.md`
- `docs/reports/SRC-001.md`
- `docs/reports/source-feasibility.md`
- `tests/fixtures/manifests/sources.json`
- `docs/implementation/MASTER_PLAN.md`
- `docs/implementation/WORK_INDEX.json`
- `docs/implementation/TASK_INDEX.json`
- `docs/implementation/work_packages/WORK-01.md`
- `docs/implementation/tasks/SRC-001.md`

## Validation

JSON syntax and invariants were checked with Python: 4 banks, 6 candidate URLs, 11 metrics per bank, all policy decisions pending, all coverage values unknown, and synchronized BLOCKED statuses in WORK_INDEX/TASK_INDEX. No application tests were available or run. Full AC evidence and failed/skipped checks are in [SRC-001](SRC-001.md).
