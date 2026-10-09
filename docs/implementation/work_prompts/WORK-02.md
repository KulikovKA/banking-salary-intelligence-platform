# Исполнительское задание WORK-02

**Mode:** `offline` for the checkpoint listed in WORK_INDEX under G0-OFFLINE. No external ingestion requests in any component, including redirects, subresources, parser/browser, and workers. Local and explicitly synthetic fixtures only; synthetic corpus is isolated from real data and publication. Live/acceptance requires G0-LIVE(source) and original gates. Checkpoint DONE is not WORK DONE.

Модель-исполнитель: **GPT-6 Luna**. Настройка reasoning: **Medium**. Выставить настройку перед запуском; текст задания её не переключает.

Выполни объединённое задание **Окружение, репозиторий и базовая БД** в проекте Banking Salary Intelligence Platform. Работа с кодом разрешена только после отдельной команды начать реализацию; текущая редакция плана не является такой командой.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/REASONING_GUIDE.md`, `docs/implementation/work_packages/WORK-02.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `SECURITY.md` в architecture и найденный AGENTS.md.

Offline checkpoint dependencies: none. WORK-01 remains a live/source dependency only; it does not block this offline checkpoint.

Причина уровня reasoning: Работа по готовой структуре и схеме; при изменении миграционного контракта повысить до High.

Не меняй утверждённые границы монолита, DTO и схемы без ADR; не выбирай провайдера за пользователя; не обходи защиту банков. Unknown не равно 0, LLM не рассчитывает тарифы, источник сохраняется целиком. Не объединяй этапы в одну непроверяемую правку. Делай checkpoint после каждого внутреннего этапа, не останавливая разрешённую работу на ненужное повторное подтверждение.

В конце: отчёт `docs/reports/WORK-02.md`, список изменённых файлов, точные команды/результаты тестов, AC evidence по каждому внутреннему этапу, ограничения. Обнови WORK_INDEX/MASTER_PLAN и TASK_INDEX/внутренние ТЗ. DONE только при выполненных критериях. Оформление уже готового отчёта/статусов допустимо на Light, без нового кода и без переоценки тестов.
