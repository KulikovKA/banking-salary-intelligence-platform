> Детализация исходных 62 этапов. Актуальные единицы исполнения — 22 WORK-блока в [MASTER_PLAN](MASTER_PLAN.md). Исходные ID сохранены для трассировки требований. Старый порядок использовать только как справку; уровни reasoning см. в обновлённых ТЗ.

# MASTER PLAN — Banking Salary Intelligence Platform

Дата проектирования: 09.10.2026. Версия архитектуры: proposed v1.1, baseline Miro v1.0.

## Текущий статус

**Пакет проектирования подготовлен. Реализация не начата.** В исходной рабочей папке не было приложения; Git root находился в родительском пользовательском каталоге. Созданы только документы. Все 62 задач будущего исполнения имеют TODO. Нет выполненных source probes POC, quality evaluation, auth/security/load tests приложения. Финальный независимый аудит ещё не проводился.

Текущий этап: согласование G0. Следующий разрешаемый шаг после отдельного указания пользователя начать работу — SRC-001. Не назначать LLM provider автоматически. Нет необходимости согласовывать каждую рутинную задачу заново после разрешения этапа; gates требуют указанной приёмки.

## Навигация

- [Пакет A–J](../README.md), [Architecture Review](../architecture/ARCHITECTURE_REVIEW.md), [Overview](../architecture/OVERVIEW.md).
- [Доменные контракты](../architecture/DOMAIN_CONTRACTS.md), [БД](../architecture/DATABASE_DESIGN.md), [API](../architecture/API_CONTRACTS.md), [структура проекта](../architecture/PROJECT_STRUCTURE.md).
- [POC scope](POC_SCOPE.md), [MVP scope](MVP_SCOPE.md), [граф зависимостей](DEPENDENCIES.md), [точный порядок](EXECUTION_ORDER.md).
- [Приёмка](../product/ACCEPTANCE_CRITERIA.md), [eval](../quality/EVALUATION_PLAN.md), [риски](../quality/RISKS.md), [review](../quality/REVIEW_CHECKLIST.md).

## Phase → Epic → Task → Subtask

| Phase | Результат | Gate перехода |
|---|---|---|
| A0 | Источники и допустимость сбора | G0 разрешает начать; SRC-001 даёт исходную карту |
| A1 | Основа, архив, parsing, 4 адаптера | G1: repeatable official access, пользователь принимает QA-001 |
| A2 | Проверенные facts, FTS, comparison, evidence, Fake LLM, простой UI | G2: численные thresholds и coverage, пользователь принимает QA-002 |
| B1 | Auth, chats, bounded LLM gateway, monitoring/events/API | G2 обязателен; security/data decisions фиксируются |
| B2 | Полный UI и analyst/admin flows | G2 обязателен, B1 API prerequisites выполнены |
| B3 | Security, privacy, operations, отдельный real provider branch | G3 security и решения активных потоков |
| B4 | E2E, 30 users, независимый audit→fix→retest | G4 operations, G5 итоговый review и пользовательская приёмка |

Технические зависимости — IDs ниже. Внешние gates дополняют граф, но не маскируются fake задачами DONE. Tasks не XL; каждая содержит именованные Subtask IDs `TASK-001.01`… и проверяемые границы. При фактическом разрастании L разбить через обновление плана до реализации.

## Backlog

| ID / ТЗ | Задача | Phase / Epic | Dependencies | Исполнитель | Приоритет / сложность | Status | Критерий готовности | Prompt |
|---|---|---|---|---|---|---|---|---|
| [SRC-001](tasks/SRC-001.md) | Инвентаризация официальных источников и допустимости сбора | A0 / Источники | — | GPT-6 Luna — Reasoning | Critical / L | TODO | Четыре банковские строки с доказательствами официальности и решениями policy; пробелы покрытия перечислены, ни один непроверенный URL не approved | [prompt](luna_prompts/SRC-001.md) |
| [INF-001](tasks/INF-001.md) | Изолированный репозиторий и воспроизводимые инструменты | A1 / Основа | SRC-001 | GPT-6 Luna — Reasoning | Critical / M | TODO | Clean setup воспроизводится из README; нет изменений вне проекта; зависимости pinned | [prompt](luna_prompts/INF-001.md) |
| [INF-002](tasks/INF-002.md) | Validated config и локальное окружение POC | A1 / Основа | INF-001 | GPT-6 Luna — Reasoning | High / M | TODO | Ошибки конфигурации обнаруживаются до обработки запросов; example env не содержит секретов | [prompt](luna_prompts/INF-002.md) |
| [DB-001](tasks/DB-001.md) | Миграции каталога, blobs и job queue | A1 / База данных | INF-002 | GPT-6 Luna — Reasoning | Critical / M | TODO | Schema соответствует контракту, seed четырёх bank codes идемпотентен, migration SQL reviewed | [prompt](luna_prompts/DB-001.md) |
| [STO-001](tasks/STO-001.md) | Неизменяемое файловое хранилище оригиналов | A1 / Архив | DB-001 | GPT-6 Luna — Reasoning | Critical / M | TODO | Оригинал никогда не перезаписывается; race даёт один blob; ни один committed ref не указывает на partial file | [prompt](luna_prompts/STO-001.md) |
| [NET-001](tasks/NET-001.md) | Безопасный FetchGateway с условными запросами | A1 / Сбор | STO-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | Ни один forbidden destination не получает запрос; observation сохранены; repeat304 не дублирует version | [prompt](luna_prompts/NET-001.md) |
| [JOB-001](tasks/JOB-001.md) | Cron enqueue, leases и повтор фоновых задач | A1 / Сбор | NET-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | Повтор запуска не создаёт duplicate jobs; истёкшая lease восстанавливается; all transitions проверены | [prompt](luna_prompts/JOB-001.md) |
| [HTML-001](tasks/HTML-001.md) | HTML extraction с сохранением значимого текста | A1 / Обработка | NET-001 | GPT-6 Luna — Reasoning | High / M | TODO | Оформление не меняет canonical meaning; значимая сноска и отрицание сохранены; HTML не имеет PDF page | [prompt](luna_prompts/HTML-001.md) |
| [PDF-001](tasks/PDF-001.md) | PDF extraction постранично и контроль качества | A1 / Обработка | STO-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | Каждая извлечённая страница связана с оригиналом; нет выдуманных page labels; выбранная лицензия отражена | [prompt](luna_prompts/PDF-001.md) |
| [DB-002](tasks/DB-002.md) | Миграции документов, страниц и chunks | A1 / База данных | DB-001 | GPT-6 Luna — Reasoning | High / M | TODO | Upgrade сохраняет catalog/blobs, family/version/extraction semantics разделены | [prompt](luna_prompts/DB-002.md) |
| [TXT-001](tasks/TXT-001.md) | Chunking, сноски и точная привязка evidence | A1 / Обработка | HTML-001, PDF-001, DB-002 | GPT-6 Luna — Reasoning | Critical / M | TODO | Quote offsets разрешаются в exact text; все pages accounted; неоднозначности видимы downstream | [prompt](luna_prompts/TXT-001.md) |
| [VER-001](tasks/VER-001.md) | Разделение raw, canonical и parser версий | A1 / Версии | TXT-001, JOB-001 | GPT-6 Luna — Reasoning | High / M | TODO | Все три причины изменения различимы; старые ответы смогут открыть прежний extraction | [prompt](luna_prompts/VER-001.md) |
| [ING-001](tasks/ING-001.md) | Адаптер банка Сбер | A1 / Банковские адаптеры | SRC-001, VER-001 | GPT-6 Luna — Reasoning | Critical / M | TODO | Сбер использует единый pipeline; минимум один настоящий tariff/conditions original получен; покрытие и все нераспознанные поля отражены | [prompt](luna_prompts/ING-001.md) |
| [ING-002](tasks/ING-002.md) | Адаптер банка ВТБ | A1 / Банковские адаптеры | SRC-001, VER-001 | GPT-6 Luna — Reasoning | Critical / M | TODO | ВТБ использует единый pipeline; минимум один настоящий tariff/conditions original получен; покрытие и все нераспознанные поля отражены | [prompt](luna_prompts/ING-002.md) |
| [ING-003](tasks/ING-003.md) | Адаптер банка Альфа-Банк | A1 / Банковские адаптеры | SRC-001, VER-001 | GPT-6 Luna — Reasoning | Critical / M | TODO | Альфа-Банк использует единый pipeline; минимум один настоящий tariff/conditions original получен; покрытие и все нераспознанные поля отражены | [prompt](luna_prompts/ING-003.md) |
| [ING-004](tasks/ING-004.md) | Адаптер банка Кубань Кредит | A1 / Банковские адаптеры | SRC-001, VER-001 | GPT-6 Luna — Reasoning | Critical / M | TODO | Кубань Кредит использует единый pipeline; минимум один настоящий tariff/conditions original получен; покрытие и все нераспознанные поля отражены | [prompt](luna_prompts/ING-004.md) |
| [QA-001](tasks/QA-001.md) | Gate G1: повторяемость получения четырёх банков | A1 / Проверка источников | ING-001, ING-002, ING-003, ING-004 | GPT-6 Luna — Reasoning | Critical / M | TODO | Собраны реальные доказательства G1 или точный NO-GO без выдуманного успеха; решение пользователя записано | [prompt](luna_prompts/QA-001.md) |
| [DB-003](tasks/DB-003.md) | Миграции фактов, evidence и публикаций | A2 / База данных | DB-002 | GPT-6 Luna — Reasoning | Critical / M | TODO | Schema допускает историю и conflict, запрещает dangling evidence и повтор кандидата | [prompt](luna_prompts/DB-003.md) |
| [FACT-001](tasks/FACT-001.md) | Нормализованные DTO тарифов и applicability | A2 / Факты | DB-003 | GPT-6 Luna — Reasoning | Critical / M | TODO | Нормализация воспроизводима и не добавляет недостающих дат/чисел | [prompt](luna_prompts/FACT-001.md) |
| [FACT-002](tasks/FACT-002.md) | Извлечение кандидатов по правилам и provenance | A2 / Факты | FACT-001, QA-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | Каждый candidate объясним quote+rule version; missing fields не выдуманы; gold metrics рассчитаны | [prompt](luna_prompts/FACT-002.md) |
| [FACT-003](tasks/FACT-003.md) | Валидация и решения аналитика | A2 / Факты | FACT-002 | GPT-6 Luna — Reasoning | Critical / M | TODO | Нельзя одобрить некорректное evidence; решения append-only; disputed candidate не появляется в published queries | [prompt](luna_prompts/FACT-003.md) |
| [FACT-004](tasks/FACT-004.md) | Атомарная публикация и выбор действующих фактов | A2 / Факты | FACT-003, VER-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | Snapshot selection воспроизводим; old versions доступны; conflicted/stale данные не становятся безусловным winner | [prompt](luna_prompts/FACT-004.md) |
| [SRCH-001](tasks/SRCH-001.md) | PostgreSQL FTS с фильтрами и оценкой поиска | A2 / Поиск | TXT-001, FACT-004 | GPT-6 Luna — Reasoning | High / M | TODO | Результаты открывают правильную версию; SQL injection невозможен через query string; metrics report сохранён | [prompt](luna_prompts/SRCH-001.md) |
| [CMP-001](tasks/CMP-001.md) | Совместимость предложений и трёхзначные условия | A2 / Сравнение | FACT-004 | GPT-6 Luna — Reasoning | Critical / M | TODO | Несовместимые предложения никогда не дают численного преимущества; missing inputs перечислены | [prompt](luna_prompts/CMP-001.md) |
| [CMP-002](tasks/CMP-002.md) | Детерминированные формулы и доказательства обеих сторон | A2 / Сравнение | CMP-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | 100% golden arithmetic/status; ни одно преимущество без доказательств обоих банков | [prompt](luna_prompts/CMP-002.md) |
| [LLM-001](tasks/LLM-001.md) | Провайдерский Protocol и Fake LLM | A2 / LLM | FACT-001 | GPT-6 Luna — Reasoning | High / M | TODO | Offline suite работает без секретов; замена provider не требует изменения comparison/parser | [prompt](luna_prompts/LLM-001.md) |
| [AI-001](tasks/AI-001.md) | Intent и безопасные read-only инструменты | A2 / Ассистент | SRCH-001, CMP-002, LLM-001 | GPT-6 Luna — Reasoning | High / M | TODO | Инструменты читают только разрешённые данные; POC intent не требует real API | [prompt](luna_prompts/AI-001.md) |
| [AI-002](tasks/AI-002.md) | Claim validation и evidence-first renderer | A2 / Ассистент | AI-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | Все существенные предложения отображают проверенные claims; unknown не ноль; поддельное утверждение не выходит | [prompt](luna_prompts/AI-002.md) |
| [DOC-001](tasks/DOC-001.md) | API метаданных и полный оригинал по UUID | A2 / Документы | VER-001 | GPT-6 Luna — Reasoning | Critical / M | TODO | Открывается именно цитированная версия целиком; PDF page основана на physical_page | [prompt](luna_prompts/DOC-001.md) |
| [API-001](tasks/API-001.md) | POC routes сравнения, поиска и вопроса | A2 / API | AI-002, DOC-001 | GPT-6 Luna — Reasoning | Critical / M | TODO | Один реальный question→источники сценарий проходит с Fake без network API | [prompt](luna_prompts/API-001.md) |
| [UI-001](tasks/UI-001.md) | Минимальный экран POC: вопрос, таблица, оригинал | A2 / POC UI | API-001 | GPT-6 Luna — Reasoning | High / M | TODO | POC пользователь видит таблицу и открывает полный доказательный документ; real API не требуется | [prompt](luna_prompts/UI-001.md) |
| [QA-002](tasks/QA-002.md) | Gate G2: оценка технического ядра POC | A2 / Приёмка POC | UI-001, QA-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | Доказано ядро или честно зафиксирован NO-GO; полный MVP начинается только после G2 | [prompt](luna_prompts/QA-002.md) |
| [DB-004](tasks/DB-004.md) | Миграции auth, чатов, usage и idempotency | B1 / База данных | QA-002, DB-003 | GPT-6 Luna — Reasoning | Critical / M | TODO | POC facts сохраняются; schema поддерживает auth/async chats без дублирования originals | [prompt](luna_prompts/DB-004.md) |
| [AUTH-001](tasks/AUTH-001.md) | Приглашения, пароли и bootstrap Admin | B1 / Авторизация | DB-004 | GPT-6 Luna — Reasoning | Critical / M | TODO | Только invite registration; token raw не в DB; no public signup | [prompt](luna_prompts/AUTH-001.md) |
| [AUTH-002](tasks/AUTH-002.md) | Сессии, CSRF и лимиты входа | B1 / Авторизация | AUTH-001 | GPT-6 Luna — Reasoning | Critical / M | TODO | Закрытые endpoints не доступны без session; cookies и limits соответствуют контракту | [prompt](luna_prompts/AUTH-002.md) |
| [AUTH-003](tasks/AUTH-003.md) | RBAC и object ownership во всех сервисах | B1 / Авторизация | AUTH-002, DOC-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | Authorization enforced backend на каждом endpoint; UI checks не единственная защита | [prompt](luna_prompts/AUTH-003.md) |
| [LLM-002](tasks/LLM-002.md) | Gateway, budgets, redaction и отказоустойчивость | B1 / LLM | DB-004, LLM-001, AUTH-003 | GPT-6 Luna — Reasoning | Critical / L | TODO | Hard caps не превышены гонкой; запрещённые поля не выходят; mock tests покрывают provider outages | [prompt](luna_prompts/LLM-002.md) |
| [CHAT-001](tasks/CHAT-001.md) | Хранение собственной истории и удаление | B1 / Чаты | AUTH-003, DB-004 | GPT-6 Luna — Reasoning | Critical / M | TODO | История личная; удалённые сообщения не читаются и не возвращаются поздним worker | [prompt](luna_prompts/CHAT-001.md) |
| [CHAT-002](tasks/CHAT-002.md) | Структурированная память и разрешение ссылок | B1 / Чаты | CHAT-001, AI-001 | GPT-6 Luna — Reasoning | Critical / M | TODO | Память сохраняет выбор, а факты всегда перечитываются; concurrency не затирает context | [prompt](luna_prompts/CHAT-002.md) |
| [AI-003](tasks/AI-003.md) | Асинхронный ответ и сохранение согласованного snapshot | B1 / Ассистент | CHAT-002, LLM-002, AI-002, JOB-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | Один вопрос имеет один результат; snapshot воспроизводим, нет long DB transaction during network | [prompt](luna_prompts/AI-003.md) |
| [DB-005](tasks/DB-005.md) | Миграции событий, outbox, подписок и аудита | B1 / База данных | DB-004, FACT-004 | GPT-6 Luna — Reasoning | High / M | TODO | Schema обеспечивает transactional event creation и повторяемую доставку | [prompt](luna_prompts/DB-005.md) |
| [CHG-001](tasks/CHG-001.md) | Содержательный diff и активация будущих условий | B1 / Изменения | DB-005, FACT-004 | GPT-6 Luna — Reasoning | Critical / L | TODO | Tariff events только подтверждённые; repeated worker не дублирует activation | [prompt](luna_prompts/CHG-001.md) |
| [NTF-001](tasks/NTF-001.md) | Подписки и идемпотентные уведомления внутри сайта | B1 / Изменения | CHG-001, AUTH-003 | GPT-6 Luna — Reasoning | High / M | TODO | Один event максимум одна карточка пользователю; внешних отправок нет | [prompt](luna_prompts/NTF-001.md) |
| [JOB-002](tasks/JOB-002.md) | Диагностика парсеров и freshness | B1 / Мониторинг | CHG-001, JOB-001 | GPT-6 Luna — Reasoning | High / M | TODO | Admin отличает доступность источника от успешной обработки; freshness доступна UI | [prompt](luna_prompts/JOB-002.md) |
| [API-002](tasks/API-002.md) | REST MVP: review, администрация и сводки | B1 / API | AI-003, NTF-001, JOB-002, AUTH-003 | GPT-6 Luna — Reasoning | Critical / L | TODO | Все заявленные MVP endpoints существуют и авторизованы; frontend types генерируются из одной схемы | [prompt](luna_prompts/API-002.md) |
| [UI-002](tasks/UI-002.md) | Каркас кабинета, вход и навигация по ролям | B2 / Frontend | API-002, UI-001 | GPT-6 Luna — Reasoning | High / M | TODO | Закрытый кабинет доступен только после auth; navigation не заменяет backend authorization | [prompt](luna_prompts/UI-002.md) |
| [UI-003](tasks/UI-003.md) | Чат MVP, история и context controls | B2 / Frontend | UI-002, AI-003 | GPT-6 Luna — Reasoning | High / M | TODO | Один submit соответствует одному run; вся собственная история и ограничения читаемы | [prompt](luna_prompts/UI-003.md) |
| [UI-004](tasks/UI-004.md) | Сравнения и каталог оригинальных документов | B2 / Frontend | UI-002, CMP-002, DOC-001 | GPT-6 Luna — Reasoning | High / M | TODO | Каждый существенный результат связан с правильным источником; UI не пересчитывает тарифы | [prompt](luna_prompts/UI-004.md) |
| [UI-005](tasks/UI-005.md) | Dashboard, лента изменений и настройки подписок | B2 / Frontend | UI-002, NTF-001, JOB-002 | GPT-6 Luna — Reasoning | High / M | TODO | Лента не смешивает технические и подтверждённые тарифные изменения; настройки персональны | [prompt](luna_prompts/UI-005.md) |
| [UI-006](tasks/UI-006.md) | Панели аналитика и администратора | B2 / Frontend | UI-002, API-002 | GPT-6 Luna — Reasoning | High / L | TODO | Ручная проверка выполнима по оригиналу; admin не получает лишние данные | [prompt](luna_prompts/UI-006.md) |
| [OPS-001](tasks/OPS-001.md) | Структурированные логи, метрики и аудит | B3 / Эксплуатация | API-002 | GPT-6 Luna — Reasoning | High / M | TODO | Операционные сбои диагностируемы без чтения персональных сообщений | [prompt](luna_prompts/OPS-001.md) |
| [SEC-001](tasks/SEC-001.md) | Матрица авторизации и adversarial API тесты | B3 / Безопасность | UI-006, OPS-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | Нет неизвестных или непроверенных routes; все prohibited accesses отвергнуты | [prompt](luna_prompts/SEC-001.md) |
| [SEC-002](tasks/SEC-002.md) | SSRF, prompt injection и вредоносные документы | B3 / Безопасность | SEC-001, LLM-002 | GPT-6 Luna — Reasoning | Critical / L | TODO | Весь attack suite без запрещённых effects; high issues устранены | [prompt](luna_prompts/SEC-002.md) |
| [SEC-003](tasks/SEC-003.md) | ПД, лицензии, retention и условия production | B3 / Безопасность | OPS-001, SRC-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | Активные потоки имеют владельца/правовое решение, политика удаления реализована и проверена | [prompt](luna_prompts/SEC-003.md) |
| [LLM-003](tasks/LLM-003.md) | Адаптер выбранного пользователем API и real evaluation | B3 / LLM | LLM-002, SEC-003, QA-002 | GPT-6 Luna — Reasoning | High / L | TODO | Утверждённый provider проходит contracts и evaluation; иначе feature остаётся выключенной | [prompt](luna_prompts/LLM-003.md) |
| [OPS-002](tasks/OPS-002.md) | Согласованные backup и восстановление | B3 / Эксплуатация | SEC-003, STO-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | Восстановление действительно выполнено, RPO/RTO измерены и evidence цело | [prompt](luna_prompts/OPS-002.md) |
| [OPS-003](tasks/OPS-003.md) | Production Compose, миграции и rollback rehearsal | B3 / Эксплуатация | OPS-002, OPS-001, SEC-002 | GPT-6 Luna — Reasoning | Critical / L | TODO | Развёртывание воспроизводимо без потери данных; rollback проверен на staging | [prompt](luna_prompts/OPS-003.md) |
| [QA-003](tasks/QA-003.md) | Сквозная приёмка функционального MVP | B4 / Приёмка MVP | UI-003, UI-004, UI-005, UI-006, OPS-003 | GPT-6 Luna — Reasoning | Critical / L | TODO | Сквозные P0 scenarios green; evidence/report воспроизводим, skips обоснованы | [prompt](luna_prompts/QA-003.md) |
| [LOAD-001](tasks/LOAD-001.md) | Нагрузка 30 пользователей и пределы ресурсов | B4 / Приёмка MVP | QA-003 | GPT-6 Luna — Reasoning | High / L | TODO | Цели достигнуты на указанном host либо честно отмечены ограничения для решения пользователя | [prompt](luna_prompts/LOAD-001.md) |
| [REV-001](tasks/REV-001.md) | Независимый финальный аудит реализации | B4 / Независимый аудит | LOAD-001, SEC-001, SEC-002, SEC-003 | Astra — независимый review | Critical / L | TODO | Все пункты оценены; findings пригодны для исправления; никаких необоснованных READY | [prompt](luna_prompts/REV-001.md) |
| [REV-002](tasks/REV-002.md) | Исправления по результатам независимого аудита | B4 / Независимый аудит | REV-001 | GPT-6 Luna — Reasoning | Critical / L | TODO | Все Critical/High исправлены с доказательствами либо явно BLOCKED; remaining limitations перечислены | [prompt](luna_prompts/REV-002.md) |
| [REV-003](tasks/REV-003.md) | Повторный аудит и итоговый статус | B4 / Независимый аудит | REV-002 | Astra — независимый review | Critical / M | TODO | Итоговый статус соответствует реальным gates; mock vs real AI различены | [prompt](luna_prompts/REV-003.md) |


## Правила статусов и отчётов

TODO → IN_PROGRESS после проверки prerequisites. BLOCKED требует конкретной причины, owner и следующего действия (например выбор provider пользователем). DONE требует tests/AC и `docs/reports/ID.md`. Не обновлять статусы на основании только написанного кода. Изменять эту таблицу и TASK_INDEX.json синхронно, ТЗ — при изменении контракта.

LLM-003 может оставаться BLOCKED при работе с Fake. Для технического MVP это допустимо только как явно принятая limitation. Для реального AI обязательны completion LLM-003 и повтор frozen evaluation. REV-001/003 исполняет независимый архитектор Astra; остальные задачи Luna, пользователь принимает принципиальные изменения/gates.

## Решения перед исполнением

G0: согласовать ADR proposals, scope SME/RU-KDA и этапность. G1: принять реальную доступность/полноту источников. До PDF-001: license decision или documented pdfplumber baseline. До production: hosting/retention/legal ownership. Перед LLM-003: явный provider/model/API/data-policy выбор. Эти решения не нужны для того, чтобы прочитать и проверить готовый пакет документации.
