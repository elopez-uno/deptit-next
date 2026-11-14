// Tipos y llamadas del módulo Consolidado institucional al proxy /api/consolidado. La institución sale siempre de la
// sesión (nunca se envía). La lectura inicial trae KPIs, control de consistencia, resumen y el catálogo de tablas; cada
// tabla del visor se pide al elegirla (clave de la lista fija + texto de búsqueda, D-AO3). Descargas binarias generadas
// en el backend: CSV de la tabla COMPLETA y Excel de la tabla mostrada (vista filtrada, D-AO4).
import { ApiError, type Named } from "@/lib/auth";
import type { Metrica, Tabla } from "@/lib/analisis";

export type Visor = {
  titulo: string;
  label: string;
  opciones: string[];
  default: string;
  buscador: { label: string; placeholder: string; help: string };
  csv: string;
};

export type Consolidado = { titulo: string; contexto: { institucion: Named | null } } & (
  | { estado: "sin_datos"; mensaje: string }
  | {
      estado: "tablero";
      metricas: Metrica[];
      caption: string;
      control: { titulo: string; abierto: boolean; metricas: Metrica[]; caption: string };
      resumen: { titulo: string; tabla: Tabla; excel: boolean };
      visor: Visor;
    }
);

export type TablaVisor =
  | { tabla: string; vacio: true; mensaje: string }
  | {
      tabla: string;
      vacio: false;
      busqueda: string;
      total: number;
      encontrados: number;
      caption: string | null;
      sin_coincidencias: string | null;
      datos: Tabla | null;
      excel: boolean;
    };

export type Archivo = { blob: Blob; nombre: string };

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

export class ConsolidadoError extends ApiError {
  constructor(status: number, code: string, message: string, public tone: "error" | "warning" | "info" = "error") {
    super(status, code, message);
  }
}

async function pedir(url: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(url, { cache: "no-store", credentials: "same-origin", ...init });
  } catch {
    throw new ConsolidadoError(0, "NETWORK", UNREACHABLE);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ConsolidadoError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE, data?.error?.tone ?? "error");
  }
  return response;
}

const post = (body: Record<string, unknown>): RequestInit => ({
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

async function archivo(response: Response, defecto: string): Promise<Archivo> {
  const disposition = response.headers.get("content-disposition") ?? "";
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  const ascii = /filename="([^"]+)"/i.exec(disposition);
  const nombre = utf8 ? decodeURIComponent(utf8[1]) : ascii ? ascii[1] : defecto;
  return { blob: await response.blob(), nombre };
}

export const consolidadoApi = {
  async overview(): Promise<Consolidado> {
    return (await pedir("/api/consolidado")).json();
  },
  async tabla(tabla: string, buscar: string): Promise<TablaVisor> {
    return (await pedir("/api/consolidado/tabla", post({ tabla, buscar }))).json();
  },
  async csv(tabla: string): Promise<Archivo> {
    return archivo(await pedir("/api/consolidado/descargas/csv", post({ tabla })), `${tabla}_consolidado.csv`);
  },
  // "resumen" = tabla "Resumen por departamento"; cualquier otra clave = la tabla del visor con su búsqueda actual.
  async excel(tabla: string, buscar: string | null): Promise<Archivo> {
    const body = tabla === "resumen" ? { tabla } : { tabla, buscar: buscar ?? "" };
    return archivo(await pedir("/api/consolidado/descargas/excel", post(body)), "Consolidado_institucional.xlsx");
  },
};
