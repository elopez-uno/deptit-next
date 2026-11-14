"""Transcripcion de la pagina certificada ``if modulo == "🏠 Inicio":`` (entry l. 59280-59794) a datos de UI.

Cada funcion reproduce, en el mismo orden y con las mismas expresiones, lo que la pagina muestra a partir del tablero
certificado ``_inicio_datos_tablero_cache`` (v188 -> v165 -> v146) ejecutado por el motor de lectura de Analisis
(D-AN1): rotulos, ``st.metric`` ya formateados (``:g``, ``.2f`` sin ceros), tablas de detalle con las columnas y
renombres de ``_inicio_mostrar_detalle`` (l. 34187), las 2 barras de ``_inicio_barra_simple`` (l. 34211) con la MISMA
especificacion Vega-Lite y los textos.  No hay formulas propias: todo valor sale del tablero certificado (anomalias
incluidas, docs/inicio_analysis.md §36).  Diferencias conscientes NEXT: titulo con el departamento OPERATIVO (D-AN4) y
caption del boton "Actualizar" sin la cache de 60 s (D-AN3).
"""
from __future__ import annotations

import textwrap
from typing import Any, Optional

import pandas as pd

from analisis.motor.ref.extracted_batch01.otros import _inicio_estado_linea
from analisis.pagina import metrica, tabla, tabla_registros

# Destinos de navegacion: rotulo del modulo certificado -> clave del shell NEXT (policy.MODULES_BASE).
DESTINOS = {
    "🏛️ Consolidado institucional": "consolidado",
    "🗓️ Períodos": "periodos",
    "📋 Comisiones": "comisiones",
    "📑 Designaciones": "designaciones",
    "👨‍🏫 Docentes": "docentes",
    "📊 Análisis": "analisis",
}
SIN_DEPARTAMENTO = "Departamento correspondiente"
MSG_INSTITUCIONAL = ("Estás en el ámbito institucional. Seleccioná un departamento desde la barra lateral "
                     "para ver su tablero operativo, o ingresá a **Consolidado institucional** para comparar "
                     "departamentos.")
MSG_SIN_PERIODO = "No hay un período abierto. Para comenzar a operar, creá o abrí el período académico correspondiente."
AYUDA_SIN_PERIODO = textwrap.dedent("""
    1. **Períodos** — crear/abrir el período académico.
    2. **Docentes** — completar la base maestra de personas.
    3. **Designaciones** — registrar cargo, dedicación, horas y tipo de designación.
    4. **Materias** — mantener carreras, planes, materias y opciones curriculares.
    5. **Comisiones** — abrir comisiones, horarios, códigos y equipos docentes.
    6. **Investigación / Extensión** — registrar proyectos y asignaciones cuando corresponda.
    7. **Actividades Especiales** — registrar actividades administrativas que no consumen horas.
    8. **Disposiciones** — generar el instrumento con la información ya validada.
    9. **Análisis / Movimientos** — auditar salud, productividad y trazabilidad.
    """).strip()
AYUDA_TABLERO = textwrap.dedent("""
    **Flujo recomendado**

    1. **Períodos** — crear/abrir el período académico.
    2. **Docentes** — completar la base maestra.
    3. **Designaciones** — registrar cargo, dedicación, horas y tipo de designación.
    4. **Materias** — mantener unidades académicas, carreras, planes, materias y opciones curriculares. Para Optativas/Electivas, definir primero opciones y habilitaciones.
    5. **Comisiones** — abrir comisiones, horarios, códigos compartidos, opción curricular concreta y equipos docentes.
    6. **Investigación / Extensión** — registrar proyectos y asignar docentes, roles y horas cuando corresponda.
    7. **Actividades Especiales** — registrar actividades administrativas del período; no consumen horas del cronograma.
    8. **Disposiciones** — generar la disposición una vez revisada la situación del docente.
    9. **Análisis / Movimientos** — controlar salud, productividad y trazabilidad.

    **Regla práctica:** para correcciones puntuales usá las pantallas de edición. Reservá las cargas rápidas para altas masivas o actualizaciones planificadas.
    """).strip()
# D-AN3: el tablero se calcula en cada consulta (sin la cache de 60 s del certificado); el boton vuelve a pedirlo.
CAPTION_ACTUALIZAR = ("El tablero se calcula con los datos vigentes en cada consulta. Podés forzar la actualización con "
                      "el botón.")
CAPTION_HISTORICO = "Foto histórica calculada exactamente al último día del período. "
CAPTION_DETALLE = "Los identificadores mostrados te permiten ubicar rápidamente el caso en el módulo correspondiente."
MSG_SIN_GRAFICO = "Todavía no hay datos para graficar."
COLS_VENCIMIENTOS = ["Docente", "Designación", "Vencimiento", "Días"]


def boton(label: str, destino: str, primario: bool = False) -> dict:
    return {"label": label, "destino": DESTINOS[destino], "primario": primario}


def titulo(departamento: Optional[dict]) -> str:
    """D-AN4: ``Inicio — {departamento operativo de la sesion}`` (``" ".join(split())`` de l. 6631)."""
    nombre = " ".join(str((departamento or {}).get("nombre") or "").strip().split())
    return f"Inicio — {nombre or SIN_DEPARTAMENTO}"


def institucional() -> dict:
    """Coordinador sin departamento operativo (l. 59286-59299): no se calcula ningun tablero."""
    return {"mensaje": MSG_INSTITUCIONAL, "boton": boton("🏛️ Ir al consolidado institucional",
                                                        "🏛️ Consolidado institucional", True)}


def sin_periodo() -> dict:
    """Sin periodo abierto (l. 59300-59324)."""
    return {"mensaje": MSG_SIN_PERIODO, "boton": boton("🗓️ Ir a Períodos", "🗓️ Períodos", True),
            "ayuda": {"titulo": "▶️ Ayuda y flujo recomendado", "abierto": True, "texto": AYUDA_SIN_PERIODO}}


# ------------------------------------------------------------------------------------------ encabezado (l. 59326-59353)
def encabezado(ns: dict, periodo_abierto: dict, hoy: Any) -> dict:
    fecha_segura = ns["_inicio_fecha_segura"]
    periodo_id = int(periodo_abierto["id"])
    nombre = str(periodo_abierto.get("nombre") or "")
    fi, ff = fecha_segura(periodo_abierto.get("fecha_inicio")), fecha_segura(periodo_abierto.get("fecha_fin"))
    fi_txt = fi.strftime("%d/%m/%Y") if fi else str(periodo_abierto.get("fecha_inicio") or "")
    ff_txt = ff.strftime("%d/%m/%Y") if ff else str(periodo_abierto.get("fecha_fin") or "")
    historico = bool(ns["es_periodo_historico_contexto_v182"](periodo_id))
    rotulo = "Foto al cierre" if historico else "Período actual"
    out = {"linea": f"**{rotulo}:** {nombre} &nbsp; · &nbsp; {fi_txt} al {ff_txt}", "historico": historico,
           "progreso": None, "caption_progreso": None}
    if fi and ff and ff >= fi:
        total = max((ff - fi).days + 1, 1)
        transcurridos = min(max((hoy - fi).days + 1, 0), total)
        progreso = transcurridos / total
        if 0 <= progreso <= 1:
            out["progreso"] = progreso
            if hoy < fi:
                out["caption_progreso"] = f"El período comienza en {(fi - hoy).days} día/s."
            elif hoy > ff:
                out["caption_progreso"] = "El período ya alcanzó su fecha de finalización prevista."
            else:
                out["caption_progreso"] = f"Avance calendario del período: {round(progreso * 100)} % · Día {transcurridos} de {total}."
    out["actualizar"] = {"label": "🔄 Actualizar tablero",
                         "caption": (CAPTION_HISTORICO if historico else "") + CAPTION_ACTUALIZAR}
    return out


# ------------------------------------------------------------------------------------------ helpers de detalle
def detalle(df: Any, columnas: Optional[list] = None, renombres: Optional[dict] = None,
            texto_vacio: str = "No se detectaron casos.") -> dict:
    """``_inicio_mostrar_detalle`` (l. 34187): columnas existentes, renombradas, sin auxiliares ``_*``."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {"tabla": None, "caption": texto_vacio}
    vista = df.copy()
    if columnas:
        existentes = [c for c in columnas if c in vista.columns]
        if existentes:
            vista = vista[existentes].copy()
    if renombres:
        vista = vista.rename(columns={k: v for k, v in renombres.items() if k in vista.columns})
    auxiliares = [c for c in vista.columns if str(c).startswith("_")]
    if auxiliares:
        vista = vista.drop(columns=auxiliares, errors="ignore")
    return {"tabla": tabla(vista), "caption": CAPTION_DETALLE}


def barra(df: Any, categoria: str, valor: str, titulo_: str, caption: str) -> dict:
    """``_inicio_barra_simple`` (l. 34211): misma especificacion de ``st.vega_lite_chart``; vacio -> ``st.info``."""
    vacio = df is None or df.empty or float(
        pd.to_numeric(df.get(valor, pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) <= 0
    out = {"titulo": titulo_, "vacio": vacio, "mensaje": MSG_SIN_GRAFICO if vacio else None, "spec": None,
           "caption": caption}
    if not vacio:
        out["spec"] = {
            "data": {"values": tabla_registros(df)},
            "mark": {"type": "bar", "tooltip": True},
            "encoding": {
                "y": {"field": categoria, "type": "nominal", "sort": "-x", "title": None},
                "x": {"field": valor, "type": "quantitative", "title": None},
                "tooltip": [{"field": categoria, "type": "nominal"}, {"field": valor, "type": "quantitative"}],
            },
        }
    return out


def _dos(v: Any) -> str:
    return f"{float(v or 0):.2f}".rstrip("0").rstrip(".")


# ------------------------------------------------------------------------------------------ 1. Situacion (l. 59369-59486)
def _lista(ns: dict, df: Any, titulo_: str, vacio: str, no_docente: bool) -> dict:
    limpiar, clave, ad_honorem = ns["limpiar_texto_tabla"], ns["_clave_cuil"], ns["_es_ad_honorem_v162"]
    out = {"titulo": titulo_, "vacio": None, "personas": []}
    if df is None or df.empty:
        out["vacio"] = vacio
        return out
    lista = df.copy()
    lista["_cuil_clave"] = lista.get("CUIL", pd.Series(index=lista.index, dtype=str)).map(clave)
    lista = lista.sort_values([c for c in ["Persona", "Cargo", "Dedicación"] if c in lista.columns], kind="stable")
    for cuil_clave, grupo in lista.groupby("_cuil_clave", sort=False, dropna=False):
        fila_persona = grupo.iloc[0]
        nombre = limpiar(fila_persona.get("Persona", "")) or str(fila_persona.get("CUIL") or cuil_clave or "Sin identificar")
        cuil_visible = str(fila_persona.get("CUIL") or cuil_clave or "")
        designaciones = []
        for nro, (_, fila) in enumerate(grupo.iterrows(), start=1):
            cargo = limpiar(fila.get("Cargo", "")) or "—"
            ded = limpiar(fila.get("Dedicación", "")) or "—"
            hs = fila.get("Horas", "")
            tipo = limpiar(fila.get("Tipo de designación", "")) or "—"
            ah = limpiar(fila.get("Ad Honórem", "")) or "No"
            estado = limpiar(fila.get("Estado", "")) or "—"
            desde = limpiar(fila.get("Desde", "")) or "—"
            hasta = limpiar(fila.get("Hasta", "")) or "—"
            d = {"linea": f"**Designación {nro}:** {cargo} · {ded} · {hs} hs · {tipo} · "
                          f"{'Ad Honórem' if ad_honorem(ah) else 'Rentada'}",
                 "funciones": None, "caption": f"Estado: {estado} · Vigencia: {desde} a {hasta}"}
            if no_docente:
                funcion = limpiar(fila.get("Funciones", "")) or "SIN FUNCIONES CARGADAS"
                d["funciones"] = f"**Funciones que cumple:** {funcion}"
            designaciones.append(d)
        out["personas"].append({"encabezado": f"**{nombre}**  ·  CUIL {cuil_visible}", "designaciones": designaciones})
    return out


def situacion(ns: dict, datos: dict) -> dict:
    m = datos["metricas"]
    docentes = int(m.get("docentes_activos", 0) or 0)
    no_docentes = int(m.get("no_docentes_activos", 0) or 0)
    personas = int(m.get("personas_activas_totales", 0) or 0)
    comisiones = int(datos.get("comisiones_activas", 0) or 0)
    sin_cubrir = int(len(datos.get("df_sin_cubrir", pd.DataFrame())))
    criticas = int(datos.get("alertas_criticas", 0) or 0)
    df_nd = datos.get("df_no_docentes_detalle", pd.DataFrame()).copy()
    df_doc = datos.get("df_docentes_designaciones_detalle", pd.DataFrame()).copy()
    n_nd = int(len(df_nd)) if isinstance(df_nd, pd.DataFrame) else 0
    n_doc = int(len(df_doc)) if isinstance(df_doc, pd.DataFrame) else 0
    return {
        "titulo": "Situación del período",
        "tarjetas": [
            metrica("Docentes activos", docentes, caption="Personas con al menos una designación docente activa."),
            metrica("No docentes activos", no_docentes,
                    caption="Personas con designaciones activas para otras funciones."),
            metrica("Comisiones abiertas", comisiones, caption="Comisiones activas del período."),
            metrica("Comisiones sin cubrir", sin_cubrir, caption="Sin equipo docente asignado."),
            metrica("Alertas críticas", criticas, caption="Casos de intervención prioritaria."),
        ],
        "caption_dotacion": (f"Dotación consolidada: {personas} persona/s activa/s por CUIL único. "
                             "Una misma persona puede figurar en Docencia y No docencia si posee designaciones de "
                             "ambos tipos."),
        "listas": [
            _lista(ns, df_nd, f"🧭 Funciones no docentes del período ({n_nd} designación/es · {no_docentes} persona/s)",
                   "No hay designaciones activas para funciones no docentes en este período.", True),
            _lista(ns, df_doc, f"👨‍🏫 Designaciones docentes del período ({n_doc} designación/es · {docentes} persona/s)",
                   "No hay designaciones docentes activas en este período.", False),
        ],
    }


# ------------------------------------------------------------------------------------------ 2. Acciones (l. 59488-59581)
_COLS_PROBLEMAS = ["Docente", "CUIL", "codigo_materia", "asignatura", "materia_especifica", "Comisión",
                   "Cargo actual en comisión", "Cargo correcto según designación", "Estado", "Detalle"]
_REN_PROBLEMAS = {"codigo_materia": "Código", "asignatura": "Asignatura", "materia_especifica": "Materia específica"}


def acciones(datos: dict) -> dict:
    items = []
    sin_cubrir = int(len(datos.get("df_sin_cubrir", pd.DataFrame())))
    if sin_cubrir > 0:
        items.append({
            "icono": "🔴", "titulo": f"{sin_cubrir} comisión{'es' if sin_cubrir != 1 else ''} sin cubrir",
            "detalle": "Comisiones activas que todavía no tienen docentes asignados.",
            "boton": "Ver comisiones", "destino": "📋 Comisiones", "df": datos.get("df_sin_cubrir", pd.DataFrame()),
            "columnas": ["codigo_materia", "asignatura", "materia_especifica", "nombre_comision", "turno", "sede",
                         "modalidad", "carrera"],
            "renombres": {"codigo_materia": "Código", "asignatura": "Asignatura",
                          "materia_especifica": "Materia específica", "nombre_comision": "Comisión", "turno": "Turno",
                          "sede": "Sede", "modalidad": "Modalidad", "carrera": "Carrera/s"},
        })
    n_venc = int(len(datos.get("df_vencimientos", pd.DataFrame())))
    if n_venc > 0:
        items.append({
            "icono": "🟠",
            "titulo": f"{n_venc} designación{'es' if n_venc != 1 else ''} próxima{'s' if n_venc != 1 else ''} a vencer",
            "detalle": "Designaciones activas cuyo vencimiento previsto cae dentro de los próximos 30 días.",
            "boton": "Revisar designaciones", "destino": "📑 Designaciones",
            "df": datos.get("df_vencimientos", pd.DataFrame()), "columnas": COLS_VENCIMIENTOS, "renombres": {},
        })
    n_sin_carga = int(datos.get("docentes_sin_carga", 0) or 0)
    if n_sin_carga > 0:
        items.append({
            "icono": "🟠", "titulo": f"{n_sin_carga} docente{'s' if n_sin_carga != 1 else ''} sin carga",
            "detalle": "Docentes con designación activa, pero sin comisiones, investigación ni extensión asignada.",
            "boton": "Ver docentes", "destino": "👨‍🏫 Docentes", "df": datos.get("df_sin_carga", pd.DataFrame()),
            "columnas": ["Docente", "CUIL", "Designación/es activa/s", "Horas de designación", "Situación"],
            "renombres": {},
        })
    n_prob = int(datos.get("asignaciones_problema", 0) or 0)
    if n_prob > 0:
        items.append({
            "icono": "🔴",
            "titulo": f"{n_prob} asignación{'es' if n_prob != 1 else ''} docente{'s' if n_prob != 1 else ''} con problemas",
            "detalle": "Casos detectados por el diagnóstico oficial de cargos/designaciones del período.",
            "boton": "Revisar asignaciones", "destino": "📋 Comisiones", "df": datos.get("df_problemas", pd.DataFrame()),
            "columnas": _COLS_PROBLEMAS, "renombres": _REN_PROBLEMAS,
        })
    out = []
    for a in items:
        df = a["df"]
        out.append({"icono": a["icono"], "titulo": a["titulo"], "detalle": a["detalle"],
                    "expander": f"Ver casos detectados ({len(df) if isinstance(df, pd.DataFrame) else 0})",
                    "casos": detalle(df, columnas=a.get("columnas"), renombres=a.get("renombres")),
                    "boton": boton(a["boton"], a["destino"])})
    return {"titulo": "Acciones prioritarias", "items": out,
            "vacio": None if out else "No hay acciones prioritarias pendientes con las reglas actuales del sistema."}


# ------------------------------------------------------------------------------------------ 3. Salud (l. 59583-59687)
def salud(datos: dict) -> dict:
    n_super = int(len(datos.get("df_super", pd.DataFrame())))
    n_sobrecarga = int(len(datos.get("df_sobrecarga", pd.DataFrame())))
    n_sin_horario = int(len(datos.get("df_sin_horario", pd.DataFrame())))
    n_dup = int(len(datos.get("df_duplicados", pd.DataFrame())))
    n_prob = int(datos.get("asignaciones_problema", 0) or 0)
    periodo_ok = bool(datos.get("periodo_ok", False))
    super_estado = _inicio_estado_linea(n_super, "Sin casos", gravedad="alta")
    sobre_estado = _inicio_estado_linea(n_sobrecarga, "Sin casos", gravedad="alta")
    horario_estado = _inicio_estado_linea(n_sin_horario, "Sin casos", gravedad="media")
    dup_estado = _inicio_estado_linea(n_dup, "Sin casos", gravedad="alta")
    items = [
        {"etiqueta": "Superposiciones horarias", "icono": super_estado[0], "resultado": super_estado[1],
         "df": datos.get("df_super", pd.DataFrame()),
         "columnas": ["docente", "cuil", "dia", "materia_1", "comision_1", "horario_1", "materia_2", "comision_2",
                      "horario_2"],
         "renombres": {"docente": "Docente", "cuil": "CUIL", "dia": "Día", "materia_1": "Materia 1",
                       "comision_1": "Comisión 1", "horario_1": "Horario 1", "materia_2": "Materia 2",
                       "comision_2": "Comisión 2", "horario_2": "Horario 2"},
         "vacio": "No se detectaron superposiciones horarias."},
        {"etiqueta": "Exceso de dedicación", "icono": sobre_estado[0], "resultado": sobre_estado[1],
         "df": datos.get("df_sobrecarga", pd.DataFrame()),
         "columnas": ["docente", "horas_contratadas", "horas_registradas", "horas_no_lectivas",
                      "porcentaje_productividad", "exceso"],
         "renombres": {"docente": "Docente", "horas_contratadas": "Horas de designación",
                       "horas_registradas": "Horas registradas", "horas_no_lectivas": "Horas no lectivas",
                       "porcentaje_productividad": "Productividad %", "exceso": "Exceso"},
         "vacio": "No se detectaron docentes con horas registradas por encima de su designación."},
        {"etiqueta": "Asignaciones docentes", "icono": ("🟢" if n_prob == 0 else "🔴"),
         "resultado": ("Válidas · Sin problemas" if n_prob == 0 else f"{n_prob} caso{'s' if n_prob != 1 else ''} a revisar"),
         "df": datos.get("df_problemas", pd.DataFrame()), "columnas": _COLS_PROBLEMAS, "renombres": _REN_PROBLEMAS,
         "vacio": "El diagnóstico oficial no detectó asignaciones docentes que requieran revisión."},
        {"etiqueta": "Comisiones sin horario", "icono": horario_estado[0], "resultado": horario_estado[1],
         "df": datos.get("df_sin_horario", pd.DataFrame()),
         "columnas": ["codigo_materia", "asignatura", "materia_especifica", "nombre_comision", "turno", "sede",
                      "modalidad"],
         "renombres": {"codigo_materia": "Código", "asignatura": "Asignatura",
                       "materia_especifica": "Materia específica", "nombre_comision": "Comisión", "turno": "Turno",
                       "sede": "Sede", "modalidad": "Modalidad"},
         "vacio": "Todas las comisiones activas tienen al menos un horario registrado."},
        {"etiqueta": "Período académico", "icono": ("🟢" if periodo_ok else "🔴"),
         "resultado": ("Correctamente configurado" if periodo_ok else "Revisar fechas/estado del período"),
         "df": datos.get("df_periodo_detalle", pd.DataFrame()),
         "columnas": ["Control", "Valor actual", "Valor esperado", "Resultado"], "renombres": {},
         "vacio": "No hay detalle disponible para el período."},
        {"etiqueta": "Docentes duplicados", "icono": dup_estado[0], "resultado": dup_estado[1],
         "df": datos.get("df_duplicados", pd.DataFrame()),
         "columnas": ["CUIL normalizado", "Docente/s", "Cantidad de registros", "cuil_normalizado", "cantidad"],
         "renombres": {"cuil_normalizado": "CUIL normalizado", "cantidad": "Cantidad de registros"},
         "vacio": "No se detectaron CUIL duplicados en la base docente del departamento."},
    ]
    pct = int(datos.get("salud", 0) or 0)
    return {
        "titulo": "Salud del período",
        "caption": "Abrí cada control para identificar exactamente los casos antes de ir al módulo correspondiente.",
        "controles": [{"titulo": f"{i['icono']} {i['etiqueta']} — {i['resultado']}",
                       "casos": detalle(i["df"], columnas=i.get("columnas"), renombres=i.get("renombres"),
                                        texto_vacio=i.get("vacio", "No se detectaron casos."))} for i in items],
        "estado_general": f"**Estado general del período: {pct} % saludable**",
        "porcentaje": pct,
        "caption_indice": ("Índice operativo orientativo: pondera superposiciones, sobrecarga, asignaciones "
                           "problemáticas, comisiones sin horario, configuración del período y duplicados."),
        "boton": boton("Ver diagnóstico completo", "📊 Análisis"),
    }


# ------------------------------------------------------------------------------------------ 4. Indicadores (l. 59689-59722)
def indicadores(datos: dict) -> dict:
    d = datos
    pct_base = float(d.get("porcentaje_no_lectivas", 0) or 0)
    fila1 = [
        metrica("Horas de designación · total", f"{d.get('horas_contratadas', 0):g} hs",
                caption=f"Docencia {d.get('horas_contratadas_docencia', 0):g} hs · "
                        f"No docentes {d.get('horas_no_docentes', 0):g} hs"),
        metrica("Horas frente a comisión", f"{d.get('horas_comisiones', 0):g} hs"),
        metrica("Horas no lectivas", f"{d.get('horas_no_lectivas', 0):g} hs",
                caption=f"Parámetro base {pct_base:g} % · comisión con 2+ docentes: {pct_base/2:g} % por docente"),
        metrica("Horas investigación + extensión",
                f"{(d.get('horas_investigacion', 0) + d.get('horas_extension', 0)):g} hs"),
        metrica("Horas funciones no docentes", f"{d.get('horas_no_docentes', 0):g} hs"),
        metrica("Cobertura de comisiones", f"{d.get('cobertura', 0):g} %"),
    ]
    if float(d.get("horas_exceso", 0) or 0) > 0:
        i10 = metrica("Exceso global registrado", f"{d.get('horas_exceso', 0):g} hs")
    else:
        i10 = metrica("Horas todavía disponibles", f"{d.get('horas_disponibles', 0):g} hs")
    fila2 = [
        metrica("Comisiones cubiertas", int(d.get("comisiones_cubiertas", 0) or 0)),
        metrica("Docentes por comisión", _dos(d.get("docentes_por_comision", 0))),
        metrica("Productividad promedio", f"{_dos(d.get('productividad_promedio_docentes', 0))} %",
                caption="Promedio simple del % de productividad de las funciones docentes; las funciones no "
                        "docentes no integran este cálculo."),
        i10,
        metrica("Alumnos por docente", _dos(d.get("alumnos_por_docente", 0)),
                caption=f"{int(d.get('alumnos_inscriptos', 0) or 0)} alumnos (sin duplicar por comisión) / "
                        f"{int(d.get('docentes_en_comisiones_calculo', d.get('docentes_activos_calculo', 0)) or 0)} "
                        "docentes únicos en comisiones"),
    ]
    return {"titulo": "Indicadores del departamento", "filas": [fila1, fila2]}


# ------------------------------------------------------------------------------------------ 5. Graficos (l. 59724-59744)
def graficos(datos: dict) -> list[dict]:
    d = datos
    filas = [
        {"Concepto": "Horas contratadas", "Horas": float(d.get("horas_contratadas", 0) or 0)},
        {"Concepto": "Comisiones (lectivas)", "Horas": float(d.get("horas_comisiones", 0) or 0)},
        {"Concepto": "Horas no lectivas", "Horas": float(d.get("horas_no_lectivas", 0) or 0)},
        {"Concepto": "Investigación", "Horas": float(d.get("horas_investigacion", 0) or 0)},
        {"Concepto": "Extensión", "Horas": float(d.get("horas_extension", 0) or 0)},
        {"Concepto": "Funciones no docentes", "Horas": float(d.get("horas_no_docentes", 0) or 0)},
    ]
    if float(d.get("horas_exceso", 0) or 0) > 0:
        filas.append({"Concepto": "Exceso sobre lo contratado", "Horas": float(d.get("horas_exceso", 0) or 0)})
    else:
        filas.append({"Concepto": "Horas disponibles", "Horas": float(d.get("horas_disponibles", 0) or 0)})
    return [
        barra(d.get("df_cargos", pd.DataFrame()), "Cargo", "Docentes", "Distribución del plantel por cargo",
              "Un docente con más de un cargo activo puede contabilizarse en más de una categoría."),
        barra(pd.DataFrame(filas), "Concepto", "Horas", "Uso de las horas disponibles",
              "El consolidado integra docencia frente a cursada, horas no lectivas, investigación, extensión y las "
              "horas contratadas para funciones no docentes. La productividad sigue calculándose solo sobre docencia."),
    ]


# ------------------------------------------------------------------------------------------ 6. Vencimientos (l. 59746-59757)
def vencimientos_visibles(datos: dict) -> Optional[pd.DataFrame]:
    """``df_venc[cols_v].head(8)``: exactamente la tabla que muestra (y exporta, D-AN6) la pagina."""
    df = datos.get("df_vencimientos", pd.DataFrame()).copy()
    if df is None or df.empty:
        return None
    return df[[c for c in COLS_VENCIMIENTOS if c in df.columns]].head(8)


def vencimientos(datos: dict) -> dict:
    vis = vencimientos_visibles(datos)
    if vis is None:
        return {"titulo": "Próximos vencimientos", "tabla": None, "excel": False, "boton": None,
                "vacio": "No hay designaciones activas con vencimiento previsto dentro de los próximos 30 días."}
    return {"titulo": "Próximos vencimientos", "tabla": tabla(vis), "excel": True, "vacio": None,
            "boton": boton("Ver todos los vencimientos", "📑 Designaciones")}


def tablero(ns: dict, datos: dict) -> dict:
    """Secciones 1-7 del tablero (l. 59369-59794) a partir del resultado de ``_inicio_datos_tablero_cache``."""
    return {"situacion": situacion(ns, datos), "acciones": acciones(datos), "salud": salud(datos),
            "indicadores": indicadores(datos), "graficos": graficos(datos), "vencimientos": vencimientos(datos),
            "ayuda": {"titulo": "▶️ Ayuda y flujo correcto de carga", "abierto": False, "texto": AYUDA_TABLERO}}


__all__ = ["titulo", "institucional", "sin_periodo", "encabezado", "tablero", "vencimientos_visibles", "DESTINOS"]
