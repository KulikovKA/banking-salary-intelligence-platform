# Архив до snapshot v1

`pre-snapshot/` — предыдущие планы, 22 WORK пакета/промпта, 62 task cards и
Luna prompts, dependency indices, старые architecture/product/quality/research
документы и root README/MASTER_PLAN. Они не являются активной спецификацией.
Смысл и исторические статусы сохранены; local Markdown links перенаправлены
к перемещённым файлам. Разрешения и доказательства не удалены.

- [Прежний master plan](pre-snapshot/implementation/MASTER_PLAN.md)
- [Прежние gates](pre-snapshot/product/ACCEPTANCE_CRITERIA.md)
- [Исторические ADR](pre-snapshot/architecture/ADR/README.md)
- [Research sources](pre-snapshot/research/SOURCES.md)
- [Полный аудит пофайлово](../reports/evidence/snapshot-document-audit-2026-10-10.json)
- [Reports и сохранённые evidence](../reports/)
- [Новый план](../implementation/MASTER_PLAN.md)

Файлы не удалены навсегда: прежние документы убраны из активного дерева и
заменены компактной snapshot спецификацией. Exact byte duplicates при аудите
не обнаружены, поэтому исторические материалы не уничтожались как «дубликаты».
`sha256_before` в inventory относится к исходным bytes; после relocation links
Markdown hash может отличаться. JSON evidence/indices сохранены без изменений
содержания; `sha256_lf_before` учитывает стандартную LF/CRLF нормализацию Git.
