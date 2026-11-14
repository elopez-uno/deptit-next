"""Reglas puras del modulo Comisiones (pandas, como el certificado).  Sin base de datos.

Origen certificado (reference_fix02, solo lectura):
- ``deptit_refactor/catalogs/comisiones.py`` (turnos, modalidades, dias, Campus Virtual) y entry l. 18383-18387.
- ``deptit_refactor/domain/comisiones.py`` (normalizaciones, etiquetas, filas del Excel, v232, v248).
- ``deptit_refactor/common/horarios.py`` + ``extracted_batch04/horarios.py`` (horas, franjas v95, exportacion v175).
- ``deptit_refactor/common/normalization.py`` (``_normalizar_si_no_cobertura_v153``), ``common/dates.py``
  (``_fecha_iso_observacion_v183``), ``extracted_batch04/numeros.py`` (v248), ``domain/residual/*``,
  ``domain/catalog_unlocked/comisiones.py`` (``validar_horarios_comision_rapida``), ``domain/materias.py``.
- entry: compuertas de periodo l. 18392-18421, foto al cierre v183 l. 39886.
Los helpers de texto, CUIL, cargos y materias v137 se reutilizan de los bloques cerrados (mismas funciones).
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from difflib import SequenceMatcher
from typing import Any, Optional

import pandas as pd

from designaciones.rules import horas_segun_dedicacion, normalizar_cargo_para_jerarquia  # noqa: F401
from docentes.rules import clave_cuil, limpiar_cuil, limpiar_texto_tabla, nombre_completo, normalizar_clave  # noqa: F401
from docentes.rules import safe_date, safe_index  # noqa: F401
from materias.rules import (  # noqa: F401
    clave_materia_conceptual_v137, clave_materia_unica_codigo_nombre, deptit_join_unicos, es_materia_optativa_electiva,
    filtrar_dataframe_por_texto, normalizar_codigo_materia, normalizar_modo_comparticion_v137,
    normalizar_tipo_opcion_v120, tipo_espacio_curricular_v120,
)

# --- catalogos (catalogs/comisiones.py; entry l. 18383-18387) ---------------------------------------------------
SEDE_CAMPUS_VIRTUAL = "Campus Virtual"
TURNOS_COMISION = ["mañana", "tarde", "noche"]
MODALIDADES_COMISION = ["Presencial", "Virtual", "Híbrida"]
DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
SEDES_COMISION_FALLBACK = ["Sin especificar", SEDE_CAMPUS_VIRTUAL]
ESTADOS_COMISION = ["Activa", "Finalizada", "Suspendida"]
ROLES_DOCENTE_COMISION = ["Responsable", "Adjunto", "JTP", "Auxiliar", "Teórico", "Práctico", "Otro"]
ORDEN_JERARQUICO_CARGOS_COMISION = ["Titular", "Asociado", "Adjunto", "JTP", "Ayudante 1ra", "Ayudante 2da"]
ESTADOS_SEDE = ["Activa", "Inactiva"]


def _is_na(valor: Any) -> bool:
    try:
        return bool(pd.isna(valor))
    except (TypeError, ValueError):
        return False


# --- texto / numeros ------------------------------------------------------------------------------------------
def similitud_texto(a, b):
    a_n = normalizar_clave(a)
    b_n = normalizar_clave(b)
    if not a_n or not b_n:
        return 0
    return round(SequenceMatcher(None, a_n, b_n).ratio(), 3)


def nombre_archivo_seguro(texto):
    txt = str(texto or "").strip()
    txt = re.sub(r"[^A-Za-z0-9ÁÉÍÓÚáéíóúÑñ_\- ]+", "", txt)
    txt = re.sub(r"\s+", "_", txt)
    return txt[:120] or "disposicion"


def hora_numero(valor):
    try:
        if valor is None or pd.isna(valor):
            return 0.0
        if isinstance(valor, str):
            valor = valor.replace("hs", "").replace(",", ".").strip()
        return float(valor or 0)
    except Exception:
        return 0.0


def opcion_id_inscriptos_v248(valor):
    try:
        if valor is None or pd.isna(valor):
            return 0
        n = int(valor)
        return n if n > 0 else 0
    except Exception:
        return 0


def entero_no_negativo_v248(valor, default=0):
    try:
        n = pd.to_numeric(valor, errors="coerce")
        if pd.isna(n):
            return int(default)
        return max(int(n), 0)
    except Exception:
        return int(default)


def normalizar_si_no_cobertura_v153(valor):
    txt = limpiar_texto_tabla(valor)
    if not txt:
        return ""
    clave = normalizar_clave(txt)
    if clave in {"SI", "SÍ", "S", "YES", "Y", "1", "TRUE", "VERDADERO"}:
        return "Sí"
    if clave in {"NO", "N", "0", "FALSE", "FALSO"}:
        return "No"
    return txt


def fecha_iso_observacion_v183(texto, patrones=None) -> Optional[date]:
    s = str(texto or "")
    patrones = patrones or [
        r"Baja por modificación de asignación\.\s*Fecha efectiva:\s*(\d{4}-\d{2}-\d{2})",
        r"Préstamo finalizado el\s*(\d{4}-\d{2}-\d{2})",
        r"Fecha efectiva:\s*(\d{4}-\d{2}-\d{2})",
    ]
    for pat in patrones:
        m = re.search(pat, s, flags=re.I)
        if m:
            return safe_date(m.group(1), None)
    return None


# --- horas y franjas ------------------------------------------------------------------------------------------
def hora_a_minutos(hora):
    try:
        if hora is None or pd.isna(hora) or str(hora).strip() == "":
            return None
        partes = str(hora).strip().split(":")
        return int(partes[0]) * 60 + int(partes[1])
    except Exception:
        return None


def hora_texto_v95(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    if hasattr(valor, "strftime"):
        try:
            return valor.strftime("%H:%M")
        except Exception:
            pass
    txt = str(valor).strip()
    m = re.match(r"^(\d{1,2}):(\d{2})", txt)
    return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}" if m else txt


def minutos_v95(valor):
    txt = hora_texto_v95(valor)
    try:
        h, m = [int(x) for x in txt.split(":")[:2]]
        return h * 60 + m
    except Exception:
        return None


def normalizar_dia_v95(dia):
    txt = normalizar_clave(dia)
    mapa = {
        "lunes": "Lunes", "martes": "Martes", "miercoles": "Miércoles",
        "jueves": "Jueves", "viernes": "Viernes", "sabado": "Sábado", "domingo": "Domingo",
    }
    return mapa.get(txt, str(dia or "").strip())


def calcular_horas_desde_texto(hora_inicio, hora_fin):
    try:
        hi = datetime.strptime(str(hora_inicio), "%H:%M")
        hf = datetime.strptime(str(hora_fin), "%H:%M")
        delta = (hf - hi).total_seconds() / 3600
        if delta < 0:
            delta += 24
        return round(delta, 2)
    except Exception:
        return 0


def normalizar_hora_excel(valor):
    txt = limpiar_texto_tabla(valor)
    if not txt:
        return ""
    txt = txt.lower().strip()
    txt = txt.replace(" ", " ")
    txt = txt.replace("a. m.", "am").replace("p. m.", "pm")
    txt = txt.replace("a.m.", "am").replace("p.m.", "pm")
    txt = txt.replace("a. m", "am").replace("p. m", "pm")
    txt = txt.replace("a m", "am").replace("p m", "pm")
    txt = " ".join(txt.split())
    formatos = ["%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p", "%I:%M:%S%p", "%I:%M%p"]
    for fmt in formatos:
        try:
            return datetime.strptime(txt.upper(), fmt).strftime("%H:%M")
        except Exception:
            pass
    try:
        es_pm = txt.endswith("pm")
        es_am = txt.endswith("am")
        limpio = txt.replace("pm", "").replace("am", "").strip()
        partes = limpio.split(":")
        hora = int(partes[0])
        minuto = int(partes[1]) if len(partes) > 1 else 0
        if es_pm and hora != 12:
            hora += 12
        if es_am and hora == 12:
            hora = 0
        if 0 <= hora <= 23 and 0 <= minuto <= 59:
            return f"{hora:02d}:{minuto:02d}"
    except Exception:
        return ""
    return ""


def intervalos_solapan(inicio_a, fin_a, inicio_b, fin_b):
    ia = hora_a_minutos(inicio_a)
    fa = hora_a_minutos(fin_a)
    ib = hora_a_minutos(inicio_b)
    fb = hora_a_minutos(fin_b)
    if None in [ia, fa, ib, fb]:
        return False
    if fa <= ia:
        fa += 24 * 60
    if fb <= ib:
        fb += 24 * 60
    return max(ia, ib) < min(fa, fb)


def calcular_horas_unicas_desde_horarios_df(df_horarios):
    if df_horarios is None or df_horarios.empty:
        return 0.0
    total_minutos = 0
    for _dia, grupo in df_horarios.groupby("dia", dropna=False):
        intervalos = []
        for _, row in grupo.iterrows():
            ini = hora_a_minutos(row.get("hora_inicio"))
            fin = hora_a_minutos(row.get("hora_fin"))
            if ini is None or fin is None:
                continue
            if fin <= ini:
                fin += 24 * 60
            intervalos.append((ini, fin))
        if not intervalos:
            continue
        intervalos.sort()
        unidos = []
        for ini, fin in intervalos:
            if not unidos or ini > unidos[-1][1]:
                unidos.append([ini, fin])
            else:
                unidos[-1][1] = max(unidos[-1][1], fin)
        total_minutos += sum(fin - ini for ini, fin in unidos)
    return round(total_minutos / 60, 2)


def horas_intervalo_v95(inicio, fin):
    a, b = minutos_v95(inicio), minutos_v95(fin)
    if a is None or b is None or b <= a:
        return 0.0
    return round((b - a) / 60.0, 2)


def es_subintervalo_v95(dia, inicio, fin, horarios_comision):
    d = normalizar_dia_v95(dia)
    a, b = minutos_v95(inicio), minutos_v95(fin)
    if a is None or b is None or b <= a:
        return False
    if horarios_comision is None or len(horarios_comision) == 0:
        return False
    for _, r in horarios_comision.iterrows():
        if normalizar_dia_v95(r.get("dia")) != d:
            continue
        ca, cb = minutos_v95(r.get("hora_inicio")), minutos_v95(r.get("hora_fin"))
        if ca is not None and cb is not None and ca <= a < b <= cb:
            return True
    return False


def normalizar_hora_export_v175(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    txt = str(valor).strip()
    if not txt:
        return ""
    m = re.match(r"^(\d{1,2}):(\d{2})", txt)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
    return txt


# --- catalogo de comisiones (domain/comisiones.py) -------------------------------------------------------------
def clave_catalogo_comision(valor):
    clave = normalizar_clave(valor)
    return clave.translate(str.maketrans({"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U", "Ñ": "N"}))


def normalizar_turno_comision(valor):
    txt = limpiar_texto_tabla(valor)
    clave = clave_catalogo_comision(txt)
    mapa = {
        "MANANA": "mañana", "TURNO MANANA": "mañana", "MATUTINO": "mañana",
        "TARDE": "tarde", "TURNO TARDE": "tarde", "VESPERTINO": "tarde",
        "NOCHE": "noche", "TURNO NOCHE": "noche", "NOCTURNO": "noche",
    }
    return mapa.get(clave, txt)


def normalizar_modalidad_comision(valor):
    txt = limpiar_texto_tabla(valor)
    if not txt:
        return "Presencial"
    clave = clave_catalogo_comision(txt)
    mapa = {"PRESENCIAL": "Presencial", "VIRTUAL": "Virtual", "HIBRIDA": "Híbrida", "HIBRIDO": "Híbrida",
            "MIXTA": "Híbrida", "MIXTO": "Híbrida"}
    return mapa.get(clave, txt)


def opciones_sedes_comision(nombres_sedes_activas: list) -> list:
    """``opciones_sedes_comision`` (l. 18278): fijas + sedes fisicas activas de la institucion."""
    nombres = [str(x).strip() for x in nombres_sedes_activas if str(x).strip()]
    opciones = ["Sin especificar", SEDE_CAMPUS_VIRTUAL] + nombres
    return list(dict.fromkeys(opciones))


def normalizar_sede_comision(valor, opciones: list):
    """``normalizar_sede_comision`` (l. 18338) con las opciones vigentes ya leidas."""
    txt = limpiar_texto_tabla(valor)
    clave_normalizada = normalizar_clave(txt)
    if not txt or clave_normalizada == "SIN ESPECIFICAR":
        return "Sin especificar"
    if clave_normalizada == "CAMPUS VIRTUAL":
        return SEDE_CAMPUS_VIRTUAL
    por_clave = {clave_catalogo_comision(x): x for x in opciones}
    clave = clave_catalogo_comision(txt)
    if clave in por_clave:
        return por_clave[clave]
    coincidencias = [x for x in opciones if clave_catalogo_comision(x).replace("SEDE ", "", 1) == clave]
    return coincidencias[0] if len(coincidencias) == 1 else txt


def inferir_turno_desde_horas_fila(row):
    horas = []
    for col in row.index:
        if str(col).startswith("hora_inicio_"):
            hora = normalizar_hora_excel(row.get(col, ""))
            if hora:
                try:
                    horas.append(int(hora.split(":")[0]))
                except Exception:
                    pass
    if not horas:
        return ""
    primera = min(horas)
    if primera < 13:
        return "mañana"
    if primera < 18:
        return "tarde"
    return "noche"


def turno_para_etiqueta(valor):
    return normalizar_turno_comision(valor) or "sin especificar"


def label_comision_desde_row(row):
    periodo = limpiar_texto_tabla(row.get("periodo", ""))
    codigo = limpiar_texto_tabla(row.get("codigo_materia", ""))
    asig = limpiar_texto_tabla(row.get("asignatura", ""))
    materia_especifica = limpiar_texto_tabla(row.get("materia_especifica", ""))
    if materia_especifica:
        asig = f"{asig} · {materia_especifica}" if asig else materia_especifica
    com = limpiar_texto_tabla(row.get("nombre_comision", ""))
    turno = turno_para_etiqueta(row.get("turno", ""))
    horarios = limpiar_texto_tabla(row.get("horarios", "")) or "Sin horarios cargados"
    carreras = limpiar_texto_tabla(row.get("carrera", "")) or "Sin carrera informada"
    materia = f"{codigo} - {asig}".strip(" -")
    partes = [p for p in [periodo, materia, f"Comisión {com}" if com else "", turno] if p]
    partes.append(f"Día/s y horario/s: {horarios}")
    partes.append(f"Carrera/s: {carreras}")
    return " — ".join(partes) or f"Comisión ID {row.get('id', '')}"


def etiqueta_comision(row):
    return label_comision_desde_row(row)


def horarios_desde_fila_comision(row):
    indices = set()
    for col in row.index:
        m = re.fullmatch(r"dia_(\d+)|hora_inicio_(\d+)|hora_fin_(\d+)", str(col))
        if m:
            indices.add(int(next(g for g in m.groups() if g)))
    horarios = []
    for n in sorted(indices):
        dia = limpiar_texto_tabla(row.get(f"dia_{n}", ""))
        hi = limpiar_texto_tabla(row.get(f"hora_inicio_{n}", ""))
        hf = limpiar_texto_tabla(row.get(f"hora_fin_{n}", ""))
        if dia or hi or hf:
            horarios.append({"n": n, "dia": dia, "hora_inicio": hi, "hora_fin": hf})
    return horarios


def docentes_desde_fila_comision(row):
    indices = set()
    slots_por_docente: dict = {}
    slots_cubre_por_docente: dict = {}
    for col in row.index:
        s = str(col)
        m = re.fullmatch(r"docente_(\d+)|cargo_docente_(\d+)", s)
        if m:
            indices.add(int(next(g for g in m.groups() if g)))
            continue
        mc = re.fullmatch(r"cubre_docente_(\d+)_horario_(\d+)", s)
        if mc:
            n_doc = int(mc.group(1)); n_h = int(mc.group(2))
            indices.add(n_doc)
            slots_por_docente.setdefault(n_doc, set()).add(n_h)
            slots_cubre_por_docente.setdefault(n_doc, set()).add(n_h)
            continue
        mh = re.fullmatch(r"(?:dia|hora_inicio|hora_fin)_docente_(\d+)_horario_(\d+)", s)
        if mh:
            n_doc = int(mh.group(1)); n_h = int(mh.group(2))
            indices.add(n_doc); slots_por_docente.setdefault(n_doc, set()).add(n_h)
    docentes = []
    for n in sorted(indices):
        docente = limpiar_texto_tabla(row.get(f"docente_{n}", ""))
        cargo = limpiar_texto_tabla(row.get(f"cargo_docente_{n}", ""))
        horarios_legacy = []
        hay_franja_legacy = False
        hay_horas_explicitas = False
        cobertura_slots = []
        tiene_columnas_cobertura = bool(slots_cubre_por_docente.get(n))
        for n_h in sorted(slots_por_docente.get(n, set())):
            cubre = normalizar_si_no_cobertura_v153(row.get(f"cubre_docente_{n}_horario_{n_h}", ""))
            dia = limpiar_texto_tabla(row.get(f"dia_docente_{n}_horario_{n_h}", ""))
            hi = limpiar_texto_tabla(row.get(f"hora_inicio_docente_{n}_horario_{n_h}", ""))
            hf = limpiar_texto_tabla(row.get(f"hora_fin_docente_{n}_horario_{n_h}", ""))
            if hi or hf:
                hay_horas_explicitas = True
            if tiene_columnas_cobertura:
                cobertura_slots.append({"n": n_h, "cubre": cubre, "dia": dia, "hora_inicio": hi, "hora_fin": hf})
            if dia or hi or hf:
                hay_franja_legacy = True
                horarios_legacy.append({"n": n_h, "dia": dia, "hora_inicio": hi, "hora_fin": hf})
        if not docente and not cargo and not hay_horas_explicitas:
            continue
        docentes.append({
            "n": n, "docente": docente, "rol": cargo,
            "horarios_reales": horarios_legacy if hay_franja_legacy else None,
            "cobertura_slots": cobertura_slots if tiene_columnas_cobertura else None,
        })
    return docentes


def validar_horarios_comision_rapida(row):
    horarios = horarios_desde_fila_comision(row)
    errores = []
    vistos = set()
    for h in horarios:
        n = h["n"]
        dia = h["dia"]
        hi = h["hora_inicio"]
        hf = h["hora_fin"]
        if not dia or not hi or not hf:
            errores.append(f"Horario {n} incompleto")
            continue
        if dia not in DIAS_SEMANA:
            errores.append(f"Día {n} inválido: {dia}")
        if not hi or not hf:
            errores.append(f"Hora {n} inválida")
        clave = (normalizar_clave(dia), hi, hf)
        if clave in vistos:
            errores.append(f"Horario {n} duplicado dentro de la fila")
        vistos.add(clave)
    return errores, horarios


def filtrar_materias_para_comisiones(df, codigo_parcial="", nombre_parcial="", cuatrimestre="Todos", escuela="Todas",
                                     carrera="Todas"):
    if df is None or df.empty:
        return pd.DataFrame()
    df_filtrado = df.copy()
    codigo_parcial = normalizar_clave(codigo_parcial)
    nombre_parcial = normalizar_clave(nombre_parcial)
    cuatrimestre = limpiar_texto_tabla(cuatrimestre)
    escuela = limpiar_texto_tabla(escuela)
    carrera = limpiar_texto_tabla(carrera)
    if codigo_parcial:
        df_filtrado = df_filtrado[df_filtrado["codigo"].apply(lambda x: codigo_parcial in normalizar_clave(x))].copy()
    if nombre_parcial:
        df_filtrado = df_filtrado[df_filtrado["asignatura"].apply(lambda x: nombre_parcial in normalizar_clave(x))].copy()
    if cuatrimestre and cuatrimestre != "Todos":
        df_filtrado = df_filtrado[df_filtrado["cuatrimestre"].astype(str).str.strip() == cuatrimestre].copy()
    if escuela and escuela != "Todas":
        df_filtrado = df_filtrado[df_filtrado["escuela"].astype(str).str.strip() == escuela].copy()
    if carrera and carrera != "Todas":
        df_filtrado = df_filtrado[df_filtrado["carrera"].astype(str).str.strip() == carrera].copy()
    return df_filtrado.reset_index(drop=True)


def filtrar_opciones_comisiones_por_busqueda(opciones, busqueda):
    if not opciones:
        return {}
    q = normalizar_clave(busqueda or "")
    if not q:
        return opciones
    return {label: value for label, value in opciones.items() if q in normalizar_clave(label)}


def etiqueta_materia_comision(row):
    codigo = limpiar_texto_tabla(row.get("codigo", ""))
    asignatura = limpiar_texto_tabla(row.get("asignatura", ""))
    carreras = limpiar_texto_tabla(row.get("carrera", ""))
    escuelas = limpiar_texto_tabla(row.get("escuela", ""))
    plan = limpiar_texto_tabla(row.get("plan_version", ""))
    anio = limpiar_texto_tabla(row.get("anio", ""))
    cuat = limpiar_texto_tabla(row.get("cuatrimestre", ""))
    prefijo = f"{codigo} - " if codigo else ""
    partes = [f"{prefijo}{asignatura}"]
    if carreras:
        partes.append(f"Carrera/s: {carreras}")
    if escuelas:
        # 6A-B3: rótulo genérico (facultad, escuela, instituto...); varias unidades vienen unidas por " / "
        rotulo = "Unidades académicas" if " / " in escuelas else "Unidad académica"
        partes.append(f"{rotulo}: {escuelas}")
    if plan:
        partes.append(f"Plan: {plan}")
    if anio:
        partes.append(f"{anio}")
    if cuat:
        partes.append(f"Cuat. {cuat}")
    return " — ".join([p for p in partes if p])


def opciones_desde_df_materias_comisiones(df):
    if df is None or df.empty:
        return {}
    opciones = {}
    for _, row in df.iterrows():
        opciones[etiqueta_materia_comision(row)] = int(row["materia_id"])
    return opciones


def normalizar_fila_bulk_comision_v232(row):
    materia_id = int(row.get("materia_id"))
    adicionales = []
    for x in list(row.get("materia_ids_adicionales", []) or []):
        try:
            adicionales.append(int(x))
        except Exception:
            pass
    opcion = row.get("opcion_curricular_id")
    try:
        opcion = int(opcion) if opcion not in [None, ""] and not pd.isna(opcion) else None
    except Exception:
        opcion = None
    return materia_id, adicionales, opcion


def etiqueta_comision_derivada_v248(fila):
    nombre = limpiar_texto_tabla((fila or {}).get("nombre_comision", ""))
    turno = limpiar_texto_tabla((fila or {}).get("turno", ""))
    sede = limpiar_texto_tabla((fila or {}).get("sede", ""))
    partes = [x for x in [f"Comisión {nombre}" if nombre else "Comisión", turno, sede] if x]
    return " · ".join(partes)


def etiqueta_item_v248(item):
    cod = limpiar_texto_tabla((item or {}).get("codigo_materia", ""))
    asig = limpiar_texto_tabla((item or {}).get("asignatura", ""))
    if cod and asig:
        return f"{cod} — {asig}"
    return cod or asig or limpiar_texto_tabla((item or {}).get("clave_asignatura_v248", ""))


# --- materias (domain/materias.py) -----------------------------------------------------------------------------
def clave_materia_unica_desde_codigo_nombre(codigo, asignatura):
    codigo_n = normalizar_clave(codigo)
    asignatura_n = normalizar_clave(asignatura)
    if codigo_n:
        return f"{codigo_n}::{asignatura_n}"
    return f"SIN_CODIGO::{asignatura_n}"


def ids_materia_v118(valor):
    if valor is None:
        return []
    if isinstance(valor, (list, tuple, set, pd.Series)):
        partes = list(valor)
    else:
        partes = re.split(r"[,;|]+", str(valor))
    salida = []
    for x in partes:
        try:
            mid = int(float(str(x).strip()))
        except Exception:
            continue
        if mid not in salida:
            salida.append(mid)
    return salida


def fila_materia_por_id_v118(df_detalle, materia_id):
    if df_detalle is None or df_detalle.empty:
        return None
    col = "materia_id" if "materia_id" in df_detalle.columns else "id" if "id" in df_detalle.columns else None
    if col is None:
        return None
    mids = pd.to_numeric(df_detalle[col], errors="coerce").astype("Int64")
    fila = df_detalle[mids == int(materia_id)]
    return None if fila.empty else fila.iloc[0]


def nombre_materia_visible_v138(codigo, asignatura, materia_especifica=""):
    base = limpiar_texto_tabla(asignatura)
    especifica = limpiar_texto_tabla(materia_especifica)
    if especifica:
        if base and normalizar_clave(especifica) not in normalizar_clave(base):
            return f"{base} ({especifica})"
        return especifica or base
    try:
        if es_materia_optativa_electiva(codigo, base):
            return f"{base} (sin opción específica registrada)" if base else \
                "Optativa/Electiva (sin opción específica registrada)"
    except Exception:
        pass
    return base


def etiqueta_opcion_curricular_v120(row):
    codigo = limpiar_texto_tabla(row.get("codigo", ""))
    nombre = limpiar_texto_tabla(row.get("nombre", ""))
    escuela = limpiar_texto_tabla(row.get("escuela_oferente", ""))
    base = f"{codigo} - {nombre}".strip(" -") or nombre
    if normalizar_tipo_opcion_v120(row.get("tipo", "")) == "Electiva" and escuela:
        return f"{base} · {escuela}"
    return base


# --- periodos (domain/residual/lectura.py; entry l. 18397-18421) ------------------------------------------------
def es_periodo_actual_para_comisiones_v233(periodo_id, ultimo: Optional[dict]) -> bool:
    try:
        return bool(ultimo and int(ultimo.get("id")) == int(periodo_id))
    except Exception:
        return False


def puede_operar_comisiones_periodo_actual(abierto: Optional[dict], actual: Optional[dict]):
    if abierto is None or actual is None:
        return False, abierto, actual, "No hay período abierto o no hay período actual creado."
    if int(abierto["id"]) != int(actual["id"]):
        return False, abierto, actual, ("El período abierto no es el último período creado. Volvé al período actual "
                                        "para abrir o modificar comisiones.")
    if abierto.get("estado") != "Abierto":
        return False, abierto, actual, "El período actual no está abierto."
    return True, abierto, actual, ""


def puede_corregir_comisiones_periodo_abierto(abierto: Optional[dict]):
    if abierto is None:
        return False, None, "No hay un período abierto para corregir."
    if str(abierto.get("estado") or "").strip() != "Abierto":
        return False, abierto, "El período seleccionado no está abierto."
    return True, abierto, ""


# --- foto al cierre (entry l. 39886) ---------------------------------------------------------------------------
def filtrar_asignaciones_comision_cierre_v183(df, historico: bool, ref: Optional[date]):
    base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if base.empty or not historico:
        return base
    if ref is None:
        return base
    keep = []
    for _, r in base.iterrows():
        estado = str(r.get("estado", r.get("estado_asignacion", "Activa")) or "Activa").strip().casefold()
        obs = str(r.get("observaciones", "") or "")
        alta = fecha_iso_observacion_v183(obs, [r"Alta por modificación de asignación\.\s*Fecha efectiva:\s*(\d{4}-\d{2}-\d{2})"])
        baja = fecha_iso_observacion_v183(obs, [
            r"Baja por modificación de asignación\.\s*Fecha efectiva:\s*(\d{4}-\d{2}-\d{2})",
            r"Préstamo finalizado el\s*(\d{4}-\d{2}-\d{2})",
        ])
        ok_alta = (alta is None or alta <= ref)
        if estado == "activa":
            ok_baja = (baja is None or baja >= ref)
        else:
            ok_baja = (baja is not None and baja >= ref)
        keep.append(bool(ok_alta and ok_baja))
    return base[pd.Series(keep, index=base.index)].copy().reset_index(drop=True)


# ------------------------------------------------------------------------------------------ cobertura docente (l. 32063)
def hora_time_v95(valor, default_h=8, default_m=0) -> str:
    """``_hora_time_v95`` (common/horarios.py l. 118) expresado como el ``HH:MM`` que muestra el ``st.time_input``."""
    txt = hora_texto_v95(valor)
    try:
        h, m = [int(x) for x in txt.split(":")[:2]]
        return time(h, m).strftime("%H:%M")
    except Exception:
        return time(default_h, default_m).strftime("%H:%M")


def _df_lista(valor) -> pd.DataFrame:
    if isinstance(valor, pd.DataFrame):
        return valor.copy()
    return pd.DataFrame(list(valor)) if valor is not None else pd.DataFrame()


def franjas_formulario_v95(horarios_fuente, default_full=True, horarios_actuales=None) -> list[dict]:
    """Valores iniciales de ``formulario_horarios_reales_asignacion``: una casilla por horario de la comision."""
    if horarios_fuente is None or len(horarios_fuente) == 0:
        return []
    df_fuente = _df_lista(horarios_fuente)
    df_actual = _df_lista(horarios_actuales) if horarios_actuales is not None else pd.DataFrame()
    out = []
    for idx, (_, r) in enumerate(df_fuente.reset_index(drop=True).iterrows()):
        dia = normalizar_dia_v95(r.get("dia")); hi0 = hora_texto_v95(r.get("hora_inicio")); hf0 = hora_texto_v95(r.get("hora_fin"))
        actual_match = pd.DataFrame()
        if not df_actual.empty:
            actual_match = df_actual[
                (df_actual["dia"].fillna("").map(normalizar_dia_v95) == dia)
                & (df_actual["hora_inicio"].fillna("").map(minutos_v95) >= minutos_v95(hi0))
                & (df_actual["hora_fin"].fillna("").map(minutos_v95) <= minutos_v95(hf0))
            ].copy()
        usar_default = bool(default_full) if horarios_actuales is None else (not actual_match.empty)
        hi_default = hora_texto_v95(actual_match.iloc[0].get("hora_inicio")) if not actual_match.empty else hi0
        hf_default = hora_texto_v95(actual_match.iloc[0].get("hora_fin")) if not actual_match.empty else hf0
        hid = r.get("id")
        out.append({"indice": idx, "dia": dia, "hora_inicio": hi0, "hora_fin": hf0, "etiqueta": f"{dia} {hi0}–{hf0}",
                    "horario_comision_id": None if hid is None or pd.isna(hid) else int(hid),
                    "usar": usar_default, "desde": hora_time_v95(hi_default), "hasta": hora_time_v95(hf_default, 23, 0)})
    return out


def horarios_reales_desde_seleccion_v95(horarios_fuente, seleccion) -> tuple[list, float, list]:
    """Resultado de ``formulario_horarios_reales_asignacion`` para lo que el usuario marco.

    ``seleccion`` = una entrada por horario de la comision (``usar``, ``desde``, ``hasta``).  Igual que el certificado,
    una subfranja fuera de su horario se informa (``st.error``) y queda fuera del resultado, sin bloquear el resto.
    """
    resultado, errores = [], []
    if horarios_fuente is None or len(horarios_fuente) == 0:
        return [], 0.0, ["La comisión todavía no tiene horarios válidos."]
    df_fuente = _df_lista(horarios_fuente)
    for idx, (_, r) in enumerate(df_fuente.reset_index(drop=True).iterrows()):
        sel = seleccion[idx]
        dia = normalizar_dia_v95(r.get("dia")); hi0 = hora_texto_v95(r.get("hora_inicio")); hf0 = hora_texto_v95(r.get("hora_fin"))
        if sel.get("usar"):
            hi, hf = hora_texto_v95(sel.get("desde")), hora_texto_v95(sel.get("hasta"))
            base_a, base_b = minutos_v95(hi0), minutos_v95(hf0); a, b = minutos_v95(hi), minutos_v95(hf)
            if None not in (base_a, base_b, a, b) and base_a <= a < b <= base_b:
                resultado.append({"dia": dia, "hora_inicio": hi, "hora_fin": hf, "horas": horas_intervalo_v95(hi, hf),
                                  "horario_comision_id": r.get("id")})
            else:
                errores.append(f"La franja de {dia} debe quedar entre {hi0} y {hf0}.")
    return resultado, round(sum(float(x.get("horas", 0) or 0) for x in resultado), 2), errores
