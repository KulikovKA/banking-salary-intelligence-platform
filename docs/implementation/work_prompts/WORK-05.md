# Исполнительское задание WORK-05

**Mode:** `offline` for the checkpoint listed in WORK_INDEX under G0-OFFLINE. No external ingestion requests in any component, including redirects, subresources, parser/browser, and workers. Local and explicitly synthetic fixtures only; synthetic corpus is isolated from real data and publication. Live/acceptance requires G0-LIVE(source) and original gates. Checkpoint DONE is not WORK DONE.

Модель-исполнитель: **GPT-6 Luna**. Настройка reasoning: **High**. Выставить настройку перед запуском; текст задания её не переключает.

Выполни объединённое задание **Четыре банковских адаптера и проверка доступности G1** в проекте Banking Salary Intelligence Platform. Работа с кодом разрешена только после отдельной команды начать реализацию; текущая редакция плана не является такой командой.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/REASONING_GUIDE.md`, `docs/implementation/work_packages/WORK-05.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `SECURITY.md` в architecture и найденный AGENTS.md.

Offline checkpoint dependency: WORK-04 checkpoint. Live adapter requests additionally require a source-specific G0-LIVE decision; full G1 acceptance retains all four banks.

Причина уровня reasoning: Разные сайты и форматы; оценка полноты не сводится к HTTP 200. Многодневную проверку нельзя заменить рассуждением.

Не меняй утверждённые границы монолита, DTO и схемы без ADR; не выбирай провайдера за пользователя; не обходи защиту банков. Unknown не равно 0, LLM не рассчитывает тарифы, источник сохраняется целиком. Не объединяй этапы в одну непроверяемую правку. Делай checkpoint после каждого внутреннего этапа, не останавливая разрешённую работу на ненужное повторное подтверждение.

В конце: отчёт `docs/reports/WORK-05.md`, список изменённых файлов, точные команды/результаты тестов, AC evidence по каждому внутреннему этапу, ограничения. Обнови WORK_INDEX/MASTER_PLAN и TASK_INDEX/внутренние ТЗ. DONE только при выполненных критериях. Оформление уже готового отчёта/статусов допустимо на Light, без нового кода и без переоценки тестов.
