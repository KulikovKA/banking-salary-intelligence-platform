import { test, expect } from "@playwright/test";
import { renderToStaticMarkup } from "react-dom/server";
import type { AnswerEnvelope, ComparisonCell, SnapshotView } from "../lib/api-contracts";
import { answerTable, displayValue } from "../lib/chat/backend-transport";
import { ResponseTable } from "../components/chat/ResponseTable";
import { ApiClientError, api } from "../lib/client";
import { formatValue } from "../lib/chat/format";

const snapshot: SnapshotView = { id: "10000000-0000-4000-8000-000000000001", revision: 7,
  corpus_kind: "synthetic", state: "frozen", created_at: "2026-10-12T00:00:00Z",
  region: "RU-KDA", employer_segment: "SME", bank_codes: ["sber"], missing_banks: ["vtb", "alfa", "kuban_credit"], document_count: 1 };
test("wire value unions preserve decimals, unknown bounds, basis/period and formulas without evaluating", () => {
  const values: NonNullable<ComparisonCell["value"]>[] = [
    { kind: "money", amount: "99999999999999.000001", currency: "RUB", period: "месяц" },
    { kind: "percent", amount: "0.300000", basis: "payroll_total", period: "месяц" },
    { kind: "count", amount: "100", unit: "операций", period: "месяц" },
    { kind: "boolean", boolean_value: false }, { kind: "text", text_value: "условие" },
    { kind: "individual", text_value: "По договору" },
    { kind: "range", lower: null, upper: "100", unit: "RUB", lower_inclusive: false },
    { kind: "formula", formula: "percentage_clamped", parameters: { rate: "0.30", min_fee: "100" }, basis: "payroll_total", currency: "RUB", period: "месяц" },
  ];
  expect(formatValue(displayValue(values[0])!)).toContain("000001");
  expect(displayValue(values[1])).toMatchObject({ kind: "percent", amount: "0.300000", basis: "payroll_total" });
  for (const value of values) expect(displayValue(value)).toBeDefined();
  expect(displayValue({ kind: "money", amount: null, currency: "RUB" })).toBeUndefined();
  expect(displayValue({ kind: "percent", amount: null, basis: "payroll_total" })).toBeUndefined();
  expect(formatValue(displayValue(values[6])!)).toContain("Неизвестно");
  expect(formatValue(displayValue(values[7])!)).toContain('"rate":"0.30"');
});
test("every cell status, required conditions, missing inputs, limitations, source escaping and unsafe links", () => {
  const statuses: ComparisonCell["status"][] = ["verified", "unknown", "individual", "conflict", "blocked", "not_applicable"];
  const answer: AnswerEnvelope = { id: "answer", snapshot_id: snapshot.id, corpus_revision: 7,
    data_as_of: "2026-10-12", generated_at: "2026-10-12T00:00:00Z", status: "partial", text: "Ответ",
    limitations: ["Не полный рейтинг"], comparison: { id: "comparison", snapshot_id: snapshot.id, corpus_revision: 7,
      generated_at: "2026-10-12T00:00:00Z", scenario_echo: { payer: "employer", operation: "account_maintenance", currency: "RUB", as_of: "2026-10-12" },
      rows: statuses.map((status) => ({ metric_code: status, cells: [{ bank_code: "sber", status,
        value: status === "verified" ? { kind: "money", amount: "0", currency: "RUB" } : null,
        conditions: "Бесплатно только при выполнении условия", missing_inputs: ["region"] }] })),
      limitations: ["Отдельное ограничение"],
    }, sources: [{ download_url: "javascript:alert(1)", evidence: { id: "source", source_version_id: snapshot.id,
      extraction_run_id: snapshot.id, chunk_id: snapshot.id, raw_sha256: "a".repeat(64), extraction_sha256: "b".repeat(64),
      quote: '<img src=x onerror="alert(1)">', quote_start: 0, quote_end: 10, locator: { kind: "html", element_path: "p" },
      original_url: "https://evil.invalid", acquired_at: "2026-10-12T00:00:00Z", support_role: "value" } }],
  };
  const table = answerTable(answer, snapshot);
  const html = renderToStaticMarkup(<ResponseTable table={table} />);
  expect(html).not.toContain("<img"); expect(html).not.toContain("href=");
  expect(html).toContain("&lt;img");
  for (const status of statuses.slice(1)) expect(html).toContain(`cell-status-${status}`);
  expect(html).toContain("Бесплатно только при выполнении условия");
  expect(html).toContain("Не хватает: region"); expect(html).toContain("Отдельное ограничение");
  expect(html).toContain("0");
});
test("typed HTTP, Retry-After, network and timeout errors never expose backend messages", async () => {
  const originalFetch = globalThis.fetch;
  try {
    for (const status of [401, 403, 404, 409, 422, 429, 503]) {
      globalThis.fetch = async () => Response.json({ error: { code: "TEST", message: "SECRET_STACK_CANARY" } }, { status, headers: { "Retry-After": "60" } });
      await expect(api("GET /api/v1/auth/me")).rejects.toMatchObject({ status });
      expect(new ApiClientError(status, "TEST", "60").message).not.toContain("SECRET_STACK_CANARY");
    }
    expect(new ApiClientError(429, "TEST", "60").message).toContain("60 с.");
    globalThis.fetch = async () => { throw new TypeError("DATABASE_SECRET_CANARY"); };
    await expect(api("GET /api/v1/auth/me")).rejects.toMatchObject({ code: "NETWORK_ERROR" });
    globalThis.fetch = async () => { throw new DOMException("SECRET", "TimeoutError"); };
    await expect(api("GET /api/v1/auth/me")).rejects.toMatchObject({ code: "TIMEOUT" });
  } finally { globalThis.fetch = originalFetch; }
});
