import type { AnswerEnvelope, BankCode, ComparisonCell, QuestionRequest, SnapshotView } from "../api-contracts";
import { api } from "../client";
import type { ChatTransport, ChatStreamEvent, DisplayValue, TableBlock } from "./models";
import { safeOriginalPath, formatTimestamp } from "./format";

export const bankLabels: Record<BankCode, string> = {
  sber: "Сбер", vtb: "ВТБ", alfa: "Альфа-Банк", kuban_credit: "Кубань Кредит",
};
export const answerLabels: Record<AnswerEnvelope["status"], string> = {
  answered: "Ответ", partial: "Частичный ответ", clarification: "Нужно уточнение",
  insufficient: "Недостаточно данных", fallback: "Резервный ответ",
};
const metricLabels: Record<string, string> = {
  account_monthly_fee: "Обслуживание счёта", payroll_credit_fee: "Зачисление зарплаты",
  external_bank_transfer_fee: "Перевод в другой банк", employee_card_fee: "Карта сотрудника",
  cash_withdrawal_limit: "Лимит снятия наличных", transfer_limit: "Лимит переводов",
  crediting_time: "Срок зачисления", employee_privilege: "Привилегии сотрудников",
  integration_1c: "Интеграция с 1С", integration_api: "Интеграция по API",
};
export function displayValue(value: ComparisonCell["value"]): DisplayValue | undefined {
  if (!value) return undefined;
  switch (value.kind) {
    case "money": return value.amount === null ? undefined : { kind: "money", amount: value.amount, currency: value.currency, period: value.period ?? undefined };
    case "percent": return value.amount === null ? undefined : { kind: "percent", amount: value.amount, basis: value.basis };
    case "text": case "individual": return { kind: "text", text: value.text_value };
    case "boolean": return { kind: "text", text: value.boolean_value ? "Да" : "Нет" };
    case "count": return { kind: "text", text: `${value.amount ?? "Неизвестно"} ${value.unit}${value.period ? ` / ${value.period}` : ""}` };
    case "range": return { kind: "text", text: `${value.lower_inclusive === false ? "(" : "["}${value.lower ?? "Неизвестно"}; ${value.upper ?? "Неизвестно"}${value.upper_inclusive === false ? ")" : "]"} ${value.unit} ${value.currency ?? ""}; ${value.basis ?? ""}; ${value.period ?? ""}` };
    case "formula": return { kind: "text", text: `Формула: ${value.formula}; параметры ${JSON.stringify(value.parameters)}; ${value.basis ?? ""}; ${value.currency ?? ""}; ${value.period ?? ""}` };
  }
}
export function answerTable(answer: AnswerEnvelope, snapshot: SnapshotView): TableBlock {
  const comparison = answer.comparison;
  const banks = [...new Set(comparison?.rows.flatMap((r) => r.cells.map((c) => c.bank_code)) ?? [])];
  return {
    id: answer.id, title: comparison ? "Сравнение по источникам" : "Источники и контекст ответа",
    synthetic: snapshot.corpus_kind === "synthetic", banks: banks.map((id) => ({ id, label: bankLabels[id] })),
    rows: comparison?.rows.map((row) => ({ id: row.metric_code, label: metricLabels[row.metric_code] ?? row.metric_code,
      cells: row.cells.map((cell) => ({ bankId: cell.bank_code, status: cell.status,
        value: displayValue(cell.value), conditions: [cell.conditions,
          ...(cell.missing_inputs ?? []).map((input) => `Не хватает: ${input}`),
          ...((cell.value?.kind === "money" || cell.value?.kind === "percent") && cell.value.amount === null ? ["Значение неизвестно"] : []),
          ...(cell.value?.kind === "percent" && cell.value.period ? [`Период: ${cell.value.period}`] : []),
          ...(cell.status !== "verified" && cell.value ? [displayValue(cell.value)?.kind === "text" ? (displayValue(cell.value) as { text: string }).text : JSON.stringify(cell.value)] : []),
        ].filter((v): v is string => Boolean(v)) })),
    })) ?? [],
    sources: (answer.sources ?? []).map((source) => ({ id: source.evidence.id,
      label: `Документ ${source.evidence.source_version_id}`,
      detail: `${source.evidence.quote} · ${JSON.stringify(source.evidence.locator)} · SHA-256 ${source.evidence.raw_sha256} · Получен ${formatTimestamp(source.evidence.acquired_at)}`,
      originalPath: safeOriginalPath(source.download_url) })),
    limitations: [...new Set([...(answer.limitations ?? []), ...(comparison?.limitations ?? []),
      ...(answer.claims ?? []).map((claim) => claim.text), ...(comparison?.claims ?? []).map((claim) => claim.text),
      ...(comparison ? [`Сценарий: ${JSON.stringify(comparison.scenario_echo)}`] : []),
      ...(comparison?.rows.flatMap((row) => (row.pairwise ?? []).map((pair) =>
        `${bankLabels[pair.left]} / ${bankLabels[pair.right]}: ${pair.status}; разница ${pair.delta ?? "неизвестна"}; ${pair.formula ?? ""}`)) ?? []),
      `Покрытие: ${snapshot.bank_codes.map((code) => bankLabels[code]).join(", ")}; отсутствуют: ${snapshot.missing_banks.map((code) => bankLabels[code]).join(", ") || "нет"}`,
    ])], revision: String(answer.corpus_revision), dataAsOf: `Дата данных: ${answer.data_as_of}`, complete: true,
  };
}
export class BackendChatTransport implements ChatTransport {
  readonly mode = "backend" as const;
  constructor(private readonly snapshot: SnapshotView,
    private readonly context: Omit<QuestionRequest, "question" | "snapshot_id"> = {},
    private readonly expired: () => void = () => {}) {}
  async *stream(request: { question: string }, signal: AbortSignal): AsyncIterable<ChatStreamEvent> {
    let answer: AnswerEnvelope;
    try {
      answer = await api("POST /api/v1/assistant/questions", { body: {
        ...this.context, snapshot_id: this.snapshot.id, question: request.question,
      }, signal });
    } catch (error) {
      if (error && typeof error === "object" && "status" in error && error.status === 401) this.expired();
      throw error;
    }
    if (signal.aborted) return;
    if (answer.snapshot_id !== this.snapshot.id || answer.corpus_revision !== this.snapshot.revision)
      throw new Error("Response context mismatch");
    // One validated JSON response; these presentation events are not server streaming.
    yield { sequence: 1, type: "text.delta", blockId: answer.id, delta: `${answerLabels[answer.status]}\n${answer.text}` };
    yield { sequence: 2, type: "table.start", table: answerTable(answer, this.snapshot) };
    yield { sequence: 3, type: "complete" };
  }
}
