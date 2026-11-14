"""SQL de Materias sobre una conexion/transaccion ya abierta.  Nunca crea ni altera tablas y nunca confirma.

``carreras``, ``materias``, ``opciones_curriculares`` y ``opcion_curricular_materias`` son tablas de INSTITUCION
(``PG_INSTITUTION_TABLES``): con la conexion certificada ``get_planes_conn()`` (kind "planes") el inyector agrega
``institucion_id`` a cada SELECT/UPDATE/DELETE y lo completa en cada INSERT; en un LEFT JOIN, por B12J, el scope de la
tabla opcional va a su ``ON``.  Aca ese ambito va explicito.  Las guardas sobre ``comisiones``/``comision_materias``
replican el SQL de ``_pg_raw_conn`` certificado (institucion explicita).
Sentencias: entry l. 7886-8060, 12455-13343, 14060-14320, 14696-16420, 27901-28012 y ``extracted_batch03``.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

import pandas as pd
from psycopg import Connection

_ORDEN_ANIO = """
            CASE {col}
                WHEN '1° Año' THEN 1
                WHEN '2° Año' THEN 2
                WHEN '3° Año' THEN 3
                WHEN '4° Año' THEN 4
                WHEN '5° Año' THEN 5
                WHEN '6° Año' THEN 6
                ELSE 99
            END"""
_ORDEN_CUAT = """
            CASE {col}
                WHEN '1' THEN 1
                WHEN '2' THEN 2
                WHEN '1 y 2' THEN 3
                ELSE 9
            END"""

CARRERA_COLS = "id, escuela, codigo, nombre, titulo_otorga, plan_version, duracion, estado, observaciones"

PLAN_SQL = f"""
    SELECT
        id, carrera_id, orden, codigo, asignatura, anio, cuatrimestre, dictado, carga_semanal, carga_total,
        duracion, estado, observaciones,
        COALESCE(comparticion_modo, 'Automática') AS comparticion_modo,
        COALESCE(comparticion_grupo, '') AS comparticion_grupo
    FROM materias
    WHERE carrera_id = %s
      AND COALESCE(en_plan, 1) = 1
      AND institucion_id = %s
    ORDER BY {_ORDEN_ANIO.format(col='anio')},
        {_ORDEN_CUAT.format(col='cuatrimestre')},
        COALESCE(orden, 9999),
        asignatura
"""
PLAN_TODAS_SQL = f"""
    SELECT
        m.id, m.carrera_id, m.orden, m.codigo, m.asignatura,
        COALESCE(c.nombre, m.carrera) AS carrera,
        COALESCE(c.escuela, m.escuela) AS escuela,
        COALESCE(c.plan_version, m.plan_version) AS plan_version,
        m.anio, m.cuatrimestre, m.dictado, m.carga_semanal, m.carga_total, m.duracion, m.estado, m.observaciones,
        COALESCE(m.comparticion_modo, 'Automática') AS comparticion_modo,
        COALESCE(m.comparticion_grupo, '') AS comparticion_grupo,
        COALESCE(m.en_plan, 1) AS en_plan
    FROM materias m
    LEFT JOIN carreras c ON (c.id = m.carrera_id) AND (c.institucion_id = %s)
    WHERE m.institucion_id = %s
    ORDER BY escuela, carrera, plan_version,
        {_ORDEN_ANIO.format(col='m.anio')},
        {_ORDEN_CUAT.format(col='m.cuatrimestre')},
        COALESCE(m.orden, 9999),
        m.codigo,
        m.asignatura
"""
CONFLICTOS_SQL = """
    SELECT
        m.id, m.codigo, m.asignatura,
        COALESCE(c.nombre, m.carrera) AS carrera,
        COALESCE(c.escuela, m.escuela) AS escuela,
        COALESCE(c.plan_version, m.plan_version) AS plan_version,
        m.anio, m.cuatrimestre
    FROM materias m
    LEFT JOIN carreras c ON (c.id = m.carrera_id) AND (c.institucion_id = %s)
    WHERE TRIM(COALESCE(m.codigo, '')) <> ''
      AND COALESCE(m.en_plan, 1) = 1
      AND m.institucion_id = %s
"""
VINCULOS_LOTE_SQL = """
    SELECT
        om.id AS vinculo_id, om.opcion_id, om.materia_id, om.fecha_vinculacion,
        COALESCE(m.codigo, '') AS codigo,
        COALESCE(m.asignatura, '') AS asignatura,
        m.carrera_id,
        COALESCE(m.carrera, '') AS carrera,
        COALESCE(m.escuela, '') AS escuela,
        COALESCE(m.plan_version, '') AS plan_version,
        COALESCE(m.anio, '') AS anio,
        COALESCE(m.cuatrimestre, '') AS cuatrimestre,
        COALESCE(m.estado, 'Activa') AS estado,
        COALESCE(m.en_plan, 1) AS en_plan
    FROM opcion_curricular_materias om
    JOIN materias m ON m.id = om.materia_id
    WHERE om.opcion_id IN ({ph}) AND om.institucion_id = %s AND m.institucion_id = %s
    ORDER BY om.opcion_id, m.escuela, m.carrera, m.plan_version, m.codigo, m.asignatura
"""
OPCION_COLS = "id, tipo, codigo, nombre, escuela_oferente, estado, observaciones, fecha_creacion, fecha_actualizacion"
GUARDA_REFS_SQL = """
    SELECT COUNT(DISTINCT comision_id) FROM (
        SELECT id AS comision_id
        FROM comisiones
        WHERE institucion_id = %s AND materia_id IN ({ph})
        UNION
        SELECT comision_id
        FROM comision_materias
        WHERE institucion_id = %s AND materia_id IN ({ph})
    ) refs
"""
GUARDA_IDS_SQL = """
    SELECT DISTINCT materia_id
    FROM (
        SELECT materia_id
        FROM comisiones
        WHERE institucion_id = %s
          AND materia_id IN ({ph})
        UNION
        SELECT materia_id
        FROM comision_materias
        WHERE institucion_id = %s
          AND materia_id IN ({ph})
    ) refs
    WHERE materia_id IS NOT NULL
"""


def _marks(n: int) -> str:
    return ",".join(["%s"] * n)


class MateriasRepository:
    def __init__(self, conn: Connection, institution_id: int):
        self._conn = conn
        self.inst = int(institution_id)
        self.mutating_statements = 0

    # --- primitivas
    def read(self, sql: str, params: Iterable[Any] = ()) -> pd.DataFrame:
        with self._conn.cursor() as cur:
            cur.execute(sql, list(params))
            cols = [d.name for d in cur.description] if cur.description else []
            rows = cur.fetchall() if cur.description else []
        # Igual que ``pandas.read_sql`` del certificado: ``coerce_float=True`` (numeric -> float).
        return pd.DataFrame.from_records(rows, columns=cols, coerce_float=True)

    def scalar(self, sql: str, params: Iterable[Any] = ()) -> Any:
        with self._conn.cursor() as cur:
            cur.execute(sql, list(params))
            row = cur.fetchone()
            return row[0] if row else None

    def mutate(self, sql: str, params: Iterable[Any] = ()) -> int:
        with self._conn.cursor() as cur:
            cur.execute(sql, list(params))
            self.mutating_statements += 1
            return max(int(cur.rowcount or 0), 0)

    def insert(self, sql: str, params: Iterable[Any]) -> int:
        with self._conn.cursor() as cur:
            cur.execute(sql + " RETURNING id", list(params))
            self.mutating_statements += 1
            return int(cur.fetchone()[0])

    # --- lecturas de la fuente unica de planes
    def carreras(self, escuela: Optional[str] = None, estado: Optional[str] = None) -> pd.DataFrame:
        filtros, params = [], []
        if escuela and escuela != "Todas":
            filtros.append("escuela = %s")
            params.append(escuela)
        if estado and estado != "Todos":
            filtros.append("estado = %s")
            params.append(estado)
        filtros.append("institucion_id = %s")
        params.append(self.inst)
        return self.read(f"SELECT {CARRERA_COLS} FROM carreras WHERE {' AND '.join(filtros)} "
                         "ORDER BY escuela, nombre, plan_version", params)

    def carrera(self, carrera_id: Any) -> Optional[dict]:
        df = self.read(f"SELECT {CARRERA_COLS} FROM carreras WHERE id = %s AND institucion_id = %s LIMIT 1",
                       [carrera_id, self.inst])
        return None if df.empty else df.iloc[0].to_dict()

    def plan(self, carrera_id: Any) -> pd.DataFrame:
        return self.read(PLAN_SQL, [carrera_id, self.inst])

    def plan_todas(self) -> pd.DataFrame:
        return self.read(PLAN_TODAS_SQL, [self.inst, self.inst])

    def escuelas(self) -> list[str]:
        valores = []
        for sql in ["SELECT DISTINCT escuela AS valor FROM carreras WHERE escuela IS NOT NULL AND TRIM(escuela) <> '' "
                    "AND institucion_id = %s",
                    "SELECT DISTINCT escuela AS valor FROM materias WHERE escuela IS NOT NULL AND TRIM(escuela) <> '' "
                    "AND institucion_id = %s"]:
            df = self.read(sql, [self.inst])
            valores.extend(df["valor"].dropna().astype(str).str.strip().tolist() if not df.empty else [])
        return sorted({v for v in valores if str(v).strip()}, key=lambda x: x.lower())

    def conteos(self) -> dict:
        return {t: int(self.scalar(f"SELECT COUNT(*) FROM {t} WHERE institucion_id = %s", [self.inst]) or 0)
                for t in ("carreras", "materias")}

    def materias_activas_carrera(self, carrera_id: Any) -> pd.DataFrame:
        return self.read("SELECT id, codigo, asignatura, anio, cuatrimestre, carga_semanal, carga_total FROM materias "
                         "WHERE carrera_id = %s AND COALESCE(en_plan, 1) = 1 AND institucion_id = %s",
                         [carrera_id, self.inst])

    def conflictos_base(self) -> pd.DataFrame:
        return self.read(CONFLICTOS_SQL, [self.inst, self.inst])

    def materias_archivadas_carrera(self, carrera_id: Any, cols: str = "id, codigo, asignatura") -> pd.DataFrame:
        return self.read(f"SELECT {cols} FROM materias WHERE carrera_id = %s AND COALESCE(en_plan, 1) = 0 "
                         "AND institucion_id = %s ORDER BY id", [carrera_id, self.inst])

    def materia(self, materia_id: Any, cols: str = "*") -> pd.DataFrame:
        return self.read(f"SELECT {cols} FROM materias WHERE id = %s AND institucion_id = %s LIMIT 1",
                         [materia_id, self.inst])

    def materias_identidad(self) -> pd.DataFrame:
        return self.read("SELECT id, carrera_id, codigo, asignatura, COALESCE(en_plan, 1) AS en_plan FROM materias "
                         "WHERE institucion_id = %s", [self.inst])

    def materias_codigo_nombre(self) -> pd.DataFrame:
        return self.read("SELECT id, codigo, asignatura FROM materias WHERE institucion_id = %s", [self.inst])

    def ids_materias_carrera(self, carrera_id: Any) -> pd.DataFrame:
        return self.read("SELECT id FROM materias WHERE carrera_id = %s AND institucion_id = %s",
                         [int(carrera_id), self.inst])

    def contar_materias_carrera(self, carrera_id: Any) -> int:
        return int(self.scalar("SELECT COUNT(*) FROM materias WHERE carrera_id = %s AND institucion_id = %s",
                               [carrera_id, self.inst]) or 0)

    def ids_misma_identidad(self, codigo: str, asignatura: str) -> pd.DataFrame:
        if codigo and asignatura:
            return self.read("SELECT id FROM materias WHERE TRIM(COALESCE(codigo, '')) = TRIM(%s) "
                             "AND LOWER(TRIM(COALESCE(asignatura, ''))) = LOWER(TRIM(%s)) AND institucion_id = %s",
                             [codigo, asignatura, self.inst])
        return self.read("SELECT id FROM materias WHERE LOWER(TRIM(COALESCE(asignatura, ''))) = LOWER(TRIM(%s)) "
                         "AND institucion_id = %s", [asignatura, self.inst])

    # --- guardas de Comisiones (lectura institucional)
    def referencias_comisiones(self, ids: list[int]) -> int:
        ph = _marks(len(ids))
        return int(self.scalar(GUARDA_REFS_SQL.format(ph=ph), [self.inst, *ids, self.inst, *ids]) or 0)

    def ids_referenciados(self, ids: list[int]) -> set[int]:
        ph = _marks(len(ids))
        df = self.read(GUARDA_IDS_SQL.format(ph=ph), [self.inst, *ids, self.inst, *ids])
        return {int(x) for x in df["materia_id"].tolist()} if not df.empty else set()

    def comisiones_con_opcion(self, opcion_id: int) -> int:
        return int(self.scalar("SELECT COUNT(*) AS n FROM comisiones WHERE institucion_id = %s "
                               "AND opcion_curricular_id = %s", [self.inst, int(opcion_id)]) or 0)

    # --- escrituras de carreras
    def insert_carrera(self, values: list) -> int:
        return self.insert("INSERT INTO carreras (escuela, codigo, nombre, titulo_otorga, plan_version, duracion, estado, "
                           "observaciones, institucion_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                           [*values, self.inst])

    def update_carrera(self, carrera_id: Any, values: list) -> int:
        return self.mutate("UPDATE carreras SET escuela = %s, codigo = %s, nombre = %s, titulo_otorga = %s, "
                           "plan_version = %s, duracion = %s, estado = %s, observaciones = %s "
                           "WHERE id = %s AND institucion_id = %s", [*values, carrera_id, self.inst])

    def sync_materias_carrera(self, carrera_id: Any, escuela: Any, nombre: Any, plan_version: Any) -> int:
        return self.mutate("UPDATE materias SET escuela = %s, carrera = %s, plan_version = %s "
                           "WHERE carrera_id = %s AND institucion_id = %s",
                           [escuela, nombre, plan_version, carrera_id, self.inst])

    def delete_vinculos_materias(self, ids: list[int]) -> int:
        return self.mutate(f"DELETE FROM opcion_curricular_materias WHERE materia_id IN ({_marks(len(ids))}) "
                           "AND institucion_id = %s", [*ids, self.inst])

    def delete_materias_carrera(self, carrera_id: Any) -> int:
        return self.mutate("DELETE FROM materias WHERE carrera_id = %s AND institucion_id = %s",
                           [carrera_id, self.inst])

    def delete_carrera(self, carrera_id: Any) -> int:
        return self.mutate("DELETE FROM carreras WHERE id = %s AND institucion_id = %s", [carrera_id, self.inst])

    # --- escrituras de materias
    def insert_materia(self, values: list) -> int:
        return self.insert("INSERT INTO materias (carrera_id, codigo, asignatura, carrera, escuela, anio, dictado, "
                           "carga_semanal, carga_total, cuatrimestre, duracion, plan_version, orden, estado, "
                           "observaciones, institucion_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                           "%s, %s, %s)", [*values, self.inst])

    def reactivar_materia(self, materia_id: int, values: list) -> int:
        return self.mutate("UPDATE materias SET en_plan = 1, codigo = %s, asignatura = %s, carrera = %s, escuela = %s, "
                           "anio = %s, dictado = %s, carga_semanal = %s, carga_total = %s, cuatrimestre = %s, "
                           "duracion = %s, plan_version = %s, orden = %s, estado = %s, observaciones = %s "
                           "WHERE id = %s AND institucion_id = %s", [*values, materia_id, self.inst])

    def update_materia(self, materia_id: Any, values: list) -> int:
        return self.mutate("UPDATE materias SET carrera_id = %s, codigo = %s, asignatura = %s, carrera = %s, "
                           "escuela = %s, anio = %s, dictado = %s, carga_semanal = %s, carga_total = %s, "
                           "cuatrimestre = %s, duracion = %s, plan_version = %s, orden = %s, estado = %s, "
                           "observaciones = %s WHERE id = %s AND institucion_id = %s",
                           [*values, materia_id, self.inst])

    def update_codigo_nombre(self, materia_id: int, codigo: str, asignatura: str) -> int:
        return self.mutate("UPDATE materias SET codigo = %s, asignatura = %s WHERE id = %s AND institucion_id = %s",
                           [codigo, asignatura, int(materia_id), self.inst])

    def archivar_materia(self, materia_id: int, carrera_id: int) -> int:
        return self.mutate("UPDATE materias SET en_plan = 0 WHERE id = %s AND carrera_id = %s "
                           "AND COALESCE(en_plan, 1) = 1 AND institucion_id = %s",
                           [materia_id, carrera_id, self.inst])

    def delete_materia_del_plan(self, materia_id: int, carrera_id: int) -> int:
        return self.mutate("DELETE FROM materias WHERE id = %s AND carrera_id = %s AND COALESCE(en_plan, 1) = 1 "
                           "AND institucion_id = %s", [materia_id, carrera_id, self.inst])

    def delete_archivadas(self, carrera_id: int, ids: list[int]) -> int:
        return self.mutate(f"DELETE FROM materias WHERE carrera_id = %s AND COALESCE(en_plan, 1) = 0 "
                           f"AND id IN ({_marks(len(ids))}) AND institucion_id = %s", [carrera_id, *ids, self.inst])

    def delete_materias_identidad(self, codigo: str, asignatura: str, materia_id: Any) -> int:
        if codigo and asignatura:
            return self.mutate("DELETE FROM materias WHERE TRIM(COALESCE(codigo, '')) = TRIM(%s) "
                               "AND LOWER(TRIM(COALESCE(asignatura, ''))) = LOWER(TRIM(%s)) AND institucion_id = %s",
                               [codigo, asignatura, self.inst])
        if asignatura:
            return self.mutate("DELETE FROM materias WHERE LOWER(TRIM(COALESCE(asignatura, ''))) = LOWER(TRIM(%s)) "
                               "AND institucion_id = %s", [asignatura, self.inst])
        return self.mutate("DELETE FROM materias WHERE id = %s AND institucion_id = %s", [materia_id, self.inst])

    # --- comparticion v137
    def comparticion(self, materia_id: int) -> tuple:
        df = self.read("SELECT COALESCE(comparticion_modo, %s) AS modo, COALESCE(comparticion_grupo, '') AS grupo "
                       "FROM materias WHERE id = %s AND institucion_id = %s LIMIT 1",
                       ["Automática", int(materia_id), self.inst])
        return (df.iloc[0]["modo"], df.iloc[0]["grupo"]) if not df.empty else None

    def set_comparticion(self, materia_id: int, modo: str, grupo: Optional[str]) -> int:
        return self.mutate("UPDATE materias SET comparticion_modo = %s, comparticion_grupo = %s "
                           "WHERE id = %s AND institucion_id = %s", [modo, grupo, int(materia_id), self.inst])

    def ids_grupo_seleccionado(self, modo: str, grupo: str) -> list[int]:
        df = self.read("SELECT id FROM materias WHERE comparticion_modo = %s AND comparticion_grupo = %s "
                       "AND institucion_id = %s", [modo, grupo, self.inst])
        return [int(x) for x in df["id"].tolist()] if not df.empty else []

    # --- opciones curriculares v120
    def opciones(self, tipo: Optional[str] = None, estado: Optional[str] = None) -> pd.DataFrame:
        filtros, params = [], []
        if tipo:
            filtros.append("tipo = %s")
            params.append(tipo)
        if estado:
            filtros.append("estado = %s")
            params.append(estado)
        filtros.append("institucion_id = %s")
        params.append(self.inst)
        return self.read(f"SELECT {OPCION_COLS} FROM opciones_curriculares WHERE {' AND '.join(filtros)} "
                         "ORDER BY tipo, nombre, codigo", params)

    def opcion(self, opcion_id: int) -> Optional[dict]:
        df = self.read(f"SELECT {OPCION_COLS} FROM opciones_curriculares WHERE id = %s AND institucion_id = %s LIMIT 1",
                       [int(opcion_id), self.inst])
        return None if df.empty else df.iloc[0].to_dict()

    def vinculos_lote(self, ids: list[int]) -> pd.DataFrame:
        return self.read(VINCULOS_LOTE_SQL.format(ph=_marks(len(ids))), [*ids, self.inst, self.inst])

    def tipos_opciones_de_materias(self, ids: list[int]) -> pd.DataFrame:
        return self.read(f"SELECT DISTINCT o.tipo FROM opcion_curricular_materias om "
                         f"JOIN opciones_curriculares o ON o.id = om.opcion_id "
                         f"WHERE om.materia_id IN ({_marks(len(ids))}) AND om.institucion_id = %s "
                         f"AND o.institucion_id = %s", [*ids, self.inst, self.inst])

    def materias_de_opcion(self, opcion_id: int) -> pd.DataFrame:
        return self.read("SELECT materia_id FROM opcion_curricular_materias WHERE opcion_id = %s AND institucion_id = %s",
                         [int(opcion_id), self.inst])

    def insert_opcion(self, values: list) -> int:
        return self.insert("INSERT INTO opciones_curriculares (tipo, codigo, nombre, escuela_oferente, estado, "
                           "observaciones, fecha_creacion, fecha_actualizacion, institucion_id) "
                           "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", [*values, self.inst])

    def update_opcion(self, opcion_id: int, values: list) -> int:
        return self.mutate("UPDATE opciones_curriculares SET tipo = %s, codigo = %s, nombre = %s, escuela_oferente = %s, "
                           "estado = %s, observaciones = %s, fecha_actualizacion = %s "
                           "WHERE id = %s AND institucion_id = %s", [*values, int(opcion_id), self.inst])

    def insert_vinculo(self, opcion_id: int, materia_id: int, fecha: str) -> int:
        return self.insert("INSERT INTO opcion_curricular_materias (opcion_id, materia_id, fecha_vinculacion, "
                           "institucion_id) VALUES (%s, %s, %s, %s)", [int(opcion_id), int(materia_id), fecha, self.inst])

    def delete_vinculo(self, opcion_id: int, materia_id: int) -> int:
        return self.mutate("DELETE FROM opcion_curricular_materias WHERE opcion_id = %s AND materia_id = %s "
                           "AND institucion_id = %s", [int(opcion_id), int(materia_id), self.inst])

    def delete_vinculos_opcion(self, opcion_id: int) -> int:
        return self.mutate("DELETE FROM opcion_curricular_materias WHERE opcion_id = %s AND institucion_id = %s",
                           [int(opcion_id), self.inst])

    def delete_opcion(self, opcion_id: int) -> int:
        return self.mutate("DELETE FROM opciones_curriculares WHERE id = %s AND institucion_id = %s",
                           [int(opcion_id), self.inst])
