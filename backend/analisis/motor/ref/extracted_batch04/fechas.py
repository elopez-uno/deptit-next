# Batch 04: pure R0 helpers extracted verbatim from certified B03 (fechas y periodos).
from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd


def _date_to_iso(valor):
    if valor is None or valor == "":
        return None
    try:
        if isinstance(valor, datetime):
            return valor.date().isoformat()
        if isinstance(valor, date):
            return valor.isoformat()
        return str(valor)[:10]
    except Exception:
        return None


def safe_date(value, fallback):
    try:
        if value is None or value == "" or pd.isna(value):
            return fallback
        return pd.to_datetime(value).date()
    except Exception:
        return fallback


def fechas_periodo(anio, semestre):
    anio = int(anio)
    semestre = int(semestre)
    if semestre == 1:
        return f"{anio}-01-01", f"{anio}-07-31"
    return f"{anio}-08-01", f"{anio}-12-31"


def _fecha_proyecto(valor):
    """Convierte fechas ISO o argentinas sin intercambiar día y mes."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or not str(valor).strip():
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    try:
        if re.match(r"^(?:19|20)\d{2}-\d{1,2}-\d{1,2}", texto):
            convertido = pd.to_datetime(texto, yearfirst=True, errors="coerce")
        else:
            convertido = pd.to_datetime(texto, dayfirst=True, errors="coerce")
        if pd.isna(convertido):
            return None
        return convertido.date()
    except Exception:
        return None


def _fecha_a_timestamp_seguro(valor):
    try:
        if valor is None or pd.isna(valor):
            return pd.NaT
        txt = str(valor).strip()
        if not txt:
            return pd.NaT
        return pd.to_datetime(txt, errors="coerce", dayfirst=False)
    except Exception:
        return pd.NaT
