"""Transcripcion de la pagina certificada ``elif modulo == "📊 Análisis"`` (entry l. 66604-67763) a datos de UI.

Cada funcion reproduce, en el mismo orden y con las mismas expresiones, lo que la pagina calcula y muestra sobre el
namespace del motor certificado (``analisis.motor.entorno``): rotulos, valores de ``st.metric`` ya formateados como
los formatea el certificado (``:g``, ``:+g``, ``.2f`` sin ceros), tablas (``st.dataframe``) con columnas y orden
originales, tortas y graficos Vega-Lite con la MISMA especificacion (D-AM10), y los textos/captions.  No hay
formulas propias: todo valor numerico sale de las funciones certificadas (D-AM13: anomalias incluidas).
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

import numpy as np
import pandas as pd

TABS = ["📌 Dashboard de dotación", "👥 Plantel / dotación", "🔄 Movimiento docente", "🤖 Análisis automático / IA",
        "📈 Comparación de períodos"]
SUBTABS_CMP = ["🎯 Resumen ejecutivo", "📊 Evolución visual", "🔎 Detalle"]
INFO = ("Panel de control académico por período. Usa las designaciones, comisiones, materias, "
        "investigación, extensión y movimientos ya cargados en el sistema.")
MSG_SIN_PERIODOS = "Todavía no hay períodos registrados."
CAPTION_NOLECT = ("Este porcentaje es propio del departamento operativo. Se aplica completo cuando el docente está solo en "
                  "la comisión; si la comisión tiene 2 o más docentes activos, a cada docente se le aplica la mitad del "
                  "porcentaje configurado. Ejemplo con parámetro 50 %: 4 hs solo en una comisión = 2 hs no lectivas; 4 hs "
                  "en una comisión compartida = 1 h no lectiva (25 %).")
HELP_NOLECT = "No modifica horarios ni designaciones: es un factor de estimación para productividad y disponibilidad."
INFO_HISTORICO = ("🕰️ Contexto histórico: el análisis reconstruye lo ocurrido en ese semestre aunque esté abierto "
                  "temporalmente por corrección. Las designaciones finalizadas automáticamente por el cierre se consideran "
                  "vigentes en la foto histórica; no se interpretan como una baja ni como 0 horas.")
LEYENDA_SEMAFORO = "🔴 **0–39 %** &nbsp;&nbsp; 🟡 **40–60 %** &nbsp;&nbsp; 🟢 **61–100 %** &nbsp;&nbsp; 🔵 **Más de 100 %**"
INDICADORES_MOV = {
    "Altas designaciones": "Altas de designaciones",
    "Bajas designaciones": "Bajas de designaciones",
    "Aumentos": "Aumentos de dedicación",
    "Disminuciones": "Disminuciones de dedicación",
    "Cambios de cargo": "Cambios de cargo",
    "Pase a Ad Honorem": "Pase a Ad Honorem",
    "Pase a Rentado": "Pase a Rentado",
}
RENOMBRES_MOV = {"periodo": "Período", "fecha": "Fecha", "cuil": "CUIL", "docente": "Docente",
                 "tipo_movimiento": "Tipo original", "categoria_movimiento": "Movimiento", "detalle": "Detalle",
                 "observaciones": "Observaciones", "variacion_horas": "Variación de horas"}
ORDEN_PROD = ["docente", "porcentaje_uso", "cuil", "cargos", "dedicaciones", "tipos_designacion",
              "departamentos_designacion", "horas_contratadas", "horas_comisiones_reales", "porcentaje_no_lectivas",
              "horas_no_lectivas", "horas_investigacion", "horas_extension", "horas_utilizadas", "horas_disponibles",
              "horas_no_contadas_por_superposicion", "diagnostico"]
RENOMBRES_PROD = {
    "docente": "Docente", "porcentaje_uso": "Productividad %", "cuil": "CUIL",
    "cargos": "Cargo/s", "dedicaciones": "Dedicación/es", "tipos_designacion": "Tipo/s designación",
    "departamentos_designacion": "Departamento/s de designación",
    "horas_contratadas": "Hs contratadas", "horas_comisiones_reales": "Hs frente a comisión",
    "porcentaje_no_lectivas": "% no lectivas", "horas_no_lectivas": "Hs no lectivas",
    "horas_investigacion": "Hs investigación", "horas_extension": "Hs extensión",
    "horas_utilizadas": "Hs utilizadas", "horas_disponibles": "Hs disponibles",
    "horas_no_contadas_por_superposicion": "Hs no contadas por superposición",
    "diagnostico": "Diagnóstico",
}
COLS_HS_PROD = ["Hs contratadas", "Hs frente a comisión", "Hs no lectivas", "Hs investigación", "Hs extensión",
                "Hs utilizadas", "Hs disponibles", "Hs no contadas por superposición"]
GRAVEDADES = ["Alta", "Media", "Baja"]


# ------------------------------------------------------------------------------------------ serializacion
def jsonable(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(v, (np.bool_,)):
        return bool(v)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def tabla(df: Optional[pd.DataFrame]) -> dict:
    """``st.dataframe(df, hide_index=True)``: columnas y filas en el orden del DataFrame."""
    if df is None or not isinstance(df, pd.DataFrame):
        return {"columnas": [], "filas": []}
    return {"columnas": [str(c) for c in df.columns],
            "filas": [[jsonable(v) for v in fila] for fila in df.itertuples(index=False, name=None)]}


def g(v: Any) -> str:
    return f"{float(v or 0):g}"


def valor(v: Any) -> str:
    """Valor de ``st.metric`` sin formato explicito (texto del objeto Python)."""
    v = jsonable(v)
    return "" if v is None else str(v)


def metrica(label: str, value: Any, delta: Optional[str] = None, delta_color: str = "normal",
            caption: Optional[str] = None) -> dict:
    return {"label": label, "valor": value if isinstance(value, str) else valor(value), "delta": delta,
            "delta_color": delta_color, "caption": caption}


def torta(ns: dict, df: Optional[pd.DataFrame], label_col: str, value_col: str, titulo: Optional[str] = None) -> dict:
    """``render_torta`` l. 24678 (misma especificacion Vega-Lite)."""
    vacio = df is None or df.empty or float(pd.to_numeric(df[value_col], errors="coerce").fillna(0).sum()) == 0
    out = {"titulo": titulo, "vacio": vacio, "mensaje": "No hay datos para graficar." if vacio else None, "spec": None}
    if not vacio:
        out["spec"] = {
            "data": {"values": tabla_registros(df)},
            "mark": {"type": "arc", "tooltip": True},
            "encoding": {
                "theta": {"field": value_col, "type": "quantitative"},
                "color": {"field": label_col, "type": "nominal"},
                "tooltip": [{"field": label_col, "type": "nominal"}, {"field": value_col, "type": "quantitative"}],
            },
            "view": {"stroke": None},
        }
    return out


def tabla_registros(df: pd.DataFrame) -> list[dict]:
    return [{str(k): jsonable(v) for k, v in r.items()} for r in df.to_dict("records")]


def conteo(ns: dict, df: pd.DataFrame, columna: str) -> dict:
    t = ns["tabla_conteo_porcentajes"](df, columna)
    return {"tabla": tabla(t), "torta": torta(ns, t, columna, "cantidad")}


# ------------------------------------------------------------------------------------------ periodo y parametro
def periodos(ns: dict) -> dict:
    """Selector "Período a analizar" (l. 66612-66626)."""
    df = ns["get_periodos"]()
    if df.empty:
        return {"vacio": True, "opciones": [], "default": None, "ids": {}}
    opciones = {row["nombre"]: row["id"] for _, row in df.iterrows()}
    base = ns["get_periodo_abierto"]() or ns["get_ultimo_periodo"]()
    nombre_default = base["nombre"] if base else list(opciones.keys())[0]
    lista = list(opciones.keys())
    default = lista[lista.index(nombre_default) if nombre_default in opciones else 0]
    return {"vacio": False, "opciones": lista, "default": default, "ids": {k: int(v) for k, v in opciones.items()},
            "df": df, "base": base}


def fila_periodo(df: pd.DataFrame, pid: int) -> dict:
    return df[df["id"] == pid].iloc[0].to_dict()


def rotulos(es_hist: bool) -> dict:
    return {"docentes": "Docentes del período" if es_hist else "Docentes activos",
            "no_docentes": "No docentes del período" if es_hist else "No docentes activos",
            "personas": "Personas del período · total" if es_hist else "Personas activas · total"}


# ------------------------------------------------------------------------------------------ 📌 Dashboard (l. 66681-66810)
def dashboard(ns: dict, m: dict, alum: dict, periodo_id: int, periodo_sel: str, es_hist: bool) -> dict:
    r = rotulos(es_hist)
    dot = [
        metrica(r["docentes"], m.get("docentes_activos", 0)),
        metrica(r["no_docentes"], m.get("no_docentes_activos", 0)),
        metrica(r["personas"], m.get("personas_activas_totales", 0)),
        metrica("Cargos docentes", m.get("cargos_docentes", m.get("cargos_totales", 0))),
        metrica("Cargos no docentes", m.get("cargos_no_docentes", 0)),
        metrica("Cargos del período · total" if es_hist else "Cargos activos · total",
                m.get("cargos_totales_consolidados", m.get("cargos_totales", 0))),
        metrica("Hs contratadas · docencia", g(m.get("horas_contratadas_docencia", m.get("horas_contratadas", 0)))),
        metrica("Hs contratadas · no docentes", g(m.get("horas_no_docentes", 0))),
        metrica("Hs contratadas · total", g(m.get("horas_contratadas_totales", m.get("horas_contratadas", 0)))),
    ]
    alumnos_doc = float(alum.get("alumnos_por_docente", 0) or 0)
    op = [
        metrica("Comisiones activas", m["comisiones"]),
        metrica("Docentes propios en comisiones", m["docentes_en_comisiones"]),
        metrica("Prestados recibidos", m.get("docentes_prestados_recibidos", 0)),
        metrica("Alumnos por docente", f"{alumnos_doc:.2f}".rstrip("0").rstrip("."), caption=(
            f"{int(alum.get('alumnos_inscriptos', 0) or 0)} alumnos (sin duplicar por comisión) / "
            f"{int(alum.get('docentes_en_comisiones_calculo', alum.get('docentes_activos_calculo', 0)) or 0)} "
            f"docentes únicos en comisiones")),
    ]
    grupos = ns["get_analisis_alumnos_por_docente_grupos_v248"](periodo_id)
    if grupos is None or grupos.empty:
        tabla_grupos = None
    else:
        tabla_grupos = tabla(grupos.rename(columns={
            "codigos": "Código/s", "asignaturas": "Asignatura/s",
            "inscriptos_totales": "Alumnos totales", "regulares_finales": "Regulares finales",
            "cantidad_comisiones": "Comisiones", "comisiones": "Detalle de comisiones",
            "docentes_unicos": "Docentes únicos", "docentes": "Docentes",
            "alumnos_por_docente": "Alumnos por docente",
        }).drop(columns=["clave_combinacion"], errors="ignore"))

    hs_doc = float(m.get("horas_contratadas_docencia", m.get("horas_contratadas", 0)) or 0)
    hs_no_doc = float(m.get("horas_no_docentes", 0) or 0)
    hs_contr = float(m.get("horas_contratadas_totales", hs_doc + hs_no_doc) or 0)
    hs_com = float(m.get("horas_comisiones", 0) or 0)
    hs_nl = float(m.get("horas_no_lectivas", 0) or 0)
    pct_nl = float(m.get("porcentaje_horas_no_lectivas", 0) or 0)
    hs_inv = float(m.get("horas_investigacion", 0) or 0)
    hs_ext = float(m.get("horas_extension", 0) or 0)
    hs_util = float(m.get("horas_utilizadas_totales", m.get("horas_academicas_utilizadas", 0)) or 0)
    hs_disp = float(m.get("horas_disponibles_totales", max(hs_contr - hs_util, 0)) or 0)
    hs_exc = float(m.get("horas_exceso_totales", max(hs_util - hs_contr, 0)) or 0)
    horas = [
        metrica("Hs contratadas · total", f"{hs_contr:g}"), metrica("Hs docencia contratadas", f"{hs_doc:g}"),
        metrica("Hs funciones no docentes", f"{hs_no_doc:g}"), metrica("Hs en comisiones", f"{hs_com:g}"),
        metrica("Hs no lectivas", f"{hs_nl:g}", caption=f"Estimación: {pct_nl:g} %"),
        metrica("Hs investigación", f"{hs_inv:g}"), metrica("Hs extensión", f"{hs_ext:g}"),
        metrica("Total utilizado", f"{hs_util:g}"),
        metrica("Exceso", f"{hs_exc:g}", delta=f"+{hs_exc:g} hs", delta_color="inverse") if hs_exc > 0
        else metrica("Disponibles", f"{hs_disp:g}"),
    ]
    conceptos = ["Comisiones (lectivas)", "Horas no lectivas", "Investigación", "Extensión", "Funciones no docentes"]
    valores = [hs_com, hs_nl, hs_inv, hs_ext, hs_no_doc]
    if hs_disp > 0:
        conceptos.append("Horas disponibles")
        valores.append(hs_disp)
    if hs_exc > 0:
        conceptos.append("Exceso sobre lo contratado")
        valores.append(hs_exc)
    df_horas = pd.DataFrame({"concepto": conceptos, "horas": valores})
    df_com_doc = pd.DataFrame({"concepto": ["Comisiones", "Docentes en comisiones"],
                               "cantidad": [m["comisiones"], m["docentes_en_comisiones"]]})
    resumen = pd.DataFrame([{
        "período": periodo_sel,
        "docentes_activos": m.get("docentes_activos", 0),
        "no_docentes_activos": m.get("no_docentes_activos", 0),
        "personas_activas_totales": m.get("personas_activas_totales", 0),
        "cargos_docentes": m.get("cargos_docentes", m.get("cargos_totales", 0)),
        "cargos_no_docentes": m.get("cargos_no_docentes", 0),
        "cargos_activos_totales": m.get("cargos_totales_consolidados", m.get("cargos_totales", 0)),
        "horas_contratadas_docencia": m.get("horas_contratadas_docencia", m.get("horas_contratadas", 0)),
        "horas_contratadas_no_docentes": m.get("horas_no_docentes", 0),
        "horas_contratadas_totales": m.get("horas_contratadas_totales", m.get("horas_contratadas", 0)),
        "materias_con_comision": m["materias_con_comision"],
        "comisiones_activas": m["comisiones"],
        "docentes_propios_en_comisiones": m["docentes_en_comisiones"],
        "docentes_prestados_recibidos": m.get("docentes_prestados_recibidos", 0),
        "horas_en_comisiones_propias": m["horas_comisiones"],
        "porcentaje_horas_no_lectivas": m.get("porcentaje_horas_no_lectivas", 0),
        "horas_no_lectivas_estimadas": m.get("horas_no_lectivas", 0),
        "horas_en_investigacion": m.get("horas_investigacion", 0),
        "horas_en_extension": m.get("horas_extension", 0),
        "horas_academicas_utilizadas": m.get("horas_academicas_utilizadas", 0),
        "horas_funciones_no_docentes": m.get("horas_no_docentes", 0),
        "horas_utilizadas_totales": m.get("horas_utilizadas_totales", 0),
        "alumnos_inscriptos_comisiones": alum.get("alumnos_inscriptos", 0),
        "alumnos_por_docente": alum.get("alumnos_por_docente", 0),
    }])
    return {
        "subtitulo": f"Dashboard de dotación — {periodo_sel}",
        "dotacion": dot,
        "caption_dotacion": ("El total de personas usa CUIL únicos; una misma persona puede integrar ambos grupos si "
                             "posee designaciones docentes y no docentes."),
        "operacion": op,
        "grupos": tabla_grupos,
        "horas": horas,
        "caption_horas": ("La productividad continúa calculándose exclusivamente sobre las designaciones docentes. El "
                          "consolidado de horas sí incorpora las funciones no docentes."),
        "torta_horas": torta(ns, df_horas, "concepto", "horas", "Distribución de la dedicación contratada"),
        "torta_comisiones": torta(ns, df_com_doc, "concepto", "cantidad", "Comisiones vs docentes en comisiones"),
        "resumen": tabla(resumen),
    }


# ------------------------------------------------------------------------------------------ 👥 Plantel (l. 66812-66946)
def plantel(ns: dict, m: dict, periodo_sel: str, es_hist: bool) -> dict:
    r = rotulos(es_hist)
    df_doc = m.get("df_desig_docentes_activas", pd.DataFrame()).copy()
    df_no = m.get("df_desig_no_docentes_activas", pd.DataFrame()).copy()
    df_tot = m.get("df_desig_activas_totales", pd.DataFrame()).copy()
    a = {"metricas": [
        metrica(r["docentes"], m.get("docentes_activos", 0)),
        metrica("Cargos docentes", m.get("cargos_docentes", m.get("cargos_totales", 0))),
        metrica("Cargos Ad Honórem", m.get("cargos_ad_honorem_docentes", 0)),
        metrica("Cargos Rentados", m.get("cargos_rentados_docentes", 0)),
    ], "horas": metrica("Horas contratadas de docencia",
                        f"{float(m.get('horas_contratadas_docencia', m.get('horas_contratadas', 0)) or 0):g} hs")}
    if df_doc.empty:
        a["vacio"] = ("No hay designaciones docentes del período seleccionado." if es_hist else
                      "No hay designaciones docentes activas en el período seleccionado.")
    else:
        vista = df_doc.copy()
        vista["Ámbito funcional"] = "Docencia"
        vista = vista.drop(columns=["funcion_no_docente", "texto_funcion_no_docente"], errors="ignore")
        a.update({"cargos": conteo(ns, df_doc, "cargo"), "dedicaciones": conteo(ns, df_doc, "dedicacion"),
                  "tipos": conteo(ns, df_doc, "tipo_designacion"),
                  "titulo_tabla": "Designaciones docentes del período" if es_hist else "Designaciones docentes activas",
                  "tabla": tabla(vista)})
    b = {"metricas": [
        metrica(r["no_docentes"], m.get("no_docentes_activos", 0)),
        metrica("Cargos no docentes", m.get("cargos_no_docentes", 0)),
        metrica("Hs no docentes", f"{float(m.get('horas_no_docentes', 0) or 0):g}"),
        metrica("Ad Honórem", m.get("cargos_ad_honorem_no_docentes", 0)),
        metrica("Rentados", m.get("cargos_rentados_no_docentes", 0)),
    ]}
    if df_no.empty:
        b["vacio"] = ("No hay designaciones para funciones no docentes en el período seleccionado." if es_hist else
                      "No hay designaciones activas destinadas a funciones no docentes en el período seleccionado.")
    else:
        vista = df_no.copy()
        vista["Ámbito funcional"] = "Funciones no docentes"
        vista["Funciones que cumple"] = vista.get(
            "texto_funcion_no_docente", pd.Series(index=vista.index, dtype=str)).fillna("").astype(str)
        vista = vista.drop(columns=["funcion_no_docente", "texto_funcion_no_docente"], errors="ignore")
        orden = [c for c in ["nombre_completo", "cuil", "Ámbito funcional", "Funciones que cumple", "cargo", "dedicacion",
                             "horas", "tipo_designacion", "ad_honorem", "fecha_desde", "fecha_hasta", "estado",
                             "observaciones"] if c in vista.columns]
        b["tabla"] = tabla(vista[orden + [c for c in vista.columns if c not in orden]])
    c = {"metricas": [
        metrica(r["personas"], m.get("personas_activas_totales", 0)),
        metrica("Cargos activos · total", m.get("cargos_totales_consolidados", 0)),
        metrica("Horas contratadas · total", f"{float(m.get('horas_contratadas_totales', 0) or 0):g}"),
        metrica("Cargos Ad Honórem · total", m.get("cargos_ad_honorem_totales", 0)),
        metrica("Cargos Rentados · total", m.get("cargos_rentados_totales", 0)),
    ], "caption": ((
        "Personas = CUIL únicos. Cargos y horas = suma de todas las designaciones del período, docentes y no docentes. "
        if es_hist else
        "Personas = CUIL únicos. Cargos y horas = suma de todas las designaciones activas, docentes y no docentes. ")
        + "Si una persona tiene ambos tipos de designación, se cuenta una vez como persona y cada designación aporta su "
          "cargo y sus horas.")}
    if not df_tot.empty:
        vista = df_tot.copy()
        vista["Ámbito funcional"] = vista.get("funcion_no_docente", pd.Series(index=vista.index, dtype=int)).map(
            lambda x: "Funciones no docentes" if ns["_es_funcion_no_docente_v162"](x) else "Docencia")
        vista["Funciones que cumple"] = vista.get(
            "texto_funcion_no_docente", pd.Series(index=vista.index, dtype=str)).fillna("").astype(str)
        vista = vista.drop(columns=["funcion_no_docente", "texto_funcion_no_docente"], errors="ignore")
        c.update({"cargos": conteo(ns, df_tot, "cargo"), "dedicaciones": conteo(ns, df_tot, "dedicacion"),
                  "tipos": conteo(ns, df_tot, "tipo_designacion"), "tabla": tabla(vista)})
    return {"subtitulo": f"Plantel y dotación — {periodo_sel}",
            "caption": ("La dotación se muestra primero separada entre funciones docentes y no docentes. "
                        "Después se presenta el consolidado total de personas, cargos y horas. La productividad "
                        "académica sigue usando solo el bloque docente."),
            "a": a, "b": b, "c": c}


# ------------------------------------------------------------------------------------------ 🔄 Movimiento (l. 66948-67145)
def movimientos_analisis(ns: dict, m: dict) -> pd.DataFrame:
    """``preparar_analisis_movimiento_docente`` + exclusion v172 de altas/bajas de personas (l. 66949-66962)."""
    df = ns["preparar_analisis_movimiento_docente"](m["df_mov"].copy())
    if not df.empty and "categoria_movimiento" in df.columns:
        df = df[~df["categoria_movimiento"].isin(["Altas de docentes", "Bajas de docentes"])].copy()
    return df


def movimiento(ns: dict, m: dict, alum: dict, periodo_id: int, periodo_sel: str, periodo_row: dict,
               es_hist: bool) -> dict:
    r = rotulos(es_hist)
    df = movimientos_analisis(ns, m)
    out: dict = {"subtitulo": f"Movimiento docente — {periodo_sel}"}
    if df.empty:
        out["vacio"] = "No hay movimientos de designaciones registrados para este período."
    else:
        res = ns["resumen_movimiento_docente"](df)
        bal = ns["balance_horas_movimiento_docente"](df)

        def n(cat):
            return int(res.loc[res["categoria_movimiento"] == cat, "movimientos"].sum()) if not res.empty else 0
        out["unitario"] = [
            metrica("Altas designaciones", n("Altas de designaciones"), f"{bal['horas_altas']:+g} hs"),
            metrica("Bajas designaciones", n("Bajas de designaciones"), f"{bal['horas_bajas']:+g} hs"),
            metrica("Aumentos", n("Aumentos de dedicación"), f"{bal['horas_aumentos']:+g} hs"),
            metrica("Disminuciones", n("Disminuciones de dedicación"), f"{bal['horas_disminuciones']:+g} hs"),
            metrica("Cambios de cargo", n("Cambios de cargo")),
            metrica("Pase a Ad Honorem", n("Pase a Ad Honorem")),
            metrica("Pase a Rentado", n("Pase a Rentado")),
        ]
        out["balance"] = [
            metrica("Horas por altas", f"{bal['horas_altas']:+g} hs"),
            metrica("Horas por bajas", f"{bal['horas_bajas']:+g} hs"),
            metrica("Horas por aumentos", f"{bal['horas_aumentos']:+g} hs"),
            metrica("Horas por disminuciones", f"{bal['horas_disminuciones']:+g} hs"),
            metrica("Saldo neto", f"{bal['saldo_neto']:+g} hs"),
        ]
        out["caption_balance"] = (
            "El saldo neto suma altas, bajas, aumentos y disminuciones de designaciones. "
            "Las renovaciones automáticas y los cierres por cambio de período se muestran como movimientos "
            "administrativos y no alteran el saldo real. Los cambios de cargo y los pases Ad Honorem/Rentado se "
            "contabilizan como cambios de condición de la designación y, por sí mismos, no modifican el balance de "
            "horas. Las altas/bajas de personas no se usan como indicador en Análisis: la unidad de gestión es cada "
            "designación.")
        indicadores = {}
        for etiqueta, cat in INDICADORES_MOV.items():
            f = df[df["categoria_movimiento"] == cat].copy()
            var = float(pd.to_numeric(f.get("variacion_horas", pd.Series(dtype=float)), errors="coerce")
                        .fillna(0).sum())
            indicadores[etiqueta] = {
                "caption": f"{len(f)} movimiento/s integran el indicador **{etiqueta}**; variación total: {var:+g} hs.",
                "vacio": f"El indicador {etiqueta} no tiene movimientos en {periodo_sel}." if f.empty else None,
                "tabla": None if f.empty else tabla(f.rename(columns=RENOMBRES_MOV)),
            }
        out["indicadores"] = indicadores
        out["indicador_default"] = list(INDICADORES_MOV)[0]
    ant = ns["get_periodo_mismo_semestre_anio_anterior"](periodo_row)
    if ant is None:
        out["anterior"] = None
    else:
        ma = ns["get_metricas_analisis_periodo"](ant["id"])
        alum_ant = ns["_alumnos_por_docente_periodo_v188"](ant["id"], metricas=ma)

        def fila(ind, a, b):
            return {"indicador": ind, "período_actual": a, "mismo_semestre_año_anterior": b, "diferencia": a - b}
        hcd = m.get("horas_contratadas_docencia", m.get("horas_contratadas", 0))
        hcd_a = ma.get("horas_contratadas_docencia", ma.get("horas_contratadas", 0))
        bal = pd.DataFrame([
            fila(r["docentes"], m["docentes_activos"], ma["docentes_activos"]),
            fila("Cargos activos", m["cargos_totales"], ma["cargos_totales"]),
            fila("Horas contratadas · docencia", hcd, hcd_a),
            fila(r["no_docentes"], m.get("no_docentes_activos", 0), ma.get("no_docentes_activos", 0)),
            fila(r["personas"], m.get("personas_activas_totales", 0), ma.get("personas_activas_totales", 0)),
            fila("Cargos activos · total", m.get("cargos_totales_consolidados", 0),
                 ma.get("cargos_totales_consolidados", 0)),
            fila("Horas contratadas · total", m.get("horas_contratadas_totales", 0), ma.get("horas_contratadas_totales", 0)),
            fila("Horas utilizadas académicas", m.get("horas_academicas_utilizadas", 0),
                 ma.get("horas_academicas_utilizadas", 0)),
            fila("Horas utilizadas · total consolidado", m.get("horas_utilizadas_totales", 0),
                 ma.get("horas_utilizadas_totales", 0)),
            fila("Materias con comisión", m["materias_con_comision"], ma["materias_con_comision"]),
            fila("Comisiones", m["comisiones"], ma["comisiones"]),
            {"indicador": "Alumnos por docente", "período_actual": alum.get("alumnos_por_docente", 0),
             "mismo_semestre_año_anterior": alum_ant.get("alumnos_por_docente", 0),
             "diferencia": round(float(alum.get("alumnos_por_docente", 0) or 0)
                                 - float(alum_ant.get("alumnos_por_docente", 0) or 0), 2)},
        ])
        out["anterior"] = {"caption": f"Comparación contra {ant['nombre']}.", "tabla": tabla(bal)}
    out["vacio_anterior"] = "No hay período equivalente del año anterior para comparar."
    out["_df"] = df
    return out


# ------------------------------------------------------------------------------------------ 🤖 Automatico / IA (l. 67148-67266)
def color_productividad(v: Any) -> str:
    """``_estilo_productividad_v148.color_pct`` (l. 30955): comparacion EXACTA del codigo (D-AM13)."""
    try:
        x = float(v)
    except Exception:
        return ""
    if x < 40:
        return "rojo"
    if x <= 60:
        return "amarillo"
    if x <= 100:
        return "verde"
    return "azul"


def fmt_max2(v: Any, sufijo: str = "") -> str:
    """``_estilo_productividad_v148.fmt_max2`` (hasta 2 decimales, sin ceros a la derecha)."""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    try:
        numero = round(float(v), 2)
    except Exception:
        return str(v)
    txt = f"{numero:.2f}".rstrip("0").rstrip(".")
    return f"{txt}{sufijo}"


def tabla_productividad(df: pd.DataFrame) -> dict:
    """Vista renombrada + formato y color del Styler certificado (celdas ya formateadas)."""
    vista = df[[c for c in ORDEN_PROD if c in df.columns]].copy().rename(columns=RENOMBRES_PROD)
    columnas = [str(c) for c in vista.columns]
    filas = []
    for fila in vista.to_dict("records"):
        celdas = []
        for col in columnas:
            v = fila[col]
            if col in COLS_HS_PROD:
                celdas.append(fmt_max2(v))
            elif col in ("Productividad %", "% no lectivas"):
                celdas.append(fmt_max2(v, " %"))
            else:
                celdas.append(jsonable(v))
        filas.append({"celdas": celdas, "color": color_productividad(fila.get("Productividad %")),
                      "diagnostico": fila.get("Diagnóstico")})
    return {"columnas": columnas, "filas": filas}


def automatico(ns: dict, m: dict, periodo_id: int, periodo_sel: str) -> dict:
    alertas = ns["construir_alertas_periodo"](periodo_id)
    prod = ns["get_docentes_productividad_periodo"](periodo_id)
    resumen = ns["generar_resumen_ejecutivo_automatico"](periodo_sel, m, alertas, prod)
    out: dict = {"subtitulo": f"Análisis automático / base para IA — {periodo_sel}", "resumen": resumen}
    if alertas.empty:
        out["alertas"] = None
    else:
        out["alertas"] = {
            "totales": len(alertas),
            "por_gravedad": {gv: int((alertas["gravedad"] == gv).sum()) for gv in GRAVEDADES},
            "tabla": tabla(alertas),
        }
    if prod.empty:
        out["productividad"] = None
    else:
        out["productividad"] = {"diagnosticos": sorted(prod["diagnostico"].dropna().unique().tolist()),
                                "total": len(prod), "tabla": tabla_productividad(prod)}
    out["prompt"] = ns["construir_prompt_ia_periodo"](periodo_sel, m, alertas, prod)
    out["_alertas"] = alertas
    return out


# ------------------------------------------------------------------------------------------ 📈 Comparacion (l. 67269-67763)
def comparacion_opciones(ns: dict, df_periodos: pd.DataFrame, periodo_base: Optional[dict]) -> dict:
    actual = ns["get_ultimo_periodo"]() or periodo_base  # D-AM13: siempre el ultimo, no el elegido arriba
    if not actual:
        return {"actual": None}
    actual_id = int(actual["id"])
    actual_nombre = str(actual.get("nombre") or actual_id)
    df_prev = df_periodos.copy()
    try:
        anio, sem = int(actual.get("anio")), int(actual.get("semestre"))
        anios = pd.to_numeric(df_prev.get("anio"), errors="coerce")
        sems = pd.to_numeric(df_prev.get("semestre"), errors="coerce")
        df_prev = df_prev[(anios < anio) | ((anios == anio) & (sems < sem))].copy()
    except Exception:
        df_prev = df_prev[pd.to_numeric(df_prev.get("id"), errors="coerce").ne(actual_id)].copy()
    if not df_prev.empty:
        orden = [c for c in ["anio", "semestre", "id"] if c in df_prev.columns]
        if orden:
            df_prev = df_prev.sort_values(orden, ascending=[False] * len(orden), kind="stable")
    opciones = {str(r.get("nombre") or r.get("id")): int(r["id"]) for _, r in df_prev.iterrows()}
    return {"actual": {"id": actual_id, "nombre": actual_nombre}, "opciones": list(opciones),
            "ids": opciones, "default": list(opciones)[:1]}


def _n(fila: dict, campo: str) -> float:
    try:
        v = pd.to_numeric(fila.get(campo), errors="coerce")
        return 0.0 if pd.isna(v) else float(v)
    except Exception:
        return 0.0


def _fmt(v: Any, dec: int = 2) -> str:
    try:
        v = float(v)
    except Exception:
        v = 0.0
    if dec == 0:
        return f"{int(round(v)):,}".replace(",", ".")
    return f"{v:.{dec}f}".rstrip("0").rstrip(".")


TARJETAS = [
    ("👥 Dotación y estudiantes", [("Docentes activos", "Docentes activos", 0, "", True),
                                  ("Alumnos inscriptos", "Alumnos inscriptos", 0, "", True),
                                  ("Alumnos por docente", "Alumnos por docente", 2, "", False),
                                  ("Docentes por comisión", "Docentes por comisión", 2, "", False)]),
    ("🏫 Cobertura y desempeño", [("Cobertura de comisiones", "Cobertura de comisiones (%)", 1, " %", False),
                                 ("Comisiones cubiertas", "Comisiones cubiertas", 0, "", True),
                                 ("Comisiones totales", "Comisiones totales", 0, "", True),
                                 ("Productividad promedio", "Productividad promedio (%)", 2, " %", False)]),
    ("⏱️ Uso de la dedicación", [("Hs de designación", "Horas de designación · total", 1, " hs", False),
                                 ("Hs frente a comisión", "Horas frente a comisión", 1, " hs", False),
                                 ("Hs no lectivas", "Horas no lectivas", 1, " hs", False),
                                 ("Hs investigación + extensión", "Horas investigación + extensión", 1, " hs", False),
                                 ("Hs funciones no docentes", "Horas funciones no docentes", 1, " hs", False)]),
    ("", [("Horas disponibles", "Horas disponibles", 1, " hs", False), ("Exceso global", "Exceso global", 1, " hs",
                                                                        False)]),
]
COLS_HORAS_CMP = ["Horas de designación · total", "Horas frente a comisión", "Horas no lectivas",
                  "Horas investigación + extensión", "Horas funciones no docentes"]


def comparacion(ns: dict, df_periodos: pd.DataFrame, opciones: dict, seleccion: list[str]) -> dict:
    actual = opciones["actual"]
    filas = [{"Período": actual["nombre"], "_periodo_id": actual["id"], "_es_actual": True,
              **ns["_indicadores_comparacion_periodo_v188"](actual["id"])}]
    for nombre in seleccion:
        pid = opciones["ids"][nombre]
        filas.append({"Período": nombre, "_periodo_id": pid, "_es_actual": False,
                      **ns["_indicadores_comparacion_periodo_v188"](pid)})
    df = pd.DataFrame(filas)
    incluidos = df["Período"].astype(str).tolist()
    meta = {}
    for _, rp in df_periodos.iterrows():
        try:
            meta[int(rp["id"])] = (int(rp.get("anio") or 0), int(rp.get("semestre") or 0))
        except Exception:
            pass
    try:
        df["_orden_cmp"] = df["_periodo_id"].map(lambda p: meta.get(int(p), (0, 0))[0] * 10
                                                 + meta.get(int(p), (0, 0))[1])
    except Exception:
        df["_orden_cmp"] = range(len(df))
    crono = df.sort_values("_orden_cmp", kind="stable").reset_index(drop=True)
    orden_periodos = crono["Período"].tolist()
    fila_actual = df[df["_es_actual"]].iloc[0].to_dict()

    referencias = {}
    for ref in seleccion:
        fila_ref = df[df["Período"].astype(str).eq(str(ref))].iloc[0].to_dict()
        grupos = []
        for titulo, items in TARJETAS:
            tarjetas = []
            for etiqueta, campo, dec, suf, entero in items:
                d = 0 if entero else dec
                dif = _n(fila_actual, campo) - _n(fila_ref, campo)
                tarjetas.append(metrica(etiqueta, _fmt(_n(fila_actual, campo), d) + suf,
                                        f"{'+' if dif > 0 else ''}{_fmt(dif, d)}{suf} vs {ref}", "off"))
            grupos.append({"titulo": titulo, "tarjetas": tarjetas})
        cov_a, cov_r = _n(fila_actual, "Cobertura de comisiones (%)"), _n(fila_ref, "Cobertura de comisiones (%)")
        pr_a, pr_r = _n(fila_actual, "Productividad promedio (%)"), _n(fila_ref, "Productividad promedio (%)")
        d_doc = _n(fila_actual, "Docentes activos") - _n(fila_ref, "Docentes activos")
        d_alum = _n(fila_actual, "Alumnos inscriptos") - _n(fila_ref, "Alumnos inscriptos")
        d_ratio = _n(fila_actual, "Alumnos por docente") - _n(fila_ref, "Alumnos por docente")
        d_cov = cov_a - cov_r
        referencias[ref] = {
            "titulo": f"{actual['nombre']} frente a {ref}",
            "grupos": grupos,
            "cobertura": [{"texto": f"{actual['nombre']}: {cov_a:g} %", "valor": max(0.0, min(cov_a / 100.0, 1.0))},
                          {"texto": f"{ref}: {cov_r:g} %", "valor": max(0.0, min(cov_r / 100.0, 1.0))}],
            "productividad": [{"texto": f"{actual['nombre']}: {pr_a:g} %", "valor": max(0.0, min(pr_a / 100.0, 1.0))},
                              {"texto": f"{ref}: {pr_r:g} %", "valor": max(0.0, min(pr_r / 100.0, 1.0))}],
            "sintesis": (f"Respecto de **{ref}**, el período actual presenta **{d_doc:+g} docentes activos**, "
                         f"**{d_alum:+g} inscripciones**, **{d_ratio:+.2f} alumnos por docente** y "
                         f"**{d_cov:+.1f} puntos porcentuales de cobertura**."),
        }

    horas_long = crono[["Período"] + COLS_HORAS_CMP].melt(id_vars=["Período"], var_name="Concepto",
                                                           value_name="Horas")
    horas_long = horas_long.sort_values(["Concepto", "Horas"], ascending=[True, False], kind="stable")
    pct_long = crono[["Período", "Cobertura de comisiones (%)", "Productividad promedio (%)"]].melt(
        id_vars=["Período"], var_name="Indicador", value_name="Porcentaje")
    com_long = crono[["Período", "Comisiones cubiertas", "Comisiones totales"]].melt(
        id_vars=["Período"], var_name="Indicador", value_name="Comisiones")
    com_long["_orden_superposicion_v190"] = com_long["Indicador"].astype(str).map(
        {"Comisiones totales": 0, "Comisiones cubiertas": 1}).fillna(2)
    com_long = com_long.sort_values(["Período", "_orden_superposicion_v190"], kind="stable")
    eje_x = {"field": "Período", "type": "ordinal", "sort": orden_periodos, "title": None}
    graficos = {
        "horas": {"data": {"values": tabla_registros(horas_long)},
                  "mark": {"type": "bar", "tooltip": True, "opacity": 0.58},
                  "encoding": {"x": {"field": "Concepto", "type": "nominal", "sort": COLS_HORAS_CMP, "title": None,
                                     "axis": {"labelAngle": -20}},
                               "y": {"field": "Horas", "type": "quantitative", "title": "Horas",
                                     "scale": {"domainMin": 0}},
                               "color": {"field": "Período", "type": "nominal", "title": "Período",
                                         "sort": orden_periodos},
                               "tooltip": [{"field": "Concepto", "type": "nominal"},
                                           {"field": "Período", "type": "nominal"},
                                           {"field": "Horas", "type": "quantitative"}]}},
        "porcentajes": {"data": {"values": tabla_registros(pct_long)},
                        "mark": {"type": "line", "point": True, "tooltip": True},
                        "encoding": {"x": eje_x, "y": {"field": "Porcentaje", "type": "quantitative", "title": "%",
                                                       "scale": {"domainMin": 0}},
                                     "color": {"field": "Indicador", "type": "nominal", "title": None},
                                     "tooltip": [{"field": "Período", "type": "nominal"},
                                                 {"field": "Indicador", "type": "nominal"},
                                                 {"field": "Porcentaje", "type": "quantitative"}]}},
        "alumnos": {"data": {"values": tabla_registros(crono[["Período", "Alumnos por docente"]])},
                    "mark": {"type": "line", "point": True, "tooltip": True},
                    "encoding": {"x": eje_x, "y": {"field": "Alumnos por docente", "type": "quantitative",
                                                   "title": "Alumnos / docente", "scale": {"domainMin": 0}},
                                 "tooltip": [{"field": "Período", "type": "nominal"},
                                             {"field": "Alumnos por docente", "type": "quantitative"}]}},
        "comisiones": {"data": {"values": tabla_registros(com_long)},
                       "mark": {"type": "bar", "tooltip": True, "opacity": 0.62},
                       "encoding": {"x": eje_x, "y": {"field": "Comisiones", "type": "quantitative",
                                                      "title": "Comisiones", "scale": {"domainMin": 0}},
                                    "color": {"field": "Indicador", "type": "nominal", "title": None,
                                              "sort": ["Comisiones totales", "Comisiones cubiertas"]},
                                    "tooltip": [{"field": "Período", "type": "nominal"},
                                                {"field": "Indicador", "type": "nominal"},
                                                {"field": "Comisiones", "type": "quantitative"}]}},
        "docentes": {"data": {"values": tabla_registros(crono[["Período", "Docentes activos"]])},
                     "mark": {"type": "bar", "tooltip": True},
                     "encoding": {"x": eje_x, "y": {"field": "Docentes activos", "type": "quantitative",
                                                    "title": "Docentes"},
                                  "tooltip": [{"field": "Período", "type": "nominal"},
                                              {"field": "Docentes activos", "type": "quantitative"}]}},
    }
    detalle = crono.drop(columns=[c for c in ["_periodo_id", "_es_actual", "_orden_cmp"] if c in crono.columns],
                         errors="ignore").copy()
    matriz = detalle.set_index("Período").T.reset_index().rename(columns={"index": "Indicador"})
    return {"incluidos": incluidos,
            "info": (f"📚 **Comparación múltiple activa: {len(incluidos)} períodos.** " + " · ".join(incluidos)),
            "referencias": referencias, "graficos": graficos, "matriz": tabla(matriz)}


def nombre_alerta_csv(categoria: str, periodo_sel: str) -> str:
    return (f"alertas_{re.sub(r'[^0-9A-Za-záéíóúÁÉÍÓÚñÑ]+', '_', categoria).strip('_').lower()}_"
            f"{periodo_sel}.csv")
