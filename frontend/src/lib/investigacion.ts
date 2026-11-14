// Tipos y llamadas del módulo Investigación al proxy /api/investigacion. El ámbito lo decide la sesión en el backend.
import { ApiError, type Named } from "@/lib/auth";

export { archivoBase64, download, g } from "@/lib/comisiones";

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

export type Permisos = {
  puede_escribir: boolean;
  puede_borrar: boolean;
  puede_cargar: boolean;
  puede_movimiento: boolean;
  puede_vincular_acto: boolean;
  puede_desvincular_acto: boolean;
};

export type Overview = {
  contexto: { institucion: Named; departamento: Named };
  periodos: Periodo[];
  abierto: Periodo | null;
  historico_abierto: boolean;
  huella_periodo: string;
  rol: string | null;
  permisos: Permisos;
  ayuda_radicacion: string;
  estados_alta: string[];
  roles_sugeridos: string[];
};

export type Ficha = {
  proyecto_id: number;
  encabezado: { nombre: string; codigo: string; situacion: string; estado: string };
  datos: Record<string, string>;
  actos: { codigo: string; acto: string; documento_id: number; dependencia_emisora: string | null; fecha: string | null; categoria: string | null; detalle: string | null }[];
  metricas: { horas_semanales: string; meses: number; horas_totales: string };
  periodo_activo: string;
  historico_contexto: boolean;
  participacion: Record<string, string | number>;
  integrantes: { id: number | null; docente: string; cuil: string; departamento: string; rol: string; horas: string; observaciones: string }[];
  historial: Fila[];
  proyecto: { nombre: string; codigo: string };
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

export type Capacidad = {
  horas_contratadas: number;
  horas_comisiones: number;
  horas_no_lectivas: number;
  horas_investigacion: number;
  horas_extension: number;
  capacidad_total_proyectos: number;
  horas_proyectos_actuales: number;
  horas_disponibles_proyectos: number;
  exceso_proyectos: number;
  mensaje: string;
};

export type DocentePadron = {
  cuil: string;
  nombre_completo: string | null;
  legajo: string | null;
  cargo_final: string | null;
  cargo: string | null;
  horas_designadas: number | null;
  tipo_docente: string | null;
  departamento_origen: string | null;
};

export type AsignarDetalle = {
  periodo: Periodo;
  integrantes: FilaHuella[];
  huella_integrantes: string;
  duplicados_legacy: boolean;
  padron: { consolidado: number | null; selector: number | null; diagnosticos: string[] };
  docentes: DocentePadron[];
  eliminables: FilaHuella[];
};

export type AlertaPostAccion = {
  tipo_modulo: string;
  periodo_id: number;
  cuil: string;
  docente: string;
  accion: string;
  horas_accion: number;
  horas_disponibles_antes: number;
};

export type WriteResult = {
  mensaje: string;
  tono: "success" | "warning" | "info";
  sin_cambios?: boolean;
  pestana?: string;
  alerta_post_accion?: AlertaPostAccion;
  detalle_proyectos?: Fila[];
  detalle_asignaciones?: Fila[];
};

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

export class InvestigacionError extends ApiError {
  constructor(status: number, code: string, message: string, public tone: "error" | "warning" | "info" = "error") {
    super(status, code, message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/investigacion${path}`, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new InvestigacionError(0, "NETWORK", UNREACHABLE);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new InvestigacionError(
      response.status,
      data?.error?.code ?? "ERROR",
      data?.error?.message ?? UNREACHABLE,
      data?.error?.tone ?? "error"
    );
  }
  return data as T;
}

export const post = <T,>(path: string, body: unknown) => call<T>(`/${path}`, { method: "POST", body: JSON.stringify(body) });

async function blob(path: string): Promise<{ blob: Blob; nombre: string }> {
  let response: Response;
  try {
    response = await fetch(`/api/investigacion/${path}`, { cache: "no-store", credentials: "same-origin" });
  } catch {
    throw new InvestigacionError(0, "NETWORK", UNREACHABLE);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new InvestigacionError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE);
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const nombre = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "investigacion.xlsx";
  return { blob: await response.blob(), nombre };
}

export const investigacionApi = {
  overview: () => call<Overview>(""),
  modeloExcel: () => blob("modelo-excel"),
};

// Memoria de sesión del balance posterior a una edición (st.session_state["_alerta_post_accion_proyecto_v187"]).
const CLAVE_ALERTA = "deptit_inv_alerta_post_accion_v187";

export function guardarAlerta(a: AlertaPostAccion) {
  try {
    sessionStorage.setItem(CLAVE_ALERTA, JSON.stringify(a));
  } catch {
    /* sin almacenamiento: la alerta no se muestra */
  }
}

export function tomarAlerta(): AlertaPostAccion | null {
  try {
    const raw = sessionStorage.getItem(CLAVE_ALERTA);
    sessionStorage.removeItem(CLAVE_ALERTA);
    return raw ? (JSON.parse(raw) as AlertaPostAccion) : null;
  } catch {
    return null;
  }
}

// E4-04: costos salariales de Proyectos vigentes (motor de Sueldos v257/v258), presentados como ESTIMACIÓN (D-E4-02).
export type Costos = {
  estimacion: { etiqueta: string; advertencia: string };
  proyectos: { proyecto_id: number; costo_tabla: string; costo_ficha: string; leyenda: string }[];
  integrantes: { asignacion_id: number; proyecto_id: number; detalle_salarial: string; costo: string }[];
  sin_costo: string;
};
