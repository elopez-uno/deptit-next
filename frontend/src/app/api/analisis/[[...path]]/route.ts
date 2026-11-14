import { NextRequest, NextResponse } from "next/server";
import { backendUrl, forwardToBackend, jsonError, sameOrigin } from "@/lib/backend-proxy";

// Proxy del módulo Análisis (incluye Productividad). Solo las operaciones migradas; cualquier otra ruta -> 404.
// Las consultas viajan por POST (el proxy nunca reenvía query strings). Las 4 descargas certificadas (Word del
// movimiento docente, CSV del indicador, CSV por categoría de alerta y TXT del prompt) son binarias y pasan por
// una ruta propia que conserva Content-Disposition. No hay Excel, PDF ni ZIP.
const POST = ["POST"] as const;
const ALLOWED = {
  "": ["GET"],
  periodo: POST,
  comparacion: POST,
  porcentaje: POST,
} as const;
const DESCARGAS = new Set(["descargas/word", "descargas/indicador", "descargas/alertas", "descargas/prompt"]);
const MAX_BODY = 64 * 1024;

// Mismo criterio que lib/backend-proxy.ts (POST solo desde el mismo origen).

async function descarga(request: NextRequest, route: string) {
  if (!sameOrigin(request)) return jsonError(403, "CSRF", "Solicitud rechazada.");
  const body = await request.text();
  if (body.length > MAX_BODY) return jsonError(413, "TOO_LARGE", "La solicitud es demasiado grande.");
  const headers: Record<string, string> = { "content-type": "application/json", "x-deptit-request": "1" };
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/analisis/${route}`, { method: "POST", headers, body, cache: "no-store", redirect: "manual" });
  } catch {
    return jsonError(503, "BACKEND_UNREACHABLE", "No se pudo conectar con el servidor. Reintentá en unos instantes.");
  }
  const out: Record<string, string> = {
    "content-type": upstream.headers.get("content-type") ?? "application/octet-stream",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  };
  const disposition = upstream.headers.get("content-disposition");
  if (upstream.ok && disposition) out["content-disposition"] = disposition;
  return new NextResponse(await upstream.arrayBuffer(), { status: upstream.status, headers: out });
}

async function forward(request: NextRequest, ctx: RouteContext<"/api/analisis/[[...path]]">) {
  const { path } = await ctx.params;
  const route = (path ?? []).join("/");
  if (DESCARGAS.has(route)) {
    if (request.method !== "POST") return jsonError(405, "METHOD", "Método no permitido.");
    return descarga(request, route);
  }
  return forwardToBackend(request, "analisis", path, ALLOWED);
}

export { forward as GET, forward as POST };
