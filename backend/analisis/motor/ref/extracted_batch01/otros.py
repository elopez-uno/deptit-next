# Batch 01 pure helpers extracted verbatim from frozen 8AS.
from __future__ import annotations

def _abreviar_asignatura_v95(nombre, max_len=18):
    txt=" ".join(str(nombre or "").split())
    if len(txt)<=max_len:return txt
    palabras=txt.split()
    if len(palabras)>1:
        sig="".join(p[0].upper() for p in palabras if p and p.lower() not in {"de","del","la","las","los","y","e","en"})
        if 2<=len(sig)<=8:return sig
    return txt[:max_len-1]+"…"


def _action_kind_from_label(label):
    txt = str(label or "").lower()
    if any(x in txt for x in ["eliminar", "borrar", "quitar", "🗑"]):
        return "delete"
    if any(x in txt for x in ["guardar", "crear", "registrar", "cargar", "actualizar", "asignar", "generar", "abrir", "cerrar", "renovar", "finalizar", "importar", "reemplazar", "subir", "editar", "anular", "confirmar"]):
        return "write"
    return "read"


def _inicio_estado_linea(cantidad, texto_ok="Sin problemas", singular="caso", plural="casos", gravedad="alta"):
    n = int(cantidad or 0)
    if n <= 0:
        return "🟢", texto_ok
    icono = "🔴" if gravedad == "alta" else "🟠"
    return icono, f"{n} {singular if n == 1 else plural}"


def _nombre_dependencia_documental_v262(nombre):
    return " ".join(str(nombre or "").strip().split())


def _normalizar_texto_disposicion(valor):
    return " ".join(str(valor or "").strip().split())


def _reemplazar_variables_texto_simple(texto, variables):
    nuevo = texto or ""
    for clave, valor in variables.items():
        if isinstance(valor, (bool, dict, list)):
            continue
        nuevo = nuevo.replace("{{" + str(clave) + "}}", "" if valor is None else str(valor))
    return nuevo


def _v279_placeholders(n):
    return ",".join(["%s"] * int(n))


def normalizar_columna_generica(col):
    clave = str(col).strip().lower()
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "ñ": "n"
    }
    for a, b in reemplazos.items():
        clave = clave.replace(a, b)
    clave = clave.replace(".", "").replace("/", "_").replace("-", "_").replace(" ", "_")
    while "__" in clave:
        clave = clave.replace("__", "_")
    return clave.strip("_")
