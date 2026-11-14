import { NextRequest, NextResponse } from "next/server";
import { backendUrl, forwardToBackend, jsonError } from "@/lib/backend-proxy";

// Proxy del módulo Materias. Solo las operaciones migradas; cualquier otra ruta -> 404.
// Las consultas con parámetros viajan por POST (el proxy nunca reenvía query strings). El Excel de
// Optativas/Electivas sube en base64 dentro del JSON y baja por la ruta binaria propia de este módulo.
const POST = ["POST"] as const;
const ALLOWED = {
  "": ["GET"],
  "carreras/consulta": POST,
  "carreras/duplicado": POST,
  "carreras/alta": POST,
  "carreras/editar": POST,
  "carreras/eliminar": POST,
  plan: POST,
  "plan/guardar": POST,
  "plan/quitar": POST,
  "materias/existentes": POST,
  "materias/duplicado": POST,
  "materias/alta": POST,
  "materias/consulta": POST,
  "materias/detalle": POST,
  "materias/editar": POST,
  "materias/eliminar": POST,
  "carga-rapida/previsualizar": POST,
  "carga-rapida": POST,
  totales: POST,
  "totales/limpiar": POST,
  unicas: POST,
  "opciones/consulta": POST,
  "opciones/alta": POST,
  "opciones/editar": POST,
  "opciones/eliminar": POST,
  "opciones/habilitaciones": POST,
  "opciones/habilitaciones/agregar": POST,
  "opciones/habilitaciones/quitar": POST,
  "opciones/excel/previsualizar": POST,
  "opciones/excel/cargar": POST,
} as const;

// Límite del cuerpo JSON (Excel de hasta 10 MB en base64 + margen).
const MAX_BODY = 16 * 1024 * 1024;

async function modeloExcel(request: NextRequest) {
  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/materias/opciones/modelo-excel`, {
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

async function forward(request: NextRequest, ctx: RouteContext<"/api/materias/[[...path]]">) {
  const { path } = await ctx.params;
  const route = (path ?? []).join("/");
  if (request.method === "GET" && route === "opciones/modelo-excel") return modeloExcel(request);
  const length = Number(request.headers.get("content-length") ?? 0);
  if (length > MAX_BODY) return jsonError(413, "TOO_LARGE", "La solicitud es demasiado grande.");
  return forwardToBackend(request, "materias", path, ALLOWED);
}

export { forward as GET, forward as POST };
