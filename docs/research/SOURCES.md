# Проверка внешних оснований — 09.10.2026

Это предварительное исследование для проектирования, не завершённый аудит банковских тарифов, не source registry production и не доказательство стабильной работы адаптеров. Поисковый индекс и разовое открытие через web-инструмент не заменяют fetch с целевого российского host. Никакие банковские цены из поиска не перенесены в seed.

## Библиотеки и БД

| Основание | Что проверено | Проектное следствие |
|---|---|---|
| [PostgreSQL FTS indexes](https://www.postgresql.org/docs/16/textsearch-indexes.html) | Документация рекомендует GIN для text search | Предложен GIN, без отдельного поискового сервиса |
| [PostgreSQL text search controls](https://www.postgresql.org/docs/current/textsearch-controls.html) | tsvector, websearch_to_tsquery, ranking | Query parameterization, русская конфигурация и измерение recall |
| [PostgreSQL SELECT](https://www.postgresql.org/docs/current/sql-select.html) | row locks и SKIP LOCKED | Предложен job leasing через короткие транзакции; fencing проектируется отдельно |
| [PyMuPDF licensing](https://pymupdf.io/licensing), [FAQ](https://pymupdf.readthedocs.io/en/latest/faq/index.html) | AGPL / commercial licensing | До включения получить решение по лицензии; не трактовать internal use как автоматическое освобождение |
| [pdfplumber repository](https://github.com/jsvine/pdfplumber) | Python PDF extraction и доступный исходный проект | Проверить качество на корпусе; proposed baseline при нерешённой лицензии PyMuPDF |

Выбор модульного монолита, sizing, интервалы, quotas и критерии качества — инженерные предложения этого проекта, а не утверждения из указанных источников. Не выбраны и не исследованы финальные LLM модели/поставщики.

## Банковские источники: стартовая карта

| Банк | Найденный ресурс | Наблюдение и следующий шаг |
|---|---|---|
| Сбер | [SberAPI: зарплатный проект](https://developers.sber.ru/docs/ru/sber-api/scenarios/salary/salary-project/overview) | Официальная документация найдена в поиске. Подходит для проверки интеграционных возможностей; НЕ заменяет тарифы работодателя. Найти product/tariff documents и область действия в SRC-001/ING-001 |
| ВТБ | [Зарплатный проект для малого бизнеса](https://www.vtb.ru/malyj-biznes/zarplatniy-proekt/) | Прямое открытие web tool завершилось internal error. Это не доказательство недоступности банка. Требуется проверка целевым FetchGateway и сбор PDF links |
| Альфа-Банк | [Зарплатный проект](https://alfabank.ru/sme/salaryproject/), [API salary](https://developers.alfabank.ru/products/alfa-api/documentation/articles/salary/salary) | Индекс показывает страницу и ссылки на документы; прямое открытие product page дало 502 в инструменте. Доступ и полноту документов проверить в POC |
| Кубань Кредит | [FAQ ДБО](https://kb.kk.bank/docs/Questions_answers.pdf), [руководство](https://kb.kk.bank/docs/Manual.pdf) | Официальные поддоменные PDF найдены, но это руководства, а не достаточный тарифный корпус. Candidate product path `https://kk.bank/business/solutions/zp-project/` не открылся инструментом, не считать подтверждённым URL |

Поиск также вернул похожую страницу Кубань Кредит на постороннем домене. Она исключена: совпадение текста/логотипа не подтверждает официальный источник. Домены kb.kkbank.ru и kb.kk.bank нельзя молча считать взаимозаменяемыми: подтвердить связь и redirect chain при source policy review.

Source acceptance manifest будущей реализации: bank, url, final_url, parent/discovery URL, official-domain evidence, checked_at, http result, MIME, sha256, publication/effective dates with evidence, region/segment, robots/terms decision, parser result, retry result, reviewer. В этой стадии такого корпуса ещё нет; SRC-001 не DONE.

## Правовые основания и пределы проверки

Найдено опубликование изменений №23-ФЗ от 28.02.2025: [КонсультантПлюс, текст закона](https://www.consultant.ru/document/cons_doc_LAW_499984/), [статья 1](https://base.garant.ru/411574151/1cafb24d049dcd1e7707a22d98e9858f/), [дата вступления в силу](https://www.consultant.ru/document/cons_doc_LAW_499984/b62da3aeb315547b6915beadea02920bd7dd4c41/). Эти материалы подтверждают изменение правил локализации с 01.07.2025; они не заменяют проверку актуальной полной редакции закона для конкретного оператора.

Попытка открыть [официальную публикацию](https://publication.pravo.gov.ru/document/0001202502280034) завершилась timeout. [Страница РКН по трансграничной передаче](https://pd.rkn.gov.ru/cross-border-transmission/) также не прочитана инструментом. Старые найденные региональные памятки РКН содержат исторические исключения и не использованы как актуальное правовое заключение.

Поэтому: правомерность автоматического сбора с каждого банка, обработки ПД и передачи конкретному внешнему LLM НЕ объявлена проверенной. SEC-003/SRC-001 требуют актуальные условия и решение ответственного до запуска соответствующих потоков. Проектирование и mock tests могут идти без передачи ПД и без выбора API.
