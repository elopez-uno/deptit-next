// Tipos y llamadas del módulo Administración SaaS al proxy /api/saas. Solo superadmin: FastAPI vuelve a autorizar CADA
// request (B10 saas.read / saas.admin / saas.delete). Una acción = un endpoint con su esquema exacto; los textos visibles
// llegan del backend (`ui`, textos certificados). Nunca viajan salt ni hash; las contraseñas solo van en el cuerpo POST.
import { ApiError } from "@/lib/auth";
import type { Tabla } from "@/lib/analisis";

export type Dependencias = { usuarios: number; departamentos: number; registros: number; tablas: number };

export type Institucion = {
  id: number;
  nombre: string;
  estado: string | null;
  plan: string | null;
  max_usuarios: number | null;
  fecha_vencimiento: string | null;
  estado_pago: string | null;
  suscripcion: string | null;
  observaciones: string | null;
  activos: number;
  dependencias: Dependencias;
  eliminable: boolean;
  ficha: Tabla;
};

export type Departamento = {
  id: number;
  institucion_id: number;
  institucion: string | null;
  nombre: string;
  estado: string | null;
  observaciones: string | null;
  usuarios: number;
  dependencias: Dependencias;
  eliminable: boolean;
  ficha: Tabla;
};

export type Usuario = {
  id: number;
  institucion_id: number | null;
  departamento_id: number | null;
  nombre: string | null;
  email: string;
  rol: string;
  estado: string | null;
  observaciones: string | null;
  etiqueta: string;
  ficha: Tabla;
};

type Expander = { titulo: string; [k: string]: string };

export type Textos = {
  titulo: string;
  pestanas: string[];
  instituciones: { subtitulo: string; crear: Expander; cupo: Expander; eliminar: Expander };
  departamentos: {
    subtitulo: string;
    institucion: string;
    planes: { titulo: string; metricas: string[]; sin_planes: string };
    crear: Expander;
    editar: Expander;
    eliminar: Expander;
  };
  usuarios: { subtitulo: string; crear: Expander; estado: Expander; editar: Expander; eliminar: Expander };
  comercial: { subtitulo: string; vacio: string; editar: Expander; criterio: { titulo: string; texto: string[] } };
  credenciales: { info: string; cuentas: string[] };
  excel: string;
};

export type Catalogos = {
  roles: string[];
  planes: string[];
  pagos: string[];
  suscripciones: string[];
  accesos: string[];
  estados_usuario: string[];
  estados_departamento: string[];
  sin_departamento: string;
  cupo: { min: number; max: number; default: number };
};

export type Overview = {
  ui: Textos;
  catalogos: Catalogos;
  actor_id: number | null;
  tablas: { instituciones: Tabla; departamentos: Tabla; usuarios: Tabla; uso: Tabla };
  instituciones: Institucion[];
  departamentos: Departamento[];
  usuarios: Usuario[];
};

export type Planes = { metricas: { label: string; valor: string }[]; aviso: string | null };
export type WriteResult = { mensaje: string; tono: "success" | "warning" | "info"; id?: number };
export type Archivo = { blob: Blob; nombre: string };

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

export class SaasError extends ApiError {
  constructor(status: number, code: string, message: string, public tone: "error" | "warning" | "info" = "error") {
    super(status, code, message);
  }
}

async function pedir(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`/api/saas${path}`, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new SaasError(0, "NETWORK", UNREACHABLE);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new SaasError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE, data?.error?.tone ?? "error");
  }
  return response;
}

async function post<T>(path: string, body: Record<string, unknown>): Promise<T> {
  return (await pedir(path, { method: "POST", body: JSON.stringify(body) })).json();
}

export const saasApi = {
  async overview(): Promise<Overview> {
    return (await pedir("")).json();
  },
  planes: (institucion_id: number) => post<Planes>("/planes", { institucion_id }),
  async excel(tabla: string, id: number | null): Promise<Archivo> {
    const response = await pedir("/descargas/excel", { method: "POST", body: JSON.stringify({ tabla, id }) });
    const disposition = response.headers.get("content-disposition") ?? "";
    const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
    const ascii = /filename="([^"]+)"/i.exec(disposition);
    const nombre = utf8 ? decodeURIComponent(utf8[1]) : ascii ? ascii[1] : "Administración_SaaS.xlsx";
    return { blob: await response.blob(), nombre };
  },
  // Instituciones
  crearInstitucion: (b: {
    nombre: string;
    max_usuarios: number;
    plan: string;
    fecha_vencimiento: string | null;
    estado_pago: string;
    suscripcion: string;
    estado: string;
    observaciones: string;
  }) => post<WriteResult>("/instituciones", b),
  cupo: (institucion_id: number, max_usuarios: number) => post<WriteResult>("/instituciones/cupo", { institucion_id, max_usuarios }),
  comercial: (b: {
    institucion_id: number;
    plan: string;
    max_usuarios: number;
    fecha_vencimiento: string | null;
    estado_pago: string;
    suscripcion: string;
    estado: string;
    observaciones: string;
  }) => post<WriteResult>("/instituciones/comercial", b),
  bloquear: (institucion_id: number) => post<WriteResult>("/instituciones/bloquear", { institucion_id }),
  desbloquear: (institucion_id: number) => post<WriteResult>("/instituciones/desbloquear", { institucion_id }),
  eliminarInstitucion: (institucion_id: number, confirmado: boolean, texto: string) =>
    post<WriteResult>("/instituciones/eliminar", { institucion_id, confirmado, texto }),
  // Departamentos
  crearDepartamento: (institucion_id: number, nombre: string, observaciones: string) =>
    post<WriteResult>("/departamentos", { institucion_id, nombre, observaciones }),
  editarDepartamento: (departamento_id: number, nombre: string, estado: string, observaciones: string) =>
    post<WriteResult>("/departamentos/editar", { departamento_id, nombre, estado, observaciones }),
  eliminarDepartamento: (departamento_id: number, confirmado: boolean) =>
    post<WriteResult>("/departamentos/eliminar", { departamento_id, confirmado }),
  // Usuarios
  crearUsuario: (b: {
    institucion_id: number;
    departamento_id: number | null;
    nombre: string;
    email: string;
    rol: string;
    password: string;
    password_confirmacion: string;
    estado: string;
    observaciones: string;
  }) => post<WriteResult>("/usuarios", b),
  estadoUsuario: (usuario_id: number, estado: string) => post<WriteResult>("/usuarios/estado", { usuario_id, estado }),
  editarUsuario: (b: {
    usuario_id: number;
    institucion_id: number | null;
    departamento_id: number | null;
    nombre: string;
    email: string;
    rol: string;
    estado: string;
    observaciones: string;
    password: string;
  }) => post<WriteResult>("/usuarios/editar", b),
  eliminarUsuario: (usuario_id: number, confirmado: boolean) => post<WriteResult>("/usuarios/eliminar", { usuario_id, confirmado }),
};
