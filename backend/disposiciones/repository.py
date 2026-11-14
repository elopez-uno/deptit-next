"""SQL de Disposiciones sobre una conexion/transaccion ya abierta.  Nunca crea ni altera tablas y nunca confirma.

Las sentencias por ``get_conn()`` son las del entry con el ambito que les agrega el inyector B12B v193 + B12J (texto
obtenido con ``tests/tools_comisiones_inject_sql.py``): ``disposiciones``, ``disposicion_parametros``,
``disposicion_docente_parametros``, ``estado_consulta_designacion``, ``docentes`` y ``periodos`` son tablas de
DEPARTAMENTO; ``disposicion_docente_designaciones`` es de INSTITUCION (el inyector solo agrega ``institucion_id``).  Las
lecturas por ``_pg_read_dataframe`` (ambito compartido/prestado, nombre del departamento, vinculos v118 globales y el
control de dueño B12E) llevan su ambito explicito, sin inyector.  Ningun UPDATE/DELETE valida ``rowcount`` salvo el
UPDATE-then-INSERT certificado de los parametros.  Sin DDL: el esquema existe (``asegurar_esquema_*`` excluidos).

``DisposicionesRepository`` hereda las lecturas ya portadas por bloques cerrados (Designaciones, Comisiones,
Investigacion, Extension, Actividades Especiales) sin modificarlas.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

import pandas as pd

from actividades_especiales.repository import ActividadesRepository
from designaciones.repository import DESIGNACIONES_SQL
from designaciones.rules import condicion_periodo_equivalente_sql
from docentes.repository import DOCENTES_SQL
from extension.repository import ExtensionRepository

_SC = "({t}.institucion_id = %s) AND ({t}.departamento_id = %s)"

# --- parametros generales (l. 5548 / 5559) ----------------------------------------------------------------------------
PARAMETROS_SQL = f"SELECT clave, valor FROM disposicion_parametros WHERE {_SC.format(t='disposicion_parametros')} "
UPDATE_PARAMETRO_SQL = ("UPDATE disposicion_parametros\n                SET valor = %s\n                WHERE clave = %s "
                        f"AND {_SC.format(t='disposicion_parametros')} ")
INSERT_PARAMETRO_SQL = ("INSERT INTO disposicion_parametros (clave, valor, institucion_id, departamento_id) "
                        "VALUES (%s, %s, %s, %s)  RETURNING id")

# --- parametros por docente (l. 5605 / 5639 -> v162 l. 35206 / 35228) -------------------------------------------------
PARAMETROS_DOCENTE_SQL = ("SELECT * FROM disposicion_docente_parametros WHERE cuil = %s AND "
                          f"{_SC.format(t='disposicion_docente_parametros')} LIMIT 1")
TEXTO_FUNCION_SQL = ("SELECT COALESCE(texto_funcion_disposicion, '') AS texto_funcion_disposicion FROM "
                     "disposicion_docente_parametros WHERE cuil = %s AND "
                     f"{_SC.format(t='disposicion_docente_parametros')} LIMIT 1")
UPDATE_PARAMETROS_DOCENTE_SQL = (
    "UPDATE disposicion_docente_parametros\n        SET resolucion_cs_concursado = %s,\n"
    "            fecha_desde_concursado = %s,\n            fecha_hasta_concursado = %s,\n"
    "            resolucion_cs_interino = %s,\n            fecha_desde_interino = %s,\n"
    "            fecha_hasta_interino = %s,\n            codigo_proyecto = %s,\n            instituto_proyecto = %s,\n"
    f"            observaciones = %s\n        WHERE cuil = %s AND {_SC.format(t='disposicion_docente_parametros')} ")
INSERT_PARAMETROS_DOCENTE_SQL = (
    "INSERT INTO disposicion_docente_parametros (cuil, resolucion_cs_concursado, fecha_desde_concursado, "
    "fecha_hasta_concursado, resolucion_cs_interino, fecha_desde_interino, fecha_hasta_interino, codigo_proyecto, "
    "instituto_proyecto, observaciones, institucion_id, departamento_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, "
    "%s, %s, %s)  RETURNING id")
UPDATE_TEXTO_FUNCION_SQL = ("UPDATE disposicion_docente_parametros SET texto_funcion_disposicion = %s WHERE cuil = %s "
                            f"AND {_SC.format(t='disposicion_docente_parametros')} ")

# --- datos por designacion (l. 5785 / 5942; tabla de INSTITUCION) ----------------------------------------------------
DATOS_DESIGNACIONES_SQL = """SELECT id, designacion_id, cuil, departamento_id, tipo_designacion,
                   cargo, dedicacion, resolucion, fecha_desde, fecha_hasta,
                   observaciones, fecha_actualizacion
            FROM disposicion_docente_designaciones
            WHERE cuil = %s AND (disposicion_docente_designaciones.institucion_id = %s) ORDER BY COALESCE(fecha_actualizacion, '') DESC, id DESC"""
UPDATE_DATOS_DESIGNACION_SQL = """UPDATE disposicion_docente_designaciones
            SET departamento_id = %s, tipo_designacion = %s, cargo = %s, dedicacion = %s,
                resolucion = %s, fecha_desde = %s, fecha_hasta = %s, observaciones = %s,
                fecha_actualizacion = %s
            WHERE designacion_id = %s AND cuil = %s AND (disposicion_docente_designaciones.institucion_id = %s) """
INSERT_DATOS_DESIGNACION_SQL = (
    "INSERT INTO disposicion_docente_designaciones (designacion_id, cuil, departamento_id, tipo_designacion, cargo, "
    "dedicacion, resolucion, fecha_desde, fecha_hasta, observaciones, fecha_actualizacion, institucion_id) VALUES "
    "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)  RETURNING id")

# --- registro (l. 6230 / 6245) e historial (extracted_batch03 ``get_disposiciones``) ----------------------------------
INSERT_DISPOSICION_SQL = (
    "INSERT INTO disposiciones (periodo_id, fecha, tipo, numero, cuil, docente, detalle, observaciones, estado, "
    "archivo_word, plantilla_usada, variables_json, fecha_creacion, institucion_id, departamento_id) VALUES (%s, %s, "
    "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)  RETURNING id")
DELETE_DISPOSICION_SQL = f"DELETE FROM disposiciones WHERE id = %s AND {_SC.format(t='disposiciones')} "
HISTORIAL_SQL = """SELECT
            d.id,
            d.periodo_id,
            p.nombre AS periodo,
            d.fecha,
            d.numero,
            d.tipo,
            d.cuil,
            d.docente,
            d.estado,
            d.detalle,
            d.observaciones,
            d.archivo_word,
            d.plantilla_usada,
            d.fecha_creacion
        FROM disposiciones d
        LEFT JOIN periodos p ON (p.id = d.periodo_id) AND (p.institucion_id = %s) AND (p.departamento_id = %s)
        WHERE {periodo}(d.institucion_id = %s) AND (d.departamento_id = %s) ORDER BY COALESCE(p.anio, 0) DESC, COALESCE(p.semestre, 0) DESC, d.fecha DESC, d.id DESC"""

# --- estado de consulta (l. 23842, SOLO LECTURA: D12) y nombre del docente (contexto base l. 7072) -------------------
ESTADO_CONSULTA_SQL = ("SELECT estado, fecha_actualizacion\n        FROM estado_consulta_designacion\n"
                       "        WHERE periodo_id = %s AND cuil = %s AND "
                       f"{_SC.format(t='estado_consulta_designacion')} ORDER BY id DESC\n        LIMIT 1")
DOCENTE_NOMBRE_SQL = """SELECT
            cuil,
            CASE
                WHEN apellido IS NOT NULL AND nombres IS NOT NULL THEN apellido || ', ' || nombres
                WHEN nombre IS NOT NULL THEN nombre
                ELSE cuil
            END AS docente
        FROM docentes
        WHERE cuil = %s AND (docentes.institucion_id = %s) AND (docentes.departamento_id = %s) LIMIT 1"""

# --- lecturas crudas (``_pg_read_dataframe``: ambito explicito) --------------------------------------------------------
DEPARTAMENTO_NOMBRE_SQL = "SELECT nombre FROM departamentos WHERE id = %s LIMIT 1"
AMBITO_DESIGNADOS_SQL = f"""
                WITH pr AS (
                    SELECT id, institucion_id, nombre, anio, semestre
                    FROM periodos
                    WHERE id = %s
                    LIMIT 1
                )
                SELECT DISTINCT d.departamento_id
                FROM designaciones d
                JOIN periodos p ON p.id = d.periodo_id
                JOIN pr ON {condicion_periodo_equivalente_sql('p', 'pr')}
                WHERE d.institucion_id = %s
                  AND regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g') = %s
                  AND COALESCE(d.estado, 'Activa') = 'Activa'
            """
AMBITO_PRESTADOS_SQL = """
                SELECT d.departamento_id,
                       COALESCE(dep.nombre, '') AS departamento,
                       COALESCE(d.observaciones, '') AS observaciones
                FROM docentes d
                LEFT JOIN departamentos dep ON dep.id = d.departamento_id
                WHERE d.institucion_id = %s
                  AND regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g') = %s
                  AND COALESCE(d.tipo_docente, 'Propio') = 'Prestado'
                  AND COALESCE(d.estado, 'Activo') = 'Activo'
                ORDER BY dep.nombre, d.id
            """
_COLS_VINCULOS_V118 = ("comision_id, materia_id, carrera_id_snapshot, carrera_snapshot, escuela_snapshot, "
                       "plan_version_snapshot, anio_snapshot, cuatrimestre_snapshot, dictado_snapshot, "
                       "carga_semanal_snapshot, carga_total_snapshot, codigo_snapshot, asignatura_snapshot, "
                       "fecha_vinculacion, origen")
VINCULOS_V118_GLOBAL_SQL = (f"SELECT {_COLS_VINCULOS_V118} FROM comision_materias WHERE institucion_id=%s AND "
                            "comision_id IN ({ph}) ORDER BY comision_id, materia_id")
# B12E ``_query_rows``: re-consulta por id con institucion/departamento explicitos del ambito de la sesion.
FILAS_DUENO_SQL = ("SELECT id, institucion_id, departamento_id, archivo_word FROM disposiciones WHERE institucion_id = %s"
                   " AND departamento_id = %s AND id IN ({ph})")


class DisposicionesRepository(ExtensionRepository, ActividadesRepository):
    """Repositorio de la operacion: ``_scope`` = [institucion, departamento] de la sesion revalidada."""

    # --- lecturas por get_conn()
    def parametros(self) -> pd.DataFrame:
        return self.read_sql(PARAMETROS_SQL, self._scope)

    def parametros_docente(self, cuil: str) -> pd.DataFrame:
        return self.read_sql(PARAMETROS_DOCENTE_SQL, [str(cuil)] + self._scope)

    def texto_funcion_docente(self, cuil: str) -> pd.DataFrame:
        return self.read_sql(TEXTO_FUNCION_SQL, [str(cuil)] + self._scope)

    def datos_designaciones(self, cuil: str) -> pd.DataFrame:
        return self.read_sql(DATOS_DESIGNACIONES_SQL, [str(cuil), self.inst])

    def historial(self, periodo_id: Optional[int]) -> pd.DataFrame:
        if periodo_id is None:
            return self.read_sql(HISTORIAL_SQL.replace("{periodo}", ""), self._scope * 2)
        return self.read_sql(HISTORIAL_SQL.replace("{periodo}", "d.periodo_id = %s AND "),
                             self._scope + [periodo_id] + self._scope)

    def estado_consulta(self, periodo_id: int, cuil: str) -> pd.DataFrame:
        return self.read_sql(ESTADO_CONSULTA_SQL, [int(periodo_id), str(cuil)] + self._scope)

    def docente_nombre(self, cuil: str) -> pd.DataFrame:
        return self.read_sql(DOCENTE_NOMBRE_SQL, [cuil] + self._scope)

    def docentes_df(self) -> pd.DataFrame:
        """``get_docentes()`` efectiva (base v204; v182/v183 solo agregan ``estado_periodo_abierto``)."""
        return self.read_sql(DOCENTES_SQL, self._scope)

    def designaciones_df(self, periodo_id: int) -> pd.DataFrame:
        """``get_designaciones(periodo_id)`` efectiva (v95 + v162: funcion no docente; v266 no aporta columnas que use
        Disposiciones)."""
        p = self._scope + self._scope + [int(periodo_id)] + self._scope
        return self.read_sql(DESIGNACIONES_SQL, p)

    # --- lecturas crudas
    def departamento_nombre(self, dep_id: int) -> pd.DataFrame:
        return self.read_raw(DEPARTAMENTO_NOMBRE_SQL, [int(dep_id)])

    def ambito_designados(self, periodo_id: int, clave_cuil: str) -> pd.DataFrame:
        return self.read_raw(AMBITO_DESIGNADOS_SQL, [int(periodo_id), self.inst, clave_cuil])

    def ambito_prestados(self, clave_cuil: str) -> pd.DataFrame:
        return self.read_raw(AMBITO_PRESTADOS_SQL, [self.inst, clave_cuil])

    def vinculos_v118_global(self, ids: list[int]) -> pd.DataFrame:
        return self.read_raw(VINCULOS_V118_GLOBAL_SQL.replace("{ph}", ",".join(["%s"] * len(ids))),
                             [self.inst] + list(ids))

    def filas_dueno(self, ids: list[int]) -> pd.DataFrame:
        return self.read_raw(FILAS_DUENO_SQL.replace("{ph}", ", ".join(["%s"] * len(ids))),
                             self._scope + [int(i) for i in ids])

    # --- escrituras (el COMMIT lo decide la Unidad)
    def update_parametro(self, clave: str, valor: str) -> int:
        return self._mutate(UPDATE_PARAMETRO_SQL, [valor, clave] + self._scope)

    def insert_parametro(self, clave: str, valor: str) -> int:
        return self._insert_id(INSERT_PARAMETRO_SQL, [clave, valor] + self._scope)

    def update_parametros_docente(self, valores: list, cuil: str) -> int:
        return self._mutate(UPDATE_PARAMETROS_DOCENTE_SQL, list(valores) + [str(cuil)] + self._scope)

    def insert_parametros_docente(self, cuil: str, valores: list) -> int:
        return self._insert_id(INSERT_PARAMETROS_DOCENTE_SQL, [str(cuil)] + list(valores) + self._scope)

    def update_texto_funcion(self, texto: str, cuil: str) -> int:
        return self._mutate(UPDATE_TEXTO_FUNCION_SQL, [texto, str(cuil)] + self._scope)

    def update_datos_designacion(self, valores: Iterable[Any]) -> int:
        return self._mutate(UPDATE_DATOS_DESIGNACION_SQL, list(valores) + [self.inst])

    def insert_datos_designacion(self, valores: Iterable[Any]) -> int:
        return self._insert_id(INSERT_DATOS_DESIGNACION_SQL, list(valores) + [self.inst])

    def insert_disposicion(self, valores: Iterable[Any]) -> int:
        return self._insert_id(INSERT_DISPOSICION_SQL, list(valores) + self._scope)

    def delete_disposicion(self, disposicion_id: int) -> int:
        return self._mutate(DELETE_DISPOSICION_SQL, [int(disposicion_id)] + self._scope)


__all__ = ["DisposicionesRepository"]
