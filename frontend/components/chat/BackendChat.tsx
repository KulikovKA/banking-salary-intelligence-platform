"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { BankCode, Identity, QuestionRequest, SnapshotView, SnapshotPage, CsrfChallenge } from "@/lib/api-contracts";
import { api, ApiClientError } from "@/lib/client";
import { BackendChatTransport, bankLabels } from "@/lib/chat/backend-transport";
import { ChatShell } from "./ChatShell";
import { formatTimestamp } from "@/lib/chat/format";

export function BackendChat() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [invite, setInvite] = useState(false);
  const [snapshots, setSnapshots] = useState<SnapshotView[]>([]);
  const [snapshotId, setSnapshotId] = useState("");
  const [generation, setGeneration] = useState(0);
  const [structured, setStructured] = useState(false);
  const [asOf, setAsOf] = useState("");
  const [operation, setOperation] = useState("account_maintenance");
  const [payer, setPayer] = useState<"employer" | "employee">("employer");
  const [period, setPeriod] = useState("месяц");
  const [region, setRegion] = useState("");
  const [payroll, setPayroll] = useState("");
  const [metrics, setMetrics] = useState("");
  const [banks, setBanks] = useState<BankCode[]>(Object.keys(bankLabels) as BankCode[]);
  const expire = useCallback(() => {
    setInvite(false);
    setIdentity(null); setSnapshots([]); setSnapshotId(""); setGeneration((v) => v + 1);
    setError("Сессия истекла. Войдите снова.");
  }, []);
  const showError = useCallback((cause: unknown) => {
    if (cause instanceof ApiClientError && cause.status === 401) expire();
    else setError(cause instanceof ApiClientError ? cause.message : "Не удалось выполнить запрос.");
  }, [expire]);
  const loadSnapshots = useCallback(async () => {
    const items: SnapshotView[] = [];
    let offset: number | null = 0;
    while (offset !== null) {
      const page: SnapshotPage = await api("GET /api/v1/snapshots", { parameters: { offset, limit: 100 } });
      items.push(...page.items.filter((item) => item.state === "frozen"));
      if (page.next_offset !== null && page.next_offset <= offset) throw new Error("Invalid pagination");
      offset = page.next_offset;
    }
    setSnapshots(items);
  }, []);
  useEffect(() => {
    let active = true;
    api("GET /api/v1/auth/me").then(async (user) => {
      if (!active) return;
      setIdentity(user);
      await loadSnapshots();
    }).catch((cause) => { if (active && !(cause instanceof ApiClientError && cause.status === 401)) showError(cause); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [loadSnapshots, showError]);
  useEffect(() => {
    if (!identity) return;
    const check = () => { if (document.visibilityState === "visible") void api("GET /api/v1/auth/me").catch(showError); };
    window.addEventListener("focus", check);
    document.addEventListener("visibilitychange", check);
    return () => { window.removeEventListener("focus", check); document.removeEventListener("visibilitychange", check); };
  }, [identity, showError]);
  async function authenticate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    setBusy(true); setError("");
    let authenticated = false;
    try {
      const challenge: CsrfChallenge = await api("GET /api/v1/auth/csrf");
      const password = String(values.get("password"));
      const user = invite
        ? await api("POST /api/v1/auth/accept-invite", { csrf: challenge.csrf_token, body: { token: String(values.get("token")), password } })
        : await api("POST /api/v1/auth/login", { csrf: challenge.csrf_token, body: { login: String(values.get("login")), password } });
      authenticated = true;
      form.reset(); setIdentity(user); setGeneration((v) => v + 1);
      await loadSnapshots();
    } catch (cause) {
      if (!authenticated && invite && cause instanceof ApiClientError && cause.status === 400)
        setError("Приглашение недействительно, уже использовано или истекло.");
      else if (!authenticated && cause instanceof ApiClientError && cause.status === 401)
        setError("Не удалось войти. Проверьте логин и пароль.");
      else showError(cause);
    }
    finally { setBusy(false); }
  }
  async function logout() {
    setBusy(true); setError("");
    // Unmount and abort all current conversations immediately, even if logout fails.
    setGeneration((v) => v + 1); setSnapshotId("");
    try { await api("POST /api/v1/auth/logout"); setIdentity(null); setSnapshots([]); setInvite(false); }
    catch (cause) { showError(cause); }
    finally { setBusy(false); }
  }
  const snapshot = snapshots.find((item) => item.id === snapshotId);
  const context: Omit<QuestionRequest, "question" | "snapshot_id"> = useMemo(() => ({
    bank_codes: banks.length ? banks : undefined,
    metric_codes: metrics.trim() ? metrics.split(",").map((v) => v.trim()).filter(Boolean) : undefined,
    scenario: structured && asOf ? { payer, operation, currency: "RUB", as_of: asOf,
      period: period || null, region: region || null, payroll_total: payroll || null } : undefined,
  }), [banks, metrics, structured, asOf, payer, operation, period, region, payroll]);
  const transport = useMemo(() => snapshot ? new BackendChatTransport(snapshot, context, expire) : undefined, [snapshot, context, expire]);
  const ready = Boolean(snapshot && (!structured || (asOf && operation && banks.length >= 2)));
  return <div className="backend-workspace">
    <div className="backend-controls">
      {loading ? <p role="status">Проверка сессии…</p> : identity ? <>
        <div className="session-controls"><span>{identity.login}</span><button onClick={() => void logout()} disabled={busy}>Выйти</button></div>
        <label>Набор данных <select aria-label="Набор данных" value={snapshotId} onChange={(e) => setSnapshotId(e.target.value)}>
          <option value="">Выберите snapshot явно</option>
          {snapshots.map((item) => <option key={item.id} value={item.id}>{item.corpus_kind} · revision {item.revision} · заморожен {formatTimestamp(item.frozen_at)}</option>)}
        </select></label>
        {!snapshots.length && <p role="status">Доступных frozen snapshot нет. Вопросы пока недоступны.</p>}
        {snapshot && <p>{snapshot.corpus_kind} · revision {snapshot.revision} · заморожен {formatTimestamp(snapshot.frozen_at)} · {snapshot.region} / {snapshot.employer_segment}. Отсутствуют: {snapshot.missing_banks.map((code) => bankLabels[code]).join(", ") || "нет"}. Дата заморозки не определяет дату действия тарифа.</p>}
        <details><summary>Параметры вопроса и сравнения</summary>
          <div className="question-controls">
            <fieldset><legend>Банки</legend>{(Object.keys(bankLabels) as BankCode[]).map((code) => <label key={code}><input type="checkbox" checked={banks.includes(code)} onChange={(e) => setBanks(e.target.checked ? [...banks, code] : banks.filter((b) => b !== code))} />{bankLabels[code]}</label>)}</fieldset>
            <label>Метрики через запятую <input value={metrics} onChange={(e) => setMetrics(e.target.value)} placeholder="account_monthly_fee" /></label>
            <label><input type="checkbox" checked={structured} onChange={(e) => setStructured(e.target.checked)} />Передать сценарий сравнения</label>
            {structured && <>
              <label>Дата действия <input aria-label="Дата действия" type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></label>
              <label>Плательщик <select value={payer} onChange={(e) => setPayer(e.target.value as typeof payer)}><option value="employer">Работодатель</option><option value="employee">Сотрудник</option></select></label>
              <label>Операция <input value={operation} onChange={(e) => setOperation(e.target.value)} /></label>
              <label>Период <input value={period} onChange={(e) => setPeriod(e.target.value)} /></label>
              <label>Регион <input value={region} onChange={(e) => setRegion(e.target.value)} placeholder="RU-KDA" /></label>
              <label>Общий фонд оплаты, RUB <input value={payroll} onChange={(e) => setPayroll(e.target.value)} inputMode="decimal" placeholder="5000000.01" /></label>
              <p>Нужны дата, операция и минимум два банка. Суммы — десятичные строки с точкой.</p>
            </>}
          </div>
        </details>
      </> : <form onSubmit={(e) => void authenticate(e)} className="login-form">
        <strong>{invite ? "Вход по приглашению" : "Вход в ассистент"}</strong>
        {invite ? <label>Токен приглашения <input name="token" type="password" autoComplete="off" required /></label> : <label>Логин <input name="login" autoComplete="username" required /></label>}
        <label>Пароль <input name="password" type="password" autoComplete={invite ? "new-password" : "current-password"} minLength={12} maxLength={128} required /></label>
        <button disabled={busy}>{busy ? "Подождите…" : invite ? "Принять приглашение" : "Войти"}</button>
        <button type="button" onClick={() => { setInvite(!invite); setError(""); }} disabled={busy}>{invite ? "Уже есть аккаунт" : "У меня приглашение"}</button>
      </form>}
      {error && <p role="alert">{error}</p>}
    </div>
    {identity && transport && <ChatShell key={`${generation}:${snapshotId}`} transport={transport} disabled={!ready || busy} />}
    {!loading && (!identity || !snapshot) && <div className="backend-placeholder">{identity ? "Выберите доступный набор данных, чтобы начать разговор." : "Войдите для доступа к данным и источникам."}</div>}
  </div>;
}
