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
import { HISTORY_KEY, readHistory, savedHistory } from "@/lib/chat/presentation";
const demoTransport = new DemoChatTransport();
export function ChatShell({
  transport = demoTransport,
  disabled = false,
  onSettings,
}: {
  transport?: ChatTransport;
  disabled?: boolean;
  onSettings?: () => void;
}) {
  const modern = transport.mode === "live";
  const [state, dispatch] = useReducer(chatReducer, undefined, initialState);
  const [restored, setRestored] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [away, setAway] = useState(false);
  const requests = useRef(
    new Map<string, { controller: AbortController; messageId: string }>(),
  );
  const scroll = useRef<HTMLDivElement>(null);
  const following = useRef(true);
  const active = state.conversations.find((c) => c.id === state.activeId)!;
  const generating = active.messages.some((m) => m.status === "streaming");
  useEffect(() => {
    const query = matchMedia("(max-width: 767px)");
    const update = () => setMobile(query.matches);
    update(); query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (modern) {
      try { const saved = readHistory(localStorage.getItem(HISTORY_KEY)); if (saved) dispatch({ type: "restore", state: saved }); } catch {}
    }
    setRestored(true);
  }, [modern]);
  useEffect(() => {
    if (modern && restored) {
      try { localStorage.setItem(HISTORY_KEY, JSON.stringify(savedHistory(state))); } catch {}
    }
  }, [modern, restored, state]);
  useEffect(() => {
    if (!disabled) return;
    for (const [id, request] of requests.current) {
      request.controller.abort();
      dispatch({ type: "stop", id, messageId: request.messageId });
    }
    requests.current.clear();
  }, [disabled]);
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
    setMobileOpen(false);
    following.current = true;
    setAway(false);
    dispatch({ type: "select", id });
  }
  function newChat() {
    setMobileOpen(false);
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
        { question, previousTopic: active.messages.filter((m) => m.role === "user").at(-1)?.blocks.map((b) => b.kind === "text" ? b.text : "").join(" ") },
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
  const composer = <ChatComposer draft={active.draft} generating={generating} conversationId={active.id}
    onDraft={(text) => dispatch({ type: "draft", id: active.id, text })}
    onSend={() => void send()} onStop={stop} disabled={disabled || (modern && !restored)}
    demo={transport.mode === "demo"} live={modern} />;
  return (
    <div className={`chat-shell ${modern ? "is-live" : ""} ${active.messages.length ? "has-conversation" : "is-empty"} ${mobileOpen ? "mobile-open" : ""} ${collapsed ? "panel-is-collapsed" : ""}`}>
      {modern && mobileOpen && <button className="sidebar-backdrop" aria-label="Закрыть меню" onClick={() => setMobileOpen(false)} />}
      <ChatSidebar
        conversations={state.conversations}
        activeId={active.id}
        collapsed={modern && mobile ? false : collapsed}
        onToggle={() => { if (modern && matchMedia("(max-width: 767px)").matches) setMobileOpen(false); else setCollapsed((value) => !value); }}
        onNew={newChat}
        onSelect={select}
        onDelete={deleteChat}
        modern={modern}
        onSettings={() => { setMobileOpen(false); onSettings?.(); }}
      />
      <main className="chat-main">
        <header className="chat-header">
          {modern && <button className="icon-button mobile-menu" aria-label="Открыть меню" onClick={() => setMobileOpen(true)}><Icon name="menu" /></button>}
          <div className="header-title">
            {modern ? "Зарплатный AI" : active.messages.length ? active.title : "Новый разговор"}
            {!modern && <span>Ассистент по зарплатным проектам</span>}
          </div>
          {!modern && <span className="mode-pill">
            <span />
            {transport.mode === "demo" ? "DEMO-режим" : "Доказательный ответ"}
          </span>}
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
                {!modern && <div className="conversation-start">
                  Начало разговора
                  <span>История доступна только в этой вкладке</span>
                </div>}
                {active.messages.map((message, index) => (
                  <ChatMessage key={message.id} message={message} demo={transport.mode === "demo"} modern={modern}
                    onRetry={!disabled && !generating ? () => {
                      const previous = active.messages.slice(0, index).findLast((m) => m.role === "user");
                      if (previous) void send(previous.blocks.map((b) => b.kind === "text" ? b.text : "").join(" "));
                    } : undefined} />
                ))}
              </>
            ) : (
              <ChatWelcome modern={modern} composer={modern ? composer : undefined} onSuggest={(question) => void send(question)} />
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
        {(!modern || active.messages.length > 0) && composer}
      </main>
    </div>
  );
}
