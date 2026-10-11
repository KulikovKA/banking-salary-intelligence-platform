export function StreamingIndicator({ empty = false }: { empty?: boolean }) {
  return (
    <span className="streaming-indicator" role="status">
      <span className="streaming-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      {empty ? "Готовлю учебный пример" : "Формирую ответ"}
    </span>
  );
}
