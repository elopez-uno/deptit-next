// Tipos y llamadas del módulo Períodos al proxy /api/periodos. El ámbito lo decide la sesión en el backend.
import { ApiError, type Named } from "@/lib/auth";

export type Periodo = {
  id: number;
  nombre: string | null;
  anio: number | null;
  semestre: number | null;
  fecha_inicio: string | null;
  fecha_fin: string | null;
  estado: string | null;
  observaciones: string | null;
};

export type PeriodosOverview = {
  contexto: { institucion: Named; departamento: Named };
  periodos: Periodo[];
  abierto: Periodo | null;
  actual: Periodo | null;
  permisos: { puede_escribir: boolean; es_superadmin: boolean };
};

export type WriteResult = { mensaje: string; periodo: Periodo; cambio: boolean };

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/periodos${path}`, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "NETWORK", UNREACHABLE);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      response.status,
      data?.error?.code ?? "ERROR",
      data?.error?.message ?? UNREACHABLE
    );
  }
  return data as T;
}

export const periodosApi = {
  overview: () => call<PeriodosOverview>(""),
  openPrevious: (body: {
    periodo_id: number;
    observaciones: string;
    confirmar_cierre: boolean;
    confirmar_excepcional: boolean;
  }) =>
    call<WriteResult>("/apertura-excepcional", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  returnCurrent: (body: {
    observaciones: string;
    confirmar_cierre_anterior: boolean;
    confirmar_retorno: boolean;
  }) =>
    call<WriteResult>("/volver-actual", { method: "POST", body: JSON.stringify(body) }),
};

export const periodoLabel = (p: Periodo) =>
  `${p.nombre ?? "-"} - ${p.fecha_inicio ?? ""} al ${p.fecha_fin ?? ""} - Estado: ${p.estado ?? ""}`;

// E4-10..E4-12: ciclo de períodos (una transacción por operación). Las respuestas de escritura traen
// ``periodo_cambiado`` (P-01b): el módulo avisa al shell para que recalcule el contexto histórico al instante.
export type TablaConteo = { tabla: string; etiqueta: string; filas: number };
export type CrearContexto = {
  aviso: string;
  anio_min: number;
  anio_max: number;
  anio_default: number;
  semestres: { valor: number; etiqueta: string }[];
  objetivo: { nombre: string; fecha_inicio: string; fecha_fin: string };
  existente: Periodo | null;
  gate: { activo: boolean; entorno: string; aviso: string | null };
  puede_escribir: boolean;
};
export type CicloResultado = { mensaje: string; tono: "success" | "warning"; periodo_cambiado: boolean };
export type RevertirDiagnostico = {
  info: string;
  es_superadmin: boolean;
  mensaje_permiso?: string;
  ok?: boolean;
  mensaje?: string;
  periodo_nuevo?: Periodo | null;
  periodo_anterior?: Periodo | null;
  designaciones_nuevo?: number;
  cierres_anterior?: number;
  activas_anterior?: number;
  bloqueos?: TablaConteo[];
  puede_revertir?: boolean;
  mensaje_bloqueo?: string;
  huella?: string;
};
export type EliminarDiagnostico = {
  info: string;
  es_superadmin: boolean;
  mensaje_permiso?: string;
  periodo?: Periodo;
  conteos?: TablaConteo[];
  movimientos?: number;
  apertura_automatica?: number | null;
  bloqueos?: TablaConteo[];
  vacio?: boolean;
  proximo_activo?: Periodo | null;
  texto_confirmacion?: string;
  mensaje?: string | null;
  huella?: string;
};
export type RepararDiagnostico = {
  es_superadmin: boolean;
  visible: boolean;
  boton?: string;
  periodo?: Periodo | null;
  movimientos_cierre?: number;
  designaciones_reactivables?: number;
  bloqueos?: TablaConteo[];
  puede_reparar?: boolean;
  mensaje?: string;
  huella?: string;
};

const postJson = <T,>(path: string, body: unknown) => call<T>(path, { method: "POST", body: JSON.stringify(body) });

export const cicloApi = {
  crearContexto: (anio: number, semestre: number) => postJson<CrearContexto>("/crear/contexto", { anio, semestre }),
  crear: (body: { anio: number; semestre: number; copiar_anterior: boolean; observaciones: string }) =>
    postJson<CicloResultado & { periodo_id: number }>("/crear", body),
  revertirDiagnostico: () => postJson<RevertirDiagnostico>("/revertir/diagnostico", {}),
  revertir: (body: { observaciones: string; confirmar_1: boolean; confirmar_2: boolean; confirmar_3: boolean; huella: string }) =>
    postJson<CicloResultado>("/revertir", body),
  eliminarDiagnostico: (periodo_id: number | null) => postJson<EliminarDiagnostico>("/eliminar/diagnostico", { periodo_id }),
  eliminar: (body: { periodo_id: number; observaciones: string; confirmar: boolean; texto_confirmacion: string; huella: string }) =>
    postJson<CicloResultado>("/eliminar", body),
  repararDiagnostico: () => postJson<RepararDiagnostico>("/reparar-finalizaciones/diagnostico", {}),
  reparar: (huella: string) => postJson<CicloResultado>("/reparar-finalizaciones", { huella }),
};
