"""Validacion estructural comun de archivos subidos (6A-B1).

Excel (.xlsx) llega como base64 (Materias, Comisiones, Investigacion, Extension) o multipart (carga integral) y lo leen
openpyxl / pandas en memoria.  Antes de entregarlo al lector se valida el CONTENIDO (no la extension ni el MIME):
firma ZIP, contenedor legible, partes minimas de un libro OOXML, sin cifrado, cantidad de entradas y tamaño
descomprimido DECLARADO acotados (``zipfile`` nunca lee mas alla de lo declarado), lo que corta las bombas de
descompresion.  Nada se escribe a disco.  PDF (``resoluciones_respaldos.rules.es_pdf``) y Word
(``disposiciones.storage.validate_docx_bytes``) ya tienen su propia validacion de contenido.
"""

from __future__ import annotations

import io
import zipfile
from typing import Optional

ZIP_MAGIC = b"PK\x03\x04"
XLSX_MAX_ENTRIES = 2000
XLSX_MAX_UNCOMPRESSED = 256 * 1024 * 1024
XLSX_PARTES = ("[Content_Types].xml", "xl/workbook.xml")


def problema_xlsx(contenido: bytes) -> Optional[str]:
    """Motivo por el que ``contenido`` no es un .xlsx aceptable (para el log), o None.  Nunca lanza."""
    if not contenido:
        return "vacio"
    if not bytes(contenido[:4]) == ZIP_MAGIC:
        return "sin firma ZIP"
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as zf:
            infos = zf.infolist()
            if len(infos) > XLSX_MAX_ENTRIES:
                return "demasiadas entradas"
            if sum(max(0, i.file_size) for i in infos) > XLSX_MAX_UNCOMPRESSED:
                return "tamaño descomprimido excesivo"
            if any(i.flag_bits & 0x1 for i in infos):
                return "cifrado"
            nombres = {i.filename for i in infos}
            if not all(p in nombres for p in XLSX_PARTES):
                return "no es un libro Excel"
    except (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, OSError, EOFError):
        return "ZIP ilegible"
    return None
