# Реестр архитектурных решений

Статус каждого решения указан в соответствующем ADR. ADR-006 принят владельцем проекта с изменениями 2026-10-10; G0-LIVE не выдан ни одному банковскому источнику. Они дополняют базовую архитектуру; рутинные детали в рамках принятого контракта повторного согласования не требуют.

| ADR | Решение | Изменение к v1.0 |
|---|---|---|
| [001](001-publication-and-provenance.md) | Явное отделение кандидатов от публикации | Уточняет сходящиеся ветки review |
| [002](002-temporal-applicability.md) | Две оси времени и явная применимость | Раскрывает нормализацию/версии |
| [003](003-constrained-claims.md) | Проверенные claims и контролируемый renderer | Усиливает проверку ответа |
| [004](004-jobs-and-outbox.md) | Leases/outbox в PostgreSQL | Уточняет cron/worker, без брокера |
| [005](005-storage-and-pdf.md) | Архивный протокол и лицензирование parser | Раскрывает archive/PDF block |
| [006](006-g0-offline-and-live-ingestion.md) | Разделение допуска к офлайн-разработке и live-ingestion | G0-OFFLINE принят для перечисленных checkpoints; G0-LIVE остаётся source-specific и не выдан |

При следующем изменении: context → alternatives → decision → consequences → affected contracts/tasks → migration/rollback → verification → approval. Не редактировать старое принятое решение задним числом.
