"""Reglas puras de Extension (B13-FIX02).  Sin SQL ni estado.

Las funciones puras certificadas son las mismas que usa Investigacion (fechas, situacion, vigencia, radicacion v216,
``_puede_administrar_proyecto_extension`` l. 22308 = ``_puede_administrar_proyecto_investigacion``, presentacion,
actos, Excel v127/v217): se importan SIN MODIFICAR de ``investigacion.rules`` (decision E9).  Aqui solo vive lo que
cambia en Extension (docs/extension_analysis.md §2.2):
- ``_ayuda_radicacion_proyecto_v216("extension")`` (l. 7012): unidad "Instituto/Departamento/Área/Secretaría" (B8);
- horas > 0 en la pantalla y en el Excel v217 (B1-B3), con 1 hora por defecto al asignar (l. 48667);
- los textos de movimientos (B5) y el tipo ``extension`` de ``documentos_respaldo_proyectos``.
"""

from __future__ import annotations

from investigacion.rules import *  # noqa: F401,F403  (funciones puras identicas, sin modificar)
from investigacion.rules import departamento_operativo_nombre

TIPO = "extension"
HORAS_DEFECTO_ASIGNAR = 1.0  # l. 48667: ``horas_default_v270 = 1.0 if es_ext else 0.0``

MOV_ASIGNACION = "Asignación a extensión"
MOV_MODIFICACION = "Modificación de extensión"
ACCION_ALERTA_MODIFICACION = "Modificación de Extensión"  # l. 66178 (memoria de sesion v187)


def ayuda_radicacion_v216(departamento_nombre) -> str:
    """``_ayuda_radicacion_proyecto_v216("extension")`` (l. 7012)."""
    unidad = "Instituto/Departamento/Área/Secretaría"
    departamento_actual = departamento_operativo_nombre(departamento_nombre)
    detalle_actual = f" ({departamento_actual})" if str(departamento_actual or "").strip() else ""
    return (
        f"Dejá este campo vacío si el proyecto radica en el mismo departamento que lo crea{detalle_actual}: "
        "el sistema ya registra automáticamente al departamento creador. "
        f"Completalo únicamente si la radicación corresponde a otro {unidad}."
    )
