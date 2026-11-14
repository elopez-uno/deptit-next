"use client";

// Selector de hora propio en 24 h (Hora 00-23 + Minutos 00/15/30/45). Reemplaza a <input type="time">, cuya
// presentación (AM/PM o 24 h) depende del idioma del navegador / Windows. El valor sigue siendo "HH:MM".
import { HORAS_24, opcionesMinutos, partesHora } from "@/lib/hora";

const SELECT = "rounded-lg border border-slate-300 px-2 py-1.5 text-sm disabled:bg-slate-50";

export function HoraInput({
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
  const p = partesHora(value);
  const h = p?.h ?? "";
  const m = p?.m ?? "";
  return (
    <div role="group" aria-label={label} className="flex w-full items-center gap-1">
      <select
        aria-label={`${label} (hora)`}
        className={`${SELECT} w-full`}
        value={h}
        disabled={disabled}
        onChange={(e) => onChange(`${e.target.value}:${m || "00"}`)}
      >
        {!h && <option value="">--</option>}
        {HORAS_24.map((x) => (
          <option key={x} value={x}>
            {x}
          </option>
        ))}
      </select>
      <span className="text-sm text-slate-500">:</span>
      <select
        aria-label={`${label} (minutos)`}
        className={`${SELECT} w-full`}
        value={m}
        disabled={disabled}
        onChange={(e) => onChange(`${h || "00"}:${e.target.value}`)}
      >
        {!m && <option value="">--</option>}
        {opcionesMinutos(m).map((x) => (
          <option key={x} value={x}>
            {x}
          </option>
        ))}
      </select>
    </div>
  );
}
