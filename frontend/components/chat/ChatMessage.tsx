"use client";
import { useEffect, useRef, useState } from "react";
import type { ChatMessageModel } from "@/lib/chat/models";
import { messagePlainText } from "@/lib/chat/format";
import { Icon } from "./Icon";
import { ResponseTable } from "./ResponseTable";
import { StreamingIndicator } from "./StreamingIndicator";
import { AnswerMarkdown } from "./AnswerMarkdown";
import { answerText } from "@/lib/chat/presentation";
export function ChatMessage({ message, demo = true, modern = false, onRetry }: { message: ChatMessageModel; demo?: boolean; modern?: boolean; onRetry?: () => void }) {
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "failed">(
    "idle",
  );
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  async function copy() {
    try {
      await navigator.clipboard.writeText(modern ? message.blocks.filter((b) => b.kind === "text").map((b) => message.role === "assistant" ? answerText(b.text) : b.text).join("\n\n") : messagePlainText(message));
      setCopyStatus("copied");
    } catch {
      setCopyStatus("failed");
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopyStatus("idle"), 2400);
  }
  const assistant = message.role === "assistant";
  return (
    <article
      className={`message message-${message.role}`}
      aria-label={assistant ? "Сообщение ассистента" : "Ваше сообщение"}
      data-message-id={message.id}
    >
      {assistant && !modern && (
        <div className="assistant-avatar">
          <Icon name="spark" size={18} />
        </div>
      )}
      <div className="message-body">
        {assistant && !modern && (
          <div className="message-author">
            Ассистент{demo && <span>DEMO</span>}
          </div>
        )}
        <div className="message-content">
          {message.blocks.map((block) =>
            block.kind === "text" ? (modern && assistant ? <AnswerMarkdown key={block.id} text={block.text} /> :
              <p className="message-text" key={block.id}>
                {block.text}
              </p>
            ) : modern ? null : (
              <ResponseTable
                key={block.table.id}
                table={block.table}
                pending={message.status === "streaming"}
              />
            ),
          )}
        </div>
        {message.status === "streaming" && (
          <StreamingIndicator empty={!message.blocks.length} modern={modern} />
        )}
        {message.status === "stopped" && (
          <p className="message-state" role="status">
            {modern ? "Ответ остановлен." : demo ? "Генерация остановлена. Показана полученная часть ответа." : "Клиентский запрос остановлен. Backend может продолжить обработку."}
          </p>
        )}
        {message.status === "error" && (
          <p className="message-error" role="alert">
            {message.error}{!modern && " Полученная часть ответа сохранена. Можно отправить запрос ещё раз."}
            {modern && onRetry && <button className="retry-button" onClick={onRetry}>Попробовать снова</button>}
          </p>
        )}
        {message.blocks.length > 0 && (!modern || assistant) && (
          <div className="message-actions">
            <button
              type="button"
              className="copy-button"
              onClick={copy}
              aria-label={
                assistant ? "Копировать ответ" : "Копировать ваше сообщение"
              }
            >
              <Icon
                name={copyStatus === "copied" ? "check" : "copy"}
                size={15}
              />
              {copyStatus === "copied" ? "Скопировано" : "Копировать"}
            </button>
            {copyStatus === "failed" && (
              <span role="status">Браузер не разрешил копирование</span>
            )}
          </div>
        )}
      </div>
    </article>
  );
}
