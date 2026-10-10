# Зарплатная аналитика: пакет проектирования v1.1

Дата: 09.10.2026. Статус: спецификация подготовлена для согласования; разработка не начата.

**Обновление плана:** 62 исходные задачи объединены в 22 WORK-блока (20 Luna + 2 Astra), каждому назначен reasoning; [таблица и порядок](implementation/MASTER_PLAN.md), [правила уровней](implementation/REASONING_GUIDE.md).

Главный документ исполнения — [MASTER_PLAN](implementation/MASTER_PLAN.md). Начать чтение с [разбора Miro](architecture/ARCHITECTURE_REVIEW.md), затем [архитектуры](architecture/OVERVIEW.md). Все предлагаемые изменения к v1.0 явно отделены от исходных требований. LLM-провайдер не выбран.

| Результат запроса | Документы |
|---|---|
| A. Architecture Review | [Аудит схем и рабочей папки](architecture/ARCHITECTURE_REVIEW.md) |
| B. Final Architecture Specification | [Overview](architecture/OVERVIEW.md), [компоненты](architecture/COMPONENTS.md), [потоки](architecture/DATA_FLOW.md), [безопасность](architecture/SECURITY.md), [эксплуатация](architecture/OPERATIONS.md) |
| C. Project Structure | [Структура будущего проекта](architecture/PROJECT_STRUCTURE.md) |
| D. Database Design | [БД](architecture/DATABASE_DESIGN.md), [доменные контракты](architecture/DOMAIN_CONTRACTS.md), [API](architecture/API_CONTRACTS.md) |
| E–H. Roadmap, backlog, зависимости, задания Luna | [MASTER_PLAN](implementation/MASTER_PLAN.md), [порядок](implementation/EXECUTION_ORDER.md), [граф](implementation/DEPENDENCIES.md), каталоги tasks и luna_prompts |
| I. Testing & Evaluation | [Стратегия тестирования](quality/TEST_STRATEGY.md), [оценка качества](quality/EVALUATION_PLAN.md) |
| J. Final Review Checklist | [Независимый аудит](quality/REVIEW_CHECKLIST.md) |
| Требования и ограничения | [Требования](product/REQUIREMENTS.md), [сценарии](product/USER_SCENARIOS.md), [приёмка](product/ACCEPTANCE_CRITERIA.md), [риски](quality/RISKS.md) |
| Проверенные внешние основания | [Исследование источников](research/SOURCES.md) |
| Примеры обмена и статусы | [Примеры контрактов](architecture/CONTRACT_EXAMPLES.md) |
| Проверка самого пакета | [Результаты проверки документации](quality/DOCUMENTATION_VALIDATION.md) |

Это документация будущей реализации. Указанные пути `backend/`, `frontend/`, `infra/`, `tests/` пока не созданы. Статусы готовности приложения не присваивались. Примеры значений тарифов синтетические, их нельзя использовать как сведения о банках.

## Правила согласованности

1. Приоритет: явные требования пользователя → утверждённые ADR → DOMAIN_CONTRACTS / DATABASE_DESIGN / API_CONTRACTS → ТЗ задач → примеры.
2. Разночтение нельзя исправлять молча. Оформить ADR, перечислить затронутые задачи и тесты.
3. Документация v1.1 является согласованным предложением; статус `proposed` не означает утверждения пользователем.
4. Новая сессия Luna обязана прочитать MASTER_PLAN, центральные контракты и ТЗ конкретной задачи. Отсутствующая зависимость не считается реализованной.
5. Не запускать реализацию по одному факту существования этих документов: пользователь запросил сейчас только проектирование.
