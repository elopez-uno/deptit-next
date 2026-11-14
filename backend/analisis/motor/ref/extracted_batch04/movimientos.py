# Batch 04: pure R0 helpers extracted verbatim from certified B03 (texto de movimientos de designaciones).
from __future__ import annotations

import re

import pandas as pd
from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla


def _extraer_horas_desde_texto(texto):
    """Extrae el primer número que antecede a 'hs' dentro de un texto."""
    import re
    if texto is None or pd.isna(texto):
        return 0.0
    txt = str(texto)
    patron = re.search(r"(-?\d+(?:[\.,]\d+)?)\s*hs", txt, flags=re.IGNORECASE)
    if not patron:
        return 0.0
    try:
        return float(patron.group(1).replace(",", "."))
    except Exception:
        return 0.0


def _extraer_antes_ahora(detalle):
    """Devuelve los textos Antes/Ahora cuando el movimiento fue registrado como cambio de designación."""
    detalle_txt = str(detalle or "")
    if "Antes:" not in detalle_txt or "Ahora:" not in detalle_txt:
        return "", ""
    try:
        antes_txt = detalle_txt.split("Antes:", 1)[1].split("/ Ahora:", 1)[0].strip()
        ahora_txt = detalle_txt.split("/ Ahora:", 1)[1].strip()
        return antes_txt, ahora_txt
    except Exception:
        return "", ""


def _horas_antes_ahora(detalle):
    antes_txt, ahora_txt = _extraer_antes_ahora(detalle)
    return _extraer_horas_desde_texto(antes_txt), _extraer_horas_desde_texto(ahora_txt)


def normalizar_tipo_movimiento_dedicacion(tipo_movimiento, variacion_horas=0):
    """Corrige la dirección de un movimiento de dedicación según su variación real de horas.

    Esto también sanea la visualización de movimientos históricos mal rotulados: si un
    registro decía "Disminución" pero las horas aumentaron, en Análisis se interpreta
    como aumento. La base histórica no se reescribe automáticamente.
    """
    tipo = str(tipo_movimiento or "").strip()
    if tipo not in ["Aumento de dedicación", "Disminución de dedicación"]:
        return tipo
    try:
        variacion = float(variacion_horas or 0)
    except Exception:
        variacion = 0.0
    if variacion > 0:
        return "Aumento de dedicación"
    if variacion < 0:
        return "Disminución de dedicación"
    return tipo


def _tipo_movimiento_designacion_normalizado(valor):
    txt = limpiar_texto_tabla(valor).lower()
    txt = txt.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    return re.sub(r"\s+", " ", txt).strip()


def _texto_row_movimiento(row, columnas=None):
    partes = []
    columnas = columnas or ["detalle", "resumen", "observaciones"]
    for col in columnas:
        try:
            valor = row.get(col, "")
        except Exception:
            valor = ""
        if valor is not None and not pd.isna(valor):
            partes.append(str(valor))
    return " | ".join(partes)


def _evento_es_baja_designacion(valor):
    v = limpiar_texto_tabla(valor).lower()
    return v in {"baja de designación", "baja de designacion", "eliminación de designación", "eliminacion de designacion", "finalización de designación", "finalizacion de designacion"}
