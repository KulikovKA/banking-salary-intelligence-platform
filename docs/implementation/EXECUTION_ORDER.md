# Порядок запуска объединённых заданий

Один WORK-prompt — одно поручение. Запускать после разрешения разработки. Исходные ID — внутренние этапы, не отдельные очереди работ.

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
