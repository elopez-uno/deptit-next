// Regla global de horarios de DEPTIT NEXT: toda hora visible es HH:mm en 24 h, nunca AM/PM, sin depender del locale
// del navegador ni de Windows. Las selecciones nuevas usan minutos de 15 en 15; un valor ya guardado con otros minutos
// (p. ej. 08:10) se muestra y se conserva tal cual (no se redondea).

export const HORAS_24: string[] = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));
export const MINUTOS_PASO: string[] = ["00", "15", "30", "45"];

// "8:05", "08:05:00", "08:05:00.000", "8:05 PM" -> "08:05" / "20:05"; cualquier otra cosa -> null.
export function partesHora(v: unknown): { h: string; m: string } | null {
  const txt = String(v ?? "").trim();
  const r = /^(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?\s*([AaPp]\.?\s*[Mm]\.?)?$/.exec(txt);
  if (!r) return null;
  let h = Number(r[1]);
  const m = Number(r[2]);
  const sufijo = r[3]?.replace(/[\s.]/g, "").toUpperCase();
  if (sufijo) {
    if (h < 1 || h > 12) return null;
    h = (h % 12) + (sufijo === "PM" ? 12 : 0);
  }
  if (h > 23 || m > 59) return null;
  return { h: String(h).padStart(2, "0"), m: String(m).padStart(2, "0") };
}

// Representación visual única HH:mm; un texto que no es una hora se devuelve sin cambios.
export function formatoHora24(v: unknown): string {
  const p = partesHora(v);
  return p ? `${p.h}:${p.m}` : String(v ?? "");
}

// Minutos ofrecidos: 00/15/30/45 más, si el valor actual es histórico (p. ej. 10), ese valor para no alterarlo.
export function opcionesMinutos(actual: string | null | undefined): string[] {
  if (!actual || MINUTOS_PASO.includes(actual)) return MINUTOS_PASO;
  return [...MINUTOS_PASO, actual].sort();
}
