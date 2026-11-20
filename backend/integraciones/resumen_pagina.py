"""E4-05 — Transcripcion de la pestaña certificada "📊 Resumen docente" (``tab5``, entry l. 60845-61197) a datos de UI.

Misma convencion que ``analisis.pagina``: cada funcion reproduce, en el orden y con las expresiones del certificado,
lo que la pagina calcula y muestra sobre el namespace del motor certificado (motor de Analisis + complemento del
Resumen): rotulos, captions, avisos, ``st.metric`` (``analisis.pagina.metrica``), tablas (``st.dataframe`` ->
``analisis.pagina.tabla``) y la torta (``analisis.pagina.torta``, misma especificacion Vega-Lite).  Los bloques HTML
del certificado (tarjeta del resumen actual, cronograma semanal) se devuelven como datos; la UI los dibuja sin HTML
crudo.  No hay formulas propias: todo valor sale de las funciones certificadas.

La seccion "Mensaje para consultar la designación" (estado de consulta + writer + mensaje, l. 61200-61275) es E4-06.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd

from analisis import pagina as P
from materias.rules import presentar_unidades_academicas
from sueldos import rules as SR

from . import resumen_horas as RH

log = logging.getLogger("deptit.resumen_pagina")

SUBTITULO = "Resumen individual del docente"
INFO = ("Seleccioná un docente y un período para analizar designaciones, movimientos, investigación, "
        "comisiones, productividad y alertas. Las materias históricas se muestran acumuladas para todos los períodos.")
MSG_SIN_DOCENTES = "Todavía no hay docentes registrados."
MSG_SIN_PERIODOS = "Todavía no hay períodos registrados."
MSG_SIN_COINCIDENCIAS = "No hay docentes que coincidan con la búsqueda."
MSG_NO_ENCONTRADO = "No se encontró información del docente seleccionado."
COLUMNAS_SELECCION = {"nombre_completo": "Docente", "cuil": "CUIL", "legajo": "Legajo", "titulo": "Título",
                      "tipo_docente": "Tipo"}
CAPTION_DESIGNACIONES = ("Se muestran las designaciones reales del mismo CUIL en todos los departamentos para el período "
                         "equivalente. En docentes prestados la designación permanece en el departamento de origen; no "
                         "se duplica en el receptor.")
CAPTION_ACTOS = ("Histórico completo del docente. Se muestran únicamente el código del acto, la dependencia emisora, "
                 "el tipo de movimiento y su detalle. Incluye documentos del repositorio, disposiciones generadas por la "
                 "app y resoluciones informadas en sus designaciones.")
CAPTION_VARIACION_NETA = "Variación neta de horas en el período."
CAPTION_FUNCIONES_ND = ("Estas funciones pertenecen a designaciones administrativas/no docentes. "
                        "Se muestran como información de la persona, pero no forman parte de la productividad docente.")
COLS_ACTIVIDADES = ["periodo", "departamento_asignacion", "titulo", "rol", "estado_actividad", "estado_asignacion",
                    "observaciones"]


def _limpio(ns: dict, v: Any) -> str:
    return ns["limpiar_texto_tabla"](v)


def _unidades_academicas(df: Optional[pd.DataFrame], columna: str) -> Optional[pd.DataFrame]:
    """6A-B3: la columna de unidad/es académica/s se presenta con la regla común (``materias.rules``); el dato
    almacenado no cambia."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty or columna not in df.columns:
        return df
    df = df.copy()
    df[columna] = df[columna].map(presentar_unidades_academicas)
    return df


def _seccion_tabla(titulo: str, df: Optional[pd.DataFrame], vacio: str, caption: Optional[str] = None,
                   tono_vacio: str = "info") -> dict:
    hay = df is not None and isinstance(df, pd.DataFrame) and not df.empty
    return {"titulo": titulo, "caption": caption, "tabla": P.tabla(df) if hay else None,
            "vacio": None if hay else {"tono": tono_vacio, "texto": vacio}}


# ------------------------------------------------------------------------------------------ datos generales
def datos_generales(ns: dict, fila_doc: pd.Series, cuil: str, periodo_id: int) -> dict:
    """l. 60910-60973."""
    nombre = _limpio(ns, fila_doc.get("nombre_completo", "")) or "Docente"
    estado = ns["estado_actual_docente"](cuil)
    legajo = _limpio(ns, fila_doc.get("legajo", "")) or "-"
    cuil_txt = _limpio(ns, fila_doc.get("cuil", "")) or "-"
    ini = fila_doc["fecha_inicio_historica"]
    fecha_inicio_hist = ini if pd.notna(ini) and str(ini).strip() != "" else "-"
    ult = fila_doc["ultima_fecha_alta"]
    ultima_fecha_alta = ult if pd.notna(ult) and str(ult).strip() != "" else "-"
    fecha_fin_doc = ns["fecha_finalizacion_resumen_docente"](cuil, periodo_id) or "-"
    tray = ns["get_trayectoria_docente_institucional_v149"](cuil, periodo_id)  # USE_POSTGRESQL
    fecha_inicio_hist = tray.get("inicio_historico") or fecha_inicio_hist
    ultima_fecha_alta = tray.get("ultima_alta") or ultima_fecha_alta
    fecha_fin_doc = tray.get("vencimiento_periodo") or fecha_fin_doc
    mail = _limpio(ns, fila_doc.get("email", "")) or "-"
    telefono = _limpio(ns, fila_doc.get("telefono", "")) or "-"
    grado = str(fila_doc.get("titulo") or "-").strip() or "-"
    posgrado = str(fila_doc.get("titulo_posgrado") or "-").strip() or "-"
    nivel = SR.nivel_posgrado_v256(fila_doc.get("nivel_posgrado_salarial", ""))
    ant_raw = fila_doc.get("antiguedad_anios")
    ant_informada = not (ant_raw is None or pd.isna(ant_raw))
    ant = SR.antiguedad_entera_v256(ant_raw)
    obs = str(fila_doc.get("observaciones") or "").strip()
    return {
        "nombre": nombre, "cuil": cuil_txt, "legajo": legajo,
        "situacion": {"texto": estado, "tono": "success" if str(estado).lower().startswith("activo") else "info"},
        # f"**Inicio histórico:** {valor}": el texto del objeto, como el certificado
        "trayectoria": {"inicio_historico": str(fecha_inicio_hist), "ultima_alta": str(ultima_fecha_alta),
                        "finalizacion": str(fecha_fin_doc)},
        "contacto": {"mail": mail, "telefono": telefono},
        "formacion": {"grado": grado, "posgrado": posgrado, "nivel": nivel or "Sin adicional",
                      "antiguedad": (f"**Antigüedad:** {ant} años" if ant_informada
                                     else "**Antigüedad:** no informada · para sueldo se toman 0 años (20%)")},
        "observaciones": obs or None,
    }


# ------------------------------------------------------------------------------------------ tarjeta resumen actual
def _corregir_situacion(ns: dict, cuil: str, periodo_id: int, fila_periodo: Optional[dict], resumen: dict) -> dict:
    """fix-horas-en-resumen-docente (Bugs A y B, ver ``integraciones.resumen_horas``): reemplaza en el resumen del
    motor los datos de cargos, horas, departamentos y evolución por los calculados con la fuente institucional de la
    tabla "Designaciones institucionales del docente" y la regla ``base + variación neta = final``.  Estado de la
    designación, funciones no docentes y cambios de cargo siguen siendo los del motor.  Si el cálculo no aplica
    (``None``) o falla, se conserva el resumen del motor."""
    try:
        sit = RH.situacion_desde_motor(ns, cuil, periodo_id, fila_periodo, resumen)
    except Exception as exc:  # la tarjeta nunca deja la página sin respuesta
        log.warning("resumen_horas: se conserva la tarjeta del motor (%s)", type(exc).__name__)
        return resumen
    if sit is None:
        return resumen
    return {
        **resumen,
        "departamentos_periodo": sit["departamentos"],
        "horas_actuales": sit["horas_finales"],
        "horas_total_departamentos": sit["horas_finales"],
        # Un único concepto de variación en toda la tarjeta: el indicador "Aumento / disminución" y la "Evolución de
        # horas del período" muestran la MISMA variación neta (altas, bajas, aumentos y disminuciones).
        "variacion_horas": sit["variacion_neta"],
        "variacion_es_neta": True,
        "baja_en_periodo": sit["baja_en_periodo"],
        "cargos_actuales": sit["cargos"] + sit["suspendidas"],
        "balance_horas_periodo": {
            "horas_inicio_operativo": sit["horas_base"],
            "variacion_operativa": sit["variacion_neta"],
            "horas_resultado_operativo": sit["horas_finales"],
        },
    }


def tarjeta(ns: dict, cuil: str, periodo_id: int, periodo_nombre: str, fila_periodo: Optional[dict] = None) -> dict:
    """``render_tarjeta_resumen_actual_docente`` (l. 27714-27838), con la situación institucional corregida."""
    resumen = _corregir_situacion(ns, cuil, periodo_id, fila_periodo,
                                  dict(ns["get_resumen_actual_periodo_docente"](cuil, periodo_id) or {}))
    prestado = bool(ns["es_docente_prestado_local"](cuil))
    aviso_prestado = None
    if prestado:
        deps = [_limpio(ns, d.get("departamento", "")) for d in (resumen.get("departamentos_periodo") or [])
                if _limpio(ns, d.get("departamento", ""))]
        origen = " / ".join(dict.fromkeys(deps)) or "su departamento de origen"
        aviso_prestado = (f"📌 DOCENTE PRESTADO: la designación sigue perteneciendo a {origen}. "
                          "Esta vista consulta y muestra esos datos institucionales sin copiar la designación "
                          "al departamento receptor.")
    variacion = float(resumen.get("variacion_horas", 0) or 0)
    historica = bool(resumen.get("lectura_historica"))
    deptos = resumen.get("departamentos_periodo") or []
    compartido = len(deptos) > 1
    if resumen.get("baja_en_periodo"):
        cargos = ["Baja en el período"]
    else:
        cargos = list(resumen.get("cargos_actuales") or ["Sin cargo activo en el período"])
    cambios = list(resumen.get("cambios_cargo") or ["Sin cambios de cargo registrados."])
    if compartido:
        label_cargos = "Cargo/s por departamento"
        label_horas = "Horas totales del período" if historica else "Horas actuales totales"
    else:
        label_cargos = "Cargo/s en el período" if historica else "Cargo/s actual/es"
        label_horas = "Horas del período" if historica else "Horas actuales"
    fnd = resumen.get("funciones_no_docentes") or []
    evol = resumen.get("balance_horas_periodo") or {}
    evolucion = None
    if evol:
        inicio = float(evol.get("horas_inicio_operativo") or 0)
        var = float(evol.get("variacion_operativa") or 0)
        res = float(evol.get("horas_resultado_operativo") or 0)
        if abs(var) < 1e-9:
            var = 0.0
        if abs(res) < 1e-9:
            res = 0.0
        evolucion = {
            "titulo": "Evolución de horas del período",
            "base": {"label": "Horas base del período", "valor": f"{inicio:g} hs"},
            "movimiento": {"label": "Baja en el período" if abs(float(res or 0)) < 1e-9 and var < 0
                           else "Aumento / disminución",
                           "valor": f"{'+' if var > 0 else ''}{var:g} hs",
                           "tono": "positivo" if var > 0 else ("negativo" if var < 0 else "neutro")},
            "resultado": {"label": "Horas del período" if historica else "Horas actuales", "valor": f"{res:g} hs"},
        }
    deptos_tabla = None
    if compartido or prestado:
        df = pd.DataFrame(deptos)
        cols = ["departamento", "cargo/s en el período", "horas"]
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        deptos_tabla = P.tabla(df[cols])
    return {
        "aviso_prestado": aviso_prestado,
        "titulo": f"{'Resumen histórico del período' if historica else 'Resumen actual del período'} — {periodo_nombre}",
        "estado_designacion": (f"Estado de la designación: **{resumen.get('estado_designacion_visible')}**"
                               if resumen.get("estado_designacion_visible") else None),
        "funciones_no_docentes": ({"titulo": "🧭 Funciones no docentes", "caption": CAPTION_FUNCIONES_ND,
                                   "tabla": P.tabla(pd.DataFrame(fnd))} if fnd else None),
        "cargos": {"label": label_cargos, "lineas": cargos},
        "horas": {"label": label_horas, "valor": f"{resumen.get('horas_actuales', 0):g} hs"},
        "variacion": {"label": "Aumento / disminución", "valor": f"{'+' if variacion > 0 else ''}{variacion:g} hs",
                      "tono": "positivo" if variacion > 0 else ("negativo" if variacion < 0 else "neutro"),
                      # Sin la corrección (respaldo: tarjeta del motor) el valor sigue siendo el del motor y su leyenda.
                      "caption": (CAPTION_VARIACION_NETA if resumen.get("variacion_es_neta")
                                  else "Solo cambios reales de dedicación.")},
        "cambios": {"label": "Cambio de cargo", "lineas": cambios},
        "evolucion": evolucion,
        "compartido": ("🧩 DOCENTE COMPARTIDO: tiene designaciones en más de un departamento para este período."
                       if compartido else None),
        "caption_origen": ("Designación/es consultada/s en el departamento de origen:"
                           if (prestado and not compartido) else None),
        "departamentos": deptos_tabla,
    }


# ------------------------------------------------------------------------------------------ cronograma
def cronograma(ns: dict, cuil: str, periodo_id: int, periodo_nombre: str) -> dict:
    """``render_cronograma_semanal_docente`` (l. 31994-32061): misma grilla 08:00-23:00 por hora y mismos rotulos."""
    df = ns["get_horarios_docente_periodo"](cuil, periodo_id)
    df = ns["_expandir_horarios_por_materias_comision_v131"](df)
    slots = list(range(8 * 60, 23 * 60, 60))
    dias = list(ns["DIAS_SEMANA_V95"])
    celdas: dict = {}
    if df is not None and not df.empty:
        for _, r in df.iterrows():
            d = ns["_normalizar_dia_v95"](r.get("dia"))
            a, b = ns["_minutos_v95"](r.get("hora_inicio")), ns["_minutos_v95"](r.get("hora_fin"))
            if d not in dias or a is None or b is None:
                continue
            asignatura_base = " ".join(str(r.get("asignatura", "") or "").split())
            especifica = " ".join(str(r.get("materia_especifica", "") or "").split())
            nombre = ns["_nombre_materia_visible_v138"](r.get("codigo_materia", ""), asignatura_base, especifica)
            if especifica:
                etiqueta = especifica if len(especifica) <= 22 else especifica[:21] + "…"
            else:
                etiqueta = ns["_abreviar_asignatura_v95"](nombre, max_len=14)
            hi, hf = ns["_hora_texto_v95"](r.get("hora_inicio")), ns["_hora_texto_v95"](r.get("hora_fin"))
            dep = _limpio(ns, r.get("departamento_comision", ""))
            titulo = f"{nombre} · {hi}–{hf}" + (f" · {dep}" if dep else "")
            info = {"label": etiqueta, "title": titulo}
            for s in slots:
                if max(s, a) < min(s + 60, b):
                    lista = celdas.setdefault((s, d), [])
                    if (info["label"], info["title"]) not in [(x["label"], x["title"]) for x in lista]:
                        lista.append(info)
    filas = []
    for s in slots:
        fila = {"hora": f"{s // 60:02d}:00–{(s + 60) // 60:02d}:00", "celdas": []}
        for d in dias:
            items = celdas.get((s, d), [])
            if items:
                labels, titulos = [], []
                for it in items:
                    if it["label"] not in labels:
                        labels.append(it["label"])
                    if it["title"] not in titulos:
                        titulos.append(it["title"])
                fila["celdas"].append({"labels": labels, "titulo": " | ".join(titulos)})
            else:
                fila["celdas"].append(None)
        filas.append(fila)
    caption = ("Sin ocupación horaria registrada para este período." if df is None or df.empty else
               "Cronograma compacto de 08:00 a 23:00. Posá el cursor sobre un bloque para ver la asignatura completa y "
               "su franja horaria exacta.")
    return {"titulo": f"Cronograma semanal — {periodo_nombre}", "dias": dias, "filas": filas, "caption": caption}


# ------------------------------------------------------------------------------------------ productividad
def productividad(ns: dict, cuil: str, periodo_id: int, periodo_nombre: str) -> dict:
    """l. 61121-61186."""
    prod = ns["get_productividad_docente_institucional_v149"](cuil, periodo_id)
    disp = float(prod.get("horas_disponibles", 0) or 0)
    metricas = [
        P.metrica("Hs contratadas", prod.get("horas_contratadas", 0)),
        P.metrica("Hs frente a comisión", prod.get("horas_en_comisiones", 0)),
        P.metrica("Hs no lectivas", prod.get("horas_no_lectivas", 0)),
        P.metrica("Productividad", f"{prod.get('porcentaje', 0)}%"),
        P.metrica("Hs investigación", prod.get("horas_en_investigacion", 0)),
        P.metrica("Hs extensión", prod.get("horas_en_extension", 0)),
        P.metrica("Hs utilizadas", prod.get("horas_utilizadas", 0)),
        P.metrica("Disponibles" if disp >= 0 else "Exceso", abs(disp)),
    ]
    detalle = prod.get("detalle_no_lectivas_departamentos") or []
    hs_c = float(prod.get("horas_contratadas", 0) or 0)
    hs_com = float(prod.get("horas_en_comisiones", 0) or 0)
    hs_nl = float(prod.get("horas_no_lectivas", 0) or 0)
    hs_inv = float(prod.get("horas_en_investigacion", 0) or 0)
    hs_ext = float(prod.get("horas_en_extension", 0) or 0)
    hs_uso = float(prod.get("horas_utilizadas", hs_com + hs_nl + hs_inv + hs_ext) or 0)
    hs_disp, hs_exc = max(hs_c - hs_uso, 0), max(hs_uso - hs_c, 0)
    etiquetas, valores = [], []
    for et, v in [("Hs frente a comisión", hs_com), ("Hs no lectivas", hs_nl), ("Hs en investigación", hs_inv),
                  ("Hs en extensión", hs_ext), ("Hs disponibles", hs_disp), ("Hs excedidas", hs_exc)]:
        if v > 0:
            etiquetas.append(et)
            valores.append(v)
    torta = P.torta(ns, pd.DataFrame({"concepto": etiquetas, "horas": valores}), "concepto", "horas") \
        if valores else None
    return {
        "titulo": f"Productividad del período — {periodo_nombre}",
        "caption": ("Vista individual institucional: consolida designaciones, comisiones, investigación y extensión "
                    "del mismo CUIL en todos los departamentos."),
        "metricas": metricas,
        "detalle_no_lectivas": ({"titulo": "Ver cálculo de horas no lectivas por comisión / departamento",
                                 "tabla": P.tabla(pd.DataFrame(detalle))} if detalle else None),
        "torta": torta,
        "sin_torta": None if valores else "No hay horas contratadas ni horas asignadas para graficar productividad.",
    }


# ------------------------------------------------------------------------------------------ resumen completo
def resumen(ns: dict, cuil: str, periodo_id: int, periodo_nombre: str, fila_periodo: dict,
            sueldo: dict, actividades: pd.DataFrame) -> dict:
    """Secciones 1-13 de la pestaña (l. 60900-61197), en orden."""
    es_hist = bool(ns["es_periodo_historico_contexto_v182"](periodo_id))
    df_docente, _desig, _mov = ns["get_resumen_docente"](cuil)
    if df_docente.empty:
        return {"error": MSG_NO_ENCONTRADO}
    fila_doc = df_docente.iloc[0]
    if isinstance(sueldo, dict) and isinstance(sueldo.get("perfil"), dict):
        # Etapa 5 / Tanda B (B1/B2): ``get_resumen_docente`` no selecciona ``antiguedad_anios`` ni
        # ``nivel_posgrado_salarial`` (el certificado mostraba siempre "no informada" y "Sin adicional"); se usa la
        # ficha del docente en el departamento de la sesion, la MISMA con la que se calcula el sueldo estimado.
        fila_doc = fila_doc.copy()
        fila_doc["antiguedad_anios"] = sueldo["perfil"]["antiguedad_anios"]
        fila_doc["nivel_posgrado_salarial"] = sueldo["perfil"]["nivel_posgrado_salarial"]
    per = periodo_nombre
    df_inv = ns["get_investigacion_docente"](cuil, periodo_id, incluir_bajas=es_hist, todos_departamentos=True)
    df_ext = ns["get_extension_docente"](cuil, periodo_id, incluir_bajas=es_hist, todos_departamentos=True)
    df_com = ns["get_comisiones_docente"](cuil, periodo_id)
    if not df_com.empty and "asignatura" in df_com.columns:
        df_com = df_com.copy()
        df_com["asignatura"] = df_com.apply(lambda r: ns["_nombre_materia_visible_v138"](
            r.get("codigo_materia", ""), r.get("asignatura", ""), r.get("materia_especifica", "")), axis=1)
    df_com = _unidades_academicas(df_com, "escuela")
    df_sup = ns["get_superposiciones_docente_institucional_v149"](cuil, periodo_id)
    act = actividades
    if act is not None and not act.empty:
        act = act[[c for c in COLS_ACTIVIDADES if c in act.columns]]
    sup = _seccion_tabla(f"Alertas de superposición — {per}", df_sup,
                         "No se detectan superposiciones horarias para este docente en el período seleccionado.",
                         tono_vacio="success")
    if sup["tabla"] is not None:
        sup["aviso"] = ("Este docente tiene superposiciones horarias entre sus comisiones. En la vista individual se "
                        "consideran todos los departamentos; las alertas generales de cada departamento siguen siendo "
                        "locales.")
    return {
        "datos_generales": datos_generales(ns, fila_doc, cuil, periodo_id),
        "tarjeta": tarjeta(ns, cuil, periodo_id, per, fila_periodo),
        "designaciones": _seccion_tabla(
            f"Designaciones institucionales del docente — {per}",
            ns["get_designaciones_docente_todos_departamentos_pg"](cuil, periodo_id),
            "Este docente no tiene designaciones registradas en el período seleccionado.", CAPTION_DESIGNACIONES),
        "actos": _seccion_tabla(
            "📄 Resoluciones, disposiciones y actos administrativos", ns["get_actos_docente_resumen_v263"](cuil),
            "No hay resoluciones, disposiciones u otros actos administrativos vinculados a este docente.",
            CAPTION_ACTOS),
        "sueldo": sueldo_seccion(sueldo, per),
        "investigacion": _seccion_tabla(
            f"Investigación del docente — {per}", df_inv.drop(columns=["id"], errors="ignore"),
            "Este docente no tiene horas/proyectos de investigación asignados en el período seleccionado.",
            "Se consolidan las asignaciones de investigación del mismo CUIL en todos los departamentos de la "
            "institución."),
        "extension": _seccion_tabla(
            f"Extensión del docente — {per}", df_ext.drop(columns=["id"], errors="ignore"),
            "Este docente no tiene horas/proyectos de extensión asignados en el período seleccionado.",
            "Se consolidan las asignaciones de extensión del mismo CUIL en todos los departamentos de la institución."),
        "actividades": _seccion_tabla(
            f"Actividades Especiales del docente — {per}", act,
            "Este docente no tiene Actividades Especiales registradas en el período seleccionado.",
            "Las Actividades Especiales son administrativas: no consumen horas de dedicación y no ocupan el "
            "cronograma semanal."),
        "comisiones": _seccion_tabla(
            f"Comisiones asignadas al docente — {per}", df_com,
            "Este docente no tiene comisiones asignadas en el período seleccionado.",
            "Vista institucional: incluye las comisiones del mismo CUIL en todos los departamentos para el período "
            "equivalente."),
        "cronograma": cronograma(ns, cuil, periodo_id, per),
        "superposiciones": sup,
        "productividad": productividad(ns, cuil, periodo_id, per),
        "materias_historicas": _seccion_tabla(
            "Materias históricas del docente",
            _unidades_academicas(ns["get_materias_historicas_docente"](cuil), "escuelas"),
            "Todavía no hay materias históricas registradas para este docente en comisiones.",
            "Esta sección no depende del período seleccionado: acumula todos los períodos cargados."),
    }


def sueldo_seccion(s: dict, periodo_nombre: str) -> dict:
    """l. 61008-61030 con ``SueldosService.sueldo_docente_resumen`` (deudas H2 corregidas en la Etapa 5 / B1)."""
    out = {"titulo": f"💰 Sueldo estimado — {periodo_nombre}", "vacio": None, "caption": None, "tabla": None,
           "total": None}
    if s["estado"] != "ok":
        out["vacio"] = {"tono": "info", "texto": s["mensaje"]}
        return out
    filas = s["filas_formateadas"]
    columnas = list(filas[0].keys()) if filas else []
    out["caption"] = s["caption"]
    out["tabla"] = {"columnas": columnas, "filas": [[P.jsonable(f.get(c)) for c in columnas] for f in filas]}
    out["total"] = P.metrica("Total estimado mensual del docente", s["total_formateado"])
    return out


__all__ = ["resumen", "datos_generales", "tarjeta", "cronograma", "productividad", "sueldo_seccion", "SUBTITULO",
           "INFO", "MSG_SIN_DOCENTES", "MSG_SIN_PERIODOS", "MSG_SIN_COINCIDENCIAS", "MSG_NO_ENCONTRADO",
           "COLUMNAS_SELECCION"]


# ------------------------------------------------------------------------------------------ E4-06: consulta y mensaje
TITULO_CONSULTA = "Mensaje para consultar la designación"
CAPTION_CONSULTA = ("Genera un correo individual con la presentación de la autoridad del departamento, todas las "
                    "designaciones, las comisiones y los proyectos de investigación y extensión registrados para el "
                    "cuatrimestre seleccionado.")
OPCIONES_CONSULTA = ["⚪ Sin estado", "🟢 Designación confirmada", "🟡 Consulta Enviada", "🔴 Rever Designación"]
MAPA_CONSULTA = {"⚪ Sin estado": "", "🟢 Designación confirmada": "Designación confirmada",
                 "🟡 Consulta Enviada": "Consulta Enviada", "🔴 Rever Designación": "Rever Designación"}
_EQUIVALENCIAS_CONSULTA = {"Consulta enviada": "Consulta Enviada", "Rever designación": "Rever Designación"}


def semaforo_consulta(estado: Any, prefijo: str = "Estado seleccionado") -> dict:
    """``mostrar_estado_consulta_designacion`` (l. 23877) con el semaforo de Disposiciones (D12)."""
    from disposiciones.rules import estado_consulta_mostrado
    s = estado_consulta_mostrado(estado)
    if s["estado"]:
        return {"tono": s["tono"], "texto": f"{s['icono']} {prefijo}: **{s['estado']}**"}
    return {"tono": "info", "texto": f"⚪ {prefijo}: **sin estado registrado**"}


def consulta(estado_raw: Any, periodo_nombre: str) -> dict:
    """l. 61200-61275 sin ejecutar nada: estado actual (``get_estado_consulta_designacion``), radio certificado y el
    semaforo de cada opcion (la UI lo muestra al elegir, como ``mostrar_estado_consulta_designacion``)."""
    actual = str(estado_raw or "")
    actual = _EQUIVALENCIAS_CONSULTA.get(actual, actual)
    etiqueta = next((et for et, valor in MAPA_CONSULTA.items() if valor == actual), "⚪ Sin estado")
    return {
        "titulo": f"{TITULO_CONSULTA} — {periodo_nombre}",
        "caption": CAPTION_CONSULTA,
        "radio": "Estado de la consulta al docente",
        "opciones": [{"etiqueta": et, "valor": MAPA_CONSULTA[et], "semaforo": semaforo_consulta(MAPA_CONSULTA[et])}
                     for et in OPCIONES_CONSULTA],
        "seleccion": etiqueta,
        "boton_guardar": "💾 Guardar estado de la consulta",
        "boton_mensaje": "✉️ Generar mensaje para el docente",
        "asunto_label": "Asunto sugerido",
        "cuerpo_label": "Mensaje listo para copiar y pegar en el correo",
    }
