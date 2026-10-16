"use client";
import { useEffect, useMemo, useState } from "react";
import { ChatShell } from "./ChatShell";
import { LiveChatTransport } from "@/lib/chat/live-transport";
import { CONSENT_KEY, HISTORY_KEY } from "@/lib/chat/presentation";
import { ChatDialog } from "./ChatDialog";
import { Icon } from "./Icon";

export function LiveChat() {
  const [allowed, setAllowed] = useState(false);
  const [consentOpen, setConsentOpen] = useState(false);
  const [settings, setSettings] = useState(false);
  const [generation, setGeneration] = useState(0);
  const [banks, setBanks] = useState<string[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    const synchronize = (event: StorageEvent) => { if (event.key === CONSENT_KEY) setAllowed(event.newValue === "accepted"); };
    window.addEventListener("storage", synchronize);
    try {
      const consent = localStorage.getItem(CONSENT_KEY) === "accepted";
      setAllowed(consent); setConsentOpen(!consent);
    } catch { setConsentOpen(true); }
    const controller = new AbortController();
    fetch("/api/local-demo/status", { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("status");
        const status: { banks: string[] } = await response.json();
        setBanks(status.banks);
      }).catch(() => { if (!controller.signal.aborted) setError("Не удалось подключиться. Обновите страницу и попробуйте снова."); });
    return () => { controller.abort(); window.removeEventListener("storage", synchronize); };
  }, []);
  const transport = useMemo(() => new LiveChatTransport(allowed), [allowed]);
  function consent(value: boolean) {
    try { if (value) localStorage.setItem(CONSENT_KEY, "accepted"); else localStorage.removeItem(CONSENT_KEY); } catch {}
    setAllowed(value); setConsentOpen(false);
  }
  return <div className="live-workspace">
    <ChatShell key={generation} transport={transport} disabled={!allowed || !banks.length} onSettings={() => setSettings(true)} />
    {error && <div className="connection-note" role="alert">{error}</div>}
    {!allowed && !consentOpen && !settings && <button className="consent-reminder" onClick={() => setConsentOpen(true)}>Разрешить обработку вопросов</button>}
    {consentOpen && <ChatDialog title="Перед первым разговором" onClose={() => setConsentOpen(false)}>
      <div className="consent-symbol"><Icon name="spark" size={28} /></div>
      <p>Чтобы подготовить ответ, ассистент отправит тему вопроса и подходящие выдержки из публичных банковских материалов в сервис Groq.</p>
      <p className="dialog-secondary">Не вводите персональные данные, реквизиты и конфиденциальные сведения. Разрешение можно отозвать в настройках.</p>
      <div className="dialog-actions"><button className="secondary-button" onClick={() => consent(false)}>Не сейчас</button><button className="primary-button" onClick={() => consent(true)}>Разрешить и продолжить</button></div>
    </ChatDialog>}
    {settings && <ChatDialog title="Настройки" onClose={() => setSettings(false)}>
      <section className="setting-section"><h3>Обработка вопросов</h3>
        <p className="dialog-secondary">{allowed ? "Вы разрешили передачу публичных выдержек в Groq для подготовки ответов." : "Обработка вопросов приостановлена. Разрешите передачу публичных выдержек, чтобы продолжить."}</p>
        <button className="secondary-button" onClick={() => { if (allowed) consent(false); else { setSettings(false); setConsentOpen(true); } }}>{allowed ? "Отозвать согласие" : "Разрешить обработку"}</button>
      </section>
      <section className="setting-section"><h3>История диалогов</h3><p className="dialog-secondary">Ваши разговоры сохраняются только в этом браузере.</p>
        <button className="danger-button" onClick={() => { try { localStorage.removeItem(HISTORY_KEY); } catch {} setGeneration((v) => v + 1); setSettings(false); }}>Очистить историю</button>
      </section>
    </ChatDialog>}
  </div>;
}
