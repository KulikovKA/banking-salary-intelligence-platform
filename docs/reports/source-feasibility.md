# Source feasibility — SRC-001

**Проверено:** 2026-10-09. **Статус:** BLOCKED для автоматического сбора; техническая инвентаризация выполнена частично. **Архитектура:** v1.1 принята. **Область:** Сбер, ВТБ, Альфа-Банк, Кубань Кредит; RU-KDA; приоритет МСБ.

Это SourceAcceptanceManifest с URL-кандидатами и доказательствами, а не юридическое заключение или разрешение на сбор. Решение владельца о локальном хранении/предварительной частоте не подтверждает разрешение банка. Цель проверки раз в 24 часа условна и подчиняется robots, условиям и ограничениям каждого сайта. CAPTCHA, авторизация, anti-bot и явные запреты не обходились.

## Итоговые статусы SourceAcceptanceManifest

- **Approved:** один URL — FAQ Кубань Кредит как ручной справочный оригинал, не тариф. Автоматический повторный сбор этого URL всё равно BLOCKED.
- **Pending:** SberAPI (официальная интеграционная справка, не тариф); статья sberbusiness.live (принадлежность домена не подтверждена); точный URL employer-тарифа Сбера; прямой URL условий ВТБ, документов Альфа и их применимость/дата.
- **Blocked:** автоматическая загрузка продуктовых страниц ВТБ/Альфа и PDF Кубань Кредит (руководство, альбом тарифов карт сотрудников, общий RKO тариф), а также URL с неустановленными правилами. Причины — bank-side permission/terms не подтверждены, robots/target GET не проверены или целевой TLS недоступен из этой среды. Для каждого такого источника предлагается ручной импорт официального документа, полученного оператором.

Полный manifest: [tests/fixtures/manifests/sources.json](../../tests/fixtures/manifests/sources.json). Историческая карта обновлена в [docs/research/SOURCES.md](../archive/pre-snapshot/research/SOURCES.md).

## Проверка доменов, URL и документов

| Банк/кандидат | Target GET, конечный URL и результат | Документ/официальность | Решение |
|---|---|---|---|
| Сбер developers.sber.ru | Web search/open распознал страницу; локальный direct GET завершился TLS EOF. Final URL не подтверждён целевым GET. | Официальная SberAPI документация описывает интеграцию, не тариф работодателя. | Источник pending; auto-fetch blocked до применимых условий. |
| Сбер sberbusiness.live | Ранее HTTP 200, text/html, без redirect; повторный GET не делался. | Информационная статья; robots file — 200. User-agent:* разрешает /publications/, запрещает /upload/. Владение доменом банком не доказано независимой официальной ссылкой. | Pending official-domain evidence; не тариф. Robots не является разрешением. |
| Сбер www.sberbank.ru/robots.txt | TLS trust error; web tool не получил файл. | Directives неизвестны; применимые terms не найдены. | Автоматический сбор blocked. |
| ВТБ product URL | https://www.vtb.ru/malyj-biznes/zarplatniy-proekt/; локальный TLS validation failed, web-open timeout, поэтому final URL/redirects unknown. | Поиск показывает условия зарплатного проекта с 01.09.2026, но original URL/bytes не получены. Основной домен и страница идентифицируют Банк ВТБ (ПАО). | Автоматизация blocked; нужен ручной импорт условий с 01.09.2026. |
| ВТБ robots/terms | Robots локально TLS failed, web timeout. Применимые terms для salary page www.vtb.ru не найдены. | Найденное соглашение developer.vtb.ru относится к другому хосту. | Нельзя вывести разрешение или rate limit. |
| Альфа product URL | https://alfabank.ru/sme/salaryproject/; local TLS validation failed, web-open internal error; final URL/redirect неизвестны. | Индекс показывает current docs и архивные правила от 19.04.2024, но точные PDF URLs/bytes не получены. | Автоматизация blocked; запросить текущий original вручную. |
| Альфа robots/terms | Robots TLS failed, web timeout; применимые terms не найдены. | Частота и автоматический доступ не подтверждены. | Blocked. |
| Кубань kb.kk.bank/docs/Questions_answers.pdf | Direct GET 200; final URL равен requested, redirects нет; application/pdf, 2,300,172 bytes. | Сам PDF связывает kb.kk.bank с официальным https://kk.bank, идентифицирует КБ «Кубань Кредит» ООО. FAQ ДБО на 32 страницы, не тариф. | Approved как ручной справочный original; автоматический fetch blocked из-за неустановленных terms. |
| Кубань kb.kk.bank/docs/Manual.pdf | Target GET завершился TLS EOF; final URL/bytes неизвестны. | Candidate manual, не тариф. | Blocked; auth не пробовалась. Предложить ручной импорт. |
| Кубань vip.kk.bank/...25d/xhld81...pdf | Search index показывает PDF; локальный GET TLS EOF. Final URL, дата и bytes unknown. | Индекс называет «Альбом тарифов»; глава по зарплатным картам относится к картам работников, не полному тарифу работодателя. | Автоматизация blocked; robots/terms недоступны. |
| Кубань promo.kk.bank/...830/...pdf | Search index candidate, direct GET TLS EOF. | Общий SME RKO tariff; точный scope зарплатного проекта не подтверждён. | Автоматизация blocked; facts не извлекать. |

### Robots, terms и принадлежность URL

- Успешно прочитан sberbusiness.live/robots.txt (200). User-agent:* не запрещает найденный article path, но запрещает /upload/; это не разрешение банка.
- kb.kk.bank/robots.txt ответил 404. Robots Сбера, ВТБ, Альфа-Банка, kk.bank, vip.kk.bank и promo.kk.bank не удалось прочитать (TLS errors/EOF, web timeout или unavailable). Не трактовать неизвестные директивы как allow.
- Применимые website terms целевых salary-hosts не установлены. Соглашение developer-сайта ВТБ и start.kk.bank/user_agreement не относятся к страницам зарплатного продукта; они исключены.
- Конечный URL/redirect chain доказан прямым GET только для статьи SberBusiness и FAQ Кубань Кредит. Для текущих тарифных/product pages цепочки остаются unknown.

## Оригиналы и SHA-256

Сохранён оригинал FAQ Кубань Кредит вне Git и публичного доступа: %LOCALAPPDATA%\BankingSalaryIntelligence\originals\kuban_credit\Questions_answers.pdf. SHA-256: 08ced4b035c1a6b396a5d7143e1c635ac8ea20ed09c1f0726b60549df391a144. PDF CreationDate/ModDate — 06.02.2025, это не effective date. Проверены HTTP 200, MIME, PDF magic и содержание локально. FAQ помогает подтвердить происхождение и описать процесс, но не проходит критерий employer tariff/conditions. Другие originals не сохранялись, поскольку target GET, правовой режим или ссылки не подтверждены. Originals не находятся в Git.

## Покрытие RU-KDA / МСБ

Матрица — 4 банка × 11 показателей; все 44 значения и пакет остаются unknown: payroll_credit_fee, external_bank_transfer_fee, account_monthly_fee, employee_card_fee, cash_withdrawal_limit, transfer_limit, crediting_time, employee_privilege, premium_eligibility, integration_1c, integration_api.

Публичные claims — только leads: ВТБ — условия с датой 01.09.2026 в поисковом индексе; Альфа — МСБ-страница, 1С и документ АЗОН от 22.06.2026; Кубань Кредит — FAQ со сроками/шагами и отдельный альбом тарифов карт сотрудников. Ни один claim не принят как региональный/договорный факт без оригинала, даты действия, пакета и проверенного RU-KDA scope. У Сбера актуальный публичный тариф работодателя не найден. Unknown не заменён на ноль или федеральное значение.

## Неразрешённые правовые вопросы

1. Разрешает ли каждый банк автоматическое получение конкретных страниц/PDF и локальное архивирование под применимыми terms и условиями самого документа?
2. Какие host/path limits действуют и допустима ли цель 24 часа? Не установлено; частота 24 часа пока не включается в планировщик.
3. Какие авторско-правовые/лицензионные условия применяются к originals, extracted tables и повторному использованию фактов?
4. Для будущих ПД и внешней LLM нужны отдельные проверка legal basis оператора, локализации/передачи и retention. В этом corpus ПД сотрудников не собирались.

Эти решения не заменяются согласием владельца проекта и не являются юридическим заключением. Пока bank-side permissibility не подтверждена, URL остаются BLOCKED для автоматической загрузки. Вариант продолжения — ручной импорт официального документа после получения оператором.

## Дополнительные официальные ссылки (2026-10-09)

Кубань Кредит: `https://kk.ru/business/solutions/zp-project/` из рабочей среды дал HTTP 200 и тот же final URL без редиректов. Официальная страница указывает «Тарифы зарплатные проекты с 01.06.2024» и отдельные «Условия обслуживания предприятия с 29.06.2026». Это разные документы: первый — тарифный кандидат, второй — условия обслуживания, не самостоятельный тариф. Web preview показывает текст/метаданные; PDF bytes не получены в локальный архив и SHA-256 отсутствует.

`https://kk.ru/robots.txt` локально ответил HTTP 200. Для User-agent `*` указаны `Disallow: /upload/*.pdf` и `Disallow: /upload/iblock/*.pdf`; обе новые PDF-ссылки попадают под запрет. Их target GET после чтения robots намеренно не выполнялся. Страница продукта этим правилом не закрыта, но доступность страницы не является разрешением на автоматический сбор. В manifest страница помечена pending, оба PDF — blocked.

Точные пользовательские страницы ВТБ и Альфа-Банка повторно проверены из среды: TLS certificate validation прерывает соединение до HTTP response; их robots.txt также не удалось проверить. TLS verification не отключалась, защиты не обходились. URL, результаты и пустые `final_url`/SHA-256 отражены в manifest.

## Разделение блокеров

**Технические:** TLS trust/path для ВТБ и Альфа не позволяет установить HTTP status, redirects, robots или скачать оригиналы; robots блокирует автоматическое получение двух PDF Кубань Кредит; точный текущий тариф Сбера и разрешённые оригиналы не подтверждены. PostgreSQL integration в рабочей среде невозможна до запуска Docker daemon.

**Юридические/организационные:** не получены bank-side permission и применимые terms на автоматическое получение и локальное хранение по host/path; не подтверждены частотные лимиты и допустимость предварительной цели 24 часа; нужны решения юриста/владельца об авторском праве и повторном использовании extracted facts; требуются текущие employer tariff/conditions с сегментом МСБ, пакетом и RU-KDA applicability. Пользовательское согласование не заменяет разрешение банка.

Покрытие не изменилось: 44 ячейки RU-KDA × банк × тарифный показатель и package остаются `unknown`; значения не заменяются нулями или неподтверждёнными превью.
