// Tipos y llamadas del módulo Movimientos al proxy /api/movimientos. El ámbito lo decide la sesión en el backend;
// FastAPI vuelve a autorizar cada escritura.
import { ApiError, type Named } from "@/lib/auth";

// Fila de la tabla certificada (8 columnas visibles + id, acto vinculado y huella de la capa U). Nunca columnas legacy.
export type FilaMovimiento = {
  id: number;
  periodo: string | null;
  fecha: string | null;
  tipo_movimiento: string | null;
  nombre: string | null;
  cuil: string | null;
  detalle: string | null;
  acto_administrativo: string | null;
  observaciones: string | null;
  acto_documento_id: number | null;
  huella: string;
};

export type Overview = {
  contexto: { institucion: Named; departamento: Named };
  periodos: string[]; // opciones del selector ("Todos los períodos" + nombres); vacío = sin selector
  periodo: string | null;
  filas: FilaMovimiento[];
  tipos_con_acto: string[];
  permisos: { puede_eliminar: boolean; puede_vincular: boolean; puede_desvincular: boolean };
};

export type Listado = { periodo: string | null; filas: FilaMovimiento[] };

export type Documento = {
  id: number;
  fecha: string | null;
  tipo_documento: string | null;
  numero: string | null;
  dependencia_emisora: string | null;
  categoria: string | null;
  titulo: string | null;
  detalle: string | null;
  periodo: string | null;
  etiqueta: string;
};

export type WriteResult = { mensaje: string; tono: "success" | "warning" | "info" };

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

export class MovimientosError extends ApiError {
  constructor(status: number, code: string, message: string, public tone: "error" | "warning" | "info" = "error") {
    super(status, code, message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/movimientos${path}`, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new MovimientosError(0, "NETWORK", UNREACHABLE);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new MovimientosError(
      response.status,
      data?.error?.code ?? "ERROR",
      data?.error?.message ?? UNREACHABLE,
      data?.error?.tone ?? "error"
    );
  }
  return data as T;
}

export const post = <T,>(path: string, body: unknown) => call<T>(`/${path}`, { method: "POST", body: JSON.stringify(body) });

export const movimientosApi = {
  overview: () => call<Overview>(""),
  listado: (periodo: string | null) => post<Listado>("listado", { periodo }),
  actos: () => post<{ documentos: Documento[] }>("actos", {}),
};
