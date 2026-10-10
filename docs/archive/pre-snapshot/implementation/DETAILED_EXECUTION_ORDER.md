> Детализация исходных 62 этапов. Актуальные единицы исполнения — 22 WORK-блока в [MASTER_PLAN](MASTER_PLAN.md). Исходные ID сохранены для трассировки требований. Старый порядок использовать только как справку; уровни reasoning см. в обновлённых ТЗ.

# Последовательность исполнения

Это топологически проверенный порядок. Выполнять только после разрешения разработки и прохождения gates. Готовые ТЗ/prompt не означают автоматический запуск реализации.

1. **SRC-001** — [Инвентаризация официальных источников и допустимости сбора](tasks/SRC-001.md); [prompt](luna_prompts/SRC-001.md). Gate: G0.
2. **INF-001** — [Изолированный репозиторий и воспроизводимые инструменты](tasks/INF-001.md); [prompt](luna_prompts/INF-001.md). Gate: G0.
3. **INF-002** — [Validated config и локальное окружение POC](tasks/INF-002.md); [prompt](luna_prompts/INF-002.md). Gate: G0.
4. **DB-001** — [Миграции каталога, blobs и job queue](tasks/DB-001.md); [prompt](luna_prompts/DB-001.md). Gate: G0.
5. **STO-001** — [Неизменяемое файловое хранилище оригиналов](tasks/STO-001.md); [prompt](luna_prompts/STO-001.md). Gate: G0.
6. **NET-001** — [Безопасный FetchGateway с условными запросами](tasks/NET-001.md); [prompt](luna_prompts/NET-001.md). Gate: G0.
7. **JOB-001** — [Cron enqueue, leases и повтор фоновых задач](tasks/JOB-001.md); [prompt](luna_prompts/JOB-001.md). Gate: G0.
8. **HTML-001** — [HTML extraction с сохранением значимого текста](tasks/HTML-001.md); [prompt](luna_prompts/HTML-001.md). Gate: G0.
9. **PDF-001** — [PDF extraction постранично и контроль качества](tasks/PDF-001.md); [prompt](luna_prompts/PDF-001.md). Gate: G0.
10. **DB-002** — [Миграции документов, страниц и chunks](tasks/DB-002.md); [prompt](luna_prompts/DB-002.md). Gate: G0.
11. **TXT-001** — [Chunking, сноски и точная привязка evidence](tasks/TXT-001.md); [prompt](luna_prompts/TXT-001.md). Gate: G0.
12. **VER-001** — [Разделение raw, canonical и parser версий](tasks/VER-001.md); [prompt](luna_prompts/VER-001.md). Gate: G0.
13. **ING-001** — [Адаптер банка Сбер](tasks/ING-001.md); [prompt](luna_prompts/ING-001.md). Gate: G0.
14. **ING-002** — [Адаптер банка ВТБ](tasks/ING-002.md); [prompt](luna_prompts/ING-002.md). Gate: G0.
15. **ING-003** — [Адаптер банка Альфа-Банк](tasks/ING-003.md); [prompt](luna_prompts/ING-003.md). Gate: G0.
16. **ING-004** — [Адаптер банка Кубань Кредит](tasks/ING-004.md); [prompt](luna_prompts/ING-004.md). Gate: G0.
17. **QA-001** — [Gate G1: повторяемость получения четырёх банков](tasks/QA-001.md); [prompt](luna_prompts/QA-001.md). Gate: G0.
18. **DB-003** — [Миграции фактов, evidence и публикаций](tasks/DB-003.md); [prompt](luna_prompts/DB-003.md). Gate: G0.
19. **FACT-001** — [Нормализованные DTO тарифов и applicability](tasks/FACT-001.md); [prompt](luna_prompts/FACT-001.md). Gate: G0.
20. **FACT-002** — [Извлечение кандидатов по правилам и provenance](tasks/FACT-002.md); [prompt](luna_prompts/FACT-002.md). Gate: G1.
21. **FACT-003** — [Валидация и решения аналитика](tasks/FACT-003.md); [prompt](luna_prompts/FACT-003.md). Gate: G0.
22. **FACT-004** — [Атомарная публикация и выбор действующих фактов](tasks/FACT-004.md); [prompt](luna_prompts/FACT-004.md). Gate: G0.
23. **SRCH-001** — [PostgreSQL FTS с фильтрами и оценкой поиска](tasks/SRCH-001.md); [prompt](luna_prompts/SRCH-001.md). Gate: G0.
24. **CMP-001** — [Совместимость предложений и трёхзначные условия](tasks/CMP-001.md); [prompt](luna_prompts/CMP-001.md). Gate: G0.
25. **CMP-002** — [Детерминированные формулы и доказательства обеих сторон](tasks/CMP-002.md); [prompt](luna_prompts/CMP-002.md). Gate: G0.
26. **LLM-001** — [Провайдерский Protocol и Fake LLM](tasks/LLM-001.md); [prompt](luna_prompts/LLM-001.md). Gate: G0.
27. **AI-001** — [Intent и безопасные read-only инструменты](tasks/AI-001.md); [prompt](luna_prompts/AI-001.md). Gate: G0.
28. **AI-002** — [Claim validation и evidence-first renderer](tasks/AI-002.md); [prompt](luna_prompts/AI-002.md). Gate: G0.
29. **DOC-001** — [API метаданных и полный оригинал по UUID](tasks/DOC-001.md); [prompt](luna_prompts/DOC-001.md). Gate: G0.
30. **API-001** — [POC routes сравнения, поиска и вопроса](tasks/API-001.md); [prompt](luna_prompts/API-001.md). Gate: G0.
31. **UI-001** — [Минимальный экран POC: вопрос, таблица, оригинал](tasks/UI-001.md); [prompt](luna_prompts/UI-001.md). Gate: G0.
32. **QA-002** — [Gate G2: оценка технического ядра POC](tasks/QA-002.md); [prompt](luna_prompts/QA-002.md). Gate: G1.
33. **DB-004** — [Миграции auth, чатов, usage и idempotency](tasks/DB-004.md); [prompt](luna_prompts/DB-004.md). Gate: G2.
34. **AUTH-001** — [Приглашения, пароли и bootstrap Admin](tasks/AUTH-001.md); [prompt](luna_prompts/AUTH-001.md). Gate: G2.
35. **AUTH-002** — [Сессии, CSRF и лимиты входа](tasks/AUTH-002.md); [prompt](luna_prompts/AUTH-002.md). Gate: G2.
36. **AUTH-003** — [RBAC и object ownership во всех сервисах](tasks/AUTH-003.md); [prompt](luna_prompts/AUTH-003.md). Gate: G2.
37. **LLM-002** — [Gateway, budgets, redaction и отказоустойчивость](tasks/LLM-002.md); [prompt](luna_prompts/LLM-002.md). Gate: G2.
38. **CHAT-001** — [Хранение собственной истории и удаление](tasks/CHAT-001.md); [prompt](luna_prompts/CHAT-001.md). Gate: G2.
39. **CHAT-002** — [Структурированная память и разрешение ссылок](tasks/CHAT-002.md); [prompt](luna_prompts/CHAT-002.md). Gate: G2.
40. **AI-003** — [Асинхронный ответ и сохранение согласованного snapshot](tasks/AI-003.md); [prompt](luna_prompts/AI-003.md). Gate: G2.
41. **DB-005** — [Миграции событий, outbox, подписок и аудита](tasks/DB-005.md); [prompt](luna_prompts/DB-005.md). Gate: G2.
42. **CHG-001** — [Содержательный diff и активация будущих условий](tasks/CHG-001.md); [prompt](luna_prompts/CHG-001.md). Gate: G2.
43. **NTF-001** — [Подписки и идемпотентные уведомления внутри сайта](tasks/NTF-001.md); [prompt](luna_prompts/NTF-001.md). Gate: G2.
44. **JOB-002** — [Диагностика парсеров и freshness](tasks/JOB-002.md); [prompt](luna_prompts/JOB-002.md). Gate: G2.
45. **API-002** — [REST MVP: review, администрация и сводки](tasks/API-002.md); [prompt](luna_prompts/API-002.md). Gate: G2.
46. **UI-002** — [Каркас кабинета, вход и навигация по ролям](tasks/UI-002.md); [prompt](luna_prompts/UI-002.md). Gate: G2.
47. **UI-003** — [Чат MVP, история и context controls](tasks/UI-003.md); [prompt](luna_prompts/UI-003.md). Gate: G2.
48. **UI-004** — [Сравнения и каталог оригинальных документов](tasks/UI-004.md); [prompt](luna_prompts/UI-004.md). Gate: G2.
49. **UI-005** — [Dashboard, лента изменений и настройки подписок](tasks/UI-005.md); [prompt](luna_prompts/UI-005.md). Gate: G2.
50. **UI-006** — [Панели аналитика и администратора](tasks/UI-006.md); [prompt](luna_prompts/UI-006.md). Gate: G2.
51. **OPS-001** — [Структурированные логи, метрики и аудит](tasks/OPS-001.md); [prompt](luna_prompts/OPS-001.md). Gate: G2.
52. **SEC-001** — [Матрица авторизации и adversarial API тесты](tasks/SEC-001.md); [prompt](luna_prompts/SEC-001.md). Gate: G2.
53. **SEC-002** — [SSRF, prompt injection и вредоносные документы](tasks/SEC-002.md); [prompt](luna_prompts/SEC-002.md). Gate: G2.
54. **SEC-003** — [ПД, лицензии, retention и условия production](tasks/SEC-003.md); [prompt](luna_prompts/SEC-003.md). Gate: G2.
55. **LLM-003** — [Адаптер выбранного пользователем API и real evaluation](tasks/LLM-003.md); [prompt](luna_prompts/LLM-003.md). Gate: G2 + решение пользователя о provider.
56. **OPS-002** — [Согласованные backup и восстановление](tasks/OPS-002.md); [prompt](luna_prompts/OPS-002.md). Gate: G2.
57. **OPS-003** — [Production Compose, миграции и rollback rehearsal](tasks/OPS-003.md); [prompt](luna_prompts/OPS-003.md). Gate: G2.
58. **QA-003** — [Сквозная приёмка функционального MVP](tasks/QA-003.md); [prompt](luna_prompts/QA-003.md). Gate: G2.
59. **LOAD-001** — [Нагрузка 30 пользователей и пределы ресурсов](tasks/LOAD-001.md); [prompt](luna_prompts/LOAD-001.md). Gate: G2.
60. **REV-001** — [Независимый финальный аудит реализации](tasks/REV-001.md); [prompt](luna_prompts/REV-001.md). Gate: G3 + G4.
61. **REV-002** — [Исправления по результатам независимого аудита](tasks/REV-002.md); [prompt](luna_prompts/REV-002.md). Gate: G3 + G4.
62. **REV-003** — [Повторный аудит и итоговый статус](tasks/REV-003.md); [prompt](luna_prompts/REV-003.md). Gate: G3 + G4.

После QA-001 дождаться фактической приёмки G1; после QA-002 — G2. Если реального provider ещё нет, LLM-003 отмечается BLOCKED с owner=user и следующие независимые задачи продолжаются с Fake. Перед production real AI вернуться к LLM-003 и evaluation. REV задачи назначены архитектору/Luna по MASTER_PLAN, не поручать независимый аудит тому же исполнителю под новым названием.

Рутина после каждой задачи: актуальные dependencies → scoped changes → tests → report → status. Не переключать DONE до выполнения AC, не брать будущий scope для заполнения времени ожидания внешней зависимости.
