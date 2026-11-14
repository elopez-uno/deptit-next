# Batch 04: pure R0 helpers extracted verbatim from certified B03 (CUIL y nombres de personas).
from __future__ import annotations

import re
from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla


def nombre_completo(apellido, nombres):
    apellido = apellido.strip() if apellido else ""
    nombres = nombres.strip() if nombres else ""
    if apellido and nombres:
        return f"{apellido}, {nombres}"
    return apellido or nombres


def _clave_cuil(valor):
    """Compara CUIL por sus dígitos, sin alterar cómo se guarda o se muestra."""
    return re.sub(r"[^0-9]", "", limpiar_texto_tabla(valor))


def limpiar_cuil(valor):
    txt = limpiar_texto_tabla(valor)
    if txt.endswith(".0"):
        txt = txt[:-2]
    return txt.replace(" ", "")


def separar_docente_en_apellido_nombres(docente):
    txt = limpiar_texto_tabla(docente)
    if not txt:
        return "", ""
    if "," in txt:
        partes = txt.split(",", 1)
        return partes[0].strip(), partes[1].strip()
    partes = txt.split()
    if len(partes) <= 1:
        return txt, ""
    # Criterio práctico: si no viene separado, tomo la última palabra como apellido.
    return partes[-1].strip(), " ".join(partes[:-1]).strip()
