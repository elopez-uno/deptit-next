# B05: extracted verbatim from certified B04 (normalizacion de valores (si/no, listas canonicas, vacios, firmas de fila)).
from __future__ import annotations

import pandas as pd

from analisis.motor.ref.extracted_batch04.texto import _normalizar_valor_plan
from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla
from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def _normalizar_clave_comparacion(valor):
    return normalizar_clave(_normalizar_valor_plan(valor))


def _valor_canonico_lista(valor, opciones, default=""):
    txt = limpiar_texto_tabla(valor)
    if not txt:
        return default
    mapa = {normalizar_clave(op): op for op in opciones}
    return mapa.get(normalizar_clave(txt), "")


def _normalizar_ad_honorem_integral(valor):
    clave = normalizar_clave(valor)
    if clave in ["SI", "SÍ", "TRUE", "1", "AD HONOREM"]:
        return "Sí"
    if clave in ["NO", "FALSE", "0", "RENTADO", "NO AD HONOREM"]:
        return "No"
    return ""


def _normalizar_si_no_cobertura_v153(valor):
    """Normaliza el selector de cobertura docente del Excel integral."""
    txt = limpiar_texto_tabla(valor)
    if not txt:
        return ""
    clave = normalizar_clave(txt)
    if clave in {"SI", "SÍ", "S", "YES", "Y", "1", "TRUE", "VERDADERO"}:
        return "Sí"
    if clave in {"NO", "N", "0", "FALSE", "FALSO"}:
        return "No"
    return txt


def _es_vacio_v168(valor):
    if valor is None:
        return True
    try:
        if pd.isna(valor):
            return True
    except Exception:
        pass
    return str(valor).strip() == ""


def _firma_fila_v168(row, columnas_clave):
    firma = []
    for col in columnas_clave:
        if col not in row:
            continue
        valor = row.get(col)
        if isinstance(valor, float):
            valor = round(valor, 8)
        if isinstance(valor, str):
            valor = valor.strip()
        firma.append((col, valor))
    return tuple(firma)
