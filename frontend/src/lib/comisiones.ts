// Tipos y llamadas del módulo Comisiones al proxy /api/comisiones. El ámbito lo decide la sesión en el backend.
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

export type Overview = {
  contexto: { institucion: Named; departamento: Named };
  periodos: Periodo[];
  abierto: Periodo | null;
  actual: Periodo | null;
  puede_operar: boolean;
  motivo_bloqueo: string | null;
  puede_corregir: boolean;
  motivo_correccion: string | null;
  periodo_correccion: Periodo | null;
  historico_abierto: boolean;
  huella_periodos: string;
  catalogos: {
    turnos: string[];
    modalidades: string[];
    dias: string[];
    roles: string[];
    sedes: string[];
    estados_sede: string[];
  };
  permisos: {
    puede_escribir: boolean;
    puede_borrar: boolean;
    puede_escribir_sedes: boolean;
    puede_borrar_sedes: boolean;
    puede_movimiento: boolean;
  };
};

export type PeriodoData =
  | { vacio: true }
  | {
      vacio: false;
      filas: Fila[];
      caption: string;
      horarios: Fila[];
      caption_horarios: string;
      asignaciones: Fila[];
      caption_asignaciones: string;
    };

export type Alertas = { periodo: Periodo | null; superposiciones?: Fila[]; sin_docentes?: Fila[] };

export type Sede = {
  id: number;
  nombre: string | null;
  direccion: string | null;
  localidad: string | null;
  estado: string | null;
  observaciones: string | null;
  huella: string;
};
export type SedesData = { sedes: Sede[]; activas: number; opciones: number };

export type FilaInscriptos = Fila & { clave: string; huella: string };
export type InscriptosData = {
  legacy: Fila[];
  vacio: boolean;
  metricas?: { asignaturas: number; alumnos: number; comisiones: number; docentes: number };
  filas?: FilaInscriptos[];
  columnas?: string[];
  grupos?: Fila[];
  historial?: Fila[];
  historial_combinaciones?: Fila[];
};

export type MateriaFila = {
  materia_id: number;
  codigo: string | null;
  asignatura: string | null;
  carrera: string | null;
  escuela: string | null;
  plan_version: string | null;
  anio: string | number | null;
  cuatrimestre: string | number | null;
  carga_semanal: string | number | null;
};
export type MateriasAlta = {
  cuatrimestres: string[];
  escuelas: string[];
  carreras: string[];
  caption: string;
  materias: MateriaFila[];
};

export type OpcionCurricular = {
  id: number;
  codigo: string | null;
  nombre: string | null;
  tipo: string | null;
  escuela_oferente: string | null;
  carreras_habilitadas: string | null;
  espacios_plan: string | null;
};
export type MateriaAlta = {
  es_oe: boolean;
  codigo: string;
  asignatura: string;
  adicionales: { etiqueta: string; materia_id: number }[];
  resumen: Fila[];
  info_multicodigo: string;
  info_compartida: string;
  tipo_espacio: string;
  opciones?: OpcionCurricular[];
  vinculos_opcion?: Fila[];
};

export type DocenteDisponible = {
  cuil: string;
  nombre_completo: string | null;
  tipo_docente: string | null;
  cargo: string | null;
  dedicacion: string | null;
  horas_designadas: number | null;
  departamento_origen: string | null;
  etiqueta_alta: string;
  etiqueta_cambio: string;
};
export type Roles = { roles: string[]; prestado_local: boolean };

export type Franja = {
  indice: number;
  dia: string;
  hora_inicio: string;
  hora_fin: string;
  etiqueta: string;
  horario_comision_id: number | null;
  usar: boolean;
  desde: string;
  hasta: string;
};
export type Seleccion = { usar: boolean; desde: string; hasta: string };

export type ComisionFila = {
  id: number;
  codigo_materia: string | null;
  asignatura: string | null;
  materia_especifica: string | null;
  nombre_comision: string | null;
  turno: string | null;
  sede: string | null;
  modalidad: string | null;
  periodo: string | null;
  carrera: string | null;
  horarios: string | null;
  docentes_asignados_detalle: string | null;
};
export type Lista = {
  periodo: Periodo | null;
  historico_abierto: boolean;
  puede_corregir: boolean;
  aviso: string | null;
  filas: ComisionFila[];
  huella_lote?: string;
};

export type HorarioFila = Fila & { id: number; etiqueta: string; etiqueta_eliminar: string };
export type AsignacionFila = Fila & { id: number; etiqueta: string; etiqueta_baja: string };
export type Detalle = {
  fila: Fila;
  etiqueta: string;
  horarios: HorarioFila[];
  asignaciones: AsignacionFila[];
  metricas: { horarios: number; horas: string; docentes_activos: number };
  franjas_alta: Franja[];
  huella: string;
  historial?: Fila[];
};

export type DatosEdicion = {
  materias: { etiqueta: string; materia_id: number }[];
  materia_id: number;
  indice_materia_actual: number;
  es_oe: boolean;
  estado: string;
  adicionales: { etiqueta: string; materia_id: number }[];
  adicionales_default: number[];
  opciones_curriculares: string[];
  indice_opcion: number;
  sin_opciones: boolean;
  avisos: string[];
  placeholder: string;
  valores: { nombre: string; turno: string; sede: string; modalidad: string; observaciones: string };
  opciones_sede: string[];
};

export type Preview = {
  mensajes: { tono: "success" | "warning" | "error" | "info"; texto: string }[];
  filas: Fila[];
  totales: { ok: number; advertencia: number; duplicada: number; error: number } | null;
  huella: string | null;
};

export type WriteResult = { mensaje: string; tono: "success" | "warning" | "info"; avisos?: string[]; sin_cambios?: boolean; id?: number };

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

export class ComisionesError extends ApiError {
  constructor(status: number, code: string, message: string, public tone: "error" | "warning" | "info" = "error") {
    super(status, code, message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/comisiones${path}`, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ComisionesError(0, "NETWORK", UNREACHABLE);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ComisionesError(
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

async function blob(path: string, init?: RequestInit): Promise<{ blob: Blob; nombre: string }> {
  let response: Response;
  try {
    response = await fetch(`/api/comisiones/${path}`, { cache: "no-store", credentials: "same-origin", ...init });
  } catch {
    throw new ComisionesError(0, "NETWORK", UNREACHABLE);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ComisionesError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE);
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const nombre = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "comisiones.xlsx";
  return { blob: await response.blob(), nombre };
}

export const comisionesApi = {
  overview: () => call<Overview>(""),
  modeloExcel: () => blob("modelo-excel"),
  periodoExcel: (periodo_id: number) =>
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

// Archivo -> base64 (sin el prefijo data:) para enviarlo dentro del JSON.
export async function archivoBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  return btoa(binary);
}

// _minutos_v95 / _horas_intervalo_v95: horas de una franja HH:MM.
export function minutos(v: string): number | null {
  const m = /^(\d{1,2}):(\d{2})/.exec(String(v ?? "").trim());
  if (!m) return null;
  return Number(m[1]) * 60 + Number(m[2]);
}

export function horasIntervalo(desde: string, hasta: string): number {
  const a = minutos(desde);
  const b = minutos(hasta);
  if (a === null || b === null || b <= a) return 0;
  return Math.round(((b - a) / 60) * 100) / 100;
}

// Formato :g de Python para horas (sin ceros sobrantes).
export const g = (n: number) => String(Number(n.toFixed(6)));

// Horas efectivas de una selección (formulario_horarios_reales_asignacion): solo franjas válidas y dentro del horario.
export function horasSeleccion(franjas: Pick<Franja, "hora_inicio" | "hora_fin" | "dia">[], sel: Seleccion[]) {
  let total = 0;
  const errores: string[] = [];
  franjas.forEach((f, i) => {
    const s = sel[i];
    if (!s?.usar) return;
    const base_a = minutos(f.hora_inicio);
    const base_b = minutos(f.hora_fin);
    const a = minutos(s.desde);
    const b = minutos(s.hasta);
    if (base_a !== null && base_b !== null && a !== null && b !== null && base_a <= a && a < b && b <= base_b) {
      total += horasIntervalo(s.desde, s.hasta);
    } else {
      errores.push(`La franja de ${f.dia} debe quedar entre ${f.hora_inicio} y ${f.hora_fin}.`);
    }
  });
  return { horas: Math.round(total * 100) / 100, errores };
}

// calcular_horas_desde_texto: duración de un horario general (si el fin es anterior al inicio suma 24 h).
export function horasHorario(inicio: string, fin: string): number {
  const a = minutos(inicio);
  const b = minutos(fin);
  if (a === null || b === null) return 0;
  let delta = (b - a) / 60;
  if (delta < 0) delta += 24;
  return Math.round(delta * 100) / 100;
}

// normalizar_clave: mayúsculas y espacios colapsados (sin quitar acentos).
export const claveTexto = (v: unknown) =>
  String(v ?? "")
    .trim()
    .toUpperCase()
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
