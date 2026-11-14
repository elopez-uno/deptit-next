"use client";

// Piezas compartidas del módulo Materias (selector de unidad académica, consultas al backend, formulario de materia).
import { useEffect, useRef, useState } from "react";
import { Field, Select, Textarea, TextInput, type Feedback } from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import { type MateriaForm, type MateriasOverview, post } from "@/lib/materias";

export type OnDone = (f: Feedback) => Promise<void>;
export type OnError = (e: unknown) => ApiError;
export type TabProps = { data: MateriasOverview; onDone: OnDone; onError: OnError };

export const MANUAL = "Escribir manualmente";

// selector_facultad_escuela: "Escribir manualmente" + Facultades/Escuelas existentes (+ el valor actual).
export function EscuelaSelector({
  label,
  escuelas,
  value,
  onChange,
  disabled,
}: {
  label: string;
  escuelas: string[];
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  const opciones = [MANUAL, ...escuelas.filter((e) => e !== MANUAL)];
  if (value && !opciones.includes(value)) opciones.push(value);
  const [manual, setManual] = useState(!value || !escuelas.includes(value));
  const sel = manual ? MANUAL : value;
  return (
    <div className="space-y-2">
      <Field label={label}>
        <Select
          value={sel}
          options={opciones}
          disabled={disabled}
          onChange={(v) => {
            if (v === MANUAL) {
              setManual(true);
              onChange("");
            } else {
              setManual(false);
              onChange(v);
            }
          }}
        />
      </Field>
      {manual && (
        <TextInput value={value} onChange={onChange} disabled={disabled} placeholder="Escribí la unidad académica" />
      )}
    </div>
  );
}

// selector_facultad_escuela_filtro: "Todas" + existentes.
export function EscuelaFiltro({
  label,
  escuelas,
  value,
  onChange,
}: {
  label: string;
  escuelas: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <Field label={label}>
      <Select value={value} options={["Todas", ...escuelas]} onChange={onChange} />
    </Field>
  );
}

// Consulta POST al backend con debounce; recarga cuando cambian `body` o `version`.
export function useConsulta<T>(path: string, body: unknown, onError: OnError, version = 0, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
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
          if (n === seq.current) setError(onError(e).message);
        })
        .finally(() => {
          if (n === seq.current) setLoading(false);
        });
    }, 250);
    return () => clearTimeout(t);
  }, [path, key, onError, version, enabled]);
  return { data, error, loading };
}

export function useAccion(onDone: OnDone, onError: OnError) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run<T extends { mensaje: string; tono?: Feedback extends null ? never : string }>(
    fn: () => Promise<T>,
    after?: (r: T) => void
  ) {
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      after?.(r);
      await onDone({ tone: (r.tono as "success" | "warning" | "info") ?? "success", text: r.mensaje });
      return r;
    } catch (e) {
      setError(onError(e).message);
      return null;
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, setError, run };
}

export const materiaDefaults = (data: MateriasOverview, d?: Record<string, unknown>): MateriaForm => {
  const c = data.catalogos;
  const txt = (v: unknown) => (v === null || v === undefined ? "" : String(v).trim());
  const int = (v: unknown, def: number) => {
    const n = Number(v);
    return v === null || v === undefined || txt(v) === "" || !Number.isFinite(n) ? def : Math.trunc(n);
  };
  const pickc = (opts: string[], v: string, def: string) => (opts.includes(v) ? v : opts.includes(def) ? def : opts[0]);
  return {
    orden: int(d?.orden, 0),
    codigo: txt(d?.codigo),
    asignatura: txt(d?.asignatura),
    anio: pickc(c.anios, txt(d?.anio) || "1° Año", c.anios[0]),
    cuatrimestre: pickc(c.cuatrimestres, txt(d?.cuatrimestre) || "1", c.cuatrimestres[0]),
    dictado: pickc(c.dictados, txt(d?.dictado) || "Presencial", c.dictados[0]),
    carga_semanal: int(d?.carga_semanal, 4),
    carga_total: int(d?.carga_total, 64),
    duracion: pickc(c.duraciones, txt(d?.duracion) || "Cuatrimestral", c.duraciones[0]),
    estado: pickc(c.estados_materia, txt(d?.estado) || "Activa", c.estados_materia[0]),
    observaciones: txt(d?.observaciones),
  };
};

function NumberInput({
  value,
  min,
  max,
  onChange,
  disabled,
}: {
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
  disabled?: boolean;
}) {
  return (
    <input
      type="number"
      min={min}
      max={max}
      step={1}
      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
      value={value}
      disabled={disabled}
      onChange={(e) => {
        const n = Math.trunc(Number(e.target.value));
        onChange(Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : min);
      }}
    />
  );
}

// _formulario_agregar_materia / edición: mismos campos, límites y listas que el certificado.
export function MateriaFields({
  form,
  set,
  data,
  disabled,
  soloAnio,
  extraIzquierda,
}: {
  form: MateriaForm;
  set: (p: Partial<MateriaForm>) => void;
  data: MateriasOverview;
  disabled?: boolean;
  soloAnio?: boolean;
  extraIzquierda?: React.ReactNode;
}) {
  const c = data.catalogos;
  const lock = disabled || soloAnio;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-4">
          {extraIzquierda}
          <Field label="Orden">
            <NumberInput value={form.orden} min={0} max={999} onChange={(v) => set({ orden: v })} disabled={lock} />
          </Field>
          <Field label="Código">
            <TextInput value={form.codigo} onChange={(v) => set({ codigo: v })} disabled={lock} />
          </Field>
          <Field label="Asignatura">
            <TextInput value={form.asignatura} onChange={(v) => set({ asignatura: v })} disabled={lock} />
          </Field>
          <Field label="Año">
            <Select value={form.anio} options={c.anios} onChange={(v) => set({ anio: v })} disabled={disabled} />
          </Field>
          <Field label="Cuatrimestre">
            <Select
              value={form.cuatrimestre}
              options={c.cuatrimestres}
              onChange={(v) => set({ cuatrimestre: v })}
              disabled={lock}
            />
          </Field>
        </div>
        <div className="space-y-4">
          <Field label="Dictado">
            <Select value={form.dictado} options={c.dictados} onChange={(v) => set({ dictado: v })} disabled={lock} />
          </Field>
          <Field label="Carga horaria semanal">
            <NumberInput
              value={form.carga_semanal}
              min={0}
              max={40}
              onChange={(v) => set({ carga_semanal: v })}
              disabled={lock}
            />
          </Field>
          <Field label="Carga horaria total">
            <NumberInput
              value={form.carga_total}
              min={0}
              max={500}
              onChange={(v) => set({ carga_total: v })}
              disabled={lock}
            />
          </Field>
          <Field label="Duración">
            <Select value={form.duracion} options={c.duraciones} onChange={(v) => set({ duracion: v })} disabled={lock} />
          </Field>
          <Field label="Estado">
            <Select
              value={form.estado}
              options={c.estados_materia}
              onChange={(v) => set({ estado: v })}
              disabled={lock}
            />
          </Field>
        </div>
      </div>
      <Field label="Observaciones">
        <Textarea value={form.observaciones} onChange={(v) => set({ observaciones: v })} disabled={lock} />
      </Field>
    </div>
  );
}

export function ReadOnlyNote() {
  return (
    <p className="rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-600">
      Tu rol puede consultar los planes de estudio, pero no modificarlos.
    </p>
  );
}

export function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wider text-slate-400">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}
