"""SQL de Investigacion sobre una conexion/transaccion ya abierta.  Nunca crea ni altera tablas y nunca confirma.

Cada sentencia es la del entry certificado con el ambito de la conexion certificada que la ejecuta:
- ``get_conn()`` + inyector B12B v193 re-enlazado por B12J: ``proyectos_investigacion`` es tabla INSTITUCIONAL
  (``institucion_id``), ``investigacion_docente`` / ``periodos`` / ``docentes`` son de DEPARTAMENTO (``institucion_id`` +
  ``departamento_id``); en un LEFT JOIN el filtro va en el ``ON``; ``departamentos`` no se toca.  Texto obtenido con
  ``tests/tools_comisiones_inject_sql.py`` sobre el SQL del entry.  Se lee como ``pd.read_sql`` -> ``read_sql``.
- ``_pg_raw_conn()`` / ``_pg_read_dataframe`` (writers de proyecto, v199, v217, v263, v261/v267, rama
  ``todos_departamentos``): sin inyector, con el ambito explicito del SQL certificado -> ``read_raw`` / ``_mutate``.
Hereda de ``ComisionesRepository`` (sin modificarlo) las primitivas, los periodos, ``insert_movement`` y las lecturas que
usan el padron v240 y la capacidad v184 ya portados.

Origen: entry l. 21215-22190, 45295-45380, 46111-46235, 48204-48323, 49057-49200, 50832-50871, 51221-51294,
54938-54973, 53142-53160.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

import pandas as pd

from comisiones.repository import ComisionesRepository
from designaciones.repository import _numeric

_INST = "(proyectos_investigacion.institucion_id = %s)"
_DEP = "(investigacion_docente.institucion_id = %s) AND (investigacion_docente.departamento_id = %s)"

# --- _proyecto_investigacion_por_id (l. 21215, get_conn) ---------------------------------------------------------
PROYECTO_POR_ID_SQL = """
    SELECT pr.id, pr.nombre_proyecto,
        COALESCE(pr.codigo_proyecto, '') AS codigo_proyecto,
        COALESCE(pr.instituto_proyecto, '') AS instituto_proyecto,
        pr.anio_llamado, pr.fecha_inicio, pr.fecha_fin,
        COALESCE(pr.periodo_ejecucion, '') AS periodo_ejecucion,
        COALESCE(pr.observaciones, '') AS observaciones,
        COALESCE(pr.estado, 'Activo') AS estado, pr.fecha_carga,
        pr.fecha_suspension,
        COALESCE(pr.motivo_suspension, '') AS motivo_suspension,
        pr.departamento_id AS departamento_creador_id,
        COALESCE(dep.nombre, '') AS departamento_creador
    FROM proyectos_investigacion pr
    LEFT JOIN departamentos dep ON dep.id = pr.departamento_id
    WHERE pr.id = %s AND (pr.institucion_id = %s) LIMIT 1
"""

# --- catalogo v199 (l. 45295, _pg_read_dataframe) ----------------------------------------------------------------
PROYECTOS_BULK_V199_SQL = """
    WITH agg AS (
        SELECT
            proyecto_id,
            COUNT(*) FILTER (WHERE COALESCE(estado_asignacion,'Activa')='Activa') AS cantidad_asignaciones,
            COUNT(*) FILTER (WHERE LOWER(TRIM(COALESCE(estado_asignacion,'Activa'))) <> 'baja') AS cantidad_asignaciones_historicas,
            COUNT(*) AS cantidad_asignaciones_registradas,
            COUNT(DISTINCT cuil) FILTER (WHERE COALESCE(estado_asignacion,'Activa')='Activa') AS cantidad_docentes,
            COUNT(DISTINCT cuil) AS cantidad_docentes_historicos,
            COUNT(DISTINCT departamento_id) AS cantidad_departamentos,
            COALESCE(SUM(horas_asignadas) FILTER (WHERE LOWER(TRIM(COALESCE(estado_asignacion,'Activa'))) <> 'baja'),0) AS horas_asignadas_historicas
        FROM investigacion_docente
        WHERE institucion_id=%s
        GROUP BY proyecto_id
    )
    SELECT
        pr.id, pr.nombre_proyecto,
        COALESCE(pr.codigo_proyecto,'') AS codigo_proyecto,
        COALESCE(pr.instituto_proyecto,'') AS instituto_proyecto,
        pr.anio_llamado, pr.fecha_inicio, pr.fecha_fin,
        COALESCE(pr.periodo_ejecucion,'') AS periodo_ejecucion,
        COALESCE(pr.observaciones,'') AS observaciones,
        COALESCE(pr.estado,'Activo') AS estado,
        pr.fecha_carga, pr.fecha_suspension,
        COALESCE(pr.motivo_suspension,'') AS motivo_suspension,
        pr.departamento_id AS departamento_creador_id,
        COALESCE(dep.nombre,'') AS departamento_creador,
        COALESCE(a.cantidad_asignaciones,0) AS cantidad_asignaciones,
        COALESCE(a.cantidad_asignaciones_historicas,0) AS cantidad_asignaciones_historicas,
        COALESCE(a.cantidad_asignaciones_registradas,0) AS cantidad_asignaciones_registradas,
        COALESCE(a.cantidad_docentes,0) AS cantidad_docentes,
        COALESCE(a.cantidad_docentes_historicos,0) AS cantidad_docentes_historicos,
        COALESCE(a.cantidad_departamentos,0) AS cantidad_departamentos,
        COALESCE(a.horas_asignadas_historicas,0) AS horas_asignadas_historicas
    FROM proyectos_investigacion pr
    LEFT JOIN departamentos dep
      ON dep.id=pr.departamento_id AND dep.institucion_id=pr.institucion_id
    LEFT JOIN agg a ON a.proyecto_id=pr.id
    WHERE pr.institucion_id=%s {filtro}
    ORDER BY COALESCE(pr.fecha_fin, '9999-12-31') DESC, pr.nombre_proyecto
"""

# --- get_investigacion_docente base (l. 22041) --------------------------------------------------------------------
_ASIG_COLS = """
        i.rol, COALESCE(pr.anio_llamado, i.anio_llamado) AS anio_llamado,
        pr.fecha_inicio, pr.fecha_fin,
        COALESCE(NULLIF(pr.periodo_ejecucion, ''), i.periodo_ejecucion, '') AS periodo_ejecucion,
        COALESCE(pr.estado, 'Activo') AS estado_proyecto,
        COALESCE(i.estado_asignacion, 'Activa') AS estado_asignacion,
        i.horas_asignadas, i.observaciones, i.fecha_carga, i.fecha_baja,
        COALESCE(i.motivo_baja, '') AS motivo_baja,
        i.departamento_id AS departamento_asignacion_id,
        COALESCE(dep.nombre, '') AS departamento_asignacion"""
_ASIG_PROY = """
        COALESCE(NULLIF(pr.nombre_proyecto, ''), i.nombre_proyecto, '') AS nombre_proyecto,
        COALESCE(NULLIF(pr.codigo_proyecto, ''), i.codigo_proyecto, '') AS codigo_proyecto,
        COALESCE(NULLIF(pr.instituto_proyecto, ''), i.instituto_proyecto, '') AS instituto_proyecto,"""
# Rama local (get_conn + inyector): params [inst, dep, inst, dep, inst] + filtros + [inst, dep].
ASIG_LOCAL_SQL = f"""
    SELECT i.id, i.proyecto_id, i.periodo_id, p.nombre AS periodo,
        p.anio AS periodo_anio, p.semestre AS periodo_semestre, i.cuil,
        CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
             WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE i.cuil END AS docente,{_ASIG_PROY}{_ASIG_COLS}
    FROM investigacion_docente i
    LEFT JOIN periodos p ON (p.id = i.periodo_id) AND (p.institucion_id = %s) AND (p.departamento_id = %s)
    LEFT JOIN docentes doc ON (doc.cuil = i.cuil) AND (doc.institucion_id = %s) AND (doc.departamento_id = %s)
    LEFT JOIN proyectos_investigacion pr ON (pr.id = i.proyecto_id) AND (pr.institucion_id = %s)
    LEFT JOIN departamentos dep ON dep.id = i.departamento_id
    WHERE {{where}}(i.institucion_id = %s) AND (i.departamento_id = %s)
    ORDER BY COALESCE(p.anio,0) DESC, COALESCE(p.semestre,0) DESC, docente, nombre_proyecto
"""
# Rama ``todos_departamentos`` (_pg_read_dataframe): igual a ``comisiones/proyectos.py`` PROYECTOS_TODOS_SQL.
PERIODO_REF_CTE = """
    WITH periodo_ref AS (
        SELECT id, institucion_id, nombre, anio, semestre
        FROM periodos
        WHERE id = %s
        LIMIT 1
    )
"""

# --- v217 (l. 48204 / 48268, _pg_read_dataframe) ------------------------------------------------------------------
BUSCAR_ACTIVA_V217_SQL = """
    WITH objetivo AS (
        SELECT nombre, anio, semestre
        FROM periodos
        WHERE id=%s AND institucion_id=%s
        LIMIT 1
    )
    SELECT a.id, a.proyecto_id, a.cuil, a.rol, a.horas_asignadas,
           a.departamento_id AS departamento_asignacion_id,
           COALESCE(dep.nombre,'') AS departamento_asignacion,
           COALESCE(p.nombre,'') AS periodo
    FROM investigacion_docente a
    JOIN periodos p ON p.id=a.periodo_id
                   AND p.institucion_id=a.institucion_id
                   AND p.departamento_id=a.departamento_id
    CROSS JOIN objetivo o
    LEFT JOIN departamentos dep ON dep.id=a.departamento_id AND dep.institucion_id=a.institucion_id
    WHERE a.institucion_id=%s
      AND a.proyecto_id=%s
      AND REGEXP_REPLACE(COALESCE(a.cuil,''), '[^0-9]', '', 'g')=%s
      AND COALESCE(a.estado_asignacion,'Activa')='Activa'
      AND ((p.anio=o.anio AND p.semestre=o.semestre) OR COALESCE(p.nombre,'')=COALESCE(o.nombre,''))
"""
INTEGRANTES_V217_SQL = """
    WITH objetivo AS (
        SELECT nombre, anio, semestre
        FROM periodos
        WHERE id=%s AND institucion_id=%s
        LIMIT 1
    )
    SELECT a.id, a.proyecto_id, a.periodo_id, a.cuil,
           CASE
               WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
               WHEN doc.nombre IS NOT NULL THEN doc.nombre
               ELSE a.cuil
           END AS docente,
           COALESCE(pr.nombre_proyecto, a.nombre_proyecto, '') AS nombre_proyecto,
           COALESCE(pr.codigo_proyecto, a.codigo_proyecto, '') AS codigo_proyecto,
           COALESCE(pr.instituto_proyecto, a.instituto_proyecto, '') AS instituto_proyecto,
           a.rol, a.horas_asignadas, COALESCE(a.observaciones,'') AS observaciones,
           a.fecha_carga, COALESCE(a.estado_asignacion,'Activa') AS estado_asignacion,
           COALESCE(p.nombre,'') AS periodo,
           a.departamento_id AS departamento_asignacion_id,
           COALESCE(dep.nombre,'') AS departamento_asignacion
    FROM investigacion_docente a
    JOIN periodos p ON p.id=a.periodo_id
                   AND p.institucion_id=a.institucion_id
                   AND p.departamento_id=a.departamento_id
    CROSS JOIN objetivo o
    LEFT JOIN proyectos_investigacion pr ON pr.id=a.proyecto_id AND pr.institucion_id=a.institucion_id
    LEFT JOIN docentes doc ON doc.institucion_id=a.institucion_id
                          AND doc.departamento_id=a.departamento_id
                          AND doc.cuil=a.cuil
    LEFT JOIN departamentos dep ON dep.id=a.departamento_id AND dep.institucion_id=a.institucion_id
    WHERE a.institucion_id=%s
      AND a.proyecto_id=%s
      AND COALESCE(a.estado_asignacion,'Activa')='Activa'
      AND ((p.anio=o.anio AND p.semestre=o.semestre) OR COALESCE(p.nombre,'')=COALESCE(o.nombre,''))
    ORDER BY departamento_asignacion, docente, a.id
"""

# --- actos v263 / v261 / v267 ------------------------------------------------------------------------------------
DOCUMENTOS_PROYECTOS_V263_SQL = """
    SELECT rp.proyecto_id, d.id AS documento_id,
           COALESCE(d.tipo_documento,'') AS tipo_documento,
           COALESCE(d.numero,'') AS numero,
           COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                    CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                         WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora,
           d.fecha, COALESCE(d.categoria,'') AS categoria,
           COALESCE(d.detalle,'') AS detalle
    FROM documentos_respaldo_proyectos rp
    JOIN documentos_respaldo d
      ON d.id=rp.documento_id
     AND d.institucion_id=rp.institucion_id
     AND d.departamento_id=rp.departamento_id
    LEFT JOIN dependencias_documentales depdoc
      ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
    WHERE rp.institucion_id=%s
      AND LOWER(TRIM(rp.proyecto_tipo))=%s
      AND rp.proyecto_id IN ({placeholders})
    ORDER BY d.fecha DESC NULLS LAST, d.id DESC
"""
UPSERT_DOCUMENTO_PROYECTO_SQL = """
    INSERT INTO documentos_respaldo_proyectos
        (institucion_id, departamento_id, documento_id, proyecto_tipo, proyecto_id,
         proyecto_nombre, codigo_proyecto)
    VALUES (%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (institucion_id, departamento_id, documento_id, proyecto_tipo, proyecto_id)
    DO UPDATE SET proyecto_nombre=EXCLUDED.proyecto_nombre,
                  codigo_proyecto=EXCLUDED.codigo_proyecto
"""
DESVINCULAR_DOCUMENTO_PROYECTOS_SQL = (
    "DELETE FROM documentos_respaldo_proyectos WHERE institucion_id=%s AND departamento_id=%s AND documento_id=%s "
    "AND LOWER(TRIM(proyecto_tipo))=LOWER(TRIM(%s)) AND proyecto_id IN ({ph})")

# --- writers de proyecto (get_conn + inyector / _pg_raw_conn) ------------------------------------------------------
DUP_CODIGO_SQL = ("SELECT id FROM proyectos_investigacion WHERE UPPER(TRIM(COALESCE(codigo_proyecto, ''))) = "
                  f"UPPER(TRIM(%s)) AND {_INST} LIMIT 1")
DUP_NOMBRE_FECHAS_SQL = ("SELECT id FROM proyectos_investigacion WHERE UPPER(TRIM(COALESCE(nombre_proyecto, ''))) = "
                         f"UPPER(TRIM(%s)) AND fecha_inicio = %s AND fecha_fin = %s AND {_INST} LIMIT 1")
INSERT_PROYECTO_SQL = ("INSERT INTO proyectos_investigacion (departamento_id, nombre_proyecto, codigo_proyecto, "
                       "instituto_proyecto, anio_llamado, fecha_inicio, fecha_fin, periodo_ejecucion, observaciones, "
                       "estado, fecha_carga, institucion_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)  "
                       "RETURNING id")
DUP_OTRO_CODIGO_SQL = """
    SELECT id FROM proyectos_investigacion
    WHERE institucion_id = %s
      AND id <> %s
      AND UPPER(TRIM(COALESCE(codigo_proyecto, ''))) = UPPER(TRIM(%s))
    LIMIT 1
"""
DUP_OTRO_NOMBRE_SQL = """
    SELECT id FROM proyectos_investigacion
    WHERE institucion_id = %s
      AND id <> %s
      AND UPPER(TRIM(COALESCE(nombre_proyecto, ''))) = UPPER(TRIM(%s))
      AND fecha_inicio = %s AND fecha_fin = %s
    LIMIT 1
"""
UPDATE_PROYECTO_SQL = """
    UPDATE proyectos_investigacion
    SET nombre_proyecto=%s, codigo_proyecto=%s, instituto_proyecto=%s,
        anio_llamado=%s, fecha_inicio=%s, fecha_fin=%s,
        periodo_ejecucion=%s, observaciones=%s, estado=%s
    WHERE id=%s AND institucion_id=%s
"""
UPDATE_ASIG_DESNORMALIZADAS_SQL = """
    UPDATE investigacion_docente
    SET nombre_proyecto=%s, codigo_proyecto=%s, instituto_proyecto=%s,
        anio_llamado=%s, periodo_ejecucion=%s
    WHERE proyecto_id=%s AND institucion_id=%s
"""
NOMBRE_PERIODO_DEP_SQL = """
    SELECT nombre
    FROM periodos
    WHERE id=%s AND institucion_id=%s AND departamento_id=%s
    LIMIT 1
"""
SUSPENDER_PROYECTO_SQL = """
    UPDATE proyectos_investigacion
    SET estado='Suspendido', fecha_suspension=%s, motivo_suspension=%s,
        observaciones=%s
    WHERE id=%s AND institucion_id=%s
"""
SUSPENDER_ASIGNACIONES_SQL = """
    UPDATE investigacion_docente i
    SET estado_asignacion='Baja', fecha_baja=%s, motivo_baja=%s
    FROM periodos p
    WHERE i.periodo_id=p.id
      AND i.institucion_id=%s
      AND p.institucion_id=%s
      AND p.nombre=%s
      AND i.proyecto_id=%s
      AND COALESCE(i.estado_asignacion, 'Activa')='Activa'
"""
ARCHIVAR_PROYECTO_SQL = f"UPDATE proyectos_investigacion SET estado='Archivado', observaciones=%s WHERE id=%s AND {_INST} "
PROYECTO_NOMBRE_CODIGO_SQL = """
    SELECT nombre_proyecto, COALESCE(codigo_proyecto, '')
    FROM proyectos_investigacion
    WHERE id=%s AND institucion_id=%s
    LIMIT 1
"""
CONTAR_ASIG_PROYECTO_SQL = """
    SELECT COUNT(*)
    FROM investigacion_docente
    WHERE proyecto_id=%s AND institucion_id=%s
"""
DELETE_ASIG_PROYECTO_SQL = "DELETE FROM investigacion_docente WHERE proyecto_id=%s AND institucion_id=%s"
DELETE_PROYECTO_SQL = "DELETE FROM proyectos_investigacion WHERE id=%s AND institucion_id=%s"

# --- writers de asignacion --------------------------------------------------------------------------------------
DUP_LOCAL_ASIG_SQL = ("SELECT id FROM investigacion_docente WHERE periodo_id=%s AND cuil=%s AND proyecto_id=%s "
                      f"AND COALESCE(estado_asignacion, 'Activa')='Activa' AND {_DEP} LIMIT 1")
INSERT_ASIG_SQL = ("INSERT INTO investigacion_docente (proyecto_id, periodo_id, cuil, nombre_proyecto, rol, anio_llamado, "
                   "periodo_ejecucion, horas_asignadas, observaciones, fecha_carga, codigo_proyecto, instituto_proyecto, "
                   "estado_asignacion, fecha_baja, motivo_baja, institucion_id, departamento_id) VALUES (%s, %s, %s, %s, "
                   "%s, %s, %s, %s, %s, %s, %s, %s, 'Activa', NULL, NULL, %s, %s)  RETURNING id")
UPDATE_ASIG_SQL = ("UPDATE investigacion_docente SET proyecto_id=%s, periodo_id=%s, cuil=%s, nombre_proyecto=%s, rol=%s, "
                   "anio_llamado=%s, periodo_ejecucion=%s, horas_asignadas=%s, observaciones=%s, codigo_proyecto=%s, "
                   f"instituto_proyecto=%s WHERE id=%s AND {_DEP} ")
BAJA_ASIG_SQL = (f"UPDATE investigacion_docente SET estado_asignacion='Baja', fecha_baja=%s, motivo_baja=%s WHERE id=%s "
                 f"AND {_DEP} ")
ASIG_POR_ID_INST_SQL = """
    SELECT id, institucion_id, departamento_id, cuil, proyecto_id
    FROM investigacion_docente
    WHERE id = %s AND institucion_id = %s
    LIMIT 1
"""
DELETE_ASIG_SQL = """
    DELETE FROM investigacion_docente
    WHERE id = %s AND institucion_id = %s
"""

# --- carga rapida de asignaciones v217 (l. 49057, _pg_raw_conn) ------------------------------------------------------
PERIODO_INST_SQL = "SELECT nombre, anio, semestre FROM periodos WHERE id=%s AND institucion_id=%s LIMIT 1"
PARES_ACTIVOS_SQL = """
    SELECT a.proyecto_id, REGEXP_REPLACE(COALESCE(a.cuil,''), '[^0-9]', '', 'g') AS cuil_key
    FROM investigacion_docente a
    JOIN periodos p ON p.id=a.periodo_id AND p.institucion_id=a.institucion_id AND p.departamento_id=a.departamento_id
    WHERE a.institucion_id=%s
      AND COALESCE(a.estado_asignacion,'Activa')='Activa'
      AND ((p.anio=%s AND p.semestre=%s) OR COALESCE(p.nombre,'')=COALESCE(%s,''))
"""
INSERT_ASIG_EXCEL_SQL = """
    INSERT INTO investigacion_docente
    (institucion_id, departamento_id, proyecto_id, periodo_id, cuil, nombre_proyecto, rol,
     anio_llamado, periodo_ejecucion, horas_asignadas, observaciones, fecha_carga,
     codigo_proyecto, instituto_proyecto, estado_asignacion, fecha_baja, motivo_baja)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Activa',NULL,NULL)
    RETURNING id
"""
INSERT_MOVIMIENTO_EXCEL_SQL = """
    INSERT INTO movimientos
    (institucion_id, departamento_id, periodo_id, fecha, tipo_movimiento, cuil, nombre, detalle, observaciones, horas_variacion)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""

# --- consolidado v240 (l. 53142) -----------------------------------------------------------------------------------
DEPARTAMENTOS_ACTIVOS_SQL = """
    SELECT id, nombre
    FROM departamentos
    WHERE institucion_id=%s
      AND COALESCE(estado,'Activo')='Activo'
    ORDER BY nombre
"""


class InvestigacionRepository(ComisionesRepository):
    """Repositorio de la operacion: ``_scope`` = [institucion, departamento] de la sesion revalidada."""

    # --- lecturas de proyectos
    def proyecto_por_id(self, proyecto_id: int) -> pd.DataFrame:
        return self.read_sql(PROYECTO_POR_ID_SQL, [int(proyecto_id), self.inst])

    def proyectos_bulk_v199(self, solo_activos: bool) -> pd.DataFrame:
        filtro = "AND COALESCE(pr.estado, 'Activo')='Activo'" if solo_activos else ""
        return self.read_raw(PROYECTOS_BULK_V199_SQL.replace("{filtro}", filtro), [self.inst, self.inst])

    # --- lecturas de asignaciones
    def asignaciones_local(self, cuil: Optional[str], periodo_id: Optional[int], incluir_bajas: bool) -> pd.DataFrame:
        filtros, params = [], []
        if cuil is not None:
            filtros.append("i.cuil = %s")
            params.append(cuil)
        if periodo_id is not None:
            filtros.append("i.periodo_id = %s")
            params.append(int(periodo_id))
        if not incluir_bajas:
            filtros.append("COALESCE(i.estado_asignacion, 'Activa') = 'Activa'")
        where = "".join(f"{f} AND " for f in filtros)
        return self.read_sql(ASIG_LOCAL_SQL.replace("{where}", where),
                             self._scope * 2 + [self.inst] + params + self._scope)

    def buscar_activa_v217(self, periodo_id: int, proyecto_id: int, cuil_key: str,
                           excluir_id: Optional[int] = None) -> pd.DataFrame:
        sql = BUSCAR_ACTIVA_V217_SQL
        params = [int(periodo_id), self.inst, self.inst, int(proyecto_id), cuil_key]
        if excluir_id is not None:
            sql += " AND a.id<>%s"
            params.append(int(excluir_id))
        sql += " ORDER BY a.id LIMIT 1"
        return self.read_raw(sql, params)

    def integrantes_v217(self, proyecto_id: int, periodo_id: int) -> pd.DataFrame:
        return self.read_raw(INTEGRANTES_V217_SQL, [int(periodo_id), self.inst, self.inst, int(proyecto_id)])

    def documentos_proyectos_v263(self, tipo: str, ids: list[int]) -> pd.DataFrame:
        ph = ",".join(["%s"] * len(ids))
        return self.read_raw(DOCUMENTOS_PROYECTOS_V263_SQL.replace("{placeholders}", ph), [self.inst, tipo] + list(ids))

    def departamentos_activos(self) -> pd.DataFrame:
        return self.read_raw(DEPARTAMENTOS_ACTIVOS_SQL, [self.inst])

    def call(self, fn):
        """Ejecuta ``fn(repo)`` sobre esta conexion (en un writer, el repositorio perezoso abre una conexion propia)."""
        return fn(self)

    def fetch_one(self, sql: str, params: Iterable[Any]) -> Optional[tuple]:
        """``cursor.fetchone()`` de la conexion certificada (tupla)."""
        with self._conn.cursor() as cur:
            cur.execute(sql, list(params))
            return cur.fetchone()

    def fetch_all(self, sql: str, params: Iterable[Any]) -> list[tuple]:
        with self._conn.cursor() as cur:
            cur.execute(sql, list(params))
            return list(cur.fetchall())

    def mutate_rowcount(self, sql: str, params: Iterable[Any]) -> int:
        """``cur.execute`` mutante con ``cur.rowcount`` crudo (puede ser 0)."""
        return self._mutate(sql, params)


__all__ = ["InvestigacionRepository", "_numeric"]
