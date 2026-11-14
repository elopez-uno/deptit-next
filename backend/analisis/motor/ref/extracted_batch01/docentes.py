# Batch 01 pure helpers extracted verbatim from frozen 8AS.
from __future__ import annotations

def _departamento_origen_desde_obs_prestado(obs):
    txt = str(obs or "").strip()
    txt = txt.replace("Docente prestado desde ", "")
    txt = txt.replace(". No posee designación local en este departamento.", "")
    txt = txt.strip(" .")
    return txt


def _reemplazar_variables_manteniendo_docente(texto, variables, marcador_docente="§§DOCENTE§§"):
    """Reemplaza todas las variables salvo {{docente}}, que se deja como marcador.

    Esto permite reconstruir artículos en los que solo el nombre del docente debe
    quedar en negrita, aunque la plantilla original tenga el párrafo completo en bold.
    """
    nuevo = texto or ""
    nuevo = nuevo.replace("{{docente}}", marcador_docente)
    for clave, valor in variables.items():
        if isinstance(valor, (bool, dict, list)) or str(clave) == "docente":
            continue
        nuevo = nuevo.replace("{{" + str(clave) + "}}", "" if valor is None else str(valor))
    return nuevo


def _texto_funcion_no_docente_limpio_v164(valor):
    return " ".join(str(valor or "").strip().split())
