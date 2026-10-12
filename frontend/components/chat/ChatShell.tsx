"use client";
import { useEffect, useReducer, useRef, useState } from "react";
import type { ChatTransport } from "@/lib/chat/models";
import { chatReducer, initialState } from "@/lib/chat/state";
import {
  ChatTransportError,
  DemoChatTransport,
} from "@/lib/chat/demo-transport";
import { ChatSidebar } from "./ChatSidebar";
import { ChatMessage } from "./ChatMessage";
import { ChatComposer } from "./ChatComposer";
import { ChatWelcome } from "./ChatWelcome";
import { Icon } from "./Icon";
import { ApiClientError } from "@/lib/client";
const demoTransport = new DemoChatTransport();
export function ChatShell({
  transport = demoTransport,
  disabled = false,
}: {
  transport?: ChatTransport;
  disabled?: boolean;
}) {
  const [state, dispatch] = useReducer(chatReducer, undefined, initialState);
  const [collapsed, setCollapsed] = useState(false);
  const [away, setAway] = useState(false);
  const requests = useRef(
    new Map<string, { controller: AbortController; messageId: string }>(),
  );
  const scroll = useRef<HTMLDivElement>(null);
  const following = useRef(true);
  const active = state.conversations.find((c) => c.id === state.activeId)!;
  const generating = active.messages.some((m) => m.status === "streaming");
  useEffect(() => {
    const pending = requests.current;
    return () => {
      pending.forEach((request) => request.controller.abort());
      pending.clear();
    };
  }, []);
  useEffect(() => {
    if (following.current && scroll.current)
      scroll.current.scrollTop = scroll.current.scrollHeight;
  }, [active.id, active.messages]);
  function followLatest() {
    following.current = true;
    setAway(false);
    if (scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight;
  }
  function select(id: string) {
    following.current = true;
    setAway(false);
    dispatch({ type: "select", id });
  }
  function newChat() {
    following.current = true;
    setAway(false);
    dispatch({ type: "new", id: crypto.randomUUID() });
  }
  function deleteChat(id: string) {
    requests.current.get(id)?.controller.abort();
    requests.current.delete(id);
    if (id === active.id) {
      following.current = true;
      setAway(false);
    }
    dispatch({ type: "delete", id, replacementId: crypto.randomUUID() });
  }
  function stop() {
    const request = requests.current.get(active.id);
    if (!request) return;
    request.controller.abort();
    requests.current.delete(active.id);
    dispatch({ type: "stop", id: active.id, messageId: request.messageId });
  }
  async function send(suggestion?: string) {
    const question = (suggestion ?? active.draft).trim();
    if (disabled || !question || question.length > 2000 || requests.current.has(active.id))
      return;
    const id = active.id,
      messageId = crypto.randomUUID(),
      controller = new AbortController();
    requests.current.set(id, { controller, messageId });
    followLatest();
    dispatch({
      type: "send",
      id,
      question,
      userId: crypto.randomUUID(),
      assistantId: messageId,
    });
    let complete = false;
    try {
      for await (const event of transport.stream(
        { question },
        controller.signal,
      )) {
        if (controller.signal.aborted) break;
        dispatch({ type: "event", id, messageId, event });
        if (event.type === "complete") {
          complete = true;
          break;
        }
      }
      if (!controller.signal.aborted && !complete)
        throw new ChatTransportError("incomplete");
    } catch (error) {
      if (!controller.signal.aborted)
        dispatch({
          type: "error",
          id,
          messageId,
          error:
            error instanceof ApiClientError ? error.message : error instanceof ChatTransportError && error.code === "incomplete"
              ? "Ответ завершился раньше времени."
              : "Не удалось завершить ответ: ошибка соединения.",
        });
    } finally {
      if (requests.current.get(id)?.messageId === messageId)
        requests.current.delete(id);
    }
  }
  return (
    <div className={`chat-shell ${collapsed ? "panel-is-collapsed" : ""}`}>
      <ChatSidebar
        conversations={state.conversations}
        activeId={active.id}
        collapsed={collapsed}
        onToggle={() => setCollapsed((value) => !value)}
        onNew={newChat}
        onSelect={select}
        onDelete={deleteChat}
      />
      <main className="chat-main">
        <header className="chat-header">
          <div className="header-title">
            {active.messages.length ? active.title : "Новый разговор"}
            <span>Ассистент по зарплатным проектам</span>
          </div>
          <span className="mode-pill">
            <span />
            {transport.mode === "demo" ? "DEMO-режим" : "Доказательный ответ"}
          </span>
        </header>
        <div
          className="chat-scroll"
          ref={scroll}
          onScroll={() => {
            const element = scroll.current;
            if (element) {
              const near =
                element.scrollHeight -
                  element.scrollTop -
                  element.clientHeight <
                72;
              following.current = near;
              setAway(!near);
            }
          }}
        >
          <div
            className={`conversation-content ${active.messages.length ? "has-messages" : ""}`}
          >
            {active.messages.length ? (
              <>
                <div className="conversation-start">
                  Начало разговора
                  <span>История доступна только в этой вкладке</span>
                </div>
                {active.messages.map((message) => (
                  <ChatMessage key={message.id} message={message} demo={transport.mode === "demo"} />
                ))}
              </>
            ) : (
              <ChatWelcome onSuggest={(question) => void send(question)} />
            )}
          </div>
        </div>
        {away && (
          <button
            className="scroll-latest"
            onClick={followLatest}
            aria-label="К последнему сообщению"
          >
            <Icon name="down" size={17} />К последнему сообщению
          </button>
        )}
        <ChatComposer
          draft={active.draft}
          generating={generating}
          conversationId={active.id}
          onDraft={(text) => dispatch({ type: "draft", id: active.id, text })}
          onSend={() => void send()}
          onStop={stop}
          disabled={disabled}
          demo={transport.mode === "demo"}
        />
      </main>
    </div>
  );
}
