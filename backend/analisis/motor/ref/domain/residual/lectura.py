# B06: extracted verbatim from certified B05 (comisiones/materias con lector read-only B03 inyectado (R1 residual)).
from __future__ import annotations

import pandas as pd

from analisis.motor.ref.domain.materias import _clave_materia_unica_desde_codigo_nombre
from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla


def periodo_actual_para_comisiones(*, get_ultimo_periodo):
    """
    Para abrir comisiones se usa únicamente el último período creado.
    Si por emergencia se abrió un período anterior, se bloquea la creación/modificación
    de comisiones hasta volver al período actual.
    """
    return get_ultimo_periodo()


def _contexto_materias_unicas_fuente(*, get_plan_estudio_todas):
    """Devuelve carreras/facultades/planes de cada materia única desde _planes_estudio.db."""
    try:
        df_planes = get_plan_estudio_todas()
    except Exception:
        df_planes = pd.DataFrame()

    contexto = {}
    por_id = {}

    if df_planes is None or df_planes.empty:
        return contexto, por_id

    df = df_planes.copy()
    for col in ["id", "codigo", "asignatura", "carrera", "escuela", "plan_version", "anio", "cuatrimestre"]:
        if col not in df.columns:
            df[col] = ""

    for col in ["codigo", "asignatura", "carrera", "escuela", "plan_version", "anio", "cuatrimestre"]:
        df[col] = df[col].apply(limpiar_texto_tabla)

    def unir_unicos(valores):
        salida = []
        for v in valores:
            v = limpiar_texto_tabla(v)
            if v and v not in salida:
                salida.append(v)
        return " | ".join(salida)

    df["_clave_materia_unica"] = df.apply(
        lambda row: _clave_materia_unica_desde_codigo_nombre(row.get("codigo"), row.get("asignatura")),
        axis=1
    )

    for _, grupo in df.groupby("_clave_materia_unica", dropna=False):
        clave = str(grupo.iloc[0].get("_clave_materia_unica") or "")
        if not clave:
            continue
        contexto[clave] = {
            "carrera": unir_unicos(grupo["carrera"]),
            "escuela": unir_unicos(grupo["escuela"]),
            "plan_version": unir_unicos(grupo["plan_version"]),
            "anio": unir_unicos(grupo["anio"]),
            "cuatrimestre": unir_unicos(grupo["cuatrimestre"]),
            "cantidad_carreras_fuente": int(grupo["carrera"].apply(limpiar_texto_tabla).replace("", pd.NA).dropna().nunique()),
            "apariciones_en_planes_fuente": int(len(grupo)),
        }

    for _, row in df.iterrows():
        try:
            mid = int(row.get("id"))
        except Exception:
            continue
        por_id[mid] = row.to_dict()

    return contexto, por_id


def _es_periodo_actual_para_comisiones_v233(periodo_id, *, get_ultimo_periodo):
    try:
        ultimo = get_ultimo_periodo()
        return bool(ultimo and int(ultimo.get("id")) == int(periodo_id))
    except Exception:
        return False
