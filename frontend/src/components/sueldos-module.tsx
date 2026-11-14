"use client";

// Módulo Sueldos (B13-FIX02, entry l. 61762-61931): las 3 pestañas certificadas en su orden original.
// "⚙️ Escalas básicas" y "📈 Tabla salarial" son de la INSTITUCIÓN; "👥 Sueldos del plantel" es del departamento de la
// sesión. Solo se persiste el básico Simple por (institución, mes, cargo); todo lo demás se calcula al vuelo.
// No hay Excel, importación, exportación, eliminación de escalas ni movimientos (no existen en el certificado).
// La UI solo deshabilita lo que el rol no puede hacer: FastAPI vuelve a autorizar cada escritura.
import { useCallback, useEffect, useRef, useState } from "react";
import { Spinner } from "@/components/brand";
import { Aviso, Caption, Cargando, Metric, TablaLibre } from "@/components/comisiones-shared";
import { Field, FeedbackBox, PrimaryButton, Select, TextInput, type Feedback } from "@/components/module-ui";
import { type Escalas, type Overview, type Plantel, type Tabla, type WriteResult, post, sueldosApi } from "@/lib/sueldos";
import { ApiError } from "@/lib/auth";

type OnDone = (f: Feedback) => Promise<void>;
type OnError = (e: unknown) => ApiError;
type TabProps = { data: Overview; version: number; onDone: OnDone; onError: OnError };

function feedbackDe(err: ApiError): NonNullable<Feedback> {
  const tone = (err as { tone?: string }).tone;
  return { tone: tone === "warning" ? "warning" : tone === "info" ? "info" : "error", text: err.message };
}

// Consulta POST al proxy de Sueldos que se repite cuando cambian sus parámetros o la versión (equivale al rerun
// certificado); descarta respuestas viejas.
function useConsulta<T>(path: string, body: unknown, onError: OnError, version = 0, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<NonNullable<Feedback> | null>(null);
  const seq = useRef(0);
  const key = JSON.stringify(body);
  useEffect(() => {
    if (!enabled) return;
    const n = ++seq.current;
    const t = setTimeout(() => {
      post<T>(path, JSON.parse(key))
        .then((d) => {
          if (n === seq.current) {
            setData(d);
            setError(null);
          }
        })
        .catch((e) => {
          if (n === seq.current) {
            setData(null);
            setError(feedbackDe(onError(e)));
          }
        });
    }, 150);
    return () => clearTimeout(t);
  }, [path, key, onError, version, enabled]);
  return { data, error };
}

// Los textos certificados usan **negrita** de Markdown (st.info / st.caption / st.markdown).
export function Md({ text }: { text: string }) {
  return (
    <>
      {text.split("**").map((parte, i) => (i % 2 === 1 ? <strong key={i}>{parte}</strong> : <span key={i}>{parte}</span>))}
    </>
  );
}

// ------------------------------------------------------------------ ⚙️ Escalas básicas (l. 61774-61822)
function EscalasTab({ data, version, onDone, onError }: TabProps) {
  const [mes, setMes] = useState(data.hoy.mes);
  const [anio, setAnio] = useState(String(data.hoy.anio));
  const anioNum = Number(anio);
  const anioOk = Number.isInteger(anioNum) && anioNum >= 2000 && anioNum <= 2100;
  const r = useConsulta<Escalas>("escalas", { anio: anioNum, mes }, onError, version, anioOk);
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Escala mensual de básicos</h3>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Mes">
          <Select
            value={String(mes)}
            options={data.meses.map((_, i) => String(i + 1))}
            label={(o) => data.meses[Number(o) - 1]}
            onChange={(v) => setMes(Number(v))}
          />
        </Field>
        <Field label="Año">
          <TextInput type="number" value={anio} onChange={setAnio} />
        </Field>
      </div>
      <Caption>{data.textos.caption_escalas}</Caption>
      {!anioOk ? (
        <Aviso feedback={{ tone: "warning", text: "El año debe estar entre 2000 y 2100." }} />
      ) : r.error ? (
        <Aviso feedback={r.error} />
      ) : !r.data ? (
        <Cargando />
      ) : (
        <>
          <FormularioEscala key={`${r.data.mes_referencia}-${version}`} data={data} escalas={r.data} anio={anioNum} mes={mes} onDone={onDone} onError={onError} />
          <h4 className="pt-2 text-base font-semibold text-slate-800">Histórico de escalas</h4>
          {r.data.historico.length === 0 ? (
            <Aviso feedback={{ tone: "info", text: r.data.mensaje_historico ?? "Todavía no hay escalas salariales cargadas." }} />
          ) : (
            <TablaLibre rows={r.data.historico} />
          )}
        </>
      )}
    </div>
  );
}

function FormularioEscala({
  data,
  escalas,
  anio,
  mes,
  onDone,
  onError,
}: {
  data: Overview;
  escalas: Escalas;
  anio: number;
  mes: number;
  onDone: OnDone;
  onError: OnError;
}) {
  const [valores, setValores] = useState<Record<string, string>>(() =>
    Object.fromEntries(data.cargos.map((c) => [c, (escalas.valores[c] ?? 0).toFixed(2)]))
  );
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const puede = data.permisos.puede_escribir;

  async function guardar() {
    setBusy(true);
    setFeedback(null);
    try {
      const body = { anio, mes, valores: Object.fromEntries(data.cargos.map((c) => [c, Number(valores[c] === "" ? 0 : valores[c])])) };
      const r = await post<WriteResult>("escalas/guardar", body);
      await onDone({ tone: r.tono ?? "success", text: r.mensaje });
    } catch (e) {
      setFeedback(feedbackDe(onError(e)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        {data.cargos.map((cargo) => (
          <Field key={cargo} label={`${cargo} — básico Simple`}>
            <TextInput type="number" value={valores[cargo]} onChange={(v) => setValores({ ...valores, [cargo]: v })} />
          </Field>
        ))}
      </div>
      {feedback && <Aviso feedback={feedback} />}
      <div title={puede ? undefined : data.ayuda_sin_permiso ?? undefined} className="inline-block">
        <PrimaryButton busy={busy} disabled={!puede} onClick={guardar}>
          💾 Guardar / actualizar escala mensual
        </PrimaryButton>
      </div>
      {!puede && data.ayuda_sin_permiso && <Caption>{data.ayuda_sin_permiso}</Caption>}
    </div>
  );
}

// ------------------------------------------------------------------ 📈 Tabla salarial (l. 61824-61858)
function TablaTab({ data, version, onError }: TabProps) {
  const [mes, setMes] = useState<string | null>(null);
  const [dedicacion, setDedicacion] = useState(data.dedicaciones[0]);
  const [nivel, setNivel] = useState("");
  const r = useConsulta<Tabla>("tabla", { mes_referencia: mes, dedicacion, nivel }, onError, version);
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Tabla salarial por cargo, dedicación y antigüedad</h3>
      {r.error ? (
        <Aviso feedback={r.error} />
      ) : !r.data ? (
        <Cargando />
      ) : r.data.meses.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "mensaje" in r.data ? r.data.mensaje : "Cargá primero una escala salarial." }} />
      ) : (
        "mes" in r.data && (
          <>
            <div className="grid gap-3 md:grid-cols-3">
              <Field label="Escala">
                <Select
                  value={r.data.mes}
                  options={r.data.meses.map((m) => m.valor)}
                  label={(o) => ("meses" in r.data! ? r.data!.meses.find((m) => m.valor === o)?.etiqueta ?? o : o)}
                  onChange={setMes}
                />
              </Field>
              <Field label="Dedicación" hint={data.textos.ayuda_dedicacion}>
                <Select value={dedicacion} options={data.dedicaciones} onChange={setDedicacion} />
              </Field>
              <Field label="Posgrado para simular">
                <Select value={nivel} options={data.niveles} label={(o) => o || "Sin adicional por posgrado"} onChange={setNivel} />
              </Field>
            </div>
            <Caption>{r.data.caption}</Caption>
            <TablaLibre rows={r.data.filas} />
            <p className="text-sm text-slate-700"><Md text={data.textos.antiguedad} /></p>
            <p className="text-sm text-slate-700"><Md text={data.textos.posgrado} /></p>
          </>
        )
      )}
    </div>
  );
}

// ------------------------------------------------------------------ 👥 Sueldos del plantel (l. 61860-61931)
function PlantelTab({ data, version, onError }: TabProps) {
  const plantel = data.plantel;
  const periodos = plantel.periodos ?? [];
  const [nombre, setNombre] = useState(plantel.periodo_defecto ?? periodos[0]?.nombre ?? "");
  const periodo = periodos.find((p) => p.nombre === nombre) ?? null;
  const r = useConsulta<Plantel>("plantel", { periodo_id: periodo?.id }, onError, version, plantel.disponible && !!periodo);
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Sueldos estimados del plantel por período</h3>
      {!plantel.disponible ? (
        <Aviso feedback={{ tone: "info", text: plantel.mensaje ?? "" }} />
      ) : periodos.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "No hay períodos registrados." }} />
      ) : (
        <>
          <Field label="Período">
            <Select value={nombre} options={periodos.map((p) => p.nombre)} onChange={setNombre} />
          </Field>
          {r.error ? (
            <Aviso feedback={r.error} />
          ) : !r.data ? (
            <Cargando />
          ) : (
            <>
              {r.data.caption_escala && <Caption><Md text={r.data.caption_escala} /></Caption>}
              {r.data.estado !== "ok" ? (
                <Aviso feedback={{ tone: r.data.tono ?? "info", text: r.data.mensaje ?? "" }} />
              ) : (
                <>
                  <div className="grid gap-3 md:grid-cols-3">
                    <Metric label="Docentes" value={r.data.metricas!.docentes} />
                    <Metric label="Designaciones" value={r.data.metricas!.designaciones} />
                    <Metric label="Total mensual estimado" value={r.data.metricas!.total} />
                  </div>
                  <TablaLibre rows={r.data.filas ?? []} />
                  <Caption>{r.data.caption}</Caption>
                </>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

const TABS: { key: string; label: string }[] = [
  { key: "escalas", label: "⚙️ Escalas básicas" },
  { key: "tabla", label: "📈 Tabla salarial" },
  { key: "plantel", label: "👥 Sueldos del plantel" },
];

const PANELS: Record<string, (p: TabProps) => React.ReactElement> = {
  escalas: EscalasTab,
  tabla: TablaTab,
  plantel: PlantelTab,
};

export function SueldosModule({ onAuthError }: { onAuthError: (e: unknown) => void }) {
  const [data, setData] = useState<Overview | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<string>("escalas");
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
      setData(await sueldosApi.overview());
      setLoadError(null);
    } catch (err) {
      setLoadError(handle(err));
    } finally {
      setLoading(false);
    }
  }, [handle]);

  useEffect(() => {
    let cancelled = false;
    sueldosApi
      .overview()
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setLoadError(handle(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [handle]);

  // st.success + st.rerun(): después de guardar se recargan las lecturas.
  async function afterWrite(result: Feedback) {
    setFeedback(result);
    await load();
    setVersion((v) => v + 1);
  }

  if (loading && !data) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando sueldos…
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

  const Panel = PANELS[tab] ?? PANELS.escalas;

  return (
    <div>
      <div className="mb-5">
        <p className="text-sm text-slate-500">
          {data.contexto.institucion.nombre}
          {data.contexto.departamento ? ` · ${data.contexto.departamento.nombre}` : ""}
        </p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">💰 Sueldos docentes</h2>
      </div>
      <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
        <Md text={data.info} />
      </div>

      <div role="tablist" aria-label="Pestañas de Sueldos" className="mb-6 mt-4 flex gap-1 overflow-x-auto border-b border-slate-200">
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
