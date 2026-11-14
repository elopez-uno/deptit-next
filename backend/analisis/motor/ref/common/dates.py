# B05: extracted verbatim from certified B04 (fechas: parseo, ISO, formatos administrativos).
from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd

from analisis.motor.ref.extracted_batch04.fechas import safe_date
from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla


def formatear_fecha_larga(valor):
    """Convierte fechas ISO/dd-mm-yyyy a formato administrativo: 04 de abril de 2029.

    Las fechas ISO se parsean de forma explícita para evitar que 2027-08-01 se
    interprete erróneamente como 8 de enero por usar dayfirst=True.
    """
    if valor is None or pd.isna(valor) or str(valor).strip() == "":
        return ""
    txt = str(valor).strip()
    meses = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
        7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", txt):
            dt = pd.to_datetime(txt, format="%Y-%m-%d", errors="coerce")
        elif re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", txt):
            dt = pd.to_datetime(txt, dayfirst=True, errors="coerce")
        else:
            dt = pd.to_datetime(txt, dayfirst=True, errors="coerce")
        if pd.isna(dt):
            return txt
        return f"{dt.day:02d} de {meses[int(dt.month)]} de {int(dt.year)}"
    except Exception:
        return txt


def normalizar_fecha_texto(valor, fallback=""):
    txt = limpiar_texto_tabla(valor)
    if not txt:
        return fallback
    try:
        return str(pd.to_datetime(txt, dayfirst=True).date())
    except Exception:
        return txt


def _fecha_iso_integral(valor, fallback=""):
    candidato = valor
    if candidato is None or (isinstance(candidato, float) and pd.isna(candidato)):
        candidato = fallback
    if candidato is None:
        return ""
    try:
        if isinstance(candidato, (date, datetime, pd.Timestamp)):
            return str(pd.Timestamp(candidato).date())
    except Exception:
        pass
    txt = limpiar_texto_tabla(candidato)
    if not txt:
        txt = limpiar_texto_tabla(fallback)
    if not txt:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T].*)?", txt):
        try:
            return str(pd.to_datetime(txt[:10], format="%Y-%m-%d").date())
        except Exception:
            return ""
    try:
        return str(pd.to_datetime(txt, dayfirst=True).date())
    except Exception:
        return ""


def _etiqueta_mes_v256(mes_ref):
    try:
        anio, mes = str(mes_ref).split("-")[:2]
        return f"{int(mes):02d}/{int(anio):04d}"
    except Exception:
        return str(mes_ref or "")


def _fecha_iso_correccion_directa_v171(valor):
    """Normaliza una fecha editada en la grilla a YYYY-MM-DD."""
    try:
        if valor is None or pd.isna(valor):
            return ""
    except Exception:
        if valor is None:
            return ""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    fecha = safe_date(valor, None)
    return fecha.isoformat() if fecha is not None else ""


def _inicio_fecha_segura(valor):
    try:
        if valor is None or pd.isna(valor) or str(valor).strip() == "":
            return None
        ts = pd.to_datetime(valor, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.date()
    except Exception:
        return None


def _fecha_iso_observacion_v183(texto, patrones=None):
    """Extrae una fecha efectiva ISO de observaciones operativas cuando existe."""
    s = str(texto or "")
    patrones = patrones or [
        r"Baja por modificación de asignación\.\s*Fecha efectiva:\s*(\d{4}-\d{2}-\d{2})",
        r"Préstamo finalizado el\s*(\d{4}-\d{2}-\d{2})",
        r"Fecha efectiva:\s*(\d{4}-\d{2}-\d{2})",
    ]
    for pat in patrones:
        m = re.search(pat, s, flags=re.I)
        if m:
            return safe_date(m.group(1), None)
    return None
