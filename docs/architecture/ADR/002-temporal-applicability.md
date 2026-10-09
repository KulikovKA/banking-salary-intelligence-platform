# ADR-002 — Действующая редакция и область применимости

Status: proposed. Date: 2026-10-09. Approval: пользователь G0.

Context: последнее скачивание не доказывает действие условий. Федеральные, региональные, пакетные и индивидуальные предложения могут сосуществовать, а новый PDF изменять только часть условий.

Decision: хранить business validity отдельно от времени обнаружения/публикации. ScopeDimension различает any/specific/unknown. Supersession имеет scope и effective interval. Unknown date/scope и conflicts возвращаются явно; individual не получает numeric value. Исторический запрос принимает as_of и optional knowledge_cutoff.

Alternatives: latest document wins; regional always wins; unknown date=fetched_at. Все три просты, но могут дать ложный тариф, поэтому отвергнуты. Не требуется полнофункциональная temporal database: достаточно append-only publications и query service.

Consequences: больше insufficient/not_comparable; зато нельзя обещать цену вне доказанных условий. Analyst должен обосновать override документом. Дата на веб-странице без смысла edition/effective не используется автоматически.

Affected: DOMAIN_CONTRACTS, FACT-001/004, CMP-001/002, CHG-001, CHAT-002, SRCH-001. Tests: future/retroactive/partial supersession, unknown region, overlapping conflict, original historical answer. Migration: preserve old facts; backfill unknown вместо придуманных дат.
