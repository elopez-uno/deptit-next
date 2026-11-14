// Tipos y llamadas del cliente al proxy /api/auth. Nunca maneja tokens: la sesión es una cookie HttpOnly.

export type Named = { id: number; nombre: string | null };

export type Modulo = {
  clave: string;
  nombre: string;
  puede_escribir: boolean;
  puede_borrar: boolean;
};

export type Session = {
  usuario: {
    id: number;
    nombre: string | null;
    email: string;
    rol: string;
    rol_original: string | null;
    modo_solo_lectura_comercial: boolean;
    es_superadmin: boolean;
  };
  acceso: "normal" | "read_only" | "blocked";
  pertenencia: { institucion: Named | null; departamento: Named | null };
  contexto: {
    institucion_encabezado: string;
    institucion: Named | null;
    departamento: Named | null;
    vista: "departamento" | "consolidado" | "sin_ambito";
    problema: string | null;
    seleccionable: boolean;
  };
  modulos: Modulo[];
  sesion: {
    inactividad_max_segundos: number;
    expira_por_inactividad_en: number;
    expira_absoluta_en: number;
  };
};

export type ContextOptions = {
  puede_elegir_institucion: boolean;
  permite_consolidado: boolean;
  instituciones: (Named & { estado: string | null })[];
  departamentos: (Named & { estado: string | null })[];
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string
  ) {
    super(message);
  }
}

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/auth/${path}`, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "NETWORK", UNREACHABLE);
  }
  if (response.status === 204) return undefined as T;
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

export const authApi = {
  login: (email: string, password: string) =>
    call<Session>("login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => call<Session>("me"),
  logout: () => call<void>("logout", { method: "POST" }),
  options: () => call<ContextOptions>("context/options"),
  setContext: (body: {
    institucion_id?: number | null;
    departamento_id?: number | null;
    consolidado?: boolean;
  }) => call<Session>("context", { method: "PUT", body: JSON.stringify(body) }),
};

export const ROLE_LABELS: Record<string, string> = {
  superadmin: "Superadministrador",
  coordinador_institucional: "Coordinación institucional",
  usuario_departamento: "Usuario de departamento",
  solo_lectura: "Solo lectura",
};

export const roleLabel = (rol: string | null | undefined) =>
  (rol && ROLE_LABELS[rol]) ?? rol ?? "-";

// Avisos al volver al login (mismos textos que B12G), según el código de fin de sesión.
const EXPIRED = new Set(["IDLE_TIMEOUT", "ABSOLUTE_TIMEOUT"]);
const REVOKED = new Set([
  "USER_DELETED",
  "USER_INACTIVE",
  "IDENTITY_AMBIGUOUS",
  "CREDENTIALS_CHANGED",
  "IDENTITY_CHANGED",
  "COMMERCIAL_BLOCKED",
  "COMMERCIAL_STATE_CHANGED",
]);

export function noticeParam(code: string): string | null {
  if (code === "NO_SESSION") return null;
  if (EXPIRED.has(code)) return "expirada";
  if (REVOKED.has(code)) return "revocada";
  return "invalida";
}

export const NOTICES: Record<string, string> = {
  expirada: "Tu sesión expiró. Volvé a ingresar.",
  revocada:
    "Tu sesión se cerró porque cambiaron tus datos de acceso o los de tu institución. Volvé a ingresar.",
  invalida: "Tu sesión no es válida. Volvé a ingresar.",
  cerrada: "Cerraste la sesión correctamente.",
};
