"""SQL de Periodos sobre una conexion/transaccion ya abierta.  Nunca crea tablas ni confirma por su cuenta.

``periodos`` y ``movimientos`` son tablas departamentales (``PG_DEPARTMENT_TABLES`` certificado): cada sentencia
lleva ``institucion_id`` + ``departamento_id`` explicitos, equivalentes a lo que inyecta ``_pg_prepare_sql`` con el
scope B12B.  Los SELECT/UPDATE/INSERT son los del entry certificado (l. 4713, 4724, 11394-11547, 4424) y
``extracted_batch03/readonly_queries.py`` (``get_ultimo_periodo``).
"""

from __future__ import annotations

from typing import Optional

from psycopg import Connection
from psycopg.rows import dict_row

_SCOPE = "institucion_id = %s AND departamento_id = %s"
_COLUMNS = "id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones"

LIST_SQL = f"SELECT {_COLUMNS} FROM periodos WHERE {_SCOPE} ORDER BY anio DESC, semestre DESC, id DESC"
OPEN_SQL = f"SELECT {_COLUMNS} FROM periodos WHERE estado = 'Abierto' AND {_SCOPE} ORDER BY id DESC LIMIT 1"
LAST_SQL = f"SELECT {_COLUMNS} FROM periodos WHERE {_SCOPE} ORDER BY anio DESC, semestre DESC, id DESC LIMIT 1"
BY_ID_SQL = (f"SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado FROM periodos "
             f"WHERE id = %s AND {_SCOPE} LIMIT 1")
LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtext(%s))"
# B12I capa T: lock de SESION en una conexion dedicada (cache_decision_integrity.consistency / _release).
TRY_SESSION_LOCK_SQL = "SELECT pg_try_advisory_lock(hashtext(%s))"
SESSION_UNLOCK_SQL = "SELECT pg_advisory_unlock(hashtext(%s))"
CLOSE_OTHERS_SQL = f"UPDATE periodos SET estado = 'Cerrado' WHERE estado = 'Abierto' AND id <> %s AND {_SCOPE}"
CLOSE_ALL_SQL = f"UPDATE periodos SET estado = 'Cerrado' WHERE estado = 'Abierto' AND {_SCOPE}"
OPEN_ONE_SQL = f"UPDATE periodos SET estado = 'Abierto' WHERE id = %s AND {_SCOPE}"
# E4-12 (eliminar periodo REALMENTE vacio, D-E4-03): solo la apertura automatica identificada y el periodo.
DELETE_MOVEMENT_SQL = f"DELETE FROM movimientos WHERE id = %s AND periodo_id = %s AND {_SCOPE}"
DELETE_PERIOD_SQL = f"DELETE FROM periodos WHERE id = %s AND {_SCOPE}"
MOVEMENT_SQL = ("INSERT INTO movimientos (periodo_id, fecha, tipo_movimiento, cuil, nombre, detalle, observaciones, "
                "horas_variacion, institucion_id, departamento_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING id")

# Claves de bloqueo certificadas: B12I serializa todo cambio de estado de periodos con la misma clave que B12C
# (Crear periodo), como lock de sesion; abrir_periodo_emergencia toma ademas la suya, transaccional, en su COMMIT 1.
PERIOD_STATE_LOCK = "deptit_crear_periodo:{inst}:{dep}"
EMERGENCY_OPEN_LOCK = "deptit_abrir_periodo_emergencia:{inst}:{dep}"


class PeriodosRepository:
    def __init__(self, conn: Connection, institution_id: int, department_id: int):
        self._conn = conn
        self._scope = [int(institution_id), int(department_id)]
        self.mutating_statements = 0

    def _all(self, sql: str, params: list) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def _first(self, sql: str, params: list) -> Optional[dict]:
        rows = self._all(sql, params)
        return rows[0] if rows else None

    def _mutate(self, sql: str, params: list) -> int:
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            self.mutating_statements += 1
            return int(cur.rowcount or 0)

    # --- lecturas
    def list(self) -> list[dict]:
        return self._all(LIST_SQL, self._scope)

    def open_period(self) -> Optional[dict]:
        return self._first(OPEN_SQL, self._scope)

    def last_period(self) -> Optional[dict]:
        return self._first(LAST_SQL, self._scope)

    def by_id(self, period_id: int) -> Optional[dict]:
        return self._first(BY_ID_SQL, [int(period_id)] + self._scope)

    # --- bloqueo transaccional (se libera con el COMMIT/ROLLBACK)
    def lock(self, key_format: str) -> None:
        self._conn.execute(LOCK_SQL, [self.lock_key(key_format)])

    def lock_key(self, key_format: str) -> str:
        inst, dep = self._scope
        return key_format.format(inst=inst, dep=dep)

    # --- escrituras
    def close_open_except(self, period_id: int) -> int:
        return self._mutate(CLOSE_OTHERS_SQL, [int(period_id)] + self._scope)

    def close_all_open(self) -> int:
        return self._mutate(CLOSE_ALL_SQL, self._scope)

    def open_one(self, period_id: int) -> int:
        return self._mutate(OPEN_ONE_SQL, [int(period_id)] + self._scope)

    def delete_movement(self, movement_id: int, period_id: int) -> int:
        return self._mutate(DELETE_MOVEMENT_SQL, [int(movement_id), int(period_id)] + self._scope)

    def delete_period(self, period_id: int) -> int:
        return self._mutate(DELETE_PERIOD_SQL, [int(period_id)] + self._scope)

    def insert_movement(self, *, period_id: Optional[int], fecha: str, tipo: str, detalle: str,
                        observaciones: str, horas_variacion: float = 0.0) -> int:
        """``registrar_movimiento`` certificado para movimientos de periodo: cuil y nombre vacios."""
        with self._conn.cursor() as cur:
            cur.execute(MOVEMENT_SQL, [period_id, fecha, tipo, "", "", detalle, observaciones,
                                       float(horas_variacion), *self._scope])
            self.mutating_statements += 1
            return int(cur.fetchone()[0])
