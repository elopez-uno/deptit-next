"""GENERADO por tools_generar_complemento_carga_integral.py -- NO EDITAR A MANO.

Texto literal del entry certificado B13-FIX02 (app_postgresql_refactor_b13fix02_uat_fixes.py, sha256 95691fdf48c1edd393daf60bf435d6452b2fa8e95f6dcb7a2254cea8138d3363): definiciones de la
Carga rápida integral (E4-09) que no estan en el motor de Analisis, 30 bloques en el orden
del entry.  Se ejecuta DESPUES de ``analisis/motor/certificado.py`` en el mismo namespace del request
(``integraciones.carga_integral``); nunca a nivel modulo.
"""
# flake8: noqa
# fmt: off

# --- entry (literal)
ESTADOS_DESIGNACION = ["Activa", "Finalizada", "Suspendida"]
# --- entry (literal)
HORAS_OPCIONES = [10, 20, 30, 40, 50]

# --- entry l. 4349-4351
def nombre_periodo(anio, semestre):
    from analisis.motor.ref.extracted_batch01.periodos import nombre_periodo as _b01_core_nombre_periodo
    return _b01_core_nombre_periodo(anio, semestre)


# --- entry l. 7789-7830
def docente_existe(cuil):
    clave = _clave_cuil(cuil)
    if not clave:
        return pd.DataFrame()
    conn = get_conn()
    if USE_POSTGRESQL:
        sql = """
            SELECT cuil, apellido, nombres, nombre, legajo, titulo,
                   COALESCE(titulo_posgrado, '') AS titulo_posgrado,
                   antiguedad_anios,
                   COALESCE(nivel_posgrado_salarial, '') AS nivel_posgrado_salarial,
                   COALESCE(email, '') AS email,
                   COALESCE(telefono, '') AS telefono,
                   COALESCE(ref_legajo_fisico, '') AS ref_legajo_fisico,
                   COALESCE(tipo_docente, 'Propio') AS tipo_docente,
                   COALESCE(estado, 'Activo') AS estado,
                   COALESCE(observaciones, '') AS observaciones
            FROM docentes
            WHERE regexp_replace(COALESCE(cuil, ''), '[^0-9]', '', 'g') = ?
            ORDER BY id
            LIMIT 1
        """
    else:
        sql = """
            SELECT cuil, apellido, nombres, nombre, legajo, titulo,
                   COALESCE(titulo_posgrado, '') AS titulo_posgrado,
                   antiguedad_anios,
                   COALESCE(nivel_posgrado_salarial, '') AS nivel_posgrado_salarial,
                   COALESCE(email, '') AS email,
                   COALESCE(telefono, '') AS telefono,
                   COALESCE(ref_legajo_fisico, '') AS ref_legajo_fisico,
                   COALESCE(tipo_docente, 'Propio') AS tipo_docente,
                   COALESCE(estado, 'Activo') AS estado,
                   COALESCE(observaciones, '') AS observaciones
            FROM docentes
            WHERE REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(cuil, ''), '-', ''), ' ', ''), '.', ''), '/', '') = ?
            ORDER BY id
            LIMIT 1
        """
    df = pd.read_sql(sql, conn, params=[clave])
    conn.close()
    return df


# --- entry l. 7833-7835
def _mezclar_docente_existente_excel_v247(row, actual):
    from integraciones.carga_integral_motor.ref.domain.docentes import _mezclar_docente_existente_excel_v247 as _b05_core__mezclar_docente_existente_excel_v247
    return _b05_core__mezclar_docente_existente_excel_v247(row, actual)


# --- entry l. 16543-16545
def normalizar_columna_generica(col):
    from analisis.motor.ref.extracted_batch01.otros import normalizar_columna_generica as _b01_core_normalizar_columna_generica
    return _b01_core_normalizar_columna_generica(col)


# --- entry l. 16567-16611
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
        elif clave in ["titulo_posgrado", "titulo_de_posgrado", "título_posgrado", "posgrado", "titulo_postgrado", "postgrado"]:
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
    columnas = ["cuil", "apellido", "nombres", "docente", "legajo", "titulo", "titulo_posgrado", "antiguedad_anios", "nivel_posgrado_salarial", "email", "telefono", "ref_legajo_fisico", "estado", "observaciones"]
    for col in columnas:
        if col not in df.columns:
            df[col] = ""
    return df[columnas]


# --- entry l. 16614-16616
def separar_docente_en_apellido_nombres(docente):
    from analisis.motor.ref.extracted_batch04.identidad import separar_docente_en_apellido_nombres as _b04_core_separar_docente_en_apellido_nombres
    return _b04_core_separar_docente_en_apellido_nombres(docente)


# --- entry l. 16675-16709
def normalizar_columnas_designaciones_pegadas(df):
    renombres = {}
    for col in df.columns:
        clave = normalizar_columna_generica(col)
        if clave in ["periodo", "periodo_nombre", "semestre"]:
            renombres[col] = "periodo"
        elif clave in ["cuil", "cuit", "dni_cuil"]:
            renombres[col] = "cuil"
        elif clave in ["cargo"]:
            renombres[col] = "cargo"
        elif clave in ["dedicacion", "dedicación"]:
            renombres[col] = "dedicacion"
        elif clave in ["horas", "hs", "cantidad_horas"]:
            renombres[col] = "horas"
        elif clave in ["tipo_designacion", "tipo_de_designacion", "tipo", "designacion", "designación"]:
            renombres[col] = "tipo_designacion"
        elif clave in ["numero_resolucion", "numero_de_resolucion", "n_resolucion", "nro_resolucion", "resolucion", "resolución", "n_de_resolucion"]:
            renombres[col] = "numero_resolucion"
        elif clave in ["ad_honorem", "adhonorem", "ad_hon"]:
            renombres[col] = "ad_honorem"
        elif clave in ["fecha_desde", "desde", "fecha_inicio", "inicio"]:
            renombres[col] = "fecha_desde"
        elif clave in ["fecha_hasta", "hasta", "fecha_fin", "fin"]:
            renombres[col] = "fecha_hasta"
        elif clave in ["estado", "estado_designacion"]:
            renombres[col] = "estado"
        elif clave in ["observaciones", "obs", "observacion"]:
            renombres[col] = "observaciones"

    df = df.rename(columns=renombres)
    columnas = ["periodo", "cuil", "cargo", "dedicacion", "horas", "tipo_designacion", "numero_resolucion", "ad_honorem", "fecha_desde", "fecha_hasta", "estado", "observaciones"]
    for col in columnas:
        if col not in df.columns:
            df[col] = ""
    return df[columnas]


# --- entry l. 17171-17198
def _normalizar_dataframe_docentes_integral(df):
    """Normaliza la hoja Docentes del Excel integral."""
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "cuil", "apellido", "nombres", "docente", "legajo", "titulo",
            "titulo_posgrado", "antiguedad_anios", "nivel_posgrado_salarial",
            "email", "telefono", "ref_legajo_fisico", "estado", "observaciones",
        ])

    df = df.copy().dropna(how="all")
    if df.empty:
        return pd.DataFrame()
    df = normalizar_columnas_docentes_pegados(df)
    for col in df.columns:
        df[col] = df[col].apply(limpiar_texto_tabla)
    df["cuil"] = df["cuil"].apply(limpiar_cuil)

    for idx, row in df.iterrows():
        if not row.get("apellido", "") and not row.get("nombres", "") and row.get("docente", ""):
            apellido, nombres = separar_docente_en_apellido_nombres(row.get("docente", ""))
            df.at[idx, "apellido"] = apellido
            df.at[idx, "nombres"] = nombres

    # v247: una celda Estado vacía debe seguir siendo realmente vacía en la hoja
    # normalizada. Para docentes nuevos se aplica Activo como default durante la
    # validación; para docentes existentes, vacío significa "conservar el actual".
    df = df[df.apply(lambda r: any(limpiar_texto_tabla(v) for v in r.tolist()), axis=1)].copy()
    return df.reset_index(drop=True)


# --- entry l. 17201-17252
def _normalizar_dataframe_designaciones_integral(df, periodo_default=None):
    """Normaliza la hoja Designaciones del Excel integral."""
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "periodo", "cuil", "cargo", "dedicacion", "horas",
            "tipo_designacion", "numero_resolucion", "ad_honorem", "fecha_desde", "fecha_hasta",
            "estado", "observaciones",
        ])

    df = df.copy().dropna(how="all")
    if df.empty:
        return pd.DataFrame()
    df = normalizar_columnas_designaciones_pegadas(df)
    for col in df.columns:
        df[col] = df[col].apply(limpiar_texto_tabla)

    # El modelo deja el período precargado en todas las filas. Se eliminan las
    # filas realmente vacías antes de aplicar valores por defecto.
    campos_carga = [
        "cuil", "cargo", "dedicacion", "horas", "tipo_designacion", "numero_resolucion",
        "ad_honorem", "fecha_desde", "fecha_hasta", "estado", "observaciones",
    ]
    mascara_con_datos = df[campos_carga].apply(
        lambda fila: any(limpiar_texto_tabla(valor) for valor in fila.tolist()), axis=1
    )
    df = df[mascara_con_datos].copy()
    if df.empty:
        return pd.DataFrame(columns=[
            "periodo", "cuil", "cargo", "dedicacion", "horas",
            "tipo_designacion", "numero_resolucion", "ad_honorem", "fecha_desde", "fecha_hasta",
            "estado", "observaciones",
        ])

    df["cuil"] = df["cuil"].apply(limpiar_cuil)
    df["cargo"] = df["cargo"].replace("", "JTP")
    df["dedicacion"] = df["dedicacion"].replace("", "Simple")
    # v160: Horas es un dato derivado, nunca una segunda carga manual.
    df["horas"] = df["dedicacion"].apply(lambda d: horas_segun_dedicacion(d, 10)).astype(int)
    df["tipo_designacion"] = df["tipo_designacion"].replace("", "Interino")
    df["ad_honorem"] = df["ad_honorem"].replace({
        "": "No", "Si": "Sí", "SI": "Sí", "si": "Sí", "sí": "Sí",
        "TRUE": "Sí", "True": "Sí", "true": "Sí", "1": "Sí",
        "FALSE": "No", "False": "No", "false": "No", "0": "No",
    })

    # v230: no se usan defaults del período abierto. Si faltan fechas, la revisión
    # lo marca como error. Período y Estado se derivan siempre de Desde/Hasta.
    df["fecha_desde"] = df["fecha_desde"].apply(lambda x: _fecha_iso_integral(x, ""))
    df["fecha_hasta"] = df["fecha_hasta"].apply(lambda x: _fecha_iso_integral(x, ""))
    df = _aplicar_periodo_estado_automaticos_v230(df)
    df = df[df.apply(lambda r: any(limpiar_texto_tabla(v) for v in r.tolist()), axis=1)].copy()
    return df.reset_index(drop=True)


# --- entry l. 17255-17285
def leer_excel_integral_docentes_designaciones(archivo, periodo_default=None):
    """Lee las hojas Docentes y Designaciones de un mismo archivo Excel."""
    if archivo is None:
        return pd.DataFrame(), pd.DataFrame(), []

    contenido = archivo.getvalue() if hasattr(archivo, "getvalue") else archivo
    libro = pd.ExcelFile(BytesIO(contenido), engine="openpyxl")
    mapa_hojas = {normalizar_columna_generica(nombre): nombre for nombre in libro.sheet_names}

    hoja_docentes = mapa_hojas.get("docentes")
    hoja_designaciones = mapa_hojas.get("designaciones")
    if hoja_docentes is None:
        raise ValueError("El archivo debe contener una hoja llamada Docentes.")
    if hoja_designaciones is None:
        raise ValueError("El archivo debe contener una hoja llamada Designaciones.")

    df_docentes = pd.read_excel(libro, sheet_name=hoja_docentes, dtype=object)
    df_designaciones = pd.read_excel(libro, sheet_name=hoja_designaciones, dtype=object)
    df_docentes = _normalizar_dataframe_docentes_integral(df_docentes)
    df_designaciones = _normalizar_dataframe_designaciones_integral(df_designaciones, periodo_default)

    advertencias = []
    if df_docentes.empty and df_designaciones.empty:
        advertencias.append("Las hojas Docentes y Designaciones no contienen filas para procesar.")
    elif df_designaciones.empty:
        advertencias.append("La hoja Designaciones está vacía: se procesarán únicamente docentes.")
    elif df_docentes.empty:
        advertencias.append(
            "La hoja Docentes está vacía: las designaciones solo podrán cargarse para CUIL ya existentes en la base maestra."
        )
    return df_docentes, df_designaciones, advertencias


# --- entry l. 17288-17290
def _valor_canonico_lista(valor, opciones, default=""):
    from analisis.motor.ref.common.normalization import _valor_canonico_lista as _b05_core__valor_canonico_lista
    return _b05_core__valor_canonico_lista(valor, opciones, default)


# --- entry l. 17293-17295
def _normalizar_ad_honorem_integral(valor):
    from analisis.motor.ref.common.normalization import _normalizar_ad_honorem_integral as _b05_core__normalizar_ad_honorem_integral
    return _b05_core__normalizar_ad_honorem_integral(valor)


# --- entry l. 17298-17300
def _fecha_iso_integral(valor, fallback=""):
    from analisis.motor.ref.common.dates import _fecha_iso_integral as _b05_core__fecha_iso_integral
    return _b05_core__fecha_iso_integral(valor, fallback)


# --- entry l. 17305-17330
def _periodos_ordenados_fechas_v230(df_periodos=None):
    """Períodos del departamento ordenados cronológicamente y con fechas válidas.

    La carga rápida ya no confía en un Período/Estado escrito por el usuario:
    ambos se derivan de Fecha desde / Fecha hasta y del último período registrado.
    """
    try:
        base = df_periodos.copy() if isinstance(df_periodos, pd.DataFrame) else get_periodos().copy()
    except Exception:
        base = pd.DataFrame()
    if base is None or base.empty:
        return pd.DataFrame()
    for col in ["id", "nombre", "anio", "semestre", "fecha_inicio", "fecha_fin"]:
        if col not in base.columns:
            base[col] = ""
    out = base.copy()
    out["_inicio_v230"] = pd.to_datetime(out["fecha_inicio"], errors="coerce")
    out["_fin_v230"] = pd.to_datetime(out["fecha_fin"], errors="coerce")
    out["_anio_v230"] = pd.to_numeric(out["anio"], errors="coerce").fillna(0).astype(int)
    out["_sem_v230"] = pd.to_numeric(out["semestre"], errors="coerce").fillna(0).astype(int)
    out["_id_v230"] = pd.to_numeric(out["id"], errors="coerce").fillna(0).astype(int)
    out = out[out["_inicio_v230"].notna() & out["_fin_v230"].notna()].copy()
    if out.empty:
        return out
    out = out.sort_values(["_anio_v230", "_sem_v230", "_id_v230", "_inicio_v230"], kind="stable")
    return out.reset_index(drop=True)


# --- entry l. 17333-17391
def _inferir_periodo_estado_fechas_v230(fecha_desde, fecha_hasta, df_periodos=None):
    """Detecta el período por solapamiento de fechas y deriva Activa/Finalizada.

    Si un rango abarca más de un período (caso típico de una concursada con fechas
    reales plurianuales), se toma el último período cronológico registrado que esté
    cubierto por la vigencia. De ese modo una concursada vigente hoy cae en el
    período actual, sin alterar sus fechas reales.
    """
    fd = _fecha_iso_integral(fecha_desde, "")
    fh = _fecha_iso_integral(fecha_hasta, "")
    if not fd or not fh or fd > fh:
        return {"periodo": None, "periodo_id": None, "periodo_nombre": "", "estado": "", "coincidencias": 0}
    try:
        dfd = pd.Timestamp(fd)
        fhd = pd.Timestamp(fh)
    except Exception:
        return {"periodo": None, "periodo_id": None, "periodo_nombre": "", "estado": "", "coincidencias": 0}
    per = _periodos_ordenados_fechas_v230(df_periodos)
    if per.empty:
        return {"periodo": None, "periodo_id": None, "periodo_nombre": "", "estado": "", "coincidencias": 0}
    candidatos = per[(dfd <= per["_fin_v230"]) & (fhd >= per["_inicio_v230"])].copy()
    if candidatos.empty:
        return {"periodo": None, "periodo_id": None, "periodo_nombre": "", "estado": "", "coincidencias": 0}
    elegido = candidatos.iloc[-1].to_dict()  # último período cronológico superpuesto
    ultimo = per.iloc[-1].to_dict()
    try:
        pid = int(elegido.get("id"))
    except Exception:
        pid = None
    try:
        ultimo_id = int(ultimo.get("id"))
    except Exception:
        ultimo_id = None
    # v237: ser el último período no alcanza. La propia vigencia y la fecha fin
    # del período también deben seguir vigentes hoy.
    try:
        fin_periodo_elegido = pd.Timestamp(elegido.get("_fin_v230")).date()
    except Exception:
        fin_periodo_elegido = None
    try:
        fin_designacion = fhd.date()
    except Exception:
        fin_designacion = None
    hoy_v237 = date.today()
    vigente_hoy = (
        pid is not None
        and ultimo_id is not None
        and pid == ultimo_id
        and (fin_periodo_elegido is None or fin_periodo_elegido >= hoy_v237)
        and (fin_designacion is None or fin_designacion >= hoy_v237)
    )
    estado = "Activa" if vigente_hoy else "Finalizada"
    return {
        "periodo": elegido,
        "periodo_id": pid,
        "periodo_nombre": limpiar_texto_tabla(elegido.get("nombre", "")),
        "estado": estado,
        "coincidencias": int(len(candidatos)),
    }


# --- entry l. 17394-17406
def _aplicar_periodo_estado_automaticos_v230(df, df_periodos=None):
    base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if base.empty:
        return base
    per = _periodos_ordenados_fechas_v230(df_periodos)
    periodos_out, estados_out = [], []
    for _, row in base.iterrows():
        inf = _inferir_periodo_estado_fechas_v230(row.get("fecha_desde", ""), row.get("fecha_hasta", ""), per)
        periodos_out.append(inf.get("periodo_nombre", ""))
        estados_out.append(inf.get("estado", ""))
    base["periodo"] = periodos_out
    base["estado"] = estados_out
    return base


# --- entry l. 17408-17693
def analizar_carga_integral_docentes_designaciones(df_docentes, df_designaciones, periodo_default=None):
    """Valida el Excel integral sin modificar la base de datos."""
    try:
        df_base_docentes = get_docentes().copy()
    except Exception:
        df_base_docentes = pd.DataFrame()
    for col in ["cuil", "apellido", "nombres", "nombre", "nombre_completo"]:
        if col not in df_base_docentes.columns:
            df_base_docentes[col] = ""
    base_docentes = {}
    for _, row in df_base_docentes.iterrows():
        clave = _clave_cuil(row.get("cuil", ""))
        if clave and clave not in base_docentes:
            base_docentes[clave] = row.to_dict()

    try:
        df_periodos_base = get_periodos().copy()
    except Exception:
        df_periodos_base = pd.DataFrame()
    periodos = {}
    if not df_periodos_base.empty:
        for _, row in df_periodos_base.iterrows():
            nombre = limpiar_texto_tabla(row.get("nombre", ""))
            if nombre:
                periodos[normalizar_clave(nombre)] = row.to_dict()

    filas_docentes = []
    cuiles_validos_archivo = set()
    vistos_docentes = set()
    for idx, row in (df_docentes if df_docentes is not None else pd.DataFrame()).iterrows():
        cuil = limpiar_cuil(row.get("cuil", ""))
        clave_cuil = _clave_cuil(cuil)
        apellido = limpiar_texto_tabla(row.get("apellido", ""))
        nombres = limpiar_texto_tabla(row.get("nombres", ""))
        existente = base_docentes.get(clave_cuil)

        # v247: en un docente existente, una celda vacía NO significa borrar.
        # El Estado también conserva su valor si la celda del Excel está vacía.
        estado_ingresado = limpiar_texto_tabla(row.get("estado", ""))
        if estado_ingresado:
            estado = _valor_canonico_lista(estado_ingresado, ESTADOS_DOCENTE, default="")
        elif existente:
            estado = limpiar_texto_tabla((existente or {}).get("estado", "")) or "Activo"
        else:
            estado = "Activo"

        antiguedad_raw = limpiar_texto_tabla(row.get("antiguedad_anios", ""))
        antiguedad_informada = bool(antiguedad_raw)
        antiguedad_anios = ""
        if antiguedad_informada:
            try:
                antig_num = float(str(antiguedad_raw).replace(",", "."))
                if not antig_num.is_integer() or antig_num < 0 or antig_num > 80:
                    raise ValueError
                antiguedad_anios = int(antig_num)
            except Exception:
                antiguedad_anios = ""

        nivel_posgrado_raw = limpiar_texto_tabla(row.get("nivel_posgrado_salarial", ""))
        nivel_posgrado_informado = bool(nivel_posgrado_raw)
        nivel_posgrado_salarial = (
            _nivel_posgrado_salarial_normalizado_v256(nivel_posgrado_raw)
            if nivel_posgrado_informado else ""
        )

        errores = []
        if not clave_cuil:
            errores.append("CUIL obligatorio")
        if clave_cuil in vistos_docentes:
            errores.append("CUIL repetido en la hoja Docentes")
        # Para altas nuevas sigue siendo obligatorio informar al menos apellido o nombres.
        # Para existentes se permite una actualización parcial de cualquier otro campo.
        if not existente and not apellido and not nombres:
            errores.append("Falta apellido o nombres")
        if estado_ingresado and not estado:
            errores.append("Estado docente no válido")
        if antiguedad_informada and antiguedad_anios == "":
            errores.append("Años de antigüedad debe ser un entero entre 0 y 80")
        if nivel_posgrado_informado and not nivel_posgrado_salarial:
            errores.append("Nivel de posgrado salarial no válido; usá Especialista, Magíster o Doctor")
        vistos_docentes.add(clave_cuil)

        if errores:
            accion = "Error"
            estado_validacion = "ERROR"
        elif existente:
            accion = "Actualizar campos informados u omitir"
            estado_validacion = "EXISTENTE"
            cuiles_validos_archivo.add(clave_cuil)
        else:
            accion = "Crear docente"
            estado_validacion = "OK"
            cuiles_validos_archivo.add(clave_cuil)

        filas_docentes.append({
            "fila": int(idx) + 2,
            "cuil": cuil,
            "apellido": apellido,
            "nombres": nombres,
            "legajo": limpiar_texto_tabla(row.get("legajo", "")),
            "titulo": limpiar_texto_tabla(row.get("titulo", "")),
            "titulo_posgrado": limpiar_texto_tabla(row.get("titulo_posgrado", "")),
            "antiguedad_anios": antiguedad_anios,
            "nivel_posgrado_salarial": nivel_posgrado_salarial,
            "email": limpiar_texto_tabla(row.get("email", "")),
            "telefono": limpiar_texto_tabla(row.get("telefono", "")),
            "ref_legajo_fisico": limpiar_texto_tabla(row.get("ref_legajo_fisico", "")),
            "estado": estado or estado_ingresado,
            "observaciones": limpiar_texto_tabla(row.get("observaciones", "")),
            "accion": accion,
            "estado_validacion": estado_validacion,
            "motivo": "; ".join(errores) if errores else ("Ya existe; si elegís actualizar, solo se modificarán las celdas con valor" if existente else "Datos válidos"),
            "_clave_cuil": clave_cuil,
            "_cuil_existente": limpiar_texto_tabla((existente or {}).get("cuil", "")),
            "_tipo_docente_existente": limpiar_texto_tabla((existente or {}).get("tipo_docente", "")) or "Propio",
            "_estado_informado_v247": bool(estado_ingresado),
            "_antiguedad_informada_v260": bool(antiguedad_informada),
            "_nivel_posgrado_informado_v260": bool(nivel_posgrado_informado),
        })

    df_doc_preview = pd.DataFrame(filas_docentes)

    # v218: resolver una etiqueta humana por CUIL para la revisión de Designaciones.
    # Se priorizan los datos cargados en la hoja Docentes y, si el docente ya existía,
    # se completa desde la base maestra. La identidad y el vínculo siguen siendo por CUIL.
    nombres_docentes_por_cuil = {}
    for _, doc_prev in df_doc_preview.iterrows():
        clave_doc = _clave_cuil(doc_prev.get("cuil", ""))
        if not clave_doc:
            continue
        nombre_doc = nombre_completo(doc_prev.get("apellido", ""), doc_prev.get("nombres", ""))
        nombre_doc = limpiar_texto_tabla(nombre_doc)
        if nombre_doc:
            nombres_docentes_por_cuil[clave_doc] = nombre_doc

    for clave_doc, doc_base in base_docentes.items():
        if clave_doc in nombres_docentes_por_cuil:
            continue
        nombre_doc = limpiar_texto_tabla(doc_base.get("nombre_completo", ""))
        if not nombre_doc:
            nombre_doc = limpiar_texto_tabla(doc_base.get("nombre", ""))
        if not nombre_doc:
            nombre_doc = limpiar_texto_tabla(
                nombre_completo(doc_base.get("apellido", ""), doc_base.get("nombres", ""))
            )
        if nombre_doc:
            nombres_docentes_por_cuil[clave_doc] = nombre_doc

    cuiles_disponibles = set(base_docentes.keys()) | cuiles_validos_archivo

    periodos_ordenados_v230 = _periodos_ordenados_fechas_v230(df_periodos_base)
    periodos_involucrados = set()
    for _, row in (df_designaciones if df_designaciones is not None else pd.DataFrame()).iterrows():
        inf_v230 = _inferir_periodo_estado_fechas_v230(
            row.get("fecha_desde", ""), row.get("fecha_hasta", ""), periodos_ordenados_v230
        )
        if inf_v230.get("periodo_id") is not None:
            periodos_involucrados.add(int(inf_v230["periodo_id"]))

    # v225: la revisión previa también consulta la foto física sin caché.
    # Así, volver a subir un Excel inmediatamente después de una carga nunca depende
    # de que una caché de get_designaciones ya haya sido invalidada.
    try:
        claves_designaciones_base = set(_snapshot_designaciones_integral_v220(periodos_involucrados).keys())
    except Exception:
        claves_designaciones_base = set()

    filas_designaciones = []
    vistas_designaciones = set()
    for idx, row in (df_designaciones if df_designaciones is not None else pd.DataFrame()).iterrows():
        errores = []
        advertencias = []
        cuil = limpiar_cuil(row.get("cuil", ""))
        clave_cuil = _clave_cuil(cuil)
        fecha_desde = _fecha_iso_integral(row.get("fecha_desde", ""), "")
        fecha_hasta = _fecha_iso_integral(row.get("fecha_hasta", ""), "")
        inf_v230 = _inferir_periodo_estado_fechas_v230(fecha_desde, fecha_hasta, periodos_ordenados_v230)
        periodo = inf_v230.get("periodo")
        nombre_periodo = inf_v230.get("periodo_nombre", "")
        estado = inf_v230.get("estado", "")
        if not clave_cuil:
            errores.append("CUIL obligatorio")
        elif clave_cuil not in cuiles_disponibles:
            errores.append("El CUIL no está en la hoja Docentes ni en la base maestra")
        if not fecha_desde or not fecha_hasta:
            errores.append("Fecha desde y Fecha hasta son obligatorias")
        elif fecha_desde > fecha_hasta:
            errores.append("Fecha desde posterior a fecha hasta")
        elif periodo is None:
            errores.append("Las fechas no coinciden con ningún período registrado")

        cargo = _valor_canonico_lista(row.get("cargo", ""), CARGOS, default="JTP")
        dedicacion = _valor_canonico_lista(row.get("dedicacion", ""), DEDICACIONES, default="Simple")
        tipo_designacion = _valor_canonico_lista(row.get("tipo_designacion", ""), TIPOS_DESIGNACION, default="Interino")
        numero_resolucion = limpiar_texto_tabla(row.get("numero_resolucion", ""))
        ad_honorem = _normalizar_ad_honorem_integral(row.get("ad_honorem", "") or "No")
        horas = horas_segun_dedicacion(dedicacion, 0)

        if not cargo:
            errores.append("Cargo no válido")
        if not dedicacion:
            errores.append("Dedicación no válida")
        if not horas:
            errores.append("No se pudieron determinar las horas desde la dedicación")
        if not tipo_designacion:
            errores.append("Tipo de designación no válido")
        if not ad_honorem:
            errores.append("Ad honorem debe ser Sí o No")
        if not estado:
            errores.append("Estado de designación no válido")

        if estado == "Activa" and not numero_resolucion:
            advertencias.append("Falta N° de resolución de la designación")
        if tipo_designacion == "Concursado":
            advertencias.append("Verificar que las fechas sean las reales del concurso")

        periodo_id = int(periodo["id"]) if periodo else None
        clave_designacion = (
            periodo_id,
            clave_cuil,
            normalizar_clave(cargo),
            normalizar_clave(dedicacion),
            horas,
            normalizar_clave(tipo_designacion),
            normalizar_clave(numero_resolucion),
            normalizar_clave(ad_honorem),
            fecha_desde,
            fecha_hasta,
            # v223: el estado es un atributo mutable de la misma designación, no una
            # identidad nueva. Esto es esencial para cargas de períodos históricos.
        )
        duplicada_archivo = clave_designacion in vistas_designaciones
        vistas_designaciones.add(clave_designacion)
        duplicada_base = clave_designacion in claves_designaciones_base

        if errores:
            accion = "Error"
            estado_validacion = "ERROR"
            motivo = "; ".join(errores)
        elif duplicada_archivo:
            accion = "Omitir duplicada"
            estado_validacion = "OMITIR"
            motivo = "Designación repetida dentro del archivo"
        elif duplicada_base:
            accion = "Omitir duplicada"
            estado_validacion = "OMITIR"
            motivo = "La designación ya existe en la base; el estado (Activa/Finalizada) no genera una designación nueva"
        elif advertencias:
            accion = "Crear designación"
            estado_validacion = "ADVERTENCIA"
            motivo = "; ".join(advertencias)
        else:
            accion = "Crear designación"
            estado_validacion = "OK"
            motivo = "Datos válidos"

        cuil_guardado = limpiar_texto_tabla((base_docentes.get(clave_cuil) or {}).get("cuil", "")) or cuil
        docente_preview = (
            nombres_docentes_por_cuil.get(clave_cuil)
            or limpiar_texto_tabla(row.get("docente", ""))
            or ""
        )
        filas_designaciones.append({
            "fila": int(idx) + 2,
            "periodo": nombre_periodo,
            "docente": docente_preview,
            "cuil": cuil,
            "cargo": cargo or limpiar_texto_tabla(row.get("cargo", "")),
            "dedicacion": dedicacion or limpiar_texto_tabla(row.get("dedicacion", "")),
            "horas": horas,
            "tipo_designacion": tipo_designacion or limpiar_texto_tabla(row.get("tipo_designacion", "")),
            "numero_resolucion": numero_resolucion,
            "ad_honorem": ad_honorem or limpiar_texto_tabla(row.get("ad_honorem", "")),
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "estado": estado or limpiar_texto_tabla(row.get("estado", "")),
            "observaciones": limpiar_texto_tabla(row.get("observaciones", "")),
            "accion": accion,
            "estado_validacion": estado_validacion,
            "motivo": motivo,
            "_periodo_id": periodo_id,
            "_clave_cuil": clave_cuil,
            "_cuil_guardado": cuil_guardado,
        })

    return df_doc_preview, pd.DataFrame(filas_designaciones)


# --- entry l. 17696-18018
def generar_excel_integral_docentes_designaciones(periodo_default=None, filas_docentes=1000, filas_designaciones=5000):
    """Genera un único Excel con hojas separadas para docentes y designaciones."""
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.workbook.defined_name import DefinedName
    from openpyxl.utils import quote_sheetname

    filas_docentes = max(20, int(filas_docentes or 1000))
    filas_designaciones = max(20, int(filas_designaciones or 5000))

    try:
        df_docentes_existentes = get_docentes().copy()
    except Exception:
        df_docentes_existentes = pd.DataFrame()
    for col in [
        "cuil", "apellido", "nombres", "nombre_completo", "legajo", "titulo", "titulo_posgrado",
        "antiguedad_anios", "nivel_posgrado_salarial", "email", "telefono", "ref_legajo_fisico",
        "estado", "tipo_docente", "observaciones",
    ]:
        if col not in df_docentes_existentes.columns:
            df_docentes_existentes[col] = ""
    if not df_docentes_existentes.empty:
        df_docentes_existentes = (
            df_docentes_existentes.assign(
                cuil=df_docentes_existentes["cuil"].fillna("").astype(str).str.strip(),
                nombre_completo=df_docentes_existentes["nombre_completo"].fillna("").astype(str).str.strip(),
            )
            .query("cuil != ''")
            .drop_duplicates(subset=["cuil"], keep="first")
            .sort_values(["nombre_completo", "cuil"], kind="stable")
            .reset_index(drop=True)
        )

    try:
        df_periodos = get_periodos().copy()
    except Exception:
        df_periodos = pd.DataFrame()
    for col in ["nombre", "fecha_inicio", "fecha_fin", "estado"]:
        if col not in df_periodos.columns:
            df_periodos[col] = ""
    if not df_periodos.empty:
        df_periodos = (
            df_periodos.assign(nombre=df_periodos["nombre"].fillna("").astype(str).str.strip())
            .query("nombre != ''")
            .drop_duplicates(subset=["nombre"], keep="first")
            .reset_index(drop=True)
        )

    wb = Workbook()
    ws_doc = wb.active
    ws_doc.title = "Docentes"
    ws_des = wb.create_sheet("Designaciones")
    ws_existentes = wb.create_sheet("Docentes existentes")
    ws_periodos = wb.create_sheet("Períodos")
    ws_instrucciones = wb.create_sheet("Instrucciones")
    ws_listas = wb.create_sheet("Listas")

    relleno_encabezado = PatternFill("solid", fgColor="1F4E78")
    relleno_entrada = PatternFill("solid", fgColor="FFF2CC")
    relleno_formula = PatternFill("solid", fgColor="D9EAF7")
    fuente_encabezado = Font(color="FFFFFF", bold=True)
    borde_fino = Border(
        left=Side(style="thin", color="D9E1F2"), right=Side(style="thin", color="D9E1F2"),
        top=Side(style="thin", color="D9E1F2"), bottom=Side(style="thin", color="D9E1F2"),
    )

    def preparar_encabezados(ws, encabezados, anchos):
        for col_idx, encabezado in enumerate(encabezados, start=1):
            celda = ws.cell(row=1, column=col_idx, value=encabezado)
            celda.fill = relleno_encabezado
            celda.font = fuente_encabezado
            celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            celda.border = borde_fino
        ws.row_dimensions[1].height = 34
        ws.freeze_panes = "A2"
        for letra, ancho in anchos.items():
            ws.column_dimensions[letra].width = ancho
        ws.sheet_view.showGridLines = False

    encabezados_doc = [
        "CUIL", "Apellido", "Nombres", "Legajo", "Título", "Título posgrado",
        "Años antigüedad", "Nivel posgrado salarial", "Email", "Teléfono",
        "Ref. legajo físico", "Estado", "Observaciones",
    ]
    preparar_encabezados(ws_doc, encabezados_doc, {
        "A": 18, "B": 24, "C": 28, "D": 15, "E": 36, "F": 36,
        "G": 18, "H": 24, "I": 32, "J": 18, "K": 24, "L": 16, "M": 40,
    })
    fin_doc = filas_docentes + 1
    for fila in range(2, fin_doc + 1):
        for col in range(1, len(encabezados_doc) + 1):
            celda = ws_doc.cell(row=fila, column=col)
            celda.fill = relleno_entrada
            celda.border = borde_fino
            celda.alignment = Alignment(vertical="center", wrap_text=True)
        for col in [1, 4, 10, 11]:
            ws_doc.cell(row=fila, column=col).number_format = "@"
        ws_doc.cell(row=fila, column=7).number_format = "0"
    tabla_doc = Table(displayName="TablaIntegralDocentes", ref=f"A1:M{fin_doc}")
    tabla_doc.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
    ws_doc.add_table(tabla_doc)

    encabezados_des = [
        "CUIL", "Docente", "Período", "Cargo", "Dedicación", "Horas",
        "Tipo designación", "N° resolución", "Ad honorem", "Fecha desde", "Fecha hasta",
        "Estado", "Observaciones",
    ]
    preparar_encabezados(ws_des, encabezados_des, {
        "A": 18, "B": 36, "C": 16, "D": 18, "E": 22, "F": 12,
        "G": 20, "H": 20, "I": 16, "J": 16, "K": 16, "L": 16, "M": 42,
    })
    fin_des = filas_designaciones + 1
    periodo_nombre_default = limpiar_texto_tabla((periodo_default or {}).get("nombre", ""))
    ultima_fila_doc_nuevos = max(2, fin_doc)
    ultima_fila_doc_existentes = max(2, len(df_docentes_existentes) + 1)
    for fila in range(2, fin_des + 1):
        if periodo_nombre_default:
            ws_des.cell(row=fila, column=3, value=periodo_nombre_default)
        ws_des.cell(
            row=fila,
            column=2,
            value=(
                f'=IF(A{fila}="","",IFERROR(INDEX(Docentes!$B$2:$B${ultima_fila_doc_nuevos},MATCH(A{fila},Docentes!$A$2:$A${ultima_fila_doc_nuevos},0))&", "&INDEX(Docentes!$C$2:$C${ultima_fila_doc_nuevos},MATCH(A{fila},Docentes!$A$2:$A${ultima_fila_doc_nuevos},0)),IFERROR(INDEX(\'Docentes existentes\'!$B$2:$B${ultima_fila_doc_existentes},MATCH(A{fila},\'Docentes existentes\'!$A$2:$A${ultima_fila_doc_existentes},0))&", "&INDEX(\'Docentes existentes\'!$C$2:$C${ultima_fila_doc_existentes},MATCH(A{fila},\'Docentes existentes\'!$A$2:$A${ultima_fila_doc_existentes},0)),"")))'
            ),
        )
        ws_des.cell(
            row=fila,
            column=6,
            value=(
                f'=IF(E{fila}="","",IF(E{fila}="Simple",10,IF(E{fila}="Parcial",20,'
                f'IF(E{fila}="Parcial + Simple",30,IF(E{fila}="Exclusiva",40,'
                f'IF(E{fila}="Exclusiva + Simple",50,""))))))'
            ),
        )
        for col in range(1, len(encabezados_des) + 1):
            celda = ws_des.cell(row=fila, column=col)
            celda.fill = relleno_formula if col in [2, 6] else relleno_entrada
            celda.border = borde_fino
            celda.alignment = Alignment(vertical="center", wrap_text=True)
        ws_des.cell(row=fila, column=1).number_format = "@"
        ws_des.cell(row=fila, column=6).number_format = "0"
        ws_des.cell(row=fila, column=10).number_format = "dd/mm/yyyy"
        ws_des.cell(row=fila, column=11).number_format = "dd/mm/yyyy"
    tabla_des = Table(displayName="TablaIntegralDesignaciones", ref=f"A1:M{fin_des}")
    tabla_des.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
    ws_des.add_table(tabla_des)

    # v260: misma estructura y mismo orden que la hoja Docentes. Así se puede copiar
    # una fila completa, completar únicamente lo faltante y pegarla en Docentes sin
    # reacomodar columnas. Los vacíos se muestran como vacíos: no se reemplazan con defaults.
    preparar_encabezados(ws_existentes, encabezados_doc, {
        "A": 18, "B": 24, "C": 28, "D": 15, "E": 36, "F": 36,
        "G": 18, "H": 24, "I": 32, "J": 18, "K": 24, "L": 16, "M": 40,
    })

    def _valor_excel_existente_v260(valor):
        try:
            if valor is None or pd.isna(valor):
                return ""
        except Exception:
            if valor is None:
                return ""
        return valor

    for fila_idx, (_, row) in enumerate(df_docentes_existentes.iterrows(), start=2):
        antig_exist = row.get("antiguedad_anios")
        try:
            antig_exist = "" if antig_exist is None or pd.isna(antig_exist) else int(float(antig_exist))
        except Exception:
            antig_exist = ""
        valores = [
            _valor_excel_existente_v260(row.get("cuil", "")),
            _valor_excel_existente_v260(row.get("apellido", "")),
            _valor_excel_existente_v260(row.get("nombres", "")),
            _valor_excel_existente_v260(row.get("legajo", "")),
            _valor_excel_existente_v260(row.get("titulo", "")),
            _valor_excel_existente_v260(row.get("titulo_posgrado", "")),
            antig_exist,
            _nivel_posgrado_salarial_normalizado_v256(row.get("nivel_posgrado_salarial", "")),
            _valor_excel_existente_v260(row.get("email", "")),
            _valor_excel_existente_v260(row.get("telefono", "")),
            _valor_excel_existente_v260(row.get("ref_legajo_fisico", "")),
            _valor_excel_existente_v260(row.get("estado", "")),
            _valor_excel_existente_v260(row.get("observaciones", "")),
        ]
        for col_idx, valor in enumerate(valores, start=1):
            c = ws_existentes.cell(row=fila_idx, column=col_idx, value=valor)
            c.border = borde_fino
            c.alignment = Alignment(vertical="top", wrap_text=True)
        for col_idx in [1, 4, 10, 11]:
            ws_existentes.cell(row=fila_idx, column=col_idx).number_format = "@"
        ws_existentes.cell(row=fila_idx, column=7).number_format = "0"
    if len(df_docentes_existentes) > 0:
        tabla_exist = Table(displayName="TablaIntegralDocentesExistentes", ref=f"A1:M{len(df_docentes_existentes) + 1}")
        tabla_exist.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
        ws_existentes.add_table(tabla_exist)

    preparar_encabezados(ws_periodos, ["Período", "Fecha inicio", "Fecha fin", "Estado"], {
        "A": 18, "B": 18, "C": 18, "D": 16,
    })
    for fila_idx, (_, row) in enumerate(df_periodos.iterrows(), start=2):
        valores = [row.get("nombre", ""), row.get("fecha_inicio", ""), row.get("fecha_fin", ""), row.get("estado", "")]
        for col_idx, valor in enumerate(valores, start=1):
            c = ws_periodos.cell(row=fila_idx, column=col_idx, value=valor)
            c.border = borde_fino
            c.alignment = Alignment(vertical="top", wrap_text=True)
    if len(df_periodos) > 0:
        tabla_per = Table(displayName="TablaIntegralPeriodos", ref=f"A1:D{len(df_periodos) + 1}")
        tabla_per.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
        ws_periodos.add_table(tabla_per)

    listas = {
        "A": ("Estados docentes", list(ESTADOS_DOCENTE)),
        "B": ("Cargos", list(CARGOS)),
        "C": ("Dedicaciones", list(DEDICACIONES)),
        "D": ("Horas", [str(v) for v in HORAS_OPCIONES]),
        "E": ("Tipos", list(TIPOS_DESIGNACION)),
        "F": ("Ad honorem", ["Sí", "No"]),
        "G": ("Estados designaciones", list(ESTADOS_DESIGNACION)),
        "H": ("Nivel posgrado salarial", ["Especialista", "Magíster", "Doctor"]),
    }
    for letra, (titulo, valores) in listas.items():
        ws_listas[f"{letra}1"] = titulo
        ws_listas[f"{letra}1"].font = Font(bold=True)
        for idx, valor in enumerate(valores, start=2):
            ws_listas[f"{letra}{idx}"] = valor

    def nombre_rango(nombre, hoja, columna, inicio, fin):
        referencia = f"{quote_sheetname(hoja)}!${columna}${inicio}:${columna}${max(inicio, fin)}"
        wb.defined_names.add(DefinedName(nombre, attr_text=referencia))

    nombre_rango("IntegralEstadosDocentes", "Listas", "A", 2, 1 + len(listas["A"][1]))
    nombre_rango("IntegralCargos", "Listas", "B", 2, 1 + len(listas["B"][1]))
    nombre_rango("IntegralDedicaciones", "Listas", "C", 2, 1 + len(listas["C"][1]))
    nombre_rango("IntegralHoras", "Listas", "D", 2, 1 + len(listas["D"][1]))
    nombre_rango("IntegralTipos", "Listas", "E", 2, 1 + len(listas["E"][1]))
    nombre_rango("IntegralAdHonorem", "Listas", "F", 2, 1 + len(listas["F"][1]))
    nombre_rango("IntegralEstadosDesignaciones", "Listas", "G", 2, 1 + len(listas["G"][1]))
    nombre_rango("IntegralNivelesPosgrado", "Listas", "H", 2, 1 + len(listas["H"][1]))
    nombre_rango("IntegralPeriodos", "Períodos", "A", 2, 1 + max(1, len(df_periodos)))

    validaciones = [
        (ws_doc, "=IntegralNivelesPosgrado", f"H2:H{fin_doc}", "Nivel de posgrado salarial"),
        (ws_doc, "=IntegralEstadosDocentes", f"L2:L{fin_doc}", "Estado docente"),
        (ws_des, "=IntegralPeriodos", f"C2:C{fin_des}", "Período"),
        (ws_des, "=IntegralCargos", f"D2:D{fin_des}", "Cargo"),
        (ws_des, "=IntegralDedicaciones", f"E2:E{fin_des}", "Dedicación"),
        (ws_des, "=IntegralTipos", f"G2:G{fin_des}", "Tipo de designación"),
        (ws_des, "=IntegralAdHonorem", f"I2:I{fin_des}", "Ad honorem"),
        (ws_des, "=IntegralEstadosDesignaciones", f"L2:L{fin_des}", "Estado de designación"),
    ]
    for ws, formula, rango, titulo in validaciones:
        dv = DataValidation(type="list", formula1=formula, allow_blank=True)
        dv.error = "El valor no pertenece a la lista disponible."
        dv.errorTitle = "Valor no válido"
        dv.prompt = f"Seleccioná un valor válido para {titulo}."
        dv.promptTitle = titulo
        dv.showErrorMessage = True
        dv.showInputMessage = True
        ws.add_data_validation(dv)
        dv.add(rango)

    dv_antig_v260 = DataValidation(type="whole", operator="between", formula1="0", formula2="80", allow_blank=True)
    dv_antig_v260.error = "Ingresá una cantidad entera de años entre 0 y 80, o dejá la celda vacía."
    dv_antig_v260.errorTitle = "Antigüedad no válida"
    dv_antig_v260.prompt = "Dato opcional. Si queda vacío, en Sueldos se toma 0 años (20%) salvo que el docente ya tenga un valor guardado y se lo esté actualizando parcialmente."
    dv_antig_v260.promptTitle = "Años de antigüedad"
    dv_antig_v260.showErrorMessage = True
    dv_antig_v260.showInputMessage = True
    ws_doc.add_data_validation(dv_antig_v260)
    dv_antig_v260.add(f"G2:G{fin_doc}")

    ws_doc["A1"].comment = Comment("El CUIL vincula al docente con una o varias designaciones.", "Sistema")
    ws_doc["G1"].comment = Comment("Años de antigüedad del docente. Es opcional; en Sueldos, si no hay dato guardado se toma 0 años (20%).", "Sistema")
    ws_doc["H1"].comment = Comment("Seleccioná Especialista, Magíster o Doctor. Es opcional y determina el adicional salarial por posgrado.", "Sistema")
    ws_des["A1"].comment = Comment("Debe coincidir con un CUIL de la hoja Docentes o con un docente ya existente.", "Sistema")
    ws_des["B1"].comment = Comment("Campo informativo: se completa automáticamente según el CUIL.", "Sistema")
    ws_des["F1"].comment = Comment("Se calcula automáticamente desde Dedicación: Simple=10, Parcial=20, Parcial + Simple=30, Exclusiva=40, Exclusiva + Simple=50.", "Sistema")
    ws_des["H1"].comment = Comment("Número de la resolución correspondiente a ESTA designación. Las disposiciones lo leen desde acá.", "Sistema")
    ws_des["J1"].comment = Comment("Para concursados, ingresá la fecha real de inicio del concurso.", "Sistema")
    ws_des["K1"].comment = Comment("Para concursados, ingresá la fecha real de finalización del concurso.", "Sistema")

    instrucciones = [
        "EXCEL INTEGRAL DE DOCENTES Y DESIGNACIONES",
        "1. En Docentes cargá una fila por persona. El CUIL es obligatorio y no debe repetirse.",
        "2. En Designaciones cargá una fila por cada designación. Un docente puede aparecer varias veces con el mismo CUIL.",
        "3. El vínculo entre ambas hojas se realiza por CUIL. La columna Docente de Designaciones es solo informativa.",
        "4. En Designaciones elegí la Dedicación: Horas se completa automáticamente (Simple=10, Parcial=20, Parcial + Simple=30, Exclusiva=40, Exclusiva + Simple=50).",
        "5. Cargá el N° de resolución propio de cada designación; las disposiciones toman ese número directamente desde Designaciones.",
        "6. La hoja Docentes existentes contiene TODOS los docentes del departamento y replica las mismas columnas de Docentes, incluso cuando algún dato está vacío. Podés copiar una fila completa a Docentes, completar o corregir solo lo necesario y volver a cargarla.",
        "7. Años antigüedad y Nivel posgrado salarial son opcionales. El nivel se elige de la lista Especialista / Magíster / Doctor. Si un docente existente deja una de esas celdas vacía, se conserva el valor que ya tenía guardado.",
        "8. Podés completar únicamente Docentes o completar ambas hojas. Si Designaciones queda vacía, se cargarán solo docentes.",
        "9. Para designaciones concursadas, ingresá siempre las fechas reales del concurso, aunque excedan el período académico.",
        "10. No cambies los nombres de las hojas Docentes y Designaciones ni los encabezados de sus tablas.",
        "11. Guardá el archivo y subilo completo desde Docentes > Carga rápida. No hace falta copiar y pegar las hojas.",
        "12. Antes de guardar, la aplicación muestra una revisión con nuevos, existentes, duplicados y errores.",
        "13. No hay un cupo de docentes ni de designaciones por departamento. Si necesitás más filas que las preformateadas, agregalas al Excel: el importador procesa todas las filas con datos.",
        "14. Si actualizás un docente existente, las celdas vacías de la hoja Docentes conservan el valor ya guardado; solo se reemplazan los campos que completes.",
    ]
    for fila, texto in enumerate(instrucciones, start=1):
        ws_instrucciones.cell(row=fila, column=1, value=texto)
        ws_instrucciones.cell(row=fila, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    ws_instrucciones["A1"].font = Font(bold=True, size=14)
    ws_instrucciones.column_dimensions["A"].width = 120
    ws_instrucciones.sheet_view.showGridLines = False
    ws_listas.sheet_state = "hidden"

    try:
        wb.calculation.calcMode = "auto"
        wb.calculation.fullCalcOnLoad = True
        wb.calculation.forceFullCalc = True
        ws_doc.sheet_view.selection[0].activeCell = "A2"
        ws_doc.sheet_view.selection[0].sqref = "A2"
    except Exception:
        pass

    salida = BytesIO()
    wb.save(salida)
    salida.seek(0)
    return salida.getvalue()


# --- entry l. 25454-25456
def _nivel_posgrado_salarial_normalizado_v256(valor):
    from integraciones.carga_integral_motor.ref.domain.salarios import _nivel_posgrado_salarial_normalizado_v256 as _b05_core__nivel_posgrado_salarial_normalizado_v256
    return _b05_core__nivel_posgrado_salarial_normalizado_v256(valor)


# --- entry l. 45822
_generar_excel_integral_pre_v230 = generar_excel_integral_docentes_designaciones


# --- entry l. 45825-45849
def _ordenar_hoja_periodos_excel_v230(ws):
    """Ordena la hoja Períodos ascendente y guarda fechas como fechas de Excel."""
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


# --- entry l. 45852-45854
def _formula_periodo_excel_v230(fila, col_desde, col_hasta, ultima_fila_periodos):
    from integraciones.carga_integral_motor.ref.domain.periodos import _formula_periodo_excel_v230 as _b05_core__formula_periodo_excel_v230
    return _b05_core__formula_periodo_excel_v230(fila, col_desde, col_hasta, ultima_fila_periodos)


# --- entry l. 45857-45864
def _quitar_validaciones_formula_v230(ws, formulas):
    try:
        existentes = list(ws.data_validations.dataValidation)
        ws.data_validations.dataValidation = [
            dv for dv in existentes if str(getattr(dv, "formula1", "") or "") not in set(formulas)
        ]
    except Exception:
        pass


# --- entry l. 45899-45926
def generar_excel_integral_docentes_designaciones(periodo_default=None, filas_docentes=1000, filas_designaciones=5000):
    from openpyxl import load_workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import PatternFill
    data = _generar_excel_integral_pre_v230(periodo_default=periodo_default, filas_docentes=filas_docentes, filas_designaciones=filas_designaciones)
    wb = load_workbook(BytesIO(data))
    ws = wb["Designaciones"]
    wsp = wb["Períodos"]
    filas_per = _ordenar_hoja_periodos_excel_v230(wsp)
    ult_fila_per = 1 + len(filas_per)
    ultimo_nombre = filas_per[-1][2] if filas_per else ""
    relleno_formula = PatternFill("solid", fgColor="D9EAF7")
    for fila in range(2, ws.max_row + 1):
        ws.cell(fila, 3).value = _formula_periodo_excel_v230(fila, "J", "K", ult_fila_per)
        ws.cell(fila, 12).value = (
            f'=IF(C{fila}="","",IF(C{fila}="{str(ultimo_nombre).replace(chr(34), chr(34)*2)}","Activa","Finalizada"))'
            if ultimo_nombre else '=""'
        )
        for col in [2, 3, 6, 12]:
            ws.cell(fila, col).fill = relleno_formula
    _quitar_validaciones_formula_v230(ws, {"=IntegralPeriodos", "=IntegralEstadosDesignaciones"})
    ws["C1"].comment = Comment("Automático: se detecta desde Fecha desde / Fecha hasta. Si la vigencia abarca varios períodos, toma el último período registrado que se superpone.", "Sistema")
    ws["L1"].comment = Comment("Automático: Activa si el período detectado es el último período cronológico del departamento; Finalizada si es histórico.", "Sistema")
    wsi = wb["Instrucciones"]
    r = wsi.max_row + 1
    wsi.cell(r, 1, "13. Período y Estado de Designaciones son automáticos: completá Fecha desde y Fecha hasta. La app los recalcula al importar y descarta cualquier valor manual en esas columnas.")
    wsi.cell(r + 1, 1, "14. Si una vigencia abarca varios períodos (por ejemplo una concursada plurianual), se asigna al último período registrado que esté cubierto por la vigencia.")
    out = BytesIO(); wb.save(out); out.seek(0); return out.getvalue()


# --- entry l. 45943
_generar_excel_integral_pre_v199 = generar_excel_integral_docentes_designaciones


# --- entry l. 45945-45952
def _excel_integral_cache_v199(periodo_id, filas_docentes, filas_designaciones, db_url, inst, dep, version):
    p = None
    if periodo_id is not None:
        try:
            dfp = get_periodos(); f = dfp[pd.to_numeric(dfp.get("id"), errors="coerce").eq(int(periodo_id))]
            p = f.iloc[0].to_dict() if not f.empty else None
        except Exception: p = None
    return _generar_excel_integral_pre_v199(periodo_default=p, filas_docentes=int(filas_docentes), filas_designaciones=int(filas_designaciones))


# --- entry l. 45953-45956
def generar_excel_integral_docentes_designaciones(periodo_default=None, filas_docentes=1000, filas_designaciones=5000):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    pid = int(periodo_default.get("id")) if isinstance(periodo_default, dict) and periodo_default.get("id") is not None else None
    return _excel_integral_cache_v199(pid, int(filas_docentes), int(filas_designaciones), db_url, inst, dep, version)


# --- entry l. 49681-49718
def _inferir_periodo_estado_fechas_v230(fecha_desde, fecha_hasta, df_periodos=None):
    fd = _fecha_iso_integral(fecha_desde, '')
    fh = _fecha_iso_integral(fecha_hasta, '')
    if not fd or not fh or fd > fh:
        return {'periodo': None, 'periodo_id': None, 'periodo_nombre': '', 'estado': '', 'coincidencias': 0}
    try:
        dfd = pd.Timestamp(fd); fhd = pd.Timestamp(fh)
    except Exception:
        return {'periodo': None, 'periodo_id': None, 'periodo_nombre': '', 'estado': '', 'coincidencias': 0}
    per = _periodos_ordenados_fechas_v230(df_periodos)
    if per.empty:
        return {'periodo': None, 'periodo_id': None, 'periodo_nombre': '', 'estado': '', 'coincidencias': 0}
    candidatos = per[(dfd <= per['_fin_v230']) & (fhd >= per['_inicio_v230'])].copy()
    if candidatos.empty:
        return {'periodo': None, 'periodo_id': None, 'periodo_nombre': '', 'estado': '', 'coincidencias': 0}
    elegido = candidatos.iloc[-1].to_dict()
    try: pid = int(elegido.get('id'))
    except Exception: pid = None
    try: ini_p = pd.Timestamp(elegido.get('_inicio_v230')).date()
    except Exception: ini_p = None
    try: fin_p = pd.Timestamp(elegido.get('_fin_v230')).date()
    except Exception: fin_p = None
    try: ini_d = dfd.date(); fin_d = fhd.date()
    except Exception: ini_d = fin_d = None
    hoy = date.today()
    vigente_hoy = (
        pid is not None
        and (ini_p is None or ini_p <= hoy)
        and (fin_p is None or fin_p >= hoy)
        and (ini_d is None or ini_d <= hoy)
        and (fin_d is None or fin_d >= hoy)
    )
    return {
        'periodo': elegido, 'periodo_id': pid,
        'periodo_nombre': limpiar_texto_tabla(elegido.get('nombre','')),
        'estado': 'Activa' if vigente_hoy else 'Finalizada',
        'coincidencias': int(len(candidatos)),
    }


# --- entry l. 49747-49757
def _clave_designacion_integral_v220(row):
    """Identidad estable para revisión/carga integral (v223).

    Incluye período, CUIL, cargo, dedicación, horas, tipo, resolución, condición
    Ad Honorem y fechas. Deliberadamente NO incluye ``estado``: Activa/Finalizada
    es el ciclo de vida de la misma designación y, además, los períodos cerrados
    pueden mostrarse como Finalizada aunque la fila histórica se haya almacenado
    como Activa.
    """
    from analisis.motor.ref.domain.catalog_unlocked.designaciones import _clave_designacion_integral_v220 as _b08_core__clave_designacion_integral_v220
    return _b08_core__clave_designacion_integral_v220(row)


# --- entry l. 49760-49827
def _snapshot_designaciones_integral_v220(periodo_ids):
    """Foto FÍSICA y sin caché de designaciones por identidad estable (v225).

    v219 difiere las invalidaciones de caché durante la carga masiva para mejorar
    rendimiento. Por eso esta verificación no puede usar ``get_designaciones``:
    dentro de la misma carga podría devolver la foto anterior al INSERT y provocar
    un falso faltante. Se lee directamente PostgreSQL/SQLite mediante ``get_conn``.
    """
    ids = sorted({int(x) for x in periodo_ids if x is not None})
    salida = {}
    if not ids:
        return salida

    conn = None
    try:
        conn = get_conn()
        marcadores = ",".join(["?"] * len(ids))
        df = pd.read_sql(
            f"""
            SELECT id, periodo_id, cuil, cargo, dedicacion, horas, tipo_designacion,
                   COALESCE(numero_resolucion,'') AS numero_resolucion,
                   COALESCE(ad_honorem,'') AS ad_honorem,
                   COALESCE(fecha_desde,'') AS fecha_desde,
                   COALESCE(fecha_hasta,'') AS fecha_hasta
            FROM designaciones
            WHERE periodo_id IN ({marcadores})
            ORDER BY id
            """,
            conn,
            params=ids,
        )
    except Exception:
        df = pd.DataFrame()
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    if df is None or df.empty:
        return salida

    for _, des in df.iterrows():
        try:
            pid = int(des.get("periodo_id"))
        except Exception:
            continue
        clave = (
            pid,
            _clave_cuil(des.get("cuil", "")),
            normalizar_clave(des.get("cargo", "")),
            normalizar_clave(des.get("dedicacion", "")),
            horas_segun_dedicacion(des.get("dedicacion", ""), des.get("horas", 0)),
            normalizar_clave(des.get("tipo_designacion", "")),
            normalizar_clave(des.get("numero_resolucion", "")),
            normalizar_clave(des.get("ad_honorem", "")),
            _fecha_iso_integral(des.get("fecha_desde", "")),
            _fecha_iso_integral(des.get("fecha_hasta", "")),
        )
        try:
            did = int(des.get("id"))
        except Exception:
            did = None
        # Si por una carga histórica defectuosa ya hay duplicados, basta con saber
        # que la identidad existe para impedir que esta carga agregue otra copia.
        salida.setdefault(clave, did)
    return salida
