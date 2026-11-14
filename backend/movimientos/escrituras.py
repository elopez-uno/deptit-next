"""Writers de la pagina Movimientos con sus COMMITs reales (B13-FIX02; sin mejorar la atomicidad).

- ``eliminar_movimiento`` l. 9566 (writer nuevo de este bloque): UN COMMIT con los 2 DELETE certificados (vinculo exacto
  con el acto + movimiento).  Sin restriccion por tipo (D-AL15).  Sin rowcount: 0 filas tambien confirma.
- ``vincular_acto_movimientos_masivo_v267`` l. 54856 / ``desvincular_acto_movimientos_masivo_v267`` l. 54904: los
  writers YA portados por Designaciones (``designaciones.escrituras``), reutilizados sin modificar sobre esta ``Unidad``.
Cada COMMIT con sentencias mutantes lleva su SUCCESS B12H en la misma transaccion (``Unidad`` de Designaciones).
Sin locks (B12I: ninguna familia de capa T), sin DDL, sin reconciliaciones v207-v214 (D-AL14).
"""

from __future__ import annotations

from typing import Any, Callable

import audit
from designaciones import escrituras as DE

from .repository import MovimientosRepository

W_ELIMINAR = "eliminar_movimiento"
W_VINCULAR_MASIVO = DE.W_VINCULAR_MOV_MASIVO  # "vincular_acto_movimientos_masivo_v267"
W_DESVINCULAR_MASIVO = DE.W_DESVINCULAR_MOV_MASIVO  # "desvincular_acto_movimientos_masivo_v267"

AuditoriaFallida = DE.AuditoriaFallida


class Unidad(DE.Unidad):
    """La ``Unidad`` B12H de Designaciones con el repositorio de Movimientos (mismo acoplamiento de COMMITs)."""

    def read(self, fn: Callable[[MovimientosRepository], Any]) -> Any:
        with self._transaction() as conn:
            return fn(MovimientosRepository(conn, self.inst, self.dep))

    def commit(self, fn: Callable[[MovimientosRepository], Any]) -> Any:
        if self.audit_failed:
            raise AuditoriaFallida("AUDIT_FAILED_EARLIER")
        repo = None
        try:
            with self._transaction() as conn:
                repo = MovimientosRepository(conn, self.inst, self.dep)
                result = fn(repo)
                if result is DE.ROLLBACK or isinstance(result, DE._Rollback):
                    raise result if isinstance(result, DE._Rollback) else DE._Rollback(None)
                if repo.mutating_statements:
                    meta = {"commit_seq": self.op.coupled_commits + 1,
                            "mutating_statements": repo.mutating_statements,
                            "committing_writer": next(n for k, n in reversed(self._stack) if k == "business"),
                            "nested_system_task": self._stack[-1][1] if self._stack[-1][0] == "system" else None}
                    try:
                        audit.insert_on(conn, self.op.event(audit.OUTCOME_SUCCESS, audit.MODE_IN_TRANSACTION,
                                                            metadata=meta))
                    except Exception as exc:
                        self.audit_failed = True
                        raise AuditoriaFallida(audit.error_code_of(exc)) from exc
        except DE._Rollback as rb:
            return rb.value
        if repo is not None and repo.mutating_statements:
            self.op.coupled_commits += 1
        return result


def eliminar_movimiento(u: Unidad, id_movimiento: Any) -> None:
    """``eliminar_movimiento`` l. 9566 (v266: elimina tambien el vinculo exacto con el acto administrativo)."""
    with u.writer(W_ELIMINAR):
        u.commit(lambda repo: repo.eliminar_movimiento(int(id_movimiento)))


def vincular_acto_movimientos_masivo(u: Unidad, ids, documento_id) -> int:
    return DE.vincular_actos_masivo(u, W_VINCULAR_MASIVO, ids, documento_id)


def desvincular_acto_movimientos_masivo(u: Unidad, ids) -> int:
    return DE.desvincular_actos_masivo(u, W_DESVINCULAR_MASIVO, ids)
