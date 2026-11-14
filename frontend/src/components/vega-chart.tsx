"use client";

// Render de especificaciones Vega-Lite (D-AM10): el backend entrega la MISMA especificación que el certificado pasaba a
// st.vega_lite_chart (datos incluidos); acá solo se agrega el ancho del contenedor (use_container_width=True).
import { useEffect, useRef, useState } from "react";
import type { VegaSpec } from "@/lib/analisis";
import { cargarEmbed } from "@/lib/vega";

export function VegaChart({ spec, label }: { spec: VegaSpec; label?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let cancel = false;
    let finalize: (() => void) | undefined;
    const el = ref.current;
    if (!el) return;
    cargarEmbed()
      .then((embed) =>
        embed(el, { ...spec, width: "container" } as never, {
          mode: "vega-lite",
          actions: false,
          renderer: "svg",
          // 6A-B1: intérprete de expresiones (vega-interpreter, incluido en vega-embed) en lugar de generar código
          // con Function(): la CSP productiva no habilita 'unsafe-eval'.
          ast: true,
        })
      )
      .then((result) => {
        if (cancel) result.finalize();
        else finalize = () => result.finalize();
      })
      .catch(() => !cancel && setError(true));
    return () => {
      cancel = true;
      finalize?.();
    };
  }, [spec]);
  return (
    <div className="w-full">
      <div ref={ref} role="img" aria-label={label ?? "Gráfico"} data-testid="vega-chart" data-mark={JSON.stringify(spec.mark ?? null)} className="w-full" />
      {error && <p className="text-xs text-slate-500">No se pudo dibujar el gráfico.</p>}
    </div>
  );
}
