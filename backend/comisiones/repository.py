"""SQL de Comisiones sobre una conexion/transaccion ya abierta.  Nunca crea ni altera tablas y nunca confirma.

Cada sentencia es la del entry certificado con el ambito que le aplica la conexion certificada que la ejecuta:
- ``get_conn()`` + inyector B12B v193 re-enlazado por B12J (tablas de DEPARTAMENTO): ``institucion_id`` +
  ``departamento_id`` en el WHERE de la tabla base, en el ``ON`` de cada LEFT JOIN y en INSERT/UPDATE/DELETE (las
  subconsultas no se tocan).  El texto se obtuvo con ``tests/tools_comisiones_inject_sql.py`` sobre el SQL del entry.
  Se lee como ``pandas.read_sql`` (``coerce_float``) -> ``read_sql``.
- ``_pg_raw_conn()`` / ``_pg_read_dataframe`` (v195, v197, v199, v232, v233, v234 ...): sin inyector, con el ambito
  explicito del SQL certificado; ``_pg_read_dataframe`` arma ``pd.DataFrame(rows)`` sin ``coerce_float`` ->
  ``read_raw``.
- ``get_auth_conn()`` (sedes): sin inyector; el SQL lleva ``institucion_id`` explicito.
Hereda de ``DesignacionesRepository`` (sin modificarlo) las lecturas de periodos/docentes y ``insert_movement``
(``registrar_movimiento``), para que la ``Unidad`` B12H de Designaciones se reutilice tal cual.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

import pandas as pd

from designaciones.repository import DESIGNACIONES_SQL, DesignacionesRepository, _numeric  # noqa: F401
from materias.repository import MateriasRepository

_ORDEN_DIA = ("CASE {c} WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3 WHEN 'Jueves' THEN 4 "
              "WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6 WHEN 'Domingo' THEN 7 ELSE 99 END")

# --- v197: listado enriquecido (l. 44319) ----------------------------------------------------------------------
COMISIONES_V197_SQL = """
    WITH cm_meta AS (
        SELECT
            cm.comision_id,
            string_agg(DISTINCT COALESCE(NULLIF(TRIM(m.codigo), ''), NULLIF(TRIM(cm.codigo_snapshot), ''), ''), ' / ')
                FILTER (WHERE COALESCE(NULLIF(TRIM(m.codigo), ''), NULLIF(TRIM(cm.codigo_snapshot), ''), '') <> '') AS codigo_materia,
            string_agg(DISTINCT COALESCE(NULLIF(TRIM(m.asignatura), ''), NULLIF(TRIM(cm.asignatura_snapshot), ''), ''), ' / ')
                FILTER (WHERE COALESCE(NULLIF(TRIM(m.asignatura), ''), NULLIF(TRIM(cm.asignatura_snapshot), ''), '') <> '') AS asignatura,
            string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.carrera_snapshot), ''), NULLIF(TRIM(c.nombre), ''), NULLIF(TRIM(m.carrera), ''), ''), ' / ')
                FILTER (WHERE COALESCE(NULLIF(TRIM(cm.carrera_snapshot), ''), NULLIF(TRIM(c.nombre), ''), NULLIF(TRIM(m.carrera), ''), '') <> '') AS carrera,
            string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.escuela_snapshot), ''), NULLIF(TRIM(c.escuela), ''), NULLIF(TRIM(m.escuela), ''), ''), ' / ')
                FILTER (WHERE COALESCE(NULLIF(TRIM(cm.escuela_snapshot), ''), NULLIF(TRIM(c.escuela), ''), NULLIF(TRIM(m.escuela), ''), '') <> '') AS escuela,
            string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.plan_version_snapshot), ''), NULLIF(TRIM(c.plan_version), ''), NULLIF(TRIM(m.plan_version), ''), ''), ' / ')
                FILTER (WHERE COALESCE(NULLIF(TRIM(cm.plan_version_snapshot), ''), NULLIF(TRIM(c.plan_version), ''), NULLIF(TRIM(m.plan_version), ''), '') <> '') AS plan_version,
            string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.anio_snapshot), ''), NULLIF(TRIM(m.anio), ''), ''), ' / ')
                FILTER (WHERE COALESCE(NULLIF(TRIM(cm.anio_snapshot), ''), NULLIF(TRIM(m.anio), ''), '') <> '') AS anio,
            string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.cuatrimestre_snapshot), ''), NULLIF(TRIM(m.cuatrimestre), ''), ''), ' / ')
                FILTER (WHERE COALESCE(NULLIF(TRIM(cm.cuatrimestre_snapshot), ''), NULLIF(TRIM(m.cuatrimestre), ''), '') <> '') AS cuatrimestre,
            string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.dictado_snapshot), ''), NULLIF(TRIM(m.dictado), ''), ''), ' / ')
                FILTER (WHERE COALESCE(NULLIF(TRIM(cm.dictado_snapshot), ''), NULLIF(TRIM(m.dictado), ''), '') <> '') AS dictado,
            string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.carga_semanal_snapshot), ''), NULLIF(TRIM(CAST(m.carga_semanal AS TEXT)), ''), ''), ' / ')
                FILTER (WHERE COALESCE(NULLIF(TRIM(cm.carga_semanal_snapshot), ''), NULLIF(TRIM(CAST(m.carga_semanal AS TEXT)), ''), '') <> '') AS carga_semanal,
            string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.carga_total_snapshot), ''), NULLIF(TRIM(CAST(m.carga_total AS TEXT)), ''), ''), ' / ')
                FILTER (WHERE COALESCE(NULLIF(TRIM(cm.carga_total_snapshot), ''), NULLIF(TRIM(CAST(m.carga_total AS TEXT)), ''), '') <> '') AS carga_total,
            string_agg(DISTINCT CAST(cm.materia_id AS TEXT), ',') AS materia_ids
        FROM comision_materias cm
        LEFT JOIN materias m ON m.id=cm.materia_id AND m.institucion_id=cm.institucion_id
        LEFT JOIN carreras c ON c.id=m.carrera_id AND c.institucion_id=m.institucion_id
        WHERE cm.institucion_id=%s AND cm.departamento_id=%s
        GROUP BY cm.comision_id
    ),
    hor AS (
        SELECT comision_id, COALESCE(SUM(horas),0) AS horas_horario, COUNT(*) AS cantidad_horarios
        FROM horarios_comision
        WHERE institucion_id=%s AND departamento_id=%s
        GROUP BY comision_id
    ),
    asig AS (
        SELECT comision_id,
               COUNT(*) FILTER (WHERE COALESCE(estado,'Activa')='Activa') AS docentes_asignados
        FROM asignaciones_docentes_comision
        WHERE institucion_id=%s AND departamento_id=%s
        GROUP BY comision_id
    )
    SELECT
        co.id, co.periodo_id, p.nombre AS periodo, co.materia_id, co.opcion_curricular_id,
        COALESCE(NULLIF(cm.codigo_materia,''), NULLIF(m0.codigo,''), '') AS codigo_materia,
        COALESCE(NULLIF(cm.asignatura,''), NULLIF(m0.asignatura,''), '') AS asignatura,
        CASE WHEN oc.id IS NOT NULL
             THEN COALESCE(NULLIF(oc.nombre,''), COALESCE(co.materia_especifica,''))
             ELSE COALESCE(co.materia_especifica,'') END AS materia_especifica,
        COALESCE(oc.tipo,'') AS tipo_opcion_curricular,
        COALESCE(oc.escuela_oferente,'') AS escuela_oferente_opcion,
        COALESCE(NULLIF(cm.carrera,''), NULLIF(c0.nombre,''), NULLIF(m0.carrera,''), '') AS carrera,
        COALESCE(NULLIF(cm.escuela,''), NULLIF(c0.escuela,''), NULLIF(m0.escuela,''), '') AS escuela,
        COALESCE(NULLIF(cm.plan_version,''), NULLIF(c0.plan_version,''), NULLIF(m0.plan_version,''), '') AS plan_version,
        COALESCE(NULLIF(cm.anio,''), NULLIF(m0.anio,''), '') AS anio,
        COALESCE(NULLIF(cm.cuatrimestre,''), NULLIF(m0.cuatrimestre,''), '') AS cuatrimestre,
        COALESCE(NULLIF(cm.dictado,''), NULLIF(m0.dictado,''), '') AS dictado,
        COALESCE(NULLIF(cm.carga_semanal,''), NULLIF(CAST(m0.carga_semanal AS TEXT),''), '') AS carga_semanal,
        COALESCE(NULLIF(cm.carga_total,''), NULLIF(CAST(m0.carga_total AS TEXT),''), '') AS carga_total,
        COALESCE(NULLIF(cm.materia_ids,''), CAST(co.materia_id AS TEXT), '') AS materia_ids,
        co.nombre_comision, co.turno, co.sede, co.modalidad, co.estado,
        co.observaciones, co.fecha_creacion,
        COALESCE(hor.horas_horario,0) AS horas_horario,
        COALESCE(hor.cantidad_horarios,0) AS cantidad_horarios,
        COALESCE(asig.docentes_asignados,0) AS docentes_asignados
    FROM comisiones co
    LEFT JOIN periodos p
      ON p.id=co.periodo_id
     AND p.institucion_id=co.institucion_id
     AND p.departamento_id=co.departamento_id
    LEFT JOIN cm_meta cm ON cm.comision_id=co.id
    LEFT JOIN materias m0 ON m0.id=co.materia_id AND m0.institucion_id=co.institucion_id
    LEFT JOIN carreras c0 ON c0.id=m0.carrera_id AND c0.institucion_id=m0.institucion_id
    LEFT JOIN opciones_curriculares oc ON oc.id=co.opcion_curricular_id AND oc.institucion_id=co.institucion_id
    LEFT JOIN hor ON hor.comision_id=co.id
    LEFT JOIN asig ON asig.comision_id=co.id
    WHERE {where}
    ORDER BY p.anio DESC, p.semestre DESC,
             COALESCE(NULLIF(cm.escuela,''), NULLIF(c0.escuela,''), NULLIF(m0.escuela,''), ''),
             COALESCE(NULLIF(cm.codigo_materia,''), NULLIF(m0.codigo,''), ''),
             COALESCE(NULLIF(cm.asignatura,''), NULLIF(m0.asignatura,''), ''),
             co.nombre_comision
"""

# --- get_conn + inyector -----------------------------------------------------------------------------------------
HORARIOS_PERIODO_SQL = (
    "SELECT h.comision_id, p.nombre AS periodo, co.materia_id, co.nombre_comision, co.turno, co.modalidad, h.dia, "
    "h.hora_inicio, h.hora_fin, h.horas, h.observaciones FROM horarios_comision h "
    "LEFT JOIN comisiones co ON (co.id = h.comision_id) AND (co.institucion_id = %s) AND (co.departamento_id = %s) "
    "LEFT JOIN periodos p ON (p.id = co.periodo_id) AND (p.institucion_id = %s) AND (p.departamento_id = %s) "
    "WHERE co.periodo_id = %s AND (h.institucion_id = %s) AND (h.departamento_id = %s) "
    "ORDER BY co.id, " + _ORDEN_DIA.format(c="h.dia") + ", h.hora_inicio")
ASIGNACIONES_PERIODO_SQL = (
    "SELECT a.comision_id, p.nombre AS periodo, co.materia_id, co.nombre_comision, co.turno, co.modalidad, a.cuil, "
    "CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres "
    "WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE a.cuil END AS docente, a.rol, a.horas_asignadas, "
    "COALESCE(a.estado, 'Activa') AS estado, COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente, a.observaciones "
    "FROM asignaciones_docentes_comision a "
    "LEFT JOIN comisiones co ON (co.id = a.comision_id) AND (co.institucion_id = %s) AND (co.departamento_id = %s) "
    "LEFT JOIN periodos p ON (p.id = co.periodo_id) AND (p.institucion_id = %s) AND (p.departamento_id = %s) "
    "LEFT JOIN docentes doc ON (doc.cuil = a.cuil) AND (doc.institucion_id = %s) AND (doc.departamento_id = %s) "
    "WHERE co.periodo_id = %s AND (a.institucion_id = %s) AND (a.departamento_id = %s) ORDER BY co.id, docente, a.rol")
INTEGRADAS_HORARIOS_SQL = (
    "SELECT co.id AS comision_id, h.dia, h.hora_inicio, h.hora_fin, h.horas FROM horarios_comision h "
    "LEFT JOIN comisiones co ON (co.id = h.comision_id) AND (co.institucion_id = %s) AND (co.departamento_id = %s) "
    "WHERE co.periodo_id = %s AND (h.institucion_id = %s) AND (h.departamento_id = %s) "
    "ORDER BY co.id, " + _ORDEN_DIA.format(c="h.dia") + ", h.hora_inicio")
INTEGRADAS_ASIGNACIONES_SQL = (
    "SELECT co.id AS comision_id, a.cuil, CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL "
    "THEN doc.apellido || ', ' || doc.nombres WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE a.cuil END AS docente, "
    "COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente, a.rol, a.horas_asignadas, a.estado "
    "FROM asignaciones_docentes_comision a "
    "LEFT JOIN comisiones co ON (co.id = a.comision_id) AND (co.institucion_id = %s) AND (co.departamento_id = %s) "
    "LEFT JOIN docentes doc ON (doc.cuil = a.cuil) AND (doc.institucion_id = %s) AND (doc.departamento_id = %s) "
    "WHERE co.periodo_id = %s AND (a.institucion_id = %s) AND (a.departamento_id = %s) ORDER BY co.id, docente, a.rol")
MODIFICACIONES_SQL = (
    "SELECT m.id, m.fecha, m.tipo_movimiento, m.cuil, m.nombre, m.detalle, m.observaciones FROM movimientos m "
    "WHERE (m.detalle LIKE %s OR m.observaciones LIKE %s){periodo} AND (m.institucion_id = %s) "
    "AND (m.departamento_id = %s) ORDER BY m.fecha, m.id")
MOVIMIENTOS_EN_CURSO_SQL = (
    "SELECT m.fecha, m.tipo_movimiento, m.cuil, m.nombre, m.detalle, m.observaciones FROM movimientos m "
    "WHERE (m.detalle LIKE %s OR m.observaciones LIKE %s){periodo} AND (m.institucion_id = %s) "
    "AND (m.departamento_id = %s) ORDER BY m.fecha, m.id")

# --- v199 lecturas en bloque (_pg_read_dataframe) ----------------------------------------------------------------
HORARIOS_TODOS_V199_SQL = """
    SELECT h.id, h.comision_id, h.dia, h.hora_inicio, h.hora_fin, h.horas, h.observaciones
    FROM horarios_comision h
    WHERE h.institucion_id=%s AND h.departamento_id=%s
    ORDER BY h.comision_id,
             CASE h.dia WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3
                  WHEN 'Jueves' THEN 4 WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6
                  WHEN 'Domingo' THEN 7 ELSE 99 END,
             h.hora_inicio
"""
ASIGNACIONES_TODAS_V199_SQL = """
    SELECT a.id, a.comision_id, a.cuil,
           CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL
                THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE a.cuil END AS docente,
           a.rol, a.horas_asignadas, a.estado,
           COALESCE(doc.tipo_docente,'Propio') AS tipo_docente,
           a.observaciones
    FROM asignaciones_docentes_comision a
    LEFT JOIN docentes doc
      ON doc.institucion_id=a.institucion_id
     AND doc.departamento_id=a.departamento_id
     AND regexp_replace(COALESCE(doc.cuil,''),'[^0-9]','','g')=
         regexp_replace(COALESCE(a.cuil,''),'[^0-9]','','g')
    WHERE a.institucion_id=%s AND a.departamento_id=%s
    ORDER BY a.comision_id, docente, a.rol
"""
VINCULOS_TODOS_V199_SQL = """
    SELECT co.id AS comision_id, co.materia_id AS materia_principal_id,
           cm.materia_id AS materia_vinculada_id
    FROM comisiones co
    LEFT JOIN comision_materias cm
      ON cm.institucion_id=co.institucion_id
     AND cm.departamento_id=co.departamento_id
     AND cm.comision_id=co.id
    WHERE co.institucion_id=%s AND co.departamento_id=%s
    ORDER BY co.id, cm.id
"""
PERSONALIZADOS_ASIGN_V199_SQL = """
    SELECT id AS asignacion_id, comision_id,
           COALESCE(usa_horario_personalizado,FALSE) AS usa_horario_personalizado
    FROM asignaciones_docentes_comision
    WHERE institucion_id=%s AND departamento_id=%s
"""
PERSONALIZADOS_HRS_V199_SQL = """
    SELECT id, asignacion_id, horario_comision_id, dia, hora_inicio, hora_fin, horas, observaciones
    FROM horarios_asignacion_docente_comision
    WHERE institucion_id=%s AND departamento_id=%s
    ORDER BY asignacion_id,
             CASE dia WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3
                      WHEN 'Jueves' THEN 4 WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6
                      WHEN 'Domingo' THEN 7 ELSE 99 END, hora_inicio
"""

# --- v195 superposiciones (l. 43646) -----------------------------------------------------------------------------
SUPERPOSICIONES_V195_SQL = """
    WITH base AS (
        SELECT
            a.id AS asignacion_id,
            a.cuil,
            a.comision_id,
            COALESCE(a.usa_horario_personalizado, FALSE) AS personalizado,
            co.nombre_comision,
            co.materia_id,
            COALESCE(co.materia_especifica, '') AS materia_especifica,
            COALESCE(m.codigo, '') AS codigo_materia,
            COALESCE(m.asignatura, '') AS asignatura,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL
                    THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE a.cuil
            END AS docente
        FROM asignaciones_docentes_comision a
        JOIN comisiones co ON co.id=a.comision_id
        LEFT JOIN materias m
               ON m.id=co.materia_id
              AND m.institucion_id=co.institucion_id
        LEFT JOIN docentes doc
               ON doc.institucion_id=a.institucion_id
              AND doc.departamento_id=a.departamento_id
              AND regexp_replace(COALESCE(doc.cuil,''), '[^0-9]', '', 'g') =
                  regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g')
        WHERE a.institucion_id=%s
          AND a.departamento_id=%s
          AND co.institucion_id=%s
          AND co.departamento_id=%s
          AND co.periodo_id=%s
          AND COALESCE(a.estado,'Activa')='Activa'
          AND COALESCE(co.estado,'Activa')='Activa'
    ),
    reales AS (
        SELECT
            b.*, ha.dia, ha.hora_inicio, ha.hora_fin, ha.horas
        FROM base b
        JOIN horarios_asignacion_docente_comision ha
          ON ha.asignacion_id=b.asignacion_id
         AND ha.institucion_id=%s
         AND ha.departamento_id=%s
        WHERE b.personalizado=TRUE

        UNION ALL

        SELECT
            b.*, h.dia, h.hora_inicio, h.hora_fin, h.horas
        FROM base b
        JOIN horarios_comision h
          ON h.comision_id=b.comision_id
         AND h.institucion_id=%s
         AND h.departamento_id=%s
        WHERE b.personalizado=FALSE
    )
    SELECT *
    FROM reales
    ORDER BY cuil,
             CASE dia
                WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2
                WHEN 'Miércoles' THEN 3 WHEN 'Jueves' THEN 4
                WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6
                WHEN 'Domingo' THEN 7 ELSE 99
             END,
             hora_inicio, comision_id
"""

# --- sedes (get_auth_conn, l. 18167) ------------------------------------------------------------------------------
SEDES_SQL = """
    SELECT id, institucion_id, nombre, direccion, localidad, estado, observaciones,
           fecha_creacion, fecha_actualizacion
    FROM sedes_institucion
    WHERE institucion_id = %s {filtro}
    ORDER BY CASE WHEN estado = 'Activa' THEN 0 ELSE 1 END, nombre
"""



class ComisionesRepository(DesignacionesRepository):
    def __init__(self, conn, institution_id: int, department_id: int):
        super().__init__(conn, institution_id, department_id)

    # --- primitivas de DataFrame
    def read_sql(self, sql: str, params: Iterable[Any] = ()) -> pd.DataFrame:
        """``pd.read_sql`` sobre la conexion certificada (``coerce_float``: numeric -> float)."""
        with self._conn.cursor() as cur:
            cur.execute(sql, list(params))
            cols = [d.name for d in cur.description] if cur.description else []
            rows = cur.fetchall() if cur.description else []
        return pd.DataFrame.from_records(rows, columns=cols, coerce_float=True)

    def read_raw(self, sql: str, params: Iterable[Any] = ()) -> pd.DataFrame:
        """``_pg_read_dataframe``: ``pd.DataFrame(rows, columns=cols)`` (numeric queda Decimal)."""
        with self._conn.cursor() as cur:
            cur.execute(sql, list(params))
            cols = [d.name for d in cur.description] if cur.description else []
            rows = cur.fetchall() if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    def materias(self) -> MateriasRepository:
        return MateriasRepository(self._conn, self.inst)

    # --- lecturas
    def comisiones_v197(self, periodo_id: Optional[int], solo_activas: bool) -> pd.DataFrame:
        filtros = ["co.institucion_id=%s", "co.departamento_id=%s"]
        params: list = [self.inst, self.dep]
        if periodo_id is not None:
            filtros.append("co.periodo_id=%s")
            params.append(int(periodo_id))
        if solo_activas:
            filtros.append("COALESCE(co.estado,'Activa')='Activa'")
        sql = COMISIONES_V197_SQL.replace("{where}", " AND ".join(filtros))
        return self.read_raw(sql, [self.inst, self.dep] * 3 + params)

    def horarios_periodo(self, periodo_id: int) -> pd.DataFrame:
        return self.read_sql(HORARIOS_PERIODO_SQL, self._scope * 2 + [periodo_id] + self._scope)

    def asignaciones_periodo(self, periodo_id: int) -> pd.DataFrame:
        return self.read_sql(ASIGNACIONES_PERIODO_SQL, self._scope * 3 + [periodo_id] + self._scope)

    def integradas_horarios(self, periodo_id: int) -> pd.DataFrame:
        return self.read_sql(INTEGRADAS_HORARIOS_SQL, self._scope + [periodo_id] + self._scope)

    def integradas_asignaciones(self, periodo_id: int) -> pd.DataFrame:
        return self.read_sql(INTEGRADAS_ASIGNACIONES_SQL, self._scope * 2 + [periodo_id] + self._scope)

    def modificaciones(self, periodo_id: Optional[int]) -> pd.DataFrame:
        sql = MODIFICACIONES_SQL.replace("{periodo}", "" if periodo_id is None else " AND m.periodo_id = %s")
        params = ["%Comisión ID%", "%Comisión ID%"] + ([] if periodo_id is None else [int(periodo_id)])
        return self.read_sql(sql, params + self._scope)

    def movimientos_en_curso(self, comision_id: int, periodo_id: Optional[int]) -> pd.DataFrame:
        sql = MOVIMIENTOS_EN_CURSO_SQL.replace("{periodo}", "" if periodo_id is None else " AND m.periodo_id = %s")
        marca = f"%Comisión ID {int(comision_id)}%"
        return self.read_sql(sql, [marca, marca] + ([] if periodo_id is None else [int(periodo_id)]) + self._scope)

    def horarios_todos_v199(self) -> pd.DataFrame:
        return self.read_raw(HORARIOS_TODOS_V199_SQL, self._scope)

    def asignaciones_todas_v199(self) -> pd.DataFrame:
        return self.read_raw(ASIGNACIONES_TODAS_V199_SQL, self._scope)

    def vinculos_todos_v199(self) -> pd.DataFrame:
        return self.read_raw(VINCULOS_TODOS_V199_SQL, self._scope)

    def personalizados_v199(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        return self.read_raw(PERSONALIZADOS_ASIGN_V199_SQL, self._scope), \
            self.read_raw(PERSONALIZADOS_HRS_V199_SQL, self._scope)

    def superposiciones_v195(self, periodo_id: int) -> pd.DataFrame:
        return self.read_raw(SUPERPOSICIONES_V195_SQL, self._scope * 2 + [int(periodo_id)] + self._scope * 2)

    def sedes(self, solo_activas: bool) -> pd.DataFrame:
        sql = SEDES_SQL.replace("{filtro}", " AND estado = 'Activa'" if solo_activas else "")
        return self.read_sql(sql, [self.inst])

    def duplicada_fallback(self, periodo_id, nombre_comision, turno, sede, modalidad, materia_id,
                           opcion_curricular_id, excluir_id) -> pd.DataFrame:
        """Fallback conservador de ``existe_comision_duplicada`` (l. 28843): ``SELECT *`` por ``get_conn()``."""
        filtros = [
            "periodo_id = %s",
            "UPPER(TRIM(COALESCE(nombre_comision, ''))) = UPPER(TRIM(%s))",
            "UPPER(TRIM(COALESCE(turno, ''))) = UPPER(TRIM(%s))",
            "UPPER(TRIM(COALESCE(sede, ''))) = UPPER(TRIM(%s))",
            "UPPER(TRIM(COALESCE(modalidad, ''))) = UPPER(TRIM(%s))",
        ]
        params = [periodo_id, nombre_comision, turno, sede, modalidad]
        if opcion_curricular_id not in [None, ""]:
            filtros.append("opcion_curricular_id = %s")
            params.append(int(opcion_curricular_id))
        filtros.append("materia_id = %s")
        params.append(int(materia_id))
        if excluir_id is not None:
            filtros.append("id <> %s")
            params.append(int(excluir_id))
        sql = ("SELECT * FROM comisiones WHERE " + " AND ".join(filtros)
               + " AND (comisiones.institucion_id = %s) AND (comisiones.departamento_id = %s) LIMIT 1")
        return self.read_sql(sql, params + self._scope)

    # --- get_designaciones (l. 32479).  El certificado ordena sin desempate por ``d.id`` y el plantel historico de
    # Comisiones arma ``detalle_designaciones`` en ese orden: dentro de un mismo docente el orden quedaba librado al
    # orden fisico de las filas (cambia con cualquier edicion).  Etapa 5 / Tanda C (C1): se usa la consulta de
    # Designaciones NEXT, que desempata por ``d.id`` (mismo orden certificado en todo lo que no empata).
    def designaciones(self, period_id: int) -> list[dict]:
        p = self._scope + self._scope + [int(period_id)] + self._scope
        return self._all(DESIGNACIONES_SQL, p)
