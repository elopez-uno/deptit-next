// Tipos y llamadas del módulo Inicio al proxy /api/inicio. El tablero llega ya calculado por el motor certificado del
// backend (sin parámetros: departamento y período salen de la sesión). La única descarga es el Excel de "Próximos
// vencimientos" (D-AN6), binaria y generada en el backend.
import { ApiError, type Named } from "@/lib/auth";
import type { Metrica, Tabla, VegaSpec } from "@/lib/analisis";

export type Boton = { label: string; destino: string; primario: boolean };
export type Casos = { tabla: Tabla | null; caption: string };
export type Lista = {
  titulo: string;
  vacio: string | null;
  personas: { encabezado: string; designaciones: { linea: string; funciones: string | null; caption: string }[] }[];
};
export type Grafico = { titulo: string; vacio: boolean; mensaje: string | null; spec: VegaSpec | null; caption: string };
export type Ayuda = { titulo: string; abierto: boolean; texto: string };

export type Tablero = {
  periodo: {
    linea: string;
    historico: boolean;
    progreso: number | null;
    caption_progreso: string | null;
    actualizar: { label: string; caption: string };
  };
  error: string | null;
  situacion?: { titulo: string; tarjetas: Metrica[]; caption_dotacion: string; listas: Lista[] };
  acciones?: {
    titulo: string;
    vacio: string | null;
    items: { icono: string; titulo: string; detalle: string; expander: string; casos: Casos; boton: Boton }[];
  };
  salud?: {
    titulo: string;
    caption: string;
    controles: { titulo: string; casos: Casos }[];
    estado_general: string;
    porcentaje: number;
    caption_indice: string;
    boton: Boton;
  };
  indicadores?: { titulo: string; filas: Metrica[][] };
  graficos?: Grafico[];
  vencimientos?: { titulo: string; vacio: string | null; tabla: Tabla | null; excel: boolean; boton: Boton | null };
  ayuda?: Ayuda;
};

export type Inicio = {
  contexto: { institucion: Named | null; departamento: Named | null };
  titulo: string;
} & (
  | { estado: "institucional"; institucional: { mensaje: string; boton: Boton } }
  | { estado: "sin_periodo"; sin_periodo: { mensaje: string; boton: Boton; ayuda: Ayuda } }
  | { estado: "tablero"; tablero: Tablero }
);

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

export class InicioError extends ApiError {
  constructor(status: number, code: string, message: string, public tone: "error" | "warning" | "info" = "error") {
    super(status, code, message);
  }
}

export type Archivo = { blob: Blob; nombre: string };

export const inicioApi = {
  async tablero(): Promise<Inicio> {
    let response: Response;
    try {
      response = await fetch("/api/inicio", { cache: "no-store", credentials: "same-origin" });
    } catch {
      throw new InicioError(0, "NETWORK", UNREACHABLE);
    }
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new InicioError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE, data?.error?.tone ?? "error");
    }
    return data as Inicio;
  },

  // Excel de las filas visibles de "Próximos vencimientos" (mismo nombre que fija el backend en Content-Disposition).
  async excelVencimientos(): Promise<Archivo> {
    let response: Response;
    try {
      response = await fetch("/api/inicio/descargas/vencimientos", {
        method: "POST",
        cache: "no-store",
        credentials: "same-origin",
        headers: { "content-type": "application/json" },
        body: "{}",
      });
    } catch {
      throw new InicioError(0, "NETWORK", UNREACHABLE);
    }
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new InicioError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE, data?.error?.tone ?? "error");
    }
    const disposition = response.headers.get("content-disposition") ?? "";
    const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
    const ascii = /filename="([^"]+)"/i.exec(disposition);
    const nombre = utf8 ? decodeURIComponent(utf8[1]) : ascii ? ascii[1] : "Inicio.xlsx";
    return { blob: await response.blob(), nombre };
  },
};
