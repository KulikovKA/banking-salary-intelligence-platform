# Передача внешнего frontend — SNAP-17 / FE-01–FE-04

Родитель: [SNAP-17](prompts/SNAP-17.md),
[план и DAG](MASTER_PLAN.md), [реестр SNAP](TASKS.json).
Контракт: [API_CONTRACTS](../architecture/API_CONTRACTS.md),
[безопасность](../architecture/SECURITY.md),
[приёмка S0–S3](../product/ACCEPTANCE_CRITERIA.md).

## Владельцы и обязательные входы

Внешний frontend-разработчик создаёт дизайн, страницы/компоненты, личный кабинет,
сравнение банков, UI чата/ответов, адаптивность и пользовательские сценарии.
Наша backend-команда владеет FastAPI, PostgreSQL/миграциями, тарифным pipeline и
ручной проверкой, поиском/comparison, Groq/ассистентом, auth/security/API и тестами.
Наша команда интеграции принимает, переносит и подключает переданный frontend;
интегратор принимает evidence и обновляет этот tracker после sequential merge.
Отдельный второй UI с нуля не создаётся.

На 11.10.2026 передача внешнего frontend **не подтверждена**. Существующий
`frontend/` — стартовый Next.js scaffold; он не является полученным внешним UI.
Таблица ниже фиксирует ожидаемый пакет, а не полученные артефакты.

| Вход | Кто передаёт / принимает | Состояние |
|---|---|---|
| URL репозитория или архив исходников, exact commit/tag и SHA-256 архива при архивной передаче | Внешний разработчик / интеграционная команда | НЕ ПОЛУЧЕНО |
| Структура, инструкции запуска, Node/npm версии, package manifest и lockfile, список зависимостей | Внешний разработчик / интеграционная команда | НЕ ПОЛУЧЕНО |
| Лицензии кода, зависимостей, шрифтов/изображений и права на перенос/использование | Внешний разработчик / интегратор | НЕ ПОЛУЧЕНО |
| Согласованный дизайн, перечень экранов/ролей/сценариев, макеты состояний и известных дефектов | Внешний разработчик / интеграционная команда | НЕ ПОЛУЧЕНО |
| Merged API, OpenAPI/TS DTO revision, auth/cookie/Origin/CSRF и typed error правила, synthetic примеры | Владелец [SNAP-16](prompts/SNAP-16.md) / интеграционная команда | ОЖИДАЕТ SNAP-16 |
| Dedicated PostgreSQL с migrations, frozen synthetic snapshot, synthetic identities analyst/admin, Fake LLM | Backend-команда / интеграционная команда | E2E интегрированного продукта ещё не выполнен |

Backend-приоритет: **SNAP-08 -> SNAP-09 -> (SNAP-10 и SNAP-11) -> SNAP-14 -> SNAP-16**.
Внешний разработчик может работать параллельно; наша команда начинает любой FE
этап только после проверяемой передачи исходников и merged SNAP-16 (включая его
backend-зависимости). До этого не выполнять приёмку, перенос, адаптацию или
подключение frontend. Никакая длительность ожидания не заменяет передачу.

## Tracker подзадач

FE-ID не расширяют DAG из 19 SNAP-ID. SNAP-17 сохраняет зависимость SNAP-16 и
статус TODO; BLOCKED ниже отражает отсутствующие входы, а не новую готовую задачу.
Интегратор обновляет статус/причину/evidence каждой строки после принятого отчёта.
Допустимые статусы FE: TODO, IN_PROGRESS, BLOCKED, DONE. DONE требует всех AC этапа
и ссылки на отчёт с exact revision, результатами проверок и unresolved issues.

| ID / этап | Владелец | Зависимости | Status | Причина / evidence |
|---|---|---|---|---|
| FE-01 — Приёмка внешнего frontend | Наша команда интеграции; внешний разработчик передаёт пакет | Переданные исходники/лицензии/зависимости + merged SNAP-16 | BLOCKED | Исходники не получены, SNAP-16 TODO; evidence отсутствует |
| FE-02 — Перенос и переработка frontend | Наша команда интеграции; внешний разработчик согласует дизайн/follow-up | FE-01 DONE + merged SNAP-16 | BLOCKED | FE-01 не принят; evidence отсутствует |
| FE-03 — Подключение к backend | Наша команда интеграции; SNAP-16 владеет API/DTO | FE-02 DONE + merged SNAP-16 и runnable API | BLOCKED | FE-02/API не готовы; evidence отсутствует |
| FE-04 — Интеграционные проверки | Наша команда интеграционных тестов; интегратор принимает | FE-03 DONE + real FastAPI/PG + frozen synthetic corpus/Fake | BLOCKED | Интеграция не выполнена; evidence отсутствует |

## FE-01 — Приёмка внешнего frontend

Действия: получить и зафиксировать пакет; проверить структуру, лицензии, качество
кода и безопасность; сопоставить экраны/сценарии с API_CONTRACTS и merged
OpenAPI/TS DTO. Проверить отсутствие секретов и payroll personal data, клиентских
Groq вызовов, произвольного fetch банков, небезопасного HTML и token localStorage.

Критерии приёмки:

- В отчёте записаны источник, exact revision/hash, состав и версии зависимостей,
  лицензии/права на перенос, воспроизводимые инструкции и согласованный дизайн.
- Составлена матрица экран/роль/действие -> route/DTO -> состояния/ошибки/evidence.
  Она покрывает login/invite/logout, snapshot/scenario, поиск, comparison,
  assistant, protected documents, admin review/freeze.
- Каждая несовместимость, отсутствующий экран/состояние, дефект безопасности или
  изменение зависимости имеет владельца, конкретный follow-up и критерий закрытия.
  Недостающие UI сценарии передаются внешнему разработчику; API/DTO изменения —
  владельцу SNAP-16 с обоснованием и согласованием, без скрытого локального fork.
- Пакет пригоден к переносу: блокирующие лицензии/секреты/известные Critical/High
  дефекты устранены; unresolved issues и решение интегратора записаны. Отсутствие
  исходников остаётся BLOCKED, проверка scaffold не закрывает FE-01.

Evidence: раздел FE-01 в будущем `docs/reports/SNAP-17.md`, inventory и матрица
совместимости с exact frontend/API revisions. Сейчас этот отчёт не создан.

## FE-02 — Перенос и переработка frontend

Действия: перенести предоставленный код в существующую Next.js архитектуру,
сохраняя согласованный дизайн и компоненты; адаптировать структуру только при
необходимости. Минимизировать переписывание работающего кода. Удалить временные
тарифные вычисления, client approvals и небезопасные клиентские решения. Fixtures
могут оставаться в тестах, product mocks удаляются при FE-03.

Критерии приёмки:

- Diff прослеживается к принятому внешнему revision; перенос и необходимые
  адаптации объяснены, согласованный дизайн/компоненты и адаптивность сохранены.
- При несовместимом стеке подготовлен конкретный план адаптации в Next.js и
  согласован с интегратором/внешним разработчиком; новый сервис/второй UI не введён.
- Нет клиентских расчётов тарифов/автоматических approvals, ключей провайдера,
  секретов в публичном bundle или небезопасного хранения сессии. Backend/DTO
  read-only; необходимый backend fix передан владельцу.
- Установка зависимостей по lockfile воспроизводима; lint/typecheck/build
  проходят. Все изменения shared config/dependencies выполняет один владелец.

Evidence: раздел FE-02 будущего SNAP-17 report, diff/import revision, результаты
проверок и перечень принятых адаптаций/оставшихся follow-up.

## FE-03 — Подключение к backend

Действия: заменить product mock-данные реальными FastAPI вызовами; использовать
типизированный API client и frozen TS DTO SNAP-16. Подключить серверные сессии,
cookie/Origin/CSRF и обработку typed errors. Подключить search/comparison,
documents и assistant; provider вызывается исключительно backend.

Критерии приёмки:

- Login/invite/logout/expiry используют защищённые server sessions и HttpOnly
  cookie через same-origin proxy; unsafe запросы передают правильный CSRF и
  Origin. Groq key не попадает в frontend/env bundle/localStorage.
- Product flows вызывают реальные API: явный snapshot/scenario, поиск,
  сравнение банков, вопрос ассистенту, protected source original и admin
  candidates/review/freeze с RBAC. Product mocks не заменяют эти маршруты.
- UI отображает evidence/clickable originals, revision/date/coverage/missing
  banks/synthetic, unknown/conflict/individual conditions/scope и fallback.
  Unknown не превращается в 0, отсутствующие данные не становятся общим рейтингом.
- Состояния clarification/missing-input, 401/403/404/409/422/429/503 и Retry-After
  обработаны по контракту без raw stacks/paths/secrets. Snippets escaped; при
  logout текущий диалог очищается. Payroll personal data не запрашиваются.
- Public API/DTO используются без изменений; любой необходимый change прошёл
  обоснованный follow-up, согласование и sequential merge владельца SNAP-16.

Evidence: раздел FE-03 будущего SNAP-17 report, exact frontend/API revisions,
матрица фактически подключённых routes и демонстрация состояний на synthetic.

## FE-04 — Интеграционные проверки

Действия: browser E2E на реальном backend с synthetic corpus, dedicated
PostgreSQL после Alembic upgrade/check и Fake; lint/typecheck/build и проверка
пользовательских сценариев, включая адаптивность. Bank/Groq network = 0.

Критерии приёмки:

- Browser flows покрывают invite/login/logout, expiry, выбор frozen synthetic
  snapshot/scenario, поиск, сравнение, вопросы ассистенту, открытие sources,
  admin review/freeze и очистку диалога. Это реальные FastAPI/PG вызовы.
- RBAC проверен для analyst/admin и identities A/B; неправильный/отсутствующий
  CSRF и wrong Origin отклоняются; XSS snippets не выполняются; provider failure,
  fallback, 429/Retry-After, 503 и неизвестные/конфликтные/индивидуальные условия
  отображаются честно. Контролируемые backend fixtures вызывают ошибки без сети.
- Lint/typecheck/build, relevant API/PG/contract tests и meaningful browser E2E
  проходят; отчёт содержит команды, exact revisions, числа PASS/FAIL/NOT RUN,
  evidence каждого AC и все unresolved issues. Известных Critical/High дефектов
  в auth/CSRF/RBAC/XSS/doc access нет; обязательный NOT RUN не закрывает FE-04.
- Принят отчёт о готовности интерфейса к эксплуатации с env/run instructions,
  limitations и честным разделением synthetic technical readiness и real release.
  Synthetic E2E не доказывает real corpus/Groq quality или S1/S2/S3 PASS.

Evidence: раздел FE-04 будущего SNAP-17 report, browser artifacts/результаты,
readiness verdict и ссылки на принятые FE-01–FE-03. SNAP-17 DONE только после
всех FE AC. [SNAP-19](prompts/SNAP-19.md) ждёт merged SNAP-17 с этими evidence и
SNAP-18; финальная приёмка проверяет готовую интеграцию внешнего frontend.

## Границы изменений и gates

Owned paths интеграции перечислены в SNAP-17. `frontend/lib/api-contracts.ts`
владеет SNAP-16; backend, migrations и public contracts не меняются конкурирующе.
На переносе frontend tree/package-lock имеет одного владельца. Новые внешние
revisions принимаются последовательно, в отдельных branches/worktrees при
реальном параллелизме, без перезаписи соседних изменений. Расширение owned paths
сначала согласуется с интегратором. TASKS/MASTER_PLAN/FE tracker обновляет один
интегратор после принятого отчёта; completed SNAP history сохраняется.

S1 — BLOCKED; S2/S3 — NOT EVALUATED; G1/G2 — NOT PASSED. S0 полного pipeline
ещё не завершён. Получение UI, DONE модуля или synthetic проверки gates не меняют.
