// Tipos y llamadas del módulo Designaciones al proxy /api/designaciones. El ámbito lo decide la sesión en el backend.
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

export type Designacion = {
  id: number;
  periodo_id: number;
  periodo: string | null;
  nombre_completo: string | null;
  cuil: string | null;
  cargo: string | null;
  dedicacion: string | null;
  horas: number | null;
  tipo_designacion: string | null;
  numero_resolucion: string | null;
  ad_honorem: string | null;
  fecha_desde: string | null;
  fecha_hasta: string | null;
  fecha_hasta_prevista: string | null;
  fecha_finalizacion_efectiva: string | null;
  fecha_registro_finalizacion: string | null;
  motivo_finalizacion: string | null;
  estado: string | null;
  observaciones: string | null;
  funcion_no_docente: number;
  texto_funcion_no_docente: string;
  numero_resolucion_legacy: string;
  acto_documento_id: number | null;
  acto_administrativo: string;
  acto_dependencia: string;
  acto_fecha: string;
  huella: string;
  estado_mostrado: string;
  funcion: string;
};

export type Movimiento = {
  id: number;
  fecha: string | null;
  cuil: string | null;
  nombre: string | null;
  tipo_movimiento: string;
  detalle: string | null;
  acto_documento_id: number | null;
  acto_administrativo: string | null;
  observaciones: string | null;
  variacion_horas: number;
  categoria: string;
  huella: string;
};

export type Indicador = { etiqueta: string; categoria: string; movimiento: string };

export type Docente = {
  cuil: string;
  nombre_completo: string | null;
  legajo: string | null;
  titulo: string | null;
  tipo_docente: string | null;
  estado: string | null;
};

export type Overview = {
  contexto: { institucion: Named; departamento: Named };
  abierto: Periodo | null;
  abierto_huella: string | null;
  actual: Periodo | null;
  historico_abierto: boolean;
  periodos: Periodo[];
  docentes: Docente[];
  catalogos: {
    cargos: string[];
    dedicaciones: string[];
    horas_por_dedicacion: Record<string, number>;
    tipos: string[];
    estados: string[];
    ad_honorem: string[];
    tipos_cambio: string[];
    movimientos_con_acto: string[];
  };
  permisos: {
    puede_escribir: boolean;
    puede_borrar: boolean;
    puede_movimiento: boolean;
    puede_vincular: boolean;
    puede_desvincular: boolean;
    es_superadmin: boolean;
  };
};

export type PeriodoData = {
  periodo: Periodo;
  historico: boolean;
  designaciones: Designacion[];
  conteo: number;
  foto_ids: number[];
  historial: Movimiento[];
  indicadores: Indicador[];
  abierto: Periodo | null;
};

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

export type ActoModo = "existente" | "nuevo" | "pendiente";
// E4-07: datos del formulario en línea "Cargar un nuevo acto ahora" (_render_nuevo_acto_inline_v267).
export type ActoNuevoForm = {
  tipo_documento: string;
  dependencia: string;
  dependencia_id: number | null;
  numero: string;
  fecha: string;
  titulo: string;
  detalle: string;
  observaciones: string;
  archivo: File | null;
};
export type ActoConfig = { modo: ActoModo; documento_id: number | null; nuevo?: ActoNuevoForm };
export type ContextoActoNuevo = {
  titulo: string;
  caption: string;
  tipos: string[];
  tipos_con_dependencia: string[];
  dependencias: { etiqueta: string; id: number | null }[];
  sin_dependencias: string;
  help_dependencia: string;
  max_pdf_bytes: number;
  pdf_grande: string;
  categoria_alta: string;
  categorias: Record<string, string>;
};

export type WriteResult = { mensaje: string; tono: "success" | "warning" | "info"; avisos?: string[]; sin_cambios?: boolean };

export type Carga = {
  filas: Record<string, string | number | null>[];
  inexistentes: { fila_pegada: number; cuil: string; motivo: string }[];
  duplicados: Record<string, string | number | null>[];
  aviso: string | null;
};

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

export class DesignacionesError extends ApiError {
  constructor(status: number, code: string, message: string, public tone: "error" | "warning" | "info" = "error") {
    super(status, code, message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/designaciones${path}`, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      // FormData (acto nuevo con PDF, E4-07): el navegador arma el boundary del multipart.
      headers: init?.body instanceof FormData ? init?.headers : { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new DesignacionesError(0, "NETWORK", UNREACHABLE);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new DesignacionesError(
      response.status,
      data?.error?.code ?? "ERROR",
      data?.error?.message ?? UNREACHABLE,
      data?.error?.tone ?? "error"
    );
  }
  return data as T;
}

export const post = <T,>(path: string, body: unknown) =>
  call<T>(`/${path}`, { method: "POST", body: JSON.stringify(body) });

// E4-07: alta / modificación con "Cargar un nuevo acto ahora". La operación y el acto viajan juntos como
// multipart/form-data (parte "datos" JSON + parte "archivo" con el PDF opcional, sin base64): FastAPI crea el acto con
// el writer de Resoluciones y respaldos y sigue con los writers de Designaciones.
export function guardarConActo(operacion: "alta" | "modificar", body: Record<string, unknown>, acto: ActoConfig) {
  const form = formularioActoNuevo(body, acto);
  if (!form) return post<WriteResult>(operacion, { ...body, acto });
  return call<WriteResult>(`/acto-nuevo/${operacion}`, { method: "POST", body: form });
}

// Cuerpo multipart de "Cargar un nuevo acto ahora" (parte "datos" + PDF opcional), o null si el modo no es "nuevo".
// 6A-B3: también lo usa Docentes → Registrar designación.
export function formularioActoNuevo(body: Record<string, unknown>, acto: ActoConfig): FormData | null {
  if (acto.modo !== "nuevo" || !acto.nuevo) return null;
  const n = acto.nuevo;
  const datos = {
    ...body,
    acto: {
      modo: "nuevo",
      payload: {
        tipo_documento: n.tipo_documento,
        dependencia_id: n.dependencia_id,
        numero: n.numero,
        fecha: n.fecha,
        titulo: n.titulo,
        detalle: n.detalle,
        observaciones: n.observaciones,
      },
    },
  };
  const form = new FormData();
  form.append("datos", JSON.stringify(datos));
  if (n.archivo) form.append("archivo", n.archivo, n.archivo.name);
  return form;
}

async function blob(path: string, init?: RequestInit): Promise<{ blob: Blob; nombre: string }> {
  let response: Response;
  try {
    response = await fetch(`/api/designaciones/${path}`, { cache: "no-store", credentials: "same-origin", ...init });
  } catch {
    throw new DesignacionesError(0, "NETWORK", UNREACHABLE);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new DesignacionesError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE);
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const nombre = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "designaciones.xlsx";
  return { blob: await response.blob(), nombre };
}

export const designacionesApi = {
  overview: () => call<Overview>(""),
  periodo: (periodo_id: number) => post<PeriodoData>("periodo", { periodo_id }),
  actos: () => post<{ documentos: Documento[] }>("actos", {}),
  modeloExcel: () => blob("modelo-excel"),
  tablaExcel: (periodo_id: number) =>
    blob("periodo/excel", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ periodo_id }),
    }),
};

export function download(file: { blob: Blob; nombre: string }) {
  const url = URL.createObjectURL(file.blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = file.nombre;
  a.click();
  URL.revokeObjectURL(url);
}

// safe_index certificado: si el valor no está entre las opciones, el selector muestra la primera.
export const pick = (opts: string[], v: string | null | undefined) =>
  v !== null && v !== undefined && opts.includes(v) ? v : opts[0];

export const horasSegunDedicacion = (catalogo: Record<string, number>, dedicacion: string, fallback = 0) => {
  const txt = dedicacion.trim().split(/\s+/).join(" ").toLocaleLowerCase();
  for (const [nombre, horas] of Object.entries(catalogo)) if (nombre.toLocaleLowerCase() === txt) return horas;
  return Math.trunc(Number(fallback) || 0);
};

export const textoLimpio = (v: string | null | undefined) => String(v ?? "").trim().split(/\s+/).filter(Boolean).join(" ");

export const esNoDocente = (v: unknown) =>
  v === true || v === 1 || ["1", "sí", "si", "true", "verdadero", "yes"].includes(String(v ?? "").trim().toLocaleLowerCase());
