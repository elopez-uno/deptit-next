"use client";

// Piezas compartidas del módulo Comisiones: consultas por POST, formulario de horario efectivo por docente
// (formulario_horarios_reales_asignacion v95) y tablas. Reutiliza sin modificarlas las piezas de Designaciones y
// Materias. La UI solo oculta lo que el rol no puede hacer: FastAPI vuelve a autorizar cada escritura.
import { useEffect, useRef, useState } from "react";
import { Spinner } from "@/components/brand";
import { HoraInput } from "@/components/hora-input";
import { Aviso, Caption, Tabla, type Col } from "@/components/designaciones-shared";
import { type Feedback } from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import { type Fila, type Franja, type Overview, type Seleccion, g, horasSeleccion, post } from "@/lib/comisiones";
import { etiquetaColumna } from "@/lib/unidades-academicas";

export type OnDone = (f: Feedback) => Promise<void>;
export type OnError = (e: unknown) => ApiError;
export type TabProps = { data: Overview; version: number; onDone: OnDone; onError: OnError };

export { Aviso, Caption, Tabla, type Col };

// Feedback de un error del backend con el tono certificado (warning / info / error).
export function feedbackDe(err: ApiError): NonNullable<Feedback> {
  const tone = (err as { tone?: string }).tone;
  return { tone: tone === "warning" ? "warning" : tone === "info" ? "info" : "error", text: err.message };
}

// Consulta POST que se repite cuando cambian sus parámetros o la versión (equivale al rerun certificado).
// Igual que en Materias: pequeña espera para no consultar en cada tecla y descarte de respuestas viejas.
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
    }, 250);
    return () => clearTimeout(t);
  }, [path, key, onError, version, enabled]);
  return { data, error, loading };
}

export function Cargando({ text = "Cargando…" }: { text?: string }) {
  return (
    <div className="flex items-center gap-3 px-1 py-4 text-sm text-slate-500">
      <Spinner className="h-4 w-4 text-brand-600" />
      {text}
    </div>
  );
}

export function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-brand-950">{value}</p>
    </div>
  );
}

export function Subtabs({
  tabs,
  value,
  onChange,
  label,
}: {
  tabs: readonly { key: string; label: string }[];
  value: string;
  onChange: (k: string) => void;
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="mb-4 flex gap-1 overflow-x-auto border-b border-slate-200">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={value === t.key}
          onClick={() => onChange(t.key)}
          className={`-mb-px shrink-0 border-b-2 px-3 py-1.5 text-sm transition ${
            value === t.key ? "border-brand-600 font-medium text-brand-800" : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

// Tabla de solo lectura con todas las columnas que trae el backend (st.dataframe certificado).
export function TablaLibre({
  rows,
  ocultar = [],
  renombres = {},
  maxHeight,
}: {
  rows: Fila[];
  ocultar?: string[];
  renombres?: Record<string, string>;
  maxHeight?: string;
}) {
  if (!rows.length) return null;
  const cols = Object.keys(rows[0])
    .filter((k) => !ocultar.includes(k))
    .map((k) => ({ key: k, label: renombres[k] ?? etiquetaColumna(k) }));
  return <Tabla rows={rows} cols={cols} rowKey={(r) => JSON.stringify(r)} maxHeight={maxHeight} />;
}

export function TimeInput({
  value,
  onChange,
  disabled,
  label,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  label: string;
}) {
  // Regla global 24 h (sin AM/PM, minutos de 15 en 15 para selecciones nuevas): componente común HoraInput.
  return <HoraInput label={label} value={value} disabled={disabled} onChange={onChange} />;
}

export const seleccionInicial = (franjas: Franja[]): Seleccion[] =>
  franjas.map((f) => ({ usar: f.usar, desde: f.desde, hasta: f.hasta }));

// formulario_horarios_reales_asignacion (v95): una casilla por horario de la comisión; subfranja opcional.
export function FranjasForm({
  franjas,
  value,
  onChange,
  disabled,
  metrica,
}: {
  franjas: Franja[];
  value: Seleccion[];
  onChange: (v: Seleccion[]) => void;
  disabled?: boolean;
  metrica: string;
}) {
  if (!franjas.length) {
    return <Aviso feedback={{ tone: "warning", text: "La comisión todavía no tiene horarios válidos." }} />;
  }
  const { horas, errores } = horasSeleccion(franjas, value);
  const set = (i: number, patch: Partial<Seleccion>) => onChange(value.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  return (
    <div className="space-y-2">
      {franjas.map((f, i) => (
        <div key={i} className="grid grid-cols-1 items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 sm:grid-cols-[1fr_8rem_8rem]">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              className="h-4 w-4 accent-brand-600"
              checked={value[i]?.usar ?? false}
              disabled={disabled}
              onChange={(e) => set(i, { usar: e.target.checked })}
            />
            Cubre {f.etiqueta}
          </label>
          <TimeInput label={`Desde ${f.etiqueta}`} value={value[i]?.desde ?? f.desde} disabled={disabled || !value[i]?.usar} onChange={(v) => set(i, { desde: v })} />
          <TimeInput label={`Hasta ${f.etiqueta}`} value={value[i]?.hasta ?? f.hasta} disabled={disabled || !value[i]?.usar} onChange={(v) => set(i, { hasta: v })} />
        </div>
      ))}
      {errores.map((e) => (
        <Aviso key={e} feedback={{ tone: "error", text: e }} />
      ))}
      <p className="text-sm text-slate-600">
        {metrica}: <span className="font-semibold text-brand-950">{g(horas)} hs</span>
      </p>
    </div>
  );
}

export function SoloLectura() {
  return (
    <Aviso
      feedback={{ tone: "info", text: "Tu rol permite consultar esta pestaña, pero no registrar cambios." }}
    />
  );
}
