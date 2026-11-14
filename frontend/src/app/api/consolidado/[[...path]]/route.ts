import { NextRequest, NextResponse } from "next/server";
import { backendUrl, forwardToBackend, jsonError, sameOrigin } from "@/lib/backend-proxy";

// Proxy del módulo Consolidado institucional. Solo la lectura inicial (GET, sin parámetros: la institución la decide la
// sesión), la tabla del visor bajo demanda (POST con clave de la lista fija y búsqueda) y las 2 descargas certificadas:
// CSV de la tabla completa y Excel de la tabla mostrada, binarias por POST con Content-Disposition conservado.
// Cualquier otra ruta -> 404. No hay Word, PDF, ZIP ni TXT.
const ALLOWED = { "": ["GET"], tabla: ["POST"] } as const;
const DESCARGAS = new Set(["descargas/csv", "descargas/excel"]);
const MAX_BODY = 16 * 1024;

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
    upstream = await fetch(`${backendUrl()}/consolidado/${route}`, { method: "POST", headers, body, cache: "no-store", redirect: "manual" });
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

async function forward(request: NextRequest, ctx: RouteContext<"/api/consolidado/[[...path]]">) {
  const { path } = await ctx.params;
  const route = (path ?? []).join("/");
  if (DESCARGAS.has(route)) {
    if (request.method !== "POST") return jsonError(405, "METHOD", "Método no permitido.");
    return descarga(request, route);
  }
  return forwardToBackend(request, "consolidado", path, ALLOWED);
}

export { forward as GET, forward as POST };
