# Batch 01 pure helpers extracted verbatim from frozen 8AS.
from __future__ import annotations

def _es_ad_honorem_v162(valor):
    return str(valor or "").strip().casefold() in {"sí", "si", "1", "true", "verdadero", "yes"}


def _estado_designacion_visible_v162(valor):
    """Texto de presentación del estado sin alterar el valor persistido en la base."""
    txt = str(valor or "").strip()
    return "Suspendida (licenciada)" if txt.casefold() == "suspendida" else txt


def _inicio_contexto_designacion(fila):
    cargo = str(fila.get("cargo") or "").strip()
    dedicacion = str(fila.get("dedicacion") or "").strip()
    tipo = str(fila.get("tipo_designacion") or "").strip()
    partes = [x for x in [cargo, dedicacion, tipo] if x]
    return " · ".join(partes)


def _variables_para_bloque_disposicion(variables, bloque_nombre=None):
    """
    En los párrafos condicionales, algunas plantillas usan variables genéricas como
    {{cargo}} y {{dedicación}}. Si el docente tiene designación concursada e interina,
    no se puede completar con el valor general porque mezclaría ambas. Por eso,
    dentro de cada bloque se pisa el valor genérico con el que corresponde a ese tipo.
    """
    vars_bloque = dict(variables)

    if bloque_nombre == "SI_TIENE_CONCURSADO":
        vars_bloque["cargo"] = variables.get("cargo_concursado", variables.get("cargo", ""))
        vars_bloque["dedicación"] = variables.get("dedicación_concursado", variables.get("dedicación", ""))
        vars_bloque["horas"] = variables.get("horas_concursado", variables.get("horas", ""))

    if bloque_nombre == "SI_TIENE_INTERINO":
        vars_bloque["cargo"] = variables.get("cargo_interino", variables.get("cargo", ""))
        vars_bloque["dedicación"] = variables.get("dedicación_interino", variables.get("dedicación", ""))
        vars_bloque["horas"] = variables.get("horas_interino", variables.get("horas", ""))
        # La base conserva la clave vieja por compatibilidad, pero en la interfaz y en el documento es Rectoral.
        vars_bloque["resolucion_rectoral_interino"] = variables.get("resolucion_rectoral_interino", variables.get("resolucion_cs_interino", ""))
        vars_bloque["resolucion_cs_interino"] = variables.get("resolucion_rectoral_interino", variables.get("resolucion_cs_interino", ""))

    return vars_bloque


def _where_designaciones_activas_sql(alias="d"):
    # Activa y no perteneciente a período cerrado. Si no hay tabla periodos o periodo_id,
    # igual filtra por estado Activa.
    return f"COALESCE({alias}.estado, 'Activa') = 'Activa'"


def detalle_designacion(row):
    return f"{row['cargo']} - {row['dedicacion']} - {row['horas']} hs - {row['tipo_designacion']} - Estado {row['estado']}"
