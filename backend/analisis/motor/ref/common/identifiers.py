# B05: extracted verbatim from certified B04 (identificadores: CUIL, claves de departamento).
from __future__ import annotations

import re

import pandas as pd

from analisis.motor.ref.extracted_batch04.identidad import _clave_cuil
from analisis.motor.ref.extracted_batch04.identidad import limpiar_cuil
from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def _clave_departamento_dispo_v159(valor):
    """Normaliza nombres de departamentos para comparar origen/receptor."""
    txt = normalizar_clave(valor or "")
    txt = re.sub(r"^DEPARTAMENTO\s+DE\s+", "", txt).strip()
    txt = re.sub(r"^DEPARTAMENTO\s+", "", txt).strip()
    return txt


def _cuiles_unicos_designaciones_v165(df):
    if df is None or df.empty:
        return set()
    return {
        _clave_cuil(x)
        for x in df.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).tolist()
        if _clave_cuil(x)
    }


def _claves_cuil_df_v194(df):
    if not isinstance(df, pd.DataFrame) or df.empty or "cuil" not in df.columns:
        return pd.Series(dtype=str)
    return df["cuil"].fillna("").astype(str).map(_clave_cuil)


def _cuil_desde_ref_docente_v217(ref):
    txt = str(ref or "").strip()
    if "|" in txt:
        txt = txt.rsplit("|", 1)[-1].strip()
    return limpiar_cuil(txt)
