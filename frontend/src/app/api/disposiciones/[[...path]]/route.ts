import { NextRequest, NextResponse } from "next/server";
import { backendUrl, forwardToBackend, jsonError, sameOrigin } from "@/lib/backend-proxy";

// Proxy del módulo Disposiciones. Solo las operaciones migradas; cualquier otra ruta -> 404 (no hay PDF, Excel,
// edición ni anulación). Las consultas con parámetros viajan por POST (el proxy nunca reenvía query strings). El Word y
// los ZIP bajan por rutas binarias propias: FastAPI re-consulta la fila y valida dueño y ruta (nunca hay paths).
const POST = ["POST"] as const;
const ALLOWED = {
  "": ["GET"],
  periodo: POST,
  docente: POST,
  "docente/vista-previa": POST,
  historial: POST,
  "configuracion/guardar": POST,
  "plantilla/reemplazar": POST,
  "numero-inicial/guardar": POST,
  "docente/guardar-datos": POST,
  generar: POST,
  "generar-masiva": POST,
  "historial/eliminar": POST,
} as const;
const BINARIOS = new Set(["descargar", "historial/zip", "zip-lote"]);

// Límite del cuerpo JSON: plantilla .docx en base64 (el backend admite hasta el doble del máximo para que la
// validación B12E informe "supera el tamaño máximo") + margen.
const MAX_BODY = 56 * 1024 * 1024;

// Mismo criterio que lib/backend-proxy.ts (escrituras y consultas POST solo desde el mismo origen).

async function binario(request: NextRequest, path: string) {
  if (!sameOrigin(request)) return jsonError(403, "CSRF", "Solicitud rechazada.");
  const body = await request.text();
  if (body.length > 64 * 1024) return jsonError(413, "TOO_LARGE", "La solicitud es demasiado grande.");
  const headers: Record<string, string> = { "content-type": "application/json", "x-deptit-request": "1" };
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/disposiciones/${path}`, {
      method: "POST",
      headers,
      body,
      cache: "no-store",
      redirect: "manual",
    });
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

async function forward(request: NextRequest, ctx: RouteContext<"/api/disposiciones/[[...path]]">) {
  const { path } = await ctx.params;
  const route = (path ?? []).join("/");
  if (request.method === "POST" && BINARIOS.has(route)) return binario(request, route);
  const length = Number(request.headers.get("content-length") ?? 0);
  if (length > MAX_BODY) return jsonError(413, "TOO_LARGE", "La solicitud es demasiado grande.");
  return forwardToBackend(request, "disposiciones", path, ALLOWED);
}

export { forward as GET, forward as POST };
