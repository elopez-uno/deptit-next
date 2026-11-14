# B05: extracted verbatim from certified B04 (texto generico: uniones, filtros textuales, nombres de archivo).
from __future__ import annotations

from difflib import SequenceMatcher

import pandas as pd

from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla
from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def _unir_lista_natural(valores):
    """Une valores como 'A', 'A y B' o 'A, B y C'."""
    limpios = []
    for v in valores or []:
        txt = " ".join(str(v or "").strip().split())
        if txt and txt not in limpios:
            limpios.append(txt)
    if not limpios:
        return ""
    if len(limpios) == 1:
        return limpios[0]
    if len(limpios) == 2:
        return f"{limpios[0]} y {limpios[1]}"
    return ", ".join(limpios[:-1]) + f" y {limpios[-1]}"


def _unir_items_administrativos(items):
    items = [str(x).strip() for x in items if str(x).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return "; ".join(items[:-1]) + "; y " + items[-1]


def nombre_archivo_seguro(texto):
    import re
    txt = str(texto or "").strip()
    txt = re.sub(r"[^A-Za-z0-9ÁÉÍÓÚáéíóúÑñ_\- ]+", "", txt)
    txt = re.sub(r"\s+", "_", txt)
    return txt[:120] or "disposicion"


def filtrar_dataframe_por_texto(df, texto, columnas):
    """Filtro textual tolerante para tablas de resultados v119."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=df.columns if isinstance(df, pd.DataFrame) else None)
    q = normalizar_clave(texto or "")
    if not q:
        return df.copy()
    cols = [c for c in list(columnas or []) if c in df.columns]
    if not cols:
        return df.copy()
    texto_filas = pd.Series("", index=df.index, dtype=str)
    for col in cols:
        texto_filas = texto_filas + " " + df[col].fillna("").astype(str)
    mask = texto_filas.map(normalizar_clave).str.contains(q, na=False, regex=False)
    return df[mask].copy()


def similitud_texto(a, b):
    a_n = normalizar_clave(a)
    b_n = normalizar_clave(b)
    if not a_n or not b_n:
        return 0
    return round(SequenceMatcher(None, a_n, b_n).ratio(), 3)


def _deptit_join_unicos(valores, sep=" / "):
    """Une valores únicos sin romper cuando `valores` es una Series de pandas.

    En Pandas no se puede evaluar una Series como booleano (`valores or []`),
    porque da: ValueError: The truth value of a Series is ambiguous.
    Esta función normaliza primero a una lista simple.
    """
    vistos = []

    if valores is None:
        iterable = []
    elif isinstance(valores, pd.DataFrame):
        iterable = valores.astype(object).where(pd.notna(valores), "").values.ravel().tolist()
    elif isinstance(valores, pd.Series):
        iterable = valores.dropna().tolist()
    elif isinstance(valores, (list, tuple, set)):
        iterable = list(valores)
    else:
        iterable = [valores]

    for v in iterable:
        if isinstance(v, pd.Series):
            sub_iter = v.dropna().tolist()
        elif isinstance(v, pd.DataFrame):
            sub_iter = v.astype(object).where(pd.notna(v), "").values.ravel().tolist()
        elif isinstance(v, (list, tuple, set)):
            sub_iter = list(v)
        else:
            sub_iter = [v]
        for sv in sub_iter:
            txt = limpiar_texto_tabla(sv)
            if txt and txt not in vistos:
                vistos.append(txt)
    return sep.join(vistos)


def _unir_unicos_v194(df, col):
    if not isinstance(df, pd.DataFrame) or df.empty or col not in df.columns:
        return ""
    vals = []
    for valor in df[col].dropna().astype(str).tolist():
        valor = " ".join(valor.strip().split())
        if valor and valor not in vals:
            vals.append(valor)
    return " / ".join(vals)
