import { NextRequest, NextResponse } from "next/server";
import { backendUrl, forwardToBackend, jsonError } from "@/lib/backend-proxy";

// Proxy del módulo Extensión. Solo las operaciones migradas; cualquier otra ruta -> 404.
// Las consultas con parámetros viajan por POST (el proxy nunca reenvía query strings). El Excel integral modelo baja por
// una ruta binaria propia.
const POST = ["POST"] as const;
const ALLOWED = {
  "": ["GET"],
  alertas: POST,
  "post-accion": POST,
  vigentes: POST,
  costos: POST,
  "vigentes/ficha": POST,
  actos: POST,
  "asignar/proyectos": POST,
  "asignar/detalle": POST,
  capacidad: POST,
  asignaciones: POST,
  historial: POST,
  "historial/asignaciones": POST,
  "editar/proyectos": POST,
  "editar/asignaciones": POST,
  "editar/asignacion/opciones": POST,
  "bajas/suspender/proyectos": POST,
  "bajas/archivar/proyectos": POST,
  "carga-rapida/previsualizar": POST,
  "proyecto/guardar": POST,
  "actos/vincular": POST,
  "actos/desvincular": POST,
  asignar: POST,
  "asignar/eliminar-error": POST,
  "editar/proyecto": POST,
  "editar/asignacion": POST,
  "bajas/asignacion": POST,
  "bajas/suspender": POST,
  "bajas/archivar": POST,
  "bajas/eliminar": POST,
  "carga-rapida": POST,
} as const;

// Límite del cuerpo JSON: Excel en base64 (hasta 15 MB en el backend) + margen.
const MAX_BODY = 24 * 1024 * 1024;

async function modeloExcel(request: NextRequest) {
  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/extension/modelo-excel`, {
      method: "GET",
      headers,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return jsonError(503, "BACKEND_UNREACHABLE", "No se pudo conectar con el servidor. Reintentá en unos instantes.");
  }
  const out: Record<string, string> = {
    "content-type": upstream.headers.get("content-type") ?? "application/octet-stream",
    "cache-control": "no-store",
  };
  const disposition = upstream.headers.get("content-disposition");
  if (upstream.ok && disposition) out["content-disposition"] = disposition;
  return new NextResponse(await upstream.arrayBuffer(), { status: upstream.status, headers: out });
}

async function forward(request: NextRequest, ctx: RouteContext<"/api/extension/[[...path]]">) {
  const { path } = await ctx.params;
  const route = (path ?? []).join("/");
  if (request.method === "GET" && route === "modelo-excel") return modeloExcel(request);
  const length = Number(request.headers.get("content-length") ?? 0);
  if (length > MAX_BODY) return jsonError(413, "TOO_LARGE", "La solicitud es demasiado grande.");
  return forwardToBackend(request, "extension", path, ALLOWED);
}

export { forward as GET, forward as POST };
