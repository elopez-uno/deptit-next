"""SQL de Movimientos sobre una conexion/transaccion ya abierta.  Nunca crea ni altera tablas y nunca confirma.

Cada sentencia es la del entry certificado con el ambito que le aplica la conexion certificada que la ejecuta
(``get_conn()`` + inyector B12B v193 re-enlazado por B12J; ``docs/audit/movimientos_phase_a/inject_sql_movimientos.txt``):
- ``get_movimientos`` l. 4824: ``institucion_id`` + ``departamento_id`` de ``movimientos`` en el WHERE y de ``periodos``
  en el ``ON`` del ``LEFT JOIN``; mismo orden de negocio (CASE por tipo).  Solo las columnas certificadas: nunca
  ``source_db`` ni las demas columnas legacy (D-AL10).
- ``eliminar_movimiento`` l. 9566: los 2 DELETE (vinculo exacto con el acto + movimiento) con el ambito en el WHERE.
El resto (periodos, mapa de actos ``_mapa_actos_movimientos_v266``, repositorio documental, vinculos v267) se hereda sin
cambios del repositorio de Designaciones.  Sin DDL (``add_column_if_not_exists`` / ``asegurar_esquema_*`` excluidos).
"""

from __future__ import annotations

from typing import Optional

from designaciones.repository import DesignacionesRepository

_SELECT = """
    SELECT
        m.id,
        m.periodo_id,
        p.nombre AS periodo,
        m.fecha,
        m.tipo_movimiento,
        m.cuil,
        m.nombre,
        m.detalle,
        m.observaciones,
        COALESCE(m.horas_variacion, 0) AS horas_variacion
    FROM movimientos m
    LEFT JOIN periodos p ON (m.periodo_id = p.id) AND (p.institucion_id = %s) AND (p.departamento_id = %s)
"""
_ORDEN = """
    ORDER BY
        COALESCE(p.anio, 0) DESC,
        COALESCE(p.semestre, 0) DESC,
        m.fecha DESC,
        CASE
            WHEN m.tipo_movimiento = 'Renovación automática de designación' THEN 1
            WHEN m.tipo_movimiento = 'Alta de designación' THEN 2
            WHEN m.tipo_movimiento = 'Aumento de dedicación' THEN 3
            WHEN m.tipo_movimiento = 'Disminución de dedicación' THEN 4
            WHEN m.tipo_movimiento = 'Cambio de cargo' THEN 5
            WHEN m.tipo_movimiento = 'Baja de designación' THEN 8
            WHEN m.tipo_movimiento = 'Finalización automática por cierre de período' THEN 9
            ELSE 6
        END ASC,
        m.id DESC
"""
MOVIMIENTOS_SQL = _SELECT + "    WHERE (m.institucion_id = %s) AND (m.departamento_id = %s)" + _ORDEN
MOVIMIENTOS_PERIODO_SQL = (_SELECT + "    WHERE m.periodo_id = %s AND (m.institucion_id = %s) AND "
                           "(m.departamento_id = %s)" + _ORDEN)
# Relectura fresca de filas puntuales (D-AL4 / D-AL13 / capa U): mismo SELECT, mismo ambito.
MOVIMIENTOS_IDS_SQL = (_SELECT + "    WHERE m.id = ANY(%s) AND (m.institucion_id = %s) AND (m.departamento_id = %s)"
                       + _ORDEN)

ELIMINAR_VINCULO_SQL = ("DELETE FROM documentos_respaldo_movimientos WHERE movimiento_id = %s AND "
                        "(documentos_respaldo_movimientos.institucion_id = %s) AND "
                        "(documentos_respaldo_movimientos.departamento_id = %s)")
ELIMINAR_SQL = ("DELETE FROM movimientos WHERE id = %s AND (movimientos.institucion_id = %s) AND "
                "(movimientos.departamento_id = %s)")

COLUMNAS = ["id", "periodo_id", "periodo", "fecha", "tipo_movimiento", "cuil", "nombre", "detalle", "observaciones",
            "horas_variacion"]


class MovimientosRepository(DesignacionesRepository):
    """Repositorio de la operacion; hereda periodos, mapa de actos, documentos y vinculos de Designaciones."""

    def movimientos(self, periodo_id: Optional[int]) -> list[dict]:
        if periodo_id is None:
            return self._all(MOVIMIENTOS_SQL, self._scope + self._scope)
        return self._all(MOVIMIENTOS_PERIODO_SQL, self._scope + [int(periodo_id)] + self._scope)

    def movimientos_ids(self, ids: list[int]) -> list[dict]:
        return self._all(MOVIMIENTOS_IDS_SQL, self._scope + [list(ids)] + self._scope)

    def eliminar_movimiento(self, id_movimiento: int) -> int:
        """``eliminar_movimiento`` l. 9566: primero el vinculo exacto (v266), luego el movimiento; mismo COMMIT."""
        self._mutate(ELIMINAR_VINCULO_SQL, [int(id_movimiento)] + self._scope)
        return self._mutate(ELIMINAR_SQL, [int(id_movimiento)] + self._scope)
