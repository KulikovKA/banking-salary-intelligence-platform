import type { CellStatus, ChatMessageModel, DisplayValue } from "./models";

export const cellStatusLabels: Record<CellStatus, string> = {
  verified: "Подтверждено",
  unknown: "Неизвестно",
  individual: "Индивидуально",
  conflict: "Конфликт данных",
  blocked: "Недоступно",
  not_applicable: "Не применимо",
};

/** Format decimal strings without binary floats, arithmetic or rounding. */
export function formatDecimal(amount: string): string {
  if (!/^-?\d+(\.\d+)?(?![\s\S])/.test(amount)) return "Некорректное значение";
  const [integer, fraction] = amount.split(".");
  return (
    integer.replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0") +
    (fraction === undefined ? "" : `,${fraction}`)
  );
}
export function formatValue(value: DisplayValue): string {
  if (value.kind === "text") return value.text;
  const amount = formatDecimal(value.amount);
  if (amount === "Некорректное значение") return amount;
  if (value.kind === "percent") return `${amount}\u00a0%`;
  return `${amount}\u00a0${value.currency === "RUB" ? "₽" : value.currency}${value.period ? ` / ${value.period}` : ""}`;
}
export function safeOriginalPath(path?: string): string | undefined {
  return path &&
    /^\/api\/v1\/documents\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\/original(?![\s\S])/i.test(
      path,
    )
    ? path
    : undefined;
}
export function formatTimestamp(value?: string | null): string {
  if (!value) return "дата неизвестна";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "дата неизвестна";
  return new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow", dateStyle: "short", timeStyle: "short" }).format(date) + " МСК";
}
export function messagePlainText(message: ChatMessageModel): string {
  return message.blocks
    .map((block) => {
      if (block.kind === "text") return block.text;
      const table = block.table;
      return [
        table.title,
        table.synthetic ? "DEMO: синтетические данные" : "Данные источников",
        `Набор ${table.revision}; ${table.dataAsOf}`,
        table.banks.map((b) => b.label).join(" | "),
        ...table.rows.map(
          (row) =>
            `${row.label}: ${table.banks
              .map((bank) => {
                const cell = row.cells.find((c) => c.bankId === bank.id);
                return cell
                  ? [
                      cell.status === "verified" && cell.value
                        ? formatValue(cell.value)
                        : cellStatusLabels[
                            cell.status === "verified" ? "unknown" : cell.status
                          ],
                      ...cell.conditions,
                    ].join("; ")
                  : "Неизвестно";
              })
              .join(" | ")}`,
        ),
        ...table.limitations,
        ...table.sources.map((s) => `${s.label}: ${s.detail}`),
      ].join("\n");
    })
    .join("\n\n");
}
