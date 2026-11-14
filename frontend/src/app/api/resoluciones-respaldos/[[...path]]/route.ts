import { NextRequest, NextResponse } from "next/server";
import { backendUrl, conLimite, Excedido, forwardToBackend, jsonError, sameOrigin } from "@/lib/backend-proxy";

// Proxy del módulo Resoluciones y respaldos. Solo las operaciones migradas; cualquier otra ruta -> 404 (no hay ZIP,
// Excel, importación, exportación, edición de número/fecha/tipo ni borrado del PDF o de dependencias).
// - JSON (lecturas por POST y escrituras sin archivo): el helper común (allowlist, mismo origen, cookie, X-DEPTIT-Request).
// - PDF (D-AK1): multipart/form-data reenviado en streaming con su boundary, SIN base64 y con límite propio del cuerpo
//   (50 MiB de PDF + margen del multipart). FastAPI vuelve a validar el tamaño real y la firma %PDF-.
// - Descarga (D-AK3/D-AK12): binario application/pdf que FastAPI sirve tras reautorizar; nunca hay rutas físicas.
const POST = ["POST"] as const;
const ALLOWED = {
  "": ["GET"],
  documento: POST,
  docentes: POST,
  proyectos: POST,
  designaciones: POST, // 6A-B3: designaciones concretas de los docentes elegidos (lectura)
  "documento/designaciones": POST, // 6A-B3: vínculo acto <-> designaciones por id real (escritura)
  "documento/docentes": POST, // 6A-B3: agregar docentes a un acto ya cargado (escritura)
  "documento/proyectos": POST, // 6A-B3: proyectos de un acto de Investigación / Extensión (escritura)
  "documento/dependencia": POST,
  "documento/eliminar": POST,
  "dependencias/agregar": POST,
  "dependencias/editar": POST,
} as const;
const MULTIPART = new Set(["actos/guardar", "documento/adjuntar-pdf"]);
const DESCARGA = "documento/pdf";

const MAX_PDF = 50 * 1024 * 1024;
const MAX_MULTIPART = MAX_PDF + 1024 * 1024;
const MSG_GRANDE = "La solicitud es demasiado grande: el PDF no puede superar 50 MB.";

// Mismo criterio que lib/backend-proxy.ts (escrituras y consultas POST solo desde el mismo origen).

function headersBase(request: NextRequest, contentType: string): Record<string, string> {
  const headers: Record<string, string> = { "content-type": contentType, "x-deptit-request": "1" };
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  return headers;
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
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/resoluciones-respaldos/${path}`, {
      method: "POST",
      headers: headersBase(request, contentType), // boundary original intacto
      body: conLimite(request.body, MAX_MULTIPART),
      // @ts-expect-error -- Node fetch (undici) exige duplex para cuerpos en streaming
      duplex: "half",
      cache: "no-store",
      redirect: "manual",
    });
  } catch (err) {
    if (err instanceof Excedido || (err as { cause?: unknown })?.cause instanceof Excedido) {
      return jsonError(413, "TOO_LARGE", MSG_GRANDE);
    }
    return jsonError(503, "BACKEND_UNREACHABLE", "No se pudo conectar con el servidor. Reintentá en unos instantes.");
  }
  return new NextResponse(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") ?? "application/json", "cache-control": "no-store" },
  });
}

async function descarga(request: NextRequest) {
  if (!sameOrigin(request)) return jsonError(403, "CSRF", "Solicitud rechazada.");
  const body = await request.text();
  if (body.length > 4 * 1024) return jsonError(413, "TOO_LARGE", "La solicitud es demasiado grande.");
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/resoluciones-respaldos/${DESCARGA}`, {
      method: "POST",
      headers: headersBase(request, "application/json"),
      body,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return jsonError(503, "BACKEND_UNREACHABLE", "No se pudo conectar con el servidor. Reintentá en unos instantes.");
  }
  const out: Record<string, string> = {
    "content-type": upstream.ok ? "application/pdf" : upstream.headers.get("content-type") ?? "application/json",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  };
  const disposition = upstream.headers.get("content-disposition");
  if (upstream.ok && disposition) out["content-disposition"] = disposition;
  return new NextResponse(upstream.body, { status: upstream.status, headers: out });
}

async function forward(request: NextRequest, ctx: RouteContext<"/api/resoluciones-respaldos/[[...path]]">) {
  const { path } = await ctx.params;
  const route = (path ?? []).join("/");
  if (request.method === "POST" && MULTIPART.has(route)) return multipart(request, route);
  if (request.method === "POST" && route === DESCARGA) return descarga(request);
  const length = Number(request.headers.get("content-length") ?? 0);
  if (length > 256 * 1024) return jsonError(413, "TOO_LARGE", "La solicitud es demasiado grande.");
  return forwardToBackend(request, "resoluciones-respaldos", path, ALLOWED);
}

export { forward as GET, forward as POST };
