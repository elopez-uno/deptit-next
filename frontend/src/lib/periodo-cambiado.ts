// P-01b (E4-01 + Tanda C): señal explícita "período cambiado". Períodos la emite después de cualquier escritura que
// cambie el período abierto (crear, revertir, eliminar, abrir anterior, volver al actual); el shell la escucha y
// recalcula al instante el contexto histórico (aviso global E4-01), sin navegar, refrescar ni volver a ingresar.
const EVENTO = "deptit:periodo-cambiado";

export function emitirPeriodoCambiado() {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(EVENTO));
}

export function alCambiarPeriodo(fn: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(EVENTO, fn);
  return () => window.removeEventListener(EVENTO, fn);
}
