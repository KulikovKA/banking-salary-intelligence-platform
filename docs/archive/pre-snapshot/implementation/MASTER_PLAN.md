# MASTER PLAN — объединённые задания

Обновлено 09.10.2026: WORK-01/SRC-001 остаётся BLOCKED после проверки новых URL Кубань Кредит, ВТБ и Альфа. Архитектура v1.1 принята как база. Два PDF Кубань Кредит запрещены robots и не сохранены; TLS мешает локальной проверке ВТБ/Альфа. Bank-side permission и актуальные employer tariff originals не подтверждены.

## Текущий статус

Updated 2026-10-10: WORK-01/SRC-001 remains BLOCKED. ADR-006 is approved with changes: listed WORK-02?09 checkpoints may proceed under G0-OFFLINE; G0-LIVE(source) is not approved for any bank. Bank permission and current employer tariff originals remain unconfirmed.

## С чего начинать

После разрешения реализации передавать модели **один WORK-prompt** из списка ниже, а не 62 разрозненных поручения. Первый — WORK-01 / Luna High. Внутри блока модель выполняет этапы по порядку и сохраняет checkpoints; не требуется новый чат/поручение для каждого старого ID.

[Порядок и промпты](EXECUTION_ORDER.md) · [Уровни reasoning](REASONING_GUIDE.md) · [Граф](DEPENDENCIES.md) · [Пакет архитектуры](../README.md) · [POC](POC_SCOPE.md) · [MVP](MVP_SCOPE.md) · [Приёмка](../product/ACCEPTANCE_CRITERIA.md).

## Рабочие блоки

| Блок | Объединённая задача | Исполнитель | Reasoning | Внутренние этапы | Зависимости | Статус |
|---|---|---|---|---|---|---|
| [WORK-01](work_packages/WORK-01.md) | Источники и границы покрытия | GPT-6 Luna | **High** | SRC-001 | — | **BLOCKED** — bank-side permission/terms/rate limits и employer tariff originals не подтверждены |
| [WORK-02](work_packages/WORK-02.md) | Environment, repository, and base DB | GPT-6 Luna | **Medium** | INF-001, INF-002, DB-001 | None for offline checkpoint; WORK-01 removed from full WORK-02 dependency | **IN_PROGRESS** ? INF-001 complete; INF-002/DB-001 under G0-OFFLINE; PostgreSQL runtime awaits Docker daemon |
| [WORK-03](work_packages/WORK-03.md) | Архив, безопасная загрузка и фоновые задания | GPT-6 Luna | **Extra High** | STO-001, NET-001, JOB-001 | WORK-02 | TODO |
| [WORK-04](work_packages/WORK-04.md) | HTML/PDF, структура документов и версии | GPT-6 Luna | **High** | HTML-001, PDF-001, DB-002, TXT-001, VER-001 | WORK-02, WORK-03 | TODO |
| [WORK-05](work_packages/WORK-05.md) | Четыре банковских адаптера и проверка доступности G1 | GPT-6 Luna | **High** | ING-001, ING-002, ING-003, ING-004, QA-001 | WORK-01, WORK-04 | TODO |
| [WORK-06](work_packages/WORK-06.md) | Тарифные факты, проверка и публикация | GPT-6 Luna | **Extra High** | DB-003, FACT-001, FACT-002, FACT-003, FACT-004 | WORK-04, WORK-05 | TODO |
| [WORK-07](work_packages/WORK-07.md) | Полнотекстовый поиск и детерминированные сравнения | GPT-6 Luna | **Extra High** | SRCH-001, CMP-001, CMP-002 | WORK-04, WORK-06 | TODO |
| [WORK-08](work_packages/WORK-08.md) | Ассистент POC, Fake LLM, API и минимальный экран | GPT-6 Luna | **High → AI-002: Extra High** | LLM-001, AI-001, AI-002, DOC-001, API-001, UI-001 | WORK-04, WORK-06, WORK-07 | TODO |
| [WORK-09](work_packages/WORK-09.md) | Оценка ядра и приёмка POC G2 | GPT-6 Luna | **High** | QA-002 | WORK-05, WORK-08 | TODO |
| [WORK-10](work_packages/WORK-10.md) | Пользователи, приглашения, сессии и права доступа | GPT-6 Luna | **High** | DB-004, AUTH-001, AUTH-002, AUTH-003 | WORK-06, WORK-08, WORK-09 | TODO |
| [WORK-11](work_packages/WORK-11.md) | Личная история, память и надёжное выполнение вопросов | GPT-6 Luna | **Extra High** | LLM-002, CHAT-001, CHAT-002, AI-003 | WORK-03, WORK-08, WORK-10 | TODO |
| [WORK-12](work_packages/WORK-12.md) | Мониторинг изменений, уведомления и полный API | GPT-6 Luna | **High** | DB-005, CHG-001, NTF-001, JOB-002, API-002 | WORK-03, WORK-06, WORK-10, WORK-11 | TODO |
| [WORK-13](work_packages/WORK-13.md) | Полный пользовательский и административный интерфейс | GPT-6 Luna | **Medium → UI-003/006: High** | UI-002, UI-003, UI-004, UI-005, UI-006 | WORK-07, WORK-08, WORK-11, WORK-12 | TODO |
| [WORK-14](work_packages/WORK-14.md) | Логи, метрики и эксплуатационный аудит | GPT-6 Luna | **Medium** | OPS-001 | WORK-12 | TODO |
| [WORK-15](work_packages/WORK-15.md) | Проверка авторизации, SSRF и prompt injection | GPT-6 Luna | **Extra High** | SEC-001, SEC-002 | WORK-11, WORK-13, WORK-14 | TODO |
| [WORK-16](work_packages/WORK-16.md) | ПД, лицензии и удаление данных | GPT-6 Luna | **High** | SEC-003 | WORK-01, WORK-14 | TODO |
| [WORK-17](work_packages/WORK-17.md) | Подключение выбранного LLM API | GPT-6 Luna | **High** | LLM-003 | WORK-09, WORK-11, WORK-16 | TODO |
| [WORK-18](work_packages/WORK-18.md) | Backup, восстановление и production-развёртывание | GPT-6 Luna | **High** | OPS-002, OPS-003 | WORK-03, WORK-14, WORK-15, WORK-16 | TODO |
| [WORK-19](work_packages/WORK-19.md) | Сквозная приёмка и нагрузка 30 пользователей | GPT-6 Luna | **High** | QA-003, LOAD-001 | WORK-13, WORK-18 | TODO |
| [WORK-20](work_packages/WORK-20.md) | Независимый финальный аудит | Astra | **—** | REV-001 | WORK-15, WORK-16, WORK-19 | TODO |
| [WORK-21](work_packages/WORK-21.md) | Исправления по замечаниям аудита | GPT-6 Luna | **Extra High** | REV-002 | WORK-20 | TODO |
| [WORK-22](work_packages/WORK-22.md) | Независимая повторная проверка и итоговый статус | Astra | **—** | REV-003 | WORK-21 | TODO |


## Offline checkpoints and execution modes

WORK-02?WORK-09 have separate `offline_checkpoint` records in WORK_INDEX with `task_ids`, `deps`, `required_gates`, `status`, and `evidence`. Offline graph: WORK-02 has no source dependency; WORK-03 depends on offline 02; WORK-04 on 02/03; WORK-05 and WORK-06 on 04; WORK-07 on 04/06; WORK-08 on 04/06/07; WORK-09 on 08. Each requires G0-OFFLINE. A DONE checkpoint does not complete its WORK block or accept G1/G2. Full acceptance dependencies remain, except WORK-01 is removed from WORK-02.

Offline/test/CI forbids external ingestion requests. Synthetic data is isolated from real archives, manifests, and publication. WORK-05 adapter scaffolds and WORK-06?09 harness work may use Fake/synthetic fixtures; live acceptance waits for exact G0-LIVE(source) and original gates. WORK-01 remains BLOCKED. WORK-10?WORK-19 remain behind accepted G2.

## Gates и исключения

- G0-OFFLINE admits only listed local/synthetic checkpoints without external ingestion requests. G0-LIVE(source) requires a separate exact host/path decision before network access; no source is approved. See ADR-006.
- G1 ? full WORK-05/QA-001: approved sources for all four banks and scheduled fetch checks on at least three different days within one week. Manual import does not count.
- G2 ? full WORK-09 on real documents and gold/holdout using original ACCEPTANCE_CRITERIA metrics. Synthetic harness is not acceptance. WORK-10?19 still require accepted G2.
- WORK-17 ждёт выбора LLM/provider пользователем. Остальные независимые блоки продолжаются с Fake; production real AI и его финальный аудит требуют завершённого WORK-17.
- G3/G4 — security, legal decisions активных потоков, E2E/restore/load. WORK-20/22 — независимый аудит Astra; WORK-21 — исправления Luna.

## Статусы и источники истины

Актуальный порядок — EXECUTION_ORDER; единицы исполнения — WORK_INDEX.json и таблица этого плана. TASK_INDEX.json и `tasks/` содержат исходные 62 этапа, теперь с work_package/reasoning. Файлы `luna_prompts/` сохранены для точечного продолжения этапа, но основной запуск — `work_prompts/WORK-XX.md`.

WORK DONE требует DONE всех входящих этапов, соответствующих AC и gates; BLOCKED содержит причину/владельца решения; незавершённые тесты не DONE. Синхронизировать статусы MASTER_PLAN, WORK_INDEX, TASK_INDEX и карточек. [DETAILED_BACKLOG](DETAILED_BACKLOG.md) и DETAILED_* — историческая детализация, не второй план исполнения.

Каждый блок включает конкретные внутренние ТЗ с файлами, алгоритмами, ошибками и тестами. Укрупнение уменьшает число поручений, но не отменяет последовательность миграций, тесты и независимую приёмку. Дополнительных агентов и реализации текущим запросом не запускается.
