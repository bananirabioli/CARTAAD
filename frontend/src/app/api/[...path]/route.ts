import type { NextRequest } from "next/server";

/**
 * Same-origin proxy: /api/<path> → FastAPI. Reads API_INTERNAL_URL at request time so the same
 * build works locally (http://localhost:8000) and in Docker (http://api:8000).
 */
const HOP_BY_HOP = ["connection", "keep-alive", "transfer-encoding", "upgrade", "host", "content-length", "content-encoding"];

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params;
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const search = req.nextUrl.search;
  const target = `${base}/${path.map(encodeURIComponent).join("/")}${search}`;

  const headers = new Headers(req.headers);
  for (const h of HOP_BY_HOP) headers.delete(h);

  const hasBody = !["GET", "HEAD"].includes(req.method);
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return Response.json({ error: { code: "upstream_unavailable", message: "La API no responde." } }, { status: 502 });
  }

  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.includes(key.toLowerCase()) && key.toLowerCase() !== "set-cookie") out.set(key, value);
  });
  for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export { proxy as DELETE, proxy as GET, proxy as PATCH, proxy as POST, proxy as PUT };
