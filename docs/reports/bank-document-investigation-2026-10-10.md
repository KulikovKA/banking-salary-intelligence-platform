# Независимое расследование банковских источников — 10.10.2026

## Результат

Техническая возможность получать реальные тарифные originals доказана для Кубань Кредит: два исходных PDF получены с проверкой TLS, извлечены и визуально просмотрены релевантные страницы. Для ВТБ получены HTML продукта и каталога, найдены точные актуальные ссылки на PDF и XLSX. PDF/XLSX ВТБ не запрашивались: robots запрещает их исследовательскому клиенту. Для Альфа-Банка и Сбера исправление TLS проверено, но обнаружились HTTP/WAF ограничения. Полное покрытие четырёх банков и G1/G2 не достигнуты.

Это исследование по текущему поручению пользователя, не запуск production ingestion. Никакие источники автоматически не одобрены, реальные факты в БД не импортированы. MASTER_PLAN, ADR и существующий SourceAcceptanceManifest не менялись. В рабочем дереве до исследования уже были пользовательские изменения; они сохранены.

Originals, сырые robots, HTML, цепочки сертификатов, JSON-результаты и изображения для проверки находятся вне Git:

`C:\Users\Kirill\AppData\Local\BankingSalaryIntelligence\investigations\2026-10-10`

## A. Root Cause Analysis

| Проверяемая причина | Фактическое наблюдение | Вывод |
|---|---|---|
| Python/certifi против Windows trust | Python 3.11.9, OpenSSL 3.0.13; установлен httpx2 2.13.1 и truststore 0.10.4. httpx и certifi исходно отсутствовали. Код httpx2 `_config.py` уже выбирает truststore по умолчанию. | Совет просто добавить truststore недостаточен. Документацию httpx нельзя автоматически переносить на установленный httpx2. |
| Недоверенный корень Альфа/Сбер | stdlib для Альфа: verify_code 19, self-signed certificate in certificate chain; truststore для Альфа/Сбер: 2148204809 = 0x800B0109; Windows curl: SEC_E_UNTRUSTED_ROOT. .NET отверг цепочки с Russian Trusted Sub CA / Russian Trusted Root CA. | Это подтверждённая проблема отсутствия доверия к НУЦ в данном окружении. Она воспроизводится вне Python. |
| Исправление CA | Официальный root загружен по HTTPS с gu-st.ru с обычной проверкой TLS. `certifi + load_verify_locations(root)` обеспечивает TLS 1.3 и проверку hostname для Альфа/Сбер. `truststore + root` отдельно проверен на Альфа. | SSL verification отключать не требуется. Системное хранилище Windows не изменялось. |
| ВТБ | Были handshake timeout/EOF; .NET отдельно получил *.vtb.ru с Russian Trusted Sub CA, но PartialChain. После добавления root HTTP-клиент получил robots и две HTML-страницы с 200. Сырой TLS probe в одном запуске ещё дал timeout, хотя отдельный HTTP GET удался. | Есть проблема CA и непостоянная доступность handshake. EOF/timeout сами по себе не доказывают ошибку доверия, причину нестабильности пока нельзя приписать банку или сети. |
| Альфа после TLS fix | robots.txt отвечает 403, text/html, 1294 bytes. Целевой product GET остановлен до отправки. | TLS решён, автоматический доступ остаётся заблокирован/неустановлен. 403 нельзя устранить добавлением CA. |
| Сбер после TLS fix | robots.txt: 200, text/html, 1579 bytes; в теле `serviceName:'waf', code:'user_blocked'`. Это HTML ошибки, не robots. | HTTP 200 не означает успешное получение документа. Дальнейший автоматический обход не выполнялся. |
| Кубань robots | В полученном файле `User-Agent: *` заканчивается перед `User-Agent: Yandex`. Оба PDF Disallow стоят внутри последней группы Yandex. Protego 0.7.0: наш UA разрешён, Yandex запрещён. | Прежний вывод о запрете этих PDF для `*` ошибочен. Причина — игнорирование границ групп. |
| Прокси | HTTP_PROXY/HTTPS_PROXY/ALL_PROXY/NO_PROXY не заданы; Windows ProxyEnable=0, PAC не настроен; WinHTTP — direct. | Явный прокси не подтверждён. Это не исключает прозрачный сетевой intermediary. Цепочка НУЦ не является сама по себе доказательством interception. |
| DNS/IPv6 | Для банка наблюдались публичные IPv4: Альфа 217.12.104.100; Сбер 84.252.149.206; ВТБ 195.242.82.13 и 195.242.83.13; kk.ru 178.248.234.134. curl не получил AAAA для проверенных Альфа/Сбер/ВТБ. | IPv6 не объясняет наблюдавшиеся соединения. DNS ответы фиксируются, IP не превращаются в постоянную настройку. |
| WSL2 | `wsl --list --quiet` показывает только docker-desktop; полноценное Linux-приложение/Ubuntu не проверялось. | Причину ошибки WSL нельзя считать установленной. Доверие Windows не переносится автоматически в Linux или контейнер. |
| Redirects | У успешно полученных локальных HTML/PDF redirect отсутствовал. При TLS failure final HTTP URL неизвестен. | Каждый redirect нужно отдельно допускать и проверять, не пользоваться бесконтрольным follow_redirects. |

Файлы доказательств: `alfa-stdlib.json`, `alfa-system.json`, `sber-system.json`, `*-chain.txt`, `alfa-fixed.json`, `alfa-system-fixed.json`, `sber-fixed.json`, `vtb-fixed.json`, `vtb-product.json`, `vtb-tariff-index.json`, `kk-*.json`.

## B. Source Discovery

Статусы не объединяются: found → reachable → downloaded → content verified → applicable/current → monitoring approved. HTML originals и найденные в них ссылки — разные объекты.

| Банк | Продукт и источники | Дата и подтверждение | Статус originals / применимость / автоматизация |
|---|---|---|---|
| Кубань Кредит | [Продукт](https://kk.ru/business/solutions/zp-project/); [тариф PDF](https://kk.ru/upload/iblock/3cf/2aukz7j463jptle27m62oo8frs1x862x.pdf); [условия PDF](https://kk.ru/upload/iblock/973/96i8chqk1f794ldm6umaie424qnvoxhb.pdf); [заявление](https://kk.ru/upload/iblock/fee/qc2kxexlj3j0c3lagsjdfelton5diugv.pdf) | В оригинале тарифа: утверждение 24.05.2024, действие 01.06.2024. В оригинале условий: 29.06.2026. Заявление подписано на HTML как действующее с 25.03.2026, его bytes не запрашивались. | Продукт и два PDF скачаны/проверены. Они представлены в актуальном разделе сайта на 10.10.2026. Условия определяют предприятия, ИП и частную практику; тариф разделён по дате договора. Явный отдельный RU-KDA тариф не обнаружен. Product policy и применимость конкретному договору требуют проверки; monitoring approved=false. |
| ВТБ | [Продукт МСБ](https://www.vtb.ru/malyj-biznes/zarplatniy-proekt/); [каталог тарифов](https://www.vtb.ru/malyj-biznes/tarify-i-komissii/); [условия PDF](https://www.vtb.ru/media-files/vtb.ru/sitepages/malyj-biznes/zarplatniy-proekt/uslovia_vtb_0109.pdf); [сборник МСБ XLSX](https://www.vtb.ru/media-files/vtb.ru/sitepages/tarify/korporativnym-klientam/2026-10-05-sbornik-tarifov_smb.xlsx); [изменения PDF](https://www.vtb.ru/media-files/vtb.ru/sitepages/tarify/korporativnym-klientam/tarify_vtb_s_05102026.pdf) | Полученный HTML относит условия к 01.09.2026; содержит сборники 22.09, 27.09 и 05.10.2026. Последняя из видимых дат — 05.10.2026. Поисковый индекс показывал старые 06.09/22.09 и не заменяет текущую страницу. | HTML originals получены/проверены. PDF/XLSX: только ссылки из originals, target GET намеренно не выполнен; contents/current tariff values/RU-KDA applicability unknown. Robots группы `*` запрещает *.pdf$ и *.xlsx$. |
| Альфа-Банк | [Продукт МСБ](https://alfabank.ru/sme/salaryproject/); [каталог документов](https://alfabank.ru/sme/quick/docstariffs/). Индекс официальной страницы перечисляет договор и положение АЗОН с 22.06.2026; правила 19.04.2024 размещены в архиве. | Даты только из индекса, не из downloaded original. [Корпоративная страница](https://alfabank.ru/corporate/salaryproject/) индексируется с договором 13.07.2026: это другой сегмент, нельзя без проверки подменять им МСБ. | TLS исправлен; robots 403. Точный действующий employer tariff PDF не установлен. Продукт/договор не скачаны, текущие тарифы unknown, автоматизация blocked. |
| Сбер | [Кандидат продукта](https://www.sberbank.ru/ru/s_m_business/bankingservice/cards/salaryproject); [кандидат RKO-каталога](https://www.sberbank.com/ru/s_m_business/bankingservice/rko/tariffs); [официальная документация SberAPI](https://developers.sber.ru/docs/ru/sber-api/scenarios/salary/salary-project/overview) | Тарифный original и дата действия не установлены. Указанные product/catalog URL не подтверждены успешным локальным target GET. SberAPI описывает интеграцию, не стоимость зарплатного проекта. | TLS исправлен, robots подменён WAF-страницей. Employer tariffs/RU-KDA scope unknown; product originals не скачаны; automated monitoring blocked. |

Дополнительный URL-кандидат Альфа: [договор на CDN](https://alfabank.servicecdn.ru/site-upload/e9/ca/7344/dog_perevod_zp_18122025.pdf). Найден поиском; не скачан; дата в filename не подтверждает действие. Текущая официальная связь этого CDN URL с документом 22.06.2026 не установлена. Не использовать его как тариф октября 2026 и не придумывать новые пути по шаблону.

### Что действительно извлечено из Кубань Кредит

Тариф, страница 1, таблица III.I: для договоров, заключённых с 12.04.2021, плата за зачисление зарплаты — 0%, выпуск основной карты — 0 рублей. Для договоров до этой даты зачисление имеет диапазон 0–1,0% со сноской согласования, выпуск определяется договором. Досрочный перевыпуск при смене тарифа: 0 рублей для старой группы; прочерк для новой группы нельзя превращать в 0.

Условия, страницы 1–3: вознаграждение определяется договором и/или тарифами; определены работодатели, порядок присоединения и разграничение договора предприятия и договора сотрудника. ИП не получает карту на своё имя в рамках этого договора. Поэтому ни «все переводы физлицам бесплатны», ни «все услуги банка бесплатны» из этих originals не следуют.

Наличие действующего раздела сайта и даты в PDF подтверждает опубликованную редакцию; не доказывает отсутствие специальных условий конкретного работодателя. Для предложения в Краснодарском крае нужно зафиксировать договор/пакет/дату присоединения и регион обслуживания. Регион не заполнять федеральным значением автоматически.

| Полученный файл | Bytes | SHA-256 |
|---|---:|---|
| kk-tariff.pdf | 648631 | db9c856a67767b6d1c290a48162d107fa6c99d8905b395d3b113ec1920b57bec |
| kk-conditions.pdf | 757961 | 4f935428de5678c4a4b176ff1f7c34e5ed0d635d30502a878d272fbac32e8ecb |
| kk-robots.txt | 3193 | 57b087c698d6e11464571542c4d33b02fca45c03d123856b9f91d63286584f2d |
| vtb-robots.txt | 3632 | aba1003ced0e5d0c5ac4219848afd28aa099c35665dafbdd66ce179da41079c8 |
| vtb-product.html | 480810 | b28e55055e56ff0ec56b36c79471fb2b7718902867044d184d2373d9ad11f983 |
| vtb-tariff-index.html | 323270 | 34523d1f3951b627f7e53f053633c3e8e0727a4b0afbdd1943fac618e15963cd |

### Точная интерпретация robots

Полный файл сохранён как `kk-robots.txt`; сокращённая схема его структуры:

```text
User-Agent: *
... директивы общей группы ...
Allow: /upload/*.jpg
Allow: /upload/*.png
Allow: /upload/*.svg

User-Agent: Yandex
... директивы группы Yandex ...
Disallow: /upload/*.pdf
...
Disallow: /upload/iblock/*.pdf
```

Для UA `BankSalaryResearch/0.1` оба переданных PDF разрешены правилами `*`; для `Yandex` запрещены. UA не маскировался под браузер или другого робота: идентичность установлена до чтения robots и оставалась постоянной. [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309) требует выбирать применимые группы, сопоставлять пути с wildcard и учитывать более специфичное совпадение. Один grep по Disallow не определяет policy. stdlib urllib.robotparser не подходит для используемых wildcard правил; проверка выполнена Protego 0.7.0.

Robots — инструкции роботу, не HTTP ACL и не лицензия на перепубликацию. Их нарушение не проверяется экспериментальной загрузкой. ВТБ PDF/XLSX не запрашивались после подтверждения запрета. Неизвестный/403/HTML вместо robots в нашем проекте остаётся blocked; это консервативная project policy, а не утверждение, что RFC всегда требует запрещать после любого 4xx.

## C. TLS Fix

Рабочий вариант для этого проекта — отдельный SSLContext для банковского fetch, доверяющий утверждённому root. На Windows также работает truststore.SSLContext с дополнительным CA. Не добавлять корень в глобальное хранилище без необходимости, не менять файл certifi на месте, не доверять leaf-сертификату, полученному из отвергнутого соединения.

Официальные каналы: [Госуслуги](https://www.gosuslugi.ru/crt), [инструкция Сбера](https://developers.sber.ru/help/certificates/how-to), [прямые ссылки в документации банка Точка](https://developers.tochka.com/docs/tochka-api/certificate). Эти документы подтверждают происхождение CA; небезопасные примеры отключения проверки в сторонних инструкциях здесь не применяются.

Загрузка по обычному DNS для gu-st.ru давала EOF. Один адрес из полученного DNS RRset, 212.193.156.251, с тем же HTTPS hostname/SNI и обычной проверкой сертификата дал успешную загрузку. Это диагностическая проверка разных узлов DNS, не production IP pinning. Не закреплять этот IP: он может измениться.

Оригинал root сохранён как `russian_trusted_root_ca_pem.crt`:

- Subject/Issuer: Russian Trusted Root CA, The Ministry of Digital Development and Communications, RU.
- Действие: 01.03.2022 21:04:15 UTC — 27.02.2032 21:04:15 UTC.
- SHA-256 DER сертификата: `d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31`.
- SHA-256 скачанного PEM файла: `936a43fea6e8e525bcc0f81acd9c3d21b4fc4b9b68acea7906d698005afc6504`.

DER fingerprint и hash файла различаются из-за PEM-представления; сравнивать нужный тип хеша.

```python
import ssl
import certifi
import httpx2 as httpx  # фактически установленный клиент проекта

ctx = ssl.create_default_context(cafile=certifi.where())
ctx.load_verify_locations(cafile="path/to/russian_trusted_root_ca_pem.crt")
assert ctx.check_hostname and ctx.verify_mode == ssl.CERT_REQUIRED

client = httpx.Client(
    verify=ctx, trust_env=False, follow_redirects=False,
    timeout=httpx.Timeout(20, connect=8),
    headers={"User-Agent": "BankSalaryResearch/0.1"},
)
# В production каждый client.get вызывается только через FetchGateway policy.
```

Альтернатива для Windows:

```python
import ssl
import truststore

ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.load_verify_locations(cafile="path/to/russian_trusted_root_ca_pem.crt")
```

[truststore](https://truststore.readthedocs.io/en/latest/) использует Windows CryptoAPI на Windows и OpenSSL на Linux; [HTTPX](https://www.python-httpx.org/advanced/ssl/) принимает явный SSLContext. Если выбирается обычный `httpx`, зависимость и импорты нужно менять осознанно, с lockfile и тестами; это не часть данного исследования.

### Воспроизводимые команды Windows

В этом сеансе диагностические зависимости установлены в изолированный каталог evidence/deps, не в зависимости приложения. Скрипт `tools/bank_tls_probe.py` без параметров не делает сетевых запросов. `--host` делает один DNS lookup и handshake; `--url` требует явный `--research-get`, читает robots и, только если правила известны/разрешают, делает один target GET. Redirect не следует. Размер ответа ограничен 50 MiB. Ошибки записываются в JSON: process exit code сам по себе не является content acceptance. Это исследовательский CLI, не SSRF-safe production gateway: предварительная DNS-проверка не заменяет привязку реального peer IP при подключении.

```powershell
$evidenceDir = Join-Path $env:LOCALAPPDATA 'BankingSalaryIntelligence\investigations\2026-10-10'
$env:PYTHONPATH = Join-Path $evidenceDir 'deps'
$env:PYTHONIOENCODING = 'utf-8'
$caFile = Join-Path $evidenceDir 'russian_trusted_root_ca_pem.crt'

# DNS, версии TLS/curl, ОС-прокси. Не печатать значения proxy URL с паролями.
Resolve-DnsName www.vtb.ru -Type A
Resolve-DnsName www.vtb.ru -Type AAAA
curl.exe --version
netsh winhttp show proxy

# Сравнение trust: два отдельных handshake, без HTTP.
.\.venv\Scripts\python.exe tools\bank_tls_probe.py --host alfabank.ru --mode stdlib
.\.venv\Scripts\python.exe tools\bank_tls_probe.py --host alfabank.ru --mode system --extra-ca $caFile

# Повторить по одному при необходимости; это исследование, не scheduled job.
.\.venv\Scripts\python.exe tools\bank_tls_probe.py --host www.vtb.ru --family 4 --mode certifi --extra-ca $caFile
.\.venv\Scripts\python.exe tools\bank_tls_probe.py --url https://kk.ru/business/solutions/zp-project/ --research-get

# Цепочка фиксируется, любое нарушение проверки отвергается.
.\tools\inspect_bank_chain.ps1 -BankHost alfabank.ru
```

На чистой машине для диагностического CLI: создать отдельный venv и установить `httpx2`, `truststore`, `certifi`, `protego`; не менять pyproject/uv.lock приложения ради исследования. Для plain httpx выбрать `--client httpx`. `--trust-env` разрешает использование env proxy для HTTP, но сырой TLS handshake всегда direct; сравнивать эти результаты с учётом разных путей.

Сравнение с curl после фикса CA:

```powershell
curl.exe --cacert $caFile --connect-timeout 8 --max-time 20 https://www.vtb.ru/robots.txt
```

Эта последняя команда предоставлена для воспроизведения; успешность конкретного curl GET с CA не заявлена. Выполненные успешные GET использовали Python SSLContext. PowerShell Invoke-WebRequest отдельно не запускался: его успешность также не предполагается. Native .NET TLS использован только для безопасного просмотра отвергнутых цепочек.

### WSL2 / Docker

В Linux сертификаты и CA path свои. Сначала сравнить Python/OpenSSL/curl, DNS IPv4/IPv6, proxy env; затем передать тот же аутентифицированный CA через SSLContext. Это обеспечивает воспроизводимость без изменения trust всей ОС. Для системного доверия в Ubuntu/Debian альтернативно:

```bash
sudo apt-get install ca-certificates openssl
sudo install -m 0644 /path/to/russian_trusted_root_ca_pem.crt /usr/local/share/ca-certificates/russian_trusted_root_ca.crt
sudo update-ca-certificates
openssl x509 -in /path/to/russian_trusted_root_ca_pem.crt -noout -subject -issuer -dates -fingerprint -sha256
openssl s_client -connect www.vtb.ru:443 -servername www.vtb.ru -verify_hostname www.vtb.ru -verify_return_error -CAfile /etc/ssl/certs/ca-certificates.crt </dev/null
```

Эти Linux-команды не выполнялись здесь. Контейнеру нужен собственный CA mount/context или осознанная установка CA при сборке; доверие Windows хоста туда не переносится. Если сервер не отдаёт intermediate, получить его из официального канала и проверить цепочку; не превращать intermediate в самостоятельный неограниченный trust anchor. Не добавлять чужой TLS-interception root без идентификации и решения ответственного.

## D. Download Strategy

| Банк | Рабочий путь получения | Остаточный блокер |
|---|---|---|
| Кубань | Разрешённый robots HTML index → явные PDF links → TLS verified GET. Это уже выполнено. Заявление можно включить отдельно после policy/content checks. | Для scheduled ingestion оформить source policy на точные пути, частоту, хранение и использование. Установить применимость договору работодателя. |
| ВТБ | Автоматически читать допущенные HTML product/index и находить новые ссылки. PDF/XLSX получать оператором либо по явно согласованному с банком каналу/исключению. | PDF/XLSX robots disallow. Нужны сборник МСБ с 05.10.2026, условия с 01.09.2026 и регионально/пакетно применимые условия. Один маркетинговый HTML не заменяет их. |
| Альфа | Запросить у оператора/менеджера МСБ текущий договор и приложения с employer fees, положение АЗОН и перечень тарифов. Официальный CDN может быть отдельным источником только после подтверждения связи, точного текущего URL и его собственной policy. | robots 403; текущий тариф и прямой актуальный URL не получены. Нужен разрешённый endpoint/allowlisting нашего стабильного UA или ручные originals. |
| Сбер | Получить у менеджера СберБизнес/оператора условия зарплатного проекта и тарифы для нужного подразделения/пакета в RU-KDA. API docs использовать для интеграционных facts, не pricing. | WAF user_blocked; тарифный original не найден. Нужен разрешённый публичный канал документов или ручной original с provenance. |

В браузерном инструменте этой сессии ответ: `No browser is available`. Поэтому ручное открытие остальных банков не подтверждено. Не выполнялись обход WAF/CAPTCHA, подмена UA, авторизация или отключение TLS. Банкам сообщения не отправлялись.

HTML допустим как original для того, что явно опубликовано в HTML: например, интеграция 1С, заявленные сроки, заявленная бесплатность открытия. Факт должен иметь source_kind=marketing_html, сохранённый HTML hash и точный фрагмент. Для цен с пакетными/договорными исключениями нужно связанное тарифное приложение; неизвестные условия не удалять ради числа 0.

Ручной путь: оператор сохраняет original без print-to-PDF подмены, requested/final URL, дату/время и происхождение; import вычисляет hash, проверяет формат, размер, банк, даты, сегмент и права на использование. Manual import не превращается в automated fetch day/G1 и не выдаёт новый G0-LIVE.

## E. Implementation Plan

В локальном коде уже существуют SourcePolicy, Source, Blob, SourceVersion, SourceFetch, JobRun и enqueue_job. Сам FetchGateway и pipeline ещё не реализованы. Минимальные изменения:

1. **TLS factory**: отдельный context system или certifi с BANK_FETCH_EXTRA_CA_FILE. Проверить PEM/CA hash, chain/hostname; отсутствующий/невалидный CA — typed config/TLS error. trust_env выключен по умолчанию; явный proxy поддержать как отдельную конфигурацию. Не использовать global inject_into_ssl или CA в общей конфигурации всех внешних клиентов. Сейчас httpx2 находится в dev dependency-group; для работающего production ingestion клиент и используемые CA/robots зависимости должны быть объявлены runtime dependencies и зафиксированы lockfile.
2. **Policy + robots**: active source-specific допуск включает scheme/host/path, способ получения, redirects, срок/отзыв, цели, storage/reuse, rate. Существующий allowed_hosts недостаточен. HTTP 200 с HTML challenge не принимать за robots. Protego либо сопоставимый проверенный RFC matcher; сохранить robots bytes/hash/time/UA/matched group. Не делать глобальный allow из отсутствия запрета и не смешивать policy block с TLS error.
3. **FetchGateway**: единственная точка egress, offline по умолчанию. Проверять policy до dispatch и каждого redirect, DNS и реальный peer IP, HTTPS, размер 50 MiB, MIME/magic, таймауты, ≤5 redirects, concurrency=1/host и утверждённый rate. Anti-bot и запрещённые files — blocked, без retries, направленных на обход.
4. **Original archive**: streaming temp в том же volume → hash → fsync/atomic rename → DB registration. Immutable blob path по SHA-256; observations отдельно от content versions. До acceptance — quarantine. Каждый repeated same hash создаёт observation, но не blob/version. 304 допустим только с существующим verified blob.
5. **Retry**: jitter/backoff для connection timeout, отдельных EOF и 5xx; 429 по Retry-After; максимум попыток. Certificate verification, policy, robots, 403/challenge — terminal до изменения причины. Не объявлять недоступный источник свежим, сохранять last good published version со stale marker.
6. **Discovery**: два простых HTML adapters для kk и vtb, извлекают link text/date/current-versus-archive/source relation. Новый URL становится pending и не скачивается автоматически без допуска. Для ВТБ поддержать kind=xlsx и безопасный XLSX parser в соответствующем parser task; сейчас schema Source.kind допускает только html/pdf/index/news. Не выдавать XLSX за PDF и не скачивать DOCX/XLSX по обходному URL.
7. **Manual import**: отдельно утверждённая запись provenance/rights/content acceptance; не путать manual и automatic policy. Parsed facts имеют immutable original/extraction hash, page/cell/quote, effective dates, observed time, segment/package/region и contract date conditions. Unknown остаётся unknown.
8. **Incremental parse**: только новые content hashes; ключ extraction=(blob_hash,parser_version). Повторный parse старого оригинала разрешён при новой parser_version. Fact/evidence append-only; human-reviewed публикация новой версии не стирает старую историю.

Использовать уже принятые STO-001/NET-001/JOB-001/HTML-001/PDF-001/VER-001, не создавать новую платформу или ADR ради этих шагов. Миграции path policy / method / validity / xlsx — небольшие дополнения существующего каталога; согласовать их с текущими контрактами перед изменением бизнес-схемы.

### Что сделано в этом исследовании

- Добавлены `tools/bank_tls_probe.py`, `tools/inspect_bank_chain.ps1`, `tools/test_bank_tls_probe.py`.
- Добавлен этот отчёт и один исполнительский prompt `docs/implementation/luna_prompts/SOURCE-RECOVERY.md`.
- Реальные файлы/evidence и временные исследовательские зависимости лежат вне Git.
- Проверки: 10 offline regression tests passed; Ruff check и Ruff format для новых Python файлов прошли. Проверены также ограничение stream size и запуск CLI без сети при отсутствии параметров. Production/test CI к банкам не обращается.
- Backend, registry seeds, gates, lockfiles и чужие изменения не изменялись. Общая application test suite здесь не запускалась: runtime приложения не менялся.

## F. Ready-to-Use Task for Luna

Полный самостоятельный prompt: [SOURCE-RECOVERY.md](../archive/pre-snapshot/implementation/luna_prompts/SOURCE-RECOVERY.md). Он требует реализовать минимальные безопасные контракты offline, проверить исправление robots regression, настроить scoped CA, архивирование и manual import; live actions остаются source-specific. Он не требует выдавать блокирующую документацию за завершённый мониторинг.
