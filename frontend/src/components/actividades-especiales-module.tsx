"use client";

// Módulo Actividades Especiales (B13-FIX02, entry l. 66418-66603): las 5 pestañas certificadas en su orden original.
// Actividades administrativas del período, propias del departamento: no consumen horas, no tienen Excel, actos, costos
// ni movimientos. Se opera sobre cualquier período del departamento (también cerrados), como el certificado.
// La UI solo oculta lo que el rol no puede hacer: FastAPI vuelve a autorizar cada escritura.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Spinner } from "@/components/brand";
import { Aviso, Caption, Cargando, TablaLibre } from "@/components/comisiones-shared";
import { filtrar } from "@/components/designaciones-shared";
import { SeleccionTabla, SoloLectura } from "@/components/investigacion-shared";
import { Check, Field, FeedbackBox, PrimaryButton, Select, TextInput, Textarea, type Feedback } from "@/components/module-ui";
import {
  type Fila,
  type FilaHuella,
  type OpcionDocente,
  type Overview,
  type WriteResult,
  actividadesApi,
  post,
} from "@/lib/actividades-especiales";
import { ApiError } from "@/lib/auth";

type OnDone = (f: Feedback) => Promise<void>;
type OnError = (e: unknown) => ApiError;
type TabProps = { data: Overview; version: number; onDone: OnDone; onError: OnError };

function feedbackDe(err: ApiError): NonNullable<Feedback> {
  const tone = (err as { tone?: string }).tone;
  return { tone: tone === "warning" ? "warning" : tone === "info" ? "info" : "error", text: err.message };
}

// Consulta POST que se repite cuando cambian sus parámetros o la versión (equivale al rerun certificado).
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

function useAccion(onDone: OnDone, onError: OnError) {
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  async function run(fn: () => Promise<WriteResult>) {
    setBusy(true);
    setFeedback(null);
    try {
      const r = await fn();
      const avisos = r.avisos ?? [];
      const texto = [r.mensaje, ...avisos].filter(Boolean).join("\n");
      // "Participaciones registradas: N." y un aviso por cada docente que falló (st.success + st.warning).
      await onDone({ tone: avisos.length ? "warning" : r.tono ?? "success", text: texto });
      return r;
    } catch (e) {
      setFeedback(feedbackDe(onError(e)));
      return null;
    } finally {
      setBusy(false);
    }
  }
  return { busy, feedback, run };
}

// Selector "Período" (por defecto el período abierto si existe; si no, el primero).
function usePeriodo(data: Overview) {
  const nombres = data.periodos.map((p) => String(p.nombre));
  const porDefecto = data.abierto && nombres.includes(String(data.abierto.nombre)) ? String(data.abierto.nombre) : nombres[0] ?? "";
  const [nombre, setNombre] = useState(porDefecto);
  const periodo = data.periodos.find((p) => String(p.nombre) === nombre) ?? null;
  return { nombres, nombre, setNombre, periodo };
}

// ------------------------------------------------------------------ 📚 Actividades del período (l. 66427-66446)
function ActividadesTab({ data, version, onError }: TabProps) {
  const p = usePeriodo(data);
  const r = useConsulta<{ actividades: Fila[]; participaciones: Fila[] }>("periodo", { periodo_id: p.periodo?.id }, onError, version, !!p.periodo);
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Actividades por período</h3>
      {data.periodos.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "Todavía no hay períodos registrados." }} />
      ) : (
        <>
          <Field label="Período">
            <Select value={p.nombre} options={p.nombres} onChange={p.setNombre} />
          </Field>
          {r.error ? (
            <Aviso feedback={r.error} />
          ) : !r.data ? (
            <Cargando />
          ) : r.data.actividades.length === 0 ? (
            <Aviso feedback={{ tone: "info", text: "No hay Actividades Especiales registradas para este período." }} />
          ) : (
            <>
              <TablaLibre rows={r.data.actividades} />
              <h4 className="text-base font-semibold text-slate-800">Participaciones docentes</h4>
              {r.data.participaciones.length === 0 ? (
                <Aviso feedback={{ tone: "info", text: "Todavía no hay docentes asignados." }} />
              ) : (
                <TablaLibre rows={r.data.participaciones} />
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ ➕ Nueva actividad (l. 66448-66465)
function NuevaTab({ data, onDone, onError }: TabProps) {
  const p = usePeriodo(data);
  const [titulo, setTitulo] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [obs, setObs] = useState("");
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Crear Actividad Especial</h3>
      {data.periodos.length === 0 ? (
        <Aviso feedback={{ tone: "warning", text: "Primero registrá un período." }} />
      ) : (
        <>
          {!data.permisos.puede_escribir && <SoloLectura />}
          <Field label="Período de la actividad">
            <Select value={p.nombre} options={p.nombres} onChange={p.setNombre} />
          </Field>
          <Field label="Título de la actividad"><TextInput value={titulo} onChange={setTitulo} /></Field>
          <Field label="Descripción (opcional)"><Textarea value={descripcion} onChange={setDescripcion} /></Field>
          <Field label="Observaciones (opcional)"><Textarea value={obs} onChange={setObs} /></Field>
          {accion.feedback && <Aviso feedback={accion.feedback} />}
          {data.permisos.puede_escribir && (
            <PrimaryButton
              busy={accion.busy}
              onClick={() =>
                accion.run(() =>
                  post<WriteResult>("crear", {
                    periodo_id: p.periodo?.id,
                    titulo,
                    descripcion,
                    observaciones: obs,
                    huella_periodos: data.huella_periodos,
                  })
                )
              }
            >
              ➕ Crear Actividad Especial
            </PrimaryButton>
          )}
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ 👥 Asignar docentes (l. 66467-66527)
type Config = { rol: string; observaciones: string };

function AsignarTab({ data, version, onDone, onError }: TabProps) {
  const p = usePeriodo(data);
  const r = useConsulta<{ actividades: FilaHuella[]; docentes: OpcionDocente[] }>(
    "asignar/datos",
    { periodo_id: p.periodo?.id },
    onError,
    version,
    !!p.periodo
  );
  const [sel, setSel] = useState<number | null>(null);
  const [buscarDoc, setBuscarDoc] = useState("");
  const [elegidos, setElegidos] = useState<string[]>([]);
  const [cfg, setCfg] = useState<Record<string, Config>>({});
  const accion = useAccion(onDone, onError);
  const onSel = useCallback((id: number | null) => setSel(id), []);
  const docentes = useMemo(() => r.data?.docentes ?? [], [r.data]);
  const visibles = useMemo(() => filtrar(docentes, buscarDoc, ["etiqueta"]), [docentes, buscarDoc]);
  const conf = (cuil: string): Config => cfg[cuil] ?? { rol: "", observaciones: "" };
  const etiqueta = (cuil: string) => docentes.find((d) => d.cuil === cuil)?.etiqueta ?? cuil;
  const actividad = r.data?.actividades.find((a) => a.id === sel) ?? null;
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Asignar docentes</h3>
      {data.periodos.length === 0 ? (
        <Aviso feedback={{ tone: "warning", text: "No hay períodos disponibles." }} />
      ) : (
        <>
          {!data.permisos.puede_escribir && <SoloLectura />}
          <Field label="Período">
            <Select value={p.nombre} options={p.nombres} onChange={(v) => { p.setNombre(v); setSel(null); setElegidos([]); }} />
          </Field>
          {r.error ? (
            <Aviso feedback={r.error} />
          ) : !r.data ? (
            <Cargando />
          ) : r.data.actividades.length === 0 ? (
            <Aviso feedback={{ tone: "info", text: "No hay actividades activas en este período." }} />
          ) : (
            <>
              <SeleccionTabla
                filas={r.data.actividades}
                cols={[
                  { key: "titulo", label: "Actividad" },
                  { key: "periodo", label: "Período" },
                  { key: "estado", label: "Estado" },
                  { key: "descripcion", label: "Descripción" },
                  { key: "observaciones", label: "Observaciones" },
                ]}
                busquedaCols={["titulo", "descripcion", "estado", "observaciones", "periodo"]}
                placeholder="Título, descripción, estado u observaciones..."
                etiquetaBuscar="Buscar actividad"
                titulo="Actividades encontradas"
                value={sel}
                onChange={onSel}
                vacio="No hay actividades que coincidan con la búsqueda."
              />
              {actividad && (
                <div className="space-y-3">
                  {docentes.length === 0 ? (
                    <Aviso feedback={{ tone: "warning", text: "No hay docentes registrados." }} />
                  ) : (
                    <>
                      <p className="text-sm font-semibold text-slate-800">Docentes participantes</p>
                      <Field label="Buscar docente">
                        <TextInput value={buscarDoc} onChange={setBuscarDoc} placeholder="Nombre o CUIL..." />
                      </Field>
                      <div className="max-h-56 space-y-1 overflow-y-auto rounded-xl border border-slate-200 px-3 py-2">
                        {visibles.map((d) => (
                          <Check
                            key={d.cuil}
                            label={d.etiqueta}
                            checked={elegidos.includes(d.cuil)}
                            onChange={(v) => setElegidos(v ? [...elegidos, d.cuil] : elegidos.filter((c) => c !== d.cuil))}
                          />
                        ))}
                      </div>
                      {elegidos.map((cuil) => (
                        <div key={cuil} className="space-y-2 rounded-xl border border-slate-200 px-4 py-3">
                          <p className="text-sm font-semibold">{etiqueta(cuil)}</p>
                          <div className="grid gap-3 md:grid-cols-2">
                            <Field label="Rol en la actividad">
                              <TextInput
                                value={conf(cuil).rol}
                                onChange={(v) => setCfg({ ...cfg, [cuil]: { ...conf(cuil), rol: v } })}
                                placeholder="Ej.: Coordinador, Evaluador, Organizador"
                              />
                            </Field>
                            <Field label="Observación de la participación (opcional)">
                              <TextInput
                                value={conf(cuil).observaciones}
                                onChange={(v) => setCfg({ ...cfg, [cuil]: { ...conf(cuil), observaciones: v } })}
                              />
                            </Field>
                          </div>
                        </div>
                      ))}
                      {accion.feedback && <Aviso feedback={accion.feedback} />}
                      {data.permisos.puede_escribir && (
                        <PrimaryButton
                          busy={accion.busy}
                          onClick={() =>
                            accion.run(() =>
                              post<WriteResult>("asignar", {
                                periodo_id: p.periodo?.id,
                                actividad_id: actividad.id,
                                huella: actividad.huella,
                                docentes: elegidos.map((c) => ({ cuil: c, rol: conf(c).rol, observaciones: conf(c).observaciones })),
                              })
                            ).then((res) => {
                              if (res) {
                                setElegidos([]);
                                setCfg({});
                              }
                            })
                          }
                        >
                          💾 Guardar participaciones
                        </PrimaryButton>
                      )}
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ 🕘 Historial (l. 66529-66535)
function HistorialTab({ version, onError }: TabProps) {
  const r = useConsulta<{ filas: Fila[] }>("historial", {}, onError, version);
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Historial de Actividades Especiales</h3>
      {r.error ? (
        <Aviso feedback={r.error} />
      ) : !r.data ? (
        <Cargando />
      ) : r.data.filas.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "Todavía no hay historial de Actividades Especiales." }} />
      ) : (
        <TablaLibre rows={r.data.filas} />
      )}
    </div>
  );
}

// ------------------------------------------------------------------ ✏️ Editar / eliminar (l. 66537-66601)
function EditarTab(props: TabProps) {
  const { data, version, onError } = props;
  const r = useConsulta<{ filas: FilaHuella[]; estados: string[] }>("editar/actividades", {}, onError, version);
  const [sel, setSel] = useState<number | null>(null);
  const onSel = useCallback((id: number | null) => setSel(id), []);
  const fila = r.data?.filas.find((f) => f.id === sel) ?? null;
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Editar / eliminar</h3>
      {!data.permisos.puede_escribir && <SoloLectura />}
      {r.error ? (
        <Aviso feedback={r.error} />
      ) : !r.data ? (
        <Cargando />
      ) : r.data.filas.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "No hay actividades para editar." }} />
      ) : (
        <>
          <SeleccionTabla
            filas={r.data.filas}
            cols={[
              { key: "periodo", label: "Período" },
              { key: "titulo", label: "Actividad" },
              { key: "estado", label: "Estado" },
              { key: "descripcion", label: "Descripción" },
              { key: "observaciones", label: "Observaciones" },
            ]}
            busquedaCols={["periodo", "titulo", "descripcion", "estado", "observaciones"]}
            placeholder="Período, título, descripción, estado..."
            etiquetaBuscar="Buscar actividad a editar"
            titulo="Actividades encontradas"
            value={sel}
            onChange={onSel}
            vacio="No hay actividades que coincidan con la búsqueda."
          />
          {fila && <EditarActividad key={`${fila.id}-${fila.huella}`} {...props} fila={fila} estados={r.data.estados} />}
        </>
      )}
    </div>
  );
}

function EditarActividad({ data, version, onDone, onError, fila, estados }: TabProps & { fila: FilaHuella; estados: string[] }) {
  const s = (k: string) => (fila[k] === null || fila[k] === undefined ? "" : String(fila[k]));
  const [titulo, setTitulo] = useState(s("titulo"));
  const [estado, setEstado] = useState(s("estado_mostrado") || "Activa");
  const [descripcion, setDescripcion] = useState(s("descripcion"));
  const [obs, setObs] = useState(s("observaciones"));
  const [confirmar, setConfirmar] = useState(false);
  const [part, setPart] = useState<number | null>(null);
  const onPart = useCallback((id: number | null) => setPart(id), []);
  const guardar = useAccion(onDone, onError);
  const quitar = useAccion(onDone, onError);
  const eliminar = useAccion(onDone, onError);
  const parts = useConsulta<{ filas: FilaHuella[] }>("editar/participaciones", { actividad_id: fila.id }, onError, version);
  const participacion = parts.data?.filas.find((x) => x.id === part) ?? null;
  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-3">
          <Field label="Título"><TextInput value={titulo} onChange={setTitulo} /></Field>
          <Field label="Estado"><Select value={estado} options={estados} onChange={setEstado} /></Field>
        </div>
        <div className="space-y-3">
          <Field label="Descripción"><Textarea value={descripcion} onChange={setDescripcion} /></Field>
          <Field label="Observaciones"><Textarea value={obs} onChange={setObs} /></Field>
        </div>
      </div>
      {guardar.feedback && <Aviso feedback={guardar.feedback} />}
      {data.permisos.puede_escribir && (
        <PrimaryButton
          tone="secondary"
          busy={guardar.busy}
          onClick={() =>
            guardar.run(() =>
              post<WriteResult>("editar", { actividad_id: fila.id, huella: fila.huella, titulo, descripcion, estado, observaciones: obs })
            )
          }
        >
          💾 Guardar cambios de la actividad
        </PrimaryButton>
      )}

      <div className="space-y-3">
        <h4 className="text-base font-semibold text-slate-800">Quitar una participación cargada por error</h4>
        {parts.error ? (
          <Aviso feedback={parts.error} />
        ) : !parts.data ? (
          <Cargando />
        ) : parts.data.filas.length === 0 ? (
          <Aviso feedback={{ tone: "info", text: "Esta actividad no tiene participaciones." }} />
        ) : (
          <>
            <SeleccionTabla
              filas={parts.data.filas}
              cols={[
                { key: "docente", label: "Docente" },
                { key: "cuil", label: "CUIL" },
                { key: "rol", label: "Rol" },
                { key: "estado_asignacion", label: "Estado" },
                { key: "periodo", label: "Período" },
                { key: "observaciones", label: "Observaciones" },
              ]}
              busquedaCols={["docente", "cuil", "rol", "estado_asignacion", "observaciones", "periodo"]}
              placeholder="Docente, CUIL, rol, estado..."
              etiquetaBuscar="Buscar participación"
              titulo="Participaciones encontradas"
              value={part}
              onChange={onPart}
            />
            {quitar.feedback && <Aviso feedback={quitar.feedback} />}
            {data.permisos.puede_borrar ? (
              <PrimaryButton
                tone="danger"
                busy={quitar.busy}
                disabled={participacion === null}
                onClick={() =>
                  quitar.run(() =>
                    post<WriteResult>("editar/quitar-participacion", {
                      actividad_id: fila.id,
                      huella: fila.huella,
                      asignacion_id: participacion?.id ?? null,
                      huella_participacion: participacion?.huella ?? null,
                    })
                  )
                }
              >
                🗑️ Eliminar participación por error
              </PrimaryButton>
            ) : (
              <Caption>La eliminación por error está reservada al rol superadmin.</Caption>
            )}
          </>
        )}
      </div>

      <div className="space-y-3">
        <h4 className="text-base font-semibold text-slate-800">Eliminar actividad completa por error</h4>
        {data.permisos.puede_borrar ? (
          <>
            <Check checked={confirmar} onChange={setConfirmar} label="Confirmo que esta actividad fue cargada por error" />
            {eliminar.feedback && <Aviso feedback={eliminar.feedback} />}
            <PrimaryButton
              tone="danger"
              busy={eliminar.busy}
              onClick={() => eliminar.run(() => post<WriteResult>("editar/eliminar", { actividad_id: fila.id, huella: fila.huella, confirmar }))}
            >
              🗑️ Eliminar actividad
            </PrimaryButton>
          </>
        ) : (
          <Caption>La eliminación por error está reservada al rol superadmin.</Caption>
        )}
      </div>
    </div>
  );
}

const TABS: { key: string; label: string }[] = [
  { key: "periodo", label: "📚 Actividades del período" },
  { key: "nueva", label: "➕ Nueva actividad" },
  { key: "asignar", label: "👥 Asignar docentes" },
  { key: "historial", label: "🕘 Historial" },
  { key: "editar", label: "✏️ Editar / eliminar" },
];

const PANELS: Record<string, (p: TabProps) => React.ReactElement> = {
  periodo: ActividadesTab,
  nueva: NuevaTab,
  asignar: AsignarTab,
  historial: HistorialTab,
  editar: EditarTab,
};

export function ActividadesEspecialesModule({ onAuthError }: { onAuthError: (e: unknown) => void }) {
  const [data, setData] = useState<Overview | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<string>("periodo");
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
      setData(await actividadesApi.overview());
      setLoadError(null);
    } catch (err) {
      setLoadError(handle(err));
    } finally {
      setLoading(false);
    }
  }, [handle]);

  useEffect(() => {
    let cancelled = false;
    actividadesApi
      .overview()
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setLoadError(handle(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [handle]);

  // st.rerun(): después de una escritura se recargan las lecturas de la pestaña actual.
  async function afterWrite(result: Feedback) {
    setFeedback(result);
    await load();
    setVersion((v) => v + 1);
  }

  if (loading && !data) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando actividades especiales…
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
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">⭐ Actividades Especiales</h2>
      </div>
      <FeedbackBox feedback={{ tone: "info", text: data.info }} />

      <div role="tablist" aria-label="Pestañas de Actividades Especiales" className="mb-6 mt-4 flex gap-1 overflow-x-auto border-b border-slate-200">
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
