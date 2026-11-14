"use client";

import { useEffect, useState } from "react";
import type { Session } from "@/lib/auth";
import { contextoApi } from "@/lib/contexto";
import { alCambiarPeriodo } from "@/lib/periodo-cambiado";

// Aviso global "🕰️ Contexto histórico activo" (E4-01, D-AN9; B13-FIX02 l. 59263-59273). Se muestra una sola vez, en
// el shell, encima de cualquier módulo. Se vuelve a pedir en cada revalidación de la sesión del shell (entrada,
// cambio de módulo o de contexto), el equivalente web del rerun certificado, y en el acto ante la señal P-01b
// "período cambiado" que emite Períodos. El texto y la condición los decide el
// backend; acá solo se pinta (sin fechas del navegador ni lógica de períodos). Si la lectura falla, no se muestra.
function Md({ text }: { text: string }) {
  const partes = text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
  return <>{partes.map((p, i) => (p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>))}</>;
}

export function ContextoHistorico({ session }: { session: Session }) {
  const [texto, setTexto] = useState<string | null>(null);
  // P-01b: una escritura de Períodos que cambia el período abierto pide recalcular el aviso en el acto.
  const [version, setVersion] = useState(0);
  useEffect(() => alCambiarPeriodo(() => setVersion((v) => v + 1)), []);

  useEffect(() => {
    let vigente = true;
    contextoApi
      .periodo()
      .then((data) => {
        if (vigente) setTexto(data.aviso?.texto ?? null);
      })
      .catch(() => {
        if (vigente) setTexto(null);
      });
    return () => {
      vigente = false;
    };
  }, [session, version]);

  if (!texto) return null;
  return (
    <div role="status" data-testid="aviso-contexto-historico" className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
      <Md text={texto} />
    </div>
  );
}
