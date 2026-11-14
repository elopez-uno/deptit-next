"use client";

// Módulo Comisiones (B13-FIX02, entry l. 70015-72307): las 8 pestañas certificadas en su orden original.
// Abrir, Carga rápida y Modificación operan sobre el período actual abierto; Editar / eliminar sobre el período abierto
// habilitado para corrección; Inscriptos y Sedes no tienen compuerta de período.
// La UI solo oculta lo que el rol no puede hacer: FastAPI vuelve a autorizar cada escritura.
import { useCallback, useEffect, useState } from "react";
import { Spinner } from "@/components/brand";
import { AbrirTab } from "@/components/comisiones-abrir";
import { CargaRapidaTab } from "@/components/comisiones-carga";
import { EdicionTab } from "@/components/comisiones-edicion";
import { InscriptosTab } from "@/components/comisiones-inscriptos";
import { ModificacionTab } from "@/components/comisiones-modificacion";
import { AlertasTab, PeriodoTab } from "@/components/comisiones-periodo";
import { SedesTab } from "@/components/comisiones-sedes";
import type { TabProps } from "@/components/comisiones-shared";
import { type Feedback, FeedbackBox } from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import { type Overview, comisionesApi } from "@/lib/comisiones";

const TABS = [
  { key: "periodo", label: "📋 Comisiones del período" },
  { key: "abrir", label: "➕ Abrir comisión" },
  { key: "inscriptos", label: "👥 Inscriptos" },
  { key: "modificacion", label: "🔁 Modificación de asignaciones" },
  { key: "carga", label: "📥 Carga rápida" },
  { key: "alertas", label: "🚨 Alertas" },
  { key: "edicion", label: "✏️ Editar / eliminar" },
  { key: "sedes", label: "🏫 Sedes institucionales" },
] as const;

const PANELS: Record<string, (p: TabProps) => React.ReactElement> = {
  periodo: PeriodoTab,
  abrir: AbrirTab,
  inscriptos: InscriptosTab,
  modificacion: ModificacionTab,
  carga: CargaRapidaTab,
  alertas: AlertasTab,
  edicion: EdicionTab,
  sedes: SedesTab,
};

// Los textos certificados usan **negrita** de Markdown: se muestran sin los asteriscos.
const sinMd = (t: string) => t.replaceAll("**", "");

function Encabezado({ data }: { data: Overview }) {
  const avisos: NonNullable<Feedback>[] = [];
  const actual = data.actual;
  if (actual) {
    avisos.push({
      tone: "info",
      text: `Período actual para comisiones: ${actual.nombre} (${actual.fecha_inicio} al ${actual.fecha_fin}).`,
    });
  }
  if (!data.puede_operar) {
    if (data.historico_abierto && data.puede_corregir && data.abierto) {
      avisos.push({
        tone: "warning",
        text: `Está abierto por excepción el período ${data.abierto.nombre}. La operatoria académica normal sigue bloqueada para proteger el historial.`,
      });
      avisos.push({
        tone: "info",
        text: sinMd(
          "Podés usar **✏️ Editar / eliminar** para corregir errores de carga de las comisiones de este período anterior: unir materias/códigos en una misma comisión, corregir datos u horarios, quitar asignaciones cargadas por error o eliminar comisiones erróneas. No se habilita abrir comisiones nuevas, carga rápida ni registrar altas/bajas reales de docentes."
        ),
      });
    } else {
      avisos.push({
        tone: "warning",
        text: sinMd(
          "Las comisiones solo se pueden abrir, cargar por Excel o registrar modificaciones operativas en el **período actual** —es decir, el último período creado y abierto."
        ),
      });
      if (data.motivo_bloqueo) {
        avisos.push({ tone: data.abierto === null || data.actual === null ? "info" : "error", text: data.motivo_bloqueo });
      }
    }
  }
  return (
    <>
      {avisos.map((a, i) => (
        <FeedbackBox key={i} feedback={a} />
      ))}
    </>
  );
}

export function ComisionesModule({ onAuthError }: { onAuthError: (e: unknown) => void }) {
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
      setData(await comisionesApi.overview());
      setLoadError(null);
    } catch (err) {
      setLoadError(handle(err));
    } finally {
      setLoading(false);
    }
  }, [handle]);

  useEffect(() => {
    let cancelled = false;
    comisionesApi
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
        Cargando comisiones…
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

  return (
    <div>
      <div className="mb-5">
        <p className="text-sm text-slate-500">
          {data.contexto.institucion.nombre} · {data.contexto.departamento.nombre}
        </p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">📋 Módulo Comisiones</h2>
      </div>
      <Encabezado data={data} />

      <div role="tablist" aria-label="Pestañas de Comisiones" className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200">
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
