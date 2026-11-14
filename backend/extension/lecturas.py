"""Lecturas certificadas de Extension (cadenas efectivas de B13-FIX02), sin cache de proceso.

Las cadenas son las de Investigacion con ``tipo="extension"`` (docs/extension_analysis.md §4):
- ``get_proyectos_extension``: v283 (piloto off) -> ``_get_proyectos_v199("extension")`` l. 45345 (bulk l. 45295).
- ``get_extension_docente``: v277 l. 47774 -> cache v191 l. 41311 -> v183 l. 39983 -> base l. 23119.
- ``buscar_asignacion_activa_docente_proyecto_extension`` v217 l. 48258; ``get_integrantes_activos_proyecto_periodo_
  extension`` v217 l. 48335.
- Padron ``_docentes_asignables_proyectos_v217(periodo, "extension")``: el MISMO padron v276/v240 (``tipo`` solo entra
  en la clave de cache) -> ``investigacion.lecturas.padron_v276`` (decision E4).
- Capacidad ``capacidad_proyectos_docente_v184(..., excluir_tipo="extension")`` y v187: ``capacidad_con_exclusion`` /
  ``validar_horas_v187`` de Investigacion (decision E5); ``detectar_excesos_proyectos_v184("extension")``: docentes con
  asignaciones LOCALES de Extension.
- ``get_documentos_proyectos_v263("extension", ...)``.
``Lecturas`` de Investigacion se reutiliza SIN MODIFICARLA: esta subclase solo cambia la rama institucional de
``get_extension_docente`` (``_proyectos_docente_todos(u, "extension")`` de Comisiones) y el tipo de los actos.
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from comisiones import proyectos as CP
from comisiones.lecturas import Lector
from investigacion import lecturas as IL
from investigacion.lecturas import (  # noqa: F401  (reutilizadas sin cambios)
    COLS_DOCS, PERIODO_REF_CTE, _ComoUnidad, capacidad_con_exclusion, enriquecer_v277, filtrar_cierre_v183,
    padron_v276, validar_horas_v187,
)

from . import rules as XR
from .repository import ExtensionRepository


class Lecturas(IL.Lecturas):
    """Lecturas de Extension sobre el repositorio de la sesion (``rol`` y departamento revalidados)."""

    def __init__(self, repo: Any, today, rol: Optional[str], clec: Optional[Lector] = None):
        super().__init__(repo, today, rol, clec)

    def _asignaciones_base(self, cuil, periodo_id, incluir_bajas, todos_departamentos) -> pd.DataFrame:
        """``get_extension_docente`` base (l. 23119)."""
        if todos_departamentos:
            return CP._proyectos_docente_todos(_ComoUnidad(self), XR.TIPO, cuil, periodo_id, incluir_bajas)
        return self.repo.asignaciones_local(cuil, int(periodo_id) if periodo_id is not None else None,
                                            bool(incluir_bajas))

    def documentos_proyectos(self, proyecto_ids) -> pd.DataFrame:
        """``get_documentos_proyectos_v263("extension", ...)`` (l. 51221)."""
        ids = []
        for x in list(proyecto_ids or []):
            try:
                i = int(x)
            except Exception:
                continue
            if i > 0 and i not in ids:
                ids.append(i)
        if not ids:
            return pd.DataFrame(columns=COLS_DOCS)
        try:
            df = self.repo.documentos_proyectos_v263(XR.TIPO, ids)
        except Exception:
            df = pd.DataFrame(columns=COLS_DOCS)
        for c in COLS_DOCS:
            if c not in df.columns:
                df[c] = ""
        return df[COLS_DOCS]


__all__ = ["Lecturas", "ExtensionRepository", "capacidad_con_exclusion", "validar_horas_v187", "padron_v276",
           "enriquecer_v277", "filtrar_cierre_v183"]
