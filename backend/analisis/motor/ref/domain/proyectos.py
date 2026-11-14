# B05: extracted verbatim from certified B04 (proyectos de investigacion/extension: fechas, horas, referencias).
from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd

from analisis.motor.ref.extracted_batch04.fechas import _fecha_proyecto
from analisis.motor.ref.extracted_batch04.fechas import safe_date
from analisis.motor.ref.extracted_batch04.texto import _valor_proyecto_v101
from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla
from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def _prefijo_instituto_proyecto(valor):
    """Devuelve el instituto/departamento con preposición para redactar investigación."""
    if valor is None or pd.isna(valor):
        return ""
    txt = " ".join(str(valor).strip().split())
    if not txt:
        return ""
    txt_lower = txt.lower()
    if txt_lower.startswith(("del ", "de la ", "de los ", "de las ", "de ")):
        return txt
    return f"del {txt}"


def _prefijo_area_extension(valor):
    """Devuelve el área/secretaría con una preposición natural para la disposición."""
    if valor is None or pd.isna(valor):
        return ""
    txt = " ".join(str(valor).strip().split())
    if not txt:
        return ""
    bajo = txt.lower()
    if bajo.startswith(("del ", "de la ", "de los ", "de las ", "de ")):
        return txt
    if bajo.startswith(("secretaría", "secretaria", "área", "area", "dirección", "direccion", "coordinación", "coordinacion")):
        return f"de la {txt}"
    return f"del {txt}"


def _fechas_desde_periodo_legacy(periodo_ejecucion, anio_llamado=None):
    """Migra el campo libre anterior a fechas reales sin perder datos históricos."""
    texto = str(periodo_ejecucion or "").strip()
    patrones_fecha = re.findall(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-](?:19|20)\d{2}|(?:19|20)\d{2}[/-]\d{1,2}[/-]\d{1,2})\b",
        texto,
    )
    fechas = []
    for valor in patrones_fecha:
        f = _fecha_proyecto(valor)
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


def _texto_periodo_proyecto(fecha_inicio, fecha_fin):
    inicio = _fecha_proyecto(fecha_inicio)
    fin = _fecha_proyecto(fecha_fin)
    if inicio and fin:
        return f"{inicio.strftime('%d/%m/%Y')} al {fin.strftime('%d/%m/%Y')}"
    if inicio:
        return inicio.strftime("%d/%m/%Y")
    if fin:
        return f"Hasta {fin.strftime('%d/%m/%Y')}"
    return ""


def proyecto_vigente_en_periodo(proyecto, periodo):
    """Verdadero cuando el proyecto y el cuatrimestre se superponen en fechas reales."""
    if not proyecto or not periodo:
        return False
    if str(proyecto.get("estado") or "Activo") != "Activo":
        return False
    inicio_proyecto = _fecha_proyecto(proyecto.get("fecha_inicio"))
    fin_proyecto = _fecha_proyecto(proyecto.get("fecha_fin"))
    inicio_periodo = _fecha_proyecto(periodo.get("fecha_inicio"))
    fin_periodo = _fecha_proyecto(periodo.get("fecha_fin"))
    if inicio_proyecto and fin_proyecto and inicio_periodo and fin_periodo:
        return inicio_proyecto <= fin_periodo and fin_proyecto >= inicio_periodo

    # Respaldo para registros históricos que todavía no tengan fechas migrables.
    try:
        anio_periodo = int(periodo.get("anio"))
    except Exception:
        return False
    inicio_legacy, fin_legacy = _fechas_desde_periodo_legacy(
        proyecto.get("periodo_ejecucion", ""), proyecto.get("anio_llamado")
    )
    if not inicio_legacy or not fin_legacy:
        return False
    return inicio_legacy.year <= anio_periodo <= fin_legacy.year


def _parse_fecha_excel_proyecto_v127(valor):
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
    f = pd.to_datetime(txt, dayfirst=True, errors="coerce")
    return None if pd.isna(f) else f.date()


def _parse_id_excel_proyecto_v127(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    txt = str(valor).strip()
    if not txt or txt.lower() in ["nan", "none"]:
        return None
    try:
        return int(float(txt))
    except Exception:
        return None


def _meses_ejecucion_proyecto_v258(fecha_inicio, fecha_fin):
    """Cantidad estimada de meses de ejecución del proyecto.

    Se calcula a partir de la duración real entre fechas usando la duración media
    del mes calendario. De este modo un año completo equivale a 12 meses, dos
    años a 24, etc. Si hay una vigencia válida pero menor a un mes, computa 1.
    """
    inicio = _fecha_proyecto(fecha_inicio)
    fin = _fecha_proyecto(fecha_fin)
    if inicio is None or fin is None or fin < inicio:
        return 0
    dias = int((fin - inicio).days) + 1
    if dias <= 0:
        return 0
    meses_float = float(dias) / (365.2425 / 12.0)
    return max(1, int(meses_float + 0.5))


def _entero_proyecto_v101(valor):
    try:
        if valor is None or pd.isna(valor):
            return 0
    except Exception:
        pass
    try:
        return int(float(valor))
    except Exception:
        return 0


def _horas_proyecto_v101(valor):
    try:
        if valor is None or pd.isna(valor):
            return "0 hs"
    except Exception:
        pass
    try:
        n = float(valor)
        return f"{int(n) if n.is_integer() else round(n, 1)} hs"
    except Exception:
        return f"{_valor_proyecto_v101(valor, '0')} hs"


def _semanas_ejecucion_proyecto_v162(fecha_inicio, fecha_fin):
    inicio = safe_date(fecha_inicio, None)
    fin = safe_date(fecha_fin, None)
    if inicio is None or fin is None or fin < inicio:
        return 0.0
    return round(((fin - inicio).days + 1) / 7.0, 2)


def _horas_totales_ejecucion_proyecto_v162(horas_semanales, fecha_inicio, fecha_fin):
    try:
        hs = float(horas_semanales or 0)
    except Exception:
        hs = 0.0
    return round(hs * _semanas_ejecucion_proyecto_v162(fecha_inicio, fecha_fin), 2)


def _semanas_solapadas_v177(inicio_a, fin_a, inicio_b, fin_b):
    a1 = safe_date(inicio_a, None); a2 = safe_date(fin_a, None)
    b1 = safe_date(inicio_b, None); b2 = safe_date(fin_b, None)
    if None in (a1, a2, b1, b2):
        return 0.0
    ini = max(a1, b1); fin = min(a2, b2)
    if fin < ini:
        return 0.0
    return round(((fin - ini).days + 1) / 7.0, 2)


def _horas_asignacion_periodo_v177(fila_asig, fila_proyecto, periodo):
    """Horas de una asignación durante el período académico, respetando fechas disponibles."""
    try:
        hs = float(pd.to_numeric(fila_asig.get("horas_asignadas", 0), errors="coerce") or 0)
    except Exception:
        hs = 0.0
    p_ini = safe_date(periodo.get("fecha_inicio"), None)
    p_fin = safe_date(periodo.get("fecha_fin"), None)
    pr_ini = safe_date(fila_proyecto.get("fecha_inicio"), p_ini)
    pr_fin = safe_date(fila_proyecto.get("fecha_fin"), p_fin)
    if p_ini is None or p_fin is None:
        return 0.0
    ini = max([x for x in [p_ini, pr_ini] if x is not None])
    fin = min([x for x in [p_fin, pr_fin] if x is not None])

    # La fecha de carga y la fecha de baja, cuando son coherentes con el período,
    # permiten aproximar mejor el tiempo real de una asignación que no cubrió todo el semestre.
    f_carga = safe_date(fila_asig.get("fecha_carga"), None)
    f_baja = safe_date(fila_asig.get("fecha_baja"), None)
    if f_carga is not None and p_ini <= f_carga <= p_fin:
        ini = max(ini, f_carga)
    if f_baja is not None and p_ini <= f_baja <= p_fin:
        fin = min(fin, f_baja)
    if fin < ini:
        return 0.0
    semanas = round(((fin - ini).days + 1) / 7.0, 2)
    return round(hs * semanas, 2)


def _etiqueta_proyecto_excel_v217(row):
    codigo = limpiar_texto_tabla(row.get("codigo_proyecto", ""))
    nombre = limpiar_texto_tabla(row.get("nombre_proyecto", ""))
    return f"[{codigo}] {nombre}" if codigo else nombre


def _resolver_proyecto_ref_v217(ref, proyectos):
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
        mask = proyectos.get("codigo_proyecto", pd.Series(index=proyectos.index, dtype=str)).fillna("").astype(str).map(normalizar_clave).eq(normalizar_clave(codigo))
        sub = proyectos[mask]
        if not sub.empty:
            return sub.iloc[0].to_dict()
    clave_nombre = normalizar_clave(nombre)
    mask = proyectos.get("nombre_proyecto", pd.Series(index=proyectos.index, dtype=str)).fillna("").astype(str).map(normalizar_clave).eq(clave_nombre)
    sub = proyectos[mask]
    if len(sub) == 1:
        return sub.iloc[0].to_dict()
    return None


def _normalizar_proyectos_respaldo_v261(proyectos, proyecto_tipo_default=""):
    """Deduplica proyectos por tipo+ID y conserva nombre/código para el repositorio."""
    salida = []
    vistos = set()
    for item in list(proyectos or []):
        if isinstance(item, dict):
            pid = item.get("id", item.get("proyecto_id"))
            p_tipo = str(item.get("tipo", item.get("proyecto_tipo", proyecto_tipo_default)) or proyecto_tipo_default).strip()
            nombre = str(item.get("nombre", item.get("nombre_proyecto", "")) or "").strip()
            codigo = str(item.get("codigo", item.get("codigo_proyecto", "")) or "").strip()
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            p_tipo = str(item[0] or proyecto_tipo_default).strip()
            pid = item[1]
            nombre = str(item[2] if len(item) > 2 else "" or "").strip()
            codigo = str(item[3] if len(item) > 3 else "" or "").strip()
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
