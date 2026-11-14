# B05: extracted verbatim from certified B04 (categorias de invalidacion de cache por motivo de mutacion).
from __future__ import annotations

from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def _categorias_mutacion_v200(motivo):
    m = normalizar_clave(str(motivo or "")).lower()
    cats = set()

    # Primero las familias específicas para evitar que "docente" dentro del
    # nombre de una asignación de proyecto invalide innecesariamente toda la base.
    if "investig" in m:
        cats |= {"investigacion"}
    if "extension" in m:
        cats |= {"extension"}
    if "actividad" in m:
        cats |= {"actividades"}
    if "movimiento" in m:
        cats |= {"movimientos"}
    if "disposicion" in m or "parametros_disposicion" in m:
        cats |= {"disposiciones"}
    if "prestamo" in m:
        cats |= {"prestamos", "docentes"}

    if "inscrip" in m:
        cats |= {"inscriptos"}
    if "opcion_curricular" in m or "vinculo" in m and "opcion" in m:
        cats |= {"opciones", "materias"}
    if any(x in m for x in ("materia", "carrera", "plan_estudio", "comparticion")):
        cats |= {"materias"}
    if "sede" in m:
        cats |= {"sedes"}
    if "periodo" in m and not any(x in m for x in ("productividad", "resumen")):
        cats |= {"periodos"}

    if "horario" in m:
        cats |= {"horarios"}
    if "comision" in m:
        cats |= {"comisiones"}
    if any(x in m for x in (
        "asignacion_docente_comision", "estado_asignacion_docente_comision",
        "asignaciones_comision", "cargos_asignaciones"
    )):
        cats |= {"asignaciones", "comisiones"}

    if "designacion" in m:
        cats |= {"designaciones"}
    # Altas/ediciones de la base maestra sí afectan el catálogo docente.
    if any(x in m for x in (
        "guardar_docente", "actualizar_docente", "eliminar_docente",
        "cuil_docente", "docente_base"
    )):
        cats |= {"docentes"}

    if "no_lectiv" in m or "productividad" in m or "config_productividad" in m:
        cats |= {"config"}

    # Dependencias derivadas de reglas del sistema.
    if "designaciones" in cats:
        cats |= {"docentes"}
    if "horarios" in cats or "asignaciones" in cats:
        cats |= {"comisiones"}
    if "materias" in cats or "opciones" in cats:
        cats |= {"comisiones"}
    if "prestamos" in cats:
        cats |= {"docentes", "designaciones"}

    if not cats:
        cats.add("global")
    return cats
