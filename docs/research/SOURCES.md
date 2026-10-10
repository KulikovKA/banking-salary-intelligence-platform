# Проверка внешних оснований — 09.10.2026

Эта заметка — исследовательский реестр, не юридическое заключение, не утверждение о тарифах и не production source registry. Поисковый индекс не заменяет target GET. Не публиковать тарифные значения без проверенных оригинала, даты действия, сегмента, пакета и области применения.

## Библиотеки и БД

| Основание | Что проверено | Проектное следствие |
|---|---|---|
| [PostgreSQL FTS indexes](https://www.postgresql.org/docs/16/textsearch-indexes.html) | Документация рекомендует GIN для text search | Предложен GIN, без отдельного поискового сервиса |
| [PostgreSQL text search controls](https://www.postgresql.org/docs/current/textsearch-controls.html) | tsvector, websearch_to_tsquery, ranking | Query parameterization, русская конфигурация и измерение recall |
| [PostgreSQL SELECT](https://www.postgresql.org/docs/current/sql-select.html) | Row locks и SKIP LOCKED | Предложен job leasing через короткие транзакции; fencing проектируется отдельно |
| [PyMuPDF licensing](https://pymupdf.io/licensing), [FAQ](https://pymupdf.readthedocs.io/en/latest/faq/index.html) | AGPL / commercial licensing | До включения получить решение по лицензии |
| [pdfplumber repository](https://github.com/jsvine/pdfplumber) | Python PDF extraction | Проверить качество на корпусе; proposed baseline при нерешённой лицензии PyMuPDF |

Выбор модульного монолита, sizing, quotas и критерии качества — инженерные предложения, а не утверждения из указанных источников. Интервал проверки банковских документов 24 часа — предварительная цель проекта, не rate limit банка.

## Банковские источники: техническая инвентаризация

Владелец проекта принял архитектуру v1.1, охват Сбер/ВТБ/Альфа-Банк/Кубань Кредит, регион RU-KDA, приоритет МСБ и локальное хранение originals вне Git. Это разрешает подготовку POC и ручной разбор, но не подтверждает разрешение банка на автоматический сбор. CAPTCHA, авторизация, anti-bot и явные ограничения не обходятся. Неясная допустимость автоматизации означает BLOCKED для конкретного URL. Полные записи см. в [SourceAcceptanceManifest](../../tests/fixtures/manifests/sources.json) и отчёте [SRC-001](../reports/SRC-001.md).

| Банк | Официальность / URL | Документы | Robots / terms и решение | Coverage RU-KDA / МСБ |
|---|---|---|---|---|
| Сбер | [SberAPI salary overview](https://developers.sber.ru/docs/ru/sber-api/scenarios/salary/salary-project/overview) на официальной документационной площадке. [SberBusiness article](https://sberbusiness.live/publications/zarplatnii-proekt-chto-eto-takoe-kak-vibrat-i-podklyuchit) ранее дал 200 без redirect, но контроль домена банком не доказан. | API docs — интеграция, не работодательский тариф; статья — не договор. Exact current tariff URL не найден. | sberbank.ru/robots.txt: TLS trust error. sberbusiness.live/robots.txt: HTTP 200; User-agent:* разрешает /publications/, запрещает /upload/. Terms/ownership не подтверждены. Автосбор BLOCKED. | Все 11 metrics и package — unknown; тариф работодателя не найден. |
| ВТБ | [Страница зарплатного проекта МСБ](https://www.vtb.ru/malyj-biznes/zarplatniy-proekt/) на www.vtb.ru, страница идентифицирует Банк ВТБ (ПАО). | Поисковый индекс перечисляет условия обслуживания с 01.09.2026 (1 MB), но прямой PDF URL и bytes не получены. | Target GET остановлен локальной TLS validation; web open timeout. vtb.ru/robots.txt — TLS/Web timeout. Применимые terms для salary page не найдены; developer.vtb.ru agreement относится к другому хосту. Автосбор BLOCKED. | Общие claims о бесплатных услугах/зачислении не подтверждают package или регион. Все 11 metrics — unknown. |
| Альфа-Банк | [Страница зарплатного проекта МСБ](https://alfabank.ru/sme/salaryproject/) на alfabank.ru. | Страница индексируется с документами; AЗОН указано с 22.06.2026, правила 19.04.2024 помещены в архив. Exact PDF URLs/bytes не получены. | Target GET остановлен TLS validation; web open internal error. alfabank.ru/robots.txt — TLS/Web timeout. Applicable terms не найдены. Автосбор BLOCKED. | Страница упоминает 1С/бесплатное открытие/перевод, но scope требует оригинала. Все 11 metrics — unknown. |
| Кубань Кредит | [FAQ PDF](https://kb.kk.bank/docs/Questions_answers.pdf) получен напрямую без redirect; PDF связывает host с официальным [kk.bank](https://kk.bank) и называет КБ «Кубань Кредит» ООО. | FAQ на 32 страницы описывает ДБО, документы и сроки карт — не тариф. Indexed [tariff album](https://vip.kk.bank/upload/iblock/25d/xhld81z4qxd9tmjlt9blm352fas17m0r.pdf) включает зарплатные карты сотрудников, но не полный тариф работодателя. FAQ сохранён вне Git; SHA-256 есть в manifest. | kb.kk.bank/robots.txt — 404; kk.bank, vip.kk.bank, promo.kk.bank robots недоступны из среды. Terms не установлены. start.kk.bank agreement относится к сервису ООО «ИСУ», не к сайту банка. Автосбор BLOCKED. | FAQ не тариф; employee-card tariffs не доказывают employer fee/package. Все 11 metrics — unknown. |

### Покрытие

Для каждого из четырёх банков все 11 показателей остаются unknown для RU-KDA и приоритетного сегмента МСБ: payroll_credit_fee, external_bank_transfer_fee, account_monthly_fee, employee_card_fee, cash_withdrawal_limit, transfer_limit, crediting_time, employee_privilege, premium_eligibility, integration_1c, integration_api. Package также unknown. Неизвестное значение не заменяется нулём или федеральным scope.

### Оригиналы и policy

Сохранён только публичный справочный FAQ Кубань Кредит: %LOCALAPPDATA%\BankingSalaryIntelligence\originals\kuban_credit\Questions_answers.pdf, SHA-256 08ced4b035c1a6b396a5d7143e1c635ac8ea20ed09c1f0726b60549df391a144. PDF metadata date 06.02.2025 не считается датой действия. Тарифные originals банков не получены/не одобрены, поэтому их значения не занесены.

Ни доступность страницы, ни robots Allow, ни отсутствие robots-файла не означают разрешение на automated retrieval/storage/reuse. Остаются правовые вопросы: bank-specific разрешение на автоматизацию и архив, применимые terms и лимиты для каждого host/path, лицензии/copyright на originals и извлечённые данные. Юридическое решение — отдельно у ответственного/юриста; решение владельца POC не заменяет разрешение банка. Интервал 24 часа не включать в scheduler до подтверждения применимых ограничений. Для blocked URL возможен ручной импорт официального документа.

Не исследованы и не выбраны LLM модели/поставщики. Будущие ПД, локализация, трансграничная передача, retention и передача внешнему LLM требуют отдельной правовой проверки.

## Дополнение к реестру — новые ссылки (2026-10-09)

Полные URL, redirect/MIME/hash evidence и decisions находятся в [SourceAcceptanceManifest](../../tests/fixtures/manifests/sources.json). Это исследовательская запись, не разрешение на сбор.

| Банк / URL | Классификация и наблюдение | Решение |
|---|---|---|
| [Кубань Кредит: salary-project page](https://kk.ru/business/solutions/zp-project/) | Локальный target GET: HTTP 200, final URL совпал, redirect chain пуст, HTML. Официальная страница перечисляет тариф от 01.06.2024 и отдельные условия обслуживания работодателя от 29.06.2026. | **Pending** для приёмки содержания; live collection **blocked** до применимых terms, bank-side permission и request limits. Robots не запрещает путь страницы. |
| [Кубань Кредит: зарплатный тариф PDF](https://kk.ru/upload/iblock/3cf/2aukz7j463jptle27m62oo8frs1x862x.pdf) | Кандидат на employer salary-project tariff; web preview показывает действие с 01.06.2024. Local original bytes и SHA-256 отсутствуют. | **Blocked**: `kk.ru/robots.txt` HTTP 200 явно запрещает `/upload/*.pdf` и `/upload/iblock/*.pdf`; target GET намеренно не выполнялся. |
| [Кубань Кредит: условия работодателя PDF](https://kk.ru/upload/iblock/973/96i8chqk1f794ldm6umaie424qnvoxhb.pdf) | Условия обслуживания работодателя, не самостоятельный тариф; web preview указывает вступление в силу 29.06.2026. Local original/hash отсутствует. | **Blocked** по тому же robots-запрету и неустановленному разрешению на сбор/хранение. |
| [ВТБ: salary-project page](https://www.vtb.ru/malyj-biznes/zarplatniy-proekt/) | Точный URL повторно проверен локально; TLS certificate validation завершилась ошибкой до HTTP response. `vtb.ru/robots.txt` не проверен из-за TLS. | **Blocked** технически и по неустановленным source terms/policy; TLS не обходился. |
| [Альфа-Банк: salary-project page](https://alfabank.ru/sme/salaryproject/) | Точный URL повторно проверен локально; TLS certificate validation завершилась ошибкой до HTTP response. `alfabank.ru/robots.txt` не проверен; TLS не обходился. | **Blocked** технически и по неустановленным source terms/policy. |

Наличие страницы или ссылки на PDF не означает согласие банка на автоматическое извлечение, хранение или повторное использование документа. Для новых PDF Кубань Кредит сохранение оригинала и SHA-256 отложены; preview не считается original. Все показатели RU-KDA × банк остаются `unknown`.
