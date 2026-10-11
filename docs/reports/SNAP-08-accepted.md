# SNAP-08 — решение после merge исправлений

Дата: 11.10.2026 (Europe/Moscow).
Проверенный merged main: `de5a9578ce5a5effd99150b8d0ba44f538f1502e`.
Исправления: [PR #15](https://github.com/KulikovKA/banking-salary-intelligence-platform/pull/15),
commit `7e2395c65168365961be0d00dbf0c05001610791`.

Решение: **ACCEPTED**. Все критерии SNAP-08 выполнены на merged implementation.

Первоначальная приёмка [SNAP-08-final-acceptance.md](SNAP-08-final-acceptance.md)
с решением BLOCKED относится к `e7218b2` и сохранена как исторический отчёт.
Все пять найденных дефектов устранены; поведение, точные исправления, регрессии и
ограничения описаны в [SNAP-08-remediation.md](SNAP-08-remediation.md).

После merge проверено, что `7e2395c` является ancestor main, а backend, tools,
CI workflow и зависимости main совпадают с проверенной рабочей копией исправлений.
Повтор одинаковых локальных runtime tests не требовался: новых runtime изменений
между проверенным commit и merge нет.

## Evidence приёмки

- Windows: полный backend + TLS probe suite **302 passed, 0 skipped**;
  после последних HTML target изменений relevant suite **26 passed, 0 skipped**.
- Linux: dedicated PostgreSQL, acceptance/pipeline/runner/PDF/HTML/XLSX/normalizer
  suite **77 passed, 0 skipped**.
- Ruff, mypy (58 files), Alembic upgrade/check, docs validator и diff check — PASS.
- Numeric ambiguity/negation/range/sign, actual header evidence, XLSX/HTML footnote
  support, operator repair, rollback/revocation и process descendants покрыты.
- Existing PG tests подтверждают exact provenance, hashes/offsets/locators,
  повторный/concurrent replay, parser-version identities и pending_review без
  автоматического review/publication.
- [CI merged main](https://github.com/KulikovKA/banking-salary-intelligence-platform/actions/runs/38098611992):
  **PASS**, completed/success; backend и frontend jobs success, exact head_sha
  `de5a9578ce5a5effd99150b8d0ba44f538f1502e`. Зелёный CI исходного `e7218b2`
  не используется как PASS исправлений.

NOT RUN локально: полный Linux suite вне указанных cases, memory-exhaustion stress,
frontend/browser E2E и real sources/Groq/real-corpus evaluation. Локальные результаты
не суммируются с перекрывающимися повторными cases и не выдают real-data PASS.

## Обновление статуса

Отдельная ветка `codex/snap-08-done` меняет только SNAP-08 TODO -> DONE в TASKS.json
и MASTER_PLAN, число завершённых задач и описание следующего доступного шага.
Все остальные task statuses, deps, порядок 19 задач, contracts/schema/runtime
сохранены. Этот отчёт фиксирует решение, а не запускает следующую задачу.

SNAP-09 остаётся TODO и в рамках поручения не реализуется.
Product gates неизменны: **S1 BLOCKED; S2/S3 NOT EVALUATED; G1/G2 NOT PASSED**.
