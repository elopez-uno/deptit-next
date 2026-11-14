# Batch 04: pure R0 helpers extracted verbatim from certified B03 (conversiones numericas defensivas).
from __future__ import annotations


import pandas as pd


def _hora_numero(valor):
    try:
        if valor is None or pd.isna(valor):
            return 0.0
        if isinstance(valor, str):
            valor = valor.replace("hs", "").replace(",", ".").strip()
        return float(valor or 0)
    except Exception:
        return 0.0


def _opcion_id_inscriptos_v248(valor):
    try:
        if valor is None or pd.isna(valor):
            return 0
        n = int(valor)
        return n if n > 0 else 0
    except Exception:
        return 0


def _entero_no_negativo_v248(valor, default=0):
    """Convierte cantidades de alumnos sin dejar que NaN/None rompan la vista."""
    try:
        n = pd.to_numeric(valor, errors="coerce")
        if pd.isna(n):
            return int(default)
        return max(int(n), 0)
    except Exception:
        return int(default)


def _id_documento_valido_v266(valor):
    try:
        if pd.isna(valor):
            return False
    except Exception:
        pass
    return str(valor or "").strip() != ""
