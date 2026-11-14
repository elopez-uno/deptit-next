# Batch 04: pure R0 helpers extracted verbatim from certified B03 (codigos y espacios curriculares).
from __future__ import annotations

import re

import pandas as pd
from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def normalizar_codigo_materia(valor):
    """Devuelve el código académico canónico, sin separadores.

    Regla v121/v161:
    - se eliminan guiones, espacios, puntos y cualquier otro separador;
    - los códigos puramente numéricos se completan con ceros a la izquierda hasta 5 dígitos;
    - los códigos alfanuméricos conservan sus letras, pero también quedan sin separadores;
    - si Excel/Pandas convirtió un código entero en decimal (p. ej. ``8049.0``),
      se recupera primero ``8049`` y recién después se completa como ``08049``.

    Ejemplos: `05-001` -> `05001`, `5001` -> `05001`,
    `8049.0` -> `08049`, `09 027` -> `09027`, `00-009OLAP` -> `00009OLAP`.
    """
    if valor is None or pd.isna(valor):
        return ""

    # Excel y read_csv pueden inferir como float una columna donde hay códigos vacíos.
    # Evita que 08049 termine leído como 8049.0 y luego normalizado erróneamente a 80490.
    txt_crudo = str(valor).strip()
    m_entero_decimal = re.fullmatch(r"([0-9]+)\.0+", txt_crudo)
    if m_entero_decimal:
        txt_crudo = m_entero_decimal.group(1)

    txt = normalizar_clave(txt_crudo)
    if not txt:
        return ""
    codigo = re.sub(r"[^A-Z0-9]", "", txt)
    if codigo.isdigit() and len(codigo) < 5:
        codigo = codigo.zfill(5)
    return codigo


def es_materia_optativa_electiva(codigo, asignatura):
    """Identifica los espacios formales Optativa/Electiva del plan.

    La identificación se hace por el nombre formal del espacio (Optativa/Electiva),
    sin depender de un prefijo de código. La opción concreta que se dicta se administra
    por separado mediante ``opciones_curriculares``.
    """
    nombre_txt = normalizar_clave(asignatura or "").lower()
    return "optativa" in nombre_txt or "electiva" in nombre_txt


def _normalizar_tipo_opcion_v120(tipo):
    n = normalizar_clave(tipo or "").lower()
    if n == "optativa":
        return "Optativa"
    if n == "electiva":
        return "Electiva"
    return ""


def _clave_materia_unica_codigo_nombre(codigo, asignatura):
    return f"{normalizar_clave(codigo)}||{normalizar_clave(asignatura)}"
