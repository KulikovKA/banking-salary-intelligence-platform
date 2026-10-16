import type { NextRequest } from "next/server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(request: NextRequest, context: { params: Promise<{ action: string }> }) {
  const { action } = await context.params;
  const host = request.headers.get("host");
  if (process.env.NODE_ENV !== "development" || process.env.LIVE_DEMO_ENABLED !== "true" ||
      process.env.APP_ENV !== "poc" || !["127.0.0.1:3010", "localhost:3010"].includes(host ?? "") ||
      !["status", "questions", "fragment"].includes(action)) return new Response(null, { status: 404 });
  if ((action === "questions") !== (request.method === "POST")) return new Response(null, { status: 405 });
  if (request.method === "POST" && request.headers.get("origin") !== `http://${host}`)
    return new Response(null, { status: 403 });
  const id = request.nextUrl.searchParams.get("id") ?? "";
  if (action === "fragment" && !/^S[a-f0-9]{12}$/.test(id)) return new Response(null, { status: 404 });
  let body: string | undefined;
  if (request.method === "POST") {
    const reader = request.body?.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    if (reader) while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 16384) { await reader.cancel(); return new Response(null, { status: 413 }); }
      chunks.push(value);
    }
    body = Buffer.concat(chunks).toString("utf8");
  }
  try {
    const upstream = await fetch(`http://127.0.0.1:8010/local-demo/${action}${action === "fragment" ? `?id=${id}` : ""}`, {
      method: request.method, body, cache: "no-store", redirect: "error",
      headers: { "Content-Type": "application/json", "X-Live-Demo-Token": process.env.LIVE_DEMO_TOKEN ?? "" },
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(25000)]),
    });
    return new Response(upstream.body, { status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        ...(upstream.headers.has("retry-after") ? { "Retry-After": upstream.headers.get("retry-after")! } : {}) } });
  } catch { return Response.json({ detail: "LOCAL_BACKEND_UNAVAILABLE" }, { status: 503 }); }
}
export const GET = proxy;
export const POST = proxy;
