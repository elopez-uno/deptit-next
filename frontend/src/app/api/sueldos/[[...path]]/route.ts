import { NextRequest } from "next/server";
import { forwardToBackend } from "@/lib/backend-proxy";

// Proxy del módulo Sueldos. Solo las operaciones migradas; cualquier otra ruta -> 404.
// Las consultas con parámetros viajan por POST (el proxy nunca reenvía query strings). No hay Excel, importación,
// exportación ni eliminación de escalas (no existen en el certificado).
const POST = ["POST"] as const;
const ALLOWED = {
  "": ["GET"],
  escalas: POST,
  tabla: POST,
  plantel: POST,
  "escalas/guardar": POST,
} as const;

async function forward(request: NextRequest, ctx: RouteContext<"/api/sueldos/[[...path]]">) {
  const { path } = await ctx.params;
  return forwardToBackend(request, "sueldos", path, ALLOWED);
}

export { forward as GET, forward as POST };
