# Batch 01 pure helpers extracted verbatim from frozen 8AS.
from __future__ import annotations

def _etiqueta_acto_v263(tipo_documento, numero, dependencia=""):
    tipo = str(tipo_documento or "Documento").strip() or "Documento"
    nro = str(numero or "").strip()
    dep = str(dependencia or "").strip()
    base = f"{tipo} {nro}".strip() if nro else f"{tipo} s/n"
    return base + (f" · {dep}" if dep else "")
