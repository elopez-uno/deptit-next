"""Unico writer de Analisis: ``guardar_porcentaje_horas_no_lectivas_v148`` (entry l. 25321), con su COMMIT real.

Rama PostgreSQL certificada: UN COMMIT con UN UPSERT en ``config_productividad_departamento`` (ambito del departamento
operativo; ``fecha_actualizacion = datetime.now()``); el porcentaje se limita a [0, 200] ANTES de escribir y se devuelve
el valor guardado.  Sin DDL (``asegurar_esquema_config_productividad_v148`` excluida: la tabla existe, docs §7).
B12H por la ``Unidad`` de Designaciones (SUCCESS en la transaccion del COMMIT).  Sin locks (B12I: ninguna familia T).
"""
from __future__ import annotations

from typing import Any, Callable

import audit
from designaciones import escrituras as DE

W_GUARDAR = "guardar_porcentaje_horas_no_lectivas_v148"
AuditoriaFallida = DE.AuditoriaFallida

LEER_SQL = ("SELECT porcentaje_horas_no_lectivas FROM config_productividad_departamento "
            "WHERE institucion_id=%s AND departamento_id=%s LIMIT 1")
UPSERT_SQL = """
                INSERT INTO config_productividad_departamento
                    (institucion_id, departamento_id, porcentaje_horas_no_lectivas, fecha_actualizacion)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (institucion_id, departamento_id)
                DO UPDATE SET porcentaje_horas_no_lectivas=EXCLUDED.porcentaje_horas_no_lectivas,
                              fecha_actualizacion=EXCLUDED.fecha_actualizacion
            """


class ConfigRepository:
    def __init__(self, conn, institution_id: int, department_id: int):
        self._conn = conn
        self.inst, self.dep = int(institution_id), int(department_id)
        self.mutating_statements = 0

    def porcentaje(self):
        with self._conn.cursor() as cur:
            cur.execute(LEER_SQL, [self.inst, self.dep])
            row = cur.fetchone()
            return None if row is None else row[0]

    def upsert(self, pct: float, ahora) -> None:
        with self._conn.cursor() as cur:
            cur.execute(UPSERT_SQL, [self.inst, self.dep, pct, ahora])
            self.mutating_statements += 1


class Unidad(DE.Unidad):
    """La ``Unidad`` B12H de Designaciones con el repositorio de configuracion (mismo acoplamiento de COMMITs)."""

    def read(self, fn: Callable[[ConfigRepository], Any]) -> Any:
        with self._transaction() as conn:
            return fn(ConfigRepository(conn, self.inst, self.dep))

    def commit(self, fn: Callable[[ConfigRepository], Any]) -> Any:
        if self.audit_failed:
            raise AuditoriaFallida("AUDIT_FAILED_EARLIER")
        repo = None
        with self._transaction() as conn:
            repo = ConfigRepository(conn, self.inst, self.dep)
            result = fn(repo)
            if repo.mutating_statements:
                meta = {"commit_seq": self.op.coupled_commits + 1, "mutating_statements": repo.mutating_statements,
                        "committing_writer": next(n for k, n in reversed(self._stack) if k == "business"),
                        "nested_system_task": None}
                try:
                    audit.insert_on(conn, self.op.event(audit.OUTCOME_SUCCESS, audit.MODE_IN_TRANSACTION,
                                                        metadata=meta))
                except Exception as exc:
                    self.audit_failed = True
                    raise AuditoriaFallida(audit.error_code_of(exc)) from exc
        if repo is not None and repo.mutating_statements:
            self.op.coupled_commits += 1
        return result


def guardar_porcentaje_horas_no_lectivas_v148(u: Unidad, porcentaje: Any) -> float:
    with u.writer(W_GUARDAR):
        pct = max(0.0, min(float(porcentaje or 0), 200.0))
        u.commit(lambda repo: repo.upsert(pct, u.now))
        return pct
