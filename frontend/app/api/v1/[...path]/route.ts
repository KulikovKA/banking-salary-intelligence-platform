import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const readable = /^(auth\/(csrf|me)|snapshots(?:\/[0-9a-f-]{36})?|documents\/[0-9a-f-]{36}(?:\/original)?)$/i;
const writable = /^(auth\/(login|logout|accept-invite)|assistant\/questions)$/;

function failure(status: number, code: string) {
  return Response.json({ schema_version: 1, error: { schema_version: 1, code,
    message: "Сервис временно недоступен", request_id: crypto.randomUUID() } },
    { status, headers: { "Cache-Control": "no-store" } });
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const route = path.join("/");
  if (!(request.method === "GET" ? readable : writable).test(route))
    return failure(404, "OBJECT_UNAVAILABLE");
  // Never infer or replace Origin from forwarded headers: FastAPI checks the actual browser value.
  const configured = process.env.BACKEND_URL;
  if (!configured) return failure(503, "BACKEND_UNAVAILABLE");
  try {
    const base = new URL(configured);
    if (!["http:", "https:"].includes(base.protocol) || base.username || base.password ||
      base.pathname !== "/" || base.search || base.hash) return failure(503, "BACKEND_UNAVAILABLE");
    const target = new URL(`/api/v1/${route}`, base);
    target.search = request.nextUrl.search;
    const headers = new Headers();
    for (const name of ["cookie", "origin", "x-csrf-token", "content-type"])
      if (request.headers.has(name)) headers.set(name, request.headers.get(name)!);
    let body: ArrayBuffer | undefined;
    if (request.method === "POST") {
      // Bound actual bytes, including chunked requests, before allocating a full body.
      const reader = request.body?.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > 65536) { await reader.cancel(); return failure(422, "PAYLOAD_TOO_LARGE"); }
          chunks.push(value);
        }
      }
      const bytes = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
      body = bytes.buffer;
    }
    const upstream = await fetch(target, { method: request.method, headers, body,
      cache: "no-store", redirect: "manual",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(50000)]) });
    if (upstream.status >= 300 && upstream.status < 400) return failure(503, "BACKEND_UNAVAILABLE");
    const outgoing = new Headers({ "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
    for (const name of ["content-type", "content-disposition", "retry-after", "x-request-id"])
      if (upstream.headers.has(name)) outgoing.set(name, upstream.headers.get(name)!);
    for (const cookie of upstream.headers.getSetCookie()) outgoing.append("set-cookie", cookie);
    return new Response(upstream.body, { status: upstream.status, headers: outgoing });
  } catch { return failure(503, "BACKEND_UNAVAILABLE"); }
}
export const GET = proxy;
export const POST = proxy;
