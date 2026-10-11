"use client";
import { useEffect, useRef, useState } from "react";
import type { ChatMessageModel } from "@/lib/chat/models";
import { messagePlainText } from "@/lib/chat/format";
import { Icon } from "./Icon";
import { ResponseTable } from "./ResponseTable";
import { StreamingIndicator } from "./StreamingIndicator";
export function ChatMessage({ message }: { message: ChatMessageModel }) {
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
      await navigator.clipboard.writeText(messagePlainText(message));
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
      {assistant && (
        <div className="assistant-avatar">
          <Icon name="spark" size={18} />
        </div>
      )}
      <div className="message-body">
        {assistant && (
          <div className="message-author">
            Ассистент<span>DEMO</span>
          </div>
        )}
        <div className="message-content">
          {message.blocks.map((block) =>
            block.kind === "text" ? (
              <p className="message-text" key={block.id}>
                {block.text}
              </p>
            ) : (
              <ResponseTable
                key={block.table.id}
                table={block.table}
                pending={message.status === "streaming"}
              />
            ),
          )}
        </div>
        {message.status === "streaming" && (
          <StreamingIndicator empty={!message.blocks.length} />
        )}
        {message.status === "stopped" && (
          <p className="message-state" role="status">
            Генерация остановлена. Показана полученная часть ответа.
          </p>
        )}
        {message.status === "error" && (
          <p className="message-error" role="alert">
            {message.error} Полученная часть ответа сохранена. Можно отправить
            запрос ещё раз.
          </p>
        )}
        {message.blocks.length > 0 && (
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
