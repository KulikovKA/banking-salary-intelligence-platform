# ADR-001 — Кандидаты, evidence и атомарная публикация

Status: proposed. Date: 2026-10-09. Owner: архитектор; approval: пользователь G0.

Context: на схеме B ручная и автоматическая ветки сходятся к сохранению факта. Без явной границы непроверенный кандидат может появиться в сравнении. Связь original→version→parse→chunk→fact должна переживать переобработку.

Decision: append-only observations/originals/extractions, отдельные fact_reviews и publications. Read модели comparison используют только approved publication members и scope/date filter. Corpus revision повышается в одной транзакции с событиями при подключённом MVP changes модуле. Публикация проверяет существование оригинала и целостность evidence.

Alternatives: флаг approved на единственной изменяемой строке — проще, но теряет историю; отдельная очередь/сервис approval — избыточно для масштаба. Выбран тот же PostgreSQL и application service.

Consequences: дополнительные таблицы и review UI; объяснимость и возможность rollback через новую corrective publication. Candidate хранится, но не является публичным утверждением. Удаление evidence RESTRICT.

Affected: DATABASE_DESIGN, DATA_FLOW, FACT-002/003/004, DB-003/005, CHG-001, UI-006, AI-002. Проверка: candidate excluded, missing source blocked, concurrent publish atomic, replay no duplicate. Откат проектного решения до реализации — правка контракта; после реализации downgrade с потерей provenance не допускается.
