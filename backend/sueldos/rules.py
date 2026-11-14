"""Reglas puras de Sueldos (B13-FIX02 v256/v257/v258, entry l. 25440-25993).  Sin SQL.

Copia literal de la aritmetica certificada (``float`` + ``round`` en los mismos pasos, decision H8):
- catalogos: ``deptit_refactor/catalogs/salarios.py`` (B07) y ``catalogs/designaciones.py`` (``CARGOS``,
  ``HORAS_POR_DEDICACION``, por import de Designaciones), ``BASICOS_JUNIO_2026_V256`` (entry l. 25444; solo valor
  inicial del formulario, H4: la tabla nunca se siembra);
- ``domain/salarios.py`` (antiguedad, porcentaje, moneda), ``common/dates.py`` (``_etiqueta_mes_v256``);
- normalizador de posgrado EFECTIVO: el de B12A (re-enlazado en el entry l. 59081), por import de Docentes;
- ``_es_ad_honorem_v162`` / ``_estado_designacion_visible_v162`` (extracted_batch01/designaciones.py).
Busqueda de cargo por texto EXACTO (sin match -> basico 0, sin aviso); dedicacion desconocida -> x1.0.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

import pandas as pd

from designaciones.rules import CARGOS, DEDICACIONES, HORAS_POR_DEDICACION  # noqa: F401  (catalogos B07)
from docentes.rules import clave_cuil, safe_date  # noqa: F401
from docentes.rules import nivel_posgrado_salarial_normalizado as nivel_posgrado_v256  # B12A efectivo

# --- catalogos (catalogs/salarios.py; entry l. 25441-25451) -------------------------------------------------------
NIVELES_POSGRADO_SALARIAL_V256 = ["", "Especialista", "Magíster", "Doctor"]
ADICIONAL_POSGRADO_V256 = {"": 0.0, "Especialista": 0.05, "Magíster": 0.08, "Doctor": 0.18}
MULTIPLICADOR_DEDICACION_V256 = {
    "Simple": 1.0,
    "Parcial": 2.0,
    "Semiexclusiva": 2.0,
    "Parcial + Simple": 3.0,
    "Exclusiva": 4.0,
    "Exclusiva + Simple": 5.0,
}
BASICOS_JUNIO_2026_V256 = {
    "Titular": 487144.77,
    "Asociado": 433482.17,
    "Adjunto": 380014.62,
    "JTP": 326359.56,
    "Ayudante 1ra": 272645.27,
    "Ayudante 2da": 218119.71,
}

# --- pagina (l. 61762-61931) ---------------------------------------------------------------------------------------
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
         "Noviembre", "Diciembre"]
DEDICACIONES_TABLA = ["Simple", "Parcial", "Parcial + Simple", "Exclusiva", "Exclusiva + Simple"]
RANGOS_TABLA = [("0–4", 0), ("5–6", 5), ("7–9", 7), ("10–11", 10), ("12–14", 12), ("15–16", 15), ("17–19", 17),
                ("20–21", 20), ("22–23", 22), ("24+", 24)]
MES_REGEX = re.compile(r"\d{4}-\d{2}")


# --- domain/salarios.py (B05) --------------------------------------------------------------------------------------
def antiguedad_entera_v256(valor) -> int:
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


def porcentaje_antiguedad_v256(anios) -> float:
    """Porcentaje adicional por antiguedad. Si no se informa, 0 anios => 20%."""
    a = antiguedad_entera_v256(anios)
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


def moneda_v256(valor) -> str:
    try:
        numero = float(valor or 0)
    except Exception:
        numero = 0.0
    txt = f"{numero:,.2f}"
    return "$ " + txt.replace(",", "X").replace(".", ",").replace("X", ".")


def etiqueta_mes_v256(mes_ref) -> str:
    """``common/dates.py::_etiqueta_mes_v256``: ``AAAA-MM`` -> ``MM/AAAA``."""
    try:
        anio, mes = str(mes_ref).split("-")[:2]
        return f"{int(mes):02d}/{int(anio):04d}"
    except Exception:
        return str(mes_ref or "")


# --- entry l. 25464-25486 ------------------------------------------------------------------------------------------
def porcentaje_posgrado_v256(nivel) -> float:
    return float(ADICIONAL_POSGRADO_V256.get(nivel_posgrado_v256(nivel), 0.0))


def multiplicador_dedicacion_v256(dedicacion) -> float:
    txt = " ".join(str(dedicacion or "").strip().split())
    for nombre, mult in MULTIPLICADOR_DEDICACION_V256.items():
        if txt.casefold() == nombre.casefold():
            return float(mult)
    return 1.0


def mes_ref_v256(valor, hoy: date) -> str:
    """``_mes_ref_v256`` (l. 25481); ``hoy`` = ``date.today()`` del certificado (reloj inyectable, H7)."""
    d = safe_date(valor, None) if valor is not None else None
    if d is None:
        d = hoy
    return f"{int(d.year):04d}-{int(d.month):02d}"


def es_ad_honorem_v162(valor) -> bool:
    return str(valor or "").strip().casefold() in {"sí", "si", "1", "true", "verdadero", "yes"}


def estado_designacion_visible_v162(valor) -> str:
    txt = str(valor or "").strip()
    return "Suspendida (licenciada)" if txt.casefold() == "suspendida" else txt


# --- motor (l. 25688) ----------------------------------------------------------------------------------------------
def calcular_sueldo_designacion_v256(cargo, dedicacion, ad_honorem, antiguedad_anios, nivel_posgrado, escala) -> dict:
    base_simple = float((escala or {}).get(str(cargo or ""), 0) or 0)
    mult = multiplicador_dedicacion_v256(dedicacion)
    basico_dedicacion = round(base_simple * mult, 2)
    pct_ant = porcentaje_antiguedad_v256(antiguedad_anios)
    pct_pos = porcentaje_posgrado_v256(nivel_posgrado)
    es_adh = es_ad_honorem_v162(ad_honorem)
    adicional_ant = round(basico_dedicacion * pct_ant, 2)
    adicional_pos = round(basico_dedicacion * pct_pos, 2)
    total = 0.0 if es_adh else round(basico_dedicacion + adicional_ant + adicional_pos, 2)
    return {
        "basico_simple": round(base_simple, 2),
        "multiplicador": mult,
        "basico_dedicacion": basico_dedicacion,
        "porcentaje_antiguedad": pct_ant,
        "adicional_antiguedad": adicional_ant,
        "porcentaje_posgrado": pct_pos,
        "adicional_posgrado": adicional_pos,
        "ad_honorem": bool(es_adh),
        "total_estimado": total,
    }


# --- escalas (l. 25603 / 25616) sobre las filas de ``get_escalas_salariales_v256`` ---------------------------------
def escala_salarial_mes_v256(df: pd.DataFrame, mes_referencia) -> dict:
    mes = str(mes_referencia or "").strip()
    if df is None or df.empty:
        return {}
    sub = df[df["mes_referencia"].astype(str).eq(mes)].copy()
    return {
        str(r.get("cargo") or ""): float(r.get("basico_simple") or 0)
        for _, r in sub.iterrows()
        if str(r.get("cargo") or "").strip()
    }


def escala_aplicable_v256(df: pd.DataFrame, mes_objetivo, hoy: date) -> tuple[Optional[str], dict]:
    objetivo = str(mes_objetivo or mes_ref_v256(hoy, hoy)).strip()
    if df is None or df.empty:
        return None, {}
    meses = sorted({str(x) for x in df["mes_referencia"].dropna().astype(str).tolist() if str(x) <= objetivo},
                   reverse=True)
    if not meses:
        return None, {}
    mes = meses[0]
    return mes, escala_salarial_mes_v256(df, mes)


def valor_inicial_formulario(cargo: str, escala_mes: dict, escala_previa: dict) -> float:
    """``number_input`` de "⚙️ Escalas básicas" (l. 61799): mes -> aplicable anterior -> 06/2026 -> 0 (H4)."""
    valor_ini = float(escala_mes.get(cargo, escala_previa.get(cargo, BASICOS_JUNIO_2026_V256.get(cargo, 0.0))) or 0.0)
    return round(valor_ini, 2)


def tabla_salarial_v256(escala: dict, dedicacion, nivel) -> list[dict]:
    """Pestaña "📈 Tabla salarial" (l. 61845-61851): Ad Honorem "No", antiguedad representativa de cada rango."""
    filas = []
    for cargo in CARGOS:
        fila = {"Cargo": cargo, "Básico Simple": moneda_v256(escala.get(cargo, 0))}
        for etiqueta, anios in RANGOS_TABLA:
            calc = calcular_sueldo_designacion_v256(cargo, dedicacion, "No", anios, nivel, escala)
            fila[f"{etiqueta} años"] = moneda_v256(calc["total_estimado"])
        filas.append(fila)
    return filas


def antiguedad_informada(valor) -> bool:
    """``antig_inf`` (l. 61901-61903) / ``antiguedad_informada_resumen`` (l. 60930)."""
    inf = valor is not None
    try:
        inf = inf and not pd.isna(valor)
    except Exception:
        pass
    return bool(inf)


def meses_ejecucion_v258(fecha_inicio, fecha_fin) -> int:
    """``domain/proyectos.py::_meses_ejecucion_proyecto_v258`` (la misma funcion ya portada por Investigacion)."""
    from investigacion.rules import meses_ejecucion_v258 as _m
    return _m(fecha_inicio, fecha_fin)


__all__ = [n for n in dir() if not n.startswith("_")]
