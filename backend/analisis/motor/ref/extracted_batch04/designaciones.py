# Batch 04: pure R0 helpers extracted verbatim from certified B03 (flags de designaciones).
from __future__ import annotations


import pandas as pd


def _flag_si_v162(valor):
    if isinstance(valor, bool):
        return valor
    try:
        if valor is not None and not pd.isna(valor) and float(valor) == 1:
            return True
    except Exception:
        pass
    return str(valor or "").strip().casefold() in {"1", "sí", "si", "true", "verdadero", "yes"}


def _es_funcion_no_docente_v162(valor):
    return _flag_si_v162(valor)
