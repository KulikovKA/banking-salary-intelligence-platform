import { test, expect } from "@playwright/test";
import { renderToStaticMarkup } from "react-dom/server";
import { ResponseTable } from "../components/chat/ResponseTable";
import { ChatMessage } from "../components/chat/ChatMessage";
import { demoTable } from "../lib/chat/demo-transport";
test("an interrupted table is explicitly partial and does not claim to be loading", () => {
  const markup = renderToStaticMarkup(
    <ResponseTable table={demoTable()} pending={false} />,
  );
  expect(markup).toContain("Таблица получена частично.");
  expect(markup).not.toContain("Таблица формируется");
});
test("local fragment links accept only fixed snippet IDs", () => {
  for (const fragmentPath of ["javascript:alert(1)", "/api/local-demo/fragment?id=../../.env", "https://evil.test/"]) {
    const table = demoTable();
    table.sources = [{ id: "x", label: "source", detail: "text", fragmentPath }];
    expect(renderToStaticMarkup(<ResponseTable table={table} />)).not.toContain("href=");
  }
  const table = demoTable();
  table.sources = [{ id: "x", label: "source", detail: "text", fragmentPath: "/api/local-demo/fragment?id=Sabcdef123456" }];
  expect(renderToStaticMarkup(<ResponseTable table={table} />)).toContain('href="/api/local-demo/fragment?id=Sabcdef123456"');
  table.sources[0].fragmentPath = "/api/local-demo/document?id=Sabcdef123456";
  expect(renderToStaticMarkup(<ResponseTable table={table} />)).toContain('href="/api/local-demo/document?id=Sabcdef123456"');
});
test("assistant text, table conditions and source titles escape HTML; arbitrary source URLs remain inert", () => {
  const payload = '<img src=x onerror="alert(1)"><script>alert(2)</script>';
  const table = demoTable();
  table.title = payload;
  table.rows = [
    {
      id: "x",
      label: payload,
      cells: [{ bankId: "a", status: "unknown", conditions: [payload] }],
    },
  ];
  table.sources = [
    {
      id: "x",
      label: payload,
      detail: payload,
      originalPath: "javascript:alert(3)",
    },
  ];
  const markup = renderToStaticMarkup(<ResponseTable table={table} />);
  expect(markup).not.toContain("<img");
  expect(markup).not.toContain("<script");
  expect(markup).not.toContain("href=");
  expect(markup).toContain("&lt;img");
  const message = renderToStaticMarkup(
    <ChatMessage
      message={{
        id: "x",
        role: "assistant",
        status: "complete",
        blocks: [{ kind: "text", id: "x", text: payload }],
        lastSequence: 1,
      }}
    />,
  );
  expect(message).not.toContain("<script");
  expect(message).toContain("&lt;script&gt;");
});
