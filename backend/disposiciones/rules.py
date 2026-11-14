"""Reglas puras de Disposiciones (B13-FIX02).  Sin SQL, sin disco, sin sesion.

Origen certificado (reference_fix02, solo lectura):
- ``extracted_batch01/otros.py``: ``_normalizar_texto_disposicion``, ``_reemplazar_variables_texto_simple``.
- ``extracted_batch01/docentes.py``: ``_reemplazar_variables_manteniendo_docente``, ``_texto_funcion_no_docente_limpio_v164``.
- ``extracted_batch01/designaciones.py``: ``_variables_para_bloque_disposicion``, ``_es_ad_honorem_v162``.
- ``extracted_batch01/periodos.py``: ``_clave_numero_inicial_disposicion_v162``.
- ``extracted_batch02/safe_helpers.py``: ``_normalizar_tipo_designacion_disposicion``,
  ``_nombre_departamento_para_considerando``, ``_clave_unidad_proyecto_notificacion_v215`` (= ``investigacion.rules``).
- ``extracted_batch04/designaciones.py``: ``_es_funcion_no_docente_v162`` (= ``designaciones.rules``).
- ``common/text.py``: ``_unir_lista_natural``, ``_unir_items_administrativos``, ``nombre_archivo_seguro`` (Comisiones).
- ``common/identifiers.py``: ``_clave_departamento_dispo_v159``; ``common/dates.py``: ``formatear_fecha_larga``.
- ``domain/materias.py``: ``formatear_nombre_escuela``; ``domain/proyectos.py``: prefijos de instituto/area.
- ``domain/documentos.py``: ``construir_considerandos_designaciones_docente``, ``_texto_asignaturas_variables_v249``.
- ``domain/designaciones.py``: ``_designacion_es_exclusivamente_docente_v249``.
- ``catalogs/documentos.py``: ``VARIABLES_ASIGNATURAS_DISPOSICION``.
- entry: ``PARAMETROS_DISPOSICION_DEFAULT`` l. 5529, ``cargo_autoridad_departamento`` l. 24072,
  ``mostrar_estado_consulta_designacion`` l. 23877 (equivalencias de estado), pagina l. 67812-68550 (textos).
Las auxiliares ya portadas por bloques cerrados se importan sin modificarlos.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from comisiones.rules import limpiar_texto_tabla, nombre_archivo_seguro  # noqa: F401  (reexportadas)
from designaciones.rules import es_funcion_no_docente
from docentes.rules import clave_cuil, normalizar_clave  # noqa: F401  (reexportadas)
from investigacion.rules import clave_unidad_proyecto_v215
from materias.rules import normalizar_codigo_materia  # noqa: F401  (reexportada)

# --- catalogos / textos certificados ------------------------------------------------------------------------------
PARAMETROS_DISPOSICION_DEFAULT = {  # l. 5529
    "Fecha Asamblea Universitaria": "",
    "N° CUDAP EXP – UNO de la Asamblea Universitaria": "",
    "fecha_acta_rector": "",
    "rector": "",
    "DNI Rector": "",
    "Período mandato": "",
    "Número de Resolución Direector de Departamento": "",
    "genero_director_departamento": "Director",
    "director/a de departamento": "",
    "DNI director/a de departamento": "",
}
# Campos de la pestaña Configuracion (l. 67830-67847): (clave guardada, etiqueta).  El genero es un select.
CAMPOS_CONFIGURACION = [
    ("Fecha Asamblea Universitaria", "Fecha Asamblea Universitaria"),
    ("N° CUDAP EXP – UNO de la Asamblea Universitaria", "N° CUDAP EXP – UNO Asamblea Universitaria"),
    ("fecha_acta_rector", "Fecha del Acta de Asamblea / Rector"),
    ("rector", "Rector/a"),
    ("DNI Rector", "DNI Rector/a"),
    ("Período mandato", "Período mandato Rector/a"),
    ("genero_director_departamento", "Cargo de la autoridad del Departamento"),
    ("Número de Resolución Direector de Departamento", "N° Resolución de la autoridad del Departamento"),
    ("director/a de departamento", "Nombre de la autoridad del Departamento"),
    ("DNI director/a de departamento", "DNI de la autoridad del Departamento"),
]
OPCIONES_GENERO_AUTORIDAD = ["Director", "Directora"]
ESTADOS_DISPOSICION = ["Borrador", "Emitida", "Anulada"]  # l. 67945 / 68141
TIPO_DEFAULT = "Asignación de funciones docentes"  # l. 67939 / 68119
OBS_MASIVA = "Generación masiva desde Nueva disposición"  # l. 68033
TIPO_MOVIMIENTO = "Generación de disposición"  # B12E ``generate``
VARIABLES_ASIGNATURAS_DISPOSICION = [
    "{{asignaturas que dicta con días, horarios, las carreras a las que pertenecen y escuelas}}",
    "{{asignaturas que dicta con las carreras a las que pertenecen y escuelas}}",
]
CLAVE_ASIGNATURAS = "asignaturas que dicta con días, horarios, las carreras a las que pertenecen y escuelas"
CLAVE_ASIGNATURAS_LEGACY = "asignaturas que dicta con las carreras a las que pertenecen y escuelas"
COLUMNAS_PARAMETROS_DOCENTE = [  # l. 5607
    "cuil", "resolucion_cs_concursado", "fecha_desde_concursado", "fecha_hasta_concursado",
    "resolucion_cs_interino", "fecha_desde_interino", "fecha_hasta_interino",
    "codigo_proyecto", "instituto_proyecto", "observaciones",
]
ARTICULO_2_GENERAL_V249 = ("Asígnese asimismo, al docente referido en el artículo anterior, en el caso de ser "
                           "necesario, el resto de las horas de su contratación para la cobertura de horas docentes, "
                           "investigación y/o extensión.")
_EQUIVALENCIAS_ESTADO_CONSULTA = {"Consulta enviada": "Consulta Enviada", "Rever designación": "Rever Designación"}


# --- texto --------------------------------------------------------------------------------------------------------
def normalizar_texto_disposicion(valor: Any) -> str:
    return " ".join(str(valor or "").strip().split())


def normalizar_tipo_designacion_disposicion(valor: Any) -> str:
    txt = normalizar_texto_disposicion(valor).lower()
    if txt == "concursado":
        return "Concursado"
    if txt == "interino":
        return "Interino"
    return normalizar_texto_disposicion(valor)


def texto_funcion_no_docente_limpio_v164(valor: Any) -> str:
    return " ".join(str(valor or "").strip().split())


def es_ad_honorem_v162(valor: Any) -> bool:
    return str(valor or "").strip().casefold() in {"sí", "si", "1", "true", "verdadero", "yes"}


def es_funcion_no_docente_v162(valor: Any) -> bool:
    return es_funcion_no_docente(valor)


def clave_numero_inicial_disposicion_v162(periodo_id: Any) -> str:
    return f"numero_inicial_disposiciones_periodo_{int(periodo_id)}"


def unir_lista_natural(valores) -> str:
    """'A', 'A y B' o 'A, B y C'."""
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


def unir_items_administrativos(items) -> str:
    items = [str(x).strip() for x in items if str(x).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return "; ".join(items[:-1]) + "; y " + items[-1]


def clave_departamento_dispo_v159(valor: Any) -> str:
    txt = normalizar_clave(valor or "")
    txt = re.sub(r"^DEPARTAMENTO\s+DE\s+", "", txt).strip()
    txt = re.sub(r"^DEPARTAMENTO\s+", "", txt).strip()
    return txt


def clave_unidad_proyecto_notificacion_v215(valor: Any) -> str:
    return clave_unidad_proyecto_v215(valor)


_MESES = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
          9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"}


def formatear_fecha_larga(valor: Any) -> str:
    """ISO / dd-mm-aaaa -> "04 de abril de 2029" (ISO explicito para no invertir dia y mes)."""
    if valor is None or pd.isna(valor) or str(valor).strip() == "":
        return ""
    txt = str(valor).strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", txt):
            dt = pd.to_datetime(txt, format="%Y-%m-%d", errors="coerce")
        elif re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", txt):
            dt = pd.to_datetime(txt, dayfirst=True, errors="coerce")
        else:
            dt = pd.to_datetime(txt, dayfirst=True, errors="coerce")
        if pd.isna(dt):
            return txt
        return f"{dt.day:02d} de {_MESES[int(dt.month)]} de {int(dt.year)}"
    except Exception:
        return txt


# 6A-B3: la presentación de unidades académicas tiene UNA fuente común (``materias.rules``), compartida con
# el Resumen docente.
from materias.rules import es_denominacion_institucional, formatear_nombre_escuela  # noqa: F401,E402


def prefijo_instituto_proyecto(valor: Any) -> str:
    if valor is None or pd.isna(valor):
        return ""
    txt = " ".join(str(valor).strip().split())
    if not txt:
        return ""
    if txt.lower().startswith(("del ", "de la ", "de los ", "de las ", "de ")):
        return txt
    return f"del {txt}"


def prefijo_area_extension(valor: Any) -> str:
    if valor is None or pd.isna(valor):
        return ""
    txt = " ".join(str(valor).strip().split())
    if not txt:
        return ""
    bajo = txt.lower()
    if bajo.startswith(("del ", "de la ", "de los ", "de las ", "de ")):
        return txt
    if bajo.startswith(("secretaría", "secretaria", "área", "area", "dirección", "direccion", "coordinación",
                        "coordinacion")):
        return f"de la {txt}"
    return f"del {txt}"


def nombre_departamento_para_considerando(valor: Any) -> str:
    txt = normalizar_texto_disposicion(valor)
    if not txt:
        return "Departamento correspondiente"
    if txt.lower().startswith("departamento"):
        return txt
    return f"Departamento de {txt}"


def texto_departamentos_revistara_desde_lista(departamentos, dep_actual: str = "") -> str:
    """``_texto_departamentos_revistara_desde_lista`` l. 6286; ``dep_actual`` = respaldo de la sesion (ya resuelto)."""
    deps = []
    for dep in departamentos or []:
        txt = " ".join(str(dep or "").strip().split())
        if txt and txt not in deps:
            deps.append(txt)
    if not deps and dep_actual:
        deps = [dep_actual]
    if not deps:
        return "el Departamento correspondiente"
    if len(deps) == 1:
        dep = deps[0]
        if dep.lower().startswith("departamento"):
            return f"el {dep}"
        return f"el Departamento de {dep}"
    return "los siguientes departamentos: " + unir_lista_natural(deps)


def texto_departamento_disposicion(deps) -> str:
    """``texto_departamento_disposicion_docente`` l. 6661 sobre los departamentos de origen ya resueltos."""
    dep = " ".join(str(deps[0] if deps else "").strip().split())
    if not dep:
        return "Departamento correspondiente"
    if dep.lower().startswith("departamento"):
        return dep
    return f"Departamento de {dep}"


def cargo_autoridad_departamento(parametros: dict) -> str:
    """l. 24072 (los parametros siempre llegan resueltos: no hay lectura implicita)."""
    valor = str((parametros or {}).get("genero_director_departamento") or "Director").strip().lower()
    return "Directora" if valor == "directora" else "Director"


def estado_consulta_mostrado(estado: Any) -> dict:
    """Semaforo de ``mostrar_estado_consulta_designacion`` (l. 23877): solo lectura en Disposiciones (D12)."""
    estado = str(estado or "").strip()
    estado = _EQUIVALENCIAS_ESTADO_CONSULTA.get(estado, estado)
    if estado == "Designación confirmada":
        return {"tono": "success", "icono": "🟢", "estado": estado}
    if estado == "Consulta Enviada":
        return {"tono": "warning", "icono": "🟡", "estado": estado}
    if estado == "Rever Designación":
        return {"tono": "error", "icono": "🔴", "estado": estado}
    return {"tono": "info", "icono": "⚪", "estado": ""}


# --- considerandos y variables ------------------------------------------------------------------------------------
def construir_considerandos_designaciones_docente(docente, cuil, registros, incluir_concursado=True,
                                                  incluir_interino=True) -> list[str]:
    """Un considerando por grupo (tipo, resolucion, desde, hasta); dentro, departamento/cargo/dedicacion."""
    seleccionados = []
    for registro in registros or []:
        tipo = normalizar_tipo_designacion_disposicion(registro.get("tipo_designacion"))
        if tipo == "Concursado" and not incluir_concursado:
            continue
        if tipo == "Interino" and not incluir_interino:
            continue
        if tipo not in ["Concursado", "Interino"]:
            continue
        seleccionados.append(dict(registro, tipo_designacion=tipo))

    grupos: dict = {}
    orden = []
    for registro in seleccionados:
        tipo = registro.get("tipo_designacion")
        resolucion = normalizar_texto_disposicion(registro.get("resolucion"))
        desde = normalizar_texto_disposicion(registro.get("fecha_desde"))
        hasta = normalizar_texto_disposicion(registro.get("fecha_hasta"))
        clave = (tipo, resolucion.lower(), desde.lower(), hasta.lower())
        if clave not in grupos:
            grupos[clave] = {"tipo": tipo, "resolucion": resolucion, "fecha_desde": desde, "fecha_hasta": hasta,
                             "registros": []}
            orden.append(clave)
        grupos[clave]["registros"].append(registro)

    considerandos = []
    for clave in orden:
        grupo = grupos[clave]
        descripciones = []
        for registro in grupo["registros"]:
            dep = nombre_departamento_para_considerando(registro.get("departamento"))
            cargo = normalizar_texto_disposicion(registro.get("cargo")) or "cargo no informado"
            dedicacion = normalizar_texto_disposicion(registro.get("dedicacion")) or "dedicación no informada"
            condicion_ad_honorem = " Ad Honorem" if es_ad_honorem_v162(registro.get("ad_honorem")) else ""
            descripcion = f"{dep} como {cargo} con dedicación {dedicacion}{condicion_ad_honorem}"
            if descripcion not in descripciones:
                descripciones.append(descripcion)
        if not descripciones:
            continue
        if len(descripciones) == 1:
            lugar = f"el {descripciones[0]}"
        else:
            lugar = "los siguientes departamentos: " + unir_lista_natural(descripciones)
        acto = "Resolución CS" if grupo["tipo"] == "Concursado" else "Resolución Rectoral"
        if grupo["resolucion"]:
            acto += f" N.º {grupo['resolucion']}"
        periodo = ""
        desde = formatear_fecha_larga(grupo["fecha_desde"])
        hasta = formatear_fecha_larga(grupo["fecha_hasta"])
        if desde and hasta:
            periodo = f" por el período que va del {desde} al {hasta}"
        elif desde:
            periodo = f" a partir del {desde}"
        elif hasta:
            periodo = f" hasta el {hasta}"
        considerandos.append(f"Que, por {acto} se designó al docente {docente} CUIL N° {cuil} "
                             f"que revistará en {lugar}{periodo};")
    return considerandos


def reemplazar_variables_texto_simple(texto, variables: dict) -> str:
    nuevo = texto or ""
    for clave, valor in variables.items():
        if isinstance(valor, (bool, dict, list)):
            continue
        nuevo = nuevo.replace("{{" + str(clave) + "}}", "" if valor is None else str(valor))
    return nuevo


def reemplazar_variables_manteniendo_docente(texto, variables: dict, marcador_docente: str = "§§DOCENTE§§") -> str:
    nuevo = texto or ""
    nuevo = nuevo.replace("{{docente}}", marcador_docente)
    for clave, valor in variables.items():
        if isinstance(valor, (bool, dict, list)) or str(clave) == "docente":
            continue
        nuevo = nuevo.replace("{{" + str(clave) + "}}", "" if valor is None else str(valor))
    return nuevo


def variables_para_bloque_disposicion(variables: dict, bloque_nombre=None) -> dict:
    """Dentro de un bloque condicional, ``cargo``/``dedicación``/``horas`` toman el valor de ese tipo."""
    vars_bloque = dict(variables)
    if bloque_nombre == "SI_TIENE_CONCURSADO":
        vars_bloque["cargo"] = variables.get("cargo_concursado", variables.get("cargo", ""))
        vars_bloque["dedicación"] = variables.get("dedicación_concursado", variables.get("dedicación", ""))
        vars_bloque["horas"] = variables.get("horas_concursado", variables.get("horas", ""))
    if bloque_nombre == "SI_TIENE_INTERINO":
        vars_bloque["cargo"] = variables.get("cargo_interino", variables.get("cargo", ""))
        vars_bloque["dedicación"] = variables.get("dedicación_interino", variables.get("dedicación", ""))
        vars_bloque["horas"] = variables.get("horas_interino", variables.get("horas", ""))
        vars_bloque["resolucion_rectoral_interino"] = variables.get("resolucion_rectoral_interino",
                                                                    variables.get("resolucion_cs_interino", ""))
        vars_bloque["resolucion_cs_interino"] = variables.get("resolucion_rectoral_interino",
                                                              variables.get("resolucion_cs_interino", ""))
    return vars_bloque


def designacion_es_exclusivamente_docente_v249(variables: dict) -> bool:
    variables = dict(variables or {})
    if bool(variables.get("ES_FUNCION_NO_DOCENTE")) or bool(variables.get("ES_FUNCION_MIXTA")):
        return False
    datos = variables.get("designaciones_disposicion") or []
    if not isinstance(datos, (list, tuple)) or not datos:
        return False
    tiene_docente = tiene_no_docente = False
    for item in datos:
        if not isinstance(item, dict):
            continue
        if es_funcion_no_docente_v162(item.get("funcion_no_docente")):
            tiene_no_docente = True
        else:
            tiene_docente = True
    return bool(tiene_docente and not tiene_no_docente)


def texto_asignaturas_variables_v249(variables: dict) -> str:
    variables = dict(variables or {})
    for clave in [CLAVE_ASIGNATURAS, CLAVE_ASIGNATURAS_LEGACY]:
        txt = str(variables.get(clave, "") or "").strip()
        if txt:
            return txt
    return ""


def cuerpo_actividades_especiales(texto: str) -> str:
    """El cuerpo del Art. 3 sin su rotulo (v95 l. 32395 / 32433)."""
    return re.sub(r"^\s*ART[ÍI]CULO\s+3\s*[º°]?\s*[.\-–—]*\s*", "", texto, count=1, flags=re.I).strip() if texto else ""


__all__ = [n for n in dir() if not n.startswith("_")]
