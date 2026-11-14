# Batch 01 pure helpers extracted verbatim from frozen 8AS.
from __future__ import annotations

def _clave_numero_inicial_disposicion_v162(periodo_id):
    return f"numero_inicial_disposiciones_periodo_{int(periodo_id)}"


def _condicion_periodo_equivalente_sql(alias_periodo="p", alias_ref="pr"):
    """Condición SQL para comparar períodos equivalentes entre departamentos."""
    return f"""
        {alias_periodo}.institucion_id = {alias_ref}.institucion_id
        AND (
            (COALESCE({alias_periodo}.anio, -1) = COALESCE({alias_ref}.anio, -1)
             AND COALESCE({alias_periodo}.semestre, -1) = COALESCE({alias_ref}.semestre, -1))
            OR COALESCE({alias_periodo}.nombre, '') = COALESCE({alias_ref}.nombre, '')
        )
    """


def nombre_periodo(anio, semestre):
    return f"{int(anio)}-{int(semestre)}"
