"""GENERADO por tools_generar_complemento_resumen.py -- NO EDITAR A MANO.

Texto literal del entry certificado B13-FIX02 (app_postgresql_refactor_b13fix02_uat_fixes.py, sha256 95691fdf48c1edd393daf60bf435d6452b2fa8e95f6dcb7a2254cea8138d3363): definiciones del
Resumen docente (E4-05) que no estan en el motor de Analisis, 23 bloques en el orden del entry.
Se ejecuta DESPUES de ``analisis/motor/certificado.py`` en el mismo namespace del request
(``integraciones.resumen_docente``); nunca a nivel modulo.
"""
# flake8: noqa
# fmt: off

# --- entry (literal)
DIAS_SEMANA_V95 = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# --- entry l. 5121-5170
def fecha_finalizacion_resumen_docente(cuil, periodo_id):
    """Fecha mostrada en Resumen docente para el período seleccionado.

    Si hay designaciones activas en el período, devuelve la fecha de vencimiento
    más lejana. Si no las hay, devuelve la última fecha de baja real registrada
    en movimientos y, como respaldo, la fecha de finalización más reciente de
    una designación finalizada. No usa la fecha administrativa genérica del
    registro docente porque puede corresponder a una designación histórica.
    """
    conn = get_conn()
    try:
        df_act = pd.read_sql("""
            SELECT COUNT(*) AS cantidad,
                   MAX(NULLIF(fecha_hasta, '')) AS fecha
            FROM designaciones
            WHERE cuil=? AND periodo_id=? AND estado='Activa'
        """, conn, params=[cuil, int(periodo_id)])
        if not df_act.empty and int(df_act.iloc[0].get("cantidad", 0) or 0) > 0:
            # Si hay designación activa, nunca se reemplaza su vencimiento por
            # una baja histórica. Cuando la fecha no está cargada, se muestra '-'.
            return limpiar_texto_tabla(df_act.iloc[0].get("fecha", ""))

        df_baja = pd.read_sql("""
            SELECT MAX(NULLIF(fecha, '')) AS fecha
            FROM movimientos
            WHERE cuil=?
              AND (
                    LOWER(TRIM(COALESCE(tipo_movimiento, ''))) = 'baja de designación'
                    OR LOWER(TRIM(COALESCE(tipo_movimiento, ''))) = 'baja de docente'
                    OR LOWER(TRIM(COALESCE(tipo_movimiento, ''))) = 'finalización de designación'
                    OR LOWER(TRIM(COALESCE(tipo_movimiento, ''))) = 'finalizacion de designacion'
                    OR LOWER(TRIM(COALESCE(tipo_movimiento, ''))) = 'finalización automática por cierre de período'
                    OR LOWER(TRIM(COALESCE(tipo_movimiento, ''))) = 'finalizacion automatica por cierre de periodo'
                  )
        """, conn, params=[cuil])
        if not df_baja.empty:
            fecha_baja = limpiar_texto_tabla(df_baja.iloc[0].get("fecha", ""))
            if fecha_baja:
                return fecha_baja

        df_finalizada = pd.read_sql("""
            SELECT MAX(NULLIF(fecha_hasta, '')) AS fecha
            FROM designaciones
            WHERE cuil=? AND estado='Finalizada'
        """, conn, params=[cuil])
        if not df_finalizada.empty:
            return limpiar_texto_tabla(df_finalizada.iloc[0].get("fecha", ""))
        return ""
    finally:
        conn.close()


# --- entry l. 5172-5198
def estado_actual_docente(cuil):
    periodo = get_periodo_abierto()
    if periodo is None:
        return "Sin período abierto"

    conn = get_conn()
    df = pd.read_sql("""
        SELECT
            COUNT(*) AS designaciones_activas,
            COALESCE(SUM(horas), 0) AS horas_activas
        FROM designaciones
        WHERE cuil = ?
          AND periodo_id = ?
          AND estado = 'Activa'
    """, conn, params=[cuil, periodo["id"]])
    conn.close()

    if df.empty:
        return "Sin información"

    activas = int(df.iloc[0]["designaciones_activas"])
    horas = int(df.iloc[0]["horas_activas"])

    if activas > 0:
        return f"Activo en {periodo['nombre']} - {activas} designación/es - {horas} hs"

    return f"Sin designación activa en {periodo['nombre']}"


# --- entry l. 6009-6011
def get_disposiciones(periodo_id=None):
    from analisis.motor.ref.extracted_batch03.readonly_queries import get_disposiciones as _b03_core_get_disposiciones
    return _b03_core_get_disposiciones(periodo_id, get_conn=get_conn, pd=pd)


# --- entry l. 6254-6256
def formatear_nombre_escuela(valor):
    from analisis.motor.ref.domain.materias import formatear_nombre_escuela as _b05_core_formatear_nombre_escuela
    return _b05_core_formatear_nombre_escuela(valor)


# --- entry l. 14577-14579
def filtrar_dataframe_por_texto(df, texto, columnas):
    from analisis.motor.ref.common.text import filtrar_dataframe_por_texto as _b05_core_filtrar_dataframe_por_texto
    return _b05_core_filtrar_dataframe_por_texto(df, texto, columnas)


# --- entry l. 20973-21024
def get_comisiones_docente(cuil, periodo_id=None):
    """Comisiones de un docente con datos de materia desde la fuente única."""
    conn = get_conn()
    filtros = ["a.cuil = ?"]
    params = [cuil]
    if periodo_id is not None:
        filtros.append("co.periodo_id = ?")
        params.append(periodo_id)
    where = "WHERE " + " AND ".join(filtros)
    df = pd.read_sql(f"""
        SELECT
            p.nombre AS periodo,
            p.anio AS _periodo_anio,
            p.semestre AS _periodo_semestre,
            co.materia_id,
            co.nombre_comision,
            co.turno,
            co.sede,
            co.modalidad,
            a.rol,
            a.horas_asignadas,
            COALESCE((
                SELECT GROUP_CONCAT(h.dia || ' ' || h.hora_inicio || '-' || h.hora_fin || ' (' || h.horas || ' hs)', ' | ')
                FROM horarios_comision h
                WHERE h.comision_id = co.id
            ), '') AS horarios,
            a.observaciones
        FROM asignaciones_docentes_comision a
        LEFT JOIN comisiones co ON co.id = a.comision_id
        LEFT JOIN periodos p ON p.id = co.periodo_id
        {where}
    """, conn, params=params)
    conn.close()

    columnas = ["periodo", "codigo_materia", "asignatura", "carrera", "escuela", "plan_version", "nombre_comision", "turno", "sede", "modalidad", "rol", "horas_asignadas", "horarios", "observaciones"]
    if df.empty:
        return pd.DataFrame(columns=columnas)

    df_mat = get_materias_para_comisiones()
    if not df_mat.empty:
        meta = df_mat[["materia_id", "codigo", "asignatura", "carrera", "escuela", "plan_version"]].drop_duplicates(subset=["materia_id"]).rename(columns={"codigo": "codigo_materia"})
        df = df.merge(meta, on="materia_id", how="left")
    else:
        for col in ["codigo_materia", "asignatura", "carrera", "escuela", "plan_version"]:
            df[col] = ""

    for col in columnas:
        if col not in df.columns:
            df[col] = ""

    df = df.sort_values(["_periodo_anio", "_periodo_semestre", "escuela", "carrera", "codigo_materia", "nombre_comision"], ascending=[False, False, True, True, True, True], kind="stable")
    return df[columnas].reset_index(drop=True)


# --- entry l. 21031-21064
def get_materias_historicas_docente(cuil):
    df = get_comisiones_docente(cuil, periodo_id=None)
    columnas = ["codigo_materia", "asignatura", "carreras", "escuelas", "periodos", "comisiones", "roles"]
    if df.empty:
        return pd.DataFrame(columns=columnas)

    if "materia_especifica" not in df.columns:
        df["materia_especifica"] = ""

    def unir_unicos(serie):
        valores = []
        for v in serie:
            v = limpiar_texto_tabla(v)
            if v and v not in valores:
                valores.append(v)
        return " | ".join(valores)

    # La materia específica forma parte de la identidad visual histórica.
    # Así, dos opciones distintas cursadas en el mismo espacio Optativa II no se
    # fusionan en una sola fila incomprensible.
    registros = []
    for (codigo, asignatura, materia_especifica), grupo in df.groupby(
        ["codigo_materia", "asignatura", "materia_especifica"], dropna=False
    ):
        registros.append({
            "codigo_materia": codigo,
            "asignatura": _nombre_materia_visible_v138(codigo, asignatura, materia_especifica),
            "carreras": unir_unicos(grupo["carrera"]),
            "escuelas": unir_unicos(grupo["escuela"]),
            "periodos": unir_unicos(grupo["periodo"]),
            "comisiones": unir_unicos(grupo["nombre_comision"]),
            "roles": unir_unicos(grupo["rol"]),
        })
    return pd.DataFrame(registros, columns=columnas).sort_values(["codigo_materia", "asignatura"], kind="stable")


# --- entry l. 26477-26542
def _get_comisiones_docente_pg_global(cuil, periodo_id=None):
    """Comisiones del docente en toda la institución.

    Si se selecciona un período, se filtra por el nombre/año-semestre del período,
    no solo por el id local. Esto permite que el departamento de origen vea una
    comisión cargada en otro departamento que tiene su propio id de período.
    """
    inst_id = _pg_current_inst_id()
    filtros = ["a.cuil = %s", "co.institucion_id = %s", "COALESCE(a.estado, 'Activa') = 'Activa'"]
    params = [cuil, int(inst_id)]
    if periodo_id is not None:
        df_p_sel = _pg_read_dataframe("SELECT nombre, anio, semestre FROM periodos WHERE id = %s LIMIT 1", [periodo_id])
        if not df_p_sel.empty:
            psel = df_p_sel.iloc[0]
            nombre_p = str(psel.get("nombre") or "")
            anio_p = psel.get("anio")
            semestre_p = psel.get("semestre")
            filtros.append("(co.periodo_id = %s OR p.nombre = %s OR (p.anio = %s AND p.semestre = %s))")
            params.extend([periodo_id, nombre_p, int(anio_p), int(semestre_p)])
        else:
            filtros.append("co.periodo_id = %s")
            params.append(periodo_id)
    where = "WHERE " + " AND ".join(filtros)
    df = _pg_read_dataframe(f"""
        SELECT
            p.nombre AS periodo,
            p.anio AS _periodo_anio,
            p.semestre AS _periodo_semestre,
            dep.nombre AS departamento_comision,
            co.materia_id,
            m.codigo AS codigo_materia,
            m.asignatura,
            c.nombre AS carrera,
            c.escuela,
            COALESCE(m.plan_version, c.plan_version, '') AS plan_version,
            co.nombre_comision,
            co.turno,
            co.sede,
            co.modalidad,
            a.rol,
            a.horas_asignadas,
            COALESCE((
                SELECT STRING_AGG(h.dia || ' ' || h.hora_inicio || '-' || h.hora_fin || ' (' || h.horas || ' hs)', ' | ' ORDER BY
                    CASE h.dia
                        WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3
                        WHEN 'Jueves' THEN 4 WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6
                        WHEN 'Domingo' THEN 7 ELSE 99 END,
                    h.hora_inicio)
                FROM horarios_comision h
                WHERE h.comision_id = co.id
            ), '') AS horarios,
            a.observaciones
        FROM asignaciones_docentes_comision a
        LEFT JOIN comisiones co ON co.id = a.comision_id
        LEFT JOIN periodos p ON p.id = co.periodo_id
        LEFT JOIN departamentos dep ON dep.id = co.departamento_id
        LEFT JOIN materias m ON m.id = co.materia_id
        LEFT JOIN carreras c ON c.id = m.carrera_id
        {where}
        ORDER BY p.anio DESC, p.semestre DESC, dep.nombre, c.escuela, c.nombre, m.codigo, m.asignatura, co.nombre_comision
    """, params)
    columnas = ["periodo", "departamento_comision", "codigo_materia", "asignatura", "carrera", "escuela", "plan_version", "nombre_comision", "turno", "sede", "modalidad", "rol", "horas_asignadas", "horarios", "observaciones"]
    for col in columnas:
        if col not in df.columns:
            df[col] = ""
    return df[columnas].reset_index(drop=True)


# --- entry l. 26545
_get_comisiones_docente_original = get_comisiones_docente


# --- entry l. 26547-26559
def get_comisiones_docente(cuil, periodo_id=None):
    """Comisiones asignadas a un docente.

    En PostgreSQL se miran todas las comisiones de la misma institución por CUIL,
    incluso si fueron cargadas desde otro departamento. Esto permite que el
    departamento de origen vea qué hace un docente prestado en otro departamento.
    """
    if USE_POSTGRESQL:
        try:
            return _get_comisiones_docente_pg_global(cuil, periodo_id)
        except Exception:
            pass
    return _get_comisiones_docente_original(cuil, periodo_id)


# --- entry l. 27854-27856
def _clave_materia_unica_codigo_nombre(codigo, asignatura):
    from analisis.motor.ref.extracted_batch04.materias import _clave_materia_unica_codigo_nombre as _b04_core__clave_materia_unica_codigo_nombre
    return _b04_core__clave_materia_unica_codigo_nombre(codigo, asignatura)


# --- entry l. 30293-30295
def _normalizar_dia_v95(dia):
    from analisis.motor.ref.extracted_batch04.horarios import _normalizar_dia_v95 as _b04_core__normalizar_dia_v95
    return _b04_core__normalizar_dia_v95(dia)


# --- entry l. 30622-30662
def _get_comisiones_docente_pg_global(cuil, periodo_id=None):
    inst_id = _pg_current_inst_id()
    filtros = ["regexp_replace(COALESCE(a.cuil, ''), '[^0-9]', '', 'g')=%s", "co.institucion_id=%s", "COALESCE(a.estado,'Activa')='Activa'"]
    params = [_clave_cuil(cuil), int(inst_id)]
    if periodo_id is not None:
        nombre_p, anio_p, sem_p = _periodo_equivalente_pg(periodo_id)
        filtros.append("(co.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))")
        params += [int(periodo_id), nombre_p, int(anio_p), int(sem_p)]
    df = _pg_read_dataframe(f"""
        SELECT a.id AS asignacion_id, co.id AS comision_id, p.nombre AS periodo, dep.nombre AS departamento_comision,
               m.codigo AS codigo_materia, m.asignatura, COALESCE(co.materia_especifica, '') AS materia_especifica,
               c.nombre AS carrera, c.escuela,
               COALESCE(m.plan_version,c.plan_version,'') AS plan_version,
               co.nombre_comision, co.turno, co.sede, co.modalidad, a.rol,
               a.horas_asignadas, a.observaciones
        FROM asignaciones_docentes_comision a
        JOIN comisiones co ON co.id=a.comision_id
        LEFT JOIN periodos p ON p.id=co.periodo_id
        LEFT JOIN departamentos dep ON dep.id=co.departamento_id
        LEFT JOIN materias m ON m.id=co.materia_id
        LEFT JOIN carreras c ON c.id=m.carrera_id
        WHERE {' AND '.join(filtros)}
        ORDER BY p.anio DESC, p.semestre DESC, dep.nombre, m.codigo, co.nombre_comision
    """, params)
    if df.empty:
        return df

    # La comisión puede guardar una fila representativa de una materia que existe
    # en varios planes. En Resumen docente se muestran todas las carreras reales.
    df = _enriquecer_carreras_comisiones_docente_v98(df)

    dfh = _get_horarios_docente_periodo_pg_global(cuil, periodo_id) if periodo_id is not None else pd.DataFrame()
    horarios_map = {}
    if not dfh.empty:
        for aid, g in dfh.groupby("asignacion_id"):
            partes=[]
            for _, h in g.iterrows():
                partes.append(f"{h.get('dia','')} {_hora_texto_v95(h.get('hora_inicio'))}-{_hora_texto_v95(h.get('hora_fin'))} ({float(h.get('horas',0) or 0):g} hs)")
            horarios_map[int(aid)] = " | ".join(partes)
    df["horarios"] = df["asignacion_id"].map(lambda x: horarios_map.get(int(x), ""))
    return df.drop(columns=["asignacion_id", "comision_id"], errors="ignore")


# --- entry l. 30665-30681
def get_comisiones_docente(cuil, periodo_id=None):
    if USE_POSTGRESQL:
        return _get_comisiones_docente_pg_global(cuil, periodo_id)
    dfh = _horarios_docente_local_v95(cuil, periodo_id) if periodo_id is not None else pd.DataFrame()
    conn=get_conn(); params=[str(cuil)]; filtro=""
    if periodo_id is not None: filtro=" AND co.periodo_id=?"; params.append(int(periodo_id))
    df=pd.read_sql(f"""SELECT a.id AS asignacion_id,co.id AS comision_id,p.nombre AS periodo,'' AS departamento_comision,m.codigo AS codigo_materia,m.asignatura,COALESCE(co.materia_especifica,'') AS materia_especifica,c.nombre AS carrera,c.escuela,
        COALESCE(m.plan_version,c.plan_version,'') AS plan_version,co.nombre_comision,co.turno,co.sede,co.modalidad,a.rol,a.horas_asignadas,a.observaciones
        FROM asignaciones_docentes_comision a JOIN comisiones co ON co.id=a.comision_id LEFT JOIN periodos p ON p.id=co.periodo_id LEFT JOIN materias m ON m.id=co.materia_id LEFT JOIN carreras c ON c.id=m.carrera_id
        WHERE a.cuil=? AND COALESCE(a.estado,'Activa')='Activa' {filtro}""",conn,params=params);conn.close()
    if df.empty:return df
    df=_enriquecer_carreras_comisiones_docente_v98(df)
    hmap={}
    if not dfh.empty:
        for aid,g in dfh.groupby("asignacion_id"):
            hmap[int(aid)]=" | ".join([f"{r.get('dia','')} {_hora_texto_v95(r.get('hora_inicio'))}-{_hora_texto_v95(r.get('hora_fin'))} ({float(r.get('horas',0) or 0):g} hs)" for _,r in g.iterrows()])
    df["horarios"]=df["asignacion_id"].map(lambda x:hmap.get(int(x),""));return df.drop(columns=["asignacion_id","comision_id"],errors="ignore")


# --- entry l. 31014-31016
def _abreviar_asignatura_v95(nombre, max_len=18):
    from analisis.motor.ref.extracted_batch01.otros import _abreviar_asignatura_v95 as _b01_core__abreviar_asignatura_v95
    return _b01_core__abreviar_asignatura_v95(nombre, max_len)


# --- entry l. 31020-31090
def _detalle_materias_comisiones_v131(comision_ids):
    """Devuelve una fila por materia conceptual que integra cada comisión."""
    ids = []
    for valor in list(comision_ids or []):
        try:
            cid = int(valor)
        except Exception:
            continue
        if cid not in ids:
            ids.append(cid)
    columnas = ["comision_id", "codigo_materia", "asignatura", "carrera", "escuela", "plan_version", "contextos_plan_v131", "escuelas_v131"]
    if not ids:
        return pd.DataFrame(columns=columnas)
    try:
        vinculos = _leer_vinculos_materias_comisiones_v118(ids, global_institucion=bool(USE_POSTGRESQL))
    except Exception:
        vinculos = pd.DataFrame()
    if vinculos is None or vinculos.empty:
        return pd.DataFrame(columns=columnas)
    try:
        detalle_actual = _materias_para_comisiones_detalle()
    except Exception:
        detalle_actual = pd.DataFrame()
    actuales = {}
    if isinstance(detalle_actual, pd.DataFrame) and not detalle_actual.empty:
        col_id = "materia_id" if "materia_id" in detalle_actual.columns else "id" if "id" in detalle_actual.columns else None
        if col_id:
            for _, fila in detalle_actual.iterrows():
                try:
                    actuales[int(fila.get(col_id))] = fila.to_dict()
                except Exception:
                    pass
    filas = []
    for _, link in vinculos.iterrows():
        try:
            cid = int(link.get("comision_id")); mid = int(link.get("materia_id"))
        except Exception:
            continue
        act = actuales.get(mid, {}) or {}
        codigo = limpiar_texto_tabla(act.get("codigo", "")) or limpiar_texto_tabla(link.get("codigo_snapshot", ""))
        asignatura = limpiar_texto_tabla(act.get("asignatura", "")) or limpiar_texto_tabla(link.get("asignatura_snapshot", ""))
        if not codigo and not asignatura:
            continue
        carrera = limpiar_texto_tabla(link.get("carrera_snapshot", "")) or limpiar_texto_tabla(act.get("carrera", ""))
        escuela = limpiar_texto_tabla(link.get("escuela_snapshot", "")) or limpiar_texto_tabla(act.get("escuela", ""))
        plan = limpiar_texto_tabla(link.get("plan_version_snapshot", "")) or limpiar_texto_tabla(act.get("plan_version", ""))
        filas.append({"comision_id": cid, "codigo_materia": codigo, "asignatura": asignatura, "carrera": carrera, "escuela": escuela, "plan_version": plan,
                      "_clave_v131": _clave_materia_unica_codigo_nombre(codigo, asignatura) or f"{codigo}::{normalizar_clave(asignatura)}"})
    base = pd.DataFrame(filas)
    if base.empty:
        return pd.DataFrame(columns=columnas)
    salida = []
    for (cid, _), grupo in base.groupby(["comision_id", "_clave_v131"], dropna=False, sort=False):
        primera = grupo.iloc[0]
        contextos, escuelas_unicas = [], []
        for _, r in grupo.iterrows():
            car = limpiar_texto_tabla(r.get("carrera", "")); esc = formatear_nombre_escuela(limpiar_texto_tabla(r.get("escuela", "")))
            if esc and esc not in escuelas_unicas: escuelas_unicas.append(esc)
            ctx = f"{car}, {esc}" if car and esc else (car or esc)
            if ctx and ctx not in contextos: contextos.append(ctx)
        salida.append({
            "comision_id": int(cid),
            "codigo_materia": _deptit_join_unicos(grupo["codigo_materia"], sep=" / ") or limpiar_texto_tabla(primera.get("codigo_materia", "")),
            "asignatura": _deptit_join_unicos(grupo["asignatura"], sep=" / ") or limpiar_texto_tabla(primera.get("asignatura", "")),
            "carrera": _deptit_join_unicos(grupo["carrera"], sep=" / "),
            "escuela": _deptit_join_unicos(grupo["escuela"], sep=" / "),
            "plan_version": _deptit_join_unicos(grupo["plan_version"], sep=" / "),
            "contextos_plan_v131": "; ".join(contextos),
            "escuelas_v131": " / ".join(escuelas_unicas),
        })
    return pd.DataFrame(salida, columns=columnas)


# --- entry l. 31093-31115
def _expandir_horarios_por_materias_comision_v131(df):
    """Expande solo la vista para mostrar todas las materias de una comisión multicódigo."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty or "comision_id" not in df.columns:
        return df
    ids = pd.to_numeric(df["comision_id"], errors="coerce").dropna().astype(int).unique().tolist()
    detalle = _detalle_materias_comisiones_v131(ids)
    if detalle.empty:
        return df
    mapa = {int(cid): g.copy() for cid, g in detalle.groupby("comision_id", sort=False)}
    filas = []
    for _, fila in df.iterrows():
        try: cid = int(fila.get("comision_id"))
        except Exception: cid = None
        materias = mapa.get(cid) if cid is not None else None
        if materias is None or materias.empty:
            filas.append(fila.to_dict()); continue
        for _, mat in materias.iterrows():
            item = fila.to_dict()
            for col in ["codigo_materia", "asignatura", "carrera", "escuela", "plan_version", "contextos_plan_v131", "escuelas_v131"]:
                valor = mat.get(col, "")
                if valor is not None and str(valor).strip(): item[col] = valor
            filas.append(item)
    return pd.DataFrame(filas)


# --- entry l. 31209-31247
def get_trayectoria_docente_institucional_v149(cuil, periodo_id=None):
    """Fechas de trayectoria tomando designaciones reales del CUIL en toda la institución."""
    salida = {"inicio_historico": "", "ultima_alta": "", "vencimiento_periodo": "", "departamentos": []}
    if not USE_POSTGRESQL or not str(cuil or "").strip():
        return salida
    try:
        inst_id = _pg_current_inst_id()
        df_hist = _pg_read_dataframe("""
            SELECT d.fecha_desde, d.fecha_hasta,
                   COALESCE(NULLIF(d.fecha_hasta_prevista,''), d.fecha_hasta) AS fecha_hasta_prevista,
                   d.estado, d.departamento_id, COALESCE(dep.nombre,'Sin departamento') AS departamento
            FROM designaciones d
            LEFT JOIN departamentos dep ON dep.id=d.departamento_id
            WHERE d.institucion_id=%s
              AND regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g')=%s
            ORDER BY d.fecha_desde
        """, [int(inst_id), _clave_cuil(cuil)])
        if df_hist is not None and not df_hist.empty:
            fechas = pd.to_datetime(df_hist.get("fecha_desde"), errors="coerce")
            if fechas.notna().any():
                salida["inicio_historico"] = str(fechas.min().date())
                salida["ultima_alta"] = str(fechas.max().date())
        if periodo_id is not None:
            df_p = _get_designaciones_periodo_institucional_v149(cuil, periodo_id)
            if df_p is not None and not df_p.empty:
                deps = []
                for d in df_p.get("departamento", pd.Series(dtype=str)).dropna().astype(str):
                    d = limpiar_texto_tabla(d)
                    if d and d not in deps:
                        deps.append(d)
                salida["departamentos"] = deps
                df_act = df_p[df_p.get("estado", pd.Series(index=df_p.index, dtype=str)).fillna("").astype(str).str.strip().str.lower().eq("activa")].copy()
                df_v = df_act if not df_act.empty else df_p
                serie = pd.to_datetime(df_v.get("fecha_hasta_prevista", pd.Series(dtype=object)), errors="coerce")
                if serie.notna().any():
                    salida["vencimiento_periodo"] = str(serie.max().date())
    except Exception:
        pass
    return salida


# --- entry l. 31390-31438
def get_superposiciones_docente_institucional_v149(cuil, periodo_id):
    """Superposiciones del docente en toda la institución; solo para su Resumen individual."""
    columnas = ["docente", "cuil", "día", "departamento_1", "asignatura_1", "comisión_1", "horario_1", "departamento_2", "asignatura_2", "comisión_2", "horario_2"]
    try:
        dfh = _get_horarios_docente_periodo_pg_global(cuil, periodo_id) if USE_POSTGRESQL else _horarios_docente_local_v95(cuil, periodo_id)
    except Exception:
        dfh = pd.DataFrame()
    if dfh is None or dfh.empty:
        return pd.DataFrame(columns=columnas)
    try:
        dfh = _enriquecer_carreras_comisiones_docente_v98(dfh)
    except Exception:
        pass
    nombre_doc = str(cuil)
    try:
        df_doc = get_docentes()
        sub = df_doc[df_doc.get("cuil", pd.Series(index=df_doc.index, dtype=str)).fillna("").astype(str).map(_clave_cuil).eq(_clave_cuil(cuil))]
        if not sub.empty:
            nombre_doc = limpiar_texto_tabla(sub.iloc[0].get("nombre_completo", "")) or str(cuil)
    except Exception:
        pass
    registros, vistos = [], set()
    for dia, g in dfh.groupby("dia"):
        rows = list(g.sort_values("hora_inicio").to_dict("records"))
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                if a.get("comision_id") == b.get("comision_id"):
                    continue
                ai, af = _minutos_v95(a.get("hora_inicio")), _minutos_v95(a.get("hora_fin"))
                bi, bf = _minutos_v95(b.get("hora_inicio")), _minutos_v95(b.get("hora_fin"))
                if None in (ai, af, bi, bf) or max(ai, bi) >= min(af, bf):
                    continue
                clave = (str(dia), min(str(a.get("comision_id")), str(b.get("comision_id"))), max(str(a.get("comision_id")), str(b.get("comision_id"))), max(ai, bi), min(af, bf))
                if clave in vistos:
                    continue
                vistos.add(clave)
                registros.append({
                    "docente": nombre_doc, "cuil": cuil, "día": dia,
                    "departamento_1": limpiar_texto_tabla(a.get("departamento_comision", "")),
                    "asignatura_1": _nombre_materia_visible_v138(a.get("codigo_materia", ""), a.get("asignatura", ""), a.get("materia_especifica", "")),
                    "comisión_1": limpiar_texto_tabla(a.get("nombre_comision", "")),
                    "horario_1": f"{_hora_texto_v95(a.get('hora_inicio'))}-{_hora_texto_v95(a.get('hora_fin'))}",
                    "departamento_2": limpiar_texto_tabla(b.get("departamento_comision", "")),
                    "asignatura_2": _nombre_materia_visible_v138(b.get("codigo_materia", ""), b.get("asignatura", ""), b.get("materia_especifica", "")),
                    "comisión_2": limpiar_texto_tabla(b.get("nombre_comision", "")),
                    "horario_2": f"{_hora_texto_v95(b.get('hora_inicio'))}-{_hora_texto_v95(b.get('hora_fin'))}",
                })
    return pd.DataFrame(registros, columns=columnas)


# --- entry l. 32742-32768
def fecha_finalizacion_resumen_docente(cuil,periodo_id):
    conn=get_conn()
    try:
        df=pd.read_sql("""SELECT MAX(NULLIF(COALESCE(NULLIF(fecha_hasta_prevista,''),fecha_hasta),'')) AS fecha FROM designaciones WHERE cuil=? AND periodo_id=? AND estado='Activa'""",conn,params=[str(cuil),int(periodo_id)])
        fecha=limpiar_texto_tabla(df.iloc[0].get("fecha","")) if not df.empty else ""
        if fecha:return fecha
        df=pd.read_sql("""SELECT MAX(NULLIF(fecha_finalizacion_efectiva,'')) AS fecha FROM designaciones WHERE cuil=? AND estado='Finalizada'""",conn,params=[str(cuil)])
        fecha=limpiar_texto_tabla(df.iloc[0].get("fecha","")) if not df.empty else ""
        if fecha:return fecha
        # No usar un LIKE con % literal en una consulta parametrizada de psycopg2:
        # los signos % se interpretan como parte del formato de parámetros y pueden
        # provocar IndexError. Se enumeran los movimientos reales de baja/finalización.
        df=pd.read_sql("""
            SELECT MAX(NULLIF(fecha,'')) AS fecha
            FROM movimientos
            WHERE cuil=?
              AND LOWER(TRIM(COALESCE(tipo_movimiento,''))) IN (
                    'baja de designación',
                    'baja de docente',
                    'finalización de designación',
                    'finalizacion de designacion',
                    'finalización automática por cierre de período',
                    'finalizacion automatica por cierre de periodo'
              )
        """,conn,params=[str(cuil)])
        return limpiar_texto_tabla(df.iloc[0].get("fecha","")) if not df.empty else ""
    finally:conn.close()


# --- entry l. 51302-51473
def get_actos_docente_resumen_v263(cuil):
    """Consolida actos del repositorio, disposiciones generadas y resoluciones de designación."""
    asegurar_esquema_documentos_respaldo_docentes_v251()
    asegurar_esquema_dependencias_documentales_v262()
    clave = _clave_cuil(cuil) or re.sub(r"[^0-9]", "", str(cuil or ""))
    columnas = ["Código", "Dependencia emisora", "Tipo de movimiento", "Detalle", "_fecha", "_fuente"]
    filas = []
    if not clave:
        return pd.DataFrame(columns=columnas[:4])

    # 1) PDFs/actos del repositorio vinculados expresamente al docente.
    try:
        if USE_POSTGRESQL:
            inst = _pg_current_inst_id()
            repo = _pg_read_dataframe("""
                SELECT d.id, COALESCE(d.tipo_documento,'') AS tipo_documento,
                       COALESCE(d.numero,'') AS numero, d.fecha,
                       COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                                CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                                     WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora,
                       COALESCE(NULLIF(TRIM(rd.tipo_movimiento),''), d.categoria, '') AS tipo_movimiento,
                       COALESCE(NULLIF(TRIM(rd.detalle_vinculo),''), d.detalle, '') AS detalle
                FROM documentos_respaldo_docentes rd
                JOIN documentos_respaldo d
                  ON d.id=rd.documento_id
                 AND d.institucion_id=rd.institucion_id
                 AND d.departamento_id=rd.departamento_id
                LEFT JOIN dependencias_documentales depdoc
                  ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
                WHERE rd.institucion_id=%s
                  AND REGEXP_REPLACE(COALESCE(rd.cuil,''), '[^0-9]', '', 'g')=%s
                ORDER BY d.fecha DESC NULLS LAST, d.id DESC
            """, [int(inst), str(clave)])
        else:
            conn = get_conn()
            repo = pd.read_sql("""
                SELECT d.id, COALESCE(d.tipo_documento,'') AS tipo_documento,
                       COALESCE(d.numero,'') AS numero, d.fecha,
                       COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                                CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                                     WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora,
                       COALESCE(NULLIF(TRIM(rd.tipo_movimiento),''), d.categoria, '') AS tipo_movimiento,
                       COALESCE(NULLIF(TRIM(rd.detalle_vinculo),''), d.detalle, '') AS detalle
                FROM documentos_respaldo_docentes rd
                JOIN documentos_respaldo d ON d.id=rd.documento_id
                LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id
                ORDER BY d.fecha DESC, d.id DESC
            """, conn)
            conn.close()
            if not repo.empty:
                repo = repo[repo.index.map(lambda _: True)].copy()
                # SQLite local: el filtro por CUIL se resuelve leyendo la relación para evitar dependencias de REGEXP_REPLACE.
                conn = get_conn()
                rel = pd.read_sql("SELECT documento_id,cuil FROM documentos_respaldo_docentes", conn); conn.close()
                ids_ok = set(pd.to_numeric(rel[rel["cuil"].map(lambda x: (_clave_cuil(x) or re.sub(r'[^0-9]','',str(x or ''))) == clave)]["documento_id"], errors="coerce").dropna().astype(int).tolist()) if not rel.empty else set()
                repo = repo[pd.to_numeric(repo["id"], errors="coerce").isin(ids_ok)].copy()
        if repo is not None and not repo.empty:
            for _, r in repo.iterrows():
                filas.append({
                    "Código": _etiqueta_acto_v263(r.get("tipo_documento"), r.get("numero")),
                    "Dependencia emisora": str(r.get("dependencia_emisora", "") or "").strip(),
                    "Tipo de movimiento": str(r.get("tipo_movimiento", "") or "").strip(),
                    "Detalle": str(r.get("detalle", "") or "").strip(),
                    "_fecha": r.get("fecha"), "_fuente": 0,
                })
    except Exception:
        pass

    # 2) Disposiciones generadas por la propia aplicación.
    try:
        if USE_POSTGRESQL:
            inst = _pg_current_inst_id()
            disp = _pg_read_dataframe("""
                SELECT d.numero, d.fecha, COALESCE(d.tipo,'') AS tipo,
                       COALESCE(d.detalle,'') AS detalle,
                       COALESCE(dep.nombre,'') AS dependencia_emisora
                FROM disposiciones d
                LEFT JOIN departamentos dep
                  ON dep.id=d.departamento_id AND dep.institucion_id=d.institucion_id
                WHERE d.institucion_id=%s
                  AND REGEXP_REPLACE(COALESCE(d.cuil,''), '[^0-9]', '', 'g')=%s
                ORDER BY d.fecha DESC, d.id DESC
            """, [int(inst), str(clave)])
        else:
            disp = get_disposiciones()
            if disp is not None and not disp.empty:
                disp = disp[disp.get("cuil", pd.Series(index=disp.index, dtype=str)).map(lambda x: (_clave_cuil(x) or re.sub(r"[^0-9]", "", str(x or ""))) == clave)].copy()
                dep_actual = str((current_user() or {}).get("departamento_nombre") or "").strip()
                disp["dependencia_emisora"] = dep_actual
        if disp is not None and not disp.empty:
            for _, r in disp.iterrows():
                filas.append({
                    "Código": _etiqueta_acto_v263("Disposición", r.get("numero")),
                    "Dependencia emisora": str(r.get("dependencia_emisora", "") or "").strip(),
                    "Tipo de movimiento": "Generación de disposición",
                    "Detalle": str(r.get("detalle", "") or r.get("tipo", "") or "").strip(),
                    "_fecha": r.get("fecha"), "_fuente": 1,
                })
    except Exception:
        pass

    # 3) Referencias manuales históricas todavía pendientes de vincular al repositorio.
    try:
        if USE_POSTGRESQL:
            inst = _pg_current_inst_id()
            des = _pg_read_dataframe("""
                SELECT COALESCE(d.numero_resolucion,'') AS numero_resolucion,
                       COALESCE(d.cargo,'') AS cargo, COALESCE(d.dedicacion,'') AS dedicacion,
                       COALESCE(d.tipo_designacion,'') AS tipo_designacion,
                       COALESCE(d.ad_honorem,'No') AS ad_honorem,
                       COALESCE(p.nombre,'') AS periodo, d.fecha_desde
                FROM designaciones d
                LEFT JOIN periodos p
                  ON p.id=d.periodo_id AND p.institucion_id=d.institucion_id AND p.departamento_id=d.departamento_id
                LEFT JOIN documentos_respaldo_designaciones adr
                  ON adr.designacion_id=d.id AND adr.institucion_id=d.institucion_id AND adr.departamento_id=d.departamento_id
                WHERE d.institucion_id=%s
                  AND REGEXP_REPLACE(COALESCE(d.cuil,''), '[^0-9]', '', 'g')=%s
                  AND TRIM(COALESCE(d.numero_resolucion,''))<>''
                  AND adr.id IS NULL
                ORDER BY d.fecha_desde DESC NULLS LAST, d.id DESC
            """, [int(inst), str(clave)])
        else:
            conn = get_conn()
            des = pd.read_sql("""
                SELECT COALESCE(d.numero_resolucion,'') AS numero_resolucion,
                       COALESCE(d.cargo,'') AS cargo, COALESCE(d.dedicacion,'') AS dedicacion,
                       COALESCE(d.tipo_designacion,'') AS tipo_designacion,
                       COALESCE(d.ad_honorem,'No') AS ad_honorem,
                       COALESCE(p.nombre,'') AS periodo, d.fecha_desde, d.cuil
                FROM designaciones d LEFT JOIN periodos p ON p.id=d.periodo_id
                LEFT JOIN documentos_respaldo_designaciones adr ON adr.designacion_id=d.id
                WHERE TRIM(COALESCE(d.numero_resolucion,''))<>'' AND adr.id IS NULL
                ORDER BY d.fecha_desde DESC, d.id DESC
            """, conn); conn.close()
            if not des.empty:
                des = des[des["cuil"].map(lambda x: (_clave_cuil(x) or re.sub(r"[^0-9]", "", str(x or ""))) == clave)].copy()
        if des is not None and not des.empty:
            for _, r in des.iterrows():
                tipo_des = str(r.get("tipo_designacion", "") or "").strip()
                dependencia = "Consejo Superior" if tipo_des.casefold() == "concursado" else "Rectorado"
                detalle = " · ".join([x for x in [
                    str(r.get("periodo", "") or "").strip(),
                    str(r.get("cargo", "") or "").strip(),
                    str(r.get("dedicacion", "") or "").strip(),
                    tipo_des,
                    ("Ad Honorem" if _es_ad_honorem_v162(r.get("ad_honorem")) else "Rentada"),
                ] if x])
                filas.append({
                    "Código": _etiqueta_acto_v263("Resolución", r.get("numero_resolucion")) + " — pendiente de vincular al repositorio",
                    "Dependencia emisora": dependencia,
                    "Tipo de movimiento": "Designación docente (pendiente de vincular)",
                    "Detalle": detalle,
                    "_fecha": r.get("fecha_desde"), "_fuente": 2,
                })
    except Exception:
        pass

    if not filas:
        return pd.DataFrame(columns=columnas[:4])
    out = pd.DataFrame(filas)
    out["_fecha_ord"] = pd.to_datetime(out.get("_fecha"), errors="coerce")
    # Si el mismo acto ya está en el repositorio, se prioriza esa versión por tener el respaldo documental.
    out["_dup"] = (
        out["Código"].fillna("").astype(str).str.strip().str.casefold() + "|" +
        out["Dependencia emisora"].fillna("").astype(str).str.strip().str.casefold() + "|" +
        out["Tipo de movimiento"].fillna("").astype(str).str.strip().str.casefold()
    )
    out = out.sort_values(["_fuente", "_fecha_ord"], ascending=[True, False], kind="stable")
    out = out.drop_duplicates("_dup", keep="first")
    out = out.sort_values(["_fecha_ord", "_fuente"], ascending=[False, True], kind="stable")
    return out[["Código", "Dependencia emisora", "Tipo de movimiento", "Detalle"]].reset_index(drop=True)


# --- entry l. 55807
_get_actos_docente_resumen_pre_v266 = get_actos_docente_resumen_v263


# --- entry l. 55808-55874
def get_actos_docente_resumen_v263(cuil):
    """v266: suma los vínculos exactos de designaciones/movimientos al resumen existente."""
    try:
        asegurar_esquema_actos_administrativos_v266()
    except Exception:
        pass
    try:
        base=_get_actos_docente_resumen_pre_v266(cuil)
    except Exception:
        base=pd.DataFrame(columns=["Código","Dependencia emisora","Tipo de movimiento","Detalle"])
    filas=[]; clave=_clave_cuil(cuil) or str(cuil or "").strip()
    if not clave:
        return base
    try:
        if USE_POSTGRESQL:
            inst=_pg_current_inst_id()
            extra_df=_pg_read_dataframe("""
                SELECT d.tipo_documento, COALESCE(d.numero,'') AS numero,
                       COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,'') AS dependencia_emisora,
                       'Designación docente' AS tipo_movimiento,
                       'Acto administrativo vinculado a designación' AS detalle
                FROM documentos_respaldo_designaciones r
                JOIN documentos_respaldo d ON d.id=r.documento_id AND d.institucion_id=r.institucion_id
                JOIN designaciones des ON des.id=r.designacion_id AND des.institucion_id=r.institucion_id AND des.departamento_id=r.departamento_id
                LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
                WHERE r.institucion_id=%s AND regexp_replace(COALESCE(des.cuil,''),'[^0-9]','','g')=%s
                UNION ALL
                SELECT d.tipo_documento, COALESCE(d.numero,'') AS numero,
                       COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,'') AS dependencia_emisora,
                       COALESCE(m.tipo_movimiento,'') AS tipo_movimiento,
                       COALESCE(m.detalle,'') AS detalle
                FROM documentos_respaldo_movimientos r
                JOIN documentos_respaldo d ON d.id=r.documento_id AND d.institucion_id=r.institucion_id
                JOIN movimientos m ON m.id=r.movimiento_id AND m.institucion_id=r.institucion_id AND m.departamento_id=r.departamento_id
                LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
                WHERE r.institucion_id=%s AND regexp_replace(COALESCE(m.cuil,''),'[^0-9]','','g')=%s
            """,[int(inst),clave,int(inst),clave])
        else:
            conn=get_conn(); extra_df=pd.read_sql("""
                SELECT d.tipo_documento, COALESCE(d.numero,'') AS numero,
                       COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,'') AS dependencia_emisora,
                       'Designación docente' AS tipo_movimiento,
                       'Acto administrativo vinculado a designación' AS detalle
                FROM documentos_respaldo_designaciones r
                JOIN documentos_respaldo d ON d.id=r.documento_id
                JOIN designaciones des ON des.id=r.designacion_id
                LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id
                WHERE REPLACE(REPLACE(REPLACE(des.cuil,'-',''),'.',''),' ','')=?
                UNION ALL
                SELECT d.tipo_documento, COALESCE(d.numero,'') AS numero,
                       COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,'') AS dependencia_emisora,
                       COALESCE(m.tipo_movimiento,'') AS tipo_movimiento,
                       COALESCE(m.detalle,'') AS detalle
                FROM documentos_respaldo_movimientos r
                JOIN documentos_respaldo d ON d.id=r.documento_id
                JOIN movimientos m ON m.id=r.movimiento_id
                LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id
                WHERE REPLACE(REPLACE(REPLACE(m.cuil,'-',''),'.',''),' ','')=?
            """,conn,params=[clave,clave]); conn.close()
        for _,r in extra_df.iterrows():
            filas.append({"Código":_etiqueta_acto_v263(r.get("tipo_documento"),r.get("numero")),"Dependencia emisora":str(r.get("dependencia_emisora") or ""),"Tipo de movimiento":str(r.get("tipo_movimiento") or ""),"Detalle":str(r.get("detalle") or "")})
    except Exception:
        pass
    if filas:
        base=pd.concat([base,pd.DataFrame(filas)],ignore_index=True,sort=False)
        base=base.drop_duplicates(subset=[c for c in ["Código","Dependencia emisora","Tipo de movimiento","Detalle"] if c in base.columns],keep="first")
    return base.reset_index(drop=True)
