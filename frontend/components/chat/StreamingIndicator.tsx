export function StreamingIndicator({ empty = false, modern = false }: { empty?: boolean; modern?: boolean }) {
  return (
    <span className="streaming-indicator" role="status">
      <span className="streaming-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      {modern ? "Формирую ответ…" : empty ? "Готовлю учебный пример" : "Формирую ответ"}
    </span>
  );
}
