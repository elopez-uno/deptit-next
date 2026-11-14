"""SQL de Docentes sobre una conexion/transaccion ya abierta.  Nunca crea ni altera tablas y nunca confirma.

Ambito de cada sentencia, igual que la fuente certificada:
- ``get_conn()`` + inyector B12B (``_pg_prepare_sql``): ``docentes``, ``designaciones``, ``movimientos``,
  ``prestamos_docentes``, ``asignaciones_docentes_comision``, ... son tablas de DEPARTAMENTO -> ``institucion_id`` +
  ``departamento_id`` explicitos; ``disposicion_docente_designaciones`` es de INSTITUCION -> solo ``institucion_id``.
- ``_pg_raw_conn()`` (identidad v168, prestamos v174, busquedas en otros departamentos): sin inyector; el SQL
  certificado lleva el ambito explicito (institucion, y departamento donde corresponde) y asi se reproduce.
Sentencias: entry l. 4462 (``get_docentes``), 7789 (``docente_existe``), 8073 (``guardar_docente``), 8113-8431
(referencias / ``eliminar_docente``), 26136 / 26639 (otros departamentos), 35576-36395 (v168), 37006-37121 (v174),
4424 (``registrar_movimiento``).
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Optional

from psycopg import Connection
from psycopg.rows import dict_row

from periodos.repository import LAST_SQL, OPEN_SQL

_DEP = "institucion_id = %s AND departamento_id = %s"
_CUIL_DIGITS = "regexp_replace(COALESCE({col}, ''), '[^0-9]', '', 'g') = %s"

# --- get_docentes (base v204) -------------------------------------------------------------------------------
DOCENTES_SQL = """
    SELECT
        doc.cuil,
        doc.legajo,
        doc.apellido,
        doc.nombres,
        CASE
            WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
            WHEN doc.nombre IS NOT NULL THEN doc.nombre
            ELSE ''
        END AS nombre_completo,
        doc.titulo,
        COALESCE(doc.titulo_posgrado, '') AS titulo_posgrado,
        doc.antiguedad_anios,
        COALESCE(doc.nivel_posgrado_salarial, '') AS nivel_posgrado_salarial,
        doc.email,
        doc.telefono,
        doc.ref_legajo_fisico,
        COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente,
        COALESCE(doc.observaciones, '') AS observaciones,
        doc.estado
    FROM docentes doc
    WHERE doc.institucion_id = %s AND doc.departamento_id = %s
    ORDER BY doc.apellido, doc.nombres
"""
DESIGNACIONES_TRAYECTORIA_SQL = """
    SELECT d.cuil, d.periodo_id, COALESCE(d.estado, 'Activa') AS estado,
           d.fecha_desde, d.fecha_hasta, d.fecha_finalizacion_efectiva
    FROM designaciones d
    WHERE d.institucion_id = %s AND d.departamento_id = %s
"""
PRESTAMOS_ESTADO_SQL = """
    SELECT pr.cuil, pr.periodo_id, COALESCE(pr.estado, 'Activo') AS estado
    FROM prestamos_docentes pr
    WHERE pr.periodo_id = %s AND pr.institucion_id = %s AND pr.departamento_id = %s
"""

DOCENTE_EXISTE_SQL = f"""
    SELECT cuil, apellido, nombres, nombre, legajo, titulo,
           COALESCE(titulo_posgrado, '') AS titulo_posgrado,
           antiguedad_anios,
           COALESCE(nivel_posgrado_salarial, '') AS nivel_posgrado_salarial,
           COALESCE(email, '') AS email,
           COALESCE(telefono, '') AS telefono,
           COALESCE(ref_legajo_fisico, '') AS ref_legajo_fisico,
           COALESCE(tipo_docente, 'Propio') AS tipo_docente,
           COALESCE(estado, 'Activo') AS estado,
           COALESCE(observaciones, '') AS observaciones
    FROM docentes
    WHERE {_CUIL_DIGITS.format(col='cuil')} AND {_DEP}
    ORDER BY id
    LIMIT 1
"""

_OTROS_DEPTOS_COLS = """
        doc.cuil,
        CASE
            WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
            WHEN doc.nombre IS NOT NULL THEN doc.nombre
            ELSE doc.cuil
        END AS nombre_completo,
        COALESCE(dep.nombre, 'Sin departamento') AS departamento_origen,
        doc.legajo, doc.apellido, doc.nombres, doc.titulo,
        COALESCE(doc.titulo_posgrado, '') AS titulo_posgrado,
"""
PRESTABLES_SQL = f"""
    SELECT DISTINCT
        {_OTROS_DEPTOS_COLS}
        doc.antiguedad_anios,
        COALESCE(doc.nivel_posgrado_salarial, '') AS nivel_posgrado_salarial,
        doc.email, doc.telefono, doc.ref_legajo_fisico
    FROM docentes doc
    LEFT JOIN departamentos dep ON dep.id = doc.departamento_id
    WHERE doc.institucion_id = %s
      AND COALESCE(doc.departamento_id, -1) <> %s
      AND COALESCE(doc.estado, 'Activo') = 'Activo'
    ORDER BY departamento_origen, nombre_completo
"""
MISMO_CUIL_OTRO_DEPTO_SQL = f"""
    SELECT DISTINCT
        {_OTROS_DEPTOS_COLS}
        doc.email, doc.telefono, doc.ref_legajo_fisico,
        COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente
    FROM docentes doc
    LEFT JOIN departamentos dep ON dep.id = doc.departamento_id
    WHERE doc.institucion_id = %s
      AND regexp_replace(COALESCE(doc.cuil, ''), '[^0-9]', '', 'g') = %s
      AND COALESCE(doc.departamento_id, -1) <> %s
      AND COALESCE(doc.estado, 'Activo') = 'Activo'
    ORDER BY departamento_origen, nombre_completo
"""

INSERT_DOCENTE_SQL = """
    INSERT INTO docentes
    (cuil, nombre, apellido, nombres, legajo, titulo, titulo_posgrado, antiguedad_anios, nivel_posgrado_salarial,
     email, telefono, ref_legajo_fisico, estado, tipo_docente, fecha_alta, observaciones, institucion_id,
     departamento_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
"""
MOVEMENT_SQL = ("INSERT INTO movimientos (periodo_id, fecha, tipo_movimiento, cuil, nombre, detalle, observaciones, "
                "horas_variacion, institucion_id, departamento_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING id")

# --- referencias locales (_diagnosticar_referencias_docente_conn) -------------------------------------------
REF_DESIGNACIONES_SQL = f"""
    SELECT d.id, d.periodo_id, d.cargo, d.dedicacion, d.horas,
           d.tipo_designacion, d.ad_honorem, d.fecha_desde, d.fecha_hasta,
           COALESCE(d.estado, 'Activa') AS estado
    FROM designaciones d
    WHERE {_CUIL_DIGITS.format(col='d.cuil')} AND d.institucion_id = %s AND d.departamento_id = %s
    ORDER BY d.periodo_id, d.id
"""
REF_COMISIONES_SQL = f"""
    SELECT a.id, a.comision_id, COALESCE(a.rol, '') AS cargo_rol,
           COALESCE(a.horas_asignadas, 0) AS horas,
           COALESCE(a.estado, 'Activa') AS estado,
           COALESCE(a.observaciones, '') AS observaciones
    FROM asignaciones_docentes_comision a
    WHERE {_CUIL_DIGITS.format(col='a.cuil')} AND a.institucion_id = %s AND a.departamento_id = %s
    ORDER BY a.comision_id, a.id
"""
REF_INVESTIGACION_SQL = f"""
    SELECT i.id, i.periodo_id, i.proyecto_id,
           COALESCE(i.codigo_proyecto, '') AS codigo,
           COALESCE(i.nombre_proyecto, '') AS proyecto,
           COALESCE(i.rol, '') AS rol,
           COALESCE(i.horas_asignadas, 0) AS horas,
           COALESCE(i.estado_asignacion, 'Activa') AS estado
    FROM investigacion_docente i
    WHERE {_CUIL_DIGITS.format(col='i.cuil')} AND i.institucion_id = %s AND i.departamento_id = %s
    ORDER BY i.periodo_id, proyecto, i.id
"""
REF_EXTENSION_SQL = f"""
    SELECT e.id, e.periodo_id, e.proyecto_id,
           COALESCE(e.codigo_proyecto, '') AS codigo,
           COALESCE(e.nombre_proyecto, '') AS proyecto,
           COALESCE(e.rol, '') AS rol,
           COALESCE(e.horas_asignadas, 0) AS horas,
           COALESCE(e.estado_asignacion, 'Activa') AS estado
    FROM extension_docente e
    WHERE {_CUIL_DIGITS.format(col='e.cuil')} AND e.institucion_id = %s AND e.departamento_id = %s
    ORDER BY e.periodo_id, proyecto, e.id
"""
REF_ACTIVIDADES_SQL = f"""
    SELECT ad.id, ad.periodo_id, ad.actividad_id,
           COALESCE(ad.rol, '') AS rol,
           COALESCE(ad.estado_asignacion, 'Activa') AS estado,
           COALESCE(ad.observaciones, '') AS observaciones
    FROM actividad_especial_docente ad
    WHERE {_CUIL_DIGITS.format(col='ad.cuil')} AND ad.institucion_id = %s AND ad.departamento_id = %s
    ORDER BY ad.periodo_id, ad.actividad_id, ad.id
"""
REF_PERIODOS_SQL = f"SELECT id, nombre, fecha_inicio FROM periodos WHERE {_DEP} ORDER BY fecha_inicio, id"
REF_COMISIONES_INFO_SQL = (f"SELECT id, periodo_id, nombre_comision, turno, modalidad FROM comisiones WHERE {_DEP} "
                           "ORDER BY id")
REF_ACTIVIDADES_INFO_SQL = f"SELECT id, titulo FROM actividades_especiales WHERE {_DEP} ORDER BY id"

# --- prestamos v174 ----------------------------------------------------------------------------------------
PRESTAMOS_PERIODO_SQL = """
    SELECT pr.id, pr.periodo_id, pr.cuil, COALESCE(pr.departamento_origen,'') AS departamento_origen,
           pr.fecha_desde, pr.fecha_hasta, COALESCE(pr.estado,'Activo') AS estado,
           COALESCE(pr.observaciones,'') AS observaciones, pr.fecha_registro, pr.fecha_finalizacion
    FROM prestamos_docentes pr
    WHERE pr.periodo_id=%s {filtro} AND pr.institucion_id = %s AND pr.departamento_id = %s
    ORDER BY pr.fecha_desde, pr.cuil
"""
PRESTAMO_UPSERT_SQL = """
    INSERT INTO prestamos_docentes
        (institucion_id, departamento_id, periodo_id, cuil, departamento_origen,
         fecha_desde, fecha_hasta, estado, observaciones, fecha_registro, fecha_finalizacion)
    VALUES (%s,%s,%s,%s,%s,%s,NULL,'Activo',%s,%s,NULL)
    ON CONFLICT (institucion_id, departamento_id, periodo_id, cuil)
    DO UPDATE SET departamento_origen=EXCLUDED.departamento_origen,
                  fecha_desde=EXCLUDED.fecha_desde,
                  fecha_hasta=NULL, estado='Activo', observaciones=EXCLUDED.observaciones,
                  fecha_finalizacion=NULL
"""
PRESTAMO_FINALIZAR_SQL = """
    UPDATE prestamos_docentes
    SET estado='Finalizado', fecha_hasta=%s, fecha_finalizacion=%s,
        observaciones=CASE WHEN COALESCE(TRIM(observaciones),'')='' THEN %s
                           WHEN COALESCE(TRIM(%s),'')='' THEN observaciones
                           ELSE observaciones || ' | ' || %s END
    WHERE institucion_id=%s AND departamento_id=%s AND periodo_id=%s AND cuil=%s
      AND UPPER(TRIM(COALESCE(estado,'Activo')))='ACTIVO'
"""
PRESTAMO_FINALIZAR_ASIGNACIONES_SQL = """
    UPDATE asignaciones_docentes_comision a
    SET estado='Finalizada',
        observaciones=CASE WHEN COALESCE(TRIM(a.observaciones),'')='' THEN %s ELSE a.observaciones || ' | ' || %s END
    FROM comisiones co
    WHERE a.comision_id=co.id
      AND a.institucion_id=%s AND a.departamento_id=%s
      AND co.institucion_id=%s AND co.departamento_id=%s AND co.periodo_id=%s
      AND a.cuil=%s
      AND UPPER(TRIM(COALESCE(a.estado,'Activa')))='ACTIVA'
"""

COLUMNS_SQL = ("SELECT column_name FROM information_schema.columns "
               "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position")


class DocentesRepository:
    def __init__(self, conn: Connection, institution_id: int, department_id: int):
        self._conn = conn
        self.inst, self.dep = int(institution_id), int(department_id)
        self._scope = [self.inst, self.dep]
        self.mutating_statements = 0
        self._columns: dict[str, list[str]] = {}

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

    # --- periodos (SQL certificado de Periodos)
    def open_period(self) -> Optional[dict]:
        return self._first(OPEN_SQL, self._scope)

    def last_period(self) -> Optional[dict]:
        return self._first(LAST_SQL, self._scope)

    # --- get_docentes
    def docentes(self) -> list[dict]:
        return self._all(DOCENTES_SQL, self._scope)

    def designaciones_trayectoria(self) -> list[dict]:
        return self._all(DESIGNACIONES_TRAYECTORIA_SQL, self._scope)

    def prestamos_estado(self, period_id: int) -> list[dict]:
        return self._all(PRESTAMOS_ESTADO_SQL, [int(period_id)] + self._scope)

    # --- existencia / otros departamentos
    def docente_existe(self, clave: str) -> Optional[dict]:
        if not clave:
            return None
        return self._first(DOCENTE_EXISTE_SQL, [clave] + self._scope)

    def prestables(self) -> list[dict]:
        return self._all(PRESTABLES_SQL, [self.inst, self.dep])

    def mismo_cuil_otro_departamento(self, clave: str) -> list[dict]:
        if not clave:
            return []
        return self._all(MISMO_CUIL_OTRO_DEPTO_SQL, [self.inst, clave, self.dep])

    # --- escrituras simples
    def insert_docente(self, values: dict) -> int:
        with self._conn.cursor() as cur:
            cur.execute(INSERT_DOCENTE_SQL, [
                values["cuil"], values["nombre"], values["apellido"], values["nombres"], values["legajo"],
                values["titulo"], values["titulo_posgrado"], values["antiguedad_anios"],
                values["nivel_posgrado_salarial"], values["email"], values["telefono"], values["ref_legajo_fisico"],
                values["estado"], values["tipo_docente"], values["fecha_alta"], values["observaciones"], *self._scope])
            self.mutating_statements += 1
            return int(cur.fetchone()[0])

    def insert_movement(self, *, period_id: Optional[int], fecha: str, tipo: str, cuil: str, nombre: str,
                        detalle: str, observaciones: str, horas_variacion: float = 0.0) -> int:
        with self._conn.cursor() as cur:
            cur.execute(MOVEMENT_SQL, [period_id, fecha, tipo, cuil, nombre, detalle, observaciones,
                                       float(horas_variacion), *self._scope])
            self.mutating_statements += 1
            return int(cur.fetchone()[0])

    # --- referencias locales
    def referencias(self, clave: str) -> dict:
        p = [clave] + self._scope
        return {
            "designaciones": self._all(REF_DESIGNACIONES_SQL, p),
            "comisiones": self._all(REF_COMISIONES_SQL, p),
            "investigacion": self._all(REF_INVESTIGACION_SQL, p),
            "extension": self._all(REF_EXTENSION_SQL, p),
            "actividades_especiales": self._all(REF_ACTIVIDADES_SQL, p),
        }

    def periodos_nombres(self) -> list[dict]:
        return self._all(REF_PERIODOS_SQL, self._scope)

    def comisiones_info(self) -> list[dict]:
        return self._all(REF_COMISIONES_INFO_SQL, self._scope)

    def actividades_info(self) -> list[dict]:
        return self._all(REF_ACTIVIDADES_INFO_SQL, self._scope)

    # --- eliminar_docente (inyector: departamento; disposicion_docente_designaciones: institucion)
    def delete_horarios_asignacion(self, ids: list[int]) -> int:
        marks = ",".join(["%s"] * len(ids))
        return self._mutate(f"DELETE FROM horarios_asignacion_docente_comision WHERE asignacion_id IN ({marks}) "
                            f"AND {_DEP}", [*ids, *self._scope])

    def delete_disposicion_designaciones(self, ids: list[int]) -> int:
        marks = ",".join(["%s"] * len(ids))
        return self._mutate(f"DELETE FROM disposicion_docente_designaciones WHERE designacion_id IN ({marks}) "
                            "AND institucion_id = %s", [*ids, self.inst])

    def delete_by_cuil(self, table: str, clave: str) -> int:
        if table not in _DELETE_BY_CUIL_TABLES:
            raise ValueError("tabla no permitida")
        return self._mutate(f"DELETE FROM {table} WHERE {_CUIL_DIGITS.format(col='cuil')} AND {_DEP}",
                            [clave, *self._scope])

    # --- prestamos v174 (conexion cruda certificada: ambito explicito)
    def prestamos_periodo(self, period_id: int, solo_activos: bool = False) -> list[dict]:
        filtro = " AND UPPER(TRIM(COALESCE(pr.estado,'Activo')))='ACTIVO'" if solo_activos else ""
        return self._all(PRESTAMOS_PERIODO_SQL.format(filtro=filtro), [int(period_id)] + self._scope)

    def upsert_prestamo(self, *, period_id: int, cuil: str, origen: str, fecha_desde: str, observaciones: str,
                        fecha_registro: str) -> int:
        return self._mutate(PRESTAMO_UPSERT_SQL, [self.inst, self.dep, int(period_id), str(cuil), str(origen or ""),
                                                  str(fecha_desde), str(observaciones or ""), fecha_registro])

    def finalizar_prestamo(self, *, period_id: int, cuil: str, fecha_hasta: str, observaciones: str,
                           fecha_finalizacion: str) -> int:
        """Devuelve las asignaciones en comision finalizadas (``rowcount`` del segundo UPDATE, como el certificado)."""
        obs = str(observaciones or "")
        self._mutate(PRESTAMO_FINALIZAR_SQL, [str(fecha_hasta), fecha_finalizacion, obs, obs, obs, self.inst,
                                              self.dep, int(period_id), str(cuil)])
        nota = f"Préstamo finalizado el {fecha_hasta}"
        return self._mutate(PRESTAMO_FINALIZAR_ASIGNACIONES_SQL, [nota, nota, self.inst, self.dep, self.inst,
                                                                  self.dep, int(period_id), str(cuil)])

    # --- identidad v168 (conexion cruda: institucion explicita donde la tabla la tiene)
    def columns(self, table: str) -> list[str]:
        if table not in self._columns:
            with self._conn.cursor() as cur:
                cur.execute(COLUMNS_SQL, [table])
                self._columns[table] = [str(r[0]) for r in cur.fetchall()]
        return self._columns[table]

    def _where_cuil(self, cols: list[str], clave: str) -> tuple[str, list]:
        parts, params = [], []
        if "institucion_id" in cols:
            parts.append("institucion_id = %s")
            params.append(self.inst)
        parts.append(_CUIL_DIGITS.format(col="cuil"))
        params.append(str(clave))
        return " AND ".join(parts), params

    def fetch_rows_cuil(self, table: str, clave: str) -> tuple[list[dict], list[str]]:
        cols = self.columns(table)
        if not cols or "cuil" not in cols:
            return [], cols
        where, params = self._where_cuil(cols, clave)
        return self._all(f"SELECT * FROM {table} WHERE {where}", params), cols

    def delete_id(self, table: str, row_id: int) -> int:
        return self._mutate(f"DELETE FROM {table} WHERE id = %s", [int(row_id)])

    def update_id_cuil(self, table: str, row_id: int, cuil: str, extra: Optional[dict] = None) -> int:
        sets, params = ["cuil = %s"], [str(cuil)]
        for col, val in dict(extra or {}).items():
            sets.append(f"{col} = %s")
            params.append(val)
        return self._mutate(f"UPDATE {table} SET {', '.join(sets)} WHERE id = %s", params + [int(row_id)])

    def update_cuil_direct(self, table: str, clave_origen: str, cuil_destino: str,
                           extras: Optional[dict] = None) -> int:
        cols = self.columns(table)
        if not cols or "cuil" not in cols:
            return 0
        where, params_where = self._where_cuil(cols, clave_origen)
        sets, params = ["cuil = %s"], [str(cuil_destino)]
        for col, val in dict(extras or {}).items():
            if col in cols:
                sets.append(f"{col} = %s")
                params.append(val)
        return self._mutate(f"UPDATE {table} SET {', '.join(sets)} WHERE {where}", params + params_where)

    def update_cuil_textual(self, table: str, origen: str, destino: str, extras: dict) -> int:
        cols = self.columns(table)
        parts, params_where = ["TRIM(COALESCE(cuil, '')) = TRIM(%s)"], [str(origen)]
        if "institucion_id" in cols:
            parts.insert(0, "institucion_id = %s")
            params_where.insert(0, self.inst)
        sets = ["cuil = %s"] + [f"{k} = %s" for k in extras]
        return self._mutate(f"UPDATE {table} SET {', '.join(sets)} WHERE {' AND '.join(parts)}",
                            [str(destino)] + list(extras.values()) + params_where)

    def count_cuil_textual(self, table: str, origen: str) -> int:
        cols = self.columns(table)
        parts, params = ["TRIM(COALESCE(cuil, '')) = TRIM(%s)"], [str(origen)]
        if "institucion_id" in cols:
            parts.insert(0, "institucion_id = %s")
            params.insert(0, self.inst)
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {' AND '.join(parts)}", params)
            return int((cur.fetchone() or [0])[0] or 0)

    def update_row_values(self, table: str, row_id: int, values: dict) -> int:
        sets = [f"{c} = %s" for c in values]
        return self._mutate(f"UPDATE {table} SET {', '.join(sets)} WHERE id = %s", list(values.values()) + [int(row_id)])

    def update_where_cuil(self, table: str, values: dict, clave: str, extra: Optional[dict] = None) -> int:
        cols = self.columns(table)
        where, params = self._where_cuil(cols, clave)
        for col, val in dict(extra or {}).items():
            where += f" AND {col} = %s"
            params.append(val)
        sets = [f"{c} = %s" for c in values]
        return self._mutate(f"UPDATE {table} SET {', '.join(sets)} WHERE {where}", list(values.values()) + params)

    def delete_where_cuil(self, table: str, clave: str, extra: Optional[dict] = None) -> int:
        cols = self.columns(table)
        where, params = self._where_cuil(cols, clave)
        for col, val in dict(extra or {}).items():
            where += f" AND {col} = %s"
            params.append(val)
        return self._mutate(f"DELETE FROM {table} WHERE {where}", params)

    def update_variables_json(self, row_id: int, data: dict) -> int:
        return self._mutate("UPDATE disposiciones SET variables_json = %s WHERE id = %s",
                            [json.dumps(data, ensure_ascii=False), int(row_id)])

    def docentes_institucion(self, clave: str) -> list[dict]:
        cols = self.columns("docentes")
        if not cols:
            return []
        where, params = self._where_cuil(cols, clave)
        return self._all(f"SELECT * FROM docentes WHERE {where}", params)

    def cuiles_docentes_institucion(self) -> list[str]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT cuil FROM docentes WHERE institucion_id = %s AND COALESCE(TRIM(cuil),'') <> ''",
                        [self.inst])
            return [r[0] for r in cur.fetchall()]

    def cuiles_por_tabla(self, table: str) -> list[tuple]:
        cols = self.columns(table)
        parts, params = ["COALESCE(TRIM(cuil),'') <> ''"], []
        if "institucion_id" in cols:
            parts.append("institucion_id = %s")
            params.append(self.inst)
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT cuil, COUNT(*) AS n FROM {table} WHERE {' AND '.join(parts)} GROUP BY cuil", params)
            return list(cur.fetchall())


_DELETE_BY_CUIL_TABLES = frozenset({
    "asignaciones_docentes_comision", "investigacion_docente", "extension_docente", "actividad_especial_docente",
    "designaciones", "estado_consulta_designacion", "disposicion_docente_parametros", "movimientos", "docentes",
})
