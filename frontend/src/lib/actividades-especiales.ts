// Tipos y llamadas del módulo Actividades Especiales al proxy /api/actividades-especiales. El ámbito lo decide la
// sesión en el backend; FastAPI vuelve a autorizar cada escritura.
import { ApiError, type Named } from "@/lib/auth";

export type Periodo = {
  id: number;
  nombre: string | null;
  anio: number | null;
  semestre: number | null;
  fecha_inicio: string | null;
  fecha_fin: string | null;
  estado: string | null;
};

export type Fila = Record<string, string | number | boolean | null>;
export type FilaHuella = Fila & { id: number; huella: string };

export type Overview = {
  contexto: { institucion: Named; departamento: Named };
  periodos: Periodo[];
  abierto: Periodo | null;
  huella_periodos: string;
  rol: string | null;
  permisos: { puede_escribir: boolean; puede_borrar: boolean };
  estados: string[];
  info: string;
};

export type OpcionDocente = { etiqueta: string; cuil: string };

export type WriteResult = { mensaje: string; tono: "success" | "warning" | "info"; avisos?: string[] };

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

export class ActividadesError extends ApiError {
  constructor(status: number, code: string, message: string, public tone: "error" | "warning" | "info" = "error") {
    super(status, code, message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/actividades-especiales${path}`, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ActividadesError(0, "NETWORK", UNREACHABLE);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ActividadesError(
      response.status,
      data?.error?.code ?? "ERROR",
      data?.error?.message ?? UNREACHABLE,
      data?.error?.tone ?? "error"
    );
  }
  return data as T;
}

export const post = <T,>(path: string, body: unknown) => call<T>(`/${path}`, { method: "POST", body: JSON.stringify(body) });

export const actividadesApi = {
  overview: () => call<Overview>(""),
};
