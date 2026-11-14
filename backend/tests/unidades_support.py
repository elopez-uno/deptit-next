"""6A-B3 (unidades académicas en toda la interfaz): divergencias DECIDIDAS respecto del certificado.

DEPTIT no usa "Escuela" ni "Facultad/Escuela" como categoría genérica: las etiquetas visibles dicen "Unidad académica".
Los diferenciales aplican estas sustituciones al lado CERTIFICADO antes de comparar; todo lo demás sigue idéntico.
Las claves internas (``escuela``, ``escuela_oferente``, rangos ``ListaEscuelasOferentes``) no cambian.
"""
from __future__ import annotations

import io
import re
import zipfile

from openpyxl import load_workbook

# (texto certificado, texto NEXT), en orden: primero los más largos
TEXTOS_MATERIAS = [
    ("Facultad/Escuela oferente muestra las escuelas actuales y permite ",
     "Unidad académica oferente muestra las unidades académicas actuales y permite "),
    ("Facultad/Escuela oferente", "Unidad académica oferente"),
    ("Tipo/Código/Nombre/Escuela siguen", "Tipo/Código/Nombre/Unidad académica siguen"),
    ("Elegí una escuela existente o escribí manualmente otra.", "Elegí una unidad académica existente o escribí manualmente otra."),
]
# celdas de encabezado cuyo valor completo cambia (hojas "Listas" y "Espacios disponibles" del modelo de opciones)
CELDAS_MATERIAS = {"Escuelas": "Unidades académicas", "Escuela": "Unidad académica"}
ENCABEZADO_OPCIONES_HISTORICO = "Facultad/Escuela oferente"
ENCABEZADO_OPCIONES = "Unidad académica oferente"
MSG_ELECTIVA_CERT = "Las Electivas deben indicar la Facultad/Escuela oferente."
MSG_ELECTIVA = "Las Electivas deben indicar la unidad académica oferente."
DETALLE_CERT, DETALLE = "Escuela oferente", "Unidad académica oferente"
COMISIONES_XLSX = [(b"Escuela/s", "Unidades académicas")]


def decidido_materias(valor):
    """Valor de celda/comentario certificado con las etiquetas decididas."""
    if not isinstance(valor, str):
        return valor
    if valor in CELDAS_MATERIAS:
        return CELDAS_MATERIAS[valor]
    for a, b in TEXTOS_MATERIAS:
        valor = valor.replace(a, b)
    return valor


def xlsx_con_encabezado_opciones(contenido: bytes, encabezado: str) -> bytes:
    """El mismo modelo de opciones con otro encabezado en la columna D (p. ej. el histórico)."""
    wb = load_workbook(io.BytesIO(contenido))
    ws = wb["Carga rápida"]
    assert ws["D1"].value in (ENCABEZADO_OPCIONES, ENCABEZADO_OPCIONES_HISTORICO)
    ws["D1"].value = encabezado
    for t in ws.tables.values():  # el encabezado de la tabla Excel debe coincidir con la celda
        for col in t.tableColumns:
            if col.name in (ENCABEZADO_OPCIONES, ENCABEZADO_OPCIONES_HISTORICO):
                col.name = encabezado
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def xlsx_comisiones_decidido(contenido: bytes) -> bytes:
    """Libro certificado de comisiones con el encabezado decidido de la hoja Materias ("Unidades académicas")."""
    entrada, salida = zipfile.ZipFile(io.BytesIO(contenido)), io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for info in entrada.infolist():
            datos = entrada.read(info.filename)
            if info.filename.endswith(".xml"):
                # openpyxl escribe las celdas inline con referencias de carácter ("&#233;") y las tablas en UTF-8
                celdas = info.filename.startswith("xl/worksheets/")
                for a, b in COMISIONES_XLSX:
                    datos = datos.replace(a, b.encode("ascii", "xmlcharrefreplace") if celdas else b.encode("utf-8"))
            z.writestr(info, datos)
    return salida.getvalue()


_ROTULO_CERT = re.compile(r"Escuela/s: (.*?)(?= — |$)")


def rotulo_materia_decidido(texto):
    """Rótulo del selector de materia de Comisiones ("… — Escuela/s: X — …") con la etiqueta decidida: "Unidad
    académica: X" o, si vienen varias unidades unidas por " / ", "Unidades académicas: X"."""
    if not isinstance(texto, str):
        return texto
    return _ROTULO_CERT.sub(lambda m: ("Unidades académicas" if " / " in m.group(1) else "Unidad académica")
                            + f": {m.group(1)}", texto)


def preview_comisiones_decidida(df):
    """Vista previa certificada de carga rápida con el rótulo decidido en las columnas de materia encontrada."""
    df = df.copy()
    for col in ("materia_encontrada", "materias_adicionales_encontradas"):
        if col in df.columns:
            df[col] = df[col].apply(lambda v: [rotulo_materia_decidido(x) for x in v] if isinstance(v, list)
                                    else rotulo_materia_decidido(v))
    return df
