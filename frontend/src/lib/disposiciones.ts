// Tipos y llamadas del módulo Disposiciones al proxy /api/disposiciones. El ámbito lo decide la sesión en el backend;
// FastAPI vuelve a autorizar cada escritura y sirve el Word y los ZIP (nunca hay rutas físicas ni enlaces file://).
import { ApiError, type Named } from "@/lib/auth";

export type Fila = Record<string, string | number | boolean | null>;
export type Tono = "success" | "warning" | "error" | "info";
export type Plantilla = { status: string; message?: string; actualizada?: string; sha256_12?: string; bytes?: number; code?: string };

export type Overview = {
  contexto: { institucion: Named; departamento: Named };
  periodos: { id: number; nombre: string | null }[];
  periodo_defecto: number | null;
  configuracion: Record<string, string>;
  huella_configuracion: string;
  rol: string | null;
  permisos: { puede_escribir: boolean; puede_borrar: boolean; puede_plantilla: boolean };
  info: string;
  campos: { clave: string; etiqueta: string }[];
  opciones_genero: string[];
  estados: string[];
  tipo_defecto: string;
  plantilla: Plantilla;
  textos: { config: string; acto: string; genero: string; sin_periodos: string };
};

export type Habilitado = {
  numero_disposicion_auto: number;
  nombre_completo: string | null;
  cuil: string;
  legajo: string | null;
  titulo: string | null;
  estado: string | null;
  email: string | null;
  huella: string;
};

export type PeriodoData = {
  numero_inicial: number;
  habilitados: Habilitado[];
  huella_padron: string;
  aviso: string;
  caption: string;
  caption_validacion: string;
  plantilla: Plantilla;
};

export type Designacion = {
  designacion_id: number | null;
  departamento: string;
  tipo: string;
  cargo: string;
  dedicacion: string;
  horas: number | string;
  horas_texto: string;
  condicion: string;
  funcion: string;
  funciones_no_docentes: string;
  texto_funcion_limpio: string;
  resolucion: string;
  fecha_desde: string;
  fecha_hasta: string;
  observaciones: string;
};

export type Vista = {
  cuil: string;
  numero: string;
  huella: string;
  huella_designaciones: string;
  estado_consulta: { tono: Tono; icono: string; estado: string };
  docente: string;
  cargo: string;
  dedicacion: string;
  departamentos_revistara: string;
  asignaturas: string;
  escuelas: string;
  tiene_concursado: boolean;
  tiene_interino: boolean;
  tiene_investigacion_o_extension: boolean;
  tiene_actividades_especiales: boolean;
  designaciones: Designacion[];
  es_no_docente: boolean;
  es_mixta: boolean;
  tiene_no_docente: boolean;
  texto_funcion_no_docente: string;
  promover_ie_art1: boolean;
  observaciones_generales: string;
  texto_investigacion: string;
  rol_investigacion: string;
  proyecto_investigacion: string;
  proyecto_extension: string;
  codigo_investigacion: string;
  instituto_investigacion: string;
  area_extension: string;
  texto_actividades_especiales: string;
  ambito: string;
  considerandos: string[];
  aviso_incompletas: string;
};

export type VistaPrevia = { considerandos: string[]; aviso_incompletas: string };

export type HistorialFila = {
  id: number;
  periodo: string | null;
  numero: string | null;
  docente: string | null;
  cuil: string | null;
  fecha: string | null;
  tipo: string | null;
  estado: string | null;
  observaciones: string | null;
  huella: string;
  documento: { disponible: boolean; mensaje: string; legado: boolean };
};

export type Historial = {
  filas: HistorialFila[];
  mensaje: string;
  zip: { cantidad: number; total: number; error?: string; aviso?: string; detalle?: string };
  permisos: Overview["permisos"];
  texto_seleccion?: string;
};

export type WriteResult = { mensaje: string; tono: Tono; plantilla?: Plantilla; id?: number; file_name?: string };

export type MasivaResult = {
  tono: Tono;
  mensaje: string;
  tabla: Record<string, string>[];
  generadas: number;
  ids: number[];
  errores: Record<string, string>[];
  aviso?: string;
  zip_nombre?: string;
};

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

export class DisposicionesError extends ApiError {
  constructor(status: number, code: string, message: string, public tone: "error" | "warning" | "info" = "error") {
    super(status, code, message);
  }
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`/api/disposiciones${path}`, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new DisposicionesError(0, "NETWORK", UNREACHABLE);
  }
}

async function fail(response: Response): Promise<never> {
  const data = await response.json().catch(() => null);
  throw new DisposicionesError(
    response.status,
    data?.error?.code ?? "ERROR",
    data?.error?.message ?? UNREACHABLE,
    data?.error?.tone ?? "error"
  );
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await request(path, init);
  if (!response.ok) return fail(response);
  return (await response.json()) as T;
}

export const post = <T,>(path: string, body: unknown) => call<T>(`/${path}`, { method: "POST", body: JSON.stringify(body) });

// Nombre del archivo desde Content-Disposition (filename* UTF-8 primero).
export function nombreArchivo(disposition: string, fallback: string): string {
  const ext = /filename\*=UTF-8''([^;]+)/i.exec(disposition)?.[1];
  if (ext) {
    try {
      return decodeURIComponent(ext);
    } catch {
      /* se usa el nombre ASCII */
    }
  }
  return /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallback;
}

// Word / ZIP servidos por FastAPI (POST con el id o el filtro; nunca rutas).
export async function archivo(path: string, body: unknown, fallback: string): Promise<{ blob: Blob; nombre: string }> {
  const response = await request(`/${path}`, { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) return fail(response);
  return { blob: await response.blob(), nombre: nombreArchivo(response.headers.get("content-disposition") ?? "", fallback) };
}

export function descargar(file: { blob: Blob; nombre: string }) {
  const url = URL.createObjectURL(file.blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = file.nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Lectura de la plantilla elegida en base64 (viaja dentro del JSON, como las cargas Excel de otros módulos).
export function leerBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new DisposicionesError(0, "FILE", "No se pudo leer el archivo seleccionado."));
    reader.onload = () => {
      const url = String(reader.result ?? "");
      resolve(url.slice(url.indexOf(",") + 1)); // "data:<mime>;base64,<contenido>"
    };
    reader.readAsDataURL(file);
  });
}

export const MAX_PLANTILLA_BYTES = 20 * 1024 * 1024;

export const disposicionesApi = {
  overview: () => call<Overview>(""),
};
