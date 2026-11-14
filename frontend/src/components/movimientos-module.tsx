"use client";

// Módulo Movimientos (B13-FIX02, elif modulo == "📜 Movimientos", entry l. 67764-67810): UNA página sin pestañas con
// el filtro de período, el buscador, la tabla (primera fila seleccionada por defecto), la gestión masiva del acto
// administrativo (v266/v267) y "Eliminar movimiento del historial". No hay alta, edición, anulación, exportación ni
// paginación. La UI solo oculta lo que el rol no puede hacer (D-AL2): FastAPI vuelve a autorizar todo.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Spinner } from "@/components/brand";
import { Aviso, Caption, Tabla, filtrar, type Col } from "@/components/designaciones-shared";
import { Check, Field, FeedbackBox, PrimaryButton, Select, TextInput, type Feedback } from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import {
  type Documento,
  type FilaMovimiento,
  type Overview,
  type WriteResult,
  movimientosApi,
  post,
} from "@/lib/movimientos";

type OnDone = (f: Feedback) => Promise<void>;
type OnError = (e: unknown) => ApiError;

const TODOS = "Todos los períodos";
// seleccionar_registro_desde_tabla (l. 67790-67795): columnas y rótulos certificados, en su orden.
const COLUMNAS: Col<FilaMovimiento>[] = [
  { key: "periodo", label: "Período" },
  { key: "fecha", label: "Fecha" },
  { key: "tipo_movimiento", label: "Movimiento" },
  { key: "nombre", label: "Persona / registro" },
  { key: "cuil", label: "CUIL" },
  { key: "detalle", label: "Detalle" },
  { key: "acto_administrativo", label: "Acto administrativo" },
  { key: "observaciones", label: "Observaciones" },
];
const BUSQUEDA = ["periodo", "fecha", "tipo_movimiento", "nombre", "cuil", "detalle", "acto_administrativo", "observaciones"];
// _render_gestion_acto_movimiento_v266 (l. 55572-55640).
const COLUMNAS_ACTOS: Col<FilaMovimiento>[] = [
  { key: "fecha", label: "Fecha" },
  { key: "tipo_movimiento", label: "Movimiento" },
  { key: "nombre", label: "Docente" },
  { key: "cuil", label: "CUIL" },
  { key: "detalle", label: "Detalle" },
  { key: "acto_administrativo", label: "Acto administrativo" },
];
const BUSQUEDA_ACTOS = ["fecha", "tipo_movimiento", "nombre", "cuil", "detalle", "acto_administrativo"];

function feedbackDe(err: ApiError): NonNullable<Feedback> {
  const tone = (err as { tone?: string }).tone;
  return { tone: tone === "warning" ? "warning" : tone === "info" ? "info" : "error", text: err.message };
}

function useAccion(onDone: OnDone, onError: OnError) {
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  async function run(fn: () => Promise<WriteResult>, after?: () => void) {
    setBusy(true);
    setFeedback(null);
    try {
      const r = await fn();
      after?.();
      await onDone({ tone: r.tono ?? "success", text: r.mensaje });
    } catch (e) {
      setFeedback(feedbackDe(onError(e)));
    } finally {
      setBusy(false);
    }
  }
  return { busy, feedback, setFeedback, run };
}

// _render_selector_acto_repositorio_v266 (l. 54518): busca un acto ya cargado; nunca crea actos ni números.
function SelectorActo({
  docs,
  actualId,
  value,
  onChange,
}: {
  docs: Documento[];
  actualId: number | null;
  value: number | null;
  onChange: (id: number | null) => void;
}) {
  const [buscar, setBuscar] = useState("");
  const [tipo, setTipo] = useState("Todos");
  const [dep, setDep] = useState("Todas");
  const [fecha, setFecha] = useState("Todas");
  const actual = docs.find((d) => d.id === actualId);
  const vista = useMemo(() => {
    let v = docs;
    if (tipo !== "Todos") v = v.filter((d) => (d.tipo_documento ?? "") === tipo);
    if (dep !== "Todas") v = v.filter((d) => (d.dependencia_emisora ?? "") === dep);
    if (fecha !== "Todas") v = v.filter((d) => (d.fecha ?? "") === fecha);
    return filtrar(v, buscar, ["numero", "tipo_documento", "dependencia_emisora", "titulo", "detalle", "categoria", "periodo"]);
  }, [docs, tipo, dep, fecha, buscar]);
  const uniq = (xs: (string | null)[]) => [...new Set(xs.filter((x): x is string => !!x))].sort();
  return (
    <div className="space-y-3">
      <p className="text-sm font-semibold text-slate-800">Acto administrativo común para los movimientos seleccionados</p>
      {actual && (
        <Caption>
          Vinculado actualmente: <b>{actual.etiqueta}</b>
        </Caption>
      )}
      <Caption>
        Buscá un documento ya cargado en <b>Resoluciones y respaldos</b>. Si todavía no existe, podés dejarlo pendiente y
        vincularlo después.
      </Caption>
      {docs.length === 0 ? (
        <FeedbackBox feedback={{ tone: "info", text: "El repositorio todavía no tiene documentos cargados. El registro quedará pendiente de vincular." }} />
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <Field label="Buscar en Resoluciones y respaldos">
              <TextInput value={buscar} onChange={setBuscar} placeholder="Número, título, detalle..." />
            </Field>
            <Field label="Tipo">
              <Select value={tipo} options={["Todos", ...uniq(docs.map((d) => d.tipo_documento))]} onChange={setTipo} />
            </Field>
            <Field label="Dependencia">
              <Select value={dep} options={["Todas", ...uniq(docs.map((d) => d.dependencia_emisora))]} onChange={setDep} />
            </Field>
            <Field label="Fecha">
              <Select value={fecha} options={["Todas", ...uniq(docs.map((d) => d.fecha)).reverse()]} onChange={setFecha} />
            </Field>
          </div>
          {vista.length === 0 ? (
            <FeedbackBox feedback={{ tone: "warning", text: "No hay actos que coincidan con los filtros. Podés dejarlo pendiente." }} />
          ) : (
            <>
              <p className="text-sm font-semibold text-slate-800">Actos encontrados</p>
              <Caption>{`Resultados encontrados: ${vista.length}. Seleccioná una fila de la tabla para continuar.`}</Caption>
              <Tabla
                rows={vista}
                rowKey={(d) => String(d.id)}
                selected={value === null ? null : String(value)}
                onSelect={(k) => onChange(Number(k))}
                maxHeight="max-h-64"
                cols={[
                  { key: "fecha", label: "Fecha" },
                  { key: "tipo_documento", label: "Tipo" },
                  { key: "numero", label: "N°" },
                  { key: "dependencia_emisora", label: "Dependencia emisora" },
                  { key: "categoria", label: "Categoría" },
                  { key: "titulo", label: "Título" },
                ]}
              />
            </>
          )}
        </>
      )}
    </div>
  );
}

// Expander "🔗 Vincular / cambiar acto administrativo de uno o varios movimientos" (l. 55572-55640).
function GestionActos({
  filas,
  tiposConActo,
  permisos,
  onDone,
  onError,
}: {
  filas: FilaMovimiento[];
  tiposConActo: string[];
  permisos: Overview["permisos"];
  onDone: OnDone;
  onError: OnError;
}) {
  const [abierto, setAbierto] = useState(false);
  const [buscar, setBuscar] = useState("");
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [doc, setDoc] = useState<number | null>(null);
  const [docs, setDocs] = useState<Documento[] | null>(null);
  const [docsError, setDocsError] = useState<string | null>(null);
  const accion = useAccion(onDone, onError);
  const elegibles = useMemo(() => filas.filter((f) => tiposConActo.includes(f.tipo_movimiento ?? "")), [filas, tiposConActo]);
  const vista = useMemo(() => filtrar(elegibles, buscar, BUSQUEDA_ACTOS), [elegibles, buscar]);
  const elegidas = vista.filter((f) => sel.has(f.id));
  const comunes = [...new Set(elegidas.map((f) => f.acto_documento_id).filter((x): x is number => x !== null))];
  const todas = vista.length > 0 && vista.every((f) => sel.has(f.id));

  useEffect(() => {
    if (!abierto || docs !== null || elegidas.length === 0) return;
    let cancel = false;
    movimientosApi
      .actos()
      .then((r) => !cancel && setDocs(r.documentos))
      .catch((e) => !cancel && setDocsError(onError(e).message));
    return () => {
      cancel = true;
    };
  }, [abierto, docs, elegidas.length, onError]);

  if (!elegibles.length) return null;

  async function ejecutar(quitar: boolean) {
    await accion.run(
      () =>
        post<WriteResult>(quitar ? "actos/desvincular" : "actos/vincular", {
          documento_id: quitar ? undefined : doc,
          seleccion: elegidas.map((f) => ({ id: f.id, huella: f.huella })),
        }),
      () => {
        setSel(new Set());
        setDocs(null);
      }
    );
  }

  return (
    <details
      className="rounded-xl border border-slate-200 bg-white shadow-sm"
      onToggle={(e) => setAbierto((e.target as HTMLDetailsElement).open)}
    >
      <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-slate-800">
        🔗 Vincular / cambiar acto administrativo de uno o varios movimientos
      </summary>
      <div className="space-y-4 border-t border-slate-100 px-5 py-4">
        <Caption>Una misma resolución puede aprobar varias altas, modificaciones o bajas.</Caption>
        <Field label="Buscar movimientos para vincular">
          <TextInput value={buscar} onChange={setBuscar} placeholder="Fecha, movimiento, docente, CUIL o detalle..." />
        </Field>
        {vista.length === 0 ? (
          <FeedbackBox feedback={{ tone: "warning", text: "No hay movimientos que coincidan con la búsqueda." }} />
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-6">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-brand-600"
                  checked={todas}
                  onChange={(e) => setSel(e.target.checked ? new Set(vista.map((f) => f.id)) : new Set())}
                />
                Seleccionar todos los movimientos filtrados
              </label>
              <Caption>{`Movimientos mostrados: ${vista.length}`}</Caption>
            </div>
            <Tabla
              rows={vista}
              cols={COLUMNAS_ACTOS}
              rowKey={(f) => String(f.id)}
              checked={new Set([...sel].map(String))}
              onCheck={(k, v) => {
                const next = new Set(sel);
                if (v) next.add(Number(k));
                else next.delete(Number(k));
                setSel(next);
              }}
              maxHeight="max-h-72"
            />
            <Caption>
              Movimientos seleccionados: <b>{elegidas.length}</b>
            </Caption>
            {elegidas.length > 0 && (
              <>
                {docsError ? (
                  <FeedbackBox feedback={{ tone: "error", text: docsError }} />
                ) : docs === null ? (
                  <Caption>Cargando el repositorio de actos…</Caption>
                ) : (
                  <SelectorActo docs={docs} actualId={comunes.length === 1 ? comunes[0] : null} value={doc} onChange={setDoc} />
                )}
                {accion.feedback && <Aviso feedback={accion.feedback} />}
                <div className="flex flex-wrap gap-3">
                  {permisos.puede_vincular && (
                    <PrimaryButton onClick={() => ejecutar(false)} busy={accion.busy} disabled={doc === null}>
                      🔗 Vincular / cambiar acto de los seleccionados
                    </PrimaryButton>
                  )}
                  {permisos.puede_desvincular && (
                    <PrimaryButton tone="secondary" onClick={() => ejecutar(true)} busy={accion.busy}>
                      Quitar vínculo de los seleccionados y dejar pendiente
                    </PrimaryButton>
                  )}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </details>
  );
}

// "Eliminar movimiento del historial" (l. 67799-67809): solo para quien tiene movimientos.delete (D-AL2).
function Eliminar({ fila, onDone, onError }: { fila: FilaMovimiento | null; onDone: OnDone; onError: OnError }) {
  // Como el st.checkbox certificado (sin key), la casilla conserva su valor entre reruns.
  const [confirmar, setConfirmar] = useState(false);
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3 border-t border-slate-200 pt-5">
      <h3 className="text-lg font-semibold text-slate-800">Eliminar movimiento del historial</h3>
      <Check checked={confirmar} onChange={setConfirmar} label="Confirmo que quiero eliminar este movimiento" />
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      <PrimaryButton
        tone="danger"
        busy={accion.busy}
        disabled={fila === null}
        onClick={() => {
          if (!fila) return;
          if (!confirmar) {
            accion.setFeedback({ tone: "error", text: "Primero confirmá la eliminación." });
            return;
          }
          void accion.run(() => post<WriteResult>("eliminar", { id: fila.id, huella: fila.huella, confirmar: true }));
        }}
      >
        🗑️ Eliminar movimiento
      </PrimaryButton>
    </div>
  );
}

export function MovimientosModule({ onAuthError }: { onAuthError: (e: ApiError) => void }) {
  const [data, setData] = useState<Overview | null>(null);
  const [filas, setFilas] = useState<FilaMovimiento[]>([]);
  const [periodo, setPeriodo] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [cargandoFilas, setCargandoFilas] = useState(false);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [buscar, setBuscar] = useState("");
  const [sel, setSel] = useState<number | null>(null);
  const [version, setVersion] = useState(0);

  const handle = useCallback(
    (err: unknown): ApiError => {
      const e = err instanceof ApiError ? err : new ApiError(0, "ERROR", "No se pudo completar la operación.");
      if (e.status === 401) onAuthError(e);
      return e;
    },
    [onAuthError]
  );

  const cargar = useCallback(async () => {
    setLoading(true);
    try {
      const d = await movimientosApi.overview();
      setData(d);
      setFilas(d.filas);
      setPeriodo(d.periodo);
      setLoadError(null);
    } catch (err) {
      setLoadError(handle(err));
    } finally {
      setLoading(false);
    }
  }, [handle]);

  useEffect(() => {
    let cancelled = false;
    movimientosApi
      .overview()
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setFilas(d.filas);
        setPeriodo(d.periodo);
      })
      .catch((err) => !cancelled && setLoadError(handle(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [handle]);

  async function listar(p: string | null) {
    setCargandoFilas(true);
    try {
      const r = await movimientosApi.listado(p);
      setFilas(r.filas);
      setPeriodo(r.periodo);
      setLoadError(null);
    } catch (err) {
      setLoadError(handle(err));
    } finally {
      setCargandoFilas(false);
    }
  }

  // st.rerun(): después de una escritura se relee el período elegido (el selector y el buscador conservan su valor).
  async function afterWrite(result: Feedback) {
    setFeedback(result);
    await listar(periodo);
    setVersion((v) => v + 1);
  }

  const vista = useMemo(() => filtrar(filas, buscar, BUSQUEDA), [filas, buscar]);
  // Primera fila por defecto (default_first=True); una selección previa se conserva si sigue en el resultado.
  const fila = vista.find((f) => f.id === sel) ?? vista[0] ?? null;

  if (loading && !data) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando movimientos…
      </div>
    );
  }
  if (loadError && !data) {
    const scope = loadError.code.startsWith("SCOPE");
    return (
      <div className={`rounded-2xl border px-6 py-8 text-sm ${scope ? "border-slate-200 bg-white text-slate-700" : "border-red-200 bg-red-50 text-red-700"}`}>
        <p>{loadError.message}</p>
        {!scope && (
          <button onClick={cargar} className="mt-4 rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800">
            Reintentar
          </button>
        )}
      </div>
    );
  }
  if (!data) return null;
  const gestionar = data.permisos.puede_vincular || data.permisos.puede_desvincular;

  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm text-slate-500">
          {data.contexto.institucion.nombre} · {data.contexto.departamento.nombre}
        </p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">📜 Movimientos</h2>
        <h3 className="mt-2 text-lg font-semibold text-slate-800">Historial de movimientos</h3>
      </div>
      {feedback && <Aviso feedback={feedback} />}
      {loadError && <FeedbackBox feedback={{ tone: "error", text: loadError.message }} />}
      {data.periodos.length > 0 && (
        <div className="max-w-sm">
          <Field label="Filtrar por período">
            <Select
              value={periodo ?? TODOS}
              options={data.periodos}
              disabled={cargandoFilas}
              onChange={(p) => {
                setFeedback(null);
                void listar(p);
              }}
            />
          </Field>
        </div>
      )}
      {cargandoFilas ? (
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <Spinner className="h-4 w-4 text-brand-600" />
          Cargando movimientos…
        </div>
      ) : filas.length === 0 ? (
        <FeedbackBox feedback={{ tone: "info", text: "Todavía no hay movimientos registrados." }} />
      ) : (
        <>
          <Field label="Buscar en movimientos">
            <TextInput value={buscar} onChange={setBuscar} placeholder="Fecha, tipo, docente, CUIL, detalle, observaciones..." />
          </Field>
          {vista.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-semibold text-slate-800">Movimientos encontrados</p>
              <Caption>{`Resultados encontrados: ${vista.length}. Seleccioná una fila de la tabla para continuar.`}</Caption>
              <Tabla
                rows={vista}
                cols={COLUMNAS}
                rowKey={(f) => String(f.id)}
                selected={fila ? String(fila.id) : null}
                onSelect={(k) => setSel(Number(k))}
              />
            </div>
          )}
          <Caption>{`Resultados: ${vista.length} de ${filas.length} movimientos`}</Caption>
          {gestionar && (
            <GestionActos
              key={`actos-${version}`}
              filas={vista}
              tiposConActo={data.tipos_con_acto}
              permisos={data.permisos}
              onDone={afterWrite}
              onError={handle}
            />
          )}
          {data.permisos.puede_eliminar && <Eliminar fila={fila} onDone={afterWrite} onError={handle} />}
        </>
      )}
    </div>
  );
}
