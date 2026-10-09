# Реестр рисков

| ID / приоритет | Риск / триггер | Контроль и остаточный риск | Владелец / gate |
|---|---|---|---|
| K01 Critical | Нет публичных сопоставимых условий одного банка | Source feasibility раньше UI; честный scope reduction. Даже официальный сайт может не публиковать цену | Пользователь + SRC-001 / G1 |
| K02 High | Неясная редакция/регион | Date/scope evidence, conflict, manual review; часть сравнений останется неизвестной | FACT-004 / G2 |
| K03 High | Потеря сноски при PDF parse | Multi-evidence, condition recall, analyst. OCR production не обещан | PDF-001 / G2 |
| K04 High | Ложный semantic event | Canonical text + validated fact diff, extraction correction type | CHG-001 / G4 |
| K05 High | Сбой между БД и file archive | Atomic file put перед DB commit, reconciliation, paired backups | STO-001, OPS-002 |
| K06 Critical | Чужая переписка/ПД попадают в LLM | Ownership, safe normalized gateway, provider gate; regex не полная гарантия | SEC-001/003 / G3 |
| K07 High | LLM уверенно расширяет вывод | Structured claim templates и fallback; естественность формулировок ограничена | AI-002 / G2 |
| K08 High | Изменения банковского сайта | Golden fixtures/versioned adapters, health отдельно от 200, no auto deletion | JOB-002 / G4 |
| K09 High | PyMuPDF license несовместима | Decision before include; pdfplumber option; качество альтернативы надо измерить | PDF-001 / G1 |
| K10 High | Неподтверждённая правомерность сбора | robots/terms + ответственный, запрет bypass. Legal review ещё не завершён | SRC-001, SEC-003 |
| K11 Medium | FTS не понимает перефразировки | synonyms + metrics; measurable pgvector trigger | SRCH-001, QA-002 |
| K12 High | Single host outage | Off-host encrypted backup, restore drill; HA вне scope | OPS-002 / G4 |
| K13 Medium | Расход LLM и burst 30 users | reservations, quotas, concurrency5, queue20, safe cache | LLM-002, LOAD-001 |
| K14 High | Внешний родительский Git | Создать project-local boundary после разрешения разработки, не трогать чужие изменения | INF-001 |
| K15 High | Несогласованные schema между задачами | Центральные контракты, migration single head, OpenAPI generation, ADR change control | DB-001…003 |

Нерешённые decisions: LLM/provider, политика внешней передачи, источник тарифов/допустимость сбора каждого банка, PyMuPDF license, hosting/retention, scope SME/premium. Они не скрыты в «техническом долге» и не считаются автоматически одобренными.
