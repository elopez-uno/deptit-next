"use client";

// Módulo Investigación (B13-FIX02, entry l. 64859-65647): las 8 pestañas certificadas en su orden original.
// Catálogo institucional de proyectos; cada departamento asigna sus docentes en el período ABIERTO (actual o histórico
// abierto por excepción). La UI solo oculta lo que el rol no puede hacer: FastAPI vuelve a autorizar cada escritura.
import { useCallback, useEffect, useState } from "react";
import { Spinner } from "@/components/brand";
import { AsignacionesTab, AsignarTab } from "@/components/investigacion-asignar";
import { CargaTab } from "@/components/investigacion-carga";
import { BajasTab, EditarTab } from "@/components/investigacion-edicion";
import { HistorialTab, NuevoTab, VigentesTab } from "@/components/investigacion-proyectos";
import { Aviso, TablaLibre, type TabProps } from "@/components/investigacion-shared";
import { type Feedback, FeedbackBox } from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import { type AlertaPostAccion, type Capacidad, type Fila, type Overview, g, investigacionApi, post, tomarAlerta } from "@/lib/investigacion";

const TABS = [
  { key: "vigentes", label: "📚 Proyectos vigentes" },
  { key: "nuevo", label: "➕ Nuevo proyecto" },
  { key: "asignar", label: "👥 Asignar docentes" },
  { key: "asignaciones", label: "📋 Asignaciones" },
  { key: "historial", label: "🕘 Historial" },
  { key: "editar", label: "✏️ Editar" },
  { key: "bajas", label: "⏸️ Bajas, suspensión, archivo y eliminación" },
  { key: "carga", label: "📥 Carga rápida" },
] as const;

const PANELS: Record<string, (p: TabProps) => React.ReactElement> = {
  vigentes: VigentesTab,
  nuevo: NuevoTab,
  asignar: AsignarTab,
  asignaciones: AsignacionesTab,
  historial: HistorialTab,
  editar: EditarTab,
  bajas: BajasTab,
  carga: CargaTab,
};

// render_alertas_exceso_proyectos_v184 (l. 40634): docentes del departamento con exceso de horas de proyectos.
function AlertasExceso({ version, onError }: { version: number; onError: (e: unknown) => ApiError }) {
  const [excesos, setExcesos] = useState<Fila[]>([]);
  useEffect(() => {
    let cancel = false;
    post<{ excesos: Fila[] }>("alertas", {})
      .then((r) => !cancel && setExcesos(r.excesos))
      .catch((e) => !cancel && onError(e));
    return () => {
      cancel = true;
    };
  }, [version, onError]);
  if (!excesos.length) return null;
  return (
    <div className="space-y-2">
      <Aviso
        feedback={{
          tone: "error",
          text: `⚠️ Alerta de horas en Investigación: hay ${excesos.length} docente/s cuyas horas de Investigación + Extensión superan el remanente disponible después de sus comisiones y horas no lectivas. La situación se mantiene señalada como exceso, pero el sistema permite registrar o modificar asignaciones igualmente.`,
        }}
      />
      <TablaLibre rows={excesos} />
    </div>
  );
}

// render_alerta_post_accion_proyecto_v187 (l. 40751): balance real una sola vez después de una edición.
function AlertaPostAccion({ data, version }: { data: Overview; version: number }) {
  const [info, setInfo] = useState<{ a: AlertaPostAccion; cap: Capacidad; detalle: Fila[] } | null>(null);
  useEffect(() => {
    const a = tomarAlerta();
    if (!a || !data.abierto || a.periodo_id !== data.abierto.id || !a.tipo_modulo.startsWith("invest")) return;
    post<{ vigente: boolean; capacidad: Capacidad; detalle: Fila[] }>("post-accion", { cuil: a.cuil, periodo_id: a.periodo_id })
      .then((r) => r.vigente && setInfo({ a, cap: r.capacidad, detalle: r.detalle }))
      .catch(() => undefined);
  }, [version, data.abierto]);
  if (!info) return null;
  const { a, cap } = info;
  const texto =
    `${a.accion} registrada para ${a.docente || a.cuil}. Antes de esta acción tenía ${g(a.horas_disponibles_antes)} hs disponibles para nuevos proyectos. ` +
    `El valor registrado en esta acción fue de ${g(a.horas_accion)} hs semanales. Capacidad total actual para Investigación + Extensión: ` +
    `${g(cap.capacidad_total_proyectos)} hs (después de comisiones y horas no lectivas). Total actual en Investigación: ${g(cap.horas_investigacion)} hs · ` +
    `Total actual en Extensión: ${g(cap.horas_extension)} hs · Excedente actual: ${g(cap.exceso_proyectos)} hs.`;
  return (
    <div className="space-y-2">
      <Aviso feedback={{ tone: cap.exceso_proyectos > 1e-9 ? "warning" : "info", text: `${cap.exceso_proyectos > 1e-9 ? "⚠️" : "ℹ️"} ${texto}` }} />
      {info.detalle.length > 0 && (
        <>
          <p className="text-sm font-semibold">Detalle actual por proyecto</p>
          <TablaLibre rows={info.detalle} />
        </>
      )}
    </div>
  );
}

export function InvestigacionModule({ onAuthError }: { onAuthError: (e: unknown) => void }) {
  const [data, setData] = useState<Overview | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<string>("vigentes");
  const [feedback, setFeedback] = useState<Feedback>(null);
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
      setData(await investigacionApi.overview());
      setLoadError(null);
    } catch (err) {
      setLoadError(handle(err));
    } finally {
      setLoading(false);
    }
  }, [handle]);

  useEffect(() => {
    let cancelled = false;
    investigacionApi
      .overview()
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setLoadError(handle(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [handle]);

  // _tabs_con_default_v217: después de un alta se vuelve a la pestaña que indicó la acción.
  async function afterWrite(result: Feedback, pestana?: string) {
    setFeedback(result);
    if (pestana && PANELS[pestana]) setTab(pestana);
    await load();
    setVersion((v) => v + 1);
  }

  if (loading && !data) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando investigación…
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

  const Panel = PANELS[tab] ?? PANELS.vigentes;

  return (
    <div>
      <div className="mb-5">
        <p className="text-sm text-slate-500">
          {data.contexto.institucion.nombre} · {data.contexto.departamento.nombre}
        </p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">🔬 Investigación</h2>
      </div>
      <FeedbackBox
        feedback={{
          tone: "info",
          text: "Cada proyecto se registra una sola vez para toda la institución y queda visible en todos los departamentos. Cada departamento asigna sus propios docentes, roles y horas. La renovación entre cuatrimestres compara las fechas reales del proyecto con las del período académico.",
        }}
      />
      {data.abierto && (
        <div className="mb-4 space-y-3">
          <AlertasExceso version={version} onError={handle} />
          <AlertaPostAccion data={data} version={version} />
        </div>
      )}

      <div role="tablist" aria-label="Pestañas de Investigación" className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200">
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

      {feedback && (
        <div className="whitespace-pre-line">
          <FeedbackBox feedback={feedback} />
        </div>
      )}
      {loadError && <FeedbackBox feedback={{ tone: "error", text: loadError.message }} />}
      <div role="tabpanel">
        <Panel data={data} version={version} onDone={afterWrite} onError={handle} />
      </div>
    </div>
  );
}
