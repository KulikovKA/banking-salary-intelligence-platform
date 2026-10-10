# Требования и трассировка

Четыре банка: Сбер, ВТБ, Альфа-Банк, Кубань Кредит. Основной регион RU-KDA, около 30 сотрудников. Закрытая платформа анализирует публичные зарплатные предложения; не выполняет платежи и не даёт гарантированного коммерческого предложения от имени банка.

| ID | Требование | Контракт / задачи |
|---|---|---|
| R01 | Официальные HTML/PDF, политики сбора, четыре адаптера | SRC-001, ING-001…004 |
| R02 | Неизменяемый полный оригинал, дата и hash | STO-001, VER-001, DOC-001 |
| R03 | Постраничный PDF, sections/footnotes HTML | PDF-001, HTML-001, TXT-001 |
| R04 | Факты, единицы, ставки, applicability и даты | FACT-001…004 |
| R05 | Региональные, федеральные и индивидуальные условия | DOMAIN_CONTRACTS, CMP-001 |
| R06 | Детерминированное честное сравнение, обе стороны доказаны | CMP-002, AI-002 |
| R07 | Версии, current/historical, без потери оригиналов | VER-001, FACT-004, CHG-001 |
| R08 | Чат, намерение, замена LLM, Fake, budget | LLM-001…003, AI-001…003 |
| R09 | Память не подменяет актуальные факты | CHAT-001, CHAT-002 |
| R10 | Приглашения, User/Analyst/Admin, ownership | AUTH-001…003, SEC-001 |
| R11 | Восемь UI разделов и честные ошибки | UI-001…006 |
| R12 | Мониторинг, содержательные события и подписки | JOB-002, CHG-001, NTF-001 |
| R13 | Ручная проверка до публикации | FACT-003, UI-006 |
| R14 | 30 пользователей, logs, backup, deployment | OPS-001…003, LOAD-001 |
| R15 | Prompt injection, SSRF, ПД | SEC-001…003 |
| R16 | Measurable POC до полного UI | QA-001…002, gates G1/G2 |
| R17 | Независимый финальный аудит и исправления | REV-001…003 |

Quality attributes: evidence completeness 100% для опубликованных claims; отсутствие неподтверждённых чисел в контрольном корпусе; сохранность оригиналов; no cross-user access; повторяемость сравнения; деградация при source/LLM outage. Это критерии приёмки, не абсолютная математическая гарантия для всех будущих документов.

Индивидуальный тариф в публичном источнике хранится как `individual`, numeric=null. Загрузка конкретных коммерческих договоров исключена из MVP и не подразумевается наличием поля contract_variant.

Нефункциональные цели после замера: p95 обычных API <500ms, search/comparison <1s на 100k chunks, answer с реальным API ≤45s deadline; 30 concurrent sessions с 5 active provider calls и backpressure. Не требовать 30 одновременных LLM вызовов. Доступность 99% в рабочее время — предложенная эксплуатационная цель на single host, без HA обещаний.

## Ответы на 15 архитектурных вопросов исходного запроса

| № | Вопрос | Зафиксированное решение / документ |
|---|---|---|
| 1 | Федеральные и региональные условия | Evidence-backed GeoScope, unknown отдельно, override только по доказательству — DOMAIN_CONTRACTS |
| 2 | Индивидуальные тарифы | kind=individual, null numeric, текст/источник; приватные договоры потребуют отдельного ACL расширения — OVERVIEW |
| 3 | Актуальная редакция | as_of + knowledge_cutoff + scope + supersession, не latest fetched — ADR-002 |
| 4 | Старые редакции | Immutable blobs/versions/extractions, RESTRICT и новые corrective publications — DATABASE_DESIGN |
| 5 | Длинные PDF | Физические страницы, section chunks и FTS с измеренным recall — EVALUATION_PLAN |
| 6 | Корректные ссылки | Backend UUID metadata, archive version, проверенная physical_page — API_CONTRACTS |
| 7 | Разные условия тарифов | Scenario + predicates TRUE/FALSE/UNKNOWN, единая база, no aggregate winner при gaps — DOMAIN_CONTRACTS |
| 8 | Ложные уведомления | Semantic diff published facts, baseline/correction/announced отдельно, dedup — DATA_FLOW |
| 9 | Число LLM вызовов | 0–2 calls/question, fixed tool plan, template fallback — DOMAIN_CONTRACTS |
| 10 | До выбора API | Fake Protocol и offline contract/eval fixtures, отдельно real-model gates — LLM-001/003 |
| 11 | Расход токенов | Atomic reserve/reconcile, quotas, estimated flag и price config — LLM-002 |
| 12 | Недоступность сайтов | Last-known-good + freshness + bounded retry/blocked, без удаления фактов — OPERATIONS |
| 13 | Обновления без потери | Expand-contract миграции, paired backup и restore rehearsal — OPERATIONS |
| 14 | Качество на реальных документах | Human gold/holdout по document family, per-bank metrics/coverage — EVALUATION_PLAN |
| 15 | Память не заменяет факты | Context только scenario/focus, свежий snapshot на каждый вопрос — DATA_FLOW/CHAT-002 |

Ссылочные имена обозначают центральные документы пакета, а не файлы приложения. Полная навигация находится в [docs README](../README.md).
