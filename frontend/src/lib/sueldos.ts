// Tipos y llamadas del módulo Sueldos al proxy /api/sueldos. El ámbito (institución y departamento) lo decide la
// sesión en el backend; FastAPI vuelve a autorizar cada escritura.
import { ApiError, type Named } from "@/lib/auth";

export type Fila = Record<string, string | number | boolean | null>;

export type Overview = {
  contexto: { institucion: Named; departamento: Named | null };
  rol: string | null;
  permisos: { puede_escribir: boolean };
  ayuda_sin_permiso: string | null;
  info: string;
  hoy: { anio: number; mes: number };
  meses: string[];
  cargos: string[];
  dedicaciones: string[];
  niveles: string[];
  textos: { caption_escalas: string; ayuda_dedicacion: string; antiguedad: string; posgrado: string; caption_plantel: string };
  plantel: {
    disponible: boolean;
    mensaje?: string;
    periodos?: { nombre: string; id: number }[];
    periodo_defecto?: string | null;
  };
};

export type Escalas = {
  mes_referencia: string;
  etiqueta: string;
  valores: Record<string, number>;
  historico: Fila[];
  mensaje_historico: string | null;
};

export type Tabla =
  | { meses: []; mensaje: string }
  | {
      meses: { valor: string; etiqueta: string }[];
      mes: string;
      dedicacion: string;
      nivel: string;
      caption: string;
      filas: Fila[];
    };

export type Plantel = {
  estado: "ok" | "sin_periodos" | "sin_escala" | "sin_designaciones" | "vacio";
  mensaje?: string;
  tono?: "info" | "warning";
  caption_escala?: string;
  metricas?: { docentes: number; designaciones: number; total: string };
  filas?: Fila[];
  caption?: string;
};

export type WriteResult = { mensaje: string; tono: "success" | "warning" | "info" };

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

export class SueldosError extends ApiError {
  constructor(status: number, code: string, message: string, public tone: "error" | "warning" | "info" = "error") {
    super(status, code, message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/sueldos${path}`, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new SueldosError(0, "NETWORK", UNREACHABLE);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new SueldosError(
      response.status,
      data?.error?.code ?? "ERROR",
      data?.error?.message ?? UNREACHABLE,
      data?.error?.tone ?? "error"
    );
  }
  return data as T;
}

export const post = <T,>(path: string, body: unknown) => call<T>(`/${path}`, { method: "POST", body: JSON.stringify(body) });

export const sueldosApi = {
  overview: () => call<Overview>(""),
};
