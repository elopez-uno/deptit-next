"""Reglas puras de Actividades Especiales (B13-FIX02, entry l. 32099-32160 y pagina l. 66418-66603).  Sin SQL.

Las auxiliares certificadas ya portadas se importan sin modificar: ``limpiar_texto_tabla`` (Comisiones),
``nombre_completo`` / ``safe_index`` (Docentes).  Una Actividad Especial es administrativa: no tiene horas, fechas
Desde/Hasta, categorias, costos ni movimientos (docs/actividades_especiales_analysis.md §3.1).
"""

from __future__ import annotations

from typing import Any

from comisiones.rules import limpiar_texto_tabla
from docentes.rules import nombre_completo, safe_index

ESTADOS = ["Activa", "Finalizada", "Suspendida"]  # l. 66564


def normalizar_espacios(valor: Any) -> str:
    """``" ".join(str(x or "").split())`` (titulo y rol en los writers l. 32100 / 32116)."""
    return " ".join(str(valor or "").split())


def estado_mostrado(valor: Any) -> str:
    """``safe_index(["Activa","Finalizada","Suspendida"], estado)``: un valor fuera de la lista se muestra como Activa."""
    return ESTADOS[safe_index(ESTADOS, str(valor or "Activa"))]


def etiqueta_docente(r: dict) -> str:
    """Opcion del multiselect "Docentes participantes" (l. 66503-66504)."""
    nom = (limpiar_texto_tabla(r.get("nombre_completo")) or nombre_completo(r.get("apellido", ""), r.get("nombres", ""))
           or limpiar_texto_tabla(r.get("nombre")) or limpiar_texto_tabla(r.get("cuil")))
    return f"{nom} - {r.get('cuil', '')}"


__all__ = ["ESTADOS", "normalizar_espacios", "estado_mostrado", "etiqueta_docente", "limpiar_texto_tabla"]
