import { ApiClientError } from "../client";
import type { ChatTransport, ChatStreamEvent } from "./models";

interface LiveAnswer {
  answer: string;
  sources: { id: string; bank: string; document: string; locator: string; text: string }[];
  provenance: { id: string; sha256: string; url: string }[];
  model: string;
  usage: { total_tokens?: number };
  latency_ms: number;
  notice: string;
  missing_banks: string[];
}
export class LiveChatTransport implements ChatTransport {
  readonly mode = "live" as const;
  constructor(private readonly allowed: boolean) {}
  async *stream(request: { question: string; previousTopic?: string }, signal: AbortSignal): AsyncIterable<ChatStreamEvent> {
    const response = await fetch("/api/local-demo/questions", {
      method: "POST", signal, headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: request.question, previous_topic: request.previousTopic ?? "", allow_public_text: this.allowed }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const code = typeof data.detail === "string" ? data.detail : "LOCAL_DEMO_UNAVAILABLE";
      const error = new ApiClientError(response.status, code);
      error.message = `Ошибка локального Groq: ${code} (HTTP ${response.status}).`;
      if (response.headers.has("retry-after")) error.message += ` Подождите ${response.headers.get("retry-after")} с.`;
      throw error;
    }
    const answer: LiveAnswer = await response.json();
    const id = crypto.randomUUID();
    yield { sequence: 1, type: "text.delta", blockId: `${id}-text`, delta: answer.answer };
    yield { sequence: 2, type: "table.start", table: {
      id, title: "Использованные выдержки · не проверенные тарифы", synthetic: false,
      banks: [], rows: [], revision: "локальный эксперимент",
      dataAsOf: `Groq ${answer.model} · ${answer.latency_ms} мс · ${answer.usage.total_tokens ?? "?"} токенов`,
      complete: true, limitations: [answer.notice, `Источник отсутствует: ${answer.missing_banks.join(", ")}`],
      sources: answer.sources.map((source) => {
        const provenance = answer.provenance.find((p) => p.id === source.id);
        return { id: source.id, label: `[${source.id}] ${source.bank} · ${source.document} · ${source.locator}`,
          fragmentPath: `/api/local-demo/fragment?id=${source.id}`,
          detail: `${source.text}\nURL оригинала: ${provenance?.url ?? "неизвестен"}\nSHA-256: ${provenance?.sha256 ?? "неизвестен"}` };
      }),
    } };
    yield { sequence: 3, type: "complete" };
  }
}
