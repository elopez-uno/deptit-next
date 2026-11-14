"""Excel de Carga rapida de Comisiones, copiado de la fuente certificada B13-FIX02 (openpyxl, mismas versiones).

Origen (reference_fix02, entry): ``generar_excel_modelo_carga_rapida_comisiones`` l. 19523 (la redefinicion v199 de
l. 45962 solo agrega cache) y ``generar_excel_comisiones_periodo_completado_v175`` l. 37564 (+ ``_contexto_excel_
materia_v175`` de ``deptit_refactor/domain/materias.py``).  Las lecturas (``get_materias_para_comisiones``,
``get_docentes_activos_para_comisiones``, ``get_docentes``, ``get_opciones_curriculares_v120``, ``get_periodos``,
sedes, institucion/departamento de la sesion, vinculos v118 y periodo) llegan por ``FuenteExcel``.  Ninguna escribe.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pandas as pd

from . import rules as R
from .lecturas import Lector

VINCULOS_COMISION_SQL = (
    "SELECT comision_id, materia_id, carrera_id_snapshot, carrera_snapshot, escuela_snapshot, plan_version_snapshot, "
    "anio_snapshot, cuatrimestre_snapshot, dictado_snapshot, carga_semanal_snapshot, carga_total_snapshot, "
    "codigo_snapshot, asignatura_snapshot, fecha_vinculacion, origen FROM comision_materias WHERE comision_id IN (%s) "
    "AND (comision_materias.institucion_id = %s) AND (comision_materias.departamento_id = %s) "
    "ORDER BY comision_id, materia_id")
PERIODO_NOMBRE_ESTADO_SQL = ("SELECT nombre, estado FROM periodos WHERE id=%s AND (periodos.institucion_id = %s) AND "
                             "(periodos.departamento_id = %s) LIMIT 1")


@dataclass
class FuenteExcel:
    """Lecturas certificadas que usan los dos libros (todas por el ``Lector`` de la operacion)."""
    L: Lector
    institucion_nombre: str
    departamento_nombre: str

    def materias_para_comisiones(self) -> pd.DataFrame:
        return self.L.materias_para_comisiones()

    def periodo_actual(self) -> Any:
        return self.L.ultimo_periodo()

    def docentes_activos(self, periodo_id: int) -> pd.DataFrame:
        return self.L.docentes_activos_para_comisiones(periodo_id)

    def docentes(self) -> pd.DataFrame:
        return pd.DataFrame(self.L.repo.docentes())

    def opciones_curriculares_activas(self) -> pd.DataFrame:
        return self.L.opciones_curriculares_v120(estado="Activa")

    def opciones_sedes(self) -> list:
        return self.L.opciones_sedes_comision()

    def periodos(self) -> pd.DataFrame:
        return pd.DataFrame(self.L.repo.periods())

    def vinculos_comision(self, comision_id: int) -> pd.DataFrame:
        repo = self.L.repo
        return repo.read_sql(VINCULOS_COMISION_SQL, [int(comision_id), int(repo.inst), int(repo.dep)])

    def periodo_nombre_estado(self, periodo_id: int) -> pd.DataFrame:
        repo = self.L.repo
        return repo.read_sql(PERIODO_NOMBRE_ESTADO_SQL, [int(periodo_id), int(repo.inst), int(repo.dep)])


def generar_excel_modelo_carga_rapida_comisiones(fuente: "FuenteExcel", periodo_id=None, filas_modelo=300) -> bytes:
    """l. 19523 (v144/v153).  Lecturas certificadas inyectadas por ``fuente`` (mismo orden y mismos datos)."""
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.workbook.defined_name import DefinedName
    from openpyxl.utils import quote_sheetname, get_column_letter

    filas_modelo = max(20, min(int(filas_modelo or 300), 2000))

    try:
        df_materias_excel = fuente.materias_para_comisiones().copy()
    except Exception:
        df_materias_excel = pd.DataFrame()
    columnas_materias = [
        "materia_id", "codigo", "asignatura", "carrera", "escuela", "plan_version", "anio",
        "cuatrimestre", "estado_materia", "comparticion_modo", "comparticion_grupo"
    ]
    for col in columnas_materias:
        if col not in df_materias_excel.columns:
            df_materias_excel[col] = ""
    if not df_materias_excel.empty:
        for col in columnas_materias:
            df_materias_excel[col] = df_materias_excel[col].fillna("").astype(str).str.strip()
        df_materias_excel = (
            df_materias_excel[columnas_materias]
            .drop_duplicates(subset=["materia_id"], keep="first")
            .sort_values(["asignatura", "codigo", "carrera", "plan_version"], kind="stable")
            .reset_index(drop=True)
        )

        # Contexto base del grupo conceptual (las carreras ya vienen agregadas por la
        # lógica v137 cuando una materia se comparte entre varios planes).
        df_materias_excel["contexto_plan_base"] = df_materias_excel.apply(
            lambda r: " — ".join([
                x for x in [
                    R.limpiar_texto_tabla(r.get("carrera", "")),
                    R.limpiar_texto_tabla(r.get("plan_version", "")),
                    R.limpiar_texto_tabla(r.get("escuela", "")),
                ] if x
            ]),
            axis=1,
        )

        # Se usa un único nombre visible por identidad textual normalizada. Esto evita
        # que pequeñas diferencias de mayúsculas/acentos entre planes rompan MATCH/VLOOKUP.
        display_por_norm = {}
        for valor in df_materias_excel["asignatura"].tolist():
            txt = R.limpiar_texto_tabla(valor)
            clave = R.normalizar_clave(txt)
            if txt and clave not in display_por_norm:
                display_por_norm[clave] = txt
        df_materias_excel["asignatura_selector"] = df_materias_excel["asignatura"].apply(
            lambda x: display_por_norm.get(R.normalizar_clave(x), R.limpiar_texto_tabla(x))
        )

        # v144: cada alternativa Carrera/plan comienza con [CÓDIGO].
        # El código queda en los primeros caracteres de la propia opción seleccionada,
        # de modo que Excel no necesita buscar el texto completo (que puede superar 255
        # caracteres cuando una materia se comparte entre muchas carreras).
        df_materias_excel["contexto_selector"] = ""
        for asig_sel, idxs in df_materias_excel.groupby("asignatura_selector", sort=False).groups.items():
            for idx in list(idxs):
                base = R.limpiar_texto_tabla(df_materias_excel.at[idx, "contexto_plan_base"])
                cod = R.limpiar_texto_tabla(df_materias_excel.at[idx, "codigo"]).upper()
                if cod:
                    etiqueta = f"[{cod}] {base}" if base else f"[{cod}]"
                else:
                    etiqueta = base
                df_materias_excel.at[idx, "contexto_selector"] = etiqueta

        # Si por alguna configuración excepcional quedaran etiquetas duplicadas dentro
        # de una misma asignatura, se agrega un sufijo corto solo para hacerlas seleccionables.
        for asig_sel, idxs in df_materias_excel.groupby("asignatura_selector", sort=False).groups.items():
            vistos_ctx = {}
            for idx in list(idxs):
                ctx = R.limpiar_texto_tabla(df_materias_excel.at[idx, "contexto_selector"])
                clave_ctx = R.normalizar_clave(ctx)
                vistos_ctx[clave_ctx] = vistos_ctx.get(clave_ctx, 0) + 1
                if vistos_ctx[clave_ctx] > 1:
                    df_materias_excel.at[idx, "contexto_selector"] = f"{ctx} — Grupo {vistos_ctx[clave_ctx]}"

        df_materias_excel["clave_selector_excel"] = df_materias_excel.apply(
            lambda r: f"{R.limpiar_texto_tabla(r.get('asignatura_selector', ''))}|||{R.limpiar_texto_tabla(r.get('contexto_selector', ''))}",
            axis=1,
        )
    else:
        df_materias_excel["contexto_plan_base"] = ""
        df_materias_excel["asignatura_selector"] = ""
        df_materias_excel["contexto_selector"] = ""
        df_materias_excel["clave_selector_excel"] = ""

    # Docentes disponibles en el período actual, igual que en la pantalla web.
    if periodo_id is None:
        try:
            periodo_ref = fuente.periodo_actual()
            periodo_id = int(periodo_ref["id"]) if periodo_ref is not None else None
        except Exception:
            periodo_id = None

    try:
        df_docentes_activos = (
            fuente.docentes_activos(int(periodo_id)).copy()
            if periodo_id is not None else pd.DataFrame()
        )
    except Exception:
        df_docentes_activos = pd.DataFrame()
    try:
        df_docentes_base = fuente.docentes().copy()
    except Exception:
        df_docentes_base = pd.DataFrame()

    columnas_docentes = ["cuil", "nombre_completo", "legajo", "estado", "tipo_docente", "titulo", "email"]
    if not df_docentes_activos.empty:
        for col in ["cuil", "nombre_completo", "tipo_docente"]:
            if col not in df_docentes_activos.columns:
                df_docentes_activos[col] = ""
        df_docentes_activos["cuil"] = df_docentes_activos["cuil"].fillna("").astype(str).str.strip()
        df_docentes_activos["nombre_completo"] = df_docentes_activos["nombre_completo"].fillna("").astype(str).str.strip()
        df_docentes_activos = df_docentes_activos[df_docentes_activos["cuil"] != ""].copy()
        if not df_docentes_base.empty and "cuil" in df_docentes_base.columns:
            df_docentes_base["cuil"] = df_docentes_base["cuil"].fillna("").astype(str).str.strip()
            cols_base = [c for c in columnas_docentes if c in df_docentes_base.columns]
            df_docentes_excel = df_docentes_activos.merge(
                df_docentes_base[cols_base].drop_duplicates(subset=["cuil"], keep="first"),
                on="cuil", how="left", suffixes=("_periodo", "_base")
            )
            nombre_periodo = df_docentes_excel.get("nombre_completo_periodo", pd.Series("", index=df_docentes_excel.index)).fillna("").astype(str).str.strip()
            nombre_base = df_docentes_excel.get("nombre_completo_base", pd.Series("", index=df_docentes_excel.index)).fillna("").astype(str).str.strip()
            df_docentes_excel["nombre_completo"] = nombre_periodo.where(nombre_periodo != "", nombre_base)
            tipo_periodo = df_docentes_excel.get("tipo_docente_periodo", pd.Series("", index=df_docentes_excel.index)).fillna("").astype(str).str.strip()
            tipo_base = df_docentes_excel.get("tipo_docente_base", pd.Series("", index=df_docentes_excel.index)).fillna("").astype(str).str.strip()
            df_docentes_excel["tipo_docente"] = tipo_periodo.where(tipo_periodo != "", tipo_base)
            for col in ["legajo", "estado", "titulo", "email"]:
                col_base = f"{col}_base"
                if col_base in df_docentes_excel.columns:
                    df_docentes_excel[col] = df_docentes_excel[col_base]
                elif col not in df_docentes_excel.columns:
                    df_docentes_excel[col] = ""
        else:
            df_docentes_excel = df_docentes_activos.copy()
    else:
        df_docentes_excel = pd.DataFrame(columns=columnas_docentes)

    for col in columnas_docentes:
        if col not in df_docentes_excel.columns:
            df_docentes_excel[col] = ""
    if not df_docentes_excel.empty:
        for col in columnas_docentes:
            df_docentes_excel[col] = df_docentes_excel[col].fillna("").astype(str).str.strip()
        df_docentes_excel = df_docentes_excel[df_docentes_excel["nombre_completo"] != ""].copy()
        df_docentes_excel = (
            df_docentes_excel[columnas_docentes]
            .drop_duplicates(subset=["cuil"], keep="first")
            .sort_values(["nombre_completo", "cuil"], kind="stable")
            .reset_index(drop=True)
        )

    # Selector único de asignaturas y mapa canónico de grupos conceptuales.
    materias_selector = []
    contextos_por_asignatura = {}
    codigo_unico_por_asignatura = {}
    contexto_unico_por_asignatura = {}

    if not df_materias_excel.empty:
        materias_selector = [
            x for x in df_materias_excel["asignatura_selector"].dropna().astype(str).drop_duplicates().tolist()
            if R.limpiar_texto_tabla(x)
        ]
        for asig in materias_selector:
            grupo = df_materias_excel[
                df_materias_excel["asignatura_selector"].astype(str).apply(R.normalizar_clave)
                == R.normalizar_clave(asig)
            ].copy()

            contextos = []
            for ctx in grupo.get("contexto_selector", pd.Series(dtype=str)).tolist():
                ctx = R.limpiar_texto_tabla(ctx)
                if ctx and ctx not in contextos:
                    contextos.append(ctx)
            contextos_por_asignatura[asig] = contextos

            codigos = []
            for cod in grupo.get("codigo", pd.Series(dtype=str)).tolist():
                cod = R.limpiar_texto_tabla(cod).upper()
                key = R.normalizar_codigo_materia(cod)
                if cod and key not in [R.normalizar_codigo_materia(x) for x in codigos]:
                    codigos.append(cod)
            codigo_unico_por_asignatura[asig] = codigos[0] if len(codigos) == 1 else ""
            contexto_unico_por_asignatura[asig] = contextos[0] if len(contextos) == 1 else ""

    docentes_selector, vistos_docentes = [], set()
    for valor in df_docentes_excel.get("nombre_completo", pd.Series(dtype=str)).tolist():
        txt = str(valor or "").strip(); clave = R.normalizar_clave(txt)
        if txt and clave not in vistos_docentes:
            vistos_docentes.add(clave); docentes_selector.append(txt)

    try:
        df_opciones_excel = fuente.opciones_curriculares_activas()
    except Exception:
        df_opciones_excel = pd.DataFrame()
    opciones_selector = []
    if isinstance(df_opciones_excel, pd.DataFrame) and not df_opciones_excel.empty:
        for _, op in df_opciones_excel.iterrows():
            etiqueta_op = R.etiqueta_opcion_curricular_v120(op)
            if etiqueta_op and etiqueta_op not in opciones_selector:
                opciones_selector.append(etiqueta_op)

    cantidad_semillas = max(1, len(materias_selector), len(docentes_selector), len(opciones_selector))
    fila_encabezado_carga = cantidad_semillas + 1
    fila_inicio_carga = fila_encabezado_carga + 1
    fila_fin_carga = fila_inicio_carga + filas_modelo - 1

    wb = Workbook()
    ws = wb.active; ws.title = "Carga rápida"
    ws_materias = wb.create_sheet("Materias")
    ws_docentes = wb.create_sheet("Docentes")
    ws_instrucciones = wb.create_sheet("Instrucciones")
    ws_listas = wb.create_sheet("Listas")

    relleno_encabezado = PatternFill("solid", fgColor="1F4E78")
    relleno_formula = PatternFill("solid", fgColor="D9EAF7")
    relleno_entrada = PatternFill("solid", fgColor="FFF2CC")
    relleno_dependiente = PatternFill("solid", fgColor="E2F0D9")
    relleno_referencia = PatternFill("solid", fgColor="DDEBF7")
    fuente_encabezado = Font(color="FFFFFF", bold=True)
    borde_fino = Border(
        left=Side(style="thin", color="D9E1F2"), right=Side(style="thin", color="D9E1F2"),
        top=Side(style="thin", color="D9E1F2"), bottom=Side(style="thin", color="D9E1F2"),
    )

    # Orden intencional: Carrera/plan queda al lado de SU Asignatura.
    encabezados = [
        "Código", "Asignatura", "Carrera / plan",
        "Código 2", "Asignatura 2", "Carrera / plan 2",
        "Código 3", "Asignatura 3", "Carrera / plan 3",
        "Opción Curricular", "Comisión", "Turno",
        "Día 1", "Hora Inicio 1", "Hora Fin 1",
        "Día 2", "Hora Inicio 2", "Hora Fin 2",
        "Día 3", "Hora Inicio 3", "Hora Fin 3",
        "Día 4", "Hora Inicio 4", "Hora Fin 4",
        "Día 5", "Hora Inicio 5", "Hora Fin 5",
        "Modalidad", "Sede",
    ]
    # Cada docente puede cubrir o excluir cada uno de los 5 horarios generales.
    # Se mantienen las columnas históricas Día/Hora Inicio/Hora Fin para no romper
    # el formato ni la lógica de cobertura parcial ya existente.
    for n_doc in range(1, 6):
        encabezados.append(f"Docente {n_doc}")
        for n_h in range(1, 6):
            encabezados.extend([
                f"Cubre Horario {n_h} - Docente {n_doc}",
                f"Día Docente {n_doc} Horario {n_h}",
                f"Hora Inicio Docente {n_doc} Horario {n_h}",
                f"Hora Fin Docente {n_doc} Horario {n_h}",
            ])

    col_idx = {nombre: i + 1 for i, nombre in enumerate(encabezados)}
    col_letra = {nombre: get_column_letter(i) for nombre, i in col_idx.items()}

    # Semillas ocultas para autocompletado nativo de Excel.
    for fila_semilla in range(1, cantidad_semillas + 1):
        if materias_selector:
            materia_semilla = materias_selector[(fila_semilla - 1) % len(materias_selector)]
            for nombre_col in ["Asignatura", "Asignatura 2", "Asignatura 3"]:
                ws.cell(row=fila_semilla, column=col_idx[nombre_col], value=materia_semilla)
        if opciones_selector:
            ws.cell(row=fila_semilla, column=col_idx["Opción Curricular"], value=opciones_selector[(fila_semilla - 1) % len(opciones_selector)])
        if docentes_selector:
            docente_semilla = docentes_selector[(fila_semilla - 1) % len(docentes_selector)]
            for n_doc in range(1, 6):
                ws.cell(row=fila_semilla, column=col_idx[f"Docente {n_doc}"], value=docente_semilla)
        ws.row_dimensions[fila_semilla].hidden = True

    for i, encabezado in enumerate(encabezados, start=1):
        c = ws.cell(row=fila_encabezado_carga, column=i, value=encabezado)
        c.fill = relleno_encabezado; c.font = fuente_encabezado
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); c.border = borde_fino
    ws.row_dimensions[fila_encabezado_carga].height = 42
    ws.freeze_panes = f"A{fila_inicio_carga}"

    # Anchos: se prioriza lectura en los campos que el usuario elige.
    for nombre, idx in col_idx.items():
        letra = get_column_letter(idx)
        if nombre.startswith("Asignatura"):
            ancho = 38
        elif nombre.startswith("Carrera / plan"):
            ancho = 46
        elif nombre.startswith("Código"):
            ancho = 13
        elif nombre.startswith("Docente ") and "Horario" not in nombre:
            ancho = 30
        elif nombre.startswith("Cubre Horario"):
            ancho = 17
        elif nombre.startswith("Día Docente"):
            ancho = 18
        elif nombre.startswith("Hora Inicio Docente") or nombre.startswith("Hora Fin Docente"):
            ancho = 18
        elif nombre == "Opción Curricular":
            ancho = 42
        elif nombre == "Sede":
            ancho = 24
        elif nombre in {"Modalidad", "Turno"}:
            ancho = 16
        elif nombre.startswith("Hora Inicio") or nombre.startswith("Hora Fin"):
            ancho = 15
        elif nombre.startswith("Día "):
            ancho = 13
        else:
            ancho = 13
        ws.column_dimensions[letra].width = ancho

    # Hoja Materias: una fila por grupo conceptual disponible, útil para auditar qué
    # representa cada alternativa del selector dependiente.
    encabezados_mat = [
        "Código", "Asignatura", "Carrera/s", "Unidades académicas", "Año/s", "Cuatrimestre/s",
        "Estado", "Contexto para carga rápida", "Clave selector"
    ]
    for j, valor in enumerate(encabezados_mat, start=1):
        c = ws_materias.cell(row=1, column=j, value=valor)
        c.fill = relleno_encabezado; c.font = fuente_encabezado
        c.alignment = Alignment(horizontal="center", vertical="center"); c.border = borde_fino
    for i, (_, fila) in enumerate(df_materias_excel.iterrows(), start=2):
        valores = [
            fila.get("codigo", ""), fila.get("asignatura_selector", ""), fila.get("carrera", ""),
            fila.get("escuela", ""), fila.get("anio", ""), fila.get("cuatrimestre", ""),
            fila.get("estado_materia", ""), fila.get("contexto_selector", ""), fila.get("clave_selector_excel", ""),
        ]
        for j, valor in enumerate(valores, start=1):
            c = ws_materias.cell(row=i, column=j, value=valor); c.border = borde_fino
            c.alignment = Alignment(vertical="top", wrap_text=True)
    ws_materias.freeze_panes = "A2"
    for letra, ancho in {"A": 16, "B": 42, "C": 44, "D": 35, "E": 16, "F": 18, "G": 14, "H": 54, "I": 20}.items():
        ws_materias.column_dimensions[letra].width = ancho
    ws_materias.column_dimensions["I"].hidden = True
    if len(df_materias_excel) > 0:
        tabla_mat = Table(displayName="TablaMateriasUniversidad", ref=f"A1:I{len(df_materias_excel) + 1}")
        tabla_mat.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
        ws_materias.add_table(tabla_mat)

    encabezados_doc = ["CUIL", "Docente", "Legajo", "Estado", "Tipo de docente", "Título", "Email"]
    for j, valor in enumerate(encabezados_doc, start=1):
        c = ws_docentes.cell(row=1, column=j, value=valor)
        c.fill = relleno_encabezado; c.font = fuente_encabezado
        c.alignment = Alignment(horizontal="center", vertical="center"); c.border = borde_fino
    for i, (_, fila) in enumerate(df_docentes_excel.iterrows(), start=2):
        valores = [fila.get("cuil", ""), fila.get("nombre_completo", ""), fila.get("legajo", ""), fila.get("estado", ""), fila.get("tipo_docente", ""), fila.get("titulo", ""), fila.get("email", "")]
        for j, valor in enumerate(valores, start=1):
            c = ws_docentes.cell(row=i, column=j, value=valor); c.border = borde_fino
            c.alignment = Alignment(vertical="top", wrap_text=True)
    ws_docentes.freeze_panes = "A2"
    for letra, ancho in {"A": 18, "B": 36, "C": 14, "D": 16, "E": 18, "F": 38, "G": 34}.items():
        ws_docentes.column_dimensions[letra].width = ancho
    if len(df_docentes_excel) > 0:
        tabla_doc = Table(displayName="TablaDocentesDepartamento", ref=f"A1:G{len(df_docentes_excel) + 1}")
        tabla_doc.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
        ws_docentes.add_table(tabla_doc)

    # Listas generales.
    # Horario institucional disponible para comisiones: 08:00 a 23:00.
    # Se ofrecen intervalos de 30 minutos y 23:00 queda como último horario posible.
    horarios_media_hora = [f"{h:02d}:{m:02d}" for h in range(8, 23) for m in (0, 30)] + ["23:00"]
    listas = {
        "A": ("Turnos", ["mañana", "tarde", "noche"]),
        "B": ("Días", list(R.DIAS_SEMANA)),
        "C": ("Modalidades", ["Presencial", "Virtual", "Híbrida"]),
        "D": ("Sedes", fuente.opciones_sedes()),
        "E": ("Horarios cada 30 min", horarios_media_hora),
    }
    for letra, (titulo, valores) in listas.items():
        ws_listas[f"{letra}1"] = titulo; ws_listas[f"{letra}1"].font = Font(bold=True)
        for idx, valor in enumerate(valores, start=2): ws_listas[f"{letra}{idx}"] = valor

    ws_listas["F1"] = "Materias para seleccionar"; ws_listas["G1"] = "Docentes para seleccionar"; ws_listas["H1"] = "Opciones curriculares"; ws_listas["I1"] = "Cobertura docente"
    for celda in ["F1", "G1", "H1", "I1"]: ws_listas[celda].font = Font(bold=True)
    for idx, valor in enumerate(materias_selector or [""], start=2): ws_listas.cell(row=idx, column=6, value=valor)
    for idx, valor in enumerate(docentes_selector or [""], start=2): ws_listas.cell(row=idx, column=7, value=valor)
    for idx, valor in enumerate(opciones_selector or [""], start=2): ws_listas.cell(row=idx, column=8, value=valor)
    ws_listas.cell(row=2, column=9, value="Sí")
    ws_listas.cell(row=3, column=9, value="No")

    def agregar_nombre(nombre, hoja, columna, fila_inicio, fila_fin):
        referencia = f"{quote_sheetname(hoja)}!${columna}${fila_inicio}:${columna}${max(fila_inicio, fila_fin)}"
        wb.defined_names.add(DefinedName(nombre, attr_text=referencia))

    agregar_nombre("ListaTurnos", "Listas", "A", 2, 1 + len(listas["A"][1]))
    agregar_nombre("ListaDias", "Listas", "B", 2, 1 + len(listas["B"][1]))
    agregar_nombre("ListaModalidades", "Listas", "C", 2, 1 + len(listas["C"][1]))
    agregar_nombre("ListaSedes", "Listas", "D", 2, 1 + len(listas["D"][1]))
    agregar_nombre("ListaHoras", "Listas", "E", 2, 1 + len(listas["E"][1]))
    agregar_nombre("ListaMaterias", "Listas", "F", 2, 1 + max(1, len(materias_selector)))
    agregar_nombre("ListaDocentes", "Listas", "G", 2, 1 + max(1, len(docentes_selector)))
    agregar_nombre("ListaOpcionesCurriculares", "Listas", "H", 2, 1 + max(1, len(opciones_selector)))
    agregar_nombre("ListaCoberturaDocente", "Listas", "I", 2, 3)

    # Listas dependientes Carrera/plan por Asignatura.
    # K:N es el mapa canónico:
    #   Asignatura | Rango contextos | Código único (si existe) | Contexto único (si existe)
    # El Código único se calcula en Python por identidad institucional, no contando filas
    # del plan; por eso una materia presente en muchas carreras sigue autocompletando su código.
    ws_listas["J1"] = "Contextos por materia"
    ws_listas["K1"] = "Asignatura"
    ws_listas["L1"] = "Rango contextos"
    ws_listas["M1"] = "Código único"
    ws_listas["N1"] = "Contexto único"
    ws_listas["O1"] = "Vacío"
    for c in ["J1", "K1", "L1", "M1", "N1", "O1"]:
        ws_listas[c].font = Font(bold=True)
    ws_listas["O2"] = ""
    agregar_nombre("ListaVacia", "Listas", "O", 2, 2)
    fila_contexto = 2
    fila_mapa = 2
    for idx_asig, asig in enumerate(materias_selector, start=1):
        contextos = list(contextos_por_asignatura.get(asig, [])) or [""]
        ini = fila_contexto
        for ctx in contextos:
            ws_listas.cell(row=fila_contexto, column=10, value=ctx)
            fila_contexto += 1
        fin = fila_contexto - 1
        nombre_rango = f"CtxMateria_{idx_asig}"
        agregar_nombre(nombre_rango, "Listas", "J", ini, fin)
        ws_listas.cell(row=fila_mapa, column=11, value=asig)
        ws_listas.cell(row=fila_mapa, column=12, value=nombre_rango)
        ws_listas.cell(row=fila_mapa, column=13, value=codigo_unico_por_asignatura.get(asig, ""))
        ws_listas.cell(row=fila_mapa, column=14, value=contexto_unico_por_asignatura.get(asig, ""))
        fila_mapa += 1
    fila_fin_mapa = max(2, fila_mapa - 1)

    # v143: mapa exacto Asignatura + Carrera/plan -> Código.
    # No se usa INDEX sobre la hoja Materias porque, si la celda encontrada está vacía,
    # Excel puede representarla como 0. El mapa contiene directamente el texto del código.
    ws_listas["P1"] = "Clave Asignatura|||Carrera/plan"
    ws_listas["Q1"] = "Código por contexto"
    ws_listas["P1"].font = Font(bold=True); ws_listas["Q1"].font = Font(bold=True)
    fila_codigo_ctx = 2
    if not df_materias_excel.empty:
        vistos_claves_codigo = set()
        for _, fila_mat_ctx in df_materias_excel.iterrows():
            clave_ctx = R.limpiar_texto_tabla(fila_mat_ctx.get("clave_selector_excel", ""))
            codigo_ctx = R.limpiar_texto_tabla(fila_mat_ctx.get("codigo", "")).upper()
            if not clave_ctx:
                continue
            # Después de agregar sufijos Grupo N, la clave visible es única. Si por
            # algún dato excepcional se repite, conservamos la primera coincidencia.
            clave_norm = R.normalizar_clave(clave_ctx)
            if clave_norm in vistos_claves_codigo:
                continue
            vistos_claves_codigo.add(clave_norm)
            ws_listas.cell(row=fila_codigo_ctx, column=16, value=clave_ctx)
            ws_listas.cell(row=fila_codigo_ctx, column=17, value=codigo_ctx)
            ws_listas.cell(row=fila_codigo_ctx, column=17).number_format = "@"
            fila_codigo_ctx += 1
    fila_fin_codigo_ctx = max(2, fila_codigo_ctx - 1)

    # Validaciones generales.
    def agregar_validacion_lista(formula, rango, titulo, mensaje, error="El valor no pertenece a la lista disponible."):
        dv = DataValidation(type="list", formula1=formula, allow_blank=True)
        dv.error = error; dv.errorTitle = "Valor no válido"; dv.prompt = mensaje; dv.promptTitle = titulo
        dv.showErrorMessage = True; dv.showInputMessage = True
        ws.add_data_validation(dv); dv.add(rango)

    for nombre_asig in ["Asignatura", "Asignatura 2", "Asignatura 3"]:
        letra = col_letra[nombre_asig]
        agregar_validacion_lista("=ListaMaterias", f"{letra}{fila_inicio_carga}:{letra}{fila_fin_carga}", nombre_asig, "Elegí una asignatura de la universidad.")

    agregar_validacion_lista("=ListaTurnos", f"{col_letra['Turno']}{fila_inicio_carga}:{col_letra['Turno']}{fila_fin_carga}", "Turno", "Elegí un turno válido.")
    agregar_validacion_lista("=ListaModalidades", f"{col_letra['Modalidad']}{fila_inicio_carga}:{col_letra['Modalidad']}{fila_fin_carga}", "Modalidad", "Elegí Presencial, Virtual o Híbrida.")
    agregar_validacion_lista("=ListaSedes", f"{col_letra['Sede']}{fila_inicio_carga}:{col_letra['Sede']}{fila_fin_carga}", "Sede", "Elegí una sede institucional, Campus Virtual o Sin especificar.")
    agregar_validacion_lista("=ListaOpcionesCurriculares", f"{col_letra['Opción Curricular']}{fila_inicio_carga}:{col_letra['Opción Curricular']}{fila_fin_carga}", "Opción curricular", "Obligatoria para Optativas/Electivas; vacía para materias comunes.")

    # Horarios generales de la comisión.
    for n_h in range(1, 6):
        agregar_validacion_lista("=ListaDias", f"{col_letra[f'Día {n_h}']}{fila_inicio_carga}:{col_letra[f'Día {n_h}']}{fila_fin_carga}", f"Día {n_h}", "Elegí un día de la semana.")
        for campo in [f"Hora Inicio {n_h}", f"Hora Fin {n_h}"]:
            agregar_validacion_lista("=ListaHoras", f"{col_letra[campo]}{fila_inicio_carga}:{col_letra[campo]}{fila_fin_carga}", campo, "Elegí una hora entre 08:00 y 23:00, en intervalos de 30 minutos.")

    # Docentes y sus horarios efectivos.
    for n_doc in range(1, 6):
        agregar_validacion_lista(
            "=ListaDocentes",
            f"{col_letra[f'Docente {n_doc}']}{fila_inicio_carga}:{col_letra[f'Docente {n_doc}']}{fila_fin_carga}",
            f"Docente {n_doc}",
            "Elegí un docente disponible en el período actual.",
        )
        for n_h in range(1, 6):
            agregar_validacion_lista(
                "=ListaCoberturaDocente",
                f"{col_letra[f'Cubre Horario {n_h} - Docente {n_doc}']}{fila_inicio_carga}:{col_letra[f'Cubre Horario {n_h} - Docente {n_doc}']}{fila_fin_carga}",
                f"Cubre Horario {n_h}",
                "Sí = participa de este horario general. No = no lo cubre. Por defecto queda Sí cuando hay docente y horario general.",
                error="Elegí Sí o No.",
            )
            agregar_validacion_lista(
                "=ListaDias",
                f"{col_letra[f'Día Docente {n_doc} Horario {n_h}']}{fila_inicio_carga}:{col_letra[f'Día Docente {n_doc} Horario {n_h}']}{fila_fin_carga}",
                f"Día docente {n_doc}",
                "Se completa automáticamente con el Día del Horario general. Solo modificalo excepcionalmente; debe coincidir con el horario general correspondiente.",
            )
            for campo in [f"Hora Inicio Docente {n_doc} Horario {n_h}", f"Hora Fin Docente {n_doc} Horario {n_h}"]:
                agregar_validacion_lista(
                    "=ListaHoras",
                    f"{col_letra[campo]}{fila_inicio_carga}:{col_letra[campo]}{fila_fin_carga}",
                    f"Cobertura docente {n_doc}",
                    "Dejá vacío para cubrir completo ese Horario general. Completá Inicio y Fin solo si cubre una subfranja.",
                )

    ultima_materia = max(2, len(df_materias_excel) + 1)
    rango_mapa_ctx = f"Listas!$K$2:$N${fila_fin_mapa}"
    rango_codigo_por_ctx = f"Listas!$P$2:$Q${fila_fin_codigo_ctx}"
    bloques_materia = [
        ("Código", "Asignatura", "Carrera / plan"),
        ("Código 2", "Asignatura 2", "Carrera / plan 2"),
        ("Código 3", "Asignatura 3", "Carrera / plan 3"),
    ]

    # Tres validaciones dependientes (una por bloque de materia). Se aplican al rango completo
    # usando una fila relativa para evitar cientos de objetos DataValidation y mantener el Excel liviano.
    for _, nombre_asig, nombre_ctx in bloques_materia:
        la = col_letra[nombre_asig]; lx = col_letra[nombre_ctx]
        dv_ctx = DataValidation(
            type="list",
            formula1=f'=INDIRECT(IFERROR(VLOOKUP(${la}{fila_inicio_carga},{rango_mapa_ctx},2,FALSE),"ListaVacia"))',
            allow_blank=True,
        )
        dv_ctx.error = "La Carrera/plan elegida no corresponde a esta asignatura."
        dv_ctx.errorTitle = "Carrera/plan no compatible"
        dv_ctx.prompt = "La lista muestra únicamente los grupos de carrera/plan posibles para la asignatura de esta fila."
        dv_ctx.promptTitle = "Carrera / plan dependiente"
        dv_ctx.showErrorMessage = True; dv_ctx.showInputMessage = True
        ws.add_data_validation(dv_ctx)
        dv_ctx.add(f"{lx}{fila_inicio_carga}:{lx}{fila_fin_carga}")

    for fila in range(fila_inicio_carga, fila_fin_carga + 1):
        # v142:
        # - Carrera/plan solo se completa sola cuando existe un único grupo conceptual.
        # - Código se completa aunque haya varios grupos, siempre que todos compartan el
        #   mismo código institucional.
        # - Si existen códigos diferentes, el código se resuelve al elegir Carrera/plan.
        for nombre_cod, nombre_asig, nombre_ctx in bloques_materia:
            lc = col_letra[nombre_cod]; la = col_letra[nombre_asig]; lx = col_letra[nombre_ctx]
            ws[f"{lx}{fila}"] = (
                f'=IF({la}{fila}="","",IFERROR(VLOOKUP({la}{fila},{rango_mapa_ctx},4,FALSE),""))'
            )
            # v144: si se eligió Carrera/plan, el código se extrae directamente del
            # prefijo [CÓDIGO]. No se usa el texto largo como clave de VLOOKUP, porque
            # Excel puede fallar con claves >255 caracteres. Si todavía no hay contexto,
            # se conserva el autocompletado por código institucional único de la materia.
            ws[f"{lc}{fila}"] = (
                f'=IF({la}{fila}="","",'
                f'IF({lx}{fila}<>"",'
                f'""&IFERROR(MID({lx}{fila},2,FIND("]",{lx}{fila})-2),'
                f'IFERROR(VLOOKUP({la}{fila},{rango_mapa_ctx},3,FALSE),"")),'
                f'""&IFERROR(VLOOKUP({la}{fila},{rango_mapa_ctx},3,FALSE),"")))'
            )
            ws[f"{lc}{fila}"].number_format = "@"

        # v153: al seleccionar un docente, cada horario general existente queda
        # automáticamente en Sí y el Día Docente replica el Día general. El usuario
        # puede sobrescribir Sí por No o informar Inicio/Fin propios para una subfranja.
        for n_doc in range(1, 6):
            ldoc = col_letra[f"Docente {n_doc}"]
            for n_h in range(1, 6):
                ldia_general = col_letra[f"Día {n_h}"]
                lcubre = col_letra[f"Cubre Horario {n_h} - Docente {n_doc}"]
                ldia_doc = col_letra[f"Día Docente {n_doc} Horario {n_h}"]
                ws[f"{lcubre}{fila}"] = (
                    f'=IF(OR(${ldoc}{fila}="",${ldia_general}{fila}=""),"","Sí")'
                )
                ws[f"{ldia_doc}{fila}"] = (
                    f'=IF(OR(${ldoc}{fila}="",${ldia_general}{fila}="",${lcubre}{fila}="No"),"",${ldia_general}{fila})'
                )

        # Estilo y formatos.
        for col in range(1, len(encabezados) + 1):
            c = ws.cell(row=fila, column=col); c.border = borde_fino
            c.alignment = Alignment(vertical="center", wrap_text=True)
            nombre = encabezados[col - 1]
            if nombre.startswith("Código"):
                c.fill = relleno_formula
            elif nombre.startswith("Carrera / plan"):
                c.fill = relleno_dependiente
            elif nombre.startswith("Cubre Horario"):
                c.fill = relleno_dependiente
            else:
                c.fill = relleno_entrada
        for nombre in encabezados:
            if nombre.startswith("Hora Inicio") or nombre.startswith("Hora Fin"):
                ws.cell(row=fila, column=col_idx[nombre]).number_format = "hh:mm"

    ultima_col = get_column_letter(len(encabezados))
    ws.auto_filter.ref = f"A{fila_encabezado_carga}:{ultima_col}{fila_fin_carga}"

    # Comentarios de uso.
    for nombre_cod, nombre_asig, nombre_ctx in bloques_materia:
        ws.cell(row=fila_encabezado_carga, column=col_idx[nombre_cod]).comment = Comment(
            "Se completa automáticamente si la Asignatura tiene un único código institucional. Si hay códigos distintos según el grupo de planes, se completa al elegir Carrera / plan.", "Sistema"
        )
        ws.cell(row=fila_encabezado_carga, column=col_idx[nombre_ctx]).comment = Comment(
            "Solo muestra grupos Carrera/plan compatibles con la Asignatura. Cada alternativa indica su Código. Si existe un único grupo se completa automáticamente; si hay varios, elegí el correcto.",
            "Sistema",
        )
    ws.cell(row=fila_encabezado_carga, column=col_idx["Opción Curricular"]).comment = Comment(
        "Obligatoria solamente para Optativas/Electivas. Para materias comunes dejá vacío.", "Sistema"
    )
    for n_doc in range(1, 6):
        ws.cell(row=fila_encabezado_carga, column=col_idx[f"Docente {n_doc}"]).comment = Comment(
            "El cargo se determina automáticamente desde la designación activa. Al elegir el docente, los horarios generales existentes quedan por defecto en Sí.",
            "Sistema",
        )
        for n_h in range(1, 6):
            ws.cell(row=fila_encabezado_carga, column=col_idx[f"Cubre Horario {n_h} - Docente {n_doc}"]).comment = Comment(
                "Sí: el docente cubre este horario general. No: no lo cubre. Si queda Sí y no cargás horas propias, cubre completo el Horario general correspondiente.",
                "Sistema",
            )
            ws.cell(row=fila_encabezado_carga, column=col_idx[f"Día Docente {n_doc} Horario {n_h}"]).comment = Comment(
                "Se completa automáticamente con el Día del Horario general correspondiente. Para cobertura parcial, normalmente solo necesitás completar Hora Inicio y Hora Fin.",
                "Sistema",
            )

    # Instrucciones legibles dentro del archivo.
    instrucciones = [
        ("Carga rápida de comisiones — v231", True),
        ("1. Elegí Asignatura. Si tiene un único código institucional, el Código se completa automáticamente aunque esté en varios planes.", False),
        ("2. Carrera / plan está al lado de cada Asignatura, muestra solo grupos compatibles y cada alternativa comienza con [CÓDIGO].", False),
        ("3. Si hay un único grupo conceptual, Carrera / plan se completa sola. Si hay varios, elegí el correcto; el Código se extrae directamente del prefijo [CÓDIGO], incluso en grupos con muchas carreras.", False),
        ("4. Código/Asignatura 2 y 3 son opcionales para comisiones multicódigo de materias comunes.", False),
        ("5. Opción Curricular se usa solamente para Optativas/Electivas.", False),
        ("6. Definí hasta 5 bloques Día/Hora Inicio/Hora Fin generales de la comisión.", False),
        ("7. Al elegir un Docente, cada Horario general existente queda automáticamente con Cubre Horario = Sí y el Día Docente se completa con el día de la comisión.", False),
        ("8. Si el docente NO cubre uno de los días/horarios de la comisión, cambiá solamente Cubre Horario a No.", False),
        ("9. Si Cubre Horario queda en Sí y dejás Hora Inicio/Fin Docente vacías, cubre completo ese horario. Si cubre solo una parte, completá Inicio y Fin; la franja debe quedar dentro del horario general.", False),
        ("10. Los Excel anteriores siguen siendo compatibles: si no existen columnas Cubre Horario, se conserva la lógica previa de cobertura completa o franjas personalizadas.", False),
        ("11. El cargo del docente se determina automáticamente desde su designación activa al cargar.", False),
        ("12. Guardá el archivo y subilo completo desde Comisiones > Carga rápida. También podés copiar y pegar la hoja Carga rápida si preferís el método manual.", False),
    ]
    for i, (txt, titulo) in enumerate(instrucciones, start=1):
        c = ws_instrucciones.cell(row=i, column=1, value=txt)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if titulo:
            c.font = Font(bold=True, size=14); c.fill = relleno_referencia
    ws_instrucciones.column_dimensions["A"].width = 125

    # Contexto institucional en hojas auxiliares.
    ws_materias["K1"] = "Universidad"; ws_materias["K2"] = str(fuente.institucion_nombre)
    ws_docentes["I1"] = "Departamento"; ws_docentes["I2"] = fuente.departamento_nombre; ws_docentes["I3"] = "Período"
    try:
        df_periodos_excel = fuente.periodos()
        fila_periodo_excel = (
            df_periodos_excel[df_periodos_excel["id"] == int(periodo_id)].iloc[0].to_dict()
            if periodo_id is not None and not df_periodos_excel.empty
            and not df_periodos_excel[df_periodos_excel["id"] == int(periodo_id)].empty else None
        )
    except Exception:
        fila_periodo_excel = None
    ws_docentes["I4"] = str(fila_periodo_excel.get("nombre", "")) if fila_periodo_excel else "Sin período actual"
    for hoja, c1, c2 in [(ws_materias, "K1", "K2"), (ws_docentes, "I1", "I2")]:
        hoja[c1].fill = relleno_referencia; hoja[c1].font = Font(bold=True); hoja[c2].alignment = Alignment(wrap_text=True)
    ws_docentes["I3"].fill = relleno_referencia; ws_docentes["I3"].font = Font(bold=True); ws_docentes["I4"].alignment = Alignment(wrap_text=True)
    ws_docentes.column_dimensions["I"].width = 36; ws_materias.column_dimensions["K"].width = 36

    ws_listas.sheet_state = "hidden"
    try:
        wb.calculation.calcMode = "auto"; wb.calculation.fullCalcOnLoad = True; wb.calculation.forceFullCalc = True
    except Exception:
        pass

    salida = BytesIO(); wb.save(salida); salida.seek(0); return salida.getvalue()


def contexto_excel_materia_v175(codigo, asignatura, candidatos, carrera="", plan="", escuela=""):
    """``deptit_refactor/domain/materias.py`` l. 373: la misma etiqueta Carrera/plan del Excel modelo."""
    codigo_n = R.normalizar_codigo_materia(codigo)
    asig_n = R.normalizar_clave(asignatura)
    matches = [r for r in candidatos if R.normalizar_codigo_materia(r.get("Código", "")) == codigo_n
               and R.normalizar_clave(r.get("Asignatura", "")) == asig_n]
    if not matches:
        matches = [r for r in candidatos if R.normalizar_clave(r.get("Asignatura", "")) == asig_n]
    if not matches:
        base = " — ".join([x for x in [R.limpiar_texto_tabla(carrera), R.limpiar_texto_tabla(plan),
                                       R.limpiar_texto_tabla(escuela)] if x])
        return f"[{R.limpiar_texto_tabla(codigo).upper()}] {base}".strip() if codigo else base
    buscado = R.normalizar_clave(" ".join([str(carrera or ""), str(plan or ""), str(escuela or "")]))
    if buscado:
        def score(r):
            ctx = R.normalizar_clave(r.get("Contexto para carga rápida", ""))
            partes = [R.normalizar_clave(x) for x in [carrera, plan, escuela] if R.normalizar_clave(x)]
            return sum(1 for p in partes if p and p in ctx)
        matches = sorted(matches, key=score, reverse=True)
    return R.limpiar_texto_tabla(matches[0].get("Contexto para carga rápida", ""))


def generar_excel_comisiones_periodo_completado_v175(fuente: "FuenteExcel", periodo_id) -> bytes:
    """l. 37564: mismo libro de Carga rápida, con las comisiones del período ya cargadas (no modifica datos)."""
    from openpyxl import load_workbook

    L = fuente.L
    df_com = L.comisiones(periodo_id=periodo_id, solo_activas=False)
    cantidad = 0 if df_com is None or df_com.empty else len(df_com)
    modelo_bytes = generar_excel_modelo_carga_rapida_comisiones(
        fuente, periodo_id, filas_modelo=max(50, cantidad + 25)
    )
    wb = load_workbook(BytesIO(modelo_bytes))
    ws = wb["Carga rápida"]

    # La fila de encabezados está después de las semillas ocultas y puede variar.
    fila_header = None
    for rr in range(1, min(ws.max_row, 3000) + 1):
        valores = [str(ws.cell(rr, cc).value or "").strip() for cc in range(1, min(ws.max_column, 12) + 1)]
        if "Código" in valores and "Asignatura" in valores and "Comisión" in valores:
            fila_header = rr
            break
    if fila_header is None:
        raise ValueError("No se pudo localizar la fila de encabezados del Excel integral.")

    encabezados = [str(ws.cell(fila_header, c).value or "").strip() for c in range(1, ws.max_column + 1)]
    col = {h: i + 1 for i, h in enumerate(encabezados) if h}

    # Referencias visibles del propio modelo para que Carrera/plan quede exactamente
    # igual que en el Excel descargado desde Carga rápida.
    candidatos_materia = []
    try:
        wsm = wb["Materias"]
        hmat = [str(wsm.cell(1, c).value or "").strip() for c in range(1, wsm.max_column + 1)]
        for rr in range(2, wsm.max_row + 1):
            rec = {hmat[c - 1]: wsm.cell(rr, c).value for c in range(1, len(hmat) + 1) if hmat[c - 1]}
            if R.limpiar_texto_tabla(rec.get("Asignatura", "")):
                candidatos_materia.append(rec)
    except Exception:
        candidatos_materia = []

    advertencias = []
    fila_salida = fila_header + 1
    if df_com is not None and not df_com.empty:
        for _, com in df_com.sort_values(["escuela", "codigo_materia", "asignatura", "nombre_comision"], kind="stable").iterrows():
            cid = int(com.get("id"))
            datos = {
                "Opción Curricular": "",
                "Comisión": R.limpiar_texto_tabla(com.get("nombre_comision", "")),
                "Turno": R.limpiar_texto_tabla(com.get("turno", "")),
                "Modalidad": R.limpiar_texto_tabla(com.get("modalidad", "")),
                "Sede": R.limpiar_texto_tabla(com.get("sede", "")),
            }

            # Opción curricular exacta cuando corresponda.
            try:
                oid = com.get("opcion_curricular_id")
                if oid is not None and not pd.isna(oid) and str(oid).strip() != "":
                    op = L.opcion_curricular_v120(int(oid))
                    datos["Opción Curricular"] = R.etiqueta_opcion_curricular_v120(op) if op else R.limpiar_texto_tabla(com.get("materia_especifica", ""))
                elif R.limpiar_texto_tabla(com.get("materia_especifica", "")):
                    datos["Opción Curricular"] = R.limpiar_texto_tabla(com.get("materia_especifica", ""))
            except Exception:
                datos["Opción Curricular"] = R.limpiar_texto_tabla(com.get("materia_especifica", ""))

            # Materias/códigos exactos de la comisión. Se agrupan las apariciones del
            # mismo código+asignatura entre planes para no confundirlas con multicódigo.
            materias = []
            try:
                reps = L.materias_conceptuales_comision_v122(cid)
            except Exception:
                reps = []
            if not reps:
                try:
                    reps = [int(com.get("materia_id"))]
                except Exception:
                    reps = []
            try:
                links = fuente.vinculos_comision(cid)
            except Exception:
                links = pd.DataFrame()

            for rep in reps[:3]:
                info = L.materia_comision(rep) or {}
                codigo = R.limpiar_texto_tabla(info.get("codigo", ""))
                asignatura = R.limpiar_texto_tabla(info.get("asignatura", ""))
                carrera = R.limpiar_texto_tabla(info.get("carrera", ""))
                plan = R.limpiar_texto_tabla(info.get("plan_version", ""))
                escuela = R.limpiar_texto_tabla(info.get("escuela", ""))
                if isinstance(links, pd.DataFrame) and not links.empty:
                    clave_cod = R.normalizar_codigo_materia(codigo)
                    clave_asig = R.normalizar_clave(asignatura)
                    gl = links[
                        links.get("codigo_snapshot", pd.Series(index=links.index, dtype=str)).fillna("").astype(str).map(R.normalizar_codigo_materia).eq(clave_cod)
                        & links.get("asignatura_snapshot", pd.Series(index=links.index, dtype=str)).fillna("").astype(str).map(R.normalizar_clave).eq(clave_asig)
                    ].copy()
                    if not gl.empty:
                        codigo = R.limpiar_texto_tabla(gl.iloc[0].get("codigo_snapshot", "")) or codigo
                        asignatura = R.limpiar_texto_tabla(gl.iloc[0].get("asignatura_snapshot", "")) or asignatura
                        carrera = R.deptit_join_unicos(gl.get("carrera_snapshot", pd.Series(dtype=str)), sep=" / ") or carrera
                        plan = R.deptit_join_unicos(gl.get("plan_version_snapshot", pd.Series(dtype=str)), sep=" / ") or plan
                        escuela = R.deptit_join_unicos(gl.get("escuela_snapshot", pd.Series(dtype=str)), sep=" / ") or escuela
                materias.append({"codigo": codigo, "asignatura": asignatura, "carrera": carrera, "plan": plan, "escuela": escuela})

            for n, mat in enumerate(materias, start=1):
                suf = "" if n == 1 else f" {n}"
                datos[f"Código{suf}"] = mat["codigo"]
                datos[f"Asignatura{suf}"] = mat["asignatura"]
                datos[f"Carrera / plan{suf}"] = contexto_excel_materia_v175(
                    mat["codigo"], mat["asignatura"], candidatos_materia,
                    mat["carrera"], mat["plan"], mat["escuela"],
                )

            # Horarios generales.
            df_h = L.horarios_comision(cid)
            if df_h is None:
                df_h = pd.DataFrame()
            df_h = df_h.head(5).copy()
            for j, (_, h) in enumerate(df_h.iterrows(), start=1):
                datos[f"Día {j}"] = R.limpiar_texto_tabla(h.get("dia", ""))
                datos[f"Hora Inicio {j}"] = R.normalizar_hora_export_v175(h.get("hora_inicio", ""))
                datos[f"Hora Fin {j}"] = R.normalizar_hora_export_v175(h.get("hora_fin", ""))
            try:
                total_h = len(L.horarios_comision(cid))
                if total_h > 5:
                    advertencias.append(f"Comisión {datos['Comisión'] or cid}: tiene {total_h} horarios; el modelo integral admite 5.")
            except Exception:
                pass

            # Docentes y cobertura real por cada horario general.
            df_a = L.asignaciones_comision(cid)
            if df_a is None:
                df_a = pd.DataFrame()
            if not df_a.empty:
                df_a = df_a.copy()
                df_a["_orden_estado"] = df_a.get("estado", pd.Series(index=df_a.index, dtype=str)).fillna("Activa").astype(str).str.strip().str.casefold().map(lambda x: 0 if x == "activa" else 1)
                df_a = df_a.sort_values(["_orden_estado", "docente"], kind="stable").drop(columns=["_orden_estado"], errors="ignore")
            if len(df_a) > 5:
                advertencias.append(f"Comisión {datos['Comisión'] or cid}: tiene {len(df_a)} docentes; el modelo integral admite 5.")
            for n_doc, (_, a) in enumerate(df_a.head(5).iterrows(), start=1):
                datos[f"Docente {n_doc}"] = R.limpiar_texto_tabla(a.get("docente", "")) or R.limpiar_texto_tabla(a.get("cuil", ""))
                try:
                    aid = int(a.get("id"))
                    df_real = L.horarios_reales_asignacion(aid)
                except Exception:
                    df_real = pd.DataFrame()
                for n_h, (_, h) in enumerate(df_h.iterrows(), start=1):
                    cobertura = pd.DataFrame()
                    hid = h.get("id")
                    if isinstance(df_real, pd.DataFrame) and not df_real.empty:
                        if hid is not None and "horario_comision_id" in df_real.columns:
                            cobertura = df_real[pd.to_numeric(df_real["horario_comision_id"], errors="coerce").eq(pd.to_numeric(pd.Series([hid]), errors="coerce").iloc[0])].copy()
                        if cobertura.empty:
                            dia_h = R.normalizar_clave(h.get("dia", ""))
                            cobertura = df_real[df_real.get("dia", pd.Series(index=df_real.index, dtype=str)).fillna("").astype(str).map(R.normalizar_clave).eq(dia_h)].copy()
                    if cobertura.empty:
                        datos[f"Cubre Horario {n_h} - Docente {n_doc}"] = "No"
                        datos[f"Día Docente {n_doc} Horario {n_h}"] = ""
                        datos[f"Hora Inicio Docente {n_doc} Horario {n_h}"] = ""
                        datos[f"Hora Fin Docente {n_doc} Horario {n_h}"] = ""
                    else:
                        datos[f"Cubre Horario {n_h} - Docente {n_doc}"] = "Sí"
                        datos[f"Día Docente {n_doc} Horario {n_h}"] = R.limpiar_texto_tabla(cobertura.iloc[0].get("dia", h.get("dia", "")))
                        inicios = [R.normalizar_hora_export_v175(x) for x in cobertura.get("hora_inicio", pd.Series(dtype=str)).tolist() if R.normalizar_hora_export_v175(x)]
                        fines = [R.normalizar_hora_export_v175(x) for x in cobertura.get("hora_fin", pd.Series(dtype=str)).tolist() if R.normalizar_hora_export_v175(x)]
                        datos[f"Hora Inicio Docente {n_doc} Horario {n_h}"] = min(inicios) if inicios else R.normalizar_hora_export_v175(h.get("hora_inicio", ""))
                        datos[f"Hora Fin Docente {n_doc} Horario {n_h}"] = max(fines) if fines else R.normalizar_hora_export_v175(h.get("hora_fin", ""))

            for nombre, valor in datos.items():
                if nombre in col:
                    celda = ws.cell(fila_salida, col[nombre])
                    celda.value = valor
                    if nombre.startswith("Código"):
                        celda.number_format = "@"
            fila_salida += 1

    # Identificación clara del período exportado.
    try:
        dfp = fuente.periodo_nombre_estado(int(periodo_id))
        periodo_nombre = str(dfp.iloc[0].get("nombre") or periodo_id) if not dfp.empty else str(periodo_id)
        periodo_estado = str(dfp.iloc[0].get("estado") or "") if not dfp.empty else ""
    except Exception:
        periodo_nombre, periodo_estado = str(periodo_id), ""
    try:
        wsi = wb["Instrucciones"]
        fila = wsi.max_row + 2
        wsi.cell(fila, 1, value=f"EXPORTACIÓN COMPLETADA DEL PERÍODO: {periodo_nombre} ({periodo_estado})")
        wsi.cell(fila, 1).font = wsi.cell(1, 1).font.copy(bold=True)
        wsi.cell(fila + 1, 1, value="Las filas de la hoja Carga rápida fueron completadas automáticamente con las comisiones registradas en el sistema para el período seleccionado.")
        if advertencias:
            wsi.cell(fila + 3, 1, value="Advertencias de capacidad del formato:")
            for i, adv in enumerate(advertencias, start=fila + 4):
                wsi.cell(i, 1, value=f"• {adv}")
    except Exception:
        pass

    salida = BytesIO()
    wb.save(salida)
    salida.seek(0)
    return salida.getvalue()
