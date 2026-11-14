# B05: extracted verbatim from certified B04 (horas de reloj, intervalos y franjas).
from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd

from analisis.motor.ref.extracted_batch04.horarios import _hora_texto_v95
from analisis.motor.ref.extracted_batch04.horarios import _minutos_v95
from analisis.motor.ref.extracted_batch04.horarios import _normalizar_dia_v95
from analisis.motor.ref.extracted_batch04.horarios import hora_a_minutos
from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla


def calcular_horas_desde_texto(hora_inicio, hora_fin):
    try:
        hi = datetime.strptime(str(hora_inicio), "%H:%M")
        hf = datetime.strptime(str(hora_fin), "%H:%M")
        delta = (hf - hi).total_seconds() / 3600
        if delta < 0:
            delta += 24
        return round(delta, 2)
    except Exception:
        return 0


def normalizar_hora_excel(valor):
    """
    Convierte horas pegadas desde Excel a HH:MM.
    Acepta ejemplos como:
    - 05:00:00 p. m.
    - 08:00:00 a. m.
    - 17:00
    - 5:00 PM
    """
    txt = limpiar_texto_tabla(valor)
    if not txt:
        return ""

    txt = txt.lower().strip()
    txt = txt.replace("\u00a0", " ")
    txt = txt.replace("a. m.", "am").replace("p. m.", "pm")
    txt = txt.replace("a.m.", "am").replace("p.m.", "pm")
    txt = txt.replace("a. m", "am").replace("p. m", "pm")
    txt = txt.replace("a m", "am").replace("p m", "pm")
    txt = " ".join(txt.split())

    formatos = ["%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p", "%I:%M:%S%p", "%I:%M%p"]
    for fmt in formatos:
        try:
            return datetime.strptime(txt.upper(), fmt).strftime("%H:%M")
        except Exception:
            pass

    # Reparación manual para casos como "05:00:00 pm" o "05:00 pm".
    try:
        es_pm = txt.endswith("pm")
        es_am = txt.endswith("am")
        limpio = txt.replace("pm", "").replace("am", "").strip()
        partes = limpio.split(":")
        hora = int(partes[0])
        minuto = int(partes[1]) if len(partes) > 1 else 0
        if es_pm and hora != 12:
            hora += 12
        if es_am and hora == 12:
            hora = 0
        if 0 <= hora <= 23 and 0 <= minuto <= 59:
            return f"{hora:02d}:{minuto:02d}"
    except Exception:
        return ""

    return ""


def intervalos_solapan(inicio_a, fin_a, inicio_b, fin_b):
    ia = hora_a_minutos(inicio_a)
    fa = hora_a_minutos(fin_a)
    ib = hora_a_minutos(inicio_b)
    fb = hora_a_minutos(fin_b)
    if None in [ia, fa, ib, fb]:
        return False
    if fa <= ia:
        fa += 24 * 60
    if fb <= ib:
        fb += 24 * 60
    return max(ia, ib) < min(fa, fb)


def _calcular_horas_unicas_desde_horarios_df(df_horarios):
    """Suma la unión de franjas horarias por día, evitando contar doble lo superpuesto."""
    if df_horarios is None or df_horarios.empty:
        return 0.0
    total_minutos = 0
    for dia, grupo in df_horarios.groupby("dia", dropna=False):
        intervalos = []
        for _, row in grupo.iterrows():
            ini = hora_a_minutos(row.get("hora_inicio"))
            fin = hora_a_minutos(row.get("hora_fin"))
            if ini is None or fin is None:
                continue
            if fin <= ini:
                fin += 24 * 60
            intervalos.append((ini, fin))
        if not intervalos:
            continue
        intervalos.sort()
        unidos = []
        for ini, fin in intervalos:
            if not unidos or ini > unidos[-1][1]:
                unidos.append([ini, fin])
            else:
                unidos[-1][1] = max(unidos[-1][1], fin)
        total_minutos += sum(fin - ini for ini, fin in unidos)
    return round(total_minutos / 60, 2)


def _hora_time_v95(valor, default_h=8, default_m=0):
    from datetime import time as _time
    txt = _hora_texto_v95(valor)
    try:
        h, m = [int(x) for x in txt.split(":")[:2]]
        return _time(h, m)
    except Exception:
        return _time(default_h, default_m)


def _horas_intervalo_v95(inicio, fin):
    a, b = _minutos_v95(inicio), _minutos_v95(fin)
    if a is None or b is None or b <= a:
        return 0.0
    return round((b - a) / 60.0, 2)


def _es_subintervalo_v95(dia, inicio, fin, horarios_comision):
    d = _normalizar_dia_v95(dia)
    a, b = _minutos_v95(inicio), _minutos_v95(fin)
    if a is None or b is None or b <= a:
        return False
    if horarios_comision is None or len(horarios_comision) == 0:
        return False
    for _, r in horarios_comision.iterrows():
        if _normalizar_dia_v95(r.get("dia")) != d:
            continue
        ca, cb = _minutos_v95(r.get("hora_inicio")), _minutos_v95(r.get("hora_fin"))
        if ca is not None and cb is not None and ca <= a < b <= cb:
            return True
    return False


def _normalizar_hora_export_v175(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    txt = str(valor).strip()
    if not txt:
        return ""
    m = re.match(r"^(\d{1,2}):(\d{2})", txt)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
    return txt
