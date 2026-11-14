"""Reglas puras de Materias (sin base de datos), copiadas de la fuente certificada B13-FIX02.

Origen (reference_fix02): entry l. 14052-14057 y 12350 (catalogos), l. 14332-14428 (columnas/filtros/opciones de
carrera), l. 14582-14693 (materias unicas), l. 16428-16528 (carga rapida de plan); ``catalogs/materias.py``;
``extracted_batch04/materias.py`` (``normalizar_codigo_materia``, tipos de espacio/opcion, clave codigo+nombre);
``extracted_batch04/texto.py`` (``_valor_limpio_materia``); ``domain/materias.py`` (``escuela_para_filtro``,
``_filtrar_busqueda_materias``, conflictos en tabla, etiquetas, Excel v124); ``domain/catalog_unlocked/materias.py``
(compartición v137); ``common/text.py`` (``filtrar_dataframe_por_texto``, ``_deptit_join_unicos``);
``extracted_batch02/safe_helpers.py`` (``_normalizar_encabezado_opcion_v124``).
Se trabaja con pandas (mismas versiones que el runtime certificado) para conservar la semantica exacta.
"""

from __future__ import annotations

import re
import unicodedata
from io import BytesIO, StringIO
from typing import Any

import pandas as pd

from docentes.rules import limpiar_texto_tabla, normalizar_clave

# --- catalogos ---------------------------------------------------------------------------------------------
ANIOS = ["1° Año", "2° Año", "3° Año", "4° Año", "5° Año", "6° Año"]
CUATRIMESTRES_MAT = ["1", "2", "1 y 2", "Sin especificar"]
DURACIONES = ["Mensual", "Bimestral", "Trimestral", "Cuatrimestral", "Semestral", "Anual", "Sin especificar"]
DICTADOS = ["Presencial", "Virtual", "Mixto"]
ESTADOS_CARRERA = ["Activa", "Inactiva"]
ESTADOS_MATERIA = ["Activa", "Inactiva"]
TIPOS_OPCION_CURRICULAR = ["Optativa", "Electiva"]
ESTADOS_OPCION_CURRICULAR = ["Activa", "Inactiva"]
MODO_COMPARTICION_AUTO = "Automática"
MODO_COMPARTICION_ESPECIFICA = "Específica"
MODO_COMPARTICION_SELECCIONADA = "Seleccionada"
ETIQUETAS_COMPARTICION_MATERIA = {
    "Compartida automáticamente entre todos los planes donde aparece": MODO_COMPARTICION_AUTO,
    "Específica de esta carrera/plan": MODO_COMPARTICION_ESPECIFICA,
    "Compartida únicamente entre planes seleccionados": MODO_COMPARTICION_SELECCIONADA,
}
ETIQUETAS_COMPARTICION_MATERIA_INV = {v: k for k, v in ETIQUETAS_COMPARTICION_MATERIA.items()}
PLAN_VIGENTE_DEFAULT = "Plan vigente"


# --- texto y codigos ---------------------------------------------------------------------------------------
def valor_limpio_materia(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    txt = str(valor).strip()
    return "" if txt.lower() in ["nan", "none", "nat"] else txt


def normalizar_codigo_materia(valor):
    """Codigo academico canonico, sin separadores; numericos completados a 5 digitos (v121/v161)."""
    if valor is None or pd.isna(valor):
        return ""
    txt_crudo = str(valor).strip()
    m_entero_decimal = re.fullmatch(r"([0-9]+)\.0+", txt_crudo)
    if m_entero_decimal:
        txt_crudo = m_entero_decimal.group(1)
    txt = normalizar_clave(txt_crudo)
    if not txt:
        return ""
    codigo = re.sub(r"[^A-Z0-9]", "", txt)
    if codigo.isdigit() and len(codigo) < 5:
        codigo = codigo.zfill(5)
    return codigo


def escuela_para_filtro(valor):
    valor = str(valor or "").strip()
    if not valor or valor in ["Todas", "Escribir manualmente"]:
        return None
    return valor


def clave_materia_unica_codigo_nombre(codigo, asignatura):
    return f"{normalizar_clave(codigo)}||{normalizar_clave(asignatura)}"


def es_materia_optativa_electiva(codigo, asignatura):
    nombre_txt = normalizar_clave(asignatura or "").lower()
    return "optativa" in nombre_txt or "electiva" in nombre_txt


def tipo_espacio_curricular_v120(codigo, asignatura):
    if not es_materia_optativa_electiva(codigo, asignatura):
        return ""
    nombre = normalizar_clave(asignatura or "").lower()
    if "electiva" in nombre:
        return "Electiva"
    if "optativa" in nombre:
        return "Optativa"
    return ""


def normalizar_tipo_opcion_v120(tipo):
    n = normalizar_clave(tipo or "").lower()
    if n == "optativa":
        return "Optativa"
    if n == "electiva":
        return "Electiva"
    return ""


def normalizar_modo_comparticion_v137(valor):
    txt = str(valor or "").strip()
    if txt in ETIQUETAS_COMPARTICION_MATERIA:
        return ETIQUETAS_COMPARTICION_MATERIA[txt]
    n = normalizar_clave(txt)
    if n in {"ESPECÍFICA", "ESPECIFICA", "ESPECÍFICO", "ESPECIFICO", "INDIVIDUAL"}:
        return MODO_COMPARTICION_ESPECIFICA
    if n in {"SELECCIONADA", "SELECCIONADOS", "GRUPO", "PARCIAL"}:
        return MODO_COMPARTICION_SELECCIONADA
    return MODO_COMPARTICION_AUTO


def clave_materia_conceptual_v137(fila):
    if fila is None:
        return ""
    try:
        mid = int(fila.get("materia_id", fila.get("id")))
    except Exception:
        mid = None
    base = clave_materia_unica_codigo_nombre(fila.get("codigo", ""), fila.get("asignatura", ""))
    modo = normalizar_modo_comparticion_v137(fila.get("comparticion_modo", MODO_COMPARTICION_AUTO))
    grupo = str(fila.get("comparticion_grupo", "") or "").strip()
    if modo == MODO_COMPARTICION_ESPECIFICA:
        return f"ESPECIFICA::{mid if mid is not None else base}"
    if modo == MODO_COMPARTICION_SELECCIONADA:
        return f"SELECCIONADA::{grupo}" if grupo else f"ESPECIFICA::{mid if mid is not None else base}"
    return f"AUTO::{base}"


def etiqueta_plan_materia_v137(fila):
    carrera = limpiar_texto_tabla(fila.get("carrera", ""))
    plan = limpiar_texto_tabla(fila.get("plan_version", "")) or "Sin plan"
    escuela = limpiar_texto_tabla(fila.get("escuela", ""))
    codigo = limpiar_texto_tabla(fila.get("codigo", ""))
    asignatura = limpiar_texto_tabla(fila.get("asignatura", ""))
    return f"{carrera} — {plan} — {escuela} — {codigo} - {asignatura}".strip(" —")


def etiqueta_espacio_plan_opcion_v124(row):
    try:
        materia_id = int(row.get("materia_id"))
    except Exception:
        materia_id = None
    tipo = limpiar_texto_tabla(row.get("tipo_espacio", ""))
    escuela = limpiar_texto_tabla(row.get("escuela", ""))
    carrera = limpiar_texto_tabla(row.get("carrera", ""))
    plan = limpiar_texto_tabla(row.get("plan_version", ""))
    codigo = limpiar_texto_tabla(row.get("codigo", ""))
    asignatura = limpiar_texto_tabla(row.get("asignatura", ""))
    anio = limpiar_texto_tabla(row.get("anio", ""))
    cuatri = limpiar_texto_tabla(row.get("cuatrimestre", ""))
    partes = [p for p in [tipo, escuela, carrera, plan, f"{codigo} - {asignatura}".strip(" -"), anio,
                          f"Cuat. {cuatri}" if cuatri else ""] if p]
    etiqueta = " · ".join(partes)
    if materia_id is not None:
        etiqueta = f"{etiqueta} [ID:{materia_id}]" if etiqueta else f"[ID:{materia_id}]"
    return etiqueta


def deptit_join_unicos(valores, sep=" / "):
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


def normalizar_encabezado_opcion_v124(valor):
    txt = str(valor or "").strip().lower()
    trans = str.maketrans("áéíóúüñ", "aeiouun")
    txt = txt.translate(trans)
    txt = re.sub(r"[^a-z0-9]+", "_", txt).strip("_")
    return txt


# --- dataframes de materias ------------------------------------------------------------------------------------
COLUMNAS_MATERIAS = [
    "id", "carrera_id", "orden", "codigo", "asignatura", "carrera", "escuela",
    "plan_version", "anio", "cuatrimestre", "dictado", "carga_semanal",
    "carga_total", "duracion", "estado", "observaciones",
    "comparticion_modo", "comparticion_grupo", "en_plan",
]


def asegurar_columnas_materias(df):
    if df is None:
        df = pd.DataFrame(columns=COLUMNAS_MATERIAS)
    df = df.copy()
    for col in COLUMNAS_MATERIAS:
        if col not in df.columns:
            df[col] = ""
    df["estado"] = df["estado"].apply(lambda x: valor_limpio_materia(x) or "Activa")
    df["comparticion_modo"] = df["comparticion_modo"].apply(normalizar_modo_comparticion_v137)
    df["comparticion_grupo"] = df["comparticion_grupo"].fillna("").astype(str).str.strip()
    df["en_plan"] = pd.to_numeric(df["en_plan"], errors="coerce").fillna(1).astype(int)
    return df[COLUMNAS_MATERIAS]


def filtrar_materias_dataframe(df, escuela=None, carrera_id=None, estado=None, cuatrimestre=None):
    df = asegurar_columnas_materias(df)
    if df.empty:
        return df
    escuela = escuela_para_filtro(escuela)
    if escuela:
        esc_n = normalizar_clave(escuela)
        df = df[df["escuela"].fillna("").astype(str).apply(lambda x: normalizar_clave(x) == esc_n)].copy()
    if carrera_id not in [None, "", "Todas"]:
        try:
            cid = int(carrera_id)
            df = df[pd.to_numeric(df["carrera_id"], errors="coerce").fillna(-1).astype(int) == cid].copy()
        except Exception:
            pass
    if estado and estado != "Todos":
        est_n = normalizar_clave(estado)
        df = df[df["estado"].fillna("Activa").astype(str).apply(lambda x: normalizar_clave(x or "Activa") == est_n)].copy()
    if cuatrimestre and cuatrimestre != "Todos":
        cuat_n = normalizar_clave(cuatrimestre)
        df = df[df["cuatrimestre"].fillna("").astype(str).apply(lambda x: normalizar_clave(x) == cuat_n)].copy()
    return df.reset_index(drop=True)


def filtrar_busqueda_materias(df, texto, columnas_extra=None):
    df = df.copy()
    texto = str(texto or "").strip()
    if not texto or df.empty:
        return df
    q_texto = normalizar_clave(texto)
    q_codigo = normalizar_codigo_materia(texto)
    columnas = ["codigo", "asignatura"] + list(columnas_extra or [])
    columnas = [c for c in columnas if c in df.columns]

    def coincide(row):
        if "codigo" in row.index:
            cod = valor_limpio_materia(row.get("codigo"))
            cod_norm = normalizar_codigo_materia(cod)
            if q_codigo and cod_norm and q_codigo in cod_norm:
                return True
            if q_texto and q_texto in normalizar_clave(cod):
                return True
        for col in columnas:
            if col == "codigo":
                continue
            val = valor_limpio_materia(row.get(col))
            if q_texto and q_texto in normalizar_clave(val):
                return True
            if q_codigo and q_codigo in normalizar_codigo_materia(val):
                return True
        return False

    return df[df.apply(coincide, axis=1)].copy().reset_index(drop=True)


def filtrar_dataframe_por_texto(df, texto, columnas):
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


def opciones_carrera_plan_desde_materias(df):
    """Opciones {etiqueta: carrera_id} desde las materias cargadas (``_opciones_carrera_plan_desde_materias``)."""
    df = asegurar_columnas_materias(df)
    opciones = {"Todas": None}
    if df.empty:
        return opciones
    tmp = df[["carrera_id", "carrera", "plan_version", "escuela"]].copy()
    for col in ["carrera", "plan_version", "escuela"]:
        tmp[col] = tmp[col].apply(valor_limpio_materia)
    tmp = tmp.drop_duplicates(subset=["carrera_id", "carrera", "plan_version", "escuela"])
    tmp = tmp.sort_values(["escuela", "carrera", "plan_version"], kind="stable")
    for _, r in tmp.iterrows():
        carrera = valor_limpio_materia(r.get("carrera"))
        plan = valor_limpio_materia(r.get("plan_version"))
        escuela = valor_limpio_materia(r.get("escuela"))
        if not carrera and not plan and not escuela:
            continue
        partes = []
        if carrera:
            partes.append(carrera)
        if plan:
            partes.append(plan)
        if escuela:
            partes.append(escuela)
        etiqueta = " — ".join(partes)
        cid = r.get("carrera_id")
        try:
            cid = int(cid) if pd.notna(cid) and str(cid).strip() != "" else None
        except Exception:
            cid = None
        if etiqueta and etiqueta not in opciones:
            opciones[etiqueta] = cid
    return opciones


def materias_unicas(df):
    """Consolidacion de ``get_materias_unicas`` sobre las materias totales ya filtradas."""
    columnas = [
        "codigo", "asignatura", "carreras", "escuelas", "planes_version",
        "cantidad_carreras", "apariciones_en_planes", "anios", "cuatrimestres",
        "cargas_semanales", "cargas_totales", "duraciones", "estados", "observaciones",
    ]
    if df.empty:
        return pd.DataFrame(columns=columnas)
    df = asegurar_columnas_materias(df)
    for col in df.columns:
        df[col] = df[col].apply(valor_limpio_materia)
    df["codigo_normalizado"] = df["codigo"].apply(normalizar_codigo_materia)
    df["asignatura_normalizada"] = df["asignatura"].apply(normalizar_clave)
    df["clave_materia"] = df.apply(
        lambda row: f"{row['codigo_normalizado']}::{row['asignatura_normalizada']}" if row["codigo_normalizado"]
        else f"SIN_CODIGO::{row['asignatura_normalizada']}",
        axis=1,
    )

    def unir_unicos(serie):
        valores = []
        for v in serie:
            v = valor_limpio_materia(v)
            if v and v not in valores:
                valores.append(v)
        return " / ".join(valores)

    registros = []
    for _, grupo in df.groupby("clave_materia", dropna=False):
        codigos = [v for v in grupo["codigo"].apply(valor_limpio_materia).tolist() if v]
        codigo = codigos[0] if codigos else "(sin código)"
        asignaturas = []
        for v in grupo["asignatura"].apply(valor_limpio_materia).tolist():
            if v and v not in asignaturas:
                asignaturas.append(v)
        carreras = []
        for _, row in grupo.iterrows():
            carrera = valor_limpio_materia(row.get("carrera", ""))
            plan = valor_limpio_materia(row.get("plan_version", ""))
            escuela = valor_limpio_materia(row.get("escuela", ""))
            etiqueta_partes = []
            if carrera:
                etiqueta_partes.append(carrera)
            if plan:
                etiqueta_partes.append(plan)
            if escuela:
                etiqueta_partes.append(escuela)
            etiqueta = " (".join([etiqueta_partes[0], " — ".join(etiqueta_partes[1:]) + ")"]) \
                if len(etiqueta_partes) > 1 else (etiqueta_partes[0] if etiqueta_partes else "")
            if etiqueta and etiqueta not in carreras:
                carreras.append(etiqueta)
        carreras_sin_plan = []
        for v in grupo["carrera"].apply(valor_limpio_materia).tolist():
            if v and v not in carreras_sin_plan:
                carreras_sin_plan.append(v)
        registros.append({
            "codigo": codigo,
            "asignatura": " / ".join(asignaturas),
            "carreras": " | ".join(carreras),
            "escuelas": unir_unicos(grupo["escuela"]),
            "planes_version": unir_unicos(grupo["plan_version"]),
            "cantidad_carreras": len(carreras_sin_plan),
            "apariciones_en_planes": len(grupo),
            "anios": unir_unicos(grupo["anio"]),
            "cuatrimestres": unir_unicos(grupo["cuatrimestre"]),
            "cargas_semanales": unir_unicos(grupo["carga_semanal"]),
            "cargas_totales": unir_unicos(grupo["carga_total"]),
            "duraciones": unir_unicos(grupo["duracion"]),
            "estados": unir_unicos(grupo["estado"]),
            "observaciones": unir_unicos(grupo["observaciones"]),
        })
    df_unicas = pd.DataFrame(registros, columns=columnas)
    if df_unicas.empty:
        return df_unicas
    return df_unicas.sort_values(["codigo", "asignatura"], kind="stable").reset_index(drop=True)


def detectar_conflictos_codigo_en_tabla(df_plan):
    if df_plan is None or df_plan.empty:
        return pd.DataFrame()
    registros = []
    grupos = {}
    for idx, row in df_plan.iterrows():
        codigo = str(row.get("codigo", "") or "").strip()
        asignatura = str(row.get("asignatura", "") or "").strip()
        codigo_n = normalizar_codigo_materia(codigo)
        asig_n = normalizar_clave(asignatura)
        if not codigo_n or not asig_n:
            continue
        if codigo_n not in grupos:
            grupos[codigo_n] = {"codigo": codigo, "asignaturas": {}, "filas": []}
        grupos[codigo_n]["asignaturas"].setdefault(asig_n, asignatura)
        grupos[codigo_n]["filas"].append(int(idx) + 1)
    for codigo_n, data in grupos.items():
        if len(data["asignaturas"]) > 1:
            registros.append({
                "codigo": data["codigo"],
                "asignaturas_detectadas": " / ".join(data["asignaturas"].values()),
                "filas": ", ".join(map(str, data["filas"])),
                "motivo": "Mismo código con nombres distintos dentro de la tabla pegada",
            })
    return pd.DataFrame(registros)


# --- carga rapida de plan (tabla pegada) -----------------------------------------------------------------------
def normalizar_columnas_plan_pegado(df):
    renombres = {}
    for col in df.columns:
        clave = str(col).strip().lower()
        clave = clave.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        clave = clave.replace(".", "").replace(" ", "_")
        if clave in ["codigo", "cod", "cod_materia", "codigo_materia"]:
            renombres[col] = "codigo"
        elif clave in ["asignatura", "materia", "nombre", "nombre_materia"]:
            renombres[col] = "asignatura"
        elif clave in ["anio", "ano", "año", "ano_carrera", "año_carrera"]:
            renombres[col] = "anio"
        elif clave in ["cuatrimestre", "cuat", "semestre"]:
            renombres[col] = "cuatrimestre"
        elif clave in ["dictado", "modalidad"]:
            renombres[col] = "dictado"
        elif clave in ["carga_semanal", "hs_semanales", "horas_semanales", "carga_horaria_semanal"]:
            renombres[col] = "carga_semanal"
        elif clave in ["carga_total", "hs_totales", "horas_totales", "carga_horaria_total"]:
            renombres[col] = "carga_total"
        elif clave in ["duracion", "duración"]:
            renombres[col] = "duracion"
        elif clave in ["orden", "nro", "numero"]:
            renombres[col] = "orden"
    df = df.rename(columns=renombres)
    columnas_esperadas = ["codigo", "asignatura", "anio", "cuatrimestre", "dictado", "carga_semanal", "carga_total",
                          "duracion", "orden"]
    for col in columnas_esperadas:
        if col not in df.columns:
            df[col] = ""
    return df[columnas_esperadas]


def parsear_plan_pegado(texto):
    if texto is None or not str(texto).strip():
        return pd.DataFrame()
    bruto = str(texto).strip()
    try:
        df = pd.read_csv(StringIO(bruto), sep=None, engine="python")
    except Exception:
        df = pd.read_csv(StringIO(bruto), sep="\\t")
    columnas = [str(c).lower() for c in df.columns]
    tiene_encabezado_util = any(
        any(palabra in col for palabra in ["codigo", "asignatura", "materia", "anio", "año", "cuatrimestre"])
        for col in columnas
    )
    if not tiene_encabezado_util:
        df = pd.read_csv(StringIO(bruto), sep=None, engine="python", header=None, dtype=str, keep_default_na=False)
        nombres = ["codigo", "asignatura", "anio", "cuatrimestre", "dictado", "carga_semanal", "carga_total", "duracion"]
        df = df.iloc[:, :len(nombres)]
        df.columns = nombres[:len(df.columns)]
    df = normalizar_columnas_plan_pegado(df)

    def limpiar_texto(valor):
        if pd.isna(valor):
            return ""
        txt = str(valor).strip()
        return "" if txt.lower() in ["nan", "none"] else txt

    for col in df.columns:
        df[col] = df[col].apply(limpiar_texto)
    df["anio"] = df["anio"].replace({
        "1": "1° Año", "1.0": "1° Año", "1 año": "1° Año", "1°": "1° Año",
        "2": "2° Año", "2.0": "2° Año", "2 año": "2° Año", "2°": "2° Año",
        "3": "3° Año", "3.0": "3° Año", "3 año": "3° Año", "3°": "3° Año",
        "4": "4° Año", "4.0": "4° Año", "4 año": "4° Año", "4°": "4° Año",
        "5": "5° Año", "5.0": "5° Año", "5 año": "5° Año", "5°": "5° Año",
        "6": "6° Año", "6.0": "6° Año", "6 año": "6° Año", "6°": "6° Año",
    })
    df["cuatrimestre"] = df["cuatrimestre"].replace({
        "1.0": "1",
        "2.0": "2",
        "1 y 2": "1 y 2",
        "anual": "1 y 2",
        "Anual": "1 y 2",
    })
    df["dictado"] = df["dictado"].replace("", "Presencial")
    df["duracion"] = df["duracion"].replace("", "Cuatrimestral")
    df["estado"] = "Activa"
    df["observaciones"] = ""
    df["carga_semanal"] = pd.to_numeric(df["carga_semanal"], errors="coerce").fillna(0).astype(int)
    df["carga_total"] = pd.to_numeric(df["carga_total"], errors="coerce").fillna(0).astype(int)
    df["orden"] = pd.to_numeric(df["orden"], errors="coerce")
    df = df[df["asignatura"].astype(str).str.strip() != ""].copy()
    return df


# --- Excel v124 (lectura) --------------------------------------------------------------------------------------
def leer_excel_carga_rapida_opciones_v124(contenido):
    if not contenido:
        return pd.DataFrame()
    try:
        df = pd.read_excel(BytesIO(contenido), sheet_name="Carga rápida", engine="openpyxl", dtype=str)
    except ValueError:
        df = pd.read_excel(BytesIO(contenido), sheet_name=0, engine="openpyxl", dtype=str)
    if df is None or df.empty:
        return pd.DataFrame()
    renombres = {}
    for col in df.columns:
        k = normalizar_encabezado_opcion_v124(col)
        if k in ["tipo"]:
            renombres[col] = "tipo"
        elif k in ["codigo_de_la_opcion", "codigo_opcion", "codigo"]:
            renombres[col] = "codigo"
        elif k in ["materia_concreta_que_se_ofrece", "materia_concreta", "opcion_concreta", "nombre", "materia"]:
            renombres[col] = "nombre"
        # 6A-B3: encabezado del modelo actual ("Unidad académica oferente"); los históricos se siguen aceptando
        elif k in ["unidad_academica_oferente", "facultad_escuela_oferente", "escuela_oferente", "facultad_oferente"]:
            renombres[col] = "escuela_oferente"
        elif k == "estado":
            renombres[col] = "estado"
        elif k in ["observaciones", "observacion"]:
            renombres[col] = "observaciones"
        else:
            m = re.fullmatch(r"habilitacion_?(\d+)", k)
            if m:
                renombres[col] = f"habilitacion_{int(m.group(1))}"
    df = df.rename(columns=renombres)
    obligatorias = ["tipo", "nombre"]
    faltantes = [c for c in obligatorias if c not in df.columns]
    if faltantes:
        raise ValueError("El Excel no contiene las columnas obligatorias: " + ", ".join(faltantes) + ".")
    for col in ["codigo", "escuela_oferente", "estado", "observaciones"]:
        if col not in df.columns:
            df[col] = ""
    habs = sorted([c for c in df.columns if re.fullmatch(r"habilitacion_\d+", str(c))],
                  key=lambda x: int(x.split("_")[-1]))
    columnas = ["tipo", "codigo", "nombre", "escuela_oferente", "estado", "observaciones"] + habs
    df = df[columnas].copy()
    for col in columnas:
        df[col] = df[col].apply(limpiar_texto_tabla)
    df = df[df.apply(lambda r: any(str(v).strip() for v in r.tolist()), axis=1)].reset_index(drop=True)
    return df


def buscar_opcion_equivalente_v124(df_ops, tipo, codigo, nombre, escuela_oferente=""):
    if df_ops is None or df_ops.empty:
        return pd.DataFrame()
    tipo_n = normalizar_tipo_opcion_v120(tipo)
    cod_n = normalizar_codigo_materia(codigo)
    nom_n = normalizar_clave(nombre)
    esc_n = normalizar_clave(escuela_oferente)
    mask = (df_ops["tipo"].apply(normalizar_tipo_opcion_v120) == tipo_n) & \
        (df_ops["nombre"].apply(normalizar_clave) == nom_n)
    if cod_n:
        mask = mask & (df_ops["codigo"].fillna("").apply(normalizar_codigo_materia) == cod_n)
    if tipo_n == "Electiva":
        mask = mask & (df_ops["escuela_oferente"].fillna("").apply(normalizar_clave) == esc_n)
    return df_ops[mask].copy()


# --- unidades académicas (6A-B3: fuente común de Disposiciones y del Resumen docente) -------------------------
# ``formatear_nombre_escuela`` es ``domain/materias.py`` certificado + la regla 6A-B3 para denominaciones
# institucionales completas; la copia certificada literal (``analisis.motor.ref``) se conserva para comparación.
_MAPA_ESCUELAS = {
    "administracion": "Escuela de Administración",
    "administración": "Escuela de Administración",
    "escuela administracion": "Escuela de Administración",
    "escuela de administracion": "Escuela de Administración",
    "escuela de administración": "Escuela de Administración",
    "ciencias juridicas politicas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
    "ciencias jurídicas políticas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
    "ciencias juridicas, politicas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
    "ciencias jurídicas, políticas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
    "escuela ciencias juridicas politicas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
    "escuela de ciencias juridicas politicas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
    "escuela de ciencias jurídicas políticas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
    "cs tecnologicas": "Escuela de Ciencias Tecnológicas",
    "cs tecnológicas": "Escuela de Ciencias Tecnológicas",
    "ciencias tecnologicas": "Escuela de Ciencias Tecnológicas",
    "ciencias tecnológicas": "Escuela de Ciencias Tecnológicas",
    "escuela cs tecnologicas": "Escuela de Ciencias Tecnológicas",
    "escuela cs tecnológicas": "Escuela de Ciencias Tecnológicas",
    "escuela de cs tecnologicas": "Escuela de Ciencias Tecnológicas",
    "escuela de cs tecnológicas": "Escuela de Ciencias Tecnológicas",
    "escuela ciencias tecnologicas": "Escuela de Ciencias Tecnológicas",
    "escuela ciencias tecnológicas": "Escuela de Ciencias Tecnológicas",
    "escuela de ciencias tecnologicas": "Escuela de Ciencias Tecnológicas",
    "escuela de ciencias tecnológicas": "Escuela de Ciencias Tecnológicas",
    "humanidades": "Escuela de Humanidades",
    "escuela humanidades": "Escuela de Humanidades",
    "escuela de humanidades": "Escuela de Humanidades",
    "salud": "Escuela de Salud",
    "escuela salud": "Escuela de Salud",
    "escuela de salud": "Escuela de Salud",
}


# 6A-B3: denominaciones institucionales que ya traen su tipo ("Facultad de Ingeniería", "Instituto de ...").
# Se comparan sin tildes ni puntos contra la(s) primera(s) palabra(s) del valor almacenado.
_TIPOS_UNIDAD_ACADEMICA = (
    "facultad", "escuela", "instituto", "departamento", "depto", "dpto", "centro", "unidad academica", "secretaria",
    "area", "direccion", "coordinacion", "colegio", "universidad", "rectorado", "vicerrectorado", "sede", "division",
)


def _sin_tildes(txt: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn")


def es_denominacion_institucional(valor: Any) -> bool:
    """True si el texto ya empieza por un tipo de unidad académica/dependencia (no hay que anteponer "Escuela de")."""
    clave = " ".join(_sin_tildes(str(valor or "")).lower().replace(".", " ").split())
    return any(clave == t or clave.startswith(t + " ") for t in _TIPOS_UNIDAD_ACADEMICA)


def formatear_nombre_escuela(valor: Any) -> str:
    """Toda escuela figura como "Escuela de ...", salvo Posgrado.

    6A-B3: si el valor ya es una denominación institucional completa ("Facultad de ...", "Instituto de ...",
    "Departamento de ..."), se respeta tal cual. Los nombres simples históricos de UNO no cambian.
    """
    if valor is None or pd.isna(valor):
        return ""
    txt = " ".join(str(valor).strip().split())
    if not txt:
        return ""
    txt_lower = txt.lower()
    if "posgrado" in txt_lower:
        return "Posgrado"
    clave = txt_lower.replace(".", "").replace("-", " ").replace(",", " ")
    clave = " ".join(clave.split())
    if clave in _MAPA_ESCUELAS:
        return _MAPA_ESCUELAS[clave]
    if txt_lower.startswith("escuela de ") or txt_lower.startswith("escuela "):
        return txt.replace("Cs. Tecnológicas", "Ciencias Tecnológicas")
    if es_denominacion_institucional(txt):
        return txt
    return f"Escuela de {txt.replace('Cs. Tecnológicas', 'Ciencias Tecnológicas')}"


def presentar_unidades_academicas(valor: Any) -> str:
    """Varias unidades unidas por " | " o " / " (tablas del Resumen docente): cada una con ``formatear_nombre_escuela``."""
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return ""
    partes = re.split(r"( \| | / )", " ".join(str(valor).split()))
    return "".join(p if i % 2 else formatear_nombre_escuela(p) for i, p in enumerate(partes))
