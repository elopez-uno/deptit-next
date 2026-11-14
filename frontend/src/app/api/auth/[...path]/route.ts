import { NextRequest, NextResponse } from "next/server";
import { backendUrl, CLIENT_IP_HEADER, clientIp, sameOrigin } from "@/lib/backend-proxy";

// Proxy de autenticación Browser -> Next.js -> FastAPI.
// Solo rutas y métodos permitidos; la cookie HttpOnly viaja sin que el JavaScript del navegador la vea.
const ALLOWED: Record<string, readonly string[]> = {
  login: ["POST"],
  logout: ["POST"],
  me: ["GET"],
  context: ["PUT"],
  "context/options": ["GET"],
};

async function forward(
  request: NextRequest,
  ctx: RouteContext<"/api/auth/[...path]">
) {
  const { path } = await ctx.params;
  const route = path.join("/");
  const method = request.method;

  if (!ALLOWED[route]?.includes(method)) {
    return NextResponse.json(
      { error: { code: "NOT_FOUND", message: "Ruta no disponible." } },
      { status: 404 }
    );
  }
  if (method !== "GET" && !sameOrigin(request)) {
    return NextResponse.json(
      { error: { code: "CSRF", message: "Solicitud rechazada." } },
      { status: 403 }
    );
  }

  const headers: Record<string, string> = { accept: "application/json" };
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  if (method !== "GET") {
    headers["content-type"] = "application/json";
    headers["x-deptit-request"] = "1";
  }
  // 6A-B1: límite de login por origen; solo con un reverse proxy confiable delante (ver lib/backend-proxy.ts).
  const ip = route === "login" ? clientIp(request) : null;
  if (ip) headers[CLIENT_IP_HEADER] = ip;

  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/auth/${route}`, {
      method,
      headers,
      body: method === "GET" ? undefined : await request.text(),
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

export { forward as GET, forward as POST, forward as PUT };
