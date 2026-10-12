import type { ApiEndpoints, ApiError } from "./api-contracts";

const messages: Record<number, string> = {
  400: "Запрос не принят. Проверьте введённые данные.",
  401: "Сессия истекла. Войдите снова.", 403: "Доступ запрещён или проверка безопасности не пройдена.",
  404: "Набор данных или источник недоступен.", 409: "Состояние данных изменилось. Обновите набор.",
  422: "Проверьте поля запроса.", 429: "Слишком много запросов.",
  503: "Сервис временно недоступен. Попробуйте позже.",
};
export class ApiClientError extends Error {
  constructor(readonly status: number, readonly code: string, readonly retryAfter?: string) {
    super((code === "TIMEOUT" ? "Время ожидания ответа истекло." : code === "NETWORK_ERROR" ? "Ошибка соединения. Проверьте сеть." : messages[status] ?? "Не удалось выполнить запрос.") +
      (status === 429 && retryAfter ? ` Повторите через ${retryAfter} с.` : ""));
  }
}
export function sessionCsrf(): string | undefined {
  const value = document.cookie.split("; ").find((part) => part.startsWith("bsi-csrf="))?.slice(9);
  return value ? decodeURIComponent(value) : undefined;
}

export async function api<K extends keyof ApiEndpoints>(endpoint: K,
  options: { body?: ApiEndpoints[K]["request"]; parameters?: ApiEndpoints[K]["parameters"]; csrf?: string; signal?: AbortSignal } = {},
): Promise<ApiEndpoints[K]["response"]> {
  const [method, path] = endpoint.split(" ");
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(options.parameters ?? {}))
    for (const item of Array.isArray(value) ? value : [value]) if (item !== undefined) query.append(key, String(item));
  const headers = new Headers();
  if (options.body !== undefined) headers.set("content-type", "application/json");
  if (method !== "GET") {
    const csrf = options.csrf ?? sessionCsrf();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  try {
    const response = await fetch(path + (query.size ? `?${query}` : ""), { method, credentials: "same-origin", cache: "no-store", headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: AbortSignal.any([...(options.signal ? [options.signal] : []), AbortSignal.timeout(55000)]) });
    if (!response.ok) {
      const payload: ApiError | undefined = await response.json().catch(() => undefined);
      const retry = response.headers.get("retry-after") ?? undefined;
      throw new ApiClientError(response.status, payload?.error?.code ?? "API_ERROR",
        retry && /^\d{1,6}$/.test(retry) ? retry : undefined);
    }
    return await response.json();
  } catch (error) {
    if (error instanceof ApiClientError || options.signal?.aborted) throw error;
    if (error instanceof DOMException && error.name === "TimeoutError")
      throw new ApiClientError(0, "TIMEOUT");
    throw new ApiClientError(0, "NETWORK_ERROR");
  }
}
