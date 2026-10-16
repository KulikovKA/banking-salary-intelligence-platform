import { test, expect, type Page } from "@playwright/test";

const answer = "## Условия Альфа-Банка\n\nТочная комиссия **неизвестна**: она определяется договором.\n\n- Проверьте дату договора.\n- Уточните условия подключения.\n\nИсточники: [Sabcdef123456]";
async function mockApi(page: Page) {
  await page.route("**/api/local-demo/status", (route) => route.fulfill({ json: { banks: ["Сбер", "ВТБ", "Альфа-Банк", "Кубань Кредит"] } }));
}
async function send(page: Page, text: string) {
  await page.getByRole("textbox", { name: "Сообщение", exact: true }).fill(text);
  await page.getByRole("button", { name: "Отправить сообщение", exact: true }).click();
}
test("consent, clean Markdown answer, persistent conversations, deletion and revocation", async ({ page, context }) => {
  const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message));
  await mockApi(page);
  let calls = 0;
  await page.route("**/api/local-demo/questions", async (route) => {
    calls++; expect(route.request().postDataJSON().allow_public_text).toBe(true);
    await new Promise((resolve) => setTimeout(resolve, 350));
    await route.fulfill({ json: { answer, sources: [{ id: "Sabcdef123456", text: "RAW_DOCUMENT_CANARY" }], usage: { total_tokens: 999 }, provenance: [{ sha256: "HASH_CANARY" }] } });
  });
  await page.goto("/");
  await expect(page.getByRole("dialog")).toBeVisible(); expect(calls).toBe(0);
  await page.getByRole("button", { name: "Разрешить и продолжить" }).click();
  await expect(page.getByRole("heading", { name: "Чем могу помочь?" })).toBeVisible();
  await send(page, "Какая комиссия у Альфа-Банка?");
  await expect(page.getByText("Формирую ответ…")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Условия Альфа-Банка" })).toBeVisible();
  await expect(page.locator(".message-assistant a, .response-table")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText(/Sabcdef|Источники:|HASH_CANARY|RAW_DOCUMENT_CANARY|999|Groq|HTTP/);
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.getByRole("button", { name: "Копировать ответ" }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).not.toMatch(/Источники|Sabcdef|RAW_DOCUMENT/);
  await page.getByRole("button", { name: "Новый чат", exact: true }).click();
  await send(page, "Какие условия у ВТБ?");
  await expect(page.getByRole("button", { name: "Остановить генерацию" })).toHaveCount(0);
  await page.locator(".conversation-select").filter({ hasText: "Какая комиссия у Альфа-Банка?" }).click();
  await expect(page.locator(".message-user")).toContainText("Альфа-Банка");
  await page.reload();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".conversation-select")).toHaveCount(2);
  const storage = await page.evaluate(() => localStorage.getItem("salary-ai-chats-v1"));
  expect(storage).not.toMatch(/RAW_DOCUMENT|HASH_CANARY|provenance|total_tokens|sources/);
  await page.locator(".conversation-item.active summary").click();
  await page.getByRole("button", { name: "Удалить чат", exact: true }).click();
  await expect(page.locator(".conversation-select")).toHaveCount(1);
  await page.getByRole("button", { name: "Настройки", exact: true }).click();
  await page.getByRole("button", { name: "Отозвать согласие" }).click();
  await page.getByRole("button", { name: "Закрыть окно" }).click();
  await expect(page.getByRole("textbox")).toBeDisabled(); expect(calls).toBe(2);
  await page.getByRole("button", { name: "Настройки", exact: true }).click();
  await page.getByRole("button", { name: "Очистить историю" }).click();
  await expect(page.locator(".conversation-select")).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("dialog")).toBeVisible(); expect(calls).toBe(2);
  expect(errors).toEqual([]);
});

test("rate limit has a readable error and explicit retry, with no provider details", async ({ page }) => {
  await mockApi(page); let calls = 0;
  await page.route("**/api/local-demo/questions", (route) => {
    calls++;
    return route.fulfill(calls === 1 ? { status: 429, json: { detail: "GROQ_HTTP_429_SECRET_CANARY" } } : { json: { answer } });
  });
  await page.goto("/"); await page.getByRole("button", { name: "Разрешить и продолжить" }).click();
  await send(page, "Какая комиссия?");
  await expect(page.locator(".message-error")).toContainText("Сейчас слишком много запросов");
  await expect(page.locator(".message-error")).toHaveCSS("background-color", "rgb(44, 37, 40)");
  await expect(page.locator("body")).not.toContainText(/GROQ_HTTP|SECRET_CANARY|429/);
  expect(calls).toBe(1);
  await page.getByRole("button", { name: "Попробовать снова" }).click();
  await expect(page.getByRole("heading", { name: "Условия Альфа-Банка" })).toBeVisible();
  expect(calls).toBe(2);
});

test("comparison suggestion submits the exact button question and displays four banks", async ({ page }) => {
  await mockApi(page);
  let calls = 0;
  await page.route("**/api/local-demo/questions", (route) => {
    calls++;
    expect(route.request().postDataJSON().question).toBe("Сравни зарплатные проекты четырёх банков: Сбер, ВТБ, Альфа-Банк и Кубань Кредит");
    return route.fulfill({ json: { answer: "- **Сбер**: условия из базы знаний.\n- **ВТБ**: условия из базы знаний.\n- **Альфа-Банк**: индивидуальная комиссия.\n- **Кубань Кредит**: ставка зависит от договора." } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Разрешить и продолжить" }).click();
  await expect(page.locator(".live-suggestions button")).toHaveCount(1);
  await page.getByRole("button", { name: "Сравнить 4 банка", exact: true }).click();
  for (const bank of ["Сбер", "ВТБ", "Альфа-Банк", "Кубань Кредит"]) {
    await expect(page.locator(".message-assistant")).toContainText(bank);
  }
  await expect(page.locator(".message-error")).toHaveCount(0);
  expect(calls).toBe(1);
});

test("responsive start screen and mobile sidebar preserve viewport and input", async ({ page }) => {
  await mockApi(page);
  await page.goto("/"); await page.getByRole("button", { name: "Разрешить и продолжить" }).click();
  for (const [width, height] of [[1920, 1080], [1440, 900], [1366, 768], [768, 1024], [390, 844], [360, 640]]) {
    await page.setViewportSize({ width, height });
    await expect(page.getByRole("textbox")).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.getByRole("heading", { name: "Чем могу помочь?" })).toBeInViewport();
  }
  await page.getByRole("button", { name: "Открыть меню" }).click();
  await expect(page.getByRole("button", { name: "Настройки", exact: true })).toBeInViewport();
  await page.getByRole("button", { name: "Закрыть меню", exact: true }).click({ position: { x: 340, y: 100 } });
  await expect(page.getByRole("textbox")).toBeInViewport();
  await page.route("**/api/local-demo/questions", (route) => route.fulfill({ json: {
    answer: "## Сравнение\n\n| Банк | Зачисление | Обслуживание | Применимость |\n|---|---|---|---|\n| Альфа-Банк | Индивидуально | Неизвестно | По договору работодателя |\n| ВТБ | Неизвестно | Неизвестно | Требует проверки |",
  } }));
  await send(page, "Сравнить условия банков");
  await expect(page.locator(".markdown-answer table")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.getByRole("button", { name: "Копировать ответ" })).toBeInViewport();
  await expect(page.getByRole("textbox")).toBeInViewport();
});
