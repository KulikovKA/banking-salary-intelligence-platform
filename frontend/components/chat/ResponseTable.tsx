import type { TableBlock } from "@/lib/chat/models";
import {
  cellStatusLabels,
  formatValue,
  safeOriginalPath,
} from "@/lib/chat/format";
import { Icon } from "./Icon";
export function ResponseTable({
  table,
  pending = false,
}: {
  table: TableBlock;
  pending?: boolean;
}) {
  return (
    <section className="response-table" aria-label={table.title}>
      <div className="table-heading">
        <span className="table-title">
          <Icon name="table" size={18} />
          {table.title}
        </span>
        {table.synthetic && <span className="demo-tag">Синтетические данные</span>}
      </div>
      <div className="table-scroll">
        <table>
          <caption className="sr-only">
            {table.title}.{" "}
            {table.synthetic
              ? "Вымышленные учебные значения."
              : "Значения из источников."}
          </caption>
          <thead>
            <tr>
              <th scope="col">Критерий</th>
              {table.banks.map((bank) => (
                <th scope="col" key={bank.id}>
                  {bank.label}
                  <span className="bank-subtitle">{bank.subtitle}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row) => (
              <tr key={row.id}>
                <th scope="row">{row.label}</th>
                {table.banks.map((bank) => {
                  const cell = row.cells.find((c) => c.bankId === bank.id);
                  const status = cell?.status ?? "unknown";
                  const numeric =
                    status === "verified" &&
                    cell?.value &&
                    cell.value.kind !== "text";
                  return (
                    <td key={bank.id} className={numeric ? "numeric-cell" : ""}>
                      {status === "verified" && cell?.value ? (
                        <span className="cell-value">
                          {formatValue(cell.value)}
                        </span>
                      ) : (
                        <span className={`cell-status cell-status-${status}`}>
                          {
                            cellStatusLabels[
                              status === "verified" ? "unknown" : status
                            ]
                          }
                        </span>
                      )}
                      {cell?.value?.kind === "percent" &&
                        status === "verified" && (
                          <span className="cell-detail">
                            {cell.value.basis}
                          </span>
                        )}
                      {cell?.conditions.map((condition, i) => (
                        <span className="cell-detail" key={i}>
                          {condition}
                        </span>
                      ))}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!table.complete && (
        <p className="table-progress" role="status">
          {pending ? "Таблица формируется…" : "Таблица получена частично."}
        </p>
      )}
      <div className="table-context">
        <span>Набор {table.revision}</span>
        <span>{table.dataAsOf}</span>
      </div>
      <div className="table-notes">
        {table.limitations.map((text) => (
          <p key={text}>{text}</p>
        ))}
      </div>
      <div className="table-sources">
        <span className="source-label">Источники</span>
        {table.sources.map((source) => {
          const path = safeOriginalPath(source.originalPath) ??
            (source.fragmentPath && /^\/api\/local-demo\/(?:fragment|document)\?id=S[a-f0-9]{12}$/.test(source.fragmentPath)
              ? source.fragmentPath : undefined);
          return (
            <div className="source" key={source.id}>
              <Icon name="file" size={17} />
              <div>
                {path ? (
                  <a href={path} target="_blank" rel="noopener noreferrer">
                    {source.label}
                  </a>
                ) : (
                  <span className="source-title">{source.label}</span>
                )}
                <p>{source.detail}</p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
