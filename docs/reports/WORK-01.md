# Отчёт WORK-01 — источники и границы покрытия

**Дата:** 2026-10-09. **Статус:** BLOCKED. **Внутренний этап:** SRC-001, частично выполнен.

Базовая архитектура v1.1, scope и место вне-Git для originals приняты владельцем. Проведена техническая инвентаризация доменов, продуктовых страниц, PDF-кандидатов, robots и terms. Получен и хеширован один справочный FAQ Кубань Кредит. Тарифный original работодателя для каждого банка и право автоматической проверки не подтверждены, поэтому G0/source acceptance не пройден.

## Checkpoints

1. **SRC-001.01 — частично.** Final URL и redirect chain проверены для статьи sberbusiness.live и Kuban FAQ (без redirect); product pages Сбера/ВТБ/Альфы и tariff/manual PDFs target GET не подтвердили.
2. **SRC-001.02 — частично.** Найдены SberAPI; ВТБ conditions с 01.09.2026 в search index; Альфа product/documents, включая архивные правила 19.04.2024; Kuban FAQ и salary-card tariff album. Нет полного актуального employer tariff/conditions набора на банк.
3. **SRC-001.03 — BLOCKED.** Проектные решения приняты, но bank-side permission, применимые site terms и rate limits не подтверждены для целевых хостов. 24 часа — предварительная цель. Robots unknown не трактуется как allow.
4. **SRC-001.04 — частично.** Coverage matrix RU-KDA/МСБ содержит 44 unknown-клетки; один справочный original сохранён вне Git и SHA-256 внесён. Ценовые факты не seeded.

## Acceptance evidence

Четыре банковские строки и source decision/gaps внесены; доступные target URLs и HTTP результаты записаны; непроверенные URL не объявлены approved. Но тарифный/conditions original employer-level минимум на банк не получен, coverage фактических тарифов неизвестно, а допустимость автоматического сбора не подтверждена. AC и DoD не выполнены; WORK-01/SRC-001 остаются BLOCKED.

## Проверки и изменённые файлы

Команды GET/robots, MIME/hash и PDF content verification описаны в SRC-001.md. Автотесты не запускались; код приложения/тесты не менялись. Обновлены:

- docs/research/SOURCES.md
- docs/reports/source-feasibility.md
- docs/reports/SRC-001.md
- tests/fixtures/manifests/sources.json
- docs/implementation/MASTER_PLAN.md, WORK_INDEX.json, TASK_INDEX.json
- docs/implementation/work_packages/WORK-01.md и tasks/SRC-001.md
- MASTER_PLAN.md

Оригинал FAQ хранится вне Git.

## Передача / блокеры

**Требуют человека:** bank-specific разрешение/terms для автоматического получения и локального архива; site/path rate limits и допустимость интервала 24 часа; решение о правах/лицензиях; получение официальных текущих employer tariff/conditions документов со scope RU-KDA/МСБ и пакетами. Согласование владельца проекта не является разрешением банка.

**Технически могу выполнить после снятия этих блокеров:** повторные GET без обхода защиты, final URL/redirect/MIME/date verification, скачивание разрешённых оригиналов во вне-Git каталог, SHA-256 и обновление coverage. G0, WORK-01 и SRC-001 не объявлять DONE.
