// Cliente del aviso global de contexto histórico (E4-01, D-AN9). Sin parámetros: el backend decide con la sesión.
import { ApiError } from "@/lib/auth";

export type AvisoContexto = { texto: string };
export type ContextoPeriodo = { aviso: AvisoContexto | null };

const UNREACHABLE = "No se pudo conectar con el servidor. Reintentá en unos instantes.";

export const contextoApi = {
  periodo: async (): Promise<ContextoPeriodo> => {
    let response: Response;
    try {
      response = await fetch("/api/contexto/periodo", { cache: "no-store", credentials: "same-origin" });
    } catch {
      throw new ApiError(0, "NETWORK", UNREACHABLE);
    }
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(response.status, data?.error?.code ?? "ERROR", data?.error?.message ?? UNREACHABLE);
    }
    return data as ContextoPeriodo;
  },
};
