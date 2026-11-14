"""Reglas puras de Resoluciones y respaldos (B13-FIX02) y el hardening NEXT aprobado (D-AK1/D-AK2/D-AK3).

Origen certificado:
- ``CATEGORIAS_RESPALDO_V249`` l. 49995; tipos ``["Resolución", "Disposición", "Otro"]`` l. 51729 / 54576; categorias
  que exigen docentes l. 51770; tipo sugerido l. 51727.
- ``_nombre_dependencia_documental_v262`` (extracted_batch01/otros.py) y ``_tipo_resolucion_legacy_desde_dependencia_
  v262`` (extracted_batch02/safe_helpers.py).
- ``_normalizar_docentes_respaldo_v251`` (domain/docentes.py) y ``_normalizar_proyectos_respaldo_v261``
  (domain/proyectos.py).
- Tope de 50 MB: ``50 * 1024 * 1024`` (UI l. 52052 y writers l. 50363 / 50512).
NEXT (no existe en el certificado): firma ``%PDF-`` (D-AK2) y ``Content-Disposition`` seguro (D-AK3).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import quote

from designaciones.rules import etiqueta_acto  # noqa: F401  (``_etiqueta_acto_v263``, ya portado)
from docentes.rules import clave_cuil, safe_date  # noqa: F401  (``_clave_cuil`` / ``safe_date`` certificados)

CATEGORIAS_RESPALDO_V249 = [
    "Designación docente",
    "Cambio de cargo",
    "Cambio de dedicación",
    "Cambio de condición Ad Honorem / Rentada",
    "Proyecto de Extensión",
    "Proyecto de Investigación",
    "Otro",
]
TIPOS_DOCUMENTO = ["Resolución", "Disposición", "Otro"]
CATEGORIAS_DOCENTE = {"Designación docente", "Cambio de cargo", "Cambio de dedicación",
                      "Cambio de condición Ad Honorem / Rentada"}
CATEGORIAS_PROYECTO = {"Proyecto de Extensión", "Proyecto de Investigación"}
TIPOS_CON_DEPENDENCIA = {"Resolución", "Disposición"}
MODOS_DOCENTES = ["Designaciones activas del período actual", "Elegir un período"]
ESTADOS_DEPENDENCIA = ["Activa", "Inactiva"]

MAX_PDF_BYTES = 50 * 1024 * 1024
PDF_MAGIC = b"%PDF-"
PDF_MIME = "application/pdf"
NOMBRE_PDF_DEFECTO = "documento.pdf"


def tipo_sugerido(categoria: str) -> str:
    return "Disposición" if categoria == "Proyecto de Investigación" else "Resolución"


def nombre_dependencia_v262(nombre: Any) -> str:
    return " ".join(str(nombre or "").strip().split())


def tipo_resolucion_legacy_v262(nombre: Any) -> str:
    clave = nombre_dependencia_v262(nombre).casefold()
    if clave == "rectorado":
        return "Rectoral"
    if clave == "consejo superior":
        return "Consejo Superior"
    return ""


def normalizar_docentes_respaldo_v251(docentes: Any) -> list[dict]:
    """Deduplica docentes por CUIL y conserva los metadatos del vinculo."""
    salida, vistos = [], set()
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
        clave = clave_cuil(cuil) or cuil
        if not cuil or clave in vistos:
            continue
        vistos.add(clave)
        salida.append({"cuil": cuil, "nombre": nombre or cuil, "tipo_movimiento": tipo_movimiento,
                       "detalle_vinculo": detalle_vinculo})
    return salida


def normalizar_proyectos_respaldo_v261(proyectos: Any, proyecto_tipo_default: str = "") -> list[dict]:
    """``_normalizar_proyectos_respaldo_v261`` (domain/proyectos.py) completo: dicts y tuplas (la copia de
    Investigacion solo recibe dicts; para dicts ambas son identicas)."""
    salida, vistos = [], set()
    for item in list(proyectos or []):
        if isinstance(item, dict):
            pid = item.get("id", item.get("proyecto_id"))
            p_tipo = str(item.get("tipo", item.get("proyecto_tipo", proyecto_tipo_default)) or proyecto_tipo_default).strip()
            nombre = str(item.get("nombre", item.get("nombre_proyecto", "")) or "").strip()
            codigo = str(item.get("codigo", item.get("codigo_proyecto", "")) or "").strip()
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            p_tipo = str(item[0] or proyecto_tipo_default).strip()
            pid = item[1]
            nombre = str(item[2] if len(item) > 2 else "" or "").strip()
            codigo = str(item[3] if len(item) > 3 else "" or "").strip()
        else:
            continue
        try:
            pid = int(pid)
        except Exception:
            continue
        if not p_tipo or pid <= 0:
            continue
        clave = (p_tipo.casefold(), pid)
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append({"tipo": p_tipo, "id": pid, "nombre": nombre, "codigo": codigo})
    return salida


# ------------------------------------------------------------------------------------------ hardening NEXT
def es_pdf(contenido: bytes) -> bool:
    """D-AK2: el contenido real debe empezar con ``%PDF-`` (no se confia en extension, nombre ni MIME)."""
    return bytes(contenido[:len(PDF_MAGIC)]) == PDF_MAGIC


_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_ASCII_UNSAFE_RE = re.compile(r'[^A-Za-z0-9._ ()\-]')


def nombre_descarga(nombre: Any) -> str:
    """Nombre visible del PDF (``archivo_nombre`` o "documento.pdf", l. 50494) sin controles ni separadores de ruta."""
    texto = _CONTROL_RE.sub("", str(nombre or "")).replace("/", "_").replace("\\", "_").strip()
    return texto[:200] or NOMBRE_PDF_DEFECTO


def content_disposition(nombre: Any) -> str:
    """D-AK3: ``attachment`` con ``filename`` ASCII seguro + ``filename*`` UTF-8 (sin CR/LF ni comillas)."""
    visible = nombre_descarga(nombre)
    ascii_name = unicodedata.normalize("NFKD", visible).encode("ascii", "ignore").decode("ascii")
    ascii_name = _ASCII_UNSAFE_RE.sub("_", ascii_name).strip(" .") or NOMBRE_PDF_DEFECTO
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(visible, safe='')}"
