// Tipos y llamadas del módulo Análisis (incluye Productividad) al proxy /api/analisis. El ámbito lo decide la sesión
// en el backend; FastAPI vuelve a autorizar cada escritura. Las descargas son binarias (Word, CSV, TXT) y nunca se
// generan en el navegador: se piden al backend con los mismos filtros visibles.
import { ApiError, type Named } from "@/lib/auth";

export type Celda = string | number | boolean | null;
export type Tabla = { columnas: string[]; filas: Celda[][] };
export type Metrica = { label: string; valor: string; delta: string | null; delta_color: "normal" | "inverse" | "off"; caption: string | null };
export type VegaSpec = Record<string, unknown>;
export type Torta = { titulo: string | null; vacio: boolean; mensaje: string | null; spec: VegaSpec | null };
export type Conteo = { tabla: Tabla; torta: Torta };

export type Overview = {
  contexto: { institucion: Named; departamento: Named };
  titulo: string;
  info: string;
  tabs: string[];
  subtabs_comparacion: string[];
  vacio: boolean;
  mensaje_sin_periodos: string;
  periodos: string[];
  periodo: string | null;
  parametro: { valor: number; texto: string; huella: string; caption: string; ayuda: string };
  comparacion: { actual: { id: number; nombre: string } | null; opciones?: string[]; default?: string[] } | null;
  permisos: { puede_guardar: boolean };
  leyenda_semaforo: string;
};

export type Seccion = {
  metricas: Metrica[];
  horas?: Metrica;
  vacio?: string;
  caption?: string;
  cargos?: Conteo;
  dedicaciones?: Conteo;
  tipos?: Conteo;
  titulo_tabla?: string;
  tabla?: Tabla;
};

export type FilaProductividad = { celdas: Celda[]; color: "rojo" | "amarillo" | "verde" | "azul" | ""; diagnostico: string | null };

export type Periodo = {
  periodo: string;
  historico: boolean;
  info_historico: string | null;
  dashboard: {
    subtitulo: string;
    dotacion: Metrica[];
    caption_dotacion: string;
    operacion: Metrica[];
    grupos: Tabla | null;
    horas: Metrica[];
    caption_horas: string;
    torta_horas: Torta;
    torta_comisiones: Torta;
    resumen: Tabla;
  };
  plantel: { subtitulo: string; caption: string; a: Seccion; b: Seccion; c: Seccion };
  movimiento: {
    subtitulo: string;
    vacio?: string;
    unitario?: Metrica[];
    balance?: Metrica[];
    caption_balance?: string;
    indicadores?: Record<string, { caption: string; vacio: string | null; tabla: Tabla | null }>;
    indicador_default?: string;
    anterior: { caption: string; tabla: Tabla } | null;
    vacio_anterior: string;
  };
  automatico: {
    subtitulo: string;
    resumen: string;
    alertas: { totales: number; por_gravedad: Record<string, number>; tabla: Tabla } | null;
    productividad: { diagnosticos: string[]; total: number; tabla: { columnas: string[]; filas: FilaProductividad[] } } | null;
    prompt: string;
  };
};

export type Comparacion =
  | { vacio: string | null }
  | {
      incluidos: string[];
      info: string;
      referencias: Record<
        string,
        {
          titulo: string;
          grupos: { titulo: string; tarjetas: Metrica[] }[];
          cobertura: { texto: string; valor: number }[];
          productividad: { texto: string; valor: number }[];
          sintesis: string;
        }
      >;
      graficos: Record<"horas" | "porcentajes" | "alumnos" | "comisiones" | "docentes", VegaSpec>;
      matriz: Tabla;
    };

export type WriteResult = { mensaje: string; tono: "success" | "warning" | "info" };

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

export class AnalisisError extends ApiError {
  constructor(status: number, code: string, message: string, public tone: "error" | "warning" | "info" = "error") {
    super(status, code, message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/analisis${path}`, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new AnalisisError(0, "NETWORK", UNREACHABLE);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new AnalisisError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE, data?.error?.tone ?? "error");
  }
  return data as T;
}

const post = <T,>(path: string, body: unknown) => call<T>(`/${path}`, { method: "POST", body: JSON.stringify(body) });

export type Archivo = { blob: Blob; nombre: string };

// Descarga binaria (POST): devuelve el contenido y el nombre que fijó el backend (Content-Disposition).
export async function descargar(ruta: "word" | "indicador" | "alertas" | "prompt", body: unknown): Promise<Archivo> {
  let response: Response;
  try {
    response = await fetch(`/api/analisis/descargas/${ruta}`, {
      method: "POST",
      cache: "no-store",
      credentials: "same-origin",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new AnalisisError(0, "NETWORK", UNREACHABLE);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new AnalisisError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE, data?.error?.tone ?? "error");
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  const ascii = /filename="([^"]+)"/i.exec(disposition);
  const nombre = utf8 ? decodeURIComponent(utf8[1]) : ascii ? ascii[1] : "descarga";
  return { blob: await response.blob(), nombre };
}

export function guardarArchivo({ blob, nombre }: Archivo) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const analisisApi = {
  overview: () => call<Overview>(""),
  periodo: (periodo: string) => post<Periodo>("periodo", { periodo }),
  comparacion: (periodos: string[]) => post<Comparacion>("comparacion", { periodos }),
  guardarPorcentaje: (porcentaje: number, huella: string) => post<WriteResult>("porcentaje", { porcentaje, huella }),
};
