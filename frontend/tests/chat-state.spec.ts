import { test, expect } from "@playwright/test";
import { applyStreamEvent, chatReducer, initialState } from "../lib/chat/state";
import {
  DemoChatTransport,
  demoTable,
  abortableDelay,
  ChatTransportError,
} from "../lib/chat/demo-transport";
import { formatDecimal, safeOriginalPath } from "../lib/chat/format";
import type { ChatMessageModel } from "../lib/chat/models";

function streaming(): ChatMessageModel {
  return {
    id: "m",
    role: "assistant",
    status: "streaming",
    blocks: [],
    lastSequence: 0,
  };
}
test("incremental fragments assemble once; replay and events after completion are ignored", () => {
  let message = applyStreamEvent(streaming(), {
    type: "text.delta",
    sequence: 1,
    blockId: "text",
    delta: "Первый ",
  });
  message = applyStreamEvent(message, {
    type: "text.delta",
    sequence: 1,
    blockId: "text",
    delta: "дубль",
  });
  message = applyStreamEvent(message, {
    type: "text.delta",
    sequence: 2,
    blockId: "text",
    delta: "ответ",
  });
  expect(message.blocks).toEqual([
    { kind: "text", id: "text", text: "Первый ответ" },
  ]);
  message = applyStreamEvent(message, { type: "complete", sequence: 3 });
  expect(
    applyStreamEvent(message, {
      type: "text.delta",
      sequence: 4,
      blockId: "text",
      delta: "поздний",
    }),
  ).toBe(message);
});
test("table rows have stable identities and finish independently of surrounding text", () => {
  let message = applyStreamEvent(streaming(), {
    type: "table.start",
    sequence: 1,
    table: demoTable(),
  });
  const row = { id: "row", label: "Test", cells: [] };
  message = applyStreamEvent(message, {
    type: "table.row",
    sequence: 2,
    tableId: "comparison",
    row,
  });
  message = applyStreamEvent(message, {
    type: "table.row",
    sequence: 3,
    tableId: "comparison",
    row,
  });
  message = applyStreamEvent(message, {
    type: "table.finish",
    sequence: 4,
    tableId: "comparison",
  });
  expect(message.blocks).toHaveLength(1);
  const block = message.blocks[0];
  expect(block.kind).toBe("table");
  if (block.kind === "table") {
    expect(block.table.rows).toHaveLength(1);
    expect(block.table.complete).toBe(true);
  }
});
test("switching and interleaved streams target their original conversations", () => {
  let state = chatReducer(initialState(), {
    type: "send",
    id: "initial",
    question: "Первая тема",
    userId: "u1",
    assistantId: "a1",
  });
  state = chatReducer(state, { type: "new", id: "second" });
  state = chatReducer(state, { type: "draft", id: "second", text: "Черновик" });
  state = chatReducer(state, {
    type: "event",
    id: "initial",
    messageId: "a1",
    event: {
      type: "text.delta",
      sequence: 1,
      blockId: "text",
      delta: "Ответ первой темы",
    },
  });
  expect(state.activeId).toBe("second");
  expect(state.conversations[0].draft).toBe("Черновик");
  expect(state.conversations[1].messages[1].blocks[0]).toEqual({
    kind: "text",
    id: "text",
    text: "Ответ первой темы",
  });
});
test("stop and delete reject late events; delete last conversation restores empty state", () => {
  let state = chatReducer(initialState(), {
    type: "send",
    id: "initial",
    question: "Тема",
    userId: "u",
    assistantId: "a",
  });
  state = chatReducer(state, { type: "stop", id: "initial", messageId: "a" });
  state = chatReducer(state, {
    type: "event",
    id: "initial",
    messageId: "a",
    event: { type: "text.delta", sequence: 1, blockId: "t", delta: "late" },
  });
  expect(state.conversations[0].messages[1].blocks).toHaveLength(0);
  state = chatReducer(state, {
    type: "delete",
    id: "initial",
    replacementId: "replacement",
  });
  state = chatReducer(state, {
    type: "event",
    id: "initial",
    messageId: "a",
    event: { type: "complete", sequence: 2 },
  });
  expect(state.activeId).toBe("replacement");
  expect(state.conversations[0].messages).toHaveLength(0);
});
test("old generation cannot modify a subsequent message after stop", () => {
  let state = chatReducer(initialState(), {
    type: "send",
    id: "initial",
    question: "First",
    userId: "u",
    assistantId: "a",
  });
  state = chatReducer(state, { type: "stop", id: "initial", messageId: "a" });
  state = chatReducer(state, {
    type: "send",
    id: "initial",
    question: "Second",
    userId: "u2",
    assistantId: "a2",
  });
  state = chatReducer(state, {
    type: "event",
    id: "initial",
    messageId: "a",
    event: { type: "complete", sequence: 99 },
  });
  expect(state.conversations[0].messages[1].status).toBe("stopped");
  expect(state.conversations[0].messages[3].status).toBe("streaming");
  expect(state.conversations[0].title).toBe("First");
});
test("decimal formatting preserves precision, zero and fractional digits", () => {
  expect(formatDecimal("12345678901234567890.123456")).toBe(
    "12 345 678 901 234 567 890,123456",
  );
  expect(formatDecimal("0.30")).toBe("0,30");
  expect(formatDecimal("0")).toBe("0");
  expect(formatDecimal("NaN")).toBe("Некорректное значение");
});
test("protected source links reject arbitrary schemes, hosts, traversal and query strings", () => {
  const safe =
    "/api/v1/documents/01234567-89ab-cdef-0123-456789abcdef/original";
  expect(safeOriginalPath(safe)).toBe(safe);
  for (const unsafe of [
    "javascript:alert(1)",
    "data:text/html,test",
    "https://example.com",
    "//evil.test",
    safe + "?next=evil",
    "/api/v1/documents/../secret/original",
    safe + "\n",
  ])
    expect(safeOriginalPath(unsafe)).toBeUndefined();
});
test("demo stream assembles full answer and every table row without a provider", async () => {
  let message = streaming();
  for await (const event of new DemoChatTransport(0, 0).stream(
    { question: "Test" },
    new AbortController().signal,
  ))
    message = applyStreamEvent(message, event);
  expect(message.status).toBe("complete");
  expect(message.blocks).toHaveLength(3);
  const table = message.blocks.find((b) => b.kind === "table");
  if (table?.kind === "table") {
    expect(table.table.rows).toHaveLength(3);
    expect(table.table.synthetic).toBe(true);
    expect(table.table.complete).toBe(true);
  }
});
test("AbortController interrupts pending delay and stream", async () => {
  const controller = new AbortController();
  const pending = abortableDelay(10000, controller.signal);
  controller.abort();
  await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  const iterator = new DemoChatTransport()
    .stream({ question: "Test" }, controller.signal)
    [Symbol.asyncIterator]();
  await expect(iterator.next()).rejects.toMatchObject({ name: "AbortError" });
});
test("network demo fails after partial text, without a completed event", async () => {
  const received: string[] = [];
  try {
    for await (const event of new DemoChatTransport(0, 0).stream(
      { question: "демо: ошибка сети" },
      new AbortController().signal,
    ))
      received.push(event.type);
    throw new Error("Expected failure");
  } catch (error) {
    expect(error).toBeInstanceOf(ChatTransportError);
  }
  expect(received.length).toBeGreaterThan(1);
  expect(received).not.toContain("complete");
});
