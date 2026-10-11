# Follow-up интегратору: desktop chat scope

Пользователь прямо заменил прежнее решение о внешнем frontend: самостоятельная
разработка desktop AI-chat в текущем Next.js scaffold. Результат находится в ветке
`codex/frontend-chat-mvp`, base `af807da`; отчёт —
[FRONTEND_CHAT_MVP_REPORT.md](FRONTEND_CHAT_MVP_REPORT.md).

После review/merge отдельным integrator commit обновить AGENTS.md, MASTER_PLAN.md,
FRONTEND_HANDOFF.md и TASKS.json под это решение. Сохранить 19 SNAP-ID и честные
статусы backend/продуктовых gates. Этот независимый DEMO не завершает SNAP-17,
не доказывает FE API integration и не подтверждает S0–S3/G1/G2.

SNAP-16 owner: передать публичный TS контракт, правила auth/CSRF, synthetic
AnswerEnvelope/ComparisonResult и typed errors. В отдельной интеграционной задаче
подключить backend adapter к ChatTransport, отобразить реальные revision/date,
scope/conditions/coverage/limitations и безопасные protected originals. UI display
models в `lib/chat/models.ts` не объявлены public DTO. Денежная арифметика и
вычисление сравнений остаются на backend.

Если настоящий streaming будет нужен, сначала согласовать изменение текущего
синхронного API-контракта и его tests; не создавать параллельный неутверждённый SSE
endpoint. Уточнить формат событий/порядок/финальную evidence-сборку и отмену.
Groq key остаётся серверным, передача данных провайдеру и real-source acceptance
по-прежнему требуют собственных допусков.

Dependency owner: полный npm audit показывает 4 high в существующей dev-цепочке
`@next/eslint-plugin-next@16.4.0 → fast-glob → micromatch → braces@3.0.3`.
Runtime-only audit: 0. Force fix предлагает major downgrade Next ESLint plugin;
зависимости этой цепочки в frontend PR не менялись. Отдельно выбрать совместимое
исправление и проверить lint/build; не смешивать это с переносом чата.
