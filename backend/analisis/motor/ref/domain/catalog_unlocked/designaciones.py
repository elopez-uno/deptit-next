# B08: extracted verbatim from certified B07 (designaciones: horas por dedicacion, jerarquia de cargos, clave integral v220 y horas v165).
# Function text copied byte-for-byte from app_postgresql_refactor_b07_catalogs.py (sha256 f422f375a973756b5a7d7f90d99db91452a09ef16976f941ea536115615e4946).
# Catalogs are the canonical B07 objects (analisis.motor.ref.catalogs); do not duplicate them here.
from __future__ import annotations

import pandas as pd

from analisis.motor.ref.catalogs.designaciones import HORAS_POR_DEDICACION
from analisis.motor.ref.catalogs.designaciones import ORDEN_JERARQUICO_CARGOS_COMISION
from analisis.motor.ref.common.dates import _fecha_iso_integral
from analisis.motor.ref.domain.designaciones import _normalizar_cargo_para_jerarquia
from analisis.motor.ref.extracted_batch04.identidad import _clave_cuil
from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def horas_segun_dedicacion(dedicacion, fallback=0):
    """Fuente única de horas contractuales según la dedicación docente."""
    txt = " ".join(str(dedicacion or "").strip().split())
    for nombre, horas in HORAS_POR_DEDICACION.items():
        if txt.casefold() == nombre.casefold():
            return int(horas)
    try:
        return int(float(fallback or 0))
    except Exception:
        return 0


def _cargo_mas_alto(cargos):
    """Selecciona el cargo de mayor jerarquía; conserva un valor desconocido solo como último recurso."""
    valores = []
    for cargo in list(cargos or []):
        canon = _normalizar_cargo_para_jerarquia(cargo)
        if canon and canon not in valores:
            valores.append(canon)
    if not valores:
        return ""
    prioridad = {cargo: i for i, cargo in enumerate(ORDEN_JERARQUICO_CARGOS_COMISION)}
    return sorted(valores, key=lambda x: (prioridad.get(x, 999), normalizar_clave(x)))[0]


def _horas_designaciones_v165(df):
    if df is None or df.empty:
        return 0.0
    total = 0.0
    for _, r in df.iterrows():
        try:
            total += float(horas_segun_dedicacion(r.get("dedicacion"), r.get("horas", 0)) or 0)
        except Exception:
            try:
                total += float(pd.to_numeric(r.get("horas"), errors="coerce") or 0)
            except Exception:
                pass
    return round(total, 2)


def _clave_designacion_integral_v220(row):
    """Identidad estable para revisión/carga integral (v223).

    Incluye período, CUIL, cargo, dedicación, horas, tipo, resolución, condición
    Ad Honorem y fechas. Deliberadamente NO incluye ``estado``: Activa/Finalizada
    es el ciclo de vida de la misma designación y, además, los períodos cerrados
    pueden mostrarse como Finalizada aunque la fila histórica se haya almacenado
    como Activa.
    """
    try:
        periodo_id = int(row.get("_periodo_id") if hasattr(row, "get") else row["_periodo_id"])
    except Exception:
        try:
            periodo_id = int(row.get("periodo_id"))
        except Exception:
            periodo_id = None
    return (
        periodo_id,
        _clave_cuil(row.get("_cuil_guardado", "") or row.get("cuil", "")),
        normalizar_clave(row.get("cargo", "")),
        normalizar_clave(row.get("dedicacion", "")),
        horas_segun_dedicacion(row.get("dedicacion", ""), row.get("horas", 0)),
        normalizar_clave(row.get("tipo_designacion", "")),
        normalizar_clave(row.get("numero_resolucion", "")),
        normalizar_clave(row.get("ad_honorem", "")),
        _fecha_iso_integral(row.get("fecha_desde", "")),
        _fecha_iso_integral(row.get("fecha_hasta", "")),
    )
