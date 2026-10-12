import { test, expect, type Page } from "@playwright/test";
import path from "node:path";

const screenshots = path.resolve(
  __dirname,
  "../../.local/frontend-chat-mvp/screenshots",
);
async function send(page: Page, text: string) {
  await page
    .getByRole("textbox", { name: "Сообщение", exact: true })
    .fill(text);
  await page
    .getByRole("button", { name: "Отправить сообщение", exact: true })
    .click();
}
async function finished(page: Page) {
  await expect(
    page.getByRole("button", { name: "Остановить генерацию" }),
  ).toHaveCount(0);
}
test.beforeEach(async ({ page }) => {
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (url.hostname !== "127.0.0.1")
      throw new Error(`Unexpected egress: ${url.hostname}`);
    return route.continue();
  });
  await page.goto("/?demo=1");
});
test("desktop welcome and progressive comparison, copy and collapse", async ({
  page,
  context,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await expect(
    page.getByRole("heading", { name: "Сложные условия. Понятный разговор." }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(screenshots, "desktop-welcome.png"),
  });
  await page.getByRole("button", { name: /Сравнить условия/ }).click();
  await expect(
    page.getByRole("button", { name: "Остановить генерацию" }),
  ).toBeVisible();
  const answer = page.getByRole("article", { name: "Сообщение ассистента" });
  await expect(answer.locator(".message-text").first()).not.toHaveText("");
  await expect(answer.locator(".table-progress")).toBeVisible();
  expect(await answer.getByRole("row").count()).toBeLessThan(4);
  await finished(page);
  await expect(answer.getByRole("row")).toHaveCount(4);
  await expect(answer.getByText("Неизвестно", { exact: true })).toBeVisible();
  await expect(
    answer.getByText("Конфликт данных", { exact: true }),
  ).toBeVisible();
  await expect(
    answer.getByText("Индивидуально", { exact: true }),
  ).toBeVisible();
  await expect(
    answer.getByText("1 200,00 ₽ / мес.", { exact: true }),
  ).toBeVisible();
  await expect(answer.getByText("0,30 %", { exact: true })).toBeVisible();
  await expect(
    answer.getByText("Синтетические данные", { exact: true }),
  ).toBeVisible();
  await expect(answer.getByRole("link")).toHaveCount(0);
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await answer.getByRole("button", { name: "Копировать ответ" }).click();
  await expect(answer.getByText("Скопировано")).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain(
    "Синтетические примеры",
  );
  await page.locator(".chat-scroll").evaluate((element) => {
    element.scrollTop = 0;
  });
  await page.screenshot({
    path: path.join(screenshots, "desktop-comparison.png"),
  });
  await answer
    .locator(".response-table")
    .screenshot({
      path: path.join(screenshots, "comparison-table.png"),
      style: ".scroll-latest { visibility: hidden; }",
    });
  await page.getByRole("button", { name: "Свернуть панель" }).click();
  await expect(page.locator(".sidebar")).toHaveCSS("width", "78px");
  await page.getByRole("button", { name: "Развернуть панель" }).click();
  await expect(
    page.locator(".conversation-select[aria-current=page]"),
  ).toHaveCount(1);
  expect(errors).toEqual([]);
});
test("stop preserves partial answer and permits another request without duplicate messages", async ({
  page,
}) => {
  await send(page, "Первая тема");
  await expect(page.locator(".message-assistant .message-text")).not.toHaveText(
    "",
  );
  await page.getByRole("button", { name: "Остановить генерацию" }).click();
  const partial = await page
    .locator(".message-assistant .message-content")
    .innerText();
  await expect(page.getByText(/Генерация остановлена/)).toBeVisible();
  await send(page, "Вторая тема");
  await finished(page);
  expect(
    await page
      .locator(".message-assistant .message-content")
      .first()
      .innerText(),
  ).toBe(partial);
  await expect(
    page.getByRole("article", { name: "Ваше сообщение" }),
  ).toHaveCount(2);
  await expect(
    page.getByRole("article", { name: "Сообщение ассистента" }),
  ).toHaveCount(2);
  await expect(page.locator(".conversation-select")).toHaveText("Первая тема");
});
test("switch during generation, isolated drafts, delete active stream and reload clears memory", async ({
  page,
}) => {
  await send(page, "Диалог А");
  await page.getByRole("button", { name: "Новый чат", exact: true }).click();
  const textbox = page.getByRole("textbox", { name: "Сообщение", exact: true });
  await textbox.fill("Черновик Б");
  await expect(page.getByRole("article")).toHaveCount(0);
  await page
    .locator(".conversation-select")
    .filter({ hasText: "Диалог А" })
    .click();
  await expect(textbox).toHaveValue("");
  await expect(
    page.getByRole("article", { name: "Ваше сообщение" }),
  ).toContainText("Диалог А");
  await page.getByRole("button", { name: "Удалить диалог: Диалог А" }).click();
  await expect(textbox).toHaveValue("Черновик Б");
  await send(page, "Диалог Б");
  await finished(page);
  await expect(page.locator(".conversation-select")).toHaveCount(1);
  await expect(page.locator(".message-user")).toHaveCount(1);
  await page.reload();
  await expect(page.locator(".conversation-select")).toHaveCount(0);
  await expect(page.getByRole("heading")).toBeVisible();
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});
test("background generation completes in its own dialog while another dialog streams", async ({
  page,
}) => {
  await send(page, "Параллельный А");
  await page.getByRole("button", { name: "Новый чат", exact: true }).click();
  await send(page, "Параллельный Б");
  await finished(page);
  await expect(page.locator(".message-user")).toHaveText(/Параллельный Б/);
  await page
    .locator(".conversation-select")
    .filter({ hasText: "Параллельный А" })
    .click();
  await finished(page);
  await expect(page.locator(".message-user")).toHaveText(/Параллельный А/);
  await expect(page.getByRole("table")).toHaveCount(1);
});
test("simulated network error preserves text and recovery works", async ({
  page,
}) => {
  await send(page, "демо: ошибка сети");
  await expect(
    page
      .getByRole("article", { name: "Сообщение ассистента" })
      .getByRole("alert"),
  ).toContainText("ошибка соединения");
  await expect(page.locator(".message-assistant .message-text")).toContainText(
    "сохраняет уже полученный текст",
  );
  await finished(page);
  await send(page, "Попробовать снова");
  await finished(page);
  await expect(page.getByRole("table")).toHaveCount(1);
});
test("Enter sends, Shift+Enter inserts newline, HTML stays text and does not execute", async ({
  page,
}) => {
  const textbox = page.getByRole("textbox", { name: "Сообщение", exact: true });
  await expect(
    page.getByRole("button", { name: "Отправить сообщение" }),
  ).toBeDisabled();
  const payload =
    '<img src=x onerror="window.__xss=1"><script>window.__xss=2</script>';
  await textbox.fill(payload);
  await textbox.press("Shift+Enter");
  await textbox.press("a");
  await expect(textbox).toHaveValue(payload + "\na");
  await expect(page.getByRole("article")).toHaveCount(0);
  await textbox.press("Enter");
  await expect(page.locator(".message-user .message-text")).toHaveText(
    payload + "\na",
  );
  await expect(
    page.locator(".message-user img, .message-user script"),
  ).toHaveCount(0);
  expect(
    await page.evaluate(() => Reflect.get(window, "__xss")),
  ).toBeUndefined();
  await page.getByRole("button", { name: "Остановить генерацию" }).click();
});
test("manual scrolling remains stable while fragments arrive and jump restores following", async ({
  page,
}) => {
  await send(page, "Первый длинный ответ");
  await finished(page);
  await send(page, "Второй ответ");
  const scroller = page.locator(".chat-scroll");
  await scroller.evaluate((element) => {
    element.scrollTop = 0;
  });
  await expect(
    page.getByRole("button", { name: "К последнему сообщению" }),
  ).toBeVisible();
  await expect(
    page.locator(".message-assistant").last().locator(".message-text").first(),
  ).toContainText("учебный пример");
  expect(await scroller.evaluate((element) => element.scrollTop)).toBe(0);
  await page.getByRole("button", { name: "К последнему сообщению" }).click();
  await finished(page);
  expect(
    await scroller.evaluate(
      (element) =>
        element.scrollHeight - element.scrollTop - element.clientHeight,
    ),
  ).toBeLessThan(72);
});
test("laptop layout keeps composer visible and no page horizontal overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await expect(
    page.getByRole("textbox", { name: "Сообщение", exact: true }),
  ).toBeInViewport();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: path.join(screenshots, "laptop-welcome.png") });
});
