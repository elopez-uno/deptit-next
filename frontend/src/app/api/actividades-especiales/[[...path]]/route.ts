import { NextRequest } from "next/server";
import { forwardToBackend } from "@/lib/backend-proxy";

// Proxy del módulo Actividades Especiales. Solo las operaciones migradas; cualquier otra ruta -> 404.
// Las consultas con parámetros viajan por POST (el proxy nunca reenvía query strings). No hay Excel ni archivos.
const POST = ["POST"] as const;
const ALLOWED = {
  "": ["GET"],
  periodo: POST,
  "asignar/datos": POST,
  historial: POST,
  "editar/actividades": POST,
  "editar/participaciones": POST,
  crear: POST,
  asignar: POST,
  editar: POST,
  "editar/quitar-participacion": POST,
  "editar/eliminar": POST,
} as const;

async function forward(request: NextRequest, ctx: RouteContext<"/api/actividades-especiales/[[...path]]">) {
  const { path } = await ctx.params;
  return forwardToBackend(request, "actividades-especiales", path, ALLOWED);
}

export { forward as GET, forward as POST };
