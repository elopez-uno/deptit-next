"use client";

import { useState } from "react";
import { Spinner } from "@/components/brand";
import { ApiError, type ContextOptions, type Session, authApi } from "@/lib/auth";

const CONSOLIDADO = "consolidado";

// Selector de contexto con las reglas certificadas (sidebar_auth_context):
// superadmin elige institución y departamento; coordinación elige consolidado o un departamento activo.
export function ContextSwitcher({
  session,
  onChanged,
  onError,
}: {
  session: Session;
  onChanged: (s: Session) => void;
  onError: (e: unknown) => void;
}) {
  const [options, setOptions] = useState<ContextOptions | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { contexto } = session;
  const label =
    contexto.departamento?.nombre ??
    (contexto.vista === "consolidado" ? "Consolidado institucional" : "Sin ámbito");

  if (!contexto.seleccionable) {
    return (
      <div className="hidden max-w-xs rounded-lg bg-slate-50 px-3 py-1.5 text-right lg:block">
        <p className="truncate text-[11px] uppercase tracking-wider text-slate-400">
          {contexto.institucion?.nombre ?? "Sin institución"}
        </p>
        <p className="truncate text-sm font-medium text-slate-700">{label}</p>
      </div>
    );
  }

  async function toggle() {
    if (open) return setOpen(false);
    setError(null);
    setBusy(true);
    try {
      setOptions(await authApi.options());
      setOpen(true);
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  async function apply(body: Parameters<typeof authApi.setContext>[0]) {
    setBusy(true);
    setError(null);
    try {
      const updated = await authApi.setContext(body);
      onChanged(updated);
      if (options?.puede_elegir_institucion) setOptions(await authApi.options());
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) setError(err.message);
      else onError(err);
    } finally {
      setBusy(false);
    }
  }

  const depValue = contexto.departamento ? String(contexto.departamento.id) : CONSOLIDADO;

  return (
    <div className="relative">
      <button
        onClick={toggle}
        aria-expanded={open}
        className="flex max-w-xs items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-left text-sm transition hover:bg-slate-50"
      >
        <span className="min-w-0">
          <span className="block truncate text-[11px] uppercase tracking-wider text-slate-400">
            {contexto.institucion?.nombre ?? "Sin institución"}
          </span>
          <span className="block truncate font-medium text-slate-800">{label}</span>
        </span>
        {busy ? <Spinner className="h-4 w-4 text-slate-400" /> : <span className="text-slate-400">▾</span>}
      </button>

      {open && options && (
        <div className="absolute right-0 z-20 mt-2 w-80 rounded-xl border border-slate-200 bg-white p-4 shadow-xl">
          <p className="mb-3 text-sm font-semibold text-brand-950">Ámbito de trabajo</p>

          {options.puede_elegir_institucion && (
            <label className="mb-3 block">
              <span className="mb-1 block text-xs font-medium text-slate-500">Institución operativa</span>
              <select
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                value={contexto.institucion?.id ?? ""}
                disabled={busy}
                onChange={(e) => apply({ institucion_id: Number(e.target.value) })}
              >
                {options.instituciones.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.nombre}
                    {i.estado && i.estado !== "Activa" ? ` (${i.estado})` : ""}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              {options.permite_consolidado ? "Vista" : "Departamento operativo"}
            </span>
            <select
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={depValue}
              disabled={busy}
              onChange={(e) =>
                e.target.value === CONSOLIDADO
                  ? apply({ consolidado: true })
                  : apply({
                      institucion_id: contexto.institucion?.id ?? null,
                      departamento_id: Number(e.target.value),
                    })
              }
            >
              {options.permite_consolidado && (
                <option value={CONSOLIDADO}>Consolidado institucional</option>
              )}
              {options.departamentos.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.nombre}
                  {d.estado && d.estado !== "Activo" ? ` (${d.estado})` : ""}
                </option>
              ))}
            </select>
          </label>

          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          <button
            onClick={() => setOpen(false)}
            className="mt-4 w-full rounded-lg bg-slate-100 py-1.5 text-sm text-slate-700 hover:bg-slate-200"
          >
            Cerrar
          </button>
        </div>
      )}
    </div>
  );
}
