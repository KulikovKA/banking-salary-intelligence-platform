import { test, expect } from "@playwright/test";
import { renderToStaticMarkup } from "react-dom/server";
import { AnswerMarkdown } from "../components/chat/AnswerMarkdown";
import { answerText, readHistory, savedHistory } from "../lib/chat/presentation";
import { initialState } from "../lib/chat/state";
import { demoTable } from "../lib/chat/demo-transport";

test("presentation removes citation metadata and preserves financial qualifications and Markdown", () => {
  const input = "## Условия\n\n**0,15 %** только для договоров до 05.06.2023 [Sabcdef123456]. Точная комиссия неизвестна.\n\n| Банк | Ставка |\n|---|---|\n| Альфа | Индивидуально |\n\nИсточники: [Sabcdef123456], [S654321abcdef]";
  const text = answerText(input);
  expect(text).toContain("0,15 %"); expect(text).toContain("до 05.06.2023");
  expect(text).not.toMatch(/Источники|Sabcdef|S654321/);
  const markup = renderToStaticMarkup(<AnswerMarkdown text={input + '\n<script>alert(1)</script>\n![image](https://evil.test/img)\n[документ](/api/local-demo/document?id=Sabcdef123456)'} />);
  expect(markup).toContain("<h2>"); expect(markup).toContain("<table>"); expect(markup).toContain("<strong>");
  expect(markup).not.toMatch(/<script|<img|href=|\/api\/|https:\/\//);
  const compared = answerText("Ставка UNKNOWN (A4), 0 % с 12.04.2021 (K2), INDIVIDUAL (Sc07920d2538f).");
  expect(compared).toContain("0 % с 12.04.2021");
  expect(compared).toContain("неизвестно"); expect(compared).toContain("индивидуально");
  expect(compared).not.toMatch(/UNKNOWN|INDIVIDUAL|A4|K2|Sc079/);
  expect(answerText("Бесплатное (см. [Sabcdef123456]). Подтверждение pending.")).toBe(
    "Бесплатное. Подтверждение ожидает проверки.",
  );
  expect(answerText("Зачисление бесплатно【Sabcdef123456】.")).toBe("Зачисление бесплатно.");
  expect(answerText("Ставка неизвестна [С9375e7dbaf0e].")).toBe("Ставка неизвестна.");
});

test("history stores only display messages, rejects malformed state and restores interrupted answers safely", () => {
  const state = initialState();
  state.conversations[0].messages = [{ id: "m", role: "assistant", status: "streaming", lastSequence: 5, blocks: [
    { kind: "text", id: "t", text: "Точная ставка неизвестна [Sabcdef123456]." },
    { kind: "table", table: demoTable() },
  ] }];
  const raw = JSON.stringify(savedHistory(state));
  expect(raw).not.toMatch(/sources|sha256|Sabcdef|table|usage|provenance/);
  const restored = readHistory(raw)!;
  expect(restored.conversations[0].messages[0].status).toBe("stopped");
  expect(readHistory('{"conversations":[{"id":"a"}]}')).toBeNull();
  expect(readHistory("invalid")).toBeNull();
});
