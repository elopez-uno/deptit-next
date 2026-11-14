"""Reglas puras de Designaciones (sin base de datos), copiadas de la fuente certificada B13-FIX02.

Origen (reference_fix02):
- ``deptit_refactor/catalogs/designaciones.py`` y ``catalogs/movimientos.py`` (catalogos), entry l. 511-515
  (``ESTADOS_DESIGNACION``, ``HORAS_OPCIONES``).
- ``domain/catalog_unlocked/designaciones.py`` (``horas_segun_dedicacion``), ``extracted_batch01/designaciones.py``
  (estado visible, ``detalle_designacion``), ``extracted_batch04/designaciones.py`` (flags v162),
  ``extracted_batch01/docentes.py`` (texto no docente v164), ``extracted_batch01/movimientos.py`` (categoria v263),
  ``extracted_batch01/documentos.py`` (etiqueta de acto v263), ``extracted_batch04/numeros.py``,
  ``extracted_batch04/fechas.py``, ``common/dates.py``.
- ``domain/designaciones.py`` (claves y firmas, cargo canonico, departamento de origen, v169/v269),
  ``domain/movimientos.py`` (variacion de horas, clasificacion, claves de movimiento),
  ``domain/catalog_unlocked/movimientos.py`` (v269), ``extracted_batch04/movimientos.py``.
- ``extracted_batch01/periodos.py`` (periodo equivalente), ``domain/periodos.py`` (formula Excel v230).
- entry l. 16675 / 16717 (pegado), 17305 / 17394 / 49681 (periodo y estado automaticos v230), 49656 (v237),
  39224 (v182), 39792 (foto v183).
Se trabaja con pandas (mismas versiones que el runtime certificado) para conservar la semantica exacta.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from io import StringIO
from typing import Any, Optional

import pandas as pd

from docentes.carga import leer_tabla_pegada, normalizar_columna_generica
from docentes.rules import _is_na, clave_cuil, limpiar_cuil, limpiar_texto_tabla, normalizar_clave, safe_date

# --- catalogos ---------------------------------------------------------------------------------------------
CARGOS = ["Titular", "Asociado", "Adjunto", "JTP", "Ayudante 1ra", "Ayudante 2da"]
DEDICACIONES = ["Simple", "Parcial", "Parcial + Simple", "Exclusiva", "Exclusiva + Simple"]
TIPOS_DESIGNACION = ["Concursado", "Interino", "Loc. Serv."]
HORAS_POR_DEDICACION = {"Simple": 10, "Parcial": 20, "Parcial + Simple": 30, "Exclusiva": 40, "Exclusiva + Simple": 50}
HORAS_OPCIONES = [10, 20, 30, 40, 50]
ESTADOS_DESIGNACION = ["Activa", "Finalizada", "Suspendida"]
# Estado de la consulta al docente (entry l. 22230; writer ``guardar_estado_consulta_designacion`` l. 23858).
ESTADOS_CONSULTA_DESIGNACION = ["Designación confirmada", "Consulta Enviada", "Rever Designación"]
AD_HONOREM = ["No", "Sí"]
ORDEN_JERARQUICO_CARGOS_COMISION = ["Titular", "Asociado", "Adjunto", "JTP", "Ayudante 1ra", "Ayudante 2da"]

# Pestaña "Modificar / finalizar designación" (entry l. 63895-63908), en el orden certificado.
TIPO_BAJA = "Finalizar / baja de designación"
TIPO_GENERAL = "Modificación general"
TIPOS_CAMBIO = ["Cambio de cargo", "Aumento de dedicación", "Disminución de dedicación", "Cambio de tipo de designación",
                "Cambio de condición Ad Honorem", "Cambio de función docente / no docente", TIPO_BAJA, TIPO_GENERAL]

TIPOS_MOVIMIENTO_VINCULADOS_DESIGNACION = {
    "alta de designación", "alta de designacion", "renovación automática de designación",
    "renovacion automatica de designacion", "aumento de dedicación", "aumento de dedicacion",
    "disminución de dedicación", "disminucion de dedicacion", "cambio de cargo", "cambio de condición ad honorem",
    "pase a ad honorem", "pase a rentado", "modificación general", "modificacion general", "baja de designación",
    "baja de designacion", "eliminación de designación", "eliminacion de designacion", "finalización de designación",
    "finalizacion de designacion", "finalización automática por cierre de período",
    "finalizacion automatica por cierre de periodo", "finalización automática por vencimiento de designación",
    "finalizacion automatica por vencimiento de designacion",
}
TIPOS_INICIO_DESIGNACION_V269 = {"Alta de designación", "Renovación automática de designación",
                                 "Continuidad automática de designación concursada"}
TIPOS_BAJA_REAL_DESIGNACION_V269 = {"Baja de designación", "Finalización de designación", "Finalizacion de designacion",
                                    "Finalizar / baja de designación",
                                    "Finalización automática por vencimiento de designación"}
MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266 = {
    "Alta de designación", "Renovación automática de designación", "Cambio de cargo", "Aumento de dedicación",
    "Disminución de dedicación", "Cambio de tipo de designación", "Cambio de condición Ad Honorem",
    "Pase a Ad Honorem", "Pase a Rentado", "Finalizar / baja de designación", "Baja de designación",
    "Finalización de designación", "Modificación general",
}
TIPOS_MOVIMIENTO_DOCENTE_POR_ERROR = {"alta de docente", "edición de docente", "edicion de docente", "baja de docente",
                                      "eliminación de docente", "eliminacion de docente"}
# get_movimientos_designaciones_periodo_v266 (entry l. 55392-55401).
TIPOS_HISTORIAL_V266 = {
    "Alta de designación", "Renovación automática de designación", "Cambio de cargo", "Aumento de dedicación",
    "Disminución de dedicación", "Cambio de tipo de designación", "Cambio de número de resolución",
    "Cambio de condición Ad Honorem", "Pase a Ad Honorem", "Pase a Rentado",
    "Cambio de función docente / no docente", "Cambio de funciones no docentes",
    "Finalizar / baja de designación", "Baja de designación", "Finalización de designación",
    "Finalización automática por vencimiento de designación",
    "Continuidad automática de designación concursada", "Modificación general",
}
# _canonizar_movimientos_designaciones_v269 (entry l. 9832-9839).
TIPOS_DESIGNACION_V269 = set(TIPOS_INICIO_DESIGNACION_V269) | set(TIPOS_BAJA_REAL_DESIGNACION_V269) | {
    "Eliminación de designación", "Eliminacion de designacion", "Aumento de dedicación", "Disminución de dedicación",
    "Cambio de cargo", "Cambio de tipo de designación", "Cambio de número de resolución",
    "Cambio de condición Ad Honorem", "Pase a Ad Honorem", "Pase a Rentado", "Cambio de función docente / no docente",
    "Cambio de funciones no docentes", "Modificación general", "Finalización automática por cierre de período",
}
# _render_historial_designaciones_analisis_v267 (entry l. 54998-55022).
ROTULOS_HISTORIAL_V267 = {
    "Altas de designaciones": "Altas designaciones", "Bajas de designaciones": "Bajas designaciones",
    "Aumentos de dedicación": "Aumentos", "Disminuciones de dedicación": "Disminuciones",
    "Cambios de cargo": "Cambios de cargo", "Pase a Ad Honorem": "Pase a Ad Honorem",
    "Pase a Rentado": "Pase a Rentado", "Renovaciones automáticas": "Renovaciones",
    "Continuidades concursadas": "Continuidades concursadas", "Cambio de tipo de designación": "Cambio de tipo",
    "Cambio de función docente / no docente": "Cambio de función",
    "Cambio de funciones no docentes": "Cambio de funciones", "Modificación general": "Modificación general",
    "Cambio de condición Ad Honorem": "Cambio Ad Honorem/Rentado",
}
ORDEN_HISTORIAL_V267 = [
    "Altas de designaciones", "Bajas de designaciones", "Aumentos de dedicación", "Disminuciones de dedicación",
    "Cambios de cargo", "Pase a Ad Honorem", "Pase a Rentado", "Renovaciones automáticas",
    "Continuidades concursadas", "Cambio de tipo de designación", "Cambio de función docente / no docente",
    "Cambio de funciones no docentes", "Modificación general",
]


# --- valores simples ----------------------------------------------------------------------------------------
def horas_segun_dedicacion(dedicacion: Any, fallback: Any = 0) -> int:
    """Fuente única de horas contractuales según la dedicación docente."""
    txt = " ".join(str(dedicacion or "").strip().split())
    for nombre, horas in HORAS_POR_DEDICACION.items():
        if txt.casefold() == nombre.casefold():
            return int(horas)
    try:
        return int(float(fallback or 0))
    except Exception:
        return 0


def flag_si_v162(valor: Any) -> bool:
    if isinstance(valor, bool):
        return valor
    try:
        if valor is not None and not pd.isna(valor) and float(valor) == 1:
            return True
    except Exception:
        pass
    return str(valor or "").strip().casefold() in {"1", "sí", "si", "true", "verdadero", "yes"}


def es_funcion_no_docente(valor: Any) -> bool:
    return flag_si_v162(valor)


def texto_funcion_limpio(valor: Any) -> str:
    return " ".join(str(valor or "").strip().split())


def estado_visible(valor: Any) -> str:
    txt = str(valor or "").strip()
    return "Suspendida (licenciada)" if txt.casefold() == "suspendida" else txt


def detalle_designacion(row: dict) -> str:
    return f"{row['cargo']} - {row['dedicacion']} - {row['horas']} hs - {row['tipo_designacion']} - Estado {row['estado']}"


def categoria_respaldo_movimiento(tipo_movimiento: Any) -> str:
    t = str(tipo_movimiento or "").strip()
    if t == "Cambio de cargo":
        return "Cambio de cargo"
    if t in {"Aumento de dedicación", "Disminución de dedicación"}:
        return "Cambio de dedicación"
    if t in {"Pase a Ad Honorem", "Pase a Rentado", "Cambio de condición Ad Honorem"}:
        return "Cambio de condición Ad Honorem / Rentada"
    return "Designación docente"


def etiqueta_acto(tipo_documento: Any, numero: Any, dependencia: Any = "") -> str:
    tipo = str(tipo_documento or "Documento").strip() or "Documento"
    nro = str(numero or "").strip()
    dep = str(dependencia or "").strip()
    base = f"{tipo} {nro}".strip() if nro else f"{tipo} s/n"
    return base + (f" · {dep}" if dep else "")


def id_documento_valido(valor: Any) -> bool:
    try:
        if pd.isna(valor):
            return False
    except Exception:
        pass
    return str(valor or "").strip() != ""


def hora_numero(valor: Any) -> float:
    try:
        if valor is None or pd.isna(valor):
            return 0.0
        if isinstance(valor, str):
            valor = valor.replace("hs", "").replace(",", ".").strip()
        return float(valor or 0)
    except Exception:
        return 0.0


def fecha_a_timestamp_seguro(valor: Any):
    try:
        if valor is None or pd.isna(valor):
            return pd.NaT
        txt = str(valor).strip()
        if not txt:
            return pd.NaT
        return pd.to_datetime(txt, errors="coerce", dayfirst=False)
    except Exception:
        return pd.NaT


def fecha_iso_correccion_directa_v171(valor: Any) -> str:
    """Normaliza una fecha editada en la grilla a YYYY-MM-DD."""
    try:
        if valor is None or pd.isna(valor):
            return ""
    except Exception:
        if valor is None:
            return ""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    fecha = safe_date(valor, None)
    return fecha.isoformat() if fecha is not None else ""


_FECHA_ANIO_PRIMERO = re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T].*)?")


def normalizar_fecha_texto(valor: Any, fallback: str = "") -> str:
    """DESVIACION DELIBERADA del baseline certificado (docs/ETAPA5_FINAL_REMEDIATION.md): el certificado aplica
    ``pd.to_datetime(txt, dayfirst=True)`` tambien a las fechas año-primero e invierte dia y mes cuando el dia es
    <= 12 (2026-03-01 -> 2026-01-03).  Año-primero se interpreta estricto como año/mes/dia; el resto, igual."""
    txt = limpiar_texto_tabla(valor)
    if not txt:
        return fallback
    m = _FECHA_ANIO_PRIMERO.fullmatch(txt)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return txt
    try:
        return str(pd.to_datetime(txt, dayfirst=True).date())
    except Exception:
        return txt


def condicion_periodo_equivalente_sql(alias_periodo: str = "p", alias_ref: str = "pr") -> str:
    """Condición SQL para comparar períodos equivalentes entre departamentos."""
    return f"""
        {alias_periodo}.institucion_id = {alias_ref}.institucion_id
        AND (
            (COALESCE({alias_periodo}.anio, -1) = COALESCE({alias_ref}.anio, -1)
             AND COALESCE({alias_periodo}.semestre, -1) = COALESCE({alias_ref}.semestre, -1))
            OR COALESCE({alias_periodo}.nombre, '') = COALESCE({alias_ref}.nombre, '')
        )
    """


def formula_periodo_excel_v230(fila: int, col_desde: str, col_hasta: str, ultima_fila_periodos: int) -> str:
    if ultima_fila_periodos < 2:
        return '=""'
    return (
        f'=IF(OR({col_desde}{fila}="",{col_hasta}{fila}=""),"",'
        f'IFERROR(LOOKUP(2,1/(({col_desde}{fila}<=\'Períodos\'!$C$2:$C${ultima_fila_periodos})*'
        f'({col_hasta}{fila}>=\'Períodos\'!$B$2:$B${ultima_fila_periodos})),\'Períodos\'!$A$2:$A${ultima_fila_periodos}),""))'
    )


# --- texto de movimientos de designaciones --------------------------------------------------------------------
def extraer_horas_desde_texto(texto: Any) -> float:
    if texto is None or pd.isna(texto):
        return 0.0
    patron = re.search(r"(-?\d+(?:[\.,]\d+)?)\s*hs", str(texto), flags=re.IGNORECASE)
    if not patron:
        return 0.0
    try:
        return float(patron.group(1).replace(",", "."))
    except Exception:
        return 0.0


def extraer_antes_ahora(detalle: Any) -> tuple[str, str]:
    detalle_txt = str(detalle or "")
    if "Antes:" not in detalle_txt or "Ahora:" not in detalle_txt:
        return "", ""
    try:
        antes_txt = detalle_txt.split("Antes:", 1)[1].split("/ Ahora:", 1)[0].strip()
        ahora_txt = detalle_txt.split("/ Ahora:", 1)[1].strip()
        return antes_txt, ahora_txt
    except Exception:
        return "", ""


def horas_antes_ahora(detalle: Any) -> tuple[float, float]:
    antes_txt, ahora_txt = extraer_antes_ahora(detalle)
    return extraer_horas_desde_texto(antes_txt), extraer_horas_desde_texto(ahora_txt)


def normalizar_tipo_movimiento_dedicacion(tipo_movimiento: Any, variacion_horas: Any = 0) -> str:
    tipo = str(tipo_movimiento or "").strip()
    if tipo not in ["Aumento de dedicación", "Disminución de dedicación"]:
        return tipo
    try:
        variacion = float(variacion_horas or 0)
    except Exception:
        variacion = 0.0
    if variacion > 0:
        return "Aumento de dedicación"
    if variacion < 0:
        return "Disminución de dedicación"
    return tipo


def tipo_movimiento_designacion_normalizado(valor: Any) -> str:
    txt = limpiar_texto_tabla(valor).lower()
    txt = txt.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    return re.sub(r"\s+", " ", txt).strip()


_TIPOS_VINCULADOS_NORM = {tipo_movimiento_designacion_normalizado(x) for x in TIPOS_MOVIMIENTO_VINCULADOS_DESIGNACION}
_TIPOS_DOCENTE_ERROR_NORM = {tipo_movimiento_designacion_normalizado(x) for x in TIPOS_MOVIMIENTO_DOCENTE_POR_ERROR}


def es_movimiento_vinculado_designacion(valor: Any) -> bool:
    return tipo_movimiento_designacion_normalizado(valor) in _TIPOS_VINCULADOS_NORM


def es_movimiento_docente_por_error(valor: Any) -> bool:
    return tipo_movimiento_designacion_normalizado(valor) in _TIPOS_DOCENTE_ERROR_NORM


def extraer_partes_designacion(designacion_txt: Any) -> dict:
    if designacion_txt is None or pd.isna(designacion_txt):
        return {}
    texto = str(designacion_txt).strip()
    partes = [p.strip() for p in texto.split(" - ")]
    cargo = partes[0] if len(partes) > 0 else ""
    dedicacion = partes[1] if len(partes) > 1 else ""
    horas = partes[2] if len(partes) > 2 else ""
    tipo_designacion = ""
    for parte in partes[3:]:
        parte_l = str(parte).strip().lower()
        if parte_l in ["interino", "concursado", "loc. serv.", "loc serv", "loc. servicios", "locacion de servicios",
                       "locación de servicios"]:
            tipo_designacion = parte.strip()
            break
    if not tipo_designacion:
        for tipo_posible in ["Interino", "Concursado", "Loc. Serv."]:
            if tipo_posible.lower() in texto.lower():
                tipo_designacion = tipo_posible
                break
    return {"cargo": cargo, "dedicacion": dedicacion, "horas": horas, "tipo_designacion": tipo_designacion}


def _normalizar_designacion_txt_para_partes(texto: Any) -> str:
    txt = limpiar_texto_tabla(texto)
    txt = re.sub(r"^\s*\d{4}\s*[-/]\s*\d+\s*-\s*", "", txt)
    txt = re.sub(r"\s*-\s*Mov\.\s*horas\s*:\s*-?\d+(?:[\.,]\d+)?\s*$", "", txt, flags=re.I)
    return txt.strip()


def _clave_designacion_desde_partes(partes: Any):
    if not isinstance(partes, dict):
        return None
    cargo = limpiar_texto_tabla(partes.get("cargo", "")).lower()
    dedic = limpiar_texto_tabla(partes.get("dedicacion", "")).lower()
    tipo = limpiar_texto_tabla(partes.get("tipo_designacion", "")).lower()
    hs = extraer_horas_desde_texto(partes.get("horas", ""))
    if not cargo and not dedic and not tipo and not hs:
        return None
    return (cargo, dedic, tipo, round(float(hs or 0), 3))


def clave_designacion_desde_texto(texto: Any):
    return _clave_designacion_desde_partes(extraer_partes_designacion(_normalizar_designacion_txt_para_partes(texto)))


def clave_designacion_desde_row(row: dict) -> tuple:
    cargo = limpiar_texto_tabla(row.get("cargo", ""))
    dedic = limpiar_texto_tabla(row.get("dedicacion", ""))
    tipo = limpiar_texto_tabla(row.get("tipo_designacion", ""))
    hs = hora_numero(row.get("horas", 0))
    return (cargo.lower(), dedic.lower(), tipo.lower(), round(float(hs or 0), 3))


def claves_designacion_movimiento(row: dict) -> set:
    """Posibles fotos de designación mencionadas por un movimiento (``_claves_designacion_movimiento``)."""
    claves = set()
    detalle = str(row.get("detalle", "") or "")
    observaciones = str(row.get("observaciones", "") or "")
    texto = " | ".join([x for x in [detalle, observaciones] if x])
    candidatos = [detalle, observaciones, texto]
    try:
        antes, ahora = extraer_antes_ahora(texto)
        candidatos.extend([antes, ahora])
    except Exception:
        pass
    for candidato in candidatos:
        if not str(candidato or "").strip():
            continue
        try:
            clave = clave_designacion_desde_texto(candidato)
        except Exception:
            clave = None
        if clave:
            claves.add(clave)
    return claves


def normalizar_cargo_para_jerarquia(valor: Any) -> str:
    txt = limpiar_texto_tabla(valor)
    if not txt:
        return ""
    n = unicodedata.normalize("NFKD", txt)
    n = "".join(ch for ch in n if not unicodedata.combining(ch)).upper()
    n = re.sub(r"[^A-Z0-9]+", " ", n)
    n = " ".join(n.split())
    if "TITULAR" in n:
        return "Titular"
    if "ASOCIADO" in n:
        return "Asociado"
    if "ADJUNTO" in n:
        return "Adjunto"
    if n == "JTP" or "JEFE DE TRABAJOS PRACTICOS" in n or "JEFE TRABAJOS PRACTICOS" in n:
        return "JTP"
    if "AYUDANTE" in n:
        if re.search(r"(^| )1($| )", n) or "PRIMER" in n or "1RA" in n or "1RO" in n:
            return "Ayudante 1ra"
        if re.search(r"(^| )2($| )", n) or "SEGUND" in n or "2DA" in n or "2DO" in n:
            return "Ayudante 2da"
    return txt


def extraer_departamento_origen_prestado(observaciones: Any) -> str:
    obs = limpiar_texto_tabla(observaciones)
    if not obs:
        return ""
    m = re.search(r"Docente\s+prestado\s+desde\s+(.+?)(?:\.\s*No\s+posee\s+designaci[oó]n\s+local|\.|$)", obs,
                  flags=re.I)
    return limpiar_texto_tabla(m.group(1)) if m else ""


# --- variacion y clasificacion de movimientos (Analisis, reutilizado por el historial v267) -------------------
def calcular_variacion_horas_movimiento(tipo_movimiento: Any, detalle: Any, horas_variacion_guardada: Any = 0) -> float:
    try:
        guardada = float(horas_variacion_guardada or 0)
    except Exception:
        guardada = 0.0
    if guardada != 0:
        return guardada
    tipo = str(tipo_movimiento or "").strip()
    detalle_txt = str(detalle or "")
    horas_antes, horas_ahora = horas_antes_ahora(detalle_txt)
    if tipo == "Alta de designación":
        return abs(extraer_horas_desde_texto(detalle_txt))
    if tipo in ["Baja de designación", "Eliminación de designación", "Finalización de designación",
                "Finalizacion de designacion", "Finalización automática por vencimiento de designación"]:
        horas = horas_antes if horas_antes else extraer_horas_desde_texto(detalle_txt)
        return -abs(horas)
    if tipo in ["Aumento de dedicación", "Disminución de dedicación", "Cambio de cargo", "Modificación general"]:
        if horas_antes or horas_ahora:
            return horas_ahora - horas_antes
        return 0.0
    return 0.0


def clasificar_movimiento_docente(tipo_movimiento: Any, variacion_horas: Any = None) -> str:
    tipo = str(tipo_movimiento or "").strip()
    if variacion_horas is not None:
        tipo = normalizar_tipo_movimiento_dedicacion(tipo, variacion_horas)
    mapa = {
        "Alta de docente": "Altas de docentes", "Baja de docente": "Bajas de docentes",
        "Baja docente inferida": "Bajas de docentes", "Eliminación de docente": "Bajas de docentes",
        "Alta de designación": "Altas de designaciones", "Baja de designación": "Bajas de designaciones",
        "Eliminación de designación": "Bajas de designaciones", "Finalización de designación": "Bajas de designaciones",
        "Finalizacion de designacion": "Bajas de designaciones",
        "Finalización automática por vencimiento de designación": "Bajas de designaciones",
        "Aumento de dedicación": "Aumentos de dedicación", "Disminución de dedicación": "Disminuciones de dedicación",
        "Cambio de cargo": "Cambios de cargo", "Renovación automática de designación": "Renovaciones automáticas",
        "Continuidad automática de designación concursada": "Continuidades concursadas",
        "Finalización automática por cierre de período": "Cierres automáticos",
    }
    return mapa.get(tipo, tipo or "Sin tipo")


# --- fotos y vigencias (v169/v183/v269) ------------------------------------------------------------------------
def fecha_fin_designacion_analisis_v169(row: dict):
    for campo in ("fecha_finalizacion_efectiva", "fecha_hasta_prevista", "fecha_hasta"):
        try:
            valor = row.get(campo, "")
        except Exception:
            valor = ""
        if valor is not None and not pd.isna(valor) and str(valor).strip():
            return fecha_a_timestamp_seguro(valor)
    return pd.NaT


def fecha_fin_real_designacion_v269(row: dict):
    for campo in ["fecha_finalizacion_efectiva", "fecha_hasta_prevista", "fecha_hasta"]:
        try:
            f = safe_date(row.get(campo), None)
        except Exception:
            f = None
        if f is not None:
            return f
    return None


def vigente_al_cierre_v269(row: dict, fecha_cierre) -> bool:
    if fecha_cierre is None:
        return True
    if normalizar_clave(row.get("estado", "")) == "SUSPENDIDA":
        return False
    desde = safe_date(row.get("fecha_desde"), None)
    hasta = fecha_fin_real_designacion_v269(row)
    if desde is not None and desde > fecha_cierre:
        return False
    if hasta is not None and hasta < fecha_cierre:
        return False
    return True


def detalle_coincide_designacion_v269(detalle: Any, row: dict) -> bool:
    txt = normalizar_clave(str(detalle or ""))
    if not txt:
        return False
    cargo = normalizar_clave(row.get("cargo", ""))
    dedic = normalizar_clave(row.get("dedicacion", ""))
    tipo = normalizar_clave(row.get("tipo_designacion", ""))
    try:
        hs = int(float(pd.to_numeric(row.get("horas"), errors="coerce") or 0))
    except Exception:
        hs = 0
    contrato = normalizar_clave(f"{row.get('cargo','')} {row.get('dedicacion','')} {hs} hs {row.get('tipo_designacion','')}")
    if contrato and contrato in txt:
        return True
    requisitos = [x for x in [cargo, dedic, tipo] if x]
    if not requisitos or not all(x in txt for x in requisitos):
        return False
    return bool(re.search(rf"(?<!\d){re.escape(str(hs))}\s*HS\b", txt, flags=re.I)) if hs else True


def firma_baja_movimiento_v269(row: dict) -> tuple:
    texto = " | ".join([str(row.get("detalle") or ""), str(row.get("observaciones") or "")])
    cuil = clave_cuil(row.get("cuil")) or str(row.get("cuil") or "").strip()
    fecha = safe_date(row.get("fecha"), None)
    fecha_key = fecha.isoformat() if fecha is not None else str(row.get("fecha") or "")[:10]
    for patron in (r"\[designacion_id=(\d+)\]", r"ID\s+designaci[oó]n\s+original\s*[:#=-]?\s*(\d+)",
                   r"\[(?:AUTO_)?V(?:207|208|209|210|211)_DESIGNACION_ID=(\d+)\]"):
        m = re.search(patron, texto, flags=re.I)
        if m:
            return ("id", cuil, m.group(1))
    norm = normalizar_clave(texto)
    cargos = sorted([str(x) for x in CARGOS], key=len, reverse=True)
    dedics = sorted([str(x) for x in DEDICACIONES], key=len, reverse=True)
    tipos = sorted([str(x) for x in TIPOS_DESIGNACION], key=len, reverse=True)
    cargo = next((normalizar_clave(x) for x in cargos if normalizar_clave(x) in norm), "")
    dedic = next((normalizar_clave(x) for x in dedics if normalizar_clave(x) in norm), "")
    tipo = next((normalizar_clave(x) for x in tipos if normalizar_clave(x) in norm), "")
    mh = re.search(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*HS\b", norm, flags=re.I)
    horas = mh.group(1).replace(",", ".") if mh else ""
    if cargo or dedic or horas or tipo:
        return ("firma", cuil, fecha_key, cargo, dedic, horas, tipo)
    reducido = re.sub(r"ESTADO\s+(ACTIVA|FINALIZADA|SUSPENDIDA)", "", norm, flags=re.I)
    reducido = re.sub(r"\s+", " ", reducido).strip()
    return ("texto", cuil, fecha_key, reducido)


def baja_sin_cambio_real_v269(row: dict) -> bool:
    tipo = str(row.get("tipo_movimiento") or "").strip()
    if tipo not in TIPOS_BAJA_REAL_DESIGNACION_V269:
        return False
    detalle = str(row.get("detalle") or "")
    if "Antes:" not in detalle or "Ahora:" not in detalle:
        return False
    antes, ahora = extraer_antes_ahora(detalle)
    if not antes and not ahora:
        return False
    est_antes = re.findall(r"Estado\s+(Activa|Finalizada|Suspendida)", antes, flags=re.I)
    est_ahora = re.findall(r"Estado\s+(Activa|Finalizada|Suspendida)", ahora, flags=re.I)
    if not est_antes or not est_ahora:
        return False
    return normalizar_clave(est_antes[-1]) == "FINALIZADA" and normalizar_clave(est_ahora[-1]) == "FINALIZADA"


def depurar_bajas_movimientos_v269(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "tipo_movimiento" not in df.columns:
        return df
    out = df.copy()
    tipo = out["tipo_movimiento"].fillna("").astype(str).str.strip()
    out = out[~tipo.isin(["Eliminación de designación", "Eliminacion de designacion"])].copy()
    if out.empty:
        return out
    out = out[~out.apply(baja_sin_cambio_real_v269, axis=1)].copy()
    if out.empty:
        return out
    bajas = out["tipo_movimiento"].fillna("").astype(str).isin(TIPOS_BAJA_REAL_DESIGNACION_V269)
    if not bajas.any():
        return out
    prioridad = {"Finalización automática por vencimiento de designación": 0, "Baja de designación": 1,
                 "Finalizar / baja de designación": 1, "Finalización de designación": 2,
                 "Finalizacion de designacion": 2}
    elegidos = {}
    for idx, row in out[bajas].iterrows():
        clave = firma_baja_movimiento_v269(row)
        pr = prioridad.get(str(row.get("tipo_movimiento") or "").strip(), 9)
        if clave not in elegidos or pr < elegidos[clave][0]:
            elegidos[clave] = (pr, idx)
    conservar_bajas = {idx for _, idx in elegidos.values()}
    conservar = [idx for idx in out.index if (not bool(bajas.loc[idx])) or idx in conservar_bajas]
    return out.loc[conservar].copy()


def es_periodo_historico(info: Optional[dict], ultimo: Optional[dict], abierto: Optional[dict]) -> bool:
    """``es_periodo_historico_contexto_v182`` con las tres lecturas ya hechas (info = período por id)."""
    try:
        if not info:
            return False
        if not ultimo:
            return str(info.get("estado") or "").strip().casefold() == "cerrado"
        pid, uid = int(info.get("id")), int(ultimo.get("id"))
        if pid != uid:
            return True
        if abierto and int(abierto.get("id")) != uid:
            return False
        return str(info.get("estado") or "").strip().casefold() == "cerrado"
    except Exception:
        return False


def filtrar_foto_v183(df: pd.DataFrame, historico: bool, info: Optional[dict]) -> pd.DataFrame:
    """``_filtrar_foto_designaciones_v169`` efectiva (v183): vigentes en el último día del período."""
    base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if base.empty:
        return base
    if not historico:
        estado = base.get("estado", pd.Series(index=base.index, dtype=str)).fillna("").astype(str).str.strip().str.casefold()
        return base[estado.eq("activa")].copy().reset_index(drop=True)
    ref = fecha_a_timestamp_seguro((info or {}).get("fecha_fin", ""))
    if "horas" in base.columns:
        base["_hs_v183"] = pd.to_numeric(base["horas"], errors="coerce").fillna(0)
        base = base[base["_hs_v183"] > 0].copy()
    if base.empty:
        return base.drop(columns=["_hs_v183"], errors="ignore")
    if "estado" in base.columns:
        estado = base["estado"].fillna("").astype(str).str.strip().str.casefold()
        base = base[~estado.eq("suspendida")].copy()
    if base.empty:
        return base.drop(columns=["_hs_v183"], errors="ignore")
    base["_desde_v183"] = base["fecha_desde"].apply(fecha_a_timestamp_seguro) if "fecha_desde" in base.columns else pd.NaT
    base["_hasta_v183"] = base.apply(fecha_fin_designacion_analisis_v169, axis=1)
    vigente = pd.Series(True, index=base.index)
    if not pd.isna(ref):
        vigente &= base["_desde_v183"].isna() | (base["_desde_v183"] <= ref)
        vigente &= base["_hasta_v183"].isna() | (base["_hasta_v183"] >= ref)
    out = base[vigente].copy()
    out["estado_analisis"] = "Vigente al cierre del período"
    return out.drop(columns=["_hs_v183", "_desde_v183", "_hasta_v183"], errors="ignore").reset_index(drop=True)


def estado_segun_vigencia_v237(estado_solicitado: Any, fecha_hasta: Any, periodo: Optional[dict], hoy: date):
    """``_estado_designacion_segun_vigencia_v237`` efectiva (entry l. 49656); ``periodo`` = fila por id o None."""
    estado_txt = str(estado_solicitado or "").strip()
    if normalizar_clave(estado_txt) != "ACTIVA":
        return estado_solicitado
    fin_designacion = safe_date(fecha_hasta, None)
    if fin_designacion is not None and fin_designacion < hoy:
        return "Finalizada"
    if periodo is None:
        return estado_solicitado
    fin_periodo = safe_date(periodo.get("fecha_fin"), None)
    if fin_periodo is not None and fin_periodo < hoy:
        return "Finalizada"
    return "Activa"


# --- carga rapida (pegado) ------------------------------------------------------------------------------------
COLUMNAS_PEGADO = ["periodo", "cuil", "cargo", "dedicacion", "horas", "tipo_designacion", "numero_resolucion",
                   "ad_honorem", "fecha_desde", "fecha_hasta", "estado", "observaciones"]


def normalizar_columnas_designaciones_pegadas(df: pd.DataFrame) -> pd.DataFrame:
    renombres = {}
    for col in df.columns:
        clave = normalizar_columna_generica(col)
        if clave in ["periodo", "periodo_nombre", "semestre"]:
            renombres[col] = "periodo"
        elif clave in ["cuil", "cuit", "dni_cuil"]:
            renombres[col] = "cuil"
        elif clave in ["cargo"]:
            renombres[col] = "cargo"
        elif clave in ["dedicacion", "dedicación"]:
            renombres[col] = "dedicacion"
        elif clave in ["horas", "hs", "cantidad_horas"]:
            renombres[col] = "horas"
        elif clave in ["tipo_designacion", "tipo_de_designacion", "tipo", "designacion", "designación"]:
            renombres[col] = "tipo_designacion"
        elif clave in ["numero_resolucion", "numero_de_resolucion", "n_resolucion", "nro_resolucion", "resolucion",
                       "resolución", "n_de_resolucion"]:
            renombres[col] = "numero_resolucion"
        elif clave in ["ad_honorem", "adhonorem", "ad_hon"]:
            renombres[col] = "ad_honorem"
        elif clave in ["fecha_desde", "desde", "fecha_inicio", "inicio"]:
            renombres[col] = "fecha_desde"
        elif clave in ["fecha_hasta", "hasta", "fecha_fin", "fin"]:
            renombres[col] = "fecha_hasta"
        elif clave in ["estado", "estado_designacion"]:
            renombres[col] = "estado"
        elif clave in ["observaciones", "obs", "observacion"]:
            renombres[col] = "observaciones"
    df = df.rename(columns=renombres)
    for col in COLUMNAS_PEGADO:
        if col not in df.columns:
            df[col] = ""
    return df[COLUMNAS_PEGADO]


def periodos_ordenados_fechas_v230(df_periodos: pd.DataFrame) -> pd.DataFrame:
    base = df_periodos.copy() if isinstance(df_periodos, pd.DataFrame) else pd.DataFrame()
    if base is None or base.empty:
        return pd.DataFrame()
    for col in ["id", "nombre", "anio", "semestre", "fecha_inicio", "fecha_fin"]:
        if col not in base.columns:
            base[col] = ""
    out = base.copy()
    out["_inicio_v230"] = pd.to_datetime(out["fecha_inicio"], errors="coerce")
    out["_fin_v230"] = pd.to_datetime(out["fecha_fin"], errors="coerce")
    out["_anio_v230"] = pd.to_numeric(out["anio"], errors="coerce").fillna(0).astype(int)
    out["_sem_v230"] = pd.to_numeric(out["semestre"], errors="coerce").fillna(0).astype(int)
    out["_id_v230"] = pd.to_numeric(out["id"], errors="coerce").fillna(0).astype(int)
    out = out[out["_inicio_v230"].notna() & out["_fin_v230"].notna()].copy()
    if out.empty:
        return out
    out = out.sort_values(["_anio_v230", "_sem_v230", "_id_v230", "_inicio_v230"], kind="stable")
    return out.reset_index(drop=True)


def fecha_iso_integral(valor: Any, fallback: Any = "") -> str:
    candidato = valor
    if candidato is None or (isinstance(candidato, float) and pd.isna(candidato)):
        candidato = fallback
    if candidato is None:
        return ""
    try:
        if isinstance(candidato, (date, datetime, pd.Timestamp)):
            return str(pd.Timestamp(candidato).date())
    except Exception:
        pass
    txt = limpiar_texto_tabla(candidato)
    if not txt:
        txt = limpiar_texto_tabla(fallback)
    if not txt:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T].*)?", txt):
        try:
            return str(pd.to_datetime(txt[:10], format="%Y-%m-%d").date())
        except Exception:
            return ""
    try:
        return str(pd.to_datetime(txt, dayfirst=True).date())
    except Exception:
        return ""


def inferir_periodo_estado_fechas_v230(fecha_desde: Any, fecha_hasta: Any, per: pd.DataFrame, hoy: date) -> dict:
    """``_inferir_periodo_estado_fechas_v230`` efectiva (entry l. 49681)."""
    fd = fecha_iso_integral(fecha_desde, "")
    fh = fecha_iso_integral(fecha_hasta, "")
    vacio = {"periodo": None, "periodo_id": None, "periodo_nombre": "", "estado": "", "coincidencias": 0}
    if not fd or not fh or fd > fh:
        return vacio
    try:
        dfd = pd.Timestamp(fd)
        fhd = pd.Timestamp(fh)
    except Exception:
        return vacio
    if per.empty:
        return vacio
    candidatos = per[(dfd <= per["_fin_v230"]) & (fhd >= per["_inicio_v230"])].copy()
    if candidatos.empty:
        return vacio
    elegido = candidatos.iloc[-1].to_dict()
    try:
        pid = int(elegido.get("id"))
    except Exception:
        pid = None
    try:
        ini_p = pd.Timestamp(elegido.get("_inicio_v230")).date()
    except Exception:
        ini_p = None
    try:
        fin_p = pd.Timestamp(elegido.get("_fin_v230")).date()
    except Exception:
        fin_p = None
    try:
        ini_d = dfd.date()
        fin_d = fhd.date()
    except Exception:
        ini_d = fin_d = None
    vigente_hoy = (pid is not None and (ini_p is None or ini_p <= hoy) and (fin_p is None or fin_p >= hoy)
                   and (ini_d is None or ini_d <= hoy) and (fin_d is None or fin_d >= hoy))
    return {"periodo": elegido, "periodo_id": pid, "periodo_nombre": limpiar_texto_tabla(elegido.get("nombre", "")),
            "estado": "Activa" if vigente_hoy else "Finalizada", "coincidencias": int(len(candidatos))}


def parsear_designaciones_pegadas(texto: Any, df_periodos: pd.DataFrame, hoy: date) -> pd.DataFrame:
    """``parsear_designaciones_pegadas`` (entry l. 16717) con período y estado automáticos v230."""
    df = leer_tabla_pegada(texto)
    if df.empty:
        return pd.DataFrame()
    columnas_norm = [normalizar_columna_generica(c) for c in df.columns]
    tiene_encabezado = any(c in ["cuil", "cargo", "dedicacion", "horas", "tipo_designacion"] for c in columnas_norm)
    if not tiene_encabezado:
        bruto = str(texto).strip()
        df = pd.read_csv(StringIO(bruto), sep=None, engine="python", header=None, dtype=str, keep_default_na=False)
        nombres_cols = ["cuil", "cargo", "dedicacion", "horas", "tipo_designacion", "ad_honorem", "fecha_desde",
                        "fecha_hasta", "estado", "observaciones"]
        df = df.iloc[:, :len(nombres_cols)]
        df.columns = nombres_cols[:len(df.columns)]
    df = normalizar_columnas_designaciones_pegadas(df)
    for col in df.columns:
        df[col] = df[col].apply(limpiar_texto_tabla)
    campos_carga = ["cuil", "cargo", "dedicacion", "horas", "tipo_designacion", "numero_resolucion", "ad_honorem",
                    "fecha_desde", "fecha_hasta", "estado", "observaciones"]
    mascara_con_datos = df[campos_carga].apply(lambda fila: any(limpiar_texto_tabla(v) for v in fila.tolist()), axis=1)
    df = df[mascara_con_datos].copy()
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS_PEGADO)
    df["cuil"] = df["cuil"].apply(limpiar_cuil)
    df["cargo"] = df["cargo"].replace("", "JTP")
    df["dedicacion"] = df["dedicacion"].replace("", "Simple")
    df["horas"] = df["dedicacion"].apply(lambda d: horas_segun_dedicacion(d, 10)).astype(int)
    df["tipo_designacion"] = df["tipo_designacion"].replace("", "Interino")
    df["ad_honorem"] = df["ad_honorem"].replace({"": "No", "Si": "Sí", "SI": "Sí", "si": "Sí", "sí": "Sí"})
    df["fecha_desde"] = df["fecha_desde"].apply(lambda x: normalizar_fecha_texto(x, ""))
    df["fecha_hasta"] = df["fecha_hasta"].apply(lambda x: normalizar_fecha_texto(x, ""))
    per = periodos_ordenados_fechas_v230(df_periodos)
    periodos_out, estados_out = [], []
    for _, row in df.iterrows():
        inf = inferir_periodo_estado_fechas_v230(row.get("fecha_desde", ""), row.get("fecha_hasta", ""), per, hoy)
        periodos_out.append(inf.get("periodo_nombre", ""))
        estados_out.append(inf.get("estado", ""))
    df["periodo"] = periodos_out
    df["estado"] = estados_out
    df = df[df["cuil"].astype(str).str.strip() != ""].copy()
    return df.reset_index(drop=True)


__all__ = [n for n in dir() if not n.startswith("__")] + ["_is_na", "clave_cuil", "limpiar_cuil", "limpiar_texto_tabla",
                                                          "normalizar_clave", "safe_date"]
