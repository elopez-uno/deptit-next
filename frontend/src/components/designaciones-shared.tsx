"use client";

// Piezas compartidas del módulo Designaciones: acciones, búsqueda certificada, tablas con selección y el selector de
// acto administrativo (v266/v267). La UI solo oculta lo que el rol no puede hacer: FastAPI vuelve a autorizar todo.
import { useEffect, useMemo, useState } from "react";
import { Field, FeedbackBox, PrimaryButton, Select, TextInput, Textarea, type Feedback } from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import {
  type ActoConfig,
  type ActoModo,
  type ActoNuevoForm,
  type ContextoActoNuevo,
  type Documento,
  type Overview,
  type PeriodoData,
  type WriteResult,
  designacionesApi,
  post,
} from "@/lib/designaciones";

export type OnDone = (f: Feedback) => Promise<void>;
export type OnError = (e: unknown) => ApiError;
export type TabProps = { data: Overview; version: number; onDone: OnDone; onError: OnError };

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
      const extra = (r.avisos ?? []).filter(Boolean);
      await onDone({ tone: r.tono ?? "success", text: [...extra, r.mensaje].join(" ") });
      return r;
    } catch (e) {
      const err = onError(e);
      const tone = (err as { tone?: string }).tone;
      setFeedback({ tone: tone === "warning" ? "warning" : tone === "info" ? "info" : "error", text: err.message });
      return null;
    } finally {
      setBusy(false);
    }
  }
  return { busy, feedback, setFeedback, run };
}

// filtrar_dataframe_por_texto: subcadena literal sobre normalizar_clave (mayúsculas, espacios colapsados).
const clave = (v: unknown) => String(v ?? "").trim().toUpperCase().split(/\s+/).filter(Boolean).join(" ");
export function filtrar<T extends Record<string, unknown>>(filas: T[], texto: string, columnas: string[]): T[] {
  const q = clave(texto);
  if (!q || !filas.length) return filas;
  const cols = columnas.filter((c) => c in filas[0]);
  if (!cols.length) return filas;
  return filas.filter((f) => clave(cols.map((c) => (f[c] === null || f[c] === undefined ? "" : String(f[c]))).join(" ")).includes(q));
}

export type Col<T> = { key: keyof T & string; label: string };

export function Tabla<T extends Record<string, unknown>>({
  rows,
  cols,
  rowKey,
  selected,
  onSelect,
  checked,
  onCheck,
  maxHeight = "max-h-[28rem]",
  render,
}: {
  rows: T[];
  cols: Col<T>[];
  rowKey: (r: T) => string;
  selected?: string | null;
  onSelect?: (k: string) => void;
  checked?: Set<string>;
  onCheck?: (k: string, v: boolean) => void;
  maxHeight?: string;
  render?: (r: T, key: keyof T & string) => React.ReactNode | undefined;
}) {
  return (
    <div className={`overflow-auto rounded-xl border border-slate-200 bg-white shadow-sm ${maxHeight}`}>
      <table className="min-w-full text-left text-sm">
        <thead className="sticky top-0 z-10 border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
          <tr>
            {(onSelect || onCheck) && <th scope="col" className="w-8 px-3 py-3" />}
            {cols.map((c) => (
              <th key={c.key} scope="col" className="whitespace-nowrap px-3 py-3 font-medium">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => {
            const k = rowKey(r);
            const sel = selected === k;
            return (
              <tr
                key={k}
                onClick={onSelect ? () => onSelect(k) : undefined}
                className={`${onSelect ? "cursor-pointer hover:bg-slate-50" : ""} ${sel ? "bg-brand-50/60" : ""}`}
              >
                {onSelect && (
                  <td className="px-3 py-2">
                    <input type="radio" aria-label="Seleccionar fila" className="h-4 w-4 accent-brand-600" checked={sel} onChange={() => onSelect(k)} />
                  </td>
                )}
                {onCheck && !onSelect && (
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      aria-label="Seleccionar"
                      className="h-4 w-4 accent-brand-600"
                      checked={checked?.has(k) ?? false}
                      onChange={(e) => onCheck(k, e.target.checked)}
                    />
                  </td>
                )}
                {cols.map((c) => {
                  const custom = render?.(r, c.key);
                  return (
                    <td key={c.key} className="whitespace-nowrap px-3 py-2 text-slate-700">
                      {custom !== undefined ? custom : r[c.key] === null || r[c.key] === undefined ? "" : String(r[c.key])}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// FeedbackBox que respeta los saltos de línea de los mensajes certificados ("...:\n- ...").
export function Aviso({ feedback }: { feedback: NonNullable<Feedback> }) {
  return (
    <div className="whitespace-pre-line">
      <FeedbackBox feedback={feedback} />
    </div>
  );
}

export function Caption({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-slate-500">{children}</p>;
}

export function DateInput({ value, onChange, disabled, label }: { value: string; onChange: (v: string) => void; disabled?: boolean; label?: string }) {
  return (
    <input
      type="date"
      aria-label={label}
      className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm disabled:bg-slate-50"
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

// Fecha local de hoy en ISO (date.today() del certificado).
export function hoyIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// safe_date: fecha ISO válida o el valor alternativo.
export const safeDate = (v: string | null | undefined, fallback: string) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(v ?? "").trim());
  return m && !Number.isNaN(new Date(`${m[1]}-${m[2]}-${m[3]}T00:00:00`).getTime()) ? `${m[1]}-${m[2]}-${m[3]}` : fallback;
};

// Datos de un período (designaciones, foto, historial); se releen después de cada escritura (`version`).
export function usePeriodo(periodoId: number | null, version: number, onError: OnError) {
  const [data, setData] = useState<PeriodoData | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (periodoId === null) return;
    let cancel = false;
    designacionesApi
      .periodo(periodoId)
      .then((r) => {
        if (cancel) return;
        setData(r);
        setError(null);
      })
      .catch((e) => !cancel && setError(onError(e).message));
    return () => {
      cancel = true;
    };
  }, [periodoId, version, onError]);
  // Mientras llega el período pedido no se muestran filas de otro.
  return { data: data && data.periodo.id === periodoId ? data : null, error };
}

// Texto de funciones no docentes con su vista previa (v164).
export function FuncionNoDocenteTexto({
  label,
  value,
  onChange,
  ayuda,
  preview,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  ayuda: React.ReactNode;
  preview: (t: string) => string;
}) {
  return (
    <div className="space-y-2">
      <Caption>{ayuda}</Caption>
      <Field label={label}>
        <Textarea value={value} onChange={onChange} placeholder="Ej.: de coordinación administrativa del Departamento" />
      </Field>
      {value.trim() && <Caption>{preview(value.trim().replace(/\.+$/, ""))}</Caption>}
    </div>
  );
}

// Repositorio de Resoluciones y respaldos (solo lectura); se relee después de cada escritura (`version`).
export function useDocumentos(version: number) {
  const [docs, setDocs] = useState<Documento[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancel = false;
    designacionesApi
      .actos()
      .then((r) => !cancel && setDocs(r.documentos))
      .catch((e) => !cancel && setError(e instanceof ApiError ? e.message : String(e)));
    return () => {
      cancel = true;
    };
  }, [version]);
  return { docs, error };
}

// _render_selector_acto_repositorio_v266: busca un acto ya cargado; nunca crea números manuales.
export function SelectorRepositorio({
  titulo,
  version,
  actualId,
  value,
  onChange,
}: {
  titulo: string;
  version: number;
  actualId?: number | null;
  value: number | null;
  onChange: (id: number | null) => void;
}) {
  const { docs, error } = useDocumentos(version);
  const [buscar, setBuscar] = useState("");
  const [tipo, setTipo] = useState("Todos");
  const [dep, setDep] = useState("Todas");
  const [fecha, setFecha] = useState("Todas");
  const actual = docs?.find((d) => d.id === actualId);
  const vista = useMemo(() => {
    let v = docs ?? [];
    if (tipo !== "Todos") v = v.filter((d) => (d.tipo_documento ?? "") === tipo);
    if (dep !== "Todas") v = v.filter((d) => (d.dependencia_emisora ?? "") === dep);
    if (fecha !== "Todas") v = v.filter((d) => (d.fecha ?? "") === fecha);
    return filtrar(v, buscar, ["numero", "tipo_documento", "dependencia_emisora", "titulo", "detalle", "categoria", "periodo"]);
  }, [docs, tipo, dep, fecha, buscar]);
  if (error) return <FeedbackBox feedback={{ tone: "error", text: error }} />;
  if (docs === null) return <Caption>Cargando el repositorio de actos…</Caption>;
  const uniq = (xs: (string | null)[]) => [...new Set(xs.filter((x): x is string => !!x))].sort();
  return (
    <div className="space-y-3">
      <p className="text-sm font-semibold text-slate-800">{titulo}</p>
      {actual && <Caption>Vinculado actualmente: <b>{actual.etiqueta}</b></Caption>}
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
          )}
        </>
      )}
    </div>
  );
}

const MODOS: [ActoModo, string][] = [
  ["existente", "Elegir del repositorio"],
  ["nuevo", "Cargar un nuevo acto ahora"],
  ["pendiente", "Dejar pendiente"],
];

// Texto con **negritas** de los captions certificados.
function Negritas({ text }: { text: string }) {
  return (
    <>
      {text.split("**").map((parte, i) => (i % 2 ? <b key={i}>{parte}</b> : <span key={i}>{parte}</span>))}
    </>
  );
}

const SIN_DEPENDENCIA = "Seleccionar dependencia";

// E4-07: _render_nuevo_acto_inline_v267 (l. 54565-54669). Mismos rótulos, orden, defaults y opciones; los errores del
// formulario (dependencia, número, PDF de 50 MB) los valida FastAPI al guardar la operación, como el certificado.
function NuevoActoInline({
  ctx,
  categoria,
  value,
  onChange,
}: {
  ctx: ContextoActoNuevo;
  categoria: string;
  value: ActoNuevoForm;
  onChange: (v: ActoNuevoForm) => void;
}) {
  const requiere = ctx.tipos_con_dependencia.includes(value.tipo_documento);
  const set = (parcial: Partial<ActoNuevoForm>) => onChange({ ...value, ...parcial });
  return (
    <div className="space-y-3">
      <p className="text-sm font-semibold text-slate-800">{ctx.titulo}</p>
      <Caption>
        <Negritas text={ctx.caption.replace("{categoria}", categoria)} />
      </Caption>
      <Field label="Tipo de documento">
        <Select
          value={value.tipo_documento}
          options={ctx.tipos}
          // la clave del selector de dependencia incluye el tipo: al cambiarlo vuelve a "Seleccionar dependencia"
          onChange={(t) => set({ tipo_documento: t, dependencia: SIN_DEPENDENCIA, dependencia_id: null })}
        />
      </Field>
      <Field label={requiere ? "Dependencia emisora" : "Dependencia emisora (opcional)"} hint={ctx.help_dependencia}>
        <Select
          value={value.dependencia}
          options={ctx.dependencias.map((d) => d.etiqueta)}
          onChange={(et) => set({ dependencia: et, dependencia_id: ctx.dependencias.find((d) => d.etiqueta === et)?.id ?? null })}
        />
      </Field>
      {requiere && ctx.sin_dependencias && <FeedbackBox feedback={{ tone: "warning", text: ctx.sin_dependencias }} />}
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Número / código del acto">
          <TextInput value={value.numero} onChange={(v) => set({ numero: v })} placeholder="Ej.: 441/2026" />
        </Field>
        <Field label="Fecha del acto">
          <DateInput label="Fecha del acto" value={value.fecha} onChange={(v) => set({ fecha: v })} />
        </Field>
      </div>
      <Field label="Título / asunto">
        <TextInput value={value.titulo} onChange={(v) => set({ titulo: v })} placeholder="Descripción breve del acto" />
      </Field>
      <Field label="Detalle / referencia adicional">
        <Textarea value={value.detalle} onChange={(v) => set({ detalle: v })} rows={3} />
      </Field>
      <Field label="Observaciones internas">
        <Textarea value={value.observaciones} onChange={(v) => set({ observaciones: v })} rows={2} />
      </Field>
      <Field label="PDF del acto administrativo (opcional; puede cargarse después)">
        <input
          type="file"
          accept="application/pdf,.pdf"
          aria-label="PDF del acto administrativo (opcional; puede cargarse después)"
          className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-brand-800"
          onChange={(e) => set({ archivo: e.target.files?.[0] ?? null })}
        />
        {value.archivo && <Caption>{`Archivo: ${value.archivo.name} — ${(value.archivo.size / 1024).toFixed(1)} KB`}</Caption>}
      </Field>
    </div>
  );
}

// Formulario vacío al elegir "Cargar un nuevo acto ahora": título y detalle sugeridos por la operación, fecha de hoy.
function nuevoForm(tituloSugerido: string, detalleSugerido: string): ActoNuevoForm {
  return {
    tipo_documento: "Resolución",
    dependencia: SIN_DEPENDENCIA,
    dependencia_id: null,
    numero: "",
    fecha: hoyIso(),
    titulo: tituloSugerido,
    detalle: detalleSugerido,
    observaciones: "",
    archivo: null,
  };
}

// _render_acto_contextual_v267: elegir del repositorio, cargar un nuevo acto ahora (E4-07) o dejar pendiente.
export function ActoContextual({
  titulo,
  version,
  value,
  onChange,
  categoria,
  tituloSugerido = "",
  detalleSugerido = "",
}: {
  titulo: string;
  version: number;
  value: ActoConfig;
  onChange: (v: ActoConfig) => void;
  categoria: (ctx: ContextoActoNuevo) => string;
  tituloSugerido?: string;
  detalleSugerido?: string;
}) {
  const [ctx, setCtx] = useState<ContextoActoNuevo | null>(null);
  const [ctxError, setCtxError] = useState<string | null>(null);
  useEffect(() => {
    if (value.modo !== "nuevo" || ctx) return;
    let cancel = false;
    post<ContextoActoNuevo>("acto-nuevo/contexto", {})
      .then((r) => !cancel && setCtx(r))
      .catch((e) => !cancel && setCtxError(e instanceof ApiError ? e.message : String(e)));
    return () => {
      cancel = true;
    };
  }, [value.modo, ctx]);
  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50/50 p-4">
      <p className="text-sm font-semibold text-slate-800">{titulo}</p>
      <div role="radiogroup" aria-label="Origen del acto administrativo" className="flex flex-wrap gap-2">
        {MODOS.map(([modo, label]) => (
          <button
            key={modo}
            type="button"
            role="radio"
            aria-checked={value.modo === modo}
            onClick={() =>
              value.modo !== modo &&
              onChange({
                modo,
                documento_id: modo === "existente" ? value.documento_id : null,
                // el formulario en línea arranca de nuevo cada vez que se muestra (el certificado borra sus widgets)
                nuevo: modo === "nuevo" ? nuevoForm(tituloSugerido, detalleSugerido) : undefined,
              })
            }
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              value.modo === modo ? "bg-brand-700 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {value.modo === "existente" && (
        <SelectorRepositorio
          titulo="Seleccionar acto ya cargado"
          version={version}
          value={value.documento_id}
          onChange={(id) => onChange({ modo: "existente", documento_id: id })}
        />
      )}
      {value.modo === "nuevo" && ctxError && <FeedbackBox feedback={{ tone: "error", text: ctxError }} />}
      {value.modo === "nuevo" && !ctx && !ctxError && <Caption>Cargando el formulario del acto…</Caption>}
      {value.modo === "nuevo" && ctx && value.nuevo && (
        <NuevoActoInline
          ctx={ctx}
          categoria={categoria(ctx)}
          value={value.nuevo}
          onChange={(nuevo) => onChange({ ...value, nuevo })}
        />
      )}
      {value.modo === "pendiente" && (
        <Caption>La operación se guardará sin acto administrativo y quedará pendiente de vincular desde el historial.</Caption>
      )}
    </div>
  );
}

// Valor inicial certificado del control "Origen del acto administrativo": "Elegir del repositorio".
export const ACTO_INICIAL: ActoConfig = { modo: "existente", documento_id: null };

// Gestión masiva v267 (designaciones o movimientos): seleccionar filas y aplicar / quitar el mismo acto.
export function GestionActos<T extends { id: number; huella: string; acto_documento_id: number | null }>({
  titulo,
  ayuda,
  filas,
  cols,
  buscarCols,
  placeholder,
  destino,
  periodoId,
  data,
  version,
  onDone,
  onError,
}: {
  titulo: string;
  ayuda: string;
  filas: T[];
  cols: Col<T>[];
  buscarCols: string[];
  placeholder: string;
  destino: "designaciones" | "movimientos";
  periodoId: number;
  data: Overview;
  version: number;
  onDone: OnDone;
  onError: OnError;
}) {
  const [buscar, setBuscar] = useState("");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [doc, setDoc] = useState<number | null>(null);
  const accion = useAccion(onDone, onError);
  const vista = filtrar(filas as unknown as Record<string, unknown>[], buscar, buscarCols) as unknown as T[];
  const elegidas = vista.filter((f) => sel.has(String(f.id)));
  const comunes = [...new Set(elegidas.map((f) => f.acto_documento_id).filter((x): x is number => x !== null))];
  const todas = vista.length > 0 && vista.every((f) => sel.has(String(f.id)));
  const etiqueta = destino === "designaciones" ? "las designaciones" : "los movimientos";
  if (!filas.length) return null;
  async function ejecutar(quitar: boolean) {
    await accion.run(
      () =>
        post<WriteResult>(quitar ? "actos/desvincular" : "actos/vincular", {
          destino,
          periodo_id: periodoId,
          documento_id: doc,
          seleccion: elegidas.map((f) => ({ id: f.id, huella: f.huella })),
        }),
      () => setSel(new Set())
    );
  }
  return (
    <details className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-slate-800">{titulo}</summary>
      <div className="space-y-4 border-t border-slate-100 px-5 py-4">
        <Caption>{ayuda}</Caption>
        <Field label={`Buscar ${destino} para vincular`}>
          <TextInput value={buscar} onChange={setBuscar} placeholder={placeholder} />
        </Field>
        {vista.length === 0 ? (
          <FeedbackBox feedback={{ tone: "warning", text: `No hay ${destino} que coincidan con la búsqueda.` }} />
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-6">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-brand-600"
                  checked={todas}
                  onChange={(e) => setSel(e.target.checked ? new Set(vista.map((f) => String(f.id))) : new Set())}
                />
                {destino === "designaciones" ? "Seleccionar todas las designaciones filtradas" : "Seleccionar todos los movimientos filtrados"}
              </label>
              <Caption>
                {destino === "designaciones" ? "Designaciones" : "Movimientos"} mostrad{destino === "designaciones" ? "a" : "o"}s: {vista.length}
              </Caption>
            </div>
            <Tabla
              rows={vista}
              cols={cols}
              rowKey={(f) => String(f.id)}
              checked={sel}
              onCheck={(k, v) => {
                const next = new Set(sel);
                if (v) next.add(k);
                else next.delete(k);
                setSel(next);
              }}
              maxHeight="max-h-72"
            />
            <Caption>
              {destino === "designaciones" ? "Designaciones seleccionadas" : "Movimientos seleccionados"}: <b>{elegidas.length}</b>
            </Caption>
            {elegidas.length > 0 && (
              <>
                <SelectorRepositorio
                  titulo={`Acto administrativo común para ${etiqueta} seleccionad${destino === "designaciones" ? "a" : "o"}s`}
                  version={version}
                  actualId={comunes.length === 1 ? comunes[0] : null}
                  value={doc}
                  onChange={setDoc}
                />
                {accion.feedback && <Aviso feedback={accion.feedback} />}
                <div className="flex flex-wrap gap-3">
                  {data.permisos.puede_vincular && (
                    <PrimaryButton onClick={() => ejecutar(false)} busy={accion.busy} disabled={doc === null}>
                      🔗 Vincular / cambiar acto de {destino === "designaciones" ? "las seleccionadas" : "los seleccionados"}
                    </PrimaryButton>
                  )}
                  {data.permisos.puede_desvincular && (
                    <PrimaryButton tone="secondary" onClick={() => ejecutar(true)} busy={accion.busy}>
                      {destino === "designaciones"
                        ? "Quitar vínculo de las seleccionadas y dejar pendiente"
                        : "Quitar vínculo de los seleccionados y dejar pendiente"}
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
