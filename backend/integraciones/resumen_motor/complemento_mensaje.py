"""GENERADO por tools_generar_complemento_resumen.py -- NO EDITAR A MANO.

Texto literal del entry certificado B13-FIX02 (app_postgresql_refactor_b13fix02_uat_fixes.py, sha256 95691fdf48c1edd393daf60bf435d6452b2fa8e95f6dcb7a2254cea8138d3363): definiciones del
Mensaje para consultar la designación (E4-06) que no estan en el motor de Analisis ni en el
complemento del Resumen, 9 bloques en el orden del entry.
Se ejecuta DESPUES de ``analisis/motor/certificado.py`` en el mismo namespace del request
(``integraciones.resumen_docente``); nunca a nivel modulo.
"""
# flake8: noqa
# fmt: off

# --- entry (literal)
PARAMETROS_DISPOSICION_DEFAULT = {
    "Fecha Asamblea Universitaria": "",
    "N° CUDAP EXP – UNO de la Asamblea Universitaria": "",
    "fecha_acta_rector": "",
    "rector": "",
    "DNI Rector": "",
    "Período mandato": "",
    "Número de Resolución Direector de Departamento": "",
    "genero_director_departamento": "Director",
    "director/a de departamento": "",
    "DNI director/a de departamento": "",
}

# --- entry l. 2725-2739
def institucion_actual_nombre():
    """Nombre institucional para encabezado visible."""
    user = current_user() or {}
    if user.get("institucion_nombre"):
        return str(user.get("institucion_nombre"))
    inst_id = st.session_state.get("superadmin_institucion_id")
    if inst_id:
        try:
            df_inst = get_instituciones_auth(solo_activas=False)
            fila = df_inst[df_inst["id"] == int(inst_id)]
            if not fila.empty:
                return str(fila.iloc[0]["nombre"])
        except Exception:
            pass
    return "Universidad Nacional del Oeste"


# --- entry l. 5548-5556
def get_parametros_disposicion():
    conn = get_conn()
    df = pd.read_sql("SELECT clave, valor FROM disposicion_parametros", conn)
    conn.close()
    datos = PARAMETROS_DISPOSICION_DEFAULT.copy()
    if not df.empty:
        for _, row in df.iterrows():
            datos[str(row["clave"])] = "" if pd.isna(row["valor"]) else str(row["valor"])
    return datos


# --- entry l. 23993-23995
def _fecha_mensaje_docente(valor):
    from integraciones.resumen_motor.ref.domain.docentes import _fecha_mensaje_docente as _b05_core__fecha_mensaje_docente
    return _b05_core__fecha_mensaje_docente(valor)


# --- entry l. 23998-24000
def _horas_mensaje(valor):
    from integraciones.resumen_motor.ref.domain.docentes import _horas_mensaje as _b05_core__horas_mensaje
    return _b05_core__horas_mensaje(valor)


# --- entry l. 24003-24012
def _datos_periodo_para_mensaje(periodo_id):
    conn = get_conn()
    df = pd.read_sql("""
        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado
        FROM periodos
        WHERE id = ?
        LIMIT 1
    """, conn, params=[periodo_id])
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else {}


# --- entry l. 24015-24069
def get_designaciones_docente_para_mensaje(cuil, periodo_id):
    columnas = [
        "cargo", "dedicacion", "horas", "tipo_designacion", "ad_honorem",
        "fecha_desde", "fecha_hasta", "estado", "departamento"
    ]
    if USE_POSTGRESQL:
        try:
            df = _pg_read_dataframe(f"""
                WITH pr AS (
                    SELECT id, institucion_id, nombre, anio, semestre
                    FROM periodos
                    WHERE id = %s
                    LIMIT 1
                )
                SELECT
                    d.cargo,
                    d.dedicacion,
                    d.horas,
                    d.tipo_designacion,
                    COALESCE(d.ad_honorem, '') AS ad_honorem,
                    d.fecha_desde,
                    d.fecha_hasta,
                    d.estado,
                    COALESCE(dep.nombre, '') AS departamento
                FROM designaciones d
                JOIN periodos p ON p.id = d.periodo_id
                JOIN pr ON {_condicion_periodo_equivalente_sql('p', 'pr')}
                LEFT JOIN departamentos dep ON dep.id = d.departamento_id
                WHERE d.cuil = %s
                ORDER BY dep.nombre, d.tipo_designacion, d.cargo, d.dedicacion, d.id
            """, [int(periodo_id), str(cuil)])
        except Exception:
            df = pd.DataFrame(columns=columnas)
    else:
        conn = get_conn()
        df = pd.read_sql("""
            SELECT
                cargo,
                dedicacion,
                horas,
                tipo_designacion,
                COALESCE(ad_honorem, '') AS ad_honorem,
                fecha_desde,
                fecha_hasta,
                estado,
                '' AS departamento
            FROM designaciones
            WHERE cuil = ? AND periodo_id = ?
            ORDER BY tipo_designacion, cargo, dedicacion, id
        """, conn, params=[cuil, periodo_id])
        conn.close()
    for col in columnas:
        if col not in df.columns:
            df[col] = ""
    return df[columnas]


# --- entry l. 24072-24075
def cargo_autoridad_departamento(parametros=None):
    parametros = parametros or get_parametros_disposicion()
    valor = str(parametros.get("genero_director_departamento") or "Director").strip().lower()
    return "Directora" if valor == "directora" else "Director"


# --- entry l. 24078-24079
def referencia_autoridad_departamento(parametros=None):
    return "de la directora" if cargo_autoridad_departamento(parametros) == "Directora" else "del director"


# --- entry l. 24088-24235
def generar_mensaje_consulta_designacion_docente(cuil, periodo_id):
    """Genera el texto listo para copiar en un correo al inicio del cuatrimestre."""
    df_docente, _, _ = get_resumen_docente(cuil)
    if df_docente.empty:
        return "", "No se pudo generar el mensaje", ["No se encontró al docente seleccionado."]

    docente = df_docente.iloc[0].to_dict()
    periodo = _datos_periodo_para_mensaje(periodo_id)
    if not periodo:
        return "", "No se pudo generar el mensaje", ["No se encontró el período seleccionado."]

    semestre = int(periodo.get("semestre") or 1)
    anio = int(periodo.get("anio") or date.today().year)
    nombre_cuatrimestre = "primer cuatrimestre" if semestre == 1 else "segundo cuatrimestre"
    fecha_inicio = periodo.get("fecha_inicio") or fechas_periodo(anio, semestre)[0]
    fecha_fin = periodo.get("fecha_fin") or fechas_periodo(anio, semestre)[1]
    fecha_inicio_txt = _fecha_mensaje_docente(fecha_inicio)
    fecha_fin_txt = _fecha_mensaje_docente(fecha_fin)

    parametros = get_parametros_disposicion()
    director = str(parametros.get("director/a de departamento") or "").strip()
    if not director:
        director = str((current_user() or {}).get("nombre") or "").strip()
    cargo_directivo = cargo_autoridad_departamento(parametros)
    referencia_directivo = referencia_autoridad_departamento(parametros)
    departamento = _departamento_actual_operativo_nombre()
    universidad = institucion_actual_nombre()

    nombre_saludo = str(docente.get("nombres") or "").strip()
    if not nombre_saludo:
        nombre_saludo = str(docente.get("nombre_completo") or "Docente").strip()

    df_desig = get_designaciones_docente_para_mensaje(cuil, periodo_id)
    if not df_desig.empty:
        activas = df_desig[df_desig["estado"].fillna("").astype(str).str.lower().eq("activa")].copy()
        if not activas.empty:
            df_desig = activas

    df_comisiones = get_comisiones_docente(cuil, periodo_id)
    df_investigacion = get_investigacion_docente(cuil=cuil, periodo_id=periodo_id, todos_departamentos=USE_POSTGRESQL)
    df_extension = get_extension_docente(cuil=cuil, periodo_id=periodo_id, todos_departamentos=USE_POSTGRESQL)

    lineas = [
        f"Buen día {nombre_saludo}, ¿cómo estás?",
        "",
        f"Mi nombre es {director or f'[nombre {referencia_directivo}]'} y soy {cargo_directivo.lower()} del {departamento} de la {universidad}.",
        "",
        f"Me comunico para consultarte y confirmar la propuesta de designación correspondiente al {nombre_cuatrimestre} de {anio}, comprendido entre el {fecha_inicio_txt} y el {fecha_fin_txt}.",
        "",
        "Según la información registrada actualmente, tu situación prevista es la siguiente:",
        "",
        "Designación:",
    ]

    if df_desig.empty:
        lineas.append("- No figura ninguna designación cargada para este período.")
    else:
        for _, row in df_desig.iterrows():
            desde = _fecha_mensaje_docente(row.get("fecha_desde")) or fecha_inicio_txt
            hasta = _fecha_mensaje_docente(row.get("fecha_hasta")) or fecha_fin_txt
            partes = [
                str(row.get("tipo_designacion") or "Tipo de designación no informado").strip(),
                f"cargo {str(row.get('cargo') or 'no informado').strip()}",
                f"dedicación {str(row.get('dedicacion') or 'no informada').strip()}",
                _horas_mensaje(row.get("horas")),
                f"desde el {desde} hasta el {hasta}",
            ]
            if str(row.get("ad_honorem") or "").strip().lower() in ["sí", "si", "true", "1"]:
                partes.append("ad honorem")
            else:
                partes.append("no ad honorem")
            dep = str(row.get("departamento") or "").strip()
            if dep:
                partes.append(dep)
            lineas.append("- " + "; ".join(partes) + ".")

    lineas.extend(["", "Actividad docente prevista en comisiones:"])
    if df_comisiones.empty:
        lineas.append("- No figuran comisiones asignadas para este período.")
    else:
        for _, row in df_comisiones.iterrows():
            materia = str(row.get("asignatura") or "Materia no informada").strip()
            materia_especifica = str(row.get("materia_especifica") or "").strip()
            materia_mostrar = materia
            if materia_especifica and normalizar_clave(materia_especifica) != normalizar_clave(materia):
                materia_mostrar = f"{materia} ({materia_especifica})"
            codigo = str(row.get("codigo_materia") or "").strip()
            comision = str(row.get("nombre_comision") or "sin denominación").strip()
            rol = str(row.get("rol") or "rol no informado").strip()
            horarios = str(row.get("horarios") or "").strip()
            dep_com = str(row.get("departamento_comision") or "").strip()
            detalle = f"{codigo + ' - ' if codigo else ''}{materia_mostrar}, comisión {comision}, como {rol}"
            if horarios:
                detalle += f". Horario/s: {horarios}"
            if dep_com:
                detalle += f". Departamento responsable: {dep_com}"
            lineas.append(f"- {detalle}.")

    lineas.extend(["", "Participación en proyectos de investigación:"])
    if df_investigacion.empty:
        lineas.append("- No figura participación en proyectos de investigación para este período.")
    else:
        for _, row in df_investigacion.iterrows():
            nombre = str(row.get("nombre_proyecto") or "Proyecto sin nombre").strip()
            codigo = str(row.get("codigo_proyecto") or "").strip()
            instituto = str(row.get("instituto_proyecto") or "").strip()
            rol = str(row.get("rol") or "rol no informado").strip()
            ejecucion = str(row.get("periodo_ejecucion") or "").strip()
            detalle = f"{nombre}{f' (código {codigo})' if codigo else ''}, con rol de {rol}"
            if instituto:
                detalle += f", radicado en {instituto}"
            if ejecucion:
                detalle += f", período de ejecución {ejecucion}"
            lineas.append(f"- {detalle}.")

    # Extensión se incorpora al mensaje cuando el docente tiene una asignación
    # vigente en el período consultado, con el mismo criterio que Investigación.
    if df_extension is not None and not df_extension.empty:
        lineas.extend(["", "Participación en proyectos de extensión:"])
        for _, row in df_extension.iterrows():
            nombre = str(row.get("nombre_proyecto") or "Proyecto sin nombre").strip()
            codigo = str(row.get("codigo_proyecto") or "").strip()
            area = str(row.get("instituto_proyecto") or "").strip()
            rol = str(row.get("rol") or "rol no informado").strip()
            ejecucion = str(row.get("periodo_ejecucion") or "").strip()
            detalle = f"{nombre}{f' (código {codigo})' if codigo else ''}, con rol de {rol}"
            if area:
                detalle += f", radicado en {area}"
            if ejecucion:
                detalle += f", período de ejecución {ejecucion}"
            lineas.append(f"- {detalle}.")

    lineas.extend([
        "",
        "Te pido por favor que revises esta información y me confirmes si coincide con lo conversado y con tu disponibilidad para el cuatrimestre. En caso de detectar alguna diferencia en la designación, las comisiones, los horarios o la participación en investigación o extensión, indicámela para poder corregirla antes del inicio de las actividades.",
        "",
        "Saludos,",
        director or f"[nombre {referencia_directivo}]",
        f"{cargo_directivo} del {departamento} de la {universidad}",
    ])

    asunto = f"Consulta y confirmación de designación - {nombre_cuatrimestre.capitalize()} {anio}"
    advertencias = []
    if not director:
        advertencias.append(f"No está cargado el nombre {referencia_directivo} en los parámetros de Disposiciones.")
    if df_desig.empty:
        advertencias.append("El docente no tiene designaciones cargadas para el período seleccionado.")
    return asunto, "\n".join(lineas), advertencias
