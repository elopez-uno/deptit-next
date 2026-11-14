import { ApiError } from "@/lib/auth";

// Cliente del módulo Resoluciones y respaldos (Browser -> /api/resoluciones-respaldos -> FastAPI).
// El PDF viaja como multipart/form-data (FormData, sin base64; D-AK1) y se descarga bajo demanda (D-AK12).

export type Tono = "success" | "warning" | "error" | "info";

export type FilaDocumento = {
  id: number;
  fecha: string | null;
  tipo_documento: string;
  tipo_resolucion: string;
  dependencia_id: number | null;
  dependencia_emisora: string;
  categoria: string;
  numero: string;
  periodo: string;
  cantidad_docentes: number;
  docentes: string;
  cuiles: string;
  cantidad_proyectos: number;
  proyectos: string;
  proyecto_ids: string;
  referencia: string;
  titulo: string;
  detalle: string;
  observaciones: string;
  archivo_nombre: string | null;
  archivo_bytes: number;
  estado_pdf: "Adjunto" | "Pendiente";
  tamano_kb: number;
};

export type Opcion = { etiqueta: string; id: number | null };

export type Dependencia = { id: number; nombre: string; estado: string; observaciones: string };

export type Overview = {
  contexto: { institucion: { id: number; nombre: string }; departamento: { id: number; nombre: string } };
  titulo: string;
  info: string;
  tabs: string[];
  permisos: { puede_escribir: boolean; puede_borrar: boolean };
  repositorio: {
    filas: FilaDocumento[];
    filtros: { tipos: string[]; categorias: string[]; dependencias: string[] };
    busqueda: string[];
    vacio: string;
    sin_coincidencias: string;
  };
  alta: {
    categorias: string[];
    tipos: string[];
    categorias_docente: string[];
    categorias_proyecto: string[];
    tipos_con_dependencia: string[];
    dependencias: Opcion[];
    sin_dependencias: string;
    periodos: Opcion[];
    modos_docentes: string[];
    periodo_actual: { id: number; nombre: string } | null;
    periodos_docentes: Opcion[];
    periodo_docentes_indice: number;
    max_pdf_bytes: number;
    textos: Record<string, string>;
  };
  dependencias: {
    filas: Dependencia[];
    activas: number;
    cargadas: number;
    caption: string;
    vacio: string;
    estados: string[];
    solo_lectura: string;
    opciones_edicion: Opcion[];
  };
};

export type Detalle = {
  fila: FilaDocumento;
  encabezado: string;
  aviso_dependencia: string;
  tiene_pdf: boolean;
  pdf_pendiente: string;
  dependencias: Opcion[];
  dependencia_indice: number;
  permisos: { puede_escribir: boolean; puede_borrar: boolean };
  // 6A-B3: acto de "Designación docente" -> designaciones concretas que respalda (ids reales).
  designacion_docente: boolean;
  designaciones: FilaDesignacion[];
  caption_designaciones: string;
  designacion_pendiente: string;
  // Relaciones que la categoría admite al cargarse; se pueden revisar después (docentes: agregar; proyectos: fijar).
  relaciones: { docentes: boolean; designaciones: boolean; proyectos: "investigacion" | "extension" | null };
  proyectos_vinculados: number[];
};

// Designación seleccionable (todas las del docente, de todos los períodos) con su acto vinculado actual.
export type FilaDesignacion = {
  id: number;
  cuil: string;
  docente: string;
  periodo: string;
  cargo: string;
  dedicacion: string;
  tipo_designacion: string;
  fecha_desde: string;
  fecha_hasta: string;
  estado: string;
  funcion_no_docente: number;
  acto_documento_id: number | null;
  acto_administrativo: string;
  vinculada: boolean;
};

export type TablaDesignaciones = { filas: FilaDesignacion[]; caption: string; aviso: string };

export type TablaDocentes = {
  filas: { Docente: string; CUIL: string }[];
  periodo_id: number | null;
  solo_activas: boolean;
  caption: string;
  aviso: string;
};

export type FilaProyecto = {
  ID: number;
  Código: string;
  Proyecto: string;
  Estado: string;
  Inicio: string | null;
  Fin: string | null;
  "Departamento creador": string;
};

// `aviso` (6A-B3): advertencia adicional del alta (p. ej. resolución de designación sin designación vinculada).
export type WriteResult = { mensaje: string; tono: Tono; id?: number; aviso?: string };

export const MAX_PDF_BYTES = 50 * 1024 * 1024;
const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";
const BASE = "/api/resoluciones-respaldos";

export class ResolucionesError extends ApiError {
  constructor(status: number, code: string, message: string, public tone: "error" | "warning" | "info" = "error") {
    super(status, code, message);
  }
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${BASE}${path}`, { ...init, cache: "no-store", credentials: "same-origin" });
  } catch {
    throw new ResolucionesError(0, "NETWORK", UNREACHABLE);
  }
}

async function fail(response: Response): Promise<never> {
  const data = await response.json().catch(() => null);
  throw new ResolucionesError(
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

export const post = <T,>(path: string, body: unknown) =>
  call<T>(`/${path}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

// D-AK1: el PDF va como parte binaria del multipart (el navegador arma el boundary; nunca base64).
export function subir<T>(path: string, datos: unknown, archivo: File | null) {
  const form = new FormData();
  form.append("datos", JSON.stringify(datos));
  if (archivo) form.append("archivo", archivo, archivo.name);
  return call<T>(`/${path}`, { method: "POST", body: form });
}

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

// PDF servido por FastAPI tras reautorizar (POST con el id; nunca rutas).
export async function descargarPdf(id: number): Promise<void> {
  const response = await request("/documento/pdf", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ id }),
  });
  if (!response.ok) return fail(response);
  const blob = await response.blob();
  const nombre = nombreArchivo(response.headers.get("content-disposition") ?? "", "documento.pdf");
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const resolucionesApi = {
  overview: () => call<Overview>(""),
};
