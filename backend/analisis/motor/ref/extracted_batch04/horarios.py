# Batch 04: pure R0 helpers extracted verbatim from certified B03 (horas de reloj y dias).
from __future__ import annotations

import re

import pandas as pd
from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def hora_a_minutos(hora):
    try:
        if hora is None or pd.isna(hora) or str(hora).strip() == "":
            return None
        partes = str(hora).strip().split(":")
        return int(partes[0]) * 60 + int(partes[1])
    except Exception:
        return None


def _hora_texto_v95(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    if hasattr(valor, "strftime"):
        try:
            return valor.strftime("%H:%M")
        except Exception:
            pass
    txt = str(valor).strip()
    m = re.match(r"^(\d{1,2}):(\d{2})", txt)
    return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}" if m else txt


def _minutos_v95(valor):
    txt = _hora_texto_v95(valor)
    try:
        h, m = [int(x) for x in txt.split(":")[:2]]
        return h * 60 + m
    except Exception:
        return None


def _normalizar_dia_v95(dia):
    txt = normalizar_clave(dia)
    mapa = {
        "lunes": "Lunes", "martes": "Martes", "miercoles": "Miércoles",
        "jueves": "Jueves", "viernes": "Viernes", "sabado": "Sábado", "domingo": "Domingo",
    }
    return mapa.get(txt, str(dia or "").strip())
