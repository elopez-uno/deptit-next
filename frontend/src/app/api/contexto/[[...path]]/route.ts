import { NextRequest } from "next/server";
import { forwardToBackend } from "@/lib/backend-proxy";

// Proxy de la capa de composición de contexto (E4-01, D-AN9). Solo el aviso de contexto histórico, por GET y sin
// parámetros (el ámbito lo decide la sesión en el backend). Cualquier otra ruta o método -> 404.
const ALLOWED = { periodo: ["GET"] } as const;

async function forward(request: NextRequest, ctx: RouteContext<"/api/contexto/[[...path]]">) {
  const { path } = await ctx.params;
  return forwardToBackend(request, "contexto", path, ALLOWED);
}

export { forward as GET, forward as POST };
