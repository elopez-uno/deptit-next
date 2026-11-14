import { NextRequest, NextResponse } from "next/server";
import { backendUrl, conLimite, Excedido, forwardToBackend, jsonError, sameOrigin } from "@/lib/backend-proxy";

// Proxy del módulo Designaciones. Solo las operaciones migradas; cualquier otra ruta -> 404.
// Las consultas con parámetros viajan por POST (el proxy nunca reenvía query strings). Los dos Excel (modelo de
// carga rápida y tabla histórica) bajan por rutas binarias propias.
// E4-07 "Cargar un nuevo acto ahora": el contexto del formulario es JSON; el alta y la modificación con acto nuevo
// viajan como multipart/form-data reenviado en streaming con su boundary (sin base64), con el mismo límite que
// Resoluciones y respaldos (50 MiB de PDF + margen). FastAPI vuelve a validar tamaño real y firma %PDF-.
const POST = ["POST"] as const;
const ALLOWED = {
  "": ["GET"],
  periodo: POST,
  actos: POST,
  duplicado: POST,
  alta: POST,
  modificar: POST,
  corregir: POST,
  eliminar: POST,
  "eliminar-masivo": POST,
  fechas: POST,
  "fechas-historicas": POST,
  "actos/vincular": POST,
  "actos/desvincular": POST,
  "carga-rapida/previsualizar": POST,
  "carga-rapida": POST,
  "acto-nuevo/contexto": POST,
} as const;
const MULTIPART = new Set(["acto-nuevo/alta", "acto-nuevo/modificar"]);
const MAX_MULTIPART = 50 * 1024 * 1024 + 1024 * 1024;
const MSG_GRANDE = "La solicitud es demasiado grande: el PDF no puede superar 50 MB.";

// Límite del cuerpo JSON (texto pegado de la carga rápida + margen).
const MAX_BODY = 4 * 1024 * 1024;

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
    upstream = await fetch(`${backendUrl()}/designaciones/${path}`, {
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

async function multipart(request: NextRequest, path: string) {
  if (!sameOrigin(request)) return jsonError(403, "CSRF", "Solicitud rechazada.");
  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.toLowerCase().startsWith("multipart/form-data") || !/boundary=/i.test(contentType)) {
    return jsonError(415, "UNSUPPORTED", "La solicitud de carga del archivo no es válida.");
  }
  const declarado = Number(request.headers.get("content-length") ?? 0);
  if (declarado > MAX_MULTIPART) return jsonError(413, "TOO_LARGE", MSG_GRANDE);
  if (!request.body) return jsonError(400, "INVALID", "La solicitud de carga del archivo no es válida.");
  const headers: Record<string, string> = { "content-type": contentType, "x-deptit-request": "1" };
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/designaciones/${path}`, {
      method: "POST",
      headers,
      body: conLimite(request.body, MAX_MULTIPART),
      cache: "no-store",
      redirect: "manual",
      duplex: "half",
    } as RequestInit);
  } catch (e) {
    if (e instanceof Excedido || (e as { cause?: unknown })?.cause instanceof Excedido) {
      return jsonError(413, "TOO_LARGE", MSG_GRANDE);
    }
    return jsonError(503, "BACKEND_UNREACHABLE", "No se pudo conectar con el servidor. Reintentá en unos instantes.");
  }
  return new NextResponse(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") ?? "application/json", "cache-control": "no-store" },
  });
}

async function forward(request: NextRequest, ctx: RouteContext<"/api/designaciones/[[...path]]">) {
  const { path } = await ctx.params;
  const route = (path ?? []).join("/");
  if (MULTIPART.has(route)) {
    if (request.method !== "POST") return jsonError(405, "METHOD", "Método no permitido.");
    return multipart(request, route);
  }
  if (request.method === "GET" && route === "modelo-excel") return binario(request, "modelo-excel");
  const length = Number(request.headers.get("content-length") ?? 0);
  if (length > MAX_BODY) return jsonError(413, "TOO_LARGE", "La solicitud es demasiado grande.");
  if (request.method === "POST" && route === "periodo/excel") {
    const body = await request.text();
    return binario(request, "periodo/excel", body.length <= 1024 ? body : "{}");
  }
  return forwardToBackend(request, "designaciones", path, ALLOWED);
}

export { forward as GET, forward as POST };
