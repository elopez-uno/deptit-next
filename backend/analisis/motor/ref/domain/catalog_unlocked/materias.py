# B08: extracted verbatim from certified B07 (materias: modo de comparticion y clave conceptual v137).
# Function text copied byte-for-byte from app_postgresql_refactor_b07_catalogs.py (sha256 f422f375a973756b5a7d7f90d99db91452a09ef16976f941ea536115615e4946).
# Catalogs are the canonical B07 objects (analisis.motor.ref.catalogs); do not duplicate them here.
from __future__ import annotations

from analisis.motor.ref.catalogs.materias import ETIQUETAS_COMPARTICION_MATERIA
from analisis.motor.ref.catalogs.materias import MODO_COMPARTICION_AUTO
from analisis.motor.ref.catalogs.materias import MODO_COMPARTICION_ESPECIFICA
from analisis.motor.ref.catalogs.materias import MODO_COMPARTICION_SELECCIONADA
from analisis.motor.ref.extracted_batch04.materias import _clave_materia_unica_codigo_nombre
from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def _normalizar_modo_comparticion_v137(valor):
    txt = str(valor or "").strip()
    if txt in ETIQUETAS_COMPARTICION_MATERIA:
        return ETIQUETAS_COMPARTICION_MATERIA[txt]
    n = normalizar_clave(txt)
    if n in {"ESPECÍFICA", "ESPECIFICA", "ESPECÍFICO", "ESPECIFICO", "INDIVIDUAL"}:
        return MODO_COMPARTICION_ESPECIFICA
    if n in {"SELECCIONADA", "SELECCIONADOS", "GRUPO", "PARCIAL"}:
        return MODO_COMPARTICION_SELECCIONADA
    return MODO_COMPARTICION_AUTO


def _clave_materia_conceptual_v137(fila):
    """Clave conceptual respetando la configuración explícita entre planes."""
    if fila is None:
        return ""
    try:
        mid = int(fila.get("materia_id", fila.get("id")))
    except Exception:
        mid = None
    base = _clave_materia_unica_codigo_nombre(fila.get("codigo", ""), fila.get("asignatura", ""))
    modo = _normalizar_modo_comparticion_v137(fila.get("comparticion_modo", MODO_COMPARTICION_AUTO))
    grupo = str(fila.get("comparticion_grupo", "") or "").strip()
    if modo == MODO_COMPARTICION_ESPECIFICA:
        return f"ESPECIFICA::{mid if mid is not None else base}"
    if modo == MODO_COMPARTICION_SELECCIONADA:
        return f"SELECCIONADA::{grupo}" if grupo else f"ESPECIFICA::{mid if mid is not None else base}"
    return f"AUTO::{base}"
