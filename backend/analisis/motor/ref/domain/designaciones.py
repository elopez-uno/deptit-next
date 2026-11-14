# B05: extracted verbatim from certified B04 (designaciones: claves, firmas, fechas de vigencia, cargos).
from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd

from analisis.motor.ref.extracted_batch01.designaciones import _es_ad_honorem_v162
from analisis.motor.ref.extracted_batch04.designaciones import _es_funcion_no_docente_v162
from analisis.motor.ref.extracted_batch04.fechas import _fecha_a_timestamp_seguro
from analisis.motor.ref.extracted_batch04.fechas import safe_date
from analisis.motor.ref.extracted_batch04.identidad import _clave_cuil
from analisis.motor.ref.extracted_batch04.movimientos import _extraer_horas_desde_texto
from analisis.motor.ref.extracted_batch04.numeros import _hora_numero
from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla
from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def extraer_partes_designacion(designacion_txt):
    """
    Convierte textos del tipo:
    'JTP - Simple - 10 hs - Interino - Estado Activa'
    en partes mínimas para resumir cambios.
    """
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
        if parte_l in ["interino", "concursado", "loc. serv.", "loc serv", "loc. servicios", "locacion de servicios", "locación de servicios"]:
            tipo_designacion = parte.strip()
            break
    if not tipo_designacion:
        for tipo_posible in ["Interino", "Concursado", "Loc. Serv."]:
            if tipo_posible.lower() in texto.lower():
                tipo_designacion = tipo_posible
                break

    return {
        "cargo": cargo,
        "dedicacion": dedicacion,
        "horas": horas,
        "tipo_designacion": tipo_designacion
    }


def _claves_designaciones_dataframe(df_designaciones):
    claves = set()
    if df_designaciones is None or df_designaciones.empty:
        return claves
    for _, row in df_designaciones.iterrows():
        try:
            claves.add(_clave_designacion_desde_row_designacion(row))
        except Exception:
            pass
    return {c for c in claves if c}


def _fecha_fin_real_designacion_v269(row):
    for campo in ["fecha_finalizacion_efectiva", "fecha_hasta_prevista", "fecha_hasta"]:
        try:
            f = safe_date(row.get(campo), None)
        except Exception:
            f = None
        if f is not None:
            return f
    return None


def _vigente_al_cierre_v269(row, fecha_cierre):
    if fecha_cierre is None:
        return True
    if normalizar_clave(row.get("estado", "")) == "SUSPENDIDA":
        return False
    desde = safe_date(row.get("fecha_desde"), None)
    hasta = _fecha_fin_real_designacion_v269(row)
    if desde is not None and desde > fecha_cierre:
        return False
    if hasta is not None and hasta < fecha_cierre:
        return False
    return True


def _firma_designacion_v269(row):
    try:
        hs = int(float(pd.to_numeric(row.get("horas"), errors="coerce") or 0))
    except Exception:
        hs = 0
    return (
        _clave_cuil(row.get("cuil")) or str(row.get("cuil") or "").strip(),
        normalizar_clave(row.get("cargo", "")),
        normalizar_clave(row.get("dedicacion", "")),
        hs,
        normalizar_clave(row.get("tipo_designacion", "")),
        normalizar_clave(row.get("ad_honorem", "No")) or "NO",
        1 if _es_funcion_no_docente_v162(row.get("funcion_no_docente")) else 0,
    )


def _detalle_coincide_designacion_v269(detalle, row):
    """Coincidencia conservadora entre un movimiento legacy y una designación."""
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
    # La secuencia contractual completa evita confundir Simple con Parcial + Simple.
    contrato = normalizar_clave(f"{row.get('cargo','')} {row.get('dedicacion','')} {hs} hs {row.get('tipo_designacion','')}")
    if contrato and contrato in txt:
        return True
    requisitos = [x for x in [cargo, dedic, tipo] if x]
    if not requisitos or not all(x in txt for x in requisitos):
        return False
    return bool(re.search(rf"(?<!\d){re.escape(str(hs))}\s*HS\b", txt, flags=re.I)) if hs else True


def _fecha_iso_reparacion_concursado(valor):
    """Normaliza una fecha de designación a AAAA-MM-DD sin invertir día y mes."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()

    txt = str(valor).strip()
    if not txt:
        return ""

    formatos = [
        (r"^\d{4}-\d{2}-\d{2}(?:[ T].*)?$", "%Y-%m-%d", False),
        (r"^\d{2}/\d{2}/\d{4}$", "%d/%m/%Y", True),
        (r"^\d{2}-\d{2}-\d{4}$", "%d-%m-%Y", True),
    ]
    for patron, formato, _ in formatos:
        if re.match(patron, txt):
            try:
                base = txt[:10]
                return datetime.strptime(base, formato).date().isoformat()
            except Exception:
                pass
    try:
        ts = pd.to_datetime(txt, errors="coerce", dayfirst=False)
        if pd.isna(ts):
            return ""
        return ts.date().isoformat()
    except Exception:
        return ""


def _clave_reparacion_designacion_concursada(fila):
    """Identifica una designación sin usar sus fechas ni el período."""
    try:
        horas = int(float(fila.get("horas") or 0))
    except Exception:
        horas = 0
    return (
        str(fila.get("cuil") or "").strip(),
        str(fila.get("cargo") or "").strip().upper(),
        str(fila.get("dedicacion") or "").strip().upper(),
        horas,
        str(fila.get("ad_honorem") or "No").strip().upper(),
    )


def _texto_designacion_para_match(row):
    """Texto estable para comparar una designación con el movimiento automático de cierre."""
    try:
        horas = int(row.get("horas", 0)) if pd.notna(row.get("horas", 0)) else 0
    except Exception:
        horas = row.get("horas", "")
    return f"{row.get('cargo', '')} - {row.get('dedicacion', '')} - {horas} hs - {row.get('tipo_designacion', '')}"


def _normalizar_designacion_txt_para_partes(texto):
    """Limpia prefijos como '2026-1 - ' para poder leer cargo/dedicación/tipo."""
    txt = limpiar_texto_tabla(texto)
    # Movimientos migrados suelen venir como: '2026-1 - Adjunto - Parcial - 20 hs - Interino'.
    txt = re.sub(r"^\s*\d{4}\s*[-/]\s*\d+\s*-\s*", "", txt)
    txt = re.sub(r"\s*-\s*Mov\.\s*horas\s*:\s*-?\d+(?:[\.,]\d+)?\s*$", "", txt, flags=re.I)
    return txt.strip()


def _clave_designacion_desde_partes(partes):
    if not isinstance(partes, dict):
        return None
    cargo = limpiar_texto_tabla(partes.get("cargo", "")).lower()
    dedic = limpiar_texto_tabla(partes.get("dedicacion", "")).lower()
    tipo = limpiar_texto_tabla(partes.get("tipo_designacion", "")).lower()
    hs = _extraer_horas_desde_texto(partes.get("horas", ""))
    if not cargo and not dedic and not tipo and not hs:
        return None
    return (cargo, dedic, tipo, round(float(hs or 0), 3))


def _clave_designacion_desde_texto(texto):
    partes = extraer_partes_designacion(_normalizar_designacion_txt_para_partes(texto))
    return _clave_designacion_desde_partes(partes)


def _clave_designacion_desde_row_designacion(row):
    cargo = limpiar_texto_tabla(row.get("cargo", ""))
    dedic = limpiar_texto_tabla(row.get("dedicacion", ""))
    tipo = limpiar_texto_tabla(row.get("tipo_designacion", ""))
    hs = _hora_numero(row.get("horas", 0))
    return (cargo.lower(), dedic.lower(), tipo.lower(), round(float(hs or 0), 3))


def _normalizar_cargo_para_jerarquia(valor):
    """Convierte variantes habituales de cargos a los nombres canónicos de la app."""
    import unicodedata
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


def _extraer_departamento_origen_prestado(observaciones):
    """Lee el departamento de origen guardado al registrar un docente prestado."""
    obs = limpiar_texto_tabla(observaciones)
    if not obs:
        return ""
    m = re.search(
        r"Docente\s+prestado\s+desde\s+(.+?)(?:\.\s*No\s+posee\s+designaci[oó]n\s+local|\.|$)",
        obs,
        flags=re.I,
    )
    return limpiar_texto_tabla(m.group(1)) if m else ""


def _designaciones_docentes_activas_v162(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=df.columns if isinstance(df, pd.DataFrame) else None)
    out = df.copy()
    estado = out.get("estado", pd.Series(index=out.index, dtype=str)).fillna("").astype(str).str.strip().str.casefold()
    no_doc = out.get("funcion_no_docente", pd.Series(0, index=out.index)).map(_es_funcion_no_docente_v162)
    return out[estado.eq("activa") & ~no_doc].copy()


def _conteo_ad_honorem_v165(df):
    if df is None or df.empty:
        return 0
    return int(df.get("ad_honorem", pd.Series(index=df.index, dtype=str)).map(_es_ad_honorem_v162).sum())


def _fecha_fin_designacion_analisis_v169(row):
    """Fecha que determina la vigencia real para una foto histórica.

    Una baja efectiva manda sobre el vencimiento previsto. Si no hubo baja real,
    se usa el vencimiento previsto/administrativo. El cierre automático no carga
    fecha_finalizacion_efectiva, por lo que una designación finalizada solo por
    cierre sigue apareciendo en la foto del semestre.
    """
    for campo in ("fecha_finalizacion_efectiva", "fecha_hasta_prevista", "fecha_hasta"):
        try:
            valor = row.get(campo, "")
        except Exception:
            valor = ""
        if valor is not None and not pd.isna(valor) and str(valor).strip():
            return _fecha_a_timestamp_seguro(valor)
    return pd.NaT


def _fecha_prestamo_texto_v179(valor):
    """Normaliza fechas de préstamo para columnas de presentación del Plantel.

    PostgreSQL/psycopg2 puede devolver columnas DATE como datetime.date. Las columnas
    fecha_alta_periodo/fecha_finalizacion_periodo provienen históricamente como texto;
    pandas reciente no permite insertar un date dentro de una columna StringDtype.
    Se normaliza a ISO YYYY-MM-DD para mantener un único tipo y evitar TypeError.
    """
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    if isinstance(valor, (date, datetime)):
        try:
            return valor.strftime("%Y-%m-%d")
        except Exception:
            return str(valor)
    txt = str(valor).strip()
    if not txt or txt.casefold() in {"none", "nan", "nat"}:
        return ""
    return txt


def _v279_cargo_residual_educacion(valor):
    raw = limpiar_texto_tabla(valor)
    if not raw:
        return False
    # Firma observada en el backup: dentro de cargo aparecen período y/o fecha.
    if re.search(r"\b20\d{2}\s*[-/]\s*[12]\b", raw):
        return True
    if re.search(r"\b20\d{2}-\d{2}-\d{2}\b", raw):
        return True
    return False


def _designacion_es_exclusivamente_docente_v249(variables):
    """Determina si el acto corresponde únicamente a función docente.

    La promoción de Investigación/Extensión al Artículo 1 solo se aplica a esta
    situación. Las disposiciones no docentes o mixtas conservan su lógica previa.
    """
    variables = dict(variables or {})
    if bool(variables.get("ES_FUNCION_NO_DOCENTE")) or bool(variables.get("ES_FUNCION_MIXTA")):
        return False
    datos = variables.get("designaciones_disposicion") or []
    if not isinstance(datos, (list, tuple)) or not datos:
        return False
    tiene_docente = False
    tiene_no_docente = False
    for item in datos:
        if not isinstance(item, dict):
            continue
        if _es_funcion_no_docente_v162(item.get("funcion_no_docente")):
            tiene_no_docente = True
        else:
            tiene_docente = True
    return bool(tiene_docente and not tiene_no_docente)
