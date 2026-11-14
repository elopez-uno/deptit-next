"use client";

// Módulo Designaciones (B13-FIX02, entry l. 63392-64858): las 5 pestañas certificadas en su orden original.
// Las pestañas 2 a 5 operan siempre sobre el período abierto; la 1 permite ver cualquier período.
// La UI solo oculta lo que el rol no puede hacer: FastAPI vuelve a autorizar cada escritura.
import { useCallback, useEffect, useState } from "react";
import { Spinner } from "@/components/brand";
import { type Feedback, FeedbackBox } from "@/components/module-ui";
import { CargaRapidaTab, CorreccionTab } from "@/components/designaciones-correccion";
import { AltaTab, ModificarTab } from "@/components/designaciones-edicion";
import { PeriodoTab } from "@/components/designaciones-periodo";
import type { TabProps } from "@/components/designaciones-shared";
import { ApiError } from "@/lib/auth";
import { type Overview, designacionesApi } from "@/lib/designaciones";

const TABS = [
  { key: "periodo", label: "📋 Designaciones del período" },
  { key: "alta", label: "➕ Nueva designación" },
  { key: "modificar", label: "✏️ Modificar / finalizar designación" },
  { key: "error", label: "🛠️ Editar / eliminar por error" },
  { key: "carga", label: "📥 Carga rápida" },
] as const;

const PANELS: Record<string, (p: TabProps) => React.ReactElement> = {
  periodo: PeriodoTab,
  alta: AltaTab,
  modificar: ModificarTab,
  error: CorreccionTab,
  carga: CargaRapidaTab,
};

export function DesignacionesModule({ onAuthError }: { onAuthError: (e: unknown) => void }) {
  const [data, setData] = useState<Overview | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<string>("periodo");
  const [feedback, setFeedback] = useState<Feedback>(null);
  // Se incrementa después de cada escritura: las pestañas releen sus datos (equivale al st.rerun certificado).
  const [version, setVersion] = useState(0);

  const handle = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) onAuthError(err);
      return err instanceof ApiError ? err : new ApiError(0, "ERROR", "No se pudo completar la operación.");
    },
    [onAuthError]
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await designacionesApi.overview());
      setLoadError(null);
    } catch (err) {
      setLoadError(handle(err));
    } finally {
      setLoading(false);
    }
  }, [handle]);

  useEffect(() => {
    let cancelled = false;
    designacionesApi
      .overview()
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setLoadError(handle(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [handle]);

  async function afterWrite(result: Feedback) {
    setFeedback(result);
    await load();
    setVersion((v) => v + 1);
  }

  if (loading && !data) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando designaciones…
      </div>
    );
  }
  if (loadError && !data) {
    const scope = loadError.code.startsWith("SCOPE");
    return (
      <div className={`rounded-2xl border px-6 py-8 text-sm ${scope ? "border-slate-200 bg-white text-slate-700" : "border-red-200 bg-red-50 text-red-700"}`}>
        <p>{loadError.message}</p>
        {!scope && (
          <button onClick={load} className="mt-4 rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800">
            Reintentar
          </button>
        )}
      </div>
    );
  }
  if (!data) return null;

  const Panel = PANELS[tab] ?? PANELS.periodo;
  const abierto = data.abierto;

  return (
    <div>
      <div className="mb-5">
        <p className="text-sm text-slate-500">
          {data.contexto.institucion.nombre} · {data.contexto.departamento.nombre}
        </p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">📑 Módulo Designaciones</h2>
      </div>
      {abierto ? (
        <FeedbackBox
          feedback={{
            tone: "success",
            text: `${data.historico_abierto ? "Foto de cierre histórica abierta" : "Período abierto actual"}: ${abierto.nombre} (${abierto.fecha_inicio} al ${abierto.fecha_fin})`,
          }}
        />
      ) : (
        <FeedbackBox
          feedback={{
            tone: "warning",
            text: "No hay período abierto. Creá uno en el módulo Períodos para cargar o modificar designaciones.",
          }}
        />
      )}

      <div role="tablist" aria-label="Pestañas de Designaciones" className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => {
              setTab(t.key);
              setFeedback(null);
            }}
            className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-sm transition ${
              tab === t.key ? "border-brand-600 font-medium text-brand-800" : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {feedback && <FeedbackBox feedback={feedback} />}
      {loadError && <FeedbackBox feedback={{ tone: "error", text: loadError.message }} />}
      <div role="tabpanel">
        <Panel data={data} version={version} onDone={afterWrite} onError={handle} />
      </div>
    </div>
  );
}
