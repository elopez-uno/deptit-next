"use client";

// Primitivas visuales de los módulos migrados (mismo diseño que el módulo Períodos).
import { Spinner } from "@/components/brand";

export type Tone = "success" | "warning" | "error" | "info";
export type Feedback = { tone: Tone; text: string } | null;

export function FeedbackBox({ feedback }: { feedback: { tone: Tone; text: string } }) {
  const tones: Record<Tone, string> = {
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    error: "border-red-200 bg-red-50 text-red-700",
    info: "border-brand-100 bg-brand-50 text-brand-800",
  };
  return (
    <div role="status" className={`mb-4 rounded-xl border px-4 py-3 text-sm ${tones[feedback.tone]}`}>
      {feedback.text}
    </div>
  );
}

export function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">
      {text}
    </div>
  );
}

export function Card({ children }: { children: React.ReactNode }) {
  return <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">{children}</div>;
}

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-500">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </label>
  );
}

const inputCls = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50";

export function TextInput({
  value,
  onChange,
  disabled,
  placeholder,
  type = "text",
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  placeholder?: string;
  type?: string;
}) {
  return (
    <input
      type={type}
      className={inputCls}
      value={value}
      disabled={disabled}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

export function Textarea({
  value,
  onChange,
  disabled,
  placeholder,
  rows,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <textarea
      className={`min-h-20 ${inputCls}`}
      value={value}
      rows={rows}
      disabled={disabled}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

export function Select({
  value,
  options,
  onChange,
  disabled,
  label = (o: string) => o,
}: {
  value: string;
  options: string[];
  onChange: (v: string) => void;
  disabled?: boolean;
  label?: (o: string) => string;
}) {
  return (
    <select className={inputCls} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
      {options.map((o) => (
        <option key={o} value={o}>
          {label(o)}
        </option>
      ))}
    </select>
  );
}

export function Check({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <label className="flex items-start gap-3 text-sm text-slate-700">
      <input
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-slate-300 accent-brand-600"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}

export function Radio({
  value,
  options,
  onChange,
  disabled,
  name,
}: {
  value: string;
  options: string[];
  onChange: (v: string) => void;
  disabled?: boolean;
  name: string;
}) {
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-2">
      {options.map((o) => (
        <label key={o} className="flex items-start gap-2 text-sm text-slate-700">
          <input
            type="radio"
            name={name}
            className="mt-0.5 h-4 w-4 accent-brand-600"
            checked={value === o}
            disabled={disabled}
            onChange={() => onChange(o)}
          />
          <span>{o}</span>
        </label>
      ))}
    </div>
  );
}

export function PrimaryButton({
  onClick,
  busy,
  disabled,
  children,
  tone = "primary",
}: {
  onClick: () => void;
  busy?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
  tone?: "primary" | "danger" | "secondary";
}) {
  const tones = {
    primary: "bg-brand-700 text-white hover:bg-brand-800",
    danger: "bg-red-600 text-white hover:bg-red-700",
    secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
  };
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy || disabled}
      className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${tones[tone]}`}
    >
      {busy && <Spinner />}
      {children}
    </button>
  );
}

export type Column<T> = { key: keyof T & string; label: string };

export function DataTable<T extends Record<string, unknown>>({
  rows,
  columns,
  rowKey,
  selected,
  onSelect,
  maxHeight = "max-h-[28rem]",
}: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (r: T, i: number) => string;
  selected?: string | null;
  onSelect?: (key: string) => void;
  maxHeight?: string;
}) {
  return (
    <div className={`overflow-auto rounded-xl border border-slate-200 bg-white shadow-sm ${maxHeight}`}>
      <table className="min-w-full text-left text-sm">
        <thead className="sticky top-0 border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
          <tr>
            {onSelect && <th scope="col" className="w-8 px-3 py-3" />}
            {columns.map((c) => (
              <th key={c.key} scope="col" className="whitespace-nowrap px-4 py-3 font-medium">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r, i) => {
            const k = rowKey(r, i);
            const isSel = selected === k;
            return (
              <tr
                key={k}
                onClick={onSelect ? () => onSelect(k) : undefined}
                className={`${onSelect ? "cursor-pointer hover:bg-slate-50" : ""} ${isSel ? "bg-brand-50/60" : ""}`}
              >
                {onSelect && (
                  <td className="px-3 py-2">
                    <input
                      type="radio"
                      aria-label="Seleccionar fila"
                      className="h-4 w-4 accent-brand-600"
                      checked={isSel}
                      onChange={() => onSelect(k)}
                    />
                  </td>
                )}
                {columns.map((c) => (
                  <td key={c.key} className="whitespace-nowrap px-4 py-2 text-slate-700">
                    {formatCell(r[c.key])}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "";
  return String(v);
}

export function Details({
  summary,
  children,
  defaultOpen,
}: {
  summary: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details open={defaultOpen} className="group rounded-xl border border-slate-200 bg-white shadow-sm">
      <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-slate-800">{summary}</summary>
      <div className="space-y-4 border-t border-slate-100 px-5 py-4">{children}</div>
    </details>
  );
}
