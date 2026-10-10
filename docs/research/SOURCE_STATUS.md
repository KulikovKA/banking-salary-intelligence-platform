# Источники snapshot: проверяемые решения

Сводка сохранённого исследования 09–10.10.2026; новых bank requests и grants
при разделении веток не было. Машиночитаемый реестр:
[sources.json](../../tests/fixtures/manifests/sources.json). Это source discovery/
approval evidence, не runtime policy: FetchGateway читает SourcePolicy в PostgreSQL.

| Банк | Проверено / остаётся |
|---|---|
| Сбер | SberAPI — integration reference, не employer tariff. Точный актуальный public tariff и accepted original не подтверждены. sberbusiness.live ownership/terms pending. |
| ВТБ | Официальная product page найдена; direct page/robots probes ранее остановились на TLS validation. Indexed conditions 01.09.2026 — lead, не accepted original. |
| Альфа-Банк | Официальная SME page найдена; актуальные документы/точные URLs/bytes/applicability не приняты. Ранее TLS validation препятствовала probes; архивные условия не current tariff. |
| Кубань Кредит | Official page содержит exact tariff/terms PDF href; hashes/size известны по research-only originals. Acquisition/storage/reuse basis и source-specific manual/automatic grants не подтверждены — оба BLOCKED. |

Ограниченный прежний допуск FAQ Кубань Кредит относится только к manual/reference
archive, не employer tariff, не автоматическому получению и не новым двум PDF.
Новый grant для application corpus не выдан ни одному банку; G1/G2 NOT PASSED,
snapshot S1 BLOCKED. Все 44 исходные RU-KDA/SME metric cells/package — unknown.
Marketing claims, snippets и research bytes не публикуются как тарифные факты.

## Exact Кубань Кредит candidates

Official product page: `https://kk.ru/business/solutions/zp-project/`.

| Document | Exact path on kk.ru | Bytes / SHA-256 | Effective date candidate |
|---|---|---|---|
| Tariff | /upload/iblock/3cf/2aukz7j463jptle27m62oo8frs1x862x.pdf | 648631 / db9c856a67767b6d1c290a48162d107fa6c99d8905b395d3b113ec1920b57bec | 2024-06-01 |
| Employer terms | /upload/iblock/973/96i8chqk1f794ldm6umaie424qnvoxhb.pdf | 757961 / 4f935428de5678c4a4b176ff1f7c34e5ed0d635d30502a878d272fbac32e8ecb | 2026-06-29 |

Даты кандидатов не доказывают applicability/currentness. Originals вне Git,
application archive и публикаций. Employer terms не самостоятельный tariff.
Robots correction: PDF disallows относятся к Yandex, а не `*`; для стабильного
BankSalaryResearch/0.1 paths разрешены. Исторический robots SHA-256
`57b087c698d6e11464571542c4d33b02fca45c03d123856b9f91d63286584f2d`.
Robots allow не выдаёт acquisition/storage/reuse permission; свежий robots GET
в этой итерации не делался. TLS verification всегда включена.

## Что необходимо до real acquisition/import

Exact host/path/redirect targets, official provenance, применимые terms либо
подтверждённое основание, acquisition/storage/reuse decision ответственного,
method-specific scope/expiry/revocation и request rate. Manual grant отдельно,
не G0-LIVE. После получения — отдельный content acceptance и evidence review.
Provider/Groq transmission/reuse decision также отдельно. Unknown остаётся blocked.
SNAP-03 ведёт этот реестр; SNAP-18 real evaluation ждёт допущенного корпуса.

## История и первичные материалы

Полные отчёты/изменения доступны в независимой [archive ветке](https://github.com/KulikovKA/banking-salary-intelligence-platform/tree/archive),
не используются при запуске main:

- [Source E2E: решения по двум exact PDF](https://github.com/KulikovKA/banking-salary-intelligence-platform/blob/02cd6c8e00e9f84c0528460c7a42835f95a41499/docs/reports/SOURCE-RECOVERY-E2E-2026-10-10.md).
- [Bank document investigation](https://github.com/KulikovKA/banking-salary-intelligence-platform/blob/02cd6c8e00e9f84c0528460c7a42835f95a41499/docs/reports/bank-document-investigation-2026-10-10.md).
- [SRC-001 decision record](https://github.com/KulikovKA/banking-salary-intelligence-platform/blob/02cd6c8e00e9f84c0528460c7a42835f95a41499/docs/reports/SRC-001.md).
- [Исторические G1/G2](https://github.com/KulikovKA/banking-salary-intelligence-platform/blob/02cd6c8e00e9f84c0528460c7a42835f95a41499/docs/archive/pre-snapshot/product/ACCEPTANCE_CRITERIA.md).
