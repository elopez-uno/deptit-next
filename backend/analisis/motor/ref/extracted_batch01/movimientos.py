# Batch 01 pure helpers extracted verbatim from frozen 8AS.
from __future__ import annotations

def _categoria_respaldo_movimiento_v263(tipo_movimiento):
    t = str(tipo_movimiento or "").strip()
    if t == "Cambio de cargo":
        return "Cambio de cargo"
    if t in {"Aumento de dedicación", "Disminución de dedicación"}:
        return "Cambio de dedicación"
    if t in {"Pase a Ad Honorem", "Pase a Rentado", "Cambio de condición Ad Honorem"}:
        return "Cambio de condición Ad Honorem / Rentada"
    return "Designación docente"


def _movimiento_es_estado_inicial(row):
    tipo = str(row.get("tipo_movimiento", "") or "").lower()
    detalle = str(row.get("detalle", "") or "").lower()
    texto = f"{tipo} {detalle}"
    return (
        "renovación" in texto
        or "renovacion" in texto
        or "carga inicial" in texto
        or "estado inicial" in texto
    )


def balance_horas_movimiento_docente(df_movimientos_analisis):
    if df_movimientos_analisis is None or df_movimientos_analisis.empty:
        return {
            "horas_altas": 0.0,
            "horas_bajas": 0.0,
            "horas_aumentos": 0.0,
            "horas_disminuciones": 0.0,
            "saldo_neto": 0.0,
        }

    df = df_movimientos_analisis.copy()
    cat = df["categoria_movimiento"].fillna("").astype(str)

    horas_altas = float(df.loc[cat == "Altas de designaciones", "variacion_horas"].sum())
    horas_bajas = float(df.loc[cat == "Bajas de designaciones", "variacion_horas"].sum())
    horas_aumentos = float(df.loc[cat == "Aumentos de dedicación", "variacion_horas"].sum())
    horas_disminuciones = float(df.loc[cat == "Disminuciones de dedicación", "variacion_horas"].sum())
    saldo_neto = horas_altas + horas_bajas + horas_aumentos + horas_disminuciones

    return {
        "horas_altas": round(horas_altas, 2),
        "horas_bajas": round(horas_bajas, 2),
        "horas_aumentos": round(horas_aumentos, 2),
        "horas_disminuciones": round(horas_disminuciones, 2),
        "saldo_neto": round(saldo_neto, 2),
    }
