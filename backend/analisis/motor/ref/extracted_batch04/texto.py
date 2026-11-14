# Batch 04: pure R0 helpers extracted verbatim from certified B03 (normalizacion generica de texto/valores de tabla).
from __future__ import annotations


import pandas as pd


def _normalizar_valor_plan(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return str(valor).strip()


def safe_index(options, value, default=0):
    try:
        return options.index(value)
    except Exception:
        return default


def normalizar_clave(valor):
    """Normaliza textos para comparar duplicados sin depender de mayúsculas/espacios."""
    if valor is None or pd.isna(valor):
        return ""
    return " ".join(str(valor).strip().upper().split())


def _valor_limpio_materia(valor):
    """Limpia valores de materias para filtros y búsquedas."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    txt = str(valor).strip()
    return "" if txt.lower() in ["nan", "none", "nat"] else txt


def limpiar_texto_tabla(valor):
    if valor is None or pd.isna(valor):
        return ""
    txt = str(valor).strip()
    if txt.lower() in ["nan", "none", "nat"]:
        return ""
    return txt


def _valor_proyecto_v101(valor, vacio="—"):
    try:
        if valor is None or pd.isna(valor):
            return vacio
    except Exception:
        pass
    txt = str(valor).strip()
    return txt if txt else vacio
