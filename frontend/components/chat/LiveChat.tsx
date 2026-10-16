"use client";
import { useMemo, useState } from "react";
import { ChatShell } from "./ChatShell";
import { LiveChatTransport } from "@/lib/chat/live-transport";

export function LiveChat() {
  const [allowed, setAllowed] = useState(false);
  const transport = useMemo(() => new LiveChatTransport(allowed), [allowed]);
  return <div className="backend-workspace">
    <div className="backend-controls">
      <strong>Локальный AI · настоящий Groq GPT-OSS 120B</strong>
      <p>Локальные оригиналы: ВТБ, Кубань Кредит. Сбер и Альфа-Банк: источник отсутствует.
        Выдержки и тарифы не прошли ручную проверку; актуальность и применимость не подтверждены.</p>
      <label><input type="checkbox" checked={allowed} onChange={(e) => setAllowed(e.target.checked)} />
        Разрешаю отправлять публичные выдержки этих документов в Groq для локального эксперимента.
        Это не разрешение банка на reuse.</label>
      <p>Внешней модели передаётся только тема из фиксированного словаря и выбранные выдержки.
        Не вводите конфиденциальные сведения. До 30 запросов за запуск, без автоматических повторов.</p>
    </div>
    <ChatShell transport={transport} disabled={!allowed} />
  </div>;
}
