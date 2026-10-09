# Реестр архитектурных решений

Статус всех ADR ниже: **proposed**, ожидают согласования пользователем в G0. Они дополняют базовую Miro v1.0; приложение ещё не менялось. После согласования записать дату/автора решения и accepted/rejected/superseded. Рутинные детали в рамках accepted контракта повторного согласования не требуют.

| ADR | Решение | Изменение к v1.0 |
|---|---|---|
| [001](001-publication-and-provenance.md) | Явное отделение кандидатов от публикации | Уточняет сходящиеся ветки review |
| [002](002-temporal-applicability.md) | Две оси времени и явная применимость | Раскрывает нормализацию/версии |
| [003](003-constrained-claims.md) | Проверенные claims и контролируемый renderer | Усиливает проверку ответа |
| [004](004-jobs-and-outbox.md) | Leases/outbox в PostgreSQL | Уточняет cron/worker, без брокера |
| [005](005-storage-and-pdf.md) | Архивный протокол и лицензирование parser | Раскрывает archive/PDF block |

При следующем изменении: context → alternatives → decision → consequences → affected contracts/tasks → migration/rollback → verification → approval. Не редактировать старое принятое решение задним числом.
