# Execution order for grouped work

One WORK prompt is one assignment. WORK-02 through WORK-09 may run only their listed offline checkpoint under G0-OFFLINE; live/acceptance work waits for source-specific G0-LIVE and original gates. See [ADR-006](../architecture/ADR/006-g0-offline-and-live-ingestion.md).

**Offline order:** WORK-02 -> WORK-03 -> WORK-04. After WORK-04, WORK-05 adapter scaffolds and QA harness can run alongside WORK-06 synthetic implementation. WORK-07 depends on offline WORK-04/06; WORK-08 depends on 04/06/07; WORK-09 evaluation harness depends on WORK-08. These checkpoints do not complete the full blocks.

**Live/acceptance path:** Continue WORK-01/SRC-001 as a separate blocked branch. After a source receives approval, retrieve and content-review its documents, then gather real scheduled observations. Full WORK-05/G1 requires all four banks and three distinct days within one week. Real-corpus checks in WORK-06 through WORK-09 and G2 use accepted real documents. Do not start WORK-10 through WORK-19 before user acceptance of G2.

**Modes:** WORK-01 is `live/acceptance` for retrieval (manifest design may be offline); WORK-02 through WORK-09 are `offline` for admitted checkpoints and `live/acceptance` only for explicitly deferred work; WORK-10 through WORK-19 are `live/acceptance` after G2; WORK-20 through WORK-22 are `live/acceptance` audit/fix verification. Each prompt states its mode.

1. **WORK-01 — Источники и границы покрытия**. GPT-6 Luna, **High**. [Передаваемый prompt](work_prompts/WORK-01.md), [состав и приёмка](work_packages/WORK-01.md).
2. **WORK-02 — Окружение, репозиторий и базовая БД**. GPT-6 Luna, **Medium**. [Передаваемый prompt](work_prompts/WORK-02.md), [состав и приёмка](work_packages/WORK-02.md).
3. **WORK-03 — Архив, безопасная загрузка и фоновые задания**. GPT-6 Luna, **Extra High**. [Передаваемый prompt](work_prompts/WORK-03.md), [состав и приёмка](work_packages/WORK-03.md).
4. **WORK-04 — HTML/PDF, структура документов и версии**. GPT-6 Luna, **High**. [Передаваемый prompt](work_prompts/WORK-04.md), [состав и приёмка](work_packages/WORK-04.md).
5. **WORK-05 — Четыре банковских адаптера и проверка доступности G1**. GPT-6 Luna, **High**. [Передаваемый prompt](work_prompts/WORK-05.md), [состав и приёмка](work_packages/WORK-05.md).
6. **WORK-06 — Тарифные факты, проверка и публикация**. GPT-6 Luna, **Extra High**. [Передаваемый prompt](work_prompts/WORK-06.md), [состав и приёмка](work_packages/WORK-06.md).
7. **WORK-07 — Полнотекстовый поиск и детерминированные сравнения**. GPT-6 Luna, **Extra High**. [Передаваемый prompt](work_prompts/WORK-07.md), [состав и приёмка](work_packages/WORK-07.md).
8. **WORK-08 — Ассистент POC, Fake LLM, API и минимальный экран**. GPT-6 Luna, **High**. [Передаваемый prompt](work_prompts/WORK-08.md), [состав и приёмка](work_packages/WORK-08.md).
9. **WORK-09 — Оценка ядра и приёмка POC G2**. GPT-6 Luna, **High**. [Передаваемый prompt](work_prompts/WORK-09.md), [состав и приёмка](work_packages/WORK-09.md).
10. **WORK-10 — Пользователи, приглашения, сессии и права доступа**. GPT-6 Luna, **High**. [Передаваемый prompt](work_prompts/WORK-10.md), [состав и приёмка](work_packages/WORK-10.md).
11. **WORK-11 — Личная история, память и надёжное выполнение вопросов**. GPT-6 Luna, **Extra High**. [Передаваемый prompt](work_prompts/WORK-11.md), [состав и приёмка](work_packages/WORK-11.md).
12. **WORK-12 — Мониторинг изменений, уведомления и полный API**. GPT-6 Luna, **High**. [Передаваемый prompt](work_prompts/WORK-12.md), [состав и приёмка](work_packages/WORK-12.md).
13. **WORK-13 — Полный пользовательский и административный интерфейс**. GPT-6 Luna, **Medium**. [Передаваемый prompt](work_prompts/WORK-13.md), [состав и приёмка](work_packages/WORK-13.md).
14. **WORK-14 — Логи, метрики и эксплуатационный аудит**. GPT-6 Luna, **Medium**. [Передаваемый prompt](work_prompts/WORK-14.md), [состав и приёмка](work_packages/WORK-14.md).
15. **WORK-15 — Проверка авторизации, SSRF и prompt injection**. GPT-6 Luna, **Extra High**. [Передаваемый prompt](work_prompts/WORK-15.md), [состав и приёмка](work_packages/WORK-15.md).
16. **WORK-16 — ПД, лицензии и удаление данных**. GPT-6 Luna, **High**. [Передаваемый prompt](work_prompts/WORK-16.md), [состав и приёмка](work_packages/WORK-16.md).
17. **WORK-17 — Подключение выбранного LLM API**. GPT-6 Luna, **High**. [Передаваемый prompt](work_prompts/WORK-17.md), [состав и приёмка](work_packages/WORK-17.md).
18. **WORK-18 — Backup, восстановление и production-развёртывание**. GPT-6 Luna, **High**. [Передаваемый prompt](work_prompts/WORK-18.md), [состав и приёмка](work_packages/WORK-18.md).
19. **WORK-19 — Сквозная приёмка и нагрузка 30 пользователей**. GPT-6 Luna, **High**. [Передаваемый prompt](work_prompts/WORK-19.md), [состав и приёмка](work_packages/WORK-19.md).
20. **WORK-20 — Независимый финальный аудит**. Astra, **—**. [Передаваемый prompt](work_prompts/WORK-20.md), [состав и приёмка](work_packages/WORK-20.md).
21. **WORK-21 — Исправления по замечаниям аудита**. GPT-6 Luna, **Extra High**. [Передаваемый prompt](work_prompts/WORK-21.md), [состав и приёмка](work_packages/WORK-21.md).
22. **WORK-22 — Независимая повторная проверка и итоговый статус**. Astra, **—**. [Передаваемый prompt](work_prompts/WORK-22.md), [состав и приёмка](work_packages/WORK-22.md).

После WORK-05 принять G1; после WORK-09 принять G2. WORK-17 можно пропустить только как BLOCKED provider branch, продолжив независимую работу с Fake. WORK-20/22 исполняет Astra. Исключения reasoning внутри WORK-08/13 и режим Light для отчётов описаны в [REASONING_GUIDE](REASONING_GUIDE.md).
