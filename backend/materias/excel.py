"""Modelo Excel de carga rapida de opciones curriculares (entry l. 12903-13107, v124), sin cambios de contenido.

El certificado leia escuelas, espacios y el catalogo actual dentro de la funcion; aca se reciben ya leidos (mismas
consultas, ver ``service.py``) para mantener el SQL en el repositorio.  Misma version de openpyxl que el runtime.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd

from docentes.rules import limpiar_texto_tabla

from .rules import ESTADOS_OPCION_CURRICULAR, TIPOS_OPCION_CURRICULAR


def generar_excel_modelo_carga_rapida_opciones_v124(escuelas, espacios_todos, mapa_id_etiqueta, opciones_existentes,
                                                     vinculos_vigentes, filas_modelo=200, max_habilitaciones=10):
    """``vinculos_vigentes``: {opcion_id: [materia_id, ...]} con ``get_vinculos_opcion_curricular_v120(solo_vigentes)``."""
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter, quote_sheetname
    from openpyxl.workbook.defined_name import DefinedName
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.table import Table, TableStyleInfo

    filas_modelo = max(20, min(int(filas_modelo or 200), 5000))
    max_habilitaciones_solicitadas = max(1, min(int(max_habilitaciones or 10), 100))

    espacios_opt = espacios_todos[espacios_todos.get("tipo_espacio", pd.Series(dtype=str)) == "Optativa"].copy() \
        if not espacios_todos.empty else pd.DataFrame()
    espacios_ele = espacios_todos[espacios_todos.get("tipo_espacio", pd.Series(dtype=str)) == "Electiva"].copy() \
        if not espacios_todos.empty else pd.DataFrame()
    lista_opt = espacios_opt.get("etiqueta_selector", pd.Series(dtype=str)).dropna().astype(str).tolist() or [""]
    lista_ele = espacios_ele.get("etiqueta_selector", pd.Series(dtype=str)).dropna().astype(str).tolist() or [""]
    lista_escuelas = [str(x).strip() for x in escuelas if str(x).strip()] or [""]

    registros_existentes = []
    max_habilitaciones_existentes = 0
    if opciones_existentes is not None and not opciones_existentes.empty:
        for _, op in opciones_existentes.sort_values(
            by=[c for c in ["tipo", "nombre", "codigo"] if c in opciones_existentes.columns],
            kind="stable",
        ).iterrows():
            try:
                oid = int(op.get("id"))
            except Exception:
                continue
            etiquetas_hab = []
            for mid in vinculos_vigentes.get(oid, []):
                etiqueta = mapa_id_etiqueta.get(int(mid), "")
                if etiqueta and etiqueta not in etiquetas_hab:
                    etiquetas_hab.append(etiqueta)
            max_habilitaciones_existentes = max(max_habilitaciones_existentes, len(etiquetas_hab))
            registros_existentes.append({
                "id": oid,
                "tipo": limpiar_texto_tabla(op.get("tipo", "")),
                "codigo": limpiar_texto_tabla(op.get("codigo", "")),
                "nombre": limpiar_texto_tabla(op.get("nombre", "")),
                "escuela_oferente": limpiar_texto_tabla(op.get("escuela_oferente", "")),
                "estado": limpiar_texto_tabla(op.get("estado", "")) or "Activa",
                "observaciones": limpiar_texto_tabla(op.get("observaciones", "")),
                "habilitaciones": etiquetas_hab,
            })

    max_habilitaciones = max(max_habilitaciones_solicitadas, max_habilitaciones_existentes)
    filas_modelo = max(filas_modelo, len(registros_existentes) + 50)

    wb = Workbook()
    ws = wb.active
    ws.title = "Carga rápida"
    ws_espacios = wb.create_sheet("Espacios disponibles")
    ws_instr = wb.create_sheet("Instrucciones")
    ws_listas = wb.create_sheet("Listas")

    relleno_encabezado = PatternFill("solid", fgColor="1F4E78")
    relleno_entrada = PatternFill("solid", fgColor="FFF2CC")
    relleno_ref = PatternFill("solid", fgColor="DDEBF7")
    fuente_encabezado = Font(color="FFFFFF", bold=True)
    borde_fino = Border(
        left=Side(style="thin", color="D9E1F2"), right=Side(style="thin", color="D9E1F2"),
        top=Side(style="thin", color="D9E1F2"), bottom=Side(style="thin", color="D9E1F2"),
    )

    encabezados = [
        "Tipo", "Código de la opción", "Materia concreta que se ofrece",
        "Unidad académica oferente", "Estado", "Observaciones",
    ] + [f"Habilitación {i}" for i in range(1, max_habilitaciones + 1)]

    for col_idx, encabezado in enumerate(encabezados, start=1):
        celda = ws.cell(row=1, column=col_idx, value=encabezado)
        celda.fill = relleno_encabezado
        celda.font = fuente_encabezado
        celda.border = borde_fino
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 36
    anchos = [15, 20, 42, 34, 15, 38] + [62] * max_habilitaciones
    for idx, ancho in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = ancho
    fila_fin = filas_modelo + 1
    for fila in range(2, fila_fin + 1):
        for col in range(1, len(encabezados) + 1):
            c = ws.cell(row=fila, column=col)
            c.fill = relleno_entrada
            c.border = borde_fino
            c.alignment = Alignment(vertical="top", wrap_text=True)
        ws.cell(row=fila, column=2).number_format = "@"

    for offset, reg in enumerate(registros_existentes, start=2):
        valores = [
            reg.get("tipo", ""), reg.get("codigo", ""), reg.get("nombre", ""),
            reg.get("escuela_oferente", ""), reg.get("estado", "Activa"), reg.get("observaciones", ""),
        ] + list(reg.get("habilitaciones", []))
        for col_idx in range(1, len(encabezados) + 1):
            valor = valores[col_idx - 1] if col_idx - 1 < len(valores) else ""
            c = ws.cell(row=offset, column=col_idx, value=valor)
            c.fill = relleno_ref
            c.border = borde_fino
            c.alignment = Alignment(vertical="top", wrap_text=True)
        ws.cell(row=offset, column=2).number_format = "@"
        ws.cell(row=offset, column=1).comment = Comment(
            f"Opción curricular ya registrada en el sistema (ID {reg.get('id')}). Podés agregar nuevas habilitaciones en "
            "esta misma fila; al volver a importar no se duplicará si Tipo/Código/Nombre/Unidad académica siguen identificando "
            "la misma opción.",
            "Sistema",
        )

    columnas_listas = {
        1: ("Tipos", list(TIPOS_OPCION_CURRICULAR), "ListaTiposOpciones"),
        2: ("Estados", list(ESTADOS_OPCION_CURRICULAR), "ListaEstadosOpciones"),
        3: ("Unidades académicas", lista_escuelas, "ListaEscuelasOferentes"),
        4: ("Espacios Optativa", lista_opt, "ListaEspaciosOptativa"),
        5: ("Espacios Electiva", lista_ele, "ListaEspaciosElectiva"),
    }
    for col, (titulo, valores, nombre_rango) in columnas_listas.items():
        ws_listas.cell(row=1, column=col, value=titulo).font = Font(bold=True)
        for idx, valor in enumerate(valores, start=2):
            ws_listas.cell(row=idx, column=col, value=valor)
        ref = (f"{quote_sheetname('Listas')}!${get_column_letter(col)}$2:${get_column_letter(col)}$"
               f"{max(2, len(valores) + 1)}")
        wb.defined_names.add(DefinedName(nombre_rango, attr_text=ref))

    dv_tipo = DataValidation(type="list", formula1="=ListaTiposOpciones", allow_blank=False)
    dv_tipo.error = "Seleccioná Optativa o Electiva."
    dv_tipo.errorTitle = "Tipo no válido"
    dv_tipo.showErrorMessage = True
    ws.add_data_validation(dv_tipo)
    dv_tipo.add(f"A2:A{fila_fin}")

    dv_estado = DataValidation(type="list", formula1="=ListaEstadosOpciones", allow_blank=True)
    dv_estado.error = "Seleccioná un estado válido."
    dv_estado.errorTitle = "Estado no válido"
    dv_estado.showErrorMessage = True
    ws.add_data_validation(dv_estado)
    dv_estado.add(f"E2:E{fila_fin}")

    dv_escuela = DataValidation(type="list", formula1="=ListaEscuelasOferentes", allow_blank=True)
    dv_escuela.showErrorMessage = False
    dv_escuela.promptTitle = "Unidad académica oferente"
    dv_escuela.prompt = "Elegí una unidad académica existente o escribí manualmente otra. En Electivas es obligatoria."
    dv_escuela.showInputMessage = True
    ws.add_data_validation(dv_escuela)
    dv_escuela.add(f"D2:D{fila_fin}")

    for col_idx in range(7, 7 + max_habilitaciones):
        letra = get_column_letter(col_idx)
        dv_hab = DataValidation(type="list", formula1='=INDIRECT("ListaEspacios"&$A2)', allow_blank=True)
        dv_hab.error = "Elegí un espacio compatible con el Tipo de la opción."
        dv_hab.errorTitle = "Espacio no válido"
        dv_hab.showErrorMessage = True
        dv_hab.showInputMessage = True
        dv_hab.promptTitle = "Habilitación"
        dv_hab.prompt = ("Elegí un espacio formal de plan. La lista cambia entre Optativa y Electiva según la columna "
                         "Tipo.")
        ws.add_data_validation(dv_hab)
        dv_hab.add(f"{letra}2:{letra}{fila_fin}")

    tabla = Table(displayName="TablaCargaRapidaOpciones", ref=f"A1:{get_column_letter(len(encabezados))}{fila_fin}")
    tabla.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
    ws.add_table(tabla)
    ws["A1"].comment = Comment("Obligatorio. Elegir Optativa o Electiva desde la lista.", "Sistema")
    ws["B1"].comment = Comment("Opcional. La columna está en formato texto para conservar ceros iniciales.", "Sistema")
    ws["C1"].comment = Comment("Obligatorio. Nombre de la materia concreta que se ofrece.", "Sistema")
    ws["D1"].comment = Comment("Obligatorio para Electivas. En Optativas puede quedar vacío.", "Sistema")
    ws["E1"].comment = Comment("Si queda vacío, se toma Activa.", "Sistema")
    for col_idx in range(7, 7 + max_habilitaciones):
        ws.cell(row=1, column=col_idx).comment = Comment(
            "Elegí desde la lista el espacio exacto de un plan para el cual esta opción será válida. Podés habilitar "
            "la misma opción en varios planes.",
            "Sistema",
        )

    cols_ref = ["tipo_espacio", "escuela", "carrera", "plan_version", "codigo", "asignatura", "anio", "cuatrimestre",
                "materia_id", "etiqueta_selector"]
    tit_ref = ["Tipo", "Unidad académica", "Carrera", "Plan", "Código espacio", "Espacio formal", "Año", "Cuatrimestre",
               "ID materia", "Valor de lista"]
    for j, t in enumerate(tit_ref, 1):
        c = ws_espacios.cell(row=1, column=j, value=t)
        c.fill = relleno_encabezado
        c.font = fuente_encabezado
        c.border = borde_fino
    if not espacios_todos.empty:
        for i, (_, r) in enumerate(espacios_todos.iterrows(), start=2):
            for j, col in enumerate(cols_ref, start=1):
                c = ws_espacios.cell(row=i, column=j, value=r.get(col, ""))
                c.fill = relleno_ref
                c.border = borde_fino
                c.alignment = Alignment(wrap_text=True, vertical="top")
    for col, ancho in enumerate([14, 28, 38, 24, 18, 28, 14, 16, 14, 95], start=1):
        ws_espacios.column_dimensions[get_column_letter(col)].width = ancho
    ws_espacios.freeze_panes = "A2"

    instrucciones = [
        "MODELO DE CARGA RÁPIDA DE OPCIONES CURRICULARES",
        "1. Completá una fila por materia concreta Optativa/Electiva que quieras registrar.",
        "2. Tipo y Estado tienen listas desplegables. Unidad académica oferente muestra las unidades académicas actuales y permite "
        "escribir una nueva; es obligatoria para Electivas.",
        "3. Habilitación 1, Habilitación 2, etc. tienen listas desplegables de los espacios formales vigentes de los "
        "planes. La lista se filtra según el Tipo de la fila.",
        "4. Una misma opción puede habilitarse para varios espacios/carreras en la misma fila. El modelo trae varias "
        "columnas de habilitación y la app también reconoce Habilitación 11, 12, etc. si se agregan con ese encabezado.",
        "5. Las primeras filas ya incluyen las opciones curriculares registradas en el sistema, con sus datos actuales y "
        "todas sus habilitaciones vigentes. Las filas celestes son existentes; las filas amarillas vacías son para "
        "nuevas altas.",
        "6. Si una opción ya existe exactamente, la carga no la duplica: reutiliza su ID y agrega únicamente las "
        "habilitaciones que falten. Podés usar una fila existente para sumar habilitaciones nuevas.",
        "7. Borrar una habilitación del Excel NO la elimina del sistema: para quitar habilitaciones existentes usá la "
        "administración individual de la pestaña, preservando así la trazabilidad de comisiones históricas.",
        "8. Las habilitaciones modifican el catálogo para futuras comisiones; no cambian retroactivamente las comisiones "
        "históricas ya abiertas.",
        "9. No cambies los nombres de las columnas principales. Luego guardá el archivo y subilo directamente en la "
        "pestaña Optativas / Electivas.",
    ]
    for i, t in enumerate(instrucciones, start=1):
        ws_instr.cell(row=i, column=1, value=t).alignment = Alignment(wrap_text=True, vertical="top")
    ws_instr["A1"].font = Font(bold=True, size=14)
    ws_instr.column_dimensions["A"].width = 125
    ws_listas.sheet_state = "hidden"

    salida = BytesIO()
    wb.save(salida)
    salida.seek(0)
    return salida.getvalue()
