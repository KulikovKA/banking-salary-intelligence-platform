import { ApiClientError } from "../client";
import type { ChatTransport, ChatStreamEvent } from "./models";
import { answerText } from "./presentation";
export class LiveChatTransport implements ChatTransport {
  readonly mode = "live" as const;
  constructor(private readonly allowed: boolean) {}
  async *stream(request: { question: string; previousTopic?: string }, signal: AbortSignal): AsyncIterable<ChatStreamEvent> {
    if (!this.allowed) throw new ApiClientError(403, "CONSENT_REQUIRED");
    const response = await fetch("/api/local-demo/questions", {
      method: "POST", signal, headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: request.question, previous_topic: request.previousTopic ?? "", allow_public_text: this.allowed }),
    });
    if (!response.ok) {
      const error = new ApiClientError(response.status, "ANSWER_UNAVAILABLE");
      error.message = response.status === 429
        ? "Сейчас слишком много запросов. Подождите немного и попробуйте снова."
        : response.status === 403 ? "Разрешите обработку вопросов в настройках, чтобы продолжить."
        : "Не удалось получить ответ. Попробуйте ещё раз чуть позже.";
      throw error;
    }
    const answer: { answer: string } = await response.json();
    const id = crypto.randomUUID();
    // Backend evidence is retained; only the readable answer enters UI state and history.
    yield { sequence: 1, type: "text.delta", blockId: `${id}-text`, delta: answerText(answer.answer) };
    yield { sequence: 2, type: "complete" };
  }
}
