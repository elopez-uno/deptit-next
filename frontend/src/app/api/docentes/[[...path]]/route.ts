import { NextRequest, NextResponse } from "next/server";
import { backendUrl, conLimite, Excedido, forwardToBackend, jsonError, sameOrigin } from "@/lib/backend-proxy";

// Proxy del módulo Docentes. Solo las operaciones migradas; cualquier otra ruta -> 404.
// Las consultas con parámetros viajan por POST porque el proxy nunca reenvía query strings.
const ALLOWED = {
  "": ["GET"],
  prestables: ["GET"],
  ficha: ["POST"],
  plantel: ["POST"],
  equipos: ["POST"],
  resumen: ["POST"],
  "resumen/estado-consulta": ["POST"],
  "resumen/mensaje": ["POST"],
  "verificar-cuil": ["POST"],
  "designacion/contexto": ["POST"],
  "designacion/duplicado": ["POST"],
  designacion: ["POST"],
  alta: ["POST"],
  editar: ["POST"],
  eliminar: ["POST"],
  prestado: ["POST"],
  "finalizar-prestamo": ["POST"],
  "reparar-cuil": ["POST"],
  "carga-rapida/previsualizar": ["POST"],
  "carga-rapida": ["POST"],
} as const;

// E4-09 carga rápida integral: la revisión y la carga viajan como multipart/form-data reenviado en streaming con su
// boundary (sin base64, sin disco), con el mismo límite que Resoluciones y respaldos (50 MiB + margen); el modelo
// Excel baja por una ruta binaria POST. FastAPI vuelve a validar tamaño real y firma XLSX.
// 6A-B3: registrar designación con "Cargar un nuevo acto ahora" (PDF opcional), mismo transporte que E4-07.
const MULTIPART = new Set(["carga-integral/previsualizar", "carga-integral", "designacion/acto-nuevo"]);
const MAX_MULTIPART = 50 * 1024 * 1024 + 1024 * 1024;
const MSG_GRANDE = "La solicitud es demasiado grande: el archivo no puede superar 50 MB.";

// Mismo criterio que lib/backend-proxy.ts (escrituras y consultas POST solo desde el mismo origen).

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
    upstream = await fetch(`${backendUrl()}/docentes/${path}`, {
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

async function modeloIntegral(request: NextRequest) {
  if (!sameOrigin(request)) return jsonError(403, "CSRF", "Solicitud rechazada.");
  const body = await request.text();
  const headers: Record<string, string> = { "content-type": "application/json", "x-deptit-request": "1" };
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/docentes/carga-integral/modelo`, {
      method: "POST",
      headers,
      body: body.length <= 1024 ? body : "{}",
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

// Descarga binaria del modelo Excel (el reenvío JSON de forwardToBackend trabaja con texto).
async function modeloExcel(request: NextRequest) {
  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/docentes/modelo-excel`, {
      headers,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "BACKEND_UNREACHABLE",
          message: "No se pudo conectar con el servidor. Reintentá en unos instantes.",
        },
      },
      { status: 503, headers: { "cache-control": "no-store" } }
    );
  }
  const out: Record<string, string> = {
    "content-type": upstream.headers.get("content-type") ?? "application/octet-stream",
    "cache-control": "no-store",
  };
  const disposition = upstream.headers.get("content-disposition");
  if (upstream.ok && disposition) out["content-disposition"] = disposition;
  return new NextResponse(await upstream.arrayBuffer(), { status: upstream.status, headers: out });
}

async function forward(
  request: NextRequest,
  ctx: RouteContext<"/api/docentes/[[...path]]">
) {
  const { path } = await ctx.params;
  const route = (path ?? []).join("/");
  if (request.method === "GET" && route === "modelo-excel") {
    return modeloExcel(request);
  }
  if (MULTIPART.has(route)) {
    if (request.method !== "POST") return jsonError(405, "METHOD", "Método no permitido.");
    return multipart(request, route);
  }
  if (request.method === "POST" && route === "carga-integral/modelo") return modeloIntegral(request);
  return forwardToBackend(request, "docentes", path, ALLOWED);
}

export { forward as GET, forward as POST };
