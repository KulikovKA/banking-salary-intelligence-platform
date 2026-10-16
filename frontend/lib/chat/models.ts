/** UI presentation models; these are not the public SNAP-16 HTTP DTOs. */
export type CellStatus =
  | "verified"
  | "unknown"
  | "individual"
  | "conflict"
  | "blocked"
  | "not_applicable";
export type DisplayValue =
  | { kind: "money"; amount: string; currency: string; period?: string }
  | { kind: "percent"; amount: string; basis: string }
  | { kind: "text"; text: string };
export interface TableCell {
  bankId: string;
  status: CellStatus;
  value?: DisplayValue;
  conditions: string[];
}
export interface TableRow {
  id: string;
  label: string;
  cells: TableCell[];
}
export interface ResponseSource {
  id: string;
  label: string;
  detail: string;
  /** Only server-provided protected original paths can become links. */
  originalPath?: string;
  fragmentPath?: string;
}
export interface TableBlock {
  id: string;
  title: string;
  synthetic: boolean;
  banks: { id: string; label: string; subtitle?: string }[];
  rows: TableRow[];
  sources: ResponseSource[];
  limitations: string[];
  revision: string;
  dataAsOf: string;
  complete: boolean;
}
export type MessageBlock =
  | { kind: "text"; id: string; text: string }
  | { kind: "table"; table: TableBlock };
export interface ChatMessageModel {
  id: string;
  role: "user" | "assistant";
  status: "streaming" | "complete" | "stopped" | "error";
  blocks: MessageBlock[];
  lastSequence: number;
  error?: string;
}
export interface Conversation {
  id: string;
  title: string;
  draft: string;
  messages: ChatMessageModel[];
}
export type ChatStreamEvent = { sequence: number } & (
  | { type: "text.delta"; blockId: string; delta: string }
  | { type: "table.start"; table: TableBlock }
  | { type: "table.row"; tableId: string; row: TableRow }
  | { type: "table.finish"; tableId: string }
  | { type: "complete" }
);
export interface ChatTransport {
  readonly mode: "demo" | "backend" | "live";
  stream(
    request: { question: string; previousTopic?: string },
    signal: AbortSignal,
  ): AsyncIterable<ChatStreamEvent>;
}
