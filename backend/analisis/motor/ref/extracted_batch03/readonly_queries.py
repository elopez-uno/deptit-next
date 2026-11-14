# Batch 03: read-only R1 functions with explicit dependency injection.
from __future__ import annotations

def _pg_available(*, USE_POSTGRESQL):
    if not USE_POSTGRESQL:
        return False
    try:
        import psycopg2
        return True
    except Exception:
        return False


def _pg_pool_cached(db_url, minconn, maxconn, connect_timeout, *, ThreadedConnectionPool):
    """Crea un pool thread-safe y lo conserva entre reruns de Streamlit."""
    from psycopg2.pool import ThreadedConnectionPool
    return ThreadedConnectionPool(int(minconn), int(maxconn), dsn=str(db_url), connect_timeout=int(connect_timeout), application_name='deptit_streamlit', keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3)


def _pg_first_inst_id(*, _pg_read_dataframe):
    try:
        df = _pg_read_dataframe('SELECT id FROM instituciones ORDER BY id LIMIT 1', [])
        if not df.empty:
            return int(df.iloc[0]['id'])
    except Exception:
        pass
    return None


def get_departamentos_auth(institucion_id=None, solo_activos=False, *, get_auth_conn, pd):
    conn = get_auth_conn()
    filtros = []
    params = []
    if institucion_id is not None:
        filtros.append('d.institucion_id = ?')
        params.append(int(institucion_id))
    if solo_activos:
        filtros.append("d.estado = 'Activo'")
    where = 'WHERE ' + ' AND '.join(filtros) if filtros else ''
    df = pd.read_sql(f'\n        SELECT d.*, i.nombre AS institucion, i.slug AS institucion_slug\n        FROM departamentos d\n        LEFT JOIN instituciones i ON i.id = d.institucion_id\n        {where}\n        ORDER BY i.nombre, d.nombre\n    ', conn, params=params)
    conn.close()
    return df


def get_usuarios_auth(institucion_id=None, *, get_auth_conn, pd):
    conn = get_auth_conn()
    filtros = []
    params = []
    if institucion_id is not None:
        filtros.append('u.institucion_id = ?')
        params.append(int(institucion_id))
    where = 'WHERE ' + ' AND '.join(filtros) if filtros else ''
    df = pd.read_sql(f"\n        SELECT\n            u.id, u.institucion_id, u.departamento_id, u.nombre, u.email, u.rol, u.estado,\n            u.fecha_alta, u.observaciones,\n            i.nombre AS institucion,\n            d.nombre AS departamento\n        FROM app_usuarios u\n        LEFT JOIN instituciones i ON i.id = u.institucion_id\n        LEFT JOIN departamentos d ON d.id = u.departamento_id\n        {where}\n        ORDER BY COALESCE(i.nombre, 'Sistema'), u.rol, u.nombre, u.email\n    ", conn, params=params)
    conn.close()
    return df


def contar_usuarios_activos_institucion(institucion_id, *, get_auth_conn):
    conn = get_auth_conn()
    c = conn.cursor()
    c.execute("\n        SELECT COUNT(*)\n        FROM app_usuarios\n        WHERE institucion_id = ?\n          AND estado = 'Activo'\n          AND rol <> 'superadmin'\n    ", (int(institucion_id),))
    total = int(c.fetchone()[0] or 0)
    conn.close()
    return total


def get_ultimo_periodo(*, get_conn, pd):
    conn = get_conn()
    df = pd.read_sql('\n        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones\n        FROM periodos\n        ORDER BY anio DESC, semestre DESC, id DESC\n        LIMIT 1\n    ', conn)
    conn.close()
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_disposiciones(periodo_id=None, *, get_conn, pd):
    conn = get_conn()
    filtro = ''
    params = []
    if periodo_id is not None:
        filtro = 'WHERE d.periodo_id = ?'
        params = [periodo_id]
    df = pd.read_sql(f'\n        SELECT\n            d.id,\n            d.periodo_id,\n            p.nombre AS periodo,\n            d.fecha,\n            d.numero,\n            d.tipo,\n            d.cuil,\n            d.docente,\n            d.estado,\n            d.detalle,\n            d.observaciones,\n            d.archivo_word,\n            d.plantilla_usada,\n            d.fecha_creacion\n        FROM disposiciones d\n        LEFT JOIN periodos p ON p.id = d.periodo_id\n        {filtro}\n        ORDER BY COALESCE(p.anio, 0) DESC, COALESCE(p.semestre, 0) DESC, d.fecha DESC, d.id DESC\n    ', conn, params=params)
    conn.close()
    return df


def contar_datos_asociados_periodo(periodo_id, *, get_conn, pd):
    """Cuenta datos vinculados a un período para decidir si puede eliminarse.

    Criterio: Eliminar período queda reservado para períodos vacíos creados por error.
    Si hay designaciones, movimientos de gestión, comisiones, inscriptos, investigación,
    extensión o disposiciones, no se permite borrar. Los movimientos simples de apertura
    no bloquean la eliminación porque se generan automáticamente al crear el período.
    """
    conn = get_conn()
    try:
        sql = "\n            SELECT\n                (SELECT COUNT(*) FROM designaciones WHERE periodo_id = ?) AS designaciones,\n                (SELECT COUNT(*) FROM movimientos WHERE periodo_id = ?) AS movimientos_total,\n                (SELECT COUNT(*) FROM movimientos\n                    WHERE periodo_id = ?\n                      AND COALESCE(tipo_movimiento, '') NOT IN ('Apertura de período')\n                ) AS movimientos_gestion,\n                (SELECT COUNT(*) FROM comisiones WHERE periodo_id = ?) AS comisiones,\n                (SELECT COUNT(*) FROM horarios_comision\n                    WHERE comision_id IN (SELECT id FROM comisiones WHERE periodo_id = ?)\n                ) AS horarios_comision,\n                (SELECT COUNT(*) FROM asignaciones_docentes_comision\n                    WHERE comision_id IN (SELECT id FROM comisiones WHERE periodo_id = ?)\n                ) AS asignaciones_comision,\n                (SELECT COUNT(*) FROM horarios_asignacion_docente_comision\n                    WHERE asignacion_id IN (\n                        SELECT id FROM asignaciones_docentes_comision\n                        WHERE comision_id IN (SELECT id FROM comisiones WHERE periodo_id = ?)\n                    )\n                ) AS horarios_asignacion_docente,\n                ((SELECT COUNT(*) FROM inscriptos_comision\n                    WHERE comision_id IN (SELECT id FROM comisiones WHERE periodo_id = ?))\n                 + (SELECT COUNT(*) FROM inscriptos_comision_materia\n                    WHERE comision_id IN (SELECT id FROM comisiones WHERE periodo_id = ?))\n                 + (SELECT COUNT(*) FROM inscriptos_asignatura_periodo WHERE periodo_id = ?)\n                ) AS inscriptos,\n                (SELECT COUNT(*) FROM investigacion_docente WHERE periodo_id = ?) AS investigacion,\n                (SELECT COUNT(*) FROM extension_docente WHERE periodo_id = ?) AS extension,\n                (SELECT COUNT(*) FROM actividades_especiales WHERE periodo_id = ?) AS actividades_especiales,\n                (SELECT COUNT(*) FROM actividad_especial_docente WHERE periodo_id = ?) AS asignaciones_actividades_especiales,\n                (SELECT COUNT(*) FROM disposiciones WHERE periodo_id = ?) AS disposiciones\n        "
        row = pd.read_sql(sql, conn, params=[periodo_id, periodo_id, periodo_id, periodo_id, periodo_id, periodo_id, periodo_id, periodo_id, periodo_id, periodo_id, periodo_id, periodo_id, periodo_id, periodo_id, periodo_id]).iloc[0].to_dict()
        return {k: int(v or 0) for k, v in row.items()}
    finally:
        conn.close()


def get_opcion_curricular_v120(opcion_id, *, get_planes_conn, pd):
    try:
        oid = int(opcion_id)
    except Exception:
        return None
    conn = get_planes_conn()
    try:
        df = pd.read_sql('\n            SELECT id, tipo, codigo, nombre, escuela_oferente, estado, observaciones,\n                   fecha_creacion, fecha_actualizacion\n            FROM opciones_curriculares\n            WHERE id = ?\n            LIMIT 1\n        ', conn, params=[oid])
    finally:
        conn.close()
    return None if df.empty else df.iloc[0].to_dict()


def get_facultades_escuelas_disponibles(*, get_planes_conn, pd):
    """Devuelve Facultades/Escuelas cargadas solo para la universidad activa.

    No usa una lista global ni toma opciones de otra universidad. Si una
    universidad todavía no tiene planes, devuelve lista vacía y permite escribir
    manualmente la primera Facultad/Escuela.
    """
    valores = []
    try:
        conn = get_planes_conn()
        consultas = ["SELECT DISTINCT escuela AS valor FROM carreras WHERE escuela IS NOT NULL AND TRIM(escuela) <> ''", "SELECT DISTINCT escuela AS valor FROM materias WHERE escuela IS NOT NULL AND TRIM(escuela) <> ''"]
        for sql in consultas:
            try:
                df = pd.read_sql(sql, conn)
                valores.extend(df['valor'].dropna().astype(str).str.strip().tolist())
            except Exception:
                pass
        conn.close()
    except Exception:
        pass
    unicos = sorted({v for v in valores if str(v).strip()}, key=lambda x: x.lower())
    return unicos


def get_carrera(carrera_id, *, get_planes_conn, pd):
    conn = get_planes_conn()
    df = pd.read_sql('\n        SELECT\n            id,\n            escuela,\n            codigo,\n            nombre,\n            titulo_otorga,\n            plan_version,\n            duracion,\n            estado,\n            observaciones\n        FROM carreras\n        WHERE id = ?\n        LIMIT 1\n    ', conn, params=[carrera_id])
    conn.close()
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_plan_estudio(carrera_id, *, get_planes_conn, pd):
    conn = get_planes_conn()
    df = pd.read_sql("\n        SELECT\n            id,\n            carrera_id,\n            orden,\n            codigo,\n            asignatura,\n            anio,\n            cuatrimestre,\n            dictado,\n            carga_semanal,\n            carga_total,\n            duracion,\n            estado,\n            observaciones,\n            COALESCE(comparticion_modo, 'Automática') AS comparticion_modo,\n            COALESCE(comparticion_grupo, '') AS comparticion_grupo\n        FROM materias\n        WHERE carrera_id = ?\n          AND COALESCE(en_plan, 1) = 1\n        ORDER BY\n            CASE anio\n                WHEN '1° Año' THEN 1\n                WHEN '2° Año' THEN 2\n                WHEN '3° Año' THEN 3\n                WHEN '4° Año' THEN 4\n                WHEN '5° Año' THEN 5\n                WHEN '6° Año' THEN 6\n                ELSE 99\n            END,\n            CASE cuatrimestre\n                WHEN '1' THEN 1\n                WHEN '2' THEN 2\n                WHEN '1 y 2' THEN 3\n                ELSE 9\n            END,\n            COALESCE(orden, 9999),\n            asignatura\n    ", conn, params=[carrera_id])
    conn.close()
    return df


def get_plan_estudio_todas(*, get_planes_conn, pd):
    """Devuelve todas las materias de la universidad activa con datos de carrera/plan."""
    conn = get_planes_conn()
    df = pd.read_sql("\n        SELECT\n            m.id,\n            m.carrera_id,\n            m.orden,\n            m.codigo,\n            m.asignatura,\n            COALESCE(c.nombre, m.carrera) AS carrera,\n            COALESCE(c.escuela, m.escuela) AS escuela,\n            COALESCE(c.plan_version, m.plan_version) AS plan_version,\n            m.anio,\n            m.cuatrimestre,\n            m.dictado,\n            m.carga_semanal,\n            m.carga_total,\n            m.duracion,\n            m.estado,\n            m.observaciones,\n            COALESCE(m.comparticion_modo, 'Automática') AS comparticion_modo,\n            COALESCE(m.comparticion_grupo, '') AS comparticion_grupo,\n            COALESCE(m.en_plan, 1) AS en_plan\n        FROM materias m\n        LEFT JOIN carreras c ON c.id = m.carrera_id\n        ORDER BY escuela, carrera, plan_version,\n            CASE m.anio\n                WHEN '1° Año' THEN 1\n                WHEN '2° Año' THEN 2\n                WHEN '3° Año' THEN 3\n                WHEN '4° Año' THEN 4\n                WHEN '5° Año' THEN 5\n                WHEN '6° Año' THEN 6\n                ELSE 99\n            END,\n            CASE m.cuatrimestre\n                WHEN '1' THEN 1\n                WHEN '2' THEN 2\n                WHEN '1 y 2' THEN 3\n                ELSE 9\n            END,\n            COALESCE(m.orden, 9999),\n            m.codigo,\n            m.asignatura\n    ", conn)
    conn.close()
    return df


def get_movimientos_comision_en_curso(comision_id, periodo_id=None, *, get_conn, pd):
    """Historial específico de altas/bajas de docentes en una comisión en curso."""
    if not comision_id:
        return pd.DataFrame(columns=['fecha', 'tipo_movimiento', 'cuil', 'nombre', 'detalle', 'observaciones'])
    conn = get_conn()
    filtros = ['(m.detalle LIKE ? OR m.observaciones LIKE ?)']
    marca = f'%Comisión ID {int(comision_id)}%'
    params = [marca, marca]
    if periodo_id is not None:
        filtros.append('m.periodo_id = ?')
        params.append(int(periodo_id))
    where = 'WHERE ' + ' AND '.join(filtros)
    df = pd.read_sql(f'\n        SELECT m.fecha, m.tipo_movimiento, m.cuil, m.nombre, m.detalle, m.observaciones\n        FROM movimientos m\n        {where}\n        ORDER BY m.fecha, m.id\n    ', conn, params=params)
    conn.close()
    return df


def get_periodo_anterior_cronologico(periodo_id, *, get_conn, pd):
    """
    Devuelve el período inmediatamente anterior al seleccionado.
    Sirve para inferir bajas docentes aunque no exista un movimiento manual cargado.
    """
    conn = get_conn()
    df_actual = pd.read_sql('\n        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones\n        FROM periodos\n        WHERE id = ?\n        LIMIT 1\n    ', conn, params=[periodo_id])
    if df_actual.empty:
        conn.close()
        return None
    actual = df_actual.iloc[0].to_dict()
    df_ant = pd.read_sql('\n        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones\n        FROM periodos\n        WHERE\n            (anio < ?)\n            OR (anio = ? AND semestre < ?)\n        ORDER BY anio DESC, semestre DESC, id DESC\n        LIMIT 1\n    ', conn, params=[int(actual['anio']), int(actual['anio']), int(actual['semestre'])])
    conn.close()
    if df_ant.empty:
        return None
    return df_ant.iloc[0].to_dict()


def _periodo_equivalente_pg(periodo_id, *, _pg_read_dataframe):
    """Devuelve datos del período para cruzar departamentos con IDs distintos."""
    try:
        df_p = _pg_read_dataframe('SELECT nombre, anio, semestre FROM periodos WHERE id = %s LIMIT 1', [periodo_id])
        if not df_p.empty:
            r = df_p.iloc[0]
            return (str(r.get('nombre') or ''), int(r.get('anio') or 0), int(r.get('semestre') or 0))
    except Exception:
        pass
    return ('', 0, 0)


def _v279_tabla_pg_existe(cur, nombre):
    cur.execute('SELECT to_regclass(%s)', [f'public.{nombre}'])
    row = cur.fetchone()
    return bool(row and row[0])


def _sql_periodos_vigentes_v238(*, _fecha_pg_v238):
    pini = _fecha_pg_v238('p.fecha_inicio')
    pfin = _fecha_pg_v238('p.fecha_fin')
    return f"\n        periodos_parse AS (\n            SELECT p.*, {pini} AS inicio_date, {pfin} AS fin_date\n            FROM periodos p\n            WHERE p.institucion_id=%s\n        ),\n        pactual AS (\n            SELECT DISTINCT ON (p.departamento_id)\n                   p.departamento_id,\n                   p.id AS periodo_actual_id,\n                   p.nombre AS periodo_actual,\n                   COALESCE(p.estado,'Abierto') AS periodo_estado,\n                   p.inicio_date AS periodo_inicio,\n                   p.fin_date AS periodo_fin\n            FROM periodos_parse p\n            WHERE p.inicio_date IS NOT NULL\n              AND p.fin_date IS NOT NULL\n              AND p.inicio_date <= CURRENT_DATE\n              AND p.fin_date >= CURRENT_DATE\n              AND UPPER(BTRIM(COALESCE(p.estado,'Abierto'))) <> 'CERRADO'\n            ORDER BY p.departamento_id, p.inicio_date DESC, p.fin_date DESC,\n                     p.anio DESC, p.semestre DESC, p.id DESC\n        )\n    "


def _sql_designaciones_vigentes_v238(*, _fecha_pg_v238):
    ddesde = _fecha_pg_v238('d.fecha_desde')
    dhasta = _fecha_pg_v238("COALESCE(NULLIF(CAST(d.fecha_finalizacion_efectiva AS text),''), NULLIF(CAST(d.fecha_hasta_prevista AS text),''), CAST(d.fecha_hasta AS text))")
    return f"\n        designaciones_parse AS (\n            SELECT d.*,\n                   regexp_replace(COALESCE(CAST(d.cuil AS text),''),'[^0-9]','','g') AS cuil_clave,\n                   {ddesde} AS desde_date,\n                   {dhasta} AS hasta_date\n            FROM designaciones d\n            WHERE d.institucion_id=%s\n        ),\n        vigentes AS (\n            SELECT d.*, dep.nombre AS departamento_nombre,\n                   pa.periodo_actual, pa.periodo_inicio, pa.periodo_fin\n            FROM designaciones_parse d\n            JOIN pactual pa\n              ON pa.departamento_id=d.departamento_id\n             AND pa.periodo_actual_id=d.periodo_id\n            JOIN departamentos dep\n              ON dep.id=d.departamento_id\n             AND dep.institucion_id=d.institucion_id\n            WHERE UPPER(BTRIM(COALESCE(d.estado,'Activa')))='ACTIVA'\n              AND COALESCE(d.funcion_no_docente,0)=0\n              AND COALESCE(d.cuil_clave,'')<>''\n              AND (d.desde_date IS NULL OR d.desde_date <= CURRENT_DATE)\n              AND (d.hasta_date IS NULL OR d.hasta_date >= CURRENT_DATE)\n        )\n    "
