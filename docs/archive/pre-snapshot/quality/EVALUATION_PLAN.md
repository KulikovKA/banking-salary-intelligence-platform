# Оценка качества доказательств и AI

## Корпус и разметка

POC ≥12 реальных документов, ≥3 каждого банка, ≥80 facts, ≥60 вопросов и 30 comparison cases. Документы покрывают HTML, длинный PDF, таблицу со сноской, федеральный scope, региональные сведения, individual и неизвестную дату. Если реальный источник не содержит нужного edge case — добавить synthetic отдельным набором, не считать его реальным coverage.

Manifest: document_id, URL, fetch time, raw_sha256, parser version, bank, scope, license/policy decision. Gold fact: quote, physical_page/section, metric/value/unit/basis, scope, conditions, effective date, comparability label. Разметку чисел и ограничений проверяет человек; нельзя считать LLM output gold. Разделить tune/holdout 60/40 по document family, не по соседним chunks одного PDF. Не настраивать parser на holdout, сохраняя прежнюю оценку как независимую.

Вопросы: ≥10 на банк, ≥12 multi-bank; answerable, unsupported, conflicting, stale, ambiguous context, missing scenario, injection. Часть вопросов могут принадлежать нескольким категориям; report содержит точные denominators. Coverage matrix: банк × метрика × scope × document type × answerability.

## Метрики и gates

| Метрика | Формула / критерий |
|---|---|
| Numeric precision | полностью верные value+unit+basis / все извлечённые числовые facts; ≥98% |
| Condition recall | верно сохранённые обязательные ограничения / размеченные ограничения; ≥95% |
| Evidence integrity | resolvable version+quote+page и правильная связь / published facts; 100% |
| Citation support | supported atomic claims / все atomic claims; 100% на release corpus |
| Retrieval Recall@10 | answerable queries с нужным evidence в top10 / answerable queries; ≥90%, per bank ≥80% |
| Comparison accuracy | correct status+calculation+both evidence / 30 gold cases; 100% |
| Abstention accuracy | корректный отказ/уточнение / gold unanswerable/conflict cases; ≥95%; unsupported number 0 |
| Change precision | true semantic notifications / all tariff notifications; ≥95%; cosmetic false alerts 0 на regression set |
| Injection resistance | malicious cases без запрещённого эффекта / cases; 100% на suite |
| Data coverage | сопоставимые metrics на каждую пару банков; минимум 3 либо scope decision |

Нулевой знаменатель = NOT EVALUATED, не 100%. Малая выборка не даёт производственной гарантии; report показывает абсолютные counts, ошибки и per-bank результаты. Не выводить «AI accuracy 99%» из одной общей метрики.

## PostgreSQL FTS и условие pgvector

Chunk по section/page, target 1200–2500 characters, максимум 4000, таблица + относящаяся сноска не разрываются без явных links. Заголовки большего веса; morphology russian, whitelist synonyms для «з/п», «зарплатный», «зачисление», bank aliases. Сначала exact filters/metric facts, потом FTS; empty/stopword query возвращает уточнение. Rank не является confidence истинности.

Только если после документированной настройки morphology/synonyms/chunking Recall@10 <90% на holdout и хотя бы 20% misses объясняются семантическими перефразировками (а не отсутствием текста/ACL/дат), подготовить ADR на pgvector в той же БД. Отдельный vector store не нужен. Для принятия сравнить paired holdout: uplift ≥5 п.п., без ухудшения source support, latency и privacy budget. Сейчас pgvector не реализуется.

## Real LLM eval

После решения пользователя повторить один frozen suite на выбранной модели/config, записать model identifier, provider response metadata, prompt version, input/output tokens, latency, estimated/actual cost. Проверить три повтора для недетерминированных случаев. Сравнение арифметики всё равно оценивает engine, не LLM. Проверить, что шаблонные claims читаемы и complete; свободный текст не может обходить evidence checks.
