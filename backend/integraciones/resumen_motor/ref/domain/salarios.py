# B05: extracted verbatim from certified B04 (parametros salariales: posgrado, antiguedad, moneda).
from __future__ import annotations

import pandas as pd

from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def _nivel_posgrado_salarial_normalizado_v256(valor):
    txt = normalizar_clave(valor or "")
    if txt in {"doctor", "doctora", "doctorado"}:
        return "Doctor"
    if txt in {"magister", "maestria", "master"}:
        return "Magíster"
    if txt in {"especialista", "especializacion"}:
        return "Especialista"
    return ""


def _antiguedad_entera_v256(valor):
    try:
        if valor is None or pd.isna(valor):
            return 0
    except Exception:
        if valor is None:
            return 0
    try:
        return max(0, int(float(valor)))
    except Exception:
        return 0


def porcentaje_antiguedad_v256(anios):
    """Porcentaje adicional por antigüedad. Si no se informa, 0 años => 20%."""
    a = _antiguedad_entera_v256(anios)
    if a <= 4:
        return 0.20
    if a <= 6:
        return 0.30
    if a <= 9:
        return 0.40
    if a <= 11:
        return 0.50
    if a <= 14:
        return 0.60
    if a <= 16:
        return 0.70
    if a <= 19:
        return 0.80
    if a <= 21:
        return 1.00
    if a <= 23:
        return 1.10
    return 1.20


def _moneda_v256(valor):
    try:
        numero = float(valor or 0)
    except Exception:
        numero = 0.0
    txt = f"{numero:,.2f}"
    return "$ " + txt.replace(",", "X").replace(".", ",").replace("X", ".")
