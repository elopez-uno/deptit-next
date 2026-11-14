import { NextRequest, NextResponse } from "next/server";
import { backendUrl, forwardToBackend, jsonError, sameOrigin } from "@/lib/backend-proxy";

// Proxy del módulo Inicio. Solo el tablero (GET, sin parámetros: el ámbito y el período los decide la sesión) y la
// única descarga certificada, el Excel de "Próximos vencimientos" (D-AN6), binaria y por POST con Content-Disposition
// conservado. Cualquier otra ruta -> 404.
const ALLOWED = { "": ["GET"] } as const;
const DESCARGAS = new Set(["descargas/vencimientos"]);

// Mismo criterio que lib/backend-proxy.ts (POST solo desde el mismo origen).

async function descarga(request: NextRequest, route: string) {
  if (!sameOrigin(request)) return jsonError(403, "CSRF", "Solicitud rechazada.");
  const headers: Record<string, string> = { "content-type": "application/json", "x-deptit-request": "1" };
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/inicio/${route}`, { method: "POST", headers, body: "{}", cache: "no-store", redirect: "manual" });
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

async function forward(request: NextRequest, ctx: RouteContext<"/api/inicio/[[...path]]">) {
  const { path } = await ctx.params;
  const route = (path ?? []).join("/");
  if (DESCARGAS.has(route)) {
    if (request.method !== "POST") return jsonError(405, "METHOD", "Método no permitido.");
    return descarga(request, route);
  }
  return forwardToBackend(request, "inicio", path, ALLOWED);
}

export { forward as GET, forward as POST };
