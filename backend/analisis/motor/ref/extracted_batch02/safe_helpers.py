# Batch 02: pure R0 helpers with explicitly allowlisted safe globals.
from __future__ import annotations

import re
from analisis.motor.ref.extracted_batch01.otros import _nombre_dependencia_documental_v262
from analisis.motor.ref.extracted_batch01.otros import _normalizar_texto_disposicion

def _slugify(valor):
    txt = str(valor or "").strip().lower()
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n",
        "ü": "u"
    }
    for k, v in reemplazos.items():
        txt = txt.replace(k, v)
    txt = re.sub(r"[^a-z0-9]+", "_", txt).strip("_")
    return txt or "sin_nombre"


def es_tenant_base_informatica_uno(institucion_slug, departamento_slug):
    """Solo el Departamento de Informática e Ingeniería de la UNO debe heredar la base actual.

    El resto de los departamentos/instituciones empiezan vacíos para no duplicar
    los 80 docentes y las comisiones cargadas originalmente para Informática.
    """
    inst = _slugify(institucion_slug or "")
    dep = _slugify(departamento_slug or "")
    return (
        inst == "universidad_nacional_del_oeste"
        and "informatica" in dep
        and "ingenieria" in dep
    )


def _normalizar_tipo_designacion_disposicion(valor):
    txt = _normalizar_texto_disposicion(valor).lower()
    if txt == "concursado":
        return "Concursado"
    if txt == "interino":
        return "Interino"
    return _normalizar_texto_disposicion(valor)


def _nombre_departamento_para_considerando(valor):
    txt = _normalizar_texto_disposicion(valor)
    if not txt:
        return "Departamento correspondiente"
    if txt.lower().startswith("departamento"):
        return txt
    return f"Departamento de {txt}"


def _clave_unidad_proyecto_notificacion_v215(valor):
    """Normaliza una unidad institucional para compararla con el departamento emisor."""
    txt = _normalizar_texto_disposicion(valor)
    if not txt:
        return ""
    clave = _slugify(txt)
    prefijos = (
        "departamento_de_", "departamento_del_", "departamento_",
        "depto_de_", "depto_del_", "depto_", "dpto_de_", "dpto_del_", "dpto_",
    )
    for prefijo in prefijos:
        if clave.startswith(prefijo):
            clave = clave[len(prefijo):]
            break
    return clave.strip("_")


def _normalizar_encabezado_opcion_v124(valor):
    txt = str(valor or "").strip().lower()
    trans = str.maketrans("áéíóúüñ", "aeiouun")
    txt = txt.translate(trans)
    txt = re.sub(r"[^a-z0-9]+", "_", txt).strip("_")
    return txt


def _normalizar_encabezado_proyecto_v127(valor):
    txt = str(valor or "").strip().lower()
    txt = txt.translate(str.maketrans("áéíóúüñ", "aeiouun"))
    return re.sub(r"[^a-z0-9]+", "_", txt).strip("_")


def _inicio_cuil_clave(valor):
    return re.sub(r"[^0-9]", "", str(valor or ""))


def _v279_cuil_residual_educacion(valor):
    raw = str(valor or "").strip()
    if not raw:
        return False
    # Un CUIL válido puede tener dígitos y guiones, pero nunca apellido/nombre.
    if re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", raw):
        return True
    # También protege contra textos concatenados aun sin letras latinas simples.
    dig = re.sub(r"\D", "", raw)
    return len(dig) != 11


def _sql_contratos_v238():
    # La identidad contractual excluye departamento/período_id deliberadamente:
    # una misma contratación replicada para un docente compartido se cuenta una
    # sola vez institucionalmente. Una resolución o cualquier diferencia real en
    # cargo/dedicación/horas/tipo/fechas mantiene contratos separados.
    return r"""
        contratos AS (
            SELECT
                cuil_clave,
                UPPER(BTRIM(COALESCE(cargo,''))) AS cargo_key,
                UPPER(BTRIM(COALESCE(dedicacion,''))) AS dedicacion_key,
                COALESCE(horas,0) AS horas_key,
                UPPER(BTRIM(COALESCE(tipo_designacion,''))) AS tipo_key,
                UPPER(BTRIM(COALESCE(ad_honorem,''))) AS ad_honorem_key,
                UPPER(BTRIM(COALESCE(numero_resolucion,''))) AS resolucion_key,
                COALESCE(desde_date::text, UPPER(BTRIM(COALESCE(CAST(fecha_desde AS text),'')))) AS desde_key,
                COALESCE(hasta_date::text, UPPER(BTRIM(COALESCE(CAST(fecha_hasta AS text),'')))) AS hasta_key,
                MIN(id) AS id_referencia,
                MIN(CAST(cuil AS text)) AS cuil,
                MIN(cargo) AS cargo,
                MIN(dedicacion) AS dedicacion,
                MAX(COALESCE(horas,0)) AS horas,
                MIN(tipo_designacion) AS tipo_designacion,
                MIN(ad_honorem) AS ad_honorem,
                MIN(numero_resolucion) AS numero_resolucion,
                MIN(CAST(fecha_desde AS text)) AS fecha_desde,
                MAX(CAST(fecha_hasta AS text)) AS fecha_hasta,
                STRING_AGG(DISTINCT departamento_nombre, ' | ' ORDER BY departamento_nombre) AS departamentos,
                STRING_AGG(DISTINCT periodo_actual, ' | ' ORDER BY periodo_actual) AS periodos_contratacion,
                COUNT(*) AS registros_departamentales
            FROM vigentes
            GROUP BY
                cuil_clave,
                UPPER(BTRIM(COALESCE(cargo,''))),
                UPPER(BTRIM(COALESCE(dedicacion,''))),
                COALESCE(horas,0),
                UPPER(BTRIM(COALESCE(tipo_designacion,''))),
                UPPER(BTRIM(COALESCE(ad_honorem,''))),
                UPPER(BTRIM(COALESCE(numero_resolucion,''))),
                COALESCE(desde_date::text, UPPER(BTRIM(COALESCE(CAST(fecha_desde AS text),'')))),
                COALESCE(hasta_date::text, UPPER(BTRIM(COALESCE(CAST(fecha_hasta AS text),''))))
        )
    """


def _tipo_resolucion_legacy_desde_dependencia_v262(nombre):
    """Compatibilidad con el campo histórico v255 sin limitar nuevas dependencias."""
    clave = _nombre_dependencia_documental_v262(nombre).casefold()
    if clave == "rectorado":
        return "Rectoral"
    if clave == "consejo superior":
        return "Consejo Superior"
    return ""
