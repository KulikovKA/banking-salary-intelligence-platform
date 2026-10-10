# Исполнительское задание WORK-15

**Mode:** `live/acceptance` after accepted G2 and all incoming gates. Use a source only with active G0-LIVE(source). Never bypass TLS, SSRF, or source policy. Fake/local tests do not count as real acceptance.

Модель-исполнитель: **GPT-6 Luna**. Настройка reasoning: **Extra High**. Выставить настройку перед запуском; текст задания её не переключает.

Выполни объединённое задание **Проверка авторизации, SSRF и prompt injection** в проекте Banking Salary Intelligence Platform. Работа с кодом разрешена только после отдельной команды начать реализацию; текущая редакция плана не является такой командой.

Сначала прочитай `docs/implementation/MASTER_PLAN.md`, `docs/implementation/REASONING_GUIDE.md`, `docs/implementation/work_packages/WORK-15.md`, `docs/architecture/DOMAIN_CONTRACTS.md`, `DATABASE_DESIGN.md`, `API_CONTRACTS.md`, `SECURITY.md` в architecture и найденный AGENTS.md.

Входящие этапы в порядке исполнения: SEC-001, SEC-002. Их ТЗ лежат в `docs/implementation/tasks/ID.md`; выполни все указанные подзадачи, контракты, обработку ошибок, тесты и AC. Dependencies блока: WORK-11, WORK-13, WORK-14. Проверяй реальные результаты, а не наличие названий папок.

Причина уровня reasoning: Нужны adversarial сценарии, анализ обходов и проверка отсутствия запрещённых эффектов.

Не меняй утверждённые границы монолита, DTO и схемы без ADR; не выбирай провайдера за пользователя; не обходи защиту банков. Unknown не равно 0, LLM не рассчитывает тарифы, источник сохраняется целиком. Не объединяй этапы в одну непроверяемую правку. Делай checkpoint после каждого внутреннего этапа, не останавливая разрешённую работу на ненужное повторное подтверждение.

В конце: отчёт `docs/reports/WORK-15.md`, список изменённых файлов, точные команды/результаты тестов, AC evidence по каждому внутреннему этапу, ограничения. Обнови WORK_INDEX/MASTER_PLAN и TASK_INDEX/внутренние ТЗ. DONE только при выполненных критериях. Оформление уже готового отчёта/статусов допустимо на Light, без нового кода и без переоценки тестов.
