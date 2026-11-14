"""SQL de Extension sobre una conexion/transaccion ya abierta.  Nunca crea ni altera tablas y nunca confirma.

El SQL certificado de Extension (entry l. 22333-23320, v199 l. 45295 con ``tabla_p``/``tabla_a``, v217 l. 48204-48268
con ``extension_docente``, carga v217 l. 49057 con ``tabla_asig``) es, sentencia por sentencia, el de Investigacion con
``proyectos_investigacion`` -> ``proyectos_extension`` e ``investigacion_docente`` -> ``extension_docente``
(docs/audit/extension_phase_a/pair_diff.txt).  Por eso cada constante se deriva del texto ya validado de
``investigacion.repository`` (sin modificarlo) sustituyendo SOLO esos dos nombres de tabla, igual que el inyector
v193/B12J que enlaza el ambito por nombre de tabla.  Las sentencias sin esas tablas (periodos, actos v263/v261/v267,
movimientos, departamentos) se reutilizan tal cual.

``ExtensionRepository`` hereda de ``InvestigacionRepository`` (primitivas, periodos, actos, departamentos) y redefine
solo los metodos que leen las tablas de proyectos.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from investigacion import repository as IQ
from investigacion.repository import InvestigacionRepository

_TABLAS = (("proyectos_investigacion", "proyectos_extension"), ("investigacion_docente", "extension_docente"))


def _ext(sql: str) -> str:
    for inv, ext in _TABLAS:
        sql = sql.replace(inv, ext)
    assert "investigacion" not in sql, sql
    return sql


PROYECTO_POR_ID_SQL = _ext(IQ.PROYECTO_POR_ID_SQL)
PROYECTOS_BULK_V199_SQL = _ext(IQ.PROYECTOS_BULK_V199_SQL)
ASIG_LOCAL_SQL = _ext(IQ.ASIG_LOCAL_SQL)
PERIODO_REF_CTE = IQ.PERIODO_REF_CTE
BUSCAR_ACTIVA_V217_SQL = _ext(IQ.BUSCAR_ACTIVA_V217_SQL)
INTEGRANTES_V217_SQL = _ext(IQ.INTEGRANTES_V217_SQL)
DOCUMENTOS_PROYECTOS_V263_SQL = IQ.DOCUMENTOS_PROYECTOS_V263_SQL
UPSERT_DOCUMENTO_PROYECTO_SQL = IQ.UPSERT_DOCUMENTO_PROYECTO_SQL
DESVINCULAR_DOCUMENTO_PROYECTOS_SQL = IQ.DESVINCULAR_DOCUMENTO_PROYECTOS_SQL
DUP_CODIGO_SQL = _ext(IQ.DUP_CODIGO_SQL)
DUP_NOMBRE_FECHAS_SQL = _ext(IQ.DUP_NOMBRE_FECHAS_SQL)
INSERT_PROYECTO_SQL = _ext(IQ.INSERT_PROYECTO_SQL)
DUP_OTRO_CODIGO_SQL = _ext(IQ.DUP_OTRO_CODIGO_SQL)
DUP_OTRO_NOMBRE_SQL = _ext(IQ.DUP_OTRO_NOMBRE_SQL)
UPDATE_PROYECTO_SQL = _ext(IQ.UPDATE_PROYECTO_SQL)
UPDATE_ASIG_DESNORMALIZADAS_SQL = _ext(IQ.UPDATE_ASIG_DESNORMALIZADAS_SQL)
NOMBRE_PERIODO_DEP_SQL = IQ.NOMBRE_PERIODO_DEP_SQL
SUSPENDER_PROYECTO_SQL = _ext(IQ.SUSPENDER_PROYECTO_SQL)
SUSPENDER_ASIGNACIONES_SQL = _ext(IQ.SUSPENDER_ASIGNACIONES_SQL)
ARCHIVAR_PROYECTO_SQL = _ext(IQ.ARCHIVAR_PROYECTO_SQL)
PROYECTO_NOMBRE_CODIGO_SQL = _ext(IQ.PROYECTO_NOMBRE_CODIGO_SQL)
CONTAR_ASIG_PROYECTO_SQL = _ext(IQ.CONTAR_ASIG_PROYECTO_SQL)
DELETE_ASIG_PROYECTO_SQL = _ext(IQ.DELETE_ASIG_PROYECTO_SQL)
DELETE_PROYECTO_SQL = _ext(IQ.DELETE_PROYECTO_SQL)
DUP_LOCAL_ASIG_SQL = _ext(IQ.DUP_LOCAL_ASIG_SQL)
INSERT_ASIG_SQL = _ext(IQ.INSERT_ASIG_SQL)
UPDATE_ASIG_SQL = _ext(IQ.UPDATE_ASIG_SQL)
BAJA_ASIG_SQL = _ext(IQ.BAJA_ASIG_SQL)
ASIG_POR_ID_INST_SQL = _ext(IQ.ASIG_POR_ID_INST_SQL)
DELETE_ASIG_SQL = _ext(IQ.DELETE_ASIG_SQL)
PERIODO_INST_SQL = IQ.PERIODO_INST_SQL
PARES_ACTIVOS_SQL = _ext(IQ.PARES_ACTIVOS_SQL)
INSERT_ASIG_EXCEL_SQL = _ext(IQ.INSERT_ASIG_EXCEL_SQL)
INSERT_MOVIMIENTO_EXCEL_SQL = IQ.INSERT_MOVIMIENTO_EXCEL_SQL
DEPARTAMENTOS_ACTIVOS_SQL = IQ.DEPARTAMENTOS_ACTIVOS_SQL


class ExtensionRepository(InvestigacionRepository):
    """Repositorio de la operacion sobre ``proyectos_extension`` / ``extension_docente``."""

    def proyecto_por_id(self, proyecto_id: int) -> pd.DataFrame:
        return self.read_sql(PROYECTO_POR_ID_SQL, [int(proyecto_id), self.inst])

    def proyectos_bulk_v199(self, solo_activos: bool) -> pd.DataFrame:
        filtro = "AND COALESCE(pr.estado, 'Activo')='Activo'" if solo_activos else ""
        return self.read_raw(PROYECTOS_BULK_V199_SQL.replace("{filtro}", filtro), [self.inst, self.inst])

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


__all__ = ["ExtensionRepository"]
