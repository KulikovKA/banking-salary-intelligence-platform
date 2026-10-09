# Stage B — MVP

Предпосылка: принят G2. Цель — закрытая эксплуатационная платформа примерно для 30 сотрудников на проверенном ядре.

## Обязательный объём

1. Приглашения, login/logout/reset, server sessions, User/Analyst/Admin, backend ownership.
2. Сохранение личной истории, structured context с focus_bank и повторное получение фактов на каждый вопрос.
3. Асинхронные question runs, idempotency, retry/poll, claim renderer и работа без доступного LLM.
4. Полные восемь разделов: Dashboard, AI Assistant, Bank Comparison, Changes Feed, Documents, Chat History, Settings, Admin/Analyst.
5. Scheduler, health/freshness, semantic changes, manual review, transactional outbox, in-app subscriptions/notifications.
6. Logs/audit/metrics, privacy retention, license decisions, Compose/TLS, backup и реальное restore rehearsal.
7. E2E/security/load для 30 sessions и независимый финальный аудит с исправлениями.

## Два режима AI

**Технический MVP с Fake:** возможен для проверки workflow и deterministic answer templates, с видимой меткой. Он не обладает подтверждённым качеством интерпретации произвольного языка реальной моделью.

**MVP с внешним LLM:** требует отдельного выбора provider/model/API пользователем, проверки data policy и LLM-003. После интеграции повторяется frozen evaluation; token cost и latency измеряются на реальном API. Нельзя объявить эту возможность готовой по тестам Fake.

## Будущие расширения вне baseline

Private contract import/ACL, OCR pipeline, дополнительные банки/регионы, семантический поиск pgvector по доказанному trigger, внешние уведомления, S3/MinIO вместо local BlobStore, SSO, HA. Наличие расширяемого интерфейса не означает, что расширение включено в 62 задачи.

## Передача в эксплуатацию

Пользователь получает конкретный release candidate, G3/G4 evidence, backup/recovery инструкции, known limitations и независимый статус G5. Не закрывать High/Critical принятием общих рисков. READY WITH LIMITATIONS допустим только для безопасных явно принятых ограничений, например отсутствующего реального API.
