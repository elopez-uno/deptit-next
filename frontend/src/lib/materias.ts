// Tipos y llamadas del módulo Materias al proxy /api/materias. La institución la decide la sesión en el backend.
import { ApiError, type Named } from "@/lib/auth";

export type Row = Record<string, string | number | null>;
export type Opcion = { etiqueta: string; id: number | null };

export type Carrera = {
  id: number;
  escuela: string | null;
  codigo: string | null;
  nombre: string | null;
  titulo_otorga: string | null;
  plan_version: string | null;
  duracion: string | null;
  estado: string | null;
  observaciones: string | null;
  huella: string;
};

export type MateriasOverview = {
  contexto: { institucion: Named; departamento: Named | null; aviso: string | null };
  carreras: Carrera[];
  escuelas: string[];
  conteos: { carreras: number; materias: number };
  opciones_activas: Opcion[];
  opciones_todas: Opcion[];
  catalogos: {
    anios: string[];
    cuatrimestres: string[];
    duraciones: string[];
    dictados: string[];
    estados_carrera: string[];
    estados_materia: string[];
    tipos_opcion: string[];
    estados_opcion: string[];
    comparticion: [string, string][];
    plan_vigente: string;
  };
  permisos: { puede_escribir: boolean; puede_borrar: boolean };
};

export type WriteResult = { mensaje: string; tono: "success" | "warning" | "info"; id?: number; detalle?: Row[] };

export type MateriaForm = {
  codigo: string;
  asignatura: string;
  anio: string;
  cuatrimestre: string;
  dictado: string;
  carga_semanal: number;
  carga_total: number;
  duracion: string;
  estado: string;
  observaciones: string;
  orden: number;
};

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/materias${path}`, {
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
    throw new ApiError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE);
  }
  return data as T;
}

export const post = <T,>(path: string, body: unknown) =>
  call<T>(`/${path}`, { method: "POST", body: JSON.stringify(body) });

export const materiasApi = {
  overview: () => call<MateriasOverview>(""),
  async modeloExcel(): Promise<Blob> {
    let response: Response;
    try {
      response = await fetch("/api/materias/opciones/modelo-excel", { cache: "no-store", credentials: "same-origin" });
    } catch {
      throw new ApiError(0, "NETWORK", UNREACHABLE);
    }
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new ApiError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE);
    }
    return response.blob();
  },
};

export async function fileToBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

export function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export const pick = (opts: string[], v: string | null | undefined, def?: string) =>
  v !== null && v !== undefined && opts.includes(v) ? v : (def ?? opts[0]);
