"use client";

// Piezas compartidas del módulo Investigación: consultas por POST, acciones, selector de actos del repositorio (v266),
// tabla seleccionable con búsqueda (filtrar_dataframe_por_texto) y capacidad horaria (v184, solo informativa).
// Reutiliza sin modificarlas las piezas visuales de Designaciones y Comisiones. FastAPI vuelve a autorizar todo.
import { useEffect, useMemo, useRef, useState } from "react";
import { Aviso, Caption, Cargando, Metric, TablaLibre } from "@/components/comisiones-shared";
import { DateInput, Tabla, filtrar, hoyIso, type Col } from "@/components/designaciones-shared";
import { Field, FeedbackBox, Select, TextInput, type Feedback } from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import { type Documento, type FilaHuella, type Overview, type WriteResult, post } from "@/lib/investigacion";

export { Aviso, Caption, Cargando, DateInput, Metric, Tabla, TablaLibre, filtrar, hoyIso, type Col };

export type OnDone = (f: Feedback, pestana?: string) => Promise<void>;
export type OnError = (e: unknown) => ApiError;
export type TabProps = { data: Overview; version: number; onDone: OnDone; onError: OnError };

export function feedbackDe(err: ApiError): NonNullable<Feedback> {
  const tone = (err as { tone?: string }).tone;
  return { tone: tone === "warning" ? "warning" : tone === "info" ? "info" : "error", text: err.message };
}

// Consulta POST que se repite cuando cambian sus parámetros o la versión (equivale al rerun certificado).
export function useConsulta<T>(path: string, body: unknown, onError: OnError, version = 0, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<NonNullable<Feedback> | null>(null);
  const [loading, setLoading] = useState(false);
  const seq = useRef(0);
  const key = JSON.stringify(body);
  useEffect(() => {
    if (!enabled) return;
    const n = ++seq.current;
    const t = setTimeout(() => {
      setLoading(true);
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
        })
        .finally(() => {
          if (n === seq.current) setLoading(false);
        });
    }, 150);
    return () => clearTimeout(t);
  }, [path, key, onError, version, enabled]);
  return { data, error, loading };
}

export function useAccion(onDone: OnDone, onError: OnError) {
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  async function run(fn: () => Promise<WriteResult>, after?: (r: WriteResult) => void) {
    setBusy(true);
    setFeedback(null);
    try {
      const r = await fn();
      if (r.sin_cambios) {
        setFeedback({ tone: r.tono === "info" ? "info" : "warning", text: r.mensaje });
        return r;
      }
      after?.(r);
      await onDone({ tone: r.tono ?? "success", text: r.mensaje }, r.pestana);
      return r;
    } catch (e) {
      setFeedback(feedbackDe(onError(e)));
      return null;
    } finally {
      setBusy(false);
    }
  }
  return { busy, feedback, setFeedback, run };
}

export function SoloLectura() {
  return <Aviso feedback={{ tone: "info", text: "Tu rol permite consultar esta pestaña, pero no registrar cambios." }} />;
}

// seleccionar_registro_desde_tabla con buscador (filtrar_dataframe_por_texto); la selección se pierde si la fila
// deja de figurar en la vista filtrada.
export function SeleccionTabla<T extends FilaHuella>({
  filas,
  cols,
  busquedaCols,
  placeholder,
  etiquetaBuscar,
  titulo,
  value,
  onChange,
  vacio,
}: {
  filas: T[];
  cols: Col<T>[];
  busquedaCols: string[];
  placeholder: string;
  etiquetaBuscar: string;
  titulo: string;
  value: number | null;
  onChange: (id: number | null) => void;
  vacio?: string;
}) {
  const [buscar, setBuscar] = useState("");
  const vista = useMemo(() => filtrar(filas, buscar, busquedaCols), [filas, buscar, busquedaCols]);
  useEffect(() => {
    if (value !== null && !vista.some((f) => f.id === value)) onChange(null);
  }, [vista, value, onChange]);
  return (
    <div className="space-y-2">
      <Field label={etiquetaBuscar}>
        <TextInput value={buscar} onChange={setBuscar} placeholder={placeholder} />
      </Field>
      {vista.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: vacio ?? "No hay registros que coincidan con la búsqueda." }} />
      ) : (
        <>
          <p className="text-sm font-semibold text-slate-800">{titulo}</p>
          <Tabla
            rows={vista}
            cols={cols}
            rowKey={(r) => String(r.id)}
            selected={value === null ? null : String(value)}
            onSelect={(k) => onChange(Number(k))}
            maxHeight="max-h-72"
          />
        </>
      )}
    </div>
  );
}

// _render_selector_acto_repositorio_v266: busca un acto ya cargado; nunca crea actos ni números.
export function SelectorActo({
  titulo,
  version,
  value,
  onChange,
  onError,
}: {
  titulo: string;
  version: number;
  value: number | null;
  onChange: (id: number | null) => void;
  onError: OnError;
}) {
  const r = useConsulta<{ documentos: Documento[] }>("actos", {}, onError, version);
  const docs = r.data?.documentos ?? null;
  const [buscar, setBuscar] = useState("");
  const [tipo, setTipo] = useState("Todos");
  const [dep, setDep] = useState("Todas");
  const [fecha, setFecha] = useState("Todas");
  const vista = useMemo(() => {
    let v = docs ?? [];
    if (tipo !== "Todos") v = v.filter((d) => (d.tipo_documento ?? "") === tipo);
    if (dep !== "Todas") v = v.filter((d) => (d.dependencia_emisora ?? "") === dep);
    if (fecha !== "Todas") v = v.filter((d) => (d.fecha ?? "") === fecha);
    return filtrar(v, buscar, ["numero", "tipo_documento", "dependencia_emisora", "titulo", "detalle", "categoria", "periodo"]);
  }, [docs, tipo, dep, fecha, buscar]);
  if (r.error) return <FeedbackBox feedback={r.error} />;
  if (docs === null) return <Caption>Cargando el repositorio de actos…</Caption>;
  const uniq = (xs: (string | null)[]) => [...new Set(xs.filter((x): x is string => !!x))].sort();
  return (
    <div className="space-y-3">
      <p className="text-sm font-semibold text-slate-800">{titulo}</p>
      <Caption>
        Buscá un documento ya cargado en <b>Resoluciones y respaldos</b>. Si todavía no existe, podés dejarlo pendiente y
        vincularlo después.
      </Caption>
      {docs.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "El repositorio todavía no tiene documentos cargados. El registro quedará pendiente de vincular." }} />
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
            <Aviso feedback={{ tone: "warning", text: "No hay actos que coincidan con los filtros. Podés dejarlo pendiente." }} />
          ) : (
            <Tabla
              rows={vista}
              rowKey={(d) => String(d.id)}
              selected={value === null ? null : String(value)}
              onSelect={(k) => onChange(value === Number(k) ? null : Number(k))}
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
          )}
        </>
      )}
    </div>
  );
}

export { Metric as MetricBox };
