# WORK-05 — Четыре банковских адаптера и проверка доступности G1

Исполнитель: **GPT-6 Luna**. Reasoning по умолчанию: **High**. Status: **TODO**.

Почему этот уровень: Разные сайты и форматы; оценка полноты не сводится к HTTP 200. Многодневную проверку нельзя заменить рассуждением.

Dependencies: [WORK-01](WORK-01.md), [WORK-04](WORK-04.md)

Gates входящих этапов: G0. Порядок внутри блока обязателен. G1 принимается после WORK-05, G2 после WORK-09. Реализация пока не начата; текущее поручение пользователя меняет только план.

[Правила reasoning](../REASONING_GUIDE.md). [Готовый prompt](../work_prompts/WORK-05.md).

## Общие условия

Центральные контракты в docs/architecture остаются обязательными. Полные внутренние ТЗ сохраняют файлы, ошибки, AC и DoD. Все входящие этапы выполняются последовательно, с отдельными проверками и checkpoints. Это укрупнённое поручение с внутренней декомпозицией, не одна задача XL без границ. Новые функции сверх перечисленного состава не добавляются.

## ING-001 — Адаптер банка Сбер

Reasoning: **High**. [Полное ТЗ](../tasks/ING-001.md).

Контракт: BankAdapter.discover/classify/extract из COMPONENTS; общие FetchGateway/Parser, bank-specific selectors only.

1. Зафиксировать approved seed URLs из SRC-001 и поддерживаемые document families.
2. Начать с официального product/tariff discovery; SberAPI manual использовать только для integration facts. Подтвердить доступность тарифов Краснодарского края, не обходить защиту..
3. Реализовать discover с allowlisted links, classify family/type/scope hints и layout health markers.
4. Прогнать frozen fixtures и scheduled probes, version selectors, сохранить unsupported cases без auto-publish.

Ошибки: Изменение DOM/новый неизвестный PDF template →review; CAPTCHA/403 →blocked; ссылку вне allowlist не скачивать автоматически.

Проверки: Сбер: product HTML, linked conditions PDF, old/new edition, missing link, 200 error, duplicate URL; общая adapter contract suite плюс frozen expected extraction.

Критерий: Сбер использует единый pipeline; минимум один настоящий tariff/conditions original получен; покрытие и все нераспознанные поля отражены.

## ING-002 — Адаптер банка ВТБ

Reasoning: **High**. [Полное ТЗ](../tasks/ING-002.md).

Контракт: BankAdapter.discover/classify/extract из COMPONENTS; общие FetchGateway/Parser, bank-specific selectors only.

1. Зафиксировать approved seed URLs из SRC-001 и поддерживаемые document families.
2. Разделить малый бизнес и другие employer segments, собрать linked tariff/conditions PDF. Недоступность web research не считать доказательством блокировки целевого host..
3. Реализовать discover с allowlisted links, classify family/type/scope hints и layout health markers.
4. Прогнать frozen fixtures и scheduled probes, version selectors, сохранить unsupported cases без auto-publish.

Ошибки: Изменение DOM/новый неизвестный PDF template →review; CAPTCHA/403 →blocked; ссылку вне allowlist не скачивать автоматически.

Проверки: ВТБ: product HTML, linked conditions PDF, old/new edition, missing link, 200 error, duplicate URL; общая adapter contract suite плюс frozen expected extraction.

Критерий: ВТБ использует единый pipeline; минимум один настоящий tariff/conditions original получен; покрытие и все нераспознанные поля отражены.

## ING-003 — Адаптер банка Альфа-Банк

Reasoning: **High**. [Полное ТЗ](../tasks/ING-003.md).

Контракт: BankAdapter.discover/classify/extract из COMPONENTS; общие FetchGateway/Parser, bank-specific selectors only.

1. Зафиксировать approved seed URLs из SRC-001 и поддерживаемые document families.
2. Разделить рекламные benefits и юридические правила зарплатного проекта; связать версии приложений/условий и банковские package codes, не обобщать zero-price headline..
3. Реализовать discover с allowlisted links, classify family/type/scope hints и layout health markers.
4. Прогнать frozen fixtures и scheduled probes, version selectors, сохранить unsupported cases без auto-publish.

Ошибки: Изменение DOM/новый неизвестный PDF template →review; CAPTCHA/403 →blocked; ссылку вне allowlist не скачивать автоматически.

Проверки: Альфа-Банк: product HTML, linked conditions PDF, old/new edition, missing link, 200 error, duplicate URL; общая adapter contract suite плюс frozen expected extraction.

Критерий: Альфа-Банк использует единый pipeline; минимум один настоящий tariff/conditions original получен; покрытие и все нераспознанные поля отражены.

## ING-004 — Адаптер банка Кубань Кредит

Reasoning: **High**. [Полное ТЗ](../tasks/ING-004.md).

Контракт: BankAdapter.discover/classify/extract из COMPONENTS; общие FetchGateway/Parser, bank-specific selectors only.

1. Зафиксировать approved seed URLs из SRC-001 и поддерживаемые document families.
2. Подтвердить официальные kk.bank/kkbank.ru домены и redirects; manuals не считать tariff evidence; сторонние зеркала исключить, региональность доказать текстом..
3. Реализовать discover с allowlisted links, classify family/type/scope hints и layout health markers.
4. Прогнать frozen fixtures и scheduled probes, version selectors, сохранить unsupported cases без auto-publish.

Ошибки: Изменение DOM/новый неизвестный PDF template →review; CAPTCHA/403 →blocked; ссылку вне allowlist не скачивать автоматически.

Проверки: Кубань Кредит: product HTML, linked conditions PDF, old/new edition, missing link, 200 error, duplicate URL; общая adapter contract suite плюс frozen expected extraction.

Критерий: Кубань Кредит использует единый pipeline; минимум один настоящий tariff/conditions original получен; покрытие и все нераспознанные поля отражены.

## QA-001 — Gate G1: повторяемость получения четырёх банков

Reasoning: **High**. [Полное ТЗ](../tasks/QA-001.md).

Контракт: G1 ACCEPTANCE_CRITERIA; automated fetch logs и official manifest.

1. Выполнить scheduled fetch на минимум3 разных дня в пределах недели с approved rates.
2. Сверить каждый archived hash с HTTP observation и содержанием tariff/conditions.
3. Проверить coverage регион/segment/metric и отделить public individual от missing parser data.
4. Подготовить GO/NO-GO отчёт и получить пользовательскую приёмку gate, не симулировать прошедшие дни.

Ошибки: Нет нужного документа/права/доступа →G1 NOT PASSED, дальнейший полный UI не стартует; manual import не маскирует failed adapter.

Проверки: 100% manifest references resolve; четыре banks представлены; at least3 distinct days; counts HTTP vs parse successes раздельно.

Критерий: Собраны реальные доказательства G1 или точный NO-GO без выдуманного успеха; решение пользователя записано.

## Завершение блока

DONE только когда все внутренние этапы прошли свои AC, тесты и gates; отчёт `docs/reports/WORK-05.md` содержит список файлов, результаты проверок, ограничения и checkpoints. Синхронизировать MASTER_PLAN/WORK_INDEX и дочерние статусы TASK_INDEX/ТЗ; старый DETAILED_BACKLOG — исторический справочник. Если часть результата не готова, блок IN_PROGRESS или BLOCKED с причиной, не DONE.

Оформление уже проверенных результатов можно поручить Luna Light отдельным проходом. На Light нельзя заново решать, что тест или критерий выполнен.
