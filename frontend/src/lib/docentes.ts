// Tipos y llamadas del módulo Docentes al proxy /api/docentes. El ámbito lo decide la sesión en el backend.
import { ApiError, type Named } from "@/lib/auth";
import { type ActoConfig, formularioActoNuevo } from "@/lib/designaciones";

export type Docente = {
  cuil: string;
  legajo: string | null;
  apellido: string | null;
  nombres: string | null;
  nombre_completo: string;
  titulo: string | null;
  titulo_posgrado: string;
  antiguedad_anios: number | null;
  nivel_posgrado_salarial: string;
  email: string | null;
  telefono: string | null;
  ref_legajo_fisico: string | null;
  tipo_docente: string;
  observaciones: string;
  estado: string | null;
  fecha_alta: string;
  fecha_finalizacion: string;
  estado_periodo_abierto: string;
  huella: string;
};

export type PeriodoRef = {
  id: number;
  nombre: string | null;
  fecha_inicio: string | null;
  fecha_fin: string | null;
  estado: string | null;
};

export type DocentesOverview = {
  contexto: { institucion: Named; departamento: Named };
  abierto: PeriodoRef | null;
  actual: PeriodoRef | null;
  historico: boolean;
  docentes: Docente[];
  catalogos: {
    estados: string[];
    estados_baja: string[];
    tipos: string[];
    niveles_posgrado: string[];
    antiguedad_min: number;
    antiguedad_max: number;
  };
  permisos: { puede_escribir: boolean; puede_borrar: boolean; es_superadmin: boolean };
};

export type Fila = Record<string, string | number | null>;

export type Ficha = {
  docente: Docente;
  referencias: {
    designaciones: Fila[];
    comisiones: Fila[];
    investigacion: Fila[];
    extension: Fila[];
    actividades_especiales: Fila[];
    total: number;
  };
  prestamo: { activo: { departamento_origen: string; fecha_desde: string } | null } | null;
  huerfanos: { cuil_huerfano: string; referencias: number; detalle: string }[];
};

export type OtroDepartamento = {
  cuil: string;
  nombre_completo: string;
  departamento_origen: string;
  legajo: string | null;
  cargo?: string | null;
  dedicacion?: string | null;
  tipo_docente?: string;
};

export type VerificacionCuil = {
  cuil_limpio: string;
  otros_departamentos: OtroDepartamento[];
  local: { cuil: string; tipo_docente: string; nombre: string } | null;
};

export type CargaPreview = {
  filas: Record<string, string>[];
  duplicados: { fila_pegada: number; cuil: string; apellido: string; nombres: string; motivo: string }[];
  aviso: string | null;
};

export type WriteResult = { mensaje: string; tono: "success" | "warning" | "info"; cuil?: string };

export type DocenteForm = {
  apellido: string;
  nombres: string;
  cuil: string;
  legajo: string;
  titulo: string;
  titulo_posgrado: string;
  nivel_posgrado_salarial: string;
  antiguedad_anios: number | null;
  email: string;
  telefono: string;
  ref_legajo_fisico: string;
  observaciones: string;
};

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/docentes${path}`, {
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

const post = <T,>(path: string, body: unknown) =>
  call<T>(path, { method: "POST", body: JSON.stringify(body) });

// Pestaña "📋 Plantel del período abierto" (E4-02): selector certificado {nombre: id} y st.dataframe del plantel.
export type PlantelPeriodo = { id: number; nombre: string };
export type Plantel = {
  periodos: PlantelPeriodo[];
  seleccionado: PlantelPeriodo | null;
  sin_periodos: string | null;
  info?: string;
  vacio?: string | null;
  tabla?: { columnas: string[]; filas: unknown[][] } | null;
  total_activos?: number | null;
};
// Pestaña "📊 Resumen docente" (E4-05): secciones de lectura transcriptas del certificado (el backend arma todo).
export type TablaUI = { columnas: string[]; filas: unknown[][] };
export type Aviso = { tono: "info" | "success" | "warning"; texto: string };
export type SeccionTabla = { titulo: string; caption: string | null; tabla: TablaUI | null; vacio: Aviso | null; aviso?: string };
export type MetricaUI = { label: string; valor: string };
export type Rotulo = { label: string; valor: string; tono?: "positivo" | "negativo" | "neutro" };
export type CeldaCronograma = { labels: string[]; titulo: string } | null;
export type ResumenSecciones = {
  datos_generales: {
    nombre: string;
    cuil: string;
    legajo: string;
    situacion: { texto: string; tono: "success" | "info" };
    trayectoria: { inicio_historico: string; ultima_alta: string; finalizacion: string };
    contacto: { mail: string; telefono: string };
    formacion: { grado: string; posgrado: string; nivel: string; antiguedad: string };
    observaciones: string | null;
  };
  tarjeta: {
    aviso_prestado: string | null;
    titulo: string;
    estado_designacion: string | null;
    funciones_no_docentes: { titulo: string; caption: string; tabla: TablaUI } | null;
    cargos: { label: string; lineas: string[] };
    horas: Rotulo;
    variacion: Rotulo & { caption: string };
    cambios: { label: string; lineas: string[] };
    evolucion: { titulo: string; base: Rotulo; movimiento: Rotulo; resultado: Rotulo } | null;
    compartido: string | null;
    caption_origen: string | null;
    departamentos: TablaUI | null;
  };
  designaciones: SeccionTabla;
  actos: SeccionTabla;
  sueldo: { titulo: string; vacio: Aviso | null; caption: string | null; tabla: TablaUI | null; total: MetricaUI | null };
  investigacion: SeccionTabla;
  extension: SeccionTabla;
  actividades: SeccionTabla;
  comisiones: SeccionTabla;
  cronograma: { titulo: string; dias: string[]; filas: { hora: string; celdas: CeldaCronograma[] }[]; caption: string };
  superposiciones: SeccionTabla;
  productividad: {
    titulo: string;
    caption: string;
    metricas: MetricaUI[];
    detalle_no_lectivas: { titulo: string; tabla: TablaUI } | null;
    torta: { spec: Record<string, unknown> } | null;
    sin_torta: string | null;
  };
  materias_historicas: SeccionTabla;
};
// Sección "Mensaje para consultar la designación" (E4-06): estado de consulta (radio + writer) y mensaje.
export type Semaforo = { tono: "success" | "warning" | "error" | "info"; texto: string };
export type Consulta = {
  titulo: string;
  caption: string;
  radio: string;
  opciones: { etiqueta: string; valor: string; semaforo: Semaforo }[];
  seleccion: string;
  boton_guardar: string;
  boton_mensaje: string;
  asunto_label: string;
  cuerpo_label: string;
};
export type MensajeConsulta = { asunto: string; cuerpo: string; advertencias: string[] };
export type EstadoGuardado = WriteResult & { estado: string; semaforo: Semaforo };
export type Resumen = {
  subtitulo: string;
  info: string;
  sin_docentes?: string;
  sin_periodos?: string;
  periodos?: PlantelPeriodo[];
  seleccionado?: PlantelPeriodo;
  error?: string;
  secciones?: ResumenSecciones;
  estimacion?: { etiqueta: string; advertencia: string };
  consulta?: Consulta;
};

// Pestaña "👥 Equipos docentes" (E4-03): mismo selector; st.dataframe de get_equipos_docentes_periodo.
export type Equipos = {
  info: string;
  periodos: PlantelPeriodo[];
  seleccionado: PlantelPeriodo | null;
  sin_periodos: string | null;
  vacio?: string | null;
  tabla?: { columnas: string[]; filas: unknown[][] } | null;
  total_materias?: number | null;
};

// E4-08: registrar una designación desde Docentes (pestaña "Registrar docente"). El alta la hace Designaciones.
export type CatalogosDesignacion = {
  cargos: string[];
  dedicaciones: string[];
  horas_por_dedicacion: Record<string, number>;
  tipos: string[];
  estados: string[];
  ad_honorem: string[];
};
export type Reincorporable = {
  nombre_completo: string | null;
  cuil: string;
  legajo: string | null;
  titulo: string | null;
  estado: string | null;
  huella: string;
};
export type ContextoDesignacion = {
  abierto: { id: number; nombre: string; fecha_inicio: string | null; fecha_fin: string | null } | null;
  abierto_huella: string | null;
  catalogos: CatalogosDesignacion;
  reincorporables: Reincorporable[];
  puede_escribir: boolean;
};
export type DesignacionDocenteForm = {
  cargo: string;
  dedicacion: string;
  tipo_designacion: string;
  ad_honorem: string;
  fecha_desde: string;
  fecha_hasta: string;
  estado: string;
  funcion_no_docente: boolean;
  texto_funcion_no_docente: string;
  observaciones: string;
};
export type RegistroDesignacion = DesignacionDocenteForm & { abierto_huella: string | null } & (
    | { camino: "reincorporar"; cuil: string; huella: string }
    | { camino: "cuil_existente"; cuil: string; departamento_origen: string; cuil_alta: string }
    | { camino: "cuil_local"; cuil_alta: string }
  );

// E4-09: carga rápida integral (Excel con hojas Docentes y Designaciones). Revisión y carga por multipart.
export type FilaRevision = Record<string, string | number | null>;
export type RevisionIntegral = {
  avisos: string[];
  filas_docentes: number;
  filas_designaciones: number;
  docentes_nuevos: number;
  docentes_existentes: number;
  designaciones_nuevas: number;
  designaciones_omitidas: number;
  designaciones_detectadas: number;
  errores_docentes: number;
  errores_designaciones: number;
  errores: number;
  sin_errores: boolean;
  docentes: FilaRevision[];
  designaciones: FilaRevision[];
  huella: string;
};
export type ResultadoIntegral = {
  mensaje: string;
  tono: "success" | "warning";
  errores: number;
  detalle: Record<string, string | number | null>[];
  errores_detalle: string[];
};

async function multipart<T>(path: string, datos: unknown, archivo: File): Promise<T> {
  const form = new FormData();
  form.append("datos", JSON.stringify(datos));
  form.append("archivo", archivo);
  return enviarFormulario<T>(path, form);
}

async function enviarFormulario<T>(path: string, form: FormData): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/docentes${path}`, { method: "POST", body: form, cache: "no-store", credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "NETWORK", UNREACHABLE);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE);
  }
  return data as T;
}

export const docentesApi = {
  overview: () => call<DocentesOverview>(""),
  prestables: () => call<{ docentes: OtroDepartamento[] }>("/prestables"),
  ficha: (cuil: string) => post<Ficha>("/ficha", { cuil }),
  plantel: (periodo_id: number | null) => post<Plantel>("/plantel", { periodo_id }),
  equipos: (periodo_id: number | null) => post<Equipos>("/equipos", { periodo_id }),
  resumen: (cuil: string, periodo_id: number | null) => post<Resumen>("/resumen", { cuil, periodo_id }),
  estadoConsulta: (cuil: string, periodo_id: number, estado: string) =>
    post<EstadoGuardado>("/resumen/estado-consulta", { cuil, periodo_id, estado }),
  mensajeConsulta: (cuil: string, periodo_id: number) => post<MensajeConsulta>("/resumen/mensaje", { cuil, periodo_id }),
  verificarCuil: (cuil: string) => post<VerificacionCuil>("/verificar-cuil", { cuil }),
  designacionContexto: () => post<ContextoDesignacion>("/designacion/contexto", {}),
  designacionDuplicado: (body: DesignacionDocenteForm & { cuil: string }) =>
    post<{ duplicada: boolean }>("/designacion/duplicado", body),
  // 6A-B3: acto administrativo opcional, misma semántica que el alta de Designaciones. "Cargar un nuevo acto ahora"
  // viaja por multipart (PDF opcional); repositorio / pendiente por JSON. Sin acto = flujo certificado.
  registrarDesignacion: (body: RegistroDesignacion, acto?: ActoConfig) => {
    const form = acto ? formularioActoNuevo(body, acto) : null;
    if (form) return enviarFormulario<WriteResult & { avisos?: string[] }>("/designacion/acto-nuevo", form);
    // "pendiente" no viaja: el cuerpo queda igual al del flujo certificado (FastAPI lo trata igual que sin acto).
    const conActo = acto && acto.modo !== "pendiente" ? { ...body, acto: { modo: acto.modo, documento_id: acto.documento_id } } : body;
    return post<WriteResult & { avisos?: string[] }>("/designacion", conActo);
  },
  alta: (body: DocenteForm & { fecha_alta: string }) => post<WriteResult>("/alta", body),
  editar: (
    body: DocenteForm & {
      cuil_original: string;
      huella: string;
      estado: string;
      tipo_docente: string;
    }
  ) => post<WriteResult>("/editar", body),
  eliminar: (body: { cuil: string; huella: string; confirmar: boolean; integral: boolean }) =>
    post<WriteResult>("/eliminar", body),
  prestado: (body: {
    flujo: "selector" | "cuil_existente";
    cuil: string;
    departamento_origen: string;
    cuil_alta?: string;
  }) => post<WriteResult>("/prestado", body),
  finalizarPrestamo: (body: {
    cuil: string;
    huella: string;
    fecha_fin: string;
    observaciones: string;
    confirmar: boolean;
  }) => post<WriteResult>("/finalizar-prestamo", body),
  repararCuil: (body: { cuil: string; huella: string; cuil_huerfano: string; confirmar: boolean }) =>
    post<WriteResult>("/reparar-cuil", body),
  cargaPreview: (texto: string) => post<CargaPreview>("/carga-rapida/previsualizar", { texto }),
  carga: (texto: string, confirmar_duplicados: boolean) =>
    post<WriteResult>("/carga-rapida", { texto, confirmar_duplicados }),
  revisarIntegral: (archivo: File) => multipart<RevisionIntegral>("/carga-integral/previsualizar", {}, archivo),
  cargarIntegral: (archivo: File, datos: { confirmar: boolean; actualizar_existentes: boolean; huella: string }) =>
    multipart<ResultadoIntegral>("/carga-integral", datos, archivo),
  async modeloIntegral(filas_docentes: number, filas_designaciones: number): Promise<Blob> {
    let response: Response;
    try {
      response = await fetch("/api/docentes/carga-integral/modelo", {
        method: "POST",
        cache: "no-store",
        credentials: "same-origin",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ filas_docentes, filas_designaciones }),
      });
    } catch {
      throw new ApiError(0, "NETWORK", UNREACHABLE);
    }
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new ApiError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE);
    }
    return response.blob();
  },
  async modeloExcel(): Promise<Blob> {
    let response: Response;
    try {
      response = await fetch("/api/docentes/modelo-excel", {
        cache: "no-store",
        credentials: "same-origin",
      });
    } catch {
      throw new ApiError(0, "NETWORK", UNREACHABLE);
    }
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new ApiError(
        response.status,
        data?.error?.code ?? "ERROR",
        data?.error?.message ?? UNREACHABLE
      );
    }
    return response.blob();
  },
};

// normalizar_clave certificado: MAYÚSCULAS + espacios colapsados (sin quitar tildes); búsqueda por subcadena.
export const normalizarClave = (v: unknown) =>
  v === null || v === undefined ? "" : String(v).trim().toUpperCase().split(/\s+/).filter(Boolean).join(" ");

export function filtrarPorTexto<T extends Record<string, unknown>>(
  filas: T[],
  texto: string,
  columnas: (keyof T)[]
): T[] {
  const q = normalizarClave(texto);
  if (!q) return filas;
  return filas.filter((f) =>
    normalizarClave(columnas.map((c) => (f[c] === null || f[c] === undefined ? "" : String(f[c]))).join(" ")).includes(q)
  );
}

// B12A (b12a/posgrado.py): nivel canónico para preseleccionar el formulario de edición; no reconocido -> "".
const POSGRADO_SINONIMOS: Record<string, string[]> = {
  Doctor: ["doctor", "doctora", "doctorado"],
  "Magíster": ["magister", "maestria", "master"],
  Especialista: ["especialista", "especializacion"],
};
const fold = (t: string) =>
  t.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().split(/\s+/).filter(Boolean).join(" ");
export const nivelPosgradoNormalizado = (v: string | null) => {
  const key = fold(v ?? "");
  if (!key) return "";
  for (const [nivel, sinonimos] of Object.entries(POSGRADO_SINONIMOS)) {
    if (key === fold(nivel) || sinonimos.includes(key)) return nivel;
  }
  return "";
};

// limpiar_cuil certificado (vista previa en pantalla; el backend vuelve a calcularlo).
export const limpiarCuil = (v: string) => {
  let t = v.trim();
  if (["nan", "none", "nat"].includes(t.toLowerCase())) t = "";
  if (t.endsWith(".0")) t = t.slice(0, -2);
  return t.replace(/ /g, "");
};

// nombre_completo certificado.
export const nombreCompleto = (apellido: string, nombres: string) => {
  const a = apellido.trim();
  const n = nombres.trim();
  return a && n ? `${a}, ${n}` : a || n;
};

export const today = () => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};
