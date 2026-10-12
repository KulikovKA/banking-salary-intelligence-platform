"use client";
import { useEffect, useRef } from "react";
import { Icon } from "./Icon";
export function ChatComposer({
  draft,
  generating,
  conversationId,
  onDraft,
  onSend,
  onStop,
  disabled = false,
  demo = true,
}: {
  draft: string;
  generating: boolean;
  conversationId: string;
  onDraft: (text: string) => void;
  onSend: () => void;
  onStop: () => void;
  disabled?: boolean;
  demo?: boolean;
}) {
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    input.current?.focus();
  }, [conversationId]);
  useEffect(() => {
    if (input.current) {
      input.current.style.height = "auto";
      input.current.style.height = `${Math.min(input.current.scrollHeight, 144)}px`;
    }
  }, [draft]);
  return (
    <div className="composer-dock">
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          onSend();
        }}
      >
        <textarea
          ref={input}
          value={draft}
          onChange={(e) => onDraft(e.target.value)}
          placeholder="Спросите об условиях зарплатного проекта…"
          aria-label="Сообщение"
          maxLength={2000}
          rows={1}
          disabled={disabled}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault();
              if (!generating) onSend();
            }
          }}
        />
        <div className="composer-toolbar">
          <span className="composer-context">
            <Icon name="spark" size={15} />
            Зарплатные проекты
          </span>
          <div className="composer-controls">
            <span className="keyboard-hint">
              Enter <span>↵</span>
            </span>
            {generating ? (
              <button
                className="send-button stop-button"
                type="button"
                onClick={onStop}
                aria-label="Остановить генерацию"
                title="Остановить генерацию"
              >
                <Icon name="stop" size={17} />
              </button>
            ) : (
              <button
                className="send-button"
                type="submit"
                disabled={disabled || !draft.trim()}
                aria-label="Отправить сообщение"
                title="Отправить сообщение"
              >
                <Icon name="arrow" size={21} />
              </button>
            )}
          </div>
        </div>
      </form>
      <p className="composer-footnote">
        {demo ? "DEMO · Синтетические данные. Не является банковским предложением." : "Ответ по выбранному snapshot. Не вводите ФИО, реквизиты и зарплатные ведомости."}
        <span>Shift + Enter — новая строка</span>
      </p>
    </div>
  );
}
