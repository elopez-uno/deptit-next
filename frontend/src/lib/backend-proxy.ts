import { NextRequest, NextResponse } from "next/server";

// Reenvío Browser -> Next.js -> FastAPI para los módulos (mismo contrato que el proxy de /api/auth):
// allowlist de rutas y métodos, mismo origen en escrituras, cabecera X-DEPTIT-Request y cookie HttpOnly
// reenviada sin exponerla al JavaScript del navegador.  Etapa 5 / Tanda C (C7): ``sameOrigin`` (control CSRF),
// ``jsonError``, ``backendUrl`` y ``conLimite`` son la UNICA copia; los proxies con rutas propias los importan.
//// reenviada sin exponerla al JavaScript del navegador.
export type Allowlist = Record<string, readonly string[]>;

// DEPTIT_BACKEND_URL es server-only (nunca una variable pública del bundle): el navegador no conoce ni alcanza FastAPI.
export const backendUrl = () =>
  process.env.DEPTIT_BACKEND_URL ?? "http://127.0.0.1:8001";

// 6A-B1: origen del cliente para el límite de login por IP. Next 16 conserva el X-Forwarded-For que mande el cliente
// (`??=`), así que SOLO se usa cuando hay un reverse proxy propio delante (DEPTIT_TRUSTED_PROXY_HOPS >= 1) que agrega
// o sobrescribe ese encabezado: se toma la entrada que agregó el proxy confiable (contando desde la derecha). Sin
// proxy (0, por defecto) no se envía nada y FastAPI aplica solo el límite por cuenta. El encabezado hacia FastAPI se
// construye desde cero: el x-deptit-client-ip que mande el navegador nunca se reenvía.
export const CLIENT_IP_HEADER = "x-deptit-client-ip";

export function trustedProxyHops(): number {
  const raw = (process.env.DEPTIT_TRUSTED_PROXY_HOPS ?? "0").trim();
  const n = /^\d+$/.test(raw) ? Number(raw) : 0;
  return n >= 0 && n <= 5 ? n : 0;
}

const IPV4 = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/;
const IPV6 = /^[0-9a-fA-F:.]{2,45}$/;

export function clientIp(request: NextRequest, hops = trustedProxyHops()): string | null {
  if (hops < 1) return null;
  const xff = (request.headers.get("x-forwarded-for") ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (xff.length < hops) return null;
  const ip = xff[xff.length - hops];
  return IPV4.test(ip) || (ip.includes(":") && IPV6.test(ip)) ? ip : null;
}

export function sameOrigin(request: NextRequest): boolean {
  const fetchSite = request.headers.get("sec-fetch-site");
  if (fetchSite && fetchSite !== "same-origin") return false;
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host) return false;
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export function jsonError(status: number, code: string, message: string) {
  return NextResponse.json(
    { error: { code, message } },
    { status, headers: { "cache-control": "no-store" } }
  );
}

// Cuerpo multipart en streaming con limite de bytes reales (corta apenas se supera, sin bufferizar todo).
export class Excedido extends Error {}

export function conLimite(body: ReadableStream<Uint8Array>, max: number): ReadableStream<Uint8Array> {
  let total = 0;
  return body.pipeThrough(
    new TransformStream<Uint8Array, Uint8Array>({
      transform(chunk, controller) {
        total += chunk.byteLength;
        if (total > max) {
          controller.error(new Excedido());
          return;
        }
        controller.enqueue(chunk);
      },
    })
  );
}

export async function forwardToBackend(
  request: NextRequest,
  prefix: string,
  segments: string[] | undefined,
  allowed: Allowlist
) {
  const route = (segments ?? []).join("/");
  const method = request.method;

  if (!allowed[route]?.includes(method)) {
    return jsonError(404, "NOT_FOUND", "Ruta no disponible.");
  }
  if (method !== "GET" && !sameOrigin(request)) {
    return jsonError(403, "CSRF", "Solicitud rechazada.");
  }

  const headers: Record<string, string> = { accept: "application/json" };
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  if (method !== "GET") {
    headers["content-type"] = "application/json";
    headers["x-deptit-request"] = "1";
  }

  let upstream: Response;
  try {
    // Sin query string: el ámbito lo decide siempre la sesión en el backend.
    upstream = await fetch(`${backendUrl()}/${prefix}${route ? `/${route}` : ""}`, {
      method,
      headers,
      body: method === "GET" ? undefined : await request.text(),
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return jsonError(
      503,
      "BACKEND_UNREACHABLE",
      "No se pudo conectar con el servidor. Reintentá en unos instantes."
    );
  }

  const response = new NextResponse(
    upstream.status === 204 ? null : await upstream.text(),
    {
      status: upstream.status,
      headers: {
        "content-type":
          upstream.headers.get("content-type") ?? "application/json",
        "cache-control": "no-store",
      },
    }
  );
  for (const setCookie of upstream.headers.getSetCookie()) {
    response.headers.append("set-cookie", setCookie);
  }
  return response;
}
