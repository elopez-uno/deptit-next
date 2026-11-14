"""SQL de Sueldos sobre una conexion/transaccion ya abierta.  Nunca crea ni altera tablas y nunca confirma.

Origen (entry): ``get_escalas_salariales_v256`` l. 25578 y ``guardar_escala_salarial_v256`` l. 25628
(``_pg_read_dataframe`` / ``_pg_raw_conn``: SQL con ambito explicito de INSTITUCION, sin inyector);
``calcular_costos_asignaciones_proyecto_v257`` l. 25759 (``_pg_read_dataframe``); designaciones de todos los
departamentos del Resumen docente: base l. 26679 (``_pg_read_dataframe`` + estado del periodo por ``get_conn()``, que
el inyector acota al departamento de la sesion) y v149 l. 31120 / v162 l. 34740 (ya portada por Comisiones:
``comisiones.proyectos.designaciones_periodo_institucional_v149``, importada sin modificar).

``escalas_salariales_docentes`` es tabla INSTITUCIONAL (``INSTITUTION_TABLES``); no tiene departamento ni periodo.
``asegurar_esquema_sueldos_v256`` NO se porta: B12F la ejecuta en modo verificacion (DDL no-op verificada, semilla
``Inicial v256`` suprimida) y el esquema de deptit_next_dev ya cumple (docs/sueldos_analysis.md §8.3).
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

import pandas as pd
from psycopg import Connection
from psycopg.rows import dict_row

from designaciones.repository import _numeric

# --- get_escalas_salariales_v256 (l. 25583-25590) -----------------------------------------------------------------
ESCALAS_SQL = """
            SELECT mes_referencia, cargo, basico_simple, fecha_actualizacion,
                   COALESCE(usuario_actualizacion, '') AS usuario_actualizacion
            FROM escalas_salariales_docentes
            WHERE institucion_id = %s
            ORDER BY mes_referencia DESC, cargo
        """

# --- guardar_escala_salarial_v256 (l. 25651-25660) ----------------------------------------------------------------
UPSERT_ESCALA_SQL = """
                    INSERT INTO escalas_salariales_docentes
                    (institucion_id, mes_referencia, cargo, basico_simple, fecha_actualizacion, usuario_actualizacion)
                    VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP,%s)
                    ON CONFLICT (institucion_id, mes_referencia, cargo)
                    DO UPDATE SET basico_simple=EXCLUDED.basico_simple,
                                  fecha_actualizacion=CURRENT_TIMESTAMP,
                                  usuario_actualizacion=EXCLUDED.usuario_actualizacion
                """

# --- _periodo_equivalente_pg (extracted_batch03 l. 204) -----------------------------------------------------------
PERIODO_EQUIVALENTE_SQL = "SELECT nombre, anio, semestre FROM periodos WHERE id = %s LIMIT 1"

# --- get_designaciones_docente_todos_departamentos_pg base (l. 26679) --------------------------------------------
# Estado del periodo por get_conn(): el inyector agrega institucion + departamento de la sesion.
ESTADO_PERIODO_SQL = ("SELECT COALESCE(estado, '') AS estado FROM periodos WHERE id = %s AND "
                      "(periodos.institucion_id = %s) AND (periodos.departamento_id = %s) LIMIT 1")
TODOS_DEPTOS_BASE_SQL = """
            SELECT
                COALESCE(dep.nombre, 'Sin departamento') AS departamento,
                p.nombre AS periodo,
                d.cargo,
                d.dedicacion,
                d.horas,
                d.tipo_designacion,
                COALESCE(d.ad_honorem, 'No') AS ad_honorem,
                d.estado,
                d.fecha_desde,
                d.fecha_hasta,
                d.observaciones
            FROM designaciones d
            JOIN periodos p ON p.id = d.periodo_id
            LEFT JOIN departamentos dep ON dep.id = d.departamento_id
            {where}
              AND p.institucion_id = d.institucion_id
              AND p.departamento_id IS NOT DISTINCT FROM d.departamento_id
              AND EXISTS (
                  SELECT 1
                  FROM docentes doc_local
                  WHERE doc_local.institucion_id = d.institucion_id
                    AND doc_local.departamento_id IS NOT DISTINCT FROM d.departamento_id
                    AND regexp_replace(COALESCE(doc_local.cuil, ''), '[^0-9]', '', 'g') =
                        regexp_replace(COALESCE(d.cuil, ''), '[^0-9]', '', 'g')
              )
            ORDER BY dep.nombre, p.anio DESC, p.semestre DESC, d.cargo, d.tipo_designacion
        """

# --- calcular_costos_asignaciones_proyecto_v257 (l. 25804-25823) --------------------------------------------------
COSTOS_DESIGNACIONES_SQL = """
                SELECT d.departamento_id, d.cuil, d.cargo, d.dedicacion,
                       COALESCE(d.horas,0) AS horas, COALESCE(d.ad_honorem,'No') AS ad_honorem,
                       COALESCE(d.estado,'Activa') AS estado
                FROM designaciones d
                JOIN periodos p ON p.id=d.periodo_id
                WHERE d.institucion_id=%s
                  AND p.institucion_id=d.institucion_id
                  AND p.departamento_id IS NOT DISTINCT FROM d.departamento_id
                  AND (d.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))
                  AND regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g') IN ({ph})
                  {estado_extra}
            """
COSTOS_PERFILES_SQL = """
                SELECT departamento_id, cuil, antiguedad_anios,
                       COALESCE(nivel_posgrado_salarial,'') AS nivel_posgrado_salarial
                FROM docentes
                WHERE institucion_id=%s
                  AND regexp_replace(COALESCE(cuil,''), '[^0-9]', '', 'g') IN ({ph})
            """


class SueldosRepository:
    """Repositorio de la operacion.  ``dep`` es el departamento de la sesion (puede faltar: la escala es institucional)."""

    def __init__(self, conn: Connection, institution_id: int, department_id: Optional[int]):
        self._conn = conn
        self.inst = int(institution_id)
        self.dep = int(department_id) if department_id is not None else None
        self.mutating_statements = 0

    # --- primitivas
    def read_raw(self, sql: str, params: Iterable[Any] = ()) -> pd.DataFrame:
        """``_pg_read_dataframe``: ``pd.DataFrame(rows, columns=cols)`` (numeric queda Decimal)."""
        with self._conn.cursor() as cur:
            cur.execute(sql, list(params))
            cols = [d.name for d in cur.description] if cur.description else []
            rows = cur.fetchall() if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    def _first(self, sql: str, params: Iterable[Any]) -> Optional[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, list(params))
            row = cur.fetchone()
        return dict(row) if row else None

    def _mutate(self, sql: str, params: Iterable[Any]) -> int:
        with self._conn.cursor() as cur:
            cur.execute(sql, list(params))
            self.mutating_statements += 1
            return max(int(cur.rowcount or 0), 0)

    # --- escalas
    def escalas(self) -> pd.DataFrame:
        return self.read_raw(ESCALAS_SQL, [self.inst])

    def upsert_escala(self, mes: str, cargo: str, basico: float, usuario: str) -> int:
        return self._mutate(UPSERT_ESCALA_SQL, [self.inst, mes, cargo, _numeric(basico), usuario])

    # --- periodo equivalente / estado
    def periodo_equivalente(self, periodo_id) -> tuple[str, int, int]:
        try:
            df = self.read_raw(PERIODO_EQUIVALENTE_SQL, [periodo_id])
            if not df.empty:
                r = df.iloc[0]
                return str(r.get("nombre") or ""), int(r.get("anio") or 0), int(r.get("semestre") or 0)
        except Exception:
            pass
        return "", 0, 0

    def estado_periodo_local(self, periodo_id) -> Optional[str]:
        row = self._first(ESTADO_PERIODO_SQL, [periodo_id, self.inst, self.dep])
        return None if row is None else str(row.get("estado") or "")

    # --- designaciones de todos los departamentos (base l. 26679)
    def todos_deptos_base(self, clave_cuil: str, periodo_id: Optional[int], filtrar_activas: Optional[bool]) -> pd.DataFrame:
        filtros = ["regexp_replace(COALESCE(d.cuil, ''), '[^0-9]', '', 'g') = %s", "d.institucion_id = %s"]
        params: list = [clave_cuil, self.inst]
        if periodo_id is not None:
            nombre_p, anio, semestre = self.periodo_equivalente(periodo_id)
            filtros.append("(d.periodo_id = %s OR p.nombre = %s OR (p.anio = %s AND p.semestre = %s))")
            params.extend([int(periodo_id), nombre_p, int(anio), int(semestre)])
            if filtrar_activas:
                filtros.append("COALESCE(d.estado, 'Activa') = 'Activa'")
        where = "WHERE " + " AND ".join(filtros)
        return self.read_raw(TODOS_DEPTOS_BASE_SQL.replace("{where}", where), params)

    # --- costos v257
    def costos_designaciones(self, periodo_id: int, nombre_p, anio_p, semestre_p, cuiles: list[str],
                             historico: bool) -> pd.DataFrame:
        ph = ",".join(["%s"] * len(cuiles))
        estado_extra = "" if historico else "AND COALESCE(d.estado, 'Activa') = 'Activa'"
        sql = COSTOS_DESIGNACIONES_SQL.replace("{ph}", ph).replace("{estado_extra}", estado_extra)
        return self.read_raw(sql, [self.inst, periodo_id, nombre_p, int(anio_p), int(semestre_p)] + list(cuiles))

    def costos_perfiles(self, cuiles: list[str]) -> pd.DataFrame:
        ph = ",".join(["%s"] * len(cuiles))
        return self.read_raw(COSTOS_PERFILES_SQL.replace("{ph}", ph), [self.inst] + list(cuiles))


__all__ = ["SueldosRepository", "ESCALAS_SQL", "UPSERT_ESCALA_SQL"]
