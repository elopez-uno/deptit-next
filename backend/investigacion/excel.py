"""Excel integral de Investigacion (decision D7): modelo v127 + hoja "Asignar docentes" v217 y su lectura.

Origen: ``_generar_excel_modelo_proyectos_no_cache_v127`` l. 23369, ``_generar_excel_proyectos_integral_cache_v217``
l. 48874, ``leer_excel_carga_rapida_proyectos_v127`` l. 23564, ``leer_asignaciones_proyectos_excel_v217`` l. 49009.
El codigo openpyxl es el del certificado; los datos llegan ya leidos (catalogo v199, padron v276 y asignaciones locales
del periodo con v183 + v277), asi que el libro es byte a byte el del certificado salvo ``docProps/core.xml`` (fechas de
creacion/modificacion que openpyxl toma del reloj).
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd

from . import rules as IR

NOMBRE_MODELO = "modelo_carga_rapida_proyectos_y_docentes_investigacion.xlsx"


def modelo_v127(df: pd.DataFrame, filas_modelo: int = 150) -> bytes:
    """``_generar_excel_modelo_proyectos_no_cache_v127`` (tipo investigacion)."""
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.workbook.defined_name import DefinedName
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.table import Table, TableStyleInfo

    lim = IR.limpiar_texto_tabla
    df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    encabezados = ["ID proyecto", "Nombre del proyecto", "Código interno del proyecto",
                   "Instituto/Departamento del proyecto", "Año de llamado", "Fecha de inicio", "Fecha de finalización",
                   "Estado administrativo", "Observaciones"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Carga rápida"
    ws_instr = wb.create_sheet("Instrucciones")
    ws_listas = wb.create_sheet("_Listas")
    azul = PatternFill("solid", fgColor="D9EAF7")
    amarillo = PatternFill("solid", fgColor="FFF2CC")
    encabezado_fill = PatternFill("solid", fgColor="1F4E78")
    encabezado_font = Font(color="FFFFFF", bold=True)
    borde = Border(left=Side(style="thin", color="D9E1F2"), right=Side(style="thin", color="D9E1F2"),
                   top=Side(style="thin", color="D9E1F2"), bottom=Side(style="thin", color="D9E1F2"))
    for j, h in enumerate(encabezados, 1):
        c = ws.cell(row=1, column=j, value=h)
        c.fill = encabezado_fill
        c.font = encabezado_font
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = borde
    existentes = 0
    if not df.empty:
        for _, r in df.iterrows():
            existentes += 1
            fila = existentes + 1
            inicio = IR.fecha_proyecto(r.get("fecha_inicio"))
            fin = IR.fecha_proyecto(r.get("fecha_fin"))
            valores = [
                int(r["id"]) if pd.notna(r.get("id")) else "",
                lim(r.get("nombre_proyecto", "")),
                lim(r.get("codigo_proyecto", "")),
                lim(r.get("instituto_proyecto", "")),
                int(r.get("anio_llamado")) if pd.notna(r.get("anio_llamado")) and str(r.get("anio_llamado")).strip() else "",
                inicio,
                fin,
                lim(r.get("estado", "")) or "Activo",
                lim(r.get("observaciones", "")),
            ]
            for j, v in enumerate(valores, 1):
                c = ws.cell(row=fila, column=j, value=v)
                c.fill = azul
                c.border = borde
                c.alignment = Alignment(wrap_text=True, vertical="top")
            ws.cell(row=fila, column=6).number_format = "DD/MM/YYYY"
            ws.cell(row=fila, column=7).number_format = "DD/MM/YYYY"
    fila_fin = max(existentes + 1 + int(filas_modelo), 20)
    for fila in range(existentes + 2, fila_fin + 1):
        for j in range(1, len(encabezados) + 1):
            c = ws.cell(row=fila, column=j)
            c.fill = amarillo
            c.border = borde
            c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row=fila, column=6).number_format = "DD/MM/YYYY"
        ws.cell(row=fila, column=7).number_format = "DD/MM/YYYY"
    for i, estado in enumerate(IR.ESTADOS_PROYECTO_EXCEL_V127, start=1):
        ws_listas.cell(row=i, column=1, value=estado)
    responsables = []
    if not df.empty and "instituto_proyecto" in df.columns:
        responsables = sorted({lim(x) for x in df["instituto_proyecto"].fillna("").tolist() if lim(x)})
    if not responsables:
        responsables = ["Sin especificar"]
    for i, valor in enumerate(responsables, start=1):
        ws_listas.cell(row=i, column=2, value=valor)
    try:
        wb.defined_names.add(DefinedName("ListaEstadosProyectoV127",
                                         attr_text=f"'_Listas'!$A$1:$A${len(IR.ESTADOS_PROYECTO_EXCEL_V127)}"))
        wb.defined_names.add(DefinedName("ListaResponsablesProyectoV127",
                                         attr_text=f"'_Listas'!$B$1:$B${max(1, len(responsables))}"))
    except Exception:
        pass
    dv_estado = DataValidation(type="list", formula1="=ListaEstadosProyectoV127", allow_blank=True)
    dv_estado.error = "Seleccioná un estado válido."
    dv_estado.errorTitle = "Estado no válido"
    dv_estado.showErrorMessage = True
    ws.add_data_validation(dv_estado)
    dv_estado.add(f"H2:H{fila_fin}")
    dv_resp = DataValidation(type="list", formula1="=ListaResponsablesProyectoV127", allow_blank=True)
    dv_resp.showErrorMessage = False
    dv_resp.showInputMessage = True
    dv_resp.promptTitle = "Responsable"
    dv_resp.prompt = "Dejá vacío si radica en el departamento creador. Completá solo una unidad externa."
    ws.add_data_validation(dv_resp)
    dv_resp.add(f"D2:D{fila_fin}")
    dv_anio = DataValidation(type="whole", operator="between", formula1="1900", formula2="2100", allow_blank=True)
    dv_anio.showErrorMessage = True
    dv_anio.error = "Ingresá un año entre 1900 y 2100."
    ws.add_data_validation(dv_anio)
    dv_anio.add(f"E2:E{fila_fin}")
    tabla = Table(displayName="TablaProyectosInvestigacionV127", ref=f"A1:{get_column_letter(len(encabezados))}{fila_fin}")
    tabla.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False,
                                          showRowStripes=True, showColumnStripes=False)
    ws.add_table(tabla)
    ws.freeze_panes = "A2"
    for i, ancho in enumerate([14, 52, 24, 42, 16, 18, 18, 24, 55], 1):
        ws.column_dimensions[get_column_letter(i)].width = ancho
    ws["A1"].comment = Comment(
        "Las filas azules ya existen. Si volvés a subir el archivo, no se duplican. "
        "Para crear proyectos nuevos, completá filas amarillas dejando este ID vacío.",
        "Sistema",
    )
    instrucciones = [
        "MODELO DE CARGA RÁPIDA DE PROYECTOS DE INVESTIGACIÓN",
        "1. Las filas azules corresponden a proyectos que ya están registrados y se incluyen como referencia.",
        "2. Para crear un proyecto nuevo, completá una fila amarilla y dejá ID proyecto vacío.",
        "3. Nombre, Fecha de inicio y Fecha de finalización son obligatorios. La fecha final no puede ser anterior a la inicial.",
        "4. Estado administrativo tiene lista desplegable. La radicación/responsable puede quedar vacía si el proyecto radica en el departamento que lo crea; completala solo si corresponde a otra unidad institucional.",
        "5. Si el código ya existe, o si sin código coinciden nombre y fechas, la app no crea un duplicado.",
        "6. Las filas con ID existente se omiten en la carga rápida: para editar, suspender, archivar o eliminar un proyecto existente usá las pestañas específicas del módulo.",
        "7. Guardá el archivo .xlsx y subilo completo desde la pestaña Carga rápida.",
    ]
    for i, linea in enumerate(instrucciones, 1):
        c = ws_instr.cell(row=i, column=1, value=linea)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws_instr["A1"].font = Font(bold=True, size=14)
    ws_instr.column_dimensions["A"].width = 125
    ws_listas.sheet_state = "hidden"
    salida = BytesIO()
    wb.save(salida)
    salida.seek(0)
    return salida.getvalue()


def integral_v217(proyectos: pd.DataFrame, docentes: pd.DataFrame, asignaciones: pd.DataFrame,
                  filas_asignacion: int = 180) -> bytes:
    """``_generar_excel_proyectos_integral_cache_v217`` (tipo investigacion) sobre el modelo v127."""
    from openpyxl import load_workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.workbook.defined_name import DefinedName
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.table import Table, TableStyleInfo

    _ = Font
    lim = IR.limpiar_texto_tabla
    base_bytes = modelo_v127(proyectos)
    wb = load_workbook(BytesIO(base_bytes))
    if "Asignar docentes" in wb.sheetnames:
        del wb["Asignar docentes"]
    ws = wb.create_sheet("Asignar docentes", 1)
    listas = wb["_Listas"] if "_Listas" in wb.sheetnames else wb.create_sheet("_Listas")
    labels_proy = []
    if isinstance(proyectos, pd.DataFrame) and not proyectos.empty:
        labels_proy = list(dict.fromkeys([IR.etiqueta_proyecto_excel_v217(r) for _, r in proyectos.iterrows()
                                          if IR.etiqueta_proyecto_excel_v217(r)]))
    labels_doc = []
    if isinstance(docentes, pd.DataFrame) and not docentes.empty:
        labels_doc = list(dict.fromkeys([IR.etiqueta_docente_excel_v217(r) for _, r in docentes.iterrows()
                                         if IR.etiqueta_docente_excel_v217(r)]))
    for col in range(4, 8):
        for row in range(1, max(len(labels_proy), len(labels_doc), 8) + 3):
            listas.cell(row=row, column=col).value = None
    for i, val in enumerate(labels_proy or ["Sin proyectos registrados"], 1):
        listas.cell(row=i, column=4, value=val)
    for i, val in enumerate(labels_doc or ["Sin docentes disponibles"], 1):
        listas.cell(row=i, column=5, value=val)
    for i, val in enumerate(IR.ROLES_EXCEL_V217, 1):
        listas.cell(row=i, column=6, value=val)
    nom_proy, nom_doc, nom_rol = "ListaProyectosInvV217", "ListaDocentesInvV217", "ListaRolesInvV217"
    try:
        for n in [nom_proy, nom_doc, nom_rol]:
            try:
                del wb.defined_names[n]
            except Exception:
                pass
        wb.defined_names.add(DefinedName(nom_proy, attr_text=f"'_Listas'!$D$1:$D${max(1,len(labels_proy))}"))
        wb.defined_names.add(DefinedName(nom_doc, attr_text=f"'_Listas'!$E$1:$E${max(1,len(labels_doc))}"))
        wb.defined_names.add(DefinedName(nom_rol, attr_text=f"'_Listas'!$F$1:$F${len(IR.ROLES_EXCEL_V217)}"))
    except Exception:
        pass
    encabezados = ["ID asignación", "Proyecto", "Docente (Nombre | CUIL)", "Rol", "Horas semanales", "Observaciones"]
    encabezado_fill = PatternFill("solid", fgColor="1F4E78")
    azul = PatternFill("solid", fgColor="D9EAF7")
    amarillo = PatternFill("solid", fgColor="FFF2CC")
    encabezado_font = Font(color="FFFFFF", bold=True)
    borde = Border(left=Side(style="thin", color="D9E1F2"), right=Side(style="thin", color="D9E1F2"),
                   top=Side(style="thin", color="D9E1F2"), bottom=Side(style="thin", color="D9E1F2"))
    for j, h in enumerate(encabezados, 1):
        c = ws.cell(row=1, column=j, value=h)
        c.fill = encabezado_fill; c.font = encabezado_font; c.border = borde
        c.alignment = Alignment(wrap_text=True, vertical="center")
    existentes = 0
    if isinstance(asignaciones, pd.DataFrame) and not asignaciones.empty:
        for _, r in asignaciones.iterrows():
            existentes += 1
            fila = existentes + 1
            valores = [
                int(r.get("id")) if pd.notna(r.get("id")) else "",
                IR.etiqueta_proyecto_excel_v217(r),
                IR.etiqueta_docente_excel_v217(r),
                lim(r.get("rol", "")),
                float(r.get("horas_asignadas") or 0),
                lim(r.get("observaciones", "")),
            ]
            for j, v in enumerate(valores, 1):
                c = ws.cell(row=fila, column=j, value=v)
                c.fill = azul; c.border = borde; c.alignment = Alignment(wrap_text=True, vertical="top")
    fila_fin = max(existentes + 1 + int(filas_asignacion), 30)
    for fila in range(existentes + 2, fila_fin + 1):
        for j in range(1, len(encabezados) + 1):
            c = ws.cell(row=fila, column=j)
            c.fill = amarillo; c.border = borde; c.alignment = Alignment(wrap_text=True, vertical="top")
    dv_p = DataValidation(type="list", formula1=f"={nom_proy}", allow_blank=True)
    dv_p.showErrorMessage = False
    dv_p.promptTitle = "Proyecto"
    dv_p.prompt = "Elegí un proyecto existente. Si lo creás en este mismo archivo, podés escribir manualmente [CÓDIGO] Nombre o el nombre exacto."
    ws.add_data_validation(dv_p); dv_p.add(f"B2:B{fila_fin}")
    dv_d = DataValidation(type="list", formula1=f"={nom_doc}", allow_blank=True)
    dv_d.showErrorMessage = False
    dv_d.promptTitle = "Docente"
    dv_d.prompt = "Elegí un docente activo disponible para el período."
    ws.add_data_validation(dv_d); dv_d.add(f"C2:C{fila_fin}")
    dv_r = DataValidation(type="list", formula1=f"={nom_rol}", allow_blank=True)
    dv_r.showErrorMessage = False
    ws.add_data_validation(dv_r); dv_r.add(f"D2:D{fila_fin}")
    dv_h = DataValidation(type="decimal", operator="between", formula1="0", formula2="100", allow_blank=True)
    dv_h.showErrorMessage = True; dv_h.error = "Ingresá una cantidad de horas entre 0 y 100."
    ws.add_data_validation(dv_h); dv_h.add(f"E2:E{fila_fin}")
    ws.freeze_panes = "A2"
    for i, ancho in enumerate([15, 58, 46, 24, 18, 52], 1):
        ws.column_dimensions[get_column_letter(i)].width = ancho
    ws["A1"].comment = Comment(
        "Las filas azules son asignaciones ya registradas y se omiten al importar. "
        "Para agregar docentes, usá filas amarillas y dejá ID asignación vacío.", "Sistema"
    )
    tabla = Table(displayName="TablaAsignacionesProyectosInvV217", ref=f"A1:F{fila_fin}")
    tabla.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False,
                                          showRowStripes=True, showColumnStripes=False)
    ws.add_table(tabla)
    if "Instrucciones" in wb.sheetnames:
        wi = wb["Instrucciones"]
        fila = wi.max_row + 2
        instrucciones = [
            "ASIGNACIÓN RÁPIDA DE DOCENTES A PROYECTOS",
            "8. La hoja 'Asignar docentes' permite cargar docentes del período directamente a proyectos de este módulo.",
            "9. Las filas azules son asignaciones existentes y se usan solo como referencia; no se vuelven a cargar.",
            "10. Para una asignación nueva, completá una fila amarilla con Proyecto, Docente, Rol y Horas semanales. Observaciones es opcional.",
            "11. Podés asignar varios docentes al mismo proyecto usando una fila por docente.",
            "12. Si también creás un proyecto nuevo en la hoja 'Carga rápida', podés referenciarlo en 'Asignar docentes' escribiendo [CÓDIGO] Nombre o su nombre exacto; primero se crea el proyecto y luego se procesan las asignaciones.",
            "13. No se permite duplicar al mismo docente en el mismo proyecto y cuatrimestre, aunque la carga se intente desde otro departamento.",
        ]
        for linea in instrucciones:
            wi.cell(row=fila, column=1, value=linea).alignment = Alignment(wrap_text=True, vertical="top")
            fila += 1
    listas.sheet_state = "hidden"
    salida = BytesIO(); wb.save(salida); salida.seek(0)
    return salida.getvalue()


def leer_carga_rapida_v127(contenido: bytes) -> pd.DataFrame:
    """``leer_excel_carga_rapida_proyectos_v127`` (l. 23564)."""
    if not contenido:
        return pd.DataFrame()
    try:
        df = pd.read_excel(BytesIO(contenido), sheet_name="Carga rápida", engine="openpyxl")
    except ValueError:
        df = pd.read_excel(BytesIO(contenido), sheet_name=0, engine="openpyxl")
    if df is None or df.empty:
        return pd.DataFrame()
    renombres = {}
    for col in df.columns:
        k = IR.normalizar_encabezado_v127(col)
        if k in ["id_proyecto", "id"]:
            renombres[col] = "id"
        elif k in ["nombre_del_proyecto", "nombre_proyecto", "proyecto", "nombre"]:
            renombres[col] = "nombre_proyecto"
        elif k in ["codigo_interno_del_proyecto", "codigo_proyecto", "codigo"]:
            renombres[col] = "codigo_proyecto"
        elif k in ["instituto_departamento_del_proyecto", "instituto_departamento",
                   "area_secretaria_responsable_del_proyecto", "area_secretaria_responsable",
                   "instituto_proyecto", "responsable"]:
            renombres[col] = "instituto_proyecto"
        elif k in ["anio_de_llamado", "anio_llamado", "anio", "ano_de_llamado", "ano_llamado", "ano"]:
            renombres[col] = "anio_llamado"
        elif k in ["fecha_de_inicio", "fecha_inicio", "inicio"]:
            renombres[col] = "fecha_inicio"
        elif k in ["fecha_de_finalizacion", "fecha_finalizacion", "fecha_fin", "fin"]:
            renombres[col] = "fecha_fin"
        elif k in ["estado_administrativo", "estado"]:
            renombres[col] = "estado"
        elif k in ["observaciones", "observacion"]:
            renombres[col] = "observaciones"
    df = df.rename(columns=renombres)
    if "nombre_proyecto" not in df.columns:
        raise ValueError("El Excel no contiene la columna 'Nombre del proyecto'.")
    for col in ["id", "codigo_proyecto", "instituto_proyecto", "anio_llamado", "fecha_inicio", "fecha_fin", "estado",
                "observaciones"]:
        if col not in df.columns:
            df[col] = ""
    columnas = ["id", "nombre_proyecto", "codigo_proyecto", "instituto_proyecto", "anio_llamado", "fecha_inicio",
                "fecha_fin", "estado", "observaciones"]
    df = df[columnas].copy()

    def _fila_con_datos(r):
        for v in r.tolist():
            if pd.notna(v) and str(v).strip():
                return True
        return False
    df = df[df.apply(_fila_con_datos, axis=1)].reset_index(drop=True)
    return df


def leer_asignaciones_v217(contenido: bytes) -> pd.DataFrame:
    """``leer_asignaciones_proyectos_excel_v217`` (l. 49009)."""
    vacio = pd.DataFrame(columns=["id", "proyecto", "docente", "rol", "horas", "observaciones"])
    if not contenido:
        return vacio
    try:
        df = pd.read_excel(BytesIO(contenido), sheet_name="Asignar docentes", engine="openpyxl")
    except Exception:
        return vacio
    if df is None or df.empty:
        return vacio
    ren = {}
    for c in df.columns:
        k = IR.normalizar_encabezado_v127(c)
        if k in {"id_asignacion", "id"}: ren[c] = "id"
        elif k in {"proyecto", "nombre_proyecto", "proyecto_codigo_nombre"}: ren[c] = "proyecto"
        elif k in {"docente_nombre_cuil", "docente", "nombre_cuil"}: ren[c] = "docente"
        elif k in {"rol", "rol_docente"}: ren[c] = "rol"
        elif k in {"horas_semanales", "horas", "horas_asignadas"}: ren[c] = "horas"
        elif k in {"observaciones", "observacion"}: ren[c] = "observaciones"
    df = df.rename(columns=ren)
    for c in ["id", "proyecto", "docente", "rol", "horas", "observaciones"]:
        if c not in df.columns: df[c] = ""
    df = df[["id", "proyecto", "docente", "rol", "horas", "observaciones"]].copy()

    def con_datos(r):
        return any(pd.notna(v) and str(v).strip() and str(v).strip().lower() not in {"nan", "none"} for v in r.tolist())
    return df[df.apply(con_datos, axis=1)].reset_index(drop=True)


def filas_nuevas(df: pd.DataFrame) -> pd.DataFrame:
    """Filas sin ID (render v217 l. 49240-49247): las totalmente vacias no cuentan como proyectos nuevos."""
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    nuevas = df[df["id"].apply(IR.parse_id_excel_v127).isna()].copy()
    if nuevas.empty:
        return nuevas
    return nuevas[nuevas.apply(lambda r: any(pd.notna(v) and str(v).strip() and str(v).strip().lower()
                                             not in {"nan", "none"} for v in r.tolist()), axis=1)].copy()
