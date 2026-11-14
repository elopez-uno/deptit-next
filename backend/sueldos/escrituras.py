"""Unico writer certificado de Sueldos: ``guardar_escala_salarial_v256`` (entry l. 25628) con su COMMIT real.

Secuencia certificada (rama PostgreSQL), replicada sin "mejoras" (H6):
1. ``asegurar_esquema_sueldos_v256()``: en B13-FIX02 corre en MODO VERIFICACION B12F (DDL no-op verificada, semilla
   ``Inicial v256`` suprimida, COMMIT sin sentencias mutantes -> sin evento).  NO se porta: no hay DDL ni semilla (H4).
2. ``mes`` con ``^\\d{4}-\\d{2}$`` -> si no, ``ValueError("Mes de referencia inválido.")`` (antes de abrir conexion).
3. usuario = ``nombre`` del usuario de la sesion, si no ``email``, si no ``""`` (H5; lo decide el backend).
4. institucion actual (la de la sesion revalidada; ausente -> ``ValueError``).
5. UNA conexion: por cada cargo de ``CARGOS`` en orden: ``round(float(valores.get(cargo, 0) or 0), 2)``; ``<= 0`` ->
   ``ValueError("El básico de {cargo} debe ser mayor a cero.")`` (los UPSERT previos se revierten); UPSERT.
   1 COMMIT con los 6 UPSERT (atomico).  Sin lock (ninguna familia B12I lo incluye), sin movimientos, sin borrado.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import date, datetime
from typing import Any, Callable, Optional

import audit
from designaciones import escrituras as DE
from psycopg import Connection

from . import rules as SR
from .repository import SueldosRepository

W_GUARDAR_ESCALA = "guardar_escala_salarial_v256"

AuditoriaFallida = DE.AuditoriaFallida


class Unidad:
    """Operacion B12H en curso (el writer externo de la UI) y su COMMIT.  Alcance de INSTITUCION: el departamento de
    la sesion puede faltar (superadmin en una institucion sin departamentos)."""

    def __init__(self, transaction: Callable[[], AbstractContextManager[Connection]], op: audit.Operation,
                 institution_id: Optional[int], department_id: Optional[int], *, today: date, now: datetime,
                 usuario: str = ""):
        self._transaction = transaction
        self.op = op
        self.inst = int(institution_id) if institution_id is not None else None
        self.dep = int(department_id) if department_id is not None else None
        self.today, self.now, self.usuario = today, now, usuario
        self.audit_failed = False

    def commit(self, fn: Callable[[SueldosRepository], Any]) -> Any:
        if self.audit_failed:
            raise AuditoriaFallida("AUDIT_FAILED_EARLIER")
        repo = None
        with self._transaction() as conn:
            repo = SueldosRepository(conn, self.inst, self.dep)
            result = fn(repo)
            if repo.mutating_statements:
                meta = {"commit_seq": self.op.coupled_commits + 1, "mutating_statements": repo.mutating_statements,
                        "committing_writer": self.op.name, "nested_system_task": None}
                try:
                    audit.insert_on(conn, self.op.event(audit.OUTCOME_SUCCESS, audit.MODE_IN_TRANSACTION,
                                                        metadata=meta))
                except Exception as exc:
                    self.audit_failed = True
                    raise AuditoriaFallida(audit.error_code_of(exc)) from exc
        if repo is not None and repo.mutating_statements:
            self.op.coupled_commits += 1
        return result


def guardar_escala_salarial_v256(u: Unidad, mes_referencia, valores: dict) -> None:
    mes = str(mes_referencia or "").strip()
    if not SR.MES_REGEX.fullmatch(mes):
        raise ValueError("Mes de referencia inválido.")
    usuario = str(u.usuario or "")
    if u.inst is None:
        raise ValueError("No se pudo identificar la institución actual.")

    def body(repo: SueldosRepository) -> None:
        for cargo in SR.CARGOS:
            basico = round(float(valores.get(cargo, 0) or 0), 2)
            if basico <= 0:
                raise ValueError(f"El básico de {cargo} debe ser mayor a cero.")
            repo.upsert_escala(mes, cargo, basico, usuario)

    u.commit(body)


__all__ = ["W_GUARDAR_ESCALA", "Unidad", "AuditoriaFallida", "guardar_escala_salarial_v256"]
