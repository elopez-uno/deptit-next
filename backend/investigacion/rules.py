"""Reglas puras de Investigacion (B13-FIX02), copiadas de sus definiciones efectivas.  Sin SQL ni estado.

Origen (entry / modulos extraidos del certificado):
- ``_fecha_proyecto`` (extracted_batch04/fechas.py), ``_situacion_proyecto`` l. 10758, ``_texto_periodo_proyecto`` /
  ``_fechas_desde_periodo_legacy`` / ``proyecto_vigente_en_periodo`` / Excel v127-v217 / v258 / v162 / v261
  (domain/proyectos.py), ``_etiqueta_docente_excel_v217`` (domain/docentes.py), ``_cuil_desde_ref_docente_v217``
  (common/identifiers.py).
- Radicacion v216 l. 6993-7021 (+ ``_clave_unidad_proyecto_notificacion_v215`` / ``_slugify`` safe_helpers.py,
  ``_normalizar_texto_disposicion`` extracted_batch01/otros.py).
- ``_mensaje_capacidad_proyectos_v184`` (extracted_batch01/investigacion_extension.py), ``_etiqueta_acto_v263``
  (extracted_batch01/documentos.py), ``_valor_proyecto_v101`` (extracted_batch04/texto.py),
  ``_normalizar_encabezado_proyecto_v127`` (extracted_batch02/safe_helpers.py), ``_id_documento_valido_v266``
  (extracted_batch04/numeros.py).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd

from comisiones import rules as R

limpiar_texto_tabla = R.limpiar_texto_tabla
normalizar_clave = R.normalizar_clave
clave_cuil = R.clave_cuil
safe_date = R.safe_date

ESTADOS_PROYECTO_EXCEL_V127 = ["Activo", "Suspendido", "Finalizado", "Archivado"]
ESTADOS_ALTA = ["Activo", "Suspendido", "Finalizado"]
ROLES_EXCEL_V217 = ["Director", "Codirector", "Integrante", "Becario", "Colaborador", "Otro"]
TIPO = "investigacion"


# ------------------------------------------------------------------------------------------ fechas y situacion
def fecha_proyecto(valor) -> Optional[date]:
    """``_fecha_proyecto``: fechas ISO o argentinas sin intercambiar dia y mes."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or not str(valor).strip():
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    try:
        if re.match(r"^(?:19|20)\d{2}-\d{1,2}-\d{1,2}", texto):
            convertido = pd.to_datetime(texto, yearfirst=True, errors="coerce")
        else:
            convertido = pd.to_datetime(texto, dayfirst=True, errors="coerce")
        if pd.isna(convertido):
            return None
        return convertido.date()
    except Exception:
        return None


def situacion_proyecto(fila, fecha_referencia=None, hoy: Optional[date] = None) -> str:
    """``_situacion_proyecto`` (l. 10758); ``hoy`` = ``date.today()`` del certificado."""
    estado = str((fila or {}).get("estado") or "Activo").strip()
    if estado in ["Suspendido", "Archivado"]:
        return estado
    if estado == "Finalizado":
        return "Finalizado"
    referencia = fecha_proyecto(fecha_referencia) or hoy or date.today()
    inicio = fecha_proyecto((fila or {}).get("fecha_inicio"))
    fin = fecha_proyecto((fila or {}).get("fecha_fin"))
    if fin and fin < referencia:
        return "Finalizado"
    if inicio and inicio > referencia:
        return "Programado"
    return "En ejecución"


def fechas_desde_periodo_legacy(periodo_ejecucion, anio_llamado=None):
    texto = str(periodo_ejecucion or "").strip()
    patrones_fecha = re.findall(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-](?:19|20)\d{2}|(?:19|20)\d{2}[/-]\d{1,2}[/-]\d{1,2})\b",
        texto,
    )
    fechas = []
    for valor in patrones_fecha:
        f = fecha_proyecto(valor)
        if f:
            fechas.append(f)
    if len(fechas) >= 2:
        return min(fechas), max(fechas)
    if len(fechas) == 1:
        return fechas[0], fechas[0]
    anios = []
    for valor in re.findall(r"(?:19|20)\d{2}", texto):
        try:
            anios.append(int(valor))
        except Exception:
            pass
    if not anios and anio_llamado is not None and str(anio_llamado).strip():
        try:
            anios.append(int(anio_llamado))
        except Exception:
            pass
    if not anios:
        return None, None
    return date(min(anios), 1, 1), date(max(anios), 12, 31)


def texto_periodo_proyecto(fecha_inicio, fecha_fin) -> str:
    inicio = fecha_proyecto(fecha_inicio)
    fin = fecha_proyecto(fecha_fin)
    if inicio and fin:
        return f"{inicio.strftime('%d/%m/%Y')} al {fin.strftime('%d/%m/%Y')}"
    if inicio:
        return inicio.strftime("%d/%m/%Y")
    if fin:
        return f"Hasta {fin.strftime('%d/%m/%Y')}"
    return ""


def proyecto_vigente_en_periodo(proyecto, periodo) -> bool:
    """Verdadero cuando el proyecto (estado Activo) y el cuatrimestre se superponen en fechas reales."""
    if not proyecto or not periodo:
        return False
    if str(proyecto.get("estado") or "Activo") != "Activo":
        return False
    inicio_proyecto = fecha_proyecto(proyecto.get("fecha_inicio"))
    fin_proyecto = fecha_proyecto(proyecto.get("fecha_fin"))
    inicio_periodo = fecha_proyecto(periodo.get("fecha_inicio"))
    fin_periodo = fecha_proyecto(periodo.get("fecha_fin"))
    if inicio_proyecto and fin_proyecto and inicio_periodo and fin_periodo:
        return inicio_proyecto <= fin_periodo and fin_proyecto >= inicio_periodo
    try:
        anio_periodo = int(periodo.get("anio"))
    except Exception:
        return False
    inicio_legacy, fin_legacy = fechas_desde_periodo_legacy(
        proyecto.get("periodo_ejecucion", ""), proyecto.get("anio_llamado")
    )
    if not inicio_legacy or not fin_legacy:
        return False
    return inicio_legacy.year <= anio_periodo <= fin_legacy.year


# ------------------------------------------------------------------------------------------ radicacion v216
def normalizar_texto_disposicion(valor) -> str:
    return " ".join(str(valor or "").strip().split())


def _slugify(valor) -> str:
    txt = str(valor or "").strip().lower()
    for k, v in {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u"}.items():
        txt = txt.replace(k, v)
    txt = re.sub(r"[^a-z0-9]+", "_", txt).strip("_")
    return txt or "sin_nombre"


def clave_unidad_proyecto_v215(valor) -> str:
    txt = normalizar_texto_disposicion(valor)
    if not txt:
        return ""
    clave = _slugify(txt)
    for prefijo in ("departamento_de_", "departamento_del_", "departamento_", "depto_de_", "depto_del_", "depto_",
                    "dpto_de_", "dpto_del_", "dpto_"):
        if clave.startswith(prefijo):
            clave = clave[len(prefijo):]
            break
    return clave.strip("_")


def departamento_operativo_nombre(nombre) -> str:
    """``_departamento_actual_operativo_nombre`` (l. 6616) sobre el nombre del departamento de la sesion."""
    dep_actual = " ".join(str(nombre or "").strip().split())
    return dep_actual or "Departamento correspondiente"


def normalizar_radicacion_v216(valor, departamento_nombre) -> str:
    """Solo se guarda una radicacion externa al departamento creador (vacio si coincide con el actual)."""
    txt = normalizar_texto_disposicion(valor)
    if not txt:
        return ""
    clave_actual = clave_unidad_proyecto_v215(departamento_operativo_nombre(departamento_nombre))
    clave_valor = clave_unidad_proyecto_v215(txt)
    if clave_actual and clave_valor and clave_valor == clave_actual:
        return ""
    return txt


def ayuda_radicacion_v216(departamento_nombre) -> str:
    unidad = "Instituto/Departamento"
    departamento_actual = departamento_operativo_nombre(departamento_nombre)
    detalle_actual = f" ({departamento_actual})" if str(departamento_actual or "").strip() else ""
    return (
        f"Dejá este campo vacío si el proyecto radica en el mismo departamento que lo crea{detalle_actual}: "
        "el sistema ya registra automáticamente al departamento creador. "
        f"Completalo únicamente si la radicación corresponde a otro {unidad}."
    )


# ------------------------------------------------------------------------------------------ permisos heredados
def puede_administrar(proyecto: dict, rol: Optional[str], dep_actual: int) -> bool:
    """``_puede_administrar_proyecto_investigacion`` (l. 21190): superadmin / coordinacion o departamento creador."""
    if rol in ["superadmin", "coordinador_institucional"]:
        return True
    creador = proyecto.get("departamento_creador_id", proyecto.get("departamento_id"))
    if creador is None or (isinstance(creador, float) and pd.isna(creador)):
        return True
    try:
        return int(creador) == int(dep_actual)
    except Exception:
        return False


# ------------------------------------------------------------------------------------------ presentacion
def valor_proyecto_v101(valor, vacio="—") -> str:
    try:
        if valor is None or pd.isna(valor):
            return vacio
    except Exception:
        pass
    txt = str(valor).strip()
    return txt if txt else vacio


def horas_proyecto_v101(valor) -> str:
    try:
        if valor is None or pd.isna(valor):
            return "0 hs"
    except Exception:
        pass
    try:
        n = float(valor)
        return f"{int(n) if n.is_integer() else round(n, 1)} hs"
    except Exception:
        return f"{valor_proyecto_v101(valor, '0')} hs"


def meses_ejecucion_v258(fecha_inicio, fecha_fin) -> int:
    inicio = fecha_proyecto(fecha_inicio)
    fin = fecha_proyecto(fecha_fin)
    if inicio is None or fin is None or fin < inicio:
        return 0
    dias = int((fin - inicio).days) + 1
    if dias <= 0:
        return 0
    meses_float = float(dias) / (365.2425 / 12.0)
    return max(1, int(meses_float + 0.5))


def semanas_ejecucion_v162(fecha_inicio, fecha_fin) -> float:
    inicio = safe_date(fecha_inicio, None)
    fin = safe_date(fecha_fin, None)
    if inicio is None or fin is None or fin < inicio:
        return 0.0
    return round(((fin - inicio).days + 1) / 7.0, 2)


def horas_totales_ejecucion_v162(horas_semanales, fecha_inicio, fecha_fin) -> float:
    try:
        hs = float(horas_semanales or 0)
    except Exception:
        hs = 0.0
    return round(hs * semanas_ejecucion_v162(fecha_inicio, fecha_fin), 2)


def etiqueta_acto_v263(tipo_documento, numero, dependencia="") -> str:
    tipo = str(tipo_documento or "Documento").strip() or "Documento"
    nro = str(numero or "").strip()
    dep = str(dependencia or "").strip()
    base = f"{tipo} {nro}".strip() if nro else f"{tipo} s/n"
    return base + (f" · {dep}" if dep else "")


def id_documento_valido_v266(valor) -> bool:
    try:
        if pd.isna(valor):
            return False
    except Exception:
        pass
    return str(valor or "").strip() != ""


def mensaje_capacidad_v184(cap: dict) -> str:
    return (
        f"Horas contratadas: {float(cap.get('horas_contratadas',0) or 0):g} hs · "
        f"Comisiones: {float(cap.get('horas_comisiones',0) or 0):g} hs · "
        f"No lectivas: {float(cap.get('horas_no_lectivas',0) or 0):g} hs · "
        f"Investigación ya asignada: {float(cap.get('horas_investigacion',0) or 0):g} hs · "
        f"Extensión ya asignada: {float(cap.get('horas_extension',0) or 0):g} hs · "
        f"Disponibles para proyectos: {float(cap.get('horas_disponibles_proyectos',0) or 0):g} hs."
    )


def normalizar_proyectos_respaldo_v261(proyectos, proyecto_tipo_default="") -> list[dict]:
    """Deduplica proyectos por tipo+ID y conserva nombre/codigo para el repositorio."""
    salida = []
    vistos = set()
    for item in list(proyectos or []):
        if isinstance(item, dict):
            pid = item.get("id", item.get("proyecto_id"))
            p_tipo = str(item.get("tipo", item.get("proyecto_tipo", proyecto_tipo_default)) or proyecto_tipo_default).strip()
            nombre = str(item.get("nombre", item.get("nombre_proyecto", "")) or "").strip()
            codigo = str(item.get("codigo", item.get("codigo_proyecto", "")) or "").strip()
        else:
            continue
        try:
            pid = int(pid)
        except Exception:
            continue
        if not p_tipo or pid <= 0:
            continue
        clave = (p_tipo.casefold(), pid)
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append({"tipo": p_tipo, "id": pid, "nombre": nombre, "codigo": codigo})
    return salida


# ------------------------------------------------------------------------------------------ Excel v127 / v217
def normalizar_encabezado_v127(valor) -> str:
    txt = str(valor or "").strip().lower()
    txt = txt.translate(str.maketrans("áéíóúüñ", "aeiouun"))
    return re.sub(r"[^a-z0-9]+", "_", txt).strip("_")


_FECHA_ANIO_PRIMERO = re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T].*)?")


def parse_fecha_excel_v127(valor) -> Optional[date]:
    """DESVIACION DELIBERADA del baseline certificado (docs/ETAPA5_FINAL_REMEDIATION.md §13): el certificado aplica
    ``pd.to_datetime(txt, dayfirst=True)`` tambien a las celdas de texto año-primero e invierte dia y mes cuando el
    dia es <= 12 (2026-03-01 -> 2026-01-03).  Año-primero se interpreta estricto como año/mes/dia; el resto, igual."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, pd.Timestamp):
        return valor.date()
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    txt = str(valor).strip()
    if not txt or txt.lower() in ["nan", "nat", "none"]:
        return None
    m = _FECHA_ANIO_PRIMERO.fullmatch(txt)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    f = pd.to_datetime(txt, dayfirst=True, errors="coerce")
    return None if pd.isna(f) else f.date()


def parse_id_excel_v127(valor) -> Optional[int]:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    txt = str(valor).strip()
    if not txt or txt.lower() in ["nan", "none"]:
        return None
    try:
        return int(float(txt))
    except Exception:
        return None


def etiqueta_proyecto_excel_v217(row) -> str:
    codigo = limpiar_texto_tabla(row.get("codigo_proyecto", ""))
    nombre = limpiar_texto_tabla(row.get("nombre_proyecto", ""))
    return f"[{codigo}] {nombre}" if codigo else nombre


def etiqueta_docente_excel_v217(row) -> str:
    nombre = limpiar_texto_tabla(row.get("nombre_completo", row.get("docente", "")))
    cuil = limpiar_texto_tabla(row.get("cuil", ""))
    return f"{nombre} | {cuil}" if nombre else cuil


def resolver_proyecto_ref_v217(ref, proyectos: pd.DataFrame) -> Optional[dict]:
    txt = " ".join(str(ref or "").strip().split())
    if not txt or proyectos is None or proyectos.empty:
        return None
    codigo = ""
    nombre = txt
    m = re.match(r"^\[([^\]]+)\]\s*(.*)$", txt)
    if m:
        codigo = limpiar_texto_tabla(m.group(1))
        nombre = limpiar_texto_tabla(m.group(2))
    if codigo:
        mask = proyectos.get("codigo_proyecto", pd.Series(index=proyectos.index, dtype=str)).fillna("").astype(str) \
            .map(normalizar_clave).eq(normalizar_clave(codigo))
        sub = proyectos[mask]
        if not sub.empty:
            return sub.iloc[0].to_dict()
    clave_nombre = normalizar_clave(nombre)
    mask = proyectos.get("nombre_proyecto", pd.Series(index=proyectos.index, dtype=str)).fillna("").astype(str) \
        .map(normalizar_clave).eq(clave_nombre)
    sub = proyectos[mask]
    if len(sub) == 1:
        return sub.iloc[0].to_dict()
    return None


def cuil_desde_ref_docente_v217(ref) -> str:
    txt = str(ref or "").strip()
    if "|" in txt:
        txt = txt.rsplit("|", 1)[-1].strip()
    return R.limpiar_cuil(txt)


def numero_g(valor: Any) -> str:
    """``f"{x:g}"`` de Python."""
    return f"{float(valor):g}"
