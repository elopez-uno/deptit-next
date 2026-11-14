import { NextRequest, NextResponse } from "next/server";
import { backendUrl, forwardToBackend, jsonError, sameOrigin } from "@/lib/backend-proxy";

// Proxy del módulo Comisiones. Solo las operaciones migradas; cualquier otra ruta -> 404.
// Las consultas con parámetros viajan por POST (el proxy nunca reenvía query strings). Los dos Excel (modelo integral
// de carga rápida y Excel completado de un período) bajan por rutas binarias propias.
const POST = ["POST"] as const;
const ALLOWED = {
  "": ["GET"],
  periodo: POST,
  inscriptos: POST,
  alertas: POST,
  sedes: POST,
  "abrir/materias": POST,
  "abrir/materia": POST,
  docentes: POST,
  "docentes/roles": POST,
  lista: POST,
  detalle: POST,
  "asignacion/franjas": POST,
  "edicion/datos": POST,
  "carga-rapida/previsualizar": POST,
  abrir: POST,
  "modificacion/alta": POST,
  "modificacion/baja": POST,
  "edicion/guardar-datos": POST,
  "edicion/nombres": POST,
  "edicion/horario/editar": POST,
  "edicion/horario/agregar": POST,
  "edicion/horario/eliminar": POST,
  "edicion/docente/asignar": POST,
  "edicion/docente/franjas": POST,
  "edicion/docente/quitar": POST,
  "edicion/eliminar": POST,
  "inscriptos/guardar": POST,
  "sedes/agregar": POST,
  "sedes/editar": POST,
  "sedes/eliminar": POST,
  "carga-rapida": POST,
} as const;

// Límite del cuerpo JSON: Excel integral en base64 (hasta 15 MB en el backend) + texto pegado + margen.
const MAX_BODY = 24 * 1024 * 1024;

// Mismo criterio que lib/backend-proxy.ts (escrituras y consultas POST solo desde el mismo origen).

async function binario(request: NextRequest, path: string, body?: string) {
  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  if (body !== undefined) {
    if (!sameOrigin(request)) {
      return jsonError(403, "CSRF", "Solicitud rechazada.");
    }
    headers["content-type"] = "application/json";
    headers["x-deptit-request"] = "1";
  }
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/comisiones/${path}`, {
      method: body === undefined ? "GET" : "POST",
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
  };
  const disposition = upstream.headers.get("content-disposition");
  if (upstream.ok && disposition) out["content-disposition"] = disposition;
  return new NextResponse(await upstream.arrayBuffer(), { status: upstream.status, headers: out });
}

async function forward(request: NextRequest, ctx: RouteContext<"/api/comisiones/[[...path]]">) {
  const { path } = await ctx.params;
  const route = (path ?? []).join("/");
  if (request.method === "GET" && route === "modelo-excel") return binario(request, "modelo-excel");
  const length = Number(request.headers.get("content-length") ?? 0);
  if (length > MAX_BODY) return jsonError(413, "TOO_LARGE", "La solicitud es demasiado grande.");
  if (request.method === "POST" && route === "periodo/excel") {
    const body = await request.text();
    return binario(request, "periodo/excel", body.length <= 1024 ? body : "{}");
  }
  return forwardToBackend(request, "comisiones", path, ALLOWED);
}

export { forward as GET, forward as POST };
