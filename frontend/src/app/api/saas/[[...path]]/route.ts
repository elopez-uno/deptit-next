import { NextRequest, NextResponse } from "next/server";
import { backendUrl, forwardToBackend, jsonError, sameOrigin } from "@/lib/backend-proxy";

// Proxy del módulo Administración SaaS (solo superadmin; FastAPI re-autoriza cada request). Lectura inicial por GET y
// una ruta POST por acción (esquema exacto en el backend); el Excel de las tablas certificadas vuelve binario con su
// Content-Disposition. Cualquier otra ruta -> 404 (sin endpoint genérico de actualización, sin importaciones).
const ALLOWED = Object.fromEntries(
  ["planes", "instituciones", "instituciones/cupo", "instituciones/comercial", "instituciones/bloquear", "instituciones/desbloquear",
   "instituciones/eliminar", "departamentos", "departamentos/editar", "departamentos/eliminar", "usuarios", "usuarios/estado",
   "usuarios/editar", "usuarios/eliminar"].map((r) => [r, ["POST"]])
) as Record<string, readonly string[]>;
ALLOWED[""] = ["GET"];
const DESCARGAS = new Set(["descargas/excel"]);
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
    upstream = await fetch(`${backendUrl()}/saas/${route}`, { method: "POST", headers, body, cache: "no-store", redirect: "manual" });
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

async function forward(request: NextRequest, ctx: RouteContext<"/api/saas/[[...path]]">) {
  const { path } = await ctx.params;
  const route = (path ?? []).join("/");
  if (DESCARGAS.has(route)) {
    if (request.method !== "POST") return jsonError(405, "METHOD", "Método no permitido.");
    return descarga(request, route);
  }
  return forwardToBackend(request, "saas", path, ALLOWED);
}

export { forward as GET, forward as POST };
