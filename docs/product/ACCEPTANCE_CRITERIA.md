# Snapshot acceptance S0–S3

Это новые критерии для fixed corpus. Исторические
[G1/G2](https://github.com/KulikovKA/banking-salary-intelligence-platform/blob/02cd6c8e00e9f84c0528460c7a42835f95a41499/docs/archive/pre-snapshot/product/ACCEPTANCE_CRITERIA.md) остаются NOT PASSED:
scheduled-fetch дни не выполняются, прежние corpus/quality thresholds не объявляются
достигнутыми. Новая цель не требует scheduler и не теряет evidence validation.
PASS требует записанного отчёта с corpus revision, denominator, результатами и
ограничениями; статус разработки не равен data acceptance.

## S0 — техническая готовность на synthetic

Existing unit/PG/E2E green; новые parsers PDF/XLSX/HTML, extraction, review, FTS,
Decimal comparison, Fake/provider-error cases, auth и API/UI E2E работают без сети.
Прямые и косвенные ingestion network requests = 0. Synthetic опубликован только
в isolated test snapshot и отображается как synthetic. Fake не доказывает Groq quality.
S0 позволяет проверить систему, не принять продукт четырёх банков.

## S1 — принятый frozen официальный корпус

Для каждого из четырёх банков минимум один релевантный официальный документ с
условиями зарплатного проекта (можно несколько: тарифы + поясняющие условия).
FAQ/news/marketing без employer tariff условий не заменяют их. Нет требования
искусственно собрать 12 документов. На 100% members есть:
source-specific acquisition/storage/reuse решение выбранного метода, provenance,
original bytes/size/SHA-256, accepted content, parser version/extraction hash,
locators, bank/region/segment/package/date coverage и reviewer.
Unknown scope/date явно отражается и не выдаётся за current verified price.
Права на Groq reuse отдельно; research originals не мигрируют автоматически.
Корпус frozen с manifest hash и exact membership; повторная обработка без замены
immutable extraction. Отзыв/повреждение blocks read, сохраняет audit.
При missing bank — S1 NO-GO; UI может показывать partial demo с явным статусом,
но release как четырёхбанковский продукт запрещён.

## S2 — доказательность и полезность сравнения

Human-reviewed gold: >=40 фактов (>=10/банк), включая числовые и качественные;
>=24 вопроса (>=6/банк) + >=12 межбанковских вопросов (по 2 на каждую из 6 пар).
Набор фиксируется до финального run; tune/holdout разделены по document family,
нет подгонки thresholds под полученный результат. Minimum может не набраться —
это честный data blocker, а не повод генерировать факты.

На реальном holdout: original/evidence linkage 100%; correct value+unit+basis+period
>=98%; required conditions recall >=95%; retrieval Recall@10 >=90%; минимум 30
golden comparison cases (включая unknown/conflict/individual/incompatible scopes)
100% правильных deterministic результатов; unsupported numbers/claims = 0.
Все опубликованные числовые факты вручную проверены; invalid evidence publish = 0.
Показывать точные numerator/denominator и per-bank results, не округлять failed
малый sample в PASS. Synthetic golden arithmetic — отдельная метрика S0.

Полезность отдельно: для каждой из 6 пар минимум 2 реально сопоставимых критерия,
из них >=1 числовой employer fee/cost с общей базой и применимым сценарием.
Полнота стоимости и общего рейтинга не обещается. Индивидуальные/неизвестные цены
показываются честно, но не засчитываются как numeric coverage. Если threshold не
достижим на публичных документах — отчёт NO-GO с coverage matrix; изменение
продуктового обещания принимает владелец отдельно, а не Codex в тесте.

## S3 — работающий закрытый AI-продукт

Authenticated Next.js -> FastAPI -> frozen real corpus -> search/comparison ->
Groq `openai/gpt-oss-120b` -> validated AnswerEnvelope с clickable originals.
Минимум 20 real-model eval вопросов из зафиксированного набора: >=90% корректного
intent/clarification, unsupported claims/numbers = 0, coverage/limitations сохранены.
Повторяемый provider failure/429/budget test даёт безопасный fallback; fallback
не засчитывается как successful Groq answer. Smoke фиксирует model ID/usage/latency,
не secrets. Пока ключа/допуска нет — S3 NOT EVALUATED, не PASS.

Invite login/logout/expiry/CSRF/RBAC, doc access и malicious snippets проверены;
0 известных Critical/High дефектов в этих сценариях. Один API instance, демонстрация
3 одновременных пользователей с bounded rate limits и честным 429/fallback;
latency цели: search/comparison p95 <=2s на локальном corpus, question deadline <=45s,
provider timeout <=20s/call. Free tier не гарантирует SLA или 30 concurrent LLM calls.
Восстановление PG+blob в отдельной среде с проверкой hashes и 100% evidence linkage.
Записаны запуск, env, ограничения и recovery. Только S0+S1+S2+S3 PASS = v1 READY.

На 10.10.2026: S0 ещё не завершён для полного нового pipeline; S1 BLOCKED,
S2/S3 NOT EVALUATED. Existing source-recovery E2E = PASS_SYNTHETIC_ONLY.
