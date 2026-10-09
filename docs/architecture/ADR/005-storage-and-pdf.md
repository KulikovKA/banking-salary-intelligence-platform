# ADR-005 — Оригиналы вне БД, parser за интерфейсом

Status: proposed. Date: 2026-10-09. Approval: пользователь G0; PDF licensing decision до PDF-001.

Context: Miro содержит архив PDF/HTML, но не задаёт consistency и backup. Заданный PyMuPDF имеет AGPL/commercial licensing, которую нельзя оставить скрытой зависимостью.

Decision: content-addressed local BlobStore, atomic file write before DB reference, SHA-256, reconciliation, backups DB+blob manifest, read-only API volume. Parser Protocol позволяет PyMuPDF после решения по лицензии или proposed pdfplumber baseline. Ни библиотека, ни confidence не дают автоматической гарантии чтения сложной таблицы.

Alternatives: PDF bytea в PostgreSQL — усложняет backup DB; немедленный S3/MinIO — лишняя инфраструктура; жёсткий импорт PyMuPDF до решения — риск поздней переделки. Выбран local storage и interface без обещания будущей миграции «без работы».

Consequences: отсутствие единой DB/filesystem транзакции закрывается write-order и reconciliation; авария может оставить orphan, но не должна создавать published dangling ref. Full HTML нельзя безопасно встроить на app origin. OCR вне MVP.

Affected: STO-001, PDF-001, DOC-001, OPS-002, SEC-003; links [research](../../research/SOURCES.md). Tests: kill/ENOSPC/duplicate blob, page provenance, hash restore, scripted HTML attachment. Migration to S3: copy→checksum→dual-read→switch DB storage key mapping, document/evidence UUID неизменны; отдельная будущая задача.
