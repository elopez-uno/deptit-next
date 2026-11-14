# B05: extracted verbatim from certified B04 (docentes: fichas, respaldos, mensajes).
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from integraciones.resumen_motor.ref.domain.salarios import _nivel_posgrado_salarial_normalizado_v256
from analisis.motor.ref.extracted_batch04.identidad import _clave_cuil
from analisis.motor.ref.extracted_batch04.identidad import separar_docente_en_apellido_nombres
from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla


def _mezclar_docente_existente_excel_v247(row, actual):
    """Combina una fila del Excel con la ficha actual sin permitir borrados por celdas vacías.

    Solo los campos con un valor real en la hoja Docentes reemplazan el dato existente.
    El CUIL y el tipo de docente se conservan; el Estado solo cambia si fue informado.
    """
    actual = dict(actual or {})

    apellido_actual = limpiar_texto_tabla(actual.get("apellido", ""))
    nombres_actual = limpiar_texto_tabla(actual.get("nombres", ""))
    nombre_actual = limpiar_texto_tabla(actual.get("nombre", ""))
    if not apellido_actual and not nombres_actual and nombre_actual:
        try:
            ap_sep, nom_sep = separar_docente_en_apellido_nombres(nombre_actual)
            apellido_actual = limpiar_texto_tabla(ap_sep)
            nombres_actual = limpiar_texto_tabla(nom_sep)
        except Exception:
            pass

    actuales = {
        "apellido": apellido_actual,
        "nombres": nombres_actual,
        "legajo": limpiar_texto_tabla(actual.get("legajo", "")),
        "titulo": limpiar_texto_tabla(actual.get("titulo", "")),
        "titulo_posgrado": limpiar_texto_tabla(actual.get("titulo_posgrado", "")),
        "antiguedad_anios": (
            None if actual.get("antiguedad_anios") is None or pd.isna(actual.get("antiguedad_anios"))
            else int(float(actual.get("antiguedad_anios")))
        ),
        "nivel_posgrado_salarial": _nivel_posgrado_salarial_normalizado_v256(actual.get("nivel_posgrado_salarial", "")),
        "email": limpiar_texto_tabla(actual.get("email", "")),
        "telefono": limpiar_texto_tabla(actual.get("telefono", "")),
        "ref_legajo_fisico": limpiar_texto_tabla(actual.get("ref_legajo_fisico", "")),
        "estado": limpiar_texto_tabla(actual.get("estado", "")) or "Activo",
        "tipo_docente": limpiar_texto_tabla(actual.get("tipo_docente", "")) or "Propio",
        "observaciones": limpiar_texto_tabla(actual.get("observaciones", "")),
    }

    campos_excel = [
        "apellido", "nombres", "legajo", "titulo", "titulo_posgrado",
        "email", "telefono", "ref_legajo_fisico", "observaciones",
    ]
    informados = []
    resultado = dict(actuales)
    for campo in campos_excel:
        valor = limpiar_texto_tabla(row.get(campo, ""))
        if valor:
            resultado[campo] = valor
            informados.append(campo)

    if bool(row.get("_antiguedad_informada_v260", False)):
        resultado["antiguedad_anios"] = int(row.get("antiguedad_anios"))
        informados.append("antiguedad_anios")

    if bool(row.get("_nivel_posgrado_informado_v260", False)):
        resultado["nivel_posgrado_salarial"] = _nivel_posgrado_salarial_normalizado_v256(
            row.get("nivel_posgrado_salarial", "")
        )
        informados.append("nivel_posgrado_salarial")

    if bool(row.get("_estado_informado_v247", False)):
        valor_estado = limpiar_texto_tabla(row.get("estado", ""))
        if valor_estado:
            resultado["estado"] = valor_estado
            informados.append("estado")

    return resultado, informados


def _fecha_mensaje_docente(valor):
    """Formatea fechas del mensaje docente sin intercambiar día y mes.

    PostgreSQL suele devolver fechas como objetos ``date`` o como texto ISO
    ``AAAA-MM-DD``. Aplicar ``dayfirst=True`` directamente a ese formato puede
    interpretar, por ejemplo, 2026-07-01 como 7 de enero. Por eso primero se
    reconocen explícitamente los formatos ISO y luego los formatos habituales
    día/mes/año.
    """
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]

    dt = None
    if isinstance(valor, (datetime, date, pd.Timestamp)):
        dt = valor
    else:
        texto = str(valor).strip()
        if not texto:
            return ""

        # Formatos guardados por PostgreSQL/SQLite y por los date_input de Streamlit.
        formatos = (
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%d/%m/%Y",
            "%d-%m-%Y",
        )
        for formato in formatos:
            try:
                dt = datetime.strptime(texto[:19], formato)
                break
            except Exception:
                continue

        if dt is None:
            try:
                # Último recurso para textos no estándar escritos manualmente.
                convertido = pd.to_datetime(texto, dayfirst=True, errors="coerce")
                if not pd.isna(convertido):
                    dt = convertido
            except Exception:
                dt = None

        if dt is None:
            return texto

    return f"{int(dt.day)} de {meses[int(dt.month)-1]} de {int(dt.year)}"


def _horas_mensaje(valor):
    try:
        numero = float(valor or 0)
        return f"{numero:g} hs"
    except Exception:
        return f"{valor} hs"


def _etiqueta_docente_excel_v217(row):
    nombre = limpiar_texto_tabla(row.get("nombre_completo", row.get("docente", "")))
    cuil = limpiar_texto_tabla(row.get("cuil", ""))
    return f"{nombre} | {cuil}" if nombre else cuil


def _normalizar_docentes_respaldo_v251(docentes):
    """Deduplica docentes por CUIL y conserva metadatos específicos del vínculo."""
    salida = []
    vistos = set()
    for item in list(docentes or []):
        if isinstance(item, dict):
            cuil = str(item.get("cuil", "") or "").strip()
            nombre = str(item.get("nombre", "") or item.get("docente", "") or cuil).strip()
            tipo_movimiento = str(item.get("tipo_movimiento", item.get("movimiento", "")) or "").strip()
            detalle_vinculo = str(item.get("detalle_vinculo", item.get("detalle", "")) or "").strip()
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            cuil = str(item[0] or "").strip()
            nombre = str(item[1] or cuil).strip()
            tipo_movimiento = str(item[2] if len(item) > 2 else "" or "").strip()
            detalle_vinculo = str(item[3] if len(item) > 3 else "" or "").strip()
        else:
            continue
        clave = _clave_cuil(cuil) or cuil
        if not cuil or clave in vistos:
            continue
        vistos.add(clave)
        salida.append({
            "cuil": cuil,
            "nombre": nombre or cuil,
            "tipo_movimiento": tipo_movimiento,
            "detalle_vinculo": detalle_vinculo,
        })
    return salida
