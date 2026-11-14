"use client";

// Módulo Materias (B13-FIX02, entry l. 68554-70014): fuente única de planes de la institución.
// Tres submódulos aprobados que agrupan las 8 pestañas certificadas en su orden original.
// La UI solo oculta lo que el rol no puede hacer: FastAPI vuelve a autorizar cada escritura.
import { useCallback, useEffect, useState } from "react";
import { Spinner } from "@/components/brand";
import { Details, type Feedback, FeedbackBox } from "@/components/module-ui";
import { CarrerasTab } from "@/components/materias-carreras";
import { EditarMateriaTab, TotalesTab, UnicasTab } from "@/components/materias-edicion";
import { OptativasTab } from "@/components/materias-optativas";
import { AgregarTab, CargaRapidaPlanTab, PlanTab } from "@/components/materias-plan";
import { Metric, type TabProps } from "@/components/materias-shared";
import { ApiError } from "@/lib/auth";
import { type MateriasOverview, materiasApi } from "@/lib/materias";

const SUBMODULOS = [
  { key: "carreras", label: "Carreras / Planes", tabs: [{ key: "carreras", label: "Unidades académicas y carreras" }] },
  {
    key: "plan",
    label: "Plan de estudio / Materias",
    tabs: [
      { key: "plan", label: "Plan de estudio" },
      { key: "agregar", label: "Agregar materia" },
      { key: "carga", label: "Carga rápida de plan" },
      { key: "editar", label: "Editar / eliminar materia" },
      { key: "totales", label: "Materias totales" },
      { key: "unicas", label: "Materias únicas" },
    ],
  },
  { key: "optativas", label: "Optativas / Electivas", tabs: [{ key: "optativas", label: "Optativas / Electivas" }] },
] as const;

const PANELS: Record<string, (p: TabProps) => React.ReactElement> = {
  carreras: CarrerasTab,
  plan: PlanTab,
  agregar: AgregarTab,
  carga: CargaRapidaPlanTab,
  editar: EditarMateriaTab,
  totales: TotalesTab,
  unicas: UnicasTab,
  optativas: OptativasTab,
};

export function MateriasModule({ onAuthError }: { onAuthError: (e: unknown) => void }) {
  const [data, setData] = useState<MateriasOverview | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [sub, setSub] = useState<string>("carreras");
  const [tab, setTab] = useState<string>("carreras");
  const [feedback, setFeedback] = useState<Feedback>(null);

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
      setData(await materiasApi.overview());
      setLoadError(null);
    } catch (err) {
      setLoadError(handle(err));
    } finally {
      setLoading(false);
    }
  }, [handle]);

  useEffect(() => {
    let cancelled = false;
    materiasApi
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
  }

  if (loading && !data) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando planes de estudio…
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

  const actual = SUBMODULOS.find((s) => s.key === sub) ?? SUBMODULOS[0];
  const Panel = PANELS[tab] ?? PANELS[actual.tabs[0].key];
  const inst = data.contexto.institucion.nombre;

  return (
    <div>
      <div className="mb-5">
        <p className="text-sm text-slate-500">{inst}</p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">Módulo Materias</h2>
      </div>
      {data.contexto.aviso && <FeedbackBox feedback={{ tone: "warning", text: data.contexto.aviso }} />}
      <FeedbackBox
        feedback={{
          tone: "success",
          text: `Estás trabajando sobre la fuente única de planes de estudio de ${inst}. Cualquier usuario de esta universidad ve y edita el mismo archivo de planes.`,
        }}
      />
      <div className="mb-4">
        <Details summary="Estado de planes compartidos de esta universidad">
          <p className="text-sm font-semibold text-slate-800">Fuente única de planes de estudio</p>
          {data.conteos.carreras > 0 || data.conteos.materias > 0 ? (
            <FeedbackBox feedback={{ tone: "success", text: "La app usa un único archivo de planes para esta universidad." }} />
          ) : (
            <FeedbackBox feedback={{ tone: "warning", text: "Todavía no hay planes cargados en la fuente única de esta universidad." }} />
          )}
          <div className="grid gap-3 sm:grid-cols-3">
            <Metric label="Carreras" value={data.conteos.carreras} />
            <Metric label="Materias" value={data.conteos.materias} />
            <Metric label="Estado" value={data.conteos.carreras > 0 || data.conteos.materias > 0 ? "OK" : "Sin datos"} />
          </div>
        </Details>
      </div>
      <FeedbackBox
        feedback={{
          tone: "info",
          text:
            "Este módulo carga planes de estudio por carrera. Primero registrás la carrera y su unidad académica; después cargás " +
            "las materias que integran ese plan. No hay importación automática desde Excel.",
        }}
      />

      <div role="tablist" aria-label="Submódulos de Materias" className="mb-3 flex flex-wrap gap-2">
        {SUBMODULOS.map((s) => (
          <button
            key={s.key}
            role="tab"
            aria-selected={sub === s.key}
            onClick={() => {
              setSub(s.key);
              setTab(s.tabs[0].key);
              setFeedback(null);
            }}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
              sub === s.key ? "bg-brand-700 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>
      {actual.tabs.length > 1 && (
        <div role="tablist" aria-label={actual.label} className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200">
          {actual.tabs.map((t) => (
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
      )}
      {actual.tabs.length === 1 && <div className="mb-6 border-b border-slate-200" />}

      {feedback && <FeedbackBox feedback={feedback} />}
      {loadError && <FeedbackBox feedback={{ tone: "error", text: loadError.message }} />}
      <div role="tabpanel">
        <Panel data={data} onDone={afterWrite} onError={handle} />
      </div>
    </div>
  );
}
