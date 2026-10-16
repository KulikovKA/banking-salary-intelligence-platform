"use client";
import { useEffect, useRef, type ReactNode } from "react";
import { Icon } from "./Icon";

export function ChatDialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current!; dialog.showModal(); return () => dialog.close(); }, []);
  return <dialog ref={ref} className="chat-dialog" aria-label={title} onCancel={(event) => { event.preventDefault(); onClose(); }}>
    <div className="dialog-heading"><h2>{title}</h2><button className="icon-button" aria-label="Закрыть окно" onClick={onClose}><Icon name="close" /></button></div>
    {children}
  </dialog>;
}
