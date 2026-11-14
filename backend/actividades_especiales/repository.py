"""SQL de Actividades Especiales sobre una conexion/transaccion ya abierta.  Nunca crea ni altera tablas y nunca confirma.

Las sentencias son las del entry (l. 32099-32160) con el ambito que les agrega ``get_conn()`` (inyector B12B v193
re-enlazado por B12J; texto obtenido con ``tests/tools_comisiones_inject_sql.py``): ``actividades_especiales``,
``actividad_especial_docente``, ``periodos`` y ``docentes`` son tablas de DEPARTAMENTO; en un LEFT JOIN el filtro va al
``ON``.  La subconsulta del conteo de docentes NO recibe ambito (el inyector solo alcanza los alias del FROM externo):
se replica tal cual.  Los UPDATE/DELETE no validan ``rowcount`` (comportamiento certificado).

La rama ``todos_departamentos`` de ``get_actividades_especiales_docente`` (l. 32126-32138, ``_pg_read_dataframe`` sin
inyector) queda como lectura institucional (decision G5) para el futuro Resumen docente.
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from comisiones.repository import ComisionesRepository

_SC = "({a}.institucion_id = %s) AND ({a}.departamento_id = %s)"

# --- get_actividades_especiales (l. 32105) ----------------------------------------------------------------------
ACTIVIDADES_SQL = f"""
    SELECT ae.id,ae.periodo_id,per.nombre AS periodo,ae.titulo,ae.descripcion,ae.estado,ae.observaciones,ae.fecha_carga,
        COALESCE((SELECT COUNT(*) FROM actividad_especial_docente ad WHERE ad.actividad_id=ae.id AND COALESCE(ad.estado_asignacion,'Activa')='Activa'),0) AS cantidad_docentes
        FROM actividades_especiales ae LEFT JOIN periodos per ON (per.id=ae.periodo_id) AND {_SC.format(a='per')}
        WHERE {{where}}{_SC.format(a='ae')} ORDER BY per.anio DESC,per.semestre DESC,ae.titulo
"""

# --- get_actividades_especiales_docente, rama local (l. 32139-32146) ------------------------------------------
PARTICIPACIONES_LOCAL_SQL = f"""
    SELECT ad.id,ad.actividad_id,ad.periodo_id,per.nombre AS periodo,'' AS departamento_asignacion,ae.titulo,ae.descripcion,ae.estado AS estado_actividad,ad.cuil,
        CASE WHEN d.apellido IS NOT NULL AND d.nombres IS NOT NULL THEN d.apellido||', '||d.nombres WHEN d.nombre IS NOT NULL THEN d.nombre ELSE ad.cuil END AS docente,
        ad.rol,ad.estado_asignacion,ad.observaciones,ad.fecha_carga FROM actividad_especial_docente ad JOIN actividades_especiales ae ON ae.id=ad.actividad_id
        LEFT JOIN periodos per ON (per.id=ad.periodo_id) AND {_SC.format(a='per')}
        LEFT JOIN docentes d ON (d.cuil=ad.cuil) AND {_SC.format(a='d')}
        WHERE {{where}}{_SC.format(a='ad')} AND {_SC.format(a='ae')} ORDER BY per.anio DESC,per.semestre DESC,ae.titulo,docente
"""

# --- rama todos_departamentos (l. 32126-32138, _pg_read_dataframe: ambito explicito, sin inyector) -------------
PERIODO_EQUIVALENTE_SQL = "SELECT nombre, anio, semestre FROM periodos WHERE id = %s LIMIT 1"  # extracted_batch03 l. 204
PARTICIPACIONES_INSTITUCION_SQL = """
    SELECT ad.id,ad.actividad_id,ad.periodo_id,per.nombre AS periodo,
            ad.departamento_id AS departamento_asignacion_id, dep.nombre AS departamento_asignacion,
            ae.titulo,ae.descripcion,ae.estado AS estado_actividad,ad.cuil,
            COALESCE((SELECT CASE WHEN d.apellido IS NOT NULL AND d.nombres IS NOT NULL THEN d.apellido||', '||d.nombres WHEN d.nombre IS NOT NULL THEN d.nombre ELSE d.cuil END FROM docentes d WHERE d.institucion_id=ad.institucion_id AND d.cuil=ad.cuil ORDER BY CASE WHEN d.departamento_id=ad.departamento_id THEN 0 ELSE 1 END,d.id LIMIT 1),ad.cuil) AS docente,
            ad.rol,ad.estado_asignacion,ad.observaciones,ad.fecha_carga
            FROM actividad_especial_docente ad JOIN actividades_especiales ae ON ae.id=ad.actividad_id LEFT JOIN periodos per ON per.id=ad.periodo_id LEFT JOIN departamentos dep ON dep.id=ad.departamento_id
            WHERE {where} ORDER BY per.anio DESC,per.semestre DESC,ae.titulo,docente
"""

# --- writers (get_conn + inyector) -------------------------------------------------------------------------------
INSERT_ACTIVIDAD_SQL = ("INSERT INTO actividades_especiales (periodo_id, titulo, descripcion, estado, observaciones, "
                        "fecha_carga, institucion_id, departamento_id) VALUES (%s, %s, %s, 'Activa', %s, %s, %s, %s)  "
                        "RETURNING id")
PERIODO_ACTIVIDAD_SQL = ("SELECT periodo_id FROM actividades_especiales WHERE id=%s AND "
                         f"{_SC.format(a='actividades_especiales')} LIMIT 1")
DUP_PARTICIPACION_SQL = ("SELECT id FROM actividad_especial_docente WHERE actividad_id=%s AND cuil=%s AND "
                         "COALESCE(estado_asignacion,'Activa')='Activa' AND "
                         f"{_SC.format(a='actividad_especial_docente')} LIMIT 1")
INSERT_PARTICIPACION_SQL = ("INSERT INTO actividad_especial_docente (actividad_id, periodo_id, cuil, rol, "
                            "estado_asignacion, observaciones, fecha_carga, institucion_id, departamento_id) VALUES "
                            "(%s, %s, %s, %s, 'Activa', %s, %s, %s, %s)  RETURNING id")
DELETE_PARTICIPACION_SQL = (f"DELETE FROM actividad_especial_docente WHERE id=%s AND "
                            f"{_SC.format(a='actividad_especial_docente')} ")
DELETE_PARTICIPACIONES_ACTIVIDAD_SQL = (f"DELETE FROM actividad_especial_docente WHERE actividad_id=%s AND "
                                        f"{_SC.format(a='actividad_especial_docente')} ")
DELETE_ACTIVIDAD_SQL = f"DELETE FROM actividades_especiales WHERE id=%s AND {_SC.format(a='actividades_especiales')} "
UPDATE_ACTIVIDAD_SQL = ("UPDATE actividades_especiales SET titulo=%s,descripcion=%s,estado=%s,observaciones=%s WHERE "
                        f"id=%s AND {_SC.format(a='actividades_especiales')} ")


class ActividadesRepository(ComisionesRepository):
    """Repositorio de la operacion: ``_scope`` = [institucion, departamento] de la sesion revalidada."""

    def actividades(self, periodo_id: Optional[int] = None, incluir_inactivas: bool = True) -> pd.DataFrame:
        """``get_actividades_especiales`` (l. 32105)."""
        filtros, params = [], []
        if periodo_id is not None:
            filtros.append("ae.periodo_id=%s")
            params.append(int(periodo_id))
        if not incluir_inactivas:
            filtros.append("COALESCE(ae.estado,'Activa')='Activa'")
        where = "".join(f"{f} AND " for f in filtros)
        return self.read_sql(ACTIVIDADES_SQL.replace("{where}", where), self._scope + params + self._scope)

    def participaciones_local(self, cuil: Optional[str] = None, periodo_id: Optional[int] = None,
                              incluir_bajas: bool = False) -> pd.DataFrame:
        """``get_actividades_especiales_docente(..., todos_departamentos=False)`` (l. 32139)."""
        filtros, params = [], []
        if cuil is not None:
            filtros.append("ad.cuil=%s")
            params.append(str(cuil))
        if periodo_id is not None:
            filtros.append("ad.periodo_id=%s")
            params.append(int(periodo_id))
        if not incluir_bajas:
            filtros.append("COALESCE(ad.estado_asignacion,'Activa')='Activa'")
        where = "".join(f"{f} AND " for f in filtros)
        return self.read_sql(PARTICIPACIONES_LOCAL_SQL.replace("{where}", where),
                             self._scope * 2 + params + self._scope * 2)

    def periodo_equivalente(self, periodo_id) -> tuple[str, int, int]:
        """``_periodo_equivalente_pg`` (extracted_batch03 l. 201)."""
        try:
            df = self.read_raw(PERIODO_EQUIVALENTE_SQL, [periodo_id])
            if not df.empty:
                r = df.iloc[0]
                return str(r.get("nombre") or ""), int(r.get("anio") or 0), int(r.get("semestre") or 0)
        except Exception:
            pass
        return "", 0, 0

    def participaciones_institucion(self, cuil: Optional[str] = None, periodo_id: Optional[int] = None,
                                    incluir_bajas: bool = False) -> pd.DataFrame:
        """``get_actividades_especiales_docente(..., todos_departamentos=True)`` (l. 32126): toda la institucion,
        periodo equivalente por id, nombre o anio+semestre (lectura institucional G5, sin pantalla)."""
        filtros, params = ["ad.institucion_id=%s"], [self.inst]
        if cuil is not None:
            filtros.append("ad.cuil=%s")
            params.append(str(cuil))
        if periodo_id is not None:
            pn, pa, ps = self.periodo_equivalente(periodo_id)
            filtros.append("(ad.periodo_id=%s OR per.nombre=%s OR (per.anio=%s AND per.semestre=%s))")
            params += [int(periodo_id), pn, int(pa), int(ps)]
        if not incluir_bajas:
            filtros.append("COALESCE(ad.estado_asignacion,'Activa')='Activa'")
        return self.read_raw(PARTICIPACIONES_INSTITUCION_SQL.replace("{where}", " AND ".join(filtros)), params)

    # --- escrituras (un COMMIT por writer lo decide la Unidad)
    def insert_actividad(self, periodo_id: int, titulo: str, descripcion: Any, observaciones: Any, fecha: str) -> int:
        return self._insert_id(INSERT_ACTIVIDAD_SQL, [int(periodo_id), titulo, descripcion, observaciones, fecha]
                               + self._scope)

    def periodo_de_actividad(self, actividad_id: int) -> Optional[int]:
        df = self.read_sql(PERIODO_ACTIVIDAD_SQL, [int(actividad_id)] + self._scope)
        return None if df.empty else int(df.iloc[0]["periodo_id"])

    def participacion_activa(self, actividad_id: int, cuil: str) -> bool:
        return not self.read_sql(DUP_PARTICIPACION_SQL, [int(actividad_id), str(cuil)] + self._scope).empty

    def insert_participacion(self, actividad_id: int, periodo_id: int, cuil: str, rol: str, observaciones: Any,
                             fecha: str) -> int:
        return self._insert_id(INSERT_PARTICIPACION_SQL, [int(actividad_id), int(periodo_id), str(cuil), rol,
                                                          observaciones, fecha] + self._scope)

    def delete_participacion(self, asignacion_id: int) -> int:
        return self._mutate(DELETE_PARTICIPACION_SQL, [int(asignacion_id)] + self._scope)

    def delete_actividad(self, actividad_id: int) -> None:
        self._mutate(DELETE_PARTICIPACIONES_ACTIVIDAD_SQL, [int(actividad_id)] + self._scope)
        self._mutate(DELETE_ACTIVIDAD_SQL, [int(actividad_id)] + self._scope)

    def update_actividad(self, actividad_id: int, titulo: str, descripcion: Any, estado: Any, observaciones: Any) -> int:
        return self._mutate(UPDATE_ACTIVIDAD_SQL, [titulo, descripcion, estado, observaciones, int(actividad_id)]
                            + self._scope)


__all__ = ["ActividadesRepository"]
