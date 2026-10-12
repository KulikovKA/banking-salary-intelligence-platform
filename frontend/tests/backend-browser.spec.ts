import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const fixturePath = path.resolve(__dirname, "../../.local/snap17-browser/fixture.json");
const fixture = () => JSON.parse(fs.readFileSync(fixturePath, "utf8"));
async function control(page: Page, action: string) {
  const response = await page.request.post("http://127.0.0.1:8007/__test/control", {
    headers: { "x-test-control": fixture().control }, data: { action },
  });
  expect(response.ok()).toBe(true);
}
async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Логин", { exact: true }).fill(fixture().login);
  await page.getByLabel("Пароль", { exact: true }).fill(fixture().password);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByLabel("Набор данных", { exact: true })).toBeVisible();
}
async function select(page: Page) {
  await page.getByLabel("Набор данных", { exact: true }).selectOption(fixture().snapshot_id);
  await expect(page.getByRole("textbox", { name: "Сообщение", exact: true })).toBeVisible();
}
async function send(page: Page, text: string) {
  const count = await page.getByRole("article", { name: "Сообщение ассистента" }).count();
  await page.getByRole("textbox", { name: "Сообщение", exact: true }).fill(text);
  await page.getByRole("button", { name: "Отправить сообщение", exact: true }).click();
  const answer = page.getByRole("article", { name: "Сообщение ассистента" }).nth(count);
  await expect(answer).toBeVisible();
  await expect(page.getByRole("button", { name: "Остановить генерацию", exact: true })).toHaveCount(0);
  return answer;
}
test.beforeEach(async ({ page }) => {
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (url.hostname !== "127.0.0.1") throw new Error(`External browser request: ${url.hostname}`);
    return route.continue();
  });
  await control(page, "reset");
});
test.afterEach(async ({ page }) => {
  const response = await page.request.get("http://127.0.0.1:8007/__test/evidence", {
    headers: { "x-test-control": fixture().control },
  });
  expect(await response.json()).toMatchObject({ egress_attempts: 0, llm_mode: "fake", corpus_kind: "synthetic" });
});

test("real login, explicit snapshot, Origin/CSRF, HttpOnly cookie, logout clears history", async ({ page, context }) => {
  await login(page);
  await expect(page.getByRole("textbox", { name: "Сообщение", exact: true })).toHaveCount(0);
  const cookies = await context.cookies();
  expect(cookies.find((c) => c.name === "bsi-session")?.httpOnly).toBe(true);
  expect(await page.evaluate(() => document.cookie)).not.toContain("bsi-session");
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
  await select(page);
  const body = { snapshot_id: fixture().snapshot_id, question: "Какой банк лучше?" };
  const csrf = cookies.find((c) => c.name === "bsi-csrf")!.value;
  const rejectedHeaders: Record<string, string>[] = [{ Origin: "http://evil.invalid", "x-csrf-token": csrf }, { Origin: "http://127.0.0.1:3100" }];
  for (const headers of rejectedHeaders) {
    const response = await page.request.post("/api/v1/assistant/questions", { headers, data: body });
    expect(response.status()).toBe(403);
  }
  const response = await page.request.get(`/api/v1/documents/${crypto.randomUUID()}/original`);
  expect(response.status()).toBe(404);
  expect((await page.request.post("/api/v1/admin/invitations", { data: {} })).status()).toBe(404);
  const answer = await send(page, "Какой банк лучше?");
  await expect(answer).toContainText("Нужно уточнение");
  await page.getByRole("button", { name: "Выйти", exact: true }).click();
  await expect(page.getByRole("article")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Войти", exact: true })).toBeVisible();
  expect((await page.request.get("/api/v1/auth/me")).status()).toBe(401);
  await login(page); await select(page);
  await expect(page.getByRole("article")).toHaveCount(0);
});

test("real verified comparison, four banks, unknown, sources/hash and escaped question", async ({ page }) => {
  await login(page); await select(page);
  await page.getByText("Параметры вопроса и сравнения", { exact: true }).click();
  await page.getByLabel("Метрики через запятую").fill("account_monthly_fee");
  await page.getByLabel("Передать сценарий сравнения").check();
  await expect(page.getByRole("button", { name: "Отправить сообщение", exact: true })).toBeDisabled();
  await page.getByLabel("Дата действия").fill("2026-10-12");
  const composer = await page.locator(".composer").boundingBox();
  expect(composer!.y + composer!.height).toBeLessThanOrEqual(900);
  const answer = await send(page, "Сравни Сбер, ВТБ, Альфа-Банк и Кубань Кредит по комиссиям");
  await expect(answer.getByRole("table")).toBeVisible();
  await expect(answer).toContainText("Частичный ответ");
  await expect(answer).toContainText("100");
  for (const bank of ["Сбер", "ВТБ", "Альфа-Банк", "Кубань Кредит"]) await expect(answer.getByRole("columnheader", { name: bank, exact: true })).toBeVisible();
  await expect(answer.locator(".cell-status-unknown")).toHaveCount(3);
  await expect(answer).toContainText("Синтетические данные");
  await expect(answer).toContainText(`Набор ${fixture().revision}`);
  await expect(answer).toContainText("Дата данных: 2026-10-12");
  const links = answer.locator("a[href$='/original']");
  expect(await links.count()).toBeGreaterThan(0);
  const original = await page.request.get((await links.first().getAttribute("href"))!);
  expect(original.ok()).toBe(true);
  expect(original.headers()["content-disposition"]).toContain("attachment");
  expect(original.headers()["x-content-type-options"]).toBe("nosniff");
  expect(crypto.createHash("sha256").update(await original.body()).digest("hex")).toBe(fixture().source_hash);
  await page.screenshot({ path: path.resolve(__dirname, "../../.local/snap17-browser/comparison.png"), fullPage: true });
  await page.getByLabel("Передать сценарий сравнения").uncheck();
  await send(page, '<img src=x onerror="window.__xss=1">');
  expect(await page.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBeUndefined();
  await expect(page.locator(".message-text img")).toHaveCount(0);
});

test("real insufficient and provider fallback retain sources", async ({ page }) => {
  await login(page); await select(page);
  await page.getByText("Параметры вопроса и сравнения", { exact: true }).click();
  await page.getByLabel("Метрики через запятую").fill("account_monthly_fee");
  for (const bank of ["Сбер", "Альфа-Банк", "Кубань Кредит"]) await page.getByLabel(bank, { exact: true }).uncheck();
  const insufficient = await send(page, "Сколько стоит обслуживание счета ВТБ?");
  await expect(insufficient).toContainText("Недостаточно данных");
  await page.getByLabel("ВТБ", { exact: true }).uncheck();
  await page.getByLabel("Сбер", { exact: true }).check();
  await control(page, "fallback");
  const fallback = await send(page, "Сколько стоит обслуживание счета Сбера?");
  await expect(fallback).toContainText("Резервный ответ");
  expect(await fallback.locator("a[href$='/original']").count()).toBeGreaterThan(0);
});

test("real rate limiting Retry-After and deadline 503 render safe errors", async ({ page }) => {
  await login(page); await select(page);
  await control(page, "rate");
  await send(page, "Какой банк лучше?");
  const rate = await send(page, "Какой банк лучше?");
  await expect(rate.getByRole("alert")).toContainText("Повторите через 60 с.");
  await control(page, "timeout");
  const timeout = await send(page, "Сколько стоит обслуживание счета Сбера?");
  await expect(timeout.getByRole("alert")).toContainText("Сервис временно недоступен");
});

test("real session expiry unmounts conversations and blocks questions", async ({ page }) => {
  await login(page); await select(page);
  await send(page, "Какой банк лучше?");
  await control(page, "expire");
  await page.getByRole("textbox", { name: "Сообщение", exact: true }).fill("Сколько стоит обслуживание счета Сбера?");
  await page.getByRole("button", { name: "Отправить сообщение", exact: true }).click();
  await expect(page.locator(".backend-controls").getByRole("alert")).toContainText("Сессия истекла");
  await expect(page.getByRole("article")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Войти", exact: true })).toBeVisible();
});

test("client AbortController stops real JSON request and rejects late display", async ({ page }) => {
  await login(page); await select(page);
  await control(page, "slow");
  await page.getByRole("textbox", { name: "Сообщение", exact: true }).fill("Сколько стоит обслуживание счета Сбера?");
  await page.getByRole("button", { name: "Отправить сообщение", exact: true }).click();
  await page.getByRole("button", { name: "Остановить генерацию", exact: true }).click();
  const answer = page.getByRole("article", { name: "Сообщение ассистента" });
  await expect(answer).toContainText("Клиентский запрос остановлен");
  await page.waitForTimeout(6500);
  await expect(answer.locator(".message-text")).toHaveCount(0);
  await expect(answer.getByRole("table")).toHaveCount(0);
});

test("real empty readable snapshot list blocks chat", async ({ page }) => {
  await control(page, "empty");
  await login(page);
  await expect(page.getByRole("status")).toContainText("Доступных frozen snapshot нет");
  await expect(page.getByRole("textbox", { name: "Сообщение", exact: true })).toHaveCount(0);
});

test("real single-use invite acceptance and logout", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "У меня приглашение", exact: true }).click();
  await page.getByLabel("Токен приглашения").fill(fixture().invitation);
  await page.getByLabel("Пароль", { exact: true }).fill(fixture().password);
  await page.getByRole("button", { name: "Принять приглашение", exact: true }).click();
  await expect(page.getByLabel("Набор данных", { exact: true })).toBeVisible();
  await select(page);
  await send(page, "Какой банк лучше?");
  await page.getByRole("button", { name: "Выйти", exact: true }).click();
  await page.getByRole("button", { name: "У меня приглашение", exact: true }).click();
  await page.getByLabel("Токен приглашения").fill(fixture().invitation);
  await page.getByLabel("Пароль", { exact: true }).fill(fixture().password);
  await page.getByRole("button", { name: "Принять приглашение", exact: true }).click();
  await expect(page.locator(".backend-controls").getByRole("alert")).toContainText("Приглашение недействительно");
});
