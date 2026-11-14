import { NextRequest } from "next/server";
import { forwardToBackend } from "@/lib/backend-proxy";

// Proxy del módulo Movimientos. Solo las operaciones migradas; cualquier otra ruta -> 404.
// Las consultas con parámetros viajan por POST (el proxy nunca reenvía query strings). No hay Excel, CSV ni archivos.
const POST = ["POST"] as const;
const ALLOWED = {
  "": ["GET"],
  listado: POST,
  actos: POST,
  eliminar: POST,
  "actos/vincular": POST,
  "actos/desvincular": POST,
} as const;

async function forward(request: NextRequest, ctx: RouteContext<"/api/movimientos/[[...path]]">) {
  const { path } = await ctx.params;
  return forwardToBackend(request, "movimientos", path, ALLOWED);
}

export { forward as GET, forward as POST };
