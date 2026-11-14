# B05: extracted verbatim from certified B04 (informes de productividad y tablas de conteo).
from __future__ import annotations

import pandas as pd


def tabla_conteo_porcentajes(df, columna):
    if df is None or df.empty or columna not in df.columns:
        return pd.DataFrame(columns=[columna, "cantidad", "porcentaje"])
    base = df[columna].fillna("Sin dato").replace("", "Sin dato")
    out = base.value_counts().reset_index()
    out.columns = [columna, "cantidad"]
    total = out["cantidad"].sum()
    out["porcentaje"] = out["cantidad"].apply(lambda x: round(x / total * 100, 2) if total else 0)
    return out


def _redondear_numericos_productividad_v150(df):
    """Evita decimales binarios largos y limita los datos numéricos a 2 decimales."""
    if df is None or not isinstance(df, pd.DataFrame):
        return df
    out = df.copy()
    columnas_numericas = [
        "porcentaje_uso", "horas_contratadas", "horas_comisiones_brutas",
        "horas_comisiones_reales", "horas_no_contadas_por_superposicion",
        "porcentaje_no_lectivas", "horas_no_lectivas", "horas_investigacion",
        "horas_extension", "horas_utilizadas", "horas_disponibles",
    ]
    for col in columnas_numericas:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(2)
    return out


def _color_productividad_word_v178(valor):
    """Mismos cortes visuales de _estilo_productividad_v148."""
    try:
        v = float(valor)
    except Exception:
        v = 0.0
    if v < 40:
        return "B91C1C", "FFFFFF"   # rojo
    if v <= 60:
        return "FACC15", "111827"   # amarillo
    if v <= 100:
        return "15803D", "FFFFFF"   # verde
    return "2563EB", "FFFFFF"       # azul
