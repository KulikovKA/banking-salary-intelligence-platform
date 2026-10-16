import type { ChatState } from "./state";

export const HISTORY_KEY = "salary-ai-chats-v1";
export const CONSENT_KEY = "salary-ai-consent-v1";

/** Remove provider citation syntax only; preserve all financial values and conditions. */
export function answerText(text: string): string {
  return text
    .replace(/(?:^|\n)\s*Источники:\s*(?:\[S[a-f0-9]+\][,\s]*)+(?=$|\n)/g, "")
    .replace(/\[(?:S[a-f0-9]{6,}|[SAVK]\d+|\d+)\]/g, "")
    .replace(/\[С[a-f0-9]{6,}\]/g, "")
    .replace(/\((?:S[a-f0-9]{6,}|[SAVK]\d+)\)/g, "")
    .replace(/\bS[a-f0-9]{12}\b/g, "")
    .replace(/【\s*】/g, "")
    .replace(/\bUNKNOWN\b/g, "неизвестно")
    .replace(/\bINDIVIDUAL\b/g, "индивидуально")
    .replace(/\bpending\b/gi, "ожидает проверки")
    .replace(/\((?:см\.?\s*)?\s*\)/g, "")
    .replace(/[ \t]+([.,;:])/g, "$1")
    .replace(/\[([^\]]+)\]\((?:https?:\/\/|\/api\/)[^)]*\)/g, "$1")
    .replace(/https?:\/\/\S+|\/api\/\S+/g, "")
    .replace(/[ \t]+\n/g, "\n")
    .trim();
}

export function savedHistory(state: ChatState): ChatState {
  return { activeId: state.activeId, conversations: state.conversations.slice(0, 50).map((chat) => ({
    id: chat.id, title: chat.title.slice(0, 80), draft: chat.draft.slice(0, 2000),
    messages: chat.messages.slice(-200).map((message) => ({
      id: message.id, role: message.role,
      status: message.status === "streaming" ? "stopped" : message.status,
      lastSequence: 0,
      // Never persist sources, snippets, API responses or credentials.
      blocks: message.blocks.filter((b) => b.kind === "text").map((b) => ({
        kind: "text" as const, id: b.id,
        text: message.role === "assistant" ? answerText(b.text).slice(0, 20000) : b.text.slice(0, 2000),
      })),
    })),
  })) };
}

export function readHistory(raw: string | null): ChatState | null {
  if (!raw || raw.length > 2_000_000) return null;
  try {
    const value: ChatState = JSON.parse(raw);
    if (!Array.isArray(value.conversations) || !value.conversations.length || value.conversations.length > 50) return null;
    const ids = new Set<string>();
    for (const chat of value.conversations) {
      if (typeof chat.id !== "string" || ids.has(chat.id) || typeof chat.title !== "string" ||
          typeof chat.draft !== "string" || !Array.isArray(chat.messages) || chat.messages.length > 200) return null;
      ids.add(chat.id);
      for (const message of chat.messages) {
        if (typeof message.id !== "string" || !["user", "assistant"].includes(message.role) ||
            !["streaming", "complete", "stopped", "error"].includes(message.status) ||
            !Array.isArray(message.blocks) || message.blocks.some((b) => b.kind !== "text" || typeof b.text !== "string" || typeof b.id !== "string")) return null;
      }
    }
    if (!ids.has(value.activeId)) value.activeId = value.conversations[0].id;
    return savedHistory(value);
  } catch { return null; }
}
