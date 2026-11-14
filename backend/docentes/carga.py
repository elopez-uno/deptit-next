"""Carga rapida simple de docentes (pura, sin base de datos), copiada de la fuente certificada B13-FIX02.

Origen (reference_fix02, entry): ``leer_tabla_pegada`` l. 16548, ``normalizar_columnas_docentes_pegados`` l. 16567,
``parsear_docentes_pegados`` l. 16619, ``generar_excel_modelo_carga_rapida_docentes`` l. 16773 (la redefinicion de
l. 45816 solo agrega cache), ``normalizar_columna_generica`` (``extracted_batch01/otros.py``).  Mismas versiones de
pandas/openpyxl que el runtime certificado (``constraints-runtime.txt``).
"""

from __future__ import annotations

import unicodedata
from io import BytesIO, StringIO

import pandas as pd

from .rules import ESTADOS_DOCENTE, limpiar_cuil, limpiar_texto_tabla, separar_docente_en_apellido_nombres

COLUMNAS = ["cuil", "apellido", "nombres", "docente", "legajo", "titulo", "titulo_posgrado", "antiguedad_anios",
            "nivel_posgrado_salarial", "email", "telefono", "ref_legajo_fisico", "estado", "observaciones"]


def normalizar_columna_generica(col):
    """Clave de encabezado (``extracted_batch01/otros.py`` l. 52) con el hardening de la Etapa 5 / Tanda B (B4): el
    certificado solo transliteraba á é í ó ú ñ, asi que los encabezados de SUS PROPIOS modelos "Años antigüedad"
    (``ü``) y "N° resolución" (``°``) no se reconocian y esos datos nunca se importaban.  Ahora se quitan todas las
    marcas diacriticas (NFD: ü -> u, à -> a, …) y los signos de grado / ordinal (° º).  Para los encabezados que el
    certificado ya reconocia el resultado es identico (test)."""
    clave = str(col).strip().lower()
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "ñ": "n"
    }
    for a, b in reemplazos.items():
        clave = clave.replace(a, b)
    clave = "".join(ch for ch in unicodedata.normalize("NFD", clave) if not unicodedata.combining(ch))
    clave = clave.replace("°", "").replace("º", "")
    clave = clave.replace(".", "").replace("/", "_").replace("-", "_").replace(" ", "_")
    while "__" in clave:
        clave = clave.replace("__", "_")
    return clave.strip("_")


def leer_tabla_pegada(texto):
    if texto is None or not str(texto).strip():
        return pd.DataFrame()

    bruto = str(texto).strip()
    # v161: todo se lee como texto para preservar codigos con ceros a la izquierda.
    kwargs = {"dtype": str, "keep_default_na": False}
    try:
        return pd.read_csv(StringIO(bruto), sep=None, engine="python", **kwargs)
    except Exception:
        return pd.read_csv(StringIO(bruto), sep="\t", **kwargs)


def normalizar_columnas_docentes_pegados(df):
    renombres = {}
    for col in df.columns:
        clave = normalizar_columna_generica(col)
        if clave in ["cuil", "cuit", "dni_cuil"]:
            renombres[col] = "cuil"
        elif clave in ["apellido", "apellidos", "apellido_s"]:
            renombres[col] = "apellido"
        elif clave in ["nombre", "nombres", "nombre_s"]:
            renombres[col] = "nombres"
        elif clave in ["docente", "apellido_y_nombre", "apellido_nombre", "nombre_completo", "apellidoynombre"]:
            renombres[col] = "docente"
        elif clave in ["legajo", "nro_legajo", "numero_legajo"]:
            renombres[col] = "legajo"
        elif clave in ["titulo", "titulo_de_grado", "título", "titulo_grado"]:
            renombres[col] = "titulo"
        elif clave in ["titulo_posgrado", "titulo_de_posgrado", "título_posgrado", "posgrado", "titulo_postgrado",
                       "postgrado"]:
            renombres[col] = "titulo_posgrado"
        elif clave in [
            "antiguedad_anios", "antiguedad", "anios_antiguedad", "anos_antiguedad",
            "anios_de_antiguedad", "anos_de_antiguedad", "años_antigüedad", "años_de_antigüedad",
        ]:
            renombres[col] = "antiguedad_anios"
        elif clave in [
            "nivel_posgrado_salarial", "nivel_de_posgrado_salarial", "nivel_posgrado",
            "nivel_de_posgrado", "posgrado_salarial", "adicional_posgrado",
        ]:
            renombres[col] = "nivel_posgrado_salarial"
        elif clave in ["email", "correo", "correo_electronico", "mail"]:
            renombres[col] = "email"
        elif clave in ["telefono", "tel", "celular"]:
            renombres[col] = "telefono"
        elif clave in ["ref_legajo_fisico", "referencia_legajo_fisico", "legajo_fisico", "referencia"]:
            renombres[col] = "ref_legajo_fisico"
        elif clave in ["estado", "estado_docente"]:
            renombres[col] = "estado"
        elif clave in ["observaciones", "observacion", "obs", "comentario", "comentarios"]:
            renombres[col] = "observaciones"

    df = df.rename(columns=renombres)
    for col in COLUMNAS:
        if col not in df.columns:
            df[col] = ""
    return df[COLUMNAS]


def parsear_docentes_pegados(texto):
    df = leer_tabla_pegada(texto)
    if df.empty:
        return pd.DataFrame()

    # Si se pego sin encabezado: cuil, apellido, nombres, legajo, titulo, titulo_posgrado, email, telefono, ...
    columnas_norm = [normalizar_columna_generica(c) for c in df.columns]
    tiene_encabezado = any(c in ["cuil", "apellido", "apellidos", "nombres", "docente", "legajo"] for c in columnas_norm)
    if not tiene_encabezado:
        bruto = str(texto).strip()
        df = pd.read_csv(StringIO(bruto), sep=None, engine="python", header=None, dtype=str, keep_default_na=False)
        nombres_cols = ["cuil", "apellido", "nombres", "legajo", "titulo", "titulo_posgrado", "email", "telefono",
                        "ref_legajo_fisico", "estado", "observaciones"]
        df = df.iloc[:, :len(nombres_cols)]
        df.columns = nombres_cols[:len(df.columns)]

    df = normalizar_columnas_docentes_pegados(df)

    for col in df.columns:
        df[col] = df[col].apply(limpiar_texto_tabla)

    df["cuil"] = df["cuil"].apply(limpiar_cuil)

    for idx, row in df.iterrows():
        if not row["apellido"] and not row["nombres"] and row["docente"]:
            apellido, nombres = separar_docente_en_apellido_nombres(row["docente"])
            df.at[idx, "apellido"] = apellido
            df.at[idx, "nombres"] = nombres

    df["estado"] = df["estado"].replace("", "Activo")
    df = df[df["cuil"].astype(str).str.strip() != ""].copy()
    return df.reset_index(drop=True)


def filas_pegadas(texto) -> list[dict]:
    """Filas del parser certificado como dicts de texto (orden de la tabla pegada)."""
    df = parsear_docentes_pegados(texto)
    if df.empty:
        return []
    return [{col: str(row[col]) for col in COLUMNAS} for _, row in df.iterrows()]


def generar_excel_modelo_carga_rapida_docentes(filas_modelo=1000):
    """Excel modelo para completar y pegar en Carga rapida de docentes (entry l. 16773, sin cambios)."""
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import quote_sheetname
    from openpyxl.workbook.defined_name import DefinedName
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.table import Table, TableStyleInfo

    filas_modelo = max(20, int(filas_modelo or 1000))
    wb = Workbook()
    ws = wb.active
    ws.title = "Carga rápida"
    ws_instrucciones = wb.create_sheet("Instrucciones")
    ws_listas = wb.create_sheet("Listas")

    relleno_encabezado = PatternFill("solid", fgColor="1F4E78")
    relleno_entrada = PatternFill("solid", fgColor="FFF2CC")
    fuente_encabezado = Font(color="FFFFFF", bold=True)
    borde_fino = Border(
        left=Side(style="thin", color="D9E1F2"),
        right=Side(style="thin", color="D9E1F2"),
        top=Side(style="thin", color="D9E1F2"),
        bottom=Side(style="thin", color="D9E1F2"),
    )

    encabezados = [
        "CUIL", "Apellido", "Nombres", "Legajo", "Título", "Título posgrado",
        "Email", "Teléfono", "Ref. legajo físico", "Estado", "Observaciones",
    ]
    for col_idx, encabezado in enumerate(encabezados, start=1):
        celda = ws.cell(row=1, column=col_idx, value=encabezado)
        celda.fill = relleno_encabezado
        celda.font = fuente_encabezado
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        celda.border = borde_fino
    ws.row_dimensions[1].height = 34
    ws.freeze_panes = "A2"

    anchos = {
        "A": 18, "B": 24, "C": 28, "D": 15, "E": 36, "F": 36,
        "G": 32, "H": 18, "I": 24, "J": 16, "K": 40,
    }
    for letra, ancho in anchos.items():
        ws.column_dimensions[letra].width = ancho

    fila_fin = filas_modelo + 1
    for fila in range(2, fila_fin + 1):
        for col in range(1, len(encabezados) + 1):
            celda = ws.cell(row=fila, column=col)
            celda.fill = relleno_entrada
            celda.border = borde_fino
            celda.alignment = Alignment(vertical="center", wrap_text=True)
        for col in [1, 4, 8, 9]:
            ws.cell(row=fila, column=col).number_format = "@"

    estados = list(ESTADOS_DOCENTE)
    ws_listas["A1"] = "Estados docentes"
    ws_listas["A1"].font = Font(bold=True)
    for idx, valor in enumerate(estados, start=2):
        ws_listas.cell(row=idx, column=1, value=valor)
    referencia_estados = f"{quote_sheetname('Listas')}!$A$2:$A${max(2, len(estados) + 1)}"
    wb.defined_names.add(DefinedName("ListaEstadosDocentes", attr_text=referencia_estados))

    dv_estado = DataValidation(type="list", formula1="=ListaEstadosDocentes", allow_blank=True)
    dv_estado.error = "Seleccioná un estado válido."
    dv_estado.errorTitle = "Estado no válido"
    dv_estado.prompt = "Elegí el estado administrativo del docente."
    dv_estado.promptTitle = "Estado"
    dv_estado.showErrorMessage = True
    dv_estado.showInputMessage = True
    ws.add_data_validation(dv_estado)
    dv_estado.add(f"J2:J{fila_fin}")

    tabla = Table(displayName="TablaCargaRapidaDocentes", ref=f"A1:K{fila_fin}")
    tabla.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False
    )
    ws.add_table(tabla)

    ws["A1"].comment = Comment(
        "Dato obligatorio. Se recomienda escribir el CUIL sin puntos y conservar los guiones.",
        "Sistema",
    )
    ws["B1"].comment = Comment(
        "Completá Apellido y Nombres en columnas separadas.", "Sistema"
    )
    ws["J1"].comment = Comment(
        "Si queda vacío, la carga rápida lo toma como Activo.", "Sistema"
    )

    instrucciones = [
        "MODELO DE CARGA RÁPIDA DE DOCENTES",
        "1. Completá una fila por docente en la hoja Carga rápida.",
        "2. El CUIL es obligatorio y se usa para detectar docentes ya existentes.",
        "3. Para cargar, copiá desde la fila de encabezados hasta la última fila utilizada y pegalo en la aplicación.",
        "4. El estado puede elegirse desde la lista desplegable. Si queda vacío, se tomará Activo.",
        "5. No cambies los nombres de las columnas.",
    ]
    for fila, texto_instruccion in enumerate(instrucciones, start=1):
        ws_instrucciones.cell(row=fila, column=1, value=texto_instruccion)
    ws_instrucciones["A1"].font = Font(bold=True, size=14)
    ws_instrucciones.column_dimensions["A"].width = 110
    for fila in range(1, len(instrucciones) + 1):
        ws_instrucciones.cell(row=fila, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    ws_instrucciones.sheet_view.showGridLines = False
    ws_listas.sheet_state = "hidden"

    try:
        ws.sheet_view.selection[0].activeCell = "A2"
        ws.sheet_view.selection[0].sqref = "A2"
    except Exception:
        pass

    salida = BytesIO()
    wb.save(salida)
    salida.seek(0)
    return salida.getvalue()
