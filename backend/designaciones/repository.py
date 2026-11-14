"""SQL de Designaciones sobre una conexion/transaccion ya abierta.  Nunca crea ni altera tablas y nunca confirma.

Cada sentencia es la del entry certificado con el ambito que le aplica la conexion certificada que la ejecuta:
- ``get_conn()`` + inyector B12B (``_pg_prepare_sql``; SELECT por ``_pg_scope_select`` v193 re-enlazado por B12J):
  tablas de DEPARTAMENTO (``designaciones``, ``docentes``, ``periodos``, ``movimientos``, ``comisiones``,
  ``asignaciones_docentes_comision``, ``documentos_respaldo*``) -> ``institucion_id`` + ``departamento_id``; en un
  ``LEFT JOIN`` el filtro va en el ``ON`` (B12J); en INSERT se agregan las dos columnas; en UPDATE/DELETE se agregan
  al WHERE de la tabla destino (las subconsultas no se tocan, igual que el inyector).
- ``_pg_raw_conn()`` / ``_pg_read_dataframe`` (vinculos v266, cargo prioritario v200, periodo del departamento):
  sin inyector; el SQL certificado lleva su ambito explicito y asi se reproduce.
Origen: entry l. 4424, 7789, 7838, 8434-9335, 9706-9760, 29724, 32479-33071, 34443-34646, 46512-46665,
52699-52806, 54344-54905, 55154-55479, 50430 (repositorio documental v249), 18020, 36408.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable, Optional

from psycopg import Connection
from psycopg.rows import dict_row

from docentes.repository import DOCENTE_EXISTE_SQL, DOCENTES_SQL
from periodos.repository import LAST_SQL, LIST_SQL, OPEN_SQL

from .rules import condicion_periodo_equivalente_sql

_DEP = "institucion_id = %s AND departamento_id = %s"


def _numeric(value: Any) -> Any:
    """Valor para una columna numeric tal como lo enlazaba psycopg2 (``repr`` del float; enteros sin cambio)."""
    if isinstance(value, float):
        return Decimal(repr(value))
    return value


def _scoped(alias: str) -> str:
    return f"({alias}.institucion_id = %s) AND ({alias}.departamento_id = %s)"


# --- periodos -----------------------------------------------------------------------------------------------
PERIOD_INFO_SQL = ("SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, COALESCE(estado, '') AS estado "
                   f"FROM periodos WHERE id = %s AND {_scoped('periodos')} LIMIT 1")
PERIOD_BY_NAME_SQL = ("SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones FROM periodos "
                      f"WHERE nombre = %s AND {_scoped('periodos')} LIMIT 1")
PERIOD_FIN_SQL = f"SELECT id, fecha_inicio, fecha_fin FROM periodos WHERE id = %s AND {_scoped('periodos')} LIMIT 1"
PERIOD_RAW_SQL = ("SELECT id, nombre, anio, semestre, institucion_id, departamento_id FROM periodos "
                  "WHERE id = %s LIMIT 1")
PERIOD_EQUIV_SQL = """
    SELECT id
    FROM periodos
    WHERE institucion_id = %s
      AND departamento_id = %s
      AND (nombre = %s OR (anio = %s AND semestre = %s))
    ORDER BY CASE WHEN COALESCE(estado, '') = 'Abierto' THEN 0 ELSE 1 END, id DESC
    LIMIT 1
"""
PERIODS_CONTEXT_V269_SQL = f"""
    SELECT id,nombre,anio,semestre,fecha_inicio,fecha_fin,estado
    FROM periodos
    WHERE {_scoped('periodos')}
    ORDER BY COALESCE(anio,0), COALESCE(semestre,0), COALESCE(fecha_inicio,''), id
"""

# --- get_designaciones (v95 l. 32479 + v162 l. 34443; v229 base reemplazada por v95) --------------------------
DESIGNACIONES_SQL = f"""
    SELECT d.id,d.periodo_id,per.nombre AS periodo,CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido||', '||doc.nombres WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE '' END AS nombre_completo,
        d.cuil,d.cargo,d.dedicacion,d.horas,d.tipo_designacion,COALESCE(d.numero_resolucion,'') AS numero_resolucion,d.ad_honorem,d.fecha_desde,d.fecha_hasta,
        COALESCE(NULLIF(d.fecha_hasta_prevista,''),d.fecha_hasta) AS fecha_hasta_prevista,d.fecha_finalizacion_efectiva,d.fecha_registro_finalizacion,d.motivo_finalizacion,
        CASE WHEN per.estado='Cerrado' AND d.estado='Activa' THEN 'Finalizada' ELSE d.estado END AS estado,d.observaciones,
        COALESCE(d.funcion_no_docente, 0) AS funcion_no_docente, COALESCE(d.texto_funcion_no_docente, '') AS texto_funcion_no_docente
    FROM designaciones d
    LEFT JOIN docentes doc ON (d.cuil=doc.cuil) AND {_scoped('doc')}
    LEFT JOIN periodos per ON (d.periodo_id=per.id) AND {_scoped('per')}
    WHERE d.periodo_id=%s AND {_scoped('d')}
    ORDER BY per.anio DESC,per.semestre DESC,doc.apellido,doc.nombres,d.id
"""
ACTOS_DESIGNACIONES_SQL = """
    SELECT r.designacion_id, d.id AS documento_id, d.tipo_documento,
           COALESCE(d.numero,'') AS numero, d.fecha,
           COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                    CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                         WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora
    FROM documentos_respaldo_designaciones r
    JOIN documentos_respaldo d ON d.id=r.documento_id
      AND d.institucion_id=r.institucion_id AND d.departamento_id=r.departamento_id
    LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
    WHERE r.institucion_id=%s AND r.departamento_id=%s
      AND r.designacion_id = ANY(%s)
"""
ACTOS_MOVIMIENTOS_SQL = """
    SELECT r.movimiento_id, d.id AS documento_id, d.tipo_documento,
           COALESCE(d.numero,'') AS numero, d.fecha,
           COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                    CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                         WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora
    FROM documentos_respaldo_movimientos r
    JOIN documentos_respaldo d ON d.id=r.documento_id
      AND d.institucion_id=r.institucion_id AND d.departamento_id=r.departamento_id
    LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
    WHERE r.institucion_id=%s AND r.departamento_id=%s
      AND r.movimiento_id = ANY(%s)
"""

DESIGNACION_REF_SQL = f"""
    SELECT id, periodo_id, cuil, cargo, dedicacion, horas, tipo_designacion,
           ad_honorem, fecha_desde, fecha_hasta, estado, observaciones
    FROM designaciones
    WHERE id = %s AND {_scoped('designaciones')}
    LIMIT 1
"""
DESIGNACION_STAR_SQL = f"SELECT * FROM designaciones WHERE id=%s AND {_scoped('designaciones')} LIMIT 1"
DESIGNACIONES_REFS_SQL = f"""
    SELECT id, periodo_id, cuil, cargo, dedicacion, horas, tipo_designacion,
           ad_honorem, fecha_desde, fecha_hasta, estado, observaciones
    FROM designaciones
    WHERE id = ANY(%s) AND {_scoped('designaciones')}
    ORDER BY id
"""

# existe_designacion_duplicada (l. 7838): los tres filtros opcionales ``(? IS NULL OR ...)`` se arman igual.
_MATCH_BASE = """
    WHERE periodo_id = %s
      AND TRIM(COALESCE(cuil, '')) = TRIM(%s)
      AND UPPER(TRIM(COALESCE(cargo, ''))) = UPPER(TRIM(%s))
      AND UPPER(TRIM(COALESCE(dedicacion, ''))) = UPPER(TRIM(%s))
      AND COALESCE(horas, 0) = %s
      AND UPPER(TRIM(COALESCE(tipo_designacion, ''))) = UPPER(TRIM(%s))
      AND UPPER(TRIM(COALESCE(ad_honorem, ''))) = UPPER(TRIM(%s))
      AND COALESCE(fecha_desde, '') = %s
      AND COALESCE(fecha_hasta, '') = %s
"""

INSERT_DESIGNACION_SQL = """
    INSERT INTO designaciones
    (periodo_id, cuil, cargo, dedicacion, horas, tipo_designacion, ad_honorem, fecha_desde, fecha_hasta, estado,
     observaciones, institucion_id, departamento_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
"""
UPDATE_BASE_SQL = f"""
    UPDATE designaciones
    SET cargo = %s, dedicacion = %s, horas = %s, tipo_designacion = %s, ad_honorem = %s,
        fecha_desde = %s, fecha_hasta = %s, estado = %s, observaciones = %s
    WHERE id = %s AND {_scoped('designaciones')}
"""
MOVEMENT_SQL = ("INSERT INTO movimientos (periodo_id, fecha, tipo_movimiento, cuil, nombre, detalle, observaciones, "
                "horas_variacion, institucion_id, departamento_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING id")

# --- historial (v266) ----------------------------------------------------------------------------------------
MOVIMIENTOS_PERIODO_SQL = f"""
    SELECT id, periodo_id, fecha, tipo_movimiento, cuil, nombre, detalle,
           COALESCE(observaciones,'') AS observaciones,
           COALESCE(horas_variacion,0) AS horas_variacion
    FROM movimientos
    WHERE periodo_id=%s AND {_scoped('movimientos')}
    ORDER BY fecha DESC, id DESC
"""
MOVIMIENTOS_CUIL_SQL = f"""
    SELECT id, periodo_id, cuil, nombre, fecha, tipo_movimiento, detalle,
           observaciones, COALESCE(horas_variacion, 0) AS horas_variacion
    FROM movimientos
    WHERE periodo_id = %s
      AND TRIM(COALESCE(cuil, '')) = TRIM(%s) AND {_scoped('movimientos')}
    ORDER BY id
"""
CONCURSADAS_CUIL_SQL = f"""
    SELECT fecha_desde,fecha_hasta,fecha_hasta_prevista,fecha_finalizacion_efectiva
    FROM designaciones
    WHERE TRIM(COALESCE(cuil,''))=TRIM(%s)
      AND UPPER(TRIM(COALESCE(tipo_designacion,'')))='CONCURSADO' AND {_scoped('designaciones')}
"""
NOMBRE_DOCENTE_SQL = f"""
    SELECT cuil,
           CASE
               WHEN TRIM(COALESCE(apellido, '')) <> '' OR TRIM(COALESCE(nombres, '')) <> ''
               THEN TRIM(COALESCE(apellido, '')) ||
                    CASE WHEN TRIM(COALESCE(apellido, '')) <> '' AND TRIM(COALESCE(nombres, '')) <> '' THEN ', ' ELSE '' END ||
                    TRIM(COALESCE(nombres, ''))
               ELSE TRIM(COALESCE(nombre, ''))
           END AS nombre_docente
    FROM docentes
    WHERE {_scoped('docentes')}
"""

# --- repositorio documental (get_documentos_respaldo_v249, columnas usadas por el selector v266) --------------
DOCUMENTOS_SQL = """
    SELECT d.id, d.tipo_documento, COALESCE(d.tipo_resolucion,'') AS tipo_resolucion, d.categoria, COALESCE(d.numero,'') AS numero,
           d.fecha, COALESCE(p.nombre,'') AS periodo,
           d.dependencia_id,
           COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                    CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                         WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora,
           COALESCE(d.titulo,'') AS titulo, COALESCE(d.detalle,'') AS detalle
    FROM documentos_respaldo d
    LEFT JOIN periodos p ON p.id=d.periodo_id AND p.institucion_id=d.institucion_id
                        AND p.departamento_id=d.departamento_id
    LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
    WHERE d.institucion_id=%s AND d.departamento_id=%s
    ORDER BY COALESCE(d.fecha, d.fecha_carga::date) DESC, d.id DESC
"""
LINK_DESIGNACION_SQL = """
    INSERT INTO documentos_respaldo_designaciones
        (institucion_id, departamento_id, documento_id, designacion_id, usuario_vinculacion)
    VALUES (%s,%s,%s,%s,%s)
    ON CONFLICT (institucion_id, departamento_id, designacion_id)
    DO UPDATE SET documento_id=EXCLUDED.documento_id,
                  fecha_vinculacion=CURRENT_TIMESTAMP,
                  usuario_vinculacion=EXCLUDED.usuario_vinculacion
"""
LINK_MOVIMIENTO_SQL = """
    INSERT INTO documentos_respaldo_movimientos
        (institucion_id, departamento_id, documento_id, movimiento_id, usuario_vinculacion)
    VALUES (%s,%s,%s,%s,%s)
    ON CONFLICT (institucion_id, departamento_id, movimiento_id)
    DO UPDATE SET documento_id=EXCLUDED.documento_id,
                  fecha_vinculacion=CURRENT_TIMESTAMP,
                  usuario_vinculacion=EXCLUDED.usuario_vinculacion
"""

# --- cargo prioritario v200 (conexion cruda: ambito explicito) -----------------------------------------------
DEPARTAMENTOS_INST_SQL = """
    SELECT id, nombre
    FROM departamentos
    WHERE institucion_id=%s
    ORDER BY id
"""
DOCENTES_TIPO_SQL = """
    SELECT cuil,
           COALESCE(tipo_docente,'Propio') AS tipo_docente,
           COALESCE(observaciones,'') AS observaciones
    FROM docentes
    WHERE institucion_id=%s
      AND departamento_id=%s
    ORDER BY id
"""
DESIGNACIONES_EQUIV_SQL = f"""
    WITH pr AS (
        SELECT id, institucion_id, nombre, anio, semestre
        FROM periodos
        WHERE id=%s
        LIMIT 1
    )
    SELECT
        d.cuil, d.cargo, d.departamento_id,
        COALESCE(dep.nombre,'') AS departamento
    FROM designaciones d
    JOIN periodos p ON p.id=d.periodo_id
    JOIN pr ON {condicion_periodo_equivalente_sql('p','pr')}
    LEFT JOIN departamentos dep ON dep.id=d.departamento_id
    WHERE d.institucion_id=%s
      AND d.estado='Activa'
      AND COALESCE(TRIM(d.cargo),'') <> ''
"""
UPDATE_ROL_SQL = f"""
    UPDATE asignaciones_docentes_comision
    SET rol = %s
    WHERE cuil = %s
      AND COALESCE(estado, 'Activa') = 'Activa'
      AND comision_id IN (
          SELECT id FROM comisiones WHERE periodo_id = %s
      ) AND {_scoped('asignaciones_docentes_comision')}
"""
# --- baja automatica de comisiones v214 (get_conn: inyector) --------------------------------------------------
DESIGNACIONES_ACTIVAS_CUIL_SQL = f"""
    SELECT id, estado, fecha_desde,
           COALESCE(NULLIF(fecha_hasta_prevista,''), fecha_hasta) AS fecha_hasta_limite,
           fecha_finalizacion_efectiva, COALESCE(funcion_no_docente,0) AS funcion_no_docente
    FROM designaciones
    WHERE periodo_id=%s AND TRIM(COALESCE(cuil,''))=TRIM(%s)
      AND COALESCE(estado,'Activa')='Activa' AND {_scoped('designaciones')}
    ORDER BY id
"""
ASIGNACIONES_ACTIVAS_SQL = f"""
    SELECT a.id, a.comision_id, a.cuil, a.rol, a.horas_asignadas,
           a.observaciones, c.nombre_comision
    FROM asignaciones_docentes_comision a
    JOIN comisiones c ON c.id=a.comision_id
    WHERE c.periodo_id=%s
      AND TRIM(COALESCE(a.cuil,''))=TRIM(%s)
      AND COALESCE(a.estado,'Activa')='Activa' AND {_scoped('a')} AND {_scoped('c')}
    ORDER BY a.id
"""
FINALIZAR_ASIGNACION_SQL = (f"UPDATE asignaciones_docentes_comision SET estado='Finalizada', observaciones=%s "
                            f"WHERE id=%s AND COALESCE(estado,'Activa')='Activa' AND "
                            f"{_scoped('asignaciones_docentes_comision')}")
# --- estado de consulta (l. 23858): DELETE + INSERT tal como los ejecuta el certificado tras el inyector de tenant
DELETE_ESTADO_CONSULTA_SQL = ("DELETE FROM estado_consulta_designacion WHERE periodo_id = %s AND cuil = %s AND "
                              "(estado_consulta_designacion.institucion_id = %s) AND "
                              "(estado_consulta_designacion.departamento_id = %s) ")
INSERT_ESTADO_CONSULTA_SQL = ("INSERT INTO estado_consulta_designacion (periodo_id, cuil, estado, fecha_actualizacion, "
                              "institucion_id, departamento_id) VALUES (%s, %s, %s, %s, %s, %s)  RETURNING id")
NOMBRE_DOCENTE_CUIL_SQL = (f"SELECT apellido, nombres, nombre FROM docentes WHERE TRIM(COALESCE(cuil,''))=TRIM(%s) "
                           f"AND {_scoped('docentes')} LIMIT 1")
MOV_BAJA_COMISION_SQL = f"""
    SELECT id
    FROM movimientos
    WHERE periodo_id=%s AND TRIM(COALESCE(cuil,''))=TRIM(%s) AND fecha=%s
      AND LOWER(TRIM(COALESCE(tipo_movimiento,'')))='baja docente por modificación de asignación'
      AND (COALESCE(detalle,'') LIKE %s OR COALESCE(observaciones,'') LIKE %s) AND {_scoped('movimientos')}
    LIMIT 1
"""

# --- v207 ----------------------------------------------------------------------------------------------------
V207_DESIGNACION_SQL = f"""
    SELECT d.id, d.periodo_id, d.cuil, d.cargo, d.dedicacion, d.horas,
           d.tipo_designacion, COALESCE(d.ad_honorem,'No') AS ad_honorem,
           COALESCE(d.funcion_no_docente,0) AS funcion_no_docente,
           p.nombre AS periodo, p.fecha_inicio, p.fecha_fin,
           CASE
             WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL
               THEN doc.apellido || ', ' || doc.nombres
             WHEN doc.nombre IS NOT NULL THEN doc.nombre
             ELSE d.cuil
           END AS nombre_completo
    FROM designaciones d
    LEFT JOIN periodos p ON (p.id=d.periodo_id) AND {_scoped('p')}
    LEFT JOIN docentes doc ON (doc.cuil=d.cuil) AND {_scoped('doc')}
    WHERE d.id=%s AND {_scoped('d')}
    LIMIT 1
"""
V207_AUTOS_SQL = f"""
    SELECT id, fecha, tipo_movimiento, detalle, observaciones
    FROM movimientos
    WHERE periodo_id=%s AND cuil=%s
      AND (COALESCE(detalle,'') LIKE %s OR COALESCE(observaciones,'') LIKE %s) AND {_scoped('movimientos')}
    ORDER BY id
"""
V207_CAND_SQL = f"""
    SELECT id, fecha, tipo_movimiento, detalle, observaciones
    FROM movimientos
    WHERE periodo_id=%s AND cuil=%s
      AND LOWER(TRIM(COALESCE(tipo_movimiento,''))) IN (
            'baja de designación', 'finalización de designación',
            'finalizacion de designacion'
      ) AND {_scoped('movimientos')}
    ORDER BY id
"""


class DesignacionesRepository:
    def __init__(self, conn: Connection, institution_id: int, department_id: int):
        self._conn = conn
        self.inst, self.dep = int(institution_id), int(department_id)
        self._scope = [self.inst, self.dep]
        self.mutating_statements = 0

    # --- primitivas
    def _all(self, sql: str, params: Iterable[Any]) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, list(params))
            return list(cur.fetchall())

    def _first(self, sql: str, params: Iterable[Any]) -> Optional[dict]:
        rows = self._all(sql, params)
        return rows[0] if rows else None

    def _mutate(self, sql: str, params: Iterable[Any]) -> int:
        with self._conn.cursor() as cur:
            cur.execute(sql, list(params))
            self.mutating_statements += 1
            return max(int(cur.rowcount or 0), 0)

    def _insert_id(self, sql: str, params: Iterable[Any]) -> int:
        with self._conn.cursor() as cur:
            cur.execute(sql, list(params))
            self.mutating_statements += 1
            return int(cur.fetchone()[0])

    # --- periodos (SQL certificado de Periodos + lecturas puntuales)
    def periods(self) -> list[dict]:
        return self._all(LIST_SQL, self._scope)

    def open_period(self) -> Optional[dict]:
        return self._first(OPEN_SQL, self._scope)

    def last_period(self) -> Optional[dict]:
        return self._first(LAST_SQL, self._scope)

    def period_info(self, period_id: int) -> Optional[dict]:
        return self._first(PERIOD_INFO_SQL, [int(period_id)] + self._scope)

    def period_by_name(self, nombre: str) -> Optional[dict]:
        return self._first(PERIOD_BY_NAME_SQL, [str(nombre).strip()] + self._scope)

    def period_fin(self, period_id: int) -> Optional[dict]:
        return self._first(PERIOD_FIN_SQL, [int(period_id)] + self._scope)

    def period_raw(self, period_id: int) -> Optional[dict]:
        return self._first(PERIOD_RAW_SQL, [int(period_id)])

    def period_equivalente(self, nombre: str, anio: int, semestre: int) -> Optional[dict]:
        return self._first(PERIOD_EQUIV_SQL, [self.inst, self.dep, nombre, int(anio), int(semestre)])

    def periods_context_v269(self) -> list[dict]:
        return self._all(PERIODS_CONTEXT_V269_SQL, self._scope)

    # --- docentes (SQL certificado de Docentes)
    def docentes(self) -> list[dict]:
        return self._all(DOCENTES_SQL, self._scope)

    def docente_existe(self, clave: str) -> Optional[dict]:
        if not clave:
            return None
        return self._first(DOCENTE_EXISTE_SQL, [clave] + self._scope)

    def nombres_docentes(self) -> list[dict]:
        return self._all(NOMBRE_DOCENTE_SQL, self._scope)

    def nombre_docente_cuil(self, cuil: str) -> Optional[dict]:
        return self._first(NOMBRE_DOCENTE_CUIL_SQL, [cuil] + self._scope)

    # --- estado de consulta (writer guardar_estado_consulta_designacion)
    def borrar_estado_consulta(self, periodo_id: int, cuil: str) -> int:
        return self._mutate(DELETE_ESTADO_CONSULTA_SQL, [int(periodo_id), str(cuil)] + self._scope)

    def insertar_estado_consulta(self, periodo_id: int, cuil: str, estado: str, fecha: str) -> int:
        return self._insert_id(INSERT_ESTADO_CONSULTA_SQL, [int(periodo_id), str(cuil), estado, fecha] + self._scope)

    # --- designaciones (lecturas)
    def designaciones(self, period_id: int) -> list[dict]:
        p = self._scope + self._scope + [int(period_id)] + self._scope
        return self._all(DESIGNACIONES_SQL, p)

    def actos_designaciones(self, ids: list[int]) -> list[dict]:
        if not ids:
            return []
        return self._all(ACTOS_DESIGNACIONES_SQL, self._scope + [list(ids)])

    def actos_movimientos(self, ids: list[int]) -> list[dict]:
        if not ids:
            return []
        return self._all(ACTOS_MOVIMIENTOS_SQL, self._scope + [list(ids)])

    def designacion_ref(self, designacion_id: int) -> Optional[dict]:
        return self._first(DESIGNACION_REF_SQL, [int(designacion_id)] + self._scope)

    def designacion_star(self, designacion_id: int) -> Optional[dict]:
        return self._first(DESIGNACION_STAR_SQL, [int(designacion_id)] + self._scope)

    def designaciones_refs(self, ids: list[int]) -> list[dict]:
        return self._all(DESIGNACIONES_REFS_SQL, [list(ids)] + self._scope)

    def match(self, period_id: Any, cuil: Any, cargo: Any, dedicacion: Any, horas: Any, tipo: Any, ad_honorem: Any,
              fecha_desde: Any, fecha_hasta: Any, *, columns: str = "id", estado: Any = None, estado_on: bool = False,
              resolucion: Optional[str] = None, resolucion_vacia: bool = False, funcion: Optional[int] = None,
              tail: str = "LIMIT 1") -> list[dict]:
        """Búsqueda de designación exactamente igual (``existe_designacion_duplicada`` y chequeos de alta)."""
        sql = f"SELECT {columns} FROM designaciones {_MATCH_BASE}"
        params = [period_id, str(cuil), str(cargo), str(dedicacion), horas, str(tipo), str(ad_honorem),
                  str(fecha_desde), str(fecha_hasta)]
        if estado_on:
            sql += " AND UPPER(TRIM(COALESCE(estado, ''))) = UPPER(TRIM(%s))"
            params.append(estado)
        if resolucion is not None:
            sql += " AND TRIM(COALESCE(numero_resolucion, '')) = TRIM(%s)"
            params.append(resolucion)
        elif resolucion_vacia:
            sql += " AND TRIM(COALESCE(numero_resolucion,'')) = ''"
        if funcion is not None:
            sql += " AND COALESCE(funcion_no_docente, 0) = %s"
            params.append(int(funcion))
        sql += f" AND {_scoped('designaciones')} {tail}"
        return self._all(sql, params + self._scope)

    def funcion_texto(self, designacion_id: int) -> Optional[dict]:
        return self._first("SELECT COALESCE(funcion_no_docente, 0) AS funcion_no_docente, "
                           "COALESCE(texto_funcion_no_docente, '') AS texto_funcion_no_docente FROM designaciones "
                           f"WHERE id = %s AND {_scoped('designaciones')}", [int(designacion_id)] + self._scope)

    def designacion_periodo(self, designacion_id: int) -> Optional[dict]:
        return self._first(f"SELECT periodo_id FROM designaciones WHERE id=%s AND {_scoped('designaciones')} LIMIT 1",
                           [int(designacion_id)] + self._scope)

    def count_designaciones_cuil(self, period_id: int, cuil: str) -> int:
        row = self._first(f"SELECT COUNT(*) AS n FROM designaciones WHERE periodo_id=%s AND cuil=%s AND "
                          f"{_scoped('designaciones')}", [int(period_id), cuil] + self._scope)
        return int((row or {}).get("n") or 0)

    def designaciones_filtradas(self, period_id: Optional[int], cuil: Optional[str]) -> list[dict]:
        filtros, params = [], []
        if period_id is not None:
            filtros.append("periodo_id = %s")
            params.append(int(period_id))
        if cuil is not None and str(cuil).strip():
            filtros.append("TRIM(COALESCE(cuil, '')) = TRIM(%s)")
            params.append(str(cuil))
        where = "WHERE " + " AND ".join(filtros + [_scoped("designaciones")])
        return self._all(f"SELECT id, periodo_id, cuil FROM designaciones {where} ORDER BY periodo_id, cuil, id",
                         params + self._scope)

    def movimientos_filtrados(self, period_id: Optional[int], cuil: Optional[str]) -> list[dict]:
        filtros, params = [], []
        if period_id is not None:
            filtros.append("periodo_id = %s")
            params.append(int(period_id))
        if cuil is not None and str(cuil).strip():
            filtros.append("TRIM(COALESCE(cuil, '')) = TRIM(%s)")
            params.append(str(cuil))
        where = "WHERE " + " AND ".join(filtros + [_scoped("movimientos")])
        return self._all(f"""SELECT id, periodo_id, cuil, nombre, fecha, tipo_movimiento, detalle,
                                    observaciones, COALESCE(horas_variacion, 0) AS horas_variacion
                             FROM movimientos {where} ORDER BY periodo_id, cuil, id""", params + self._scope)

    def movimientos_cuil(self, period_id: int, cuil: str) -> list[dict]:
        return self._all(MOVIMIENTOS_CUIL_SQL, [int(period_id), cuil] + self._scope)

    def movimientos_periodo(self, period_id: int) -> list[dict]:
        return self._all(MOVIMIENTOS_PERIODO_SQL, [int(period_id)] + self._scope)

    def concursadas_cuil(self, cuil: str) -> list[dict]:
        return self._all(CONCURSADAS_CUIL_SQL, [str(cuil or "")] + self._scope)

    # --- designaciones (escrituras)
    def insert_designacion(self, period_id, cuil, cargo, dedicacion, horas, tipo, ad_honorem, fecha_desde,
                           fecha_hasta, estado, observaciones) -> int:
        return self._insert_id(INSERT_DESIGNACION_SQL, [period_id, cuil, cargo, dedicacion, horas, tipo, ad_honorem,
                                                        str(fecha_desde), str(fecha_hasta), estado, observaciones,
                                                        *self._scope])

    def update_base(self, designacion_id, cargo, dedicacion, horas, tipo, ad_honorem, fecha_desde, fecha_hasta,
                    estado, observaciones) -> int:
        return self._mutate(UPDATE_BASE_SQL, [cargo, dedicacion, horas, tipo, ad_honorem, str(fecha_desde),
                                              str(fecha_hasta), estado, observaciones, designacion_id, *self._scope])

    def update_prevista_coalesce(self, designacion_id: int) -> int:
        return self._mutate("UPDATE designaciones SET fecha_hasta_prevista=COALESCE(NULLIF(fecha_hasta_prevista,''),"
                            f"fecha_hasta) WHERE id=%s AND {_scoped('designaciones')}",
                            [int(designacion_id)] + self._scope)

    def update_prevista_coalesce_resolucion(self, designacion_id: int, resolucion: str) -> int:
        return self._mutate("UPDATE designaciones SET fecha_hasta_prevista=COALESCE(NULLIF(fecha_hasta_prevista,''),"
                            f"fecha_hasta), numero_resolucion=%s WHERE id=%s AND {_scoped('designaciones')}",
                            [resolucion, int(designacion_id)] + self._scope)

    def update_prevista(self, designacion_id: int, fecha_hasta: Any, resolucion: Optional[str] = None) -> int:
        if resolucion is None:
            return self._mutate(f"UPDATE designaciones SET fecha_hasta_prevista=%s WHERE id=%s AND "
                                f"{_scoped('designaciones')}", [str(fecha_hasta), int(designacion_id)] + self._scope)
        return self._mutate(f"UPDATE designaciones SET fecha_hasta_prevista=%s, numero_resolucion=%s WHERE id=%s AND "
                            f"{_scoped('designaciones')}",
                            [str(fecha_hasta), str(resolucion or '').strip(), int(designacion_id)] + self._scope)

    def update_funcion(self, designacion_id: int, flag: int, texto: str) -> int:
        return self._mutate("UPDATE designaciones SET funcion_no_docente = %s, texto_funcion_no_docente = %s "
                            f"WHERE id = %s AND {_scoped('designaciones')}",
                            [int(flag), texto, int(designacion_id)] + self._scope)

    def limpiar_metadatos_finalizacion(self, designacion_id: int) -> int:
        return self._mutate(f"""
            UPDATE designaciones
            SET fecha_finalizacion_efectiva=NULL,
                fecha_registro_finalizacion=NULL,
                motivo_finalizacion=''
            WHERE id=%s
              AND UPPER(TRIM(COALESCE(estado,'')))='ACTIVA'
              AND (
                    NULLIF(TRIM(COALESCE(fecha_finalizacion_efectiva,'')),'') IS NOT NULL
                 OR NULLIF(TRIM(COALESCE(fecha_registro_finalizacion,'')),'') IS NOT NULL
                 OR NULLIF(TRIM(COALESCE(motivo_finalizacion,'')),'') IS NOT NULL
              ) AND {_scoped('designaciones')}
        """, [int(designacion_id)] + self._scope)

    def finalizar(self, designacion_id: int, fecha_efectiva: str, registro: str, motivo: str) -> int:
        return self._mutate("UPDATE designaciones SET estado='Finalizada',fecha_finalizacion_efectiva=%s,"
                            "fecha_registro_finalizacion=%s,motivo_finalizacion=%s,fecha_hasta_prevista=COALESCE("
                            f"NULLIF(fecha_hasta_prevista,''),fecha_hasta) WHERE id=%s AND {_scoped('designaciones')}",
                            [fecha_efectiva, registro, motivo, int(designacion_id)] + self._scope)

    def update_fechas_v171(self, designacion_id: int, resolucion: str, desde: str, hasta: str) -> int:
        return self._mutate(f"""
            UPDATE designaciones
            SET numero_resolucion = %s,
                fecha_desde = %s,
                fecha_hasta = %s,
                fecha_hasta_prevista = %s
            WHERE id = %s AND {_scoped('designaciones')}
        """, [resolucion, desde, hasta, hasta, int(designacion_id)] + self._scope)

    def delete_links_designaciones(self, ids: list[int]) -> int:
        return self._mutate(f"DELETE FROM documentos_respaldo_designaciones WHERE designacion_id = ANY(%s) AND "
                            f"{_scoped('documentos_respaldo_designaciones')}", [list(ids)] + self._scope)

    def delete_designaciones(self, ids: list[int]) -> int:
        return self._mutate(f"DELETE FROM designaciones WHERE id = ANY(%s) AND {_scoped('designaciones')}",
                            [list(ids)] + self._scope)

    def delete_links_movimientos(self, ids: list[int]) -> int:
        return self._mutate(f"DELETE FROM documentos_respaldo_movimientos WHERE movimiento_id = ANY(%s) AND "
                            f"{_scoped('documentos_respaldo_movimientos')}", [list(ids)] + self._scope)

    def delete_movimientos(self, ids: list[int]) -> int:
        return self._mutate(f"DELETE FROM movimientos WHERE id = ANY(%s) AND {_scoped('movimientos')}",
                            [list(ids)] + self._scope)

    # --- movimientos
    def insert_movement(self, *, period_id: Optional[int], fecha: str, tipo: str, cuil: str, nombre: str,
                        detalle: str, observaciones: str, horas_variacion: float = 0.0) -> int:
        # psycopg2 (certificado) envia el float como literal ``repr``: 10.0 queda numeric 10.0 (misma escala).
        return self._insert_id(MOVEMENT_SQL, [period_id, fecha, tipo, cuil, nombre, detalle, observaciones,
                                              _numeric(horas_variacion), *self._scope])

    def v207_designacion(self, designacion_id: int) -> Optional[dict]:
        return self._first(V207_DESIGNACION_SQL, self._scope + self._scope + [int(designacion_id)] + self._scope)

    def v207_autos(self, period_id: int, cuil: str, marcador: str) -> list[dict]:
        patron = f"%{marcador}%"
        return self._all(V207_AUTOS_SQL, [int(period_id), cuil, patron, patron] + self._scope)

    def v207_candidatos(self, period_id: int, cuil: str) -> list[dict]:
        return self._all(V207_CAND_SQL, [int(period_id), cuil] + self._scope)

    def v207_update_completo(self, movimiento_id: int, fecha: str, nombre: str, detalle: str, observaciones: str,
                             variacion: float) -> int:
        return self._mutate(f"""
            UPDATE movimientos
            SET fecha=%s, tipo_movimiento='Baja de designación', nombre=%s, detalle=%s,
                observaciones=%s, horas_variacion=%s
            WHERE id=%s AND {_scoped('movimientos')}
        """, [fecha, nombre, detalle, observaciones, _numeric(variacion), int(movimiento_id)] + self._scope)

    def v207_update_legacy(self, movimiento_id: int, fecha: str, variacion: float) -> int:
        return self._mutate(f"""
            UPDATE movimientos
            SET fecha=%s, tipo_movimiento='Baja de designación', horas_variacion=%s
            WHERE id=%s AND {_scoped('movimientos')}
        """, [fecha, _numeric(variacion), int(movimiento_id)] + self._scope)

    def delete_movimiento(self, movimiento_id: int) -> int:
        return self._mutate(f"DELETE FROM movimientos WHERE id=%s AND {_scoped('movimientos')}",
                            [int(movimiento_id)] + self._scope)

    # --- repositorio documental y vinculos v266/v267 (conexion cruda: ambito explicito)
    def documentos(self) -> list[dict]:
        return self._all(DOCUMENTOS_SQL, self._scope)

    def link_designacion(self, documento_id: int, designacion_id: int, usuario: str) -> int:
        return self._mutate(LINK_DESIGNACION_SQL, [self.inst, self.dep, int(documento_id), int(designacion_id),
                                                   usuario])

    def unlink_designaciones(self, ids: list[int]) -> int:
        return self._mutate("DELETE FROM documentos_respaldo_designaciones WHERE institucion_id=%s AND "
                            "departamento_id=%s AND designacion_id = ANY(%s)", [self.inst, self.dep, list(ids)])

    def link_movimiento(self, documento_id: int, movimiento_id: int, usuario: str) -> int:
        return self._mutate(LINK_MOVIMIENTO_SQL, [self.inst, self.dep, int(documento_id), int(movimiento_id),
                                                  usuario])

    def unlink_movimientos(self, ids: list[int]) -> int:
        return self._mutate("DELETE FROM documentos_respaldo_movimientos WHERE institucion_id=%s AND "
                            "departamento_id=%s AND movimiento_id = ANY(%s)", [self.inst, self.dep, list(ids)])

    # --- comisiones: cargo prioritario v200 y baja automatica v214
    def departamentos_institucion(self) -> list[dict]:
        return self._all(DEPARTAMENTOS_INST_SQL, [self.inst])

    def docentes_tipo(self, department_id: int) -> list[dict]:
        return self._all(DOCENTES_TIPO_SQL, [self.inst, int(department_id)])

    def designaciones_equivalentes(self, period_id: int) -> list[dict]:
        return self._all(DESIGNACIONES_EQUIV_SQL, [int(period_id), self.inst])

    def update_rol_asignaciones(self, cargo: str, cuil: str, period_id: int) -> int:
        return self._mutate(UPDATE_ROL_SQL, [cargo, cuil, int(period_id)] + self._scope)

    def designaciones_activas_cuil(self, period_id: int, cuil: str) -> list[dict]:
        return self._all(DESIGNACIONES_ACTIVAS_CUIL_SQL, [int(period_id), cuil] + self._scope)

    def asignaciones_activas(self, period_id: int, cuil: str) -> list[dict]:
        return self._all(ASIGNACIONES_ACTIVAS_SQL, [int(period_id), cuil] + self._scope + self._scope)

    def finalizar_asignacion(self, observaciones: str, asignacion_id: int) -> int:
        return self._mutate(FINALIZAR_ASIGNACION_SQL, [observaciones, int(asignacion_id)] + self._scope)

    def movimiento_baja_comision(self, period_id: int, cuil: str, fecha: str, comision_id: int) -> Optional[dict]:
        patron = f"%Comisión ID {int(comision_id)}%"
        return self._first(MOV_BAJA_COMISION_SQL, [int(period_id), cuil, fecha, patron, patron] + self._scope)
