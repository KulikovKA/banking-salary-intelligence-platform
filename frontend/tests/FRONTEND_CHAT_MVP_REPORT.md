# Desktop AI Chat — Frontend MVP

Дата: 11.10.2026. Ветка: `codex/frontend-chat-mvp`.
Base: `af807da` (`origin/main`, обновлён перед созданием worktree).
Worktree: `C:\Users\Kirill\Desktop\sber-ai-frontend-chat-mvp`.

Это самостоятельная frontend-задача по новому прямому поручению владельца.
Она не заявляет выполнение SNAP-16/17 или прохождение продуктовых gates.
Backend, публичные DTO, конфигурация Next.js и файлы планирования не менялись.
Чужие изменения в исходном worktree сохранены.

## Реализованное поведение

- Единственная страница: светлый desktop-чат с зелёным акцентом, приветствием и тремя примерами запросов. Проверены 1440×900 и 1280×720; мобильная адаптация не входит в задачу.
- Sidebar: новый диалог, список, автоматический заголовок по первому вопросу, активный диалог, переключение, удаление, сворачивание. Черновики принадлежат своим диалогам. История живёт только в React state текущей вкладки и исчезает после reload.
- Composer: Enter отправляет, Shift+Enter переносит строку, IME composition не отправляет вопрос, пустой ввод не отправляется, длина ограничена 2000 символами, высота поля подстраивается.
- Поток: текст поступает фрагментами, затем появляются строки таблицы, затем заключение. Stop использует AbortController. Частичный ответ сохраняется. Новое сообщение после отмены безопасно; запоздалые события не изменяют остановленный ответ.
- Переключение диалога не прерывает генерацию: каждый поток привязан к conversation/message ID. Другой диалог может генерировать свой ответ. Удаление диалога и unmount отменяют соответствующие запросы.
- Sequence guards исключают повторную сборку событий; строки таблицы имеют стабильные ID. Завершение потока без `complete` отображается как ошибка, а не успешный ответ.
- Ошибка соединения сохраняет полученный текст и возвращает доступный composer. Для локальной демонстрации ошибки отправьте **`демо: ошибка сети`**. Это искусственная ошибка адаптера; сетевой запрос не выполняется.
- Автопрокрутка следует за потоком, пока пользователь находится у конца диалога; ручной scroll вверх сохраняет позицию. Кнопка перехода к последнему сообщению возобновляет слежение.
- Копирование пользовательского сообщения и полного структурированного ответа, включая таблицу, условия, revision/date, ограничения и источники; отображается результат или отказ Clipboard API.
- Таблица: три вымышленных банка, денежные/процентные/текстовые значения, выравнивание чисел, перенос длинных условий, unknown/individual/conflict/blocked/not_applicable, источники и ограничения. Отмена не оставляет ложный индикатор загрузки частичной таблицы.

## Структура

| Файл | Ответственность |
|---|---|
| `components/chat/ChatShell.tsx` | Диалоги, жизненный цикл запросов, scroll, внедряемый transport |
| `ChatSidebar.tsx` | История и управление диалогами |
| `ChatWelcome.tsx` | Приветствие и примеры вопросов |
| `ChatComposer.tsx` | Поле ввода, клавиатура, Send/Stop |
| `ChatMessage.tsx` | Текст, таблицы, статусы и копирование |
| `StreamingIndicator.tsx` | Индикатор генерации |
| `ResponseTable.tsx` | Структурированные табличные блоки |
| `Icon.tsx` | Небольшой набор локальных SVG-иконок |
| `lib/chat/models.ts` | UI presentation models и ChatTransport; не HTTP DTO |
| `lib/chat/state.ts` | Reducer и идемпотентная сборка событий |
| `lib/chat/demo-transport.ts` | Локальный DEMO adapter и прерываемые задержки |
| `lib/chat/format.ts` | Decimal-string display, plain-text copy, safe original paths |
| `styles/chat.css` | Desktop layout, состояния, reduced-motion |

Публичный `frontend/lib/api-contracts.ts` не создавался и не изменялся.
Новый обязательный runtime package не добавлен. Добавлен только
`@playwright/test@1.64.0` как dev dependency с lockfile и `npm test`: нужен для
реальных браузерных сценариев, проверок изоляции потоков/XSS и скриншотов.
Prettier использован однократно для форматирования; зависимость проекта не добавлена.

## Безопасность и ограничения

Текст отображается средствами React; HTML/JavaScript не исполняется. Произвольные
URL не превращаются в ссылки. ResponseTable допускает только точный same-origin
путь `/api/v1/documents/{UUID}/original`, заданный серверным адаптером; доступ к
оригиналу впоследствии обязан повторно проверять backend. DEMO не содержит таких ссылок.
Секретов, `.env`, browser Groq key, local/sessionStorage, server chat memory,
клиентских тарифных вычислений и самостоятельного выбора победителя нет.
Decimal strings форматируются без Number/float, вычислений и округления.

Демо отвечает одним учебным примером независимо от смысла вопроса, кроме команды
ошибки. Числа статические и вымышленные; источники — учебные метаданные, не
официальные документы. Текущий adapter не делает fetch/SSE/provider requests.
Разработка/установка пакетов и Chromium требует сети; выполнение тестов обращается
только к локальному Next.js. Browser routes отвергают внешний egress.

Проверенные источники, auth, выбор реального snapshot/scenario, fallback/429/503,
protected originals и API/PG интеграция будут подключаться отдельной задачей после
SNAP-16. Настоящих банковских предложений, разрешений или real-provider eval здесь нет.
S0 полного продукта не подтверждён; G1/G2, S1/S2/S3 не переоценивались.

## Запуск

Из корня нового worktree:

```powershell
npm --prefix frontend ci
npm --prefix frontend run dev
# http://localhost:3000
```

Проверки и воспроизводимые screenshots:

```powershell
npm --prefix frontend run lint
npm --prefix frontend run typecheck
$env:NEXT_TELEMETRY_DISABLED = '1'
npm --prefix frontend run build
Push-Location frontend
npx playwright install chromium
npm test
Pop-Location
```

Playwright запускает production Next.js на `127.0.0.1:3100`, останавливает его после
проверок и сохраняет screenshots/HTML report/traces в ignored `.local/frontend-chat-mvp/`.

## Результаты проверок

| Проверка | Результат |
|---|---|
| `npm run lint` | PASS, 0 ошибок |
| `npm run typecheck` | PASS, 0 ошибок |
| `npm run build` | PASS, production static route `/` |
| Frontend Playwright suite | PASS: 20/20 за 21,0 с; 8 браузерных, 10 reducer/transport/format, 2 SSR/security; 0 skipped |
| `uv run --no-sync ruff check .` | PASS |
| `uv run --no-sync mypy backend/app` | PASS, 63 файла |
| `uv run --no-sync pytest backend/tests/test_health.py -q` | PASS, 1 тест |
| `python tools/validate_docs.py` | PASS, 19 prompts, ссылки/DAG/statuses/source decisions |
| `git diff --check` | PASS |
| `npm audit --package-lock-only --omit=dev` | PASS, 0 production vulnerabilities |
| Полный `npm audit` | FAIL: 4 high в существующей dev-цепочке eslint-plugin-next → fast-glob → micromatch → braces; 0 critical. Исходные версии не изменены, force downgrade не выполнялся; follow-up интегратору. |
| PG/Alembic/full backend suite, FastAPI↔UI E2E | NOT RUN: backend/DB/API не менялись; эта задача — независимый локальный frontend, SNAP-16 ещё не подключён |
| Live bank/Groq, real streaming | NOT RUN: не входит в допущенный DEMO scope |

Первый frontend запуск: 17 PASS / 2 FAIL из-за слишком короткого промежуточного
ожидания числа строк и неоднозначного селектора `alert` (Next.js route announcer).
После исправления оба упавших сценария отдельно прошли. Добавлена проверка
частичной таблицы; финальный полный прогон: **20 PASS / 0 FAIL / 0 SKIP за 21,0 с**.

Скриншоты визуально проверены: `desktop-welcome.png`, `desktop-comparison.png`,
`comparison-table.png`, `laptop-welcome.png` в `.local/frontend-chat-mvp/screenshots/`.
В crop таблицы плавающая кнопка scroll скрыта только при screenshot, чтобы она не
перекрывала источники; рабочий интерфейс не изменяется.

## Что требуется для реального backend

Сначала SNAP-16 должен передать frozen OpenAPI/TS DTO, auth cookie/Origin/CSRF
правила, typed errors и synthetic AnswerEnvelope/ComparisonResult examples.
Backend adapter привязывает вопрос к явно выбранному snapshot/scenario, принимает
bounded stateless request и отображает AnswerEnvelope в существующие UI blocks,
сохраняя источники, scope/date/conditions, неизвестные значения и limitations.
UI models не копируют public DTO и не являются контрактом серверного streaming.

Текущий контракт предусматривает синхронный AnswerEnvelope без SSE. Его можно
подключить через этот transport как готовый ответ; это не настоящее token streaming.
Для настоящего server stream нужен отдельный согласованный follow-up владельцу
контрактов: framing, идентификаторы и порядок событий, cancellation/disconnect,
ошибки и финальная evidence-validated сборка. Существующий запрет SSE не обходится
новым endpoint в этом PR. LLM не вычисляет тарифы и не создаёт произвольные ссылки.

Отдельный запрос интегратору: [INTEGRATOR_FOLLOWUP.md](INTEGRATOR_FOLLOWUP.md).
