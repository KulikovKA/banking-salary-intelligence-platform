import type {
  ChatStreamEvent,
  ChatTransport,
  TableBlock,
  TableRow,
} from "./models";

export class ChatTransportError extends Error {
  constructor(readonly code: "network" | "incomplete") {
    super(code);
  }
}
export function abortableDelay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted();
    const abort = () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, ms);
    signal.addEventListener("abort", abort, { once: true });
  });
}

const rows: TableRow[] = [
  {
    id: "monthly",
    label: "Обслуживание счёта",
    cells: [
      {
        bankId: "a",
        status: "verified",
        value: {
          kind: "money",
          amount: "1200.00",
          currency: "RUB",
          period: "мес.",
        },
        conditions: ["Учебное значение. Пакет «Пример»."],
      },
      {
        bankId: "b",
        status: "verified",
        value: {
          kind: "money",
          amount: "900.00",
          currency: "RUB",
          period: "мес.",
        },
        conditions: [
          "Учебное значение. Только при выполнении условий пакета и подключении электронного документооборота.",
        ],
      },
      {
        bankId: "c",
        status: "individual",
        conditions: ["Определяется индивидуальным договором."],
      },
    ],
  },
  {
    id: "crediting",
    label: "Зачисление зарплаты",
    cells: [
      {
        bankId: "a",
        status: "verified",
        value: { kind: "percent", amount: "0.30", basis: "от суммы реестра" },
        conditions: ["Учебное значение. Внутри выбранного пакета."],
      },
      {
        bankId: "b",
        status: "unknown",
        conditions: ["В учебном документе нет подтверждённой ставки."],
      },
      {
        bankId: "c",
        status: "conflict",
        conditions: ["Учебные документы расходятся. Требуется проверка."],
      },
    ],
  },
  {
    id: "integration",
    label: "Интеграция с 1С",
    cells: [
      {
        bankId: "a",
        status: "verified",
        value: { kind: "text", text: "По условиям пакета" },
        conditions: ["Версия и подключение требуют уточнения."],
      },
      {
        bankId: "b",
        status: "not_applicable",
        conditions: ["Не входит в этот учебный сценарий."],
      },
      {
        bankId: "c",
        status: "blocked",
        conditions: ["Учебный источник недоступен для проверки."],
      },
    ],
  },
];
export function demoTable(): TableBlock {
  return {
    id: "comparison",
    title: "Сравнение условий",
    synthetic: true,
    complete: false,
    banks: [
      { id: "a", label: "Демо-банк А", subtitle: "Пакет «Пример»" },
      { id: "b", label: "Демо-банк Б", subtitle: "Пакет «Учебный»" },
      { id: "c", label: "Демо-банк В", subtitle: "Индивидуальные условия" },
    ],
    rows: [],
    revision: "DEMO-01",
    dataAsOf: "Дата условий неизвестна",
    sources: [
      {
        id: "demo-document",
        label: "Учебный набор DEMO-01",
        detail:
          "Синтетические примеры для интерфейса. Официальных банковских документов нет.",
      },
    ],
    limitations: [
      "Регион и сегмент не подтверждены. Применимость значений не установлена.",
      "Это вымышленные условия, а не банковские предложения. Итоговая стоимость и победитель не определяются.",
    ],
  };
}

/** Local development adapter: no fetch, provider call, credentials or HTTP endpoint. */
export class DemoChatTransport implements ChatTransport {
  readonly mode = "demo" as const;
  constructor(
    private readonly fragmentDelay = 45,
    private readonly rowDelay = 300,
  ) {}
  async *stream(
    request: { question: string },
    signal: AbortSignal,
  ): AsyncIterable<ChatStreamEvent> {
    let sequence = 0;
    const errorDemo =
      request.question.trim().toLocaleLowerCase("ru") === "демо: ошибка сети";
    const text = errorDemo
      ? "Покажу, как чат сохраняет уже полученный текст при ошибке соединения. "
      : "Давайте посмотрим на условия рядом. Ниже — учебный пример сравнения трёх вымышленных банков. Я покажу значения, обязательные условия и пробелы в данных.\n\nВсе числа синтетические: по ним нельзя выбирать реальный зарплатный проект.";
    for (const delta of text.match(/[\s\S]{1,12}/g) ?? []) {
      await abortableDelay(this.fragmentDelay, signal);
      yield {
        type: "text.delta",
        blockId: "intro",
        delta,
        sequence: ++sequence,
      };
    }
    if (errorDemo) throw new ChatTransportError("network");
    await abortableDelay(this.rowDelay, signal);
    yield { type: "table.start", table: demoTable(), sequence: ++sequence };
    for (const row of rows) {
      await abortableDelay(this.rowDelay, signal);
      yield {
        type: "table.row",
        tableId: "comparison",
        row,
        sequence: ++sequence,
      };
    }
    signal.throwIfAborted();
    yield { type: "table.finish", tableId: "comparison", sequence: ++sequence };
    const closing =
      "Для реального сравнения понадобятся проверенные документы банков и одинаковый сценарий. Неизвестная ставка остаётся неизвестной, а индивидуальные условия требуют отдельного предложения.";
    for (const delta of closing.match(/[\s\S]{1,12}/g) ?? []) {
      await abortableDelay(this.fragmentDelay, signal);
      yield {
        type: "text.delta",
        blockId: "closing",
        delta,
        sequence: ++sequence,
      };
    }
    signal.throwIfAborted();
    yield { type: "complete", sequence: ++sequence };
  }
}
