"""Modelo Excel de carga rapida de designaciones, copiado de la fuente certificada B13-FIX02.

Origen (reference_fix02, entry): ``generar_excel_modelo_carga_rapida_designaciones`` l. 16894 (base), redefinida en
l. 45867 (v230: Periodo y Estado automaticos, hoja Periodos ordenada) y l. 45938 (v199: solo cache).
``_ordenar_hoja_periodos_excel_v230`` l. 45825, ``_quitar_validaciones_formula_v230`` l. 45857,
``_formula_periodo_excel_v230`` (``domain/periodos.py``).  Mismas versiones de pandas/openpyxl que el runtime
certificado.  Las entradas son las lecturas certificadas ``get_docentes`` y ``get_periodos`` del departamento.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd

from .rules import CARGOS, DEDICACIONES, ESTADOS_DESIGNACION, HORAS_OPCIONES, TIPOS_DESIGNACION
from .rules import formula_periodo_excel_v230, safe_date


def _generar_base(docentes: list[dict], periodos: list[dict], periodo_default=None, filas_modelo=5000) -> bytes:
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import quote_sheetname
    from openpyxl.workbook.defined_name import DefinedName
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.table import Table, TableStyleInfo

    filas_modelo = max(20, int(filas_modelo or 5000))

    df_docentes_modelo = pd.DataFrame(docentes)
    for col in ["cuil", "nombre_completo", "legajo", "estado", "tipo_docente"]:
        if col not in df_docentes_modelo.columns:
            df_docentes_modelo[col] = ""
    if not df_docentes_modelo.empty:
        for col in ["cuil", "nombre_completo", "legajo", "estado", "tipo_docente"]:
            df_docentes_modelo[col] = df_docentes_modelo[col].fillna("").astype(str).str.strip()
        df_docentes_modelo = (
            df_docentes_modelo[df_docentes_modelo["cuil"] != ""]
            .drop_duplicates(subset=["cuil"], keep="first")
            .sort_values(["nombre_completo", "cuil"], kind="stable")
            .reset_index(drop=True)
        )

    df_periodos_modelo = pd.DataFrame(periodos)
    for col in ["nombre", "fecha_inicio", "fecha_fin", "estado"]:
        if col not in df_periodos_modelo.columns:
            df_periodos_modelo[col] = ""
    if not df_periodos_modelo.empty:
        for col in ["nombre", "fecha_inicio", "fecha_fin", "estado"]:
            df_periodos_modelo[col] = df_periodos_modelo[col].fillna("").astype(str).str.strip()
        df_periodos_modelo = (
            df_periodos_modelo[df_periodos_modelo["nombre"] != ""]
            .drop_duplicates(subset=["nombre"], keep="first")
            .reset_index(drop=True)
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Carga rápida"
    ws_docentes = wb.create_sheet("Docentes")
    ws_periodos = wb.create_sheet("Períodos")
    ws_instrucciones = wb.create_sheet("Instrucciones")
    ws_listas = wb.create_sheet("Listas")

    relleno_encabezado = PatternFill("solid", fgColor="1F4E78")
    relleno_entrada = PatternFill("solid", fgColor="FFF2CC")
    relleno_formula = PatternFill("solid", fgColor="D9EAF7")
    fuente_encabezado = Font(color="FFFFFF", bold=True)
    borde_fino = Border(
        left=Side(style="thin", color="D9E1F2"),
        right=Side(style="thin", color="D9E1F2"),
        top=Side(style="thin", color="D9E1F2"),
        bottom=Side(style="thin", color="D9E1F2"),
    )

    encabezados = [
        "Período", "Docente", "CUIL", "Cargo", "Dedicación", "Horas",
        "Tipo designación", "N° resolución", "Ad honorem", "Fecha desde", "Fecha hasta",
        "Estado", "Observaciones",
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
        "A": 16, "B": 36, "C": 18, "D": 18, "E": 22, "F": 12,
        "G": 20, "H": 20, "I": 16, "J": 16, "K": 16, "L": 16, "M": 42,
    }
    for letra, ancho in anchos.items():
        ws.column_dimensions[letra].width = ancho

    encabezados_doc = ["Docente", "CUIL", "Legajo", "Estado", "Tipo de docente"]
    for col_idx, encabezado in enumerate(encabezados_doc, start=1):
        c = ws_docentes.cell(row=1, column=col_idx, value=encabezado)
        c.fill = relleno_encabezado
        c.font = fuente_encabezado
        c.border = borde_fino
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for fila_idx, (_, fila_doc) in enumerate(df_docentes_modelo.iterrows(), start=2):
        valores = [
            fila_doc.get("nombre_completo", ""), fila_doc.get("cuil", ""),
            fila_doc.get("legajo", ""), fila_doc.get("estado", ""),
            fila_doc.get("tipo_docente", ""),
        ]
        for col_idx, valor in enumerate(valores, start=1):
            c = ws_docentes.cell(row=fila_idx, column=col_idx, value=valor)
            c.border = borde_fino
            c.alignment = Alignment(vertical="top", wrap_text=True)
        ws_docentes.cell(row=fila_idx, column=2).number_format = "@"
    ws_docentes.freeze_panes = "A2"
    for letra, ancho in {"A": 38, "B": 18, "C": 14, "D": 18, "E": 18}.items():
        ws_docentes.column_dimensions[letra].width = ancho
    if len(df_docentes_modelo) > 0:
        tabla_doc = Table(displayName="TablaDocentesDesignaciones", ref=f"A1:E{len(df_docentes_modelo) + 1}")
        tabla_doc.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
        ws_docentes.add_table(tabla_doc)

    encabezados_per = ["Período", "Fecha inicio", "Fecha fin", "Estado"]
    for col_idx, encabezado in enumerate(encabezados_per, start=1):
        c = ws_periodos.cell(row=1, column=col_idx, value=encabezado)
        c.fill = relleno_encabezado
        c.font = fuente_encabezado
        c.border = borde_fino
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for fila_idx, (_, fila_per) in enumerate(df_periodos_modelo.iterrows(), start=2):
        valores = [
            fila_per.get("nombre", ""), fila_per.get("fecha_inicio", ""),
            fila_per.get("fecha_fin", ""), fila_per.get("estado", ""),
        ]
        for col_idx, valor in enumerate(valores, start=1):
            c = ws_periodos.cell(row=fila_idx, column=col_idx, value=valor)
            c.border = borde_fino
            c.alignment = Alignment(vertical="top", wrap_text=True)
    ws_periodos.freeze_panes = "A2"
    for letra, ancho in {"A": 18, "B": 18, "C": 18, "D": 16}.items():
        ws_periodos.column_dimensions[letra].width = ancho
    if len(df_periodos_modelo) > 0:
        tabla_per = Table(displayName="TablaPeriodosDesignaciones", ref=f"A1:D{len(df_periodos_modelo) + 1}")
        tabla_per.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
        ws_periodos.add_table(tabla_per)

    listas = {
        "A": ("Cargos", list(CARGOS)),
        "B": ("Dedicaciones", list(DEDICACIONES)),
        "C": ("Horas", [str(v) for v in HORAS_OPCIONES]),
        "D": ("Tipos", list(TIPOS_DESIGNACION)),
        "E": ("Ad honorem", ["Sí", "No"]),
        "F": ("Estados", list(ESTADOS_DESIGNACION)),
    }
    for letra, (titulo, valores) in listas.items():
        ws_listas[f"{letra}1"] = titulo
        ws_listas[f"{letra}1"].font = Font(bold=True)
        for idx, valor in enumerate(valores, start=2):
            ws_listas[f"{letra}{idx}"] = valor

    def agregar_nombre(nombre, hoja, columna, fila_inicio, fila_fin):
        referencia = f"{quote_sheetname(hoja)}!${columna}${fila_inicio}:${columna}${max(fila_inicio, fila_fin)}"
        wb.defined_names.add(DefinedName(nombre, attr_text=referencia))

    agregar_nombre("ListaDocentesDesignaciones", "Docentes", "A", 2, 1 + max(1, len(df_docentes_modelo)))
    agregar_nombre("ListaPeriodosDesignaciones", "Períodos", "A", 2, 1 + max(1, len(df_periodos_modelo)))
    agregar_nombre("ListaCargosDesignaciones", "Listas", "A", 2, 1 + len(listas["A"][1]))
    agregar_nombre("ListaDedicacionesDesignaciones", "Listas", "B", 2, 1 + len(listas["B"][1]))
    agregar_nombre("ListaHorasDesignaciones", "Listas", "C", 2, 1 + len(listas["C"][1]))
    agregar_nombre("ListaTiposDesignaciones", "Listas", "D", 2, 1 + len(listas["D"][1]))
    agregar_nombre("ListaAdHonoremDesignaciones", "Listas", "E", 2, 1 + len(listas["E"][1]))
    agregar_nombre("ListaEstadosDesignaciones", "Listas", "F", 2, 1 + len(listas["F"][1]))

    fila_fin = filas_modelo + 1
    periodo_nombre_default = str((periodo_default or {}).get("nombre") or "").strip()
    ultima_fila_docentes = max(2, len(df_docentes_modelo) + 1)
    for fila in range(2, fila_fin + 1):
        if periodo_nombre_default:
            ws.cell(row=fila, column=1, value=periodo_nombre_default)
        ws.cell(
            row=fila,
            column=3,
            value=(
                f'=IF(B{fila}="","",IFERROR(INDEX(Docentes!$B$2:$B${ultima_fila_docentes},'
                f'MATCH(B{fila},Docentes!$A$2:$A${ultima_fila_docentes},0)),""))'
            ),
        )
        ws.cell(
            row=fila,
            column=6,
            value=(
                f'=IF(E{fila}="","",IF(E{fila}="Simple",10,IF(E{fila}="Parcial",20,'
                f'IF(E{fila}="Parcial + Simple",30,IF(E{fila}="Exclusiva",40,'
                f'IF(E{fila}="Exclusiva + Simple",50,""))))))'
            ),
        )
        for col in range(1, len(encabezados) + 1):
            celda = ws.cell(row=fila, column=col)
            celda.fill = relleno_formula if col in [3, 6] else relleno_entrada
            celda.border = borde_fino
            celda.alignment = Alignment(vertical="center", wrap_text=True)
        ws.cell(row=fila, column=3).number_format = "@"
        ws.cell(row=fila, column=6).number_format = "0"
        ws.cell(row=fila, column=10).number_format = "dd/mm/yyyy"
        ws.cell(row=fila, column=11).number_format = "dd/mm/yyyy"

    validaciones = [
        ("=ListaPeriodosDesignaciones", f"A2:A{fila_fin}", "Período", "Elegí un período existente."),
        ("=ListaDocentesDesignaciones", f"B2:B{fila_fin}", "Docente", "Elegí un docente de la base maestra del departamento."),
        ("=ListaCargosDesignaciones", f"D2:D{fila_fin}", "Cargo", "Elegí un cargo válido."),
        ("=ListaDedicacionesDesignaciones", f"E2:E{fila_fin}", "Dedicación", "Elegí una dedicación válida."),
        ("=ListaTiposDesignaciones", f"G2:G{fila_fin}", "Tipo", "Elegí el tipo de designación."),
        ("=ListaAdHonoremDesignaciones", f"I2:I{fila_fin}", "Ad honorem", "Indicá Sí o No."),
        ("=ListaEstadosDesignaciones", f"L2:L{fila_fin}", "Estado", "Elegí el estado de la designación."),
    ]
    for formula, rango, titulo, mensaje in validaciones:
        dv = DataValidation(type="list", formula1=formula, allow_blank=True)
        dv.error = "El valor no pertenece a la lista disponible."
        dv.errorTitle = "Valor no válido"
        dv.prompt = mensaje
        dv.promptTitle = titulo
        dv.showErrorMessage = True
        dv.showInputMessage = True
        ws.add_data_validation(dv)
        dv.add(rango)

    tabla = Table(displayName="TablaCargaRapidaDesignaciones", ref=f"A1:M{fila_fin}")
    tabla.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
    ws.add_table(tabla)

    ws["B1"].comment = Comment(
        "Seleccioná el docente. El CUIL se completa automáticamente en la columna siguiente.", "Sistema"
    )
    ws["C1"].comment = Comment(
        "Se completa automáticamente al seleccionar el docente. También puede escribirse manualmente.", "Sistema"
    )
    ws["F1"].comment = Comment(
        "Se calcula automáticamente desde Dedicación: Simple=10, Parcial=20, Parcial + Simple=30, Exclusiva=40, Exclusiva + Simple=50.", "Sistema"
    )
    ws["H1"].comment = Comment(
        "Número de la resolución correspondiente a ESTA designación. Se usa como fuente para las disposiciones.", "Sistema"
    )
    ws["J1"].comment = Comment(
        "Para designaciones concursadas, ingresá la fecha real de inicio del concurso.", "Sistema"
    )
    ws["K1"].comment = Comment(
        "Para designaciones concursadas, ingresá la fecha real de finalización del concurso.", "Sistema"
    )

    instrucciones = [
        "MODELO DE CARGA RÁPIDA DE DESIGNACIONES",
        "1. Completá una fila por designación en la hoja Carga rápida.",
        "2. Seleccioná el docente: el CUIL se completa automáticamente.",
        "3. Completá Fecha desde y Fecha hasta: el Período se calcula automáticamente y no se carga manualmente.",
        "4. Elegí la Dedicación. La columna Horas se completa automáticamente (10/20/30/40/50 según dedicación) y no se carga manualmente.",
        "5. Cargá el N° de resolución propio de cada designación. Ese dato será usado por las disposiciones.",
        "6. Para designaciones concursadas, cargá siempre las fechas reales de inicio y fin del concurso.",
        "7. Para cargar, copiá desde la fila de encabezados hasta la última fila utilizada y pegalo en la aplicación.",
        "8. No cambies los nombres de las columnas. La columna Docente sirve como ayuda y el sistema procesa el CUIL.",
    ]
    for fila, texto_instruccion in enumerate(instrucciones, start=1):
        ws_instrucciones.cell(row=fila, column=1, value=texto_instruccion)
    ws_instrucciones["A1"].font = Font(bold=True, size=14)
    ws_instrucciones.column_dimensions["A"].width = 115
    for fila in range(1, len(instrucciones) + 1):
        ws_instrucciones.cell(row=fila, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    ws_instrucciones.sheet_view.showGridLines = False
    ws_listas.sheet_state = "hidden"

    try:
        wb.calculation.calcMode = "auto"
        wb.calculation.fullCalcOnLoad = True
        wb.calculation.forceFullCalc = True
    except Exception:
        pass
    try:
        ws.sheet_view.selection[0].activeCell = "B2"
        ws.sheet_view.selection[0].sqref = "B2"
    except Exception:
        pass

    salida = BytesIO()
    wb.save(salida)
    salida.seek(0)
    return salida.getvalue()


def _ordenar_hoja_periodos_excel_v230(ws):
    filas = []
    for r in range(2, ws.max_row + 1):
        nombre = ws.cell(r, 1).value
        if nombre is None or str(nombre).strip() == "":
            continue
        ini = safe_date(ws.cell(r, 2).value, None)
        fin = safe_date(ws.cell(r, 3).value, None)
        estado = ws.cell(r, 4).value
        if ini is None or fin is None:
            continue
        filas.append((ini, fin, str(nombre), estado))
    filas.sort(key=lambda x: (x[0], x[1], x[2]))
    for r in range(2, ws.max_row + 1):
        for c in range(1, 5):
            ws.cell(r, c).value = None
    for r, (ini, fin, nombre, estado) in enumerate(filas, start=2):
        ws.cell(r, 1).value = nombre
        ws.cell(r, 2).value = ini
        ws.cell(r, 3).value = fin
        ws.cell(r, 4).value = estado
        ws.cell(r, 2).number_format = "dd/mm/yyyy"
        ws.cell(r, 3).number_format = "dd/mm/yyyy"
    return filas


def _quitar_validaciones_formula_v230(ws, formulas):
    try:
        existentes = list(ws.data_validations.dataValidation)
        ws.data_validations.dataValidation = [
            dv for dv in existentes if str(getattr(dv, "formula1", "") or "") not in set(formulas)
        ]
    except Exception:
        pass


def generar_excel_modelo_carga_rapida_designaciones(docentes: list[dict], periodos: list[dict], periodo_default=None,
                                                    filas_modelo=5000) -> bytes:
    """v230 sobre la base: Período y Estado son fórmulas automáticas."""
    from openpyxl import load_workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import PatternFill

    data = _generar_base(docentes, periodos, periodo_default=periodo_default, filas_modelo=filas_modelo)
    wb = load_workbook(BytesIO(data))
    ws = wb["Carga rápida"]
    wsp = wb["Períodos"]
    filas_per = _ordenar_hoja_periodos_excel_v230(wsp)
    ult_fila_per = 1 + len(filas_per)
    ultimo_nombre = filas_per[-1][2] if filas_per else ""
    relleno_formula = PatternFill("solid", fgColor="D9EAF7")
    for fila in range(2, ws.max_row + 1):
        ws.cell(fila, 1).value = formula_periodo_excel_v230(fila, "J", "K", ult_fila_per)
        ws.cell(fila, 12).value = (
            f'=IF(A{fila}="","",IF(A{fila}="{str(ultimo_nombre).replace(chr(34), chr(34)*2)}","Activa","Finalizada"))'
            if ultimo_nombre else '=""'
        )
        ws.cell(fila, 1).fill = relleno_formula
        ws.cell(fila, 3).fill = relleno_formula
        ws.cell(fila, 6).fill = relleno_formula
        ws.cell(fila, 12).fill = relleno_formula
    _quitar_validaciones_formula_v230(ws, {"=ListaPeriodosDesignaciones", "=ListaEstadosDesignaciones"})
    ws["A1"].comment = Comment("Automático: se detecta desde Fecha desde / Fecha hasta. Si la vigencia abarca varios períodos, toma el último período registrado que se superpone.", "Sistema")
    ws["L1"].comment = Comment("Automático: Activa si el período detectado es el último período cronológico del departamento; Finalizada si es histórico.", "Sistema")
    wsi = wb["Instrucciones"]
    r = wsi.max_row + 1
    wsi.cell(r, 1, "9. Período y Estado son automáticos: completá Fecha desde y Fecha hasta; la app vuelve a calcular ambos al importar y no confía en valores manuales.")
    wsi.cell(r + 1, 1, "10. Si una vigencia abarca varios períodos (por ejemplo una concursada plurianual), se asigna al último período registrado que esté comprendido en esa vigencia.")
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out.getvalue()
