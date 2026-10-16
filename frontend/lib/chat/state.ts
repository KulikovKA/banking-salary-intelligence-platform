import type { ChatMessageModel, ChatStreamEvent, Conversation } from "./models";

export interface ChatState {
  activeId: string;
  conversations: Conversation[];
}
export function newConversation(id: string): Conversation {
  return { id, title: "Новый чат", draft: "", messages: [] };
}
export function initialState(): ChatState {
  return { activeId: "initial", conversations: [newConversation("initial")] };
}
export type ChatAction =
  | { type: "restore"; state: ChatState }
  | { type: "new"; id: string }
  | { type: "select"; id: string }
  | { type: "delete"; id: string; replacementId: string }
  | { type: "draft"; id: string; text: string }
  | {
      type: "send";
      id: string;
      question: string;
      userId: string;
      assistantId: string;
    }
  | { type: "event"; id: string; messageId: string; event: ChatStreamEvent }
  | { type: "stop" | "error"; id: string; messageId: string; error?: string };

/** Sequence and status guards reject replayed events and late writes after abort/delete. */
export function applyStreamEvent(
  message: ChatMessageModel,
  event: ChatStreamEvent,
): ChatMessageModel {
  if (message.status !== "streaming" || event.sequence <= message.lastSequence)
    return message;
  const next = { ...message, lastSequence: event.sequence };
  switch (event.type) {
    case "text.delta": {
      const existing = message.blocks.find(
        (block) => block.kind === "text" && block.id === event.blockId,
      );
      next.blocks = existing
        ? message.blocks.map((block) =>
            block.kind === "text" && block.id === event.blockId
              ? { ...block, text: block.text + event.delta }
              : block,
          )
        : [
            ...message.blocks,
            { kind: "text", id: event.blockId, text: event.delta },
          ];
      break;
    }
    case "table.start":
      if (
        !message.blocks.some(
          (block) =>
            block.kind === "table" && block.table.id === event.table.id,
        )
      ) {
        next.blocks = [
          ...message.blocks,
          { kind: "table", table: event.table },
        ];
      }
      break;
    case "table.row":
      next.blocks = message.blocks.map((block) =>
        block.kind === "table" &&
        block.table.id === event.tableId &&
        !block.table.rows.some((row) => row.id === event.row.id)
          ? {
              ...block,
              table: { ...block.table, rows: [...block.table.rows, event.row] },
            }
          : block,
      );
      break;
    case "table.finish":
      next.blocks = message.blocks.map((block) =>
        block.kind === "table" && block.table.id === event.tableId
          ? { ...block, table: { ...block.table, complete: true } }
          : block,
      );
      break;
    case "complete":
      next.status = "complete";
      break;
  }
  return next;
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  if (action.type === "restore") return action.state;
  if (action.type === "new")
    return {
      activeId: action.id,
      conversations: [newConversation(action.id), ...state.conversations],
    };
  if (action.type === "select")
    return state.conversations.some((c) => c.id === action.id)
      ? { ...state, activeId: action.id }
      : state;
  if (action.type === "delete") {
    const remaining = state.conversations.filter((c) => c.id !== action.id);
    const conversations = remaining.length
      ? remaining
      : [newConversation(action.replacementId)];
    return {
      conversations,
      activeId:
        state.activeId === action.id ? conversations[0].id : state.activeId,
    };
  }
  return {
    ...state,
    conversations: state.conversations.map((conversation) => {
      if (conversation.id !== action.id) return conversation;
      if (action.type === "draft")
        return { ...conversation, draft: action.text };
      if (action.type === "send") {
        if (conversation.messages.some((m) => m.status === "streaming"))
          return conversation;
        const user: ChatMessageModel = {
          id: action.userId,
          role: "user",
          status: "complete",
          blocks: [{ kind: "text", id: "question", text: action.question }],
          lastSequence: 0,
        };
        const assistant: ChatMessageModel = {
          id: action.assistantId,
          role: "assistant",
          status: "streaming",
          blocks: [],
          lastSequence: 0,
        };
        return {
          ...conversation,
          draft: "",
          title: conversation.messages.length
            ? conversation.title
            : action.question.replace(/\s+/g, " ").slice(0, 48),
          messages: [...conversation.messages, user, assistant],
        };
      }
      return {
        ...conversation,
        messages: conversation.messages.map((message) => {
          if (message.id !== action.messageId) return message;
          if (action.type === "event")
            return applyStreamEvent(message, action.event);
          if (message.status !== "streaming") return message;
          return {
            ...message,
            status: action.type === "stop" ? "stopped" : "error",
            error: action.error,
          };
        }),
      };
    }),
  };
}
