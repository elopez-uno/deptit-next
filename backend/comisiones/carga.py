"""Carga rapida de comisiones (pestaña 5), copiada de la fuente efectiva de B13-FIX02.

Origen (reference_fix02, entry): ``parsear_comisiones_pegadas`` l. 20215, ``normalizar_columnas_comisiones_pegadas``
l. 19323, ``leer_tabla_pegada`` l. 16548, ``leer_excel_integral_comisiones_v149`` l. 31923,
``buscar_materia_para_comision_rapida`` l. 20278, ``buscar_docente_para_comision_rapida`` l. 20509,
``validar_docentes_comision_rapida`` v153 l. 29463, ``preparar_preview_comisiones_rapidas`` l. 20605,
``_firma_fuente_carga_comisiones_v232`` l. 52147 y ``cargar_comisiones_rapidas_lote_v232`` l. 52236 (rama PostgreSQL).
Cargo automatico: ``obtener_cargo_prioritario_docente_periodo`` v200 (mapa de Designaciones, sin modificarlo) con el
``motivo`` certificado.  Las caches de sesion v232 no cambian el resultado: la vista previa se recalcula fresca.
"""

from __future__ import annotations

import hashlib
import re
import time
from io import BytesIO, StringIO
from typing import Any, Optional

import pandas as pd

from designaciones import escrituras as DE
from designaciones.repository import _numeric
from docentes.carga import leer_tabla_pegada, normalizar_columna_generica

from . import rules as R
from .lecturas import Lector

COLUMNAS_PREVIEW = [
    "estado_validacion", "motivo", "advertencia", "clave_generada", "codigos_comision", "codigo", "asignatura",
    "opcion_curricular", "comision", "turno", "resumen_horarios", "resumen_docentes", "materia_encontrada", "modalidad",
    "sede", "estado",
]
ESTADOS_CARGABLES = ("OK", "ADVERTENCIA")
OBS_AUTO_CARGA = "Cargado automáticamente desde carga rápida de comisiones."


# ------------------------------------------------------------------------------------------ lectura de la fuente
def normalizar_columnas_comisiones_pegadas(df):
    """l. 19323: Codigo/Asignatura/Carrera-plan N, Dia/Hora N, Docente/Cargo N y coberturas v153."""
    renombres = {}
    indices_horarios = set()
    indices_docentes = set()
    indices_materias_adicionales = set()
    horarios_por_docente = set()  # pares (n_docente, n_horario)

    for col in df.columns:
        clave = normalizar_columna_generica(col)
        clave = clave.replace("(", "_").replace(")", "")
        while "__" in clave:
            clave = clave.replace("__", "_")
        clave = clave.strip("_")

        m_codigo_extra = re.fullmatch(r"(?:codigo|cod|codigo_materia|cod_materia)_?(\d+)", clave)
        m_asig_extra = re.fullmatch(r"(?:asignatura|materia|nombre_materia)_?(\d+)", clave)
        m_contexto_extra = re.fullmatch(r"(?:carrera_plan|plan_carrera|contexto_plan|carrera)_?(\d+)", clave)

        if clave in ["codigo", "cod", "codigo_materia", "cod_materia"]:
            renombres[col] = "codigo"
        elif clave in ["asignatura", "materia", "nombre_materia"]:
            renombres[col] = "asignatura"
        elif m_codigo_extra:
            n = int(m_codigo_extra.group(1))
            if n <= 1:
                renombres[col] = "codigo"
            else:
                renombres[col] = f"codigo_{n}"
                indices_materias_adicionales.add(n)
        elif m_asig_extra:
            n = int(m_asig_extra.group(1))
            if n <= 1:
                renombres[col] = "asignatura"
            else:
                renombres[col] = f"asignatura_{n}"
                indices_materias_adicionales.add(n)
        elif clave in ["carrera_plan", "plan_carrera", "contexto_plan", "carrera"]:
            renombres[col] = "contexto_plan"
        elif m_contexto_extra:
            n = int(m_contexto_extra.group(1))
            if n <= 1:
                renombres[col] = "contexto_plan"
            else:
                renombres[col] = f"contexto_plan_{n}"
                indices_materias_adicionales.add(n)
        elif clave in ["opcion_curricular", "opcion", "materia_especifica", "materia_dictada", "opcion_concreta"]:
            renombres[col] = "opcion_curricular"
        elif clave in ["comision", "nombre_comision"]:
            renombres[col] = "comision"
        elif clave in ["turno"]:
            renombres[col] = "turno"
        elif clave in ["dictado", "modalidad"]:
            renombres[col] = "modalidad"
        elif clave in ["sede"]:
            renombres[col] = "sede"
        elif clave in ["estado", "estado_comision"]:
            renombres[col] = "estado"
        elif clave in ["observaciones", "obs", "observacion"]:
            renombres[col] = "observaciones"
        else:
            m_cubre = re.fullmatch(
                r"(?:cubre|cobertura)(?:_horario)?_?(\d+)_?(?:docente|profesor|prof)_?(\d+)",
                clave,
            )
            m_cubre_inv = re.fullmatch(
                r"(?:cubre|cobertura)_?(?:docente|profesor|prof)_?(\d+)_?(?:horario)?_?(\d+)",
                clave,
            )
            if m_cubre or m_cubre_inv:
                m_cov = m_cubre or m_cubre_inv
                if m_cubre:
                    n_h = int(m_cov.group(1)); n_doc = int(m_cov.group(2))
                else:
                    n_doc = int(m_cov.group(1)); n_h = int(m_cov.group(2))
                renombres[col] = f"cubre_docente_{n_doc}_horario_{n_h}"
                indices_docentes.add(n_doc)
                horarios_por_docente.add((n_doc, n_h))
                continue

            patrones_doc = [
                (r"dia_docente_?(\d+)_?(?:horario_?)?(\d+)", "dia"),
                (r"hora_inicio_docente_?(\d+)_?(?:horario_?)?(\d+)", "hora_inicio"),
                (r"inicio_docente_?(\d+)_?(?:horario_?)?(\d+)", "hora_inicio"),
                (r"hora_fin_docente_?(\d+)_?(?:horario_?)?(\d+)", "hora_fin"),
                (r"fin_docente_?(\d+)_?(?:horario_?)?(\d+)", "hora_fin"),
            ]
            encontrado_doc = False
            for patron, tipo_h in patrones_doc:
                m = re.fullmatch(patron, clave)
                if m:
                    n_doc = int(m.group(1)); n_h = int(m.group(2))
                    renombres[col] = f"{tipo_h}_docente_{n_doc}_horario_{n_h}"
                    indices_docentes.add(n_doc)
                    horarios_por_docente.add((n_doc, n_h))
                    encontrado_doc = True
                    break
            if encontrado_doc:
                continue

            m_dia = re.fullmatch(r"dia_?(\d+)", clave)
            m_hi = re.fullmatch(r"hora_inicio_?(\d+)|inicio_?(\d+)|hora_desde_?(\d+)|desde_?(\d+)", clave)
            m_hf = re.fullmatch(r"hora_fin_?(\d+)|fin_?(\d+)|hora_hasta_?(\d+)|hasta_?(\d+)", clave)
            m_doc = re.fullmatch(r"docente_?(\d+)|profesor_?(\d+)|prof_?(\d+)", clave)
            m_rol = re.fullmatch(r"cargo_?(\d+)(_?final)?|cargo_final_?(\d+)|rol_?(\d+)", clave)

            if m_dia:
                n = int(m_dia.group(1))
                renombres[col] = f"dia_{n}"
                indices_horarios.add(n)
            elif m_hi:
                n = int(next(g for g in m_hi.groups() if g))
                renombres[col] = f"hora_inicio_{n}"
                indices_horarios.add(n)
            elif m_hf:
                n = int(next(g for g in m_hf.groups() if g))
                renombres[col] = f"hora_fin_{n}"
                indices_horarios.add(n)
            elif m_doc:
                n = int(next(g for g in m_doc.groups() if g))
                renombres[col] = f"docente_{n}"
                indices_docentes.add(n)
            elif m_rol:
                n = int(next(g for g in m_rol.groups() if g))
                renombres[col] = f"cargo_docente_{n}"
                indices_docentes.add(n)
            # Se ignoran deliberadamente: Cupo Total y Clave Comision.

    df = df.rename(columns=renombres)

    columnas_base = ["codigo", "asignatura", "contexto_plan", "opcion_curricular", "comision", "turno", "modalidad",
                     "sede", "estado", "observaciones"]
    for col in columnas_base:
        if col not in df.columns:
            df[col] = ""

    if not indices_horarios:
        indices_horarios = {1, 2}

    columnas_horarios = []
    for n in sorted(indices_horarios):
        for col in [f"dia_{n}", f"hora_inicio_{n}", f"hora_fin_{n}"]:
            if col not in df.columns:
                df[col] = ""
            columnas_horarios.append(col)

    columnas_materias_adicionales = []
    for n in sorted(indices_materias_adicionales):
        for col in [f"codigo_{n}", f"asignatura_{n}", f"contexto_plan_{n}"]:
            if col not in df.columns:
                df[col] = ""
            columnas_materias_adicionales.append(col)

    horarios_slots_por_doc = {}
    for n_doc, n_h in horarios_por_docente:
        horarios_slots_por_doc.setdefault(n_doc, set()).add(n_h)

    columnas_docentes = []
    for n in sorted(indices_docentes):
        for col in [f"docente_{n}", f"cargo_docente_{n}"]:
            if col not in df.columns:
                df[col] = ""
            columnas_docentes.append(col)
        for n_h in sorted(horarios_slots_por_doc.get(n, set())):
            for col in [
                f"cubre_docente_{n}_horario_{n_h}",
                f"dia_docente_{n}_horario_{n_h}",
                f"hora_inicio_docente_{n}_horario_{n_h}",
                f"hora_fin_docente_{n}_horario_{n_h}",
            ]:
                if col not in df.columns:
                    df[col] = ""
                columnas_docentes.append(col)

    return df[columnas_base + columnas_materias_adicionales + columnas_horarios + columnas_docentes]


def parsear_comisiones_pegadas(texto, opciones_sedes: list):
    """l. 20215.  ``opciones_sedes`` = ``opciones_sedes_comision()`` leido fresco por quien llama."""
    df = leer_tabla_pegada(texto)
    if df.empty:
        return pd.DataFrame()

    columnas_norm = [normalizar_columna_generica(c) for c in df.columns]
    tiene_encabezado = any(c in ["codigo", "asignatura", "materia", "comision", "dia_1", "hora_inicio_1"]
                           for c in columnas_norm)

    if not tiene_encabezado:
        bruto = str(texto).strip()
        df = pd.read_csv(StringIO(bruto), sep=None, engine="python", header=None, dtype=str, keep_default_na=False)
        nombres_cols = [
            "codigo", "asignatura", "comision", "turno",
            "dia_1", "hora_inicio_1", "hora_fin_1",
            "dia_2", "hora_inicio_2", "hora_fin_2", "modalidad"
        ]
        df = df.iloc[:, :len(nombres_cols)]
        df.columns = nombres_cols[:len(df.columns)]

    df = normalizar_columnas_comisiones_pegadas(df)
    for col in df.columns:
        df[col] = df[col].apply(R.limpiar_texto_tabla)

    for col_codigo in [c for c in df.columns if c == "codigo" or re.fullmatch(r"codigo_\d+", str(c))]:
        df[col_codigo] = df[col_codigo].apply(lambda x: R.limpiar_texto_tabla(x).upper())
    df["comision"] = df["comision"].apply(lambda x: R.limpiar_texto_tabla(x).upper())
    df["turno"] = df["turno"].apply(R.normalizar_turno_comision)
    df["sede"] = df["sede"].apply(lambda x: R.normalizar_sede_comision(x, opciones_sedes))
    df["modalidad"] = df["modalidad"].apply(R.normalizar_modalidad_comision)
    df["estado"] = df["estado"].replace("", "Activa")

    for col in df.columns:
        if col.startswith("dia_"):
            df[col] = df[col].apply(lambda x: R.limpiar_texto_tabla(x).capitalize())
        elif col.startswith("hora_inicio_") or col.startswith("hora_fin_"):
            df[col] = df[col].apply(R.normalizar_hora_excel)
        elif col.startswith("cubre_docente_"):
            df[col] = df[col].apply(R.normalizar_si_no_cobertura_v153)

    for idx, fila in df.iterrows():
        if not R.limpiar_texto_tabla(fila.get("turno", "")):
            df.at[idx, "turno"] = R.inferir_turno_desde_horas_fila(fila)

    df = df[df["comision"].astype(str).str.strip() != ""].copy()
    tiene_materia = (
        df["codigo"].astype(str).str.strip().ne("")
        | df["asignatura"].astype(str).str.strip().ne("")
    )
    df = df[tiene_materia].copy()
    df["clave_generada"] = df.apply(
        lambda r: f"{R.limpiar_texto_tabla(r.get('codigo', '')) or R.limpiar_texto_tabla(r.get('asignatura', ''))} | "
                  f"{R.limpiar_texto_tabla(r.get('comision', ''))}",
        axis=1,
    )
    return df.reset_index(drop=True)


def leer_excel_integral_comisiones_v149(contenido: bytes, opciones_sedes: list):
    """l. 31923: hoja 'Carga rápida', fila de encabezados detectada; luego el mismo parser del pegado."""
    if contenido is None:
        return pd.DataFrame()
    xls = pd.ExcelFile(BytesIO(contenido), engine="openpyxl")
    mapa = {R.normalizar_clave(nombre).replace(" ", "_"): nombre for nombre in xls.sheet_names}
    hoja = None
    for clave, nombre in mapa.items():
        if clave in {"CARGA_RÁPIDA", "CARGA_RAPIDA"} or R.normalizar_clave(nombre) in {"CARGA RÁPIDA", "CARGA RAPIDA"}:
            hoja = nombre
            break
    if hoja is None:
        raise ValueError("El archivo no contiene la hoja 'Carga rápida' del modelo de comisiones.")

    try:
        from openpyxl import load_workbook
        wb_hdr = load_workbook(BytesIO(contenido), read_only=True, data_only=False)
        ws_hdr = wb_hdr[hoja]
        fila_encabezado_excel = None
        max_scan = min(int(ws_hdr.max_row or 1), 500)
        for nro_fila, valores in enumerate(
            ws_hdr.iter_rows(min_row=1, max_row=max_scan, values_only=True),
            start=1,
        ):
            claves = {
                normalizar_columna_generica(v)
                for v in valores
                if v is not None and R.limpiar_texto_tabla(v)
            }
            if (
                "comision" in claves
                and ("codigo" in claves or "asignatura" in claves)
                and any(k.startswith("docente_") or k == "docente" for k in claves)
            ):
                fila_encabezado_excel = nro_fila
                break
        wb_hdr.close()
    except Exception:
        fila_encabezado_excel = None

    header_pd = (int(fila_encabezado_excel) - 1) if fila_encabezado_excel else 0
    df = pd.read_excel(
        BytesIO(contenido),
        sheet_name=hoja,
        engine="openpyxl",
        dtype=object,
        header=header_pd,
    )
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.dropna(how="all")
    if df.empty:
        return pd.DataFrame()

    texto = df.to_csv(index=False, sep="\t", na_rep="")
    return parsear_comisiones_pegadas(texto, opciones_sedes)


def firma_fuente(contenido: Optional[bytes] = None, texto: str = "") -> str:
    """``_firma_fuente_carga_comisiones_v232`` (l. 52147)."""
    if contenido is not None:
        return "xlsx:" + hashlib.sha256(contenido).hexdigest()
    return "txt:" + hashlib.sha256(str(texto or "").encode("utf-8", errors="ignore")).hexdigest()


# ------------------------------------------------------------------------------------------ vista previa
class Validador:
    """Validaciones de la vista previa contra lecturas frescas (``L``) del periodo actual."""

    def __init__(self, L: Lector, periodo_id: int):
        self.L = L
        self.periodo_id = int(periodo_id)
        self._docentes: Optional[pd.DataFrame] = None
        self._mapa_cargos: Optional[dict] = None
        self._sedes: Optional[list] = None

    def opciones_sedes(self) -> list:
        if self._sedes is None:
            self._sedes = self.L.opciones_sedes_comision()
        return self._sedes

    # l. 20278
    def buscar_materia_para_comision_rapida(self, codigo, asignatura="", contexto_plan=""):
        df = self.L.materias_para_comisiones()
        if df.empty:
            return {
                "estado": "ERROR",
                "motivo": "No hay materias cargadas en la fuente única de planes de esta universidad.",
                "materia": None,
                "advertencia": ""
            }

        df = df.copy()
        codigo_limpio = R.limpiar_texto_tabla(codigo)
        if codigo_limpio.startswith("=") or codigo_limpio.strip() in {"0", "0.0"}:
            codigo_limpio = ""
        asignatura_limpia = R.limpiar_texto_tabla(asignatura)
        contexto_limpio = R.limpiar_texto_tabla(contexto_plan)

        m_codigo_prefijo = re.match(r"^\[([^\]]+)\]\s*(.*)$", contexto_limpio)
        if m_codigo_prefijo:
            codigo_desde_contexto = R.limpiar_texto_tabla(m_codigo_prefijo.group(1)).upper()
            if not codigo_limpio and codigo_desde_contexto:
                codigo_limpio = codigo_desde_contexto
            contexto_limpio = R.limpiar_texto_tabla(m_codigo_prefijo.group(2))
            contexto_limpio = re.sub(r"\s+—\s+Grupo\s+\d+\s*$", "", contexto_limpio, flags=re.I).strip()
        else:
            m_codigo_ctx = re.search(r"\s+—\s+C[oó]digo\s*:?[ ]*([^—]+?)(?:\s+—\s+Grupo\s+\d+)?\s*$", contexto_limpio,
                                     flags=re.I)
            if m_codigo_ctx:
                codigo_desde_contexto = R.limpiar_texto_tabla(m_codigo_ctx.group(1)).upper()
                if not codigo_limpio and codigo_desde_contexto:
                    codigo_limpio = codigo_desde_contexto
                contexto_limpio = re.sub(
                    r"\s+—\s+C[oó]digo\s*:?[ ]*[^—]+?(?:\s+—\s+Grupo\s+\d+)?\s*$",
                    "",
                    contexto_limpio,
                    flags=re.I,
                ).strip()
            else:
                contexto_limpio = re.sub(r"\s+—\s+Grupo\s+\d+\s*$", "", contexto_limpio, flags=re.I).strip()

        codigo_key = R.normalizar_codigo_materia(codigo_limpio)
        asignatura_n = R.normalizar_clave(asignatura_limpia)
        contexto_n = R.normalizar_clave(contexto_limpio)

        df["_codigo_key"] = df["codigo"].apply(R.normalizar_codigo_materia)
        df["_contexto_plan"] = df.apply(
            lambda r: " — ".join([
                x for x in [
                    R.limpiar_texto_tabla(r.get("carrera", "")),
                    R.limpiar_texto_tabla(r.get("plan_version", "")),
                    R.limpiar_texto_tabla(r.get("escuela", "")),
                ] if x
            ]),
            axis=1,
        )

        def filtrar_contexto(candidatos):
            if candidatos is None or candidatos.empty or not contexto_n:
                return candidatos
            norm = candidatos["_contexto_plan"].fillna("").astype(str).apply(R.normalizar_clave)
            exactos = candidatos[norm == contexto_n].copy()
            if not exactos.empty:
                return exactos
            parciales = candidatos[norm.apply(lambda x: contexto_n in x or x in contexto_n)].copy()
            return parciales

        def error_ambiguo(candidatos):
            contextos = R.deptit_join_unicos(candidatos.get("_contexto_plan", pd.Series(dtype=str)), sep=" / ")
            return {
                "estado": "ERROR",
                "motivo": (
                    "El código y nombre corresponden a más de un grupo de planes. "
                    "Completá la columna 'Carrera / plan' para indicar cuál querés usar."
                    + (f" Opciones: {contextos}." if contextos else "")
                ),
                "materia": None,
                "advertencia": ""
            }

        if codigo_key:
            candidatos_codigo = df[df["_codigo_key"] == codigo_key].copy()
            if not candidatos_codigo.empty:
                candidatos_codigo_ctx = filtrar_contexto(candidatos_codigo)
                if contexto_n and candidatos_codigo_ctx.empty:
                    return {
                        "estado": "ERROR",
                        "motivo": f"El código {codigo_limpio} existe, pero no en la Carrera / plan indicada: {contexto_limpio}.",
                        "materia": None,
                        "advertencia": ""
                    }
                candidatos_codigo = candidatos_codigo_ctx

                if asignatura_n:
                    candidatos_codigo["similitud_asignatura"] = candidatos_codigo["asignatura"].apply(
                        lambda x: R.similitud_texto(x, asignatura_limpia)
                    )
                    compatibles = candidatos_codigo[candidatos_codigo["similitud_asignatura"] >= 0.82].copy()
                    if compatibles.empty:
                        asignaturas_codigo = " / ".join(
                            candidatos_codigo["asignatura"].dropna().astype(str).drop_duplicates().tolist())
                        return {
                            "estado": "ERROR",
                            "motivo": f"El código existe en la fuente única, pero la asignatura no coincide. Código {codigo_limpio} figura como: {asignaturas_codigo}.",
                            "materia": None,
                            "advertencia": ""
                        }
                    if len(compatibles) > 1 and not contexto_n:
                        nombres_norm = compatibles["asignatura"].fillna("").astype(str).apply(R.normalizar_clave).nunique()
                        if nombres_norm == 1:
                            return error_ambiguo(compatibles)
                    mejor = compatibles.sort_values(["similitud_asignatura", "materia_id"],
                                                    ascending=[False, True]).iloc[0].to_dict()
                    advertencia = ""
                    if len(compatibles) > 1:
                        carreras = " / ".join(compatibles["carrera"].dropna().astype(str).drop_duplicates().tolist())
                        advertencia = f"Hay más de una aparición compatible: {carreras}."
                    return {"estado": "OK", "motivo": "Código y asignatura validados contra la fuente única.",
                            "materia": mejor, "advertencia": advertencia}

                if len(candidatos_codigo) > 1 and not contexto_n:
                    return error_ambiguo(candidatos_codigo)
                mejor = candidatos_codigo.sort_values(["materia_id"], kind="stable").iloc[0].to_dict()
                advertencia = "Asignatura vacía: se usó solo el código validado contra la fuente única."
                return {"estado": "OK", "motivo": "Materia encontrada por código en la fuente única.", "materia": mejor,
                        "advertencia": advertencia}

        if asignatura_n:
            df2 = filtrar_contexto(df.copy())
            if contexto_n and df2.empty:
                return {
                    "estado": "ERROR",
                    "motivo": f"No hay materias disponibles para la Carrera / plan indicada: {contexto_limpio}.",
                    "materia": None,
                    "advertencia": ""
                }
            df2["similitud_asignatura"] = df2["asignatura"].apply(lambda x: R.similitud_texto(x, asignatura_limpia))
            candidatos_asig = df2[df2["similitud_asignatura"] >= 0.90].copy()
            if not candidatos_asig.empty:
                max_sim = float(candidatos_asig["similitud_asignatura"].max())
                mejores = candidatos_asig[candidatos_asig["similitud_asignatura"] >= max_sim - 1e-9].copy()
                if len(mejores) > 1 and not contexto_n:
                    nombres_norm = mejores["asignatura"].fillna("").astype(str).apply(R.normalizar_clave).nunique()
                    if nombres_norm == 1:
                        return error_ambiguo(mejores)
                mejor = mejores.sort_values(["materia_id"], kind="stable").iloc[0].to_dict()
                advertencia = "No se encontró por código; se vinculó por asignatura contra la fuente única. Revisar antes de cargar."
                if codigo_limpio:
                    advertencia += f" Código pegado no encontrado: {codigo_limpio}."
                return {"estado": "ADVERTENCIA", "motivo": "Materia encontrada por asignatura, no por código.",
                        "materia": mejor, "advertencia": advertencia}

        return {
            "estado": "ERROR",
            "motivo": "No se encontró materia cargada con ese código ni una asignatura equivalente en la fuente única de planes.",
            "materia": None,
            "advertencia": ""
        }

    def docentes_activos(self) -> pd.DataFrame:
        if self._docentes is None:
            self._docentes = self.L.docentes_activos_para_comisiones(self.periodo_id)
        return self._docentes

    # l. 20509
    def buscar_docente_para_comision_rapida(self, nombre_docente):
        nombre_docente = R.limpiar_texto_tabla(nombre_docente)
        if not nombre_docente:
            return {"estado": "VACIO", "motivo": "Docente vacío", "docente": None, "advertencia": ""}

        df = self.docentes_activos()
        if df.empty:
            return {"estado": "ERROR", "motivo": "No hay docentes activos en el período actual.", "docente": None,
                    "advertencia": ""}

        df = df.copy()
        nombre_n = R.normalizar_clave(nombre_docente)
        df["_nombre_n"] = df["nombre_completo"].apply(R.normalizar_clave)

        exactos = df[df["_nombre_n"] == nombre_n].copy()
        if len(exactos) == 1:
            return {"estado": "OK", "motivo": "Docente encontrado por nombre exacto.", "docente": exactos.iloc[0].to_dict(),
                    "advertencia": ""}
        if len(exactos) > 1:
            opciones = " / ".join(exactos["nombre_completo"].astype(str).tolist())
            return {"estado": "ERROR", "motivo": f"Hay más de un docente con ese nombre: {opciones}.", "docente": None,
                    "advertencia": ""}

        df["similitud_docente"] = df["nombre_completo"].apply(lambda x: R.similitud_texto(x, nombre_docente))
        candidatos = df[df["similitud_docente"] >= 0.92].sort_values(["similitud_docente", "nombre_completo"],
                                                                     ascending=[False, True]).copy()

        if len(candidatos) == 1:
            docente = candidatos.iloc[0].to_dict()
            return {
                "estado": "ADVERTENCIA",
                "motivo": "Docente encontrado por similitud, no por coincidencia exacta.",
                "docente": docente,
                "advertencia": f"Se interpretó '{nombre_docente}' como '{docente['nombre_completo']}'."
            }

        if len(candidatos) > 1:
            opciones = " / ".join(candidatos["nombre_completo"].astype(str).head(5).tolist())
            return {"estado": "ERROR", "motivo": f"Coincidencia ambigua para docente '{nombre_docente}': {opciones}.",
                    "docente": None, "advertencia": ""}

        return {"estado": "ERROR", "motivo": f"No se encontró docente activo para '{nombre_docente}'.", "docente": None,
                "advertencia": ""}

    def obtener_cargo_prioritario(self, cuil) -> dict:
        """v200 (l. 46666) con el ``motivo`` certificado; un CUIL fuera del mapa cae en el fallback historico."""
        cuil_limpio = R.limpiar_cuil(cuil)
        if not cuil_limpio or self.periodo_id is None:
            return {"cargo": "", "departamento": "", "motivo": "Falta CUIL o período."}
        if self._mapa_cargos is None:
            self._mapa_cargos = DE.mapa_cargos_prioritarios(self.L.repo, self.periodo_id, int(self.L.repo.dep))
        dato = self._mapa_cargos.get(R.clave_cuil(cuil_limpio))
        if dato is None:
            return {"cargo": "", "departamento": "",
                    "motivo": "No se encontró una designación activa para el período de la comisión."}
        cargo = str(dato.get("cargo") or "")
        departamento = str(dato.get("departamento") or "")
        if not cargo:
            motivo = (f"No se encontró una designación activa en {departamento} para el período de la comisión."
                      if departamento else "No se encontró designación activa.")
        else:
            motivo = f"Cargo activo de {departamento}." if departamento else "Cargo activo detectado."
        return {"cargo": cargo, "departamento": departamento, "motivo": motivo}

    # v153 l. 29463
    def validar_docentes_comision_rapida(self, row, horarios_comision=None):
        docentes_crudos = R.docentes_desde_fila_comision(row)
        errores = []
        advertencias = []
        docentes = []
        vistos = set()

        horarios_base = list(horarios_comision or [])
        df_horarios_base = pd.DataFrame(horarios_base)
        base_por_slot = {}
        horas_total_comision = 0.0
        for h in horarios_base:
            try:
                n_base = int(h.get("n"))
                base_por_slot[n_base] = h
            except Exception:
                pass
            horas_total_comision += R.calcular_horas_desde_texto(
                h.get("hora_inicio", ""), h.get("hora_fin", "")
            )

        for d in docentes_crudos:
            n = d["n"]
            nombre = R.limpiar_texto_tabla(d.get("docente", ""))
            rol_original = R.limpiar_texto_tabla(d.get("rol", ""))
            horarios_raw = d.get("horarios_reales")
            cobertura_slots = d.get("cobertura_slots")

            if not nombre and (rol_original or horarios_raw or cobertura_slots):
                errores.append(f"Docente {n} vacío con cargo/rol o cobertura horaria cargada")
                continue
            if not nombre:
                continue

            busqueda = self.buscar_docente_para_comision_rapida(nombre)
            if busqueda["estado"] == "ERROR":
                errores.append(f"Docente {n}: {busqueda['motivo']}")
                continue
            if busqueda["estado"] == "ADVERTENCIA":
                advertencias.append(
                    f"Docente {n}: {busqueda.get('advertencia') or busqueda.get('motivo')}"
                )

            docente = busqueda.get("docente")
            if not docente:
                continue

            rol = rol_original
            rol_n = R.normalizar_clave(rol)
            requiere_cargo_automatico = not rol or rol_n in {"REVISAR CARGO", "SIN ESPECIFICAR"}
            if requiere_cargo_automatico:
                resultado_cargo = self.obtener_cargo_prioritario(docente["cuil"])
                rol = R.limpiar_texto_tabla(resultado_cargo.get("cargo", ""))
                if not rol:
                    errores.append(
                        f"Docente {n}: no se pudo completar el cargo automáticamente. "
                        f"{resultado_cargo.get('motivo', 'Revisá su designación activa.')}"
                    )
                    continue
                dep_txt = R.limpiar_texto_tabla(resultado_cargo.get("departamento", ""))
                origen = f" desde {dep_txt}" if dep_txt else ""
                advertencias.append(
                    f"Docente {n}: se tomó automáticamente el cargo '{rol}'{origen} "
                    "por ser el de mayor jerarquía de su designación activa."
                )

            clave = (R.limpiar_cuil(docente["cuil"]), R.normalizar_clave(rol))
            if clave in vistos:
                errores.append(f"Docente {n} duplicado dentro de la fila con el mismo cargo/rol")
                continue
            vistos.add(clave)

            horarios_validados = None
            horas_reales = round(float(horas_total_comision or 0), 2)

            if cobertura_slots is not None:
                franjas = []
                vistos_h = set()

                for slot in cobertura_slots:
                    try:
                        nh = int(slot.get("n"))
                    except Exception:
                        continue

                    base = base_por_slot.get(nh)
                    estado = R.normalizar_si_no_cobertura_v153(slot.get("cubre", ""))
                    dia_raw = R.limpiar_texto_tabla(slot.get("dia", ""))
                    hi_raw = R.limpiar_texto_tabla(slot.get("hora_inicio", ""))
                    hf_raw = R.limpiar_texto_tabla(slot.get("hora_fin", ""))

                    if not estado and base is not None:
                        estado = "Sí"

                    if estado not in {"Sí", "No", ""}:
                        errores.append(
                            f"Docente {n}, horario {nh}: valor de cobertura inválido '{estado}'. Usá Sí o No."
                        )
                        continue

                    if estado == "No":
                        if hi_raw or hf_raw:
                            errores.append(
                                f"Docente {n}, horario {nh}: figura 'No' pero tiene horas propias cargadas"
                            )
                        continue

                    if estado != "Sí":
                        continue

                    if base is None:
                        errores.append(
                            f"Docente {n}, horario {nh}: figura 'Sí' pero no existe el Horario {nh} general de la comisión"
                        )
                        continue

                    dia_base = R.normalizar_dia_v95(base.get("dia", ""))
                    hi_base = R.hora_texto_v95(base.get("hora_inicio", ""))
                    hf_base = R.hora_texto_v95(base.get("hora_fin", ""))

                    dia = R.normalizar_dia_v95(dia_raw) if dia_raw else dia_base
                    if dia_raw and dia != dia_base:
                        errores.append(
                            f"Docente {n}, horario {nh}: el día {dia} no coincide con el horario general {nh} ({dia_base})"
                        )
                        continue

                    if not hi_raw and not hf_raw:
                        hi, hf = hi_base, hf_base
                    elif not hi_raw or not hf_raw:
                        errores.append(
                            f"Docente {n}, horario {nh}: para una cobertura parcial completá Hora Inicio y Hora Fin"
                        )
                        continue
                    else:
                        hi = R.hora_texto_v95(hi_raw)
                        hf = R.hora_texto_v95(hf_raw)

                    if not dia or not hi or not hf:
                        errores.append(f"Docente {n}, horario {nh}: cobertura incompleta")
                        continue

                    a, b = R.minutos_v95(hi), R.minutos_v95(hf)
                    if a is None or b is None or b <= a:
                        errores.append(f"Docente {n}, horario {nh}: franja inválida {hi}-{hf}")
                        continue

                    if df_horarios_base.empty or not R.es_subintervalo_v95(dia, hi, hf, df_horarios_base):
                        errores.append(
                            f"Docente {n}, horario {nh}: {dia} {hi}-{hf} queda fuera del horario general de la comisión"
                        )
                        continue

                    firma = (R.normalizar_clave(dia), hi, hf)
                    if firma in vistos_h:
                        errores.append(f"Docente {n}, horario {nh}: franja duplicada")
                        continue
                    vistos_h.add(firma)
                    franjas.append({"dia": dia, "hora_inicio": hi, "hora_fin": hf})

                horas_reales = round(sum(
                    R.calcular_horas_desde_texto(h.get("hora_inicio", ""), h.get("hora_fin", ""))
                    for h in franjas
                ), 2)

                if horas_reales <= 0:
                    errores.append(
                        f"Docente {n}: quedó asignado a la comisión pero no cubre ningún horario"
                    )
                    horarios_validados = []
                else:
                    firmas_base = {
                        (
                            R.normalizar_clave(R.normalizar_dia_v95(h.get("dia", ""))),
                            R.hora_texto_v95(h.get("hora_inicio", "")),
                            R.hora_texto_v95(h.get("hora_fin", "")),
                        )
                        for h in horarios_base
                        if h.get("dia") and h.get("hora_inicio") and h.get("hora_fin")
                    }
                    firmas_doc = {
                        (R.normalizar_clave(h["dia"]), h["hora_inicio"], h["hora_fin"])
                        for h in franjas
                    }
                    horarios_validados = None if firmas_doc == firmas_base else franjas

            elif horarios_raw is not None:
                horarios_validados = []
                vistos_h = set()
                for h in horarios_raw:
                    nh = h.get("n", "")
                    dia = R.normalizar_dia_v95(h.get("dia", ""))
                    hi = R.hora_texto_v95(h.get("hora_inicio", ""))
                    hf = R.hora_texto_v95(h.get("hora_fin", ""))
                    if not dia or not hi or not hf:
                        errores.append(f"Docente {n}, horario {nh}: cobertura incompleta")
                        continue
                    if dia not in R.DIAS_SEMANA:
                        errores.append(f"Docente {n}, horario {nh}: día inválido ({dia})")
                        continue
                    a, b = R.minutos_v95(hi), R.minutos_v95(hf)
                    if a is None or b is None or b <= a:
                        errores.append(f"Docente {n}, horario {nh}: franja inválida {hi}-{hf}")
                        continue
                    if df_horarios_base.empty or not R.es_subintervalo_v95(dia, hi, hf, df_horarios_base):
                        errores.append(
                            f"Docente {n}, horario {nh}: {dia} {hi}-{hf} queda fuera del horario general de la comisión"
                        )
                        continue
                    firma = (R.normalizar_clave(dia), hi, hf)
                    if firma in vistos_h:
                        errores.append(f"Docente {n}, horario {nh}: franja duplicada")
                        continue
                    vistos_h.add(firma)
                    horarios_validados.append({"dia": dia, "hora_inicio": hi, "hora_fin": hf})

                if horarios_raw and not horarios_validados:
                    errores.append(f"Docente {n}: no quedó ninguna cobertura horaria válida")
                horas_reales = round(sum(
                    R.calcular_horas_desde_texto(h.get("hora_inicio", ""), h.get("hora_fin", ""))
                    for h in (horarios_validados or [])
                ), 2)
                if horas_reales <= 0:
                    errores.append(
                        f"Docente {n}: la cobertura horaria personalizada debe tener una duración mayor a 0"
                    )

            docentes.append({
                "n": n,
                "cuil": R.limpiar_cuil(docente["cuil"]),
                "docente": docente["nombre_completo"],
                "rol": rol,
                "horas_designadas": docente.get("horas_designadas", 0),
                "horarios_reales": horarios_validados,
                "horas_reales": horas_reales,
            })

        return errores, advertencias, docentes

    # l. 20605
    def preparar_preview_comisiones_rapidas(self, df_comisiones):
        L = self.L
        periodo_id = self.periodo_id
        if df_comisiones is None or df_comisiones.empty:
            return pd.DataFrame()

        registros, vistas = [], set()
        for idx, row in df_comisiones.iterrows():
            codigo = R.limpiar_texto_tabla(row.get("codigo", "")).upper()
            comision = R.limpiar_texto_tabla(row.get("comision", "")).upper()
            opcion_raw = R.limpiar_texto_tabla(row.get("opcion_curricular", ""))

            busqueda = self.buscar_materia_para_comision_rapida(codigo, row.get("asignatura", ""),
                                                                row.get("contexto_plan", ""))
            materia = busqueda.get("materia")
            errores_horario, horarios = R.validar_horarios_comision_rapida(row)
            errores_docentes, advertencias_docentes, docentes = self.validar_docentes_comision_rapida(
                row, horarios_comision=horarios)
            errores_catalogo = []
            errores_materias = []
            turno_fila = R.normalizar_turno_comision(row.get("turno", ""))
            modalidad_fila = R.normalizar_modalidad_comision(row.get("modalidad", ""))
            sede_fila = R.normalizar_sede_comision(row.get("sede", ""), self.opciones_sedes())
            if turno_fila not in R.TURNOS_COMISION:
                errores_catalogo.append("Turno inválido. Usá mañana, tarde o noche")
            if modalidad_fila not in R.MODALIDADES_COMISION:
                errores_catalogo.append("Modalidad inválida. Usá Presencial, Virtual o Híbrida")
            if sede_fila not in self.opciones_sedes():
                errores_catalogo.append("Sede inválida. Elegí Campus Virtual, una sede institucional cargada o Sin especificar")

            materia_id = None
            materia_ids_adicionales = []
            materia_encontrada = ""
            materias_adicionales_encontradas = []
            es_oe = False
            opcion_id = None
            opcion_nombre = ""
            opcion_estado = ""
            opcion_motivo = ""
            advertencias = [R.limpiar_texto_tabla(busqueda.get("advertencia", ""))]

            if materia is not None:
                materia_id = int(materia["materia_id"])
                materia_encontrada = R.etiqueta_materia_comision(materia)
                es_oe = R.es_materia_optativa_electiva(materia.get("codigo", ""), materia.get("asignatura", ""))
                if es_oe:
                    res_op = L.buscar_opcion_curricular_para_materia_v120(materia_id, opcion_raw)
                    opcion_estado = res_op.get("estado", "ERROR")
                    opcion_motivo = res_op.get("motivo", "")
                    op = res_op.get("opcion")
                    if op is not None:
                        opcion_id = int(op["id"])
                        opcion_nombre = R.limpiar_texto_tabla(op.get("nombre", ""))
                        if opcion_estado == "ADVERTENCIA":
                            advertencias.append(opcion_motivo)
                elif opcion_raw:
                    opcion_estado = "ERROR"
                    opcion_motivo = "La columna Opción Curricular debe quedar vacía para materias comunes."

            indices_extra = set()
            for col in row.index:
                m = re.fullmatch(r"(?:codigo|asignatura)_(\d+)", str(col))
                if m and int(m.group(1)) >= 2:
                    indices_extra.add(int(m.group(1)))
            claves_extra_vistas = set()
            for n in sorted(indices_extra):
                codigo_n = R.limpiar_texto_tabla(row.get(f"codigo_{n}", "")).upper()
                asignatura_n = R.limpiar_texto_tabla(row.get(f"asignatura_{n}", ""))
                if not codigo_n and not asignatura_n:
                    continue
                bus_n = self.buscar_materia_para_comision_rapida(codigo_n, asignatura_n, row.get(f"contexto_plan_{n}", ""))
                mat_n = bus_n.get("materia")
                if mat_n is None:
                    errores_materias.append(f"Código/materia adicional {n}: {bus_n.get('motivo', 'no encontrada')}")
                    continue
                mid_n = int(mat_n["materia_id"])
                if R.es_materia_optativa_electiva(mat_n.get("codigo", ""), mat_n.get("asignatura", "")):
                    errores_materias.append(
                        f"Código/materia adicional {n}: una Optativa/Electiva no puede mezclarse en una comisión multicódigo."
                    )
                    continue
                clave_n = (R.limpiar_texto_tabla(mat_n.get("_clave_unica", "")) or R.clave_materia_conceptual_v137(mat_n)
                           or f"ID:{mid_n}")
                if clave_n in claves_extra_vistas:
                    continue
                claves_extra_vistas.add(clave_n)
                if materia_id is not None:
                    info_principal = L.materia_comision(materia_id) or {}
                    clave_principal = (R.limpiar_texto_tabla(info_principal.get("_clave_unica", ""))
                                       or R.clave_materia_conceptual_v137(info_principal))
                    if clave_n == clave_principal:
                        continue
                materia_ids_adicionales.append(mid_n)
                materias_adicionales_encontradas.append(R.etiqueta_materia_comision(mat_n))
                adv_n = R.limpiar_texto_tabla(bus_n.get("advertencia", ""))
                if adv_n:
                    advertencias.append(f"Materia adicional {n}: {adv_n}")

            if es_oe and materia_ids_adicionales:
                errores_materias.append("Una comisión Optativa/Electiva no puede tener códigos adicionales.")

            if materia_id is not None:
                try:
                    claves_sel = sorted(L.claves_materias_comision_v122(materia_id, materia_ids_adicionales))
                    clave_materias = "+".join(claves_sel)
                except Exception:
                    clave_materias = codigo
            else:
                clave_materias = codigo
            clave_op = str(opcion_id) if opcion_id is not None else R.normalizar_clave(opcion_raw)
            clave = f"{clave_materias} | {clave_op} | {comision}" if es_oe else f"{clave_materias} | {comision}"
            duplicada_en_pegado = clave in vistas
            vistas.add(clave)

            dup_base = pd.DataFrame()
            if (materia_id is not None and comision and not errores_catalogo and not errores_materias
                    and (not es_oe or opcion_id is not None)):
                dup_base = L.existe_comision_duplicada(
                    periodo_id, materia_id, comision, turno_fila, sede_fila, modalidad_fila,
                    opcion_curricular_id=opcion_id, materia_especifica=opcion_nombre,
                    materia_ids_adicionales=materia_ids_adicionales,
                )

            if materia is None:
                estado_validacion = "ERROR"
                motivo = busqueda.get("motivo", "No se encontró la materia")
            elif errores_materias:
                estado_validacion = "ERROR"
                motivo = " / ".join(errores_materias)
            elif opcion_estado == "ERROR":
                estado_validacion = "ERROR"
                motivo = opcion_motivo
            elif duplicada_en_pegado:
                estado_validacion = "DUPLICADA"
                motivo = "Duplicada dentro de la tabla pegada"
            elif not dup_base.empty:
                estado_validacion = "DUPLICADA"
                motivo = "Ya existe esa comisión para la misma composición de materia(s)/opción en el período actual"
            elif errores_catalogo:
                estado_validacion = "ERROR"
                motivo = " / ".join(errores_catalogo)
            elif errores_horario:
                estado_validacion = "ERROR"
                motivo = " / ".join(errores_horario)
            elif errores_docentes:
                estado_validacion = "ERROR"
                motivo = " / ".join(errores_docentes)
            else:
                adv_limpias = [x for x in advertencias + list(advertencias_docentes or []) if R.limpiar_texto_tabla(x)]
                estado_validacion = ("ADVERTENCIA" if adv_limpias or busqueda.get("estado") == "ADVERTENCIA"
                                     or opcion_estado == "ADVERTENCIA" else "OK")
                motivo = "Lista para cargar" if estado_validacion == "OK" else " / ".join(adv_limpias)

            codigos_resumen = []
            if materia is not None:
                codigos_resumen.append(R.limpiar_texto_tabla(materia.get("codigo", codigo)))
            for mid_n in materia_ids_adicionales:
                info_n = L.materia_comision(mid_n) or {}
                cod_n = R.limpiar_texto_tabla(info_n.get("codigo", ""))
                if cod_n and cod_n not in codigos_resumen:
                    codigos_resumen.append(cod_n)

            registros.append({
                "fila_pegada": int(idx) + 1,
                "estado_validacion": estado_validacion,
                "motivo": motivo,
                "advertencia": " / ".join([x for x in advertencias if x]),
                "clave_generada": clave,
                "materia_id": materia_id,
                "materia_ids_adicionales": materia_ids_adicionales,
                "materia_encontrada": " / ".join([x for x in [materia_encontrada] + materias_adicionales_encontradas if x]),
                "codigos_comision": " / ".join(codigos_resumen),
                "opcion_curricular_id": opcion_id,
                "opcion_curricular": opcion_nombre or opcion_raw,
                "materia_especifica": opcion_nombre if es_oe else "",
                "codigo": codigo,
                "asignatura": row.get("asignatura", ""),
                "comision": comision,
                "turno": turno_fila,
                "resumen_horarios": " | ".join([f"{h['dia']} {h['hora_inicio']}-{h['hora_fin']}" for h in horarios])
                if horarios else "",
                "resumen_docentes": " | ".join([
                    f"{d['docente']} ({d['rol']}) — " + (
                        " / ".join([f"{h.get('dia','')} {h.get('hora_inicio','')}-{h.get('hora_fin','')}"
                                    for h in (d.get('horarios_reales') or [])])
                        if d.get('horarios_reales') is not None else "horario completo de la comisión"
                    ) for d in docentes
                ]) if docentes else "",
                "modalidad": modalidad_fila,
                "sede": sede_fila,
                "estado": row.get("estado", "Activa"),
                "observaciones": row.get("observaciones", ""),
                "horarios": horarios,
                "docentes": docentes,
            })
        return pd.DataFrame(registros)


# ------------------------------------------------------------------------------------------ lote v232 (un COMMIT)
_INS_COMISIONES = ("INSERT INTO comisiones (institucion_id, departamento_id, periodo_id, materia_id, nombre_comision, "
                   "turno, sede, modalidad, estado, observaciones, fecha_creacion, materia_especifica, "
                   "opcion_curricular_id) VALUES {values} RETURNING id")
_INS_VINCULOS = ("INSERT INTO comision_materias (institucion_id, departamento_id, comision_id, materia_id, "
                 "carrera_id_snapshot, carrera_snapshot, escuela_snapshot, plan_version_snapshot, anio_snapshot, "
                 "cuatrimestre_snapshot, dictado_snapshot, carga_semanal_snapshot, carga_total_snapshot, codigo_snapshot, "
                 "asignatura_snapshot, fecha_vinculacion, origen) VALUES {values}")
_INS_HORARIOS = ("INSERT INTO horarios_comision (institucion_id, departamento_id, comision_id, dia, hora_inicio, hora_fin, "
                 "horas, observaciones) VALUES {values} RETURNING id")
_INS_ASIGNACIONES = ("INSERT INTO asignaciones_docentes_comision (institucion_id, departamento_id, comision_id, cuil, rol, "
                     "horas_asignadas, estado, observaciones, usa_horario_personalizado) VALUES {values} RETURNING id")
_INS_FRANJAS = ("INSERT INTO horarios_asignacion_docente_comision (institucion_id, departamento_id, asignacion_id, "
                "horario_comision_id, dia, hora_inicio, hora_fin, horas, observaciones) VALUES {values}")
_INS_MOVIMIENTOS = ("INSERT INTO movimientos (institucion_id, departamento_id, periodo_id, fecha, tipo_movimiento, cuil, "
                    "nombre, detalle, observaciones, horas_variacion) VALUES {values}")


def _execute_values(repo, sql: str, rows: list, page_size: int, fetch: bool = False) -> list:
    """``psycopg2.extras.execute_values``: un INSERT multi-fila por pagina (cada pagina = una sentencia)."""
    out = []
    for i in range(0, len(rows), page_size):
        page = rows[i:i + page_size]
        values = ",".join("(" + ",".join(["%s"] * len(r)) + ")" for r in page)
        params = [v for r in page for v in r]
        with repo._conn.cursor() as cur:
            cur.execute(sql.replace("{values}", values), params)
            repo.mutating_statements += 1
            if fetch:
                out.extend(cur.fetchall())
    return out


def cargar_comisiones_rapidas_lote_v232(u, df_ok: pd.DataFrame, periodo_actual: dict) -> dict:
    """l. 52236 (PostgreSQL): todas las comisiones, vinculos, horarios, asignaciones, franjas y movimientos en UN
    COMMIT; despues, el reajuste de proyectos v184 por CUIL con proyectos (fuera de ese COMMIT, errores silenciados)."""
    from .escrituras import AuditoriaFallida
    from .proyectos import cuiles_con_proyectos_periodo_v232, reconciliar_horas_proyectos_por_comisiones_v184

    if df_ok is None or not isinstance(df_ok, pd.DataFrame) or df_ok.empty:
        return {"comisiones": 0, "horarios": 0, "docentes": 0, "segundos": 0.0, "ajustes_proyectos": 0}
    pid = int(periodo_actual["id"])
    pnombre = str(periodo_actual.get("nombre", ""))
    t0 = time.perf_counter()
    inst, dep = int(u.inst or 0), int(u.dep or 0)
    if inst <= 0 or dep <= 0:
        raise RuntimeError("No se pudo determinar institución/departamento para la carga masiva.")
    L = u.lector
    hoy = str(u.today)

    cache_vinculos = {}
    preparados = []
    cuiles = set()
    for _, row in df_ok.iterrows():
        mid, adicionales, opcion = R.normalizar_fila_bulk_comision_v232(row)
        key = (mid, tuple(adicionales), opcion)
        if key not in cache_vinculos:
            seleccion = L.materias_conceptuales_seleccionadas_v122(mid, adicionales)
            principal = int(seleccion[0]["materia_id"])
            es_oe = len(seleccion) == 1 and bool(seleccion[0]["es_optativa_electiva"])
            vinculos = L.preparar_vinculos_multiples_materias_comision_v122(
                principal, [x["materia_id"] for x in seleccion[1:]],
                opcion_curricular_id=opcion, incluir_historicas=False,
            )
            cache_vinculos[key] = (principal, es_oe, vinculos)
        principal, es_oe, vinculos = cache_vinculos[key]
        obs_base = R.limpiar_texto_tabla(row.get("observaciones", ""))
        obs_auto = (
            "Carga rápida de comisiones con horarios. "
            f"Clave generada: {row['clave_generada']}. "
            f"Validación: {row.get('motivo','')}. "
            f"Advertencia: {row.get('advertencia','')}. "
            f"Docentes: {row.get('resumen_docentes','')}."
        )
        obs = f"{obs_base} | {obs_auto}" if obs_base else obs_auto
        docs = list(row.get("docentes", []) or [])
        for d in docs:
            if d.get("cuil"):
                cuiles.add(str(d["cuil"]))
        preparados.append({
            "row": row, "principal": principal, "es_oe": es_oe,
            "opcion": opcion, "vinculos": vinculos, "obs": obs,
            "horarios": list(row.get("horarios", []) or []), "docentes": docs,
        })
    sedes = L.opciones_sedes_comision()
    resumen = {}

    def body(repo):
        com_rows = []
        for p in preparados:
            r = p["row"]
            com_rows.append((
                inst, dep, pid, int(p["principal"]), str(r.get("comision", "")).strip(),
                R.normalizar_turno_comision(r.get("turno", "")), R.normalizar_sede_comision(r.get("sede", ""), sedes),
                R.normalizar_modalidad_comision(r.get("modalidad", "")), str(r.get("estado", "Activa") or "Activa"),
                p["obs"], hoy, R.limpiar_texto_tabla(r.get("materia_especifica", "")) if p["es_oe"] else "",
                p["opcion"] if p["es_oe"] else None,
            ))
        ret = _execute_values(repo, _INS_COMISIONES, com_rows, 1000, fetch=True)
        cids = [int(x[0]) for x in ret]
        if len(cids) != len(preparados):
            raise RuntimeError("PostgreSQL no devolvió todos los IDs de las comisiones insertadas.")
        for p, cid in zip(preparados, cids):
            p["comision_id"] = cid

        vinc_rows = []
        for p in preparados:
            vistos = set()
            origen = ("apertura_opcion_curricular_v120" if p["es_oe"] else
                      ("apertura_multicodigo_v122" if len(R.normalizar_fila_bulk_comision_v232(p["row"])[1])
                       else "apertura_v118"))
            for v in p["vinculos"]:
                try:
                    vmid = int(v.get("materia_id"))
                except Exception:
                    continue
                if vmid in vistos:
                    continue
                vistos.add(vmid)
                vinc_rows.append((
                    inst, dep, int(p["comision_id"]), vmid, v.get("carrera_id_snapshot"), v.get("carrera_snapshot", ""),
                    v.get("escuela_snapshot", ""), v.get("plan_version_snapshot", ""), v.get("anio_snapshot", ""),
                    v.get("cuatrimestre_snapshot", ""), v.get("dictado_snapshot", ""), v.get("carga_semanal_snapshot", ""),
                    v.get("carga_total_snapshot", ""), v.get("codigo_snapshot", ""), v.get("asignatura_snapshot", ""),
                    hoy, origen,
                ))
        if vinc_rows:
            _execute_values(repo, _INS_VINCULOS, vinc_rows, 2000)

        h_rows, h_meta = [], []
        for pi, p in enumerate(preparados):
            for h in p["horarios"]:
                if not (h.get("dia") and h.get("hora_inicio") and h.get("hora_fin")):
                    continue
                dia = R.normalizar_dia_v95(h.get("dia")); hi = R.hora_texto_v95(h.get("hora_inicio"))
                hf = R.hora_texto_v95(h.get("hora_fin"))
                horas = R.calcular_horas_desde_texto(hi, hf)
                h_rows.append((inst, dep, int(p["comision_id"]), dia, hi, hf, _numeric(horas), OBS_AUTO_CARGA))
                h_meta.append((pi, dia, hi, hf))
        h_ids = []
        if h_rows:
            ret = _execute_values(repo, _INS_HORARIOS, h_rows, 2000, fetch=True)
            h_ids = [int(x[0]) for x in ret]
        horarios_insertados = {i: [] for i in range(len(preparados))}
        for hid, (pi, dia, hi, hf) in zip(h_ids, h_meta):
            horarios_insertados[pi].append({"id": hid, "dia": dia, "hora_inicio": hi, "hora_fin": hf})

        a_rows, a_meta = [], []
        for pi, p in enumerate(preparados):
            total_com = round(sum(R.calcular_horas_desde_texto(h.get("hora_inicio", ""), h.get("hora_fin", ""))
                                  for h in p["horarios"]), 2)
            for d in p["docentes"]:
                hr = d.get("horarios_reales")
                hd = round(float(d.get("horas_reales", total_com) or 0), 2)
                a_rows.append((inst, dep, int(p["comision_id"]), str(d["cuil"]), d["rol"], _numeric(hd), "Activa",
                               OBS_AUTO_CARGA, bool(hr is not None)))
                a_meta.append((pi, d, hd))
        a_ids = []
        if a_rows:
            ret = _execute_values(repo, _INS_ASIGNACIONES, a_rows, 2000, fetch=True)
            a_ids = [int(x[0]) for x in ret]

        hp_rows = []
        mov_rows = []
        for aid, (pi, d, hd) in zip(a_ids, a_meta):
            hr = d.get("horarios_reales")
            if hr is not None:
                for item in list(hr or []):
                    dia = R.normalizar_dia_v95(item.get("dia")); hi = R.hora_texto_v95(item.get("hora_inicio"))
                    hf = R.hora_texto_v95(item.get("hora_fin"))
                    hid = None
                    ai, af = R.minutos_v95(hi), R.minutos_v95(hf)
                    for gh in horarios_insertados.get(pi, []):
                        if R.normalizar_dia_v95(gh["dia"]) != dia:
                            continue
                        gi, gf = R.minutos_v95(gh["hora_inicio"]), R.minutos_v95(gh["hora_fin"])
                        if None not in (ai, af, gi, gf) and gi <= ai and gf >= af:
                            hid = int(gh["id"])
                            break
                    if hid is None:
                        raise ValueError(f"No se pudo vincular la cobertura {dia} {hi}-{hf} del docente "
                                         f"{d.get('docente') or d.get('cuil')} con un horario general.")
                    hp_rows.append((inst, dep, int(aid), hid, dia, hi, hf, _numeric(R.horas_intervalo_v95(hi, hf)), ""))
            p = preparados[pi]; r = p["row"]
            cobertura_txt = (" / ".join([f"{h.get('dia','')} {h.get('hora_inicio','')}-{h.get('hora_fin','')}"
                                         for h in (hr or [])]) if hr is not None else "horario completo de la comisión")
            mov_rows.append((inst, dep, pid, hoy, "Asignación docente a comisión", str(d["cuil"]), str(d.get("docente", "")),
                             f"Carga rápida: se asignó a {r['clave_generada']} como {d['rol']} ({hd:g} hs). "
                             f"Cobertura: {cobertura_txt}.", p["obs"], _numeric(0.0)))
        if hp_rows:
            _execute_values(repo, _INS_FRANJAS, hp_rows, 4000)

        for p in preparados:
            r = p["row"]
            mov_rows.append((inst, dep, pid, hoy, "Apertura de comisión", "", "",
                             f"Carga rápida: se abrió {r['clave_generada']} en {pnombre} con {len(p['horarios'])} horario/s.",
                             p["obs"], _numeric(0.0)))
        if mov_rows:
            _execute_values(repo, _INS_MOVIMIENTOS, mov_rows, 4000)
        resumen.update(horarios=len(h_rows), docentes=len(a_rows))

    u.commit(body)

    ajustes = 0
    try:
        claves_proy = cuiles_con_proyectos_periodo_v232(u, cuiles, pid)
        mapa_cuil = {R.clave_cuil(c): c for c in cuiles}
        for k in claves_proy:
            cuil = mapa_cuil.get(k, k)
            try:
                cambios = reconciliar_horas_proyectos_por_comisiones_v184(u, cuil, pid) or []
                ajustes += len(cambios)
            except AuditoriaFallida:
                raise
            except Exception:
                pass
    except AuditoriaFallida:
        raise
    except Exception:
        pass

    return {
        "comisiones": len(preparados), "horarios": resumen["horarios"], "docentes": resumen["docentes"],
        "segundos": round(time.perf_counter() - t0, 3), "ajustes_proyectos": int(ajustes),
    }
