# Документация snapshot v1

Документы ниже — активная спецификация. Код и миграции определяют фактически
реализованное состояние; будущие контракты и таблицы явно помечены как планируемые.

| Документ | Назначение |
|---|---|
| [Архитектура](architecture/OVERVIEW.md) | Scope, стек, компоненты, схема движения данных |
| [Доменные контракты](architecture/DOMAIN_CONTRACTS.md) | Parsing, facts, evidence, comparison, LLM |
| [База данных](architecture/DATABASE_DESIGN.md) | Существующая схема и добавочные миграции |
| [API](architecture/API_CONTRACTS.md) | Маршруты, DTO, ошибки и доступ |
| [Безопасность](architecture/SECURITY.md) | Trust boundaries, auth, документы и Groq |
| [ADR-007](architecture/ADR/007-snapshot-monolith.md) | Смена архитектуры и судьба старых ADR/gates |
| [План](implementation/MASTER_PLAN.md) | DAG, порядок и executable prompts |
| [Source recovery](implementation/SOURCE_RECOVERY_USAGE.md) | Работающий fetch/import CLI |
| [Приёмка](product/ACCEPTANCE_CRITERIA.md) | S0–S3, реальные данные и честный NO-GO |
| [Codex](../AGENTS.md) | Правила исполнения и совместной работы |
| [Аудит изменений](reports/SNAPSHOT-REBASE-2026-10-10.md) | Инвентаризация, проверки, ограничения |
| [Архив](archive/README.md) | Предыдущие планы/ADR, отчёты и доказательства |

Задачи находятся только в `implementation/prompts/SNAP-*.md`; их зависимости и
статусы — в одном `implementation/TASKS.json`. Старые WORK_INDEX/TASK_INDEX не активны.
Исторические разрешения находятся в отчётах и исходном manifest
[sources.json](../tests/fixtures/manifests/sources.json); реестр не подменяется планом.
