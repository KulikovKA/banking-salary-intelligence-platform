# SNAP-03 — реестр готовности источников

Срез на 10.10.2026 по сохранённым решениям в `docs/research/SOURCE_STATUS.md`.
Новые обращения к банкам, загрузки и grants в рамках SNAP-03 не выполнялись.
Реальные originals не читались и не импортировались приложением.

| Банк | Ожидаемые документы | Статус в приложении | Что отсутствует |
|---|---|---|---|
| Сбер | Актуальные условия зарплатного проекта для работодателя | BLOCKED | Нет точного актуального URL и принятой версии; найденные integration/reference материалы не являются тарифом; ownership/terms `sberbusiness.live` не подтверждены. |
| ВТБ | Условия/тариф зарплатного проекта для SME и RU-KDA | BLOCKED | TLS не позволил проверить страницу и robots; indexed date — только lead; нет разрешённой acquisition, принятой версии и подтверждения применимости. |
| Альфа-Банк | Актуальные правила/тариф работодателя для SME и RU-KDA | BLOCKED | Прямые URLs и bytes актуальных документов не приняты; прошлые TLS probes не прошли; архивные условия не подтверждают текущий тариф. |
| Кубань Кредит | Тариф и условия обслуживания зарплатного проекта | BLOCKED | Exact official links и candidate hashes известны из исследования, но originals остаются вне application corpus; acquisition/storage/reuse basis и method-specific grants отсутствуют. |

## Ограничения доступа и покрытия

- У всех четырёх банков application corpus не содержит accepted real source versions.
- Реестр исследований не является runtime permission: разрешение задаётся `SourcePolicy` в PostgreSQL.
- Прежний manual/reference допуск FAQ Кубань Кредит не распространяется на зарплатные документы и не является G0-LIVE.
- Все 44 исходные ячейки покрытия RU-KDA/SME и банковские пакеты остаются `unknown`; тарифы и reviewer не создавались.
- G1/G2 остаются `NOT PASSED`, S1 остаётся `BLOCKED`. Synthetic fixture SNAP-03 не меняет эти статусы.
- `docs/research/SOURCE_STATUS.md` ссылается на `tests/fixtures/manifests/sources.json`, которого нет в исходном `main` на `504c71f`; область SNAP-03 не включает этот путь, поэтому здесь использован сохранённый человекочитаемый реестр.

Перед любым real import необходимы source-specific evidence официального происхождения, применимых terms или другого проверенного acquisition/storage/reuse основания, exact allowed URLs/redirects, отдельное method-specific решение, срок/отзыв и rate limit. После импорта нужны отдельные content acceptance и review. Ни один из этих gates этим отчётом не пройден.
