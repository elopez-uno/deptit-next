import { NextRequest } from "next/server";
import { forwardToBackend } from "@/lib/backend-proxy";

// Proxy del módulo Períodos. Solo las operaciones migradas; cualquier otra ruta -> 404.
const ALLOWED = {
  "": ["GET"],
  "apertura-excepcional": ["POST"],
  "volver-actual": ["POST"],
  // E4-10..E4-12 (ciclo de períodos, una transacción por operación)
  "crear/contexto": ["POST"],
  crear: ["POST"],
  "revertir/diagnostico": ["POST"],
  revertir: ["POST"],
  "eliminar/diagnostico": ["POST"],
  eliminar: ["POST"],
  // E4-12 / P-12b: "♻️ Reparar finalizaciones automáticas del período abierto"
  "reparar-finalizaciones/diagnostico": ["POST"],
  "reparar-finalizaciones": ["POST"],
} as const;

async function forward(
  request: NextRequest,
  ctx: RouteContext<"/api/periodos/[[...path]]">
) {
  const { path } = await ctx.params;
  return forwardToBackend(request, "periodos", path, ALLOWED);
}

export { forward as GET, forward as POST };
