"""GENERADO por tools_generar_motor_analisis.py -- NO EDITAR A MANO.

Texto literal del entry certificado B13-FIX02 (app_postgresql_refactor_b13fix02_uat_fixes.py, sha256 95691fdf48c1edd393daf60bf435d6452b2fa8e95f6dcb7a2254cea8138d3363): cierre transitivo de la
pagina Analisis (l. 66604-67763), 613 bloques en el orden del entry.  Las referencias a
``deptit_refactor`` apuntan a la copia literal ``analisis.motor.ref``.  Se compila y ejecuta por request en un
namespace propio (``analisis.motor.entorno``); nunca a nivel modulo.
"""
# flake8: noqa
# fmt: off

# --- entry (literal)
DB_PATH = "C:/Users/augus/app_uoeste/designaciones.db"
# --- entry (literal)
ESTADOS_OPCION_CURRICULAR = ["Activa", "Inactiva"]
# --- entry (literal)
PG_DEPARTMENT_TABLES = {
    "periodos", "docentes", "designaciones", "movimientos", "comisiones",
    "horarios_comision", "asignaciones_docentes_comision", "inscriptos_comision", "investigacion_docente", "extension_docente",
    "disposiciones", "config_disposiciones", "resoluciones", "disposicion_parametros",
    "disposicion_docente_parametros", "estado_consulta_designacion",
    "horarios_asignacion_docente_comision", "actividades_especiales", "actividad_especial_docente",
    "comision_materias", "inscriptos_comision_materia", "inscriptos_asignatura_periodo", "correcciones_historial_horas",
    "config_productividad_departamento", "prestamos_docentes", "documentos_respaldo", "documentos_respaldo_docentes", "documentos_respaldo_proyectos",
    "documentos_respaldo_designaciones", "documentos_respaldo_movimientos",
}
# --- entry (literal)
PG_INSTITUTION_TABLES = {"carreras", "materias", "proyectos_investigacion", "proyectos_extension", "disposicion_docente_designaciones", "opciones_curriculares", "opcion_curricular_materias", "escalas_salariales_docentes", "dependencias_documentales"}
# --- entry (literal)
PLANES_INSTITUCIONALES_DB_FILENAME = "_planes_estudio.db"
# --- entry (literal)
PLANES_SECRETARIA_OLD_DB_FILENAME = "_secretaria_academica_planes.db"
# --- entry (literal)
_PERF_DB_COUNT_V192 = 0
# --- entry (literal)
_PERF_DB_POR_FUNC_V192 = {}
# --- entry (literal)
_PERF_DB_ROWS_V192 = 0
# --- entry (literal)
_PERF_DB_SECONDS_V192 = 0.0
# --- entry (literal)
_PERF_FUNC_STACK_V193 = []
# --- entry (literal)
_PERF_SQL_COUNT_V191 = 0
# --- entry (literal)
_PERF_SQL_POR_FUNC_V192 = {}
# --- entry (literal)
_PERF_SQL_SECONDS_V191 = 0.0
# --- entry (literal)
_PERF_SQL_SLOW_THRESHOLD_V191 = 0.075
# --- entry (literal)
_PERF_SQL_SLOW_V191 = []

# --- entry l. 198-223
def _perf_caller_app_v192():
    """Busca la función de negocio más cercana que originó una consulta."""
    excluir = {
        "_perf_registrar_sql_v191", "_perf_registrar_db_v192",
        "_perf_caller_app_v192", "_pg_read_dataframe", "_pd_read_sql_deptit",
        "execute", "cursor", "get_conn", "_pg_raw_conn", "_pg_borrow_raw_connection",
        "_pg_return_raw_connection", "_pg_prepare_sql", "_pg_scope_select",
        "_pg_scope_insert", "_pg_scope_update_delete", "_pg_convert_sql",
    }
    try:
        frame = inspect.currentframe()
        if frame is not None:
            frame = frame.f_back
        pasos = 0
        app_file = str(Path(__file__).resolve())
        while frame is not None and pasos < 30:
            code = frame.f_code
            nombre = str(code.co_name or "")
            archivo = str(Path(code.co_filename).resolve()) if code.co_filename else ""
            if archivo == app_file and nombre not in excluir and not nombre.startswith("_perf_"):
                return nombre
            frame = frame.f_back
            pasos += 1
    except Exception:
        pass
    return "sin_atribuir"


# --- entry l. 226-245
def _perf_sql_por_func_v192(sql, elapsed):
    if not _perf_habilitado_v191():
        return
    try:
        nombre = _perf_caller_app_v192()
        d = _PERF_SQL_POR_FUNC_V192.setdefault(nombre, {
            "consultas": 0,
            "segundos": 0.0,
            "max_ms": 0.0,
            "ejemplo": "",
        })
        elapsed = float(elapsed or 0)
        d["consultas"] += 1
        d["segundos"] += elapsed
        d["max_ms"] = max(float(d.get("max_ms", 0) or 0), elapsed * 1000.0)
        if not d.get("ejemplo"):
            resumen = " ".join(str(sql or "").strip().split())
            d["ejemplo"] = resumen[:220] + ("..." if len(resumen) > 220 else "")
    except Exception:
        pass


# --- entry l. 248-271
def _perf_registrar_db_v192(sql, elapsed, filas=0, origen="db"):
    """Mide preparación + conexión + execute + fetch + creación del DataFrame."""
    if not _perf_habilitado_v191():
        return
    global _PERF_DB_COUNT_V192, _PERF_DB_SECONDS_V192, _PERF_DB_ROWS_V192
    try:
        elapsed = float(elapsed or 0)
        filas = int(filas or 0)
        _PERF_DB_COUNT_V192 += 1
        _PERF_DB_SECONDS_V192 += elapsed
        _PERF_DB_ROWS_V192 += max(filas, 0)
        nombre = _perf_caller_app_v192()
        d = _PERF_DB_POR_FUNC_V192.setdefault(nombre, {
            "accesos": 0,
            "segundos": 0.0,
            "filas": 0,
            "max_ms": 0.0,
        })
        d["accesos"] += 1
        d["segundos"] += elapsed
        d["filas"] += max(filas, 0)
        d["max_ms"] = max(float(d.get("max_ms", 0) or 0), elapsed * 1000.0)
    except Exception:
        pass


# --- entry l. 279-283
def _perf_habilitado_v191():
    try:
        return bool(st.session_state.get("_perf_diagnostico_v191", False))
    except Exception:
        return False


# --- entry l. 286-311
def _perf_registrar_sql_v191(sql, elapsed, origen="sql"):
    """Registra tiempos solo cuando el diagnóstico está activado."""
    if not _perf_habilitado_v191():
        return
    global _PERF_SQL_COUNT_V191, _PERF_SQL_SECONDS_V191, _PERF_SQL_SLOW_V191
    try:
        elapsed = float(elapsed or 0)
        _PERF_SQL_COUNT_V191 += 1
        _PERF_SQL_SECONDS_V191 += elapsed
        _perf_sql_por_func_v192(sql, elapsed)
        if elapsed >= _PERF_SQL_SLOW_THRESHOLD_V191:
            resumen = " ".join(str(sql or "").strip().split())
            if len(resumen) > 260:
                resumen = resumen[:257] + "..."
            _PERF_SQL_SLOW_V191.append({
                "Tiempo (ms)": round(elapsed * 1000.0, 1),
                "Origen": str(origen),
                "Consulta": resumen,
            })
            _PERF_SQL_SLOW_V191 = sorted(
                _PERF_SQL_SLOW_V191,
                key=lambda x: float(x.get("Tiempo (ms)", 0) or 0),
                reverse=True,
            )[:25]
    except Exception:
        pass


# --- entry l. 492
LEGACY_DB_PATH = DB_PATH


# --- entry l. 518-521
def horas_segun_dedicacion(dedicacion, fallback=0):
    """Fuente única de horas contractuales según la dedicación docente."""
    from analisis.motor.ref.domain.catalog_unlocked.designaciones import horas_segun_dedicacion as _b08_core_horas_segun_dedicacion
    return _b08_core_horas_segun_dedicacion(dedicacion, fallback)


# --- entry l. 550-559
def _valor_configuracion(nombre, default=""):
    valor_entorno = os.environ.get(nombre)
    if valor_entorno is not None and str(valor_entorno).strip() != "":
        return valor_entorno
    try:
        if nombre in st.secrets:
            return st.secrets[nombre]
    except Exception:
        pass
    return default


# --- entry l. 591-593
def _pg_available():
    from analisis.motor.ref.extracted_batch03.readonly_queries import _pg_available as _b03_core__pg_available
    return _b03_core__pg_available(USE_POSTGRESQL=USE_POSTGRESQL)


# --- entry l. 776-777
def _pg_raw_conn():
    return _PgPooledRawConnection()


# --- entry l. 780-821
def _pg_split_sql_args(arg_text):
    """Separa argumentos SQL por coma a nivel superior, respetando comillas y paréntesis."""
    args = []
    actual = []
    depth = 0
    in_single = False
    in_double = False
    i = 0
    s = str(arg_text or "")
    while i < len(s):
        ch = s[i]
        if in_single:
            actual.append(ch)
            if ch == "'" and i + 1 < len(s) and s[i + 1] == "'":
                actual.append(s[i + 1]); i += 2; continue
            if ch == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            actual.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True; actual.append(ch); i += 1; continue
        if ch == '"':
            in_double = True; actual.append(ch); i += 1; continue
        if ch == '(':
            depth += 1; actual.append(ch); i += 1; continue
        if ch == ')':
            depth = max(0, depth - 1); actual.append(ch); i += 1; continue
        if ch == ',' and depth == 0:
            args.append(''.join(actual).strip())
            actual = []
            i += 1
            continue
        actual.append(ch); i += 1
    if actual or s.strip():
        args.append(''.join(actual).strip())
    return args


# --- entry l. 824-827
def _pg_quote_literal_text(valor, default=', '):
    'Convierte un literal SQL simple a texto seguro para usar como separador.'
    from analisis.motor.ref.extracted_batch01.infra_db import _pg_quote_literal_text as _b01_core__pg_quote_literal_text
    return _b01_core__pg_quote_literal_text(valor, default)


# --- entry l. 830-895
def _pg_convert_group_concat(sql):
    """Convierte GROUP_CONCAT de SQLite a STRING_AGG de PostgreSQL sin romper subconsultas.

    La conversión anterior usaba regex amplias y podía transformar mal casos como:
    SELECT GROUP_CONCAT(DISTINCT d.cargo) FROM designaciones d
    dejándolo como STRING_AGG(DISTINCT (d.cargo) FROM..., lo que causaba errores
    de sintaxis en módulos como Análisis.
    """
    s = str(sql or "")
    out = []
    i = 0
    pat = re.compile(r"GROUP_CONCAT\s*\(", flags=re.I)
    while True:
        m = pat.search(s, i)
        if not m:
            out.append(s[i:])
            break
        out.append(s[i:m.start()])
        open_pos = s.find('(', m.start())
        depth = 0
        in_single = False
        in_double = False
        j = open_pos
        end_pos = None
        while j < len(s):
            ch = s[j]
            if in_single:
                if ch == "'" and j + 1 < len(s) and s[j + 1] == "'":
                    j += 2; continue
                if ch == "'":
                    in_single = False
                j += 1; continue
            if in_double:
                if ch == '"':
                    in_double = False
                j += 1; continue
            if ch == "'":
                in_single = True; j += 1; continue
            if ch == '"':
                in_double = True; j += 1; continue
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    end_pos = j
                    break
            j += 1
        if end_pos is None:
            # Si no se pudo parsear, deja el texto original.
            out.append(s[m.start():])
            i = len(s)
            break
        args_text = s[open_pos + 1:end_pos]
        args = _pg_split_sql_args(args_text)
        expr = args[0] if args else "''"
        sep = _pg_quote_literal_text(args[1], ', ') if len(args) > 1 else ', '
        expr_strip = str(expr).strip()
        if expr_strip.upper().startswith('DISTINCT '):
            expr2 = expr_strip[9:].strip()
            repl = f"STRING_AGG(DISTINCT ({expr2})::text, '{sep}')"
        else:
            repl = f"STRING_AGG(({expr_strip})::text, '{sep}')"
        out.append(repl)
        i = end_pos + 1
    return ''.join(out)


# --- entry l. 896-904
def _pg_convert_sql(sql):
    sql = str(sql or "")
    # placeholders SQLite -> psycopg2
    sql = sql.replace("?", "%s")
    # funciones SQLite frecuentes
    sql = re.sub(r"\bIFNULL\s*\(", "COALESCE(", sql, flags=re.I)
    # GROUP_CONCAT de SQLite -> STRING_AGG de PostgreSQL, con parseo seguro.
    sql = _pg_convert_group_concat(sql)
    return sql


# --- entry l. 907-909
def _pg_first_inst_id():
    from analisis.motor.ref.extracted_batch03.readonly_queries import _pg_first_inst_id as _b03_core__pg_first_inst_id
    return _b03_core__pg_first_inst_id(_pg_read_dataframe=_pg_read_dataframe)


# --- entry l. 910-918
def _pg_inst_id_from_slug(slug):
    slug = _slugify(slug or "")
    try:
        df = _pg_read_dataframe("SELECT id FROM instituciones WHERE slug = %s LIMIT 1", [slug])
        if not df.empty:
            return int(df.iloc[0]["id"])
    except Exception:
        pass
    return None


# --- entry l. 921-929
def _pg_dep_id_from_slug(inst_id, dep_slug):
    dep_slug = _slugify(dep_slug or "")
    try:
        df = _pg_read_dataframe("SELECT id FROM departamentos WHERE institucion_id = %s AND slug = %s LIMIT 1", [int(inst_id), dep_slug])
        if not df.empty:
            return int(df.iloc[0]["id"])
    except Exception:
        pass
    return None


# --- entry l. 932-946
def _pg_current_inst_id():
    try:
        user = current_user() or {}
    except Exception:
        user = {}
    try:
        if user.get("rol") == "superadmin" and st.session_state.get("superadmin_institucion_id"):
            return int(st.session_state.get("superadmin_institucion_id"))
        if user.get("institucion_id"):
            return int(user.get("institucion_id"))
        if st.session_state.get("superadmin_institucion_id"):
            return int(st.session_state.get("superadmin_institucion_id"))
    except Exception:
        pass
    return _pg_first_inst_id()


# --- entry l. 949-965
def _pg_current_dep_id():
    try:
        if st.session_state.get("tenant_scope_departamento_id"):
            return int(st.session_state.get("tenant_scope_departamento_id"))
        user = current_user() or {}
        if user.get("departamento_id"):
            return int(user.get("departamento_id"))
    except Exception:
        pass
    try:
        inst_id = _pg_current_inst_id()
        df = _pg_read_dataframe("SELECT id FROM departamentos WHERE institucion_id = %s ORDER BY id LIMIT 1", [inst_id])
        if not df.empty:
            return int(df.iloc[0]["id"])
    except Exception:
        pass
    return None


# --- entry l. 968-993
def _pg_read_dataframe(sql, params=None):
    """Ejecuta una lectura usando una conexión reutilizada del pool."""
    _t_db_v192 = time.perf_counter()
    conn = _pg_raw_conn()
    cur = None
    _filas_db_v192 = 0
    try:
        cur = conn.cursor()
        _t_sql_v191 = time.perf_counter()
        cur.execute(_pg_convert_sql(sql), list(params or []))
        _perf_registrar_sql_v191(sql, time.perf_counter() - _t_sql_v191, "_pg_read_dataframe")
        rows = cur.fetchall() if cur.description else []
        cols = [d[0] for d in cur.description] if cur.description else []
        _filas_db_v192 = len(rows)
        df_v192 = pd.DataFrame(rows, columns=cols)
        _perf_registrar_db_v192(
            sql, time.perf_counter() - _t_db_v192, _filas_db_v192, "_pg_read_dataframe"
        )
        return df_v192
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        conn.close()


# --- entry l. 1292-1299
def _pg_conn(kind="auth", institucion_id=None, departamento_id=None):
    if not _pg_available():
        raise RuntimeError("PostgreSQL está activado, pero falta instalar psycopg2-binary. Ejecutá: pip install psycopg2-binary")
    if institucion_id is None and kind in ["tenant", "planes"]:
        institucion_id = _pg_current_inst_id()
    if departamento_id is None and kind == "tenant":
        departamento_id = _pg_current_dep_id()
    return PgConnectionCompat(kind=kind, institucion_id=institucion_id, departamento_id=departamento_id)


# --- entry l. 1344-1355
def _pg_count_table(table, institucion_id=None, departamento_id=None):
    table = str(table or "").lower()
    if table in PG_INSTITUTION_TABLES:
        return int(_pg_read_dataframe(f"SELECT COUNT(*) AS n FROM {table} WHERE institucion_id = %s", [int(institucion_id or _pg_current_inst_id())]).iloc[0]["n"] or 0)
    if table in PG_DEPARTMENT_TABLES:
        params = [int(institucion_id or _pg_current_inst_id())]
        sql = f"SELECT COUNT(*) AS n FROM {table} WHERE institucion_id = %s"
        if departamento_id is not None:
            sql += " AND departamento_id = %s"
            params.append(int(departamento_id))
        return int(_pg_read_dataframe(sql, params).iloc[0]["n"] or 0)
    return int(_pg_read_dataframe(f"SELECT COUNT(*) AS n FROM {table}", []).iloc[0]["n"] or 0)


# --- entry l. 1652-1655
def get_conn():
    if USE_POSTGRESQL:
        return _pg_conn("tenant")
    return sqlite3.connect(DB_PATH)


# --- entry l. 1657-1665
def add_column_if_not_exists(cursor, table, column, definition):
    if USE_POSTGRESQL:
        # El esquema PostgreSQL se creó con el script de migración. Se deja no-op
        # para evitar ejecutar PRAGMA/ALTER de SQLite sobre PostgreSQL.
        return
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


# --- entry l. 1669-1671
def _slugify(valor):
    from analisis.motor.ref.extracted_batch02.safe_helpers import _slugify as _b02_core__slugify
    return _b02_core__slugify(valor)


# --- entry l. 1685-1689
def get_auth_conn():
    if USE_POSTGRESQL:
        return _pg_conn("auth")
    os.makedirs(APP_BASE_DIR, exist_ok=True)
    return sqlite3.connect(AUTH_DB_PATH)


# --- entry l. 1816-1821
def get_instituciones_auth(solo_activas=False):
    conn = get_auth_conn()
    filtro = "WHERE estado = 'Activa'" if solo_activas else ""
    df = pd.read_sql(f"SELECT * FROM instituciones {filtro} ORDER BY nombre", conn)
    conn.close()
    return df


# --- entry l. 2002-2038
def _copiar_tabla_completa(origen_db, destino_db, tabla):
    """Copia esquema y datos de una tabla del origen al destino reemplazando contenido.

    Se usa para planes de estudio compartidos en la UNO: carreras y materias son institucionales,
    no departamentales. No copia docentes, designaciones ni comisiones.
    """
    if not os.path.exists(origen_db):
        return 0
    conn_o = sqlite3.connect(origen_db)
    conn_d = sqlite3.connect(destino_db)
    try:
        sql_schema = pd.read_sql(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            conn_o,
            params=[tabla]
        )
        if sql_schema.empty or not str(sql_schema.iloc[0]["sql"] or "").strip():
            return 0
        # Reemplaza completamente solo la tabla de planes solicitada.
        # Antes intentaba crear la tabla aunque ya existiera y podía fallar con:
        # sqlite3.OperationalError: table carreras already exists.
        conn_d.execute(f"DROP TABLE IF EXISTS {tabla}")
        conn_d.execute(str(sql_schema.iloc[0]["sql"]))
        df = pd.read_sql(f"SELECT * FROM {tabla}", conn_o)
        if not df.empty:
            cols = list(df.columns)
            placeholders = ",".join(["?"] * len(cols))
            col_sql = ",".join([f'"{c}"' for c in cols])
            conn_d.executemany(
                f"INSERT INTO {tabla} ({col_sql}) VALUES ({placeholders})",
                df.where(pd.notna(df), None).values.tolist()
            )
        conn_d.commit()
        return len(df)
    finally:
        conn_o.close()
        conn_d.close()


# --- entry l. 2041-2054
def planes_institucionales_db_path(institucion_slug):
    """Archivo único de planes de estudio de una institución.

    A partir de esta versión, carreras y materias no son una copia propia de
    Secretaría Académica ni de cada departamento. Todas las cuentas de una misma
    universidad leen y editan este único archivo: `_planes_estudio.db`.
    Las bases departamentales pueden conservar una copia de consulta para módulos
    históricos, pero la fuente real de edición es siempre este archivo.
    """
    inst_slug = _slugify(institucion_slug or "institucion")
    carpeta = os.path.join(TENANT_DATA_DIR, inst_slug)
    if not USE_POSTGRESQL:  # B13-FIX02 K1: en PostgreSQL el path es puro (sin mkdir de la carpeta SQLite heredada)
        os.makedirs(carpeta, exist_ok=True)
    return os.path.join(carpeta, PLANES_INSTITUCIONALES_DB_FILENAME)


# --- entry l. 2057-2063
def planes_secretaria_antigua_db_path(institucion_slug):
    """Ruta de la base vieja de Secretaría Académica, solo como fuente de migración."""
    inst_slug = _slugify(institucion_slug or "institucion")
    carpeta = os.path.join(TENANT_DATA_DIR, inst_slug)
    if not USE_POSTGRESQL:  # B13-FIX02 K1: en PostgreSQL el path es puro (sin mkdir de la carpeta SQLite heredada)
        os.makedirs(carpeta, exist_ok=True)
    return os.path.join(carpeta, PLANES_SECRETARIA_OLD_DB_FILENAME)


# --- entry l. 2066-2090
def _contar_filas_tabla_db(db_path, tabla):
    if USE_POSTGRESQL:
        try:
            inst_slug = _inferir_institucion_slug_desde_db(db_path)
            inst_id = _pg_inst_id_from_slug(inst_slug) if inst_slug else _pg_current_inst_id()
            dep_id = None
            try:
                base = os.path.basename(str(db_path or ""))
                if base.endswith(".db") and not base.startswith("_") and base != "consolidado.db":
                    dep_slug = os.path.splitext(base)[0]
                    dep_id = _pg_dep_id_from_slug(inst_id, dep_slug)
            except Exception:
                dep_id = None
            return _pg_count_table(tabla, inst_id, dep_id)
        except Exception:
            return 0
    if not db_path or not os.path.exists(db_path):
        return 0
    try:
        conn = sqlite3.connect(db_path)
        n = int(pd.read_sql(f"SELECT COUNT(*) AS n FROM {tabla}", conn).iloc[0]["n"] or 0)
        conn.close()
        return n
    except Exception:
        return 0


# --- entry l. 2092-2097
def _contar_planes_db(db_path):
    """Devuelve cantidad de carreras/materias de una base, sin romper si faltan tablas."""
    return {
        "carreras": _contar_filas_tabla_db(db_path, "carreras"),
        "materias": _contar_filas_tabla_db(db_path, "materias"),
    }


# --- entry l. 2100-2102
def _puntaje_planes_db(db_path):
    c = _contar_planes_db(db_path)
    return int(c.get("carreras", 0) or 0) + int(c.get("materias", 0) or 0)


# --- entry l. 2105-2115
def _db_tiene_planes(db_path):
    """Indica si una base tiene planes de estudio cargados.

    Se considera que tiene planes si existe al menos una carrera o una materia.
    Esta función se usa para evitar errores cuando Secretaría Académica está vacía
    o cuando una base departamental todavía no tiene creadas esas tablas.
    """
    return (
        _contar_filas_tabla_db(db_path, "carreras") > 0
        or _contar_filas_tabla_db(db_path, "materias") > 0
    )


# --- entry l. 2120-2164
def asegurar_esquema_planes_db(db_path):
    if USE_POSTGRESQL:
        return
    if not db_path:
        return
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS carreras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            escuela TEXT,
            nombre TEXT,
            codigo TEXT,
            titulo_otorga TEXT,
            plan_version TEXT,
            duracion TEXT,
            estado TEXT DEFAULT 'Activa',
            observaciones TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS materias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT,
            asignatura TEXT,
            carrera TEXT,
            escuela TEXT,
            anio TEXT,
            dictado TEXT,
            carga_semanal INTEGER,
            carga_total INTEGER,
            cuatrimestre TEXT,
            duracion TEXT
        )
    """)
    add_column_if_not_exists(c, "materias", "carrera_id", "INTEGER")
    add_column_if_not_exists(c, "materias", "plan_version", "TEXT")
    add_column_if_not_exists(c, "materias", "orden", "INTEGER")
    add_column_if_not_exists(c, "materias", "estado", "TEXT DEFAULT 'Activa'")
    add_column_if_not_exists(c, "materias", "observaciones", "TEXT")
    add_column_if_not_exists(c, "materias", "en_plan", "INTEGER DEFAULT 1")
    c.execute("UPDATE materias SET en_plan = 1 WHERE en_plan IS NULL")
    conn.commit()
    conn.close()


# --- entry l. 2217-2223
def get_planes_conn():
    """Conexión a la fuente única de planes de la universidad actual."""
    if USE_POSTGRESQL:
        return _pg_conn("planes", institucion_id=_pg_current_inst_id())
    inst_slug = institucion_slug_actual_operativa()
    asegurar_planes_secretaria_institucion_desde_mejor_fuente(inst_slug, forzar=False)
    return sqlite3.connect(planes_institucionales_db_path(inst_slug))


# --- entry l. 2233-2244
def _inferir_institucion_slug_desde_db(db_path):
    """Intenta obtener el slug de institución a partir de una ruta dentro de datos_instituciones."""
    try:
        abs_db = os.path.abspath(db_path)
        abs_tenant = os.path.abspath(TENANT_DATA_DIR)
        rel = os.path.relpath(abs_db, abs_tenant)
        partes = rel.split(os.sep)
        if len(partes) >= 2:
            return _slugify(partes[0])
    except Exception:
        pass
    return ""


# --- entry l. 2247-2255
def _institucion_slug_por_id(institucion_id):
    try:
        df_inst = get_instituciones_auth(solo_activas=False)
        fila = df_inst[df_inst["id"] == int(institucion_id)]
        if not fila.empty:
            return _slugify(fila.iloc[0].get("slug") or fila.iloc[0].get("nombre"))
    except Exception:
        pass
    return ""


# --- entry l. 2270-2291
def institucion_slug_actual_operativa(default="universidad_nacional_del_oeste"):
    """Devuelve la institución sobre la que está trabajando la pantalla actual."""
    try:
        user = current_user() or {}
        if current_role() == "superadmin":
            inst_id = st.session_state.get("superadmin_institucion_id") or user.get("institucion_id")
            if inst_id:
                slug = _institucion_slug_por_id(inst_id)
                if slug:
                    return slug
        if user.get("institucion_slug"):
            return _slugify(user.get("institucion_slug"))
        if user.get("institucion_id"):
            slug = _institucion_slug_por_id(user.get("institucion_id"))
            if slug:
                return slug
        slug_db = _inferir_institucion_slug_desde_db(DB_PATH)
        if slug_db:
            return slug_db
    except Exception:
        pass
    return _slugify(default or "universidad_nacional_del_oeste")


# --- entry l. 2294-2332
def _buscar_mejor_fuente_planes_institucion(institucion_slug, excluir_db=None):
    """Busca fuente de planes sin mezclar universidades.

    Regla nueva:
    - Para cualquier universidad, la única fuente real es su propio
      `_planes_estudio.db`.
    - Para universidades nuevas o sin planes cargados, se deja vacío.
    - Solo para UNO se permite usar la base histórica como migración inicial,
      porque esos planes pertenecen a la UNO.

    No se toman planes desde departamentos, consolidado ni Secretaría vieja de
    otras universidades. Esto evita que UBA u otra institución herede escuelas
    o planes de la UNO por accidente.
    """
    inst_slug = _slugify(institucion_slug or "")
    excluir_abs = os.path.abspath(excluir_db) if excluir_db else ""
    candidatos = []

    fuente_unica = planes_institucionales_db_path(inst_slug)
    if os.path.exists(fuente_unica) and os.path.abspath(fuente_unica) != excluir_abs and _db_tiene_planes(fuente_unica):
        candidatos.append((fuente_unica, "Archivo único de planes"))

    if inst_slug == "universidad_nacional_del_oeste":
        secretaria_vieja_db = planes_secretaria_antigua_db_path(inst_slug)
        if os.path.exists(secretaria_vieja_db) and os.path.abspath(secretaria_vieja_db) != excluir_abs and _db_tiene_planes(secretaria_vieja_db):
            candidatos.append((secretaria_vieja_db, "Base anterior de Secretaría Académica UNO"))
        if os.path.exists(LEGACY_DB_PATH) and os.path.abspath(LEGACY_DB_PATH) != excluir_abs and _db_tiene_planes(LEGACY_DB_PATH):
            candidatos.append((LEGACY_DB_PATH, "Base histórica UNO"))

    mejor_db = None
    mejor_desc = ""
    mejor_puntaje = 0
    for dbp, desc in candidatos:
        puntaje = _puntaje_planes_db(dbp)
        if puntaje > mejor_puntaje:
            mejor_db = dbp
            mejor_desc = desc
            mejor_puntaje = puntaje
    return mejor_db, mejor_desc, mejor_puntaje


# --- entry l. 2339-2374
def asegurar_planes_secretaria_institucion_desde_mejor_fuente(institucion_slug, forzar=False):
    """Asegura el archivo único de planes de una institución.

    Para universidades distintas de la UNO, NO se autocompletan planes desde
    otra base. Si todavía no se cargaron planes, `_planes_estudio.db` queda
    creado pero vacío hasta que el usuario los cargue desde el módulo Materias.
    """
    inst_slug = _slugify(institucion_slug or "")
    if not inst_slug:
        return {"actualizado": False, "motivo": "No se pudo identificar la institución.", "origen": "", "carreras": 0, "materias": 0}

    destino = planes_institucionales_db_path(inst_slug)
    asegurar_esquema_planes_db(destino)
    actual = _puntaje_planes_db(destino)

    if actual > 0 and _db_tiene_planes(destino):
        c = _contar_planes_db(destino)
        return {"actualizado": False, "motivo": "La fuente única de planes ya tiene datos cargados.", "origen": "Archivo único de planes", "carreras": c["carreras"], "materias": c["materias"]}

    # No copiar planes a instituciones nuevas que no sean UNO.
    if inst_slug != "universidad_nacional_del_oeste":
        c = _contar_planes_db(destino)
        return {"actualizado": False, "motivo": "Fuente única creada vacía. Cargá los planes de esta universidad desde Materias.", "origen": "", "carreras": c["carreras"], "materias": c["materias"]}

    origen, desc, puntaje = _buscar_mejor_fuente_planes_institucion(inst_slug, excluir_db=destino)
    if not origen or puntaje <= 0:
        c = _contar_planes_db(destino)
        return {"actualizado": False, "motivo": "No se encontró una fuente con carreras/materias para UNO.", "origen": "", "carreras": c["carreras"], "materias": c["materias"]}

    try:
        carreras = _copiar_tabla_completa(origen, destino, "carreras")
        materias = _copiar_tabla_completa(origen, destino, "materias")
        _set_auth_flag(f"planes_{inst_slug}_migracion_inicial_desde_mejor_fuente", "1")
        return {"actualizado": True, "motivo": "La fuente única de planes fue creada/actualizada.", "origen": desc, "carreras": carreras, "materias": materias}
    except Exception as e:
        return {"actualizado": False, "motivo": f"No se pudo actualizar la fuente única: {e}", "origen": desc, "carreras": 0, "materias": 0}


# --- entry l. 2704-2705
def current_user():
    return st.session_state.get("auth_user")


# --- entry l. 2708-2710
def current_role():
    u = current_user() or {}
    return u.get("rol", "")


# --- entry l. 4339-4341
def safe_date(value, fallback):
    from analisis.motor.ref.extracted_batch04.fechas import safe_date as _b04_core_safe_date
    return _b04_core_safe_date(value, fallback)


# --- entry l. 4344-4346
def nombre_completo(apellido, nombres):
    from analisis.motor.ref.extracted_batch04.identidad import nombre_completo as _b04_core_nombre_completo
    return _b04_core_nombre_completo(apellido, nombres)


# --- entry l. 4354-4356
def fechas_periodo(anio, semestre):
    from analisis.motor.ref.extracted_batch04.fechas import fechas_periodo as _b04_core_fechas_periodo
    return _b04_core_fechas_periodo(anio, semestre)


# --- entry l. 4424-4459
def registrar_movimiento(tipo, cuil, nombre, detalle, observaciones="", periodo_id=None, horas_variacion=0, fecha_movimiento=None):
    """Registra un movimiento permitiendo conservar su fecha efectiva real.

    v207: ``fecha_movimiento`` es opcional para mantener compatibilidad con todas
    las llamadas existentes. Si se informa (por ejemplo, una baja histórica), el
    movimiento queda fechado en el día en que ocurrió y no en el día de carga.
    """
    conn = get_conn()
    c = conn.cursor()
    add_column_if_not_exists(c, "movimientos", "horas_variacion", "REAL DEFAULT 0")
    try:
        horas_variacion = float(horas_variacion or 0)
    except Exception:
        horas_variacion = 0
    fecha_mov = ""
    if fecha_movimiento is not None:
        try:
            _fm = safe_date(fecha_movimiento, None)
            fecha_mov = _fm.isoformat() if _fm is not None else ""
        except Exception:
            fecha_mov = ""
    if not fecha_mov:
        fecha_mov = str(date.today())
    c.execute("""
        INSERT INTO movimientos
        (periodo_id, fecha, tipo_movimiento, cuil, nombre, detalle, observaciones, horas_variacion)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (periodo_id, fecha_mov, tipo, cuil, nombre, detalle, observaciones, horas_variacion))
    movimiento_id = int(c.lastrowid) if getattr(c, "lastrowid", None) not in [None, ""] else None
    conn.commit()
    conn.close()
    try:
        invalidar_cache_rendimiento_v191(f"movimiento registrado: {tipo}")
    except Exception:
        pass
    return movimiento_id


# --- entry l. 4462-4643
def get_docentes():
    """Base maestra con trayectoria derivada exclusivamente de designaciones.

    v204 - criterio único para todos los departamentos:
    - fecha_alta: la fecha_desde más antigua de todas las designaciones locales
      del docente, sin depender de la fecha guardada manualmente en docentes.
    - fecha_finalizacion: queda vacía mientras el docente integre el plantel del
      último período cronológico del departamento. Si ya no lo integra, muestra
      la finalización real más reciente hasta hoy (fecha_finalizacion_efectiva si
      existe; en caso contrario fecha_hasta).

    Las fechas se calculan en lectura para que cualquier corrección histórica de
    una designación se refleje automáticamente y el criterio sea idéntico en
    todos los departamentos.
    """
    try:
        periodo_actual = get_ultimo_periodo()
    except Exception:
        periodo_actual = None
    periodo_actual_id = None
    try:
        if periodo_actual and periodo_actual.get("id") is not None:
            periodo_actual_id = int(periodo_actual.get("id"))
    except Exception:
        periodo_actual_id = None

    conn = get_conn()
    try:
        # La base maestra aporta identidad/datos personales. Las fechas visibles
        # se reemplazan más abajo por la trayectoria real de designaciones.
        df = pd.read_sql("""
            SELECT
                doc.cuil,
                doc.legajo,
                doc.apellido,
                doc.nombres,
                CASE
                    WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                    WHEN doc.nombre IS NOT NULL THEN doc.nombre
                    ELSE ''
                END AS nombre_completo,
                doc.titulo,
                COALESCE(doc.titulo_posgrado, '') AS titulo_posgrado,
                doc.antiguedad_anios,
                COALESCE(doc.nivel_posgrado_salarial, '') AS nivel_posgrado_salarial,
                doc.email,
                doc.telefono,
                doc.ref_legajo_fisico,
                COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente,
                COALESCE(doc.observaciones, '') AS observaciones,
                doc.estado,
                doc.fecha_alta AS fecha_alta_registrada,
                doc.fecha_finalizacion AS fecha_finalizacion_registrada
            FROM docentes doc
            ORDER BY doc.apellido, doc.nombres
        """, conn)

        # Una única lectura histórica de designaciones del departamento actual.
        # get_conn() mantiene el scope institucion/departamento correspondiente.
        try:
            df_des = pd.read_sql("""
                SELECT
                    d.cuil,
                    d.periodo_id,
                    COALESCE(d.estado, 'Activa') AS estado,
                    d.fecha_desde,
                    d.fecha_hasta,
                    d.fecha_finalizacion_efectiva
                FROM designaciones d
            """, conn)
        except Exception:
            df_des = pd.DataFrame(columns=[
                "cuil", "periodo_id", "estado", "fecha_desde", "fecha_hasta",
                "fecha_finalizacion_efectiva"
            ])

        # Los prestados activos también integran el plantel operativo del
        # departamento receptor aunque su designación formal viva en el origen.
        try:
            if periodo_actual_id is not None:
                df_prest = pd.read_sql("""
                    SELECT pr.cuil, pr.periodo_id, COALESCE(pr.estado, 'Activo') AS estado
                    FROM prestamos_docentes pr
                    WHERE pr.periodo_id = ?
                """, conn, params=[periodo_actual_id])
            else:
                df_prest = pd.DataFrame(columns=["cuil", "periodo_id", "estado"])
        except Exception:
            df_prest = pd.DataFrame(columns=["cuil", "periodo_id", "estado"])
    finally:
        conn.close()

    if df is None or df.empty:
        return pd.DataFrame() if df is None else df

    def _cuil_key_v204(valor):
        return re.sub(r"\D", "", str(valor or "")).strip()

    hoy = date.today()
    activos_actuales = set()

    # Plantel propio activo = al menos una designación Activa en el último
    # período cronológico del departamento. No se usa get_periodo_abierto()
    # porque un período histórico puede abrirse temporalmente por corrección.
    if isinstance(df_des, pd.DataFrame) and not df_des.empty and periodo_actual_id is not None:
        per_num = pd.to_numeric(df_des.get("periodo_id"), errors="coerce")
        est = df_des.get("estado", pd.Series(index=df_des.index, dtype=str)).fillna("Activa").astype(str).str.strip().str.casefold()
        sub_act = df_des[per_num.eq(periodo_actual_id) & est.eq("activa")].copy()
        activos_actuales.update(
            _cuil_key_v204(x) for x in sub_act.get("cuil", pd.Series(dtype=str)).tolist() if _cuil_key_v204(x)
        )

    # Prestados vigentes del período actual también cuentan como plantel activo.
    if isinstance(df_prest, pd.DataFrame) and not df_prest.empty:
        est_pr = df_prest.get("estado", pd.Series(index=df_prest.index, dtype=str)).fillna("Activo").astype(str).str.strip().str.casefold()
        sub_pr = df_prest[est_pr.eq("activo")].copy()
        activos_actuales.update(
            _cuil_key_v204(x) for x in sub_pr.get("cuil", pd.Series(dtype=str)).tolist() if _cuil_key_v204(x)
        )

    fechas_alta = {}
    fechas_fin = {}
    cuiles_con_designacion = set()

    if isinstance(df_des, pd.DataFrame) and not df_des.empty:
        for _, r in df_des.iterrows():
            k = _cuil_key_v204(r.get("cuil"))
            if not k:
                continue
            cuiles_con_designacion.add(k)

            desde = safe_date(r.get("fecha_desde"), None)
            if desde is not None:
                anterior = fechas_alta.get(k)
                if anterior is None or desde < anterior:
                    fechas_alta[k] = desde

            # La baja efectiva prevalece sobre el vencimiento previsto de esa
            # misma designación. Si no hubo baja anticipada, se toma fecha_hasta.
            fin = safe_date(r.get("fecha_finalizacion_efectiva"), None)
            if fin is None:
                fin = safe_date(r.get("fecha_hasta"), None)

            # "Última finalización" significa una fecha ya ocurrida. Así se
            # evita mostrar como finalizado hoy a un concursado cuyo vencimiento
            # real está todavía en el futuro.
            if fin is not None and fin <= hoy:
                anterior_fin = fechas_fin.get(k)
                if anterior_fin is None or fin > anterior_fin:
                    fechas_fin[k] = fin

    altas_visibles = []
    finales_visibles = []
    estados_operativos = []

    for _, r in df.iterrows():
        k = _cuil_key_v204(r.get("cuil"))
        alta = fechas_alta.get(k)
        esta_activo = bool(k and k in activos_actuales)
        fin = None if esta_activo else fechas_fin.get(k)

        altas_visibles.append(alta.isoformat() if alta is not None else "")
        finales_visibles.append(fin.isoformat() if fin is not None else "")

        if esta_activo:
            estados_operativos.append("Activo en período actual")
        elif periodo_actual_id is None:
            estados_operativos.append("Sin período actual")
        elif k in cuiles_con_designacion:
            estados_operativos.append("Finalizado / sin designación activa")
        else:
            estados_operativos.append("Sin designación registrada")

    df = df.copy()
    df["fecha_alta"] = altas_visibles
    df["fecha_finalizacion"] = finales_visibles
    df["estado_periodo_abierto"] = estados_operativos

    # Las fechas manuales antiguas quedan fuera de la interfaz y de las lecturas
    # que consumen get_docentes(); se conservan físicamente solo por compatibilidad.
    df = df.drop(columns=["fecha_alta_registrada", "fecha_finalizacion_registrada"], errors="ignore")
    return df


# --- entry l. 4645-4711
def get_plantel_periodo(periodo_id):
    conn = get_conn()
    df = pd.read_sql("""
        SELECT
            doc.cuil,
            doc.legajo,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE ''
            END AS nombre_completo,
            doc.titulo,
            COALESCE(doc.titulo_posgrado, '') AS titulo_posgrado,
            doc.email,
            doc.telefono,
            COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente,
            CASE
                WHEN SUM(
                    CASE
                        WHEN d.estado = 'Activa'
                         AND COALESCE((SELECT p2.estado FROM periodos p2 WHERE p2.id = d.periodo_id), '') <> 'Cerrado'
                        THEN 1 ELSE 0
                    END
                ) > 0
                    THEN 'Activo en el período'
                ELSE 'Finalizado / sin designación activa'
            END AS estado_operativo_periodo,
            MIN(d.fecha_desde) AS fecha_alta_periodo,
            MAX(d.fecha_hasta) AS fecha_finalizacion_periodo,
            COUNT(d.id) AS designaciones_del_periodo,
            SUM(
                CASE
                    WHEN d.estado = 'Activa'
                     AND COALESCE((SELECT p3.estado FROM periodos p3 WHERE p3.id = d.periodo_id), '') <> 'Cerrado'
                    THEN 1 ELSE 0
                END
            ) AS designaciones_activas,
            SUM(
                CASE
                    WHEN d.estado = 'Activa'
                     AND COALESCE((SELECT p4.estado FROM periodos p4 WHERE p4.id = d.periodo_id), '') <> 'Cerrado'
                    THEN COALESCE(d.horas, 0) ELSE 0
                END
            ) AS horas_activas,
            SUM(COALESCE(d.horas, 0)) AS horas_registradas_periodo,
            GROUP_CONCAT(
                d.cargo || ' - ' || d.dedicacion || ' - ' || d.horas || ' hs - ' ||
                d.tipo_designacion || ' - Ad Honorem: ' || COALESCE(d.ad_honorem, 'No') ||
                ' - Estado: ' ||
                CASE
                    WHEN COALESCE((SELECT p5.estado FROM periodos p5 WHERE p5.id = d.periodo_id), '') = 'Cerrado'
                     AND d.estado = 'Activa'
                    THEN 'Finalizada'
                    ELSE COALESCE(d.estado, '')
                END,
                ' | '
            ) AS detalle_designaciones
        FROM designaciones d
        LEFT JOIN docentes doc ON d.cuil = doc.cuil
        WHERE d.periodo_id = ?
        GROUP BY
            doc.cuil, doc.legajo, doc.apellido, doc.nombres, doc.nombre,
            doc.titulo, doc.titulo_posgrado, doc.email, doc.telefono, doc.tipo_docente
        ORDER BY doc.apellido, doc.nombres
    """, conn, params=[periodo_id])
    conn.close()
    return df


# --- entry l. 4713-4721
def get_periodos():
    conn = get_conn()
    df = pd.read_sql("""
        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones
        FROM periodos
        ORDER BY anio DESC, semestre DESC, id DESC
    """, conn)
    conn.close()
    return df


# --- entry l. 4724-4736
def get_periodo_abierto():
    conn = get_conn()
    df = pd.read_sql("""
        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones
        FROM periodos
        WHERE estado = 'Abierto'
        ORDER BY id DESC
        LIMIT 1
    """, conn)
    conn.close()
    if df.empty:
        return None
    return df.iloc[0].to_dict()


# --- entry l. 4739-4741
def get_ultimo_periodo():
    from analisis.motor.ref.extracted_batch03.readonly_queries import get_ultimo_periodo as _b03_core_get_ultimo_periodo
    return _b03_core_get_ultimo_periodo(get_conn=get_conn, pd=pd)


# --- entry l. 4742-4789
def get_designaciones(periodo_id=None):
    conn = get_conn()
    filtro = ""
    params = []
    if periodo_id is not None:
        filtro = "WHERE d.periodo_id = ?"
        params = [periodo_id]
    df = pd.read_sql(f"""
        SELECT
            d.id,
            d.periodo_id,
            p.nombre AS periodo,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE ''
            END AS nombre_completo,
            d.cuil,
            d.cargo,
            d.dedicacion,
            d.horas,
            d.tipo_designacion,
            d.ad_honorem,
            d.fecha_desde,
            d.fecha_hasta,
            CASE
                -- v229: una designación solo puede ser Activa si pertenece al
                -- último período cronológico del departamento. Abrir un período
                -- histórico por excepción NO reactiva sus designaciones.
                WHEN d.estado = 'Activa'
                     AND d.periodo_id <> (
                         SELECT pult.id
                         FROM periodos pult
                         ORDER BY pult.anio DESC, pult.semestre DESC, pult.id DESC
                         LIMIT 1
                     )
                    THEN 'Finalizada'
                ELSE d.estado
            END AS estado,
            d.observaciones
        FROM designaciones d
        LEFT JOIN docentes doc ON d.cuil = doc.cuil
        LEFT JOIN periodos p ON d.periodo_id = p.id
        {filtro}
        ORDER BY p.anio DESC, p.semestre DESC, doc.apellido, doc.nombres
    """, conn, params=params)
    conn.close()
    return df


# --- entry l. 4824-4863
def get_movimientos(periodo_id=None):
    conn = get_conn()
    filtro = ""
    params = []
    if periodo_id is not None:
        filtro = "WHERE m.periodo_id = ?"
        params = [periodo_id]
    df = pd.read_sql(f"""
        SELECT
            m.id,
            m.periodo_id,
            p.nombre AS periodo,
            m.fecha,
            m.tipo_movimiento,
            m.cuil,
            m.nombre,
            m.detalle,
            m.observaciones,
            COALESCE(m.horas_variacion, 0) AS horas_variacion
        FROM movimientos m
        LEFT JOIN periodos p ON m.periodo_id = p.id
        {filtro}
        ORDER BY
            COALESCE(p.anio, 0) DESC,
            COALESCE(p.semestre, 0) DESC,
            m.fecha DESC,
            CASE
                WHEN m.tipo_movimiento = 'Renovación automática de designación' THEN 1
                WHEN m.tipo_movimiento = 'Alta de designación' THEN 2
                WHEN m.tipo_movimiento = 'Aumento de dedicación' THEN 3
                WHEN m.tipo_movimiento = 'Disminución de dedicación' THEN 4
                WHEN m.tipo_movimiento = 'Cambio de cargo' THEN 5
                WHEN m.tipo_movimiento = 'Baja de designación' THEN 8
                WHEN m.tipo_movimiento = 'Finalización automática por cierre de período' THEN 9
                ELSE 6
            END ASC,
            m.id DESC
    """, conn, params=params)
    conn.close()
    return df


# --- entry l. 4876
_get_movimientos_legacy_v284 = get_movimientos


# --- entry l. 4879-4886
def _modo_lectura_movimientos_v284():
    try:
        from analisis.motor.ref.integration.movements_pilot import normalize_movements_mode
        return normalize_movements_mode(
            _valor_configuracion("DEPTIT_MOVEMENTS_READ_MODE", "off")
        )
    except Exception:
        return "off"


# --- entry l. 4890-4897
def _get_movimientos_nuevo_cache_v284(periodo_id, db_url, inst, dep, version):
    from analisis.motor.ref.integration.movements_pilot import build_movement_service
    from analisis.motor.ref.integration.periods_pilot import build_runtime_database

    db = build_runtime_database(_pg_raw_conn)
    service = build_movement_service(db, int(inst), int(dep))
    pid = int(periodo_id) if periodo_id is not None else None
    return service.list(pid)


# --- entry l. 4900-4936
def _guardar_diagnostico_movimientos_v284(
    decision,
    *,
    inst=None,
    dep=None,
    periodo_id=None,
    error=None,
):
    try:
        diag = decision.diagnostics() if decision is not None else {}
    except Exception:
        diag = {}
    try:
        diag.update({
            "institucion_id": int(inst) if inst is not None else None,
            "departamento_id": int(dep) if dep is not None else None,
            "periodo_id": int(periodo_id) if periodo_id is not None else None,
            "error": str(error)[:500] if error is not None else "",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        st.session_state["_v284_movements_read_diag"] = diag
        try:
            mostrar_stdout = str(_valor_configuracion("DEPTIT_MOVEMENTS_DIAG_STDOUT", "0")).strip().casefold() in {"1", "true", "yes", "si", "sí"}
            if mostrar_stdout:
                print(
                    "[DEPTIT v284 movimientos] "
                    f"mode={diag.get('mode')} source={diag.get('source')} "
                    f"equivalent={diag.get('equivalent')} "
                    f"inst={diag.get('institucion_id')} dep={diag.get('departamento_id')} "
                    f"periodo={diag.get('periodo_id')} "
                    f"legacy_rows={diag.get('legacy_rows')} new_rows={diag.get('new_rows')} "
                    f"reason={diag.get('reason')} error={diag.get('error')}"
                )
        except Exception:
            pass
    except Exception:
        pass


# --- entry l. 4946-5001
def get_movimientos(periodo_id=None):
    legacy = _get_movimientos_legacy_v284(periodo_id)
    mode = _modo_lectura_movimientos_v284()

    if mode == "off":
        try:
            from analisis.motor.ref.integration.movements_pilot import choose_movements_frame
            decision = choose_movements_frame(mode="off", legacy=legacy)
            _guardar_diagnostico_movimientos_v284(decision, periodo_id=periodo_id)
        except Exception:
            pass
        return pd.DataFrame(legacy).copy()

    if not USE_POSTGRESQL or not DATABASE_URL:
        try:
            from analisis.motor.ref.integration.movements_pilot import choose_movements_frame
            decision = choose_movements_frame(
                mode=mode,
                legacy=legacy,
                new_error=RuntimeError("PostgreSQL no disponible para el piloto v284"),
            )
            _guardar_diagnostico_movimientos_v284(decision, periodo_id=periodo_id)
        except Exception:
            pass
        return pd.DataFrame(legacy).copy()

    inst = dep = None
    try:
        db_url, inst, dep, version = _scope_rendimiento_v191()
        if dep is None:
            raise RuntimeError("El piloto v284 requiere scope departamental explícito")
        new_df = _get_movimientos_nuevo_cache_v284(
            int(periodo_id) if periodo_id is not None else None,
            str(db_url),
            int(inst),
            int(dep),
            version,
        )
        from analisis.motor.ref.integration.movements_pilot import choose_movements_frame
        decision = choose_movements_frame(mode=mode, legacy=legacy, new=new_df)
        _guardar_diagnostico_movimientos_v284(
            decision, inst=inst, dep=dep, periodo_id=periodo_id
        )
        return pd.DataFrame(decision.frame).copy()
    except Exception as exc:
        try:
            from analisis.motor.ref.integration.movements_pilot import choose_movements_frame
            decision = choose_movements_frame(
                mode=mode, legacy=legacy, new_error=exc
            )
            _guardar_diagnostico_movimientos_v284(
                decision, inst=inst, dep=dep, periodo_id=periodo_id, error=exc
            )
        except Exception:
            pass
        return pd.DataFrame(legacy).copy()


# --- entry l. 5004-5117
def get_resumen_docente(cuil):
    conn = get_conn()

    df_docente = pd.read_sql("""
        SELECT
            cuil,
            legajo,
            apellido,
            nombres,
            CASE
                WHEN apellido IS NOT NULL AND nombres IS NOT NULL THEN apellido || ', ' || nombres
                WHEN nombre IS NOT NULL THEN nombre
                ELSE ''
            END AS nombre_completo,
            titulo,
            COALESCE(titulo_posgrado, '') AS titulo_posgrado,
            email,
            telefono,
            COALESCE(tipo_docente, 'Propio') AS tipo_docente,
            COALESCE(observaciones, '') AS observaciones,
            COALESCE(
                (
                    SELECT MIN(NULLIF(d0.fecha_desde, ''))
                    FROM designaciones d0
                    WHERE d0.cuil = docentes.cuil
                ),
                NULLIF(fecha_alta, '')
            ) AS fecha_inicio_historica,
            COALESCE(
                (
                    SELECT MAX(NULLIF(d1.fecha_desde, ''))
                    FROM designaciones d1
                    WHERE d1.cuil = docentes.cuil
                ),
                NULLIF(fecha_alta, '')
            ) AS ultima_fecha_alta,
            CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM designaciones da
                    JOIN periodos pa ON pa.id = da.periodo_id
                    WHERE da.cuil = docentes.cuil
                      AND da.estado = 'Activa'
                      AND pa.estado = 'Abierto'
                ) THEN ''
                ELSE COALESCE(
                    NULLIF(fecha_finalizacion, ''),
                    (
                        SELECT MAX(d2.fecha_hasta)
                        FROM designaciones d2
                        WHERE d2.cuil = docentes.cuil
                          AND d2.estado = 'Finalizada'
                    )
                )
            END AS fecha_finalizacion
        FROM docentes
        WHERE cuil = ?
        LIMIT 1
    """, conn, params=[cuil])

    df_designaciones = pd.read_sql("""
        SELECT
            p.nombre AS periodo,
            p.fecha_inicio AS periodo_inicio,
            p.fecha_fin AS periodo_fin,
            d.cargo,
            d.dedicacion,
            d.horas,
            d.tipo_designacion,
            d.ad_honorem,
            d.fecha_desde,
            d.fecha_hasta,
            CASE
                WHEN p.estado = 'Cerrado' AND d.estado = 'Activa'
                    THEN 'Finalizada'
                ELSE d.estado
            END AS estado,
            d.observaciones
        FROM designaciones d
        LEFT JOIN periodos p ON d.periodo_id = p.id
        WHERE d.cuil = ?
        ORDER BY p.anio DESC, p.semestre DESC, d.fecha_desde DESC, d.id DESC
    """, conn, params=[cuil])

    df_movimientos = pd.read_sql("""
        SELECT
            p.nombre AS periodo,
            m.fecha,
            m.tipo_movimiento,
            m.detalle,
            m.observaciones,
            COALESCE(m.horas_variacion, 0) AS horas_variacion
        FROM movimientos m
        LEFT JOIN periodos p ON m.periodo_id = p.id
        WHERE m.cuil = ?
        ORDER BY
            COALESCE(p.anio, 0) DESC,
            COALESCE(p.semestre, 0) DESC,
            m.fecha DESC,
            CASE
                WHEN m.tipo_movimiento = 'Renovación automática de designación' THEN 1
                WHEN m.tipo_movimiento = 'Alta de designación' THEN 2
                WHEN m.tipo_movimiento = 'Aumento de dedicación' THEN 3
                WHEN m.tipo_movimiento = 'Disminución de dedicación' THEN 4
                WHEN m.tipo_movimiento = 'Cambio de cargo' THEN 5
                WHEN m.tipo_movimiento = 'Baja de designación' THEN 8
                WHEN m.tipo_movimiento = 'Finalización automática por cierre de período' THEN 9
                ELSE 6
            END ASC,
            m.id DESC
    """, conn, params=[cuil])

    conn.close()
    return df_docente, df_designaciones, df_movimientos


# --- entry l. 5216-5218
def simplificar_detalle_movimiento(tipo_movimiento, detalle):
    from analisis.motor.ref.domain.movimientos import simplificar_detalle_movimiento as _b05_core_simplificar_detalle_movimiento
    return _b05_core_simplificar_detalle_movimiento(tipo_movimiento, detalle)


# --- entry l. 5233-5235
def _extraer_antes_ahora(detalle):
    from analisis.motor.ref.extracted_batch04.movimientos import _extraer_antes_ahora as _b04_core__extraer_antes_ahora
    return _b04_core__extraer_antes_ahora(detalle)


# --- entry l. 5243-5245
def calcular_variacion_horas_movimiento(tipo_movimiento, detalle, horas_variacion_guardada=0):
    from analisis.motor.ref.domain.movimientos import calcular_variacion_horas_movimiento as _b05_core_calcular_variacion_horas_movimiento
    return _b05_core_calcular_variacion_horas_movimiento(tipo_movimiento, detalle, horas_variacion_guardada)


# --- entry l. 5248-5250
def normalizar_tipo_movimiento_dedicacion(tipo_movimiento, variacion_horas=0):
    from analisis.motor.ref.extracted_batch04.movimientos import normalizar_tipo_movimiento_dedicacion as _b04_core_normalizar_tipo_movimiento_dedicacion
    return _b04_core_normalizar_tipo_movimiento_dedicacion(tipo_movimiento, variacion_horas)


# --- entry l. 5253-5255
def clasificar_movimiento_docente(tipo_movimiento, variacion_horas=None):
    from analisis.motor.ref.domain.movimientos import clasificar_movimiento_docente as _b05_core_clasificar_movimiento_docente
    return _b05_core_clasificar_movimiento_docente(tipo_movimiento, variacion_horas)


# --- entry l. 5258-5313
def preparar_analisis_movimiento_docente(df_movimientos):
    """
    Arma la base analítica de movimientos: una fila por movimiento, con docente, tipo,
    categoría y variación de horas con signo.
    """
    columnas = [
        "periodo", "fecha", "cuil", "docente", "tipo_movimiento", "categoria_movimiento",
        "detalle", "observaciones", "variacion_horas"
    ]
    if df_movimientos is None or df_movimientos.empty:
        return pd.DataFrame(columns=columnas)

    df = df_movimientos.copy()
    df = _deduplicar_bajas_misma_designacion(df, evento_col="tipo_movimiento")
    if "horas_variacion" not in df.columns:
        df["horas_variacion"] = 0

    df["docente"] = df["nombre"].fillna("").astype(str).str.strip()
    df.loc[df["docente"] == "", "docente"] = df.loc[df["docente"] == "", "cuil"].fillna("").astype(str)
    df["variacion_horas"] = df.apply(
        lambda row: calcular_variacion_horas_movimiento(
            row.get("tipo_movimiento", ""),
            row.get("detalle", ""),
            row.get("horas_variacion", 0)
        ),
        axis=1
    )

    # La categoría de Aumento/Disminución se determina por el signo real de horas,
    # no solamente por el texto con el que se guardó el movimiento. Esto corrige en
    # Análisis casos históricos mal rotulados sin alterar la trazabilidad original.
    tipo_original = df["tipo_movimiento"].fillna("").astype(str).str.strip()
    es_mov_dedicacion = tipo_original.isin(["Aumento de dedicación", "Disminución de dedicación"])
    sin_variacion = es_mov_dedicacion & (pd.to_numeric(df["variacion_horas"], errors="coerce").fillna(0).abs() < 1e-9)
    # Un supuesto aumento/disminución sin variación real no representa un movimiento
    # de dedicación y se omite del análisis. Desde v123 tampoco se permite guardarlo.
    df = df.loc[~sin_variacion].copy()
    if df.empty:
        return pd.DataFrame(columns=columnas)

    df["tipo_movimiento"] = df.apply(
        lambda row: normalizar_tipo_movimiento_dedicacion(
            row.get("tipo_movimiento", ""), row.get("variacion_horas", 0)
        ), axis=1
    )
    df["categoria_movimiento"] = df.apply(
        lambda row: clasificar_movimiento_docente(
            row.get("tipo_movimiento", ""), row.get("variacion_horas", 0)
        ), axis=1
    )
    df["detalle"] = df.apply(
        lambda row: simplificar_detalle_movimiento(row.get("tipo_movimiento", ""), row.get("detalle", "")),
        axis=1
    )

    return df[[c for c in columnas if c in df.columns]].copy()


# --- entry l. 5316-5318
def resumen_movimiento_docente(df_movimientos_analisis):
    from analisis.motor.ref.domain.movimientos import resumen_movimiento_docente as _b05_core_resumen_movimiento_docente
    return _b05_core_resumen_movimiento_docente(df_movimientos_analisis)


# --- entry l. 5326-5328
def balance_horas_movimiento_docente(df_movimientos_analisis):
    from analisis.motor.ref.extracted_batch01.movimientos import balance_horas_movimiento_docente as _b01_core_balance_horas_movimiento_docente
    return _b01_core_balance_horas_movimiento_docente(df_movimientos_analisis)


# --- entry l. 6336-6339
def _condicion_periodo_equivalente_sql(alias_periodo="p", alias_ref="pr"):
    'Condición SQL para comparar períodos equivalentes entre departamentos.'
    from analisis.motor.ref.extracted_batch01.periodos import _condicion_periodo_equivalente_sql as _b01_core__condicion_periodo_equivalente_sql
    return _b01_core__condicion_periodo_equivalente_sql(alias_periodo, alias_ref)


# --- entry l. 6342-6403
def get_designaciones_docente_periodo_todos_departamentos(cuil, periodo_id):
    """Designaciones del docente para el mismo período académico, en todos los departamentos.

    Esto es clave para docentes prestados: desde el departamento receptor no tienen
    designación local, pero sí revistan en su departamento de origen.
    """
    columnas = [
        "id", "periodo_id", "departamento_id", "cargo", "dedicacion", "horas",
        "tipo_designacion", "numero_resolucion", "fecha_desde", "fecha_hasta", "estado", "departamento"
    ]
    if not USE_POSTGRESQL:
        conn = get_conn()
        try:
            df = pd.read_sql("""
                SELECT id, periodo_id, NULL AS departamento_id,
                       cargo, dedicacion, horas, tipo_designacion, COALESCE(numero_resolucion,'') AS numero_resolucion,
                       fecha_desde, fecha_hasta, estado, '' AS departamento
                FROM designaciones
                WHERE cuil = ? AND periodo_id = ?
                ORDER BY tipo_designacion, cargo, dedicacion
            """, conn, params=[cuil, periodo_id])
        finally:
            conn.close()
        for col in columnas:
            if col not in df.columns:
                df[col] = ""
        return df[columnas]

    try:
        df = _pg_read_dataframe(f"""
            WITH pr AS (
                SELECT id, institucion_id, nombre, anio, semestre
                FROM periodos
                WHERE id = %s
                LIMIT 1
            )
            SELECT
                d.id,
                d.periodo_id,
                d.departamento_id,
                d.cargo,
                d.dedicacion,
                d.horas,
                d.tipo_designacion,
                COALESCE(d.numero_resolucion, '') AS numero_resolucion,
                d.fecha_desde,
                d.fecha_hasta,
                d.estado,
                dep.nombre AS departamento
            FROM designaciones d
            JOIN periodos p ON p.id = d.periodo_id
            JOIN pr ON {_condicion_periodo_equivalente_sql('p', 'pr')}
            LEFT JOIN departamentos dep ON dep.id = d.departamento_id
            WHERE regexp_replace(COALESCE(d.cuil, ''), '[^0-9]', '', 'g') = %s
            ORDER BY dep.nombre, d.tipo_designacion, d.cargo, d.dedicacion, d.id
        """, [int(periodo_id), _clave_cuil(cuil)])
    except Exception:
        df = pd.DataFrame(columns=columnas)
    for col in columnas:
        if col not in df.columns:
            df[col] = ""
    return df[columnas]


# --- entry l. 6616-6633
def _departamento_actual_operativo_nombre():
    """Departamento del usuario/ámbito actual, usado solo como respaldo."""
    dep_actual = ""
    try:
        dep_actual = (current_user() or {}).get("departamento_nombre") or ""
    except Exception:
        dep_actual = ""
    if not dep_actual and USE_POSTGRESQL:
        try:
            dep_id = _pg_current_dep_id()
            if dep_id:
                df_dep = _pg_read_dataframe("SELECT nombre FROM departamentos WHERE id = %s LIMIT 1", [int(dep_id)])
                if not df_dep.empty:
                    dep_actual = str(df_dep.iloc[0].get("nombre") or "")
        except Exception:
            dep_actual = ""
    dep_actual = " ".join(str(dep_actual or "").strip().split())
    return dep_actual or "Departamento correspondiente"


# --- entry l. 7585-7609
def _obtener_document_python_docx():
    """Devuelve Document de python-docx.

    En la versión local puede pasar que el entorno nuevo de PostgreSQL no tenga
    instalado python-docx. Para que no falle la generación de disposiciones,
    se intenta instalar automáticamente en el mismo entorno virtual donde corre
    Streamlit. Si no se puede instalar, recién ahí se muestra el mensaje manual.
    """
    # NEXT 6A-B1: sin instalacion dinamica de paquetes (python-docx esta en requirements.txt).
    try:
        from docx import Document
        return Document
    except Exception as e:
        raise RuntimeError(
            "Falta instalar python-docx. Cerrá la app y ejecutá en el CMD activo: "
            "python -m pip install python-docx"
        ) from e


# --- entry l. 7727-7729
def nombre_archivo_seguro(texto):
    from analisis.motor.ref.common.text import nombre_archivo_seguro as _b05_core_nombre_archivo_seguro
    return _b05_core_nombre_archivo_seguro(texto)


# --- entry l. 7735-7737
def normalizar_clave(valor):
    from analisis.motor.ref.extracted_batch04.texto import normalizar_clave as _b04_core_normalizar_clave
    return _b04_core_normalizar_clave(valor)


# --- entry l. 7740-7742
def normalizar_codigo_materia(valor):
    from analisis.motor.ref.extracted_batch04.materias import normalizar_codigo_materia as _b04_core_normalizar_codigo_materia
    return _b04_core_normalizar_codigo_materia(valor)


# --- entry l. 7784-7786
def _clave_cuil(valor):
    from analisis.motor.ref.extracted_batch04.identidad import _clave_cuil as _b04_core__clave_cuil
    return _b04_core__clave_cuil(valor)


# --- entry l. 8584-8586
def _tipo_movimiento_designacion_normalizado(valor):
    from analisis.motor.ref.extracted_batch04.movimientos import _tipo_movimiento_designacion_normalizado as _b04_core__tipo_movimiento_designacion_normalizado
    return _b04_core__tipo_movimiento_designacion_normalizado(valor)


# --- entry l. 9377-9412
def asegurar_esquema_correcciones_historial_horas_v132():
    """Guarda correcciones administrativas de la foto inicial sin inventar movimientos."""
    if st.session_state.get("_esquema_corr_hist_horas_v132_ok"):
        return
    conn = get_conn(); c = conn.cursor()
    try:
        if USE_POSTGRESQL:
            c.execute("""
                CREATE TABLE IF NOT EXISTS correcciones_historial_horas (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT NOT NULL,
                    periodo_id BIGINT NOT NULL,
                    cuil TEXT NOT NULL,
                    horas_inicio_reales REAL NOT NULL,
                    motivo TEXT,
                    fecha_actualizacion TEXT,
                    UNIQUE(institucion_id, departamento_id, periodo_id, cuil)
                )
            """)
        else:
            c.execute("""
                CREATE TABLE IF NOT EXISTS correcciones_historial_horas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    periodo_id INTEGER NOT NULL,
                    cuil TEXT NOT NULL,
                    horas_inicio_reales REAL NOT NULL,
                    motivo TEXT,
                    fecha_actualizacion TEXT,
                    UNIQUE(periodo_id, cuil)
                )
            """)
        conn.commit()
        st.session_state["_esquema_corr_hist_horas_v132_ok"] = True
    finally:
        conn.close()


# --- entry l. 9415-9434
def get_horas_inicio_real_v132(periodo_id, cuil):
    """Devuelve la base horaria corregida del período, si fue confirmada administrativamente."""
    asegurar_esquema_correcciones_historial_horas_v132()
    conn = get_conn()
    try:
        df = pd.read_sql("""
            SELECT horas_inicio_reales
            FROM correcciones_historial_horas
            WHERE periodo_id = ? AND TRIM(COALESCE(cuil, '')) = TRIM(?)
            ORDER BY id DESC
            LIMIT 1
        """, conn, params=[int(periodo_id), str(cuil)])
    finally:
        conn.close()
    if df.empty:
        return None
    try:
        return float(df.iloc[0].get("horas_inicio_reales"))
    except Exception:
        return None


# --- entry l. 9750-9775
def _periodos_contexto_v269(periodo_id):
    """Devuelve período seleccionado, primero cronológico e inmediatamente anterior."""
    try:
        pid = int(periodo_id)
    except Exception:
        return None, None, None
    conn = get_conn()
    try:
        df = pd.read_sql("""
            SELECT id,nombre,anio,semestre,fecha_inicio,fecha_fin,estado
            FROM periodos
            ORDER BY COALESCE(anio,0), COALESCE(semestre,0), COALESCE(fecha_inicio,''), id
        """, conn)
    finally:
        conn.close()
    if df.empty:
        return None, None, None
    ids = pd.to_numeric(df["id"], errors="coerce")
    pos = df.index[ids.eq(pid)].tolist()
    if not pos:
        return None, df.iloc[0].to_dict(), None
    idx = df.index.get_loc(pos[0])
    actual = df.iloc[idx].to_dict()
    primero = df.iloc[0].to_dict()
    anterior = df.iloc[idx - 1].to_dict() if idx > 0 else None
    return actual, primero, anterior


# --- entry l. 9783-9785
def _vigente_al_cierre_v269(row, fecha_cierre):
    from analisis.motor.ref.domain.designaciones import _vigente_al_cierre_v269 as _b05_core__vigente_al_cierre_v269
    return _b05_core__vigente_al_cierre_v269(row, fecha_cierre)


# --- entry l. 9793-9795
def _detalle_coincide_designacion_v269(detalle, row):
    from analisis.motor.ref.domain.designaciones import _detalle_coincide_designacion_v269 as _b05_core__detalle_coincide_designacion_v269
    return _b05_core__detalle_coincide_designacion_v269(detalle, row)


# --- entry l. 9809-9812
def _depurar_bajas_movimientos_v269(df):
    """Eliminación = corrección de carga, no baja real; además quita duplicados/no-op."""
    from analisis.motor.ref.domain.catalog_unlocked.movimientos import _depurar_bajas_movimientos_v269 as _b08_core__depurar_bajas_movimientos_v269
    return _b08_core__depurar_bajas_movimientos_v269(df)


# --- entry l. 9815-9946
def _canonizar_movimientos_designaciones_v269(df_mov, periodo_id, preservar_no_designacion=True):
    """Reconstruye la lectura administrativa sin reescribir la auditoría de la base.

    - Primer período cronológico: una Alta por cada designación física real del período.
    - Períodos posteriores: un Alta legacy se muestra como Renovación/Continuidad si
      coincide con una designación vigente al cierre del período inmediatamente anterior.
    - Eliminaciones por corrección y bajas sin cambio real no integran indicadores.
    """
    if df_mov is None:
        return pd.DataFrame()
    base = df_mov.copy()
    actual, primero, anterior = _periodos_contexto_v269(periodo_id)
    if actual is None:
        return _depurar_bajas_movimientos_v269(base)
    pid = int(actual.get("id"))
    es_primero = primero is not None and int(primero.get("id")) == pid

    tipos_designacion = set(_TIPOS_INICIO_DESIGNACION_V269) | set(_TIPOS_BAJA_REAL_DESIGNACION_V269) | {
        "Eliminación de designación", "Eliminacion de designacion",
        "Aumento de dedicación", "Disminución de dedicación", "Cambio de cargo",
        "Cambio de tipo de designación", "Cambio de número de resolución",
        "Cambio de condición Ad Honorem", "Pase a Ad Honorem", "Pase a Rentado",
        "Cambio de función docente / no docente", "Cambio de funciones no docentes",
        "Modificación general", "Finalización automática por cierre de período",
    }

    if preservar_no_designacion:
        no_des = base[~base.get("tipo_movimiento", pd.Series(index=base.index,dtype=str)).fillna("").astype(str).isin(tipos_designacion)].copy()
        des_mov = base[base.get("tipo_movimiento", pd.Series(index=base.index,dtype=str)).fillna("").astype(str).isin(tipos_designacion)].copy()
    else:
        no_des = pd.DataFrame(columns=base.columns)
        des_mov = base.copy()

    des_mov = _depurar_bajas_movimientos_v269(des_mov)

    try:
        actuales = get_designaciones(pid)
        if actuales is None:
            actuales = pd.DataFrame()
    except Exception:
        actuales = pd.DataFrame()

    if es_primero:
        # El primer período es la línea de base institucional. Los viejos movimientos
        # de alta estaban incompletos porque la carga inicial precede al historial actual.
        if not des_mov.empty:
            des_mov = des_mov[~des_mov["tipo_movimiento"].fillna("").astype(str).isin(_TIPOS_INICIO_DESIGNACION_V269)].copy()
        sinteticas = []
        inicio_per = safe_date(actual.get("fecha_inicio"), None)
        fin_per = safe_date(actual.get("fecha_fin"), None)
        nombre_per = str(actual.get("nombre") or "")
        for _, d in actuales.iterrows():
            did = int(pd.to_numeric(d.get("id"), errors="coerce") or 0)
            fdesde = safe_date(d.get("fecha_desde"), None)
            fecha_mov = fdesde if (fdesde is not None and (inicio_per is None or fdesde >= inicio_per) and (fin_per is None or fdesde <= fin_per)) else inicio_per
            hs = float(pd.to_numeric(d.get("horas"), errors="coerce") or 0)
            detalle = (
                f"{nombre_per} - {d.get('cargo','')} - {d.get('dedicacion','')} - {hs:g} hs - "
                f"{d.get('tipo_designacion','')}"
            )
            fila = {c: pd.NA for c in base.columns}
            fila.update({
                "id": -900000000 - did,
                "periodo_id": pid,
                "periodo": nombre_per,
                "fecha": fecha_mov.isoformat() if fecha_mov is not None else str(actual.get("fecha_inicio") or ""),
                "tipo_movimiento": "Alta de designación",
                "cuil": d.get("cuil", ""),
                "nombre": d.get("nombre_completo", d.get("nombre", d.get("cuil", ""))),
                "detalle": detalle,
                "observaciones": "Base inicial del sistema: la designación real del primer período se considera alta para el análisis histórico.",
                "horas_variacion": abs(hs),
            })
            if "acto_documento_id" in base.columns:
                fila["acto_documento_id"] = d.get("acto_documento_id", pd.NA)
            if "acto_administrativo" in base.columns:
                fila["acto_administrativo"] = d.get("acto_administrativo", "Pendiente de vincular")
            sinteticas.append(fila)
        if sinteticas:
            des_mov = pd.concat([des_mov, pd.DataFrame(sinteticas)], ignore_index=True, sort=False)
    elif anterior is not None and not des_mov.empty:
        try:
            prev = get_designaciones(int(anterior.get("id")))
            if prev is None:
                prev = pd.DataFrame()
        except Exception:
            prev = pd.DataFrame()
        cierre_prev = safe_date(anterior.get("fecha_fin"), None)
        if not prev.empty:
            prev = prev[prev.apply(lambda r: _vigente_al_cierre_v269(r, cierre_prev), axis=1)].copy()
        for idx, mov in des_mov.iterrows():
            if str(mov.get("tipo_movimiento") or "").strip() != "Alta de designación":
                continue
            clave = _clave_cuil(mov.get("cuil")) or str(mov.get("cuil") or "").strip()
            candidatos = prev[prev.get("cuil", pd.Series(index=prev.index,dtype=str)).fillna("").astype(str).map(lambda x: _clave_cuil(x) or str(x).strip()).eq(clave)].copy() if not prev.empty else pd.DataFrame()
            if candidatos.empty:
                continue
            coinciden = candidatos[candidatos.apply(lambda r: _detalle_coincide_designacion_v269(mov.get("detalle", ""), r), axis=1)].copy()
            if coinciden.empty and len(candidatos) == 1:
                coinciden = candidatos.copy()
            if coinciden.empty:
                continue
            # Si varias coinciden por un legacy poco específico, solo se reclasifica si todas
            # llevan al mismo tipo administrativo.
            tipos_prev = {normalizar_clave(x) for x in coinciden.get("tipo_designacion", pd.Series(dtype=str)).fillna("").astype(str)}
            if tipos_prev == {"CONCURSADO"}:
                nuevo_tipo = "Continuidad automática de designación concursada"
                nota = "Reclasificado desde un Alta legacy: la concursada ya estaba vigente al cierre del período anterior."
            elif "CONCURSADO" not in tipos_prev:
                nuevo_tipo = "Renovación automática de designación"
                nota = "Reclasificado desde un Alta legacy: la designación ya estaba vigente al cierre del período anterior."
            else:
                continue
            des_mov.at[idx, "tipo_movimiento"] = nuevo_tipo
            obs = str(des_mov.at[idx, "observaciones"] or "").strip() if "observaciones" in des_mov.columns else ""
            if "observaciones" in des_mov.columns:
                des_mov.at[idx, "observaciones"] = (obs + " | " if obs else "") + nota
            if "horas_variacion" in des_mov.columns:
                des_mov.at[idx, "horas_variacion"] = 0

    out = pd.concat([no_des, des_mov], ignore_index=True, sort=False) if preservar_no_designacion else des_mov
    if out.empty:
        return out
    # Orden estable: movimientos más recientes primero, como las vistas administrativas.
    orden_cols = [c for c in ["fecha", "id"] if c in out.columns]
    if orden_cols:
        asc = [False] * len(orden_cols)
        try:
            out = out.sort_values(orden_cols, ascending=asc, kind="stable", na_position="last")
        except Exception:
            pass
    return out.reset_index(drop=True)


# --- entry l. 10743-10745
def _fecha_proyecto(valor):
    from analisis.motor.ref.extracted_batch04.fechas import _fecha_proyecto as _b04_core__fecha_proyecto
    return _b04_core__fecha_proyecto(valor)


# --- entry l. 10748-10750
def _fechas_desde_periodo_legacy(periodo_ejecucion, anio_llamado=None):
    from analisis.motor.ref.domain.proyectos import _fechas_desde_periodo_legacy as _b05_core__fechas_desde_periodo_legacy
    return _b05_core__fechas_desde_periodo_legacy(periodo_ejecucion, anio_llamado)


# --- entry l. 10753-10755
def _texto_periodo_proyecto(fecha_inicio, fecha_fin):
    from analisis.motor.ref.domain.proyectos import _texto_periodo_proyecto as _b05_core__texto_periodo_proyecto
    return _b05_core__texto_periodo_proyecto(fecha_inicio, fecha_fin)


# --- entry l. 10758-10771
def _situacion_proyecto(fila, fecha_referencia=None):
    estado = str((fila or {}).get("estado") or "Activo").strip()
    if estado in ["Suspendido", "Archivado"]:
        return estado
    if estado == "Finalizado":
        return "Finalizado"
    referencia = _fecha_proyecto(fecha_referencia) or date.today()
    inicio = _fecha_proyecto((fila or {}).get("fecha_inicio"))
    fin = _fecha_proyecto((fila or {}).get("fecha_fin"))
    if fin and fin < referencia:
        return "Finalizado"
    if inicio and inicio > referencia:
        return "Programado"
    return "En ejecución"


# --- entry l. 10774-10776
def proyecto_vigente_en_periodo(proyecto, periodo):
    from analisis.motor.ref.domain.proyectos import proyecto_vigente_en_periodo as _b05_core_proyecto_vigente_en_periodo
    return _b05_core_proyecto_vigente_en_periodo(proyecto, periodo)


# --- entry l. 10780-11164
def asegurar_esquema_investigacion_separado():
    """Prepara el catálogo institucional de proyectos y las asignaciones departamentales.

    En PostgreSQL existe un único registro de cada proyecto por institución. El
    campo ``departamento_id`` conserva el departamento creador, pero no limita la
    visibilidad: todos los departamentos de la institución pueden usar el proyecto.
    Las filas de ``investigacion_docente`` continúan perteneciendo al departamento
    que realizó cada asignación.
    """
    if st.session_state.get("_esquema_investigacion_institucional_v4_ok"):
        return

    if USE_POSTGRESQL:
        try:
            import psycopg2
            conn = _pg_raw_conn()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS proyectos_investigacion (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT,
                    nombre_proyecto TEXT NOT NULL,
                    codigo_proyecto TEXT,
                    instituto_proyecto TEXT,
                    anio_llamado INTEGER,
                    fecha_inicio DATE,
                    fecha_fin DATE,
                    periodo_ejecucion TEXT,
                    observaciones TEXT,
                    estado TEXT DEFAULT 'Activo',
                    fecha_carga TEXT,
                    fecha_suspension DATE,
                    motivo_suspension TEXT
                )
            """)
            cur.execute("ALTER TABLE proyectos_investigacion ADD COLUMN IF NOT EXISTS institucion_id BIGINT")
            cur.execute("ALTER TABLE proyectos_investigacion ADD COLUMN IF NOT EXISTS departamento_id BIGINT")
            cur.execute("ALTER TABLE proyectos_investigacion ADD COLUMN IF NOT EXISTS fecha_inicio DATE")
            cur.execute("ALTER TABLE proyectos_investigacion ADD COLUMN IF NOT EXISTS fecha_fin DATE")
            cur.execute("ALTER TABLE proyectos_investigacion ADD COLUMN IF NOT EXISTS fecha_suspension DATE")
            cur.execute("ALTER TABLE proyectos_investigacion ADD COLUMN IF NOT EXISTS motivo_suspension TEXT")
            cur.execute("ALTER TABLE investigacion_docente ADD COLUMN IF NOT EXISTS proyecto_id BIGINT")
            cur.execute("ALTER TABLE investigacion_docente ADD COLUMN IF NOT EXISTS estado_asignacion TEXT DEFAULT 'Activa'")
            cur.execute("ALTER TABLE investigacion_docente ADD COLUMN IF NOT EXISTS fecha_baja TEXT")
            cur.execute("ALTER TABLE investigacion_docente ADD COLUMN IF NOT EXISTS motivo_baja TEXT")
            cur.execute("""
                UPDATE investigacion_docente
                SET estado_asignacion = 'Activa'
                WHERE estado_asignacion IS NULL OR TRIM(estado_asignacion) = ''
            """)

            # Vincula registros históricos todavía sueltos con un proyecto
            # institucional. El departamento del primer registro queda como creador.
            cur.execute("""
                SELECT DISTINCT institucion_id, departamento_id,
                    COALESCE(nombre_proyecto, ''), COALESCE(codigo_proyecto, ''),
                    COALESCE(instituto_proyecto, ''), anio_llamado,
                    COALESCE(periodo_ejecucion, '')
                FROM investigacion_docente
                WHERE proyecto_id IS NULL
                  AND TRIM(COALESCE(nombre_proyecto, '')) <> ''
                ORDER BY institucion_id, departamento_id
            """)
            for inst_id, dep_id, nombre, codigo, instituto, anio, ejecucion in cur.fetchall():
                if str(codigo or "").strip():
                    cur.execute("""
                        SELECT id
                        FROM proyectos_investigacion
                        WHERE institucion_id = %s
                          AND UPPER(TRIM(COALESCE(codigo_proyecto, ''))) = UPPER(TRIM(%s))
                        ORDER BY id
                        LIMIT 1
                    """, [inst_id, codigo])
                else:
                    fecha_inicio, fecha_fin = _fechas_desde_periodo_legacy(ejecucion, anio)
                    cur.execute("""
                        SELECT id
                        FROM proyectos_investigacion
                        WHERE institucion_id = %s
                          AND UPPER(TRIM(COALESCE(nombre_proyecto, ''))) = UPPER(TRIM(%s))
                          AND COALESCE(anio_llamado, -1) = COALESCE(%s, -1)
                          AND fecha_inicio IS NOT DISTINCT FROM %s
                          AND fecha_fin IS NOT DISTINCT FROM %s
                        ORDER BY id
                        LIMIT 1
                    """, [inst_id, nombre, anio, fecha_inicio, fecha_fin])
                fila = cur.fetchone()
                if fila:
                    proyecto_id = int(fila[0])
                else:
                    fecha_inicio, fecha_fin = _fechas_desde_periodo_legacy(ejecucion, anio)
                    cur.execute("""
                        INSERT INTO proyectos_investigacion
                        (institucion_id, departamento_id, nombre_proyecto, codigo_proyecto,
                         instituto_proyecto, anio_llamado, fecha_inicio, fecha_fin,
                         periodo_ejecucion, observaciones, estado, fecha_carga)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '', 'Activo', %s)
                        RETURNING id
                    """, [inst_id, dep_id, nombre, codigo, instituto, anio,
                          fecha_inicio, fecha_fin, ejecucion, str(date.today())])
                    proyecto_id = int(cur.fetchone()[0])

                if str(codigo or "").strip():
                    cur.execute("""
                        UPDATE investigacion_docente
                        SET proyecto_id = %s
                        WHERE proyecto_id IS NULL
                          AND institucion_id = %s
                          AND departamento_id IS NOT DISTINCT FROM %s
                          AND UPPER(TRIM(COALESCE(codigo_proyecto, ''))) = UPPER(TRIM(%s))
                    """, [proyecto_id, inst_id, dep_id, codigo])
                else:
                    cur.execute("""
                        UPDATE investigacion_docente
                        SET proyecto_id = %s
                        WHERE proyecto_id IS NULL
                          AND institucion_id = %s
                          AND departamento_id IS NOT DISTINCT FROM %s
                          AND UPPER(TRIM(COALESCE(nombre_proyecto, ''))) = UPPER(TRIM(%s))
                          AND COALESCE(anio_llamado, -1) = COALESCE(%s, -1)
                          AND UPPER(TRIM(COALESCE(periodo_ejecucion, ''))) = UPPER(TRIM(%s))
                    """, [proyecto_id, inst_id, dep_id, nombre, anio, ejecucion])

            # Migra períodos antiguos escritos como texto a fechas reales.
            cur.execute("""
                SELECT id, periodo_ejecucion, anio_llamado
                FROM proyectos_investigacion
                WHERE fecha_inicio IS NULL OR fecha_fin IS NULL
            """)
            for proyecto_id, ejecucion, anio in cur.fetchall():
                fecha_inicio, fecha_fin = _fechas_desde_periodo_legacy(ejecucion, anio)
                if fecha_inicio or fecha_fin:
                    cur.execute("""
                        UPDATE proyectos_investigacion
                        SET fecha_inicio = COALESCE(fecha_inicio, %s),
                            fecha_fin = COALESCE(fecha_fin, %s),
                            periodo_ejecucion = %s
                        WHERE id = %s
                    """, [fecha_inicio, fecha_fin,
                          _texto_periodo_proyecto(fecha_inicio, fecha_fin) or ejecucion,
                          proyecto_id])

            # Unifica las copias departamentales existentes. Primero se redirigen
            # todas las asignaciones al id canónico y después se borran duplicados.
            cur.execute("""
                WITH ranked AS (
                    SELECT id,
                           MIN(id) OVER (
                               PARTITION BY institucion_id,
                                            UPPER(TRIM(COALESCE(codigo_proyecto, '')))
                           ) AS canonico
                    FROM proyectos_investigacion
                    WHERE TRIM(COALESCE(codigo_proyecto, '')) <> ''
                )
                UPDATE investigacion_docente i
                SET proyecto_id = r.canonico
                FROM ranked r
                WHERE i.proyecto_id = r.id
                  AND r.id <> r.canonico
            """)
            cur.execute("""
                WITH ranked AS (
                    SELECT id,
                           MIN(id) OVER (
                               PARTITION BY institucion_id,
                                            UPPER(TRIM(COALESCE(codigo_proyecto, '')))
                           ) AS canonico
                    FROM proyectos_investigacion
                    WHERE TRIM(COALESCE(codigo_proyecto, '')) <> ''
                )
                DELETE FROM proyectos_investigacion p
                USING ranked r
                WHERE p.id = r.id
                  AND r.id <> r.canonico
            """)
            cur.execute("""
                WITH ranked AS (
                    SELECT id,
                           MIN(id) OVER (
                               PARTITION BY institucion_id,
                                            UPPER(TRIM(COALESCE(nombre_proyecto, ''))),
                                            COALESCE(anio_llamado, -1),
                                            fecha_inicio,
                                            fecha_fin
                           ) AS canonico
                    FROM proyectos_investigacion
                    WHERE TRIM(COALESCE(codigo_proyecto, '')) = ''
                )
                UPDATE investigacion_docente i
                SET proyecto_id = r.canonico
                FROM ranked r
                WHERE i.proyecto_id = r.id
                  AND r.id <> r.canonico
            """)
            cur.execute("""
                WITH ranked AS (
                    SELECT id,
                           MIN(id) OVER (
                               PARTITION BY institucion_id,
                                            UPPER(TRIM(COALESCE(nombre_proyecto, ''))),
                                            COALESCE(anio_llamado, -1),
                                            fecha_inicio,
                                            fecha_fin
                           ) AS canonico
                    FROM proyectos_investigacion
                    WHERE TRIM(COALESCE(codigo_proyecto, '')) = ''
                )
                DELETE FROM proyectos_investigacion p
                USING ranked r
                WHERE p.id = r.id
                  AND r.id <> r.canonico
            """)

            # Mantiene las columnas históricas de cada asignación sincronizadas
            # con el único proyecto institucional.
            cur.execute("""
                UPDATE investigacion_docente i
                SET nombre_proyecto = p.nombre_proyecto,
                    codigo_proyecto = p.codigo_proyecto,
                    instituto_proyecto = p.instituto_proyecto,
                    anio_llamado = p.anio_llamado,
                    periodo_ejecucion = p.periodo_ejecucion
                FROM proyectos_investigacion p
                WHERE i.proyecto_id = p.id
            """)

            cur.execute("DROP INDEX IF EXISTS idx_deptit_proyectos_inv_scope")
            cur.execute("DROP INDEX IF EXISTS idx_deptit_proyectos_inv_codigo")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_proyectos_inv_institucion ON proyectos_investigacion (institucion_id)")
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_deptit_proyectos_inv_codigo_institucional
                ON proyectos_investigacion (institucion_id, UPPER(TRIM(codigo_proyecto)))
                WHERE TRIM(COALESCE(codigo_proyecto, '')) <> ''
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_deptit_proyectos_inv_sin_codigo_institucional
                ON proyectos_investigacion (
                    institucion_id,
                    UPPER(TRIM(nombre_proyecto)),
                    COALESCE(anio_llamado, -1),
                    fecha_inicio,
                    fecha_fin
                )
                WHERE TRIM(COALESCE(codigo_proyecto, '')) = ''
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_proyectos_inv_fechas ON proyectos_investigacion (fecha_inicio, fecha_fin)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_inv_doc_proyecto ON investigacion_docente (proyecto_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_inv_doc_cuil_periodo ON investigacion_docente (institucion_id, cuil, periodo_id)")

            conn.commit()
            cur.close()
            conn.close()
            st.session_state["_esquema_investigacion_institucional_v4_ok"] = True
            return
        except Exception as e:
            try:
                st.warning(f"No se pudo preparar el catálogo institucional de investigación: {e}")
            except Exception:
                pass
            return

    # Compatibilidad SQLite: se conserva el catálogo dentro de la base activa.
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS proyectos_investigacion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_proyecto TEXT NOT NULL,
                codigo_proyecto TEXT,
                instituto_proyecto TEXT,
                anio_llamado INTEGER,
                fecha_inicio TEXT,
                fecha_fin TEXT,
                periodo_ejecucion TEXT,
                observaciones TEXT,
                estado TEXT DEFAULT 'Activo',
                fecha_carga TEXT
            )
        """)
        add_column_if_not_exists(c, "proyectos_investigacion", "fecha_inicio", "TEXT")
        add_column_if_not_exists(c, "proyectos_investigacion", "fecha_fin", "TEXT")
        add_column_if_not_exists(c, "proyectos_investigacion", "fecha_suspension", "TEXT")
        add_column_if_not_exists(c, "proyectos_investigacion", "motivo_suspension", "TEXT")
        add_column_if_not_exists(c, "investigacion_docente", "proyecto_id", "INTEGER")
        add_column_if_not_exists(c, "investigacion_docente", "estado_asignacion", "TEXT DEFAULT 'Activa'")
        add_column_if_not_exists(c, "investigacion_docente", "fecha_baja", "TEXT")
        add_column_if_not_exists(c, "investigacion_docente", "motivo_baja", "TEXT")
        c.execute("""
            UPDATE investigacion_docente
            SET estado_asignacion = 'Activa'
            WHERE estado_asignacion IS NULL OR TRIM(estado_asignacion) = ''
        """)
        conn.commit()

        df_legacy = pd.read_sql("""
            SELECT DISTINCT COALESCE(nombre_proyecto, '') AS nombre_proyecto,
                COALESCE(codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(instituto_proyecto, '') AS instituto_proyecto,
                anio_llamado, COALESCE(periodo_ejecucion, '') AS periodo_ejecucion
            FROM investigacion_docente
            WHERE proyecto_id IS NULL
              AND TRIM(COALESCE(nombre_proyecto, '')) <> ''
        """, conn)
        for _, row in df_legacy.iterrows():
            nombre = str(row.get("nombre_proyecto") or "").strip()
            codigo = str(row.get("codigo_proyecto") or "").strip()
            instituto = str(row.get("instituto_proyecto") or "").strip()
            anio = row.get("anio_llamado")
            ejecucion = str(row.get("periodo_ejecucion") or "").strip()
            if codigo:
                c.execute("""
                    SELECT id FROM proyectos_investigacion
                    WHERE UPPER(TRIM(COALESCE(codigo_proyecto,'')))=UPPER(TRIM(?))
                    ORDER BY id LIMIT 1
                """, (codigo,))
            else:
                c.execute("""
                    SELECT id FROM proyectos_investigacion
                    WHERE UPPER(TRIM(COALESCE(nombre_proyecto,'')))=UPPER(TRIM(?))
                      AND COALESCE(anio_llamado,-1)=COALESCE(?,-1)
                      AND UPPER(TRIM(COALESCE(periodo_ejecucion,'')))=UPPER(TRIM(?))
                    ORDER BY id LIMIT 1
                """, (nombre, anio, ejecucion))
            existente = c.fetchone()
            if existente:
                proyecto_id = int(existente[0])
            else:
                fecha_inicio, fecha_fin = _fechas_desde_periodo_legacy(ejecucion, anio)
                c.execute("""
                    INSERT INTO proyectos_investigacion
                    (nombre_proyecto, codigo_proyecto, instituto_proyecto, anio_llamado,
                     fecha_inicio, fecha_fin, periodo_ejecucion, observaciones, estado, fecha_carga)
                    VALUES (?, ?, ?, ?, ?, ?, ?, '', 'Activo', ?)
                """, (nombre, codigo, instituto, anio,
                      str(fecha_inicio) if fecha_inicio else None,
                      str(fecha_fin) if fecha_fin else None,
                      ejecucion, str(date.today())))
                proyecto_id = int(c.lastrowid)
            if codigo:
                c.execute("""
                    UPDATE investigacion_docente
                    SET proyecto_id=?
                    WHERE proyecto_id IS NULL
                      AND UPPER(TRIM(COALESCE(codigo_proyecto,'')))=UPPER(TRIM(?))
                """, (proyecto_id, codigo))
            else:
                c.execute("""
                    UPDATE investigacion_docente SET proyecto_id=?
                    WHERE proyecto_id IS NULL
                      AND UPPER(TRIM(COALESCE(nombre_proyecto,'')))=UPPER(TRIM(?))
                      AND COALESCE(anio_llamado,-1)=COALESCE(?,-1)
                      AND UPPER(TRIM(COALESCE(periodo_ejecucion,'')))=UPPER(TRIM(?))
                """, (proyecto_id, nombre, anio, ejecucion))

        df_fechas = pd.read_sql("""
            SELECT id, periodo_ejecucion, anio_llamado, fecha_inicio, fecha_fin
            FROM proyectos_investigacion
        """, conn)
        for _, row in df_fechas.iterrows():
            if _fecha_proyecto(row.get("fecha_inicio")) and _fecha_proyecto(row.get("fecha_fin")):
                continue
            fecha_inicio, fecha_fin = _fechas_desde_periodo_legacy(
                row.get("periodo_ejecucion"), row.get("anio_llamado")
            )
            if fecha_inicio or fecha_fin:
                c.execute("""
                    UPDATE proyectos_investigacion
                    SET fecha_inicio=COALESCE(fecha_inicio, ?),
                        fecha_fin=COALESCE(fecha_fin, ?),
                        periodo_ejecucion=?
                    WHERE id=?
                """, (str(fecha_inicio) if fecha_inicio else None,
                      str(fecha_fin) if fecha_fin else None,
                      _texto_periodo_proyecto(fecha_inicio, fecha_fin) or row.get("periodo_ejecucion", ""),
                      int(row["id"])))
        conn.commit()
        conn.close()
        st.session_state["_esquema_investigacion_institucional_v4_ok"] = True
    except Exception as e:
        try:
            st.warning(f"No se pudo preparar el esquema histórico de investigación: {e}")
        except Exception:
            pass


# --- entry l. 12105-12233
def asegurar_esquema_extension_separado():
    """Crea el catálogo institucional de extensión y sus asignaciones departamentales."""
    if st.session_state.get("_esquema_extension_institucional_v2_ok"):
        return
    if USE_POSTGRESQL:
        try:
            conn = _pg_raw_conn()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS proyectos_extension (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT,
                    nombre_proyecto TEXT NOT NULL,
                    codigo_proyecto TEXT,
                    instituto_proyecto TEXT,
                    anio_llamado INTEGER,
                    fecha_inicio DATE,
                    fecha_fin DATE,
                    periodo_ejecucion TEXT,
                    observaciones TEXT,
                    estado TEXT DEFAULT 'Activo',
                    fecha_carga TEXT,
                    fecha_suspension DATE,
                    motivo_suspension TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS extension_docente (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT,
                    proyecto_id BIGINT,
                    periodo_id BIGINT,
                    cuil TEXT,
                    nombre_proyecto TEXT,
                    rol TEXT,
                    anio_llamado INTEGER,
                    periodo_ejecucion TEXT,
                    horas_asignadas REAL,
                    observaciones TEXT,
                    fecha_carga TEXT,
                    codigo_proyecto TEXT,
                    instituto_proyecto TEXT,
                    estado_asignacion TEXT DEFAULT 'Activa',
                    fecha_baja TEXT,
                    motivo_baja TEXT
                )
            """)
            cur.execute("ALTER TABLE proyectos_extension ADD COLUMN IF NOT EXISTS institucion_id BIGINT")
            cur.execute("ALTER TABLE proyectos_extension ADD COLUMN IF NOT EXISTS departamento_id BIGINT")
            cur.execute("ALTER TABLE proyectos_extension ADD COLUMN IF NOT EXISTS fecha_inicio DATE")
            cur.execute("ALTER TABLE proyectos_extension ADD COLUMN IF NOT EXISTS fecha_fin DATE")
            cur.execute("ALTER TABLE proyectos_extension ADD COLUMN IF NOT EXISTS fecha_suspension DATE")
            cur.execute("ALTER TABLE proyectos_extension ADD COLUMN IF NOT EXISTS motivo_suspension TEXT")
            cur.execute("ALTER TABLE extension_docente ADD COLUMN IF NOT EXISTS institucion_id BIGINT")
            cur.execute("ALTER TABLE extension_docente ADD COLUMN IF NOT EXISTS departamento_id BIGINT")
            cur.execute("ALTER TABLE extension_docente ADD COLUMN IF NOT EXISTS proyecto_id BIGINT")
            cur.execute("ALTER TABLE extension_docente ADD COLUMN IF NOT EXISTS estado_asignacion TEXT DEFAULT 'Activa'")
            cur.execute("ALTER TABLE extension_docente ADD COLUMN IF NOT EXISTS fecha_baja TEXT")
            cur.execute("ALTER TABLE extension_docente ADD COLUMN IF NOT EXISTS motivo_baja TEXT")
            cur.execute("""
                UPDATE extension_docente
                SET estado_asignacion = 'Activa'
                WHERE estado_asignacion IS NULL OR TRIM(estado_asignacion) = ''
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_proyectos_ext_institucion ON proyectos_extension (institucion_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_proyectos_ext_codigo ON proyectos_extension (institucion_id, UPPER(TRIM(codigo_proyecto)))")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_proyectos_ext_fechas ON proyectos_extension (fecha_inicio, fecha_fin)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_ext_doc_proyecto ON extension_docente (proyecto_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_ext_doc_cuil_periodo ON extension_docente (institucion_id, cuil, periodo_id)")
            conn.commit()
            cur.close(); conn.close()
            st.session_state["_esquema_extension_institucional_v2_ok"] = True
            return
        except Exception as e:
            try:
                st.warning(f"No se pudo preparar el catálogo institucional de extensión: {e}")
            except Exception:
                pass
            return

    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS proyectos_extension (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_proyecto TEXT NOT NULL,
                codigo_proyecto TEXT,
                instituto_proyecto TEXT,
                anio_llamado INTEGER,
                fecha_inicio TEXT,
                fecha_fin TEXT,
                periodo_ejecucion TEXT,
                observaciones TEXT,
                estado TEXT DEFAULT 'Activo',
                fecha_carga TEXT
            )
        """)
        add_column_if_not_exists(c, "proyectos_extension", "fecha_suspension", "TEXT")
        add_column_if_not_exists(c, "proyectos_extension", "motivo_suspension", "TEXT")
        c.execute("""
            CREATE TABLE IF NOT EXISTS extension_docente (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proyecto_id INTEGER,
                periodo_id INTEGER,
                cuil TEXT,
                nombre_proyecto TEXT,
                rol TEXT,
                anio_llamado INTEGER,
                periodo_ejecucion TEXT,
                horas_asignadas REAL,
                observaciones TEXT,
                fecha_carga TEXT,
                codigo_proyecto TEXT,
                instituto_proyecto TEXT,
                estado_asignacion TEXT DEFAULT 'Activa',
                fecha_baja TEXT,
                motivo_baja TEXT
            )
        """)
        conn.commit(); conn.close()
        st.session_state["_esquema_extension_institucional_v2_ok"] = True
    except Exception as e:
        try:
            st.warning(f"No se pudo preparar el esquema de extensión: {e}")
        except Exception:
            pass


# --- entry l. 12353-12355
def tipo_espacio_curricular_v120(codigo, asignatura):
    from analisis.motor.ref.domain.materias import tipo_espacio_curricular_v120 as _b05_core_tipo_espacio_curricular_v120
    return _b05_core_tipo_espacio_curricular_v120(codigo, asignatura)


# --- entry l. 12489-12491
def get_opcion_curricular_v120(opcion_id):
    from analisis.motor.ref.extracted_batch03.readonly_queries import get_opcion_curricular_v120 as _b03_core_get_opcion_curricular_v120
    return _b03_core_get_opcion_curricular_v120(opcion_id, get_planes_conn=get_planes_conn, pd=pd)


# --- entry l. 12492-12498
def _cache_scope_opciones_v127():
    try:
        inst_id = _pg_current_inst_id() if USE_POSTGRESQL else 0
    except Exception:
        inst_id = 0
    version = int(st.session_state.get("_opciones_cache_version_v127", 0) or 0)
    return str(DATABASE_URL), int(inst_id or 0), version


# --- entry l. 12501-12520
def limpiar_cache_opciones_curriculares_v127():
    """Invalida solo las lecturas pesadas del catálogo de Optativas/Electivas."""
    try:
        st.session_state["_opciones_cache_version_v127"] = int(
            st.session_state.get("_opciones_cache_version_v127", 0) or 0
        ) + 1
    except Exception:
        pass
    for nombre in [
        "_get_vinculos_opcion_curricular_v120_cache_v127",
        "_get_opciones_curriculares_v120_cache_v127",
        "_generar_excel_modelo_carga_rapida_opciones_cache_v127",
        "_get_opciones_curriculares_para_materia_cache_v129",
    ]:
        try:
            fn = globals().get(nombre)
            if fn is not None and hasattr(fn, "clear"):
                fn.clear()
        except Exception:
            pass


# --- entry l. 12523-12584
def _get_vinculos_opciones_lote_v127(opcion_ids, solo_vigentes=False):
    """Trae habilitaciones de varias opciones en una sola consulta.

    Evita el patrón N+1 que antes consultaba nuevamente todos los planes por cada
    opción curricular visible en pantalla.
    """
    ids = []
    for x in list(opcion_ids or []):
        try:
            v = int(x)
        except Exception:
            continue
        if v not in ids:
            ids.append(v)
    columnas = [
        "vinculo_id", "opcion_id", "materia_id", "fecha_vinculacion", "codigo", "asignatura",
        "tipo_espacio", "carrera_id", "carrera", "escuela", "plan_version", "anio",
        "cuatrimestre", "estado", "en_plan"
    ]
    if not ids:
        return pd.DataFrame(columns=columnas)
    ph = ",".join(["?"] * len(ids))
    conn = get_planes_conn()
    try:
        sql = f"""
            SELECT
                om.id AS vinculo_id,
                om.opcion_id,
                om.materia_id,
                om.fecha_vinculacion,
                COALESCE(m.codigo, '') AS codigo,
                COALESCE(m.asignatura, '') AS asignatura,
                m.carrera_id,
                COALESCE(m.carrera, '') AS carrera,
                COALESCE(m.escuela, '') AS escuela,
                COALESCE(m.plan_version, '') AS plan_version,
                COALESCE(m.anio, '') AS anio,
                COALESCE(m.cuatrimestre, '') AS cuatrimestre,
                COALESCE(m.estado, 'Activa') AS estado,
                COALESCE(m.en_plan, 1) AS en_plan
            FROM opcion_curricular_materias om
            JOIN materias m ON m.id = om.materia_id
            WHERE om.opcion_id IN ({ph})
            ORDER BY om.opcion_id, m.escuela, m.carrera, m.plan_version, m.codigo, m.asignatura
        """
        out = pd.read_sql(sql, conn, params=ids)
    finally:
        conn.close()
    if out.empty:
        return pd.DataFrame(columns=columnas)
    out["tipo_espacio"] = out.apply(
        lambda r: tipo_espacio_curricular_v120(r.get("codigo", ""), r.get("asignatura", "")),
        axis=1,
    )
    if solo_vigentes:
        en_plan = pd.to_numeric(out["en_plan"], errors="coerce").fillna(1).astype(int)
        estado = out["estado"].fillna("Activa").astype(str).str.strip().str.lower()
        out = out[(en_plan == 1) & estado.isin(["", "activa"])].copy()
    for col in columnas:
        if col not in out.columns:
            out[col] = ""
    return out[columnas].reset_index(drop=True)


# --- entry l. 12609-12681
def _get_opciones_curriculares_v120_no_cache_v127(tipo=None, estado=None):
    """Catálogo enriquecido en dos consultas: opciones + todas sus habilitaciones."""
    conn = get_planes_conn()
    filtros, params = [], []
    if tipo in TIPOS_OPCION_CURRICULAR:
        filtros.append("tipo = ?")
        params.append(tipo)
    if estado in ESTADOS_OPCION_CURRICULAR:
        filtros.append("estado = ?")
        params.append(estado)
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    try:
        df = pd.read_sql(f"""
            SELECT id, tipo, codigo, nombre, escuela_oferente, estado, observaciones,
                   fecha_creacion, fecha_actualizacion
            FROM opciones_curriculares
            {where}
            ORDER BY tipo, nombre, codigo
        """, conn, params=params)
    finally:
        conn.close()

    columnas_extra = [
        "cantidad_habilitaciones", "destinos", "carreras_habilitadas",
        "escuelas_destino", "espacios_plan"
    ]
    for col in columnas_extra:
        df[col] = "" if col != "cantidad_habilitaciones" else 0
    if df.empty:
        return df

    ids = pd.to_numeric(df["id"], errors="coerce").dropna().astype(int).tolist()
    vinculos = _get_vinculos_opciones_lote_v127(ids, solo_vigentes=True)
    if vinculos.empty:
        return df

    grupos = {int(k): g.copy() for k, g in vinculos.groupby("opcion_id", sort=False)}
    for i, row in df.iterrows():
        try:
            oid = int(row["id"])
        except Exception:
            continue
        vinc = grupos.get(oid, pd.DataFrame())
        if vinc.empty:
            continue
        destinos = []
        for _, v in vinc.iterrows():
            partes = []
            carrera = limpiar_texto_tabla(v.get("carrera", ""))
            espacio = limpiar_texto_tabla(v.get("asignatura", ""))
            codigo = limpiar_texto_tabla(v.get("codigo", ""))
            plan = limpiar_texto_tabla(v.get("plan_version", ""))
            if carrera:
                partes.append(carrera)
            if codigo or espacio:
                partes.append(f"{codigo} - {espacio}".strip(" -"))
            if plan:
                partes.append(plan)
            if partes:
                destinos.append(" · ".join(partes))
        df.at[i, "cantidad_habilitaciones"] = int(len(vinc))
        df.at[i, "destinos"] = " | ".join(destinos)
        df.at[i, "carreras_habilitadas"] = _deptit_join_unicos(
            vinc.get("carrera", pd.Series(dtype=str)).tolist(), sep=" / "
        )
        df.at[i, "escuelas_destino"] = _deptit_join_unicos(
            vinc.get("escuela", pd.Series(dtype=str)).tolist(), sep=" / "
        )
        df.at[i, "espacios_plan"] = _deptit_join_unicos([
            f"{limpiar_texto_tabla(v.get('codigo',''))} - {limpiar_texto_tabla(v.get('asignatura',''))}".strip(" -")
            for _, v in vinc.iterrows()
        ], sep=" / ")
    return df


# --- entry l. 12685-12686
def _get_opciones_curriculares_v120_cache_v127(tipo, estado, db_url, inst_id, version):
    return _get_opciones_curriculares_v120_no_cache_v127(tipo=tipo, estado=estado)


# --- entry l. 12689-12692
def get_opciones_curriculares_v120(tipo=None, estado=None):
    db_url, inst_id, version = _cache_scope_opciones_v127()
    df = _get_opciones_curriculares_v120_cache_v127(tipo, estado, db_url, inst_id, version)
    return df.copy()


# --- entry l. 13476-13579
def asegurar_esquema_inscriptos_comision():
    """Prepara inscriptos por código/materia sin romper registros históricos.

    ``inscriptos_comision`` se conserva como tabla legacy (una cantidad global por
    comisión). Desde v123 la fuente operativa es ``inscriptos_comision_materia``:
    una fila por comisión + materia conceptual/código. El total de la comisión se
    calcula como suma de sus códigos.
    """
    if st.session_state.get("_esquema_inscriptos_comision_v123_ok"):
        return
    try:
        if USE_POSTGRESQL:
            conn = _pg_raw_conn(); cur = conn.cursor()
            # Tabla legacy: se conserva para no perder datos previos.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS inscriptos_comision (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT,
                    comision_id BIGINT NOT NULL,
                    cantidad INTEGER DEFAULT 0,
                    cantidad_final INTEGER,
                    fecha_actualizacion TEXT,
                    fecha_actualizacion_final TEXT,
                    observaciones TEXT
                )
            """)
            cur.execute("ALTER TABLE inscriptos_comision ADD COLUMN IF NOT EXISTS cantidad_final INTEGER")
            cur.execute("ALTER TABLE inscriptos_comision ADD COLUMN IF NOT EXISTS fecha_actualizacion_final TEXT")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS inscriptos_comision_materia (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT,
                    comision_id BIGINT NOT NULL,
                    materia_id BIGINT NOT NULL,
                    cantidad INTEGER DEFAULT 0,
                    cantidad_final INTEGER,
                    fecha_actualizacion TEXT,
                    fecha_actualizacion_final TEXT,
                    observaciones TEXT
                )
            """)
            for nombre, tipo in [
                ("institucion_id", "BIGINT"), ("departamento_id", "BIGINT"),
                ("comision_id", "BIGINT"), ("materia_id", "BIGINT"),
                ("cantidad", "INTEGER DEFAULT 0"), ("cantidad_final", "INTEGER"),
                ("fecha_actualizacion", "TEXT"), ("fecha_actualizacion_final", "TEXT"),
                ("observaciones", "TEXT"),
            ]:
                cur.execute(f"ALTER TABLE inscriptos_comision_materia ADD COLUMN IF NOT EXISTS {nombre} {tipo}")
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_deptit_inscriptos_comision_materia_v123
                ON inscriptos_comision_materia (institucion_id, departamento_id, comision_id, materia_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_deptit_inscriptos_comision_materia_comision_v123
                ON inscriptos_comision_materia (institucion_id, departamento_id, comision_id)
            """)
            conn.commit(); cur.close(); conn.close()
        else:
            conn = get_conn(); c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS inscriptos_comision (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comision_id INTEGER NOT NULL UNIQUE,
                    cantidad INTEGER DEFAULT 0,
                    cantidad_final INTEGER,
                    fecha_actualizacion TEXT,
                    fecha_actualizacion_final TEXT,
                    observaciones TEXT
                )
            """)
            add_column_if_not_exists(c, "inscriptos_comision", "cantidad_final", "INTEGER")
            add_column_if_not_exists(c, "inscriptos_comision", "fecha_actualizacion_final", "TEXT")
            c.execute("""
                CREATE TABLE IF NOT EXISTS inscriptos_comision_materia (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comision_id INTEGER NOT NULL,
                    materia_id INTEGER NOT NULL,
                    cantidad INTEGER DEFAULT 0,
                    cantidad_final INTEGER,
                    fecha_actualizacion TEXT,
                    fecha_actualizacion_final TEXT,
                    observaciones TEXT,
                    UNIQUE(comision_id, materia_id)
                )
            """)
            conn.commit(); conn.close()
        st.session_state["_esquema_inscriptos_comision_v123_ok"] = True
        # En el arranque esta función se invoca antes de que estén definidas las
        # utilidades multicódigo v122. La migración legacy se difiere hasta que esas
        # funciones existan; get_inscriptos_comisiones_periodo() vuelve a intentarla.
        if "get_materias_conceptuales_comision_v122" in globals():
            try:
                migrar_inscriptos_legacy_por_materia_v123()
            except Exception as e:
                st.session_state["_migracion_inscriptos_v123_error"] = str(e)
    except Exception as e:
        try:
            st.warning(f"No se pudo preparar el registro de inscriptos por código: {e}")
        except Exception:
            pass


# --- entry l. 13582-13591
def _materia_representante_inscriptos_v123(materia_id):
    try:
        mid = int(materia_id)
    except Exception:
        return None
    info = get_materia_comision(mid) or {}
    try:
        return int(info.get("materia_id") or mid)
    except Exception:
        return mid


# --- entry l. 13594-13627
def get_materias_inscriptos_comision_v123(comision_id):
    """Devuelve una fila por código/materia conceptual que integra la comisión."""
    try:
        cid = int(comision_id)
    except Exception:
        return pd.DataFrame(columns=["materia_id_inscriptos", "codigo_materia", "asignatura", "carrera", "escuela", "plan_version"])

    reps = get_materias_conceptuales_comision_v122(cid)
    if not reps:
        try:
            conn = get_conn()
            df = pd.read_sql("SELECT materia_id FROM comisiones WHERE id=? LIMIT 1", conn, params=[cid])
            conn.close()
            if not df.empty and pd.notna(df.iloc[0].get("materia_id")):
                reps = [int(df.iloc[0]["materia_id"])]
        except Exception:
            reps = []

    registros, vistos = [], set()
    for mid_raw in reps:
        rep = _materia_representante_inscriptos_v123(mid_raw)
        if rep is None or rep in vistos:
            continue
        vistos.add(rep)
        info = get_materia_comision(rep) or {}
        registros.append({
            "materia_id_inscriptos": rep,
            "codigo_materia": limpiar_texto_tabla(info.get("codigo", "")),
            "asignatura": limpiar_texto_tabla(info.get("asignatura", "")),
            "carrera": limpiar_texto_tabla(info.get("carrera", "")),
            "escuela": limpiar_texto_tabla(info.get("escuela", "")),
            "plan_version": limpiar_texto_tabla(info.get("plan_version", "")),
        })
    return pd.DataFrame(registros)


# --- entry l. 13630-13692
def migrar_inscriptos_legacy_por_materia_v123():
    """Copia automáticamente datos legacy cuando una comisión tiene un solo código.

    Si una comisión legacy ya es multicódigo, la cantidad global no se reparte de
    manera arbitraria: se conserva como ``legacy_total_sin_discriminar`` hasta que
    el usuario cargue la distribución real por código.
    """
    if st.session_state.get("_migracion_inscriptos_legacy_v123_ok"):
        return {"migrados": 0, "multicodigo_pendientes": 0}
    conn = get_conn()
    try:
        legacy = pd.read_sql("""
            SELECT comision_id, COALESCE(cantidad,0) AS cantidad, cantidad_final,
                   COALESCE(fecha_actualizacion,'') AS fecha_actualizacion,
                   COALESCE(fecha_actualizacion_final,'') AS fecha_actualizacion_final,
                   COALESCE(observaciones,'') AS observaciones
            FROM inscriptos_comision
        """, conn)
        existentes = pd.read_sql("SELECT comision_id, materia_id FROM inscriptos_comision_materia", conn)
        claves_existentes = set()
        if not existentes.empty:
            for _, r in existentes.iterrows():
                try:
                    claves_existentes.add((int(r.get("comision_id")), int(r.get("materia_id"))))
                except Exception:
                    pass
        c = conn.cursor(); migrados = 0; pendientes = 0
        for _, r in legacy.iterrows():
            try:
                cid = int(r.get("comision_id"))
            except Exception:
                continue
            mats = get_materias_inscriptos_comision_v123(cid)
            if mats.empty:
                continue
            if len(mats) != 1:
                pendientes += 1
                continue
            mid = int(mats.iloc[0]["materia_id_inscriptos"])
            if (cid, mid) in claves_existentes:
                continue
            c.execute("""
                INSERT INTO inscriptos_comision_materia
                (comision_id, materia_id, cantidad, cantidad_final, fecha_actualizacion,
                 fecha_actualizacion_final, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                cid, mid, int(r.get("cantidad") or 0),
                None if pd.isna(r.get("cantidad_final")) else int(r.get("cantidad_final")),
                str(r.get("fecha_actualizacion") or ""),
                str(r.get("fecha_actualizacion_final") or ""),
                str(r.get("observaciones") or ""),
            ))
            claves_existentes.add((cid, mid)); migrados += 1
        conn.commit()
        st.session_state["_migracion_inscriptos_legacy_v123_ok"] = True
        return {"migrados": migrados, "multicodigo_pendientes": pendientes}
    except Exception:
        try: conn.rollback()
        except Exception: pass
        raise
    finally:
        conn.close()


# --- entry l. 13756-13803
def get_inscriptos_comision(comision_id, materia_id=None):
    """Devuelve un código concreto o, si se omite, el total sumado de la comisión."""
    asegurar_esquema_inscriptos_comision()
    cid = int(comision_id)
    conn = get_conn()
    try:
        if materia_id is not None:
            mid = _materia_representante_inscriptos_v123(materia_id)
            df = pd.read_sql("""
                SELECT id, comision_id, materia_id, COALESCE(cantidad,0) AS cantidad,
                       cantidad_final, COALESCE(fecha_actualizacion,'') AS fecha_actualizacion,
                       COALESCE(fecha_actualizacion_final,'') AS fecha_actualizacion_final,
                       COALESCE(observaciones,'') AS observaciones
                FROM inscriptos_comision_materia
                WHERE comision_id=? AND materia_id=? LIMIT 1
            """, conn, params=[cid, int(mid)])
            if df.empty:
                return {"comision_id": cid, "materia_id": int(mid), "cantidad": 0, "cantidad_final": None,
                        "fecha_actualizacion": "", "fecha_actualizacion_final": "", "observaciones": ""}
            return df.iloc[0].to_dict()

        df = pd.read_sql("""
            SELECT COUNT(*) AS registros,
                   COALESCE(SUM(cantidad),0) AS cantidad,
                   CASE WHEN COUNT(*) > 0 AND COUNT(cantidad_final)=COUNT(*) THEN SUM(cantidad_final) ELSE NULL END AS cantidad_final,
                   MAX(COALESCE(fecha_actualizacion,'')) AS fecha_actualizacion,
                   MAX(COALESCE(fecha_actualizacion_final,'')) AS fecha_actualizacion_final
            FROM inscriptos_comision_materia WHERE comision_id=?
        """, conn, params=[cid])
        registros_nuevos = int(df.iloc[0].get("registros", 0) or 0) if not df.empty else 0
        # Solo usar el total legacy si todavía NO existe ninguna fila discriminada.
        # Un total nuevo legítimamente igual a cero no debe resucitar un valor viejo.
        if registros_nuevos == 0:
            legacy = pd.read_sql("""
                SELECT COALESCE(cantidad,0) AS cantidad, cantidad_final,
                       COALESCE(fecha_actualizacion,'') AS fecha_actualizacion,
                       COALESCE(fecha_actualizacion_final,'') AS fecha_actualizacion_final,
                       COALESCE(observaciones,'') AS observaciones
                FROM inscriptos_comision WHERE comision_id=? LIMIT 1
            """, conn, params=[cid])
            if not legacy.empty:
                r = legacy.iloc[0].to_dict(); r["comision_id"] = cid; return r
        r = df.iloc[0].to_dict() if not df.empty else {}
        r.pop("registros", None)
        r.update({"comision_id": cid, "observaciones": ""})
        return r
    finally:
        conn.close()


# --- entry l. 13806-13903
def get_inscriptos_comisiones_periodo(periodo_id):
    """Una fila por código de cada comisión, más los totales de la comisión."""
    asegurar_esquema_inscriptos_comision()
    try:
        migrar_inscriptos_legacy_por_materia_v123()
    except Exception:
        pass
    df_com = get_comisiones_integradas_periodo(periodo_id)
    if df_com is None or df_com.empty:
        return pd.DataFrame(columns=["comision_id", "materia_id_inscriptos", "codigo_materia", "asignatura", "cantidad", "total_comision"])

    conn = get_conn()
    try:
        df_ins = pd.read_sql("""
            SELECT icm.comision_id, icm.materia_id, COALESCE(icm.cantidad,0) AS cantidad,
                   icm.cantidad_final,
                   COALESCE(icm.fecha_actualizacion,'') AS fecha_actualizacion,
                   COALESCE(icm.fecha_actualizacion_final,'') AS fecha_actualizacion_final,
                   COALESCE(icm.observaciones,'') AS observaciones_inscriptos
            FROM inscriptos_comision_materia icm
            JOIN comisiones co ON co.id=icm.comision_id
            WHERE co.periodo_id=?
        """, conn, params=[int(periodo_id)])
        df_legacy = pd.read_sql("""
            SELECT ic.comision_id, COALESCE(ic.cantidad,0) AS legacy_cantidad,
                   ic.cantidad_final AS legacy_cantidad_final
            FROM inscriptos_comision ic
            JOIN comisiones co ON co.id=ic.comision_id
            WHERE co.periodo_id=?
        """, conn, params=[int(periodo_id)])
    finally:
        conn.close()

    ins_map = {}
    if not df_ins.empty:
        for _, r in df_ins.iterrows():
            try:
                clave=(int(r.get("comision_id")), _materia_representante_inscriptos_v123(r.get("materia_id")))
                ins_map[clave]=r.to_dict()
            except Exception:
                pass
    legacy_map = {}
    if not df_legacy.empty:
        for _, r in df_legacy.iterrows():
            try: legacy_map[int(r.get("comision_id"))]=r.to_dict()
            except Exception: pass

    registros=[]
    for _, com in df_com.iterrows():
        try: cid=int(com.get("id"))
        except Exception: continue
        mats=get_materias_inscriptos_comision_v123(cid)
        if mats.empty:
            continue
        es_multi=len(mats)>1
        legacy=legacy_map.get(cid,{})
        for _, mat in mats.iterrows():
            mid=int(mat.get("materia_id_inscriptos"))
            ins=ins_map.get((cid,mid),{})
            reg={
                "comision_id":cid,
                "materia_id_inscriptos":mid,
                "periodo":com.get("periodo",""),
                "codigo_materia":mat.get("codigo_materia",""),
                "asignatura":mat.get("asignatura",""),
                "materia_especifica":com.get("materia_especifica","") if len(mats)==1 else "",
                "carrera":mat.get("carrera",""),
                "escuela":mat.get("escuela",""),
                "plan_version":mat.get("plan_version",""),
                "nombre_comision":com.get("nombre_comision",""),
                "turno":com.get("turno",""), "sede":com.get("sede",""), "modalidad":com.get("modalidad",""),
                "horarios":com.get("horarios",""),
                "cantidad":int(ins.get("cantidad",0) or 0),
                "cantidad_final":ins.get("cantidad_final",pd.NA),
                "fecha_actualizacion":ins.get("fecha_actualizacion","") or "",
                "fecha_actualizacion_final":ins.get("fecha_actualizacion_final","") or "",
                "observaciones_inscriptos":ins.get("observaciones_inscriptos","") or "",
                "legacy_total_sin_discriminar":int(legacy.get("legacy_cantidad",0) or 0) if es_multi else 0,
            }
            registros.append(reg)
    base=pd.DataFrame(registros)
    if base.empty:
        return base
    base["cantidad"]=pd.to_numeric(base["cantidad"],errors="coerce").fillna(0).astype(int)
    base["cantidad_final"]=pd.to_numeric(base["cantidad_final"],errors="coerce")
    base["total_comision"]=base.groupby("comision_id")["cantidad"].transform("sum").astype(int)
    total_final={}
    for cid,g in base.groupby("comision_id",sort=False):
        vals=pd.to_numeric(g["cantidad_final"],errors="coerce")
        total_final[cid]=vals.sum() if len(vals)>0 and vals.notna().all() else pd.NA
    base["total_final_comision"]=base["comision_id"].map(total_final)
    columnas=[
        "comision_id","materia_id_inscriptos","periodo","codigo_materia","asignatura","materia_especifica",
        "carrera","escuela","plan_version","nombre_comision","turno","sede","modalidad","horarios",
        "cantidad","cantidad_final","total_comision","total_final_comision","fecha_actualizacion",
        "fecha_actualizacion_final","observaciones_inscriptos","legacy_total_sin_discriminar"
    ]
    return base[[c for c in columnas if c in base.columns]].sort_values(["nombre_comision","codigo_materia","asignatura"],kind="stable").reset_index(drop=True)


# --- entry l. 14323-14326
def get_plan_estudio_todas():
    'Devuelve todas las materias de la universidad activa con datos de carrera/plan.'
    from analisis.motor.ref.extracted_batch03.readonly_queries import get_plan_estudio_todas as _b03_core_get_plan_estudio_todas
    return _b03_core_get_plan_estudio_todas(get_planes_conn=get_planes_conn, pd=pd)


# --- entry l. 16533-16535
def limpiar_texto_tabla(valor):
    from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla as _b04_core_limpiar_texto_tabla
    return _b04_core_limpiar_texto_tabla(valor)


# --- entry l. 16538-16540
def limpiar_cuil(valor):
    from analisis.motor.ref.extracted_batch04.identidad import limpiar_cuil as _b04_core_limpiar_cuil
    return _b04_core_limpiar_cuil(valor)


# --- entry l. 18104-18119
def _institucion_id_operativa():
    """Institución actual para datos compartidos entre todos sus departamentos."""
    if USE_POSTGRESQL:
        return _pg_current_inst_id()
    user = current_user() or {}
    if user.get("institucion_id"):
        return int(user.get("institucion_id"))
    if st.session_state.get("superadmin_institucion_id"):
        return int(st.session_state.get("superadmin_institucion_id"))
    try:
        df = get_instituciones_auth(solo_activas=False)
        if not df.empty:
            return int(df.iloc[0]["id"])
    except Exception:
        pass
    return None


# --- entry l. 18424-18462
def get_materias_para_comisiones():
    """Materias disponibles para abrir comisiones.

    Desde la lógica de fuente única, las materias se leen desde
    `datos_instituciones/<universidad>/_planes_estudio.db` y no desde la copia
    departamental. Esto evita que, después de cambiar códigos en Materias, la
    carga de comisiones valide contra una base vieja.
    """
    try:
        df = get_plan_estudio_todas()
    except Exception:
        df = pd.DataFrame()

    columnas = [
        "materia_id", "codigo", "asignatura", "anio", "cuatrimestre",
        "carga_semanal", "carga_total", "estado_materia", "carrera", "escuela", "plan_version", "en_plan"
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=columnas)

    df = df.copy()
    if "id" in df.columns and "materia_id" not in df.columns:
        df = df.rename(columns={"id": "materia_id"})
    if "estado" in df.columns and "estado_materia" not in df.columns:
        df = df.rename(columns={"estado": "estado_materia"})

    for col in columnas:
        if col not in df.columns:
            df[col] = ""

    df = df[columnas].copy()
    df["estado_materia"] = df["estado_materia"].replace("", "Activa")
    df = df[df["estado_materia"].fillna("Activa").astype(str).str.strip().replace("", "Activa") == "Activa"].copy()
    df["en_plan"] = pd.to_numeric(df["en_plan"], errors="coerce").fillna(1).astype(int)

    for col in ["codigo", "asignatura", "anio", "cuatrimestre", "estado_materia", "carrera", "escuela", "plan_version"]:
        df[col] = df[col].apply(limpiar_texto_tabla)

    return df.sort_values(["escuela", "carrera", "plan_version", "codigo", "asignatura"], kind="stable").reset_index(drop=True)


# --- entry l. 18464-18476
def get_materia_comision(materia_id):
    """Devuelve una materia para comisiones desde la fuente única de planes."""
    df = get_materias_para_comisiones()
    if df.empty:
        return None
    try:
        mid = int(materia_id)
    except Exception:
        return None
    df = df[df["materia_id"].astype(str) == str(mid)].copy()
    if df.empty:
        return None
    return df.iloc[0].to_dict()


# --- entry l. 18871-18932
def get_comisiones(periodo_id=None, solo_activas=False):
    """Listado de comisiones enriquecido con materias desde la fuente única.

    La tabla comisiones vive en la base departamental, pero materia/carrera/plan
    se leen desde `_planes_estudio.db`. Así, si cambiás un código o una materia
    en el módulo Materias, Comisiones lo ve sin depender de una copia vieja.
    """
    conn = get_conn()
    filtros = []
    params = []
    if periodo_id is not None:
        filtros.append("co.periodo_id = ?")
        params.append(periodo_id)
    if solo_activas:
        filtros.append("COALESCE(co.estado, 'Activa') = 'Activa'")
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    df = pd.read_sql(f"""
        SELECT
            co.id,
            co.periodo_id,
            p.nombre AS periodo,
            p.anio AS _periodo_anio,
            p.semestre AS _periodo_semestre,
            co.materia_id,
            co.nombre_comision,
            co.turno,
            co.sede,
            co.modalidad,
            co.estado,
            co.observaciones,
            co.fecha_creacion,
            COALESCE((SELECT SUM(h.horas) FROM horarios_comision h WHERE h.comision_id = co.id), 0) AS horas_horario,
            COALESCE((SELECT COUNT(*) FROM horarios_comision h WHERE h.comision_id = co.id), 0) AS cantidad_horarios,
            COALESCE((SELECT COUNT(*) FROM asignaciones_docentes_comision a WHERE a.comision_id = co.id AND COALESCE(a.estado, 'Activa') = 'Activa'), 0) AS docentes_asignados
        FROM comisiones co
        LEFT JOIN periodos p ON p.id = co.periodo_id
        {where}
    """, conn, params=params)
    conn.close()

    columnas = [
        "id", "periodo_id", "periodo", "materia_id", "codigo_materia", "asignatura", "carrera", "escuela", "plan_version",
        "nombre_comision", "turno", "sede", "modalidad", "estado", "observaciones", "fecha_creacion",
        "horas_horario", "cantidad_horarios", "docentes_asignados"
    ]
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

    df = df.sort_values(["_periodo_anio", "_periodo_semestre", "escuela", "carrera", "asignatura", "nombre_comision"], ascending=[False, False, True, True, True, True], kind="stable")
    return df[columnas].reset_index(drop=True)


# --- entry l. 19073-19097
def get_horarios_comision(comision_id=None):
    """Horarios enriquecidos con materia concreta y carreras snapshot de la comisión."""
    conn = get_conn(); filtro=""; params=[]
    if comision_id is not None:
        filtro="WHERE h.comision_id = ?"; params=[comision_id]
    df=pd.read_sql(f"""
        SELECT h.id, h.comision_id, h.dia, h.hora_inicio, h.hora_fin, h.horas, h.observaciones
        FROM horarios_comision h
        {filtro}
        ORDER BY CASE h.dia WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3
                 WHEN 'Jueves' THEN 4 WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6 WHEN 'Domingo' THEN 7 ELSE 99 END,
                 h.hora_inicio
    """,conn,params=params); conn.close()
    extras=["periodo","codigo_materia","asignatura","materia_especifica","carrera","escuela","plan_version","nombre_comision","turno","modalidad"]
    if df.empty:
        for c in extras: df[c]=""
        return df
    try:
        dfc=get_comisiones(periodo_id=None,solo_activas=False)
        meta=dfc[[c for c in ["id"]+extras if c in dfc.columns]].rename(columns={"id":"comision_id"})
        df=df.merge(meta,on="comision_id",how="left")
    except Exception:
        for c in extras:
            if c not in df.columns: df[c]=""
    return df


# --- entry l. 19204-19256
def get_modificaciones_asignaciones_periodo(periodo_id=None):
    """Resumen por comisión de altas/bajas registradas desde Modificación de asignaciones."""
    conn = get_conn()
    filtros = ["(m.detalle LIKE ? OR m.observaciones LIKE ?)"]
    params = ["%Comisión ID%", "%Comisión ID%"]
    if periodo_id is not None:
        filtros.append("m.periodo_id = ?")
        params.append(int(periodo_id))
    where = "WHERE " + " AND ".join(filtros)
    df = pd.read_sql(f"""
        SELECT m.id, m.fecha, m.tipo_movimiento, m.cuil, m.nombre, m.detalle, m.observaciones
        FROM movimientos m
        {where}
        ORDER BY m.fecha, m.id
    """, conn, params=params)
    conn.close()
    cols = ["comision_id", "modificaciones_asignaciones_periodo"]
    if df.empty:
        return pd.DataFrame(columns=cols)

    def _extraer_comision_id(row):
        texto = f"{row.get('detalle', '')} {row.get('observaciones', '')}"
        m = re.search(r"Comisión\s+ID\s+(\d+)", str(texto), flags=re.I)
        return int(m.group(1)) if m else None

    df["comision_id"] = df.apply(_extraer_comision_id, axis=1)
    df = df[pd.notna(df["comision_id"])].copy()
    if df.empty:
        return pd.DataFrame(columns=cols)
    df["comision_id"] = df["comision_id"].astype(int)

    def _resumir(grupo):
        partes = []
        for _, r in grupo.iterrows():
            tipo = limpiar_texto_tabla(r.get("tipo_movimiento", ""))
            if "baja" in tipo.lower():
                etiqueta = "Baja"
            elif "alta" in tipo.lower():
                etiqueta = "Alta"
            else:
                etiqueta = "Cambio"
            fecha = limpiar_texto_tabla(r.get("fecha", ""))
            docente = limpiar_texto_tabla(r.get("nombre", "")) or limpiar_texto_tabla(r.get("cuil", ""))
            partes.append(f"{etiqueta}: {docente}" + (f" ({fecha})" if fecha else ""))
        # Evita repetir la misma frase si una edición duplicó movimientos iguales.
        unicos = []
        for ptxt in partes:
            if ptxt not in unicos:
                unicos.append(ptxt)
        return " | ".join(unicos)

    res = df.groupby("comision_id", dropna=False).apply(_resumir).reset_index(name="modificaciones_asignaciones_periodo")
    return res[cols]


# --- entry l. 19268-19299
def get_asignaciones_comision(comision_id=None):
    """Asignaciones docentes enriquecidas con la metadata real/snapshot de la comisión."""
    conn = get_conn()
    filtro = ""; params=[]
    if comision_id is not None:
        filtro = "WHERE a.comision_id = ?"; params=[comision_id]
    df = pd.read_sql(f"""
        SELECT a.id, a.comision_id, a.cuil,
               CASE
                   WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                   WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE a.cuil END AS docente,
               a.rol, a.horas_asignadas, a.estado,
               COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente, a.observaciones
        FROM asignaciones_docentes_comision a
        LEFT JOIN docentes doc ON doc.cuil = a.cuil
        {filtro}
        ORDER BY docente, a.rol
    """, conn, params=params)
    conn.close()
    extras=["periodo","codigo_materia","asignatura","materia_especifica","carrera","escuela","plan_version","nombre_comision"]
    if df.empty:
        for c in extras: df[c]=""
        return df
    try:
        dfc=get_comisiones(periodo_id=None, solo_activas=False)
        cols=[c for c in ["id"]+extras if c in dfc.columns]
        meta=dfc[cols].rename(columns={"id":"comision_id"})
        df=df.merge(meta,on="comision_id",how="left")
    except Exception:
        for c in extras:
            if c not in df.columns: df[c]=""
    return df


# --- entry l. 20851-20890
def get_asignaciones_comisiones_periodo(periodo_id=None):
    conn = get_conn()
    filtros = []
    params = []
    if periodo_id is not None:
        filtros.append("co.periodo_id = ?")
        params.append(periodo_id)
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    df = pd.read_sql(f"""
        SELECT
            p.nombre AS periodo,
            m.codigo AS codigo_materia,
            m.asignatura,
            c.nombre AS carrera,
            c.escuela,
            co.nombre_comision,
            co.turno,
            co.modalidad,
            a.cuil,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE a.cuil
            END AS docente,
            a.rol,
            a.horas_asignadas,
            COALESCE(a.estado, 'Activa') AS estado,
            COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente,
            a.observaciones
        FROM asignaciones_docentes_comision a
        LEFT JOIN comisiones co ON co.id = a.comision_id
        LEFT JOIN periodos p ON p.id = co.periodo_id
        LEFT JOIN materias m ON m.id = co.materia_id
        LEFT JOIN carreras c ON c.id = m.carrera_id
        LEFT JOIN docentes doc ON doc.cuil = a.cuil
        {where}
        ORDER BY c.escuela, c.nombre, m.codigo, m.asignatura, co.nombre_comision, docente, a.rol
    """, conn, params=params)
    conn.close()
    return df


# --- entry l. 20912-20971
def get_productividad_docente(cuil, periodo_id):
    conn = get_conn()
    df = pd.read_sql("""
        SELECT
            COALESCE((
                SELECT SUM(horas)
                FROM designaciones
                WHERE cuil = ?
                  AND periodo_id = ?
                  AND estado = 'Activa'
            ), 0) AS horas_contratadas,
            COALESCE((
                SELECT SUM(horas_asignadas)
                FROM asignaciones_docentes_comision a
                JOIN comisiones co ON co.id = a.comision_id
                WHERE a.cuil = ?
                  AND co.periodo_id = ?
                  AND COALESCE(a.estado, 'Activa') = 'Activa'
            ), 0) AS horas_en_comisiones_brutas,
            COALESCE((
                SELECT SUM(horas_asignadas)
                FROM investigacion_docente i
                WHERE i.cuil = ?
                  AND i.periodo_id = ?
                  AND COALESCE(i.estado_asignacion, 'Activa') = 'Activa'
            ), 0) AS horas_en_investigacion
    """, conn, params=[cuil, periodo_id, cuil, periodo_id, cuil, periodo_id])
    conn.close()

    if df.empty:
        return {
            "horas_contratadas": 0.0,
            "horas_en_comisiones": 0.0,
            "horas_en_comisiones_brutas": 0.0,
            "horas_en_investigacion": 0.0,
            "horas_utilizadas": 0.0,
            "horas_disponibles": 0.0,
            "porcentaje": 0.0,
            "horas_no_contadas_por_superposicion": 0.0
        }

    contratadas = float(df.iloc[0]["horas_contratadas"] or 0)
    comisiones_brutas = float(df.iloc[0]["horas_en_comisiones_brutas"] or 0)
    comisiones_unicas = calcular_horas_comisiones_unicas_docente(cuil, periodo_id)
    investigacion = float(df.iloc[0]["horas_en_investigacion"] or 0)

    utilizadas = comisiones_unicas + investigacion
    disponibles = contratadas - utilizadas
    porcentaje = round((utilizadas / contratadas * 100), 2) if contratadas > 0 else 0.0

    return {
        "horas_contratadas": contratadas,
        "horas_en_comisiones": comisiones_unicas,
        "horas_en_comisiones_brutas": comisiones_brutas,
        "horas_en_investigacion": investigacion,
        "horas_utilizadas": utilizadas,
        "horas_disponibles": disponibles,
        "porcentaje": porcentaje,
        "horas_no_contadas_por_superposicion": max(round(comisiones_brutas - comisiones_unicas, 2), 0)
    }


# --- entry l. 21026-21028
def _nombre_materia_visible_v138(codigo, asignatura, materia_especifica=""):
    from analisis.motor.ref.domain.materias import _nombre_materia_visible_v138 as _b05_core__nombre_materia_visible_v138
    return _b05_core__nombre_materia_visible_v138(codigo, asignatura, materia_especifica)


# --- entry l. 21190-21212
def _puede_administrar_proyecto_investigacion(proyecto):
    """Indica si el usuario actual puede editar, archivar o borrar el proyecto.

    Todos los departamentos pueden verlo y asignar docentes. La administración
    del registro institucional queda en el departamento creador, salvo para
    coordinación institucional y superadmin.
    """
    if not USE_POSTGRESQL:
        return True
    try:
        if current_role() in ["superadmin", "coordinador_institucional"]:
            return True
    except Exception:
        pass
    if not isinstance(proyecto, dict):
        proyecto = _proyecto_investigacion_por_id(proyecto)
    creador = proyecto.get("departamento_creador_id", proyecto.get("departamento_id"))
    if creador is None or (isinstance(creador, float) and pd.isna(creador)):
        return True
    try:
        return int(creador) == int(_pg_current_dep_id())
    except Exception:
        return False


# --- entry l. 21215-21261
def _proyecto_investigacion_por_id(proyecto_id):
    if proyecto_id is None:
        return {}
    asegurar_esquema_investigacion_separado()
    conn = get_conn()
    if USE_POSTGRESQL:
        df = pd.read_sql("""
            SELECT pr.id, pr.nombre_proyecto,
                COALESCE(pr.codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(pr.instituto_proyecto, '') AS instituto_proyecto,
                pr.anio_llamado, pr.fecha_inicio, pr.fecha_fin,
                COALESCE(pr.periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(pr.observaciones, '') AS observaciones,
                COALESCE(pr.estado, 'Activo') AS estado, pr.fecha_carga,
                pr.fecha_suspension,
                COALESCE(pr.motivo_suspension, '') AS motivo_suspension,
                pr.departamento_id AS departamento_creador_id,
                COALESCE(dep.nombre, '') AS departamento_creador
            FROM proyectos_investigacion pr
            LEFT JOIN departamentos dep ON dep.id = pr.departamento_id
            WHERE pr.id = ?
            LIMIT 1
        """, conn, params=[proyecto_id])
    else:
        df = pd.read_sql("""
            SELECT id, nombre_proyecto,
                COALESCE(codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(instituto_proyecto, '') AS instituto_proyecto,
                anio_llamado, fecha_inicio, fecha_fin,
                COALESCE(periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(observaciones, '') AS observaciones,
                COALESCE(estado, 'Activo') AS estado, fecha_carga,
                fecha_suspension,
                COALESCE(motivo_suspension, '') AS motivo_suspension,
                NULL AS departamento_creador_id,
                '' AS departamento_creador
            FROM proyectos_investigacion
            WHERE id = ?
            LIMIT 1
        """, conn, params=[proyecto_id])
    conn.close()
    if df.empty:
        return {}
    fila = df.iloc[0].to_dict()
    fila["situacion"] = _situacion_proyecto(fila)
    fila["puede_administrar"] = _puede_administrar_proyecto_investigacion(fila)
    return fila


# --- entry l. 21265-21276
def _cache_scope_proyectos_v127(tipo):
    try:
        inst_id = _pg_current_inst_id() if USE_POSTGRESQL else 0
    except Exception:
        inst_id = 0
    try:
        dep_id = _pg_current_dep_id() if USE_POSTGRESQL else 0
    except Exception:
        dep_id = 0
    clave = "_proyectos_cache_version_inv_v127" if str(tipo).lower().startswith("inv") else "_proyectos_cache_version_ext_v127"
    version = int(st.session_state.get(clave, 0) or 0)
    return str(DATABASE_URL), int(inst_id or 0), int(dep_id or 0), version


# --- entry l. 21303-21407
def get_proyectos_investigacion(solo_activos=False, periodo_id=None):
    """Catálogo institucional visible desde todos los departamentos.

    Las métricas de docentes y asignaciones consolidan toda la institución. El
    período usado para filtrar vigencia sigue siendo el período del departamento
    desde el que se está trabajando.
    """
    asegurar_esquema_investigacion_separado()
    filtros = []
    params = []
    if solo_activos:
        filtros.append("COALESCE(pr.estado, 'Activo') = 'Activo'")
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    conn = get_conn()
    if USE_POSTGRESQL:
        df = pd.read_sql(f"""
            SELECT pr.id, pr.nombre_proyecto,
                COALESCE(pr.codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(pr.instituto_proyecto, '') AS instituto_proyecto,
                pr.anio_llamado, pr.fecha_inicio, pr.fecha_fin,
                COALESCE(pr.periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(pr.observaciones, '') AS observaciones,
                COALESCE(pr.estado, 'Activo') AS estado, pr.fecha_carga,
                pr.fecha_suspension,
                COALESCE(pr.motivo_suspension, '') AS motivo_suspension,
                pr.departamento_id AS departamento_creador_id,
                COALESCE(dep.nombre, '') AS departamento_creador,
                COALESCE((SELECT COUNT(*) FROM investigacion_docente i
                          WHERE i.proyecto_id = pr.id
                            AND COALESCE(i.estado_asignacion, 'Activa') = 'Activa'), 0) AS cantidad_asignaciones,
                COALESCE((SELECT COUNT(*) FROM investigacion_docente i
                          WHERE i.proyecto_id = pr.id
                            AND LOWER(TRIM(COALESCE(i.estado_asignacion, 'Activa'))) <> 'baja'), 0) AS cantidad_asignaciones_historicas,
                COALESCE((SELECT COUNT(*) FROM investigacion_docente i
                          WHERE i.proyecto_id = pr.id), 0) AS cantidad_asignaciones_registradas,
                COALESCE((SELECT COUNT(DISTINCT i.cuil) FROM investigacion_docente i
                          WHERE i.proyecto_id = pr.id
                            AND COALESCE(i.estado_asignacion, 'Activa') = 'Activa'), 0) AS cantidad_docentes,
                COALESCE((SELECT COUNT(DISTINCT i.cuil) FROM investigacion_docente i
                          WHERE i.proyecto_id = pr.id), 0) AS cantidad_docentes_historicos,
                COALESCE((SELECT COUNT(DISTINCT i.departamento_id) FROM investigacion_docente i
                          WHERE i.proyecto_id = pr.id), 0) AS cantidad_departamentos,
                COALESCE((SELECT SUM(i.horas_asignadas) FROM investigacion_docente i
                          WHERE i.proyecto_id = pr.id
                            AND LOWER(TRIM(COALESCE(i.estado_asignacion, 'Activa'))) <> 'baja'), 0) AS horas_asignadas_historicas
            FROM proyectos_investigacion pr
            LEFT JOIN departamentos dep ON dep.id = pr.departamento_id
            {where}
            ORDER BY COALESCE(pr.fecha_fin, '9999-12-31') DESC, pr.nombre_proyecto
        """, conn, params=params)
    else:
        df = pd.read_sql(f"""
            SELECT pr.id, pr.nombre_proyecto,
                COALESCE(pr.codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(pr.instituto_proyecto, '') AS instituto_proyecto,
                pr.anio_llamado, pr.fecha_inicio, pr.fecha_fin,
                COALESCE(pr.periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(pr.observaciones, '') AS observaciones,
                COALESCE(pr.estado, 'Activo') AS estado, pr.fecha_carga,
                pr.fecha_suspension,
                COALESCE(pr.motivo_suspension, '') AS motivo_suspension,
                NULL AS departamento_creador_id,
                '' AS departamento_creador,
                COALESCE((SELECT COUNT(*) FROM investigacion_docente i
                          WHERE i.proyecto_id = pr.id
                            AND COALESCE(i.estado_asignacion, 'Activa') = 'Activa'), 0) AS cantidad_asignaciones,
                COALESCE((SELECT COUNT(*) FROM investigacion_docente i
                          WHERE i.proyecto_id = pr.id
                            AND LOWER(TRIM(COALESCE(i.estado_asignacion, 'Activa'))) <> 'baja'), 0) AS cantidad_asignaciones_historicas,
                COALESCE((SELECT COUNT(*) FROM investigacion_docente i
                          WHERE i.proyecto_id = pr.id), 0) AS cantidad_asignaciones_registradas,
                COALESCE((SELECT COUNT(DISTINCT i.cuil) FROM investigacion_docente i
                          WHERE i.proyecto_id = pr.id
                            AND COALESCE(i.estado_asignacion, 'Activa') = 'Activa'), 0) AS cantidad_docentes,
                COALESCE((SELECT COUNT(DISTINCT i.cuil) FROM investigacion_docente i
                          WHERE i.proyecto_id = pr.id), 0) AS cantidad_docentes_historicos,
                1 AS cantidad_departamentos,
                COALESCE((SELECT SUM(i.horas_asignadas) FROM investigacion_docente i
                          WHERE i.proyecto_id = pr.id
                            AND LOWER(TRIM(COALESCE(i.estado_asignacion, 'Activa'))) <> 'baja'), 0) AS horas_asignadas_historicas
            FROM proyectos_investigacion pr
            {where}
            ORDER BY COALESCE(pr.fecha_fin, '9999-12-31') DESC, pr.nombre_proyecto
        """, conn, params=params)

    periodo = None
    if periodo_id is not None:
        dfp = pd.read_sql("""
            SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin
            FROM periodos
            WHERE id=?
            LIMIT 1
        """, conn, params=[periodo_id])
        if not dfp.empty:
            periodo = dfp.iloc[0].to_dict()
    conn.close()
    if df.empty:
        return df
    df["situacion"] = df.apply(lambda r: _situacion_proyecto(r.to_dict()), axis=1)
    df["puede_administrar"] = df.apply(
        lambda r: _puede_administrar_proyecto_investigacion(r.to_dict()), axis=1
    )
    if periodo is not None:
        df = df[df.apply(lambda r: proyecto_vigente_en_periodo(r.to_dict(), periodo), axis=1)].copy()
    return df.reset_index(drop=True)


# --- entry l. 21410
_get_proyectos_investigacion_no_cache_v127 = get_proyectos_investigacion


# --- entry l. 21413-21416
def _get_proyectos_investigacion_cache_v127(solo_activos, periodo_id, db_url, inst_id, dep_id, version):
    return _get_proyectos_investigacion_no_cache_v127(
        solo_activos=bool(solo_activos), periodo_id=periodo_id
    )


# --- entry l. 21419-21424
def get_proyectos_investigacion(solo_activos=False, periodo_id=None):
    db_url, inst_id, dep_id, version = _cache_scope_proyectos_v127("investigacion")
    df = _get_proyectos_investigacion_cache_v127(
        bool(solo_activos), periodo_id, db_url, inst_id, dep_id, version
    )
    return df.copy()


# --- entry l. 22041-22190
def get_investigacion_docente(cuil=None, periodo_id=None, incluir_bajas=False,
                              todos_departamentos=False):
    """Devuelve asignaciones de investigación.

    Por defecto respeta el departamento actual. Con ``todos_departamentos=True``
    y PostgreSQL consolida las asignaciones del mismo CUIL en todos los
    departamentos de la institución y compara períodos equivalentes por
    año/semestre o nombre.
    """
    asegurar_esquema_investigacion_separado()

    if USE_POSTGRESQL and todos_departamentos:
        inst_id = int(_pg_current_inst_id())
        filtros = ["i.institucion_id = %s"]
        params_filtros = [inst_id]
        if cuil is not None:
            filtros.append("regexp_replace(COALESCE(i.cuil, ''), '[^0-9]', '', 'g') = %s")
            params_filtros.append(_clave_cuil(cuil))
        if not incluir_bajas:
            filtros.append("COALESCE(i.estado_asignacion, 'Activa') = 'Activa'")
        where = "WHERE " + " AND ".join(filtros)

        if periodo_id is not None:
            cte = """
                WITH periodo_ref AS (
                    SELECT id, institucion_id, nombre, anio, semestre
                    FROM periodos
                    WHERE id = %s
                    LIMIT 1
                )
            """
            join_ref = f"""
                JOIN periodo_ref pref
                  ON {_condicion_periodo_equivalente_sql('p', 'pref')}
            """
            params = [int(periodo_id)] + params_filtros
        else:
            cte = ""
            join_ref = ""
            params = params_filtros

        return _pg_read_dataframe(f"""
            {cte}
            SELECT i.id, i.proyecto_id, i.periodo_id, p.nombre AS periodo,
                p.anio AS periodo_anio, p.semestre AS periodo_semestre, i.cuil,
                COALESCE(doc.docente, i.cuil) AS docente,
                COALESCE(NULLIF(pr.nombre_proyecto, ''), i.nombre_proyecto, '') AS nombre_proyecto,
                COALESCE(NULLIF(pr.codigo_proyecto, ''), i.codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(NULLIF(pr.instituto_proyecto, ''), i.instituto_proyecto, '') AS instituto_proyecto,
                i.rol, COALESCE(pr.anio_llamado, i.anio_llamado) AS anio_llamado,
                pr.fecha_inicio, pr.fecha_fin,
                COALESCE(NULLIF(pr.periodo_ejecucion, ''), i.periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(pr.estado, 'Activo') AS estado_proyecto,
                COALESCE(i.estado_asignacion, 'Activa') AS estado_asignacion,
                i.horas_asignadas, i.observaciones, i.fecha_carga, i.fecha_baja,
                COALESCE(i.motivo_baja, '') AS motivo_baja,
                i.departamento_id AS departamento_asignacion_id,
                COALESCE(dep.nombre, '') AS departamento_asignacion
            FROM investigacion_docente i
            JOIN periodos p ON p.id = i.periodo_id
            {join_ref}
            LEFT JOIN proyectos_investigacion pr ON pr.id = i.proyecto_id
            LEFT JOIN departamentos dep ON dep.id = i.departamento_id
            LEFT JOIN LATERAL (
                SELECT
                    CASE
                        WHEN d.apellido IS NOT NULL AND d.nombres IS NOT NULL
                            THEN d.apellido || ', ' || d.nombres
                        WHEN d.nombre IS NOT NULL THEN d.nombre
                        ELSE i.cuil
                    END AS docente
                FROM docentes d
                WHERE d.institucion_id = i.institucion_id
                  AND regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g') = regexp_replace(COALESCE(i.cuil,''), '[^0-9]', '', 'g')
                ORDER BY
                    CASE WHEN d.departamento_id IS NOT DISTINCT FROM i.departamento_id THEN 0 ELSE 1 END,
                    d.id
                LIMIT 1
            ) doc ON TRUE
            {where}
            ORDER BY COALESCE(p.anio,0) DESC, COALESCE(p.semestre,0) DESC,
                     departamento_asignacion, docente, nombre_proyecto
        """, params)

    filtros = []
    params = []
    if cuil is not None:
        filtros.append("i.cuil = ?")
        params.append(cuil)
    if periodo_id is not None:
        filtros.append("i.periodo_id = ?")
        params.append(periodo_id)
    if not incluir_bajas:
        filtros.append("COALESCE(i.estado_asignacion, 'Activa') = 'Activa'")
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    conn = get_conn()

    if USE_POSTGRESQL:
        df = pd.read_sql(f"""
            SELECT i.id, i.proyecto_id, i.periodo_id, p.nombre AS periodo,
                p.anio AS periodo_anio, p.semestre AS periodo_semestre, i.cuil,
                CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                     WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE i.cuil END AS docente,
                COALESCE(NULLIF(pr.nombre_proyecto, ''), i.nombre_proyecto, '') AS nombre_proyecto,
                COALESCE(NULLIF(pr.codigo_proyecto, ''), i.codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(NULLIF(pr.instituto_proyecto, ''), i.instituto_proyecto, '') AS instituto_proyecto,
                i.rol, COALESCE(pr.anio_llamado, i.anio_llamado) AS anio_llamado,
                pr.fecha_inicio, pr.fecha_fin,
                COALESCE(NULLIF(pr.periodo_ejecucion, ''), i.periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(pr.estado, 'Activo') AS estado_proyecto,
                COALESCE(i.estado_asignacion, 'Activa') AS estado_asignacion,
                i.horas_asignadas, i.observaciones, i.fecha_carga, i.fecha_baja,
                COALESCE(i.motivo_baja, '') AS motivo_baja,
                i.departamento_id AS departamento_asignacion_id,
                COALESCE(dep.nombre, '') AS departamento_asignacion
            FROM investigacion_docente i
            LEFT JOIN periodos p ON p.id = i.periodo_id
            LEFT JOIN docentes doc ON doc.cuil = i.cuil
            LEFT JOIN proyectos_investigacion pr ON pr.id = i.proyecto_id
            LEFT JOIN departamentos dep ON dep.id = i.departamento_id
            {where}
            ORDER BY COALESCE(p.anio,0) DESC, COALESCE(p.semestre,0) DESC, docente, nombre_proyecto
        """, conn, params=params)
    else:
        df = pd.read_sql(f"""
            SELECT i.id, i.proyecto_id, i.periodo_id, p.nombre AS periodo,
                p.anio AS periodo_anio, p.semestre AS periodo_semestre, i.cuil,
                CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                     WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE i.cuil END AS docente,
                COALESCE(NULLIF(pr.nombre_proyecto, ''), i.nombre_proyecto, '') AS nombre_proyecto,
                COALESCE(NULLIF(pr.codigo_proyecto, ''), i.codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(NULLIF(pr.instituto_proyecto, ''), i.instituto_proyecto, '') AS instituto_proyecto,
                i.rol, COALESCE(pr.anio_llamado, i.anio_llamado) AS anio_llamado,
                pr.fecha_inicio, pr.fecha_fin,
                COALESCE(NULLIF(pr.periodo_ejecucion, ''), i.periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(pr.estado, 'Activo') AS estado_proyecto,
                COALESCE(i.estado_asignacion, 'Activa') AS estado_asignacion,
                i.horas_asignadas, i.observaciones, i.fecha_carga, i.fecha_baja,
                COALESCE(i.motivo_baja, '') AS motivo_baja,
                NULL AS departamento_asignacion_id,
                '' AS departamento_asignacion
            FROM investigacion_docente i
            LEFT JOIN periodos p ON p.id = i.periodo_id
            LEFT JOIN docentes doc ON doc.cuil = i.cuil
            LEFT JOIN proyectos_investigacion pr ON pr.id = i.proyecto_id
            {where}
            ORDER BY COALESCE(p.anio,0) DESC, COALESCE(p.semestre,0) DESC, docente, nombre_proyecto
        """, conn, params=params)
    conn.close()
    return df


# --- entry l. 22308-22330
def _puede_administrar_proyecto_extension(proyecto):
    """Indica si el usuario actual puede editar, archivar o borrar el proyecto.

    Todos los departamentos pueden verlo y asignar docentes. La administración
    del registro institucional queda en el departamento creador, salvo para
    coordinación institucional y superadmin.
    """
    if not USE_POSTGRESQL:
        return True
    try:
        if current_role() in ["superadmin", "coordinador_institucional"]:
            return True
    except Exception:
        pass
    if not isinstance(proyecto, dict):
        proyecto = _proyecto_extension_por_id(proyecto)
    creador = proyecto.get("departamento_creador_id", proyecto.get("departamento_id"))
    if creador is None or (isinstance(creador, float) and pd.isna(creador)):
        return True
    try:
        return int(creador) == int(_pg_current_dep_id())
    except Exception:
        return False


# --- entry l. 22333-22379
def _proyecto_extension_por_id(proyecto_id):
    if proyecto_id is None:
        return {}
    asegurar_esquema_extension_separado()
    conn = get_conn()
    if USE_POSTGRESQL:
        df = pd.read_sql("""
            SELECT pr.id, pr.nombre_proyecto,
                COALESCE(pr.codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(pr.instituto_proyecto, '') AS instituto_proyecto,
                pr.anio_llamado, pr.fecha_inicio, pr.fecha_fin,
                COALESCE(pr.periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(pr.observaciones, '') AS observaciones,
                COALESCE(pr.estado, 'Activo') AS estado, pr.fecha_carga,
                pr.fecha_suspension,
                COALESCE(pr.motivo_suspension, '') AS motivo_suspension,
                pr.departamento_id AS departamento_creador_id,
                COALESCE(dep.nombre, '') AS departamento_creador
            FROM proyectos_extension pr
            LEFT JOIN departamentos dep ON dep.id = pr.departamento_id
            WHERE pr.id = ?
            LIMIT 1
        """, conn, params=[proyecto_id])
    else:
        df = pd.read_sql("""
            SELECT id, nombre_proyecto,
                COALESCE(codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(instituto_proyecto, '') AS instituto_proyecto,
                anio_llamado, fecha_inicio, fecha_fin,
                COALESCE(periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(observaciones, '') AS observaciones,
                COALESCE(estado, 'Activo') AS estado, fecha_carga,
                fecha_suspension,
                COALESCE(motivo_suspension, '') AS motivo_suspension,
                NULL AS departamento_creador_id,
                '' AS departamento_creador
            FROM proyectos_extension
            WHERE id = ?
            LIMIT 1
        """, conn, params=[proyecto_id])
    conn.close()
    if df.empty:
        return {}
    fila = df.iloc[0].to_dict()
    fila["situacion"] = _situacion_proyecto(fila)
    fila["puede_administrar"] = _puede_administrar_proyecto_extension(fila)
    return fila


# --- entry l. 22382-22486
def get_proyectos_extension(solo_activos=False, periodo_id=None):
    """Catálogo institucional visible desde todos los departamentos.

    Las métricas de docentes y asignaciones consolidan toda la institución. El
    período usado para filtrar vigencia sigue siendo el período del departamento
    desde el que se está trabajando.
    """
    asegurar_esquema_extension_separado()
    filtros = []
    params = []
    if solo_activos:
        filtros.append("COALESCE(pr.estado, 'Activo') = 'Activo'")
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    conn = get_conn()
    if USE_POSTGRESQL:
        df = pd.read_sql(f"""
            SELECT pr.id, pr.nombre_proyecto,
                COALESCE(pr.codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(pr.instituto_proyecto, '') AS instituto_proyecto,
                pr.anio_llamado, pr.fecha_inicio, pr.fecha_fin,
                COALESCE(pr.periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(pr.observaciones, '') AS observaciones,
                COALESCE(pr.estado, 'Activo') AS estado, pr.fecha_carga,
                pr.fecha_suspension,
                COALESCE(pr.motivo_suspension, '') AS motivo_suspension,
                pr.departamento_id AS departamento_creador_id,
                COALESCE(dep.nombre, '') AS departamento_creador,
                COALESCE((SELECT COUNT(*) FROM extension_docente i
                          WHERE i.proyecto_id = pr.id
                            AND COALESCE(i.estado_asignacion, 'Activa') = 'Activa'), 0) AS cantidad_asignaciones,
                COALESCE((SELECT COUNT(*) FROM extension_docente i
                          WHERE i.proyecto_id = pr.id
                            AND LOWER(TRIM(COALESCE(i.estado_asignacion, 'Activa'))) <> 'baja'), 0) AS cantidad_asignaciones_historicas,
                COALESCE((SELECT COUNT(*) FROM extension_docente i
                          WHERE i.proyecto_id = pr.id), 0) AS cantidad_asignaciones_registradas,
                COALESCE((SELECT COUNT(DISTINCT i.cuil) FROM extension_docente i
                          WHERE i.proyecto_id = pr.id
                            AND COALESCE(i.estado_asignacion, 'Activa') = 'Activa'), 0) AS cantidad_docentes,
                COALESCE((SELECT COUNT(DISTINCT i.cuil) FROM extension_docente i
                          WHERE i.proyecto_id = pr.id), 0) AS cantidad_docentes_historicos,
                COALESCE((SELECT COUNT(DISTINCT i.departamento_id) FROM extension_docente i
                          WHERE i.proyecto_id = pr.id), 0) AS cantidad_departamentos,
                COALESCE((SELECT SUM(i.horas_asignadas) FROM extension_docente i
                          WHERE i.proyecto_id = pr.id
                            AND LOWER(TRIM(COALESCE(i.estado_asignacion, 'Activa'))) <> 'baja'), 0) AS horas_asignadas_historicas
            FROM proyectos_extension pr
            LEFT JOIN departamentos dep ON dep.id = pr.departamento_id
            {where}
            ORDER BY COALESCE(pr.fecha_fin, '9999-12-31') DESC, pr.nombre_proyecto
        """, conn, params=params)
    else:
        df = pd.read_sql(f"""
            SELECT pr.id, pr.nombre_proyecto,
                COALESCE(pr.codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(pr.instituto_proyecto, '') AS instituto_proyecto,
                pr.anio_llamado, pr.fecha_inicio, pr.fecha_fin,
                COALESCE(pr.periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(pr.observaciones, '') AS observaciones,
                COALESCE(pr.estado, 'Activo') AS estado, pr.fecha_carga,
                pr.fecha_suspension,
                COALESCE(pr.motivo_suspension, '') AS motivo_suspension,
                NULL AS departamento_creador_id,
                '' AS departamento_creador,
                COALESCE((SELECT COUNT(*) FROM extension_docente i
                          WHERE i.proyecto_id = pr.id
                            AND COALESCE(i.estado_asignacion, 'Activa') = 'Activa'), 0) AS cantidad_asignaciones,
                COALESCE((SELECT COUNT(*) FROM extension_docente i
                          WHERE i.proyecto_id = pr.id
                            AND LOWER(TRIM(COALESCE(i.estado_asignacion, 'Activa'))) <> 'baja'), 0) AS cantidad_asignaciones_historicas,
                COALESCE((SELECT COUNT(*) FROM extension_docente i
                          WHERE i.proyecto_id = pr.id), 0) AS cantidad_asignaciones_registradas,
                COALESCE((SELECT COUNT(DISTINCT i.cuil) FROM extension_docente i
                          WHERE i.proyecto_id = pr.id
                            AND COALESCE(i.estado_asignacion, 'Activa') = 'Activa'), 0) AS cantidad_docentes,
                COALESCE((SELECT COUNT(DISTINCT i.cuil) FROM extension_docente i
                          WHERE i.proyecto_id = pr.id), 0) AS cantidad_docentes_historicos,
                1 AS cantidad_departamentos,
                COALESCE((SELECT SUM(i.horas_asignadas) FROM extension_docente i
                          WHERE i.proyecto_id = pr.id
                            AND LOWER(TRIM(COALESCE(i.estado_asignacion, 'Activa'))) <> 'baja'), 0) AS horas_asignadas_historicas
            FROM proyectos_extension pr
            {where}
            ORDER BY COALESCE(pr.fecha_fin, '9999-12-31') DESC, pr.nombre_proyecto
        """, conn, params=params)

    periodo = None
    if periodo_id is not None:
        dfp = pd.read_sql("""
            SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin
            FROM periodos
            WHERE id=?
            LIMIT 1
        """, conn, params=[periodo_id])
        if not dfp.empty:
            periodo = dfp.iloc[0].to_dict()
    conn.close()
    if df.empty:
        return df
    df["situacion"] = df.apply(lambda r: _situacion_proyecto(r.to_dict()), axis=1)
    df["puede_administrar"] = df.apply(
        lambda r: _puede_administrar_proyecto_extension(r.to_dict()), axis=1
    )
    if periodo is not None:
        df = df[df.apply(lambda r: proyecto_vigente_en_periodo(r.to_dict(), periodo), axis=1)].copy()
    return df.reset_index(drop=True)


# --- entry l. 22489
_get_proyectos_extension_no_cache_v127 = get_proyectos_extension


# --- entry l. 22492-22495
def _get_proyectos_extension_cache_v127(solo_activos, periodo_id, db_url, inst_id, dep_id, version):
    return _get_proyectos_extension_no_cache_v127(
        solo_activos=bool(solo_activos), periodo_id=periodo_id
    )


# --- entry l. 22498-22503
def get_proyectos_extension(solo_activos=False, periodo_id=None):
    db_url, inst_id, dep_id, version = _cache_scope_proyectos_v127("extension")
    df = _get_proyectos_extension_cache_v127(
        bool(solo_activos), periodo_id, db_url, inst_id, dep_id, version
    )
    return df.copy()


# --- entry l. 23119-23268
def get_extension_docente(cuil=None, periodo_id=None, incluir_bajas=False,
                              todos_departamentos=False):
    """Devuelve asignaciones de extensión.

    Por defecto respeta el departamento actual. Con ``todos_departamentos=True``
    y PostgreSQL consolida las asignaciones del mismo CUIL en todos los
    departamentos de la institución y compara períodos equivalentes por
    año/semestre o nombre.
    """
    asegurar_esquema_extension_separado()

    if USE_POSTGRESQL and todos_departamentos:
        inst_id = int(_pg_current_inst_id())
        filtros = ["i.institucion_id = %s"]
        params_filtros = [inst_id]
        if cuil is not None:
            filtros.append("regexp_replace(COALESCE(i.cuil, ''), '[^0-9]', '', 'g') = %s")
            params_filtros.append(_clave_cuil(cuil))
        if not incluir_bajas:
            filtros.append("COALESCE(i.estado_asignacion, 'Activa') = 'Activa'")
        where = "WHERE " + " AND ".join(filtros)

        if periodo_id is not None:
            cte = """
                WITH periodo_ref AS (
                    SELECT id, institucion_id, nombre, anio, semestre
                    FROM periodos
                    WHERE id = %s
                    LIMIT 1
                )
            """
            join_ref = f"""
                JOIN periodo_ref pref
                  ON {_condicion_periodo_equivalente_sql('p', 'pref')}
            """
            params = [int(periodo_id)] + params_filtros
        else:
            cte = ""
            join_ref = ""
            params = params_filtros

        return _pg_read_dataframe(f"""
            {cte}
            SELECT i.id, i.proyecto_id, i.periodo_id, p.nombre AS periodo,
                p.anio AS periodo_anio, p.semestre AS periodo_semestre, i.cuil,
                COALESCE(doc.docente, i.cuil) AS docente,
                COALESCE(NULLIF(pr.nombre_proyecto, ''), i.nombre_proyecto, '') AS nombre_proyecto,
                COALESCE(NULLIF(pr.codigo_proyecto, ''), i.codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(NULLIF(pr.instituto_proyecto, ''), i.instituto_proyecto, '') AS instituto_proyecto,
                i.rol, COALESCE(pr.anio_llamado, i.anio_llamado) AS anio_llamado,
                pr.fecha_inicio, pr.fecha_fin,
                COALESCE(NULLIF(pr.periodo_ejecucion, ''), i.periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(pr.estado, 'Activo') AS estado_proyecto,
                COALESCE(i.estado_asignacion, 'Activa') AS estado_asignacion,
                i.horas_asignadas, i.observaciones, i.fecha_carga, i.fecha_baja,
                COALESCE(i.motivo_baja, '') AS motivo_baja,
                i.departamento_id AS departamento_asignacion_id,
                COALESCE(dep.nombre, '') AS departamento_asignacion
            FROM extension_docente i
            JOIN periodos p ON p.id = i.periodo_id
            {join_ref}
            LEFT JOIN proyectos_extension pr ON pr.id = i.proyecto_id
            LEFT JOIN departamentos dep ON dep.id = i.departamento_id
            LEFT JOIN LATERAL (
                SELECT
                    CASE
                        WHEN d.apellido IS NOT NULL AND d.nombres IS NOT NULL
                            THEN d.apellido || ', ' || d.nombres
                        WHEN d.nombre IS NOT NULL THEN d.nombre
                        ELSE i.cuil
                    END AS docente
                FROM docentes d
                WHERE d.institucion_id = i.institucion_id
                  AND regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g') = regexp_replace(COALESCE(i.cuil,''), '[^0-9]', '', 'g')
                ORDER BY
                    CASE WHEN d.departamento_id IS NOT DISTINCT FROM i.departamento_id THEN 0 ELSE 1 END,
                    d.id
                LIMIT 1
            ) doc ON TRUE
            {where}
            ORDER BY COALESCE(p.anio,0) DESC, COALESCE(p.semestre,0) DESC,
                     departamento_asignacion, docente, nombre_proyecto
        """, params)

    filtros = []
    params = []
    if cuil is not None:
        filtros.append("i.cuil = ?")
        params.append(cuil)
    if periodo_id is not None:
        filtros.append("i.periodo_id = ?")
        params.append(periodo_id)
    if not incluir_bajas:
        filtros.append("COALESCE(i.estado_asignacion, 'Activa') = 'Activa'")
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    conn = get_conn()

    if USE_POSTGRESQL:
        df = pd.read_sql(f"""
            SELECT i.id, i.proyecto_id, i.periodo_id, p.nombre AS periodo,
                p.anio AS periodo_anio, p.semestre AS periodo_semestre, i.cuil,
                CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                     WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE i.cuil END AS docente,
                COALESCE(NULLIF(pr.nombre_proyecto, ''), i.nombre_proyecto, '') AS nombre_proyecto,
                COALESCE(NULLIF(pr.codigo_proyecto, ''), i.codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(NULLIF(pr.instituto_proyecto, ''), i.instituto_proyecto, '') AS instituto_proyecto,
                i.rol, COALESCE(pr.anio_llamado, i.anio_llamado) AS anio_llamado,
                pr.fecha_inicio, pr.fecha_fin,
                COALESCE(NULLIF(pr.periodo_ejecucion, ''), i.periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(pr.estado, 'Activo') AS estado_proyecto,
                COALESCE(i.estado_asignacion, 'Activa') AS estado_asignacion,
                i.horas_asignadas, i.observaciones, i.fecha_carga, i.fecha_baja,
                COALESCE(i.motivo_baja, '') AS motivo_baja,
                i.departamento_id AS departamento_asignacion_id,
                COALESCE(dep.nombre, '') AS departamento_asignacion
            FROM extension_docente i
            LEFT JOIN periodos p ON p.id = i.periodo_id
            LEFT JOIN docentes doc ON doc.cuil = i.cuil
            LEFT JOIN proyectos_extension pr ON pr.id = i.proyecto_id
            LEFT JOIN departamentos dep ON dep.id = i.departamento_id
            {where}
            ORDER BY COALESCE(p.anio,0) DESC, COALESCE(p.semestre,0) DESC, docente, nombre_proyecto
        """, conn, params=params)
    else:
        df = pd.read_sql(f"""
            SELECT i.id, i.proyecto_id, i.periodo_id, p.nombre AS periodo,
                p.anio AS periodo_anio, p.semestre AS periodo_semestre, i.cuil,
                CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                     WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE i.cuil END AS docente,
                COALESCE(NULLIF(pr.nombre_proyecto, ''), i.nombre_proyecto, '') AS nombre_proyecto,
                COALESCE(NULLIF(pr.codigo_proyecto, ''), i.codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(NULLIF(pr.instituto_proyecto, ''), i.instituto_proyecto, '') AS instituto_proyecto,
                i.rol, COALESCE(pr.anio_llamado, i.anio_llamado) AS anio_llamado,
                pr.fecha_inicio, pr.fecha_fin,
                COALESCE(NULLIF(pr.periodo_ejecucion, ''), i.periodo_ejecucion, '') AS periodo_ejecucion,
                COALESCE(pr.estado, 'Activo') AS estado_proyecto,
                COALESCE(i.estado_asignacion, 'Activa') AS estado_asignacion,
                i.horas_asignadas, i.observaciones, i.fecha_carga, i.fecha_baja,
                COALESCE(i.motivo_baja, '') AS motivo_baja,
                NULL AS departamento_asignacion_id,
                '' AS departamento_asignacion
            FROM extension_docente i
            LEFT JOIN periodos p ON p.id = i.periodo_id
            LEFT JOIN docentes doc ON doc.cuil = i.cuil
            LEFT JOIN proyectos_extension pr ON pr.id = i.proyecto_id
            {where}
            ORDER BY COALESCE(p.anio,0) DESC, COALESCE(p.semestre,0) DESC, docente, nombre_proyecto
        """, conn, params=params)
    conn.close()
    return df


# --- entry l. 24238-24240
def _clave_materia_unica_desde_codigo_nombre(codigo, asignatura):
    from analisis.motor.ref.domain.materias import _clave_materia_unica_desde_codigo_nombre as _b05_core__clave_materia_unica_desde_codigo_nombre
    return _b05_core__clave_materia_unica_desde_codigo_nombre(codigo, asignatura)


# --- entry l. 24243-24245
def _contexto_materias_unicas_fuente():
    from analisis.motor.ref.domain.residual.lectura import _contexto_materias_unicas_fuente as _b06_core__contexto_materias_unicas_fuente
    return _b06_core__contexto_materias_unicas_fuente(get_plan_estudio_todas=get_plan_estudio_todas)


# --- entry l. 24356-24358
def hora_a_minutos(hora):
    from analisis.motor.ref.extracted_batch04.horarios import hora_a_minutos as _b04_core_hora_a_minutos
    return _b04_core_hora_a_minutos(hora)


# --- entry l. 24361-24363
def intervalos_solapan(inicio_a, fin_a, inicio_b, fin_b):
    from analisis.motor.ref.common.horarios import intervalos_solapan as _b05_core_intervalos_solapan
    return _b05_core_intervalos_solapan(inicio_a, fin_a, inicio_b, fin_b)


# --- entry l. 24366-24395
def get_horarios_docente_periodo(cuil, periodo_id, excluir_comision_id=None):
    conn = get_conn()
    filtros=["a.cuil = ?","co.periodo_id = ?","COALESCE(a.estado, 'Activa') = 'Activa'"]
    params=[cuil,periodo_id]
    if excluir_comision_id is not None:
        filtros.append("co.id <> ?"); params.append(excluir_comision_id)
    df=pd.read_sql(f"""
        SELECT a.id AS asignacion_id, a.cuil,
               CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                    WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE a.cuil END AS docente,
               a.rol, co.id AS comision_id, h.dia, h.hora_inicio, h.hora_fin, h.horas
        FROM asignaciones_docentes_comision a
        JOIN comisiones co ON co.id = a.comision_id
        JOIN horarios_comision h ON h.comision_id = co.id
        LEFT JOIN docentes doc ON doc.cuil = a.cuil
        WHERE {" AND ".join(filtros)}
        ORDER BY h.dia, h.hora_inicio, co.id
    """,conn,params=params); conn.close()
    extras=["periodo","codigo_materia","asignatura","materia_especifica","carrera","escuela","nombre_comision","turno","modalidad"]
    if df.empty:
        for c in extras: df[c]=""
        return df
    try:
        dfc=get_comisiones(periodo_id=periodo_id,solo_activas=False)
        meta=dfc[[c for c in ["id"]+extras if c in dfc.columns]].rename(columns={"id":"comision_id"})
        df=df.merge(meta,on="comision_id",how="left")
    except Exception:
        for c in extras:
            if c not in df.columns: df[c]=""
    return df


# --- entry l. 24433-24501
def get_superposiciones_periodo(periodo_id):
    conn = get_conn()
    df = pd.read_sql("""
        SELECT
            a.cuil,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE a.cuil
            END AS docente,
            a.rol,
            co.id AS comision_id,
            m.codigo AS codigo_materia,
            m.asignatura,
            c.nombre AS carrera,
            co.nombre_comision,
            co.turno,
            h.dia,
            h.hora_inicio,
            h.hora_fin,
            h.horas
        FROM asignaciones_docentes_comision a
        JOIN comisiones co ON co.id = a.comision_id
        JOIN horarios_comision h ON h.comision_id = co.id
        LEFT JOIN materias m ON m.id = co.materia_id
        LEFT JOIN carreras c ON c.id = m.carrera_id
        LEFT JOIN docentes doc ON doc.cuil = a.cuil
        WHERE co.periodo_id = ?
          AND COALESCE(a.estado, 'Activa') = 'Activa'
        ORDER BY docente, h.dia, h.hora_inicio
    """, conn, params=[periodo_id])
    conn.close()

    columnas = ["docente", "cuil", "dia", "materia_1", "comision_1", "horario_1", "materia_2", "comision_2", "horario_2"]
    if df.empty:
        return pd.DataFrame(columns=columnas)

    registros = []
    vistos = set()

    for cuil, grupo_doc in df.groupby("cuil", dropna=False):
        filas = grupo_doc.to_dict("records")
        for i in range(len(filas)):
            for j in range(i + 1, len(filas)):
                a = filas[i]
                b = filas[j]
                if a["comision_id"] == b["comision_id"]:
                    continue
                if str(a.get("dia", "")).strip() != str(b.get("dia", "")).strip():
                    continue
                if not intervalos_solapan(a.get("hora_inicio"), a.get("hora_fin"), b.get("hora_inicio"), b.get("hora_fin")):
                    continue
                clave = tuple(sorted([str(a["comision_id"]), str(b["comision_id"])])) + (str(cuil), str(a.get("dia", "")))
                if clave in vistos:
                    continue
                vistos.add(clave)
                registros.append({
                    "docente": a.get("docente", ""),
                    "cuil": cuil,
                    "dia": a.get("dia", ""),
                    "materia_1": a.get("asignatura", ""),
                    "comision_1": a.get("nombre_comision", ""),
                    "horario_1": f"{a.get('hora_inicio', '')}-{a.get('hora_fin', '')}",
                    "materia_2": b.get("asignatura", ""),
                    "comision_2": b.get("nombre_comision", ""),
                    "horario_2": f"{b.get('hora_inicio', '')}-{b.get('hora_fin', '')}",
                })

    return pd.DataFrame(registros, columns=columnas)


# --- entry l. 24504-24535
def calcular_horas_comisiones_unicas_docente(cuil, periodo_id):
    """Suma horas por día sin contar dos veces franjas superpuestas."""
    df = get_horarios_docente_periodo(cuil, periodo_id)
    if df.empty:
        return 0.0

    total_minutos = 0
    for dia, grupo in df.groupby("dia", dropna=False):
        intervalos = []
        for _, row in grupo.iterrows():
            ini = hora_a_minutos(row.get("hora_inicio"))
            fin = hora_a_minutos(row.get("hora_fin"))
            if ini is None or fin is None:
                continue
            if fin <= ini:
                fin += 24 * 60
            intervalos.append((ini, fin))

        if not intervalos:
            continue

        intervalos.sort()
        merged = []
        for ini, fin in intervalos:
            if not merged or ini > merged[-1][1]:
                merged.append([ini, fin])
            else:
                merged[-1][1] = max(merged[-1][1], fin)

        total_minutos += sum(fin - ini for ini, fin in merged)

    return round(total_minutos / 60, 2)


# --- entry l. 24538-24544
def get_comisiones_sin_docentes_periodo(periodo_id):
    df = get_comisiones(periodo_id=periodo_id, solo_activas=True)
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["docentes_asignados"] = pd.to_numeric(df["docentes_asignados"], errors="coerce").fillna(0).astype(int)
    return df[df["docentes_asignados"] == 0].drop(columns=["id", "periodo_id", "materia_id", "estado"], errors="ignore")


# --- entry l. 24614-24650
def get_metricas_analisis_periodo(periodo_id):
    df_plantel = get_plantel_periodo(periodo_id)
    df_desig = get_designaciones(periodo_id)
    df_com = get_comisiones(periodo_id=periodo_id, solo_activas=True)
    df_asig = get_asignaciones_comisiones_periodo(periodo_id)
    df_mov = get_movimientos(periodo_id)

    horas_contratadas = float(pd.to_numeric(df_desig[df_desig["estado"] == "Activa"]["horas"], errors="coerce").fillna(0).sum()) if not df_desig.empty else 0.0
    if not df_asig.empty and "tipo_docente" in df_asig.columns:
        df_asig_propios = df_asig[df_asig["tipo_docente"].fillna("Propio").astype(str).str.strip() != "Prestado"].copy()
        df_asig_prestados = df_asig[df_asig["tipo_docente"].fillna("Propio").astype(str).str.strip() == "Prestado"].copy()
    else:
        df_asig_propios = df_asig.copy() if not df_asig.empty else pd.DataFrame()
        df_asig_prestados = pd.DataFrame()
    horas_comisiones_brutas = float(pd.to_numeric(df_asig_propios.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not df_asig_propios.empty else 0.0
    docentes_prestados_recibidos = int(df_asig_prestados["cuil"].dropna().nunique()) if not df_asig_prestados.empty else 0
    docentes_activos = int((df_plantel["estado_operativo_periodo"] == "Activo en el período").sum()) if not df_plantel.empty else 0
    cargos_totales = int(len(df_desig[df_desig["estado"] == "Activa"])) if not df_desig.empty else 0
    materias_con_comision = int(df_com["codigo_materia"].dropna().nunique()) if not df_com.empty else 0
    comisiones = int(len(df_com)) if not df_com.empty else 0
    docentes_en_comisiones = int(df_asig_propios["cuil"].dropna().nunique()) if not df_asig_propios.empty else 0

    return {
        "df_plantel": df_plantel,
        "df_desig": df_desig,
        "df_com": df_com,
        "df_asig": df_asig,
        "df_mov": df_mov,
        "docentes_activos": docentes_activos,
        "cargos_totales": cargos_totales,
        "horas_contratadas": horas_contratadas,
        "horas_comisiones": horas_comisiones_brutas,
        "materias_con_comision": materias_con_comision,
        "comisiones": comisiones,
        "docentes_en_comisiones": docentes_en_comisiones,
        "docentes_prestados_recibidos": docentes_prestados_recibidos
    }


# --- entry l. 24653-24655
def tabla_conteo_porcentajes(df, columna):
    from analisis.motor.ref.domain.informes import tabla_conteo_porcentajes as _b05_core_tabla_conteo_porcentajes
    return _b05_core_tabla_conteo_porcentajes(df, columna)


# --- entry l. 24658-24671
def get_periodo_mismo_semestre_anio_anterior(periodo):
    if not periodo:
        return None
    conn = get_conn()
    df = pd.read_sql("""
        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones
        FROM periodos
        WHERE anio = ? AND semestre = ?
        LIMIT 1
    """, conn, params=[int(periodo["anio"]) - 1, int(periodo["semestre"])])
    conn.close()
    if df.empty:
        return None
    return df.iloc[0].to_dict()


# --- entry l. 24678-24699
def render_torta(df, label_col, value_col, titulo=None):
    if titulo:
        st.markdown(f"**{titulo}**")
    if df is None or df.empty or float(pd.to_numeric(df[value_col], errors="coerce").fillna(0).sum()) == 0:
        st.info("No hay datos para graficar.")
        return
    st.vega_lite_chart(
        df,
        {
            "mark": {"type": "arc", "tooltip": True},
            "encoding": {
                "theta": {"field": value_col, "type": "quantitative"},
                "color": {"field": label_col, "type": "nominal"},
                "tooltip": [
                    {"field": label_col, "type": "nominal"},
                    {"field": value_col, "type": "quantitative"}
                ]
            },
            "view": {"stroke": None}
        },
        use_container_width=True
    )


# --- entry l. 24704-24779
def get_docentes_productividad_periodo(periodo_id):
    """Devuelve productividad por docente activo del período, sin contar doble las horas superpuestas."""
    df_plantel = get_plantel_periodo(periodo_id)
    columnas = [
        "cuil", "docente", "tipo_docente", "cargos", "dedicaciones", "tipos_designacion",
        "horas_contratadas", "horas_comisiones_brutas", "horas_comisiones_reales",
        "horas_no_contadas_por_superposicion", "horas_investigacion", "horas_extension",
        "horas_utilizadas", "horas_disponibles", "porcentaje_uso", "diagnostico"
    ]
    if df_plantel.empty:
        return pd.DataFrame(columns=columnas)

    df_desig = get_designaciones(periodo_id)
    if not df_desig.empty:
        df_desig_act = df_desig[df_desig["estado"] == "Activa"].copy()
    else:
        df_desig_act = pd.DataFrame(columns=["cuil", "cargo", "dedicacion", "tipo_designacion"])

    registros = []
    for _, row in df_plantel.iterrows():
        cuil = row.get("cuil", "")
        if not cuil:
            continue
        if str(row.get("tipo_docente", "Propio")).strip() == "Prestado":
            continue
        prod = get_productividad_docente(cuil, periodo_id)
        desig_doc = df_desig_act[df_desig_act["cuil"] == cuil].copy() if not df_desig_act.empty else pd.DataFrame()

        def unir_unicos(col):
            if desig_doc.empty or col not in desig_doc.columns:
                return ""
            vals = []
            for v in desig_doc[col].dropna().astype(str).tolist():
                v = v.strip()
                if v and v not in vals:
                    vals.append(v)
            return " / ".join(vals)

        contratadas = float(prod.get("horas_contratadas", 0) or 0)
        utilizadas = float(prod.get("horas_utilizadas", 0) or 0)
        disponibles = float(prod.get("horas_disponibles", 0) or 0)
        porcentaje = float(prod.get("porcentaje", 0) or 0)

        if contratadas <= 0 and utilizadas > 0:
            diagnostico = "Actividad registrada sin horas contratadas"
        elif utilizadas > contratadas:
            diagnostico = "Sobrecarga: horas utilizadas superan las contratadas"
        elif contratadas > 0 and utilizadas == 0:
            diagnostico = "Sin actividad registrada"
        elif contratadas > 0 and porcentaje < 50:
            diagnostico = "Subutilización: baja carga registrada"
        else:
            diagnostico = "Sin alerta principal"

        registros.append({
            "cuil": cuil,
            "docente": row.get("nombre_completo", ""),
            "tipo_docente": row.get("tipo_docente", "Propio"),
            "cargos": unir_unicos("cargo"),
            "dedicaciones": unir_unicos("dedicacion"),
            "tipos_designacion": unir_unicos("tipo_designacion"),
            "horas_contratadas": contratadas,
            "horas_comisiones_brutas": float(prod.get("horas_en_comisiones_brutas", 0) or 0),
            "horas_comisiones_reales": float(prod.get("horas_en_comisiones", 0) or 0),
            "horas_no_contadas_por_superposicion": float(prod.get("horas_no_contadas_por_superposicion", 0) or 0),
            "horas_investigacion": float(prod.get("horas_en_investigacion", 0) or 0),
            "horas_extension": float(prod.get("horas_en_extension", 0) or 0),
            "horas_utilizadas": round(utilizadas, 2),
            "horas_disponibles": round(disponibles, 2),
            "porcentaje_uso": porcentaje,
            "diagnostico": diagnostico,
        })

    if not registros:
        return pd.DataFrame(columns=columnas)
    return pd.DataFrame(registros, columns=columnas).sort_values(["diagnostico", "docente"], kind="stable")


# --- entry l. 24782-24816
def get_docentes_asignados_sin_designacion_periodo(periodo_id):
    """Docentes propios asignados a comisiones sin designación activa en el período."""
    conn = get_conn()
    df = pd.read_sql("""
        SELECT
            a.cuil,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE a.cuil
            END AS docente,
            COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente,
            m.codigo AS codigo_materia,
            m.asignatura,
            co.nombre_comision,
            a.rol,
            COALESCE((
                SELECT COUNT(*)
                FROM designaciones d
                WHERE d.cuil = a.cuil
                  AND d.periodo_id = co.periodo_id
                  AND d.estado = 'Activa'
            ), 0) AS designaciones_activas
        FROM asignaciones_docentes_comision a
        JOIN comisiones co ON co.id = a.comision_id
        LEFT JOIN materias m ON m.id = co.materia_id
        LEFT JOIN docentes doc ON doc.cuil = a.cuil
        WHERE co.periodo_id = ?
          AND COALESCE(a.estado, 'Activa') = 'Activa'
        ORDER BY docente, m.codigo, co.nombre_comision
    """, conn, params=[periodo_id])
    conn.close()
    if df.empty:
        return df
    return df[(df["designaciones_activas"] == 0) & (df["tipo_docente"].fillna("Propio") != "Prestado")].copy()


# --- entry l. 24819-24869
def get_roles_inconsistentes_periodo(periodo_id):
    """Detecta roles asignados en comisión que no coinciden con cargos activos del docente."""
    conn = get_conn()
    df = pd.read_sql("""
        SELECT
            a.cuil,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE a.cuil
            END AS docente,
            COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente,
            m.codigo AS codigo_materia,
            m.asignatura,
            co.nombre_comision,
            a.rol,
            COALESCE((
                SELECT GROUP_CONCAT(DISTINCT d.cargo)
                FROM designaciones d
                WHERE d.cuil = a.cuil
                  AND d.periodo_id = co.periodo_id
                  AND d.estado = 'Activa'
            ), '') AS cargos_activos
        FROM asignaciones_docentes_comision a
        JOIN comisiones co ON co.id = a.comision_id
        LEFT JOIN materias m ON m.id = co.materia_id
        LEFT JOIN docentes doc ON doc.cuil = a.cuil
        WHERE co.periodo_id = ?
          AND COALESCE(a.estado, 'Activa') = 'Activa'
        ORDER BY docente, m.codigo, co.nombre_comision
    """, conn, params=[periodo_id])
    conn.close()

    columnas = ["cuil", "docente", "tipo_docente", "codigo_materia", "asignatura", "nombre_comision", "rol", "cargos_activos", "detalle"]
    if df.empty:
        return pd.DataFrame(columns=columnas)

    registros = []
    for _, row in df.iterrows():
        if str(row.get("tipo_docente", "Propio")).strip() == "Prestado":
            continue
        rol = normalizar_clave(row.get("rol", ""))
        cargos = [normalizar_clave(x) for x in str(row.get("cargos_activos", "")).split(",") if str(x).strip()]
        if not rol or not cargos:
            continue
        if rol not in cargos:
            item = row.to_dict()
            item["detalle"] = "El rol asignado en comisión no coincide con los cargos activos del docente en el período."
            registros.append(item)

    return pd.DataFrame(registros, columns=columnas) if registros else pd.DataFrame(columns=columnas)


# --- entry l. 24872-24878
def get_comisiones_sin_horarios_periodo(periodo_id):
    df = get_comisiones(periodo_id=periodo_id, solo_activas=True)
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["cantidad_horarios"] = pd.to_numeric(df["cantidad_horarios"], errors="coerce").fillna(0).astype(int)
    return df[df["cantidad_horarios"] == 0].drop(columns=["id", "periodo_id", "materia_id", "estado"], errors="ignore")


# --- entry l. 24881-24965
def construir_alertas_periodo(periodo_id):
    """Construye alertas por reglas duras. La IA, si se agrega, debería redactar sobre esta base."""
    alertas = []

    df_super = get_superposiciones_periodo(periodo_id)
    for _, row in df_super.iterrows():
        alertas.append({
            "gravedad": "Alta",
            "categoria": "Superposición horaria",
            "docente": row.get("docente", ""),
            "detalle": f"{row.get('dia', '')}: {row.get('materia_1', '')} comisión {row.get('comision_1', '')} ({row.get('horario_1', '')}) se superpone con {row.get('materia_2', '')} comisión {row.get('comision_2', '')} ({row.get('horario_2', '')}).",
            "accion_sugerida": "Revisar horario o reasignar docente. No contar doble esas horas en productividad."
        })

    df_sin_doc = get_comisiones_sin_docentes_periodo(periodo_id)
    for _, row in df_sin_doc.iterrows():
        alertas.append({
            "gravedad": "Alta",
            "categoria": "Comisión sin docentes",
            "docente": "",
            "detalle": f"{row.get('codigo_materia', '')} - {row.get('asignatura', '')}, comisión {row.get('nombre_comision', '')}, turno {row.get('turno', '')}.",
            "accion_sugerida": "Asignar equipo docente o cerrar la comisión si no corresponde dictarla."
        })

    df_sin_hor = get_comisiones_sin_horarios_periodo(periodo_id)
    for _, row in df_sin_hor.iterrows():
        alertas.append({
            "gravedad": "Media",
            "categoria": "Comisión sin horarios",
            "docente": "",
            "detalle": f"{row.get('codigo_materia', '')} - {row.get('asignatura', '')}, comisión {row.get('nombre_comision', '')} no tiene horarios cargados.",
            "accion_sugerida": "Cargar días y horarios para poder calcular horas y detectar superposiciones."
        })

    df_sin_desig = get_docentes_asignados_sin_designacion_periodo(periodo_id)
    for _, row in df_sin_desig.iterrows():
        alertas.append({
            "gravedad": "Alta",
            "categoria": "Docente asignado sin designación activa",
            "docente": row.get("docente", ""),
            "detalle": f"Figura en {row.get('codigo_materia', '')} - {row.get('asignatura', '')}, comisión {row.get('nombre_comision', '')}, rol {row.get('rol', '')}, pero no tiene designación activa en el período.",
            "accion_sugerida": "Cargar/verificar designación o marcarlo como docente prestado si corresponde."
        })

    df_roles = get_roles_inconsistentes_periodo(periodo_id)
    for _, row in df_roles.iterrows():
        alertas.append({
            "gravedad": "Media",
            "categoria": "Rol distinto al cargo activo",
            "docente": row.get("docente", ""),
            "detalle": f"En {row.get('codigo_materia', '')} - {row.get('asignatura', '')}, comisión {row.get('nombre_comision', '')}, figura como {row.get('rol', '')}; cargos activos: {row.get('cargos_activos', '')}.",
            "accion_sugerida": "Revisar si el rol de comisión debe coincidir con el cargo activo o si hay que corregir la designación."
        })

    df_prod = get_docentes_productividad_periodo(periodo_id)
    if not df_prod.empty:
        for _, row in df_prod.iterrows():
            diagnostico = row.get("diagnostico", "")
            if diagnostico == "Sobrecarga: horas utilizadas superan las contratadas":
                alertas.append({
                    "gravedad": "Alta",
                    "categoria": "Docente sobrecargado",
                    "docente": row.get("docente", ""),
                    "detalle": f"Tiene {row.get('horas_contratadas', 0)} hs contratadas y {row.get('horas_utilizadas', 0)} hs registradas entre comisiones reales, horas no lectivas, investigación y extensión.",
                    "accion_sugerida": "Revisar distribución de horas, comisiones, investigación, extensión o dedicación."
                })
            elif diagnostico == "Sin actividad registrada":
                alertas.append({
                    "gravedad": "Media",
                    "categoria": "Docente sin actividad registrada",
                    "docente": row.get("docente", ""),
                    "detalle": f"Tiene {row.get('horas_contratadas', 0)} hs contratadas y no registra comisiones, investigación ni extensión.",
                    "accion_sugerida": "Cargar actividad real, investigación/extensión o revisar si la designación corresponde."
                })
            elif diagnostico == "Subutilización: baja carga registrada":
                alertas.append({
                    "gravedad": "Baja",
                    "categoria": "Docente subutilizado",
                    "docente": row.get("docente", ""),
                    "detalle": f"Tiene {row.get('horas_contratadas', 0)} hs contratadas y {row.get('horas_utilizadas', 0)} hs registradas ({row.get('porcentaje_uso', 0)}%).",
                    "accion_sugerida": "Verificar si faltan actividades cargadas o si hay horas disponibles para reasignación."
                })

    columnas = ["gravedad", "categoria", "docente", "detalle", "accion_sugerida"]
    return pd.DataFrame(alertas, columns=columnas) if alertas else pd.DataFrame(columns=columnas)


# --- entry l. 24968-25001
def generar_resumen_ejecutivo_automatico(periodo_nombre, metricas, df_alertas, df_prod):
    total_alertas = len(df_alertas) if df_alertas is not None else 0
    altas = int((df_alertas["gravedad"] == "Alta").sum()) if df_alertas is not None and not df_alertas.empty else 0
    medias = int((df_alertas["gravedad"] == "Media").sum()) if df_alertas is not None and not df_alertas.empty else 0
    bajas = int((df_alertas["gravedad"] == "Baja").sum()) if df_alertas is not None and not df_alertas.empty else 0

    superposiciones = int((df_alertas["categoria"] == "Superposición horaria").sum()) if df_alertas is not None and not df_alertas.empty else 0
    sin_docentes = int((df_alertas["categoria"] == "Comisión sin docentes").sum()) if df_alertas is not None and not df_alertas.empty else 0
    sobrecargados = int((df_alertas["categoria"] == "Docente sobrecargado").sum()) if df_alertas is not None and not df_alertas.empty else 0
    sin_actividad = int((df_alertas["categoria"] == "Docente sin actividad registrada").sum()) if df_alertas is not None and not df_alertas.empty else 0
    subutilizados = int((df_alertas["categoria"] == "Docente subutilizado").sum()) if df_alertas is not None and not df_alertas.empty else 0

    texto = (
        f"Durante el período {periodo_nombre} se registran {metricas.get('docentes_activos', 0)} docentes activos, "
        f"{metricas.get('cargos_totales', 0)} cargos activos, {metricas.get('horas_contratadas', 0)} horas contratadas, "
        f"{metricas.get('materias_con_comision', 0)} materias con comisión y {metricas.get('comisiones', 0)} comisiones activas. "
        f"Hay {metricas.get('docentes_en_comisiones', 0)} docentes asignados a comisiones y "
        f"{metricas.get('horas_academicas_utilizadas', 0)} horas totales distribuidas entre docencia, horas no lectivas, investigación y extensión. "
    )

    if total_alertas == 0:
        texto += "No se detectaron alertas automáticas relevantes con las reglas actuales. Conviene igualmente revisar datos sensibles como resoluciones, disposiciones y cargas recientes."
    else:
        texto += (
            f"El análisis automático detectó {total_alertas} alertas: {altas} de gravedad alta, {medias} de gravedad media y {bajas} de gravedad baja. "
            f"Entre los puntos principales aparecen {superposiciones} superposiciones horarias, {sin_docentes} comisiones sin docentes, "
            f"{sobrecargados} docentes sobrecargados, {sin_actividad} docentes sin actividad registrada y {subutilizados} docentes con baja carga registrada. "
        )
        if sin_docentes or superposiciones:
            texto += "La prioridad operativa debería ser corregir comisiones sin equipo docente y superposiciones, porque afectan directamente la consistencia del plantel y la productividad. "
        if sin_actividad or subutilizados:
            texto += "Luego conviene revisar docentes con horas contratadas sin actividad suficiente cargada, porque puede haber actividades reales no registradas o recursos subutilizados."

    return texto


# --- entry l. 25004-25048
def construir_prompt_ia_periodo(periodo_nombre, metricas, df_alertas, df_prod):
    alertas_txt = "Sin alertas detectadas."
    if df_alertas is not None and not df_alertas.empty:
        alertas_txt = df_alertas.head(80).to_csv(index=False)

    prod_txt = "Sin datos de productividad."
    if df_prod is not None and not df_prod.empty:
        cols = [
            "docente", "cargos", "dedicaciones", "horas_contratadas",
            "horas_comisiones_reales", "porcentaje_no_lectivas", "horas_no_lectivas",
            "horas_investigacion", "horas_extension", "horas_utilizadas",
            "horas_disponibles", "porcentaje_uso", "diagnostico"
        ]
        prod_txt = df_prod[[c for c in cols if c in df_prod.columns]].head(80).to_csv(index=False)

    return f"""Actuá como auditor académico-administrativo del Departamento de Informática e Ingeniería.
Analizá el período {periodo_nombre} con criterio técnico, directo y orientado a gestión.
No inventes datos. Basate únicamente en la información estructurada que sigue.

Métricas generales:
- Docentes activos: {metricas.get('docentes_activos', 0)}
- Cargos activos: {metricas.get('cargos_totales', 0)}
- Horas contratadas: {metricas.get('horas_contratadas', 0)}
- Materias con comisión: {metricas.get('materias_con_comision', 0)}
- Comisiones activas: {metricas.get('comisiones', 0)}
- Docentes en comisiones: {metricas.get('docentes_en_comisiones', 0)}
- Horas en comisiones: {metricas.get('horas_comisiones', 0)}
- Horas en investigación: {metricas.get('horas_investigacion', 0)}
- Horas en extensión: {metricas.get('horas_extension', 0)}
- Total de horas utilizadas: {metricas.get('horas_academicas_utilizadas', 0)}

Alertas detectadas por reglas:
{alertas_txt}

Productividad por docente:
{prod_txt}

Devolvé:
1. Resumen ejecutivo del semestre.
2. Problemas críticos y por qué importan.
3. Docentes sobrecargados o subutilizados.
4. Comisiones que requieren acción.
5. Sugerencias priorizadas de corrección.
6. Riesgos si no se corrige.
"""


# --- entry l. 25214-25216
def _normalizar_modo_comparticion_v137(valor):
    from analisis.motor.ref.domain.catalog_unlocked.materias import _normalizar_modo_comparticion_v137 as _b08_core__normalizar_modo_comparticion_v137
    return _b08_core__normalizar_modo_comparticion_v137(valor)


# --- entry l. 25251-25288
def asegurar_esquema_config_productividad_v148():
    """Crea una configuración propia por departamento para estimar horas no lectivas."""
    if st.session_state.get("_esquema_config_productividad_v148_ok"):
        return
    try:
        if USE_POSTGRESQL:
            conn = _pg_raw_conn(); cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS config_productividad_departamento (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT NOT NULL,
                    porcentaje_horas_no_lectivas DOUBLE PRECISION NOT NULL DEFAULT 0,
                    fecha_actualizacion TIMESTAMP,
                    UNIQUE (institucion_id, departamento_id)
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_config_productividad_departamento_scope "
                "ON config_productividad_departamento (institucion_id, departamento_id)"
            )
            conn.commit(); cur.close(); conn.close()
        else:
            conn = get_conn(); c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS config_productividad_departamento (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    porcentaje_horas_no_lectivas REAL NOT NULL DEFAULT 0,
                    fecha_actualizacion TEXT
                )
            """)
            conn.commit(); conn.close()
        st.session_state["_esquema_config_productividad_v148_ok"] = True
    except Exception as e:
        try:
            st.warning(f"No se pudo preparar la configuración de productividad: {e}")
        except Exception:
            pass


# --- entry l. 25291-25318
def get_porcentaje_horas_no_lectivas_v148():
    """Porcentaje adicional sobre horas lectivas de comisión. Es propio del departamento actual."""
    asegurar_esquema_config_productividad_v148()
    try:
        if USE_POSTGRESQL:
            inst_id = _pg_current_inst_id(); dep_id = _pg_current_dep_id()
            if inst_id is None or dep_id is None:
                return 0.0
            df = _pg_read_dataframe(
                """SELECT porcentaje_horas_no_lectivas
                   FROM config_productividad_departamento
                   WHERE institucion_id=%s AND departamento_id=%s
                   LIMIT 1""",
                [int(inst_id), int(dep_id)],
            )
        else:
            conn = get_conn()
            df = pd.read_sql(
                "SELECT porcentaje_horas_no_lectivas FROM config_productividad_departamento ORDER BY id LIMIT 1",
                conn,
            )
            conn.close()
        if df is None or df.empty:
            return 0.0
        valor = float(pd.to_numeric(df.iloc[0].get("porcentaje_horas_no_lectivas"), errors="coerce") or 0)
        return max(0.0, min(valor, 200.0))
    except Exception:
        return 0.0


# --- entry l. 25321-25361
def guardar_porcentaje_horas_no_lectivas_v148(porcentaje):
    """Guarda el porcentaje estimado sin modificar designaciones ni horarios reales."""
    asegurar_esquema_config_productividad_v148()
    pct = max(0.0, min(float(porcentaje or 0), 200.0))
    ahora = datetime.now()
    if USE_POSTGRESQL:
        inst_id = _pg_current_inst_id(); dep_id = _pg_current_dep_id()
        if inst_id is None or dep_id is None:
            raise ValueError("No se pudo identificar el departamento operativo.")
        conn = _pg_raw_conn(); cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO config_productividad_departamento
                    (institucion_id, departamento_id, porcentaje_horas_no_lectivas, fecha_actualizacion)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (institucion_id, departamento_id)
                DO UPDATE SET porcentaje_horas_no_lectivas=EXCLUDED.porcentaje_horas_no_lectivas,
                              fecha_actualizacion=EXCLUDED.fecha_actualizacion
            """, [int(inst_id), int(dep_id), pct, ahora])
            conn.commit()
        finally:
            cur.close(); conn.close()
    else:
        conn = get_conn(); c = conn.cursor()
        try:
            c.execute("SELECT id FROM config_productividad_departamento ORDER BY id LIMIT 1")
            fila = c.fetchone()
            if fila:
                c.execute(
                    "UPDATE config_productividad_departamento SET porcentaje_horas_no_lectivas=?, fecha_actualizacion=? WHERE id=?",
                    (pct, str(ahora), int(fila[0])),
                )
            else:
                c.execute(
                    "INSERT INTO config_productividad_departamento (porcentaje_horas_no_lectivas, fecha_actualizacion) VALUES (?, ?)",
                    (pct, str(ahora)),
                )
            conn.commit()
        finally:
            conn.close()
    return pct


# --- entry l. 26179-26194
def _docente_tipo_local(cuil):
    """Tipo del docente dentro del departamento actual. Si figura como Prestado, no se computa como plantel propio."""
    try:
        conn = get_conn()
        df = pd.read_sql("""
            SELECT COALESCE(tipo_docente, 'Propio') AS tipo_docente
            FROM docentes
            WHERE cuil = ?
            LIMIT 1
        """, conn, params=[cuil])
        conn.close()
        if not df.empty:
            return str(df.iloc[0].get("tipo_docente") or "Propio").strip() or "Propio"
    except Exception:
        pass
    return "Propio"


# --- entry l. 26197-26198
def es_docente_prestado_local(cuil):
    return _docente_tipo_local(cuil).strip().lower() == "prestado"


# --- entry l. 26361-26469
def get_comisiones_integradas_periodo(periodo_id=None):
    """Una fila por comisión con materia, horarios y docentes asignados agregados."""
    filtros = []
    params = []
    if periodo_id is not None:
        filtros.append("co.periodo_id = ?")
        params.append(periodo_id)
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    conn = get_conn()
    df_com = pd.read_sql(f"""
        SELECT
            co.id,
            p.nombre AS periodo,
            m.codigo AS codigo_materia,
            m.asignatura,
            c.nombre AS carrera,
            c.escuela,
            COALESCE(m.plan_version, c.plan_version, '') AS plan_version,
            m.anio,
            m.cuatrimestre,
            m.dictado,
            m.carga_semanal,
            m.carga_total,
            co.nombre_comision,
            co.turno,
            co.sede,
            co.modalidad,
            co.estado,
            co.observaciones
        FROM comisiones co
        LEFT JOIN periodos p ON p.id = co.periodo_id
        LEFT JOIN materias m ON m.id = co.materia_id
        LEFT JOIN carreras c ON c.id = m.carrera_id
        {where}
        ORDER BY c.escuela, c.nombre, m.codigo, m.asignatura, co.nombre_comision
    """, conn, params=params)
    df_h = pd.read_sql(f"""
        SELECT
            co.id AS comision_id,
            h.dia, h.hora_inicio, h.hora_fin, h.horas
        FROM horarios_comision h
        LEFT JOIN comisiones co ON co.id = h.comision_id
        {where}
        ORDER BY co.id,
            CASE h.dia
                WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3
                WHEN 'Jueves' THEN 4 WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6
                WHEN 'Domingo' THEN 7 ELSE 99 END,
            h.hora_inicio
    """, conn, params=params)
    df_a = pd.read_sql(f"""
        SELECT
            co.id AS comision_id,
            a.cuil,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE a.cuil
            END AS docente,
            COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente,
            a.rol,
            a.horas_asignadas,
            a.estado
        FROM asignaciones_docentes_comision a
        LEFT JOIN comisiones co ON co.id = a.comision_id
        LEFT JOIN docentes doc ON doc.cuil = a.cuil
        {where}
        ORDER BY co.id, docente, a.rol
    """, conn, params=params)
    conn.close()

    if df_com.empty:
        return pd.DataFrame()

    def _join_h(g):
        vals = []
        for _, r in g.iterrows():
            vals.append(f"{r.get('dia','')} {r.get('hora_inicio','')}-{r.get('hora_fin','')} ({r.get('horas',0)} hs)")
        return " | ".join(vals)
    def _join_a(g):
        vals = []
        for _, r in g.iterrows():
            tipo = f" - {r.get('tipo_docente')}" if r.get('tipo_docente') else ""
            vals.append(f"{r.get('docente','')} [{r.get('cuil','')}] - {r.get('rol','')} ({r.get('horas_asignadas',0)} hs{tipo})")
        return " | ".join(vals)

    if not df_h.empty:
        h_ag = df_h.groupby("comision_id", dropna=False).apply(_join_h).reset_index(name="horarios")
        hs_ag = df_h.groupby("comision_id", dropna=False)["horas"].sum().reset_index(name="horas_semanales_horario")
        df_com = df_com.merge(h_ag, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
        df_com = df_com.merge(hs_ag, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
    else:
        df_com["horarios"] = ""
        df_com["horas_semanales_horario"] = 0.0

    if not df_a.empty:
        a_ag = df_a.groupby("comision_id", dropna=False).apply(_join_a).reset_index(name="docentes_asignados_detalle")
        a_ct = df_a.groupby("comision_id", dropna=False)["cuil"].nunique().reset_index(name="cantidad_docentes")
        df_com = df_com.merge(a_ag, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
        df_com = df_com.merge(a_ct, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
    else:
        df_com["docentes_asignados_detalle"] = ""
        df_com["cantidad_docentes"] = 0

    df_com["horarios"] = df_com["horarios"].fillna("")
    df_com["docentes_asignados_detalle"] = df_com["docentes_asignados_detalle"].fillna("")
    df_com["horas_semanales_horario"] = pd.to_numeric(df_com["horas_semanales_horario"], errors="coerce").fillna(0)
    df_com["cantidad_docentes"] = pd.to_numeric(df_com["cantidad_docentes"], errors="coerce").fillna(0).astype(int)
    return df_com


# --- entry l. 26564-26567
def _periodo_equivalente_pg(periodo_id):
    'Devuelve datos del período para cruzar departamentos con IDs distintos.'
    from analisis.motor.ref.extracted_batch03.readonly_queries import _periodo_equivalente_pg as _b03_core__periodo_equivalente_pg
    return _b03_core__periodo_equivalente_pg(periodo_id, _pg_read_dataframe=_pg_read_dataframe)


# --- entry l. 26568-26627
def _get_horarios_docente_periodo_pg_global(cuil, periodo_id, excluir_comision_id=None):
    """Horarios del docente en toda la institución para el mismo período académico."""
    if not USE_POSTGRESQL:
        return get_horarios_docente_periodo(cuil, periodo_id, excluir_comision_id=excluir_comision_id)
    try:
        inst_id = _pg_current_inst_id()
        periodo_nombre, anio, semestre = _periodo_equivalente_pg(periodo_id)
        filtros = [
            "a.cuil = %s",
            "co.institucion_id = %s",
            "COALESCE(a.estado, 'Activa') = 'Activa'",
            "(co.periodo_id = %s OR p.nombre = %s OR (p.anio = %s AND p.semestre = %s))",
        ]
        params = [_clave_cuil(cuil), int(inst_id), int(periodo_id), periodo_nombre, int(anio), int(semestre)]
        if excluir_comision_id is not None:
            filtros.append("co.id <> %s")
            params.append(int(excluir_comision_id))
        where = "WHERE " + " AND ".join(filtros)
        return _pg_read_dataframe(f"""
            SELECT
                a.id AS asignacion_id,
                a.cuil,
                COALESCE((
                    SELECT CASE
                        WHEN d.apellido IS NOT NULL AND d.nombres IS NOT NULL THEN d.apellido || ', ' || d.nombres
                        WHEN d.nombre IS NOT NULL THEN d.nombre
                        ELSE d.cuil
                    END
                    FROM docentes d
                    WHERE d.cuil = a.cuil
                      AND d.institucion_id = co.institucion_id
                    ORDER BY CASE WHEN d.departamento_id = co.departamento_id THEN 0 ELSE 1 END, d.id
                    LIMIT 1
                ), a.cuil) AS docente,
                a.rol,
                co.id AS comision_id,
                dep.nombre AS departamento_comision,
                p.nombre AS periodo,
                m.codigo AS codigo_materia,
                m.asignatura,
                c.nombre AS carrera,
                c.escuela,
                co.nombre_comision,
                co.turno,
                h.dia,
                h.hora_inicio,
                h.hora_fin,
                h.horas
            FROM asignaciones_docentes_comision a
            JOIN comisiones co ON co.id = a.comision_id
            JOIN horarios_comision h ON h.comision_id = co.id
            LEFT JOIN periodos p ON p.id = co.periodo_id
            LEFT JOIN departamentos dep ON dep.id = co.departamento_id
            LEFT JOIN materias m ON m.id = co.materia_id
            LEFT JOIN carreras c ON c.id = m.carrera_id
            {where}
            ORDER BY h.dia, h.hora_inicio, dep.nombre, m.codigo, co.nombre_comision
        """, params)
    except Exception:
        return pd.DataFrame()


# --- entry l. 26630-26632
def _calcular_horas_unicas_desde_horarios_df(df_horarios):
    from analisis.motor.ref.common.horarios import _calcular_horas_unicas_desde_horarios_df as _b05_core__calcular_horas_unicas_desde_horarios_df
    return _b05_core__calcular_horas_unicas_desde_horarios_df(df_horarios)


# --- entry l. 26635-26636
def calcular_horas_comisiones_unicas_docente_pg_global(cuil, periodo_id):
    return _calcular_horas_unicas_desde_horarios_df(_get_horarios_docente_periodo_pg_global(cuil, periodo_id))


# --- entry l. 26679-26735
def get_designaciones_docente_todos_departamentos_pg(cuil, periodo_id=None):
    """Designaciones del mismo CUIL en todos los departamentos de la institución."""
    if not USE_POSTGRESQL or not str(cuil or "").strip():
        return pd.DataFrame()
    try:
        inst_id = _pg_current_inst_id()
        clave_cuil = _clave_cuil(cuil)
        filtros = ["regexp_replace(COALESCE(d.cuil, ''), '[^0-9]', '', 'g') = %s", "d.institucion_id = %s"]
        params = [clave_cuil, int(inst_id)]
        if periodo_id is not None:
            nombre_p, anio, semestre = _periodo_equivalente_pg(periodo_id)
            filtros.append("(d.periodo_id = %s OR p.nombre = %s OR (p.anio = %s AND p.semestre = %s))")
            params.extend([int(periodo_id), nombre_p, int(anio), int(semestre)])
            try:
                conn_estado = get_conn()
                df_estado = pd.read_sql(
                    "SELECT COALESCE(estado, '') AS estado FROM periodos WHERE id = ? LIMIT 1",
                    conn_estado,
                    params=[periodo_id],
                )
                conn_estado.close()
                if not df_estado.empty and str(df_estado.iloc[0].get("estado") or "").strip().lower() != "cerrado":
                    filtros.append("COALESCE(d.estado, 'Activa') = 'Activa'")
            except Exception:
                filtros.append("COALESCE(d.estado, 'Activa') = 'Activa'")
        where = "WHERE " + " AND ".join(filtros)
        return _pg_read_dataframe(f"""
            SELECT
                COALESCE(dep.nombre, 'Sin departamento') AS departamento,
                p.nombre AS periodo,
                d.cargo,
                d.dedicacion,
                d.horas,
                d.tipo_designacion,
                COALESCE(d.ad_honorem, 'No') AS ad_honorem,
                d.estado,
                d.fecha_desde,
                d.fecha_hasta,
                d.observaciones
            FROM designaciones d
            JOIN periodos p ON p.id = d.periodo_id
            LEFT JOIN departamentos dep ON dep.id = d.departamento_id
            {where}
              AND p.institucion_id = d.institucion_id
              AND p.departamento_id IS NOT DISTINCT FROM d.departamento_id
              AND EXISTS (
                  SELECT 1
                  FROM docentes doc_local
                  WHERE doc_local.institucion_id = d.institucion_id
                    AND doc_local.departamento_id IS NOT DISTINCT FROM d.departamento_id
                    AND regexp_replace(COALESCE(doc_local.cuil, ''), '[^0-9]', '', 'g') =
                        regexp_replace(COALESCE(d.cuil, ''), '[^0-9]', '', 'g')
              )
            ORDER BY dep.nombre, p.anio DESC, p.semestre DESC, d.cargo, d.tipo_designacion
        """, params)
    except Exception:
        return pd.DataFrame()


# --- entry l. 26738-26772
def _docente_tiene_designacion_local_periodo_pg(cuil, periodo_id, incluir_historicas=False):
    """Comprueba que el docente realmente tenga designación en el departamento actual."""
    if not USE_POSTGRESQL or not str(cuil or "").strip() or periodo_id is None:
        return False
    try:
        inst_id = _pg_current_inst_id()
        dep_id = _pg_current_dep_id()
        if inst_id is None or dep_id is None:
            return False
        nombre_p, anio, semestre = _periodo_equivalente_pg(periodo_id)
        estado_extra = "" if incluir_historicas else "AND COALESCE(d.estado, 'Activa') = 'Activa'"
        df = _pg_read_dataframe(f"""
            SELECT 1 AS existe
            FROM designaciones d
            JOIN periodos p ON p.id = d.periodo_id
            WHERE d.institucion_id = %s
              AND d.departamento_id = %s
              AND p.institucion_id = d.institucion_id
              AND p.departamento_id IS NOT DISTINCT FROM d.departamento_id
              AND regexp_replace(COALESCE(d.cuil, ''), '[^0-9]', '', 'g') = %s
              AND EXISTS (
                  SELECT 1
                  FROM docentes doc_local
                  WHERE doc_local.institucion_id = d.institucion_id
                    AND doc_local.departamento_id IS NOT DISTINCT FROM d.departamento_id
                    AND regexp_replace(COALESCE(doc_local.cuil, ''), '[^0-9]', '', 'g') =
                        regexp_replace(COALESCE(d.cuil, ''), '[^0-9]', '', 'g')
              )
              AND (d.periodo_id = %s OR p.nombre = %s OR (p.anio = %s AND p.semestre = %s))
              {estado_extra}
            LIMIT 1
        """, [int(inst_id), int(dep_id), _clave_cuil(cuil), int(periodo_id), nombre_p, int(anio), int(semestre)])
        return not df.empty
    except Exception:
        return False


# --- entry l. 26775-26811
def es_docente_compartido_en_otros_departamentos(cuil, periodo_id=None):
    """Es compartido solo cuando hay designaciones reales en dos o más departamentos.

    La mera existencia del CUIL en otra base maestra ya no alcanza. Esto evita que
    una prueba eliminada siga mostrando al docente como compartido.
    """
    if not USE_POSTGRESQL or not str(cuil or "").strip():
        return False
    try:
        if periodo_id is None:
            periodo = get_periodo_abierto()
            periodo_id = periodo.get("id") if periodo else None
        if periodo_id is None:
            return False

        conn = get_conn()
        df_estado = pd.read_sql(
            "SELECT COALESCE(estado, '') AS estado FROM periodos WHERE id = ? LIMIT 1",
            conn,
            params=[periodo_id],
        )
        conn.close()
        lectura_historica = (not df_estado.empty and str(df_estado.iloc[0].get("estado") or "").strip().lower() == "cerrado")

        if not _docente_tiene_designacion_local_periodo_pg(cuil, periodo_id, incluir_historicas=lectura_historica):
            return False

        df = _df_designaciones_periodo_todos_departamentos_pg(
            cuil, periodo_id, lectura_historica=lectura_historica
        )
        if df is None or df.empty or "departamento_id" not in df.columns:
            return False
        departamentos = set(int(x) for x in df["departamento_id"].dropna().tolist())
        dep_actual = _pg_current_dep_id()
        return dep_actual is not None and int(dep_actual) in departamentos and len(departamentos) > 1
    except Exception:
        return False


# --- entry l. 26813
_get_productividad_docente_original = get_productividad_docente


# --- entry l. 26815-26926
def get_productividad_docente(cuil, periodo_id):
    if not USE_POSTGRESQL:
        return _get_productividad_docente_original(cuil, periodo_id)
    try:
        # En el departamento receptor, un prestado no computa como horas propias.
        if es_docente_prestado_local(cuil):
            return {
                "horas_contratadas": 0.0,
                "horas_en_comisiones": 0.0,
                "horas_en_comisiones_brutas": 0.0,
                "horas_en_investigacion": 0.0,
                "horas_utilizadas": 0.0,
                "horas_disponibles": 0.0,
                "porcentaje": 0.0,
                "horas_no_contadas_por_superposicion": 0.0,
                "docente_prestado": True,
            }

        # Solo se consolidan horas de otros departamentos cuando el docente tiene
        # una designación real en el departamento actual para este período. Si la
        # designación local fue eliminada por error, no debe heredarse la dedicación
        # que conserva en otro departamento.
        try:
            conn_estado_prod = get_conn()
            df_estado_prod = pd.read_sql(
                "SELECT COALESCE(estado, '') AS estado FROM periodos WHERE id = ? LIMIT 1",
                conn_estado_prod,
                params=[periodo_id],
            )
            conn_estado_prod.close()
            periodo_historico_prod = (
                not df_estado_prod.empty
                and str(df_estado_prod.iloc[0].get("estado") or "").strip().lower() == "cerrado"
            )
        except Exception:
            periodo_historico_prod = False

        if not _docente_tiene_designacion_local_periodo_pg(
            cuil, periodo_id, incluir_historicas=periodo_historico_prod
        ):
            return _get_productividad_docente_original(cuil, periodo_id)

        inst_id = _pg_current_inst_id()
        periodo_nombre, anio, semestre = _periodo_equivalente_pg(periodo_id)

        df = _pg_read_dataframe("""
            SELECT
                COALESCE((
                    SELECT SUM(d.horas)
                    FROM designaciones d
                    LEFT JOIN periodos pd ON pd.id = d.periodo_id
                    WHERE regexp_replace(COALESCE(d.cuil, ''), '[^0-9]', '', 'g') = %s
                      AND d.institucion_id = %s
                      AND d.estado = 'Activa'
                      AND (d.periodo_id = %s OR pd.nombre = %s OR (pd.anio = %s AND pd.semestre = %s))
                ), 0) AS horas_contratadas,
                COALESCE((
                    SELECT SUM(a.horas_asignadas)
                    FROM asignaciones_docentes_comision a
                    JOIN comisiones co ON co.id = a.comision_id
                    LEFT JOIN periodos pc ON pc.id = co.periodo_id
                    WHERE regexp_replace(COALESCE(a.cuil, ''), '[^0-9]', '', 'g') = %s
                      AND co.institucion_id = %s
                      AND COALESCE(a.estado, 'Activa') = 'Activa'
                      AND (co.periodo_id = %s OR pc.nombre = %s OR (pc.anio = %s AND pc.semestre = %s))
                ), 0) AS horas_en_comisiones_brutas,
                COALESCE((
                    SELECT SUM(i.horas_asignadas)
                    FROM investigacion_docente i
                    LEFT JOIN periodos pi ON pi.id = i.periodo_id
                    WHERE regexp_replace(COALESCE(i.cuil, ''), '[^0-9]', '', 'g') = %s
                      AND i.institucion_id = %s
                      AND COALESCE(i.estado_asignacion, 'Activa') = 'Activa'
                      AND (i.periodo_id = %s OR pi.nombre = %s OR (pi.anio = %s AND pi.semestre = %s))
                ), 0) AS horas_en_investigacion
        """, [
            _clave_cuil(cuil), int(inst_id), periodo_id, periodo_nombre, anio, semestre,
            _clave_cuil(cuil), int(inst_id), periodo_id, periodo_nombre, anio, semestre,
            _clave_cuil(cuil), int(inst_id), periodo_id, periodo_nombre, anio, semestre,
        ])
        contratadas = float(df.iloc[0]["horas_contratadas"] or 0) if not df.empty else 0.0
        # En períodos cerrados, las designaciones pueden quedar finalizadas por
        # cierre técnico. Si la consulta de activas da 0, se usa la misma foto
        # histórica que muestra el resumen docente para no romper productividad.
        if contratadas <= 0:
            try:
                resumen_periodo = get_resumen_actual_periodo_docente(cuil, periodo_id)
                horas_resumen = float(resumen_periodo.get("horas_actuales") or 0)
                if horas_resumen > 0:
                    contratadas = horas_resumen
            except Exception:
                pass
        comisiones_brutas = float(df.iloc[0]["horas_en_comisiones_brutas"] or 0) if not df.empty else 0.0
        # Antes se usaba comisiones_brutas también como horas únicas. Eso hacía que
        # "Hs no contadas por superposición" diera 0 aunque el sistema detectara solapes.
        comisiones_unicas = calcular_horas_comisiones_unicas_docente_pg_global(cuil, periodo_id)
        investigacion = float(df.iloc[0]["horas_en_investigacion"] or 0) if not df.empty else 0.0
        utilizadas = comisiones_unicas + investigacion
        disponibles = contratadas - utilizadas
        porcentaje = round((utilizadas / contratadas * 100), 2) if contratadas > 0 else 0.0
        return {
            "horas_contratadas": contratadas,
            "horas_en_comisiones": comisiones_unicas,
            "horas_en_comisiones_brutas": comisiones_brutas,
            "horas_en_investigacion": investigacion,
            "horas_utilizadas": utilizadas,
            "horas_disponibles": disponibles,
            "porcentaje": porcentaje,
            "horas_no_contadas_por_superposicion": max(round(comisiones_brutas - comisiones_unicas, 2), 0.0)
        }
    except Exception:
        return _get_productividad_docente_original(cuil, periodo_id)


# --- entry l. 26929
_get_plantel_periodo_original = get_plantel_periodo


# --- entry l. 26931-26933
def _departamento_origen_desde_obs_prestado(obs):
    from analisis.motor.ref.extracted_batch01.docentes import _departamento_origen_desde_obs_prestado as _b01_core__departamento_origen_desde_obs_prestado
    return _b01_core__departamento_origen_desde_obs_prestado(obs)


# --- entry l. 26936-27046
def get_plantel_periodo(periodo_id):
    """Plantel del período con docentes propios + docentes prestados registrados localmente.

    Los prestados aparecen para gestión operativa del período, pero quedan
    identificados y no deben computar como plantel/designaciones propias.
    """
    df_base = _get_plantel_periodo_original(periodo_id)
    try:
        conn = get_conn()
        df_prest = pd.read_sql("""
            SELECT
                doc.cuil,
                doc.legajo,
                CASE
                    WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                    WHEN doc.nombre IS NOT NULL THEN doc.nombre
                    ELSE ''
                END AS nombre_completo,
                doc.titulo,
                COALESCE(doc.titulo_posgrado, '') AS titulo_posgrado,
                doc.email,
                doc.telefono,
                COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente,
                doc.fecha_alta,
                COALESCE(doc.observaciones, '') AS observaciones
            FROM docentes doc
            WHERE COALESCE(doc.estado, 'Activo') = 'Activo'
              AND COALESCE(doc.tipo_docente, 'Propio') = 'Prestado'
            ORDER BY doc.apellido, doc.nombres
        """, conn)
        conn.close()
        if df_prest.empty:
            return df_base
        if df_base is None or df_base.empty:
            columnas = [
                "cuil", "legajo", "nombre_completo", "titulo", "titulo_posgrado", "email", "telefono",
                "tipo_docente", "estado_operativo_periodo", "fecha_alta_periodo", "fecha_finalizacion_periodo",
                "designaciones_del_periodo", "designaciones_activas", "horas_activas",
                "horas_registradas_periodo", "detalle_designaciones"
            ]
            df_base = pd.DataFrame(columns=columnas)
        existentes = set(df_base.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).str.strip())
        rows = []
        for _, r in df_prest.iterrows():
            cuil = str(r.get("cuil") or "").strip()
            if not cuil or cuil in existentes:
                continue
            origen = _departamento_origen_desde_obs_prestado(r.get("observaciones", ""))
            # La designación NO se copia al departamento receptor. Se consulta en
            # el/los departamentos donde realmente revista el mismo CUIL y se usa
            # únicamente para mostrar su situación institucional.
            try:
                df_des_prest = get_designaciones_docente_periodo_todos_departamentos(cuil, periodo_id)
            except Exception:
                df_des_prest = pd.DataFrame()
            if df_des_prest is None:
                df_des_prest = pd.DataFrame()
            if not df_des_prest.empty and "estado" in df_des_prest.columns:
                df_des_prest_act = df_des_prest[
                    df_des_prest["estado"].fillna("").astype(str).str.strip().str.lower().eq("activa")
                ].copy()
            else:
                df_des_prest_act = pd.DataFrame()
            designaciones_periodo_prest = int(len(df_des_prest)) if not df_des_prest.empty else 0
            designaciones_activas_prest = int(len(df_des_prest_act)) if not df_des_prest_act.empty else 0
            horas_activas_prest = float(pd.to_numeric(
                df_des_prest_act.get("horas", pd.Series(dtype=float)), errors="coerce"
            ).fillna(0).sum()) if not df_des_prest_act.empty else 0.0
            detalle_partes_prest = []
            for _, rd in (df_des_prest_act if not df_des_prest_act.empty else df_des_prest).iterrows() if not df_des_prest.empty else []:
                dep_rd = limpiar_texto_tabla(rd.get("departamento", ""))
                cargo_rd = limpiar_texto_tabla(rd.get("cargo", ""))
                ded_rd = limpiar_texto_tabla(rd.get("dedicacion", ""))
                tipo_rd = limpiar_texto_tabla(rd.get("tipo_designacion", ""))
                hs_rd = _hora_numero(rd.get("horas", 0))
                txt_rd = " · ".join([x for x in [cargo_rd, ded_rd, tipo_rd, f"{hs_rd:g} hs" if hs_rd else ""] if x])
                if dep_rd:
                    txt_rd = f"{dep_rd}: {txt_rd}" if txt_rd else dep_rd
                if txt_rd and txt_rd not in detalle_partes_prest:
                    detalle_partes_prest.append(txt_rd)
            detalle = "DOCENTE PRESTADO"
            if origen:
                detalle += f" desde {origen}"
            if detalle_partes_prest:
                detalle += " | Designación institucional: " + " / ".join(detalle_partes_prest)
            else:
                detalle += " | Sin designación institucional encontrada para el período"
            detalle += ". No computa como designación propia del departamento receptor."
            rows.append({
                "cuil": cuil,
                "legajo": r.get("legajo", ""),
                "nombre_completo": r.get("nombre_completo", ""),
                "titulo": r.get("titulo", ""),
                "titulo_posgrado": r.get("titulo_posgrado", ""),
                "email": r.get("email", ""),
                "telefono": r.get("telefono", ""),
                "tipo_docente": "Prestado",
                "estado_operativo_periodo": "Docente prestado en el período",
                "fecha_alta_periodo": r.get("fecha_alta", ""),
                "fecha_finalizacion_periodo": "",
                "designaciones_del_periodo": designaciones_periodo_prest,
                "designaciones_activas": designaciones_activas_prest,
                "horas_activas": round(horas_activas_prest, 2),
                "horas_registradas_periodo": round(horas_activas_prest, 2),
                "detalle_designaciones": detalle,
            })
        if rows:
            df_base = pd.concat([df_base, pd.DataFrame(rows)], ignore_index=True)
        return df_base
    except Exception:
        return df_base


# --- entry l. 27049
_get_metricas_analisis_periodo_original = get_metricas_analisis_periodo


# --- entry l. 27051-27063
def get_metricas_analisis_periodo(periodo_id):
    datos = _get_metricas_analisis_periodo_original(periodo_id)
    try:
        df_plantel = datos.get("df_plantel", pd.DataFrame())
        if df_plantel is not None and not df_plantel.empty and "tipo_docente" in df_plantel.columns:
            propios = df_plantel[df_plantel["tipo_docente"].fillna("Propio").astype(str).str.strip() != "Prestado"].copy()
            datos["docentes_activos"] = int((propios["estado_operativo_periodo"] == "Activo en el período").sum()) if not propios.empty else 0
        df_asig = datos.get("df_asig", pd.DataFrame())
        if df_asig is not None and not df_asig.empty and "tipo_docente" in df_asig.columns:
            datos["docentes_prestados_recibidos"] = int(df_asig[df_asig["tipo_docente"].fillna("Propio").astype(str).str.strip() == "Prestado"]["cuil"].dropna().nunique())
    except Exception:
        pass
    return datos


# --- entry l. 27069
_get_productividad_docente_antes_extension = get_productividad_docente


# --- entry l. 27071-27098
def get_productividad_docente(cuil, periodo_id):
    datos = dict(_get_productividad_docente_antes_extension(cuil, periodo_id) or {})
    horas_extension = 0.0
    try:
        todos = False
        if USE_POSTGRESQL:
            try:
                todos = _docente_tiene_designacion_local_periodo_pg(cuil, periodo_id, incluir_historicas=False)
            except Exception:
                todos = False
        df_ext = get_extension_docente(
            cuil=cuil, periodo_id=periodo_id,
            todos_departamentos=bool(USE_POSTGRESQL and todos),
        )
        if df_ext is not None and not df_ext.empty:
            horas_extension = float(pd.to_numeric(df_ext.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    except Exception:
        horas_extension = 0.0

    datos["horas_en_extension"] = round(horas_extension, 2)
    contratadas = float(datos.get("horas_contratadas", 0) or 0)
    comisiones = float(datos.get("horas_en_comisiones", 0) or 0)
    investigacion = float(datos.get("horas_en_investigacion", 0) or 0)
    utilizadas = comisiones + investigacion + horas_extension
    datos["horas_utilizadas"] = round(utilizadas, 2)
    datos["horas_disponibles"] = round(contratadas - utilizadas, 2)
    datos["porcentaje"] = round((utilizadas / contratadas * 100), 2) if contratadas > 0 else 0.0
    return datos


# --- entry l. 27101
_get_metricas_analisis_periodo_antes_extension = get_metricas_analisis_periodo


# --- entry l. 27103-27129
def get_metricas_analisis_periodo(periodo_id):
    datos = dict(_get_metricas_analisis_periodo_antes_extension(periodo_id) or {})
    horas_investigacion = 0.0
    horas_extension = 0.0
    try:
        df_inv = get_investigacion_docente(periodo_id=periodo_id)
        if df_inv is not None and not df_inv.empty:
            horas_investigacion = float(pd.to_numeric(df_inv.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    except Exception:
        pass
    try:
        df_ext = get_extension_docente(periodo_id=periodo_id)
        if df_ext is not None and not df_ext.empty:
            horas_extension = float(pd.to_numeric(df_ext.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    except Exception:
        pass
    datos["horas_investigacion"] = round(horas_investigacion, 2)
    datos["horas_extension"] = round(horas_extension, 2)
    porcentaje_no_lectivas = float(get_porcentaje_horas_no_lectivas_v148() or 0)
    horas_comisiones = float(datos.get("horas_comisiones", 0) or 0)
    horas_no_lectivas = round(horas_comisiones * porcentaje_no_lectivas / 100.0, 2)
    datos["porcentaje_horas_no_lectivas"] = round(porcentaje_no_lectivas, 2)
    datos["horas_no_lectivas"] = horas_no_lectivas
    datos["horas_academicas_utilizadas"] = round(
        horas_comisiones + horas_no_lectivas + horas_investigacion + horas_extension, 2
    )
    return datos


# --- entry l. 27132-27134
def _fecha_a_timestamp_seguro(valor):
    from analisis.motor.ref.extracted_batch04.fechas import _fecha_a_timestamp_seguro as _b04_core__fecha_a_timestamp_seguro
    return _b04_core__fecha_a_timestamp_seguro(valor)


# --- entry l. 27137-27139
def _hora_numero(valor):
    from analisis.motor.ref.extracted_batch04.numeros import _hora_numero as _b04_core__hora_numero
    return _b04_core__hora_numero(valor)


# --- entry l. 27157-27159
def _clave_designacion_desde_texto(texto):
    from analisis.motor.ref.domain.designaciones import _clave_designacion_desde_texto as _b05_core__clave_designacion_desde_texto
    return _b05_core__clave_designacion_desde_texto(texto)


# --- entry l. 27162-27164
def _clave_designacion_desde_row_designacion(row):
    from analisis.motor.ref.domain.designaciones import _clave_designacion_desde_row_designacion as _b05_core__clave_designacion_desde_row_designacion
    return _b05_core__clave_designacion_desde_row_designacion(row)


# --- entry l. 27167-27169
def _texto_row_movimiento(row, columnas=None):
    from analisis.motor.ref.extracted_batch04.movimientos import _texto_row_movimiento as _b04_core__texto_row_movimiento
    return _b04_core__texto_row_movimiento(row, columnas)


# --- entry l. 27177-27179
def _evento_es_baja_designacion(valor):
    from analisis.motor.ref.extracted_batch04.movimientos import _evento_es_baja_designacion as _b04_core__evento_es_baja_designacion
    return _b04_core__evento_es_baja_designacion(valor)


# --- entry l. 27182-27184
def _deduplicar_bajas_misma_designacion(df, evento_col="evento"):
    from analisis.motor.ref.domain.movimientos import _deduplicar_bajas_misma_designacion as _b05_core__deduplicar_bajas_misma_designacion
    return _b05_core__deduplicar_bajas_misma_designacion(df, evento_col)


# --- entry l. 27192-27194
def _hay_baja_en_periodo_en_movimientos(df_movimientos, evento_col="evento"):
    from analisis.motor.ref.domain.movimientos import _hay_baja_en_periodo_en_movimientos as _b05_core__hay_baja_en_periodo_en_movimientos
    return _b05_core__hay_baja_en_periodo_en_movimientos(df_movimientos, evento_col)


# --- entry l. 27263-27265
def _resumen_cambio_cargo_limpio(detalle):
    from analisis.motor.ref.domain.movimientos import _resumen_cambio_cargo_limpio as _b05_core__resumen_cambio_cargo_limpio
    return _b05_core__resumen_cambio_cargo_limpio(detalle)


# --- entry l. 27274-27276
def _df_designaciones_estado_final_operativo_periodo(df_all, fecha_inicio_periodo, fecha_fin_periodo, df_mov=None):
    from analisis.motor.ref.domain.analisis_periodo import _df_designaciones_estado_final_operativo_periodo as _b05_core__df_designaciones_estado_final_operativo_periodo
    return _b05_core__df_designaciones_estado_final_operativo_periodo(df_all, fecha_inicio_periodo, fecha_fin_periodo, df_mov)


# --- entry l. 27284-27286
def _balance_horas_periodo_docente(df_all, df_mov, fecha_inicio_periodo, fecha_fin_periodo=None, horas_actuales_visuales=0, horas_inicio_override=None):
    from analisis.motor.ref.domain.analisis_periodo import _balance_horas_periodo_docente as _b05_core__balance_horas_periodo_docente
    return _b05_core__balance_horas_periodo_docente(df_all, df_mov, fecha_inicio_periodo, fecha_fin_periodo, horas_actuales_visuales, horas_inicio_override)


# --- entry l. 27288-27290
def _df_designaciones_vigentes_durante_periodo(df_all, fecha_inicio_periodo, fecha_fin_periodo):
    from analisis.motor.ref.domain.analisis_periodo import _df_designaciones_vigentes_durante_periodo as _b05_core__df_designaciones_vigentes_durante_periodo
    return _b05_core__df_designaciones_vigentes_durante_periodo(df_all, fecha_inicio_periodo, fecha_fin_periodo)


# --- entry l. 27294-27338
def _df_designaciones_periodo_todos_departamentos_pg(cuil, periodo_id, lectura_historica=False, fecha_inicio_periodo="", fecha_fin_periodo=""):
    """Trae la foto de designaciones del docente en todos los departamentos para el mismo período académico.

    Se usa para docentes compartidos: el resumen docente debe mostrar qué cargo y
    cuántas horas tiene en cada departamento. Para períodos cerrados reconstruye
    la foto histórica por fechas, sin interpretar la finalización técnica como 0 hs.
    """
    if not USE_POSTGRESQL or not str(cuil or "").strip():
        return pd.DataFrame()
    try:
        inst_id = _pg_current_inst_id()
        periodo_nombre, anio, semestre = _periodo_equivalente_pg(periodo_id)
        df = _pg_read_dataframe("""
            SELECT
                d.cargo, d.dedicacion, d.horas, d.tipo_designacion, d.estado,
                d.fecha_desde, d.fecha_hasta, COALESCE(NULLIF(d.fecha_hasta_prevista,''), d.fecha_hasta) AS fecha_hasta_prevista,
                d.fecha_finalizacion_efectiva, d.fecha_registro_finalizacion, d.motivo_finalizacion, d.departamento_id,
                COALESCE(dep.nombre, 'Sin departamento') AS departamento
            FROM designaciones d
            JOIN periodos p ON p.id = d.periodo_id
            LEFT JOIN departamentos dep ON dep.id = d.departamento_id
            WHERE regexp_replace(COALESCE(d.cuil, ''), '[^0-9]', '', 'g') = %s
              AND d.institucion_id = %s
              AND p.institucion_id = d.institucion_id
              AND p.departamento_id IS NOT DISTINCT FROM d.departamento_id
              AND EXISTS (
                  SELECT 1
                  FROM docentes doc_local
                  WHERE doc_local.institucion_id = d.institucion_id
                    AND doc_local.departamento_id IS NOT DISTINCT FROM d.departamento_id
                    AND regexp_replace(COALESCE(doc_local.cuil, ''), '[^0-9]', '', 'g') =
                        regexp_replace(COALESCE(d.cuil, ''), '[^0-9]', '', 'g')
              )
              AND (d.periodo_id = %s OR p.nombre = %s OR (p.anio = %s AND p.semestre = %s))
            ORDER BY dep.nombre, d.cargo, d.dedicacion, d.tipo_designacion, d.fecha_desde
        """, [_clave_cuil(cuil), int(inst_id), int(periodo_id), periodo_nombre, int(anio), int(semestre)])
        if df is None or df.empty:
            return pd.DataFrame()
        if lectura_historica:
            return _df_designaciones_vigentes_durante_periodo(df, fecha_inicio_periodo, fecha_fin_periodo)
        if "estado" in df.columns:
            return df[df["estado"].fillna("").astype(str).str.strip().str.lower() == "activa"].copy()
        return df.copy()
    except Exception:
        return pd.DataFrame()


# --- entry l. 27341-27343
def _resumen_departamentos_desde_designaciones_df(df_designaciones):
    from analisis.motor.ref.domain.analisis_periodo import _resumen_departamentos_desde_designaciones_df as _b05_core__resumen_departamentos_desde_designaciones_df
    return _b05_core__resumen_departamentos_desde_designaciones_df(df_designaciones)


# --- entry l. 27346-27366
def _nombre_departamento_actual_v227():
    """Nombre físico del departamento actual, resuelto por ID y no por texto de sesión."""
    if not USE_POSTGRESQL:
        try:
            return limpiar_texto_tabla(_departamento_actual_operativo_nombre())
        except Exception:
            return ""
    try:
        inst_id = _pg_current_inst_id()
        dep_id = _pg_current_dep_id()
        if inst_id is None or dep_id is None:
            return ""
        df_dep = _pg_read_dataframe(
            "SELECT nombre FROM departamentos WHERE institucion_id=%s AND id=%s LIMIT 1",
            [int(inst_id), int(dep_id)],
        )
        if df_dep is not None and not df_dep.empty:
            return limpiar_texto_tabla(df_dep.iloc[0].get("nombre", ""))
    except Exception:
        pass
    return ""


# --- entry l. 27369-27421
def _designaciones_locales_resumen_v227(cuil, periodo_id):
    """Lee DIRECTO de PostgreSQL las designaciones del CUIL en ESTE departamento/período.

    No usa get_designaciones() ni su caché. De esta forma la tarjeta del Resumen y
    la pestaña Designaciones comparten la misma identidad física: institución,
    departamento y periodo_id.
    """
    if periodo_id is None or not str(cuil or "").strip():
        return pd.DataFrame()
    if not USE_POSTGRESQL:
        try:
            df = get_designaciones(periodo_id)
            if df is None or df.empty:
                return pd.DataFrame()
            claves = df.get("cuil", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
            return df[claves.eq(_clave_cuil(cuil))].copy().reset_index(drop=True)
        except Exception:
            return pd.DataFrame()

    try:
        inst_id = _pg_current_inst_id()
        dep_id = _pg_current_dep_id()
        if inst_id is None or dep_id is None:
            return pd.DataFrame()
        return _pg_read_dataframe("""
            SELECT
                d.id, d.cuil, d.periodo_id, d.departamento_id,
                COALESCE(dep.nombre, '') AS departamento,
                p.nombre AS periodo,
                d.cargo, d.dedicacion, d.horas, d.tipo_designacion, d.estado,
                d.fecha_desde, d.fecha_hasta,
                COALESCE(NULLIF(d.fecha_hasta_prevista,''), d.fecha_hasta) AS fecha_hasta_prevista,
                d.fecha_finalizacion_efectiva, d.fecha_registro_finalizacion,
                d.motivo_finalizacion, COALESCE(d.observaciones, '') AS observaciones,
                COALESCE(d.numero_resolucion, '') AS numero_resolucion,
                COALESCE(d.funcion_no_docente, 0) AS funcion_no_docente,
                COALESCE(d.texto_funcion_no_docente, '') AS texto_funcion_no_docente
            FROM designaciones d
            JOIN periodos p
              ON p.id = d.periodo_id
             AND p.institucion_id = d.institucion_id
             AND p.departamento_id IS NOT DISTINCT FROM d.departamento_id
            LEFT JOIN departamentos dep
              ON dep.id = d.departamento_id
             AND dep.institucion_id = d.institucion_id
            WHERE d.institucion_id = %s
              AND d.departamento_id = %s
              AND d.periodo_id = %s
              AND regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g') = %s
            ORDER BY d.fecha_desde, d.id
        """, [int(inst_id), int(dep_id), int(periodo_id), _clave_cuil(cuil)])
    except Exception:
        return pd.DataFrame()


# --- entry l. 27424-27505
def _fuente_designaciones_resumen_v227(cuil, periodo_id):
    """Fuente segura para Resumen docente.

    Regla:
    - Propio sin designación local: vacío, aunque exista una fila institucional
      con el mismo CUIL.
    - Prestado: puede usar la designación institucional de origen.
    - Compartido real: parte de una designación local y suma otros departamentos.
    - Si existe otro departamento con el MISMO nombre visible pero distinto ID,
      se lo considera una sombra administrativa y no se mezcla con el actual.
    """
    local = _designaciones_locales_resumen_v227(cuil, periodo_id)
    meta = {
        "tiene_local": bool(local is not None and not local.empty),
        "es_prestado": False,
        "es_compartido": False,
        "usa_institucional": False,
        "filas_sombra_omitidas": 0,
    }
    if not USE_POSTGRESQL:
        return (local if isinstance(local, pd.DataFrame) else pd.DataFrame()), meta

    try:
        meta["es_prestado"] = bool(es_docente_prestado_local(cuil))
    except Exception:
        meta["es_prestado"] = False

    # Un docente propio sin designación local no puede heredar una designación
    # de otro registro departamental/institucional.
    if not meta["es_prestado"] and not meta["tiene_local"]:
        return pd.DataFrame(columns=getattr(local, "columns", [])), meta

    try:
        meta["es_compartido"] = bool(
            meta["tiene_local"] and es_docente_compartido_en_otros_departamentos(cuil, periodo_id)
        )
    except Exception:
        meta["es_compartido"] = False

    if not (meta["es_prestado"] or meta["es_compartido"]):
        return (local if isinstance(local, pd.DataFrame) else pd.DataFrame()), meta

    try:
        inst = _get_designaciones_periodo_institucional_v149(cuil, periodo_id)
    except Exception:
        inst = pd.DataFrame()
    if inst is None or inst.empty:
        return (local if isinstance(local, pd.DataFrame) else pd.DataFrame()), meta

    # Protección específica contra departamentos homónimos con IDs diferentes.
    # Es una causa especialmente peligrosa porque visualmente parecen el mismo
    # departamento aunque una fila no pertenezca al tenant actual.
    try:
        dep_actual_id = int(_pg_current_dep_id())
    except Exception:
        dep_actual_id = None
    dep_actual_nombre = _nombre_departamento_actual_v227()
    clave_nombre_actual = normalizar_clave(dep_actual_nombre) if dep_actual_nombre else ""

    if dep_actual_id is not None and "departamento_id" in inst.columns:
        ids_inst = pd.to_numeric(inst["departamento_id"], errors="coerce")
        nombres_inst = inst.get("departamento", pd.Series("", index=inst.index)).fillna("").astype(str)
        sombras = (
            ~ids_inst.eq(dep_actual_id)
            & nombres_inst.map(normalizar_clave).eq(clave_nombre_actual)
            if clave_nombre_actual else pd.Series(False, index=inst.index)
        )
        meta["filas_sombra_omitidas"] = int(sombras.sum())
        inst = inst[~sombras].copy()

    # Para un compartido debe sobrevivir la designación del departamento actual.
    # Si no está, no se confía en la consolidación institucional.
    if meta["es_compartido"] and dep_actual_id is not None:
        ids_restantes = set(
            pd.to_numeric(inst.get("departamento_id", pd.Series(dtype=float)), errors="coerce")
            .dropna().astype(int).tolist()
        )
        if dep_actual_id not in ids_restantes:
            return (local if isinstance(local, pd.DataFrame) else pd.DataFrame()), meta

    meta["usa_institucional"] = True
    return inst.reset_index(drop=True), meta


# --- entry l. 27508-27712
def get_resumen_actual_periodo_docente(cuil, periodo_id):
    conn = get_conn()
    df_act = pd.read_sql("""
        SELECT cargo, dedicacion, horas, tipo_designacion, estado, fecha_desde, fecha_hasta,
               COALESCE(NULLIF(fecha_hasta_prevista,''), fecha_hasta) AS fecha_hasta_prevista,
               fecha_finalizacion_efectiva, fecha_registro_finalizacion, motivo_finalizacion
        FROM designaciones
        WHERE cuil = ? AND periodo_id = ? AND estado = 'Activa'
        ORDER BY cargo, dedicacion, tipo_designacion
    """, conn, params=[cuil, periodo_id])
    df_all = pd.read_sql("""
        SELECT cargo, dedicacion, horas, tipo_designacion, estado, fecha_desde, fecha_hasta,
               COALESCE(NULLIF(fecha_hasta_prevista,''), fecha_hasta) AS fecha_hasta_prevista,
               fecha_finalizacion_efectiva, fecha_registro_finalizacion, motivo_finalizacion
        FROM designaciones
        WHERE cuil = ? AND periodo_id = ?
        ORDER BY fecha_desde, id
    """, conn, params=[cuil, periodo_id])
    df_mov = pd.read_sql("""
        SELECT id, fecha, tipo_movimiento, detalle, COALESCE(horas_variacion, 0) AS horas_variacion
        FROM movimientos
        WHERE cuil = ? AND periodo_id = ?
        ORDER BY fecha, id
    """, conn, params=[cuil, periodo_id])
    df_periodo = pd.read_sql("""
        SELECT fecha_inicio, fecha_fin, COALESCE(estado, '') AS estado
        FROM periodos
        WHERE id = ?
        LIMIT 1
    """, conn, params=[periodo_id])
    conn.close()

    fecha_inicio_periodo = ""
    fecha_fin_periodo = ""
    estado_periodo = ""
    if df_periodo is not None and not df_periodo.empty:
        fecha_inicio_periodo = df_periodo.iloc[0].get("fecha_inicio", "")
        fecha_fin_periodo = df_periodo.iloc[0].get("fecha_fin", "")
        estado_periodo = str(df_periodo.iloc[0].get("estado", "") or "").strip()

    # Lectura histórica: si el período está cerrado, las designaciones pueden
    # figurar Finalizadas por cierre, pero para el resumen interesa mostrar lo
    # que el docente tuvo activo durante ese período.
    lectura_historica = estado_periodo.lower() == "cerrado"

    # v227: el Resumen usa como fuente de verdad la fila física del departamento
    # actual. Solo adopta la vista institucional para prestados o compartidos reales.
    _meta_fuente_resumen_v227 = {
        "tiene_local": bool(df_all is not None and not df_all.empty),
        "es_prestado": False,
        "es_compartido": False,
        "usa_institucional": False,
        "filas_sombra_omitidas": 0,
    }
    if USE_POSTGRESQL:
        try:
            df_fuente_v227, _meta_fuente_resumen_v227 = _fuente_designaciones_resumen_v227(cuil, periodo_id)
            df_all = df_fuente_v227.copy() if isinstance(df_fuente_v227, pd.DataFrame) else pd.DataFrame()
            if not df_all.empty:
                df_act = df_all[
                    df_all.get("estado", pd.Series(index=df_all.index, dtype=str))
                    .fillna("").astype(str).str.strip().str.casefold().eq("activa")
                ].copy()
            else:
                df_act = pd.DataFrame(columns=df_all.columns)

            # Los movimientos institucionales solo se mezclan cuando también se
            # permitió consolidar designaciones institucionales. Además se limitan
            # a los departamentos que quedaron en la fuente validada.
            if bool(_meta_fuente_resumen_v227.get("usa_institucional")):
                df_mov_inst = _get_movimientos_periodo_institucional_v149(cuil, periodo_id)
                if df_mov_inst is not None and not df_mov_inst.empty:
                    deps_validos = set(
                        pd.to_numeric(
                            df_all.get("departamento_id", pd.Series(dtype=float)),
                            errors="coerce",
                        ).dropna().astype(int).tolist()
                    )
                    if deps_validos and "departamento_id" in df_mov_inst.columns:
                        ids_mov = pd.to_numeric(df_mov_inst["departamento_id"], errors="coerce")
                        df_mov_inst = df_mov_inst[ids_mov.isin(deps_validos)].copy()
                    df_mov = df_mov_inst.copy()
        except Exception:
            # Ante cualquier duda se conserva exclusivamente la lectura local
            # obtenida con get_conn() al comienzo de la función.
            pass

    df_act_visual = df_act
    if lectura_historica:
        # Para períodos cerrados se muestra el estado operativo justo antes del cierre:
        # si hubo baja real, puede ser 0; si no, toma la designación vigente al fin del período.
        df_fin_operativo = _df_designaciones_estado_final_operativo_periodo(df_all, fecha_inicio_periodo, fecha_fin_periodo, df_mov)
        if df_fin_operativo is not None and not df_fin_operativo.empty:
            df_act_visual = df_fin_operativo
        else:
            df_act_visual = pd.DataFrame(columns=df_all.columns)

    horas_actuales = float(pd.to_numeric(df_act_visual["horas"], errors="coerce").fillna(0).sum()) if not df_act_visual.empty else 0.0
    cargos_actuales = []
    if not df_act_visual.empty:
        for _, r in df_act_visual.iterrows():
            cargo = limpiar_texto_tabla(r.get("cargo", ""))
            dedic = limpiar_texto_tabla(r.get("dedicacion", ""))
            tipo = limpiar_texto_tabla(r.get("tipo_designacion", ""))
            hs = _hora_numero(r.get("horas", 0))
            txt = f"{cargo}"
            if tipo:
                txt += f" ({tipo})"
            if dedic:
                txt += f" · {dedic}"
            txt += f" · {int(hs) if float(hs or 0).is_integer() else hs:g} hs"
            if txt not in cargos_actuales:
                cargos_actuales.append(txt)

    departamentos_periodo = []
    if USE_POSTGRESQL:
        try:
            # df_act_visual ya contiene la foto institucional del período. Se usa
            # tanto para prestados (un departamento de origen) como para compartidos.
            departamentos_periodo = _resumen_departamentos_desde_designaciones_df(df_act_visual)
            if departamentos_periodo:
                if len(departamentos_periodo) > 1:
                    cargos_actuales = [
                        f"{d.get('departamento')}: {d.get('cargo/s en el período')}"
                        for d in departamentos_periodo
                        if d.get('cargo/s en el período')
                    ]
                horas_actuales = round(sum(float(d.get('horas') or 0) for d in departamentos_periodo), 2)
        except Exception:
            departamentos_periodo = []

    horas_inicio_override = (
        get_horas_inicio_real_institucional_v149(periodo_id, cuil, df_all)
        if USE_POSTGRESQL and bool(_meta_fuente_resumen_v227.get("usa_institucional"))
        else get_horas_inicio_real_v132(periodo_id, cuil)
    )
    # Si es docente propio y no existe ninguna designación física local para el
    # período, tampoco se reutiliza una corrección histórica de horas como si
    # existiera una designación actual.
    if (
        USE_POSTGRESQL
        and not bool(_meta_fuente_resumen_v227.get("es_prestado"))
        and not bool(_meta_fuente_resumen_v227.get("tiene_local"))
    ):
        horas_inicio_override = 0.0
    balance_horas = _balance_horas_periodo_docente(
        df_all, df_mov, fecha_inicio_periodo, fecha_fin_periodo, horas_actuales,
        horas_inicio_override=horas_inicio_override
    )

    if lectura_historica:
        # En lectura histórica se muestra el resultado operativo previo al cierre,
        # no la finalización técnica posterior.
        horas_inicio = float(balance_horas.get("horas_inicio_operativo") or 0)
        horas_actuales = float(balance_horas.get("horas_resultado_operativo") or 0)
        # v139: el indicador superior muestra solo cambios reales de dedicación.
        # Una designación paralela nueva (p. ej. Interino + Concursado) modifica el
        # total de horas, pero no constituye un aumento de la designación previa.
        variacion_horas = float(balance_horas.get("variacion_operativa") or 0)
        baja_en_periodo = bool(balance_horas.get("baja_en_periodo_operativa"))
        estado_resumen_periodo = "Baja en el período" if baja_en_periodo else ""
    else:
        horas_inicio = float(balance_horas.get("horas_inicio_operativo") or 0)
        # v139: Aumento / disminución refleja únicamente movimientos reales de
        # dedicación. Altas de otras designaciones simultáneas se informan aparte.
        variacion_horas = float(balance_horas.get("variacion_operativa") or 0)
        baja_en_periodo = (float(horas_actuales or 0) <= 0) and (float(variacion_horas or 0) < 0 or _hay_baja_en_periodo_en_movimientos(df_mov, evento_col="tipo_movimiento"))
        estado_resumen_periodo = "Baja en el período" if baja_en_periodo else ""

    cambios_cargo = []
    if df_mov is not None and not df_mov.empty:
        for _, r in df_mov.iterrows():
            evento = str(r.get("tipo_movimiento", ""))
            detalle = str(r.get("detalle", ""))
            if "Cambio de cargo" in evento or "cambio de cargo" in detalle.lower():
                resumen_cambio = _resumen_cambio_cargo_limpio(detalle)
                dep_mov = limpiar_texto_tabla(r.get("departamento", ""))
                if dep_mov and len(departamentos_periodo) > 1 and resumen_cambio:
                    resumen_cambio = f"{dep_mov}: {resumen_cambio}"
                if resumen_cambio and resumen_cambio not in cambios_cargo:
                    cambios_cargo.append(resumen_cambio)
    if not cambios_cargo:
        cambios_cargo = ["Sin cambio de cargo registrado en este período."]

    return {
        "cargos_actuales": cargos_actuales,
        "horas_actuales": horas_actuales,
        "horas_inicio": float(horas_inicio or 0),
        "variacion_horas": variacion_horas,
        "cambios_cargo": cambios_cargo,
        "estado_resumen_periodo": estado_resumen_periodo,
        "baja_en_periodo": baja_en_periodo,
        "lectura_historica": lectura_historica,
        "departamentos_periodo": departamentos_periodo,
        "horas_total_departamentos": round(sum(float(d.get("horas") or 0) for d in departamentos_periodo), 2) if departamentos_periodo else horas_actuales,
        "balance_horas_periodo": balance_horas,
        "horas_inicio_corregidas": horas_inicio_override is not None,
        "horas_inicio_override": horas_inicio_override,
        "fuente_resumen_v227": dict(_meta_fuente_resumen_v227 or {}),
        "sin_designacion_local_periodo_v227": bool(
            USE_POSTGRESQL
            and not bool(_meta_fuente_resumen_v227.get("es_prestado"))
            and not bool(_meta_fuente_resumen_v227.get("tiene_local"))
        ),
    }


# --- entry l. 27849-27851
def _deptit_join_unicos(valores, sep=" / "):
    from analisis.motor.ref.common.text import _deptit_join_unicos as _b05_core__deptit_join_unicos
    return _b05_core__deptit_join_unicos(valores, sep)


# --- entry l. 27859-27862
def _clave_materia_conceptual_v137(fila):
    """Clave conceptual respetando la configuración explícita entre planes."""
    from analisis.motor.ref.domain.catalog_unlocked.materias import _clave_materia_conceptual_v137 as _b08_core__clave_materia_conceptual_v137
    return _b08_core__clave_materia_conceptual_v137(fila)


# --- entry l. 28015-28037
def _materias_para_comisiones_detalle():
    """Devuelve TODAS las filas de materias, sin filtrar por estado ni pertenencia al plan.

    La identidad histórica de una comisión se conserva por ``materia_id``. Por eso,
    para leer comisiones existentes no se puede partir de la oferta de materias activas:
    una materia puede haber sido quitada del plan o marcada inactiva y su ID debe seguir
    resolviendo código, nombre y demás metadatos históricos.
    """
    try:
        df = get_plan_estudio_todas()
    except Exception:
        df = pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    if "id" in df.columns and "materia_id" not in df.columns:
        df = df.rename(columns={"id": "materia_id"})
    if "estado" in df.columns and "estado_materia" not in df.columns:
        df = df.rename(columns={"estado": "estado_materia"})
    if "en_plan" not in df.columns:
        df["en_plan"] = 1
    return df


# --- entry l. 28040-28142
def _materias_para_comisiones_unificadas_y_mapa():
    """Devuelve dos tablas:
    - df_unicas: materias actualmente incluidas en al menos un plan, una fila por grupo conceptual configurado.
    - df_mapa: todos los materia_id (también los quitados de un plan) para conservar la trazabilidad histórica.
    """
    df = _materias_para_comisiones_detalle()
    columnas_base = [
        "materia_id", "codigo", "asignatura", "anio", "cuatrimestre",
        "carga_semanal", "carga_total", "estado_materia", "carrera", "escuela", "plan_version",
        "comparticion_modo", "comparticion_grupo", "en_plan"
    ]
    columnas_extra = [c for c in columnas_base if c != "en_plan"] + ["materia_ids", "cantidad_carreras", "cantidad_escuelas"]
    if df.empty:
        return pd.DataFrame(columns=columnas_extra), pd.DataFrame(columns=["materia_id_original"] + columnas_extra)

    df = df.copy()
    for col in columnas_base:
        if col not in df.columns:
            df[col] = 1 if col == "en_plan" else ""
    for col in ["codigo", "asignatura", "anio", "cuatrimestre", "estado_materia", "carrera", "escuela", "plan_version"]:
        df[col] = df[col].apply(limpiar_texto_tabla)
    df["comparticion_modo"] = df["comparticion_modo"].apply(_normalizar_modo_comparticion_v137)
    df["comparticion_grupo"] = df["comparticion_grupo"].fillna("").astype(str).str.strip()
    df["en_plan"] = pd.to_numeric(df["en_plan"], errors="coerce").fillna(1).astype(int)
    # Solo para la OFERTA de nuevas comisiones se exige materia activa + incluida en plan.
    # El mapa histórico, en cambio, conserva todas las filas y todos los IDs.
    estado_operativo = df["estado_materia"].fillna("Activa").astype(str).str.strip()
    estado_operativo = estado_operativo.replace("", "Activa").str.lower()
    df["_estado_activo_comision"] = estado_operativo.eq("activa")
    df["materia_id_original"] = pd.to_numeric(df["materia_id"], errors="coerce")
    df = df.dropna(subset=["materia_id_original"]).copy()
    if df.empty:
        return pd.DataFrame(columns=columnas_extra), pd.DataFrame(columns=["materia_id_original"] + columnas_extra)
    df["materia_id_original"] = df["materia_id_original"].astype(int)
    # v137: la clave conceptual puede ser automática, específica o un grupo seleccionado.
    df["_clave_unica"] = df.apply(_clave_materia_conceptual_v137, axis=1)

    def _armar_registro(g, materia_id_rep):
        codigo = _deptit_join_unicos(g["codigo"], sep=" / ")
        asignatura = _deptit_join_unicos(g["asignatura"], sep=" / ")
        carreras = _deptit_join_unicos(g["carrera"], sep=" / ")
        escuelas = _deptit_join_unicos(g["escuela"], sep=" / ")
        planes = _deptit_join_unicos(g["plan_version"], sep=" / ")
        anios = _deptit_join_unicos(g["anio"], sep=" / ")
        cuats = _deptit_join_unicos(g["cuatrimestre"], sep=" / ")
        cargas_sem = _deptit_join_unicos([str(x).replace('.0','') for x in g["carga_semanal"].fillna("").tolist()], sep=" / ")
        cargas_tot = _deptit_join_unicos([str(x).replace('.0','') for x in g["carga_total"].fillna("").tolist()], sep=" / ")
        estados = _deptit_join_unicos(g["estado_materia"], sep=" / ") or "Activa"
        modos = _deptit_join_unicos(g["comparticion_modo"], sep=" / ") or MODO_COMPARTICION_AUTO
        grupos = _deptit_join_unicos(g["comparticion_grupo"], sep=" / ")
        materia_ids = ",".join([str(int(x)) for x in sorted(g["materia_id_original"].dropna().astype(int).unique().tolist())])
        return {
            "materia_id": int(materia_id_rep),
            "codigo": codigo,
            "asignatura": asignatura,
            "anio": anios,
            "cuatrimestre": cuats,
            "carga_semanal": cargas_sem,
            "carga_total": cargas_tot,
            "estado_materia": estados,
            "carrera": carreras,
            "escuela": escuelas,
            "plan_version": planes,
            "comparticion_modo": modos,
            "comparticion_grupo": grupos,
            "materia_ids": materia_ids,
            "cantidad_carreras": int(g["carrera"].replace("", pd.NA).dropna().nunique()),
            "cantidad_escuelas": int(g["escuela"].replace("", pd.NA).dropna().nunique()),
        }

    registros = []
    mapa_rows = []
    for clave, g_all in df.groupby("_clave_unica", dropna=False, sort=False):
        g_all = g_all.sort_values(["escuela", "carrera", "plan_version", "anio", "cuatrimestre", "materia_id_original"], kind="stable")
        g_act = g_all[(g_all["en_plan"] == 1) & (g_all["_estado_activo_comision"] == True)].copy()

        # La oferta para nuevas comisiones usa únicamente apariciones activas que siguen en un plan.
        if not g_act.empty:
            materia_id_rep_act = int(g_act["materia_id_original"].iloc[0])
            registro_act = _armar_registro(g_act, materia_id_rep_act)
            registro_act["_clave_unica"] = clave
            registros.append(registro_act)
        else:
            materia_id_rep_act = int(g_all["materia_id_original"].iloc[0])

        # El mapa histórico conserva todos los IDs, incluso los quitados del plan.
        # Se usa la metadata completa del grupo para que las comisiones viejas sigan legibles.
        registro_hist = _armar_registro(g_all, materia_id_rep_act)
        registro_hist["_clave_unica"] = clave
        for mid in g_all["materia_id_original"].dropna().astype(int).unique().tolist():
            mr = dict(registro_hist)
            mr["materia_id_original"] = int(mid)
            mr["materia_id"] = int(mid)
            mr["materia_id_unificada"] = materia_id_rep_act
            mapa_rows.append(mr)

    df_unicas = pd.DataFrame(registros)
    df_mapa = pd.DataFrame(mapa_rows)
    if not df_unicas.empty:
        df_unicas = df_unicas.sort_values(["escuela", "codigo", "asignatura"], kind="stable").reset_index(drop=True)
    if not df_mapa.empty:
        df_mapa = df_mapa.reset_index(drop=True)
    return df_unicas, df_mapa


# --- entry l. 28144-28160
def get_materias_para_comisiones():
    """Materias para abrir comisiones, unificadas según su comportamiento entre planes.

    Por defecto se mantiene la regla código+nombre. Una aparición puede marcarse
    específica o pertenecer a un grupo explícito de planes sin cambiar sus códigos oficiales.
    """
    df_unicas, _ = _materias_para_comisiones_unificadas_y_mapa()
    columnas = [
        "materia_id", "codigo", "asignatura", "anio", "cuatrimestre",
        "carga_semanal", "carga_total", "estado_materia", "carrera", "escuela", "plan_version",
        "comparticion_modo", "comparticion_grupo",
        "materia_ids", "cantidad_carreras", "cantidad_escuelas"
    ]
    for col in columnas:
        if col not in df_unicas.columns:
            df_unicas[col] = ""
    return df_unicas[columnas].reset_index(drop=True)


# --- entry l. 28163-28178
def get_materia_comision(materia_id):
    """Devuelve la metadata unificada aun si la comisión quedó asociada a un materia_id viejo."""
    try:
        mid = int(materia_id)
    except Exception:
        return None
    df_unicas, df_mapa = _materias_para_comisiones_unificadas_y_mapa()
    if not df_mapa.empty:
        fila = df_mapa[pd.to_numeric(df_mapa["materia_id"], errors="coerce").astype("Int64") == mid]
        if not fila.empty:
            return fila.iloc[0].to_dict()
    if not df_unicas.empty:
        fila = df_unicas[pd.to_numeric(df_unicas["materia_id"], errors="coerce").astype("Int64") == mid]
        if not fila.empty:
            return fila.iloc[0].to_dict()
    return None


# --- entry l. 28477-28530
def get_materias_conceptuales_comision_v122(comision_id):
    """Devuelve los representantes conceptuales que integran una comisión.

    Sirve para editar una comisión multicódigo sin confundir las múltiples apariciones
    de una misma materia en diferentes planes con códigos/materias adicionales.
    """
    try:
        cid = int(comision_id)
    except Exception:
        return []

    ids = []
    try:
        df_v = _leer_vinculos_materias_comisiones_v118([cid], global_institucion=False)
        if isinstance(df_v, pd.DataFrame) and not df_v.empty:
            ids.extend(pd.to_numeric(df_v.get("materia_id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist())
    except Exception:
        pass

    principal = None
    try:
        conn = get_conn()
        df_c = pd.read_sql("SELECT materia_id FROM comisiones WHERE id = ? LIMIT 1", conn, params=[cid])
        conn.close()
        if not df_c.empty and pd.notna(df_c.iloc[0].get("materia_id")):
            principal = int(df_c.iloc[0]["materia_id"])
            ids.insert(0, principal)
    except Exception:
        pass

    representantes = []
    claves = set()
    principal_rep = None
    for mid in ids:
        info = get_materia_comision(mid) or {}
        if info:
            try:
                rep = int(info.get("materia_id_unificada") or info.get("materia_id") or mid)
            except Exception:
                rep = int(mid)
            clave = limpiar_texto_tabla(info.get("_clave_unica", "")) or _clave_materia_conceptual_v137(info) or f"ID:{rep}"
        else:
            rep = int(mid)
            clave = f"ID:{rep}"
        if principal is not None and int(mid) == int(principal):
            principal_rep = rep
        if clave in claves:
            continue
        claves.add(clave)
        representantes.append(rep)

    if principal_rep is not None and principal_rep in representantes:
        representantes = [principal_rep] + [x for x in representantes if x != principal_rep]
    return representantes


# --- entry l. 28624-28656
def _leer_vinculos_materias_comisiones_v118(comision_ids, global_institucion=False):
    ids = []
    for x in list(comision_ids or []):
        try:
            cid = int(x)
        except Exception:
            continue
        if cid not in ids:
            ids.append(cid)
    columnas = [
        "comision_id", "materia_id", "carrera_id_snapshot", "carrera_snapshot",
        "escuela_snapshot", "plan_version_snapshot", "anio_snapshot", "cuatrimestre_snapshot",
        "dictado_snapshot", "carga_semanal_snapshot", "carga_total_snapshot",
        "codigo_snapshot", "asignatura_snapshot", "fecha_vinculacion", "origen"
    ]
    if not ids:
        return pd.DataFrame(columns=columnas)
    if USE_POSTGRESQL and global_institucion:
        inst_id = _pg_current_inst_id()
        ph = ",".join(["%s"] * len(ids))
        return _pg_read_dataframe(
            f"SELECT {', '.join(columnas)} FROM comision_materias WHERE institucion_id=%s AND comision_id IN ({ph}) ORDER BY comision_id, materia_id",
            [int(inst_id)] + ids,
        )
    conn = get_conn()
    try:
        ph = ",".join(["?"] * len(ids))
        return pd.read_sql(
            f"SELECT {', '.join(columnas)} FROM comision_materias WHERE comision_id IN ({ph}) ORDER BY comision_id, materia_id",
            conn, params=ids,
        )
    finally:
        conn.close()


# --- entry l. 28659-28730
def metadata_explicita_comisiones_v118(comision_ids, global_institucion=False):
    """Combina identidad actual de la materia con carrera/plan fijados al abrir la comisión."""
    df_v = _leer_vinculos_materias_comisiones_v118(comision_ids, global_institucion=global_institucion)
    columnas = [
        "comision_id", "codigo_materia", "asignatura", "carrera", "escuela", "plan_version",
        "anio", "cuatrimestre", "dictado", "carga_semanal", "carga_total", "materia_ids"
    ]
    if df_v is None or df_v.empty:
        return pd.DataFrame(columns=columnas)

    df_det = _materias_para_comisiones_detalle()
    actuales = {}
    if isinstance(df_det, pd.DataFrame) and not df_det.empty:
        col_id = "materia_id" if "materia_id" in df_det.columns else "id" if "id" in df_det.columns else None
        if col_id:
            for _, r in df_det.iterrows():
                try:
                    actuales[int(r.get(col_id))] = r
                except Exception:
                    continue

    registros = []
    for cid, g in df_v.groupby("comision_id", dropna=False, sort=False):
        codigos, nombres = [], []
        carreras, escuelas, planes, anios, cuats, dictados, cs, ct = [], [], [], [], [], [], [], []
        mids = []
        for _, link in g.iterrows():
            try:
                mid = int(link.get("materia_id"))
            except Exception:
                continue
            mids.append(mid)
            act = actuales.get(mid)
            if act is not None:
                codigos.append(limpiar_texto_tabla(act.get("codigo", "")) or limpiar_texto_tabla(link.get("codigo_snapshot", "")))
                nombres.append(limpiar_texto_tabla(act.get("asignatura", "")) or limpiar_texto_tabla(link.get("asignatura_snapshot", "")))
            else:
                codigos.append(limpiar_texto_tabla(link.get("codigo_snapshot", "")))
                nombres.append(limpiar_texto_tabla(link.get("asignatura_snapshot", "")))

            def snap_o_actual(snap_col, actual_col):
                sv = limpiar_texto_tabla(link.get(snap_col, ""))
                if sv:
                    return sv
                if act is not None:
                    return limpiar_texto_tabla(act.get(actual_col, ""))
                return ""

            carreras.append(snap_o_actual("carrera_snapshot", "carrera"))
            escuelas.append(snap_o_actual("escuela_snapshot", "escuela"))
            planes.append(snap_o_actual("plan_version_snapshot", "plan_version"))
            anios.append(snap_o_actual("anio_snapshot", "anio"))
            cuats.append(snap_o_actual("cuatrimestre_snapshot", "cuatrimestre"))
            dictados.append(snap_o_actual("dictado_snapshot", "dictado"))
            cs.append(snap_o_actual("carga_semanal_snapshot", "carga_semanal"))
            ct.append(snap_o_actual("carga_total_snapshot", "carga_total"))

        registros.append({
            "comision_id": int(cid),
            "codigo_materia": _deptit_join_unicos(codigos, sep=" / "),
            "asignatura": _deptit_join_unicos(nombres, sep=" / "),
            "carrera": _deptit_join_unicos(carreras, sep=" / "),
            "escuela": _deptit_join_unicos(escuelas, sep=" / "),
            "plan_version": _deptit_join_unicos(planes, sep=" / "),
            "anio": _deptit_join_unicos(anios, sep=" / "),
            "cuatrimestre": _deptit_join_unicos(cuats, sep=" / "),
            "dictado": _deptit_join_unicos(dictados, sep=" / "),
            "carga_semanal": _deptit_join_unicos(cs, sep=" / "),
            "carga_total": _deptit_join_unicos(ct, sep=" / "),
            "materia_ids": ",".join(str(x) for x in sorted(set(mids))),
        })
    return pd.DataFrame(registros, columns=columnas)


# --- entry l. 28871-28976
def get_comisiones(periodo_id=None, solo_activas=False):
    """Listado de comisiones con planes congelados y opción curricular concreta cuando corresponde."""
    conn = get_conn()
    filtros, params = [], []
    if periodo_id is not None:
        filtros.append("co.periodo_id = ?"); params.append(periodo_id)
    if solo_activas:
        filtros.append("COALESCE(co.estado, 'Activa') = 'Activa'")
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    df = pd.read_sql(f"""
        SELECT
            co.id, co.periodo_id, p.nombre AS periodo,
            p.anio AS _periodo_anio, p.semestre AS _periodo_semestre,
            co.materia_id, co.opcion_curricular_id,
            COALESCE(co.materia_especifica, '') AS materia_especifica,
            co.nombre_comision, co.turno, co.sede, co.modalidad, co.estado,
            co.observaciones, co.fecha_creacion,
            COALESCE((SELECT SUM(h.horas) FROM horarios_comision h WHERE h.comision_id = co.id), 0) AS horas_horario,
            COALESCE((SELECT COUNT(*) FROM horarios_comision h WHERE h.comision_id = co.id), 0) AS cantidad_horarios,
            COALESCE((SELECT COUNT(*) FROM asignaciones_docentes_comision a WHERE a.comision_id = co.id AND COALESCE(a.estado, 'Activa') = 'Activa'), 0) AS docentes_asignados
        FROM comisiones co
        LEFT JOIN periodos p ON p.id = co.periodo_id
        {where}
    """, conn, params=params)
    conn.close()

    columnas = [
        "id", "periodo_id", "periodo", "materia_id", "opcion_curricular_id",
        "codigo_materia", "asignatura", "materia_especifica", "tipo_opcion_curricular",
        "escuela_oferente_opcion", "carrera", "escuela", "plan_version", "anio", "cuatrimestre",
        "dictado", "carga_semanal", "carga_total", "materia_ids", "nombre_comision", "turno",
        "sede", "modalidad", "estado", "observaciones", "fecha_creacion", "horas_horario",
        "cantidad_horarios", "docentes_asignados"
    ]
    if df.empty:
        return pd.DataFrame(columns=columnas)

    meta_exp = metadata_explicita_comisiones_v118(df["id"].tolist(), global_institucion=False)
    meta_exp_map = {}
    if isinstance(meta_exp, pd.DataFrame) and not meta_exp.empty:
        for _, r in meta_exp.iterrows():
            try: meta_exp_map[int(r.get("comision_id"))] = r.to_dict()
            except Exception: pass

    _, df_mapa = _materias_para_comisiones_unificadas_y_mapa()
    fallback = {}
    if isinstance(df_mapa, pd.DataFrame) and not df_mapa.empty:
        for _, r in df_mapa.iterrows():
            try: fallback[int(r.get("materia_id"))] = r.to_dict()
            except Exception: pass

    opciones_map = {}
    try:
        df_ops = get_opciones_curriculares_v120()
        if isinstance(df_ops, pd.DataFrame) and not df_ops.empty:
            for _, op in df_ops.iterrows():
                try: opciones_map[int(op.get("id"))] = op.to_dict()
                except Exception: pass
    except Exception:
        opciones_map = {}

    campos = [
        "codigo_materia", "asignatura", "carrera", "escuela", "plan_version", "anio",
        "cuatrimestre", "dictado", "carga_semanal", "carga_total", "materia_ids"
    ]
    for i, row in df.iterrows():
        try: cid = int(row.get("id"))
        except Exception: cid = None
        meta = meta_exp_map.get(cid) if cid is not None else None
        if not meta:
            try: mid = int(row.get("materia_id"))
            except Exception: mid = None
            fm = fallback.get(mid, {}) if mid is not None else {}
            meta = {
                "codigo_materia": fm.get("codigo", ""), "asignatura": fm.get("asignatura", ""),
                "carrera": fm.get("carrera", ""), "escuela": fm.get("escuela", ""),
                "plan_version": fm.get("plan_version", ""), "anio": fm.get("anio", ""),
                "cuatrimestre": fm.get("cuatrimestre", ""), "dictado": fm.get("dictado", ""),
                "carga_semanal": fm.get("carga_semanal", ""), "carga_total": fm.get("carga_total", ""),
                "materia_ids": fm.get("materia_ids", str(mid) if mid is not None else ""),
            }
        for campo in campos:
            df.at[i, campo] = meta.get(campo, "")

        try:
            oid_raw = row.get("opcion_curricular_id")
            oid = int(oid_raw) if oid_raw is not None and not pd.isna(oid_raw) else None
        except Exception:
            oid = None
        op = opciones_map.get(oid, {}) if oid is not None else {}
        df.at[i, "tipo_opcion_curricular"] = limpiar_texto_tabla(op.get("tipo", ""))
        df.at[i, "escuela_oferente_opcion"] = limpiar_texto_tabla(op.get("escuela_oferente", ""))
        if op:
            # El nombre actual de la opción se refleja sin perder el snapshot de carreras/planes.
            df.at[i, "materia_especifica"] = limpiar_texto_tabla(op.get("nombre", ""))

    for col in columnas:
        if col not in df.columns: df[col] = ""
    try:
        df = df.sort_values(
            ["_periodo_anio", "_periodo_semestre", "escuela", "codigo_materia", "asignatura", "nombre_comision"],
            ascending=[False, False, True, True, True, True], kind="stable"
        )
    except Exception:
        pass
    return df[columnas].reset_index(drop=True)


# --- entry l. 29029-29073
def get_asignaciones_comisiones_periodo(periodo_id=None):
    conn = get_conn()
    filtros = []
    params = []
    if periodo_id is not None:
        filtros.append("co.periodo_id = ?")
        params.append(periodo_id)
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    df = pd.read_sql(f"""
        SELECT
            a.comision_id,
            p.nombre AS periodo,
            co.materia_id,
            co.nombre_comision,
            co.turno,
            co.modalidad,
            a.cuil,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE a.cuil
            END AS docente,
            a.rol,
            a.horas_asignadas,
            COALESCE(a.estado, 'Activa') AS estado,
            COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente,
            a.observaciones
        FROM asignaciones_docentes_comision a
        LEFT JOIN comisiones co ON co.id = a.comision_id
        LEFT JOIN periodos p ON p.id = co.periodo_id
        LEFT JOIN docentes doc ON doc.cuil = a.cuil
        {where}
        ORDER BY co.id, docente, a.rol
    """, conn, params=params)
    conn.close()
    if df.empty:
        return df
    meta = get_comisiones(periodo_id=periodo_id, solo_activas=False)[["id", "codigo_materia", "asignatura", "materia_especifica", "carrera", "escuela", "plan_version"]].rename(columns={"id": "comision_id"})
    if not meta.empty:
        df = df.merge(meta, on="comision_id", how="left")
    cols = ["comision_id", "periodo", "codigo_materia", "asignatura", "materia_especifica", "carrera", "escuela", "plan_version", "nombre_comision", "turno", "modalidad", "cuil", "docente", "rol", "horas_asignadas", "estado", "tipo_docente", "observaciones"]
    for col in cols:
        if col not in df.columns:
            df[col] = ""
    return df[cols].reset_index(drop=True)


# --- entry l. 29076-29164
def get_comisiones_integradas_periodo(periodo_id=None):
    """Una fila por comisión con materia única, carreras/escuelas agregadas, horarios y docentes."""
    df_com = get_comisiones(periodo_id=periodo_id, solo_activas=False)
    if df_com is None or df_com.empty:
        return pd.DataFrame()

    conn = get_conn()
    filtros = []
    params = []
    if periodo_id is not None:
        filtros.append("co.periodo_id = ?")
        params.append(periodo_id)
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    df_h = pd.read_sql(f"""
        SELECT co.id AS comision_id, h.dia, h.hora_inicio, h.hora_fin, h.horas
        FROM horarios_comision h
        LEFT JOIN comisiones co ON co.id = h.comision_id
        {where}
        ORDER BY co.id,
            CASE h.dia
                WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3
                WHEN 'Jueves' THEN 4 WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6
                WHEN 'Domingo' THEN 7 ELSE 99 END,
            h.hora_inicio
    """, conn, params=params)
    df_a = pd.read_sql(f"""
        SELECT
            co.id AS comision_id,
            a.cuil,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE a.cuil
            END AS docente,
            COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente,
            a.rol,
            a.horas_asignadas,
            a.estado
        FROM asignaciones_docentes_comision a
        LEFT JOIN comisiones co ON co.id = a.comision_id
        LEFT JOIN docentes doc ON doc.cuil = a.cuil
        {where}
        ORDER BY co.id, docente, a.rol
    """, conn, params=params)
    conn.close()

    def _join_h(g):
        vals = []
        for _, r in g.iterrows():
            vals.append(f"{r.get('dia','')} {r.get('hora_inicio','')}-{r.get('hora_fin','')} ({r.get('horas',0)} hs)")
        return " | ".join(vals)

    def _join_a(g):
        vals = []
        for _, r in g.iterrows():
            tipo = f" - {r.get('tipo_docente')}" if r.get('tipo_docente') else ""
            vals.append(f"{r.get('docente','')} [{r.get('cuil','')}] - {r.get('rol','')} ({r.get('horas_asignadas',0)} hs{tipo})")
        return " | ".join(vals)

    if not df_h.empty:
        h_ag = df_h.groupby("comision_id", dropna=False).apply(_join_h).reset_index(name="horarios")
        hs_ag = df_h.groupby("comision_id", dropna=False)["horas"].sum().reset_index(name="horas_semanales_horario")
        df_com = df_com.merge(h_ag, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
        df_com = df_com.merge(hs_ag, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
    else:
        df_com["horarios"] = ""
        df_com["horas_semanales_horario"] = 0.0

    if not df_a.empty:
        a_ag = df_a.groupby("comision_id", dropna=False).apply(_join_a).reset_index(name="docentes_asignados_detalle")
        a_ct = df_a.groupby("comision_id", dropna=False)["cuil"].nunique().reset_index(name="cantidad_docentes")
        df_com = df_com.merge(a_ag, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
        df_com = df_com.merge(a_ct, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
    else:
        df_com["docentes_asignados_detalle"] = ""
        df_com["cantidad_docentes"] = 0

    df_mod_asig = get_modificaciones_asignaciones_periodo(periodo_id)
    if not df_mod_asig.empty:
        df_com = df_com.merge(df_mod_asig, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
    else:
        df_com["modificaciones_asignaciones_periodo"] = ""

    df_com["horarios"] = df_com["horarios"].fillna("")
    df_com["docentes_asignados_detalle"] = df_com["docentes_asignados_detalle"].fillna("")
    df_com["modificaciones_asignaciones_periodo"] = df_com["modificaciones_asignaciones_periodo"].fillna("")
    df_com["horas_semanales_horario"] = pd.to_numeric(df_com["horas_semanales_horario"], errors="coerce").fillna(0)
    df_com["cantidad_docentes"] = pd.to_numeric(df_com["cantidad_docentes"], errors="coerce").fillna(0).astype(int)
    return df_com.reset_index(drop=True)


# --- entry l. 29172-29182
def _cache_scope_comisiones_key():
    try:
        inst_id = _pg_current_inst_id() if USE_POSTGRESQL else 0
    except Exception:
        inst_id = 0
    try:
        dep_id = _pg_current_dep_id() if USE_POSTGRESQL else 0
    except Exception:
        dep_id = 0
    version = int(st.session_state.get("_comisiones_cache_version", 0) or 0)
    return str(DATABASE_URL), int(inst_id or 0), int(dep_id or 0), version


# --- entry l. 29185-29214
def limpiar_cache_comisiones_operativas():
    """Invalida caché de materias/comisiones después de cambios reales."""
    try:
        st.session_state["_comisiones_cache_version"] = int(st.session_state.get("_comisiones_cache_version", 0) or 0) + 1
    except Exception:
        pass
    # Los cambios de materias/planes también pueden alterar el catálogo de
    # espacios Optativa/Electiva; se invalida esa caché sin recalcular nada acá.
    try:
        limpiar_cache_opciones_curriculares_v127()
    except Exception:
        pass
    for fn_name in [
        "_materias_para_comisiones_unificadas_y_mapa_cache",
        "_get_comisiones_cache",
        "_get_comisiones_integradas_periodo_cache",
        "_get_horarios_comisiones_periodo_cache",
        "_get_asignaciones_comisiones_periodo_cache",
        "_get_horarios_comision_cache",
        "_get_asignaciones_comision_cache",
        "_get_docentes_activos_para_comisiones_cache",
        # v248: la lista de asignaturas y combinaciones depende directamente de las comisiones.
        "_inscriptos_asignaturas_periodo_cache_v248",
    ]:
        try:
            fn = globals().get(fn_name)
            if fn is not None and hasattr(fn, "clear"):
                fn.clear()
        except Exception:
            pass


# --- entry l. 29218
_materias_para_comisiones_unificadas_y_mapa_no_cache = _materias_para_comisiones_unificadas_y_mapa


# --- entry l. 29221-29223
def _materias_para_comisiones_unificadas_y_mapa_cache(db_url, inst_id, dep_id, version):
    df_unicas, df_mapa = _materias_para_comisiones_unificadas_y_mapa_no_cache()
    return df_unicas, df_mapa


# --- entry l. 29226-29229
def _materias_para_comisiones_unificadas_y_mapa():
    db_url, inst_id, dep_id, version = _cache_scope_comisiones_key()
    df_unicas, df_mapa = _materias_para_comisiones_unificadas_y_mapa_cache(db_url, inst_id, dep_id, version)
    return df_unicas.copy(), df_mapa.copy()


# --- entry l. 29232
_get_comisiones_no_cache_opt = get_comisiones


# --- entry l. 29235-29237
def _get_comisiones_cache(periodo_id, solo_activas, db_url, inst_id, dep_id, version):
    df = _get_comisiones_no_cache_opt(periodo_id=periodo_id, solo_activas=solo_activas)
    return df


# --- entry l. 29240-29243
def get_comisiones(periodo_id=None, solo_activas=False):
    db_url, inst_id, dep_id, version = _cache_scope_comisiones_key()
    df = _get_comisiones_cache(periodo_id, bool(solo_activas), db_url, inst_id, dep_id, version)
    return df.copy()


# --- entry l. 29246
_get_comisiones_integradas_periodo_no_cache_opt = get_comisiones_integradas_periodo


# --- entry l. 29249-29251
def _get_comisiones_integradas_periodo_cache(periodo_id, db_url, inst_id, dep_id, version):
    df = _get_comisiones_integradas_periodo_no_cache_opt(periodo_id=periodo_id)
    return df


# --- entry l. 29254-29257
def get_comisiones_integradas_periodo(periodo_id=None):
    db_url, inst_id, dep_id, version = _cache_scope_comisiones_key()
    df = _get_comisiones_integradas_periodo_cache(periodo_id, db_url, inst_id, dep_id, version)
    return df.copy()


# --- entry l. 29279-29281
def _normalizar_cargo_para_jerarquia(valor):
    from analisis.motor.ref.domain.designaciones import _normalizar_cargo_para_jerarquia as _b05_core__normalizar_cargo_para_jerarquia
    return _b05_core__normalizar_cargo_para_jerarquia(valor)


# --- entry l. 29284-29287
def _cargo_mas_alto(cargos):
    """Selecciona el cargo de mayor jerarquía; conserva un valor desconocido solo como último recurso."""
    from analisis.motor.ref.domain.catalog_unlocked.designaciones import _cargo_mas_alto as _b08_core__cargo_mas_alto
    return _b08_core__cargo_mas_alto(cargos)


# --- entry l. 29290-29292
def _extraer_departamento_origen_prestado(observaciones):
    from analisis.motor.ref.domain.designaciones import _extraer_departamento_origen_prestado as _b05_core__extraer_departamento_origen_prestado
    return _b05_core__extraer_departamento_origen_prestado(observaciones)


# --- entry l. 29295-29316
def _buscar_departamento_id_por_nombre(inst_id, nombre_departamento):
    if not USE_POSTGRESQL or not inst_id or not nombre_departamento:
        return None
    try:
        df = _pg_read_dataframe(
            "SELECT id, nombre FROM departamentos WHERE institucion_id = %s ORDER BY id",
            [int(inst_id)],
        )
        objetivo = normalizar_clave(nombre_departamento)
        if df.empty or not objetivo:
            return None
        exactos = df[df["nombre"].fillna("").astype(str).apply(normalizar_clave) == objetivo]
        if not exactos.empty:
            return int(exactos.iloc[0]["id"])
        parciales = df[df["nombre"].fillna("").astype(str).apply(
            lambda x: objetivo in normalizar_clave(x) or normalizar_clave(x) in objetivo
        )]
        if len(parciales) == 1:
            return int(parciales.iloc[0]["id"])
    except Exception:
        pass
    return None


# --- entry l. 29319-29460
def obtener_cargo_prioritario_docente_periodo(cuil, periodo_id, departamento_contexto_id=None):
    """Obtiene el cargo que debe usarse por defecto en una comisión.

    - Docente propio: designaciones activas del departamento de la comisión.
    - Docente prestado: designaciones activas de su departamento de origen.
    - Si hay varios cargos en ese departamento, devuelve el de mayor jerarquía.
    """
    cuil = limpiar_cuil(cuil)
    if not cuil or not periodo_id:
        return {"cargo": "", "departamento": "", "motivo": "Falta CUIL o período."}

    if not USE_POSTGRESQL:
        try:
            conn = get_conn()
            df = pd.read_sql(
                """
                SELECT cargo
                FROM designaciones
                WHERE cuil = ? AND periodo_id = ? AND estado = 'Activa'
                  AND COALESCE(TRIM(cargo), '') <> ''
                """,
                conn,
                params=[cuil, int(periodo_id)],
            )
            conn.close()
            cargo = _cargo_mas_alto(df["cargo"].tolist() if not df.empty else [])
            return {
                "cargo": cargo,
                "departamento": _departamento_actual_operativo_nombre() if cargo else "",
                "motivo": "Cargo activo del departamento actual." if cargo else "No se encontró designación activa.",
            }
        except Exception as e:
            return {"cargo": "", "departamento": "", "motivo": str(e)}

    try:
        inst_id = _pg_current_inst_id()
        dep_contexto = int(departamento_contexto_id or _pg_current_dep_id())
        if inst_id is None or dep_contexto is None:
            return {"cargo": "", "departamento": "", "motivo": "No se pudo determinar institución/departamento."}

        df_doc = _pg_read_dataframe(
            """
            SELECT COALESCE(tipo_docente, 'Propio') AS tipo_docente,
                   COALESCE(observaciones, '') AS observaciones
            FROM docentes
            WHERE institucion_id = %s AND departamento_id = %s AND cuil = %s
            ORDER BY id
            LIMIT 1
            """,
            [int(inst_id), int(dep_contexto), cuil],
        )
        tipo = str(df_doc.iloc[0].get("tipo_docente") or "Propio") if not df_doc.empty else "Propio"
        obs = str(df_doc.iloc[0].get("observaciones") or "") if not df_doc.empty else ""
        es_prestado = normalizar_clave(tipo) == "PRESTADO"

        dep_designacion = dep_contexto
        dep_origen_nombre = ""
        if es_prestado:
            dep_origen_nombre = _extraer_departamento_origen_prestado(obs)
            dep_origen_id = _buscar_departamento_id_por_nombre(inst_id, dep_origen_nombre)
            dep_designacion = dep_origen_id

        params = [int(periodo_id), cuil, int(inst_id)]
        filtro_dep = ""
        if dep_designacion is not None:
            filtro_dep = " AND d.departamento_id = %s"
            params.append(int(dep_designacion))
        elif es_prestado:
            filtro_dep = " AND COALESCE(d.departamento_id, -1) <> %s"
            params.append(int(dep_contexto))

        df_cargos = _pg_read_dataframe(
            f"""
            WITH pr AS (
                SELECT id, institucion_id, nombre, anio, semestre
                FROM periodos
                WHERE id = %s
                LIMIT 1
            )
            SELECT d.cargo, d.departamento_id, COALESCE(dep.nombre, '') AS departamento
            FROM designaciones d
            JOIN periodos p ON p.id = d.periodo_id
            JOIN pr ON {_condicion_periodo_equivalente_sql('p', 'pr')}
            LEFT JOIN departamentos dep ON dep.id = d.departamento_id
            WHERE d.cuil = %s
              AND d.institucion_id = %s
              AND d.estado = 'Activa'
              AND COALESCE(TRIM(d.cargo), '') <> ''
              {filtro_dep}
            """,
            params,
        )

        # Respaldo para prestados antiguos cuyo departamento de origen no quedó
        # escrito de forma reconocible: toma sus designaciones fuera del receptor.
        if df_cargos.empty and es_prestado and dep_designacion is not None:
            df_cargos = _pg_read_dataframe(
                f"""
                WITH pr AS (
                    SELECT id, institucion_id, nombre, anio, semestre
                    FROM periodos WHERE id = %s LIMIT 1
                )
                SELECT d.cargo, d.departamento_id, COALESCE(dep.nombre, '') AS departamento
                FROM designaciones d
                JOIN periodos p ON p.id = d.periodo_id
                JOIN pr ON {_condicion_periodo_equivalente_sql('p', 'pr')}
                LEFT JOIN departamentos dep ON dep.id = d.departamento_id
                WHERE d.cuil = %s
                  AND d.institucion_id = %s
                  AND d.estado = 'Activa'
                  AND COALESCE(TRIM(d.cargo), '') <> ''
                  AND COALESCE(d.departamento_id, -1) <> %s
                """,
                [int(periodo_id), cuil, int(inst_id), int(dep_contexto)],
            )

        if df_cargos.empty:
            origen_txt = f" en {dep_origen_nombre}" if dep_origen_nombre else ""
            return {
                "cargo": "",
                "departamento": dep_origen_nombre,
                "motivo": f"No se encontró una designación activa{origen_txt} para el período de la comisión.",
            }

        # Si por un dato heredado aparecen designaciones de más de un departamento,
        # primero selecciona el departamento esperado; en el respaldo, el cargo más
        # alto disponible y conserva el departamento de esa fila.
        df_cargos = df_cargos.copy()
        df_cargos["cargo_canonico"] = df_cargos["cargo"].apply(_normalizar_cargo_para_jerarquia)
        prioridad = {cargo: i for i, cargo in enumerate(ORDEN_JERARQUICO_CARGOS_COMISION)}
        df_cargos["_prioridad"] = df_cargos["cargo_canonico"].map(prioridad).fillna(999)
        df_cargos = df_cargos.sort_values(["_prioridad", "departamento", "cargo_canonico"])
        elegido = df_cargos.iloc[0]
        cargo = str(elegido.get("cargo_canonico") or elegido.get("cargo") or "").strip()
        departamento = str(elegido.get("departamento") or dep_origen_nombre or "").strip()
        return {
            "cargo": cargo,
            "departamento": departamento,
            "motivo": f"Cargo activo de {departamento}." if departamento else "Cargo activo detectado.",
        }
    except Exception as e:
        return {"cargo": "", "departamento": "", "motivo": f"No se pudo determinar el cargo: {e}"}


# --- entry l. 29755-29847
def diagnosticar_cargos_asignaciones_periodo(periodo_id):
    """Compara el cargo visible en comisiones con la designación activa del período.

    La revisión se limita estrictamente al período indicado, al departamento que
    está operando la aplicación y a asignaciones/comisiones activas. No modifica
    períodos anteriores ni otros departamentos.
    """
    resultado = {
        "periodo_id": int(periodo_id) if periodo_id is not None else None,
        "correctas": 0,
        "a_corregir": 0,
        "sin_resolver": 0,
        "detalle": pd.DataFrame(),
    }
    if periodo_id is None:
        return resultado

    conn = get_conn()
    try:
        df = pd.read_sql(
            """
            SELECT
                a.id AS asignacion_id,
                a.comision_id,
                a.cuil,
                COALESCE(a.rol, '') AS cargo_comision,
                COALESCE(co.nombre_comision, '') AS comision,
                co.periodo_id,
                co.departamento_id,
                CASE
                    WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL
                        THEN doc.apellido || ', ' || doc.nombres
                    WHEN doc.nombre IS NOT NULL THEN doc.nombre
                    ELSE a.cuil
                END AS docente
            FROM asignaciones_docentes_comision a
            JOIN comisiones co ON co.id = a.comision_id
            LEFT JOIN docentes doc ON doc.cuil = a.cuil
            WHERE co.periodo_id = ?
              AND COALESCE(a.estado, 'Activa') = 'Activa'
              AND COALESCE(co.estado, 'Activa') = 'Activa'
            ORDER BY docente, co.nombre_comision, a.id
            """,
            conn,
            params=[int(periodo_id)],
        )
    finally:
        conn.close()

    if df.empty:
        return resultado

    detalle = []
    for _, fila in df.iterrows():
        departamento_contexto = fila.get("departamento_id")
        try:
            departamento_contexto = int(departamento_contexto) if pd.notna(departamento_contexto) else None
        except Exception:
            departamento_contexto = None

        dato = obtener_cargo_prioritario_docente_periodo(
            fila.get("cuil"), int(periodo_id), departamento_contexto
        )
        cargo_correcto = limpiar_texto_tabla(dato.get("cargo", ""))
        cargo_actual = limpiar_texto_tabla(fila.get("cargo_comision", ""))

        actual_canonico = _normalizar_cargo_para_jerarquia(cargo_actual)
        correcto_canonico = _normalizar_cargo_para_jerarquia(cargo_correcto)

        if not cargo_correcto:
            estado = "Sin designación activa comprobable"
            resultado["sin_resolver"] += 1
        elif normalizar_clave(actual_canonico) == normalizar_clave(correcto_canonico):
            estado = "Correcto"
            resultado["correctas"] += 1
        else:
            estado = "Corregir"
            resultado["a_corregir"] += 1

        detalle.append({
            "Asignación ID": int(fila.get("asignacion_id")),
            "Comisión ID": int(fila.get("comision_id")),
            "Docente": limpiar_texto_tabla(fila.get("docente", "")),
            "CUIL": limpiar_cuil(fila.get("cuil", "")),
            "Comisión": limpiar_texto_tabla(fila.get("comision", "")),
            "Cargo actual en comisión": cargo_actual,
            "Cargo correcto según designación": cargo_correcto,
            "Estado": estado,
            "Detalle": limpiar_texto_tabla(dato.get("motivo", "")),
        })

    resultado["detalle"] = pd.DataFrame(detalle)
    return resultado


# --- entry l. 30037
_get_asignaciones_comisiones_periodo_no_cache_opt = get_asignaciones_comisiones_periodo


# --- entry l. 30040-30042
def _get_asignaciones_comisiones_periodo_cache(periodo_id, db_url, inst_id, dep_id, version):
    df = _get_asignaciones_comisiones_periodo_no_cache_opt(periodo_id=periodo_id)
    return df


# --- entry l. 30045-30048
def get_asignaciones_comisiones_periodo(periodo_id=None):
    db_url, inst_id, dep_id, version = _cache_scope_comisiones_key()
    df = _get_asignaciones_comisiones_periodo_cache(periodo_id, db_url, inst_id, dep_id, version)
    return df.copy()


# --- entry l. 30051
_get_horarios_comision_no_cache_opt = get_horarios_comision


# --- entry l. 30054-30056
def _get_horarios_comision_cache(comision_id, db_url, inst_id, dep_id, version):
    df = _get_horarios_comision_no_cache_opt(comision_id=comision_id)
    return df


# --- entry l. 30059-30062
def get_horarios_comision(comision_id=None):
    db_url, inst_id, dep_id, version = _cache_scope_comisiones_key()
    df = _get_horarios_comision_cache(comision_id, db_url, inst_id, dep_id, version)
    return df.copy()


# --- entry l. 30065
_get_asignaciones_comision_no_cache_opt = get_asignaciones_comision


# --- entry l. 30068-30070
def _get_asignaciones_comision_cache(comision_id, db_url, inst_id, dep_id, version):
    df = _get_asignaciones_comision_no_cache_opt(comision_id=comision_id)
    return df


# --- entry l. 30073-30076
def get_asignaciones_comision(comision_id=None):
    db_url, inst_id, dep_id, version = _cache_scope_comisiones_key()
    df = _get_asignaciones_comision_cache(comision_id, db_url, inst_id, dep_id, version)
    return df.copy()


# --- entry l. 30273-30275
def _hora_texto_v95(valor):
    from analisis.motor.ref.extracted_batch04.horarios import _hora_texto_v95 as _b04_core__hora_texto_v95
    return _b04_core__hora_texto_v95(valor)


# --- entry l. 30283-30285
def _minutos_v95(valor):
    from analisis.motor.ref.extracted_batch04.horarios import _minutos_v95 as _b04_core__minutos_v95
    return _b04_core__minutos_v95(valor)


# --- entry l. 30303-30346
def get_horarios_reales_asignacion(asignacion_id):
    """Franjas efectivamente cubiertas por una asignación.

    Compatibilidad: las asignaciones históricas sin horario personalizado siguen
    cubriendo automáticamente todos los horarios de la comisión, exactamente como
    funcionaba la aplicación antes de esta versión.
    """
    conn = get_conn()
    df_asig = pd.read_sql(
        "SELECT id, comision_id, COALESCE(usa_horario_personalizado, FALSE) AS usa_horario_personalizado FROM asignaciones_docentes_comision WHERE id=? LIMIT 1",
        conn, params=[int(asignacion_id)]
    )
    if df_asig.empty:
        conn.close()
        return pd.DataFrame(columns=["id", "asignacion_id", "horario_comision_id", "dia", "hora_inicio", "hora_fin", "horas", "observaciones"])
    personalizado = bool(df_asig.iloc[0].get("usa_horario_personalizado", False))
    comision_id = int(df_asig.iloc[0]["comision_id"])
    if personalizado:
        df = pd.read_sql("""
            SELECT id, asignacion_id, horario_comision_id, dia, hora_inicio, hora_fin, horas, observaciones
            FROM horarios_asignacion_docente_comision
            WHERE asignacion_id=?
            ORDER BY CASE dia
                WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3
                WHEN 'Jueves' THEN 4 WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6
                WHEN 'Domingo' THEN 7 ELSE 99 END, hora_inicio
        """, conn, params=[int(asignacion_id)])
        conn.close()
        return df
    conn.close()
    df = get_horarios_comision(comision_id)
    if df is None or df.empty:
        return pd.DataFrame(columns=["id", "asignacion_id", "horario_comision_id", "dia", "hora_inicio", "hora_fin", "horas", "observaciones"])
    out = pd.DataFrame({
        "id": [None] * len(df),
        "asignacion_id": [int(asignacion_id)] * len(df),
        "horario_comision_id": df["id"].tolist(),
        "dia": df["dia"].tolist(),
        "hora_inicio": df["hora_inicio"].tolist(),
        "hora_fin": df["hora_fin"].tolist(),
        "horas": df["horas"].tolist(),
        "observaciones": [""] * len(df),
    })
    return out


# --- entry l. 30494-30517
def _horarios_docente_local_v95(cuil, periodo_id, excluir_comision_id=None):
    conn = get_conn()
    filtro_ex = " AND co.id <> ?" if excluir_comision_id is not None else ""
    params = [str(cuil), int(periodo_id)] + ([int(excluir_comision_id)] if excluir_comision_id is not None else [])
    df_as = pd.read_sql(f"""
        SELECT a.id AS asignacion_id, a.cuil, a.rol, a.comision_id, co.materia_id,
               co.nombre_comision, co.turno, m.codigo AS codigo_materia, m.asignatura,
               COALESCE(co.materia_especifica, '') AS materia_especifica,
               COALESCE(c.nombre, m.carrera) AS carrera, COALESCE(c.escuela, m.escuela) AS escuela
        FROM asignaciones_docentes_comision a
        JOIN comisiones co ON co.id=a.comision_id
        LEFT JOIN materias m ON m.id=co.materia_id
        LEFT JOIN carreras c ON c.id=m.carrera_id
        WHERE a.cuil=? AND co.periodo_id=?
          AND COALESCE(a.estado,'Activa')='Activa' AND COALESCE(co.estado,'Activa')='Activa' {filtro_ex}
    """, conn, params=params)
    conn.close()
    rows = []
    for _, a in df_as.iterrows():
        dfh = get_horarios_reales_asignacion(int(a["asignacion_id"]))
        for _, h in dfh.iterrows():
            item = a.to_dict(); item.update({"dia": h.get("dia"), "hora_inicio": h.get("hora_inicio"), "hora_fin": h.get("hora_fin"), "horas": h.get("horas")})
            rows.append(item)
    return pd.DataFrame(rows)


# --- entry l. 30520-30523
def get_horarios_docente_periodo(cuil, periodo_id, excluir_comision_id=None):
    if USE_POSTGRESQL:
        return _get_horarios_docente_periodo_pg_global(cuil, periodo_id, excluir_comision_id=excluir_comision_id)
    return _horarios_docente_local_v95(cuil, periodo_id, excluir_comision_id=excluir_comision_id)


# --- entry l. 30526-30566
def _get_horarios_docente_periodo_pg_global(cuil, periodo_id, excluir_comision_id=None):
    if not USE_POSTGRESQL:
        return _horarios_docente_local_v95(cuil, periodo_id, excluir_comision_id)
    try:
        inst_id = _pg_current_inst_id(); periodo_nombre, anio, semestre = _periodo_equivalente_pg(periodo_id)
        filtro_ex = " AND co.id <> %s" if excluir_comision_id is not None else ""
        params = [_clave_cuil(cuil), int(inst_id), int(periodo_id), periodo_nombre, int(anio), int(semestre)]
        if excluir_comision_id is not None:
            params.append(int(excluir_comision_id))
        return _pg_read_dataframe(f"""
            WITH base AS (
                SELECT a.id AS asignacion_id, a.cuil, a.rol, a.comision_id,
                       COALESCE(a.usa_horario_personalizado, FALSE) AS personalizado,
                       co.departamento_id, dep.nombre AS departamento_comision, co.materia_id,
                       p.nombre AS periodo, m.codigo AS codigo_materia, m.asignatura,
                       COALESCE(co.materia_especifica, '') AS materia_especifica,
                       c.nombre AS carrera, c.escuela, co.nombre_comision, co.turno
                FROM asignaciones_docentes_comision a
                JOIN comisiones co ON co.id=a.comision_id
                LEFT JOIN periodos p ON p.id=co.periodo_id
                LEFT JOIN departamentos dep ON dep.id=co.departamento_id
                LEFT JOIN materias m ON m.id=co.materia_id
                LEFT JOIN carreras c ON c.id=m.carrera_id
                WHERE regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g')=%s AND co.institucion_id=%s
                  AND COALESCE(a.estado,'Activa')='Activa' AND COALESCE(co.estado,'Activa')='Activa'
                  AND (co.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s)) {filtro_ex}
            ), reales AS (
                SELECT b.*, ha.dia, ha.hora_inicio, ha.hora_fin, ha.horas
                FROM base b JOIN horarios_asignacion_docente_comision ha ON ha.asignacion_id=b.asignacion_id
                WHERE b.personalizado=TRUE
                UNION ALL
                SELECT b.*, h.dia, h.hora_inicio, h.hora_fin, h.horas
                FROM base b JOIN horarios_comision h ON h.comision_id=b.comision_id
                WHERE b.personalizado=FALSE
            )
            SELECT * FROM reales
            ORDER BY CASE dia WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3 WHEN 'Jueves' THEN 4 WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6 WHEN 'Domingo' THEN 7 ELSE 99 END,
                     hora_inicio, departamento_comision, codigo_materia, nombre_comision
        """, params)
    except Exception:
        return pd.DataFrame()


# --- entry l. 30570-30619
def _enriquecer_carreras_comisiones_docente_v98(df):
    """Enriquece el resumen docente con los planes fijados explícitamente en cada comisión."""
    if df is None or df.empty:
        return df
    salida = df.copy()
    if "comision_id" in salida.columns:
        try:
            meta = metadata_explicita_comisiones_v118(
                salida["comision_id"].dropna().tolist(), global_institucion=bool(USE_POSTGRESQL)
            )
        except Exception:
            meta = pd.DataFrame()
        if isinstance(meta, pd.DataFrame) and not meta.empty:
            mapa = {}
            for _, r in meta.iterrows():
                try:
                    mapa[int(r.get("comision_id"))] = r.to_dict()
                except Exception:
                    continue
            for idx, row in salida.iterrows():
                try:
                    m = mapa.get(int(row.get("comision_id")))
                except Exception:
                    m = None
                if not m:
                    continue
                for destino in ["codigo_materia", "asignatura", "carrera", "escuela", "plan_version"]:
                    valor = limpiar_texto_tabla(m.get(destino, ""))
                    if valor:
                        salida.at[idx, destino] = valor
            return salida

    try:
        contexto, _ = _contexto_materias_unicas_fuente()
    except Exception:
        contexto = {}
    if not contexto:
        return salida
    for idx, row in salida.iterrows():
        clave = _clave_materia_unica_desde_codigo_nombre(
            row.get("codigo_materia", ""), row.get("asignatura", "")
        )
        meta = contexto.get(clave, {}) if clave else {}
        if not meta:
            continue
        for destino in ["carrera", "escuela", "plan_version"]:
            valor = limpiar_texto_tabla(meta.get(destino, ""))
            if valor:
                salida.at[idx, destino] = valor
    return salida


# --- entry l. 30703-30792
def get_superposiciones_periodo(periodo_id):
    """Superposiciones informativas SOLO del departamento operativo y del período seleccionado.

    La validación al asignar docentes puede seguir consultando contexto institucional cuando corresponda,
    pero las alertas y tableros departamentales nunca mezclan comisiones de otros departamentos.
    """
    try:
        conn = get_conn()
        df_cuil = pd.read_sql(
            """SELECT DISTINCT a.cuil
               FROM asignaciones_docentes_comision a
               JOIN comisiones co ON co.id=a.comision_id
               WHERE co.periodo_id=?
                 AND COALESCE(a.estado,'Activa')='Activa'
                 AND COALESCE(co.estado,'Activa')='Activa'""",
            conn,
            params=[int(periodo_id)],
        )
        conn.close()
    except Exception:
        df_cuil = pd.DataFrame(columns=["cuil"])

    try:
        df_docs_alertas = get_docentes().copy()
    except Exception:
        df_docs_alertas = pd.DataFrame()
    mapa_nombres_alertas = {}
    if isinstance(df_docs_alertas, pd.DataFrame) and not df_docs_alertas.empty and "cuil" in df_docs_alertas.columns:
        for _, rd in df_docs_alertas.iterrows():
            cuil_d = str(rd.get("cuil") or "").strip()
            nombre_d = limpiar_texto_tabla(rd.get("nombre_completo", ""))
            if not nombre_d:
                ape = limpiar_texto_tabla(rd.get("apellido", ""))
                nom = limpiar_texto_tabla(rd.get("nombres", ""))
                nombre_d = ", ".join([x for x in [ape, nom] if x])
            if cuil_d:
                mapa_nombres_alertas[cuil_d] = nombre_d or cuil_d

    out = []
    vistos = set()
    for cuil in df_cuil.get("cuil", pd.Series(dtype=str)).dropna().astype(str):
        # Importante: se usa deliberadamente la consulta LOCAL del departamento,
        # no get_horarios_docente_periodo(), que en PostgreSQL puede consolidar institución.
        try:
            dfh = _horarios_docente_local_v95(cuil, periodo_id)
        except Exception:
            dfh = pd.DataFrame()
        try:
            dfh = _enriquecer_carreras_comisiones_docente_v98(dfh)
        except Exception:
            pass
        for dia, g in dfh.groupby("dia") if not dfh.empty else []:
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
                    clave = (
                        str(cuil), str(dia),
                        min(str(a.get("comision_id")), str(b.get("comision_id"))),
                        max(str(a.get("comision_id")), str(b.get("comision_id"))),
                        max(ai, bi), min(af, bf),
                    )
                    if clave in vistos:
                        continue
                    vistos.add(clave)
                    out.append({
                        "docente": mapa_nombres_alertas.get(str(cuil).strip(), str(cuil)),
                        "cuil": cuil,
                        "dia": dia,
                        "asignatura_1": _nombre_materia_visible_v138(
                            a.get("codigo_materia", ""), a.get("asignatura", ""), a.get("materia_especifica", "")
                        ),
                        "comision_1": str(a.get("nombre_comision", "")),
                        "horario_1": f"{_hora_texto_v95(a.get('hora_inicio'))}-{_hora_texto_v95(a.get('hora_fin'))}",
                        "asignatura_2": _nombre_materia_visible_v138(
                            b.get("codigo_materia", ""), b.get("asignatura", ""), b.get("materia_especifica", "")
                        ),
                        "comision_2": str(b.get("nombre_comision", "")),
                        "horario_2": f"{_hora_texto_v95(b.get('hora_inicio'))}-{_hora_texto_v95(b.get('hora_fin'))}",
                    })
    return pd.DataFrame(out, columns=[
        "docente", "cuil", "dia", "asignatura_1", "comision_1", "horario_1",
        "asignatura_2", "comision_2", "horario_2"
    ])


# --- entry l. 30795-30874
def _productividad_docente_departamento_v148(cuil, periodo_id):
    """Calcula productividad con datos del departamento operativo solamente."""
    cuil_txt = str(cuil or "").strip()
    porcentaje_no_lectivas = float(get_porcentaje_horas_no_lectivas_v148() or 0)

    # Designaciones propias del departamento/período.
    df_desig = get_designaciones(periodo_id)
    if df_desig is None:
        df_desig = pd.DataFrame()
    if not df_desig.empty:
        sub_d = df_desig[
            df_desig.get("cuil", pd.Series(index=df_desig.index, dtype=str)).fillna("").astype(str).str.strip().eq(cuil_txt)
        ].copy()
        sub_d_act = sub_d[sub_d.get("estado", pd.Series(index=sub_d.index, dtype=str)).fillna("").astype(str).eq("Activa")].copy()
    else:
        sub_d = pd.DataFrame(); sub_d_act = pd.DataFrame()
    contratadas = float(pd.to_numeric(sub_d_act.get("horas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not sub_d_act.empty else 0.0
    if contratadas <= 0:
        # No usar el Resumen docente institucional como fallback: las métricas y
        # alertas del departamento deben seguir siendo estrictamente locales.
        try:
            df_p_local = get_periodos()
            fila_p_local = df_p_local[df_p_local["id"] == int(periodo_id)].iloc[0] if not df_p_local.empty and not df_p_local[df_p_local["id"] == int(periodo_id)].empty else None
            if fila_p_local is not None and str(fila_p_local.get("estado", "")).strip().lower() == "cerrado" and not sub_d.empty:
                df_hist_local = _df_designaciones_vigentes_durante_periodo(
                    sub_d, fila_p_local.get("fecha_inicio", ""), fila_p_local.get("fecha_fin", "")
                )
                contratadas = float(pd.to_numeric(df_hist_local.get("horas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not df_hist_local.empty else 0.0
        except Exception:
            pass

    # Horas lectivas reales del departamento (respeta franjas personalizadas y no duplica superposiciones).
    try:
        df_h = _horarios_docente_local_v95(cuil_txt, periodo_id)
    except Exception:
        df_h = pd.DataFrame()
    comisiones_reales = _calcular_horas_unicas_desde_horarios_df(df_h) if df_h is not None and not df_h.empty else 0.0

    # Horas brutas de asignación, también locales, para informar cuánto se descarta por solape.
    try:
        df_asig = get_asignaciones_comisiones_periodo(periodo_id)
        if df_asig is not None and not df_asig.empty:
            sub_a = df_asig[
                df_asig.get("cuil", pd.Series(index=df_asig.index, dtype=str)).fillna("").astype(str).str.strip().eq(cuil_txt)
                & df_asig.get("estado", pd.Series(index=df_asig.index, dtype=str)).fillna("Activa").astype(str).eq("Activa")
            ].copy()
            comisiones_brutas = float(pd.to_numeric(sub_a.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        else:
            comisiones_brutas = 0.0
    except Exception:
        comisiones_brutas = float(comisiones_reales)

    try:
        df_inv = get_investigacion_docente(cuil=cuil_txt, periodo_id=periodo_id, todos_departamentos=False)
        investigacion = float(pd.to_numeric(df_inv.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if df_inv is not None and not df_inv.empty else 0.0
    except Exception:
        investigacion = 0.0
    try:
        df_ext = get_extension_docente(cuil=cuil_txt, periodo_id=periodo_id, todos_departamentos=False)
        extension = float(pd.to_numeric(df_ext.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if df_ext is not None and not df_ext.empty else 0.0
    except Exception:
        extension = 0.0

    horas_no_lectivas = round(float(comisiones_reales) * porcentaje_no_lectivas / 100.0, 2)
    utilizadas = round(float(comisiones_reales) + horas_no_lectivas + investigacion + extension, 2)
    disponibles = round(contratadas - utilizadas, 2)
    porcentaje = round((utilizadas / contratadas * 100.0), 2) if contratadas > 0 else 0.0
    return {
        "horas_contratadas": round(contratadas, 2),
        "horas_en_comisiones": round(float(comisiones_reales), 2),
        "horas_en_comisiones_brutas": round(float(comisiones_brutas), 2),
        "horas_no_contadas_por_superposicion": max(round(float(comisiones_brutas) - float(comisiones_reales), 2), 0.0),
        "porcentaje_no_lectivas": round(porcentaje_no_lectivas, 2),
        "horas_no_lectivas": horas_no_lectivas,
        "horas_en_investigacion": round(investigacion, 2),
        "horas_en_extension": round(extension, 2),
        "horas_utilizadas": utilizadas,
        "horas_disponibles": disponibles,
        "porcentaje": porcentaje,
    }


# --- entry l. 30877-30950
def get_docentes_productividad_periodo(periodo_id):
    """Productividad departamental; no mezcla designaciones ni actividades de otros departamentos."""
    df_plantel = get_plantel_periodo(periodo_id)
    columnas = [
        "cuil", "docente", "tipo_docente", "cargos", "dedicaciones", "tipos_designacion",
        "porcentaje_uso", "horas_contratadas", "horas_comisiones_brutas", "horas_comisiones_reales",
        "horas_no_contadas_por_superposicion", "porcentaje_no_lectivas", "horas_no_lectivas",
        "horas_investigacion", "horas_extension", "horas_utilizadas", "horas_disponibles", "diagnostico"
    ]
    if df_plantel is None or df_plantel.empty:
        return pd.DataFrame(columns=columnas)

    df_desig = get_designaciones(periodo_id)
    if df_desig is not None and not df_desig.empty:
        df_desig_act = df_desig[df_desig["estado"] == "Activa"].copy()
    else:
        df_desig_act = pd.DataFrame(columns=["cuil", "cargo", "dedicacion", "tipo_designacion"])

    registros = []
    for _, row in df_plantel.iterrows():
        cuil = str(row.get("cuil", "") or "").strip()
        if not cuil or str(row.get("tipo_docente", "Propio")).strip() == "Prestado":
            continue
        prod = _productividad_docente_departamento_v148(cuil, periodo_id)
        desig_doc = df_desig_act[df_desig_act["cuil"].fillna("").astype(str).str.strip() == cuil].copy() if not df_desig_act.empty else pd.DataFrame()

        def unir_unicos(col):
            if desig_doc.empty or col not in desig_doc.columns:
                return ""
            vals = []
            for v in desig_doc[col].dropna().astype(str).tolist():
                v = v.strip()
                if v and v not in vals:
                    vals.append(v)
            return " / ".join(vals)

        contratadas = float(prod.get("horas_contratadas", 0) or 0)
        utilizadas = float(prod.get("horas_utilizadas", 0) or 0)
        porcentaje = float(prod.get("porcentaje", 0) or 0)
        if contratadas <= 0 and utilizadas > 0:
            diagnostico = "Actividad registrada sin horas contratadas"
        elif utilizadas > contratadas:
            diagnostico = "Sobrecarga: horas utilizadas superan las contratadas"
        elif contratadas > 0 and utilizadas == 0:
            diagnostico = "Sin actividad registrada"
        elif contratadas > 0 and porcentaje < 50:
            diagnostico = "Subutilización: baja carga registrada"
        else:
            diagnostico = "Sin alerta principal"

        registros.append({
            "cuil": cuil,
            "docente": row.get("nombre_completo", ""),
            "tipo_docente": row.get("tipo_docente", "Propio"),
            "cargos": unir_unicos("cargo"),
            "dedicaciones": unir_unicos("dedicacion"),
            "tipos_designacion": unir_unicos("tipo_designacion"),
            "porcentaje_uso": porcentaje,
            "horas_contratadas": contratadas,
            "horas_comisiones_brutas": float(prod.get("horas_en_comisiones_brutas", 0) or 0),
            "horas_comisiones_reales": float(prod.get("horas_en_comisiones", 0) or 0),
            "horas_no_contadas_por_superposicion": float(prod.get("horas_no_contadas_por_superposicion", 0) or 0),
            "porcentaje_no_lectivas": float(prod.get("porcentaje_no_lectivas", 0) or 0),
            "horas_no_lectivas": float(prod.get("horas_no_lectivas", 0) or 0),
            "horas_investigacion": float(prod.get("horas_en_investigacion", 0) or 0),
            "horas_extension": float(prod.get("horas_en_extension", 0) or 0),
            "horas_utilizadas": round(utilizadas, 2),
            "horas_disponibles": round(float(prod.get("horas_disponibles", 0) or 0), 2),
            "diagnostico": diagnostico,
        })

    if not registros:
        return pd.DataFrame(columns=columnas)
    return pd.DataFrame(registros, columns=columnas).sort_values(["diagnostico", "docente"], kind="stable")


# --- entry l. 30953-31004
def _estilo_productividad_v148(df):
    """Destaca productividad y muestra todos los datos numéricos con hasta 2 decimales."""
    def color_pct(valor):
        try:
            v = float(valor)
        except Exception:
            return ""
        if v < 40:
            return "background-color: #b91c1c; color: white; font-weight: 700;"
        if v <= 60:
            return "background-color: #facc15; color: #111827; font-weight: 700;"
        if v <= 100:
            return "background-color: #15803d; color: white; font-weight: 700;"
        return "background-color: #2563eb; color: white; font-weight: 700;"

    def fmt_max2(valor, sufijo=""):
        try:
            if pd.isna(valor):
                return ""
        except Exception:
            pass
        try:
            numero = round(float(valor), 2)
        except Exception:
            return str(valor)
        txt = f"{numero:.2f}".rstrip("0").rstrip(".")
        return f"{txt}{sufijo}"

    sty = df.style
    try:
        sty = sty.map(color_pct, subset=["Productividad %"])
    except Exception:
        sty = sty.applymap(color_pct, subset=["Productividad %"])

    formatos = {}
    for col in [
        "Hs contratadas", "Hs frente a comisión", "Hs no lectivas",
        "Hs investigación", "Hs extensión", "Hs utilizadas", "Hs disponibles",
        "Hs no contadas por superposición",
    ]:
        if col in df.columns:
            formatos[col] = lambda v: fmt_max2(v)
    if "Productividad %" in df.columns:
        formatos["Productividad %"] = lambda v: fmt_max2(v, " %")
    if "% no lectivas" in df.columns:
        formatos["% no lectivas"] = lambda v: fmt_max2(v, " %")
    if formatos:
        try:
            sty = sty.format(formatos)
        except Exception:
            pass
    return sty


# --- entry l. 31006-31007
def calcular_horas_comisiones_unicas_docente(cuil, periodo_id):
    return _calcular_horas_unicas_desde_horarios_df(get_horarios_docente_periodo(cuil, periodo_id))


# --- entry l. 31010-31011
def calcular_horas_comisiones_unicas_docente_pg_global(cuil, periodo_id):
    return _calcular_horas_unicas_desde_horarios_df(_get_horarios_docente_periodo_pg_global(cuil, periodo_id))


# --- entry l. 31120-31155
def _get_designaciones_periodo_institucional_v149(cuil, periodo_id):
    """Todas las designaciones del CUIL para el período equivalente, sin cambiar su departamento de origen."""
    if not USE_POSTGRESQL or not str(cuil or "").strip() or periodo_id is None:
        return pd.DataFrame()
    try:
        inst_id = _pg_current_inst_id()
        periodo_nombre, anio, semestre = _periodo_equivalente_pg(periodo_id)
        return _pg_read_dataframe("""
            SELECT
                d.id, d.cuil, d.periodo_id, d.departamento_id,
                COALESCE(dep.nombre, 'Sin departamento') AS departamento,
                p.nombre AS periodo,
                d.cargo, d.dedicacion, d.horas, d.tipo_designacion, d.estado,
                d.fecha_desde, d.fecha_hasta,
                COALESCE(NULLIF(d.fecha_hasta_prevista,''), d.fecha_hasta) AS fecha_hasta_prevista,
                d.fecha_finalizacion_efectiva, d.fecha_registro_finalizacion,
                d.motivo_finalizacion, COALESCE(d.observaciones, '') AS observaciones
            FROM designaciones d
            JOIN periodos p ON p.id=d.periodo_id
            LEFT JOIN departamentos dep ON dep.id=d.departamento_id
            WHERE d.institucion_id=%s
              AND p.institucion_id=d.institucion_id
              AND p.departamento_id IS NOT DISTINCT FROM d.departamento_id
              AND regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g')=%s
              AND (d.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))
              AND EXISTS (
                  SELECT 1 FROM docentes docx
                  WHERE docx.institucion_id=d.institucion_id
                    AND docx.departamento_id IS NOT DISTINCT FROM d.departamento_id
                    AND regexp_replace(COALESCE(docx.cuil,''), '[^0-9]', '', 'g')=
                        regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g')
              )
            ORDER BY dep.nombre, d.fecha_desde, d.id
        """, [int(inst_id), _clave_cuil(cuil), int(periodo_id), periodo_nombre, int(anio), int(semestre)])
    except Exception:
        return pd.DataFrame()


# --- entry l. 31158-31178
def _get_movimientos_periodo_institucional_v149(cuil, periodo_id):
    """Movimientos del mismo CUIL en todos los departamentos para el período equivalente."""
    if not USE_POSTGRESQL or not str(cuil or "").strip() or periodo_id is None:
        return pd.DataFrame()
    try:
        inst_id = _pg_current_inst_id()
        periodo_nombre, anio, semestre = _periodo_equivalente_pg(periodo_id)
        return _pg_read_dataframe("""
            SELECT m.id, m.fecha, m.tipo_movimiento, m.detalle,
                   COALESCE(m.horas_variacion,0) AS horas_variacion,
                   m.departamento_id, COALESCE(dep.nombre,'Sin departamento') AS departamento
            FROM movimientos m
            LEFT JOIN periodos p ON p.id=m.periodo_id
            LEFT JOIN departamentos dep ON dep.id=m.departamento_id
            WHERE m.institucion_id=%s
              AND regexp_replace(COALESCE(m.cuil,''), '[^0-9]', '', 'g')=%s
              AND (m.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))
            ORDER BY m.fecha, m.id
        """, [int(inst_id), _clave_cuil(cuil), int(periodo_id), periodo_nombre, int(anio), int(semestre)])
    except Exception:
        return pd.DataFrame()


# --- entry l. 31181-31206
def get_horas_inicio_real_institucional_v149(periodo_id, cuil, df_designaciones=None):
    """Usa correcciones históricas solo cuando cubren todos los departamentos con designación."""
    if not USE_POSTGRESQL:
        return get_horas_inicio_real_v132(periodo_id, cuil)
    try:
        asegurar_esquema_correcciones_historial_horas_v132()
        inst_id = _pg_current_inst_id()
        periodo_nombre, anio, semestre = _periodo_equivalente_pg(periodo_id)
        df_corr = _pg_read_dataframe("""
            SELECT ch.departamento_id, ch.horas_inicio_reales
            FROM correcciones_historial_horas ch
            LEFT JOIN periodos p ON p.id=ch.periodo_id
            WHERE ch.institucion_id=%s
              AND regexp_replace(COALESCE(ch.cuil,''), '[^0-9]', '', 'g')=%s
              AND (ch.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))
        """, [int(inst_id), _clave_cuil(cuil), int(periodo_id), periodo_nombre, int(anio), int(semestre)])
        if df_corr is None or df_corr.empty:
            return None
        df_d = df_designaciones if isinstance(df_designaciones, pd.DataFrame) else _get_designaciones_periodo_institucional_v149(cuil, periodo_id)
        deps_d = set(pd.to_numeric(df_d.get("departamento_id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist()) if df_d is not None and not df_d.empty else set()
        deps_c = set(pd.to_numeric(df_corr.get("departamento_id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist())
        if deps_d and not deps_d.issubset(deps_c):
            return None
        return float(pd.to_numeric(df_corr["horas_inicio_reales"], errors="coerce").fillna(0).sum())
    except Exception:
        return None


# --- entry l. 31250-31268
def _get_porcentajes_no_lectivos_departamentos_v149():
    """Mapa departamento_id -> porcentaje configurado de horas no lectivas."""
    if not USE_POSTGRESQL:
        dep_id = _pg_current_dep_id() if USE_POSTGRESQL else None
        return {dep_id: float(get_porcentaje_horas_no_lectivas_v148() or 0)} if dep_id is not None else {}
    try:
        asegurar_esquema_config_productividad_v148()
        inst_id = _pg_current_inst_id()
        df = _pg_read_dataframe("""
            SELECT departamento_id, COALESCE(porcentaje_horas_no_lectivas,0) AS porcentaje
            FROM config_productividad_departamento
            WHERE institucion_id=%s
        """, [int(inst_id)])
        return {
            int(r.get("departamento_id")): float(r.get("porcentaje") or 0)
            for _, r in df.iterrows() if pd.notna(r.get("departamento_id"))
        }
    except Exception:
        return {}


# --- entry l. 31271-31374
def get_productividad_docente_institucional_v149(cuil, periodo_id):
    """Productividad individual consolidada entre todos los departamentos del mismo CUIL.

    Las alertas y métricas departamentales siguen usando _productividad_docente_departamento_v148.
    """
    if not USE_POSTGRESQL:
        return _get_productividad_docente_pre_v149(cuil, periodo_id) if "_get_productividad_docente_pre_v149" in globals() else {}
    df_des = _get_designaciones_periodo_institucional_v149(cuil, periodo_id)
    if df_des is None:
        df_des = pd.DataFrame()
    if not df_des.empty:
        df_act = df_des[df_des.get("estado", pd.Series(index=df_des.index, dtype=str)).fillna("").astype(str).str.strip().str.lower().eq("activa")].copy()
        if df_act.empty:
            try:
                inst_id = _pg_current_inst_id()
                df_periodo_ref_v149 = _pg_read_dataframe(
                    "SELECT COALESCE(estado,'') AS estado, fecha_inicio, fecha_fin FROM periodos WHERE id=%s AND institucion_id=%s LIMIT 1",
                    [int(periodo_id), int(inst_id)],
                )
                if not df_periodo_ref_v149.empty and str(df_periodo_ref_v149.iloc[0].get("estado") or "").strip().lower() == "cerrado":
                    df_act = _df_designaciones_vigentes_durante_periodo(
                        df_des,
                        df_periodo_ref_v149.iloc[0].get("fecha_inicio", ""),
                        df_periodo_ref_v149.iloc[0].get("fecha_fin", ""),
                    )
            except Exception:
                pass
    else:
        df_act = pd.DataFrame()
    contratadas = float(pd.to_numeric(df_act.get("horas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not df_act.empty else 0.0

    try:
        df_h = _get_horarios_docente_periodo_pg_global(cuil, periodo_id)
    except Exception:
        df_h = pd.DataFrame()
    comisiones_reales = _calcular_horas_unicas_desde_horarios_df(df_h) if df_h is not None and not df_h.empty else 0.0

    try:
        inst_id = _pg_current_inst_id(); periodo_nombre, anio, semestre = _periodo_equivalente_pg(periodo_id)
        df_br = _pg_read_dataframe("""
            SELECT COALESCE(SUM(a.horas_asignadas),0) AS horas
            FROM asignaciones_docentes_comision a
            JOIN comisiones co ON co.id=a.comision_id
            LEFT JOIN periodos p ON p.id=co.periodo_id
            WHERE a.institucion_id=%s
              AND regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g')=%s
              AND COALESCE(a.estado,'Activa')='Activa' AND COALESCE(co.estado,'Activa')='Activa'
              AND (co.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))
        """, [int(inst_id), _clave_cuil(cuil), int(periodo_id), periodo_nombre, int(anio), int(semestre)])
        comisiones_brutas = float(df_br.iloc[0].get("horas") or 0) if df_br is not None and not df_br.empty else float(comisiones_reales)
    except Exception:
        comisiones_brutas = float(comisiones_reales)

    porcentajes = _get_porcentajes_no_lectivos_departamentos_v149()
    detalle_no_lectivas = []
    horas_no_lectivas = 0.0
    if df_h is not None and not df_h.empty and "departamento_id" in df_h.columns:
        for dep_id, g in df_h.groupby("departamento_id", dropna=True, sort=True):
            try:
                dep_int = int(dep_id)
            except Exception:
                continue
            hs_dep = float(_calcular_horas_unicas_desde_horarios_df(g) or 0)
            pct_dep = float(porcentajes.get(dep_int, 0) or 0)
            hs_nl = round(hs_dep * pct_dep / 100.0, 2)
            horas_no_lectivas += hs_nl
            dep_nombre = limpiar_texto_tabla(g.iloc[0].get("departamento_comision", "")) or f"Departamento {dep_int}"
            detalle_no_lectivas.append({
                "Departamento": dep_nombre, "Hs frente a comisión": round(hs_dep, 2),
                "% no lectivas": round(pct_dep, 2), "Hs no lectivas": hs_nl,
            })
    horas_no_lectivas = round(horas_no_lectivas, 2)
    porcentaje_no_lectivas_efectivo = round(
        (horas_no_lectivas / float(comisiones_reales) * 100.0), 2
    ) if float(comisiones_reales or 0) > 0 else 0.0

    try:
        df_inv = get_investigacion_docente(cuil=cuil, periodo_id=periodo_id, todos_departamentos=True)
        investigacion = float(pd.to_numeric(df_inv.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if df_inv is not None and not df_inv.empty else 0.0
    except Exception:
        investigacion = 0.0
    try:
        df_ext = get_extension_docente(cuil=cuil, periodo_id=periodo_id, todos_departamentos=True)
        extension = float(pd.to_numeric(df_ext.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if df_ext is not None and not df_ext.empty else 0.0
    except Exception:
        extension = 0.0

    utilizadas = round(float(comisiones_reales) + horas_no_lectivas + investigacion + extension, 2)
    disponibles = round(contratadas - utilizadas, 2)
    porcentaje = round((utilizadas / contratadas * 100.0), 2) if contratadas > 0 else 0.0
    return {
        "horas_contratadas": round(contratadas, 2),
        "horas_en_comisiones": round(float(comisiones_reales), 2),
        "horas_en_comisiones_brutas": round(float(comisiones_brutas), 2),
        "horas_no_contadas_por_superposicion": max(round(float(comisiones_brutas) - float(comisiones_reales), 2), 0.0),
        "porcentaje_no_lectivas": porcentaje_no_lectivas_efectivo,
        "horas_no_lectivas": horas_no_lectivas,
        "detalle_no_lectivas_departamentos": detalle_no_lectivas,
        "horas_en_investigacion": round(investigacion, 2),
        "horas_en_extension": round(extension, 2),
        "horas_utilizadas": utilizadas,
        "horas_disponibles": disponibles,
        "porcentaje": porcentaje,
    }


# --- entry l. 31377
_get_productividad_docente_pre_v149 = get_productividad_docente


# --- entry l. 31379-31387
def get_productividad_docente(cuil, periodo_id):
    """Vista individual: en PostgreSQL consolida el CUIL en toda la institución.

    Los paneles/alertas departamentales no usan esta función: conservan la versión
    estrictamente local _productividad_docente_departamento_v148.
    """
    if USE_POSTGRESQL:
        return get_productividad_docente_institucional_v149(cuil, periodo_id)
    return _get_productividad_docente_pre_v149(cuil, periodo_id)


# --- entry l. 31443
_get_docentes_productividad_periodo_pre_v150 = get_docentes_productividad_periodo


# --- entry l. 31446-31448
def _redondear_numericos_productividad_v150(df):
    from analisis.motor.ref.domain.informes import _redondear_numericos_productividad_v150 as _b05_core__redondear_numericos_productividad_v150
    return _b05_core__redondear_numericos_productividad_v150(df)


# --- entry l. 31451-31561
def get_docentes_productividad_periodo(periodo_id):
    """Productividad de los docentes propios del departamento, con carga institucional.

    La pertenencia del plantel sigue siendo departamental: en esta tabla solo se
    analizan docentes propios del departamento operativo. Para cada uno, sin embargo,
    se consolidan por CUIL las designaciones y actividades del mismo período académico
    en TODA la institución (comisiones, horas no lectivas, investigación y extensión).

    Así, si un docente de Ciencias Exactas dicta una comisión en Informática e Ingeniería,
    esas horas sí forman parte de su productividad en el análisis de Ciencias Exactas.
    Un docente meramente prestado al departamento actual sigue sin convertirse en plantel
    propio de ese departamento.
    """
    if not USE_POSTGRESQL:
        return _redondear_numericos_productividad_v150(
            _get_docentes_productividad_periodo_pre_v150(periodo_id)
        )

    df_plantel = get_plantel_periodo(periodo_id)
    columnas = [
        "cuil", "docente", "tipo_docente", "departamentos_designacion",
        "cargos", "dedicaciones", "tipos_designacion", "porcentaje_uso",
        "horas_contratadas", "horas_comisiones_brutas", "horas_comisiones_reales",
        "horas_no_contadas_por_superposicion", "porcentaje_no_lectivas", "horas_no_lectivas",
        "horas_investigacion", "horas_extension", "horas_utilizadas",
        "horas_disponibles", "diagnostico",
    ]
    if df_plantel is None or df_plantel.empty:
        return pd.DataFrame(columns=columnas)

    registros = []
    cuiles_vistos = set()
    for _, row in df_plantel.iterrows():
        cuil = str(row.get("cuil", "") or "").strip()
        clave_cuil = _clave_cuil(cuil)
        if not clave_cuil or clave_cuil in cuiles_vistos:
            continue
        # El departamento analiza su propio plantel. Los prestados se visualizan en su
        # Resumen, pero su productividad corresponde al/los departamentos a los que pertenecen.
        if str(row.get("tipo_docente", "Propio") or "Propio").strip().lower() == "prestado":
            continue
        cuiles_vistos.add(clave_cuil)

        prod = get_productividad_docente_institucional_v149(cuil, periodo_id)
        if not isinstance(prod, dict):
            prod = {}

        df_desig_inst = _get_designaciones_periodo_institucional_v149(cuil, periodo_id)
        if df_desig_inst is None:
            df_desig_inst = pd.DataFrame()
        if not df_desig_inst.empty:
            activas = df_desig_inst[
                df_desig_inst.get("estado", pd.Series(index=df_desig_inst.index, dtype=str))
                .fillna("").astype(str).str.strip().str.lower().eq("activa")
            ].copy()
            df_desig_mostrar = activas if not activas.empty else df_desig_inst.copy()
        else:
            df_desig_mostrar = pd.DataFrame()

        def unir_unicos(col):
            if df_desig_mostrar.empty or col not in df_desig_mostrar.columns:
                return ""
            vals = []
            for valor in df_desig_mostrar[col].dropna().astype(str).tolist():
                valor = " ".join(valor.strip().split())
                if valor and valor not in vals:
                    vals.append(valor)
            return " / ".join(vals)

        contratadas = round(float(prod.get("horas_contratadas", 0) or 0), 2)
        utilizadas = round(float(prod.get("horas_utilizadas", 0) or 0), 2)
        porcentaje = round(float(prod.get("porcentaje", 0) or 0), 2)

        if contratadas <= 0 and utilizadas > 0:
            diagnostico = "Actividad registrada sin horas contratadas"
        elif utilizadas > contratadas:
            diagnostico = "Sobrecarga: horas utilizadas superan las contratadas"
        elif contratadas > 0 and utilizadas == 0:
            diagnostico = "Sin actividad registrada"
        elif contratadas > 0 and porcentaje < 50:
            diagnostico = "Subutilización: baja carga registrada"
        else:
            diagnostico = "Sin alerta principal"

        registros.append({
            "cuil": cuil,
            "docente": row.get("nombre_completo", ""),
            "tipo_docente": row.get("tipo_docente", "Propio"),
            "departamentos_designacion": unir_unicos("departamento"),
            "cargos": unir_unicos("cargo"),
            "dedicaciones": unir_unicos("dedicacion"),
            "tipos_designacion": unir_unicos("tipo_designacion"),
            "porcentaje_uso": porcentaje,
            "horas_contratadas": contratadas,
            "horas_comisiones_brutas": round(float(prod.get("horas_en_comisiones_brutas", 0) or 0), 2),
            "horas_comisiones_reales": round(float(prod.get("horas_en_comisiones", 0) or 0), 2),
            "horas_no_contadas_por_superposicion": round(float(prod.get("horas_no_contadas_por_superposicion", 0) or 0), 2),
            "porcentaje_no_lectivas": round(float(prod.get("porcentaje_no_lectivas", 0) or 0), 2),
            "horas_no_lectivas": round(float(prod.get("horas_no_lectivas", 0) or 0), 2),
            "horas_investigacion": round(float(prod.get("horas_en_investigacion", 0) or 0), 2),
            "horas_extension": round(float(prod.get("horas_en_extension", 0) or 0), 2),
            "horas_utilizadas": utilizadas,
            "horas_disponibles": round(float(prod.get("horas_disponibles", 0) or 0), 2),
            "diagnostico": diagnostico,
        })

    if not registros:
        return pd.DataFrame(columns=columnas)
    out = pd.DataFrame(registros, columns=columnas)
    out = _redondear_numericos_productividad_v150(out)
    return out.sort_values(["diagnostico", "docente"], kind="stable").reset_index(drop=True)


# --- entry l. 31565-31622
def _conteo_docentes_activos_por_comision_v151(comision_ids):
    """Cantidad de docentes activos distintos por comisión.

    Se usa para aplicar el porcentaje completo de horas no lectivas cuando el
    docente está solo y la mitad del parámetro cuando la comisión tiene 2 o más
    docentes. El conteo es de personas (CUIL), no de roles/asignaciones.
    """
    ids = []
    for valor in list(comision_ids or []):
        try:
            cid = int(valor)
        except Exception:
            continue
        if cid not in ids:
            ids.append(cid)
    if not ids:
        return {}

    try:
        if USE_POSTGRESQL:
            inst_id = _pg_current_inst_id()
            if inst_id is None:
                return {}
            placeholders = ", ".join(["%s"] * len(ids))
            df = _pg_read_dataframe(f"""
                SELECT a.comision_id,
                       COUNT(DISTINCT regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g')) AS docentes
                FROM asignaciones_docentes_comision a
                JOIN comisiones co ON co.id = a.comision_id
                WHERE co.institucion_id = %s
                  AND a.comision_id IN ({placeholders})
                  AND COALESCE(a.estado, 'Activa') = 'Activa'
                  AND COALESCE(co.estado, 'Activa') = 'Activa'
                  AND COALESCE(a.cuil, '') <> ''
                GROUP BY a.comision_id
            """, [int(inst_id)] + ids)
        else:
            conn = get_conn()
            placeholders = ",".join(["?"] * len(ids))
            df = pd.read_sql(f"""
                SELECT a.comision_id, COUNT(DISTINCT a.cuil) AS docentes
                FROM asignaciones_docentes_comision a
                JOIN comisiones co ON co.id = a.comision_id
                WHERE a.comision_id IN ({placeholders})
                  AND COALESCE(a.estado, 'Activa') = 'Activa'
                  AND COALESCE(co.estado, 'Activa') = 'Activa'
                  AND COALESCE(a.cuil, '') <> ''
                GROUP BY a.comision_id
            """, conn, params=ids)
            conn.close()
        if df is None or df.empty:
            return {}
        return {
            int(r.get("comision_id")): max(int(r.get("docentes") or 0), 0)
            for _, r in df.iterrows() if pd.notna(r.get("comision_id"))
        }
    except Exception:
        return {}


# --- entry l. 31625-31690
def _calcular_horas_no_lectivas_institucional_v151(cuil, periodo_id, df_horarios=None):
    """Calcula horas no lectivas por comisión y departamento para un docente.

    Regla v151:
    - 1 docente activo en la comisión: 100 % del parámetro del departamento.
    - 2 o más docentes activos: 50 % del parámetro del departamento para cada docente.
    """
    if not USE_POSTGRESQL:
        return 0.0, 0.0, []

    df_h = df_horarios if isinstance(df_horarios, pd.DataFrame) else None
    if df_h is None:
        try:
            df_h = _get_horarios_docente_periodo_pg_global(cuil, periodo_id)
        except Exception:
            df_h = pd.DataFrame()
    if df_h is None or df_h.empty or "comision_id" not in df_h.columns:
        return 0.0, 0.0, []

    porcentajes = _get_porcentajes_no_lectivos_departamentos_v149()
    ids = pd.to_numeric(df_h["comision_id"], errors="coerce").dropna().astype(int).unique().tolist()
    conteos = _conteo_docentes_activos_por_comision_v151(ids)
    detalle = []
    total_no_lectivas = 0.0

    for cid, grupo in df_h.groupby("comision_id", dropna=True, sort=True):
        try:
            cid_int = int(cid)
        except Exception:
            continue
        hs_doc = float(_calcular_horas_unicas_desde_horarios_df(grupo) or 0)
        try:
            dep_id = int(pd.to_numeric(grupo.iloc[0].get("departamento_id"), errors="coerce"))
        except Exception:
            dep_id = None
        pct_base = float(porcentajes.get(dep_id, 0) or 0) if dep_id is not None else 0.0
        cantidad_docentes = int(conteos.get(cid_int, 1) or 1)
        pct_aplicado = pct_base if cantidad_docentes <= 1 else pct_base / 2.0
        hs_nl = round(hs_doc * pct_aplicado / 100.0, 2)
        total_no_lectivas += hs_nl

        dep_nombre = limpiar_texto_tabla(grupo.iloc[0].get("departamento_comision", "")) or (
            f"Departamento {dep_id}" if dep_id is not None else "Sin departamento"
        )
        asignatura = _nombre_materia_visible_v138(
            grupo.iloc[0].get("codigo_materia", ""),
            grupo.iloc[0].get("asignatura", ""),
            grupo.iloc[0].get("materia_especifica", ""),
        )
        detalle.append({
            "Departamento": dep_nombre,
            "Comisión": limpiar_texto_tabla(grupo.iloc[0].get("nombre_comision", "")),
            "Asignatura": asignatura,
            "Docentes activos en comisión": cantidad_docentes,
            "Hs frente a comisión": round(hs_doc, 2),
            "% base no lectivas": round(pct_base, 2),
            "% aplicado": round(pct_aplicado, 2),
            "Hs no lectivas": hs_nl,
        })

    total_no_lectivas = round(total_no_lectivas, 2)
    hs_lectivas_reales = float(_calcular_horas_unicas_desde_horarios_df(df_h) or 0)
    porcentaje_efectivo = round(
        (total_no_lectivas / hs_lectivas_reales * 100.0), 2
    ) if hs_lectivas_reales > 0 else 0.0
    return total_no_lectivas, porcentaje_efectivo, detalle


# --- entry l. 31693
_get_productividad_docente_institucional_pre_v151 = get_productividad_docente_institucional_v149


# --- entry l. 31696-31722
def get_productividad_docente_institucional_v149(cuil, periodo_id):
    """Productividad institucional v151 con regla de horas no lectivas por comisión."""
    datos = dict(_get_productividad_docente_institucional_pre_v151(cuil, periodo_id) or {})
    if not USE_POSTGRESQL:
        return datos
    try:
        df_h = _get_horarios_docente_periodo_pg_global(cuil, periodo_id)
    except Exception:
        df_h = pd.DataFrame()
    horas_nl, pct_efectivo, detalle = _calcular_horas_no_lectivas_institucional_v151(
        cuil, periodo_id, df_horarios=df_h
    )
    datos["horas_no_lectivas"] = round(horas_nl, 2)
    datos["porcentaje_no_lectivas"] = round(pct_efectivo, 2)
    # Se conserva esta clave por compatibilidad con el Resumen docente, aunque
    # desde v151 el detalle es más preciso: una fila por comisión/departamento.
    datos["detalle_no_lectivas_departamentos"] = detalle

    contratadas = float(datos.get("horas_contratadas", 0) or 0)
    comisiones = float(datos.get("horas_en_comisiones", 0) or 0)
    investigacion = float(datos.get("horas_en_investigacion", 0) or 0)
    extension = float(datos.get("horas_en_extension", 0) or 0)
    utilizadas = round(comisiones + horas_nl + investigacion + extension, 2)
    datos["horas_utilizadas"] = utilizadas
    datos["horas_disponibles"] = round(contratadas - utilizadas, 2)
    datos["porcentaje"] = round((utilizadas / contratadas * 100.0), 2) if contratadas > 0 else 0.0
    return datos


# --- entry l. 31725
_get_docentes_productividad_periodo_pre_v151 = get_docentes_productividad_periodo


# --- entry l. 31728-31741
def _cuiles_designacion_activa_local_v151(periodo_id):
    """CUIL del plantel que tiene al menos una designación ACTIVA en el departamento actual."""
    try:
        df = get_designaciones(periodo_id)
    except Exception:
        df = pd.DataFrame()
    if df is None or df.empty:
        return set()
    estado = df.get("estado", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).str.strip().str.lower()
    df = df[estado.eq("activa")].copy()
    return {
        _clave_cuil(x) for x in df.get("cuil", pd.Series(dtype=str)).tolist()
        if _clave_cuil(x)
    }


# --- entry l. 31744-31855
def get_docentes_productividad_periodo(periodo_id):
    """Análisis automático: solo plantel con designación local activa; carga consolidada institucionalmente.

    Una designación finalizada/dada de baja no genera una fila de productividad ni
    una alerta de subutilización/sin actividad en el período actual. Si el docente
    continúa activo en otro departamento, será analizado en ese departamento.
    """
    if not USE_POSTGRESQL:
        df = _get_docentes_productividad_periodo_pre_v151(periodo_id)
        if df is None or df.empty:
            return df
        activos_locales = _cuiles_designacion_activa_local_v151(periodo_id)
        if not activos_locales:
            return df.iloc[0:0].copy()
        claves = df.get("cuil", pd.Series(index=df.index, dtype=str)).map(_clave_cuil)
        return _redondear_numericos_productividad_v150(df[claves.isin(activos_locales)].copy()).reset_index(drop=True)

    activos_locales = _cuiles_designacion_activa_local_v151(periodo_id)
    columnas = [
        "cuil", "docente", "tipo_docente", "departamentos_designacion",
        "cargos", "dedicaciones", "tipos_designacion", "porcentaje_uso",
        "horas_contratadas", "horas_comisiones_brutas", "horas_comisiones_reales",
        "horas_no_contadas_por_superposicion", "porcentaje_no_lectivas", "horas_no_lectivas",
        "horas_investigacion", "horas_extension", "horas_utilizadas",
        "horas_disponibles", "diagnostico",
    ]
    if not activos_locales:
        return pd.DataFrame(columns=columnas)

    df_plantel = get_plantel_periodo(periodo_id)
    if df_plantel is None or df_plantel.empty:
        return pd.DataFrame(columns=columnas)

    registros = []
    cuiles_vistos = set()
    for _, row in df_plantel.iterrows():
        cuil = str(row.get("cuil", "") or "").strip()
        clave_cuil = _clave_cuil(cuil)
        if not clave_cuil or clave_cuil in cuiles_vistos or clave_cuil not in activos_locales:
            continue
        if str(row.get("tipo_docente", "Propio") or "Propio").strip().lower() == "prestado":
            continue
        cuiles_vistos.add(clave_cuil)

        prod = get_productividad_docente_institucional_v149(cuil, periodo_id)
        if not isinstance(prod, dict):
            prod = {}

        df_desig_inst = _get_designaciones_periodo_institucional_v149(cuil, periodo_id)
        if df_desig_inst is None:
            df_desig_inst = pd.DataFrame()
        if not df_desig_inst.empty:
            activas = df_desig_inst[
                df_desig_inst.get("estado", pd.Series(index=df_desig_inst.index, dtype=str))
                .fillna("").astype(str).str.strip().str.lower().eq("activa")
            ].copy()
            df_desig_mostrar = activas if not activas.empty else pd.DataFrame()
        else:
            df_desig_mostrar = pd.DataFrame()

        def unir_unicos(col):
            if df_desig_mostrar.empty or col not in df_desig_mostrar.columns:
                return ""
            vals = []
            for valor in df_desig_mostrar[col].dropna().astype(str).tolist():
                valor = " ".join(valor.strip().split())
                if valor and valor not in vals:
                    vals.append(valor)
            return " / ".join(vals)

        contratadas = round(float(prod.get("horas_contratadas", 0) or 0), 2)
        utilizadas = round(float(prod.get("horas_utilizadas", 0) or 0), 2)
        porcentaje = round(float(prod.get("porcentaje", 0) or 0), 2)

        if contratadas <= 0 and utilizadas > 0:
            diagnostico = "Actividad registrada sin horas contratadas"
        elif utilizadas > contratadas:
            diagnostico = "Sobrecarga: horas utilizadas superan las contratadas"
        elif contratadas > 0 and utilizadas == 0:
            diagnostico = "Sin actividad registrada"
        elif contratadas > 0 and porcentaje < 50:
            diagnostico = "Subutilización: baja carga registrada"
        else:
            diagnostico = "Sin alerta principal"

        registros.append({
            "cuil": cuil,
            "docente": row.get("nombre_completo", ""),
            "tipo_docente": row.get("tipo_docente", "Propio"),
            "departamentos_designacion": unir_unicos("departamento"),
            "cargos": unir_unicos("cargo"),
            "dedicaciones": unir_unicos("dedicacion"),
            "tipos_designacion": unir_unicos("tipo_designacion"),
            "porcentaje_uso": porcentaje,
            "horas_contratadas": contratadas,
            "horas_comisiones_brutas": round(float(prod.get("horas_en_comisiones_brutas", 0) or 0), 2),
            "horas_comisiones_reales": round(float(prod.get("horas_en_comisiones", 0) or 0), 2),
            "horas_no_contadas_por_superposicion": round(float(prod.get("horas_no_contadas_por_superposicion", 0) or 0), 2),
            "porcentaje_no_lectivas": round(float(prod.get("porcentaje_no_lectivas", 0) or 0), 2),
            "horas_no_lectivas": round(float(prod.get("horas_no_lectivas", 0) or 0), 2),
            "horas_investigacion": round(float(prod.get("horas_en_investigacion", 0) or 0), 2),
            "horas_extension": round(float(prod.get("horas_en_extension", 0) or 0), 2),
            "horas_utilizadas": utilizadas,
            "horas_disponibles": round(float(prod.get("horas_disponibles", 0) or 0), 2),
            "diagnostico": diagnostico,
        })

    if not registros:
        return pd.DataFrame(columns=columnas)
    out = pd.DataFrame(registros, columns=columnas)
    out = _redondear_numericos_productividad_v150(out)
    return out.sort_values(["diagnostico", "docente"], kind="stable").reset_index(drop=True)


# --- entry l. 31858
_get_metricas_analisis_periodo_pre_v151 = get_metricas_analisis_periodo


# --- entry l. 31861-31920
def get_metricas_analisis_periodo(periodo_id):
    """Métricas departamentales con horas no lectivas ponderadas por dotación de cada comisión."""
    datos = dict(_get_metricas_analisis_periodo_pre_v151(periodo_id) or {})
    pct_base = float(get_porcentaje_horas_no_lectivas_v148() or 0)
    df_asig = datos.get("df_asig", pd.DataFrame())
    df_com = datos.get("df_com", pd.DataFrame())
    horas_no_lectivas = 0.0

    try:
        if isinstance(df_asig, pd.DataFrame) and not df_asig.empty and "comision_id" in df_asig.columns:
            asig = df_asig.copy()
            estado = asig.get("estado", pd.Series(index=asig.index, dtype=str)).fillna("Activa").astype(str).str.strip().str.lower()
            asig = asig[estado.eq("activa")].copy()

            # Solo comisiones activas del período/departamento actual.
            if isinstance(df_com, pd.DataFrame) and not df_com.empty and "id" in df_com.columns:
                ids_activas = set(pd.to_numeric(df_com["id"], errors="coerce").dropna().astype(int).tolist())
                asig["_cid_v151"] = pd.to_numeric(asig["comision_id"], errors="coerce")
                asig = asig[asig["_cid_v151"].isin(ids_activas)].copy()
            else:
                asig["_cid_v151"] = pd.to_numeric(asig["comision_id"], errors="coerce")

            asig["_cuil_v151"] = asig.get("cuil", pd.Series(index=asig.index, dtype=str)).map(_clave_cuil)
            conteos = (
                asig[asig["_cuil_v151"].astype(str).ne("")]
                .groupby("_cid_v151")["_cuil_v151"].nunique().to_dict()
            )
            if "tipo_docente" in asig.columns:
                propios = asig[asig["tipo_docente"].fillna("Propio").astype(str).str.strip().str.lower().ne("prestado")].copy()
            else:
                propios = asig.copy()
            propios = propios[propios["_cuil_v151"].astype(str).ne("") & propios["_cid_v151"].notna()].copy()
            if not propios.empty:
                pares = (
                    propios.groupby(["_cid_v151", "_cuil_v151"], as_index=False)
                    .agg(horas_asignadas=("horas_asignadas", "max"))
                )
                for _, r in pares.iterrows():
                    cid = r.get("_cid_v151")
                    hs = float(pd.to_numeric(r.get("horas_asignadas"), errors="coerce") or 0)
                    n_doc = int(conteos.get(cid, 1) or 1)
                    pct_aplicado = pct_base if n_doc <= 1 else pct_base / 2.0
                    horas_no_lectivas += hs * pct_aplicado / 100.0
    except Exception:
        # Ante una falla del detalle, se conserva un cálculo seguro basado en la
        # regla anterior para no romper el tablero.
        horas_no_lectivas = float(datos.get("horas_comisiones", 0) or 0) * pct_base / 100.0

    horas_no_lectivas = round(horas_no_lectivas, 2)
    datos["porcentaje_horas_no_lectivas"] = round(pct_base, 2)
    datos["porcentaje_horas_no_lectivas_compartida"] = round(pct_base / 2.0, 2)
    datos["horas_no_lectivas"] = horas_no_lectivas
    datos["horas_academicas_utilizadas"] = round(
        float(datos.get("horas_comisiones", 0) or 0)
        + horas_no_lectivas
        + float(datos.get("horas_investigacion", 0) or 0)
        + float(datos.get("horas_extension", 0) or 0),
        2,
    )
    return datos


# --- entry l. 32479-32497
def get_designaciones(periodo_id=None):
    # v212: al consultar un período, reparar primero las bajas históricas que ya
    # existen como movimiento real pero dejaron vacía fecha_finalizacion_efectiva.
    # Se usa globals() porque la rutina v212 se define más abajo en el archivo.
    if periodo_id is not None:
        try:
            _repair_v212 = globals().get("reconciliar_fechas_finalizacion_desde_movimientos_v212")
            if callable(_repair_v212):
                _repair_v212(int(periodo_id))
        except Exception:
            pass
    conn=get_conn();f="";p=[]
    if periodo_id is not None:f="WHERE d.periodo_id=?";p=[int(periodo_id)]
    df=pd.read_sql(f"""SELECT d.id,d.periodo_id,per.nombre AS periodo,CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido||', '||doc.nombres WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE '' END AS nombre_completo,
        d.cuil,d.cargo,d.dedicacion,d.horas,d.tipo_designacion,COALESCE(d.numero_resolucion,'') AS numero_resolucion,d.ad_honorem,d.fecha_desde,d.fecha_hasta,
        COALESCE(NULLIF(d.fecha_hasta_prevista,''),d.fecha_hasta) AS fecha_hasta_prevista,d.fecha_finalizacion_efectiva,d.fecha_registro_finalizacion,d.motivo_finalizacion,
        CASE WHEN per.estado='Cerrado' AND d.estado='Activa' THEN 'Finalizada' ELSE d.estado END AS estado,d.observaciones
        FROM designaciones d LEFT JOIN docentes doc ON d.cuil=doc.cuil LEFT JOIN periodos per ON d.periodo_id=per.id {f}
        ORDER BY per.anio DESC,per.semestre DESC,doc.apellido,doc.nombres""",conn,params=p);conn.close();return df


# --- entry l. 32773
_get_resumen_docente_base_v95 = get_resumen_docente


# --- entry l. 32774-32795
def get_resumen_docente(cuil):
    df_docente, _, df_movimientos = _get_resumen_docente_base_v95(cuil)
    conn = get_conn()
    df_designaciones = pd.read_sql("""
        SELECT p.nombre AS periodo, p.fecha_inicio AS periodo_inicio, p.fecha_fin AS periodo_fin,
               d.cargo, d.dedicacion, d.horas, d.tipo_designacion, COALESCE(d.numero_resolucion,'') AS numero_resolucion, d.ad_honorem,
               COALESCE(d.funcion_no_docente, 0) AS funcion_no_docente,
               COALESCE(d.texto_funcion_no_docente, '') AS texto_funcion_no_docente,
               d.fecha_desde,
               COALESCE(NULLIF(d.fecha_hasta_prevista,''), d.fecha_hasta) AS fecha_hasta_prevista,
               d.fecha_finalizacion_efectiva,
               d.fecha_registro_finalizacion,
               d.motivo_finalizacion,
               CASE WHEN p.estado='Cerrado' AND d.estado='Activa' THEN 'Finalizada' ELSE d.estado END AS estado,
               d.observaciones
        FROM designaciones d
        LEFT JOIN periodos p ON p.id=d.periodo_id
        WHERE d.cuil=?
        ORDER BY p.anio DESC, p.semestre DESC, d.fecha_desde DESC, d.id DESC
    """, conn, params=[str(cuil)])
    conn.close()
    return df_docente, df_designaciones, df_movimientos


# --- entry l. 33644-33646
def _inicio_cuil_clave(valor):
    from analisis.motor.ref.extracted_batch02.safe_helpers import _inicio_cuil_clave as _b02_core__inicio_cuil_clave
    return _b02_core__inicio_cuil_clave(valor)


# --- entry l. 33647-33649
def _inicio_fecha_segura(valor):
    from analisis.motor.ref.common.dates import _inicio_fecha_segura as _b05_core__inicio_fecha_segura
    return _b05_core__inicio_fecha_segura(valor)


# --- entry l. 33652-33654
def _inicio_contexto_designacion(fila):
    from analisis.motor.ref.extracted_batch01.designaciones import _inicio_contexto_designacion as _b01_core__inicio_contexto_designacion
    return _b01_core__inicio_contexto_designacion(fila)


# --- entry l. 33663-34179
def _inicio_datos_tablero_cache(periodo_id, institucion_id, departamento_id, hoy_iso):
    """Calcula el tablero de inicio en bloque para evitar consultas repetidas en cada rerun.

    El cache se segmenta por institución/departamento/período y dura solo 60 segundos.
    Los módulos operativos siguen siendo la fuente de verdad; este tablero es una vista ejecutiva.
    """
    metricas = get_metricas_analisis_periodo(int(periodo_id))
    df_plantel = metricas.get("df_plantel", pd.DataFrame()).copy()
    df_desig = metricas.get("df_desig", pd.DataFrame()).copy()
    df_com = metricas.get("df_com", pd.DataFrame()).copy()
    df_asig = metricas.get("df_asig", pd.DataFrame()).copy()

    # --- Plantel y designaciones activas propias ---
    if not df_desig.empty:
        df_desig_act = df_desig[df_desig.get("estado", pd.Series(index=df_desig.index, dtype=str)).fillna("").astype(str).eq("Activa")].copy()
        if "funcion_no_docente" in df_desig_act.columns:
            df_desig_act = df_desig_act[
                ~df_desig_act["funcion_no_docente"].map(_es_funcion_no_docente_v162)
            ].copy()
    else:
        df_desig_act = pd.DataFrame()

    if not df_plantel.empty:
        if "tipo_docente" in df_plantel.columns:
            df_propios = df_plantel[df_plantel["tipo_docente"].fillna("Propio").astype(str).str.strip().ne("Prestado")].copy()
        else:
            df_propios = df_plantel.copy()
        if "estado_operativo_periodo" in df_propios.columns:
            df_propios_act = df_propios[df_propios["estado_operativo_periodo"].fillna("").astype(str).eq("Activo en el período")].copy()
        else:
            df_propios_act = df_propios.copy()
    else:
        df_propios_act = pd.DataFrame()

    activos_cuil = set(_inicio_cuil_clave(x) for x in df_propios_act.get("cuil", pd.Series(dtype=str)).tolist() if _inicio_cuil_clave(x))
    # Una persona registrada como "Activo" pero cuya única designación vigente es
    # para funciones no docentes no forma parte del plantel docente operativo.
    cuiles_docentes_designados = set(
        _inicio_cuil_clave(x)
        for x in df_desig_act.get("cuil", pd.Series(dtype=str)).tolist()
        if _inicio_cuil_clave(x)
    )
    activos_cuil = activos_cuil & cuiles_docentes_designados

    # --- Comisiones cubiertas / sin cubrir ---
    if not df_com.empty:
        docentes_num = pd.to_numeric(df_com.get("docentes_asignados", pd.Series(index=df_com.index, dtype=float)), errors="coerce").fillna(0)
        df_sin_cubrir = df_com[docentes_num <= 0].copy()
        comisiones_activas = int(len(df_com))
        comisiones_cubiertas = int((docentes_num > 0).sum())
    else:
        df_sin_cubrir = pd.DataFrame()
        comisiones_activas = 0
        comisiones_cubiertas = 0
    cobertura = round((comisiones_cubiertas / comisiones_activas * 100), 1) if comisiones_activas else 0.0

    # Promedio de docentes activos distintos por comisión. Incluye docentes propios
    # y prestados porque describe la dotación real de las comisiones del departamento.
    docentes_por_comision = 0.0
    try:
        if comisiones_activas > 0 and isinstance(df_asig, pd.DataFrame) and not df_asig.empty and "comision_id" in df_asig.columns:
            asig_prom = df_asig.copy()
            estado_prom = asig_prom.get("estado", pd.Series(index=asig_prom.index, dtype=str)).fillna("Activa").astype(str).str.strip().str.lower()
            asig_prom = asig_prom[estado_prom.eq("activa")].copy()
            ids_com_inicio = set(pd.to_numeric(df_com.get("id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist()) if "id" in df_com.columns else set()
            asig_prom["_cid_inicio_v151"] = pd.to_numeric(asig_prom["comision_id"], errors="coerce")
            if ids_com_inicio:
                asig_prom = asig_prom[asig_prom["_cid_inicio_v151"].isin(ids_com_inicio)].copy()
            asig_prom["_cuil_inicio_v151"] = asig_prom.get("cuil", pd.Series(index=asig_prom.index, dtype=str)).map(_inicio_cuil_clave)
            pares_doc_com = asig_prom[asig_prom["_cid_inicio_v151"].notna() & asig_prom["_cuil_inicio_v151"].astype(str).ne("")][["_cid_inicio_v151", "_cuil_inicio_v151"]].drop_duplicates()
            docentes_por_comision = round(float(len(pares_doc_com)) / float(comisiones_activas), 2)
    except Exception:
        docentes_por_comision = 0.0

    # --- Horas y actividad docente ---
    if not df_asig.empty:
        df_asig_act = df_asig[df_asig.get("estado", pd.Series(index=df_asig.index, dtype=str)).fillna("Activa").astype(str).eq("Activa")].copy()
        if "tipo_docente" in df_asig_act.columns:
            df_asig_propios = df_asig_act[df_asig_act["tipo_docente"].fillna("Propio").astype(str).str.strip().ne("Prestado")].copy()
        else:
            df_asig_propios = df_asig_act.copy()
    else:
        df_asig_act = pd.DataFrame()
        df_asig_propios = pd.DataFrame()

    comision_cuil = set(_inicio_cuil_clave(x) for x in df_asig_propios.get("cuil", pd.Series(dtype=str)).tolist() if _inicio_cuil_clave(x))

    # Investigación y extensión: una sola lectura liviana para conjuntos y horas por docente.
    inv_horas_por_cuil = {}
    ext_horas_por_cuil = {}
    inv_cuil = set()
    ext_cuil = set()
    try:
        conn = get_conn()
        df_inv_inicio = pd.read_sql("""
            SELECT cuil, COALESCE(horas_asignadas, 0) AS horas_asignadas
            FROM investigacion_docente
            WHERE periodo_id = ?
              AND COALESCE(estado_asignacion, 'Activa') = 'Activa'
        """, conn, params=[int(periodo_id)])
        df_ext_inicio = pd.read_sql("""
            SELECT cuil, COALESCE(horas_asignadas, 0) AS horas_asignadas
            FROM extension_docente
            WHERE periodo_id = ?
              AND COALESCE(estado_asignacion, 'Activa') = 'Activa'
        """, conn, params=[int(periodo_id)])
        conn.close()
        for _, r in df_inv_inicio.iterrows():
            c = _inicio_cuil_clave(r.get("cuil"))
            if c:
                inv_cuil.add(c)
                hs_inv = pd.to_numeric(r.get("horas_asignadas"), errors="coerce")
                try:
                    hs_inv = float(hs_inv) if not pd.isna(hs_inv) else 0.0
                except Exception:
                    hs_inv = 0.0
                inv_horas_por_cuil[c] = inv_horas_por_cuil.get(c, 0.0) + hs_inv
        for _, r in df_ext_inicio.iterrows():
            c = _inicio_cuil_clave(r.get("cuil"))
            if c:
                ext_cuil.add(c)
                hs_ext = pd.to_numeric(r.get("horas_asignadas"), errors="coerce")
                try:
                    hs_ext = float(hs_ext) if not pd.isna(hs_ext) else 0.0
                except Exception:
                    hs_ext = 0.0
                ext_horas_por_cuil[c] = ext_horas_por_cuil.get(c, 0.0) + hs_ext
    except Exception:
        pass

    docentes_con_carga = comision_cuil | inv_cuil | ext_cuil
    docentes_sin_carga_cuil = activos_cuil - docentes_con_carga
    docentes_sin_carga = int(len(docentes_sin_carga_cuil))

    # --- Docentes sin carga: detalle identificable para el Inicio ---
    filas_sin_carga = []
    if docentes_sin_carga_cuil:
        df_propios_aux = df_propios_act.copy()
        if not df_propios_aux.empty:
            df_propios_aux["_cuil_inicio"] = df_propios_aux.get(
                "cuil", pd.Series(index=df_propios_aux.index, dtype=str)
            ).map(_inicio_cuil_clave)

        df_desig_aux = df_desig_act.copy()
        if not df_desig_aux.empty:
            df_desig_aux["_cuil_inicio"] = df_desig_aux.get(
                "cuil", pd.Series(index=df_desig_aux.index, dtype=str)
            ).map(_inicio_cuil_clave)

        for cuil_clave in sorted(docentes_sin_carga_cuil):
            nombre = cuil_clave
            cuil_visible = cuil_clave
            if not df_propios_aux.empty:
                sub_p = df_propios_aux[df_propios_aux["_cuil_inicio"] == cuil_clave]
                if not sub_p.empty:
                    fila_p = sub_p.iloc[0]
                    nombre = str(
                        fila_p.get("nombre_completo")
                        or fila_p.get("docente")
                        or fila_p.get("nombre")
                        or cuil_clave
                    ).strip()
                    cuil_visible = str(fila_p.get("cuil") or cuil_clave).strip()

            designaciones_txt = []
            horas_doc = 0.0
            if not df_desig_aux.empty:
                sub_d = df_desig_aux[df_desig_aux["_cuil_inicio"] == cuil_clave]
                for _, fila_d in sub_d.iterrows():
                    contexto = _inicio_contexto_designacion(fila_d)
                    if contexto and contexto not in designaciones_txt:
                        designaciones_txt.append(contexto)
                    hs = pd.to_numeric(fila_d.get("horas"), errors="coerce")
                    try:
                        horas_doc += float(hs) if not pd.isna(hs) else 0.0
                    except Exception:
                        pass

            filas_sin_carga.append({
                "Docente": nombre,
                "CUIL": cuil_visible,
                "Designación/es activa/s": " / ".join(designaciones_txt) if designaciones_txt else "—",
                "Horas de designación": round(horas_doc, 2),
                "Situación": "Sin comisiones, investigación ni extensión asignada",
            })
    df_sin_carga = pd.DataFrame(filas_sin_carga)

    # --- Horas por docente para el control de dedicación ---
    horas_contratadas_por_cuil = {}
    if not df_desig_act.empty:
        for _, r in df_desig_act.iterrows():
            c = _inicio_cuil_clave(r.get("cuil"))
            if not c:
                continue
            hs = pd.to_numeric(r.get("horas"), errors="coerce")
            try:
                hs = float(hs) if not pd.isna(hs) else 0.0
            except Exception:
                hs = 0.0
            horas_contratadas_por_cuil[c] = horas_contratadas_por_cuil.get(c, 0.0) + hs

    horas_comision_por_cuil = {}
    if not df_asig_propios.empty:
        for _, r in df_asig_propios.iterrows():
            c = _inicio_cuil_clave(r.get("cuil"))
            if not c:
                continue
            hs = pd.to_numeric(r.get("horas_asignadas"), errors="coerce")
            try:
                hs = float(hs) if not pd.isna(hs) else 0.0
            except Exception:
                hs = 0.0
            horas_comision_por_cuil[c] = horas_comision_por_cuil.get(c, 0.0) + hs

    # --- Asignaciones docentes con problemas ---
    # Se usa el diagnóstico oficial de la app, que respeta período, departamento,
    # docentes prestados/origen y la jerarquía de las designaciones activas.
    diagnostico_asignaciones = {
        "correctas": 0,
        "a_corregir": 0,
        "sin_resolver": 0,
        "detalle": pd.DataFrame(),
    }
    try:
        diagnostico_asignaciones = diagnosticar_cargos_asignaciones_periodo(int(periodo_id)) or diagnostico_asignaciones
    except Exception:
        pass

    df_diag_asignaciones = diagnostico_asignaciones.get("detalle", pd.DataFrame())
    if df_diag_asignaciones is None:
        df_diag_asignaciones = pd.DataFrame()
    else:
        df_diag_asignaciones = df_diag_asignaciones.copy()

    if not df_diag_asignaciones.empty and "Estado" in df_diag_asignaciones.columns:
        df_problemas = df_diag_asignaciones[
            df_diag_asignaciones["Estado"].fillna("").astype(str).str.strip().ne("Correcto")
        ].copy()
    else:
        df_problemas = pd.DataFrame()

    # Enriquecemos el diagnóstico con código/materia para que el usuario pueda
    # localizar rápidamente la comisión en el módulo correspondiente.
    if not df_problemas.empty and not df_asig_act.empty and "Comisión ID" in df_problemas.columns:
        columnas_meta = [
            c for c in [
                "comision_id", "codigo_materia", "asignatura", "materia_especifica",
                "turno", "sede", "modalidad"
            ] if c in df_asig_act.columns
        ]
        if "comision_id" in columnas_meta:
            meta_com = df_asig_act[columnas_meta].copy()
            meta_com = meta_com.drop_duplicates(subset=["comision_id"], keep="first")
            df_problemas = df_problemas.merge(
                meta_com,
                left_on="Comisión ID",
                right_on="comision_id",
                how="left",
            )

    asignaciones_problema = int(len(df_problemas))

    # --- Exceso de dedicación, con productividad del plantel propio consolidada institucionalmente ---
    # Incluye horas no lectivas según dotación de comisión y carga del docente en otros departamentos.
    try:
        df_prod_inicio = get_docentes_productividad_periodo(int(periodo_id))
    except Exception:
        df_prod_inicio = pd.DataFrame()
    # Productividad promedio del plantel propio activo del departamento.
    # Se usa exactamente el mismo porcentaje individual que aparece en Análisis
    # (porcentaje_uso) y se calcula un promedio simple entre los docentes mostrados allí.
    productividad_promedio_docentes = 0.0
    if df_prod_inicio is not None and not df_prod_inicio.empty and "porcentaje_uso" in df_prod_inicio.columns:
        serie_pct_inicio = pd.to_numeric(df_prod_inicio["porcentaje_uso"], errors="coerce").dropna()
        if not serie_pct_inicio.empty:
            productividad_promedio_docentes = round(float(serie_pct_inicio.mean()), 2)

    sobrecarga = []
    if df_prod_inicio is not None and not df_prod_inicio.empty:
        for _, r in df_prod_inicio.iterrows():
            contratadas = float(pd.to_numeric(r.get("horas_contratadas"), errors="coerce") or 0)
            utilizadas = float(pd.to_numeric(r.get("horas_utilizadas"), errors="coerce") or 0)
            if contratadas > 0 and utilizadas > contratadas + 1e-9:
                sobrecarga.append({
                    "docente": str(r.get("docente") or r.get("cuil") or "").strip(),
                    "horas_contratadas": round(contratadas, 2),
                    "horas_registradas": round(utilizadas, 2),
                    "horas_no_lectivas": round(float(pd.to_numeric(r.get("horas_no_lectivas"), errors="coerce") or 0), 2),
                    "porcentaje_productividad": round(float(pd.to_numeric(r.get("porcentaje_uso"), errors="coerce") or 0), 2),
                    "exceso": round(utilizadas - contratadas, 2),
                })
    df_sobrecarga = pd.DataFrame(sobrecarga)

    # --- Superposiciones ---
    try:
        df_super = get_superposiciones_periodo(int(periodo_id))
    except Exception:
        df_super = pd.DataFrame()

    # --- Comisiones sin horario ---
    try:
        df_sin_horario = get_comisiones_sin_horarios_periodo(int(periodo_id))
    except Exception:
        df_sin_horario = pd.DataFrame()

    # --- Duplicados de personas por CUIL normalizado dentro del departamento ---
    df_duplicados = pd.DataFrame()
    try:
        conn = get_conn()
        if USE_POSTGRESQL:
            df_duplicados = pd.read_sql("""
                SELECT regexp_replace(COALESCE(cuil, ''), '[^0-9]', '', 'g') AS cuil_normalizado,
                       COUNT(*) AS cantidad
                FROM docentes
                WHERE COALESCE(cuil, '') <> ''
                GROUP BY regexp_replace(COALESCE(cuil, ''), '[^0-9]', '', 'g')
                HAVING COUNT(*) > 1
            """, conn)
        else:
            df_dup_base = pd.read_sql("SELECT cuil FROM docentes WHERE COALESCE(cuil, '') <> ''", conn)
            if not df_dup_base.empty:
                df_dup_base["cuil_normalizado"] = df_dup_base["cuil"].map(_inicio_cuil_clave)
                df_duplicados = df_dup_base.groupby("cuil_normalizado").size().reset_index(name="cantidad")
                df_duplicados = df_duplicados[df_duplicados["cantidad"] > 1].copy()
        conn.close()
    except Exception:
        df_duplicados = pd.DataFrame()

    # Agrega nombres visibles a los CUIL duplicados para poder identificarlos desde Inicio.
    if df_duplicados is not None and not df_duplicados.empty:
        try:
            conn = get_conn()
            df_doc_dup = pd.read_sql(
                """
                SELECT cuil,
                       CASE
                           WHEN apellido IS NOT NULL AND nombres IS NOT NULL
                               THEN apellido || ', ' || nombres
                           WHEN nombre IS NOT NULL THEN nombre
                           ELSE cuil
                       END AS docente
                FROM docentes
                WHERE COALESCE(cuil, '') <> ''
                """,
                conn,
            )
            conn.close()
            if not df_doc_dup.empty:
                df_doc_dup["_cuil_norm"] = df_doc_dup["cuil"].map(_inicio_cuil_clave)
                nombres_dup = (
                    df_doc_dup.groupby("_cuil_norm")["docente"]
                    .apply(lambda s: " / ".join(dict.fromkeys(str(x).strip() for x in s if str(x).strip())))
                    .to_dict()
                )
                df_duplicados["Docente/s"] = df_duplicados["cuil_normalizado"].map(nombres_dup).fillna("")
                df_duplicados = df_duplicados.rename(columns={
                    "cuil_normalizado": "CUIL normalizado",
                    "cantidad": "Cantidad de registros",
                })
        except Exception:
            pass

    # --- Vencimientos próximos (30 días desde hoy) ---
    hoy = _inicio_fecha_segura(hoy_iso) or date.today()
    limite = hoy + pd.Timedelta(days=30)
    limite = limite.date() if hasattr(limite, "date") else limite
    vencimientos = []
    if not df_desig_act.empty:
        for _, r in df_desig_act.iterrows():
            f = _inicio_fecha_segura(r.get("fecha_hasta_prevista") or r.get("fecha_hasta"))
            if f is None or f < hoy or f > limite:
                continue
            vencimientos.append({
                "Docente": str(r.get("nombre_completo") or r.get("cuil") or "").strip(),
                "Designación": _inicio_contexto_designacion(r),
                "Vencimiento": f.strftime("%d/%m/%Y"),
                "Días": int((f - hoy).days),
                "_fecha": f,
            })
    df_vencimientos = pd.DataFrame(vencimientos)
    if not df_vencimientos.empty:
        df_vencimientos = df_vencimientos.sort_values(["_fecha", "Docente"], kind="stable").reset_index(drop=True)

    # --- Correcta configuración del período ---
    periodo_ok = True
    df_periodo_detalle = pd.DataFrame()
    try:
        conn = get_conn()
        df_periodo = pd.read_sql(
            "SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado FROM periodos WHERE id = ? LIMIT 1",
            conn,
            params=[int(periodo_id)],
        )
        conn.close()
        if df_periodo.empty:
            periodo_ok = False
            df_periodo_detalle = pd.DataFrame([{
                "Control": "Período",
                "Valor actual": "No encontrado",
                "Valor esperado": "Período abierto y correctamente configurado",
                "Resultado": "Revisar",
            }])
        else:
            rp = df_periodo.iloc[0].to_dict()
            fi_esperada, ff_esperada = fechas_periodo(int(rp.get("anio")), int(rp.get("semestre")))
            estado_actual = str(rp.get("estado") or "").strip()
            fi_actual = str(rp.get("fecha_inicio") or "")[:10]
            ff_actual = str(rp.get("fecha_fin") or "")[:10]
            estado_ok = estado_actual == "Abierto"
            fi_ok = fi_actual == str(fi_esperada)
            ff_ok = ff_actual == str(ff_esperada)
            periodo_ok = bool(estado_ok and fi_ok and ff_ok)
            df_periodo_detalle = pd.DataFrame([
                {
                    "Control": "Estado",
                    "Valor actual": estado_actual or "—",
                    "Valor esperado": "Abierto",
                    "Resultado": "Correcto" if estado_ok else "Revisar",
                },
                {
                    "Control": "Fecha de inicio",
                    "Valor actual": fi_actual or "—",
                    "Valor esperado": str(fi_esperada),
                    "Resultado": "Correcto" if fi_ok else "Revisar",
                },
                {
                    "Control": "Fecha de finalización",
                    "Valor actual": ff_actual or "—",
                    "Valor esperado": str(ff_esperada),
                    "Resultado": "Correcto" if ff_ok else "Revisar",
                },
            ])
    except Exception as exc:
        periodo_ok = False
        df_periodo_detalle = pd.DataFrame([{
            "Control": "Período",
            "Valor actual": "No se pudo verificar",
            "Valor esperado": "Período abierto y correctamente configurado",
            "Resultado": f"Revisar: {exc}",
        }])

    # --- Salud: índice operativo ponderado (no es una auditoría formal) ---
    n_super = int(len(df_super)) if df_super is not None else 0
    n_sobrecarga = int(len(df_sobrecarga)) if df_sobrecarga is not None else 0
    n_sin_horario = int(len(df_sin_horario)) if df_sin_horario is not None else 0
    n_dup = int(len(df_duplicados)) if df_duplicados is not None else 0
    salud = 100
    salud -= min(25, n_super * 5)
    salud -= min(25, n_sobrecarga * 5)
    salud -= min(25, asignaciones_problema * 5)
    salud -= min(10, n_sin_horario * 2)
    salud -= min(10, n_dup * 5)
    if not periodo_ok:
        salud -= 15
    salud = max(0, min(100, int(salud)))

    # Alertas críticas: solo problemas que requieren intervención prioritaria.
    alertas_criticas = int(len(df_sin_cubrir)) + n_super + n_sobrecarga + asignaciones_problema

    # Distribución del plantel por cargo: docentes únicos dentro de cada cargo activo.
    cargos_orden = ["Titular", "Asociado", "Adjunto", "JTP", "Ayudante 1ra", "Ayudante 2da"]
    filas_cargos = []
    if not df_desig_act.empty:
        base_cargos = df_desig_act.copy()
        base_cargos["_cuil"] = base_cargos.get("cuil", pd.Series(index=base_cargos.index, dtype=str)).map(_inicio_cuil_clave)
        for cargo in cargos_orden:
            sub = base_cargos[base_cargos.get("cargo", pd.Series(index=base_cargos.index, dtype=str)).fillna("").astype(str).str.strip().eq(cargo)]
            filas_cargos.append({"Cargo": cargo, "Docentes": int(sub["_cuil"].replace("", pd.NA).dropna().nunique())})
    df_cargos = pd.DataFrame(filas_cargos)

    # Resumen de horas.
    horas_contratadas = float(metricas.get("horas_contratadas", 0) or 0)
    horas_comisiones = float(metricas.get("horas_comisiones", 0) or 0)
    horas_no_lectivas = float(metricas.get("horas_no_lectivas", 0) or 0)
    porcentaje_no_lectivas = float(metricas.get("porcentaje_horas_no_lectivas", 0) or 0)
    horas_investigacion = float(metricas.get("horas_investigacion", 0) or 0)
    horas_extension = float(metricas.get("horas_extension", 0) or 0)
    horas_utilizadas = float(metricas.get("horas_academicas_utilizadas", horas_comisiones + horas_no_lectivas + horas_investigacion + horas_extension) or 0)
    horas_disponibles = max(horas_contratadas - horas_utilizadas, 0.0)
    horas_exceso = max(horas_utilizadas - horas_contratadas, 0.0)
    promedio_horas = round(horas_utilizadas / max(int(metricas.get("docentes_activos", 0) or 0), 1), 1) if int(metricas.get("docentes_activos", 0) or 0) else 0.0

    return {
        "metricas": metricas,
        "df_sin_cubrir": df_sin_cubrir,
        "df_sin_carga": df_sin_carga,
        "df_problemas": df_problemas,
        "df_diag_asignaciones": df_diag_asignaciones,
        "df_super": df_super,
        "df_sobrecarga": df_sobrecarga,
        "df_sin_horario": df_sin_horario,
        "df_duplicados": df_duplicados,
        "df_periodo_detalle": df_periodo_detalle,
        "df_vencimientos": df_vencimientos,
        "df_cargos": df_cargos,
        "docentes_sin_carga": docentes_sin_carga,
        "docentes_sin_carga_cuil": sorted(docentes_sin_carga_cuil),
        "comisiones_activas": comisiones_activas,
        "comisiones_cubiertas": comisiones_cubiertas,
        "docentes_por_comision": round(docentes_por_comision, 2),
        "cobertura": cobertura,
        "asignaciones_problema": asignaciones_problema,
        "periodo_ok": bool(periodo_ok),
        "salud": salud,
        "alertas_criticas": alertas_criticas,
        "horas_contratadas": round(horas_contratadas, 2),
        "horas_comisiones": round(horas_comisiones, 2),
        "horas_no_lectivas": round(horas_no_lectivas, 2),
        "porcentaje_no_lectivas": round(porcentaje_no_lectivas, 2),
        "horas_investigacion": round(horas_investigacion, 2),
        "horas_extension": round(horas_extension, 2),
        "horas_utilizadas": round(horas_utilizadas, 2),
        "horas_disponibles": round(horas_disponibles, 2),
        "horas_exceso": round(horas_exceso, 2),
        "promedio_horas": promedio_horas,  # compatibilidad interna; ya no se muestra como KPI principal
        "productividad_promedio_docentes": round(productividad_promedio_docentes, 2),
    }


# --- entry l. 34235-34238
def _estado_designacion_visible_v162(valor):
    'Texto de presentación del estado sin alterar el valor persistido en la base.'
    from analisis.motor.ref.extracted_batch01.designaciones import _estado_designacion_visible_v162 as _b01_core__estado_designacion_visible_v162
    return _b01_core__estado_designacion_visible_v162(valor)


# --- entry l. 34246-34248
def _es_ad_honorem_v162(valor):
    from analisis.motor.ref.extracted_batch01.designaciones import _es_ad_honorem_v162 as _b01_core__es_ad_honorem_v162
    return _b01_core__es_ad_honorem_v162(valor)


# --- entry l. 34251-34253
def _es_funcion_no_docente_v162(valor):
    from analisis.motor.ref.extracted_batch04.designaciones import _es_funcion_no_docente_v162 as _b04_core__es_funcion_no_docente_v162
    return _b04_core__es_funcion_no_docente_v162(valor)


# --- entry l. 34409-34411
def _texto_funcion_no_docente_limpio_v164(valor):
    from analisis.motor.ref.extracted_batch01.docentes import _texto_funcion_no_docente_limpio_v164 as _b01_core__texto_funcion_no_docente_limpio_v164
    return _b01_core__texto_funcion_no_docente_limpio_v164(valor)


# --- entry l. 34440
_get_designaciones_pre_v162 = get_designaciones


# --- entry l. 34443-34478
def get_designaciones(periodo_id=None):
    df = _get_designaciones_pre_v162(periodo_id)
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    if out.empty:
        if "funcion_no_docente" not in out.columns:
            out["funcion_no_docente"] = pd.Series(dtype=int)
        if "texto_funcion_no_docente" not in out.columns:
            out["texto_funcion_no_docente"] = pd.Series(dtype=str)
        return out
    try:
        conn = get_conn()
        if periodo_id is None:
            extra = pd.read_sql(
                "SELECT id, COALESCE(funcion_no_docente, 0) AS funcion_no_docente, COALESCE(texto_funcion_no_docente, '') AS texto_funcion_no_docente FROM designaciones",
                conn,
            )
        else:
            extra = pd.read_sql(
                "SELECT id, COALESCE(funcion_no_docente, 0) AS funcion_no_docente, COALESCE(texto_funcion_no_docente, '') AS texto_funcion_no_docente FROM designaciones WHERE periodo_id = ?",
                conn,
                params=[int(periodo_id)],
            )
        conn.close()
        out = out.drop(columns=["funcion_no_docente", "texto_funcion_no_docente"], errors="ignore").merge(extra, on="id", how="left")
    except Exception:
        out["funcion_no_docente"] = 0
        out["texto_funcion_no_docente"] = ""
    out["funcion_no_docente"] = pd.to_numeric(
        out.get("funcion_no_docente", 0), errors="coerce"
    ).fillna(0).astype(int)
    if "texto_funcion_no_docente" not in out.columns:
        out["texto_funcion_no_docente"] = ""
    out["texto_funcion_no_docente"] = out["texto_funcion_no_docente"].fillna("").astype(str)
    return out


# --- entry l. 34650
_get_designaciones_periodo_institucional_pre_v162 = _get_designaciones_periodo_institucional_v149


# --- entry l. 34653-34737
def _sanear_designaciones_institucionales_v265(df):
    """Depura SOLO la vista consolidada institucional, sin modificar PostgreSQL.

    El Resumen docente de un compartido/prestado reúne designaciones de varios
    departamentos. Si quedó una fila residual de cargas antiguas con columnas
    concatenadas (por ejemplo nombre/período/fechas dentro de ``cargo``), esa fila
    no debe convertirse en otra designación ni sumar horas. También se eliminan
    duplicados lógicos idénticos de un mismo departamento visible, aun cuando
    provengan de IDs departamentales legacy diferentes.

    La pestaña Designaciones local sigue siendo la fuente física de verdad; esta
    función únicamente protege las lecturas institucionales consolidadas.
    """
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    if out.empty:
        return out

    # 1) Descarta filas estructuralmente imposibles para un cargo. No se exige que
    # el texto sea idéntico al canónico (para tolerar 'Profesor Adjunto', etc.),
    # pero sí se rechazan señales inequívocas de una fila concatenada/corrupta.
    if "cargo" in out.columns:
        def _cargo_valido_v265(valor):
            raw = limpiar_texto_tabla(valor)
            if not raw:
                return False
            # Un cargo nunca debe contener un período ni fechas ISO.
            if re.search(r"\b20\d{2}\s*[-/]\s*[12]\b", raw):
                return False
            if re.search(r"\b20\d{2}-\d{2}-\d{2}\b", raw):
                return False
            canon = _normalizar_cargo_para_jerarquia(raw)
            if canon not in CARGOS:
                return False
            raw_key = normalizar_clave(raw)
            canon_key = normalizar_clave(canon)
            # Si dentro del supuesto cargo aparecen además una dedicación o un
            # tipo de designación, es una fuerte señal de columnas pegadas.
            if raw_key != canon_key:
                tokens_prohibidos = [normalizar_clave(x) for x in (DEDICACIONES + TIPOS_DESIGNACION)]
                if any(tok and re.search(rf"(^| )%s($| )" % re.escape(tok), raw_key) for tok in tokens_prohibidos):
                    return False
            return True
        out = out[out["cargo"].map(_cargo_valido_v265)].copy()

    if out.empty:
        return out

    # 2) Quita duplicados lógicos dentro del mismo departamento visible. Esto
    # protege contra IDs legacy/homónimos sin mezclar designaciones realmente
    # distintas (Concursado + Interino, cargos/dedicaciones diferentes, etc.).
    def _serie_texto(col, default=""):
        if col in out.columns:
            return out[col].fillna(default).astype(str).map(limpiar_texto_tabla)
        return pd.Series(default, index=out.index, dtype=str)

    dep_nombre = _serie_texto("departamento")
    if "departamento_id" in out.columns:
        dep_id = pd.to_numeric(out["departamento_id"], errors="coerce")
    else:
        dep_id = pd.Series(float("nan"), index=out.index)
    out["_v265_dep_key"] = [
        normalizar_clave(nom) if normalizar_clave(nom) else (f"id:{int(did)}" if pd.notna(did) else "sin_departamento")
        for nom, did in zip(dep_nombre.tolist(), dep_id.tolist())
    ]
    out["_v265_cargo_key"] = _serie_texto("cargo").map(lambda x: normalizar_clave(_normalizar_cargo_para_jerarquia(x)))
    out["_v265_dedic_key"] = _serie_texto("dedicacion").map(normalizar_clave)
    out["_v265_tipo_key"] = _serie_texto("tipo_designacion").map(normalizar_clave)
    out["_v265_estado_key"] = _serie_texto("estado").map(normalizar_clave)
    out["_v265_hs_key"] = pd.to_numeric(out.get("horas", 0), errors="coerce").fillna(0).round(3)
    out["_v265_desde_key"] = _serie_texto("fecha_desde")
    out["_v265_hasta_key"] = _serie_texto("fecha_hasta")
    if "funcion_no_docente" in out.columns:
        out["_v265_nd_key"] = pd.to_numeric(out["funcion_no_docente"], errors="coerce").fillna(0).astype(int)
    else:
        out["_v265_nd_key"] = 0

    claves = [
        "_v265_dep_key", "_v265_cargo_key", "_v265_dedic_key", "_v265_tipo_key",
        "_v265_estado_key", "_v265_hs_key", "_v265_desde_key", "_v265_hasta_key", "_v265_nd_key",
    ]
    out = out.drop_duplicates(subset=claves, keep="first").copy()
    out = out.drop(columns=[c for c in claves if c in out.columns], errors="ignore")
    return out.reset_index(drop=True)


# --- entry l. 34740-34770
def _get_designaciones_periodo_institucional_v149(cuil, periodo_id):
    df = _get_designaciones_periodo_institucional_pre_v162(cuil, periodo_id)
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    if out.empty:
        if "funcion_no_docente" not in out.columns:
            out["funcion_no_docente"] = pd.Series(dtype=int)
        return out
    try:
        inst_id = _pg_current_inst_id()
        extra = _pg_read_dataframe("""
            SELECT id, COALESCE(funcion_no_docente, 0) AS funcion_no_docente,
                   COALESCE(texto_funcion_no_docente, '') AS texto_funcion_no_docente
            FROM designaciones
            WHERE institucion_id = %s
              AND regexp_replace(COALESCE(cuil,''), '[^0-9]', '', 'g') = %s
        """, [int(inst_id), _clave_cuil(cuil)])
        out = out.drop(columns=["funcion_no_docente", "texto_funcion_no_docente"], errors="ignore").merge(extra, on="id", how="left")
    except Exception:
        out["funcion_no_docente"] = 0
        out["texto_funcion_no_docente"] = ""
    out["funcion_no_docente"] = pd.to_numeric(
        out.get("funcion_no_docente", 0), errors="coerce"
    ).fillna(0).astype(int)
    if "texto_funcion_no_docente" not in out.columns:
        out["texto_funcion_no_docente"] = ""
    out["texto_funcion_no_docente"] = out["texto_funcion_no_docente"].fillna("").astype(str)
    # v265: toda lectura institucional (Resumen, productividad de compartidos,
    # etc.) recibe una fuente saneada. No se borra ni corrige ningún registro.
    return _sanear_designaciones_institucionales_v265(out)


# --- entry l. 34773-34775
def _designaciones_docentes_activas_v162(df):
    from analisis.motor.ref.domain.designaciones import _designaciones_docentes_activas_v162 as _b05_core__designaciones_docentes_activas_v162
    return _b05_core__designaciones_docentes_activas_v162(df)


# --- entry l. 34778-34797
def _horas_contratadas_docentes_v162(cuil, periodo_id):
    try:
        if USE_POSTGRESQL:
            df = _get_designaciones_periodo_institucional_v149(cuil, periodo_id)
        else:
            df = get_designaciones(periodo_id)
            if not df.empty:
                df = df[
                    df.get("cuil", pd.Series(index=df.index, dtype=str))
                    .fillna("").astype(str).map(_clave_cuil).eq(_clave_cuil(cuil))
                ].copy()
        df = _designaciones_docentes_activas_v162(df)
        if df.empty:
            return 0.0
        total = 0.0
        for _, r in df.iterrows():
            total += float(horas_segun_dedicacion(r.get("dedicacion"), r.get("horas", 0)) or 0)
        return round(total, 2)
    except Exception:
        return 0.0


# --- entry l. 34800-34822
def _cuiles_designacion_docente_activa_institucional_v162(periodo_id):
    if not USE_POSTGRESQL:
        return _cuiles_designacion_activa_local_v151(periodo_id)
    try:
        inst_id = _pg_current_inst_id()
        nombre_p, anio, semestre = _periodo_equivalente_pg(periodo_id)
        df = _pg_read_dataframe("""
            SELECT DISTINCT d.cuil
            FROM designaciones d
            JOIN periodos p ON p.id = d.periodo_id
            WHERE d.institucion_id = %s
              AND p.institucion_id = d.institucion_id
              AND p.departamento_id IS NOT DISTINCT FROM d.departamento_id
              AND (d.periodo_id = %s OR p.nombre = %s OR (p.anio = %s AND p.semestre = %s))
              AND COALESCE(d.estado, 'Activa') = 'Activa'
              AND COALESCE(d.funcion_no_docente, 0) = 0
        """, [int(inst_id), int(periodo_id), nombre_p, int(anio), int(semestre)])
        return {
            _clave_cuil(x) for x in df.get("cuil", pd.Series(dtype=str)).tolist()
            if _clave_cuil(x)
        }
    except Exception:
        return set()


# --- entry l. 34825-34834
def _cuiles_designacion_activa_local_v151(periodo_id):
    """CUIL con al menos una designación docente activa en el departamento actual."""
    try:
        df = _designaciones_docentes_activas_v162(get_designaciones(periodo_id))
    except Exception:
        df = pd.DataFrame()
    return {
        _clave_cuil(x) for x in df.get("cuil", pd.Series(dtype=str)).tolist()
        if _clave_cuil(x)
    }


# --- entry l. 34857
_get_productividad_docente_institucional_pre_v162 = get_productividad_docente_institucional_v149


# --- entry l. 34860-34867
def get_productividad_docente_institucional_v149(cuil, periodo_id):
    datos = dict(_get_productividad_docente_institucional_pre_v162(cuil, periodo_id) or {})
    contratadas = _horas_contratadas_docentes_v162(cuil, periodo_id)
    utilizadas = float(datos.get("horas_utilizadas", 0) or 0)
    datos["horas_contratadas"] = round(contratadas, 2)
    datos["horas_disponibles"] = round(contratadas - utilizadas, 2)
    datos["porcentaje"] = round((utilizadas / contratadas * 100.0), 2) if contratadas > 0 else 0.0
    return datos


# --- entry l. 34870
_get_productividad_docente_departamento_pre_v162 = _productividad_docente_departamento_v148


# --- entry l. 34873-34893
def _productividad_docente_departamento_v148(cuil, periodo_id):
    datos = dict(_get_productividad_docente_departamento_pre_v162(cuil, periodo_id) or {})
    try:
        df = get_designaciones(periodo_id)
        if not df.empty:
            df = df[
                df.get("cuil", pd.Series(index=df.index, dtype=str))
                .fillna("").astype(str).map(_clave_cuil).eq(_clave_cuil(cuil))
            ].copy()
        df = _designaciones_docentes_activas_v162(df)
        contratadas = sum(
            float(horas_segun_dedicacion(r.get("dedicacion"), r.get("horas", 0)) or 0)
            for _, r in df.iterrows()
        ) if not df.empty else 0.0
        utilizadas = float(datos.get("horas_utilizadas", 0) or 0)
        datos["horas_contratadas"] = round(contratadas, 2)
        datos["horas_disponibles"] = round(contratadas - utilizadas, 2)
        datos["porcentaje"] = round((utilizadas / contratadas * 100.0), 2) if contratadas > 0 else 0.0
    except Exception:
        pass
    return datos


# --- entry l. 34896
_get_docentes_productividad_periodo_pre_v162 = get_docentes_productividad_periodo


# --- entry l. 34899-34915
def get_docentes_productividad_periodo(periodo_id):
    df = _get_docentes_productividad_periodo_pre_v162(periodo_id)
    if df is None or df.empty:
        return df
    habilitados = _cuiles_designacion_activa_local_v151(periodo_id)
    out = df[
        df.get("cuil", pd.Series(index=df.index, dtype=str))
        .fillna("").astype(str).map(_clave_cuil).isin(habilitados)
    ].copy()
    for idx, r in out.iterrows():
        cuil = r.get("cuil", "")
        contratadas = _horas_contratadas_docentes_v162(cuil, periodo_id)
        utilizadas = float(pd.to_numeric(r.get("horas_utilizadas"), errors="coerce") or 0)
        out.at[idx, "horas_contratadas"] = round(contratadas, 2)
        out.at[idx, "horas_disponibles"] = round(contratadas - utilizadas, 2)
        out.at[idx, "porcentaje_uso"] = round((utilizadas / contratadas * 100.0), 2) if contratadas > 0 else 0.0
    return _redondear_numericos_productividad_v150(out).reset_index(drop=True)


# --- entry l. 34918
_get_metricas_analisis_periodo_pre_v162 = get_metricas_analisis_periodo


# --- entry l. 34921-34972
def get_metricas_analisis_periodo(periodo_id):
    datos = dict(_get_metricas_analisis_periodo_pre_v162(periodo_id) or {})
    df_desig = get_designaciones(periodo_id)
    df_doc_act = _designaciones_docentes_activas_v162(df_desig)
    datos["df_desig"] = df_desig
    datos["docentes_activos"] = int(
        df_doc_act.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).replace("", pd.NA).dropna().nunique()
    ) if not df_doc_act.empty else 0
    datos["cargos_totales"] = int(len(df_doc_act))
    datos["horas_contratadas"] = round(sum(
        float(horas_segun_dedicacion(r.get("dedicacion"), r.get("horas", 0)) or 0)
        for _, r in df_doc_act.iterrows()
    ), 2) if not df_doc_act.empty else 0.0

    # Recalcula las horas académicas desde la tabla de productividad ya filtrada.
    try:
        df_prod = get_docentes_productividad_periodo(periodo_id)
        if df_prod is not None and not df_prod.empty:
            datos["horas_comisiones"] = round(float(pd.to_numeric(df_prod.get("horas_comisiones_reales"), errors="coerce").fillna(0).sum()), 2)
            datos["horas_no_lectivas"] = round(float(pd.to_numeric(df_prod.get("horas_no_lectivas"), errors="coerce").fillna(0).sum()), 2)
            datos["horas_investigacion"] = round(float(pd.to_numeric(df_prod.get("horas_investigacion"), errors="coerce").fillna(0).sum()), 2)
            datos["horas_extension"] = round(float(pd.to_numeric(df_prod.get("horas_extension"), errors="coerce").fillna(0).sum()), 2)
            datos["horas_academicas_utilizadas"] = round(float(pd.to_numeric(df_prod.get("horas_utilizadas"), errors="coerce").fillna(0).sum()), 2)
        else:
            for k in ["horas_comisiones", "horas_no_lectivas", "horas_investigacion", "horas_extension", "horas_academicas_utilizadas"]:
                datos[k] = 0.0
    except Exception:
        pass

    # Docentes propios en comisiones: solo CUIL con designación docente local activa.
    try:
        df_asig = datos.get("df_asig", pd.DataFrame())
        if isinstance(df_asig, pd.DataFrame) and not df_asig.empty:
            da = df_asig.copy()
            est = da.get("estado", pd.Series(index=da.index, dtype=str)).fillna("Activa").astype(str).str.strip().str.casefold()
            da = da[est.eq("activa")].copy()
            if "tipo_docente" in da.columns:
                da = da[da["tipo_docente"].fillna("Propio").astype(str).str.strip().str.casefold().ne("prestado")].copy()
            claves = da.get("cuil", pd.Series(index=da.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
            datos["docentes_en_comisiones"] = int(claves[claves.isin(_cuiles_designacion_activa_local_v151(periodo_id))].replace("", pd.NA).dropna().nunique())
            if "tipo_docente" in da.columns:
                prest = da[
                    da["tipo_docente"].fillna("Propio").astype(str).str.strip().str.casefold().eq("prestado")
                ].copy()
                claves_prest = prest.get("cuil", pd.Series(index=prest.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
                habilitados_inst = _cuiles_designacion_docente_activa_institucional_v162(periodo_id)
                datos["docentes_prestados_recibidos"] = int(
                    claves_prest[claves_prest.isin(habilitados_inst)].replace("", pd.NA).dropna().nunique()
                )
    except Exception:
        pass
    return datos


# --- entry l. 34976
_get_resumen_docente_pre_v162 = get_resumen_docente


# --- entry l. 34979-34984
def get_resumen_docente(cuil):
    df_docente, df_designaciones, df_movimientos = _get_resumen_docente_pre_v162(cuil)
    if isinstance(df_designaciones, pd.DataFrame) and not df_designaciones.empty and "estado" in df_designaciones.columns:
        df_designaciones = df_designaciones.copy()
        df_designaciones["estado"] = df_designaciones["estado"].map(_estado_designacion_visible_v162)
    return df_docente, df_designaciones, df_movimientos


# --- entry l. 34987
_get_designaciones_todos_deptos_pre_v162 = get_designaciones_docente_todos_departamentos_pg


# --- entry l. 34990-35040
def get_designaciones_docente_todos_departamentos_pg(cuil, periodo_id=None):
    base = _get_designaciones_todos_deptos_pre_v162(cuil, periodo_id)
    if base is None:
        base = pd.DataFrame()
    out = base.copy()
    if USE_POSTGRESQL and periodo_id is not None:
        try:
            inst_completo = _get_designaciones_periodo_institucional_v149(cuil, periodo_id)
            if inst_completo is not None and not inst_completo.empty:
                out = inst_completo.copy()
        except Exception:
            pass

    # En un período abierto la versión anterior traía solo Activas. Agrega las
    # Suspendidas para que el Resumen no las haga desaparecer.
    if USE_POSTGRESQL and periodo_id is not None:
        try:
            inst = _get_designaciones_periodo_institucional_v149(cuil, periodo_id)
            if inst is not None and not inst.empty:
                susp = inst[
                    inst.get("estado", pd.Series(index=inst.index, dtype=str))
                    .fillna("").astype(str).str.strip().str.casefold().eq("suspendida")
                ].copy()
                if not susp.empty:
                    cols = [
                        "departamento", "periodo", "cargo", "dedicacion", "horas",
                        "tipo_designacion", "estado", "fecha_desde", "fecha_hasta", "observaciones",
                    ]
                    for col in cols:
                        if col not in susp.columns:
                            susp[col] = ""
                    out = pd.concat([out, susp[cols]], ignore_index=True, sort=False)
                    claves_dup = [c for c in ["departamento", "periodo", "cargo", "dedicacion", "tipo_designacion", "fecha_desde", "fecha_hasta"] if c in out.columns]
                    if claves_dup:
                        out = out.drop_duplicates(subset=claves_dup, keep="first")
        except Exception:
            pass
    if not out.empty and "estado" in out.columns:
        out["estado"] = out["estado"].map(_estado_designacion_visible_v162)
    if not out.empty and "funcion_no_docente" in out.columns:
        out["funcion_no_docente"] = out["funcion_no_docente"].map(
            lambda x: "No docente" if _es_funcion_no_docente_v162(x) else "Docencia"
        )
    if "texto_funcion_no_docente" in out.columns:
        out["texto_funcion_no_docente"] = out["texto_funcion_no_docente"].fillna("").astype(str)
    out = out.rename(columns={
        "funcion_no_docente": "Función",
        "texto_funcion_no_docente": "Funciones no docentes",
        "numero_resolucion": "N° resolución",
    })
    return out.reset_index(drop=True)


# --- entry l. 35043
_get_resumen_actual_periodo_docente_pre_v162 = get_resumen_actual_periodo_docente


# --- entry l. 35046-35166
def get_resumen_actual_periodo_docente(cuil, periodo_id):
    resumen = dict(_get_resumen_actual_periodo_docente_pre_v162(cuil, periodo_id) or {})
    try:
        if USE_POSTGRESQL:
            df, _meta_wrap_resumen_v227 = _fuente_designaciones_resumen_v227(cuil, periodo_id)
        else:
            _meta_wrap_resumen_v227 = {
                "tiene_local": False, "es_prestado": False,
                "es_compartido": False, "usa_institucional": False,
                "filas_sombra_omitidas": 0,
            }
            df = get_designaciones(periodo_id)
            if not df.empty:
                df = df[
                    df.get("cuil", pd.Series(index=df.index, dtype=str))
                    .fillna("").astype(str).map(_clave_cuil).eq(_clave_cuil(cuil))
                ].copy()
        if df is not None and not df.empty:
            # En el Resumen docente, las designaciones no docentes se informan en su
            # sección propia, pero no deben inflar los cargos/horas de docencia.
            # Para el período abierto se recalcula la tarjeta superior solo con
            # designaciones docentes activas. La lectura histórica conserva la lógica
            # institucional previa para no alterar cierres de períodos anteriores.
            if not bool(resumen.get("lectura_historica")) and "funcion_no_docente" in df.columns:
                df_doc_act = df[
                    ~df["funcion_no_docente"].map(_es_funcion_no_docente_v162)
                    & df.get("estado", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).str.strip().str.casefold().eq("activa")
                ].copy()
                horas_doc_act = float(pd.to_numeric(df_doc_act.get("horas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not df_doc_act.empty else 0.0
                cargos_doc_act = []
                for _, r_doc in df_doc_act.iterrows():
                    cargo_doc = limpiar_texto_tabla(r_doc.get("cargo", ""))
                    dedic_doc = limpiar_texto_tabla(r_doc.get("dedicacion", ""))
                    tipo_doc = limpiar_texto_tabla(r_doc.get("tipo_designacion", ""))
                    dep_doc = limpiar_texto_tabla(r_doc.get("departamento", ""))
                    hs_doc = _hora_numero(r_doc.get("horas", 0))
                    txt_doc = cargo_doc or "Sin cargo"
                    if tipo_doc:
                        txt_doc += f" ({tipo_doc})"
                    if dedic_doc:
                        txt_doc += f" · {dedic_doc}"
                    txt_doc += f" · {int(hs_doc) if float(hs_doc or 0).is_integer() else hs_doc:g} hs"
                    if dep_doc and USE_POSTGRESQL:
                        txt_doc = f"{dep_doc}: {txt_doc}"
                    if txt_doc not in cargos_doc_act:
                        cargos_doc_act.append(txt_doc)
                resumen["horas_actuales"] = round(horas_doc_act, 2)
                resumen["horas_total_departamentos"] = round(horas_doc_act, 2)
                resumen["cargos_actuales"] = cargos_doc_act
                try:
                    resumen["departamentos_periodo"] = _resumen_departamentos_desde_designaciones_df(df_doc_act) if not df_doc_act.empty else []
                except Exception:
                    resumen["departamentos_periodo"] = []

            susp = df[
                df.get("estado", pd.Series(index=df.index, dtype=str))
                .fillna("").astype(str).str.strip().str.casefold().eq("suspendida")
            ].copy()
        else:
            susp = pd.DataFrame()
        if not susp.empty:
            resumen["estado_designacion_visible"] = "Suspendida (licenciada)"
            cargos = list(resumen.get("cargos_actuales") or [])
            susp_cargos = susp
            if "funcion_no_docente" in susp_cargos.columns:
                susp_cargos = susp_cargos[~susp_cargos["funcion_no_docente"].map(_es_funcion_no_docente_v162)].copy()
            for _, r in susp_cargos.iterrows():
                cargo = limpiar_texto_tabla(r.get("cargo", ""))
                tipo = limpiar_texto_tabla(r.get("tipo_designacion", ""))
                dedic = limpiar_texto_tabla(r.get("dedicacion", ""))
                dep = limpiar_texto_tabla(r.get("departamento", ""))
                partes = [x for x in [cargo, f"({tipo})" if tipo else "", dedic, "Suspendida (licenciada)"] if x]
                txt = " · ".join(partes)
                if dep and USE_POSTGRESQL:
                    txt = f"{dep}: {txt}"
                if txt and txt not in cargos:
                    cargos.append(txt)
            resumen["cargos_actuales"] = cargos

        funciones_no_docentes = []
        if df is not None and not df.empty and "funcion_no_docente" in df.columns:
            df_nd = df[df["funcion_no_docente"].map(_es_funcion_no_docente_v162)].copy()
            for _, r in df_nd.iterrows():
                texto_nd = _texto_funcion_no_docente_limpio_v164(r.get("texto_funcion_no_docente", ""))
                if not texto_nd:
                    continue
                item_nd = {
                    "Departamento": limpiar_texto_tabla(r.get("departamento", "")),
                    "Cargo": limpiar_texto_tabla(r.get("cargo", "")),
                    "Dedicación": limpiar_texto_tabla(r.get("dedicacion", "")),
                    "Estado": _estado_designacion_visible_v162(r.get("estado", "")),
                    "Funciones no docentes": texto_nd,
                }
                clave_nd = tuple(item_nd.values())
                if clave_nd not in {tuple(x.values()) for x in funciones_no_docentes}:
                    funciones_no_docentes.append(item_nd)
        resumen["funciones_no_docentes"] = funciones_no_docentes

        # v227: regla de consistencia final. Si Designaciones del período no tiene
        # una fila física local para un docente propio, el Resumen NO puede mostrar
        # cargo, horas, evolución ni funciones provenientes de otra vista.
        if USE_POSTGRESQL and bool(resumen.get("sin_designacion_local_periodo_v227")):
            resumen["cargos_actuales"] = []
            resumen["horas_actuales"] = 0.0
            resumen["horas_total_departamentos"] = 0.0
            resumen["departamentos_periodo"] = []
            resumen["horas_inicio"] = 0.0
            resumen["variacion_horas"] = 0.0
            resumen["cambios_cargo"] = ["Sin cambio de cargo registrado en este período."]
            resumen["estado_resumen_periodo"] = ""
            resumen["estado_designacion_visible"] = ""
            resumen["baja_en_periodo"] = False
            resumen["balance_horas_periodo"] = {
                "horas_inicio_operativo": 0.0,
                "variacion_operativa": 0.0,
                "horas_resultado_operativo": 0.0,
            }
            resumen["funciones_no_docentes"] = []
    except Exception:
        resumen.setdefault("funciones_no_docentes", [])
    return resumen


# --- entry l. 35299-35301
def _semanas_ejecucion_proyecto_v162(fecha_inicio, fecha_fin):
    from analisis.motor.ref.domain.proyectos import _semanas_ejecucion_proyecto_v162 as _b05_core__semanas_ejecucion_proyecto_v162
    return _b05_core__semanas_ejecucion_proyecto_v162(fecha_inicio, fecha_fin)


# --- entry l. 35304-35306
def _horas_totales_ejecucion_proyecto_v162(horas_semanales, fecha_inicio, fecha_fin):
    from analisis.motor.ref.domain.proyectos import _horas_totales_ejecucion_proyecto_v162 as _b05_core__horas_totales_ejecucion_proyecto_v162
    return _b05_core__horas_totales_ejecucion_proyecto_v162(horas_semanales, fecha_inicio, fecha_fin)


# --- entry l. 35312-35346
def _designaciones_activas_funcionales_v165(periodo_id):
    """Devuelve designaciones activas separadas por función y unificadas.

    La separación es por designación, no por persona: una misma persona puede tener
    simultáneamente una designación docente y otra no docente. En el consolidado de
    personas se cuenta una única vez por CUIL; cargos y horas se suman por designación.
    """
    try:
        df = get_designaciones(int(periodo_id))
    except Exception:
        df = pd.DataFrame()
    if df is None:
        df = pd.DataFrame()
    base = df.copy()
    if base.empty:
        for col, dtype in [
            ("funcion_no_docente", int), ("texto_funcion_no_docente", str),
            ("cuil", str), ("estado", str), ("horas", float),
        ]:
            if col not in base.columns:
                base[col] = pd.Series(dtype=dtype)
        return base.copy(), base.copy(), base.copy()

    estado = base.get("estado", pd.Series(index=base.index, dtype=str)).fillna("").astype(str).str.strip().str.casefold()
    base = base[estado.eq("activa")].copy()
    if "funcion_no_docente" not in base.columns:
        base["funcion_no_docente"] = 0
    if "texto_funcion_no_docente" not in base.columns:
        base["texto_funcion_no_docente"] = ""
    base["funcion_no_docente"] = base["funcion_no_docente"].map(lambda x: 1 if _es_funcion_no_docente_v162(x) else 0)
    base["texto_funcion_no_docente"] = base["texto_funcion_no_docente"].fillna("").astype(str)

    df_no_doc = base[base["funcion_no_docente"].eq(1)].copy()
    df_doc = base[base["funcion_no_docente"].eq(0)].copy()
    return df_doc.reset_index(drop=True), df_no_doc.reset_index(drop=True), base.reset_index(drop=True)


# --- entry l. 35349-35351
def _cuiles_unicos_designaciones_v165(df):
    from analisis.motor.ref.common.identifiers import _cuiles_unicos_designaciones_v165 as _b05_core__cuiles_unicos_designaciones_v165
    return _b05_core__cuiles_unicos_designaciones_v165(df)


# --- entry l. 35354-35356
def _horas_designaciones_v165(df):
    from analisis.motor.ref.domain.catalog_unlocked.designaciones import _horas_designaciones_v165 as _b08_core__horas_designaciones_v165
    return _b08_core__horas_designaciones_v165(df)


# --- entry l. 35359-35361
def _conteo_ad_honorem_v165(df):
    from analisis.motor.ref.domain.designaciones import _conteo_ad_honorem_v165 as _b05_core__conteo_ad_honorem_v165
    return _b05_core__conteo_ad_honorem_v165(df)


# --- entry l. 35364
_get_metricas_analisis_periodo_pre_v165 = get_metricas_analisis_periodo


# --- entry l. 35367-35417
def get_metricas_analisis_periodo(periodo_id):
    """Amplía las métricas históricas sin mezclar productividad docente con funciones no docentes."""
    datos = dict(_get_metricas_analisis_periodo_pre_v165(periodo_id) or {})
    df_doc, df_no_doc, df_total = _designaciones_activas_funcionales_v165(periodo_id)

    cuil_doc = _cuiles_unicos_designaciones_v165(df_doc)
    cuil_no_doc = _cuiles_unicos_designaciones_v165(df_no_doc)
    cuil_total = cuil_doc | cuil_no_doc

    hs_doc = _horas_designaciones_v165(df_doc)
    hs_no_doc = _horas_designaciones_v165(df_no_doc)
    hs_total = round(hs_doc + hs_no_doc, 2)

    ah_doc = _conteo_ad_honorem_v165(df_doc)
    ah_no_doc = _conteo_ad_honorem_v165(df_no_doc)
    ah_total = _conteo_ad_honorem_v165(df_total)

    # Mantiene las claves históricas como métricas EXCLUSIVAMENTE docentes para no
    # alterar productividad, alertas ni diagnósticos académicos existentes.
    datos["docentes_activos"] = int(len(cuil_doc))
    datos["cargos_totales"] = int(len(df_doc))
    datos["horas_contratadas"] = hs_doc

    # Nuevas métricas separadas y consolidadas.
    datos["no_docentes_activos"] = int(len(cuil_no_doc))
    datos["personas_activas_totales"] = int(len(cuil_total))
    datos["cargos_docentes"] = int(len(df_doc))
    datos["cargos_no_docentes"] = int(len(df_no_doc))
    datos["cargos_totales_consolidados"] = int(len(df_total))
    datos["horas_contratadas_docencia"] = hs_doc
    datos["horas_no_docentes"] = hs_no_doc
    datos["horas_contratadas_totales"] = hs_total
    datos["cargos_ad_honorem_docentes"] = ah_doc
    datos["cargos_rentados_docentes"] = int(len(df_doc) - ah_doc)
    datos["cargos_ad_honorem_no_docentes"] = ah_no_doc
    datos["cargos_rentados_no_docentes"] = int(len(df_no_doc) - ah_no_doc)
    datos["cargos_ad_honorem_totales"] = ah_total
    datos["cargos_rentados_totales"] = int(len(df_total) - ah_total)
    datos["df_desig_docentes_activas"] = df_doc
    datos["df_desig_no_docentes_activas"] = df_no_doc
    datos["df_desig_activas_totales"] = df_total

    # Las funciones no docentes consumen íntegramente las horas de su designación.
    # Se agregan solo al consolidado global; no ingresan a productividad docente.
    hs_acad = float(datos.get("horas_academicas_utilizadas", 0) or 0)
    hs_util_total = round(hs_acad + hs_no_doc, 2)
    datos["horas_no_docentes_utilizadas"] = hs_no_doc
    datos["horas_utilizadas_totales"] = hs_util_total
    datos["horas_disponibles_totales"] = round(max(hs_total - hs_util_total, 0.0), 2)
    datos["horas_exceso_totales"] = round(max(hs_util_total - hs_total, 0.0), 2)
    return datos


# --- entry l. 35420
_inicio_datos_tablero_cache_pre_v165 = _inicio_datos_tablero_cache


# --- entry l. 35424-35529
def _inicio_datos_tablero_cache(periodo_id, institucion_id, departamento_id, hoy_iso):
    """Extiende Inicio con no docentes y con totales consolidados de horas."""
    datos = dict(_inicio_datos_tablero_cache_pre_v165(periodo_id, institucion_id, departamento_id, hoy_iso) or {})
    metricas = dict(datos.get("metricas") or get_metricas_analisis_periodo(int(periodo_id)) or {})
    datos["metricas"] = metricas

    df_no_doc = metricas.get("df_desig_no_docentes_activas", pd.DataFrame())
    if df_no_doc is None:
        df_no_doc = pd.DataFrame()
    df_no_doc = df_no_doc.copy()
    if not df_no_doc.empty:
        vista = df_no_doc.copy()
        vista["Funciones"] = vista.get("texto_funcion_no_docente", pd.Series(index=vista.index, dtype=str)).fillna("").astype(str).map(_texto_funcion_no_docente_limpio_v164)
        vista["Ámbito"] = "Funciones no docentes"
        vista["Estado"] = vista.get("estado", pd.Series(index=vista.index, dtype=str)).map(_estado_designacion_visible_v162)
        vista = vista.rename(columns={
            "nombre_completo": "Persona", "cuil": "CUIL", "cargo": "Cargo",
            "dedicacion": "Dedicación", "horas": "Horas", "tipo_designacion": "Tipo de designación",
            "ad_honorem": "Ad Honórem", "fecha_desde": "Desde", "fecha_hasta": "Hasta",
        })
        columnas = [c for c in [
            "id", "Persona", "CUIL", "Cargo", "Dedicación", "Horas", "Tipo de designación",
            "Ad Honórem", "Estado", "Funciones", "Desde", "Hasta"
        ] if c in vista.columns]
        vista = vista[columnas].copy()
    else:
        vista = pd.DataFrame(columns=["Persona", "CUIL", "Cargo", "Dedicación", "Horas", "Tipo de designación", "Ad Honórem", "Estado", "Funciones", "Desde", "Hasta"])
    datos["df_no_docentes_detalle"] = vista

    # v166: misma vista detallada para las designaciones docentes. Inicio la
    # muestra completa, sin obligar a seleccionar una persona por vez.
    df_doc = metricas.get("df_desig_docentes_activas", pd.DataFrame())
    if df_doc is None:
        df_doc = pd.DataFrame()
    df_doc = df_doc.copy()
    if not df_doc.empty:
        vista_doc = df_doc.copy()
        vista_doc["Estado"] = vista_doc.get(
            "estado", pd.Series(index=vista_doc.index, dtype=str)
        ).map(_estado_designacion_visible_v162)
        vista_doc = vista_doc.rename(columns={
            "nombre_completo": "Persona", "cuil": "CUIL", "cargo": "Cargo",
            "dedicacion": "Dedicación", "horas": "Horas", "tipo_designacion": "Tipo de designación",
            "ad_honorem": "Ad Honórem", "fecha_desde": "Desde", "fecha_hasta": "Hasta",
        })
        columnas_doc = [c for c in [
            "id", "Persona", "CUIL", "Cargo", "Dedicación", "Horas", "Tipo de designación",
            "Ad Honórem", "Estado", "Desde", "Hasta"
        ] if c in vista_doc.columns]
        vista_doc = vista_doc[columnas_doc].copy()
    else:
        vista_doc = pd.DataFrame(columns=[
            "Persona", "CUIL", "Cargo", "Dedicación", "Horas", "Tipo de designación",
            "Ad Honórem", "Estado", "Desde", "Hasta"
        ])
    datos["df_docentes_designaciones_detalle"] = vista_doc

    datos["no_docentes_activos"] = int(metricas.get("no_docentes_activos", 0) or 0)
    datos["personas_activas_totales"] = int(metricas.get("personas_activas_totales", 0) or 0)

    # Inicio usa el total global para las tarjetas/gráficos de horas, conservando
    # además las claves separadas para mostrar el origen de cada bloque.
    datos["horas_contratadas_docencia"] = round(float(metricas.get("horas_contratadas_docencia", metricas.get("horas_contratadas", 0)) or 0), 2)
    datos["horas_no_docentes"] = round(float(metricas.get("horas_no_docentes", 0) or 0), 2)
    datos["horas_contratadas"] = round(float(metricas.get("horas_contratadas_totales", 0) or 0), 2)
    datos["horas_utilizadas"] = round(float(metricas.get("horas_utilizadas_totales", 0) or 0), 2)
    datos["horas_disponibles"] = round(float(metricas.get("horas_disponibles_totales", 0) or 0), 2)
    datos["horas_exceso"] = round(float(metricas.get("horas_exceso_totales", 0) or 0), 2)

    # Los vencimientos son administrativos y por eso incluyen también designaciones
    # no docentes, aunque estas no participen de productividad ni alertas académicas.
    try:
        hoy_v = _inicio_fecha_segura(hoy_iso) or date.today()
        limite_v = hoy_v + pd.Timedelta(days=30)
        limite_v = limite_v.date() if hasattr(limite_v, "date") else limite_v
        filas_v_nd = []
        for _, r_nd in df_no_doc.iterrows():
            f_nd = _inicio_fecha_segura(r_nd.get("fecha_hasta_prevista") or r_nd.get("fecha_hasta"))
            if f_nd is None or f_nd < hoy_v or f_nd > limite_v:
                continue
            func_nd = _texto_funcion_no_docente_limpio_v164(r_nd.get("texto_funcion_no_docente", ""))
            desig_nd = _inicio_contexto_designacion(r_nd)
            if func_nd:
                desig_nd = (desig_nd + " · " if desig_nd else "") + f"Funciones no docentes: {func_nd}"
            filas_v_nd.append({
                "Docente": str(r_nd.get("nombre_completo") or r_nd.get("cuil") or "").strip(),
                "Designación": desig_nd or "Funciones no docentes",
                "Vencimiento": f_nd.strftime("%d/%m/%Y"),
                "Días": int((f_nd - hoy_v).days),
                "_fecha": f_nd,
            })
        if filas_v_nd:
            df_v_actual = datos.get("df_vencimientos", pd.DataFrame())
            if df_v_actual is None:
                df_v_actual = pd.DataFrame()
            df_v_total = pd.concat([df_v_actual, pd.DataFrame(filas_v_nd)], ignore_index=True, sort=False)
            if not df_v_total.empty:
                claves_v = [c for c in ["Docente", "Designación", "Vencimiento"] if c in df_v_total.columns]
                if claves_v:
                    df_v_total = df_v_total.drop_duplicates(subset=claves_v, keep="first")
                if "_fecha" in df_v_total.columns:
                    df_v_total = df_v_total.sort_values(["_fecha", "Docente"], kind="stable").reset_index(drop=True)
            datos["df_vencimientos"] = df_v_total
    except Exception:
        pass
    return datos


# --- entry l. 35532
_generar_resumen_ejecutivo_automatico_pre_v165 = generar_resumen_ejecutivo_automatico


# --- entry l. 35535-35544
def generar_resumen_ejecutivo_automatico(periodo_nombre, metricas, df_alertas, df_prod):
    base = _generar_resumen_ejecutivo_automatico_pre_v165(periodo_nombre, metricas, df_alertas, df_prod)
    agregado = (
        f" Dotación funcional del período: {metricas.get('docentes_activos', 0)} persona/s con funciones docentes y "
        f"{metricas.get('no_docentes_activos', 0)} persona/s con funciones no docentes; "
        f"el consolidado único es de {metricas.get('personas_activas_totales', 0)} persona/s, "
        f"{metricas.get('cargos_totales_consolidados', 0)} cargos y {metricas.get('horas_contratadas_totales', 0)} horas contratadas. "
        f"Las {metricas.get('horas_no_docentes', 0)} horas de funciones no docentes se informan en el consolidado, pero no integran la productividad docente."
    )
    return str(base or "").strip() + agregado


# --- entry l. 35547
_construir_prompt_ia_periodo_pre_v165 = construir_prompt_ia_periodo


# --- entry l. 35550-35568
def construir_prompt_ia_periodo(periodo_nombre, metricas, df_alertas, df_prod):
    base = _construir_prompt_ia_periodo_pre_v165(periodo_nombre, metricas, df_alertas, df_prod)
    bloque = f"""

Dotación funcional separada y consolidada:
- Personas con funciones docentes: {metricas.get('docentes_activos', 0)}
- Personas con funciones no docentes: {metricas.get('no_docentes_activos', 0)}
- Personas activas totales (CUIL únicos): {metricas.get('personas_activas_totales', 0)}
- Cargos docentes: {metricas.get('cargos_docentes', 0)}
- Cargos no docentes: {metricas.get('cargos_no_docentes', 0)}
- Cargos totales consolidados: {metricas.get('cargos_totales_consolidados', 0)}
- Horas contratadas de docencia: {metricas.get('horas_contratadas_docencia', 0)}
- Horas contratadas para funciones no docentes: {metricas.get('horas_no_docentes', 0)}
- Horas contratadas totales: {metricas.get('horas_contratadas_totales', 0)}
- Horas utilizadas totales (académicas + funciones no docentes): {metricas.get('horas_utilizadas_totales', 0)}

Importante: la productividad se calcula solo sobre funciones docentes. Las funciones no docentes deben analizarse como parte de la dotación y de las horas institucionales consolidadas, no como productividad académica.
"""
    return str(base or "").rstrip() + bloque


# --- entry l. 36408-36422
def _info_periodo_analisis_v169(periodo_id):
    try:
        conn = get_conn()
        df = pd.read_sql(
            """SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin,
                      COALESCE(estado, '') AS estado
               FROM periodos WHERE id = ? LIMIT 1""",
            conn, params=[int(periodo_id)]
        )
        conn.close()
        if not df.empty:
            return df.iloc[0].to_dict()
    except Exception:
        pass
    return {}


# --- entry l. 36425-36427
def _periodo_cerrado_analisis_v169(periodo_id):
    info = _info_periodo_analisis_v169(periodo_id)
    return str(info.get("estado", "") or "").strip().casefold() == "cerrado"


# --- entry l. 36430-36432
def _fecha_fin_designacion_analisis_v169(row):
    from analisis.motor.ref.domain.designaciones import _fecha_fin_designacion_analisis_v169 as _b05_core__fecha_fin_designacion_analisis_v169
    return _b05_core__fecha_fin_designacion_analisis_v169(row)


# --- entry l. 36435-36484
def _filtrar_foto_designaciones_v169(df, periodo_id):
    """Designaciones que integran la foto operativa del período seleccionado."""
    if df is None:
        df = pd.DataFrame()
    base = df.copy()
    if base.empty:
        return base

    info = _info_periodo_analisis_v169(periodo_id)
    cerrado = str(info.get("estado", "") or "").strip().casefold() == "cerrado"

    # En el período abierto se conserva exactamente la lógica operativa vigente.
    if not cerrado:
        estado = base.get("estado", pd.Series(index=base.index, dtype=str)).fillna("").astype(str).str.strip().str.casefold()
        return base[estado.eq("activa")].copy().reset_index(drop=True)

    # En un período cerrado se reconstruye qué seguía vigente al cierre. El
    # estado Finalizada por sí solo no sirve, porque es justamente el estado que
    # asigna el cierre técnico a todas las designaciones que estaban activas.
    if "horas" in base.columns:
        base["_hs_v169"] = pd.to_numeric(base["horas"], errors="coerce").fillna(0)
        base = base[base["_hs_v169"] > 0].copy()
    if base.empty:
        return base.drop(columns=["_hs_v169"], errors="ignore")

    if "estado" in base.columns:
        estado = base["estado"].fillna("").astype(str).str.strip().str.casefold()
        # Una licencia/suspensión sigue sin integrar la dotación operativa.
        base = base[~estado.eq("suspendida")].copy()
    if base.empty:
        return base.drop(columns=["_hs_v169"], errors="ignore")

    fecha_inicio = _fecha_a_timestamp_seguro(info.get("fecha_inicio", ""))
    fecha_fin = _fecha_a_timestamp_seguro(info.get("fecha_fin", ""))
    base["_desde_v169"] = (
        base["fecha_desde"].apply(_fecha_a_timestamp_seguro)
        if "fecha_desde" in base.columns else pd.NaT
    )
    base["_hasta_v169"] = base.apply(_fecha_fin_designacion_analisis_v169, axis=1)

    vigente = pd.Series(True, index=base.index)
    if not pd.isna(fecha_fin):
        vigente &= base["_desde_v169"].isna() | (base["_desde_v169"] <= fecha_fin)
        vigente &= base["_hasta_v169"].isna() | (base["_hasta_v169"] >= fecha_fin)
    elif not pd.isna(fecha_inicio):
        vigente &= base["_hasta_v169"].isna() | (base["_hasta_v169"] >= fecha_inicio)

    out = base[vigente].copy()
    out["estado_analisis"] = "Vigente al cierre del período"
    return out.drop(columns=["_hs_v169", "_desde_v169", "_hasta_v169"], errors="ignore").reset_index(drop=True)


# --- entry l. 36487-36514
def _designaciones_funcionales_analisis_v169(periodo_id):
    try:
        base = get_designaciones(int(periodo_id))
    except Exception:
        base = pd.DataFrame()
    base = _filtrar_foto_designaciones_v169(base, periodo_id)
    if base is None:
        base = pd.DataFrame()
    if base.empty:
        for col, dtype in [
            ("funcion_no_docente", int), ("texto_funcion_no_docente", str),
            ("cuil", str), ("estado", str), ("horas", float),
        ]:
            if col not in base.columns:
                base[col] = pd.Series(dtype=dtype)
        return base.copy(), base.copy(), base.copy()

    if "funcion_no_docente" not in base.columns:
        base["funcion_no_docente"] = 0
    if "texto_funcion_no_docente" not in base.columns:
        base["texto_funcion_no_docente"] = ""
    base["funcion_no_docente"] = base["funcion_no_docente"].map(
        lambda x: 1 if _es_funcion_no_docente_v162(x) else 0
    )
    base["texto_funcion_no_docente"] = base["texto_funcion_no_docente"].fillna("").astype(str)
    df_no_doc = base[base["funcion_no_docente"].eq(1)].copy()
    df_doc = base[base["funcion_no_docente"].eq(0)].copy()
    return df_doc.reset_index(drop=True), df_no_doc.reset_index(drop=True), base.reset_index(drop=True)


# --- entry l. 36517-36533
def _designaciones_docentes_institucionales_analisis_v169(cuil, periodo_id):
    """Foto histórica institucional del mismo CUIL, solo para productividad docente."""
    try:
        if USE_POSTGRESQL:
            df = _get_designaciones_periodo_institucional_v149(cuil, periodo_id)
        else:
            df = get_designaciones(periodo_id)
            if not df.empty:
                claves = df.get("cuil", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
                df = df[claves.eq(_clave_cuil(cuil))].copy()
    except Exception:
        df = pd.DataFrame()
    df = _filtrar_foto_designaciones_v169(df, periodo_id)
    if df is None or df.empty:
        return pd.DataFrame(columns=getattr(df, "columns", []))
    no_doc = df.get("funcion_no_docente", pd.Series(0, index=df.index)).map(_es_funcion_no_docente_v162)
    return df[~no_doc].copy().reset_index(drop=True)


# --- entry l. 36536-36538
def _cuiles_docentes_foto_local_v169(periodo_id):
    df_doc, _, _ = _designaciones_funcionales_analisis_v169(periodo_id)
    return _cuiles_unicos_designaciones_v165(df_doc)


# --- entry l. 36541-36635
def _productividad_historica_periodo_v169(periodo_id):
    """Reconstruye productividad del período cerrado sin exigir estado='Activa'."""
    df_doc_local, _, _ = _designaciones_funcionales_analisis_v169(periodo_id)
    columnas = [
        "cuil", "docente", "tipo_docente", "departamentos_designacion",
        "cargos", "dedicaciones", "tipos_designacion", "porcentaje_uso",
        "horas_contratadas", "horas_comisiones_brutas", "horas_comisiones_reales",
        "horas_no_contadas_por_superposicion", "porcentaje_no_lectivas", "horas_no_lectivas",
        "horas_investigacion", "horas_extension", "horas_utilizadas",
        "horas_disponibles", "diagnostico",
    ]
    if df_doc_local is None or df_doc_local.empty:
        return pd.DataFrame(columns=columnas)

    registros = []
    vistos = set()
    for _, row_local in df_doc_local.iterrows():
        cuil = str(row_local.get("cuil", "") or "").strip()
        clave = _clave_cuil(cuil)
        if not clave or clave in vistos:
            continue
        vistos.add(clave)

        df_inst = _designaciones_docentes_institucionales_analisis_v169(cuil, periodo_id)
        if df_inst.empty:
            # En SQLite o ante una inconsistencia institucional, la foto local es
            # mejor respaldo que devolver 0 para una persona que sí integra el período.
            claves_local = df_doc_local.get("cuil", pd.Series(index=df_doc_local.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
            df_inst = df_doc_local[claves_local.eq(clave)].copy()

        try:
            prod = (
                get_productividad_docente_institucional_v149(cuil, periodo_id)
                if USE_POSTGRESQL else _productividad_docente_departamento_v148(cuil, periodo_id)
            )
        except Exception:
            prod = {}
        if not isinstance(prod, dict):
            prod = {}

        def unir_unicos(col):
            if df_inst.empty or col not in df_inst.columns:
                return ""
            vals = []
            for valor in df_inst[col].dropna().astype(str).tolist():
                valor = " ".join(valor.strip().split())
                if valor and valor not in vals:
                    vals.append(valor)
            return " / ".join(vals)

        contratadas = _horas_designaciones_v165(df_inst)
        utilizadas = round(float(prod.get("horas_utilizadas", 0) or 0), 2)
        porcentaje = round((utilizadas / contratadas * 100.0), 2) if contratadas > 0 else 0.0
        disponibles = round(contratadas - utilizadas, 2)

        if contratadas <= 0 and utilizadas > 0:
            diagnostico = "Actividad registrada sin horas contratadas"
        elif utilizadas > contratadas:
            diagnostico = "Sobrecarga: horas utilizadas superan las contratadas"
        elif contratadas > 0 and utilizadas == 0:
            diagnostico = "Sin actividad registrada"
        elif contratadas > 0 and porcentaje < 50:
            diagnostico = "Subutilización: baja carga registrada"
        else:
            diagnostico = "Sin alerta principal"

        nombre = limpiar_texto_tabla(row_local.get("nombre_completo", "")) or cuil
        registros.append({
            "cuil": cuil,
            "docente": nombre,
            "tipo_docente": "Propio",
            "departamentos_designacion": unir_unicos("departamento"),
            "cargos": unir_unicos("cargo"),
            "dedicaciones": unir_unicos("dedicacion"),
            "tipos_designacion": unir_unicos("tipo_designacion"),
            "porcentaje_uso": porcentaje,
            "horas_contratadas": round(contratadas, 2),
            "horas_comisiones_brutas": round(float(prod.get("horas_en_comisiones_brutas", 0) or 0), 2),
            "horas_comisiones_reales": round(float(prod.get("horas_en_comisiones", 0) or 0), 2),
            "horas_no_contadas_por_superposicion": round(float(prod.get("horas_no_contadas_por_superposicion", 0) or 0), 2),
            "porcentaje_no_lectivas": round(float(prod.get("porcentaje_no_lectivas", 0) or 0), 2),
            "horas_no_lectivas": round(float(prod.get("horas_no_lectivas", 0) or 0), 2),
            "horas_investigacion": round(float(prod.get("horas_en_investigacion", 0) or 0), 2),
            "horas_extension": round(float(prod.get("horas_en_extension", 0) or 0), 2),
            "horas_utilizadas": utilizadas,
            "horas_disponibles": disponibles,
            "diagnostico": diagnostico,
        })

    if not registros:
        return pd.DataFrame(columns=columnas)
    out = pd.DataFrame(registros, columns=columnas)
    return _redondear_numericos_productividad_v150(out).sort_values(
        ["diagnostico", "docente"], kind="stable"
    ).reset_index(drop=True)


# --- entry l. 36638
_get_docentes_productividad_periodo_pre_v169 = get_docentes_productividad_periodo


# --- entry l. 36641-36644
def get_docentes_productividad_periodo(periodo_id):
    if not _periodo_cerrado_analisis_v169(periodo_id):
        return _get_docentes_productividad_periodo_pre_v169(periodo_id)
    return _productividad_historica_periodo_v169(periodo_id)


# --- entry l. 36647
_get_metricas_analisis_periodo_pre_v169 = get_metricas_analisis_periodo


# --- entry l. 36650-36744
def get_metricas_analisis_periodo(periodo_id):
    """Métricas del período seleccionado, abierto o histórico.

    Para un período cerrado, 'activo' significa vigente en la foto operativa al
    cierre del semestre, inmediatamente antes de la finalización técnica masiva.
    """
    datos = dict(_get_metricas_analisis_periodo_pre_v169(periodo_id) or {})
    info = _info_periodo_analisis_v169(periodo_id)
    cerrado = str(info.get("estado", "") or "").strip().casefold() == "cerrado"
    datos["estado_periodo_analisis"] = info.get("estado", "")
    datos["lectura_historica_periodo"] = bool(cerrado)
    if not cerrado:
        return datos

    df_doc, df_no_doc, df_total = _designaciones_funcionales_analisis_v169(periodo_id)
    cuil_doc = _cuiles_unicos_designaciones_v165(df_doc)
    cuil_no_doc = _cuiles_unicos_designaciones_v165(df_no_doc)
    cuil_total = cuil_doc | cuil_no_doc

    hs_doc = _horas_designaciones_v165(df_doc)
    hs_no_doc = _horas_designaciones_v165(df_no_doc)
    hs_total = round(hs_doc + hs_no_doc, 2)
    ah_doc = _conteo_ad_honorem_v165(df_doc)
    ah_no_doc = _conteo_ad_honorem_v165(df_no_doc)
    ah_total = _conteo_ad_honorem_v165(df_total)

    datos["docentes_activos"] = int(len(cuil_doc))
    datos["no_docentes_activos"] = int(len(cuil_no_doc))
    datos["personas_activas_totales"] = int(len(cuil_total))
    datos["cargos_totales"] = int(len(df_doc))
    datos["cargos_docentes"] = int(len(df_doc))
    datos["cargos_no_docentes"] = int(len(df_no_doc))
    datos["cargos_totales_consolidados"] = int(len(df_total))
    datos["horas_contratadas"] = hs_doc
    datos["horas_contratadas_docencia"] = hs_doc
    datos["horas_no_docentes"] = hs_no_doc
    datos["horas_contratadas_totales"] = hs_total
    datos["cargos_ad_honorem_docentes"] = ah_doc
    datos["cargos_rentados_docentes"] = int(len(df_doc) - ah_doc)
    datos["cargos_ad_honorem_no_docentes"] = ah_no_doc
    datos["cargos_rentados_no_docentes"] = int(len(df_no_doc) - ah_no_doc)
    datos["cargos_ad_honorem_totales"] = ah_total
    datos["cargos_rentados_totales"] = int(len(df_total) - ah_total)
    datos["df_desig_docentes_activas"] = df_doc
    datos["df_desig_no_docentes_activas"] = df_no_doc
    datos["df_desig_activas_totales"] = df_total

    # Productividad histórica: usa la dotación docente reconstruida, no el estado
    # Finalizada que dejó el cierre técnico.
    try:
        df_prod = get_docentes_productividad_periodo(periodo_id)
    except Exception:
        df_prod = pd.DataFrame()
    if df_prod is not None and not df_prod.empty:
        datos["horas_comisiones"] = round(float(pd.to_numeric(df_prod.get("horas_comisiones_reales"), errors="coerce").fillna(0).sum()), 2)
        datos["horas_no_lectivas"] = round(float(pd.to_numeric(df_prod.get("horas_no_lectivas"), errors="coerce").fillna(0).sum()), 2)
        datos["horas_investigacion"] = round(float(pd.to_numeric(df_prod.get("horas_investigacion"), errors="coerce").fillna(0).sum()), 2)
        datos["horas_extension"] = round(float(pd.to_numeric(df_prod.get("horas_extension"), errors="coerce").fillna(0).sum()), 2)
        datos["horas_academicas_utilizadas"] = round(float(pd.to_numeric(df_prod.get("horas_utilizadas"), errors="coerce").fillna(0).sum()), 2)
    else:
        for k in ["horas_comisiones", "horas_no_lectivas", "horas_investigacion", "horas_extension", "horas_academicas_utilizadas"]:
            datos[k] = 0.0

    # Comisiones: el equipo se cruza contra la dotación histórica del período.
    try:
        df_asig = datos.get("df_asig", pd.DataFrame())
        if isinstance(df_asig, pd.DataFrame) and not df_asig.empty:
            da = df_asig.copy()
            estado_asig = da.get("estado", pd.Series(index=da.index, dtype=str)).fillna("Activa").astype(str).str.strip().str.casefold()
            da = da[estado_asig.eq("activa")].copy()
            claves = da.get("cuil", pd.Series(index=da.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
            tipo = da.get("tipo_docente", pd.Series("Propio", index=da.index)).fillna("Propio").astype(str).str.strip().str.casefold()
            propios = da[tipo.ne("prestado")].copy()
            claves_prop = propios.get("cuil", pd.Series(index=propios.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
            datos["docentes_en_comisiones"] = int(claves_prop[claves_prop.isin(cuil_doc)].replace("", pd.NA).dropna().nunique())

            prest = da[tipo.eq("prestado")].copy()
            prest_validos = set()
            for cuil_p in prest.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).tolist():
                clave_p = _clave_cuil(cuil_p)
                if not clave_p or clave_p in prest_validos:
                    continue
                if not _designaciones_docentes_institucionales_analisis_v169(cuil_p, periodo_id).empty:
                    prest_validos.add(clave_p)
            datos["docentes_prestados_recibidos"] = int(len(prest_validos))
    except Exception:
        pass

    hs_acad = float(datos.get("horas_academicas_utilizadas", 0) or 0)
    hs_util_total = round(hs_acad + hs_no_doc, 2)
    datos["horas_no_docentes_utilizadas"] = hs_no_doc
    datos["horas_utilizadas_totales"] = hs_util_total
    datos["horas_disponibles_totales"] = round(max(hs_total - hs_util_total, 0.0), 2)
    datos["horas_exceso_totales"] = round(max(hs_util_total - hs_total, 0.0), 2)
    return datos


# --- entry l. 36747
_get_docentes_asignados_sin_designacion_pre_v169 = get_docentes_asignados_sin_designacion_periodo


# --- entry l. 36750-36764
def get_docentes_asignados_sin_designacion_periodo(periodo_id):
    if not _periodo_cerrado_analisis_v169(periodo_id):
        return _get_docentes_asignados_sin_designacion_pre_v169(periodo_id)
    df = get_asignaciones_comisiones_periodo(periodo_id)
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    est = out.get("estado", pd.Series(index=out.index, dtype=str)).fillna("Activa").astype(str).str.strip().str.casefold()
    out = out[est.eq("activa")].copy()
    if "tipo_docente" in out.columns:
        out = out[out["tipo_docente"].fillna("Propio").astype(str).str.strip().str.casefold().ne("prestado")].copy()
    habilitados = _cuiles_docentes_foto_local_v169(periodo_id)
    claves = out.get("cuil", pd.Series(index=out.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
    out = out[~claves.isin(habilitados)].copy()
    return out


# --- entry l. 36767
_get_roles_inconsistentes_pre_v169 = get_roles_inconsistentes_periodo


# --- entry l. 36770-36811
def get_roles_inconsistentes_periodo(periodo_id):
    if not _periodo_cerrado_analisis_v169(periodo_id):
        return _get_roles_inconsistentes_pre_v169(periodo_id)
    df_asig = get_asignaciones_comisiones_periodo(periodo_id)
    df_doc, _, _ = _designaciones_funcionales_analisis_v169(periodo_id)
    columnas = ["cuil", "docente", "tipo_docente", "codigo_materia", "asignatura", "nombre_comision", "rol", "cargos_activos", "detalle"]
    if df_asig is None or df_asig.empty or df_doc is None or df_doc.empty:
        return pd.DataFrame(columns=columnas)

    mapa = {}
    for _, r in df_doc.iterrows():
        clave = _clave_cuil(r.get("cuil", ""))
        cargo = limpiar_texto_tabla(r.get("cargo", ""))
        if clave and cargo:
            mapa.setdefault(clave, [])
            if cargo not in mapa[clave]:
                mapa[clave].append(cargo)

    registros = []
    for _, row in df_asig.iterrows():
        if str(row.get("estado", "Activa") or "Activa").strip().casefold() != "activa":
            continue
        if str(row.get("tipo_docente", "Propio") or "Propio").strip().casefold() == "prestado":
            continue
        clave = _clave_cuil(row.get("cuil", ""))
        cargos = mapa.get(clave, [])
        rol = normalizar_clave(row.get("rol", ""))
        cargos_norm = [normalizar_clave(x) for x in cargos if x]
        if not rol or not cargos_norm or rol in cargos_norm:
            continue
        registros.append({
            "cuil": row.get("cuil", ""),
            "docente": row.get("docente", ""),
            "tipo_docente": row.get("tipo_docente", "Propio"),
            "codigo_materia": row.get("codigo_materia", ""),
            "asignatura": row.get("asignatura", ""),
            "nombre_comision": row.get("nombre_comision", ""),
            "rol": row.get("rol", ""),
            "cargos_activos": ", ".join(cargos),
            "detalle": "El rol asignado en comisión no coincide con el cargo vigente en la foto histórica del período.",
        })
    return pd.DataFrame(registros, columns=columnas) if registros else pd.DataFrame(columns=columnas)


# --- entry l. 36835-36845
def _departamento_contexto_prestamo_v174():
    """Devuelve el departamento operativo real; evita inferir uno en la vista institucional."""
    try:
        if current_role() == "coordinador_institucional" and not st.session_state.get("tenant_scope_departamento_id"):
            return None
    except Exception:
        pass
    try:
        return _pg_current_dep_id() if USE_POSTGRESQL else None
    except Exception:
        return None


# --- entry l. 36848-36906
def asegurar_esquema_prestamos_docentes_v174():
    """Persistencia de préstamos: un préstamo pertenece a un único período receptor."""
    if st.session_state.get("_prestamos_docentes_v174_schema_ok"):
        return
    if USE_POSTGRESQL:
        conn = _pg_raw_conn()
        cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS prestamos_docentes (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT NOT NULL,
                    periodo_id BIGINT NOT NULL,
                    cuil TEXT NOT NULL,
                    departamento_origen TEXT,
                    fecha_desde DATE,
                    fecha_hasta DATE,
                    estado TEXT NOT NULL DEFAULT 'Activo',
                    observaciones TEXT,
                    fecha_registro TEXT,
                    fecha_finalizacion TEXT
                )
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_deptit_prestamo_periodo_cuil
                ON prestamos_docentes (institucion_id, departamento_id, periodo_id, cuil)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_deptit_prestamo_periodo_estado
                ON prestamos_docentes (institucion_id, departamento_id, periodo_id, estado)
            """)
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        conn = get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prestamos_docentes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    periodo_id INTEGER NOT NULL,
                    cuil TEXT NOT NULL,
                    departamento_origen TEXT,
                    fecha_desde TEXT,
                    fecha_hasta TEXT,
                    estado TEXT DEFAULT 'Activo',
                    observaciones TEXT,
                    fecha_registro TEXT,
                    fecha_finalizacion TEXT,
                    UNIQUE(periodo_id, cuil)
                )
            """)
            conn.commit()
        finally:
            conn.close()
    st.session_state["_prestamos_docentes_v174_schema_ok"] = True


# --- entry l. 37006-37024
def get_prestamos_docentes_periodo_v174(periodo_id, solo_activos=False):
    asegurar_esquema_prestamos_docentes_v174()
    if periodo_id is None:
        return pd.DataFrame(columns=["id","periodo_id","cuil","departamento_origen","fecha_desde","fecha_hasta","estado","observaciones"])
    try:
        conn = get_conn()
        filtro = " AND UPPER(TRIM(COALESCE(pr.estado,'Activo')))='ACTIVO'" if solo_activos else ""
        df = pd.read_sql(f"""
            SELECT pr.id, pr.periodo_id, pr.cuil, COALESCE(pr.departamento_origen,'') AS departamento_origen,
                   pr.fecha_desde, pr.fecha_hasta, COALESCE(pr.estado,'Activo') AS estado,
                   COALESCE(pr.observaciones,'') AS observaciones, pr.fecha_registro, pr.fecha_finalizacion
            FROM prestamos_docentes pr
            WHERE pr.periodo_id=? {filtro}
            ORDER BY pr.fecha_desde, pr.cuil
        """, conn, params=[int(periodo_id)])
        conn.close()
        return df
    except Exception:
        return pd.DataFrame(columns=["id","periodo_id","cuil","departamento_origen","fecha_desde","fecha_hasta","estado","observaciones"])


# --- entry l. 37118-37122
def _cuiles_prestamos_v174(periodo_id, solo_activos=False):
    df = get_prestamos_docentes_periodo_v174(periodo_id, solo_activos=solo_activos)
    if df.empty:
        return set()
    return {x for x in df.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x}


# --- entry l. 37126
_get_plantel_periodo_pre_v174 = get_plantel_periodo


# --- entry l. 37128-37130
def _fecha_prestamo_texto_v179(valor):
    from analisis.motor.ref.domain.designaciones import _fecha_prestamo_texto_v179 as _b05_core__fecha_prestamo_texto_v179
    return _b05_core__fecha_prestamo_texto_v179(valor)


# --- entry l. 37132-37231
def get_plantel_periodo(periodo_id):
    base = _get_plantel_periodo_pre_v174(periodo_id)
    base = base.copy() if isinstance(base, pd.DataFrame) else pd.DataFrame()
    try:
        conn = get_conn(); df_per = pd.read_sql("SELECT estado FROM periodos WHERE id=? LIMIT 1", conn, params=[int(periodo_id)]); conn.close()
        abierto = (not df_per.empty and str(df_per.iloc[0].get("estado") or "").strip().casefold() == "abierto")
    except Exception:
        abierto = False
    prestamos = get_prestamos_docentes_periodo_v174(periodo_id, solo_activos=abierto)
    claves_permitidas = {x for x in prestamos.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x} if not prestamos.empty else set()

    # v179: estas columnas pueden venir con StringDtype. Antes de actualizar una fila
    # de préstamo las dejamos en un tipo compatible y normalizamos su contenido.
    for _col_fecha_v179 in ["fecha_alta_periodo", "fecha_finalizacion_periodo"]:
        if _col_fecha_v179 in base.columns:
            try:
                base[_col_fecha_v179] = base[_col_fecha_v179].map(_fecha_prestamo_texto_v179).astype(object)
            except Exception:
                base[_col_fecha_v179] = base[_col_fecha_v179].astype(object)
        else:
            base[_col_fecha_v179] = pd.Series([""] * len(base), index=base.index, dtype=object)

    if not base.empty and "tipo_docente" in base.columns:
        tipo = base["tipo_docente"].fillna("Propio").astype(str).str.strip().str.casefold()
        claves = base.get("cuil", pd.Series(index=base.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
        base = base[(tipo.ne("prestado")) | (claves.isin(claves_permitidas))].copy()

    if prestamos.empty:
        return base.reset_index(drop=True)

    existentes = set(base.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist()) if not base.empty else set()
    mapa_p = { _clave_cuil(r.get("cuil")): r.to_dict() for _, r in prestamos.iterrows() if _clave_cuil(r.get("cuil")) }

    # Ajusta fechas/estado de filas prestadas ya producidas por la lógica previa.
    if not base.empty and "tipo_docente" in base.columns:
        for idx, r in base.iterrows():
            if str(r.get("tipo_docente", "Propio")).strip().casefold() != "prestado":
                continue
            pr = mapa_p.get(_clave_cuil(r.get("cuil")))
            if not pr:
                continue
            base.at[idx, "fecha_alta_periodo"] = _fecha_prestamo_texto_v179(pr.get("fecha_desde", ""))
            base.at[idx, "fecha_finalizacion_periodo"] = _fecha_prestamo_texto_v179(pr.get("fecha_hasta", ""))
            base.at[idx, "estado_operativo_periodo"] = (
                "Docente prestado en el período" if str(pr.get("estado", "Activo")).strip().casefold() == "activo"
                else "Préstamo finalizado en el período"
            )

    # Si el préstamo histórico fue reconstruido y ya no queda una fila local tipo Prestado,
    # lo agrega desde la identidad institucional para que el plantel histórico siga completo.
    faltantes = [r for _, r in prestamos.iterrows() if _clave_cuil(r.get("cuil")) not in existentes]
    if faltantes and USE_POSTGRESQL:
        inst_id = int(_pg_current_inst_id())
        filas_nuevas = []
        for pr in faltantes:
            cuil = str(pr.get("cuil") or "").strip()
            if not cuil:
                continue
            try:
                df_doc = _pg_read_dataframe("""
                    SELECT doc.cuil, doc.legajo, doc.apellido, doc.nombres, doc.nombre, doc.titulo,
                           COALESCE(doc.titulo_posgrado,'') AS titulo_posgrado, doc.email, doc.telefono
                    FROM docentes doc
                    WHERE doc.institucion_id=%s AND doc.cuil=%s
                    ORDER BY CASE WHEN doc.departamento_id=%s THEN 0 ELSE 1 END, doc.id
                    LIMIT 1
                """, [inst_id, cuil, int(_departamento_contexto_prestamo_v174() or 0)])
                dr = df_doc.iloc[0].to_dict() if not df_doc.empty else {}
            except Exception:
                dr = {}
            nombre = nombre_completo(str(dr.get("apellido") or ""), str(dr.get("nombres") or "")) or str(dr.get("nombre") or cuil)
            try:
                dfi = _designaciones_docentes_institucionales_analisis_v169(cuil, periodo_id)
            except Exception:
                dfi = pd.DataFrame()
            horas = float(pd.to_numeric(dfi.get("horas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not dfi.empty else 0.0
            detalles = []
            if not dfi.empty:
                for _, rd in dfi.iterrows():
                    dep = limpiar_texto_tabla(rd.get("departamento", "")); cargo = limpiar_texto_tabla(rd.get("cargo", "")); ded = limpiar_texto_tabla(rd.get("dedicacion", ""))
                    t = " · ".join([x for x in [cargo, ded] if x])
                    if dep: t = f"{dep}: {t}" if t else dep
                    if t and t not in detalles: detalles.append(t)
            detalle = f"DOCENTE PRESTADO desde {pr.get('departamento_origen','') or 'otro departamento'}"
            if detalles: detalle += " | Designación institucional: " + " / ".join(detalles)
            detalle += ". No computa como designación propia del departamento receptor."
            filas_nuevas.append({
                "cuil": cuil, "legajo": dr.get("legajo", ""), "nombre_completo": nombre,
                "titulo": dr.get("titulo", ""), "titulo_posgrado": dr.get("titulo_posgrado", ""),
                "email": dr.get("email", ""), "telefono": dr.get("telefono", ""), "tipo_docente": "Prestado",
                "estado_operativo_periodo": "Docente prestado en el período" if str(pr.get("estado","Activo")).strip().casefold()=="activo" else "Préstamo finalizado en el período",
                "fecha_alta_periodo": _fecha_prestamo_texto_v179(pr.get("fecha_desde", "")), "fecha_finalizacion_periodo": _fecha_prestamo_texto_v179(pr.get("fecha_hasta", "")),
                "designaciones_del_periodo": int(len(dfi)) if not dfi.empty else 0,
                "designaciones_activas": int(len(dfi)) if not dfi.empty else 0,
                "horas_activas": round(horas,2), "horas_registradas_periodo": round(horas,2),
                "detalle_designaciones": detalle,
            })
        if filas_nuevas:
            base = pd.concat([base, pd.DataFrame(filas_nuevas)], ignore_index=True, sort=False)
    return base.reset_index(drop=True)


# --- entry l. 37266
_get_metricas_analisis_periodo_pre_v174 = get_metricas_analisis_periodo


# --- entry l. 37268-37283
def get_metricas_analisis_periodo(periodo_id):
    datos = dict(_get_metricas_analisis_periodo_pre_v174(periodo_id) or {})
    try:
        prestamos = get_prestamos_docentes_periodo_v174(periodo_id, solo_activos=False)
        claves_prest = {x for x in prestamos.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x} if not prestamos.empty else set()
        df_asig = datos.get("df_asig", pd.DataFrame())
        if df_asig is None or df_asig.empty:
            df_asig = get_asignaciones_comisiones_periodo(periodo_id)
        claves_con_comision = set()
        if isinstance(df_asig, pd.DataFrame) and not df_asig.empty:
            claves_con_comision = {x for x in df_asig.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x}
        datos["docentes_prestados_recibidos"] = int(len(claves_prest & claves_con_comision))
        datos["df_prestamos_docentes_periodo"] = prestamos
    except Exception:
        pass
    return datos


# --- entry l. 37288
_preparar_analisis_movimiento_docente_pre_v174 = preparar_analisis_movimiento_docente


# --- entry l. 37290-37292
def _destino_ad_honorem_mov_v174(detalle):
    from analisis.motor.ref.domain.movimientos import _destino_ad_honorem_mov_v174 as _b05_core__destino_ad_honorem_mov_v174
    return _b05_core__destino_ad_honorem_mov_v174(detalle)


# --- entry l. 37295-37317
def preparar_analisis_movimiento_docente(df_movimientos):
    base_v269 = df_movimientos.copy() if isinstance(df_movimientos, pd.DataFrame) else df_movimientos
    try:
        if isinstance(base_v269, pd.DataFrame) and not base_v269.empty and "periodo_id" in base_v269.columns:
            pids_v269 = pd.to_numeric(base_v269["periodo_id"], errors="coerce").dropna().astype(int).unique().tolist()
            if len(pids_v269) == 1:
                base_v269 = _canonizar_movimientos_designaciones_v269(base_v269, pids_v269[0], preservar_no_designacion=True)
    except Exception:
        base_v269 = df_movimientos
    out = _preparar_analisis_movimiento_docente_pre_v174(base_v269)
    if out is None or out.empty:
        return out
    out = out.copy()
    for idx, r in out.iterrows():
        tipo = str(r.get("tipo_movimiento") or "").strip()
        if tipo == "Cambio de condición Ad Honorem":
            destino = _destino_ad_honorem_mov_v174(r.get("detalle", ""))
            if destino:
                out.at[idx, "tipo_movimiento"] = destino
                out.at[idx, "categoria_movimiento"] = destino
        elif tipo in {"Pase a Ad Honorem", "Pase a Rentado"}:
            out.at[idx, "categoria_movimiento"] = tipo
    return out


# --- entry l. 37327-37538
def _prestados_recibidos_periodo_v175(periodo_id):
    """Reconstruye quién fue prestado RECIBIDO en el período seleccionado.

    Criterio operativo/histórico:
    - tuvo al menos una asignación en una comisión del departamento receptor en ese período; y
    - existe evidencia de préstamo del mismo período (tabla de préstamos o movimiento explícito),
      o bien no tuvo designación docente local y sí tuvo designación docente en otro departamento
      del mismo semestre. Para datos anteriores a v174 se conserva como último respaldo la marca
      histórica ``docentes.tipo_docente = Prestado``.

    La comparación de CUIL se hace normalizada, por lo que diferencias de guiones/espacios no
    hacen desaparecer un préstamo histórico.
    """
    columnas = ["cuil", "docente", "departamento_origen", "evidencia", "estado_asignacion"]
    if periodo_id is None:
        return pd.DataFrame(columns=columnas)

    if not USE_POSTGRESQL:
        try:
            df_asig = get_asignaciones_comisiones_periodo(periodo_id)
            if df_asig is None or df_asig.empty:
                return pd.DataFrame(columns=columnas)
            prestamos = get_prestamos_docentes_periodo_v174(periodo_id, solo_activos=False)
            claves_pr = _cuiles_prestamos_v174(periodo_id, solo_activos=False)
            registros = []
            for _, r in df_asig.iterrows():
                cuil = str(r.get("cuil") or "").strip()
                clave = _clave_cuil(cuil)
                tipo = str(r.get("tipo_docente") or "").strip().casefold()
                if clave and (clave in claves_pr or tipo == "prestado"):
                    registros.append({
                        "cuil": cuil,
                        "docente": str(r.get("docente") or cuil),
                        "departamento_origen": "",
                        "evidencia": "Préstamo registrado" if clave in claves_pr else "Marca histórica de prestado",
                        "estado_asignacion": str(r.get("estado") or ""),
                    })
            if not registros:
                return pd.DataFrame(columns=columnas)
            out = pd.DataFrame(registros).drop_duplicates(subset=["cuil"], keep="first")
            return out[columnas].reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=columnas)

    try:
        inst_id = int(_pg_current_inst_id())
        dep_id = _departamento_contexto_prestamo_v174()
        if dep_id is None:
            return pd.DataFrame(columns=columnas)
        dep_id = int(dep_id)

        df_per = _pg_read_dataframe(
            "SELECT id, anio, semestre, estado FROM periodos WHERE id=%s AND institucion_id=%s AND departamento_id=%s LIMIT 1",
            [int(periodo_id), inst_id, dep_id],
        )
        if df_per.empty:
            return pd.DataFrame(columns=columnas)
        anio = int(df_per.iloc[0].get("anio"))
        semestre = int(df_per.iloc[0].get("semestre"))

        # 1) La persona debe haber tenido una asignación en comisión del receptor.
        df_asig = _pg_read_dataframe("""
            SELECT DISTINCT a.cuil, COALESCE(a.estado,'Activa') AS estado_asignacion
            FROM asignaciones_docentes_comision a
            JOIN comisiones co
              ON co.id=a.comision_id
             AND co.institucion_id=a.institucion_id
             AND co.departamento_id=a.departamento_id
            WHERE co.institucion_id=%s AND co.departamento_id=%s AND co.periodo_id=%s
              AND COALESCE(TRIM(a.cuil),'')<>''
        """, [inst_id, dep_id, int(periodo_id)])
        if df_asig.empty:
            return pd.DataFrame(columns=columnas)

        # Padrón local solo para nombre/tipo histórico; nunca define por sí solo el período.
        df_doc_local = _pg_read_dataframe("""
            SELECT cuil,
                   CASE WHEN apellido IS NOT NULL AND nombres IS NOT NULL THEN apellido || ', ' || nombres
                        WHEN nombre IS NOT NULL THEN nombre ELSE cuil END AS docente,
                   COALESCE(tipo_docente,'Propio') AS tipo_docente,
                   COALESCE(observaciones,'') AS observaciones
            FROM docentes
            WHERE institucion_id=%s AND departamento_id=%s
        """, [inst_id, dep_id])
        mapa_doc = {}
        for _, r in df_doc_local.iterrows():
            k = _clave_cuil(r.get("cuil"))
            if k:
                mapa_doc[k] = r.to_dict()

        # Designaciones docentes locales del período. Si existen, la persona es propia/compartida,
        # salvo que haya un préstamo explícito registrado para ese mismo período.
        df_local_des = _pg_read_dataframe("""
            SELECT DISTINCT cuil
            FROM designaciones
            WHERE institucion_id=%s AND departamento_id=%s AND periodo_id=%s
              AND COALESCE(funcion_no_docente,0)=0
              AND COALESCE(TRIM(cuil),'')<>''
        """, [inst_id, dep_id, int(periodo_id)])
        claves_local_des = {_clave_cuil(x) for x in df_local_des.get("cuil", pd.Series(dtype=str)).tolist() if _clave_cuil(x)}

        # Designaciones docentes en otros departamentos del MISMO período académico.
        df_otras_des = _pg_read_dataframe("""
            SELECT DISTINCT d.cuil, dep.nombre AS departamento_origen
            FROM designaciones d
            JOIN periodos p
              ON p.id=d.periodo_id AND p.institucion_id=d.institucion_id AND p.departamento_id=d.departamento_id
            JOIN departamentos dep
              ON dep.id=d.departamento_id AND dep.institucion_id=d.institucion_id
            WHERE d.institucion_id=%s AND d.departamento_id<>%s
              AND p.anio=%s AND p.semestre=%s
              AND COALESCE(d.funcion_no_docente,0)=0
              AND COALESCE(TRIM(d.cuil),'')<>''
        """, [inst_id, dep_id, anio, semestre])
        origenes_otros = {}
        for _, r in df_otras_des.iterrows():
            k = _clave_cuil(r.get("cuil"))
            dep = str(r.get("departamento_origen") or "").strip()
            if not k:
                continue
            origenes_otros.setdefault(k, [])
            if dep and dep not in origenes_otros[k]:
                origenes_otros[k].append(dep)

        # Evidencia explícita: relación v174, activa o finalizada, porque el análisis
        # pregunta si fue prestado EN ESE PERÍODO, no si lo sigue siendo hoy.
        try:
            df_pr = _pg_read_dataframe("""
                SELECT cuil, COALESCE(departamento_origen,'') AS departamento_origen,
                       COALESCE(estado,'Activo') AS estado
                FROM prestamos_docentes
                WHERE institucion_id=%s AND departamento_id=%s AND periodo_id=%s
            """, [inst_id, dep_id, int(periodo_id)])
        except Exception:
            df_pr = pd.DataFrame()
        mapa_pr = {}
        for _, r in df_pr.iterrows():
            k = _clave_cuil(r.get("cuil"))
            if k:
                mapa_pr[k] = r.to_dict()

        df_mov_pr = _pg_read_dataframe("""
            SELECT DISTINCT cuil
            FROM movimientos
            WHERE institucion_id=%s AND departamento_id=%s AND periodo_id=%s
              AND LOWER(TRIM(COALESCE(tipo_movimiento,'')))='alta de docente prestado'
              AND COALESCE(TRIM(cuil),'')<>''
        """, [inst_id, dep_id, int(periodo_id)])
        claves_mov_pr = {_clave_cuil(x) for x in df_mov_pr.get("cuil", pd.Series(dtype=str)).tolist() if _clave_cuil(x)}

        estados_por_clave = {}
        cuil_original = {}
        for _, r in df_asig.iterrows():
            k = _clave_cuil(r.get("cuil"))
            if not k:
                continue
            cuil_original.setdefault(k, str(r.get("cuil") or "").strip())
            estados_por_clave.setdefault(k, [])
            est = str(r.get("estado_asignacion") or "").strip()
            if est and est not in estados_por_clave[k]:
                estados_por_clave[k].append(est)

        registros = []
        for k in sorted(cuil_original.keys()):
            doc = mapa_doc.get(k, {})
            tipo_local = str(doc.get("tipo_docente") or "").strip().casefold()
            tiene_local = k in claves_local_des
            tiene_otro = k in origenes_otros
            tiene_pr = k in mapa_pr
            tiene_mov = k in claves_mov_pr

            es_prestado = bool(
                tiene_pr
                or tiene_mov
                or ((not tiene_local) and (tiene_otro or tipo_local == "prestado"))
            )
            if not es_prestado:
                continue

            evidencias = []
            if tiene_pr:
                evidencias.append("Préstamo registrado en el período")
            if tiene_mov:
                evidencias.append("Alta de docente prestado registrada")
            if tiene_otro and not tiene_local:
                evidencias.append("Comisión receptora + designación docente en otro departamento")
            if tipo_local == "prestado" and not (tiene_pr or tiene_mov or tiene_otro):
                evidencias.append("Marca histórica de prestado")

            origen = str((mapa_pr.get(k) or {}).get("departamento_origen") or "").strip()
            if not origen and tiene_otro:
                origen = " / ".join(origenes_otros.get(k, []))
            if not origen:
                origen = _departamento_origen_desde_obs_prestado(doc.get("observaciones", ""))

            registros.append({
                "cuil": cuil_original[k],
                "docente": str(doc.get("docente") or cuil_original[k]).strip(),
                "departamento_origen": origen,
                "evidencia": " · ".join(evidencias),
                "estado_asignacion": " / ".join(estados_por_clave.get(k, [])),
            })

        if not registros:
            return pd.DataFrame(columns=columnas)
        return pd.DataFrame(registros, columns=columnas).sort_values(["docente", "cuil"], kind="stable").reset_index(drop=True)
    except Exception as e:
        try:
            st.session_state["_prestados_v175_error"] = str(e)
        except Exception:
            pass
        return pd.DataFrame(columns=columnas)


# --- entry l. 37541
_get_metricas_analisis_periodo_pre_v175 = get_metricas_analisis_periodo


# --- entry l. 37543-37551
def get_metricas_analisis_periodo(periodo_id):
    datos = dict(_get_metricas_analisis_periodo_pre_v175(periodo_id) or {})
    try:
        df_pr = _prestados_recibidos_periodo_v175(periodo_id)
        datos["docentes_prestados_recibidos"] = int(len(df_pr))
        datos["df_prestados_recibidos_periodo"] = df_pr
    except Exception:
        pass
    return datos


# --- entry l. 37554-37556
def _normalizar_hora_export_v175(valor):
    from analisis.motor.ref.common.horarios import _normalizar_hora_export_v175 as _b05_core__normalizar_hora_export_v175
    return _b05_core__normalizar_hora_export_v175(valor)


# --- entry l. 37778-37780
def _filtrar_movimientos_informe_v176(df_mov_analisis):
    from analisis.motor.ref.domain.movimientos import _filtrar_movimientos_informe_v176 as _b05_core__filtrar_movimientos_informe_v176
    return _b05_core__filtrar_movimientos_informe_v176(df_mov_analisis)


# --- entry l. 37784-37786
def _ordenar_comisiones_informe_por_asignatura_v201(df_com):
    from analisis.motor.ref.domain.comisiones import _ordenar_comisiones_informe_por_asignatura_v201 as _b05_core__ordenar_comisiones_informe_por_asignatura_v201
    return _b05_core__ordenar_comisiones_informe_por_asignatura_v201(df_com)


# --- entry l. 37788-37885
def _datos_comisiones_informe_v176(periodo_id):
    """Una fila por comisión del período, con materias/códigos y docentes reales."""
    columnas = ["fecha", "comision", "codigos", "asignaturas", "docentes", "horarios", "turno", "modalidad", "sede", "estado"]
    if periodo_id is None:
        return pd.DataFrame(columns=columnas)
    try:
        df_com = get_comisiones(periodo_id=int(periodo_id), solo_activas=False)
    except Exception:
        df_com = pd.DataFrame()
    if df_com is None or df_com.empty:
        return pd.DataFrame(columns=columnas)

    registros = []
    df_com = _ordenar_comisiones_informe_por_asignatura_v201(df_com)
    for _, co in df_com.iterrows():
        try:
            cid = int(co.get("id"))
        except Exception:
            continue

        pares = []
        try:
            links = _leer_vinculos_materias_comisiones_v118([cid], global_institucion=False)
        except Exception:
            links = pd.DataFrame()
        if isinstance(links, pd.DataFrame) and not links.empty:
            for _, lr in links.iterrows():
                cod = limpiar_texto_tabla(lr.get("codigo_snapshot", ""))
                asig = limpiar_texto_tabla(lr.get("asignatura_snapshot", ""))
                clave = (normalizar_codigo_materia(cod), normalizar_clave(asig))
                if (cod or asig) and clave not in [(normalizar_codigo_materia(x[0]), normalizar_clave(x[1])) for x in pares]:
                    pares.append((cod, asig))
        if not pares:
            try:
                reps = get_materias_conceptuales_comision_v122(cid) or []
            except Exception:
                reps = []
            if not reps:
                try:
                    reps = [int(co.get("materia_id"))]
                except Exception:
                    reps = []
            for mid in reps:
                try:
                    info = get_materia_comision(mid) or {}
                except Exception:
                    info = {}
                cod = limpiar_texto_tabla(info.get("codigo", "")) or limpiar_texto_tabla(co.get("codigo_materia", ""))
                asig = limpiar_texto_tabla(info.get("asignatura", "")) or limpiar_texto_tabla(co.get("asignatura", ""))
                clave = (normalizar_codigo_materia(cod), normalizar_clave(asig))
                if (cod or asig) and clave not in [(normalizar_codigo_materia(x[0]), normalizar_clave(x[1])) for x in pares]:
                    pares.append((cod, asig))

        try:
            da = get_asignaciones_comision(cid)
        except Exception:
            da = pd.DataFrame()
        docentes = []
        if isinstance(da, pd.DataFrame) and not da.empty:
            for _, ar in da.iterrows():
                nom = limpiar_texto_tabla(ar.get("docente", "")) or limpiar_texto_tabla(ar.get("cuil", ""))
                rol = limpiar_texto_tabla(ar.get("rol", ""))
                est = limpiar_texto_tabla(ar.get("estado", ""))
                txt = nom
                if rol:
                    txt += f" ({rol})"
                if est and est.casefold() != "activa":
                    txt += f" [{est}]"
                if txt and txt not in docentes:
                    docentes.append(txt)

        try:
            dh = get_horarios_comision(cid)
        except Exception:
            dh = pd.DataFrame()
        horarios = []
        if isinstance(dh, pd.DataFrame) and not dh.empty:
            for _, hr in dh.iterrows():
                dia = limpiar_texto_tabla(hr.get("dia", ""))
                hi = _normalizar_hora_export_v175(hr.get("hora_inicio", ""))
                hf = _normalizar_hora_export_v175(hr.get("hora_fin", ""))
                txt = " ".join(x for x in [dia, f"{hi}-{hf}" if hi or hf else ""] if x).strip()
                if txt and txt not in horarios:
                    horarios.append(txt)

        registros.append({
            "fecha": limpiar_texto_tabla(co.get("fecha_creacion", "")),
            "comision": limpiar_texto_tabla(co.get("nombre_comision", "")),
            "codigos": " / ".join([x[0] for x in pares if x[0]]),
            "asignaturas": " / ".join([x[1] for x in pares if x[1]]),
            "docentes": "; ".join(docentes) if docentes else "Sin docentes asignados",
            "horarios": " / ".join(horarios),
            "turno": limpiar_texto_tabla(co.get("turno", "")),
            "modalidad": limpiar_texto_tabla(co.get("modalidad", "")),
            "sede": limpiar_texto_tabla(co.get("sede", "")),
            "estado": limpiar_texto_tabla(co.get("estado", "")),
        })
    return pd.DataFrame(registros, columns=columnas)


# --- entry l. 37888-37953
def _datos_proyectos_informe_v176(periodo_id, tipo="investigacion"):
    """Proyectos del período vinculados al departamento y sus docentes asignados."""
    tipo = "extension" if str(tipo).strip().casefold().startswith("ext") else "investigacion"
    try:
        if tipo == "extension":
            catalogo = get_proyectos_extension(solo_activos=False, periodo_id=int(periodo_id))
            asignaciones = get_extension_docente(periodo_id=int(periodo_id), incluir_bajas=True, todos_departamentos=False)
        else:
            catalogo = get_proyectos_investigacion(solo_activos=False, periodo_id=int(periodo_id))
            asignaciones = get_investigacion_docente(periodo_id=int(periodo_id), incluir_bajas=True, todos_departamentos=False)
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

    catalogo = catalogo.copy() if isinstance(catalogo, pd.DataFrame) else pd.DataFrame()
    asignaciones = asignaciones.copy() if isinstance(asignaciones, pd.DataFrame) else pd.DataFrame()

    ids_asignados = set()
    if not asignaciones.empty and "proyecto_id" in asignaciones.columns:
        ids_asignados = {int(x) for x in pd.to_numeric(asignaciones["proyecto_id"], errors="coerce").dropna().tolist()}

    # En PostgreSQL el catálogo es institucional. En el informe departamental se muestran
    # los proyectos creados por el departamento o aquellos en los que tuvo asignaciones.
    if USE_POSTGRESQL and not catalogo.empty:
        try:
            dep_id = int(_pg_current_dep_id())
        except Exception:
            dep_id = None
        if dep_id is not None:
            ids_cat = pd.to_numeric(catalogo.get("id", pd.Series(index=catalogo.index, dtype=float)), errors="coerce")
            creadores = pd.to_numeric(catalogo.get("departamento_creador_id", pd.Series(index=catalogo.index, dtype=float)), errors="coerce")
            catalogo = catalogo[(creadores.eq(dep_id)) | (ids_cat.isin(ids_asignados))].copy()

    # Compatibilidad histórica: si una asignación referencia un proyecto que ya no está
    # en el catálogo filtrado, se conserva una ficha mínima en el informe.
    ids_catalogo = set()
    if not catalogo.empty and "id" in catalogo.columns:
        ids_catalogo = {int(x) for x in pd.to_numeric(catalogo["id"], errors="coerce").dropna().tolist()}
    faltantes = ids_asignados - ids_catalogo
    if faltantes and not asignaciones.empty:
        extras = []
        for pid in sorted(faltantes):
            sub = asignaciones[pd.to_numeric(asignaciones.get("proyecto_id"), errors="coerce").eq(pid)]
            if sub.empty:
                continue
            r = sub.iloc[0]
            extras.append({
                "id": pid,
                "nombre_proyecto": r.get("nombre_proyecto", ""),
                "codigo_proyecto": r.get("codigo_proyecto", ""),
                "instituto_proyecto": r.get("instituto_proyecto", ""),
                "anio_llamado": r.get("anio_llamado", ""),
                "fecha_inicio": r.get("fecha_inicio", ""),
                "fecha_fin": r.get("fecha_fin", ""),
                "periodo_ejecucion": r.get("periodo_ejecucion", ""),
                "estado": r.get("estado_proyecto", ""),
                "observaciones": "",
                "departamento_creador": "",
            })
        if extras:
            catalogo = pd.concat([catalogo, pd.DataFrame(extras)], ignore_index=True, sort=False)

    if not catalogo.empty:
        orden = [c for c in ["codigo_proyecto", "nombre_proyecto"] if c in catalogo.columns]
        if orden:
            catalogo = catalogo.sort_values(orden, kind="stable")
    return catalogo.reset_index(drop=True), asignaciones.reset_index(drop=True)


# --- entry l. 37956-38194
def generar_informe_movimiento_docente_word_v175(periodo_nombre, departamento, df_mov_analisis, periodo_id=None):
    """Informe ejecutivo del período con movimientos relevantes, comisiones y proyectos."""
    Document = _obtener_document_python_docx()
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(1.7); sec.bottom_margin = Cm(1.7)
    sec.left_margin = Cm(1.7); sec.right_margin = Cm(1.7)

    estilos = doc.styles
    estilos["Normal"].font.name = "Arial"; estilos["Normal"].font.size = Pt(9)
    for nombre in ["Title", "Heading 1", "Heading 2", "Heading 3"]:
        try:
            estilos[nombre].font.name = "Arial"
        except Exception:
            pass
    estilos["Title"].font.size = Pt(18); estilos["Title"].font.bold = True
    estilos["Heading 1"].font.size = Pt(13); estilos["Heading 1"].font.bold = True
    estilos["Heading 2"].font.size = Pt(11); estilos["Heading 2"].font.bold = True
    try:
        estilos["Heading 3"].font.size = Pt(9.5); estilos["Heading 3"].font.bold = True
    except Exception:
        pass

    def sombrear(celda, fill):
        tcPr = celda._tc.get_or_add_tcPr()
        shd = tcPr.find(qn("w:shd"))
        if shd is None:
            shd = OxmlElement("w:shd"); tcPr.append(shd)
        shd.set(qn("w:fill"), fill)

    def texto_celda(celda, texto, bold=False, color=None, tam=8.2):
        celda.text = ""
        p = celda.paragraphs[0]
        r = p.add_run(str(texto if texto is not None else ""))
        r.bold = bold; r.font.name = "Arial"; r.font.size = Pt(tam)
        if color:
            r.font.color.rgb = RGBColor.from_string(color)
        celda.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    def fecha_txt(valor):
        if valor is None or (isinstance(valor, float) and pd.isna(valor)):
            return ""
        try:
            dt = pd.to_datetime(valor, errors="coerce")
            if pd.notna(dt):
                return dt.strftime("%d/%m/%Y")
        except Exception:
            pass
        return str(valor or "")

    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("INFORME DE MOVIMIENTO Y OPERACIÓN DOCENTE")
    psub = doc.add_paragraph(); psub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = psub.add_run(f"{departamento} · Período {periodo_nombre}")
    r.bold = True; r.font.name = "Arial"; r.font.size = Pt(11)
    pfecha = doc.add_paragraph(); pfecha.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = pfecha.add_run(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    r.font.name = "Arial"; r.font.size = Pt(8); r.font.color.rgb = RGBColor(100, 100, 100)

    df_total = df_mov_analisis.copy() if isinstance(df_mov_analisis, pd.DataFrame) else pd.DataFrame()
    df_filtrado = _filtrar_movimientos_informe_v176(df_total)
    # Aperturas se presentan con los datos reales de la comisión en una sección propia.
    if not df_filtrado.empty:
        tipo_norm = df_filtrado.get("tipo_movimiento", pd.Series("", index=df_filtrado.index)).fillna("").astype(str).map(normalizar_clave)
        cat_norm = df_filtrado.get("categoria_movimiento", pd.Series("", index=df_filtrado.index)).fillna("").astype(str).map(normalizar_clave)
        es_apertura = tipo_norm.eq(normalizar_clave("Apertura de comisión")) | cat_norm.eq(normalizar_clave("Apertura de comisión"))
        df = df_filtrado[~es_apertura].copy()
    else:
        df = df_filtrado.copy()

    df_comisiones = _datos_comisiones_informe_v176(periodo_id) if periodo_id is not None else pd.DataFrame()
    df_proy_inv, df_asig_inv = _datos_proyectos_informe_v176(periodo_id, "investigacion") if periodo_id is not None else (pd.DataFrame(), pd.DataFrame())
    df_proy_ext, df_asig_ext = _datos_proyectos_informe_v176(periodo_id, "extension") if periodo_id is not None else (pd.DataFrame(), pd.DataFrame())

    resumen = resumen_movimiento_docente(df) if not df.empty else pd.DataFrame()
    balance = balance_horas_movimiento_docente(df) if not df.empty else {
        "horas_altas": 0, "horas_bajas": 0, "horas_aumentos": 0, "horas_disminuciones": 0, "saldo_neto": 0
    }
    total_mov = int(len(df))
    docentes_afectados = int(df.get("cuil", pd.Series(dtype=str)).replace("", pd.NA).dropna().astype(str).nunique()) if not df.empty else 0

    doc.add_heading("1. Resumen ejecutivo", level=1)
    p = doc.add_paragraph()
    p.add_run(
        f"Durante el período {periodo_nombre} se registraron {total_mov} movimientos administrativos relevantes "
        f"de designaciones, con {docentes_afectados} persona/s afectada/s. El saldo neto de horas derivado de altas, "
        f"bajas y cambios de dedicación fue de {float(balance.get('saldo_neto', 0) or 0):+g} horas. "
        f"Además, el período contiene {len(df_comisiones)} comisión/es, {len(df_proy_inv)} proyecto/s de investigación "
        f"y {len(df_proy_ext)} proyecto/s de extensión vinculados al departamento."
    )

    categorias_clave = [
        ("Altas de designaciones", "Altas"), ("Bajas de designaciones", "Bajas"),
        ("Aumentos de dedicación", "Aumentos"), ("Disminuciones de dedicación", "Disminuciones"),
        ("Cambios de cargo", "Cambios de cargo"), ("Pase a Ad Honorem", "Pase a Ad Honorem"),
        ("Pase a Rentado", "Pase a Rentado"),
    ]
    tabla_kpi = doc.add_table(rows=2, cols=len(categorias_clave))
    tabla_kpi.alignment = WD_TABLE_ALIGNMENT.CENTER; tabla_kpi.autofit = True
    for j, (cat, rotulo) in enumerate(categorias_clave):
        cantidad = int((df.get("categoria_movimiento", pd.Series(dtype=str)) == cat).sum()) if not df.empty else 0
        texto_celda(tabla_kpi.cell(0, j), rotulo, bold=True, color="FFFFFF", tam=7.4); sombrear(tabla_kpi.cell(0, j), "1F4E78")
        texto_celda(tabla_kpi.cell(1, j), cantidad, bold=True, tam=10); sombrear(tabla_kpi.cell(1, j), "EAF2F8")

    doc.add_heading("2. Balance de horas", level=1)
    tb = doc.add_table(rows=2, cols=5); tb.alignment = WD_TABLE_ALIGNMENT.CENTER; tb.style = "Table Grid"
    balance_items = [
        ("Altas", balance.get("horas_altas", 0)), ("Bajas", balance.get("horas_bajas", 0)),
        ("Aumentos", balance.get("horas_aumentos", 0)), ("Disminuciones", balance.get("horas_disminuciones", 0)),
        ("Saldo neto", balance.get("saldo_neto", 0)),
    ]
    for j, (rot, val) in enumerate(balance_items):
        texto_celda(tb.cell(0, j), rot, bold=True, color="FFFFFF"); sombrear(tb.cell(0, j), "2F75B5")
        texto_celda(tb.cell(1, j), f"{float(val or 0):+g} hs", bold=True, tam=9.5)
    doc.add_paragraph(
        "El saldo horario considera altas, bajas, aumentos y disminuciones de dedicación. "
        "Los cambios de cargo y los pases entre Ad Honorem y Rentado se informan por separado."
    )

    doc.add_heading("3. Resumen por tipo de movimiento", level=1)
    if resumen is None or resumen.empty:
        doc.add_paragraph("No se registraron movimientos relevantes de designaciones para el período seleccionado.")
    else:
        tr = doc.add_table(rows=1, cols=4); tr.style = "Table Grid"; tr.alignment = WD_TABLE_ALIGNMENT.CENTER
        headers = ["Movimiento", "Cantidad", "Docentes afectados", "Variación de horas"]
        for j, h in enumerate(headers):
            texto_celda(tr.cell(0, j), h, bold=True, color="FFFFFF"); sombrear(tr.cell(0, j), "1F4E78")
        orden_preferido = {c: i for i, (c, _) in enumerate(categorias_clave)}
        res2 = resumen.copy(); res2["_o"] = res2["categoria_movimiento"].map(orden_preferido).fillna(99)
        res2 = res2.sort_values(["_o", "categoria_movimiento"], kind="stable")
        for _, rr in res2.iterrows():
            cells = tr.add_row().cells
            vals = [rr.get("categoria_movimiento", ""), rr.get("movimientos", 0), rr.get("docentes_afectados", 0), f"{float(rr.get('variacion_horas', 0) or 0):+g} hs"]
            for j, v in enumerate(vals): texto_celda(cells[j], v, tam=8.1)

    doc.add_page_break()
    doc.add_heading("4. Detalle de movimientos relevantes", level=1)
    if df.empty:
        doc.add_paragraph("Sin movimientos administrativos relevantes para detallar.")
    else:
        orden_cat = [x[0] for x in categorias_clave] + [x for x in df["categoria_movimiento"].dropna().astype(str).unique().tolist() if x not in [c[0] for c in categorias_clave]]
        for categoria in orden_cat:
            dcat = df[df["categoria_movimiento"].astype(str) == str(categoria)].copy()
            if dcat.empty:
                continue
            doc.add_heading(f"{categoria} ({len(dcat)})", level=2)
            td = doc.add_table(rows=1, cols=6); td.style = "Table Grid"; td.alignment = WD_TABLE_ALIGNMENT.CENTER
            hs = ["Fecha", "Docente", "CUIL", "Detalle", "Observaciones", "Δ horas"]
            for j, h in enumerate(hs):
                texto_celda(td.cell(0, j), h, bold=True, color="FFFFFF", tam=7.4); sombrear(td.cell(0, j), "5B9BD5")
            for _, rr in dcat.sort_values(["fecha", "docente"], kind="stable").iterrows():
                cells = td.add_row().cells
                vals = [rr.get("fecha", ""), rr.get("docente", ""), rr.get("cuil", ""), rr.get("detalle", ""), rr.get("observaciones", ""), f"{float(rr.get('variacion_horas', 0) or 0):+g}"]
                for j, v in enumerate(vals): texto_celda(cells[j], v, tam=7.2)

    doc.add_heading("5. Apertura de comisiones", level=1)
    doc.add_paragraph(
        "Se detallan las comisiones creadas en el período con su fecha de apertura, materias/códigos y el equipo docente registrado."
    )
    if df_comisiones is None or df_comisiones.empty:
        doc.add_paragraph("No hay comisiones registradas para el período seleccionado.")
    else:
        tc = doc.add_table(rows=1, cols=6); tc.style = "Table Grid"; tc.alignment = WD_TABLE_ALIGNMENT.CENTER
        heads = ["Fecha", "Comisión", "Código/s", "Asignatura/s", "Docentes", "Horario/s"]
        for j, h in enumerate(heads):
            texto_celda(tc.cell(0, j), h, bold=True, color="FFFFFF", tam=7.2); sombrear(tc.cell(0, j), "4472C4")
        for _, rr in df_comisiones.iterrows():
            cells = tc.add_row().cells
            vals = [fecha_txt(rr.get("fecha", "")), rr.get("comision", ""), rr.get("codigos", ""), rr.get("asignaturas", ""), rr.get("docentes", ""), rr.get("horarios", "")]
            for j, v in enumerate(vals): texto_celda(cells[j], v, tam=6.9)

    def agregar_proyectos(titulo, catalogo, asignaciones, numero):
        doc.add_heading(f"{numero}. {titulo}", level=1)
        if catalogo is None or catalogo.empty:
            doc.add_paragraph("No hay proyectos vinculados al departamento para el período seleccionado.")
            return
        for _, pr in catalogo.iterrows():
            pid = pr.get("id")
            codigo = limpiar_texto_tabla(pr.get("codigo_proyecto", ""))
            nombre = limpiar_texto_tabla(pr.get("nombre_proyecto", "")) or "Proyecto sin nombre"
            titulo_pr = f"{codigo} — {nombre}" if codigo else nombre
            doc.add_heading(titulo_pr, level=2)
            meta = []
            instituto = limpiar_texto_tabla(pr.get("instituto_proyecto", ""))
            if instituto: meta.append(f"Instituto/área: {instituto}")
            anio = limpiar_texto_tabla(pr.get("anio_llamado", ""))
            if anio: meta.append(f"Año de llamado: {anio}")
            fi = fecha_txt(pr.get("fecha_inicio", "")); ff = fecha_txt(pr.get("fecha_fin", ""))
            if fi or ff: meta.append(f"Vigencia: {fi or '—'} a {ff or '—'}")
            estado = limpiar_texto_tabla(pr.get("estado", pr.get("situacion", "")))
            if estado: meta.append(f"Estado: {estado}")
            depc = limpiar_texto_tabla(pr.get("departamento_creador", ""))
            if depc: meta.append(f"Departamento creador: {depc}")
            if meta:
                doc.add_paragraph(" · ".join(meta))
            obs = limpiar_texto_tabla(pr.get("observaciones", ""))
            if obs:
                pobs = doc.add_paragraph(); pobs.add_run("Observaciones: ").bold = True; pobs.add_run(obs)

            if asignaciones is None or asignaciones.empty or "proyecto_id" not in asignaciones.columns:
                sub = pd.DataFrame()
            else:
                try:
                    sub = asignaciones[pd.to_numeric(asignaciones["proyecto_id"], errors="coerce").eq(int(pid))].copy()
                except Exception:
                    sub = pd.DataFrame()
            if sub.empty:
                doc.add_paragraph("Sin docentes asignados en este departamento durante el período.")
            else:
                ta = doc.add_table(rows=1, cols=6); ta.style = "Table Grid"; ta.alignment = WD_TABLE_ALIGNMENT.CENTER
                hds = ["Docente", "CUIL", "Rol", "Hs semanales", "Estado", "Departamento"]
                for j, h in enumerate(hds):
                    texto_celda(ta.cell(0, j), h, bold=True, color="FFFFFF", tam=7.2); sombrear(ta.cell(0, j), "70AD47")
                for _, ar in sub.sort_values([c for c in ["docente", "rol"] if c in sub.columns], kind="stable").iterrows():
                    cells = ta.add_row().cells
                    vals = [ar.get("docente", ""), ar.get("cuil", ""), ar.get("rol", ""), f"{float(ar.get('horas_asignadas', 0) or 0):g}", ar.get("estado_asignacion", ""), ar.get("departamento_asignacion", "")]
                    for j, v in enumerate(vals): texto_celda(cells[j], v, tam=7.2)

    agregar_proyectos("Proyectos de investigación y docentes asignados", df_proy_inv, df_asig_inv, 6)
    agregar_proyectos("Proyectos de extensión y docentes asignados", df_proy_ext, df_asig_ext, 7)

    doc.add_heading("8. Criterio de lectura", level=1)
    for texto in [
        "La unidad principal de movimiento de dotación es la designación, no el alta o baja de la persona.",
        "El informe omite eventos técnicos/operativos que no aportan a la lectura ejecutiva solicitada, como generación de disposiciones, altas de horarios y renovaciones automáticas.",
        "Las aperturas de comisión se reconstruyen desde las comisiones reales del período para informar código/s, asignatura/s, comisión, fecha y docentes.",
        "Los proyectos se informan por período y departamento, con la ficha del proyecto y las asignaciones docentes registradas, incluidas las históricas/bajas del mismo período.",
    ]:
        p = doc.add_paragraph(style=None); p.style = estilos["Normal"]; p.add_run("• " + texto)

    salida = BytesIO(); doc.save(salida); salida.seek(0)
    return salida.getvalue()


# --- entry l. 38198-38211
def _periodo_informe_v177(periodo_id):
    columnas = ["id", "nombre", "anio", "semestre", "fecha_inicio", "fecha_fin", "estado"]
    try:
        conn = get_conn()
        df = pd.read_sql(
            "SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado FROM periodos WHERE id=? LIMIT 1",
            conn, params=[int(periodo_id)]
        )
        conn.close()
        if not df.empty:
            return df.iloc[0].to_dict()
    except Exception:
        pass
    return {c: "" for c in columnas}


# --- entry l. 38219-38221
def _horas_asignacion_periodo_v177(fila_asig, fila_proyecto, periodo):
    from analisis.motor.ref.domain.proyectos import _horas_asignacion_periodo_v177 as _b05_core__horas_asignacion_periodo_v177
    return _b05_core__horas_asignacion_periodo_v177(fila_asig, fila_proyecto, periodo)


# --- entry l. 38224-38311
def _datos_proyectos_institucionales_informe_v177(periodo_id, tipo="investigacion"):
    """Todos los proyectos institucionales del período y todas sus asignaciones departamentales."""
    tipo = "extension" if str(tipo).strip().casefold().startswith("ext") else "investigacion"
    try:
        if tipo == "extension":
            catalogo = get_proyectos_extension(solo_activos=False, periodo_id=int(periodo_id))
            asignaciones = get_extension_docente(
                periodo_id=int(periodo_id), incluir_bajas=True,
                todos_departamentos=bool(USE_POSTGRESQL)
            )
        else:
            catalogo = get_proyectos_investigacion(solo_activos=False, periodo_id=int(periodo_id))
            asignaciones = get_investigacion_docente(
                periodo_id=int(periodo_id), incluir_bajas=True,
                todos_departamentos=bool(USE_POSTGRESQL)
            )
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

    catalogo = catalogo.copy() if isinstance(catalogo, pd.DataFrame) else pd.DataFrame()
    asignaciones = asignaciones.copy() if isinstance(asignaciones, pd.DataFrame) else pd.DataFrame()
    periodo = _periodo_informe_v177(periodo_id)

    # Si existiera una asignación histórica cuyo proyecto ya no estuviera en el catálogo,
    # se agrega una ficha mínima para no perderla del informe institucional.
    ids_cat = set()
    if not catalogo.empty and "id" in catalogo.columns:
        ids_cat = {int(x) for x in pd.to_numeric(catalogo["id"], errors="coerce").dropna().tolist()}
    ids_asig = set()
    if not asignaciones.empty and "proyecto_id" in asignaciones.columns:
        ids_asig = {int(x) for x in pd.to_numeric(asignaciones["proyecto_id"], errors="coerce").dropna().tolist()}
    faltantes = ids_asig - ids_cat
    extras = []
    for pid in sorted(faltantes):
        sub = asignaciones[pd.to_numeric(asignaciones.get("proyecto_id"), errors="coerce").eq(pid)].copy()
        if sub.empty:
            continue
        r = sub.iloc[0]
        extras.append({
            "id": pid,
            "nombre_proyecto": r.get("nombre_proyecto", ""),
            "codigo_proyecto": r.get("codigo_proyecto", ""),
            "instituto_proyecto": r.get("instituto_proyecto", ""),
            "anio_llamado": r.get("anio_llamado", ""),
            "fecha_inicio": r.get("fecha_inicio", periodo.get("fecha_inicio", "")),
            "fecha_fin": r.get("fecha_fin", periodo.get("fecha_fin", "")),
            "periodo_ejecucion": r.get("periodo_ejecucion", ""),
            "estado": r.get("estado_proyecto", ""),
            "situacion": r.get("estado_proyecto", ""),
            "observaciones": "",
            "departamento_creador": "",
        })
    if extras:
        catalogo = pd.concat([catalogo, pd.DataFrame(extras)], ignore_index=True, sort=False)

    # Totales institucionales por proyecto. Se informa toda asignación, aunque esté de baja,
    # y el total del período usa las fechas de carga/baja cuando están disponibles.
    if not catalogo.empty:
        hs_semanales = {}
        hs_periodo = {}
        docentes = {}
        departamentos = {}
        for _, pr in catalogo.iterrows():
            try:
                pid = int(pr.get("id"))
            except Exception:
                continue
            if asignaciones.empty or "proyecto_id" not in asignaciones.columns:
                sub = pd.DataFrame()
            else:
                sub = asignaciones[pd.to_numeric(asignaciones["proyecto_id"], errors="coerce").eq(pid)].copy()
            total_sem = float(pd.to_numeric(sub.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not sub.empty else 0.0
            total_per = 0.0
            if not sub.empty:
                for _, ar in sub.iterrows():
                    total_per += _horas_asignacion_periodo_v177(ar, pr, periodo)
            hs_semanales[pid] = round(total_sem, 2)
            hs_periodo[pid] = round(total_per, 2)
            docentes[pid] = int(sub.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).replace("", pd.NA).dropna().nunique()) if not sub.empty else 0
            departamentos[pid] = int(sub.get("departamento_asignacion", pd.Series(dtype=str)).fillna("").astype(str).str.strip().replace("", pd.NA).dropna().nunique()) if not sub.empty else 0
        catalogo["horas_semanales_totales"] = catalogo["id"].apply(lambda x: hs_semanales.get(int(x), 0.0) if pd.notna(x) else 0.0)
        catalogo["horas_totales_periodo_seleccionado"] = catalogo["id"].apply(lambda x: hs_periodo.get(int(x), 0.0) if pd.notna(x) else 0.0)
        catalogo["docentes_asignados_totales"] = catalogo["id"].apply(lambda x: docentes.get(int(x), 0) if pd.notna(x) else 0)
        catalogo["departamentos_asignados_totales"] = catalogo["id"].apply(lambda x: departamentos.get(int(x), 0) if pd.notna(x) else 0)
        orden = [c for c in ["codigo_proyecto", "nombre_proyecto"] if c in catalogo.columns]
        if orden:
            catalogo = catalogo.sort_values(orden, kind="stable")
    return catalogo.reset_index(drop=True), asignaciones.reset_index(drop=True)


# --- entry l. 38314-38379
def _indicadores_departamento_informe_v177(periodo_id):
    """Replica en el informe los KPI del bloque 'Indicadores del departamento' de Inicio."""
    metricas = dict(get_metricas_analisis_periodo(int(periodo_id)) or {})
    df_com = metricas.get("df_com", pd.DataFrame())
    df_asig = metricas.get("df_asig", pd.DataFrame())
    historico = bool(metricas.get("lectura_historica_periodo"))

    comisiones = int(len(df_com)) if isinstance(df_com, pd.DataFrame) and not df_com.empty else int(metricas.get("comisiones", 0) or 0)
    cubiertas = 0
    docentes_por_comision = 0.0
    try:
        if isinstance(df_asig, pd.DataFrame) and not df_asig.empty and "comision_id" in df_asig.columns:
            da = df_asig.copy()
            if not historico and "estado" in da.columns:
                da = da[da["estado"].fillna("Activa").astype(str).str.strip().str.casefold().eq("activa")].copy()
            elif "estado" in da.columns:
                # En históricos, una asignación finalizada dentro del mismo período sigue demostrando cobertura.
                da = da[~da["estado"].fillna("").astype(str).str.strip().str.casefold().str.contains("elimin")].copy()
            if isinstance(df_com, pd.DataFrame) and not df_com.empty and "id" in df_com.columns:
                ids = set(pd.to_numeric(df_com["id"], errors="coerce").dropna().astype(int).tolist())
                da["_cid_v177"] = pd.to_numeric(da["comision_id"], errors="coerce")
                if ids:
                    da = da[da["_cid_v177"].isin(ids)].copy()
            else:
                da["_cid_v177"] = pd.to_numeric(da["comision_id"], errors="coerce")
            da["_cuil_v177"] = da.get("cuil", pd.Series(index=da.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
            pares = da[da["_cid_v177"].notna() & da["_cuil_v177"].astype(str).ne("")][["_cid_v177", "_cuil_v177"]].drop_duplicates()
            cubiertas = int(pares["_cid_v177"].nunique())
            docentes_por_comision = round(float(len(pares)) / float(comisiones), 2) if comisiones else 0.0
    except Exception:
        pass
    cobertura = round(cubiertas / comisiones * 100.0, 1) if comisiones else 0.0

    try:
        df_prod = get_docentes_productividad_periodo(int(periodo_id))
        productividad_prom = round(float(pd.to_numeric(df_prod.get("porcentaje_uso", pd.Series(dtype=float)), errors="coerce").dropna().mean()), 2) if isinstance(df_prod, pd.DataFrame) and not df_prod.empty else 0.0
        if pd.isna(productividad_prom):
            productividad_prom = 0.0
    except Exception:
        productividad_prom = 0.0

    total_contratadas = float(metricas.get("horas_contratadas_totales", metricas.get("horas_contratadas", 0)) or 0)
    doc_contratadas = float(metricas.get("horas_contratadas_docencia", metricas.get("horas_contratadas", 0)) or 0)
    no_doc = float(metricas.get("horas_no_docentes", 0) or 0)
    utilizadas = float(metricas.get("horas_utilizadas_totales", metricas.get("horas_academicas_utilizadas", 0)) or 0)
    disponibles = float(metricas.get("horas_disponibles_totales", max(total_contratadas - utilizadas, 0)) or 0)
    exceso = float(metricas.get("horas_exceso_totales", max(utilizadas - total_contratadas, 0)) or 0)
    pct_nl = float(metricas.get("porcentaje_horas_no_lectivas", get_porcentaje_horas_no_lectivas_v148() or 0) or 0)
    return {
        "horas_contratadas": round(total_contratadas, 2),
        "horas_contratadas_docencia": round(doc_contratadas, 2),
        "horas_no_docentes": round(no_doc, 2),
        "horas_comisiones": round(float(metricas.get("horas_comisiones", 0) or 0), 2),
        "horas_no_lectivas": round(float(metricas.get("horas_no_lectivas", 0) or 0), 2),
        "porcentaje_no_lectivas": round(pct_nl, 2),
        "horas_investigacion": round(float(metricas.get("horas_investigacion", 0) or 0), 2),
        "horas_extension": round(float(metricas.get("horas_extension", 0) or 0), 2),
        "cobertura": cobertura,
        "comisiones_cubiertas": cubiertas,
        "comisiones_total": comisiones,
        "docentes_por_comision": docentes_por_comision,
        "productividad_promedio": productividad_prom,
        "horas_disponibles": round(disponibles, 2),
        "horas_exceso": round(exceso, 2),
        "metricas": metricas,
    }


# --- entry l. 38382-38458
def _comisiones_docente_informe_v177(cuil, periodo_id):
    """Comisiones del CUIL en toda la institución, incluyendo asignaciones finalizadas del período."""
    if not str(cuil or "").strip() or periodo_id is None:
        return pd.DataFrame()
    if USE_POSTGRESQL:
        try:
            inst_id = int(_pg_current_inst_id())
            nombre_p, anio_p, sem_p = _periodo_equivalente_pg(periodo_id)
            df = _pg_read_dataframe("""
                SELECT a.id AS asignacion_id, co.id AS comision_id, p.nombre AS periodo,
                       COALESCE(dep.nombre,'') AS departamento_comision,
                       m.codigo AS codigo_materia, m.asignatura,
                       COALESCE(co.materia_especifica,'') AS materia_especifica,
                       co.nombre_comision, co.turno, co.sede, co.modalidad,
                       a.rol, COALESCE(a.horas_asignadas,0) AS horas_asignadas,
                       COALESCE(a.estado,'Activa') AS estado_asignacion,
                       COALESCE(a.observaciones,'') AS observaciones
                FROM asignaciones_docentes_comision a
                JOIN comisiones co ON co.id=a.comision_id
                LEFT JOIN periodos p ON p.id=co.periodo_id
                LEFT JOIN departamentos dep ON dep.id=co.departamento_id
                LEFT JOIN materias m ON m.id=co.materia_id
                WHERE a.institucion_id=%s
                  AND regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g')=%s
                  AND (co.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))
                ORDER BY dep.nombre, m.codigo, co.nombre_comision, a.id
            """, [inst_id, _clave_cuil(cuil), int(periodo_id), nombre_p, int(anio_p), int(sem_p)])
        except Exception:
            return pd.DataFrame()
    else:
        try:
            conn = get_conn()
            df = pd.read_sql("""
                SELECT a.id AS asignacion_id, co.id AS comision_id, p.nombre AS periodo,
                       '' AS departamento_comision, m.codigo AS codigo_materia, m.asignatura,
                       COALESCE(co.materia_especifica,'') AS materia_especifica,
                       co.nombre_comision, co.turno, co.sede, co.modalidad,
                       a.rol, COALESCE(a.horas_asignadas,0) AS horas_asignadas,
                       COALESCE(a.estado,'Activa') AS estado_asignacion,
                       COALESCE(a.observaciones,'') AS observaciones
                FROM asignaciones_docentes_comision a
                JOIN comisiones co ON co.id=a.comision_id
                LEFT JOIN periodos p ON p.id=co.periodo_id
                LEFT JOIN materias m ON m.id=co.materia_id
                WHERE a.cuil=? AND co.periodo_id=?
                ORDER BY m.codigo, co.nombre_comision, a.id
            """, conn, params=[str(cuil), int(periodo_id)])
            conn.close()
        except Exception:
            return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    # Reemplaza la materia representativa por todas las materias reales cuando la comisión es multicódigo.
    for idx, r in df.iterrows():
        try:
            cid = int(r.get("comision_id"))
            links = _leer_vinculos_materias_comisiones_v118([cid], global_institucion=bool(USE_POSTGRESQL))
        except Exception:
            links = pd.DataFrame()
        if isinstance(links, pd.DataFrame) and not links.empty:
            pares = []
            for _, lr in links.iterrows():
                cod = limpiar_texto_tabla(lr.get("codigo_snapshot", ""))
                asi = limpiar_texto_tabla(lr.get("asignatura_snapshot", ""))
                clave = (normalizar_codigo_materia(cod), normalizar_clave(asi))
                if (cod or asi) and clave not in [(normalizar_codigo_materia(x[0]), normalizar_clave(x[1])) for x in pares]:
                    pares.append((cod, asi))
            if pares:
                df.at[idx, "codigo_materia"] = " / ".join([x[0] for x in pares if x[0]])
                df.at[idx, "asignatura"] = " / ".join([x[1] for x in pares if x[1]])
        if limpiar_texto_tabla(r.get("materia_especifica", "")):
            base = limpiar_texto_tabla(df.at[idx, "asignatura"])
            esp = limpiar_texto_tabla(r.get("materia_especifica", ""))
            if esp and esp not in base:
                df.at[idx, "asignatura"] = f"{base} — {esp}" if base else esp
    return df.reset_index(drop=True)


# --- entry l. 38461-38514
def _docentes_informe_v177(periodo_id, df_mov_analisis=None):
    """Personas con actividad en el departamento durante el período seleccionado."""
    mapa = {}
    def agregar(cuil, nombre="", tipo=""):
        clave = _clave_cuil(cuil)
        if not clave:
            return
        actual = mapa.setdefault(clave, {"cuil": str(cuil or ""), "docente": "", "tipo_docente": ""})
        if nombre and not actual["docente"]:
            actual["docente"] = limpiar_texto_tabla(nombre)
        if tipo and not actual["tipo_docente"]:
            actual["tipo_docente"] = limpiar_texto_tabla(tipo)

    try:
        metricas = get_metricas_analisis_periodo(int(periodo_id)) or {}
    except Exception:
        metricas = {}
    try:
        plantel = get_plantel_periodo(int(periodo_id))
    except Exception:
        plantel = pd.DataFrame()
    if isinstance(plantel, pd.DataFrame) and not plantel.empty:
        for _, r in plantel.iterrows():
            dper = pd.to_numeric(r.get("designaciones_del_periodo", 0), errors="coerce")
            hper = pd.to_numeric(r.get("horas_registradas_periodo", 0), errors="coerce")
            est = normalizar_clave(r.get("estado_operativo_periodo", ""))
            tipo = limpiar_texto_tabla(r.get("tipo_docente", ""))
            incluir = (pd.notna(dper) and float(dper or 0) > 0) or (pd.notna(hper) and float(hper or 0) > 0) or ("ACTIVO EN EL PERIODO" in est) or (normalizar_clave(tipo) == normalizar_clave("Prestado"))
            if incluir:
                agregar(r.get("cuil"), r.get("nombre_completo", ""), tipo)

    for clave_df in ["df_desig_activas_totales", "df_asig"]:
        dfx = metricas.get(clave_df, pd.DataFrame())
        if isinstance(dfx, pd.DataFrame) and not dfx.empty:
            for _, r in dfx.iterrows():
                agregar(r.get("cuil"), r.get("nombre_completo", r.get("docente", "")), r.get("tipo_docente", ""))

    # Proyectos locales también integran el universo del departamento aunque la persona no tenga comisión.
    for getter in [get_investigacion_docente, get_extension_docente]:
        try:
            dfx = getter(periodo_id=int(periodo_id), incluir_bajas=True, todos_departamentos=False)
        except Exception:
            dfx = pd.DataFrame()
        if isinstance(dfx, pd.DataFrame) and not dfx.empty:
            for _, r in dfx.iterrows():
                agregar(r.get("cuil"), r.get("docente", ""), "")

    if isinstance(df_mov_analisis, pd.DataFrame) and not df_mov_analisis.empty:
        for _, r in df_mov_analisis.iterrows():
            agregar(r.get("cuil"), r.get("docente", ""), "")

    registros = list(mapa.values())
    registros.sort(key=lambda r: (normalizar_clave(r.get("docente", "")), _clave_cuil(r.get("cuil", ""))))
    return registros


# --- entry l. 38517-38534
def _productividad_docente_informe_v177(cuil, periodo_id):
    try:
        if USE_POSTGRESQL:
            datos = dict(get_productividad_docente_institucional_v149(cuil, int(periodo_id)) or {})
        else:
            datos = dict(get_productividad_docente(cuil, int(periodo_id)) or {})
    except Exception:
        datos = {}
    return {
        "horas_contratadas": round(float(datos.get("horas_contratadas", 0) or 0), 2),
        "horas_en_comisiones": round(float(datos.get("horas_en_comisiones", 0) or 0), 2),
        "horas_no_lectivas": round(float(datos.get("horas_no_lectivas", 0) or 0), 2),
        "horas_en_investigacion": round(float(datos.get("horas_en_investigacion", 0) or 0), 2),
        "horas_en_extension": round(float(datos.get("horas_en_extension", 0) or 0), 2),
        "horas_utilizadas": round(float(datos.get("horas_utilizadas", 0) or 0), 2),
        "horas_disponibles": round(float(datos.get("horas_disponibles", 0) or 0), 2),
        "porcentaje": round(float(datos.get("porcentaje", 0) or 0), 2),
    }


# --- entry l. 38537-38934
def generar_informe_movimiento_docente_word_v175(periodo_nombre, departamento, df_mov_analisis, periodo_id=None):
    """v177: informe integral del departamento y del plantel, con proyectos institucionales."""
    Document = _obtener_document_python_docx()
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(1.55); sec.bottom_margin = Cm(1.55)
    sec.left_margin = Cm(1.55); sec.right_margin = Cm(1.55)
    estilos = doc.styles
    estilos["Normal"].font.name = "Arial"; estilos["Normal"].font.size = Pt(8.7)
    for nombre in ["Title", "Heading 1", "Heading 2", "Heading 3"]:
        try: estilos[nombre].font.name = "Arial"
        except Exception: pass
    estilos["Title"].font.size = Pt(18); estilos["Title"].font.bold = True
    estilos["Heading 1"].font.size = Pt(13); estilos["Heading 1"].font.bold = True
    estilos["Heading 2"].font.size = Pt(10.8); estilos["Heading 2"].font.bold = True
    try:
        estilos["Heading 3"].font.size = Pt(9.2); estilos["Heading 3"].font.bold = True
    except Exception: pass

    def sombrear(celda, fill):
        tcPr = celda._tc.get_or_add_tcPr(); shd = tcPr.find(qn("w:shd"))
        if shd is None:
            shd = OxmlElement("w:shd"); tcPr.append(shd)
        shd.set(qn("w:fill"), fill)

    def texto_celda(celda, texto, bold=False, color=None, tam=7.5):
        celda.text = ""; p = celda.paragraphs[0]
        r = p.add_run(str(texto if texto is not None else "")); r.bold = bold
        r.font.name = "Arial"; r.font.size = Pt(tam)
        if color: r.font.color.rgb = RGBColor.from_string(color)
        celda.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    def fecha_txt(valor):
        if valor is None or (isinstance(valor, float) and pd.isna(valor)): return ""
        try:
            dt = pd.to_datetime(valor, errors="coerce")
            if pd.notna(dt): return dt.strftime("%d/%m/%Y")
        except Exception: pass
        return str(valor or "")

    def tabla_kpis(items, columnas=4, color="1F4E78"):
        items = list(items)
        for ini in range(0, len(items), columnas):
            grupo = items[ini:ini+columnas]
            t = doc.add_table(rows=2, cols=len(grupo)); t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.style = "Table Grid"
            for j, (rot, val) in enumerate(grupo):
                texto_celda(t.cell(0, j), rot, bold=True, color="FFFFFF", tam=7.1); sombrear(t.cell(0, j), color)
                texto_celda(t.cell(1, j), val, bold=True, tam=9.0); sombrear(t.cell(1, j), "F3F6F9")
            doc.add_paragraph().paragraph_format.space_after = Pt(1)

    title = doc.add_paragraph(style="Title"); title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("INFORME DE MOVIMIENTO Y GESTIÓN DOCENTE")
    psub = doc.add_paragraph(); psub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = psub.add_run(f"{departamento} · Período {periodo_nombre}"); r.bold = True; r.font.name = "Arial"; r.font.size = Pt(11)
    pfecha = doc.add_paragraph(); pfecha.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = pfecha.add_run(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"); r.font.name = "Arial"; r.font.size = Pt(8); r.font.color.rgb = RGBColor(100,100,100)

    df_total = df_mov_analisis.copy() if isinstance(df_mov_analisis, pd.DataFrame) else pd.DataFrame()
    df_filtrado = _filtrar_movimientos_informe_v176(df_total)
    if not df_filtrado.empty:
        tipo_norm = df_filtrado.get("tipo_movimiento", pd.Series("", index=df_filtrado.index)).fillna("").astype(str).map(normalizar_clave)
        cat_norm = df_filtrado.get("categoria_movimiento", pd.Series("", index=df_filtrado.index)).fillna("").astype(str).map(normalizar_clave)
        es_apertura = tipo_norm.eq(normalizar_clave("Apertura de comisión")) | cat_norm.eq(normalizar_clave("Apertura de comisión"))
        df = df_filtrado[~es_apertura].copy()
    else:
        df = df_filtrado.copy()

    periodo = _periodo_informe_v177(periodo_id) if periodo_id is not None else {}
    indicadores = _indicadores_departamento_informe_v177(periodo_id) if periodo_id is not None else {}
    df_comisiones = _datos_comisiones_informe_v176(periodo_id) if periodo_id is not None else pd.DataFrame()
    df_proy_inv, df_asig_inv = _datos_proyectos_institucionales_informe_v177(periodo_id, "investigacion") if periodo_id is not None else (pd.DataFrame(), pd.DataFrame())
    df_proy_ext, df_asig_ext = _datos_proyectos_institucionales_informe_v177(periodo_id, "extension") if periodo_id is not None else (pd.DataFrame(), pd.DataFrame())
    docentes_periodo = _docentes_informe_v177(periodo_id, df) if periodo_id is not None else []
    try:
        plantel_resumen_v177 = get_plantel_periodo(int(periodo_id)) if periodo_id is not None else pd.DataFrame()
    except Exception:
        plantel_resumen_v177 = pd.DataFrame()

    balance = balance_horas_movimiento_docente(df) if not df.empty else {
        "horas_altas":0, "horas_bajas":0, "horas_aumentos":0, "horas_disminuciones":0, "saldo_neto":0
    }
    total_mov = int(len(df)); docentes_afectados = int(df.get("cuil", pd.Series(dtype=str)).replace("", pd.NA).dropna().astype(str).nunique()) if not df.empty else 0

    # 1. Resumen ejecutivo: se conserva la lógica solicitada, ampliada con contexto departamental/institucional.
    doc.add_heading("1. Resumen ejecutivo", level=1)
    p = doc.add_paragraph()
    p.add_run(
        f"Durante el período {periodo_nombre} se registraron {total_mov} movimientos administrativos relevantes de designaciones, "
        f"con {docentes_afectados} persona/s afectada/s. El saldo neto de horas derivado de altas, bajas y cambios de dedicación "
        f"fue de {float(balance.get('saldo_neto',0) or 0):+g} horas. El plantel analizado contiene {len(docentes_periodo)} persona/s con "
        f"actividad departamental registrada. En la institución, para el mismo período, se informan {len(df_proy_inv)} proyecto/s de "
        f"investigación y {len(df_proy_ext)} proyecto/s de extensión."
    )
    categorias_clave = [
        ("Altas de designaciones","Altas"),("Bajas de designaciones","Bajas"),
        ("Aumentos de dedicación","Aumentos"),("Disminuciones de dedicación","Disminuciones"),
        ("Cambios de cargo","Cambios de cargo"),("Pase a Ad Honorem","Pase a Ad Honorem"),("Pase a Rentado","Pase a Rentado")
    ]
    tabla_kpis([
        (rot, int((df.get("categoria_movimiento", pd.Series(dtype=str)) == cat).sum()) if not df.empty else 0)
        for cat, rot in categorias_clave
    ], columnas=4, color="1F4E78")

    # 2. Indicadores del departamento: mismos KPI conceptuales que Inicio.
    doc.add_heading("2. Indicadores del departamento", level=1)
    tabla_kpis([
        ("Horas de designación · total", f"{indicadores.get('horas_contratadas',0):g} hs"),
        ("Horas frente a comisión", f"{indicadores.get('horas_comisiones',0):g} hs"),
        ("Horas no lectivas", f"{indicadores.get('horas_no_lectivas',0):g} hs"),
        ("Horas investigación + extensión", f"{indicadores.get('horas_investigacion',0)+indicadores.get('horas_extension',0):g} hs"),
        ("Horas funciones no docentes", f"{indicadores.get('horas_no_docentes',0):g} hs"),
        ("Cobertura de comisiones", f"{indicadores.get('cobertura',0):g} %"),
        ("Comisiones cubiertas", f"{indicadores.get('comisiones_cubiertas',0)} / {indicadores.get('comisiones_total',0)}"),
        ("Docentes por comisión", f"{indicadores.get('docentes_por_comision',0):g}"),
        ("Productividad promedio", f"{indicadores.get('productividad_promedio',0):g} %"),
        ("Exceso global" if indicadores.get('horas_exceso',0)>0 else "Horas todavía disponibles", f"{indicadores.get('horas_exceso',0) if indicadores.get('horas_exceso',0)>0 else indicadores.get('horas_disponibles',0):g} hs"),
    ], columnas=5, color="4472C4")
    p = doc.add_paragraph()
    p.add_run("Composición de las horas de designación: ").bold = True
    p.add_run(f"docencia {indicadores.get('horas_contratadas_docencia',0):g} hs · funciones no docentes {indicadores.get('horas_no_docentes',0):g} hs. ")
    p.add_run(f"Parámetro base de horas no lectivas: {indicadores.get('porcentaje_no_lectivas',0):g} %.")

    # 3. Balance: mantiene el formato anterior.
    doc.add_heading("3. Balance de horas", level=1)
    tb = doc.add_table(rows=2, cols=5); tb.alignment = WD_TABLE_ALIGNMENT.CENTER; tb.style = "Table Grid"
    balance_items = [
        ("Altas",balance.get("horas_altas",0)),("Bajas",balance.get("horas_bajas",0)),
        ("Aumentos",balance.get("horas_aumentos",0)),("Disminuciones",balance.get("horas_disminuciones",0)),
        ("Saldo neto",balance.get("saldo_neto",0)),
    ]
    for j,(rot,val) in enumerate(balance_items):
        texto_celda(tb.cell(0,j),rot,bold=True,color="FFFFFF"); sombrear(tb.cell(0,j),"2F75B5")
        texto_celda(tb.cell(1,j),f"{float(val or 0):+g} hs",bold=True,tam=9.5)
    doc.add_paragraph("El saldo horario considera altas, bajas, aumentos y disminuciones de dedicación. Los cambios de cargo y los pases entre Ad Honorem y Rentado se informan por separado.")

    # 4. Resumen individual de cada integrante con actividad en el departamento.
    doc.add_page_break(); doc.add_heading("4. Resumen individual del plantel docente", level=1)
    doc.add_paragraph("Se presenta una ficha por persona con actividad registrada en el departamento durante el período, incluyendo designaciones institucionales, proyectos, comisiones y productividad.")

    for nro, reg in enumerate(docentes_periodo, start=1):
        cuil = str(reg.get("cuil") or "").strip(); nombre_fallback = limpiar_texto_tabla(reg.get("docente", "")) or cuil
        try:
            df_docente, _, _ = get_resumen_docente(cuil)
        except Exception:
            df_docente = pd.DataFrame()
        fila_doc = df_docente.iloc[0].to_dict() if isinstance(df_docente, pd.DataFrame) and not df_docente.empty else {}
        nombre = limpiar_texto_tabla(fila_doc.get("nombre_completo", "")) or nombre_fallback or f"Docente {nro}"
        doc.add_heading(f"{nro}. {nombre}", level=2)

        # Situación y datos generales.
        situacion_periodo = "Con actividad registrada en el período"
        try:
            if isinstance(plantel_resumen_v177, pd.DataFrame) and not plantel_resumen_v177.empty:
                subp = plantel_resumen_v177[plantel_resumen_v177.get("cuil", pd.Series(index=plantel_resumen_v177.index,dtype=str)).fillna("").astype(str).map(_clave_cuil).eq(_clave_cuil(cuil))]
                if not subp.empty:
                    situacion_periodo = limpiar_texto_tabla(subp.iloc[0].get("estado_operativo_periodo", "")) or situacion_periodo
                    if not reg.get("tipo_docente"):
                        reg["tipo_docente"] = limpiar_texto_tabla(subp.iloc[0].get("tipo_docente", ""))
        except Exception:
            pass

        datos_generales = [
            ("CUIL", limpiar_texto_tabla(fila_doc.get("cuil", "")) or cuil),
            ("Legajo", limpiar_texto_tabla(fila_doc.get("legajo", "")) or "—"),
            ("Tipo en el departamento", limpiar_texto_tabla(reg.get("tipo_docente", "")) or "—"),
            ("Situación en el período", situacion_periodo),
            ("Título de grado", limpiar_texto_tabla(fila_doc.get("titulo", "")) or "—"),
            ("Título de posgrado", limpiar_texto_tabla(fila_doc.get("titulo_posgrado", "")) or "—"),
            ("Mail", limpiar_texto_tabla(fila_doc.get("email", "")) or "—"),
            ("Teléfono", limpiar_texto_tabla(fila_doc.get("telefono", "")) or "—"),
            ("Inicio histórico", fecha_txt(fila_doc.get("fecha_inicio_historica", "")) or "—"),
            ("Última alta", fecha_txt(fila_doc.get("ultima_fecha_alta", "")) or "—"),
        ]
        tg = doc.add_table(rows=0, cols=4); tg.style = "Table Grid"; tg.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i in range(0, len(datos_generales), 2):
            cells = tg.add_row().cells
            for j, (rot, val) in enumerate(datos_generales[i:i+2]):
                texto_celda(cells[j*2], rot, bold=True, color="FFFFFF", tam=7.0); sombrear(cells[j*2], "7F8C8D")
                texto_celda(cells[j*2+1], val, tam=7.2)
        obs = limpiar_texto_tabla(fila_doc.get("observaciones", ""))
        if obs:
            p = doc.add_paragraph(); p.add_run("Observaciones: ").bold = True; p.add_run(obs)

        # Designaciones institucionales.
        doc.add_heading("Designaciones del período", level=3)
        try:
            if USE_POSTGRESQL:
                dd = get_designaciones_docente_todos_departamentos_pg(cuil, int(periodo_id))
            else:
                dd = get_designaciones(int(periodo_id))
                if not dd.empty:
                    dd = dd[dd.get("cuil", pd.Series(index=dd.index,dtype=str)).fillna("").astype(str).map(_clave_cuil).eq(_clave_cuil(cuil))].copy()
        except Exception:
            dd = pd.DataFrame()
        if dd is None or dd.empty:
            doc.add_paragraph("Sin designaciones registradas para el período.")
        else:
            for nd, (_, dr) in enumerate(dd.iterrows(), start=1):
                depd = limpiar_texto_tabla(dr.get("departamento", "")) or departamento
                cargo = limpiar_texto_tabla(dr.get("cargo", "")) or "—"
                p = doc.add_paragraph(); p.add_run(f"Designación {nd} — {depd} — {cargo}").bold = True
                funcion_val = dr.get("Función", dr.get("funcion_no_docente", ""))
                if isinstance(funcion_val, (int,float,bool)):
                    funcion_txt = "Funciones no docentes" if _es_funcion_no_docente_v162(funcion_val) else "Docencia"
                else:
                    funcion_txt = limpiar_texto_tabla(funcion_val) or "Docencia"
                ah = limpiar_texto_tabla(dr.get("ad_honorem", dr.get("Ad Honórem", "")))
                condicion = "Ad Honorem" if _es_ad_honorem_v162(ah) else "Rentada"
                detalle = (
                    f"Dedicación: {limpiar_texto_tabla(dr.get('dedicacion','')) or '—'} · "
                    f"Horas: {float(pd.to_numeric(dr.get('horas',0), errors='coerce') or 0):g} · "
                    f"Tipo: {limpiar_texto_tabla(dr.get('tipo_designacion','')) or '—'} · {condicion} · "
                    f"Estado: {limpiar_texto_tabla(dr.get('estado','')) or '—'} · Función: {funcion_txt}."
                )
                doc.add_paragraph(detalle)
                reso = limpiar_texto_tabla(dr.get("N° resolución", dr.get("numero_resolucion", ""))) or "—"
                doc.add_paragraph(
                    f"Vigencia: {fecha_txt(dr.get('fecha_desde','')) or '—'} a {fecha_txt(dr.get('fecha_hasta','')) or '—'} · Resolución: {reso}."
                )
                txt_fn = limpiar_texto_tabla(dr.get("Funciones no docentes", dr.get("texto_funcion_no_docente", "")))
                if txt_fn:
                    p = doc.add_paragraph(); p.add_run("Funciones no docentes: ").bold = True; p.add_run(txt_fn)
                obs_d = limpiar_texto_tabla(dr.get("observaciones", ""))
                if obs_d:
                    p = doc.add_paragraph(); p.add_run("Observaciones de la designación: ").bold = True; p.add_run(obs_d)

        # Investigación individual institucional.
        doc.add_heading("Investigación", level=3)
        try:
            if isinstance(df_asig_inv, pd.DataFrame) and not df_asig_inv.empty:
                di = df_asig_inv[df_asig_inv.get("cuil", pd.Series(index=df_asig_inv.index,dtype=str)).fillna("").astype(str).map(_clave_cuil).eq(_clave_cuil(cuil))].copy()
            else:
                di = pd.DataFrame()
        except Exception:
            di = pd.DataFrame()
        if di is None or di.empty:
            doc.add_paragraph("Sin proyectos de investigación asignados en el período.")
        else:
            ti = doc.add_table(rows=1, cols=6); ti.style = "Table Grid"; ti.alignment = WD_TABLE_ALIGNMENT.CENTER
            for j,h in enumerate(["Código","Proyecto","Departamento","Rol","Hs/sem","Estado"]):
                texto_celda(ti.cell(0,j),h,bold=True,color="FFFFFF",tam=6.8); sombrear(ti.cell(0,j),"70AD47")
            for _, ar in di.iterrows():
                vals=[ar.get("codigo_proyecto",""),ar.get("nombre_proyecto",""),ar.get("departamento_asignacion",""),ar.get("rol",""),f"{float(pd.to_numeric(ar.get('horas_asignadas',0),errors='coerce') or 0):g}",ar.get("estado_asignacion","")]
                cells=ti.add_row().cells
                for j,v in enumerate(vals): texto_celda(cells[j],v,tam=6.7)

        # Extensión individual institucional.
        doc.add_heading("Extensión", level=3)
        try:
            if isinstance(df_asig_ext, pd.DataFrame) and not df_asig_ext.empty:
                de = df_asig_ext[df_asig_ext.get("cuil", pd.Series(index=df_asig_ext.index,dtype=str)).fillna("").astype(str).map(_clave_cuil).eq(_clave_cuil(cuil))].copy()
            else:
                de = pd.DataFrame()
        except Exception:
            de = pd.DataFrame()
        if de is None or de.empty:
            doc.add_paragraph("Sin proyectos de extensión asignados en el período.")
        else:
            te = doc.add_table(rows=1, cols=6); te.style = "Table Grid"; te.alignment = WD_TABLE_ALIGNMENT.CENTER
            for j,h in enumerate(["Código","Proyecto","Departamento","Rol","Hs/sem","Estado"]):
                texto_celda(te.cell(0,j),h,bold=True,color="FFFFFF",tam=6.8); sombrear(te.cell(0,j),"ED7D31")
            for _, ar in de.iterrows():
                vals=[ar.get("codigo_proyecto",""),ar.get("nombre_proyecto",""),ar.get("departamento_asignacion",""),ar.get("rol",""),f"{float(pd.to_numeric(ar.get('horas_asignadas',0),errors='coerce') or 0):g}",ar.get("estado_asignacion","")]
                cells=te.add_row().cells
                for j,v in enumerate(vals): texto_celda(cells[j],v,tam=6.7)

        # Comisiones institucionales del período, incluso si la asignación fue finalizada dentro del semestre.
        doc.add_heading("Comisiones", level=3)
        dc = _comisiones_docente_informe_v177(cuil, int(periodo_id))
        if dc is None or dc.empty:
            doc.add_paragraph("Sin comisiones asignadas en el período.")
        else:
            tc = doc.add_table(rows=1, cols=7); tc.style = "Table Grid"; tc.alignment = WD_TABLE_ALIGNMENT.CENTER
            for j,h in enumerate(["Departamento","Código/s","Asignatura/s","Comisión","Rol","Hs","Estado"]):
                texto_celda(tc.cell(0,j),h,bold=True,color="FFFFFF",tam=6.4); sombrear(tc.cell(0,j),"5B9BD5")
            for _, cr in dc.iterrows():
                vals=[cr.get("departamento_comision",""),cr.get("codigo_materia",""),cr.get("asignatura",""),cr.get("nombre_comision",""),cr.get("rol",""),f"{float(pd.to_numeric(cr.get('horas_asignadas',0),errors='coerce') or 0):g}",cr.get("estado_asignacion","")]
                cells=tc.add_row().cells
                for j,v in enumerate(vals): texto_celda(cells[j],v,tam=6.2)

        # Productividad individual, igual en conceptos a Resumen docente.
        doc.add_heading("Productividad", level=3)
        prod = _productividad_docente_informe_v177(cuil, int(periodo_id))
        tabla_kpis([
            ("Hs contratadas", f"{prod['horas_contratadas']:g}"),
            ("Hs frente a comisión", f"{prod['horas_en_comisiones']:g}"),
            ("Hs no lectivas", f"{prod['horas_no_lectivas']:g}"),
            ("Productividad", f"{prod['porcentaje']:g} %"),
            ("Hs investigación", f"{prod['horas_en_investigacion']:g}"),
            ("Hs extensión", f"{prod['horas_en_extension']:g}"),
            ("Hs utilizadas", f"{prod['horas_utilizadas']:g}"),
            ("Disponibles" if prod['horas_disponibles']>=0 else "Exceso", f"{abs(prod['horas_disponibles']):g}"),
        ], columnas=4, color="8064A2")
        if nro < len(docentes_periodo):
            doc.add_paragraph("—" * 28)

    # 5. Detalle de movimientos relevantes. No se agrega Resumen por tipo de movimiento.
    doc.add_page_break(); doc.add_heading("5. Detalle de movimientos relevantes", level=1)
    if df.empty:
        doc.add_paragraph("Sin movimientos administrativos relevantes para detallar.")
    else:
        orden_cat = [x[0] for x in categorias_clave] + [x for x in df["categoria_movimiento"].dropna().astype(str).unique().tolist() if x not in [c[0] for c in categorias_clave]]
        for categoria in orden_cat:
            dcat = df[df["categoria_movimiento"].astype(str) == str(categoria)].copy()
            if dcat.empty: continue
            doc.add_heading(f"{categoria} ({len(dcat)})", level=2)
            td = doc.add_table(rows=1, cols=6); td.style="Table Grid"; td.alignment=WD_TABLE_ALIGNMENT.CENTER
            for j,h in enumerate(["Fecha","Docente","CUIL","Detalle","Observaciones","Δ horas"]):
                texto_celda(td.cell(0,j),h,bold=True,color="FFFFFF",tam=7.0); sombrear(td.cell(0,j),"5B9BD5")
            for _, rr in dcat.sort_values(["fecha","docente"],kind="stable").iterrows():
                vals=[rr.get("fecha",""),rr.get("docente",""),rr.get("cuil",""),rr.get("detalle",""),rr.get("observaciones",""),f"{float(rr.get('variacion_horas',0) or 0):+g}"]
                cells=td.add_row().cells
                for j,v in enumerate(vals): texto_celda(cells[j],v,tam=6.9)

    # 6. Apertura de comisiones, con los datos reconstruidos desde la comisión real.
    doc.add_heading("6. Apertura de comisiones", level=1)
    doc.add_paragraph("Se detallan las comisiones del período con fecha de apertura, materias/códigos y equipo docente registrado.")
    if df_comisiones is None or df_comisiones.empty:
        doc.add_paragraph("No hay comisiones registradas para el período seleccionado.")
    else:
        tc = doc.add_table(rows=1, cols=6); tc.style="Table Grid"; tc.alignment=WD_TABLE_ALIGNMENT.CENTER
        for j,h in enumerate(["Fecha","Comisión","Código/s","Asignatura/s","Docentes","Horario/s"]):
            texto_celda(tc.cell(0,j),h,bold=True,color="FFFFFF",tam=6.8); sombrear(tc.cell(0,j),"4472C4")
        for _, rr in df_comisiones.iterrows():
            vals=[fecha_txt(rr.get("fecha","")),rr.get("comision",""),rr.get("codigos",""),rr.get("asignaturas",""),rr.get("docentes",""),rr.get("horarios","")]
            cells=tc.add_row().cells
            for j,v in enumerate(vals): texto_celda(cells[j],v,tam=6.5)

    def agregar_proyectos_institucionales(titulo, catalogo, asignaciones, numero, color):
        doc.add_heading(f"{numero}. {titulo}", level=1)
        doc.add_paragraph("Alcance institucional: se muestran todos los proyectos vigentes/superpuestos con el período y todas las asignaciones registradas en los distintos departamentos.")
        if catalogo is None or catalogo.empty:
            doc.add_paragraph("No hay proyectos institucionales para el período seleccionado.")
            return
        for _, pr in catalogo.iterrows():
            pid = pr.get("id")
            codigo = limpiar_texto_tabla(pr.get("codigo_proyecto", "")); nombre = limpiar_texto_tabla(pr.get("nombre_proyecto", "")) or "Proyecto sin nombre"
            doc.add_heading(f"{codigo} — {nombre}" if codigo else nombre, level=2)
            meta=[]
            instituto=limpiar_texto_tabla(pr.get("instituto_proyecto","")); anio=limpiar_texto_tabla(pr.get("anio_llamado",""))
            if instituto: meta.append(f"Instituto/área: {instituto}")
            if anio: meta.append(f"Año de llamado: {anio}")
            fi=fecha_txt(pr.get("fecha_inicio","")); ff=fecha_txt(pr.get("fecha_fin",""))
            if fi or ff: meta.append(f"Vigencia: {fi or '—'} a {ff or '—'}")
            estado=limpiar_texto_tabla(pr.get("estado",pr.get("situacion","")))
            if estado: meta.append(f"Estado: {estado}")
            depc=limpiar_texto_tabla(pr.get("departamento_creador",""))
            if depc: meta.append(f"Departamento creador: {depc}")
            if meta: doc.add_paragraph(" · ".join(meta))
            tabla_kpis([
                ("Hs semanales totales", f"{float(pr.get('horas_semanales_totales',0) or 0):g} hs"),
                ("Hs totales del período seleccionado", f"{float(pr.get('horas_totales_periodo_seleccionado',0) or 0):g} hs"),
                ("Docentes asignados", int(pr.get("docentes_asignados_totales",0) or 0)),
                ("Departamentos con asignaciones", int(pr.get("departamentos_asignados_totales",0) or 0)),
            ], columnas=4, color=color)
            obs=limpiar_texto_tabla(pr.get("observaciones",""))
            if obs:
                po=doc.add_paragraph(); po.add_run("Observaciones: ").bold=True; po.add_run(obs)
            if asignaciones is None or asignaciones.empty or "proyecto_id" not in asignaciones.columns:
                sub=pd.DataFrame()
            else:
                try: sub=asignaciones[pd.to_numeric(asignaciones["proyecto_id"],errors="coerce").eq(int(pid))].copy()
                except Exception: sub=pd.DataFrame()
            if sub.empty:
                doc.add_paragraph("Sin docentes asignados durante el período seleccionado.")
            else:
                ta=doc.add_table(rows=1,cols=6); ta.style="Table Grid"; ta.alignment=WD_TABLE_ALIGNMENT.CENTER
                for j,h in enumerate(["Departamento","Docente","CUIL","Rol","Hs/sem","Estado"]):
                    texto_celda(ta.cell(0,j),h,bold=True,color="FFFFFF",tam=6.7); sombrear(ta.cell(0,j),color)
                orden=[c for c in ["departamento_asignacion","docente","rol"] if c in sub.columns]
                if orden: sub=sub.sort_values(orden,kind="stable")
                for _, ar in sub.iterrows():
                    vals=[ar.get("departamento_asignacion",""),ar.get("docente",""),ar.get("cuil",""),ar.get("rol",""),f"{float(pd.to_numeric(ar.get('horas_asignadas',0),errors='coerce') or 0):g}",ar.get("estado_asignacion","")]
                    cells=ta.add_row().cells
                    for j,v in enumerate(vals): texto_celda(cells[j],v,tam=6.5)

    agregar_proyectos_institucionales("Proyectos de investigación y docentes asignados", df_proy_inv, df_asig_inv, 7, "70AD47")
    agregar_proyectos_institucionales("Proyectos de extensión y docentes asignados", df_proy_ext, df_asig_ext, 8, "ED7D31")

    doc.add_heading("9. Criterio de lectura", level=1)
    criterios = [
        "La unidad principal de movimiento de dotación es la designación, no el alta o baja de la persona.",
        "El detalle de movimientos omite eventos técnicos o administrativos expresamente excluidos para mantener una lectura ejecutiva.",
        "El resumen individual reúne la actividad del docente en el período y, cuando corresponde, consolida designaciones, investigación, extensión y comisiones de toda la institución.",
        "Las aperturas de comisión se reconstruyen desde las comisiones reales del período para informar código/s, asignatura/s, comisión, fecha y docentes.",
        "Investigación y Extensión se informan con alcance institucional: todos los proyectos y todas las asignaciones de todos los departamentos para el período equivalente.",
        "Las horas totales de cada proyecto en el período seleccionado se estiman a partir de las horas semanales de cada asignación y las fechas de vigencia disponibles dentro del período académico.",
    ]
    for t in criterios:
        p=doc.add_paragraph(); p.style=estilos["Normal"]; p.add_run("• "+t)

    salida=BytesIO(); doc.save(salida); salida.seek(0); return salida.getvalue()


# --- entry l. 38943
_datos_proyectos_institucionales_informe_pre_v178 = _datos_proyectos_institucionales_informe_v177


# --- entry l. 38946-38999
def _datos_proyectos_institucionales_informe_v177(periodo_id, tipo="investigacion"):
    """v178: horas totales = horas semanales institucionales × semanas completas del proyecto.

    La suma semanal toma las asignaciones que el informe ya consolida para el período
    seleccionado en todos los departamentos. Luego se proyecta sobre TODA la vigencia
    del proyecto (fecha_inicio → fecha_fin), usando la misma lógica que ya utiliza la
    pantalla de Proyectos vigentes.
    """
    catalogo, asignaciones = _datos_proyectos_institucionales_informe_pre_v178(periodo_id, tipo)
    catalogo = catalogo.copy() if isinstance(catalogo, pd.DataFrame) else pd.DataFrame()
    asignaciones = asignaciones.copy() if isinstance(asignaciones, pd.DataFrame) else pd.DataFrame()

    if catalogo.empty:
        return catalogo, asignaciones

    for idx, pr in catalogo.iterrows():
        try:
            pid = int(pr.get("id"))
        except Exception:
            continue

        if asignaciones.empty or "proyecto_id" not in asignaciones.columns:
            sub = pd.DataFrame()
        else:
            sub = asignaciones[
                pd.to_numeric(asignaciones["proyecto_id"], errors="coerce").eq(pid)
            ].copy()

        # Todas las asignaciones institucionales mostradas en el informe aportan
        # a la dedicación semanal total del proyecto.
        total_semanal = (
            float(
                pd.to_numeric(
                    sub.get("horas_asignadas", pd.Series(dtype=float)),
                    errors="coerce",
                ).fillna(0).sum()
            )
            if not sub.empty else 0.0
        )

        semanas = _semanas_ejecucion_proyecto_v162(
            pr.get("fecha_inicio"), pr.get("fecha_fin")
        )
        total_ejecucion = _horas_totales_ejecucion_proyecto_v162(
            total_semanal, pr.get("fecha_inicio"), pr.get("fecha_fin")
        )

        catalogo.at[idx, "horas_semanales_totales"] = round(total_semanal, 2)
        # Se conserva el nombre técnico previo para no romper el generador,
        # pero desde v178 su significado es TOTAL DE TODA LA EJECUCIÓN.
        catalogo.at[idx, "horas_totales_periodo_seleccionado"] = round(total_ejecucion, 2)
        catalogo.at[idx, "semanas_ejecucion_totales"] = round(float(semanas or 0), 2)

    return catalogo.reset_index(drop=True), asignaciones.reset_index(drop=True)


# --- entry l. 39002
_generar_informe_movimiento_docente_word_pre_v178 = generar_informe_movimiento_docente_word_v175


# --- entry l. 39005-39028
def _inscriptos_apertura_comisiones_v178(periodo_id):
    """Total del conjunto de asignaturas de cada comisión, en el orden del informe."""
    if periodo_id is None:
        return []
    try:
        df_com = get_comisiones(periodo_id=int(periodo_id), solo_activas=False)
    except Exception:
        df_com = pd.DataFrame()
    if df_com is None or df_com.empty:
        return []

    df_com = _ordenar_comisiones_informe_por_asignatura_v201(df_com)

    salida = []
    for _, co in df_com.iterrows():
        try:
            cid = int(co.get("id"))
            ins = get_inscriptos_comision(cid) or {}
            cantidad_num = pd.to_numeric(ins.get("cantidad", 0), errors="coerce")
            cantidad = int(cantidad_num) if not pd.isna(cantidad_num) else 0
        except Exception:
            cantidad = 0
        salida.append(cantidad)
    return salida


# --- entry l. 39031-39033
def _color_productividad_word_v178(valor):
    from analisis.motor.ref.domain.informes import _color_productividad_word_v178 as _b05_core__color_productividad_word_v178
    return _b05_core__color_productividad_word_v178(valor)


# --- entry l. 39036-39198
def generar_informe_movimiento_docente_word_v175(periodo_nombre, departamento, df_mov_analisis, periodo_id=None):
    """v178: conserva el formato v177 y aplica los cambios solicitados al Word final."""
    data = _generar_informe_movimiento_docente_word_pre_v178(
        periodo_nombre, departamento, df_mov_analisis, periodo_id=periodo_id
    )

    Document = _obtener_document_python_docx()
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document(BytesIO(data))

    def sombrear(celda, fill):
        tcPr = celda._tc.get_or_add_tcPr()
        shd = tcPr.find(qn("w:shd"))
        if shd is None:
            shd = OxmlElement("w:shd")
            tcPr.append(shd)
        shd.set(qn("w:fill"), str(fill).replace("#", "").upper())

    def poner_texto_celda(celda, texto, bold=False, color=None, tam=6.4):
        celda.text = ""
        p = celda.paragraphs[0]
        r = p.add_run(str(texto if texto is not None else ""))
        r.bold = bool(bold)
        r.font.name = "Arial"
        r.font.size = Pt(tam)
        if color:
            r.font.color.rgb = RGBColor.from_string(str(color).replace("#", "").upper())

    # 1) Apertura de comisiones: muestra el total de alumnos del conjunto de asignaturas/comisiones.
    inscriptos = _inscriptos_apertura_comisiones_v178(periodo_id)
    tabla_apertura = None
    for tabla in doc.tables:
        if not tabla.rows:
            continue
        cab = [c.text.strip() for c in tabla.rows[0].cells]
        if cab[:6] == ["Fecha", "Comisión", "Código/s", "Asignatura/s", "Docentes", "Horario/s"]:
            tabla_apertura = tabla
            break

    if tabla_apertura is not None and "Alumnos del conjunto" not in [c.text.strip() for c in tabla_apertura.rows[0].cells]:
        tabla_apertura.add_column(Cm(1.35))
        poner_texto_celda(
            tabla_apertura.rows[0].cells[-1],
            "Alumnos del conjunto",
            bold=True,
            color="FFFFFF",
            tam=6.5,
        )
        sombrear(tabla_apertura.rows[0].cells[-1], "4472C4")
        for i, fila in enumerate(tabla_apertura.rows[1:]):
            cantidad = inscriptos[i] if i < len(inscriptos) else 0
            poner_texto_celda(fila.cells[-1], cantidad, bold=True, tam=6.5)

    # 2) Los totales de proyecto ya fueron recalculados por el helper v178.
    # Ajusta únicamente el rótulo visible para que no siga diciendo "período seleccionado".
    for tabla in doc.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                if celda.text.strip() == "Hs totales del período seleccionado":
                    poner_texto_celda(
                        celda,
                        "Hs totales de ejecución",
                        bold=True,
                        color="FFFFFF",
                        tam=7.1,
                    )

    # 3) Productividad individual con los mismos colores de la app.
    for tabla in doc.tables:
        if len(tabla.rows) < 2:
            continue
        cab = [c.text.strip() for c in tabla.rows[0].cells]
        if "Productividad" not in cab:
            continue
        j = cab.index("Productividad")
        if j >= len(tabla.rows[1].cells):
            continue
        celda_valor = tabla.rows[1].cells[j]
        txt = celda_valor.text.replace("%", "").strip().replace(",", ".")
        try:
            pct = float(txt)
        except Exception:
            continue
        fill, color_txt = _color_productividad_word_v178(pct)
        sombrear(celda_valor, fill)
        for par in celda_valor.paragraphs:
            for run in par.runs:
                run.bold = True
                run.font.color.rgb = RGBColor.from_string(color_txt)

    # 4) Cambia el criterio de cálculo escrito al final.
    for p in doc.paragraphs:
        txt = p.text.strip()
        if txt.startswith("• Las horas totales de cada proyecto en el período seleccionado"):
            p.text = (
                "• Las horas totales de cada proyecto se calculan como la suma de horas "
                "semanales de todas las asignaciones institucionales mostradas × todas las "
                "semanas comprendidas entre la fecha de inicio y la fecha de finalización "
                "del proyecto."
            )
            p.style = doc.styles["Normal"]

    # 5) El Resumen individual del plantel pasa al FINAL del informe.
    # Se mueve el bloque XML completo para preservar tablas, tipografías y formato.
    resumen_p = None
    detalle_p = None
    for p in doc.paragraphs:
        t = p.text.strip()
        if t == "4. Resumen individual del plantel docente":
            resumen_p = p
        elif t == "5. Detalle de movimientos relevantes":
            detalle_p = p

    if resumen_p is not None and detalle_p is not None:
        body = doc._element.body
        hijos = list(body)
        try:
            i_ini = hijos.index(resumen_p._p)
            i_fin = hijos.index(detalle_p._p)
        except ValueError:
            i_ini = i_fin = -1

        if 0 <= i_ini < i_fin:
            bloque_resumen = hijos[i_ini:i_fin]
            for elem in bloque_resumen:
                body.remove(elem)

            # Renumeración del resto, manteniendo estilos.
            mapa_titulos = {
                "5. Detalle de movimientos relevantes": "4. Detalle de movimientos relevantes",
                "6. Apertura de comisiones": "5. Apertura de comisiones",
                "7. Proyectos de investigación y docentes asignados": "6. Proyectos de investigación y docentes asignados",
                "8. Proyectos de extensión y docentes asignados": "7. Proyectos de extensión y docentes asignados",
                "9. Criterio de lectura": "8. Criterio de lectura",
            }
            for p in doc.paragraphs:
                actual = p.text.strip()
                if actual in mapa_titulos:
                    p.text = mapa_titulos[actual]

            # Salto de página antes del resumen final.
            p_break = doc.add_paragraph()
            p_break.add_run().add_break(WD_BREAK.PAGE)

            # Inserta todo el bloque del resumen inmediatamente antes de sectPr,
            # o sea después de todo el contenido previo.
            sectPr = body.sectPr
            pos = list(body).index(sectPr)
            for elem in bloque_resumen:
                body.insert(pos, elem)
                pos += 1

            # El objeto sigue apuntando al mismo XML movido.
            resumen_p.text = "9. Resumen individual del plantel docente"

    salida = BytesIO()
    doc.save(salida)
    salida.seek(0)
    return salida.getvalue()


# --- entry l. 39213-39221
def _periodo_contexto_info_v182(periodo_id=None):
    """Información normalizada del período usado como contexto de lectura."""
    try:
        if periodo_id is None:
            p = get_periodo_abierto() or get_ultimo_periodo()
            return dict(p or {})
        return dict(_info_periodo_analisis_v169(int(periodo_id)) or {})
    except Exception:
        return {}


# --- entry l. 39224-39254
def es_periodo_historico_contexto_v182(periodo_id=None):
    """True si el período no es el último período cronológico de ese departamento.

    Se compara contra get_ultimo_periodo(), NO contra estado='Cerrado'. Esto es
    deliberado: abrir un período anterior por excepción lo marca 'Abierto', pero
    sigue siendo histórico; a la vez, el último período puede quedar temporalmente
    'Cerrado' mientras se corrige el anterior y no por eso deja de ser el actual.
    """
    try:
        info = _periodo_contexto_info_v182(periodo_id)
        if not info:
            return False
        ultimo = get_ultimo_periodo()
        if not ultimo:
            return str(info.get("estado") or "").strip().casefold() == "cerrado"
        pid = int(info.get("id"))
        uid = int(ultimo.get("id"))
        if pid != uid:
            return True
        # Si el último período está cerrado y NO hay otro período anterior abierto
        # por excepción, también corresponde lectura histórica. Si hay un anterior
        # abierto, el cierre del último es solo temporal y no cambia su naturaleza.
        try:
            abierto = get_periodo_abierto()
            if abierto and int(abierto.get("id")) != uid:
                return False
        except Exception:
            pass
        return str(info.get("estado") or "").strip().casefold() == "cerrado"
    except Exception:
        return False


# --- entry l. 39257-39265
def fecha_referencia_contexto_v182(periodo_id=None):
    """Fecha de referencia: hoy para el período actual; fin de período para pasado."""
    info = _periodo_contexto_info_v182(periodo_id)
    if info and es_periodo_historico_contexto_v182(info.get("id")):
        try:
            return safe_date(info.get("fecha_fin"), date.today())
        except Exception:
            return date.today()
    return date.today()


# --- entry l. 39274-39275
def _periodo_cerrado_analisis_v169(periodo_id):
    return es_periodo_historico_contexto_v182(periodo_id)


# --- entry l. 39278-39320
def _filtrar_foto_designaciones_v169(df, periodo_id):
    """Designaciones que tuvieron vigencia en algún momento del período.

    Para el período actual se conserva exactamente la regla operativa estado=Activa.
    Para un período histórico se usa solapamiento temporal:
        desde <= fin_periodo  Y  fin_real >= inicio_periodo.
    La baja efectiva prevalece sobre el vencimiento previsto.
    """
    base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if base.empty:
        return base

    if not es_periodo_historico_contexto_v182(periodo_id):
        estado = base.get("estado", pd.Series(index=base.index, dtype=str)).fillna("").astype(str).str.strip().str.casefold()
        return base[estado.eq("activa")].copy().reset_index(drop=True)

    info = _periodo_contexto_info_v182(periodo_id)
    if "horas" in base.columns:
        base["_hs_v182"] = pd.to_numeric(base["horas"], errors="coerce").fillna(0)
        base = base[base["_hs_v182"] > 0].copy()
    if base.empty:
        return base.drop(columns=["_hs_v182"], errors="ignore")

    if "estado" in base.columns:
        estado = base["estado"].fillna("").astype(str).str.strip().str.casefold()
        base = base[~estado.eq("suspendida")].copy()
    if base.empty:
        return base.drop(columns=["_hs_v182"], errors="ignore")

    fi = _fecha_a_timestamp_seguro(info.get("fecha_inicio", ""))
    ff = _fecha_a_timestamp_seguro(info.get("fecha_fin", ""))
    base["_desde_v182"] = base["fecha_desde"].apply(_fecha_a_timestamp_seguro) if "fecha_desde" in base.columns else pd.NaT
    base["_hasta_v182"] = base.apply(_fecha_fin_designacion_analisis_v169, axis=1)

    vig = pd.Series(True, index=base.index)
    if not pd.isna(ff):
        vig &= base["_desde_v182"].isna() | (base["_desde_v182"] <= ff)
    if not pd.isna(fi):
        vig &= base["_hasta_v182"].isna() | (base["_hasta_v182"] >= fi)

    out = base[vig].copy()
    out["estado_analisis"] = "Integró el período"
    return out.drop(columns=["_hs_v182", "_desde_v182", "_hasta_v182"], errors="ignore").reset_index(drop=True)


# --- entry l. 39324
_get_proyectos_investigacion_pre_v182 = get_proyectos_investigacion


# --- entry l. 39325
_get_proyectos_extension_pre_v182 = get_proyectos_extension


# --- entry l. 39328-39341
def _proyectos_contexto_historico_v182(fn, solo_activos=False, periodo_id=None):
    if periodo_id is None or not es_periodo_historico_contexto_v182(periodo_id):
        return fn(solo_activos=solo_activos, periodo_id=periodo_id)
    # False evita que un proyecto hoy Finalizado/Suspendido desaparezca del semestre
    # en el que efectivamente se ejecutaba. El fn original ya filtra por solapamiento
    # de fechas cuando recibe periodo_id.
    df = fn(solo_activos=False, periodo_id=periodo_id)
    if df is None or df.empty:
        return df
    out = df.copy()
    ref = fecha_referencia_contexto_v182(periodo_id)
    out["situacion"] = out.apply(lambda r: _situacion_proyecto(r.to_dict(), ref), axis=1)
    out["fecha_referencia_contexto"] = str(ref)
    return out.reset_index(drop=True)


# --- entry l. 39344-39347
def get_proyectos_investigacion(solo_activos=False, periodo_id=None):
    return _proyectos_contexto_historico_v182(
        _get_proyectos_investigacion_pre_v182, solo_activos=solo_activos, periodo_id=periodo_id
    )


# --- entry l. 39350-39353
def get_proyectos_extension(solo_activos=False, periodo_id=None):
    return _proyectos_contexto_historico_v182(
        _get_proyectos_extension_pre_v182, solo_activos=solo_activos, periodo_id=periodo_id
    )


# --- entry l. 39358-39414
def _horarios_docente_historicos_v182(cuil, periodo_id, todos_departamentos=True):
    if not str(cuil or "").strip():
        return pd.DataFrame()
    if USE_POSTGRESQL:
        try:
            inst_id = int(_pg_current_inst_id())
            nombre_p, anio, semestre = _periodo_equivalente_pg(periodo_id)
            filtros = [
                "a.institucion_id=%s",
                "regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g')=%s",
                "(co.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))",
            ]
            params = [inst_id, _clave_cuil(cuil), int(periodo_id), nombre_p, int(anio), int(semestre)]
            if not todos_departamentos:
                dep_id = _pg_current_dep_id()
                if dep_id is not None:
                    filtros.append("co.departamento_id=%s")
                    params.append(int(dep_id))
            return _pg_read_dataframe(f"""
                SELECT DISTINCT
                    a.id AS asignacion_id, a.cuil, COALESCE(a.estado,'Activa') AS estado_asignacion,
                    COALESCE(a.horas_asignadas,0) AS horas_asignadas,
                    co.id AS comision_id, co.departamento_id,
                    COALESCE(dep.nombre,'') AS departamento_comision,
                    h.dia, h.hora_inicio, h.hora_fin, h.horas
                FROM asignaciones_docentes_comision a
                JOIN comisiones co ON co.id=a.comision_id
                JOIN periodos p ON p.id=co.periodo_id
                JOIN horarios_comision h ON h.comision_id=co.id
                LEFT JOIN departamentos dep ON dep.id=co.departamento_id
                WHERE {' AND '.join(filtros)}
                ORDER BY h.dia, h.hora_inicio, co.id
            """, params)
        except Exception:
            return pd.DataFrame()

    # SQLite: toma asignaciones del período y expande horarios de cada comisión.
    try:
        dfa = get_asignaciones_comisiones_periodo(periodo_id)
        if dfa is None or dfa.empty:
            return pd.DataFrame()
        claves = dfa.get("cuil", pd.Series(index=dfa.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
        dfa = dfa[claves.eq(_clave_cuil(cuil))].copy()
        filas = []
        for _, a in dfa.iterrows():
            cid = int(a.get("comision_id"))
            dfh = get_horarios_comision(cid)
            for _, h in dfh.iterrows() if isinstance(dfh, pd.DataFrame) else []:
                x = h.to_dict(); x.update({
                    "asignacion_id": a.get("id"), "cuil": a.get("cuil"),
                    "estado_asignacion": a.get("estado", "Activa"),
                    "horas_asignadas": a.get("horas_asignadas", 0), "comision_id": cid,
                    "departamento_id": 0, "departamento_comision": "",
                }); filas.append(x)
        return pd.DataFrame(filas)
    except Exception:
        return pd.DataFrame()


# --- entry l. 39417-39432
def _designaciones_docente_contexto_v182(cuil, periodo_id, institucional=True):
    try:
        if USE_POSTGRESQL and institucional:
            df = _get_designaciones_periodo_institucional_v149(cuil, periodo_id)
        else:
            df = get_designaciones(periodo_id)
            if not df.empty:
                claves = df.get("cuil", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
                df = df[claves.eq(_clave_cuil(cuil))].copy()
        df = _filtrar_foto_designaciones_v169(df, periodo_id)
        if df is None or df.empty:
            return pd.DataFrame()
        no_doc = df.get("funcion_no_docente", pd.Series(0, index=df.index)).map(_es_funcion_no_docente_v162)
        return df[~no_doc].copy().reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


# --- entry l. 39435-39506
def _productividad_docente_contexto_v182(cuil, periodo_id, institucional=True):
    if not es_periodo_historico_contexto_v182(periodo_id):
        return None
    df_des = _designaciones_docente_contexto_v182(cuil, periodo_id, institucional=institucional)
    contratadas = _horas_designaciones_v165(df_des) if not df_des.empty else 0.0

    df_h = _horarios_docente_historicos_v182(cuil, periodo_id, todos_departamentos=institucional)
    com_reales = _calcular_horas_unicas_desde_horarios_df(df_h) if isinstance(df_h, pd.DataFrame) and not df_h.empty else 0.0
    if isinstance(df_h, pd.DataFrame) and not df_h.empty and "asignacion_id" in df_h.columns:
        dfa = df_h.drop_duplicates(subset=["asignacion_id"]).copy()
        com_brutas = float(pd.to_numeric(dfa.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    else:
        com_brutas = float(com_reales)

    horas_nl = 0.0
    detalle_nl = []
    if institucional and isinstance(df_h, pd.DataFrame) and not df_h.empty and "departamento_id" in df_h.columns:
        mapa_pct = _get_porcentajes_no_lectivos_departamentos_v149()
        for dep_id, g in df_h.groupby("departamento_id", dropna=True):
            try:
                dep_i = int(dep_id)
            except Exception:
                continue
            hs = float(_calcular_horas_unicas_desde_horarios_df(g) or 0)
            pct = float(mapa_pct.get(dep_i, 0) or 0)
            hs_n = round(hs * pct / 100.0, 2)
            horas_nl += hs_n
            detalle_nl.append({
                "Departamento": limpiar_texto_tabla(g.iloc[0].get("departamento_comision", "")) or str(dep_i),
                "Hs frente a comisión": round(hs, 2), "% no lectivas": round(pct, 2), "Hs no lectivas": hs_n,
            })
    else:
        pct = float(get_porcentaje_horas_no_lectivas_v148() or 0)
        horas_nl = round(float(com_reales) * pct / 100.0, 2)

    try:
        df_inv = get_investigacion_docente(
            cuil=cuil, periodo_id=periodo_id, incluir_bajas=False,
            todos_departamentos=(USE_POSTGRESQL and institucional),
        )
        hs_inv = float(pd.to_numeric(df_inv.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if isinstance(df_inv, pd.DataFrame) and not df_inv.empty else 0.0
    except Exception:
        hs_inv = 0.0
    try:
        df_ext = get_extension_docente(
            cuil=cuil, periodo_id=periodo_id, incluir_bajas=False,
            todos_departamentos=(USE_POSTGRESQL and institucional),
        )
        hs_ext = float(pd.to_numeric(df_ext.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if isinstance(df_ext, pd.DataFrame) and not df_ext.empty else 0.0
    except Exception:
        hs_ext = 0.0

    horas_nl = round(float(horas_nl), 2)
    utilizadas = round(float(com_reales) + horas_nl + hs_inv + hs_ext, 2)
    disponibles = round(float(contratadas) - utilizadas, 2)
    pct_uso = round(utilizadas / float(contratadas) * 100.0, 2) if contratadas > 0 else 0.0
    pct_nl_ef = round(horas_nl / float(com_reales) * 100.0, 2) if com_reales > 0 else 0.0
    return {
        "horas_contratadas": round(float(contratadas), 2),
        "horas_en_comisiones": round(float(com_reales), 2),
        "horas_en_comisiones_brutas": round(float(com_brutas), 2),
        "horas_no_contadas_por_superposicion": max(round(float(com_brutas)-float(com_reales), 2), 0.0),
        "porcentaje_no_lectivas": pct_nl_ef,
        "horas_no_lectivas": horas_nl,
        "detalle_no_lectivas_departamentos": detalle_nl,
        "horas_en_investigacion": round(hs_inv, 2),
        "horas_en_extension": round(hs_ext, 2),
        "horas_utilizadas": utilizadas,
        "horas_disponibles": disponibles,
        "porcentaje": pct_uso,
        "lectura_historica": True,
    }


# --- entry l. 39509
_get_productividad_docente_institucional_pre_v182 = get_productividad_docente_institucional_v149


# --- entry l. 39510
_productividad_docente_departamento_pre_v182 = _productividad_docente_departamento_v148


# --- entry l. 39511
_get_productividad_docente_pre_v182 = get_productividad_docente


# --- entry l. 39514-39518
def get_productividad_docente_institucional_v149(cuil, periodo_id):
    hist = _productividad_docente_contexto_v182(cuil, periodo_id, institucional=True)
    if hist is not None:
        return hist
    return _get_productividad_docente_institucional_pre_v182(cuil, periodo_id)


# --- entry l. 39521-39525
def _productividad_docente_departamento_v148(cuil, periodo_id):
    hist = _productividad_docente_contexto_v182(cuil, periodo_id, institucional=False)
    if hist is not None:
        return hist
    return _productividad_docente_departamento_pre_v182(cuil, periodo_id)


# --- entry l. 39528-39531
def get_productividad_docente(cuil, periodo_id):
    if es_periodo_historico_contexto_v182(periodo_id):
        return get_productividad_docente_institucional_v149(cuil, periodo_id) if USE_POSTGRESQL else _productividad_docente_departamento_v148(cuil, periodo_id)
    return _get_productividad_docente_pre_v182(cuil, periodo_id)


# --- entry l. 39536
_get_plantel_periodo_pre_v182 = get_plantel_periodo


# --- entry l. 39539-39556
def _identidad_docente_institucional_v182(cuil):
    try:
        if USE_POSTGRESQL:
            inst = int(_pg_current_inst_id()); dep = int(_pg_current_dep_id() or 0)
            df = _pg_read_dataframe("""
                SELECT doc.cuil, doc.legajo, doc.apellido, doc.nombres, doc.nombre,
                       doc.titulo, COALESCE(doc.titulo_posgrado,'') AS titulo_posgrado,
                       doc.email, doc.telefono
                FROM docentes doc
                WHERE doc.institucion_id=%s
                  AND regexp_replace(COALESCE(doc.cuil,''), '[^0-9]', '', 'g')=%s
                ORDER BY CASE WHEN doc.departamento_id=%s THEN 0 ELSE 1 END, doc.id
                LIMIT 1
            """, [inst, _clave_cuil(cuil), dep])
            return df.iloc[0].to_dict() if not df.empty else {}
    except Exception:
        pass
    return {}


# --- entry l. 39559-39645
def get_plantel_periodo(periodo_id):
    base = _get_plantel_periodo_pre_v182(periodo_id)
    base = base.copy() if isinstance(base, pd.DataFrame) else pd.DataFrame()
    if not es_periodo_historico_contexto_v182(periodo_id):
        return base

    df_doc, _, _ = _designaciones_funcionales_analisis_v169(periodo_id)
    claves_doc = {
        x for x in df_doc.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x
    } if isinstance(df_doc, pd.DataFrame) and not df_doc.empty else set()

    try:
        df_pr = _prestados_recibidos_periodo_v175(periodo_id)
    except Exception:
        df_pr = pd.DataFrame()
    try:
        df_pr_tabla = get_prestamos_docentes_periodo_v174(periodo_id, solo_activos=False)
    except Exception:
        df_pr_tabla = pd.DataFrame()
    claves_prest = set()
    for dfx in [df_pr, df_pr_tabla]:
        if isinstance(dfx, pd.DataFrame) and not dfx.empty:
            claves_prest |= {x for x in dfx.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x}

    # Elimina del histórico filas permanentes tipo Prestado que no pertenecieron a ese período.
    if not base.empty:
        tipo = base.get("tipo_docente", pd.Series("Propio", index=base.index)).fillna("Propio").astype(str).str.strip().str.casefold()
        claves = base.get("cuil", pd.Series(index=base.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
        base = base[(tipo.ne("prestado") & claves.isin(claves_doc)) | (tipo.eq("prestado") & claves.isin(claves_prest))].copy()

    # Ajusta designaciones propias a la foto histórica por solapamiento.
    if isinstance(df_doc, pd.DataFrame) and not df_doc.empty:
        for idx, r in base.iterrows():
            if str(r.get("tipo_docente", "Propio")).strip().casefold() == "prestado":
                continue
            k = _clave_cuil(r.get("cuil"))
            sub = df_doc[df_doc.get("cuil", pd.Series(index=df_doc.index, dtype=str)).fillna("").astype(str).map(_clave_cuil).eq(k)].copy()
            if sub.empty:
                continue
            hs = _horas_designaciones_v165(sub)
            base.at[idx, "estado_operativo_periodo"] = "Vigente al cierre del período"
            base.at[idx, "designaciones_del_periodo"] = int(len(sub))
            base.at[idx, "designaciones_activas"] = int(len(sub))
            base.at[idx, "horas_activas"] = round(hs, 2)
            base.at[idx, "horas_registradas_periodo"] = round(hs, 2)
            partes = []
            for _, d in sub.iterrows():
                partes.append(
                    f"{d.get('cargo','')} - {d.get('dedicacion','')} - {float(pd.to_numeric(d.get('horas'), errors='coerce') or 0):g} hs - "
                    f"{d.get('tipo_designacion','')} - Ad Honorem: {d.get('ad_honorem','No')} - Estado al cierre: Vigente"
                )
            base.at[idx, "detalle_designaciones"] = " | ".join(partes)

    # Añade préstamos históricos que la versión operativa pudo omitir por estar hoy finalizados.
    existentes = {x for x in base.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x} if not base.empty else set()
    mapa_pr = {}
    for dfx in [df_pr_tabla, df_pr]:
        if isinstance(dfx, pd.DataFrame) and not dfx.empty:
            for _, r in dfx.iterrows():
                k = _clave_cuil(r.get("cuil"))
                if k:
                    mapa_pr.setdefault(k, {}).update(r.to_dict())

    nuevas = []
    for k in sorted(claves_prest - existentes):
        pr = mapa_pr.get(k, {})
        cuil = str(pr.get("cuil") or k).strip()
        ident = _identidad_docente_institucional_v182(cuil)
        nombre = nombre_completo(str(ident.get("apellido") or ""), str(ident.get("nombres") or "")) or str(ident.get("nombre") or pr.get("docente") or cuil)
        dfi = _designaciones_docentes_institucionales_analisis_v169(cuil, periodo_id)
        hs = _horas_designaciones_v165(dfi) if isinstance(dfi, pd.DataFrame) and not dfi.empty else 0.0
        estado_pr = str(pr.get("estado") or "").strip().casefold()
        nuevas.append({
            "cuil": cuil, "legajo": ident.get("legajo", ""), "nombre_completo": nombre,
            "titulo": ident.get("titulo", ""), "titulo_posgrado": ident.get("titulo_posgrado", ""),
            "email": ident.get("email", ""), "telefono": ident.get("telefono", ""), "tipo_docente": "Prestado",
            "estado_operativo_periodo": "Préstamo finalizado en el período" if estado_pr in {"finalizado", "finalizada", "cerrado"} else "Docente prestado en el período",
            "fecha_alta_periodo": _fecha_prestamo_texto_v179(pr.get("fecha_desde", "")),
            "fecha_finalizacion_periodo": _fecha_prestamo_texto_v179(pr.get("fecha_hasta", "")),
            "designaciones_del_periodo": 0, "designaciones_activas": 0,
            "horas_activas": 0.0, "horas_registradas_periodo": 0.0,
            "detalle_designaciones": f"DOCENTE PRESTADO desde {pr.get('departamento_origen','') or 'otro departamento'}; designación institucional de origen: {round(hs,2):g} hs.",
        })
    if nuevas:
        base = pd.concat([base, pd.DataFrame(nuevas)], ignore_index=True, sort=False)

    return base.reset_index(drop=True)


# --- entry l. 39648
_get_docentes_pre_v182 = get_docentes


# --- entry l. 39651-39661
def get_docentes():
    df = _get_docentes_pre_v182()
    df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    p = get_periodo_abierto()
    if df.empty or not p or not es_periodo_historico_contexto_v182(p.get("id")):
        return df
    plantel = get_plantel_periodo(p["id"])
    claves = {x for x in plantel.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x} if isinstance(plantel, pd.DataFrame) and not plantel.empty else set()
    kdf = df.get("cuil", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
    df["estado_periodo_abierto"] = ["Integró el período en contexto" if k in claves else "Sin actividad registrada en el período en contexto" for k in kdf]
    return df


# --- entry l. 39705
_get_metricas_analisis_periodo_pre_v182 = get_metricas_analisis_periodo


# --- entry l. 39708-39771
def get_metricas_analisis_periodo(periodo_id):
    datos = dict(_get_metricas_analisis_periodo_pre_v182(periodo_id) or {})
    if not es_periodo_historico_contexto_v182(periodo_id):
        datos["lectura_historica_periodo"] = False
        return datos

    df_doc, df_no_doc, df_total = _designaciones_funcionales_analisis_v169(periodo_id)
    c_doc = _cuiles_unicos_designaciones_v165(df_doc)
    c_no = _cuiles_unicos_designaciones_v165(df_no_doc)
    hs_doc = _horas_designaciones_v165(df_doc); hs_no = _horas_designaciones_v165(df_no_doc); hs_total = round(hs_doc + hs_no, 2)
    ah_doc = _conteo_ad_honorem_v165(df_doc); ah_no = _conteo_ad_honorem_v165(df_no_doc); ah_total = _conteo_ad_honorem_v165(df_total)

    datos.update({
        "lectura_historica_periodo": True,
        "estado_periodo_analisis": _periodo_contexto_info_v182(periodo_id).get("estado", ""),
        "docentes_activos": len(c_doc), "no_docentes_activos": len(c_no), "personas_activas_totales": len(c_doc | c_no),
        "cargos_totales": len(df_doc), "cargos_docentes": len(df_doc), "cargos_no_docentes": len(df_no_doc), "cargos_totales_consolidados": len(df_total),
        "horas_contratadas": hs_doc, "horas_contratadas_docencia": hs_doc, "horas_no_docentes": hs_no, "horas_contratadas_totales": hs_total,
        "cargos_ad_honorem_docentes": ah_doc, "cargos_rentados_docentes": len(df_doc)-ah_doc,
        "cargos_ad_honorem_no_docentes": ah_no, "cargos_rentados_no_docentes": len(df_no_doc)-ah_no,
        "cargos_ad_honorem_totales": ah_total, "cargos_rentados_totales": len(df_total)-ah_total,
        "df_desig_docentes_activas": df_doc, "df_desig_no_docentes_activas": df_no_doc, "df_desig_activas_totales": df_total,
    })

    try:
        df_prod = get_docentes_productividad_periodo(periodo_id)
    except Exception:
        df_prod = pd.DataFrame()
    if isinstance(df_prod, pd.DataFrame) and not df_prod.empty:
        datos["horas_comisiones"] = round(float(pd.to_numeric(df_prod.get("horas_comisiones_reales"), errors="coerce").fillna(0).sum()), 2)
        datos["horas_no_lectivas"] = round(float(pd.to_numeric(df_prod.get("horas_no_lectivas"), errors="coerce").fillna(0).sum()), 2)
        datos["horas_investigacion"] = round(float(pd.to_numeric(df_prod.get("horas_investigacion"), errors="coerce").fillna(0).sum()), 2)
        datos["horas_extension"] = round(float(pd.to_numeric(df_prod.get("horas_extension"), errors="coerce").fillna(0).sum()), 2)
        datos["horas_academicas_utilizadas"] = round(float(pd.to_numeric(df_prod.get("horas_utilizadas"), errors="coerce").fillna(0).sum()), 2)
    else:
        for k in ["horas_comisiones", "horas_no_lectivas", "horas_investigacion", "horas_extension", "horas_academicas_utilizadas"]:
            datos[k] = 0.0

    try:
        df_com = get_comisiones(periodo_id=periodo_id, solo_activas=False)
        datos["comisiones"] = int(len(df_com)) if isinstance(df_com, pd.DataFrame) else 0
    except Exception:
        pass
    try:
        df_asig = get_asignaciones_comisiones_periodo(periodo_id)
        datos["df_asig"] = df_asig
        if isinstance(df_asig, pd.DataFrame) and not df_asig.empty:
            claves_asig = df_asig.get("cuil", pd.Series(index=df_asig.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
            datos["docentes_en_comisiones"] = int(claves_asig[claves_asig.isin(c_doc)].replace("", pd.NA).dropna().nunique())
    except Exception:
        pass
    try:
        pr = _prestados_recibidos_periodo_v175(periodo_id)
        datos["docentes_prestados_recibidos"] = int(len(pr))
        datos["df_prestados_recibidos_periodo"] = pr
    except Exception:
        pass

    hs_acad = float(datos.get("horas_academicas_utilizadas", 0) or 0)
    datos["horas_no_docentes_utilizadas"] = hs_no
    datos["horas_utilizadas_totales"] = round(hs_acad + hs_no, 2)
    datos["horas_disponibles_totales"] = round(max(hs_total - datos["horas_utilizadas_totales"], 0), 2)
    datos["horas_exceso_totales"] = round(max(datos["horas_utilizadas_totales"] - hs_total, 0), 2)
    return datos


# --- entry l. 39782-39784
def _fecha_cierre_periodo_v183(periodo_id):
    info = _periodo_contexto_info_v182(periodo_id)
    return safe_date((info or {}).get("fecha_fin"), None)


# --- entry l. 39787-39789
def _fecha_iso_observacion_v183(texto, patrones=None):
    from analisis.motor.ref.common.dates import _fecha_iso_observacion_v183 as _b05_core__fecha_iso_observacion_v183
    return _b05_core__fecha_iso_observacion_v183(texto, patrones)


# --- entry l. 39792-39826
def _filtrar_foto_designaciones_v169(df, periodo_id):
    """Foto de designaciones vigente exactamente en el último día del período."""
    base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if base.empty:
        return base

    if not es_periodo_historico_contexto_v182(periodo_id):
        estado = base.get("estado", pd.Series(index=base.index, dtype=str)).fillna("").astype(str).str.strip().str.casefold()
        return base[estado.eq("activa")].copy().reset_index(drop=True)

    info = _periodo_contexto_info_v182(periodo_id)
    ref = _fecha_a_timestamp_seguro((info or {}).get("fecha_fin", ""))

    if "horas" in base.columns:
        base["_hs_v183"] = pd.to_numeric(base["horas"], errors="coerce").fillna(0)
        base = base[base["_hs_v183"] > 0].copy()
    if base.empty:
        return base.drop(columns=["_hs_v183"], errors="ignore")

    if "estado" in base.columns:
        estado = base["estado"].fillna("").astype(str).str.strip().str.casefold()
        base = base[~estado.eq("suspendida")].copy()
    if base.empty:
        return base.drop(columns=["_hs_v183"], errors="ignore")

    base["_desde_v183"] = base["fecha_desde"].apply(_fecha_a_timestamp_seguro) if "fecha_desde" in base.columns else pd.NaT
    base["_hasta_v183"] = base.apply(_fecha_fin_designacion_analisis_v169, axis=1)
    vigente = pd.Series(True, index=base.index)
    if not pd.isna(ref):
        vigente &= base["_desde_v183"].isna() | (base["_desde_v183"] <= ref)
        vigente &= base["_hasta_v183"].isna() | (base["_hasta_v183"] >= ref)

    out = base[vigente].copy()
    out["estado_analisis"] = "Vigente al cierre del período"
    return out.drop(columns=["_hs_v183", "_desde_v183", "_hasta_v183"], errors="ignore").reset_index(drop=True)


# --- entry l. 39829-39841
def _filtrar_prestamos_cierre_v183(df, periodo_id):
    """Préstamos que seguían vigentes en la fecha de cierre del período."""
    base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if base.empty or not es_periodo_historico_contexto_v182(periodo_id):
        return base
    ref = _fecha_cierre_periodo_v183(periodo_id)
    if ref is None:
        return base

    desde = base.get("fecha_desde", pd.Series(index=base.index, dtype=object)).apply(lambda x: safe_date(x, None))
    hasta = base.get("fecha_hasta", pd.Series(index=base.index, dtype=object)).apply(lambda x: safe_date(x, None))
    ok = (desde.isna() | (desde <= ref)) & (hasta.isna() | (hasta >= ref))
    return base[ok].copy().reset_index(drop=True)


# --- entry l. 39844
_prestados_recibidos_periodo_pre_v183 = _prestados_recibidos_periodo_v175


# --- entry l. 39846-39883
def _prestados_recibidos_periodo_v175(periodo_id):
    """Prestados recibidos que forman parte de la foto al cierre."""
    raw = _prestados_recibidos_periodo_pre_v183(periodo_id)
    raw = raw.copy() if isinstance(raw, pd.DataFrame) else pd.DataFrame()
    if raw.empty or not es_periodo_historico_contexto_v182(periodo_id):
        return raw

    # Debe seguir teniendo asignación en comisión al cierre.
    try:
        asig = get_asignaciones_comisiones_periodo(periodo_id)
        claves_asig = {
            x for x in asig.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x
        } if isinstance(asig, pd.DataFrame) and not asig.empty else set()
    except Exception:
        claves_asig = set()

    # Si existe registro explícito de préstamo, respeta su vigencia al cierre.
    try:
        pr_all = get_prestamos_docentes_periodo_v174(periodo_id, solo_activos=False)
        pr_close = _filtrar_prestamos_cierre_v183(pr_all, periodo_id)
        claves_registradas = {
            x for x in pr_all.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x
        } if isinstance(pr_all, pd.DataFrame) and not pr_all.empty else set()
        claves_pr_close = {
            x for x in pr_close.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x
        } if isinstance(pr_close, pd.DataFrame) and not pr_close.empty else set()
    except Exception:
        claves_registradas, claves_pr_close = set(), set()

    claves_raw = raw.get("cuil", pd.Series(index=raw.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
    def _ok(k):
        if k not in claves_asig:
            return False
        # Para datos legacy sin fila de préstamo explícita, conserva la evidencia robusta v175.
        if k not in claves_registradas:
            return True
        return k in claves_pr_close
    return raw[[bool(_ok(k)) for k in claves_raw]].copy().reset_index(drop=True)


# --- entry l. 39886-39912
def _filtrar_asignaciones_comision_cierre_v183(df, periodo_id):
    """Asignaciones a comisión vigentes al cierre, usando fechas efectivas si existen."""
    base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if base.empty or not es_periodo_historico_contexto_v182(periodo_id):
        return base
    ref = _fecha_cierre_periodo_v183(periodo_id)
    if ref is None:
        return base

    keep = []
    for _, r in base.iterrows():
        estado = str(r.get("estado", r.get("estado_asignacion", "Activa")) or "Activa").strip().casefold()
        obs = str(r.get("observaciones", "") or "")
        alta = _fecha_iso_observacion_v183(obs, [r"Alta por modificación de asignación\.\s*Fecha efectiva:\s*(\d{4}-\d{2}-\d{2})"])
        baja = _fecha_iso_observacion_v183(obs, [
            r"Baja por modificación de asignación\.\s*Fecha efectiva:\s*(\d{4}-\d{2}-\d{2})",
            r"Préstamo finalizado el\s*(\d{4}-\d{2}-\d{2})",
        ])
        ok_alta = (alta is None or alta <= ref)
        if estado == "activa":
            ok_baja = (baja is None or baja >= ref)
        else:
            # Una asignación hoy finalizada solo integra la foto si consta que su baja
            # efectiva fue el día de cierre o después. Sin fecha verificable, no se inventa vigencia.
            ok_baja = (baja is not None and baja >= ref)
        keep.append(bool(ok_alta and ok_baja))
    return base[pd.Series(keep, index=base.index)].copy().reset_index(drop=True)


# --- entry l. 39915
_get_asignaciones_comisiones_periodo_pre_v183 = get_asignaciones_comisiones_periodo


# --- entry l. 39916
_get_asignaciones_comision_pre_v183 = get_asignaciones_comision


# --- entry l. 39919-39923
def get_asignaciones_comisiones_periodo(periodo_id=None):
    df = _get_asignaciones_comisiones_periodo_pre_v183(periodo_id)
    if periodo_id is not None and es_periodo_historico_contexto_v182(periodo_id):
        return _filtrar_asignaciones_comision_cierre_v183(df, periodo_id)
    return df


# --- entry l. 39926-39933
def _periodo_comision_v183(comision_id):
    try:
        conn = get_conn()
        d = pd.read_sql("SELECT periodo_id FROM comisiones WHERE id=? LIMIT 1", conn, params=[int(comision_id)])
        conn.close()
        return int(d.iloc[0]["periodo_id"]) if not d.empty else None
    except Exception:
        return None


# --- entry l. 39936-39941
def get_asignaciones_comision(comision_id=None):
    df = _get_asignaciones_comision_pre_v183(comision_id)
    pid = _periodo_comision_v183(comision_id) if comision_id is not None else None
    if pid is not None and es_periodo_historico_contexto_v182(pid):
        return _filtrar_asignaciones_comision_cierre_v183(df, pid)
    return df


# --- entry l. 39944-39965
def _filtrar_asignaciones_proyecto_cierre_v183(df, periodo_id):
    """Participaciones de investigación/extensión vigentes exactamente al cierre."""
    base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if base.empty or not es_periodo_historico_contexto_v182(periodo_id):
        return base
    ref = _fecha_cierre_periodo_v183(periodo_id)
    if ref is None:
        return base

    carga = base.get("fecha_carga", pd.Series(index=base.index, dtype=object)).apply(lambda x: safe_date(x, None))
    baja = base.get("fecha_baja", pd.Series(index=base.index, dtype=object)).apply(lambda x: safe_date(x, None))
    estado = base.get("estado_asignacion", pd.Series("Activa", index=base.index)).fillna("Activa").astype(str).str.strip().str.casefold()
    ini_pr = base.get("fecha_inicio", pd.Series(index=base.index, dtype=object)).apply(lambda x: safe_date(x, None))
    fin_pr = base.get("fecha_fin", pd.Series(index=base.index, dtype=object)).apply(lambda x: safe_date(x, None))

    ok = carga.isna() | (carga <= ref)
    # Si existe fecha de baja, manda la fecha. Si no existe, solo una asignación aún activa puede computar.
    ok &= baja.isna() | (baja >= ref)
    ok &= estado.eq("activa") | (baja.notna() & (baja >= ref))
    ok &= ini_pr.isna() | (ini_pr <= ref)
    ok &= fin_pr.isna() | (fin_pr >= ref)
    return base[ok].copy().reset_index(drop=True)


# --- entry l. 39968
_get_investigacion_docente_pre_v183 = get_investigacion_docente


# --- entry l. 39969
_get_extension_docente_pre_v183 = get_extension_docente


# --- entry l. 39972-39980
def get_investigacion_docente(cuil=None, periodo_id=None, incluir_bajas=False, todos_departamentos=False):
    if periodo_id is not None and es_periodo_historico_contexto_v182(periodo_id) and not incluir_bajas:
        raw = _get_investigacion_docente_pre_v183(
            cuil=cuil, periodo_id=periodo_id, incluir_bajas=True, todos_departamentos=todos_departamentos
        )
        return _filtrar_asignaciones_proyecto_cierre_v183(raw, periodo_id)
    return _get_investigacion_docente_pre_v183(
        cuil=cuil, periodo_id=periodo_id, incluir_bajas=incluir_bajas, todos_departamentos=todos_departamentos
    )


# --- entry l. 39983-39991
def get_extension_docente(cuil=None, periodo_id=None, incluir_bajas=False, todos_departamentos=False):
    if periodo_id is not None and es_periodo_historico_contexto_v182(periodo_id) and not incluir_bajas:
        raw = _get_extension_docente_pre_v183(
            cuil=cuil, periodo_id=periodo_id, incluir_bajas=True, todos_departamentos=todos_departamentos
        )
        return _filtrar_asignaciones_proyecto_cierre_v183(raw, periodo_id)
    return _get_extension_docente_pre_v183(
        cuil=cuil, periodo_id=periodo_id, incluir_bajas=incluir_bajas, todos_departamentos=todos_departamentos
    )


# --- entry l. 39994-40014
def _proyecto_vigente_al_cierre_v183(fila, periodo_id):
    ref = _fecha_cierre_periodo_v183(periodo_id)
    if ref is None:
        return False
    ini = safe_date((fila or {}).get("fecha_inicio"), None)
    fin = safe_date((fila or {}).get("fecha_fin"), None)
    if ini is None or fin is None:
        ini_l, fin_l = _fechas_desde_periodo_legacy((fila or {}).get("periodo_ejecucion", ""), (fila or {}).get("anio_llamado"))
        ini = ini or ini_l; fin = fin or fin_l
    if ini is not None and ini > ref:
        return False
    if fin is not None and fin < ref:
        return False
    fs = safe_date((fila or {}).get("fecha_suspension"), None)
    if fs is not None and fs <= ref:
        return False
    # Archivado/Finalizado actuales no se proyectan hacia atrás: se priorizan las
    # fechas efectivas disponibles. Suspensión sí tiene fecha propia en el sistema.
    if str((fila or {}).get("estado") or "Activo").strip().casefold() == "suspendido" and fs is None:
        return False
    return True


# --- entry l. 40017-40030
def _situacion_proyecto_cierre_v183(fila, periodo_id):
    ref = _fecha_cierre_periodo_v183(periodo_id)
    if ref is None:
        return _situacion_proyecto(fila)
    fs = safe_date((fila or {}).get("fecha_suspension"), None)
    if fs is not None and fs <= ref:
        return "Suspendido"
    ini = safe_date((fila or {}).get("fecha_inicio"), None)
    fin = safe_date((fila or {}).get("fecha_fin"), None)
    if fin is not None and fin < ref:
        return "Finalizado"
    if ini is not None and ini > ref:
        return "Programado"
    return "En ejecución al cierre"


# --- entry l. 40033-40045
def _proyectos_contexto_historico_v182(fn, solo_activos=False, periodo_id=None):
    if periodo_id is None or not es_periodo_historico_contexto_v182(periodo_id):
        return fn(solo_activos=solo_activos, periodo_id=periodo_id)
    df = fn(solo_activos=False, periodo_id=periodo_id)
    if df is None or df.empty:
        return df
    out = df.copy()
    if solo_activos:
        mask = out.apply(lambda r: _proyecto_vigente_al_cierre_v183(r.to_dict(), periodo_id), axis=1)
        out = out[mask].copy()
    out["situacion"] = out.apply(lambda r: _situacion_proyecto_cierre_v183(r.to_dict(), periodo_id), axis=1)
    out["fecha_referencia_contexto"] = str(_fecha_cierre_periodo_v183(periodo_id) or "")
    return out.reset_index(drop=True)


# --- entry l. 40048
_get_plantel_periodo_v182_pre_v183 = get_plantel_periodo


# --- entry l. 40051-40110
def get_plantel_periodo(periodo_id):
    base = _get_plantel_periodo_v182_pre_v183(periodo_id)
    base = base.copy() if isinstance(base, pd.DataFrame) else pd.DataFrame()
    if not es_periodo_historico_contexto_v182(periodo_id):
        return base

    df_doc, _, _ = _designaciones_funcionales_analisis_v169(periodo_id)
    claves_doc = {
        x for x in df_doc.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x
    } if isinstance(df_doc, pd.DataFrame) and not df_doc.empty else set()

    try:
        pr_all = get_prestamos_docentes_periodo_v174(periodo_id, solo_activos=False)
        pr_close = _filtrar_prestamos_cierre_v183(pr_all, periodo_id)
        claves_prest = {
            x for x in pr_close.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x
        } if isinstance(pr_close, pd.DataFrame) and not pr_close.empty else set()
    except Exception:
        pr_close = pd.DataFrame(); claves_prest = set()

    # Legacy: si v175 acredita préstamo + comisión vigente al cierre, no lo pierde.
    try:
        pr_legacy = _prestados_recibidos_periodo_v175(periodo_id)
        claves_prest |= {
            x for x in pr_legacy.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x
        } if isinstance(pr_legacy, pd.DataFrame) and not pr_legacy.empty else set()
    except Exception:
        pr_legacy = pd.DataFrame()

    if not base.empty:
        tipo = base.get("tipo_docente", pd.Series("Propio", index=base.index)).fillna("Propio").astype(str).str.strip().str.casefold()
        claves = base.get("cuil", pd.Series(index=base.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
        base = base[(tipo.ne("prestado") & claves.isin(claves_doc)) | (tipo.eq("prestado") & claves.isin(claves_prest))].copy()

    # Reexpresa la dotación propia como foto de cierre.
    if isinstance(df_doc, pd.DataFrame) and not df_doc.empty and not base.empty:
        claves_df_doc = df_doc.get("cuil", pd.Series(index=df_doc.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
        for idx, r in base.iterrows():
            if str(r.get("tipo_docente", "Propio")).strip().casefold() == "prestado":
                base.at[idx, "estado_operativo_periodo"] = "Prestado vigente al cierre del período"
                continue
            k = _clave_cuil(r.get("cuil"))
            sub = df_doc[claves_df_doc.eq(k)].copy()
            if sub.empty:
                continue
            hs = _horas_designaciones_v165(sub)
            base.at[idx, "estado_operativo_periodo"] = "Vigente al cierre del período"
            base.at[idx, "designaciones_del_periodo"] = int(len(sub))
            base.at[idx, "designaciones_activas"] = int(len(sub))
            base.at[idx, "horas_activas"] = round(hs, 2)
            base.at[idx, "horas_registradas_periodo"] = round(hs, 2)
            partes = []
            for _, d in sub.iterrows():
                partes.append(
                    f"{d.get('cargo','')} - {d.get('dedicacion','')} - {float(pd.to_numeric(d.get('horas'), errors='coerce') or 0):g} hs - "
                    f"{d.get('tipo_designacion','')} - Ad Honorem: {d.get('ad_honorem','No')} - Estado al cierre: Vigente"
                )
            base.at[idx, "detalle_designaciones"] = " | ".join(partes)

    return base.reset_index(drop=True)


# --- entry l. 40113
_get_docentes_v182_pre_v183 = get_docentes


# --- entry l. 40115-40130
def get_docentes():
    df = _get_docentes_v182_pre_v183()
    df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    p = get_periodo_abierto()
    if df.empty or not p or not es_periodo_historico_contexto_v182(p.get("id")):
        return df
    plantel = get_plantel_periodo(p["id"])
    claves = {
        x for x in plantel.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(_clave_cuil).tolist() if x
    } if isinstance(plantel, pd.DataFrame) and not plantel.empty else set()
    kdf = df.get("cuil", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
    df["estado_periodo_abierto"] = [
        "Vigente al cierre del período en contexto" if k in claves else "Fuera de la dotación al cierre del período en contexto"
        for k in kdf
    ]
    return df


# --- entry l. 40805-40827
def _comisiones_contexto_alumnos_v188(periodo_id):
    """Comisiones que integran el cálculo de alumnos del período.

    - período actual: solo comisiones activas;
    - período histórico: todas las comisiones del período, porque el cierre técnico
      puede haberlas dejado como Finalizadas aunque integraban la foto al cierre.
    """
    try:
        historico = bool(es_periodo_historico_contexto_v182(int(periodo_id)))
    except Exception:
        historico = False
    try:
        df = get_comisiones(periodo_id=int(periodo_id), solo_activas=not historico)
    except Exception:
        df = pd.DataFrame()
    df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if df.empty:
        return df
    # Excluye solamente estados explícitamente eliminados/cancelados si existieran.
    if "estado" in df.columns:
        est = df["estado"].fillna("").astype(str).str.strip().str.casefold()
        df = df[~est.str.contains(r"elimin|cancel", regex=True, na=False)].copy()
    return df.reset_index(drop=True)


# --- entry l. 40830-40884
def _total_inscriptos_comisiones_periodo_v188(periodo_id):
    """Suma los inscriptos de las comisiones consideradas abiertas/en foto del período.

    Respeta la fuente por materia/código de v123 y evita duplicar una comisión
    multicódigo tomando una sola vez su total_comision.
    """
    df_com = _comisiones_contexto_alumnos_v188(periodo_id)
    if df_com.empty or "id" not in df_com.columns:
        return 0, 0

    ids = set(
        pd.to_numeric(df_com["id"], errors="coerce").dropna().astype(int).tolist()
    )
    if not ids:
        return 0, 0

    total = 0
    ids_contados = set()
    try:
        df_ins = get_inscriptos_comisiones_periodo(int(periodo_id))
    except Exception:
        df_ins = pd.DataFrame()

    if isinstance(df_ins, pd.DataFrame) and not df_ins.empty and "comision_id" in df_ins.columns:
        aux = df_ins.copy()
        aux["_cid_v188"] = pd.to_numeric(aux["comision_id"], errors="coerce")
        aux = aux[aux["_cid_v188"].isin(ids)].copy()
        if not aux.empty:
            if "total_comision" in aux.columns:
                por_com = (
                    aux.groupby("_cid_v188", dropna=True)["total_comision"]
                    .max()
                )
            else:
                por_com = (
                    aux.groupby("_cid_v188", dropna=True)["cantidad"]
                    .sum()
                )
            for cid, cantidad in por_com.items():
                try:
                    cid_int = int(cid)
                    total += int(pd.to_numeric(cantidad, errors="coerce") or 0)
                    ids_contados.add(cid_int)
                except Exception:
                    pass

    # Fallback para comisiones legacy que no hayan producido filas por materia.
    for cid in sorted(ids - ids_contados):
        try:
            ins = get_inscriptos_comision(int(cid)) or {}
            total += int(pd.to_numeric(ins.get("cantidad", 0), errors="coerce") or 0)
        except Exception:
            pass

    return int(total), int(len(ids))


# --- entry l. 40887-40905
def _alumnos_por_docente_periodo_v188(periodo_id, metricas=None):
    """Alumnos por docente = suma de inscriptos / docentes activos docentes."""
    if metricas is None:
        try:
            metricas = dict(get_metricas_analisis_periodo(int(periodo_id)) or {})
        except Exception:
            metricas = {}
    else:
        metricas = dict(metricas or {})

    total_alumnos, comisiones_consideradas = _total_inscriptos_comisiones_periodo_v188(periodo_id)
    docentes = int(metricas.get("docentes_activos", 0) or 0)
    ratio = round(float(total_alumnos) / float(docentes), 2) if docentes > 0 else 0.0
    return {
        "alumnos_inscriptos": int(total_alumnos),
        "docentes_activos_calculo": int(docentes),
        "comisiones_consideradas": int(comisiones_consideradas),
        "alumnos_por_docente": float(ratio),
    }


# --- entry l. 40909
_inicio_datos_tablero_cache_pre_v188 = _inicio_datos_tablero_cache


# --- entry l. 40912-40922
def _inicio_datos_tablero_cache(periodo_id, institucion_id, departamento_id, hoy_iso):
    datos = dict(
        _inicio_datos_tablero_cache_pre_v188(
            periodo_id, institucion_id, departamento_id, hoy_iso
        ) or {}
    )
    alumnos = _alumnos_por_docente_periodo_v188(
        periodo_id, metricas=datos.get("metricas", {})
    )
    datos.update(alumnos)
    return datos


# --- entry l. 40925-41018
def _indicadores_comparacion_periodo_v188(periodo_id):
    """Los KPI de Inicio, reconstruidos con el mismo contexto temporal del período."""
    metricas = dict(get_metricas_analisis_periodo(int(periodo_id)) or {})
    historico = bool(metricas.get("lectura_historica_periodo"))

    df_com = _comisiones_contexto_alumnos_v188(periodo_id)
    total_com = int(len(df_com)) if isinstance(df_com, pd.DataFrame) else 0
    ids_com = set(
        pd.to_numeric(df_com.get("id", pd.Series(dtype=float)), errors="coerce")
        .dropna().astype(int).tolist()
    ) if isinstance(df_com, pd.DataFrame) and not df_com.empty else set()

    try:
        df_asig = get_asignaciones_comisiones_periodo(int(periodo_id))
    except Exception:
        df_asig = pd.DataFrame()
    df_asig = df_asig.copy() if isinstance(df_asig, pd.DataFrame) else pd.DataFrame()

    pares = pd.DataFrame(columns=["_cid_v188", "_cuil_v188"])
    if not df_asig.empty and "comision_id" in df_asig.columns:
        da = df_asig.copy()
        if not historico and "estado" in da.columns:
            est = da["estado"].fillna("Activa").astype(str).str.strip().str.casefold()
            da = da[est.eq("activa")].copy()
        da["_cid_v188"] = pd.to_numeric(da["comision_id"], errors="coerce")
        if ids_com:
            da = da[da["_cid_v188"].isin(ids_com)].copy()
        da["_cuil_v188"] = da.get(
            "cuil", pd.Series(index=da.index, dtype=str)
        ).fillna("").astype(str).map(_clave_cuil)
        pares = da[
            da["_cid_v188"].notna() & da["_cuil_v188"].astype(str).ne("")
        ][["_cid_v188", "_cuil_v188"]].drop_duplicates()

    cubiertas = int(pares["_cid_v188"].nunique()) if not pares.empty else 0
    cobertura = round(cubiertas * 100.0 / total_com, 1) if total_com else 0.0
    docentes_por_com = round(float(len(pares)) / float(total_com), 2) if total_com else 0.0

    try:
        df_prod = get_docentes_productividad_periodo(int(periodo_id))
        serie_pct = pd.to_numeric(
            df_prod.get("porcentaje_uso", pd.Series(dtype=float)), errors="coerce"
        ).dropna() if isinstance(df_prod, pd.DataFrame) else pd.Series(dtype=float)
        productividad = round(float(serie_pct.mean()), 2) if not serie_pct.empty else 0.0
    except Exception:
        productividad = 0.0

    total_contratadas = float(
        metricas.get(
            "horas_contratadas_totales",
            metricas.get("horas_contratadas", 0),
        ) or 0
    )
    utilizadas = float(
        metricas.get(
            "horas_utilizadas_totales",
            metricas.get("horas_academicas_utilizadas", 0),
        ) or 0
    )
    disponibles = float(
        metricas.get(
            "horas_disponibles_totales",
            max(total_contratadas - utilizadas, 0),
        ) or 0
    )
    exceso = float(
        metricas.get(
            "horas_exceso_totales",
            max(utilizadas - total_contratadas, 0),
        ) or 0
    )

    alumnos = _alumnos_por_docente_periodo_v188(periodo_id, metricas=metricas)

    return {
        "Horas de designación · total": round(total_contratadas, 2),
        "Horas frente a comisión": round(float(metricas.get("horas_comisiones", 0) or 0), 2),
        "Horas no lectivas": round(float(metricas.get("horas_no_lectivas", 0) or 0), 2),
        "Horas investigación + extensión": round(
            float(metricas.get("horas_investigacion", 0) or 0)
            + float(metricas.get("horas_extension", 0) or 0), 2
        ),
        "Horas funciones no docentes": round(float(metricas.get("horas_no_docentes", 0) or 0), 2),
        "Cobertura de comisiones (%)": cobertura,
        "Comisiones cubiertas": cubiertas,
        "Comisiones totales": total_com,
        "Docentes por comisión": docentes_por_com,
        "Productividad promedio (%)": productividad,
        "Horas disponibles": round(disponibles, 2),
        "Exceso global": round(exceso, 2),
        "Alumnos inscriptos": int(alumnos["alumnos_inscriptos"]),
        "Docentes activos": int(metricas.get("docentes_activos", 0) or 0),
        "Alumnos por docente": round(float(alumnos["alumnos_por_docente"]), 2),
    }


# --- entry l. 41021-41038
def _listados_designaciones_informe_v188(periodo_id):
    """Mismas fuentes de dotación funcional que Inicio/Análisis."""
    try:
        metricas = dict(get_metricas_analisis_periodo(int(periodo_id)) or {})
    except Exception:
        metricas = {}
    df_doc = metricas.get("df_desig_docentes_activas", pd.DataFrame())
    df_nd = metricas.get("df_desig_no_docentes_activas", pd.DataFrame())
    df_doc = df_doc.copy() if isinstance(df_doc, pd.DataFrame) else pd.DataFrame()
    df_nd = df_nd.copy() if isinstance(df_nd, pd.DataFrame) else pd.DataFrame()

    for df in [df_doc, df_nd]:
        if not df.empty:
            orden = [c for c in ["nombre_completo", "cuil", "cargo", "dedicacion"] if c in df.columns]
            if orden:
                df.sort_values(orden, kind="stable", inplace=True)

    return df_doc.reset_index(drop=True), df_nd.reset_index(drop=True), metricas


# --- entry l. 41042
_generar_informe_movimiento_docente_word_pre_v188 = generar_informe_movimiento_docente_word_v175


# --- entry l. 41044-41205
def generar_informe_movimiento_docente_word_v175(periodo_nombre, departamento, df_mov_analisis, periodo_id=None):
    data = _generar_informe_movimiento_docente_word_pre_v188(
        periodo_nombre, departamento, df_mov_analisis, periodo_id=periodo_id
    )
    if periodo_id is None:
        return data

    Document = _obtener_document_python_docx()
    from docx.shared import Pt, RGBColor
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
    from docx.enum.text import WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document(BytesIO(data))

    def _shade_v188(celda, fill):
        tcPr = celda._tc.get_or_add_tcPr()
        shd = tcPr.find(qn("w:shd"))
        if shd is None:
            shd = OxmlElement("w:shd")
            tcPr.append(shd)
        shd.set(qn("w:fill"), str(fill).replace("#", "").upper())

    def _cell_v188(celda, valor, bold=False, color=None, size=5.8):
        celda.text = ""
        p = celda.paragraphs[0]
        r = p.add_run(str(valor if valor not in [None, ""] else "—"))
        r.bold = bool(bold)
        r.font.name = "Arial"
        r.font.size = Pt(size)
        if color:
            r.font.color.rgb = RGBColor.from_string(str(color).replace("#", "").upper())
        celda.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    def _fecha_v188(valor):
        try:
            d = pd.to_datetime(valor, errors="coerce")
            return d.strftime("%d/%m/%Y") if pd.notna(d) else "—"
        except Exception:
            return str(valor or "—")

    def _estado_vigencia_v188(r):
        estado = (
            limpiar_texto_tabla(r.get("estado_analisis", ""))
            or limpiar_texto_tabla(r.get("estado", ""))
            or "—"
        )
        return f"{estado} · {_fecha_v188(r.get('fecha_desde'))} a {_fecha_v188(r.get('fecha_hasta'))}"

    def _tabla_v188(df, no_docente=False):
        if df is None or df.empty:
            doc.add_paragraph("No hay designaciones registradas para este bloque en el período.")
            return
        headers = [
            "Persona", "CUIL", "Cargo", "Dedicación", "Hs",
            "Tipo", "Condición", "Estado / vigencia",
        ]
        if no_docente:
            headers.append("Función")
        t = doc.add_table(rows=1, cols=len(headers))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, h in enumerate(headers):
            _cell_v188(t.rows[0].cells[j], h, bold=True, color="FFFFFF", size=5.6)
            _shade_v188(t.rows[0].cells[j], "8064A2" if no_docente else "4472C4")

        for _, r in df.iterrows():
            cells = t.add_row().cells
            nombre = (
                limpiar_texto_tabla(r.get("nombre_completo", ""))
                or limpiar_texto_tabla(r.get("docente", ""))
                or str(r.get("cuil") or "")
            )
            ah = "Ad Honórem" if _es_ad_honorem_v162(r.get("ad_honorem", "")) else "Rentada"
            valores = [
                nombre,
                str(r.get("cuil") or ""),
                limpiar_texto_tabla(r.get("cargo", "")),
                limpiar_texto_tabla(r.get("dedicacion", "")),
                f"{float(pd.to_numeric(r.get('horas'), errors='coerce') or 0):g}",
                limpiar_texto_tabla(r.get("tipo_designacion", "")),
                ah,
                _estado_vigencia_v188(r),
            ]
            if no_docente:
                valores.append(
                    _texto_funcion_no_docente_limpio_v164(
                        r.get("texto_funcion_no_docente", "")
                    ) or "SIN FUNCIONES CARGADAS"
                )
            for j, val in enumerate(valores):
                _cell_v188(cells[j], val, size=5.35 if no_docente else 5.55)
        doc.add_paragraph().paragraph_format.space_after = Pt(1)

    # Busca el resumen individual que v178 dejó al final.
    resumen_p = next(
        (p for p in doc.paragraphs if p.text.strip() == "9. Resumen individual del plantel docente"),
        None,
    )
    if resumen_p is None:
        salida = BytesIO()
        doc.save(salida)
        return salida.getvalue()

    df_doc, df_nd, metricas = _listados_designaciones_informe_v188(periodo_id)

    body = doc._element.body
    sectPr = body.sectPr
    pos_inicio_nuevo = list(body).index(sectPr)

    doc.add_heading("9. Plantel y designaciones del período", level=1)
    doc.add_paragraph(
        "Listado previo al resumen individual. Se separan las designaciones docentes "
        "de las destinadas a funciones no docentes, usando la misma foto del período "
        "que se presenta en Inicio y Análisis."
    )

    cant_doc = int(len(df_doc))
    pers_doc = int(
        df_doc.get("cuil", pd.Series(dtype=str)).fillna("").astype(str)
        .map(_clave_cuil).replace("", pd.NA).dropna().nunique()
    ) if not df_doc.empty else 0
    doc.add_heading(
        f"9.1 Designaciones docentes del período ({cant_doc} designación/es · {pers_doc} persona/s)",
        level=2,
    )
    _tabla_v188(df_doc, no_docente=False)

    cant_nd = int(len(df_nd))
    pers_nd = int(
        df_nd.get("cuil", pd.Series(dtype=str)).fillna("").astype(str)
        .map(_clave_cuil).replace("", pd.NA).dropna().nunique()
    ) if not df_nd.empty else 0
    doc.add_heading(
        f"9.2 Funciones no docentes del período ({cant_nd} designación/es · {pers_nd} persona/s)",
        level=2,
    )
    _tabla_v188(df_nd, no_docente=True)

    # El resumen individual debe seguir empezando en una página nueva.
    p_break = doc.add_paragraph()
    p_break.add_run().add_break(WD_BREAK.PAGE)

    # Los elementos recién creados quedaron al final: se mueven completos antes
    # del resumen individual, preservando tablas y formato.
    pos_fin_nuevo = list(body).index(sectPr)
    nuevos = list(body)[pos_inicio_nuevo:pos_fin_nuevo]
    for elem in nuevos:
        body.remove(elem)

    idx_destino = list(body).index(resumen_p._p)
    for elem in nuevos:
        body.insert(idx_destino, elem)
        idx_destino += 1

    resumen_p.text = "10. Resumen individual del plantel docente"

    salida = BytesIO()
    doc.save(salida)
    salida.seek(0)
    return salida.getvalue()


# --- entry l. 41211-41224
def _copiar_resultado_cache_v191(valor):
    if isinstance(valor, pd.DataFrame):
        return valor.copy(deep=True)
    if isinstance(valor, pd.Series):
        return valor.copy(deep=True)
    if isinstance(valor, dict):
        return {k: _copiar_resultado_cache_v191(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_copiar_resultado_cache_v191(v) for v in valor]
    if isinstance(valor, tuple):
        return tuple(_copiar_resultado_cache_v191(v) for v in valor)
    if isinstance(valor, set):
        return set(valor)
    return valor


# --- entry l. 41227-41237
def _scope_rendimiento_v191():
    try:
        inst = int(_pg_current_inst_id() or 0) if USE_POSTGRESQL else 0
    except Exception:
        inst = 0
    try:
        dep = int(_pg_current_dep_id() or 0) if USE_POSTGRESQL else 0
    except Exception:
        dep = 0
    version = int(st.session_state.get("_perf_data_version_v191", 0) or 0)
    return str(DATABASE_URL), inst, dep, version


# --- entry l. 41240-41252
def invalidar_cache_rendimiento_v191(motivo="actualización"):
    """La próxima lectura ve los datos nuevos sin limpiar todos los cachés globales."""
    try:
        st.session_state["_perf_data_version_v191"] = int(
            st.session_state.get("_perf_data_version_v191", 0) or 0
        ) + 1
        st.session_state["_perf_ultima_invalidacion_v191"] = {
            "motivo": str(motivo or "actualización"),
            "fecha": datetime.now().strftime("%H:%M:%S"),
            "version": int(st.session_state["_perf_data_version_v191"]),
        }
    except Exception:
        pass


# --- entry l. 41256
_get_docentes_pre_v191 = get_docentes


# --- entry l. 41258-41259
def _get_docentes_cache_v191(db_url, inst, dep, version):
    return _get_docentes_pre_v191()


# --- entry l. 41260-41262
def get_docentes():
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(_get_docentes_cache_v191(db_url, inst, dep, version))


# --- entry l. 41265
_get_designaciones_pre_v191 = get_designaciones


# --- entry l. 41267-41268
def _get_designaciones_cache_v191(periodo_id, db_url, inst, dep, version):
    return _get_designaciones_pre_v191(periodo_id)


# --- entry l. 41269-41273
def get_designaciones(periodo_id=None):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _get_designaciones_cache_v191(periodo_id, db_url, inst, dep, version)
    )


# --- entry l. 41276
_get_plantel_periodo_pre_v191 = get_plantel_periodo


# --- entry l. 41278-41279
def _get_plantel_periodo_cache_v191(periodo_id, db_url, inst, dep, version):
    return _get_plantel_periodo_pre_v191(periodo_id)


# --- entry l. 41280-41284
def get_plantel_periodo(periodo_id):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _get_plantel_periodo_cache_v191(int(periodo_id), db_url, inst, dep, version)
    )


# --- entry l. 41287
_get_inv_doc_pre_v191 = get_investigacion_docente


# --- entry l. 41289-41293
def _get_inv_doc_cache_v191(cuil, periodo_id, incluir_bajas, todos_departamentos, db_url, inst, dep, version):
    return _get_inv_doc_pre_v191(
        cuil=cuil, periodo_id=periodo_id,
        incluir_bajas=bool(incluir_bajas), todos_departamentos=bool(todos_departamentos)
    )


# --- entry l. 41294-41301
def get_investigacion_docente(cuil=None, periodo_id=None, incluir_bajas=False, todos_departamentos=False):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _get_inv_doc_cache_v191(
            cuil, periodo_id, bool(incluir_bajas), bool(todos_departamentos),
            db_url, inst, dep, version
        )
    )


# --- entry l. 41304
_get_ext_doc_pre_v191 = get_extension_docente


# --- entry l. 41306-41310
def _get_ext_doc_cache_v191(cuil, periodo_id, incluir_bajas, todos_departamentos, db_url, inst, dep, version):
    return _get_ext_doc_pre_v191(
        cuil=cuil, periodo_id=periodo_id,
        incluir_bajas=bool(incluir_bajas), todos_departamentos=bool(todos_departamentos)
    )


# --- entry l. 41311-41318
def get_extension_docente(cuil=None, periodo_id=None, incluir_bajas=False, todos_departamentos=False):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _get_ext_doc_cache_v191(
            cuil, periodo_id, bool(incluir_bajas), bool(todos_departamentos),
            db_url, inst, dep, version
        )
    )


# --- entry l. 41321
_get_inscriptos_periodo_pre_v191 = get_inscriptos_comisiones_periodo


# --- entry l. 41323-41324
def _get_inscriptos_periodo_cache_v191(periodo_id, db_url, inst, dep, version):
    return _get_inscriptos_periodo_pre_v191(int(periodo_id))


# --- entry l. 41325-41329
def get_inscriptos_comisiones_periodo(periodo_id):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _get_inscriptos_periodo_cache_v191(int(periodo_id), db_url, inst, dep, version)
    )


# --- entry l. 41332
_get_prod_periodo_pre_v191 = get_docentes_productividad_periodo


# --- entry l. 41334-41335
def _get_prod_periodo_cache_v191(periodo_id, db_url, inst, dep, version):
    return _get_prod_periodo_pre_v191(int(periodo_id))


# --- entry l. 41336-41340
def get_docentes_productividad_periodo(periodo_id):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _get_prod_periodo_cache_v191(int(periodo_id), db_url, inst, dep, version)
    )


# --- entry l. 41345-41502
def completar_bajas_designaciones_inferidas_v205(periodo_id, df_movimientos):
    """Completa SOLO la vista de Análisis con bajas deducibles por vigencia real.

    No inserta ni modifica filas de ``movimientos``. La fuente histórica sigue intacta.

    v207 restringe esta compatibilidad a ``fecha_finalizacion_efectiva``.
    ``fecha_hasta`` sola ya no alcanza para inferir una baja, porque puede provenir
    de una carga histórica errónea o de un vencimiento contractual. Las nuevas
    correcciones de fecha_hasta que implican una baja generan su movimiento canónico
    al momento de guardarse.

    Si ya existe un movimiento explícito de baja que identifica esa misma designación,
    no se agrega la fila inferida. Los vencimientos normales en el último día del
    período no se consideran bajas y las finalizaciones futuras tampoco.
    """
    base = df_movimientos.copy() if isinstance(df_movimientos, pd.DataFrame) else pd.DataFrame()
    conn = get_conn()
    try:
        df = pd.read_sql("""
            SELECT
                d.id,
                d.periodo_id,
                p.nombre AS periodo,
                p.fecha_inicio AS periodo_inicio,
                p.fecha_fin AS periodo_fin,
                d.cuil,
                CASE
                    WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                    WHEN doc.nombre IS NOT NULL THEN doc.nombre
                    ELSE d.cuil
                END AS nombre_completo,
                d.cargo,
                d.dedicacion,
                d.horas,
                d.tipo_designacion,
                COALESCE(d.ad_honorem, 'No') AS ad_honorem,
                COALESCE(d.funcion_no_docente, 0) AS funcion_no_docente,
                d.fecha_desde,
                d.fecha_hasta,
                d.fecha_finalizacion_efectiva,
                d.estado
            FROM designaciones d
            LEFT JOIN periodos p ON p.id = d.periodo_id
            LEFT JOIN docentes doc ON doc.cuil = d.cuil
            WHERE d.periodo_id = ?
            ORDER BY d.id
        """, conn, params=[int(periodo_id)])
    finally:
        conn.close()

    if df.empty:
        return base

    # Bajas explícitas ya registradas en el período. Se intenta asociarlas a la
    # designación por CUIL + foto contractual para no duplicar una baja real.
    explicitas = base.copy() if not base.empty else pd.DataFrame()
    if not explicitas.empty and "tipo_movimiento" in explicitas.columns:
        explicitas = explicitas[
            explicitas["tipo_movimiento"].fillna("").astype(str).map(_evento_es_baja_designacion)
        ].copy()
    else:
        explicitas = pd.DataFrame()

    def _movimiento_explicito_coincide(row_desig):
        if explicitas.empty:
            return False
        cuil = str(row_desig.get("cuil") or "").strip()
        sub = explicitas[explicitas.get("cuil", pd.Series(index=explicitas.index, dtype=str)).fillna("").astype(str).str.strip().eq(cuil)]
        if sub.empty:
            return False
        cargo = limpiar_texto_tabla(row_desig.get("cargo", "")).lower()
        dedic = limpiar_texto_tabla(row_desig.get("dedicacion", "")).lower()
        tipo = limpiar_texto_tabla(row_desig.get("tipo_designacion", "")).lower()
        hs = _hora_numero(row_desig.get("horas", 0))
        hs_tokens = {f"{hs:g} hs", f"{int(hs)} hs" if float(hs).is_integer() else f"{hs:g} hs"}
        for _, mov in sub.iterrows():
            texto = _texto_row_movimiento(mov, columnas=["detalle", "observaciones"]).lower()
            if cargo and cargo not in texto:
                continue
            if dedic and dedic not in texto:
                continue
            if tipo and tipo not in texto:
                continue
            if hs > 0 and not any(tok.lower() in texto for tok in hs_tokens):
                continue
            return True
        # Si solo hay una designación candidata del CUIL y una baja explícita,
        # alcanza para evitar duplicarla aunque el detalle histórico sea pobre.
        try:
            candidatas_cuil = df[df["cuil"].fillna("").astype(str).str.strip().eq(cuil)]
            if len(candidatas_cuil) == 1 and len(sub) >= 1:
                return True
        except Exception:
            pass
        return False

    hoy = pd.Timestamp(date.today())
    filas = []
    for _, r in df.iterrows():
        fi = _fecha_a_timestamp_seguro(r.get("periodo_inicio"))
        ff = _fecha_a_timestamp_seguro(r.get("periodo_fin"))
        fe_efectiva = _fecha_a_timestamp_seguro(r.get("fecha_finalizacion_efectiva"))
        # v207: una fecha_hasta histórica por sí sola no prueba una baja real.
        # Solo una finalización efectiva inequívoca puede alimentar esta capa legacy.
        fe = fe_efectiva
        if pd.isna(fe) or pd.isna(ff):
            continue
        # El vencimiento normal al cierre no es una baja de gestión.
        if fe >= ff:
            continue
        if not pd.isna(fi) and fe < fi:
            continue
        # No anticipar bajas que todavía no ocurrieron en el período actual.
        if fe > hoy:
            continue
        if _movimiento_explicito_coincide(r):
            continue

        hs = _hora_numero(r.get("horas", 0))
        es_no_docente = _es_funcion_no_docente_v162(r.get("funcion_no_docente"))
        fecha_txt = fe.date().isoformat()
        detalle = (
            f"{r.get('periodo','')} - Baja inferida por vigencia real. "
            f"Antes: {limpiar_texto_tabla(r.get('cargo',''))} - "
            f"{limpiar_texto_tabla(r.get('dedicacion',''))} - {hs:g} hs - "
            f"{limpiar_texto_tabla(r.get('tipo_designacion',''))} - "
            f"Ad Honorem: {limpiar_texto_tabla(r.get('ad_honorem','No'))}. "
            f"Fecha real de finalización: {fecha_txt}. "
            f"ID designación original: {int(r.get('id'))}."
        )
        filas.append({
            "id": -int(r.get("id")),
            "periodo_id": int(periodo_id),
            "periodo": str(r.get("periodo") or ""),
            "fecha": fecha_txt,
            "tipo_movimiento": "Baja de designación",
            "cuil": str(r.get("cuil") or ""),
            "nombre": str(r.get("nombre_completo") or r.get("cuil") or ""),
            "detalle": detalle,
            "observaciones": "Inferida por Análisis desde la vigencia real de la designación; no existe un movimiento explícito de baja.",
            "horas_variacion": 0.0 if es_no_docente else -abs(float(hs or 0)),
        })

    if not filas:
        return base

    inferidas = pd.DataFrame(filas)
    if base.empty:
        out = inferidas
    else:
        # Alinea columnas sin perder las que pudiera traer una versión histórica.
        cols = list(dict.fromkeys(list(base.columns) + list(inferidas.columns)))
        out = pd.concat([base.reindex(columns=cols), inferidas.reindex(columns=cols)], ignore_index=True)
    try:
        out = out.sort_values(["fecha", "id"], kind="stable", na_position="last").reset_index(drop=True)
    except Exception:
        out = out.reset_index(drop=True)
    return out


# --- entry l. 41505
_get_metricas_pre_v191 = get_metricas_analisis_periodo


# --- entry l. 41507-41508
def _get_metricas_cache_v191(periodo_id, db_url, inst, dep, version):
    return _get_metricas_pre_v191(int(periodo_id))


# --- entry l. 41509-41524
def get_metricas_analisis_periodo(periodo_id):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    datos = _copiar_resultado_cache_v191(
        _get_metricas_cache_v191(int(periodo_id), db_url, inst, dep, version)
    )
    # v205: Análisis no depende exclusivamente de que exista una fila manual en
    # Movimientos. Si la vigencia real demuestra una baja dentro del período,
    # se completa solo la vista analítica, sin escribir ni alterar el historial.
    try:
        if isinstance(datos, dict):
            datos["df_mov"] = completar_bajas_designaciones_inferidas_v205(
                int(periodo_id), datos.get("df_mov")
            )
    except Exception:
        pass
    return datos


# --- entry l. 41527-41723
def completar_bajas_designaciones_desde_baja_docente_v206(periodo_id, df_movimientos):
    """Traduce bajas personales históricas a bajas de designación SOLO para Análisis.

    Motivo:
    versiones anteriores podían registrar la salida del docente como ``Baja de docente``
    aunque operativamente implicara el cese de sus designaciones. Desde v172 Análisis
    excluye las altas/bajas de personas y trabaja por designación, por lo que esos
    registros históricos quedaban invisibles.

    Regla:
    - toma movimientos ``Baja de docente`` del período;
    - busca las designaciones del mismo CUIL en ese período;
    - crea una fila analítica ``Baja de designación`` por cada designación que todavía
      no tenga una baja explícita/inferida identificable;
    - usa la fecha del movimiento personal como fecha de la baja analítica;
    - no modifica ``movimientos`` ni ``designaciones``.
    """
    base = df_movimientos.copy() if isinstance(df_movimientos, pd.DataFrame) else pd.DataFrame()
    if base.empty or "tipo_movimiento" not in base.columns:
        return base

    tipo_norm = base["tipo_movimiento"].fillna("").astype(str).map(
        lambda x: _tipo_movimiento_designacion_normalizado(x)
    )
    bajas_doc = base[tipo_norm.eq(_tipo_movimiento_designacion_normalizado("Baja de docente"))].copy()
    if bajas_doc.empty:
        return base

    # Período para validar que la fecha personal realmente corresponda al intervalo.
    conn = get_conn()
    try:
        df_periodo = pd.read_sql(
            "SELECT id, nombre, fecha_inicio, fecha_fin FROM periodos WHERE id=? LIMIT 1",
            conn, params=[int(periodo_id)]
        )
        cuiles = sorted({
            str(x).strip() for x in bajas_doc.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).tolist()
            if str(x).strip()
        })
        if not cuiles:
            return base
        placeholders = ",".join(["?"] * len(cuiles))
        df_des = pd.read_sql(f"""
            SELECT d.id, d.periodo_id, d.cuil, d.cargo, d.dedicacion, d.horas,
                   d.tipo_designacion, COALESCE(d.ad_honorem,'No') AS ad_honorem,
                   COALESCE(d.funcion_no_docente,0) AS funcion_no_docente,
                   d.fecha_desde, d.fecha_hasta, d.fecha_finalizacion_efectiva,
                   d.estado
            FROM designaciones d
            WHERE d.periodo_id=? AND d.cuil IN ({placeholders})
            ORDER BY d.cuil, d.id
        """, conn, params=[int(periodo_id)] + cuiles)
    finally:
        conn.close()

    if df_periodo.empty or df_des.empty:
        return base

    fi = _fecha_a_timestamp_seguro(df_periodo.iloc[0].get("fecha_inicio"))
    ff = _fecha_a_timestamp_seguro(df_periodo.iloc[0].get("fecha_fin"))

    # Designaciones ya cubiertas por una baja de designación explícita o inferida.
    ids_cubiertos = set()
    for _, mov in base.iterrows():
        if not _evento_es_baja_designacion(mov.get("tipo_movimiento", "")):
            continue
        texto = _texto_row_movimiento(mov)
        m = re.search(r"ID\s+designaci[oó]n\s+original\s*[:#-]?\s*(\d+)", texto, flags=re.I)
        if m:
            try:
                ids_cubiertos.add(int(m.group(1)))
            except Exception:
                pass

    # v209: una baja legacy sin ID también puede cubrir inequívocamente una
    # designación. Esto evita que la compatibilidad de Baja de docente agregue
    # una segunda fila cuando la baja de designación ya estaba tenida en cuenta.
    bajas_designacion_base = base[
        base["tipo_movimiento"].fillna("").astype(str).map(_evento_es_baja_designacion)
    ].copy() if (not base.empty and "tipo_movimiento" in base.columns) else pd.DataFrame()

    def _baja_base_cubre_v209(row_des, fecha_ref):
        if bajas_designacion_base.empty:
            return False
        did = int(row_des.get("id"))
        cuil = str(row_des.get("cuil") or "").strip()
        sub_b = bajas_designacion_base[
            bajas_designacion_base.get("cuil", pd.Series(index=bajas_designacion_base.index, dtype=str))
            .fillna("").astype(str).str.strip().eq(cuil)
        ]
        if sub_b.empty:
            return False
        cargo = limpiar_texto_tabla(row_des.get("cargo", "")).casefold()
        dedic = limpiar_texto_tabla(row_des.get("dedicacion", "")).casefold()
        tipo = limpiar_texto_tabla(row_des.get("tipo_designacion", "")).casefold()
        hs = float(_hora_numero(row_des.get("horas", 0)) or 0)
        for _, mov in sub_b.iterrows():
            txt = _texto_row_movimiento(mov).casefold()
            mid = re.search(r"ID\s+designaci[oó]n\s+original\s*[:#=-]?\s*(\d+)", txt, flags=re.I)
            if mid:
                try:
                    if int(mid.group(1)) == did:
                        return True
                except Exception:
                    pass
            fmov = None
            mf = re.search(r"fecha\s+efectiva\s+de\s+baja\s*:\s*(\d{4}-\d{2}-\d{2})", txt, flags=re.I)
            if mf:
                fmov = _fecha_a_timestamp_seguro(mf.group(1))
            if fmov is None or pd.isna(fmov):
                fmov = _fecha_a_timestamp_seguro(mov.get("fecha"))
            if fecha_ref is not None and not pd.isna(fecha_ref) and not pd.isna(fmov) and fmov.date() != fecha_ref.date():
                continue
            contrato_ok = (not cargo or cargo in txt) and (not dedic or dedic in txt) and (not tipo or tipo in txt)
            if hs > 0:
                tokens = {f"{hs:g} hs".casefold()}
                if float(hs).is_integer():
                    tokens.add(f"{int(hs)} hs".casefold())
                contrato_ok = contrato_ok and any(tok in txt for tok in tokens)
            if contrato_ok:
                return True
        # Asociación segura cuando hay una sola designación del CUIL y una sola baja.
        try:
            des_cuil = df_des[df_des["cuil"].fillna("").astype(str).str.strip().eq(cuil)]
            if len(des_cuil) == 1 and len(sub_b) == 1:
                return True
        except Exception:
            pass
        return False

    filas = []
    for _, baja in bajas_doc.iterrows():
        cuil = str(baja.get("cuil") or "").strip()
        if not cuil:
            continue
        fecha_mov = _fecha_a_timestamp_seguro(baja.get("fecha"))
        if pd.isna(fecha_mov):
            # Sin fecha no se puede afirmar en qué período ocurrió la baja.
            continue
        if not pd.isna(fi) and fecha_mov < fi:
            continue
        if not pd.isna(ff) and fecha_mov > ff:
            continue

        sub = df_des[df_des["cuil"].fillna("").astype(str).str.strip().eq(cuil)].copy()
        if sub.empty:
            continue

        for _, r in sub.iterrows():
            did = int(r.get("id"))
            if did in ids_cubiertos:
                continue
            if _baja_base_cubre_v209(r, fecha_mov):
                ids_cubiertos.add(did)
                continue

            hs = _hora_numero(r.get("horas", 0))
            es_no_docente = _es_funcion_no_docente_v162(r.get("funcion_no_docente"))
            detalle = (
                f"{df_periodo.iloc[0].get('nombre','')} - Baja de designación reconstruida desde una "
                f"Baja de docente histórica. Antes: {limpiar_texto_tabla(r.get('cargo',''))} - "
                f"{limpiar_texto_tabla(r.get('dedicacion',''))} - {hs:g} hs - "
                f"{limpiar_texto_tabla(r.get('tipo_designacion',''))} - "
                f"Ad Honorem: {limpiar_texto_tabla(r.get('ad_honorem','No'))}. "
                f"Fecha registrada de baja del docente: {fecha_mov.date().isoformat()}. "
                f"ID designación original: {did}."
            )
            filas.append({
                "id": -(100000000 + did),
                "periodo_id": int(periodo_id),
                "periodo": str(df_periodo.iloc[0].get("nombre") or ""),
                "fecha": fecha_mov.date().isoformat(),
                "tipo_movimiento": "Baja de designación",
                "cuil": cuil,
                "nombre": str(baja.get("nombre") or cuil),
                "detalle": detalle,
                "observaciones": (
                    "Reconstruida por Análisis a partir de una Baja de docente histórica. "
                    "No se alteró la tabla Movimientos ni la designación."
                ),
                "horas_variacion": 0.0 if es_no_docente else -abs(float(hs or 0)),
            })
            ids_cubiertos.add(did)

    if not filas:
        return base

    extras = pd.DataFrame(filas)
    cols = list(dict.fromkeys(list(base.columns) + list(extras.columns)))
    out = pd.concat(
        [base.reindex(columns=cols), extras.reindex(columns=cols)],
        ignore_index=True
    )
    try:
        return out.sort_values(["fecha", "id"], kind="stable", na_position="last").reset_index(drop=True)
    except Exception:
        return out.reset_index(drop=True)


# --- entry l. 41726
_get_metricas_analisis_periodo_pre_v206 = get_metricas_analisis_periodo


# --- entry l. 41728-41742
def get_metricas_analisis_periodo(periodo_id):
    """v206: completa Análisis con compatibilidad para bajas históricas personales."""
    datos = dict(_get_metricas_analisis_periodo_pre_v206(int(periodo_id)) or {})
    try:
        datos["df_mov"] = completar_bajas_designaciones_desde_baja_docente_v206(
            int(periodo_id), datos.get("df_mov")
        )
    except Exception as exc:
        # No se rompe Análisis si una base legacy tiene una estructura inesperada;
        # se deja el diagnóstico disponible para soporte.
        try:
            st.session_state["_analisis_bajas_v206_error"] = str(exc)
        except Exception:
            pass
    return datos


# --- entry l. 41748
_get_metricas_analisis_periodo_pre_v207 = get_metricas_analisis_periodo


# --- entry l. 41750-41755
def get_metricas_analisis_periodo(periodo_id):
    # v209: la reconciliación física ya no se ejecuta en esta capa v207.
    # La capa final v209 hace una sola reconciliación uno-a-uno antes de leer
    # Movimientos, evitando que dos reconciliadores compitan y creen/eliminar
    # filas en el mismo rerun.
    return dict(_get_metricas_analisis_periodo_pre_v207(int(periodo_id)) or {})


# --- entry l. 41759-42033
def asegurar_movimientos_baja_efectiva_v208(periodo_id):
    """v211: reconcilia hechos de baja efectivos contra Movimientos, sin duplicar.

    Principio rector:
    ``Análisis`` no inventa eventos. Una baja solo llega a Análisis si existe como
    fila física en ``movimientos``. Esta función es únicamente una reparación
    histórica para hechos inequívocos que dejaron evidencia estructurada en
    ``designaciones.fecha_finalizacion_efectiva``.

    La conciliación se hace por día y por docente:
    1. cada designación con fecha_finalizacion_efectiva es un hecho esperado;
    2. se buscan bajas ya registradas ese mismo día y CUIL;
    3. primero se empareja por ID de designación; luego por relación unívoca y,
       solo si hay varias, por firma contractual;
    4. un movimiento legacy emparejado se ADOPTA agregándole el ID de designación
       como metadata, pero no se duplica ni se borra;
    5. únicamente un hecho sin movimiento equivalente genera una nueva
       ``Baja de designación``.

    Si un grupo es ambiguo (varias designaciones y varios movimientos sin una
    correspondencia clara), no se fabrica nada: se deja diagnóstico para revisión.
    """
    pid = int(periodo_id)
    conn = get_conn()
    try:
        df_periodo = pd.read_sql(
            "SELECT id, nombre, fecha_inicio, fecha_fin FROM periodos WHERE id=? LIMIT 1",
            conn, params=[pid]
        )
        if df_periodo.empty:
            return 0
        pr = df_periodo.iloc[0]
        fi = safe_date(pr.get("fecha_inicio"), None)
        ff = safe_date(pr.get("fecha_fin"), None)

        df_des = pd.read_sql("""
            SELECT id, cuil, cargo, dedicacion, horas, tipo_designacion,
                   COALESCE(ad_honorem,'No') AS ad_honorem,
                   COALESCE(funcion_no_docente,0) AS funcion_no_docente,
                   fecha_finalizacion_efectiva
            FROM designaciones
            WHERE periodo_id=?
              AND COALESCE(TRIM(fecha_finalizacion_efectiva),'') <> ''
            ORDER BY id
        """, conn, params=[pid])

        df_mov = pd.read_sql("""
            SELECT id, periodo_id, fecha, tipo_movimiento, cuil, nombre,
                   detalle, observaciones, COALESCE(horas_variacion,0) AS horas_variacion
            FROM movimientos
            WHERE periodo_id=?
            ORDER BY fecha, id
        """, conn, params=[pid])

        cuiles = sorted({str(x or '').strip() for x in df_des.get('cuil', pd.Series(dtype=str)).tolist() if str(x or '').strip()})
        if cuiles:
            placeholders = ",".join(["?"] * len(cuiles))
            df_nom = pd.read_sql(
                f"SELECT cuil, apellido, nombres, nombre FROM docentes WHERE cuil IN ({placeholders})",
                conn, params=cuiles
            )
        else:
            df_nom = pd.DataFrame()

        hoy = date.today()
        hechos = {}
        for _, r in df_des.iterrows():
            try:
                did = int(r.get("id"))
            except Exception:
                continue
            fe = safe_date(r.get("fecha_finalizacion_efectiva"), None)
            if fe is None or fe > hoy:
                continue
            if fi is not None and fe < fi:
                continue
            if ff is not None and fe > ff:
                continue
            item = r.to_dict()
            item["_fe"] = fe
            hechos[did] = item

        if not hechos:
            return 0

        def _texto_mov(m):
            return f"{m.get('detalle','')} {m.get('observaciones','')}"

        def _id_declarado(m):
            txt = _texto_mov(m)
            for patron in (
                r"ID\s+designaci[oó]n\s+original\s*[:#=-]?\s*(\d+)",
                r"\[(?:AUTO_)?V(?:207|208|209|210|211)_DESIGNACION_ID=(\d+)\]",
            ):
                mt = re.search(patron, txt, flags=re.I)
                if mt:
                    try:
                        return int(mt.group(1))
                    except Exception:
                        pass
            return None

        def _fecha_mov(m):
            txt = _texto_mov(m)
            for patron in (
                r"fecha\s+efectiva\s+de\s+baja\s*:\s*(\d{4}-\d{2}-\d{2})",
                r"fecha\s+real\s+de\s+finalizaci[oó]n\s*:\s*(\d{4}-\d{2}-\d{2})",
                r"fecha\s+registrada\s+de\s+baja\s+del\s+docente\s*:\s*(\d{4}-\d{2}-\d{2})",
            ):
                mt = re.search(patron, txt, flags=re.I)
                if mt:
                    f = safe_date(mt.group(1), None)
                    if f is not None:
                        return f
            return safe_date(m.get("fecha"), None)

        def _es_baja(m):
            return _evento_es_baja_designacion(m.get("tipo_movimiento", ""))

        def _score(des, mov):
            txt = _texto_mov(mov).casefold()
            score = 0
            cargo = limpiar_texto_tabla(des.get("cargo", "")).casefold()
            dedic = limpiar_texto_tabla(des.get("dedicacion", "")).casefold()
            tipo = limpiar_texto_tabla(des.get("tipo_designacion", "")).casefold()
            hs = float(_hora_numero(des.get("horas", 0)) or 0)
            if cargo and cargo in txt: score += 5
            if dedic and dedic in txt: score += 5
            if tipo and tipo in txt: score += 3
            if hs > 0:
                toks = {f"{hs:g} hs".casefold()}
                if float(hs).is_integer(): toks.add(f"{int(hs)} hs".casefold())
                if any(t in txt for t in toks): score += 4
            return score

        bajas = [m.to_dict() for _, m in df_mov.iterrows() if _es_baja(m)] if not df_mov.empty else []
        cubiertos = set()
        usados = set()
        adopciones = []
        ambiguos = []

        # Exacto por ID ya registrado.
        for m in bajas:
            try: mid = int(m.get("id"))
            except Exception: continue
            did = _id_declarado(m)
            if did in hechos and did not in cubiertos:
                cubiertos.add(did); usados.add(mid)

        # Conciliación por día + CUIL para hechos legacy sin vínculo explícito.
        grupos_hechos = {}
        for did, des in hechos.items():
            if did in cubiertos: continue
            grupos_hechos.setdefault((str(des.get("cuil") or "").strip(), des.get("_fe")), []).append(did)

        grupos_mov = {}
        for m in bajas:
            try: mid = int(m.get("id"))
            except Exception: continue
            if mid in usados: continue
            f = _fecha_mov(m)
            grupos_mov.setdefault((str(m.get("cuil") or "").strip(), f), []).append(m)

        for clave, dids in grupos_hechos.items():
            movs = [m for m in grupos_mov.get(clave, []) if int(m.get("id")) not in usados]
            dids = [d for d in dids if d not in cubiertos]
            if not dids:
                continue
            if not movs:
                continue

            # Un hecho en ese docente/día: cualquier única baja existente lo cubre.
            if len(dids) == 1:
                did = dids[0]
                # Si existen varias filas, escoger la más parecida; las restantes no
                # se borran. El deduplicador de Análisis solo colapsa equivalencias
                # realmente idénticas o vinculadas al mismo ID.
                mov = max(movs, key=lambda m: (_score(hechos[did], m), -int(m.get("id") or 0)))
                mid = int(mov.get("id"))
                cubiertos.add(did); usados.add(mid); adopciones.append((mid, did))
                continue

            # Varias designaciones el mismo día: matching uno-a-uno solo con firma
            # contractual fuerte y única. Nada de zip por cantidad.
            pendientes = set(dids)
            for mov in sorted(movs, key=lambda m: int(m.get("id") or 0)):
                puntajes = sorted(
                    [(did, _score(hechos[did], mov)) for did in pendientes],
                    key=lambda x: (-x[1], x[0])
                )
                if not puntajes:
                    break
                mejor = puntajes[0][1]
                mejores = [x for x in puntajes if x[1] == mejor]
                if mejor >= 7 and len(mejores) == 1:
                    did = mejores[0][0]
                    mid = int(mov.get("id"))
                    cubiertos.add(did); usados.add(mid); pendientes.remove(did)
                    adopciones.append((mid, did))
            if pendientes and movs:
                ambiguos.append({"cuil": clave[0], "fecha": str(clave[1]), "designaciones": sorted(pendientes), "movimientos": [int(m.get('id')) for m in movs if int(m.get('id')) not in usados]})

        c = conn.cursor()
        adoptados = 0
        # Vincular movimientos legacy ya existentes al ID real. No cambia el evento.
        for mid, did in adopciones:
            dfm = df_mov[df_mov["id"].astype(int).eq(int(mid))]
            if dfm.empty:
                continue
            obs = str(dfm.iloc[0].get("observaciones") or "").strip()
            if re.search(r"ID\s+designaci[oó]n\s+original\s*[:#=-]?\s*%s\b" % did, obs, flags=re.I):
                continue
            marca = f"ID designación original: {did}. [V211_DESIGNACION_ID={did}]"
            obs_nueva = (obs.rstrip(". ") + ". " if obs else "") + "Vinculado por reconciliación histórica v211. " + marca
            c.execute("UPDATE movimientos SET observaciones=? WHERE id=?", (obs_nueva, int(mid)))
            adoptados += int(c.rowcount or 0)

        if adoptados:
            conn.commit()

        nombres = {}
        if isinstance(df_nom, pd.DataFrame) and not df_nom.empty:
            for _, nr in df_nom.iterrows():
                cu = str(nr.get("cuil") or "").strip()
                nom = nombre_completo(str(nr.get("apellido") or ""), str(nr.get("nombres") or ""))
                nombres[cu] = nom or str(nr.get("nombre") or "").strip() or cu

    finally:
        conn.close()

    creados = 0
    # Crear únicamente hechos no cubiertos y no ambiguos.
    ids_ambiguos = {did for g in ambiguos for did in g.get("designaciones", [])}
    for did, des in hechos.items():
        if did in cubiertos or did in ids_ambiguos:
            continue
        fe = des.get("_fe")
        cuil = str(des.get("cuil") or "").strip()
        hs = float(_hora_numero(des.get("horas", 0)) or 0)
        es_nd = _es_funcion_no_docente_v162(des.get("funcion_no_docente"))
        marcador = f"[V211_DESIGNACION_ID={did}]"
        detalle = (
            f"{str(pr.get('nombre') or '')} - Baja de designación. "
            f"Antes: {limpiar_texto_tabla(des.get('cargo',''))} - "
            f"{limpiar_texto_tabla(des.get('dedicacion',''))} - {hs:g} hs - "
            f"{limpiar_texto_tabla(des.get('tipo_designacion',''))} - "
            f"Ad Honorem: {limpiar_texto_tabla(des.get('ad_honorem','No'))}. "
            f"Fecha efectiva de baja: {fe.isoformat()}. "
            f"ID designación original: {did}. {marcador}"
        )
        registrar_movimiento(
            "Baja de designación", cuil, nombres.get(cuil, cuil), detalle,
            f"Movimiento faltante reconstruido por conciliación histórica v211. {marcador}",
            pid, horas_variacion=(0 if es_nd else -abs(hs)), fecha_movimiento=fe,
        )
        creados += 1

    if ambiguos:
        try:
            st.session_state["_reconciliacion_movimientos_ambiguos_v211"] = ambiguos
        except Exception:
            pass
    else:
        try:
            st.session_state.pop("_reconciliacion_movimientos_ambiguos_v211", None)
        except Exception:
            pass

    cambios = int(creados + adoptados)
    if cambios:
        try:
            invalidar_cache_rendimiento_v191("reconciliación histórica de movimientos v211")
        except Exception:
            pass
    return cambios


# --- entry l. 42138-42326
def reparar_bajas_historicas_confirmadas_v214(periodo_id):
    """Normaliza Cetrangolo y Campanella reutilizando movimientos ya existentes.

    No reconstruye una segunda baja si ya existe una válida. Para Campanella se
    conservan dos movimientos originales (uno por designación), se corrige su
    fecha al 19/08/2026 y se eliminan únicamente copias automáticas generadas por
    reconciliadores previos. Para Cetrangolo se adopta su baja original del
    06/08/2026 y se completa la fecha efectiva de la designación.
    """
    try:
        pid = int(periodo_id)
    except Exception:
        return {"designaciones": 0, "movimientos_actualizados": 0, "duplicados_auto_eliminados": 0}

    conn = get_conn()
    stats = {"designaciones": 0, "movimientos_actualizados": 0, "duplicados_auto_eliminados": 0}
    try:
        df_per = pd.read_sql("SELECT id, nombre FROM periodos WHERE id=? LIMIT 1", conn, params=[pid])
        if df_per.empty or str(df_per.iloc[0].get("nombre") or "").strip() != "2026-2":
            return stats

        def _es_auto_mov(row):
            txt = f"{row.get('detalle','')} {row.get('observaciones','')}".casefold()
            return any(x in txt for x in (
                "movimiento faltante reconstruido",
                "reconstruida automáticamente",
                "reconstruida automaticamente",
                "conciliación histórica v211",
                "conciliacion historica v211",
                "[v207_designacion_id=", "[v208_designacion_id=", "[v209_designacion_id=",
                "[v210_designacion_id=", "[v211_designacion_id=",
            ))

        def _score_objetivo(row, cargo, dedicacion, horas, tipo):
            txt = f"{row.get('detalle','')} {row.get('observaciones','')}".casefold()
            score = 0
            if str(cargo).casefold() in txt: score += 5
            if str(dedicacion).casefold() in txt: score += 5
            if str(tipo).casefold() in txt: score += 3
            if re.search(rf"(?<!\d){int(horas)}(?:[\.,]0+)?\s*hs\b", txt, flags=re.I): score += 4
            return score

        def _asegurar_marcador_mov(cur, mov, did, fecha_obj):
            detalle = str(mov.get("detalle") or "").strip()
            obs = str(mov.get("observaciones") or "").strip()
            if not re.search(r"fecha\s+efectiva\s+de\s+baja\s*:\s*\d{4}-\d{2}-\d{2}", detalle, flags=re.I):
                detalle = (detalle.rstrip(". ") + ". " if detalle else "") + f"Fecha efectiva de baja: {fecha_obj}."
            if not re.search(r"ID\s+designaci[oó]n\s+original\s*[:#=-]?\s*%s\b" % int(did), f"{detalle} {obs}", flags=re.I):
                obs = (obs.rstrip(". ") + ". " if obs else "") + f"Vinculado a designación histórica. ID designación original: {int(did)}. [V214_DESIGNACION_ID={int(did)}]"
            cur.execute("UPDATE movimientos SET fecha=?, detalle=?, observaciones=? WHERE id=?", (fecha_obj, detalle, obs, int(mov.get("id"))))
            stats["movimientos_actualizados"] += int(cur.rowcount or 0)

        def _cargar_designacion(cuil, cargo, dedicacion, horas, tipo):
            return pd.read_sql("""
                SELECT id, cuil, cargo, dedicacion, horas, tipo_designacion,
                       fecha_desde, COALESCE(NULLIF(fecha_hasta_prevista,''),fecha_hasta) AS fecha_hasta_limite,
                       fecha_finalizacion_efectiva, motivo_finalizacion
                FROM designaciones
                WHERE periodo_id=? AND TRIM(COALESCE(cuil,''))=TRIM(?)
                  AND LOWER(TRIM(COALESCE(cargo,'')))=LOWER(?)
                  AND LOWER(TRIM(COALESCE(dedicacion,'')))=LOWER(?)
                  AND COALESCE(horas,0)=?
                  AND LOWER(TRIM(COALESCE(tipo_designacion,'')))=LOWER(?)
                ORDER BY id
            """, conn, params=[pid, cuil, cargo, dedicacion, int(horas), tipo])

        cur = conn.cursor()

        # --- Cetrangolo: reutilizar su baja original del 06/08, jamás crear otra. ---
        cet_cuil = "20-30439634-3"
        cet_fecha = "2026-08-06"
        cet_des = _cargar_designacion(cet_cuil, "JTP", "Simple", 10, "Interino")
        if len(cet_des) == 1:
            d = cet_des.iloc[0]
            did = int(d.get("id"))
            movs = pd.read_sql("""
                SELECT id, fecha, tipo_movimiento, detalle, observaciones
                FROM movimientos
                WHERE periodo_id=? AND TRIM(COALESCE(cuil,''))=TRIM(?)
                  AND LOWER(TRIM(COALESCE(tipo_movimiento,''))) IN ('baja de designación','baja de designacion','finalización de designación','finalizacion de designacion')
                ORDER BY id
            """, conn, params=[pid, cet_cuil])
            candidatos = [r.to_dict() for _, r in movs.iterrows() if str(r.get("fecha") or "")[:10] == cet_fecha and _score_objetivo(r, "JTP", "Simple", 10, "Interino") >= 7]
            if candidatos:
                originales = [m for m in candidatos if not _es_auto_mov(m)]
                elegido = (originales or candidatos)[0]
                motivo = str(d.get("motivo_finalizacion") or "").strip()
                nota = "Fecha efectiva vinculada a la Baja de designación histórica ya existente del 2026-08-06."
                motivo_nuevo = motivo if nota in motivo else (motivo.rstrip(". ") + ". " if motivo else "") + nota
                cur.execute("""
                    UPDATE designaciones
                    SET estado='Finalizada', fecha_finalizacion_efectiva=?, motivo_finalizacion=?
                    WHERE id=? AND (COALESCE(TRIM(fecha_finalizacion_efectiva),'')='' OR fecha_finalizacion_efectiva<>?)
                """, (cet_fecha, motivo_nuevo, did, cet_fecha))
                stats["designaciones"] += int(cur.rowcount or 0)
                _asegurar_marcador_mov(cur, elegido, did, cet_fecha)
                elegido_id = int(elegido.get("id"))
                for m in candidatos:
                    if int(m.get("id")) == elegido_id or not _es_auto_mov(m):
                        continue
                    cur.execute("DELETE FROM movimientos WHERE id=?", (int(m.get("id")),))
                    stats["duplicados_auto_eliminados"] += int(cur.rowcount or 0)

        # --- Campanella: dos designaciones, dos movimientos originales, ambos 19/08. ---
        cam_cuil = "20-11076770-7"
        cam_fecha = "2026-08-19"
        objetivos = [
            ("Titular", "Simple", 10, "Concursado"),
            ("Titular", "Parcial", 20, "Interino"),
        ]
        movs_cam = pd.read_sql("""
            SELECT id, fecha, tipo_movimiento, detalle, observaciones
            FROM movimientos
            WHERE periodo_id=? AND TRIM(COALESCE(cuil,''))=TRIM(?)
              AND LOWER(TRIM(COALESCE(tipo_movimiento,''))) IN ('baja de designación','baja de designacion','finalización de designación','finalizacion de designacion')
            ORDER BY id
        """, conn, params=[pid, cam_cuil])
        usados = set()
        vinculados = {}
        for cargo, dedicacion, horas, tipo in objetivos:
            df_d = _cargar_designacion(cam_cuil, cargo, dedicacion, horas, tipo)
            if len(df_d) != 1:
                continue
            d = df_d.iloc[0]
            did = int(d.get("id"))
            candidatos = []
            for _, mr in movs_cam.iterrows():
                m = mr.to_dict()
                mid = int(m.get("id"))
                if mid in usados:
                    continue
                score = _score_objetivo(m, cargo, dedicacion, horas, tipo)
                if score >= 7:
                    candidatos.append((0 if not _es_auto_mov(m) else 1, -score, mid, m))
            if not candidatos:
                continue
            candidatos.sort(key=lambda x: (x[0], x[1], x[2]))
            elegido = candidatos[0][3]
            mid = int(elegido.get("id"))
            usados.add(mid)
            vinculados[did] = mid

            motivo = str(d.get("motivo_finalizacion") or "").strip()
            nota = "Reparación histórica confirmada: designación finalizada el 2026-08-19."
            motivo_nuevo = motivo if nota in motivo else (motivo.rstrip(". ") + ". " if motivo else "") + nota
            cur.execute("""
                UPDATE designaciones
                SET estado='Finalizada', fecha_finalizacion_efectiva=?, motivo_finalizacion=?
                WHERE id=? AND (COALESCE(TRIM(fecha_finalizacion_efectiva),'')='' OR fecha_finalizacion_efectiva<>?)
            """, (cam_fecha, motivo_nuevo, did, cam_fecha))
            stats["designaciones"] += int(cur.rowcount or 0)
            _asegurar_marcador_mov(cur, elegido, did, cam_fecha)

        # Borrar SOLO copias automáticas de Campanella que correspondan a alguna de
        # las dos designaciones ya vinculadas. Los movimientos originales se conservan.
        if vinculados:
            for _, mr in movs_cam.iterrows():
                m = mr.to_dict(); mid = int(m.get("id"))
                if mid in usados or not _es_auto_mov(m):
                    continue
                matches = []
                for cargo, dedicacion, horas, tipo in objetivos:
                    df_d = _cargar_designacion(cam_cuil, cargo, dedicacion, horas, tipo)
                    if len(df_d) != 1:
                        continue
                    did = int(df_d.iloc[0].get("id"))
                    if did not in vinculados:
                        continue
                    if _score_objetivo(m, cargo, dedicacion, horas, tipo) >= 7:
                        matches.append(did)
                if len(matches) == 1:
                    cur.execute("DELETE FROM movimientos WHERE id=?", (mid,))
                    stats["duplicados_auto_eliminados"] += int(cur.rowcount or 0)

        conn.commit()
        cur.close()
    finally:
        conn.close()

    if any(int(v or 0) for v in stats.values()):
        try:
            invalidar_cache_rendimiento_v191("normalización histórica Cetrangolo/Campanella v214")
        except Exception:
            pass
        try:
            limpiar_cache_comisiones_operativas()
        except Exception:
            pass
    return stats


# --- entry l. 42330-42589
def reconciliar_fechas_finalizacion_desde_movimientos_v212(periodo_id):
    """Completa ``fecha_finalizacion_efectiva`` desde bajas históricas inequívocas.

    Esta rutina repara una inconsistencia legacy concreta: en versiones antiguas
    podía quedar una fila física ``Baja de designación`` en ``movimientos`` sin que
    la designación recibiera ``fecha_finalizacion_efectiva``.

    Fuente de verdad para la reparación: el movimiento YA EXISTENTE.
    No crea una baja nueva y no usa ``fecha_hasta`` para inferir eventos.

    Asociación conservadora, en este orden:
    1. ID de designación declarado en detalle/observaciones;
    2. mismo CUIL + período + fecha compatible + firma contractual de ``Antes:``;
    3. solo si para ese CUIL existe una única designación candidata y una única
       baja de designación histórica pendiente, se acepta la relación unívoca.

    Los movimientos ``Baja docente por modificación de asignación`` corresponden
    a bajas en una comisión y se excluyen expresamente: no prueban por sí solos
    que haya terminado una designación.
    """
    try:
        pid = int(periodo_id)
    except Exception:
        return {"actualizadas": 0, "vinculadas": 0, "ambiguas": []}

    # v214: normalizar primero los casos históricos confirmados reutilizando
    # movimientos existentes, sin crear duplicados.
    try:
        reparar_bajas_historicas_confirmadas_v214(pid)
    except Exception:
        pass

    conn = get_conn()
    actualizadas = 0
    vinculadas = 0
    ambiguas = []
    try:
        df_des = pd.read_sql("""
            SELECT id, periodo_id, cuil, cargo, dedicacion, horas, tipo_designacion,
                   fecha_desde, COALESCE(NULLIF(fecha_hasta_prevista,''),fecha_hasta) AS fecha_hasta_limite,
                   fecha_finalizacion_efectiva, fecha_registro_finalizacion, motivo_finalizacion
            FROM designaciones
            WHERE periodo_id=?
              AND COALESCE(TRIM(fecha_finalizacion_efectiva),'') = ''
            ORDER BY cuil, id
        """, conn, params=[pid])

        df_mov = pd.read_sql("""
            SELECT id, periodo_id, fecha, tipo_movimiento, cuil, nombre, detalle, observaciones
            FROM movimientos
            WHERE periodo_id=?
              AND LOWER(TRIM(COALESCE(tipo_movimiento,''))) IN (
                    'baja de designación', 'baja de designacion',
                    'finalización de designación', 'finalizacion de designacion'
              )
            ORDER BY fecha, id
        """, conn, params=[pid])

        if df_des.empty or df_mov.empty:
            return {"actualizadas": 0, "vinculadas": 0, "ambiguas": []}

        def _txt_mov(row):
            return f"{row.get('detalle','')} {row.get('observaciones','')}"

        def _id_mov(row):
            txt = _txt_mov(row)
            for patron in (
                r"ID\s+designaci[oó]n\s+original\s*[:#=-]?\s*(\d+)",
                r"\[(?:AUTO_)?V(?:207|208|209|210|211|212)_DESIGNACION_ID=(\d+)\]",
            ):
                m = re.search(patron, txt, flags=re.I)
                if m:
                    try:
                        return int(m.group(1))
                    except Exception:
                        pass
            return None

        def _fecha_efectiva_mov(row):
            txt = _txt_mov(row)
            for patron in (
                r"fecha\s+efectiva\s+de\s+baja\s*:\s*(\d{4}-\d{2}-\d{2})",
                r"fecha\s+real\s+de\s+finalizaci[oó]n\s*:\s*(\d{4}-\d{2}-\d{2})",
            ):
                m = re.search(patron, txt, flags=re.I)
                if m:
                    f = safe_date(m.group(1), None)
                    if f is not None:
                        return f
            return safe_date(row.get('fecha'), None)

        def _clave_mov_antes(row):
            antes, _ahora = _extraer_antes_ahora(row.get('detalle', ''))
            if antes:
                return _clave_designacion_desde_texto(antes)
            # Algunos movimientos legacy guardaban la foto completa sin / Ahora:.
            txt = str(row.get('detalle') or '')
            if 'Antes:' in txt:
                try:
                    trozo = txt.split('Antes:', 1)[1]
                    trozo = re.split(r"(?:Fecha efectiva|Fecha real|ID designaci[oó]n)", trozo, maxsplit=1, flags=re.I)[0]
                    return _clave_designacion_desde_texto(trozo.strip(' .-/'))
                except Exception:
                    pass
            return None

        def _fecha_compatible(des, fecha):
            if fecha is None:
                return False
            fd = safe_date(des.get('fecha_desde'), None)
            fh = safe_date(des.get('fecha_hasta_limite'), None)
            if fd is not None and fecha < fd:
                return False
            if fh is not None and fecha > fh:
                return False
            return True

        usados_designacion = set()
        usados_movimiento = set()
        pendientes = []

        # Primero: vínculos explícitos por ID.
        for _, mov in df_mov.iterrows():
            mid = int(mov.get('id'))
            did = _id_mov(mov)
            if did is None:
                pendientes.append(mov.to_dict())
                continue
            cand = df_des[df_des['id'].astype(int).eq(int(did))]
            if cand.empty:
                continue
            des = cand.iloc[0]
            if str(des.get('cuil') or '').strip() != str(mov.get('cuil') or '').strip():
                ambiguas.append({"movimiento_id": mid, "motivo": "ID declarado con CUIL distinto"})
                continue
            fe = _fecha_efectiva_mov(mov)
            if not _fecha_compatible(des, fe):
                ambiguas.append({"movimiento_id": mid, "designacion_id": did, "motivo": "fecha fuera de vigencia"})
                continue
            usados_designacion.add(int(did))
            usados_movimiento.add(mid)
            c = conn.cursor()
            motivo = str(des.get('motivo_finalizacion') or '').strip()
            if not motivo:
                motivo = f"Reconstruida desde movimiento histórico Baja de designación ID {mid}."
            c.execute("""
                UPDATE designaciones
                SET estado='Finalizada', fecha_finalizacion_efectiva=?,
                    motivo_finalizacion=?
                WHERE id=? AND COALESCE(TRIM(fecha_finalizacion_efectiva),'')=''
            """, (fe.isoformat(), motivo, int(did)))
            actualizadas += int(c.rowcount or 0)
            c.close()

        # Luego: movimientos legacy sin ID, siempre dentro del mismo CUIL.
        pendientes = [m for m in pendientes if int(m.get('id')) not in usados_movimiento]
        for cuil, grupo_mov in pd.DataFrame(pendientes).groupby('cuil', dropna=False) if pendientes else []:
            cuil_txt = str(cuil or '').strip()
            if not cuil_txt:
                continue
            des_cuil = df_des[df_des['cuil'].fillna('').astype(str).str.strip().eq(cuil_txt)].copy()
            des_cuil = des_cuil[~des_cuil['id'].astype(int).isin(usados_designacion)].copy()
            if des_cuil.empty:
                continue

            movimientos = [r.to_dict() for _, r in grupo_mov.iterrows()]
            # Procesar por fecha para no cruzar bajas de días distintos.
            por_fecha = {}
            for mov in movimientos:
                fe = _fecha_efectiva_mov(mov)
                por_fecha.setdefault(fe, []).append(mov)

            for fe, movs_fecha in por_fecha.items():
                if fe is None:
                    for m in movs_fecha:
                        ambiguas.append({"movimiento_id": int(m.get('id')), "motivo": "fecha de baja inválida"})
                    continue
                candidatas = des_cuil[des_cuil.apply(lambda r: _fecha_compatible(r, fe), axis=1)].copy()
                candidatas = candidatas[~candidatas['id'].astype(int).isin(usados_designacion)].copy()
                if candidatas.empty:
                    continue

                for mov in movs_fecha:
                    mid = int(mov.get('id'))
                    if mid in usados_movimiento:
                        continue
                    clave_mov = _clave_mov_antes(mov)
                    elegida = None
                    if clave_mov is not None:
                        iguales = candidatas[candidatas.apply(
                            lambda r: _clave_designacion_desde_row_designacion(r) == clave_mov,
                            axis=1
                        )]
                        iguales = iguales[~iguales['id'].astype(int).isin(usados_designacion)]
                        if len(iguales) == 1:
                            elegida = iguales.iloc[0]
                        elif len(iguales) > 1:
                            ambiguas.append({"movimiento_id": mid, "cuil": cuil_txt, "fecha": fe.isoformat(), "motivo": "más de una designación con la misma firma contractual"})
                            continue

                    if elegida is None:
                        libres = candidatas[~candidatas['id'].astype(int).isin(usados_designacion)]
                        movs_libres = [m for m in movs_fecha if int(m.get('id')) not in usados_movimiento]
                        # Asociación unívoca de último recurso: una sola baja y una sola designación.
                        if len(libres) == 1 and len(movs_libres) == 1:
                            elegida = libres.iloc[0]
                        else:
                            ambiguas.append({"movimiento_id": mid, "cuil": cuil_txt, "fecha": fe.isoformat(), "motivo": "asociación no unívoca"})
                            continue

                    did = int(elegida.get('id'))
                    motivo = str(elegida.get('motivo_finalizacion') or '').strip()
                    if not motivo:
                        motivo = f"Reconstruida desde movimiento histórico Baja de designación ID {mid}."
                    c = conn.cursor()
                    c.execute("""
                        UPDATE designaciones
                        SET estado='Finalizada', fecha_finalizacion_efectiva=?,
                            motivo_finalizacion=?
                        WHERE id=? AND COALESCE(TRIM(fecha_finalizacion_efectiva),'')=''
                    """, (fe.isoformat(), motivo, did))
                    actualizadas += int(c.rowcount or 0)

                    # Adoptar el movimiento existente: agregar ID para que desde ahora
                    # quede atado inequívocamente a la designación y nunca se duplique.
                    obs = str(mov.get('observaciones') or '').strip()
                    marca = f"ID designación original: {did}. [V212_DESIGNACION_ID={did}]"
                    if not re.search(r"ID\s+designaci[oó]n\s+original\s*[:#=-]?\s*%s\b" % did, obs, flags=re.I):
                        obs_nueva = (obs.rstrip('. ') + '. ' if obs else '') + "Vinculado por reparación histórica v212. " + marca
                        c.execute("UPDATE movimientos SET observaciones=? WHERE id=?", (obs_nueva, mid))
                        vinculadas += int(c.rowcount or 0)
                    c.close()
                    usados_designacion.add(did)
                    usados_movimiento.add(mid)

        if actualizadas or vinculadas:
            conn.commit()

    finally:
        conn.close()

    if actualizadas or vinculadas:
        try:
            invalidar_cache_rendimiento_v191("fecha efectiva desde movimientos históricos v212")
        except Exception:
            pass
        try:
            limpiar_cache_comisiones_operativas()
        except Exception:
            pass

    try:
        if ambiguas:
            st.session_state['_reparacion_fecha_efectiva_ambiguas_v212'] = ambiguas
        else:
            st.session_state.pop('_reparacion_fecha_efectiva_ambiguas_v212', None)
    except Exception:
        pass

    return {"actualizadas": int(actualizadas), "vinculadas": int(vinculadas), "ambiguas": ambiguas}


# --- entry l. 42592
_get_metricas_analisis_periodo_pre_v208 = get_metricas_analisis_periodo


# --- entry l. 42594-42634
def get_metricas_analisis_periodo(periodo_id):
    """v211: Análisis consume exclusivamente movimientos físicos del sistema.

    Antes de leerlos ejecuta una conciliación conservadora de bajas efectivas
    históricas. Después se relee ``movimientos`` en fresco. No se agregan filas
    sintéticas solo para la vista de Análisis.
    """
    pid = int(periodo_id)
    # v212: primero reparar Designaciones desde movimientos históricos reales.
    # Luego v211 asegura que toda fecha efectiva tenga un movimiento físico.
    try:
        _rep_v212 = reconciliar_fechas_finalizacion_desde_movimientos_v212(pid)
        if int((_rep_v212 or {}).get("actualizadas", 0) or 0):
            st.session_state["_analisis_fechas_efectivas_reparadas_v212"] = int(_rep_v212.get("actualizadas", 0) or 0)
    except Exception as exc:
        try:
            st.session_state["_analisis_reparacion_v212_error"] = str(exc)
        except Exception:
            pass
    try:
        n = int(asegurar_movimientos_baja_efectiva_v208(pid) or 0)
        if n:
            st.session_state["_analisis_movimientos_reconciliados_v211"] = n
        st.session_state.pop("_analisis_bajas_v208_error", None)
    except Exception as exc:
        try:
            st.session_state["_analisis_bajas_v208_error"] = str(exc)
        except Exception:
            pass

    datos = dict(_get_metricas_analisis_periodo_pre_v208(pid) or {})
    try:
        # Fuente única de los indicadores de movimiento: la tabla Movimientos.
        datos["df_mov"] = get_movimientos(pid)
        st.session_state.pop("_analisis_bajas_v208_lectura_error", None)
    except Exception as exc:
        try:
            st.session_state["_analisis_bajas_v208_lectura_error"] = str(exc)
        except Exception:
            pass
    return datos


# --- entry l. 42664
_indicadores_cmp_pre_v191 = _indicadores_comparacion_periodo_v188


# --- entry l. 42666-42667
def _indicadores_cmp_cache_v191(periodo_id, db_url, inst, dep, version):
    return _indicadores_cmp_pre_v191(int(periodo_id))


# --- entry l. 42668-42672
def _indicadores_comparacion_periodo_v188(periodo_id):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _indicadores_cmp_cache_v191(int(periodo_id), db_url, inst, dep, version)
    )


# --- entry l. 42831
_pg_convert_sql_pre_v193 = _pg_convert_sql


# --- entry l. 42834-42835
def _pg_convert_sql_cache_v193(sql_text):
    return _pg_convert_sql_pre_v193(str(sql_text or ""))


# --- entry l. 42837-42838
def _pg_convert_sql(sql):
    return _pg_convert_sql_cache_v193(str(sql or ""))


# --- entry l. 42936
_get_periodos_pre_v193 = get_periodos


# --- entry l. 42938-42939
def _get_periodos_cache_v193(db_url, inst, dep, version):
    return _get_periodos_pre_v193()


# --- entry l. 42940-42944
def get_periodos():
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _get_periodos_cache_v193(db_url, inst, dep, version)
    )


# --- entry l. 42947
_get_hor_com_pre_v193 = get_horarios_comision


# --- entry l. 42949-42950
def _get_hor_com_cache_v193(comision_id, db_url, inst, dep, version):
    return _get_hor_com_pre_v193(comision_id)


# --- entry l. 42951-42955
def get_horarios_comision(comision_id=None):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _get_hor_com_cache_v193(comision_id, db_url, inst, dep, version)
    )


# --- entry l. 42997-42998
def _perf_func_actual_v193():
    return _PERF_FUNC_STACK_V193[-1] if _PERF_FUNC_STACK_V193 else "infraestructura / no atribuida"


# --- entry l. 43032-43048
def _perf_sql_por_func_v192(sql, elapsed):
    if not _perf_habilitado_v191():
        return
    try:
        nombre = _perf_func_actual_v193()
        d = _PERF_SQL_POR_FUNC_V192.setdefault(nombre, {
            "consultas": 0, "segundos": 0.0, "max_ms": 0.0, "ejemplo": "",
        })
        elapsed = float(elapsed or 0)
        d["consultas"] += 1
        d["segundos"] += elapsed
        d["max_ms"] = max(float(d.get("max_ms", 0) or 0), elapsed * 1000.0)
        if not d.get("ejemplo"):
            resumen = " ".join(str(sql or "").strip().split())
            d["ejemplo"] = resumen[:220] + ("..." if len(resumen) > 220 else "")
    except Exception:
        pass


# --- entry l. 43051-43070
def _perf_registrar_db_v192(sql, elapsed, filas=0, origen="db"):
    if not _perf_habilitado_v191():
        return
    global _PERF_DB_COUNT_V192, _PERF_DB_SECONDS_V192, _PERF_DB_ROWS_V192
    try:
        elapsed = float(elapsed or 0)
        filas = int(filas or 0)
        _PERF_DB_COUNT_V192 += 1
        _PERF_DB_SECONDS_V192 += elapsed
        _PERF_DB_ROWS_V192 += max(filas, 0)
        nombre = _perf_func_actual_v193()
        d = _PERF_DB_POR_FUNC_V192.setdefault(nombre, {
            "accesos": 0, "segundos": 0.0, "filas": 0, "max_ms": 0.0,
        })
        d["accesos"] += 1
        d["segundos"] += elapsed
        d["filas"] += max(filas, 0)
        d["max_ms"] = max(float(d.get("max_ms", 0) or 0), elapsed * 1000.0)
    except Exception:
        pass


# --- entry l. 43102
_get_docentes_productividad_periodo_pre_v194 = get_docentes_productividad_periodo


# --- entry l. 43105-43107
def _claves_cuil_df_v194(df):
    from analisis.motor.ref.common.identifiers import _claves_cuil_df_v194 as _b05_core__claves_cuil_df_v194
    return _b05_core__claves_cuil_df_v194(df)


# --- entry l. 43110-43112
def _unir_unicos_v194(df, col):
    from analisis.motor.ref.common.text import _unir_unicos_v194 as _b05_core__unir_unicos_v194
    return _b05_core__unir_unicos_v194(df, col)


# --- entry l. 43115-43152
def _consulta_designaciones_institucionales_bulk_v194(periodo_id, claves):
    if not USE_POSTGRESQL or not claves:
        return pd.DataFrame()
    inst_id = int(_pg_current_inst_id())
    periodo_nombre, anio, semestre = _periodo_equivalente_pg(int(periodo_id))
    placeholders = ", ".join(["%s"] * len(claves))
    params = [inst_id] + list(claves) + [
        int(periodo_id), periodo_nombre, int(anio), int(semestre)
    ]
    return _pg_read_dataframe(f"""
        SELECT
            d.id, d.cuil, d.periodo_id, d.departamento_id,
            COALESCE(dep.nombre, 'Sin departamento') AS departamento,
            p.nombre AS periodo,
            d.cargo, d.dedicacion, d.horas, d.tipo_designacion, d.estado,
            d.fecha_desde, d.fecha_hasta,
            COALESCE(NULLIF(d.fecha_hasta_prevista,''), d.fecha_hasta) AS fecha_hasta_prevista,
            d.fecha_finalizacion_efectiva, d.fecha_registro_finalizacion,
            d.motivo_finalizacion, COALESCE(d.observaciones, '') AS observaciones,
            COALESCE(d.funcion_no_docente, 0) AS funcion_no_docente,
            COALESCE(d.texto_funcion_no_docente, '') AS texto_funcion_no_docente
        FROM designaciones d
        JOIN periodos p ON p.id=d.periodo_id
        LEFT JOIN departamentos dep ON dep.id=d.departamento_id
        WHERE d.institucion_id=%s
          AND p.institucion_id=d.institucion_id
          AND p.departamento_id IS NOT DISTINCT FROM d.departamento_id
          AND regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g') IN ({placeholders})
          AND (d.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))
          AND EXISTS (
              SELECT 1 FROM docentes docx
              WHERE docx.institucion_id=d.institucion_id
                AND docx.departamento_id IS NOT DISTINCT FROM d.departamento_id
                AND regexp_replace(COALESCE(docx.cuil,''), '[^0-9]', '', 'g')=
                    regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g')
          )
        ORDER BY dep.nombre, d.fecha_desde, d.id
    """, params)


# --- entry l. 43155-43232
def _consulta_horarios_bulk_v194(periodo_id, claves, historico=False):
    if not USE_POSTGRESQL or not claves:
        return pd.DataFrame()
    inst_id = int(_pg_current_inst_id())
    periodo_nombre, anio, semestre = _periodo_equivalente_pg(int(periodo_id))
    placeholders = ", ".join(["%s"] * len(claves))

    if historico:
        params = [inst_id] + list(claves) + [
            int(periodo_id), periodo_nombre, int(anio), int(semestre)
        ]
        # Replica _horarios_docente_historicos_v182: no filtra por estado actual
        # y usa los horarios base de la comisión para reconstruir el período.
        return _pg_read_dataframe(f"""
            SELECT DISTINCT
                a.id AS asignacion_id, a.cuil,
                COALESCE(a.estado,'Activa') AS estado_asignacion,
                COALESCE(a.horas_asignadas,0) AS horas_asignadas,
                co.id AS comision_id, co.departamento_id,
                COALESCE(dep.nombre,'') AS departamento_comision,
                h.dia, h.hora_inicio, h.hora_fin, h.horas
            FROM asignaciones_docentes_comision a
            JOIN comisiones co ON co.id=a.comision_id
            JOIN periodos p ON p.id=co.periodo_id
            JOIN horarios_comision h ON h.comision_id=co.id
            LEFT JOIN departamentos dep ON dep.id=co.departamento_id
            WHERE a.institucion_id=%s
              AND regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g') IN ({placeholders})
              AND (co.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))
            ORDER BY a.cuil, h.dia, h.hora_inicio, co.id
        """, params)

    params = list(claves) + [
        inst_id, int(periodo_id), periodo_nombre, int(anio), int(semestre)
    ]
    # Replica _get_horarios_docente_periodo_pg_global, pero para todos los CUIL.
    return _pg_read_dataframe(f"""
        WITH base AS (
            SELECT a.id AS asignacion_id, a.cuil, a.rol, a.comision_id,
                   COALESCE(a.usa_horario_personalizado, FALSE) AS personalizado,
                   co.departamento_id,
                   COALESCE(dep.nombre,'') AS departamento_comision,
                   co.materia_id, p.nombre AS periodo,
                   m.codigo AS codigo_materia, m.asignatura,
                   COALESCE(co.materia_especifica, '') AS materia_especifica,
                   c.nombre AS carrera, c.escuela, co.nombre_comision, co.turno
            FROM asignaciones_docentes_comision a
            JOIN comisiones co ON co.id=a.comision_id
            LEFT JOIN periodos p ON p.id=co.periodo_id
            LEFT JOIN departamentos dep ON dep.id=co.departamento_id
            LEFT JOIN materias m ON m.id=co.materia_id
            LEFT JOIN carreras c ON c.id=m.carrera_id
            WHERE regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g') IN ({placeholders})
              AND co.institucion_id=%s
              AND COALESCE(a.estado,'Activa')='Activa'
              AND COALESCE(co.estado,'Activa')='Activa'
              AND (co.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))
        ), reales AS (
            SELECT b.*, ha.dia, ha.hora_inicio, ha.hora_fin, ha.horas
            FROM base b
            JOIN horarios_asignacion_docente_comision ha ON ha.asignacion_id=b.asignacion_id
            WHERE b.personalizado=TRUE
            UNION ALL
            SELECT b.*, h.dia, h.hora_inicio, h.hora_fin, h.horas
            FROM base b
            JOIN horarios_comision h ON h.comision_id=b.comision_id
            WHERE b.personalizado=FALSE
        )
        SELECT * FROM reales
        ORDER BY a.cuil
    """.replace("ORDER BY a.cuil", """
        ORDER BY cuil,
                 CASE dia WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2
                          WHEN 'Miércoles' THEN 3 WHEN 'Jueves' THEN 4
                          WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6
                          WHEN 'Domingo' THEN 7 ELSE 99 END,
                 hora_inicio, departamento_comision, codigo_materia, nombre_comision
    """), params)


# --- entry l. 43235-43263
def _consulta_horas_brutas_bulk_v194(periodo_id, claves):
    if not USE_POSTGRESQL or not claves:
        return {}
    inst_id = int(_pg_current_inst_id())
    periodo_nombre, anio, semestre = _periodo_equivalente_pg(int(periodo_id))
    placeholders = ", ".join(["%s"] * len(claves))
    params = [inst_id] + list(claves) + [
        int(periodo_id), periodo_nombre, int(anio), int(semestre)
    ]
    df = _pg_read_dataframe(f"""
        SELECT
            regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g') AS cuil_clave,
            COALESCE(SUM(a.horas_asignadas),0) AS horas
        FROM asignaciones_docentes_comision a
        JOIN comisiones co ON co.id=a.comision_id
        LEFT JOIN periodos p ON p.id=co.periodo_id
        WHERE a.institucion_id=%s
          AND regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g') IN ({placeholders})
          AND COALESCE(a.estado,'Activa')='Activa'
          AND COALESCE(co.estado,'Activa')='Activa'
          AND (co.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))
        GROUP BY regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g')
    """, params)
    if df is None or df.empty:
        return {}
    return {
        str(r.get("cuil_clave") or ""): float(r.get("horas") or 0)
        for _, r in df.iterrows()
    }


# --- entry l. 43266-43291
def _mapa_horas_proyectos_bulk_v194(periodo_id, claves, tipo):
    try:
        if str(tipo).startswith("inv"):
            df = get_investigacion_docente(
                cuil=None, periodo_id=int(periodo_id),
                incluir_bajas=False, todos_departamentos=True
            )
        else:
            df = get_extension_docente(
                cuil=None, periodo_id=int(periodo_id),
                incluir_bajas=False, todos_departamentos=True
            )
    except Exception:
        df = pd.DataFrame()
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {}
    aux = df.copy()
    aux["_cuil_v194"] = _claves_cuil_df_v194(aux)
    aux = aux[aux["_cuil_v194"].isin(set(claves))].copy()
    if aux.empty:
        return {}
    aux["_hs_v194"] = pd.to_numeric(
        aux.get("horas_asignadas", pd.Series(index=aux.index, dtype=float)),
        errors="coerce"
    ).fillna(0)
    return aux.groupby("_cuil_v194")["_hs_v194"].sum().astype(float).to_dict()


# --- entry l. 43294-43549
def _productividad_periodo_bulk_pg_v194(periodo_id):
    columnas = [
        "cuil", "docente", "tipo_docente", "departamentos_designacion",
        "cargos", "dedicaciones", "tipos_designacion", "porcentaje_uso",
        "horas_contratadas", "horas_comisiones_brutas", "horas_comisiones_reales",
        "horas_no_contadas_por_superposicion", "porcentaje_no_lectivas",
        "horas_no_lectivas", "horas_investigacion", "horas_extension",
        "horas_utilizadas", "horas_disponibles", "diagnostico",
    ]
    if not USE_POSTGRESQL:
        return _get_docentes_productividad_periodo_pre_v194(periodo_id)

    historico = bool(es_periodo_historico_contexto_v182(int(periodo_id)))

    # 1. Determina exactamente qué docentes pertenecen al plantel que se analiza.
    if historico:
        df_local_doc, _, _ = _designaciones_funcionales_analisis_v169(int(periodo_id))
        df_local_doc = df_local_doc.copy() if isinstance(df_local_doc, pd.DataFrame) else pd.DataFrame()
        claves_objetivo = sorted(_cuiles_unicos_designaciones_v165(df_local_doc))
        mapa_nombre = {}
        for clave, g in (
            df_local_doc.assign(_clave_v194=_claves_cuil_df_v194(df_local_doc))
            .groupby("_clave_v194", sort=False)
            if not df_local_doc.empty else []
        ):
            if clave:
                mapa_nombre[clave] = limpiar_texto_tabla(g.iloc[0].get("nombre_completo", "")) or str(g.iloc[0].get("cuil") or clave)
    else:
        df_local = get_designaciones(int(periodo_id))
        df_local_doc = _designaciones_docentes_activas_v162(df_local)
        habilitados = _cuiles_unicos_designaciones_v165(df_local_doc)

        # Replica el filtro histórico del producto v150/v151: propio, no prestado.
        try:
            plantel = get_plantel_periodo(int(periodo_id))
        except Exception:
            plantel = pd.DataFrame()
        mapa_nombre = {}
        claves_propias = set()
        if isinstance(plantel, pd.DataFrame) and not plantel.empty:
            for _, r in plantel.iterrows():
                clave = _clave_cuil(r.get("cuil"))
                if not clave:
                    continue
                if str(r.get("tipo_docente", "Propio") or "Propio").strip().casefold() == "prestado":
                    continue
                claves_propias.add(clave)
                mapa_nombre[clave] = limpiar_texto_tabla(r.get("nombre_completo", "")) or str(r.get("cuil") or clave)
        claves_objetivo = sorted(habilitados & claves_propias) if claves_propias else sorted(habilitados)
        if not mapa_nombre and isinstance(df_local_doc, pd.DataFrame) and not df_local_doc.empty:
            for _, r in df_local_doc.iterrows():
                clave = _clave_cuil(r.get("cuil"))
                if clave and clave not in mapa_nombre:
                    mapa_nombre[clave] = limpiar_texto_tabla(r.get("nombre_completo", "")) or str(r.get("cuil") or clave)

    if not claves_objetivo:
        return pd.DataFrame(columns=columnas)

    # Un CUIL visible para cada clave, preservando el formato registrado localmente.
    mapa_cuil_visible = {}
    if isinstance(df_local_doc, pd.DataFrame) and not df_local_doc.empty:
        for _, r in df_local_doc.iterrows():
            clave = _clave_cuil(r.get("cuil"))
            if clave and clave not in mapa_cuil_visible:
                mapa_cuil_visible[clave] = str(r.get("cuil") or clave).strip()

    # 2. Toda la información institucional se trae en bloque.
    df_des_inst = _consulta_designaciones_institucionales_bulk_v194(
        int(periodo_id), claves_objetivo
    )
    if isinstance(df_des_inst, pd.DataFrame) and not df_des_inst.empty:
        df_des_inst = df_des_inst.copy()
        df_des_inst["_cuil_v194"] = _claves_cuil_df_v194(df_des_inst)

    if historico:
        df_des_doc = _filtrar_foto_designaciones_v169(df_des_inst, int(periodo_id))
        if isinstance(df_des_doc, pd.DataFrame) and not df_des_doc.empty:
            no_doc = df_des_doc.get(
                "funcion_no_docente", pd.Series(0, index=df_des_doc.index)
            ).map(_es_funcion_no_docente_v162)
            df_des_doc = df_des_doc[~no_doc].copy()
            df_des_doc["_cuil_v194"] = _claves_cuil_df_v194(df_des_doc)
        df_des_mostrar = df_des_doc
    else:
        if isinstance(df_des_inst, pd.DataFrame) and not df_des_inst.empty:
            est = df_des_inst.get(
                "estado", pd.Series(index=df_des_inst.index, dtype=str)
            ).fillna("").astype(str).str.strip().str.casefold()
            df_des_mostrar = df_des_inst[est.eq("activa")].copy()
            df_des_doc = _designaciones_docentes_activas_v162(df_des_inst)
            if not df_des_doc.empty:
                df_des_doc["_cuil_v194"] = _claves_cuil_df_v194(df_des_doc)
        else:
            df_des_mostrar = pd.DataFrame()
            df_des_doc = pd.DataFrame()

    df_h = _consulta_horarios_bulk_v194(
        int(periodo_id), claves_objetivo, historico=historico
    )
    if isinstance(df_h, pd.DataFrame) and not df_h.empty:
        df_h = df_h.copy()
        df_h["_cuil_v194"] = _claves_cuil_df_v194(df_h)

    bruto_map = (
        {} if historico
        else _consulta_horas_brutas_bulk_v194(int(periodo_id), claves_objetivo)
    )
    inv_map = _mapa_horas_proyectos_bulk_v194(
        int(periodo_id), claves_objetivo, "investigacion"
    )
    ext_map = _mapa_horas_proyectos_bulk_v194(
        int(periodo_id), claves_objetivo, "extension"
    )
    porcentajes = _get_porcentajes_no_lectivos_departamentos_v149()

    # La regla v151 requiere saber una sola vez cuántos docentes activos tiene
    # cada comisión. Antes esto se consultaba repetidamente por docente.
    conteos_comision = {}
    if not historico and isinstance(df_h, pd.DataFrame) and not df_h.empty and "comision_id" in df_h.columns:
        ids_com = pd.to_numeric(
            df_h["comision_id"], errors="coerce"
        ).dropna().astype(int).unique().tolist()
        conteos_comision = _conteo_docentes_activos_por_comision_v151(ids_com)

    # 3. Agrupa en memoria. No vuelve a consultar PostgreSQL por cada docente.
    registros = []
    for clave in claves_objetivo:
        cuil_visible = mapa_cuil_visible.get(clave, clave)
        nombre = mapa_nombre.get(clave, cuil_visible)

        if isinstance(df_des_doc, pd.DataFrame) and not df_des_doc.empty:
            sub_doc = df_des_doc[
                df_des_doc["_cuil_v194"].eq(clave)
            ].copy()
        else:
            sub_doc = pd.DataFrame()

        if isinstance(df_des_mostrar, pd.DataFrame) and not df_des_mostrar.empty:
            if "_cuil_v194" not in df_des_mostrar.columns:
                df_des_mostrar = df_des_mostrar.copy()
                df_des_mostrar["_cuil_v194"] = _claves_cuil_df_v194(df_des_mostrar)
            sub_mostrar = df_des_mostrar[
                df_des_mostrar["_cuil_v194"].eq(clave)
            ].copy()
        else:
            sub_mostrar = pd.DataFrame()

        contratadas = _horas_designaciones_v165(sub_doc)

        if isinstance(df_h, pd.DataFrame) and not df_h.empty:
            gh = df_h[df_h["_cuil_v194"].eq(clave)].copy()
        else:
            gh = pd.DataFrame()

        com_reales = (
            float(_calcular_horas_unicas_desde_horarios_df(gh) or 0)
            if not gh.empty else 0.0
        )

        if historico:
            if not gh.empty and "asignacion_id" in gh.columns:
                dfa = gh.drop_duplicates(subset=["asignacion_id"]).copy()
                com_brutas = float(
                    pd.to_numeric(
                        dfa.get("horas_asignadas", pd.Series(dtype=float)),
                        errors="coerce"
                    ).fillna(0).sum()
                )
            else:
                com_brutas = float(com_reales)

            horas_nl = 0.0
            if not gh.empty and "departamento_id" in gh.columns:
                for dep_id, gd in gh.groupby("departamento_id", dropna=True):
                    try:
                        dep_i = int(dep_id)
                    except Exception:
                        continue
                    hs_dep = float(_calcular_horas_unicas_desde_horarios_df(gd) or 0)
                    pct = float(porcentajes.get(dep_i, 0) or 0)
                    horas_nl += round(hs_dep * pct / 100.0, 2)
            horas_nl = round(horas_nl, 2)
        else:
            com_brutas = float(bruto_map.get(clave, com_reales) or 0)
            horas_nl = 0.0
            if not gh.empty and "comision_id" in gh.columns:
                for cid, gc in gh.groupby("comision_id", dropna=True, sort=True):
                    try:
                        cid_i = int(cid)
                    except Exception:
                        continue
                    hs_doc = float(_calcular_horas_unicas_desde_horarios_df(gc) or 0)
                    try:
                        dep_i = int(pd.to_numeric(
                            gc.iloc[0].get("departamento_id"), errors="coerce"
                        ))
                    except Exception:
                        dep_i = None
                    pct_base = float(porcentajes.get(dep_i, 0) or 0) if dep_i is not None else 0.0
                    cantidad = int(conteos_comision.get(cid_i, 1) or 1)
                    pct_aplicado = pct_base if cantidad <= 1 else pct_base / 2.0
                    horas_nl += round(hs_doc * pct_aplicado / 100.0, 2)
            horas_nl = round(horas_nl, 2)

        investigacion = round(float(inv_map.get(clave, 0) or 0), 2)
        extension = round(float(ext_map.get(clave, 0) or 0), 2)
        utilizadas = round(com_reales + horas_nl + investigacion + extension, 2)
        disponibles = round(float(contratadas) - utilizadas, 2)
        porcentaje = round(
            utilizadas / float(contratadas) * 100.0, 2
        ) if contratadas > 0 else 0.0
        pct_nl = round(
            horas_nl / float(com_reales) * 100.0, 2
        ) if com_reales > 0 else 0.0

        if contratadas <= 0 and utilizadas > 0:
            diagnostico = "Actividad registrada sin horas contratadas"
        elif utilizadas > contratadas:
            diagnostico = "Sobrecarga: horas utilizadas superan las contratadas"
        elif contratadas > 0 and utilizadas == 0:
            diagnostico = "Sin actividad registrada"
        elif contratadas > 0 and porcentaje < 50:
            diagnostico = "Subutilización: baja carga registrada"
        else:
            diagnostico = "Sin alerta principal"

        registros.append({
            "cuil": cuil_visible,
            "docente": nombre,
            "tipo_docente": "Propio",
            "departamentos_designacion": _unir_unicos_v194(sub_mostrar, "departamento"),
            "cargos": _unir_unicos_v194(sub_mostrar, "cargo"),
            "dedicaciones": _unir_unicos_v194(sub_mostrar, "dedicacion"),
            "tipos_designacion": _unir_unicos_v194(sub_mostrar, "tipo_designacion"),
            "porcentaje_uso": porcentaje,
            "horas_contratadas": round(float(contratadas), 2),
            "horas_comisiones_brutas": round(float(com_brutas), 2),
            "horas_comisiones_reales": round(float(com_reales), 2),
            "horas_no_contadas_por_superposicion": max(
                round(float(com_brutas) - float(com_reales), 2), 0.0
            ),
            "porcentaje_no_lectivas": pct_nl,
            "horas_no_lectivas": horas_nl,
            "horas_investigacion": investigacion,
            "horas_extension": extension,
            "horas_utilizadas": utilizadas,
            "horas_disponibles": disponibles,
            "diagnostico": diagnostico,
        })

    if not registros:
        return pd.DataFrame(columns=columnas)
    out = pd.DataFrame(registros, columns=columnas)
    return _redondear_numericos_productividad_v150(out).sort_values(
        ["diagnostico", "docente"], kind="stable"
    ).reset_index(drop=True)


# --- entry l. 43553-43556
def _productividad_periodo_bulk_cache_v194(
    periodo_id, db_url, inst, dep, version
):
    return _productividad_periodo_bulk_pg_v194(int(periodo_id))


# --- entry l. 43559-43567
def get_docentes_productividad_periodo(periodo_id):
    if not USE_POSTGRESQL:
        return _get_docentes_productividad_periodo_pre_v194(periodo_id)
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _productividad_periodo_bulk_cache_v194(
            int(periodo_id), db_url, inst, dep, version
        )
    )


# --- entry l. 43580
_invalidar_cache_rendimiento_pre_v195 = invalidar_cache_rendimiento_v191


# --- entry l. 43582-43587
def invalidar_cache_rendimiento_v191(motivo="actualización"):
    _invalidar_cache_rendimiento_pre_v195(motivo)
    try:
        _inicio_datos_tablero_cache.clear()
    except Exception:
        pass


# --- entry l. 43590
_limpiar_cache_comisiones_pre_v195 = limpiar_cache_comisiones_operativas


# --- entry l. 43592-43597
def limpiar_cache_comisiones_operativas():
    _limpiar_cache_comisiones_pre_v195()
    try:
        _inicio_datos_tablero_cache.clear()
    except Exception:
        pass


# --- entry l. 43602
_obtener_cargo_prioritario_pre_v195 = obtener_cargo_prioritario_docente_periodo


# --- entry l. 43605-43611
def _obtener_cargo_prioritario_cache_v195(
    cuil, periodo_id, departamento_contexto_id,
    db_url, inst, dep, version
):
    return _obtener_cargo_prioritario_pre_v195(
        cuil, int(periodo_id), departamento_contexto_id
    )


# --- entry l. 43613-43623
def obtener_cargo_prioritario_docente_periodo(
    cuil, periodo_id, departamento_contexto_id=None
):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    resultado = _obtener_cargo_prioritario_cache_v195(
        str(cuil or ""),
        int(periodo_id),
        int(departamento_contexto_id) if departamento_contexto_id is not None else None,
        db_url, inst, dep, version,
    )
    return dict(resultado or {})


# --- entry l. 43628
_diagnosticar_cargos_pre_v195 = diagnosticar_cargos_asignaciones_periodo


# --- entry l. 43631-43632
def _diagnosticar_cargos_cache_v195(periodo_id, db_url, inst, dep, version):
    return _diagnosticar_cargos_pre_v195(int(periodo_id))


# --- entry l. 43634-43640
def diagnosticar_cargos_asignaciones_periodo(periodo_id):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _diagnosticar_cargos_cache_v195(
            int(periodo_id), db_url, inst, dep, version
        )
    )


# --- entry l. 43646-43798
def _superposiciones_periodo_bulk_pg_v195(periodo_id):
    if not USE_POSTGRESQL:
        return None

    inst_id = _pg_current_inst_id()
    dep_id = _pg_current_dep_id()
    if inst_id is None or dep_id is None:
        return pd.DataFrame(columns=[
            "docente", "cuil", "dia", "asignatura_1", "comision_1", "horario_1",
            "asignatura_2", "comision_2", "horario_2"
        ])

    dfh = _pg_read_dataframe("""
        WITH base AS (
            SELECT
                a.id AS asignacion_id,
                a.cuil,
                a.comision_id,
                COALESCE(a.usa_horario_personalizado, FALSE) AS personalizado,
                co.nombre_comision,
                co.materia_id,
                COALESCE(co.materia_especifica, '') AS materia_especifica,
                COALESCE(m.codigo, '') AS codigo_materia,
                COALESCE(m.asignatura, '') AS asignatura,
                CASE
                    WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL
                        THEN doc.apellido || ', ' || doc.nombres
                    WHEN doc.nombre IS NOT NULL THEN doc.nombre
                    ELSE a.cuil
                END AS docente
            FROM asignaciones_docentes_comision a
            JOIN comisiones co ON co.id=a.comision_id
            LEFT JOIN materias m
                   ON m.id=co.materia_id
                  AND m.institucion_id=co.institucion_id
            LEFT JOIN docentes doc
                   ON doc.institucion_id=a.institucion_id
                  AND doc.departamento_id=a.departamento_id
                  AND regexp_replace(COALESCE(doc.cuil,''), '[^0-9]', '', 'g') =
                      regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g')
            WHERE a.institucion_id=%s
              AND a.departamento_id=%s
              AND co.institucion_id=%s
              AND co.departamento_id=%s
              AND co.periodo_id=%s
              AND COALESCE(a.estado,'Activa')='Activa'
              AND COALESCE(co.estado,'Activa')='Activa'
        ),
        reales AS (
            SELECT
                b.*, ha.dia, ha.hora_inicio, ha.hora_fin, ha.horas
            FROM base b
            JOIN horarios_asignacion_docente_comision ha
              ON ha.asignacion_id=b.asignacion_id
             AND ha.institucion_id=%s
             AND ha.departamento_id=%s
            WHERE b.personalizado=TRUE

            UNION ALL

            SELECT
                b.*, h.dia, h.hora_inicio, h.hora_fin, h.horas
            FROM base b
            JOIN horarios_comision h
              ON h.comision_id=b.comision_id
             AND h.institucion_id=%s
             AND h.departamento_id=%s
            WHERE b.personalizado=FALSE
        )
        SELECT *
        FROM reales
        ORDER BY cuil,
                 CASE dia
                    WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2
                    WHEN 'Miércoles' THEN 3 WHEN 'Jueves' THEN 4
                    WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6
                    WHEN 'Domingo' THEN 7 ELSE 99
                 END,
                 hora_inicio, comision_id
    """, [
        int(inst_id), int(dep_id), int(inst_id), int(dep_id), int(periodo_id),
        int(inst_id), int(dep_id), int(inst_id), int(dep_id),
    ])

    if not isinstance(dfh, pd.DataFrame) or dfh.empty:
        return pd.DataFrame(columns=[
            "docente", "cuil", "dia", "asignatura_1", "comision_1", "horario_1",
            "asignatura_2", "comision_2", "horario_2"
        ])

    out = []
    vistos = set()

    dfh = dfh.copy()
    dfh["_cuil_v195"] = dfh["cuil"].fillna("").astype(str).map(_clave_cuil)

    for (cuil_clave, dia), g in dfh.groupby(["_cuil_v195", "dia"], dropna=False, sort=False):
        if not cuil_clave or pd.isna(dia):
            continue
        rows = list(g.sort_values(["hora_inicio", "hora_fin", "comision_id"], kind="stable").to_dict("records"))
        for i in range(len(rows)):
            a = rows[i]
            ai, af = _minutos_v95(a.get("hora_inicio")), _minutos_v95(a.get("hora_fin"))
            if ai is None or af is None:
                continue
            for j in range(i + 1, len(rows)):
                b = rows[j]
                if a.get("comision_id") == b.get("comision_id"):
                    continue
                bi, bf = _minutos_v95(b.get("hora_inicio")), _minutos_v95(b.get("hora_fin"))
                if bi is None or bf is None:
                    continue
                if max(ai, bi) >= min(af, bf):
                    # Al estar ordenado por inicio, si b empieza después de que a termina
                    # ya no habrá solape con filas posteriores.
                    if bi >= af:
                        break
                    continue

                clave = (
                    str(cuil_clave), str(dia),
                    min(int(a.get("comision_id")), int(b.get("comision_id"))),
                    max(int(a.get("comision_id")), int(b.get("comision_id"))),
                    max(ai, bi), min(af, bf),
                )
                if clave in vistos:
                    continue
                vistos.add(clave)

                out.append({
                    "docente": str(a.get("docente") or b.get("docente") or a.get("cuil") or ""),
                    "cuil": str(a.get("cuil") or b.get("cuil") or ""),
                    "dia": dia,
                    "asignatura_1": _nombre_materia_visible_v138(
                        a.get("codigo_materia", ""),
                        a.get("asignatura", ""),
                        a.get("materia_especifica", ""),
                    ),
                    "comision_1": str(a.get("nombre_comision") or ""),
                    "horario_1": f"{_hora_texto_v95(a.get('hora_inicio'))}-{_hora_texto_v95(a.get('hora_fin'))}",
                    "asignatura_2": _nombre_materia_visible_v138(
                        b.get("codigo_materia", ""),
                        b.get("asignatura", ""),
                        b.get("materia_especifica", ""),
                    ),
                    "comision_2": str(b.get("nombre_comision") or ""),
                    "horario_2": f"{_hora_texto_v95(b.get('hora_inicio'))}-{_hora_texto_v95(b.get('hora_fin'))}",
                })

    return pd.DataFrame(out, columns=[
        "docente", "cuil", "dia", "asignatura_1", "comision_1", "horario_1",
        "asignatura_2", "comision_2", "horario_2"
    ])


# --- entry l. 43801
_get_superposiciones_periodo_pre_v195 = get_superposiciones_periodo


# --- entry l. 43804-43809
def _get_superposiciones_periodo_cache_v195(
    periodo_id, db_url, inst, dep, version, com_version
):
    if USE_POSTGRESQL:
        return _superposiciones_periodo_bulk_pg_v195(int(periodo_id))
    return _get_superposiciones_periodo_pre_v195(int(periodo_id))


# --- entry l. 43811-43818
def get_superposiciones_periodo(periodo_id):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    com_version = int(st.session_state.get("_comisiones_cache_version", 0) or 0)
    return _copiar_resultado_cache_v191(
        _get_superposiciones_periodo_cache_v195(
            int(periodo_id), db_url, inst, dep, version, com_version
        )
    )


# --- entry l. 44062-44063
def _catalogo_materias_version_v196():
    return int(st.session_state.get("_catalogo_materias_version_v196", 0) or 0)


# --- entry l. 44086
_materias_para_comisiones_detalle_pre_v196 = _materias_para_comisiones_detalle


# --- entry l. 44089-44092
def _materias_para_comisiones_detalle_cache_v196(
    db_url, inst_id, dep_id, catalogo_version
):
    return _materias_para_comisiones_detalle_pre_v196()


# --- entry l. 44095-44107
def _materias_para_comisiones_detalle():
    try:
        inst_id = int(_pg_current_inst_id() or 0) if USE_POSTGRESQL else 0
    except Exception:
        inst_id = 0
    try:
        dep_id = int(_pg_current_dep_id() or 0) if USE_POSTGRESQL else 0
    except Exception:
        dep_id = 0
    df = _materias_para_comisiones_detalle_cache_v196(
        str(DATABASE_URL), inst_id, dep_id, _catalogo_materias_version_v196()
    )
    return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()


# --- entry l. 44112
_materias_unificadas_pre_v196 = _materias_para_comisiones_unificadas_y_mapa_no_cache


# --- entry l. 44115-44119
def _materias_para_comisiones_unificadas_cache_v196(
    db_url, inst_id, dep_id, catalogo_version
):
    unicas, mapa = _materias_unificadas_pre_v196()
    return unicas, mapa


# --- entry l. 44122-44137
def _materias_para_comisiones_unificadas_y_mapa():
    try:
        inst_id = int(_pg_current_inst_id() or 0) if USE_POSTGRESQL else 0
    except Exception:
        inst_id = 0
    try:
        dep_id = int(_pg_current_dep_id() or 0) if USE_POSTGRESQL else 0
    except Exception:
        dep_id = 0
    unicas, mapa = _materias_para_comisiones_unificadas_cache_v196(
        str(DATABASE_URL), inst_id, dep_id, _catalogo_materias_version_v196()
    )
    return (
        unicas.copy() if isinstance(unicas, pd.DataFrame) else pd.DataFrame(),
        mapa.copy() if isinstance(mapa, pd.DataFrame) else pd.DataFrame(),
    )


# --- entry l. 44317
_get_comisiones_pre_v197 = get_comisiones


# --- entry l. 44319-44442
def _get_comisiones_fast_pg_v197(periodo_id=None, solo_activas=False):
    inst_id = _pg_current_inst_id()
    dep_id = _pg_current_dep_id()
    if inst_id is None or dep_id is None:
        return pd.DataFrame()

    filtros = ["co.institucion_id=%s", "co.departamento_id=%s"]
    params = [int(inst_id), int(dep_id)]
    if periodo_id is not None:
        filtros.append("co.periodo_id=%s")
        params.append(int(periodo_id))
    if solo_activas:
        filtros.append("COALESCE(co.estado,'Activa')='Activa'")
    where = " AND ".join(filtros)

    sql = f"""
        WITH cm_meta AS (
            SELECT
                cm.comision_id,
                string_agg(DISTINCT COALESCE(NULLIF(TRIM(m.codigo), ''), NULLIF(TRIM(cm.codigo_snapshot), ''), ''), ' / ')
                    FILTER (WHERE COALESCE(NULLIF(TRIM(m.codigo), ''), NULLIF(TRIM(cm.codigo_snapshot), ''), '') <> '') AS codigo_materia,
                string_agg(DISTINCT COALESCE(NULLIF(TRIM(m.asignatura), ''), NULLIF(TRIM(cm.asignatura_snapshot), ''), ''), ' / ')
                    FILTER (WHERE COALESCE(NULLIF(TRIM(m.asignatura), ''), NULLIF(TRIM(cm.asignatura_snapshot), ''), '') <> '') AS asignatura,
                string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.carrera_snapshot), ''), NULLIF(TRIM(c.nombre), ''), NULLIF(TRIM(m.carrera), ''), ''), ' / ')
                    FILTER (WHERE COALESCE(NULLIF(TRIM(cm.carrera_snapshot), ''), NULLIF(TRIM(c.nombre), ''), NULLIF(TRIM(m.carrera), ''), '') <> '') AS carrera,
                string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.escuela_snapshot), ''), NULLIF(TRIM(c.escuela), ''), NULLIF(TRIM(m.escuela), ''), ''), ' / ')
                    FILTER (WHERE COALESCE(NULLIF(TRIM(cm.escuela_snapshot), ''), NULLIF(TRIM(c.escuela), ''), NULLIF(TRIM(m.escuela), ''), '') <> '') AS escuela,
                string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.plan_version_snapshot), ''), NULLIF(TRIM(c.plan_version), ''), NULLIF(TRIM(m.plan_version), ''), ''), ' / ')
                    FILTER (WHERE COALESCE(NULLIF(TRIM(cm.plan_version_snapshot), ''), NULLIF(TRIM(c.plan_version), ''), NULLIF(TRIM(m.plan_version), ''), '') <> '') AS plan_version,
                string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.anio_snapshot), ''), NULLIF(TRIM(m.anio), ''), ''), ' / ')
                    FILTER (WHERE COALESCE(NULLIF(TRIM(cm.anio_snapshot), ''), NULLIF(TRIM(m.anio), ''), '') <> '') AS anio,
                string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.cuatrimestre_snapshot), ''), NULLIF(TRIM(m.cuatrimestre), ''), ''), ' / ')
                    FILTER (WHERE COALESCE(NULLIF(TRIM(cm.cuatrimestre_snapshot), ''), NULLIF(TRIM(m.cuatrimestre), ''), '') <> '') AS cuatrimestre,
                string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.dictado_snapshot), ''), NULLIF(TRIM(m.dictado), ''), ''), ' / ')
                    FILTER (WHERE COALESCE(NULLIF(TRIM(cm.dictado_snapshot), ''), NULLIF(TRIM(m.dictado), ''), '') <> '') AS dictado,
                string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.carga_semanal_snapshot), ''), NULLIF(TRIM(CAST(m.carga_semanal AS TEXT)), ''), ''), ' / ')
                    FILTER (WHERE COALESCE(NULLIF(TRIM(cm.carga_semanal_snapshot), ''), NULLIF(TRIM(CAST(m.carga_semanal AS TEXT)), ''), '') <> '') AS carga_semanal,
                string_agg(DISTINCT COALESCE(NULLIF(TRIM(cm.carga_total_snapshot), ''), NULLIF(TRIM(CAST(m.carga_total AS TEXT)), ''), ''), ' / ')
                    FILTER (WHERE COALESCE(NULLIF(TRIM(cm.carga_total_snapshot), ''), NULLIF(TRIM(CAST(m.carga_total AS TEXT)), ''), '') <> '') AS carga_total,
                string_agg(DISTINCT CAST(cm.materia_id AS TEXT), ',') AS materia_ids
            FROM comision_materias cm
            LEFT JOIN materias m ON m.id=cm.materia_id AND m.institucion_id=cm.institucion_id
            LEFT JOIN carreras c ON c.id=m.carrera_id AND c.institucion_id=m.institucion_id
            WHERE cm.institucion_id=%s AND cm.departamento_id=%s
            GROUP BY cm.comision_id
        ),
        hor AS (
            SELECT comision_id, COALESCE(SUM(horas),0) AS horas_horario, COUNT(*) AS cantidad_horarios
            FROM horarios_comision
            WHERE institucion_id=%s AND departamento_id=%s
            GROUP BY comision_id
        ),
        asig AS (
            SELECT comision_id,
                   COUNT(*) FILTER (WHERE COALESCE(estado,'Activa')='Activa') AS docentes_asignados
            FROM asignaciones_docentes_comision
            WHERE institucion_id=%s AND departamento_id=%s
            GROUP BY comision_id
        )
        SELECT
            co.id, co.periodo_id, p.nombre AS periodo, co.materia_id, co.opcion_curricular_id,
            COALESCE(NULLIF(cm.codigo_materia,''), NULLIF(m0.codigo,''), '') AS codigo_materia,
            COALESCE(NULLIF(cm.asignatura,''), NULLIF(m0.asignatura,''), '') AS asignatura,
            CASE WHEN oc.id IS NOT NULL
                 THEN COALESCE(NULLIF(oc.nombre,''), COALESCE(co.materia_especifica,''))
                 ELSE COALESCE(co.materia_especifica,'') END AS materia_especifica,
            COALESCE(oc.tipo,'') AS tipo_opcion_curricular,
            COALESCE(oc.escuela_oferente,'') AS escuela_oferente_opcion,
            COALESCE(NULLIF(cm.carrera,''), NULLIF(c0.nombre,''), NULLIF(m0.carrera,''), '') AS carrera,
            COALESCE(NULLIF(cm.escuela,''), NULLIF(c0.escuela,''), NULLIF(m0.escuela,''), '') AS escuela,
            COALESCE(NULLIF(cm.plan_version,''), NULLIF(c0.plan_version,''), NULLIF(m0.plan_version,''), '') AS plan_version,
            COALESCE(NULLIF(cm.anio,''), NULLIF(m0.anio,''), '') AS anio,
            COALESCE(NULLIF(cm.cuatrimestre,''), NULLIF(m0.cuatrimestre,''), '') AS cuatrimestre,
            COALESCE(NULLIF(cm.dictado,''), NULLIF(m0.dictado,''), '') AS dictado,
            COALESCE(NULLIF(cm.carga_semanal,''), NULLIF(CAST(m0.carga_semanal AS TEXT),''), '') AS carga_semanal,
            COALESCE(NULLIF(cm.carga_total,''), NULLIF(CAST(m0.carga_total AS TEXT),''), '') AS carga_total,
            COALESCE(NULLIF(cm.materia_ids,''), CAST(co.materia_id AS TEXT), '') AS materia_ids,
            co.nombre_comision, co.turno, co.sede, co.modalidad, co.estado,
            co.observaciones, co.fecha_creacion,
            COALESCE(hor.horas_horario,0) AS horas_horario,
            COALESCE(hor.cantidad_horarios,0) AS cantidad_horarios,
            COALESCE(asig.docentes_asignados,0) AS docentes_asignados
        FROM comisiones co
        LEFT JOIN periodos p
          ON p.id=co.periodo_id
         AND p.institucion_id=co.institucion_id
         AND p.departamento_id=co.departamento_id
        LEFT JOIN cm_meta cm ON cm.comision_id=co.id
        LEFT JOIN materias m0 ON m0.id=co.materia_id AND m0.institucion_id=co.institucion_id
        LEFT JOIN carreras c0 ON c0.id=m0.carrera_id AND c0.institucion_id=m0.institucion_id
        LEFT JOIN opciones_curriculares oc ON oc.id=co.opcion_curricular_id AND oc.institucion_id=co.institucion_id
        LEFT JOIN hor ON hor.comision_id=co.id
        LEFT JOIN asig ON asig.comision_id=co.id
        WHERE {where}
        ORDER BY p.anio DESC, p.semestre DESC,
                 COALESCE(NULLIF(cm.escuela,''), NULLIF(c0.escuela,''), NULLIF(m0.escuela,''), ''),
                 COALESCE(NULLIF(cm.codigo_materia,''), NULLIF(m0.codigo,''), ''),
                 COALESCE(NULLIF(cm.asignatura,''), NULLIF(m0.asignatura,''), ''),
                 co.nombre_comision
    """
    sql_params = [
        int(inst_id), int(dep_id),
        int(inst_id), int(dep_id),
        int(inst_id), int(dep_id),
    ] + params

    df = _pg_read_dataframe(sql, sql_params)
    columnas = [
        "id", "periodo_id", "periodo", "materia_id", "opcion_curricular_id",
        "codigo_materia", "asignatura", "materia_especifica", "tipo_opcion_curricular",
        "escuela_oferente_opcion", "carrera", "escuela", "plan_version", "anio", "cuatrimestre",
        "dictado", "carga_semanal", "carga_total", "materia_ids", "nombre_comision", "turno",
        "sede", "modalidad", "estado", "observaciones", "fecha_creacion", "horas_horario",
        "cantidad_horarios", "docentes_asignados"
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=columnas)
    for col in columnas:
        if col not in df.columns:
            df[col] = ""
    df["horas_horario"] = pd.to_numeric(df["horas_horario"], errors="coerce").fillna(0)
    df["cantidad_horarios"] = pd.to_numeric(df["cantidad_horarios"], errors="coerce").fillna(0).astype(int)
    df["docentes_asignados"] = pd.to_numeric(df["docentes_asignados"], errors="coerce").fillna(0).astype(int)
    return df[columnas].reset_index(drop=True)


# --- entry l. 44446-44447
def _get_comisiones_fast_cache_v197(periodo_id, solo_activas, db_url, inst_id, dep_id, comisiones_version, catalogo_version, opciones_version):
    return _get_comisiones_fast_pg_v197(periodo_id=periodo_id, solo_activas=bool(solo_activas))


# --- entry l. 44450-44463
def get_comisiones(periodo_id=None, solo_activas=False):
    if not USE_POSTGRESQL:
        return _get_comisiones_pre_v197(periodo_id=periodo_id, solo_activas=solo_activas)
    inst_id = int(_pg_current_inst_id() or 0)
    dep_id = int(_pg_current_dep_id() or 0)
    com_ver = int(st.session_state.get("_comisiones_cache_version", 0) or 0)
    cat_ver = int(st.session_state.get("_catalogo_materias_version_v196", 0) or 0)
    opc_ver = int(st.session_state.get("_opciones_cache_version_v127", 0) or 0)
    df = _get_comisiones_fast_cache_v197(
        int(periodo_id) if periodo_id is not None else None,
        bool(solo_activas), str(DATABASE_URL), inst_id, dep_id,
        com_ver, cat_ver, opc_ver,
    )
    return df.copy()


# --- entry l. 44487
_limpiar_opciones_pre_v197 = limpiar_cache_opciones_curriculares_v127


# --- entry l. 44488-44493
def limpiar_cache_opciones_curriculares_v127():
    _limpiar_opciones_pre_v197()
    try:
        _get_comisiones_fast_cache_v197.clear()
    except Exception:
        pass


# --- entry l. 44509-44516
def _registro_versiones_v199():
    return {
        "lock": threading.RLock(),
        "departamentos": {},
        "instituciones": {},
        "auth": 0,
        "epoch": 0,
    }


# --- entry l. 44519-44525
def _versiones_scope_v199(inst, dep):
    reg = _registro_versiones_v199()
    with reg["lock"]:
        iv = int(reg["instituciones"].get(int(inst or 0), 0) or 0)
        dv = int(reg["departamentos"].get((int(inst or 0), int(dep or 0)), 0) or 0)
        ep = int(reg.get("epoch", 0) or 0)
    return iv, dv, ep


# --- entry l. 44528-44537
def _scope_rendimiento_v191():
    try: inst = int(_pg_current_inst_id() or 0) if USE_POSTGRESQL else 0
    except Exception: inst = 0
    try: dep = int(_pg_current_dep_id() or 0) if USE_POSTGRESQL else 0
    except Exception: dep = 0
    iv, dv, ep = _versiones_scope_v199(inst, dep)
    # Se mantiene el entero visible que ya usa el diagnóstico/Word v191.
    try: st.session_state["_perf_data_version_v191"] = ep
    except Exception: pass
    return str(DATABASE_URL), inst, dep, (iv, dv)


# --- entry l. 44540
_invalidar_cache_rendimiento_pre_v199 = invalidar_cache_rendimiento_v191


# --- entry l. 44542-44575
def invalidar_cache_rendimiento_v191(motivo="actualización"):
    _invalidar_cache_rendimiento_pre_v199(motivo)
    try:
        inst = int(_pg_current_inst_id() or 0) if USE_POSTGRESQL else 0
        dep = int(_pg_current_dep_id() or 0) if USE_POSTGRESQL else 0
        reg = _registro_versiones_v199()
        with reg["lock"]:
            reg["instituciones"][inst] = int(reg["instituciones"].get(inst, 0) or 0) + 1
            clave = (inst, dep)
            reg["departamentos"][clave] = int(reg["departamentos"].get(clave, 0) or 0) + 1
            reg["epoch"] = int(reg.get("epoch", 0) or 0) + 1
            ep = int(reg["epoch"])
        st.session_state["_perf_data_version_v191"] = ep
    except Exception:
        pass
    # Caches legacy cuya clave usaba versiones de session_state. Limpiarlos evita
    # que una segunda cuenta reciba una capa interna vieja aunque el cache v199 ya
    # haya detectado la escritura.
    for _nombre_cache_v199 in [
        "_get_comisiones_fast_cache_v197",
        "_get_proyectos_investigacion_cache_v127",
        "_get_proyectos_extension_cache_v127",
        "_get_opciones_curriculares_cache_v127",
        "_get_opciones_curriculares_para_materia_cache_v127",
        "_materias_para_comisiones_detalle_cache_v196",
        "_materias_para_comisiones_unificadas_cache_v196",
        "_excel_comisiones_periodo_completado_cache_v175",
    ]:
        try:
            _fn_cache_v199 = globals().get(_nombre_cache_v199)
            if _fn_cache_v199 is not None and hasattr(_fn_cache_v199, "clear"):
                _fn_cache_v199.clear()
        except Exception:
            pass


# --- entry l. 44658
_get_periodos_legacy_v280 = get_periodos


# --- entry l. 44661-44668
def _modo_lectura_periodos_v280():
    try:
        from analisis.motor.ref.integration.periods_pilot import normalize_periods_mode
        return normalize_periods_mode(
            _valor_configuracion("DEPTIT_PERIODS_READ_MODE", "off")
        )
    except Exception:
        return "off"


# --- entry l. 44672-44682
def _get_periodos_nuevo_cache_v280(db_url, inst, dep, version):
    from analisis.motor.ref.integration.periods_pilot import (
        build_period_service,
        build_runtime_database,
    )

    # Reutiliza el pool PostgreSQL estable del monolito. El piloto no abre un
    # segundo pool ni aumenta artificialmente la presión de conexiones.
    db = build_runtime_database(_pg_raw_conn)
    service = build_period_service(db, int(inst), int(dep))
    return service.list()


# --- entry l. 44685-44712
def _guardar_diagnostico_periodos_v280(decision, inst=None, dep=None, error=None):
    try:
        diag = decision.diagnostics() if decision is not None else {}
    except Exception:
        diag = {}
    try:
        diag.update({
            "institucion_id": int(inst) if inst is not None else None,
            "departamento_id": int(dep) if dep is not None else None,
            "error": str(error)[:500] if error is not None else "",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        st.session_state["_v280_periods_read_diag"] = diag
        try:
            mostrar_stdout = str(_valor_configuracion("DEPTIT_PERIODS_DIAG_STDOUT", "0")).strip().casefold() in {"1", "true", "yes", "si", "sí"}
            if mostrar_stdout:
                print(
                    "[DEPTIT v280 períodos] "
                    f"mode={diag.get('mode')} source={diag.get('source')} "
                    f"equivalent={diag.get('equivalent')} "
                    f"inst={diag.get('institucion_id')} dep={diag.get('departamento_id')} "
                    f"legacy_rows={diag.get('legacy_rows')} new_rows={diag.get('new_rows')} "
                    f"reason={diag.get('reason')} error={diag.get('error')}"
                )
        except Exception:
            pass
    except Exception:
        pass


# --- entry l. 44723-44776
def get_periodos():
    legacy = _get_periodos_legacy_v280()
    mode = _modo_lectura_periodos_v280()

    # Default conservador: cero imports/costo adicional si el piloto está apagado.
    if mode == "off":
        try:
            from analisis.motor.ref.integration.periods_pilot import choose_periods_frame
            decision = choose_periods_frame(mode="off", legacy=legacy)
            _guardar_diagnostico_periodos_v280(decision)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)

    if not USE_POSTGRESQL or not DATABASE_URL:
        try:
            from analisis.motor.ref.integration.periods_pilot import choose_periods_frame
            decision = choose_periods_frame(
                mode=mode,
                legacy=legacy,
                new_error=RuntimeError("PostgreSQL no disponible para el piloto v280"),
            )
            _guardar_diagnostico_periodos_v280(decision)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)

    db_url = str(DATABASE_URL)
    inst = dep = None
    try:
        db_url, inst, dep, version = _scope_rendimiento_v191()
        new_df = _get_periodos_nuevo_cache_v280(
            str(db_url), int(inst), int(dep), version
        )
        from analisis.motor.ref.integration.periods_pilot import choose_periods_frame
        decision = choose_periods_frame(
            mode=mode,
            legacy=legacy,
            new=new_df,
        )
        _guardar_diagnostico_periodos_v280(decision, inst, dep)
        return _copiar_resultado_cache_v191(decision.frame)
    except Exception as exc:
        try:
            from analisis.motor.ref.integration.periods_pilot import choose_periods_frame
            decision = choose_periods_frame(
                mode=mode,
                legacy=legacy,
                new_error=exc,
            )
            _guardar_diagnostico_periodos_v280(decision, inst, dep, error=exc)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)


# --- entry l. 44788
_get_docentes_legacy_v281 = get_docentes


# --- entry l. 44791-44798
def _modo_lectura_docentes_v281():
    try:
        from analisis.motor.ref.integration.teachers_pilot import normalize_teachers_mode
        return normalize_teachers_mode(
            _valor_configuracion("DEPTIT_TEACHERS_READ_MODE", "off")
        )
    except Exception:
        return "off"


# --- entry l. 44802-44811
def _get_docentes_nuevo_cache_v281(db_url, inst, dep, version):
    from analisis.motor.ref.integration.teachers_pilot import (
        build_teacher_service,
    )
    from analisis.motor.ref.integration.periods_pilot import build_runtime_database

    # Reutiliza el pool PostgreSQL estable del monolito. No crea conexiones paralelas.
    db = build_runtime_database(_pg_raw_conn)
    service = build_teacher_service(db, int(inst), int(dep))
    return service.list_master()


# --- entry l. 44814-44841
def _guardar_diagnostico_docentes_v281(decision, inst=None, dep=None, error=None):
    try:
        diag = decision.diagnostics() if decision is not None else {}
    except Exception:
        diag = {}
    try:
        diag.update({
            "institucion_id": int(inst) if inst is not None else None,
            "departamento_id": int(dep) if dep is not None else None,
            "error": str(error)[:500] if error is not None else "",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        st.session_state["_v281_teachers_read_diag"] = diag
        try:
            mostrar_stdout = str(_valor_configuracion("DEPTIT_TEACHERS_DIAG_STDOUT", "0")).strip().casefold() in {"1", "true", "yes", "si", "sí"}
            if mostrar_stdout:
                print(
                    "[DEPTIT v281 docentes] "
                    f"mode={diag.get('mode')} source={diag.get('source')} "
                    f"equivalent={diag.get('equivalent')} "
                    f"inst={diag.get('institucion_id')} dep={diag.get('departamento_id')} "
                    f"legacy_rows={diag.get('legacy_rows')} new_rows={diag.get('new_rows')} "
                    f"reason={diag.get('reason')} error={diag.get('error')}"
                )
        except Exception:
            pass
    except Exception:
        pass


# --- entry l. 44852-44904
def get_docentes():
    legacy = _get_docentes_legacy_v281()
    mode = _modo_lectura_docentes_v281()

    if mode == "off":
        try:
            from analisis.motor.ref.integration.teachers_pilot import choose_teachers_frame
            decision = choose_teachers_frame(mode="off", legacy=legacy)
            _guardar_diagnostico_docentes_v281(decision)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)

    if not USE_POSTGRESQL or not DATABASE_URL:
        try:
            from analisis.motor.ref.integration.teachers_pilot import choose_teachers_frame
            decision = choose_teachers_frame(
                mode=mode,
                legacy=legacy,
                new_error=RuntimeError("PostgreSQL no disponible para el piloto v281"),
            )
            _guardar_diagnostico_docentes_v281(decision)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)

    db_url = str(DATABASE_URL)
    inst = dep = None
    try:
        db_url, inst, dep, version = _scope_rendimiento_v191()
        new_df = _get_docentes_nuevo_cache_v281(
            str(db_url), int(inst), int(dep), version
        )
        from analisis.motor.ref.integration.teachers_pilot import choose_teachers_frame
        decision = choose_teachers_frame(
            mode=mode,
            legacy=legacy,
            new=new_df,
        )
        _guardar_diagnostico_docentes_v281(decision, inst, dep)
        return _copiar_resultado_cache_v191(decision.frame)
    except Exception as exc:
        try:
            from analisis.motor.ref.integration.teachers_pilot import choose_teachers_frame
            decision = choose_teachers_frame(
                mode=mode,
                legacy=legacy,
                new_error=exc,
            )
            _guardar_diagnostico_docentes_v281(decision, inst, dep, error=exc)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)


# --- entry l. 44910
_get_comisiones_pre_v199 = get_comisiones


# --- entry l. 44913-44916
def _get_comisiones_cache_v199(periodo_id, solo_activas, db_url, inst, dep, version):
    if USE_POSTGRESQL and "_get_comisiones_fast_pg_v197" in globals():
        return _get_comisiones_fast_pg_v197(periodo_id=periodo_id, solo_activas=bool(solo_activas))
    return _get_comisiones_pre_v199(periodo_id=periodo_id, solo_activas=bool(solo_activas))


# --- entry l. 44919-44926
def get_comisiones(periodo_id=None, solo_activas=False):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _get_comisiones_cache_v199(
            int(periodo_id) if periodo_id is not None else None,
            bool(solo_activas), db_url, inst, dep, version
        )
    )


# --- entry l. 44939
_get_comisiones_legacy_v285 = get_comisiones


# --- entry l. 44942-44949
def _modo_lectura_comisiones_v285():
    try:
        from analisis.motor.ref.integration.commissions_pilot import normalize_commissions_mode
        return normalize_commissions_mode(
            _valor_configuracion("DEPTIT_COMMISSIONS_READ_MODE", "off")
        )
    except Exception:
        return "off"


# --- entry l. 44953-44960
def _get_comisiones_nuevo_cache_v285(periodo_id, solo_activas, db_url, inst, dep, version):
    from analisis.motor.ref.integration.commissions_pilot import build_commission_service
    from analisis.motor.ref.integration.periods_pilot import build_runtime_database

    db = build_runtime_database(_pg_raw_conn)
    service = build_commission_service(db, int(inst), int(dep))
    pid = int(periodo_id) if periodo_id is not None else None
    return service.list(period_id=pid, only_active=bool(solo_activas))


# --- entry l. 44963-45001
def _guardar_diagnostico_comisiones_v285(
    decision,
    *,
    inst=None,
    dep=None,
    periodo_id=None,
    solo_activas=False,
    error=None,
):
    try:
        diag = decision.diagnostics() if decision is not None else {}
    except Exception:
        diag = {}
    try:
        diag.update({
            "institucion_id": int(inst) if inst is not None else None,
            "departamento_id": int(dep) if dep is not None else None,
            "periodo_id": int(periodo_id) if periodo_id is not None else None,
            "solo_activas": bool(solo_activas),
            "error": str(error)[:500] if error is not None else "",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        st.session_state["_v285_commissions_read_diag"] = diag
        try:
            mostrar_stdout = str(_valor_configuracion("DEPTIT_COMMISSIONS_DIAG_STDOUT", "0")).strip().casefold() in {"1", "true", "yes", "si", "sí"}
            if mostrar_stdout:
                print(
                    "[DEPTIT v285 comisiones] "
                    f"mode={diag.get('mode')} source={diag.get('source')} "
                    f"equivalent={diag.get('equivalent')} "
                    f"inst={diag.get('institucion_id')} dep={diag.get('departamento_id')} "
                    f"periodo={diag.get('periodo_id')} solo_activas={diag.get('solo_activas')} "
                    f"legacy_rows={diag.get('legacy_rows')} new_rows={diag.get('new_rows')} "
                    f"reason={diag.get('reason')} error={diag.get('error')}"
                )
        except Exception:
            pass
    except Exception:
        pass


# --- entry l. 45011-45089
def get_comisiones(periodo_id=None, solo_activas=False):
    legacy = _get_comisiones_legacy_v285(
        periodo_id=periodo_id,
        solo_activas=solo_activas,
    )
    mode = _modo_lectura_comisiones_v285()

    if mode == "off":
        try:
            from analisis.motor.ref.integration.commissions_pilot import choose_commissions_frame
            decision = choose_commissions_frame(mode="off", legacy=legacy)
            _guardar_diagnostico_comisiones_v285(
                decision,
                periodo_id=periodo_id,
                solo_activas=solo_activas,
            )
        except Exception:
            pass
        return pd.DataFrame(legacy).copy()

    if not USE_POSTGRESQL or not DATABASE_URL:
        try:
            from analisis.motor.ref.integration.commissions_pilot import choose_commissions_frame
            decision = choose_commissions_frame(
                mode=mode,
                legacy=legacy,
                new_error=RuntimeError("PostgreSQL no disponible para el piloto v285"),
            )
            _guardar_diagnostico_comisiones_v285(
                decision,
                periodo_id=periodo_id,
                solo_activas=solo_activas,
            )
        except Exception:
            pass
        return pd.DataFrame(legacy).copy()

    inst = dep = None
    try:
        db_url, inst, dep, version = _scope_rendimiento_v191()
        if dep is None:
            raise RuntimeError("El piloto v285 requiere scope departamental explícito")
        new_df = _get_comisiones_nuevo_cache_v285(
            int(periodo_id) if periodo_id is not None else None,
            bool(solo_activas),
            str(db_url),
            int(inst),
            int(dep),
            version,
        )
        from analisis.motor.ref.integration.commissions_pilot import choose_commissions_frame
        decision = choose_commissions_frame(mode=mode, legacy=legacy, new=new_df)
        _guardar_diagnostico_comisiones_v285(
            decision,
            inst=inst,
            dep=dep,
            periodo_id=periodo_id,
            solo_activas=solo_activas,
        )
        return pd.DataFrame(decision.frame).copy()
    except Exception as exc:
        try:
            from analisis.motor.ref.integration.commissions_pilot import choose_commissions_frame
            decision = choose_commissions_frame(
                mode=mode,
                legacy=legacy,
                new_error=exc,
            )
            _guardar_diagnostico_comisiones_v285(
                decision,
                inst=inst,
                dep=dep,
                periodo_id=periodo_id,
                solo_activas=solo_activas,
                error=exc,
            )
        except Exception:
            pass
        return pd.DataFrame(legacy).copy()


# --- entry l. 45094
_get_horarios_comision_pre_v199 = get_horarios_comision


# --- entry l. 45095
_get_asignaciones_comision_pre_v199 = get_asignaciones_comision


# --- entry l. 45096
_get_materias_conceptuales_pre_v199 = get_materias_conceptuales_comision_v122


# --- entry l. 45099-45124
def _horarios_comisiones_todos_v199(db_url, inst, dep, version):
    if not USE_POSTGRESQL:
        return _get_horarios_comision_pre_v199(comision_id=None)
    df = _pg_read_dataframe("""
        SELECT h.id, h.comision_id, h.dia, h.hora_inicio, h.hora_fin, h.horas, h.observaciones
        FROM horarios_comision h
        WHERE h.institucion_id=%s AND h.departamento_id=%s
        ORDER BY h.comision_id,
                 CASE h.dia WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3
                      WHEN 'Jueves' THEN 4 WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6
                      WHEN 'Domingo' THEN 7 ELSE 99 END,
                 h.hora_inicio
    """, [int(inst), int(dep)])
    extras=["periodo","codigo_materia","asignatura","materia_especifica","carrera","escuela","plan_version","nombre_comision","turno","modalidad"]
    if df is None: df = pd.DataFrame()
    if df.empty:
        for c in extras: df[c]=""
        return df
    dfc = get_comisiones(periodo_id=None, solo_activas=False)
    if isinstance(dfc, pd.DataFrame) and not dfc.empty:
        cols=[c for c in ["id"]+extras if c in dfc.columns]
        df=df.merge(dfc[cols].rename(columns={"id":"comision_id"}),on="comision_id",how="left")
    else:
        for c in extras:
            if c not in df.columns: df[c]=""
    return df


# --- entry l. 45127-45133
def get_horarios_comision(comision_id=None):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    df = _horarios_comisiones_todos_v199(db_url, inst, dep, version)
    out = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if comision_id is not None and not out.empty:
        out = out[pd.to_numeric(out.get("comision_id"), errors="coerce").eq(int(comision_id))].copy()
    return out.reset_index(drop=True)


# --- entry l. 45137-45170
def _asignaciones_comisiones_todas_v199(db_url, inst, dep, version):
    if not USE_POSTGRESQL:
        return _get_asignaciones_comision_pre_v199(comision_id=None)
    df = _pg_read_dataframe("""
        SELECT a.id, a.comision_id, a.cuil,
               CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL
                    THEN doc.apellido || ', ' || doc.nombres
                    WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE a.cuil END AS docente,
               a.rol, a.horas_asignadas, a.estado,
               COALESCE(doc.tipo_docente,'Propio') AS tipo_docente,
               a.observaciones
        FROM asignaciones_docentes_comision a
        LEFT JOIN docentes doc
          ON doc.institucion_id=a.institucion_id
         AND doc.departamento_id=a.departamento_id
         AND regexp_replace(COALESCE(doc.cuil,''),'[^0-9]','','g')=
             regexp_replace(COALESCE(a.cuil,''),'[^0-9]','','g')
        WHERE a.institucion_id=%s AND a.departamento_id=%s
        ORDER BY a.comision_id, docente, a.rol
    """, [int(inst), int(dep)])
    extras=["periodo","codigo_materia","asignatura","materia_especifica","carrera","escuela","plan_version","nombre_comision"]
    if df is None: df = pd.DataFrame()
    if df.empty:
        for c in extras: df[c]=""
        return df
    dfc = get_comisiones(periodo_id=None, solo_activas=False)
    if isinstance(dfc, pd.DataFrame) and not dfc.empty:
        cols=[c for c in ["id"]+extras+["periodo_id"] if c in dfc.columns]
        meta=dfc[cols].rename(columns={"id":"comision_id", "periodo_id":"_periodo_id_v199"})
        df=df.merge(meta,on="comision_id",how="left")
    else:
        for c in extras:
            if c not in df.columns: df[c]=""
    return df


# --- entry l. 45173-45185
def get_asignaciones_comision(comision_id=None):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    df = _asignaciones_comisiones_todas_v199(db_url, inst, dep, version)
    out = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if comision_id is not None and not out.empty:
        out = out[pd.to_numeric(out.get("comision_id"), errors="coerce").eq(int(comision_id))].copy()
        pid = None
        if "_periodo_id_v199" in out.columns and not out.empty:
            try: pid = int(pd.to_numeric(out.iloc[0].get("_periodo_id_v199"), errors="coerce"))
            except Exception: pid = None
        if pid is not None and es_periodo_historico_contexto_v182(pid):
            out = _filtrar_asignaciones_comision_cierre_v183(out, pid)
    return out.drop(columns=["_periodo_id_v199"], errors="ignore").reset_index(drop=True)


# --- entry l. 45189-45202
def _vinculos_comisiones_todos_v199(db_url, inst, dep, version):
    if not USE_POSTGRESQL:
        return pd.DataFrame()
    return _pg_read_dataframe("""
        SELECT co.id AS comision_id, co.materia_id AS materia_principal_id,
               cm.materia_id AS materia_vinculada_id
        FROM comisiones co
        LEFT JOIN comision_materias cm
          ON cm.institucion_id=co.institucion_id
         AND cm.departamento_id=co.departamento_id
         AND cm.comision_id=co.id
        WHERE co.institucion_id=%s AND co.departamento_id=%s
        ORDER BY co.id, cm.id
    """, [int(inst), int(dep)])


# --- entry l. 45205-45236
def get_materias_conceptuales_comision_v122(comision_id):
    if not USE_POSTGRESQL:
        return _get_materias_conceptuales_pre_v199(comision_id)
    try: cid=int(comision_id)
    except Exception: return []
    db_url, inst, dep, version = _scope_rendimiento_v191()
    df=_vinculos_comisiones_todos_v199(db_url, inst, dep, version)
    sub=df[pd.to_numeric(df.get("comision_id"), errors="coerce").eq(cid)].copy() if isinstance(df,pd.DataFrame) and not df.empty else pd.DataFrame()
    if sub.empty:
        return []
    principal=None; ids=[]
    try:
        val=pd.to_numeric(sub.iloc[0].get("materia_principal_id"), errors="coerce")
        if not pd.isna(val): principal=int(val); ids.append(principal)
    except Exception: principal=None
    if "materia_vinculada_id" in sub.columns:
        ids.extend(pd.to_numeric(sub["materia_vinculada_id"], errors="coerce").dropna().astype(int).tolist())
    representantes=[]; claves=set(); principal_rep=None
    for mid in ids:
        info=get_materia_comision(mid) or {}
        if info:
            try: rep=int(info.get("materia_id_unificada") or info.get("materia_id") or mid)
            except Exception: rep=int(mid)
            clave=limpiar_texto_tabla(info.get("_clave_unica", "")) or _clave_materia_conceptual_v137(info) or f"ID:{rep}"
        else:
            rep=int(mid); clave=f"ID:{rep}"
        if principal is not None and int(mid)==int(principal): principal_rep=rep
        if clave in claves: continue
        claves.add(clave); representantes.append(rep)
    if principal_rep is not None and principal_rep in representantes:
        representantes=[principal_rep]+[x for x in representantes if x!=principal_rep]
    return representantes


# --- entry l. 45239
_get_horarios_reales_asignacion_pre_v199 = get_horarios_reales_asignacion


# --- entry l. 45242-45260
def _horarios_personalizados_todos_v199(db_url, inst, dep, version):
    if not USE_POSTGRESQL:
        return pd.DataFrame(), pd.DataFrame()
    asign = _pg_read_dataframe("""
        SELECT id AS asignacion_id, comision_id,
               COALESCE(usa_horario_personalizado,FALSE) AS usa_horario_personalizado
        FROM asignaciones_docentes_comision
        WHERE institucion_id=%s AND departamento_id=%s
    """, [int(inst), int(dep)])
    hrs = _pg_read_dataframe("""
        SELECT id, asignacion_id, horario_comision_id, dia, hora_inicio, hora_fin, horas, observaciones
        FROM horarios_asignacion_docente_comision
        WHERE institucion_id=%s AND departamento_id=%s
        ORDER BY asignacion_id,
                 CASE dia WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3
                          WHEN 'Jueves' THEN 4 WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6
                          WHEN 'Domingo' THEN 7 ELSE 99 END, hora_inicio
    """, [int(inst), int(dep)])
    return asign, hrs


# --- entry l. 45263-45288
def get_horarios_reales_asignacion(asignacion_id):
    if not USE_POSTGRESQL:
        return _get_horarios_reales_asignacion_pre_v199(asignacion_id)
    try: aid=int(asignacion_id)
    except Exception:
        return pd.DataFrame(columns=["id","asignacion_id","horario_comision_id","dia","hora_inicio","hora_fin","horas","observaciones"])
    db_url, inst, dep, version = _scope_rendimiento_v191()
    asign, hrs = _horarios_personalizados_todos_v199(db_url, inst, dep, version)
    if not isinstance(asign,pd.DataFrame) or asign.empty:
        return pd.DataFrame(columns=["id","asignacion_id","horario_comision_id","dia","hora_inicio","hora_fin","horas","observaciones"])
    sub=asign[pd.to_numeric(asign.get("asignacion_id"),errors="coerce").eq(aid)]
    if sub.empty:
        return pd.DataFrame(columns=["id","asignacion_id","horario_comision_id","dia","hora_inicio","hora_fin","horas","observaciones"])
    personalizado=bool(sub.iloc[0].get("usa_horario_personalizado",False))
    cid=int(sub.iloc[0].get("comision_id"))
    if personalizado:
        out=hrs[pd.to_numeric(hrs.get("asignacion_id"),errors="coerce").eq(aid)].copy() if isinstance(hrs,pd.DataFrame) and not hrs.empty else pd.DataFrame()
        return out.reset_index(drop=True)
    df=get_horarios_comision(cid)
    if df is None or df.empty:
        return pd.DataFrame(columns=["id","asignacion_id","horario_comision_id","dia","hora_inicio","hora_fin","horas","observaciones"])
    return pd.DataFrame({
        "id":[None]*len(df), "asignacion_id":[aid]*len(df), "horario_comision_id":df["id"].tolist(),
        "dia":df["dia"].tolist(), "hora_inicio":df["hora_inicio"].tolist(), "hora_fin":df["hora_fin"].tolist(),
        "horas":df["horas"].tolist(), "observaciones":[""]*len(df),
    })


# --- entry l. 45295-45342
def _proyectos_raw_bulk_v199(tipo, solo_activos, db_url, inst_id, inst_version):
    if not USE_POSTGRESQL:
        fn = _get_proyectos_investigacion_pre_v182 if tipo == "investigacion" else _get_proyectos_extension_pre_v182
        return fn(solo_activos=bool(solo_activos), periodo_id=None)
    tabla_p = "proyectos_investigacion" if tipo == "investigacion" else "proyectos_extension"
    tabla_a = "investigacion_docente" if tipo == "investigacion" else "extension_docente"
    filtro = "AND COALESCE(pr.estado, 'Activo')='Activo'" if solo_activos else ""
    return _pg_read_dataframe(f"""
        WITH agg AS (
            SELECT
                proyecto_id,
                COUNT(*) FILTER (WHERE COALESCE(estado_asignacion,'Activa')='Activa') AS cantidad_asignaciones,
                COUNT(*) FILTER (WHERE LOWER(TRIM(COALESCE(estado_asignacion,'Activa'))) <> 'baja') AS cantidad_asignaciones_historicas,
                COUNT(*) AS cantidad_asignaciones_registradas,
                COUNT(DISTINCT cuil) FILTER (WHERE COALESCE(estado_asignacion,'Activa')='Activa') AS cantidad_docentes,
                COUNT(DISTINCT cuil) AS cantidad_docentes_historicos,
                COUNT(DISTINCT departamento_id) AS cantidad_departamentos,
                COALESCE(SUM(horas_asignadas) FILTER (WHERE LOWER(TRIM(COALESCE(estado_asignacion,'Activa'))) <> 'baja'),0) AS horas_asignadas_historicas
            FROM {tabla_a}
            WHERE institucion_id=%s
            GROUP BY proyecto_id
        )
        SELECT
            pr.id, pr.nombre_proyecto,
            COALESCE(pr.codigo_proyecto,'') AS codigo_proyecto,
            COALESCE(pr.instituto_proyecto,'') AS instituto_proyecto,
            pr.anio_llamado, pr.fecha_inicio, pr.fecha_fin,
            COALESCE(pr.periodo_ejecucion,'') AS periodo_ejecucion,
            COALESCE(pr.observaciones,'') AS observaciones,
            COALESCE(pr.estado,'Activo') AS estado,
            pr.fecha_carga, pr.fecha_suspension,
            COALESCE(pr.motivo_suspension,'') AS motivo_suspension,
            pr.departamento_id AS departamento_creador_id,
            COALESCE(dep.nombre,'') AS departamento_creador,
            COALESCE(a.cantidad_asignaciones,0) AS cantidad_asignaciones,
            COALESCE(a.cantidad_asignaciones_historicas,0) AS cantidad_asignaciones_historicas,
            COALESCE(a.cantidad_asignaciones_registradas,0) AS cantidad_asignaciones_registradas,
            COALESCE(a.cantidad_docentes,0) AS cantidad_docentes,
            COALESCE(a.cantidad_docentes_historicos,0) AS cantidad_docentes_historicos,
            COALESCE(a.cantidad_departamentos,0) AS cantidad_departamentos,
            COALESCE(a.horas_asignadas_historicas,0) AS horas_asignadas_historicas
        FROM {tabla_p} pr
        LEFT JOIN departamentos dep
          ON dep.id=pr.departamento_id AND dep.institucion_id=pr.institucion_id
        LEFT JOIN agg a ON a.proyecto_id=pr.id
        WHERE pr.institucion_id=%s {filtro}
        ORDER BY COALESCE(pr.fecha_fin, '9999-12-31') DESC, pr.nombre_proyecto
    """, [int(inst_id), int(inst_id)])


# --- entry l. 45345-45377
def _get_proyectos_v199(tipo, solo_activos=False, periodo_id=None):
    inst = int(_pg_current_inst_id() or 0) if USE_POSTGRESQL else 0
    iv, _dv, _ep = _versiones_scope_v199(inst, int(_pg_current_dep_id() or 0) if USE_POSTGRESQL else 0)
    historico = bool(periodo_id is not None and es_periodo_historico_contexto_v182(periodo_id))
    # En histórico se conserva la regla v182: un proyecto hoy finalizado/suspendido
    # no desaparece del semestre en que estaba vigente.
    raw = _proyectos_raw_bulk_v199(
        str(tipo), False if historico else bool(solo_activos), str(DATABASE_URL), inst, iv
    )
    df = raw.copy() if isinstance(raw, pd.DataFrame) else pd.DataFrame()
    if df.empty:
        return df
    periodo = None
    if periodo_id is not None:
        try:
            dfp = get_periodos()
            fila = dfp[pd.to_numeric(dfp.get("id"), errors="coerce").eq(int(periodo_id))]
            if not fila.empty:
                periodo = fila.iloc[0].to_dict()
        except Exception:
            periodo = None
    ref = fecha_referencia_contexto_v182(periodo_id) if historico else None
    df["situacion"] = df.apply(
        lambda r: _situacion_proyecto(r.to_dict(), ref) if historico else _situacion_proyecto(r.to_dict()),
        axis=1,
    )
    permiso = _puede_administrar_proyecto_investigacion if tipo == "investigacion" else _puede_administrar_proyecto_extension
    df["puede_administrar"] = df.apply(lambda r: permiso(r.to_dict()), axis=1)
    if periodo is not None:
        df = df[df.apply(lambda r: proyecto_vigente_en_periodo(r.to_dict(), periodo), axis=1)].copy()
    if historico:
        df["fecha_referencia_contexto"] = str(ref)
    return df.reset_index(drop=True)


# --- entry l. 45380-45381
def get_proyectos_investigacion(solo_activos=False, periodo_id=None):
    return _get_proyectos_v199("investigacion", solo_activos=solo_activos, periodo_id=periodo_id)


# --- entry l. 45384-45385
def get_proyectos_extension(solo_activos=False, periodo_id=None):
    return _get_proyectos_v199("extension", solo_activos=solo_activos, periodo_id=periodo_id)


# --- entry l. 45398
_get_proyectos_investigacion_legacy_v283 = get_proyectos_investigacion


# --- entry l. 45399
_get_proyectos_extension_legacy_v283 = get_proyectos_extension


# --- entry l. 45402-45409
def _modo_lectura_proyectos_v283():
    try:
        from analisis.motor.ref.integration.projects_pilot import normalize_projects_mode
        return normalize_projects_mode(
            _valor_configuracion("DEPTIT_PROJECTS_READ_MODE", "off")
        )
    except Exception:
        return "off"


# --- entry l. 45413-45424
def _get_proyectos_nuevo_cache_v283(tipo, solo_activos, periodo_id, db_url, inst, dep, version, role):
    from analisis.motor.ref.integration.projects_pilot import build_project_service
    from analisis.motor.ref.integration.periods_pilot import build_runtime_database

    db = build_runtime_database(_pg_raw_conn)
    service = build_project_service(db, int(inst), int(dep), role=str(role or ""))
    pid = int(periodo_id) if periodo_id is not None else None
    return service.list(
        str(tipo),
        only_active=bool(solo_activos),
        period_id=pid,
    )


# --- entry l. 45427-45468
def _guardar_diagnostico_proyectos_v283(
    decision,
    *,
    tipo,
    inst=None,
    dep=None,
    periodo_id=None,
    solo_activos=False,
    error=None,
):
    try:
        diag = decision.diagnostics() if decision is not None else {}
    except Exception:
        diag = {}
    try:
        tipo = str(tipo or "")
        diag.update({
            "tipo": tipo,
            "institucion_id": int(inst) if inst is not None else None,
            "departamento_id": int(dep) if dep is not None else None,
            "periodo_id": int(periodo_id) if periodo_id is not None else None,
            "solo_activos": bool(solo_activos),
            "error": str(error)[:500] if error is not None else "",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        st.session_state[f"_v283_projects_read_diag_{tipo}"] = diag
        try:
            mostrar_stdout = str(_valor_configuracion("DEPTIT_PROJECTS_DIAG_STDOUT", "0")).strip().casefold() in {"1", "true", "yes", "si", "sí"}
            if mostrar_stdout:
                print(
                    "[DEPTIT v283 proyectos] "
                    f"kind={diag.get('kind') or tipo} mode={diag.get('mode')} source={diag.get('source')} "
                    f"equivalent={diag.get('equivalent')} "
                    f"inst={diag.get('institucion_id')} dep={diag.get('departamento_id')} "
                    f"periodo={diag.get('periodo_id')} solo_activos={diag.get('solo_activos')} "
                    f"legacy_rows={diag.get('legacy_rows')} new_rows={diag.get('new_rows')} "
                    f"reason={diag.get('reason')} error={diag.get('error')}"
                )
        except Exception:
            pass
    except Exception:
        pass


# --- entry l. 45479-45566
def _get_proyectos_piloto_v283(tipo, solo_activos=False, periodo_id=None):
    tipo = str(tipo or "").strip().casefold()
    legacy_fn = (
        _get_proyectos_investigacion_legacy_v283
        if tipo == "investigacion"
        else _get_proyectos_extension_legacy_v283
    )
    legacy = legacy_fn(solo_activos=solo_activos, periodo_id=periodo_id)
    mode = _modo_lectura_proyectos_v283()

    if mode == "off":
        try:
            from analisis.motor.ref.integration.projects_pilot import choose_projects_frame
            decision = choose_projects_frame(kind=tipo, mode="off", legacy=legacy)
            _guardar_diagnostico_proyectos_v283(
                decision, tipo=tipo, periodo_id=periodo_id, solo_activos=solo_activos
            )
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)

    if not USE_POSTGRESQL or not DATABASE_URL:
        try:
            from analisis.motor.ref.integration.projects_pilot import choose_projects_frame
            decision = choose_projects_frame(
                kind=tipo,
                mode=mode,
                legacy=legacy,
                new_error=RuntimeError("PostgreSQL no disponible para el piloto v283"),
            )
            _guardar_diagnostico_proyectos_v283(
                decision, tipo=tipo, periodo_id=periodo_id, solo_activos=solo_activos
            )
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)

    inst = dep = None
    try:
        db_url, inst, dep, version = _scope_rendimiento_v191()
        role = current_role()
        new_df = _get_proyectos_nuevo_cache_v283(
            tipo,
            bool(solo_activos),
            int(periodo_id) if periodo_id is not None else None,
            str(db_url),
            int(inst),
            int(dep),
            version,
            str(role or ""),
        )
        from analisis.motor.ref.integration.projects_pilot import choose_projects_frame
        decision = choose_projects_frame(
            kind=tipo,
            mode=mode,
            legacy=legacy,
            new=new_df,
        )
        _guardar_diagnostico_proyectos_v283(
            decision,
            tipo=tipo,
            inst=inst,
            dep=dep,
            periodo_id=periodo_id,
            solo_activos=solo_activos,
        )
        return _copiar_resultado_cache_v191(decision.frame)
    except Exception as exc:
        try:
            from analisis.motor.ref.integration.projects_pilot import choose_projects_frame
            decision = choose_projects_frame(
                kind=tipo,
                mode=mode,
                legacy=legacy,
                new_error=exc,
            )
            _guardar_diagnostico_proyectos_v283(
                decision,
                tipo=tipo,
                inst=inst,
                dep=dep,
                periodo_id=periodo_id,
                solo_activos=solo_activos,
                error=exc,
            )
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)


# --- entry l. 45569-45572
def get_proyectos_investigacion(solo_activos=False, periodo_id=None):
    return _get_proyectos_piloto_v283(
        "investigacion", solo_activos=solo_activos, periodo_id=periodo_id
    )


# --- entry l. 45575-45578
def get_proyectos_extension(solo_activos=False, periodo_id=None):
    return _get_proyectos_piloto_v283(
        "extension", solo_activos=solo_activos, periodo_id=periodo_id
    )


# --- entry l. 46304-46309
def _registro_dependencias_v200():
    return {
        "lock": threading.RLock(),
        "inst": {},
        "dep": {},
    }


# --- entry l. 46312-46314
def _categorias_mutacion_v200(motivo):
    from analisis.motor.ref.common.cache_categories import _categorias_mutacion_v200 as _b05_core__categorias_mutacion_v200
    return _b05_core__categorias_mutacion_v200(motivo)


# --- entry l. 46317-46335
def _bump_dependencias_v200(motivo):
    cats = _categorias_mutacion_v200(motivo)
    try:
        inst = int(_pg_current_inst_id() or 0) if USE_POSTGRESQL else 0
    except Exception:
        inst = 0
    try:
        dep = int(_pg_current_dep_id() or 0) if USE_POSTGRESQL else 0
    except Exception:
        dep = 0

    reg = _registro_dependencias_v200()
    with reg["lock"]:
        inst_map = reg["inst"].setdefault(inst, {})
        dep_map = reg["dep"].setdefault((inst, dep), {})
        for cat in cats:
            inst_map[cat] = int(inst_map.get(cat, 0) or 0) + 1
            dep_map[cat] = int(dep_map.get(cat, 0) or 0) + 1
    return cats


# --- entry l. 46338-46354
def _version_dependencias_v200(categorias, inst=None, dep=None):
    if inst is None:
        try: inst = int(_pg_current_inst_id() or 0) if USE_POSTGRESQL else 0
        except Exception: inst = 0
    if dep is None:
        try: dep = int(_pg_current_dep_id() or 0) if USE_POSTGRESQL else 0
        except Exception: dep = 0

    cats = tuple(sorted(set(categorias or ()) | {"global"}))
    reg = _registro_dependencias_v200()
    with reg["lock"]:
        im = reg["inst"].get(int(inst or 0), {})
        dm = reg["dep"].get((int(inst or 0), int(dep or 0)), {})
        return tuple(
            (cat, int(im.get(cat, 0) or 0), int(dm.get(cat, 0) or 0))
            for cat in cats
        )


# --- entry l. 46357
_invalidar_cache_rendimiento_pre_v200 = invalidar_cache_rendimiento_v191


# --- entry l. 46359-46367
def invalidar_cache_rendimiento_v191(motivo="actualización"):
    # Mantiene toda la invalidación/diagnóstico heredada y agrega una capa fina
    # utilizada por los wrappers finales de v200.
    _invalidar_cache_rendimiento_pre_v200(motivo)
    try:
        cats = _bump_dependencias_v200(motivo)
        st.session_state["_perf_dependencias_v200"] = ", ".join(sorted(cats))
    except Exception:
        pass


# --- entry l. 46509
_obtener_cargo_prioritario_pre_v200 = obtener_cargo_prioritario_docente_periodo


# --- entry l. 46512-46663
def _mapa_cargos_prioritarios_v200(periodo_id, dep_contexto, inst_id, version_dep):
    if not USE_POSTGRESQL:
        return {}

    try:
        df_dep = _pg_read_dataframe(
            """
            SELECT id, nombre
            FROM departamentos
            WHERE institucion_id=%s
            ORDER BY id
            """,
            [int(inst_id)],
        )
    except Exception:
        df_dep = pd.DataFrame()

    dep_por_nombre = {}
    if isinstance(df_dep, pd.DataFrame) and not df_dep.empty:
        for _, r in df_dep.iterrows():
            k = normalizar_clave(r.get("nombre", ""))
            if k:
                dep_por_nombre[k] = int(r.get("id"))

    try:
        df_doc = _pg_read_dataframe(
            """
            SELECT cuil,
                   COALESCE(tipo_docente,'Propio') AS tipo_docente,
                   COALESCE(observaciones,'') AS observaciones
            FROM docentes
            WHERE institucion_id=%s
              AND departamento_id=%s
            ORDER BY id
            """,
            [int(inst_id), int(dep_contexto)],
        )
    except Exception:
        df_doc = pd.DataFrame()

    try:
        df_des = _pg_read_dataframe(
            f"""
            WITH pr AS (
                SELECT id, institucion_id, nombre, anio, semestre
                FROM periodos
                WHERE id=%s
                LIMIT 1
            )
            SELECT
                d.cuil, d.cargo, d.departamento_id,
                COALESCE(dep.nombre,'') AS departamento
            FROM designaciones d
            JOIN periodos p ON p.id=d.periodo_id
            JOIN pr ON {_condicion_periodo_equivalente_sql('p','pr')}
            LEFT JOIN departamentos dep ON dep.id=d.departamento_id
            WHERE d.institucion_id=%s
              AND d.estado='Activa'
              AND COALESCE(TRIM(d.cargo),'') <> ''
            """,
            [int(periodo_id), int(inst_id)],
        )
    except Exception:
        df_des = pd.DataFrame()

    tipos = {}
    if isinstance(df_doc, pd.DataFrame) and not df_doc.empty:
        for _, r in df_doc.iterrows():
            k = _clave_cuil(r.get("cuil"))
            if not k:
                continue
            tipos[k] = {
                "tipo": str(r.get("tipo_docente") or "Propio"),
                "obs": str(r.get("observaciones") or ""),
            }

    grupos = {}
    if isinstance(df_des, pd.DataFrame) and not df_des.empty:
        aux = df_des.copy()
        aux["_cuil_v200"] = aux["cuil"].fillna("").astype(str).map(_clave_cuil)
        for k, g in aux.groupby("_cuil_v200", sort=False):
            if k:
                grupos[str(k)] = g.copy()

    prioridad = {cargo: i for i, cargo in enumerate(ORDEN_JERARQUICO_CARGOS_COMISION)}
    claves = set(grupos) | set(tipos)
    salida = {}

    for k in claves:
        meta = tipos.get(k, {"tipo": "Propio", "obs": ""})
        es_prestado = normalizar_clave(meta.get("tipo", "")) == "PRESTADO"
        dep_esperado = int(dep_contexto)
        dep_origen_nombre = ""

        if es_prestado:
            dep_origen_nombre = _extraer_departamento_origen_prestado(meta.get("obs", ""))
            dep_esperado = dep_por_nombre.get(normalizar_clave(dep_origen_nombre))

        g = grupos.get(k, pd.DataFrame())
        candidatos = pd.DataFrame()
        if isinstance(g, pd.DataFrame) and not g.empty:
            if es_prestado:
                if dep_esperado is not None:
                    candidatos = g[
                        pd.to_numeric(g["departamento_id"], errors="coerce")
                        .fillna(-1).astype(int).eq(int(dep_esperado))
                    ].copy()
                    if candidatos.empty:
                        candidatos = g[
                            ~pd.to_numeric(g["departamento_id"], errors="coerce")
                            .fillna(-1).astype(int).eq(int(dep_contexto))
                        ].copy()
                else:
                    candidatos = g[
                        ~pd.to_numeric(g["departamento_id"], errors="coerce")
                        .fillna(-1).astype(int).eq(int(dep_contexto))
                    ].copy()
            else:
                candidatos = g[
                    pd.to_numeric(g["departamento_id"], errors="coerce")
                    .fillna(-1).astype(int).eq(int(dep_contexto))
                ].copy()

        if candidatos.empty:
            salida[k] = {
                "cargo": "",
                "departamento": dep_origen_nombre,
                "motivo": (
                    f"No se encontró una designación activa en {dep_origen_nombre} para el período de la comisión."
                    if dep_origen_nombre
                    else "No se encontró designación activa."
                ),
            }
            continue

        candidatos = candidatos.copy()
        candidatos["cargo_canonico"] = candidatos["cargo"].map(_normalizar_cargo_para_jerarquia)
        candidatos["_prioridad"] = candidatos["cargo_canonico"].map(prioridad).fillna(999)
        candidatos = candidatos.sort_values(
            ["_prioridad", "departamento", "cargo_canonico"],
            kind="stable",
        )
        elegido = candidatos.iloc[0]
        cargo = str(elegido.get("cargo_canonico") or elegido.get("cargo") or "").strip()
        departamento = str(elegido.get("departamento") or dep_origen_nombre or "").strip()
        salida[k] = {
            "cargo": cargo,
            "departamento": departamento,
            "motivo": f"Cargo activo de {departamento}." if departamento else "Cargo activo detectado.",
        }

    return salida


# --- entry l. 46666-46694
def obtener_cargo_prioritario_docente_periodo(cuil, periodo_id, departamento_contexto_id=None):
    if not USE_POSTGRESQL:
        return _obtener_cargo_prioritario_pre_v200(
            cuil, periodo_id, departamento_contexto_id
        )
    cuil_limpio = limpiar_cuil(cuil)
    if not cuil_limpio or periodo_id is None:
        return {"cargo": "", "departamento": "", "motivo": "Falta CUIL o período."}
    try:
        inst = int(_pg_current_inst_id() or 0)
        dep = int(departamento_contexto_id or _pg_current_dep_id() or 0)
        version_dep = _version_dependencias_v200(
            ("docentes", "designaciones", "prestamos", "periodos"),
            inst,
            dep,
        )
        mapa = _mapa_cargos_prioritarios_v200(
            int(periodo_id), dep, inst, version_dep
        )
        dato = mapa.get(_clave_cuil(cuil_limpio))
        if dato is not None:
            return dict(dato)
    except Exception:
        pass

    # Fallback exacto a la lógica histórica si aparece un caso no contemplado.
    return _obtener_cargo_prioritario_pre_v200(
        cuil, periodo_id, departamento_contexto_id
    )


# --- entry l. 47458-47692
def _docentes_asignables_proyectos_institucional_pg_v276(periodo_id):
    """Padrón EXACTO del Consolidado institucional para Investigación/Extensión.

    Regla v276:
    - La pertenencia al selector NO se decide desde ``designaciones``.
    - Se toma literalmente el conjunto de CUIL que el Consolidado institucional
      cuenta como "Docentes únicos por CUIL" en la foto actual de cada departamento.
    - Las designaciones sirven únicamente para enriquecer Cargo/Dedicación/Horas.
      Si una designación legacy es inválida y el saneamiento v265 la descarta, el
      docente NO desaparece del selector: conserva su identidad desde el Plantel.
    - Por construcción, antes de quitar a quienes ya están asignados a un proyecto,
      la cantidad de candidatos coincide con el total de docentes únicos del
      Consolidado institucional.
    """
    columnas_salida = [
        "cuil", "nombre_completo", "legajo", "tipo_docente",
        "departamento_origen", "es_externo", "horas_designadas",
        "cargo", "cargo_final", "dedicacion",
        "estado_docente_base", "advertencia_disponibilidad",
    ]
    if not USE_POSTGRESQL:
        return pd.DataFrame(columns=columnas_salida)

    try:
        inst_id = int(_pg_current_inst_id() or 0)
        _ = int(periodo_id)
    except Exception:
        return pd.DataFrame(columns=columnas_salida)
    if inst_id <= 0:
        return pd.DataFrame(columns=columnas_salida)

    try:
        df_resumen, df_doc, df_des_raw, cuiles_unicos = _consolidado_desde_listados_reales_v240(inst_id)
    except Exception:
        return pd.DataFrame(columns=columnas_salida)

    df_doc = df_doc.copy() if isinstance(df_doc, pd.DataFrame) else pd.DataFrame()
    df_des_raw = df_des_raw.copy() if isinstance(df_des_raw, pd.DataFrame) else pd.DataFrame()
    cuiles_unicos = {str(x) for x in (cuiles_unicos or set()) if str(x).strip()}

    if not cuiles_unicos:
        out = pd.DataFrame(columns=columnas_salida)
        out.attrs["consolidado_docentes_unicos_v276"] = 0
        out.attrs["selector_docentes_unicos_v276"] = 0
        out.attrs["diagnostico_v276"] = []
        return out

    diagnosticos = []

    # Las designaciones no habilitan/excluyen docentes. Solo se usan como datos de
    # enriquecimiento y se sanean para no volver a mostrar campos concatenados.
    df_des_limpias = pd.DataFrame()
    if not df_des_raw.empty:
        partes_limpias = []
        if "departamento_origen" in df_des_raw.columns:
            grupos_dep = list(df_des_raw.groupby(df_des_raw["departamento_origen"].fillna("").astype(str), dropna=False))
        else:
            grupos_dep = [("", df_des_raw)]
        for dep_nom, sub in grupos_dep:
            sub = sub.copy()
            antes = len(sub)
            limpia = _sanear_designaciones_institucionales_v265(sub)
            removidas = max(antes - len(limpia), 0)
            if removidas:
                diagnosticos.append(
                    f"{limpiar_texto_tabla(dep_nom) or 'Departamento sin identificar'}: "
                    f"{removidas} designación/es activa/s legacy o estructuralmente inválida/s "
                    "fueron omitidas SOLO para Cargo/Dedicación/Horas. Sus docentes siguen disponibles "
                    "porque el padrón lo determina el Consolidado institucional."
                )
            if isinstance(limpia, pd.DataFrame) and not limpia.empty:
                partes_limpias.append(limpia)
        if partes_limpias:
            df_des_limpias = pd.concat(partes_limpias, ignore_index=True, sort=False)

    # Índices por CUIL normalizado.
    grupos_doc = {}
    if not df_doc.empty:
        for _, r in df_doc.iterrows():
            k = _clave_cuil(r.get("cuil"))
            if k:
                grupos_doc.setdefault(k, []).append(r.to_dict())

    grupos_des = {}
    if not df_des_limpias.empty:
        for _, r in df_des_limpias.iterrows():
            k = _clave_cuil(r.get("cuil"))
            if k:
                grupos_des.setdefault(k, []).append(r.to_dict())

    def _texto_primero(rows, *cols):
        for r in rows:
            for col in cols:
                v = limpiar_texto_tabla(r.get(col, ""))
                if v:
                    return v
        return ""

    def _score_identidad(r):
        tipo = limpiar_texto_tabla(r.get("tipo_docente", "Propio")) or "Propio"
        nom = limpiar_texto_tabla(r.get("nombre_completo", r.get("nombre", "")))
        leg = limpiar_texto_tabla(r.get("legajo", ""))
        return (0 if tipo.casefold() != "prestado" else 1, 0 if nom else 1, 0 if leg else 1)

    filas = []
    for clave in sorted(cuiles_unicos):
        docs = list(grupos_doc.get(clave, []))
        desigs = list(grupos_des.get(clave, []))
        ident = sorted(docs, key=_score_identidad)[0] if docs else {}

        cuil_mostrar = _texto_primero(docs, "cuil") or _texto_primero(desigs, "cuil") or clave
        nombre = _texto_primero(docs, "nombre_completo", "docente", "nombre") or cuil_mostrar
        legajo = _texto_primero(docs, "legajo")

        # Propio si existe al menos una identidad propia institucional; Prestado solo
        # cuando todas las filas visibles del mismo CUIL son Prestado.
        tipos = [limpiar_texto_tabla(r.get("tipo_docente", "Propio")) or "Propio" for r in docs]
        tipo_real = "Propio" if any(t.casefold() != "prestado" for t in tipos) else (tipos[0] if tipos else "Propio")

        # v278: "Departamento de origen" no es lo mismo que departamento donde el
        # docente aparece operativamente. Un Prestado integra el Plantel del receptor,
        # pero ese receptor NO es su origen. Solo se muestran departamentos en los que
        # existe una designación activa propia y la identidad local no es Prestado.
        tipo_por_dep = {}
        for r in docs:
            dep = limpiar_texto_tabla(r.get("departamento_origen", r.get("departamento", "")))
            if not dep:
                continue
            tipo_r = limpiar_texto_tabla(r.get("tipo_docente", "Propio")) or "Propio"
            clave_dep = normalizar_clave(dep)
            # Si hay filas repetidas del mismo departamento, Propio prevalece sobre Prestado.
            previo = tipo_por_dep.get(clave_dep)
            if previo is None or (str(previo).casefold() == "prestado" and tipo_r.casefold() != "prestado"):
                tipo_por_dep[clave_dep] = tipo_r

        departamentos = []
        for r in desigs:
            dep = limpiar_texto_tabla(r.get("departamento_origen", r.get("departamento", "")))
            if not dep:
                continue
            tipo_dep = tipo_por_dep.get(normalizar_clave(dep), "")
            # Si Plantel identifica explícitamente ese departamento como Prestado, no
            # puede convertirse en origen aunque exista una fila legacy de designación.
            if str(tipo_dep).casefold() == "prestado":
                continue
            if dep not in departamentos:
                departamentos.append(dep)

        # Respaldo conservador: si todas las designaciones fueron saneadas por legado,
        # usamos solo departamentos del Plantel donde la identidad sea Propio. Nunca
        # incorporamos receptores Prestado como origen.
        if not departamentos:
            for r in docs:
                tipo_r = limpiar_texto_tabla(r.get("tipo_docente", "Propio")) or "Propio"
                if tipo_r.casefold() == "prestado":
                    continue
                dep = limpiar_texto_tabla(r.get("departamento_origen", r.get("departamento", "")))
                if dep and dep not in departamentos:
                    departamentos.append(dep)

        cargos, dedicaciones = [], []
        total_horas = 0.0
        for r in desigs:
            cargo_raw = limpiar_texto_tabla(r.get("cargo", ""))
            cargo = _normalizar_cargo_para_jerarquia(cargo_raw) if cargo_raw else ""
            dedic = limpiar_texto_tabla(r.get("dedicacion", ""))
            if cargo and cargo in CARGOS and cargo not in cargos:
                cargos.append(cargo)
            if dedic and dedic not in dedicaciones:
                dedicaciones.append(dedic)
            try:
                total_horas += float(horas_segun_dedicacion(dedic, r.get("horas", 0)) or 0)
            except Exception:
                try:
                    total_horas += float(r.get("horas", 0) or 0)
                except Exception:
                    pass

        # Si todas las designaciones del docente fueron descartadas por legado, NO
        # inventamos cargo. Para horas usamos la foto del Plantel/Consolidado como
        # respaldo, procurando no duplicar un préstamo receptor.
        advertencias = []
        if not desigs:
            horas_propias = []
            horas_todas = []
            for r in docs:
                try:
                    hs = float(pd.to_numeric(r.get("horas_activas", r.get("horas_registradas_periodo", 0)), errors="coerce") or 0)
                except Exception:
                    hs = 0.0
                horas_todas.append(hs)
                tipo_r = limpiar_texto_tabla(r.get("tipo_docente", "Propio")) or "Propio"
                if tipo_r.casefold() != "prestado":
                    horas_propias.append(hs)
            total_horas = sum(horas_propias) if horas_propias else (max(horas_todas) if horas_todas else 0.0)
            advertencias.append(
                "Docente habilitado por el Consolidado institucional; no se usa un cargo legacy inválido para mostrar información."
            )

        filas.append({
            "cuil": cuil_mostrar,
            "nombre_completo": nombre,
            "legajo": legajo,
            "tipo_docente": tipo_real,
            "departamento_origen": " / ".join(departamentos),
            "es_externo": 0,
            "horas_designadas": round(total_horas, 2),
            "cargo": " / ".join(cargos),
            "cargo_final": " / ".join(cargos),
            "dedicacion": " / ".join(dedicaciones),
            "estado_docente_base": "Activo en el período",
            "advertencia_disponibilidad": " | ".join(advertencias),
        })

    out = pd.DataFrame(filas, columns=columnas_salida)
    if not out.empty:
        # Blindaje final: un único registro por CUIL, exactamente como Consolidado.
        out["_cuil_key_v276"] = out["cuil"].astype(str).map(_clave_cuil)
        out = out.drop_duplicates(subset=["_cuil_key_v276"], keep="first").copy()
        out["_orden_nombre_v276"] = out["nombre_completo"].fillna("").astype(str).str.casefold()
        out = out.sort_values(["_orden_nombre_v276", "_cuil_key_v276"], kind="stable")
        out = out.drop(columns=["_orden_nombre_v276", "_cuil_key_v276"], errors="ignore").reset_index(drop=True)

    consolidado_n = int(len(cuiles_unicos))
    selector_n = int(len(out))
    if selector_n != consolidado_n:
        diagnosticos.insert(
            0,
            f"Control interno: Consolidado institucional={consolidado_n} docentes únicos por CUIL, "
            f"selector={selector_n}. Esta diferencia no debería ocurrir y debe revisarse."
        )
    out.attrs["consolidado_docentes_unicos_v276"] = consolidado_n
    out.attrs["selector_docentes_unicos_v276"] = selector_n
    out.attrs["diagnostico_v276"] = diagnosticos
    return out


# --- entry l. 47695-47755
def _enriquecer_asignaciones_proyecto_origen_v277(df, periodo_id):
    """Completa nombre y departamento/s reales del docente en una asignación.

    La fila de investigación/extensión conserva ``departamento_asignacion`` como
    dato técnico: identifica qué departamento realizó la carga y sigue usándose
    para permisos, auditoría y borrado. Para la PRESENTACIÓN, en cambio, el docente
    debe verse como en el padrón institucional: nombre real y todos los departamentos
    donde tiene una designación docente activa en el período.

    Esto resuelve el caso de un docente de otro departamento cargado desde el
    departamento actual: no vuelve a mostrarse como CUIL ni como perteneciente al
    departamento que hizo la carga.
    """
    if df is None:
        return pd.DataFrame()
    out = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(df)
    if out.empty:
        return out

    if "departamento_origen_docente" not in out.columns:
        out["departamento_origen_docente"] = ""

    if not USE_POSTGRESQL or periodo_id is None:
        if "departamento_asignacion" in out.columns:
            vacio = out["departamento_origen_docente"].fillna("").astype(str).str.strip().eq("")
            out.loc[vacio, "departamento_origen_docente"] = out.loc[vacio, "departamento_asignacion"].fillna("").astype(str)
        return out

    try:
        padron = _docentes_asignables_proyectos_institucional_pg_v276(int(periodo_id))
    except Exception:
        padron = pd.DataFrame()

    if isinstance(padron, pd.DataFrame) and not padron.empty and "cuil" in padron.columns:
        mapa = {}
        for _, r in padron.iterrows():
            k = _clave_cuil(r.get("cuil"))
            if not k:
                continue
            mapa[k] = {
                "nombre": limpiar_texto_tabla(r.get("nombre_completo", "")),
                "departamentos": limpiar_texto_tabla(r.get("departamento_origen", "")),
                "tipo": limpiar_texto_tabla(r.get("tipo_docente", "")),
            }

        for idx, r in out.iterrows():
            k = _clave_cuil(r.get("cuil"))
            info = mapa.get(k, {})
            nombre = limpiar_texto_tabla(info.get("nombre", ""))
            deps = limpiar_texto_tabla(info.get("departamentos", ""))
            if nombre:
                out.at[idx, "docente"] = nombre
            if deps:
                out.at[idx, "departamento_origen_docente"] = deps
            if info.get("tipo"):
                out.at[idx, "tipo_docente_origen"] = info.get("tipo")

    if "departamento_asignacion" in out.columns:
        vacio = out["departamento_origen_docente"].fillna("").astype(str).str.strip().eq("")
        out.loc[vacio, "departamento_origen_docente"] = out.loc[vacio, "departamento_asignacion"].fillna("").astype(str)
    return out


# --- entry l. 47760
_get_investigacion_docente_pre_v277 = get_investigacion_docente


# --- entry l. 47761-47771
def get_investigacion_docente(cuil=None, periodo_id=None, incluir_bajas=False, todos_departamentos=False):
    df = _get_investigacion_docente_pre_v277(
        cuil=cuil, periodo_id=periodo_id, incluir_bajas=incluir_bajas,
        todos_departamentos=todos_departamentos,
    )
    if periodo_id is not None:
        try:
            return _enriquecer_asignaciones_proyecto_origen_v277(df, int(periodo_id))
        except Exception:
            pass
    return df


# --- entry l. 47773
_get_extension_docente_pre_v277 = get_extension_docente


# --- entry l. 47774-47784
def get_extension_docente(cuil=None, periodo_id=None, incluir_bajas=False, todos_departamentos=False):
    df = _get_extension_docente_pre_v277(
        cuil=cuil, periodo_id=periodo_id, incluir_bajas=incluir_bajas,
        todos_departamentos=todos_departamentos,
    )
    if periodo_id is not None:
        try:
            return _enriquecer_asignaciones_proyecto_origen_v277(df, int(periodo_id))
        except Exception:
            pass
    return df


# --- entry l. 49303
_invalidar_cache_rendimiento_pre_v219 = invalidar_cache_rendimiento_v191


# --- entry l. 49305-49312
def invalidar_cache_rendimiento_v191(motivo="actualización"):
    try:
        if bool(st.session_state.get("_carga_integral_masiva_v219", False)):
            st.session_state["_carga_integral_pendiente_invalidar_v219"] = True
            return
    except Exception:
        pass
    return _invalidar_cache_rendimiento_pre_v219(motivo)


# --- entry l. 50006-50074
def asegurar_esquema_documentos_respaldo_v249():
    if st.session_state.get("_esquema_documentos_respaldo_v249_ok"):
        return
    if USE_POSTGRESQL:
        inst = _pg_current_inst_id(); dep = _pg_current_dep_id()
        conn = _pg_raw_conn(); cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documentos_respaldo (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT NOT NULL,
                    tipo_documento TEXT NOT NULL,
                    categoria TEXT NOT NULL,
                    numero TEXT,
                    fecha DATE,
                    periodo_id BIGINT,
                    cuil TEXT,
                    docente_nombre TEXT,
                    proyecto_tipo TEXT,
                    proyecto_id BIGINT,
                    referencia_texto TEXT,
                    titulo TEXT,
                    detalle TEXT,
                    observaciones TEXT,
                    archivo_nombre TEXT NOT NULL,
                    archivo_mime TEXT DEFAULT 'application/pdf',
                    archivo_pdf BYTEA NOT NULL,
                    archivo_bytes BIGINT DEFAULT 0,
                    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usuario_carga TEXT
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_docresp_dep_fecha_v249 ON documentos_respaldo (institucion_id, departamento_id, fecha DESC, id DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_docresp_docente_v249 ON documentos_respaldo (institucion_id, departamento_id, cuil)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_docresp_proyecto_v249 ON documentos_respaldo (institucion_id, proyecto_tipo, proyecto_id)")
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        conn = get_conn(); c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS documentos_respaldo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_documento TEXT NOT NULL,
                categoria TEXT NOT NULL,
                numero TEXT,
                fecha TEXT,
                periodo_id INTEGER,
                cuil TEXT,
                docente_nombre TEXT,
                proyecto_tipo TEXT,
                proyecto_id INTEGER,
                referencia_texto TEXT,
                titulo TEXT,
                detalle TEXT,
                observaciones TEXT,
                archivo_nombre TEXT NOT NULL,
                archivo_mime TEXT DEFAULT 'application/pdf',
                archivo_pdf BLOB NOT NULL,
                archivo_bytes INTEGER DEFAULT 0,
                fecha_carga TEXT,
                usuario_carga TEXT
            )
        """)
        conn.commit(); conn.close()
    st.session_state["_esquema_documentos_respaldo_v249_ok"] = True


# --- entry l. 50077-50100
def asegurar_tipo_resolucion_documentos_v255():
    """Agrega de forma compatible el subtipo de resolución al repositorio existente."""
    if st.session_state.get("_esquema_tipo_resolucion_v255_ok"):
        return
    asegurar_esquema_documentos_respaldo_v249()
    if USE_POSTGRESQL:
        conn = _pg_raw_conn(); cur = conn.cursor()
        try:
            cur.execute("ALTER TABLE documentos_respaldo ADD COLUMN IF NOT EXISTS tipo_resolucion TEXT")
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        conn = get_conn(); c = conn.cursor()
        try:
            cols = [str(r[1]) for r in c.execute("PRAGMA table_info(documentos_respaldo)").fetchall()]
            if "tipo_resolucion" not in cols:
                c.execute("ALTER TABLE documentos_respaldo ADD COLUMN tipo_resolucion TEXT")
                conn.commit()
        finally:
            conn.close()
    st.session_state["_esquema_tipo_resolucion_v255_ok"] = True


# --- entry l. 50113-50213
def asegurar_esquema_dependencias_documentales_v262():
    """Catálogo institucional de organismos/áreas que emiten actos administrativos."""
    if st.session_state.get("_esquema_dependencias_documentales_v262_ok"):
        return
    asegurar_esquema_documentos_respaldo_v249()
    asegurar_tipo_resolucion_documentos_v255()

    if USE_POSTGRESQL:
        inst = _pg_current_inst_id()
        if inst is None:
            return
        conn = _pg_raw_conn(); cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dependencias_documentales (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    nombre TEXT NOT NULL,
                    estado TEXT DEFAULT 'Activa',
                    observaciones TEXT,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_dependencias_documentales_nombre_v262
                ON dependencias_documentales (institucion_id, LOWER(TRIM(nombre)))
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS ix_dependencias_documentales_estado_v262
                ON dependencias_documentales (institucion_id, estado, nombre)
            """)
            cur.execute("ALTER TABLE documentos_respaldo ADD COLUMN IF NOT EXISTS dependencia_id BIGINT")
            cur.execute("ALTER TABLE documentos_respaldo ADD COLUMN IF NOT EXISTS dependencia_nombre TEXT")

            # Valores que ya existían implícitamente en v255.
            for nombre in ["Rectorado", "Consejo Superior"]:
                cur.execute("""
                    INSERT INTO dependencias_documentales
                        (institucion_id, nombre, estado, observaciones, fecha_creacion, fecha_actualizacion)
                    SELECT %s, %s, 'Activa', '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    WHERE NOT EXISTS (
                        SELECT 1 FROM dependencias_documentales
                        WHERE institucion_id=%s AND LOWER(TRIM(nombre))=LOWER(TRIM(%s))
                    )
                """, [int(inst), nombre, int(inst), nombre])

            # Migra documentos viejos cuyo emisor puede inferirse sin ambigüedad.
            cur.execute("""
                UPDATE documentos_respaldo d
                SET dependencia_id = dep.id, dependencia_nombre = dep.nombre
                FROM dependencias_documentales dep
                WHERE d.institucion_id=%s
                  AND dep.institucion_id=d.institucion_id
                  AND COALESCE(d.dependencia_id,0)=0
                  AND (
                       (LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' AND LOWER(TRIM(dep.nombre))='rectorado')
                    OR (LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' AND LOWER(TRIM(dep.nombre))='consejo superior')
                  )
            """, [int(inst)])
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        try: inst = int(_institucion_id_operativa() or 1)
        except Exception: inst = 1
        conn = get_conn(); c = conn.cursor()
        try:
            c.execute("""
                CREATE TABLE IF NOT EXISTS dependencias_documentales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    institucion_id INTEGER NOT NULL,
                    nombre TEXT NOT NULL,
                    estado TEXT DEFAULT 'Activa',
                    observaciones TEXT,
                    fecha_creacion TEXT,
                    fecha_actualizacion TEXT
                )
            """)
            cols = [str(r[1]) for r in c.execute("PRAGMA table_info(documentos_respaldo)").fetchall()]
            if "dependencia_id" not in cols:
                c.execute("ALTER TABLE documentos_respaldo ADD COLUMN dependencia_id INTEGER")
            if "dependencia_nombre" not in cols:
                c.execute("ALTER TABLE documentos_respaldo ADD COLUMN dependencia_nombre TEXT")
            for nombre in ["Rectorado", "Consejo Superior"]:
                ex = c.execute("SELECT id FROM dependencias_documentales WHERE institucion_id=? AND LOWER(TRIM(nombre))=LOWER(TRIM(?)) LIMIT 1", (inst, nombre)).fetchone()
                if not ex:
                    ahora = datetime.now().isoformat(timespec="seconds")
                    c.execute("INSERT INTO dependencias_documentales (institucion_id,nombre,estado,observaciones,fecha_creacion,fecha_actualizacion) VALUES (?,?,?,?,?,?)", (inst,nombre,"Activa","",ahora,ahora))
            deps = c.execute("SELECT id,nombre FROM dependencias_documentales WHERE institucion_id=?", (inst,)).fetchall()
            mapa = {str(n or "").strip().casefold(): int(i) for i,n in deps}
            if "rectorado" in mapa:
                c.execute("UPDATE documentos_respaldo SET dependencia_id=?, dependencia_nombre='Rectorado' WHERE COALESCE(dependencia_id,0)=0 AND LOWER(TRIM(COALESCE(tipo_resolucion,'')))='rectoral'", (mapa["rectorado"],))
            if "consejo superior" in mapa:
                c.execute("UPDATE documentos_respaldo SET dependencia_id=?, dependencia_nombre='Consejo Superior' WHERE COALESCE(dependencia_id,0)=0 AND LOWER(TRIM(COALESCE(tipo_resolucion,'')))='consejo superior'", (mapa["consejo superior"],))
            conn.commit()
        finally:
            conn.close()
    st.session_state["_esquema_dependencias_documentales_v262_ok"] = True


# --- entry l. 50636-50711
def asegurar_esquema_documentos_respaldo_docentes_v251():
    """Relación uno-a-muchos entre un PDF respaldatorio y sus docentes."""
    asegurar_esquema_documentos_respaldo_v249()
    if st.session_state.get("_esquema_documentos_respaldo_docentes_v263_ok"):
        return

    if USE_POSTGRESQL:
        inst = _pg_current_inst_id(); dep = _pg_current_dep_id()
        conn = _pg_raw_conn(); cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documentos_respaldo_docentes (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT NOT NULL,
                    documento_id BIGINT NOT NULL REFERENCES documentos_respaldo(id) ON DELETE CASCADE,
                    cuil TEXT NOT NULL,
                    docente_nombre TEXT,
                    fecha_vinculacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (institucion_id, departamento_id, documento_id, cuil)
                )
            """)
            cur.execute("ALTER TABLE documentos_respaldo_docentes ADD COLUMN IF NOT EXISTS tipo_movimiento TEXT")
            cur.execute("ALTER TABLE documentos_respaldo_docentes ADD COLUMN IF NOT EXISTS detalle_vinculo TEXT")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_docresp_docentes_documento_v251
                ON documentos_respaldo_docentes (institucion_id, departamento_id, documento_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_docresp_docentes_cuil_v251
                ON documentos_respaldo_docentes (institucion_id, departamento_id, cuil)
            """)
            # Migra automáticamente los documentos creados con v249, que admitían
            # un único docente guardado en la tabla principal.
            cur.execute("""
                INSERT INTO documentos_respaldo_docentes
                    (institucion_id, departamento_id, documento_id, cuil, docente_nombre)
                SELECT d.institucion_id, d.departamento_id, d.id, TRIM(d.cuil), COALESCE(d.docente_nombre,'')
                FROM documentos_respaldo d
                WHERE d.institucion_id=%s AND d.departamento_id=%s
                  AND TRIM(COALESCE(d.cuil,'')) <> ''
                ON CONFLICT (institucion_id, departamento_id, documento_id, cuil) DO NOTHING
            """, [int(inst), int(dep)])
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        conn = get_conn(); c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS documentos_respaldo_docentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                documento_id INTEGER NOT NULL,
                cuil TEXT NOT NULL,
                docente_nombre TEXT,
                fecha_vinculacion TEXT,
                UNIQUE (documento_id, cuil)
            )
        """)
        cols_docresp_v263 = [str(r[1]) for r in c.execute("PRAGMA table_info(documentos_respaldo_docentes)").fetchall()]
        if "tipo_movimiento" not in cols_docresp_v263:
            c.execute("ALTER TABLE documentos_respaldo_docentes ADD COLUMN tipo_movimiento TEXT")
        if "detalle_vinculo" not in cols_docresp_v263:
            c.execute("ALTER TABLE documentos_respaldo_docentes ADD COLUMN detalle_vinculo TEXT")
        c.execute("""
            INSERT OR IGNORE INTO documentos_respaldo_docentes
                (documento_id, cuil, docente_nombre, fecha_vinculacion)
            SELECT id, TRIM(cuil), COALESCE(docente_nombre,''), ?
            FROM documentos_respaldo
            WHERE TRIM(COALESCE(cuil,'')) <> ''
        """, (datetime.now().isoformat(timespec="seconds"),))
        conn.commit(); conn.close()

    st.session_state["_esquema_documentos_respaldo_docentes_v251_ok"] = True
    st.session_state["_esquema_documentos_respaldo_docentes_v263_ok"] = True


# --- entry l. 51297-51299
def _etiqueta_acto_v263(tipo_documento, numero, dependencia=""):
    from analisis.motor.ref.extracted_batch01.documentos import _etiqueta_acto_v263 as _b01_core__etiqueta_acto_v263
    return _b01_core__etiqueta_acto_v263(tipo_documento, numero, dependencia)


# --- entry l. 53026-53139
def _snapshot_listados_departamento_v240(inst_id, dep_id, dep_nombre):
    """Lee un departamento usando exactamente las funciones de sus pantallas.

    No cambia datos. Solo modifica temporalmente el departamento de contexto de
    esta sesión para que get_periodos/get_designaciones/get_plantel_periodo usen
    el mismo scoping PostgreSQL que tendrían al entrar manualmente al departamento.
    """
    _ausente = object()
    _dep_anterior = st.session_state.get("tenant_scope_departamento_id", _ausente)
    try:
        st.session_state["tenant_scope_departamento_id"] = int(dep_id)

        df_periodos = get_periodos()
        if df_periodos is None or df_periodos.empty:
            return {
                "resumen": {
                    "departamento_id": int(dep_id),
                    "departamento": str(dep_nombre or ""),
                    "periodo_actual": "Sin períodos",
                    "estado_periodo": "Sin períodos",
                    "docentes": 0,
                    "designaciones": 0,
                    "horas_designadas": 0.0,
                },
                "docentes": pd.DataFrame(),
                "designaciones": pd.DataFrame(),
            }

        # Replica exactamente el período que seleccionan por defecto las pantallas:
        # período abierto si existe; de lo contrario, el primero de get_periodos().
        p_abierto = get_periodo_abierto()
        if p_abierto:
            periodo_id = int(p_abierto["id"])
            periodo_nombre = str(p_abierto.get("nombre") or "")
            periodo_estado = str(p_abierto.get("estado") or "Abierto")
        else:
            p0 = df_periodos.iloc[0].to_dict()
            periodo_id = int(p0["id"])
            periodo_nombre = str(p0.get("nombre") or "")
            periodo_estado = str(p0.get("estado") or "")

        # 1) MISMA fuente de "Designaciones del período", pero el Consolidado
        # cuenta únicamente las que están ACTIVAS dentro del período tomado.
        # get_designaciones(periodo_id) ya acota al período/departamento; acá solo
        # se aplica el estado operativo explícito de la propia designación.
        # No se reinterpreta por fechas ni se altera el tipo de función: una
        # designación activa no docente también sigue siendo una designación activa.
        df_desig = get_designaciones(periodo_id)
        df_desig = df_desig.copy() if isinstance(df_desig, pd.DataFrame) else pd.DataFrame()
        if not df_desig.empty and "estado" in df_desig.columns:
            _estado_desig_v242 = (
                df_desig["estado"].fillna("").astype(str).str.strip().str.casefold()
            )
            df_desig_contadas = df_desig[_estado_desig_v242.eq("activa")].copy()
        else:
            # Si excepcionalmente falta la columna estado, no se inventa una
            # vigencia alternativa desde Consolidado.
            df_desig_contadas = df_desig.copy()

        # 2) MISMA fuente de "Docentes del período", pero contando únicamente
        # docentes que todavía tienen al menos una designación ACTIVA en ese
        # período/departamento. get_plantel_periodo() ya calcula ese dato en la
        # columna designaciones_activas, por lo que el Consolidado no reconstruye
        # la vigencia ni usa otra SQL paralela.
        df_plantel = get_plantel_periodo(periodo_id)
        df_plantel = df_plantel.copy() if isinstance(df_plantel, pd.DataFrame) else pd.DataFrame()
        if not df_plantel.empty:
            if "designaciones_activas" in df_plantel.columns:
                _activas_v241 = pd.to_numeric(
                    df_plantel["designaciones_activas"], errors="coerce"
                ).fillna(0)
                df_doc_contados = df_plantel[_activas_v241.gt(0)].copy()
            elif "estado_operativo_periodo" in df_plantel.columns:
                # Respaldo para bases/versiones antiguas donde todavía no exista
                # la columna numérica pero sí el estado calculado por Plantel.
                _estado_v241 = (
                    df_plantel["estado_operativo_periodo"]
                    .fillna("").astype(str).str.strip().str.casefold()
                )
                df_doc_contados = df_plantel[_estado_v241.eq("activo en el período".casefold())].copy()
            else:
                # No inventar una tercera lógica: si faltaran ambos campos, se
                # conserva el listado original en lugar de adivinar vigencias.
                df_doc_contados = df_plantel.copy()
        else:
            df_doc_contados = df_plantel.copy()

        horas = float(pd.to_numeric(
            df_desig_contadas.get("horas", pd.Series(dtype=float)), errors="coerce"
        ).fillna(0).sum()) if not df_desig_contadas.empty else 0.0

        for df_det in (df_doc_contados, df_desig_contadas):
            if isinstance(df_det, pd.DataFrame) and not df_det.empty:
                df_det.insert(0, "departamento_origen", str(dep_nombre or ""))
                df_det.insert(1, "periodo_consolidado", periodo_nombre)

        return {
            "resumen": {
                "departamento_id": int(dep_id),
                "departamento": str(dep_nombre or ""),
                "periodo_actual": periodo_nombre,
                "estado_periodo": periodo_estado,
                "docentes": int(len(df_doc_contados)),
                "designaciones": int(len(df_desig_contadas)),
                "horas_designadas": round(horas, 2),
            },
            "docentes": df_doc_contados.reset_index(drop=True),
            "designaciones": df_desig_contadas.reset_index(drop=True),
        }
    finally:
        if _dep_anterior is _ausente:
            st.session_state.pop("tenant_scope_departamento_id", None)
        else:
            st.session_state["tenant_scope_departamento_id"] = _dep_anterior


# --- entry l. 53142-53181
def _consolidado_desde_listados_reales_v240(inst_id):
    """Construye el consolidado sumando literalmente los listados departamentales."""
    departamentos = _pg_read_dataframe("""
        SELECT id, nombre
        FROM departamentos
        WHERE institucion_id=%s
          AND COALESCE(estado,'Activo')='Activo'
        ORDER BY nombre
    """, [int(inst_id)])

    if departamentos is None or departamentos.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), set()

    resumenes = []
    docentes_partes = []
    designaciones_partes = []
    cuiles_unicos = set()

    for _, dep in departamentos.iterrows():
        snap = _snapshot_listados_departamento_v240(
            int(inst_id), int(dep["id"]), str(dep.get("nombre") or "")
        )
        resumenes.append(snap["resumen"])

        dfd = snap.get("docentes", pd.DataFrame())
        if isinstance(dfd, pd.DataFrame) and not dfd.empty:
            docentes_partes.append(dfd)
            for cuil in dfd.get("cuil", pd.Series(dtype=str)).tolist():
                clave = _clave_cuil(cuil)
                if clave:
                    cuiles_unicos.add(clave)

        dfg = snap.get("designaciones", pd.DataFrame())
        if isinstance(dfg, pd.DataFrame) and not dfg.empty:
            designaciones_partes.append(dfg)

    df_resumen = pd.DataFrame(resumenes)
    df_docentes = pd.concat(docentes_partes, ignore_index=True, sort=False) if docentes_partes else pd.DataFrame()
    df_designaciones = pd.concat(designaciones_partes, ignore_index=True, sort=False) if designaciones_partes else pd.DataFrame()
    return df_resumen, df_docentes, df_designaciones, cuiles_unicos


# --- entry l. 53300-53373
def asegurar_esquema_inscriptos_asignatura_periodo_v248():
    """Crea la nueva fuente de inscriptos: una fila por asignatura/código y período.

    La comisión deja de ser parte de la identidad del dato. ``materia_id`` conserva
    la identidad conceptual existente y ``opcion_curricular_id`` distingue una
    Optativa/Electiva concreta cuando corresponde. Las tablas v123 se mantienen
    únicamente como legado para no perder información histórica.
    """
    if st.session_state.get("_esquema_inscriptos_asignatura_periodo_v248_ok"):
        return
    if USE_POSTGRESQL:
        conn = _pg_raw_conn(); cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS inscriptos_asignatura_periodo (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT,
                    periodo_id BIGINT NOT NULL,
                    materia_id BIGINT NOT NULL,
                    opcion_curricular_id BIGINT NOT NULL DEFAULT 0,
                    cantidad INTEGER DEFAULT 0,
                    cantidad_final INTEGER,
                    fecha_actualizacion TEXT,
                    fecha_actualizacion_final TEXT,
                    observaciones TEXT
                )
            """)
            for nombre, tipo in [
                ("institucion_id", "BIGINT"), ("departamento_id", "BIGINT"),
                ("periodo_id", "BIGINT"), ("materia_id", "BIGINT"),
                ("opcion_curricular_id", "BIGINT NOT NULL DEFAULT 0"),
                ("cantidad", "INTEGER DEFAULT 0"), ("cantidad_final", "INTEGER"),
                ("fecha_actualizacion", "TEXT"), ("fecha_actualizacion_final", "TEXT"),
                ("observaciones", "TEXT"),
            ]:
                cur.execute(f"ALTER TABLE inscriptos_asignatura_periodo ADD COLUMN IF NOT EXISTS {nombre} {tipo}")
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_deptit_inscriptos_asignatura_periodo_v248
                ON inscriptos_asignatura_periodo
                (institucion_id, departamento_id, periodo_id, materia_id, opcion_curricular_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_deptit_inscriptos_asignatura_periodo_periodo_v248
                ON inscriptos_asignatura_periodo (institucion_id, departamento_id, periodo_id)
            """)
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        conn = get_conn(); c = conn.cursor()
        try:
            c.execute("""
                CREATE TABLE IF NOT EXISTS inscriptos_asignatura_periodo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    periodo_id INTEGER NOT NULL,
                    materia_id INTEGER NOT NULL,
                    opcion_curricular_id INTEGER NOT NULL DEFAULT 0,
                    cantidad INTEGER DEFAULT 0,
                    cantidad_final INTEGER,
                    fecha_actualizacion TEXT,
                    fecha_actualizacion_final TEXT,
                    observaciones TEXT,
                    UNIQUE(periodo_id, materia_id, opcion_curricular_id)
                )
            """)
            conn.commit()
        finally:
            conn.close()
    st.session_state["_esquema_inscriptos_asignatura_periodo_v248_ok"] = True


# --- entry l. 53376-53378
def _opcion_id_inscriptos_v248(valor):
    from analisis.motor.ref.extracted_batch04.numeros import _opcion_id_inscriptos_v248 as _b04_core__opcion_id_inscriptos_v248
    return _b04_core__opcion_id_inscriptos_v248(valor)


# --- entry l. 53381-53383
def _entero_no_negativo_v248(valor, default=0):
    from analisis.motor.ref.extracted_batch04.numeros import _entero_no_negativo_v248 as _b04_core__entero_no_negativo_v248
    return _b04_core__entero_no_negativo_v248(valor, default)


# --- entry l. 53386-53400
def _fila_comision_v248(comision_id, periodo_id=None):
    try:
        cid = int(comision_id)
    except Exception:
        return {}
    try:
        df = get_comisiones(periodo_id=periodo_id, solo_activas=False)
    except Exception:
        df = pd.DataFrame()
    if isinstance(df, pd.DataFrame) and not df.empty and "id" in df.columns:
        ids = pd.to_numeric(df["id"], errors="coerce")
        sub = df[ids.eq(cid)]
        if not sub.empty:
            return sub.iloc[0].to_dict()
    return {}


# --- entry l. 53403-53469
def _items_asignaturas_comision_v248(comision_id, fila_comision=None):
    """Asignaturas/códigos exactos que integran una comisión ya cargada.

    No crea agrupaciones paralelas: parte de get_materias_conceptuales_comision_v122.
    Una opción curricular concreta se distingue cuando la comisión corresponde a
    un único espacio Optativa/Electiva.
    """
    try:
        cid = int(comision_id)
    except Exception:
        return []
    fila = dict(fila_comision or _fila_comision_v248(cid) or {})
    try:
        reps = [int(x) for x in (get_materias_conceptuales_comision_v122(cid) or [])]
    except Exception:
        reps = []
    if not reps:
        try:
            mid0 = int(fila.get("materia_id"))
            reps = [mid0]
        except Exception:
            reps = []
    # v122 impide mezclar Optativa/Electiva con otros códigos. Por eso una opción
    # concreta solo forma parte de la identidad cuando la comisión tiene un único
    # representante conceptual.
    opcion_id = _opcion_id_inscriptos_v248(fila.get("opcion_curricular_id")) if len(reps) == 1 else 0
    opcion = {}
    if opcion_id:
        try:
            opcion = dict(get_opcion_curricular_v120(opcion_id) or {})
        except Exception:
            opcion = {}

    items, vistos = [], set()
    for mid_raw in reps:
        mid = _materia_representante_inscriptos_v123(mid_raw)
        if mid is None:
            continue
        oid = opcion_id if len(reps) == 1 else 0
        clave = (int(mid), int(oid))
        if clave in vistos:
            continue
        vistos.add(clave)
        try:
            info = dict(get_materia_comision(int(mid)) or {})
        except Exception:
            info = {}
        base_asig = limpiar_texto_tabla(info.get("asignatura", ""))
        materia_especifica = limpiar_texto_tabla(
            (opcion or {}).get("nombre", "")
            or fila.get("materia_especifica", "")
        )
        codigo = limpiar_texto_tabla((opcion or {}).get("codigo", "")) or limpiar_texto_tabla(info.get("codigo", ""))
        asignatura = materia_especifica or base_asig
        items.append({
            "materia_id_inscriptos": int(mid),
            "opcion_curricular_id_inscriptos": int(oid),
            "clave_asignatura_v248": f"{int(mid)}:{int(oid)}",
            "codigo_materia": codigo,
            "asignatura": asignatura,
            "asignatura_base": base_asig,
            "materia_especifica": materia_especifica,
            "carrera": limpiar_texto_tabla(info.get("carrera", "")),
            "escuela": limpiar_texto_tabla(info.get("escuela", "")),
            "plan_version": limpiar_texto_tabla(info.get("plan_version", "")),
        })
    return items


# --- entry l. 53472-53474
def _etiqueta_comision_derivada_v248(fila):
    from analisis.motor.ref.domain.comisiones import _etiqueta_comision_derivada_v248 as _b05_core__etiqueta_comision_derivada_v248
    return _b05_core__etiqueta_comision_derivada_v248(fila)


# --- entry l. 53477-53479
def _etiqueta_item_v248(item):
    from analisis.motor.ref.domain.comisiones import _etiqueta_item_v248 as _b05_core__etiqueta_item_v248
    return _b05_core__etiqueta_item_v248(item)


# --- entry l. 53482-53577
def migrar_inscriptos_a_asignatura_periodo_v248():
    """Migra una sola vez los datos v123 sumando las comisiones por asignatura.

    La suma es la conversión semántica correcta: antes cada comisión guardaba su
    porción de alumnos; ahora el período guarda una única cantidad total por código.
    Nunca sobreescribe una fila v248 que ya haya sido cargada/corregida.
    """
    asegurar_esquema_inscriptos_asignatura_periodo_v248()
    if st.session_state.get("_migracion_inscriptos_asignatura_periodo_v248_ok"):
        return {"migrados": 0}
    try:
        migrar_inscriptos_legacy_por_materia_v123()
    except Exception:
        pass
    conn = get_conn()
    try:
        viejo = pd.read_sql("""
            SELECT co.periodo_id, icm.comision_id, icm.materia_id,
                   COALESCE(co.opcion_curricular_id,0) AS opcion_curricular_id,
                   COALESCE(icm.cantidad,0) AS cantidad, icm.cantidad_final,
                   COALESCE(icm.fecha_actualizacion,'') AS fecha_actualizacion,
                   COALESCE(icm.fecha_actualizacion_final,'') AS fecha_actualizacion_final,
                   COALESCE(icm.observaciones,'') AS observaciones
            FROM inscriptos_comision_materia icm
            JOIN comisiones co ON co.id=icm.comision_id
            WHERE co.periodo_id IS NOT NULL
        """, conn)
        existentes = pd.read_sql("""
            SELECT periodo_id, materia_id, COALESCE(opcion_curricular_id,0) AS opcion_curricular_id
            FROM inscriptos_asignatura_periodo
        """, conn)
        claves_existentes = set()
        if not existentes.empty:
            for _, r in existentes.iterrows():
                try:
                    claves_existentes.add((int(r.get("periodo_id")), int(r.get("materia_id")), _opcion_id_inscriptos_v248(r.get("opcion_curricular_id"))))
                except Exception:
                    pass
        if viejo.empty:
            st.session_state["_migracion_inscriptos_asignatura_periodo_v248_ok"] = True
            return {"migrados": 0}

        registros = []
        for _, r in viejo.iterrows():
            try:
                pid = int(r.get("periodo_id")); mid = _materia_representante_inscriptos_v123(r.get("materia_id"))
                if mid is None:
                    continue
                oid = _opcion_id_inscriptos_v248(r.get("opcion_curricular_id"))
                registros.append({**r.to_dict(), "periodo_id": pid, "materia_id": int(mid), "opcion_curricular_id": oid})
            except Exception:
                continue
        if not registros:
            st.session_state["_migracion_inscriptos_asignatura_periodo_v248_ok"] = True
            return {"migrados": 0}
        df = pd.DataFrame(registros)
        cur = conn.cursor(); migrados = 0
        for (pid, mid, oid), g in df.groupby(["periodo_id", "materia_id", "opcion_curricular_id"], dropna=False):
            clave = (int(pid), int(mid), int(oid))
            if clave in claves_existentes:
                continue
            cantidades = pd.to_numeric(g.get("cantidad"), errors="coerce").fillna(0)
            finales = pd.to_numeric(g.get("cantidad_final"), errors="coerce")
            cantidad = int(cantidades.sum())
            cantidad_final = int(finales.sum()) if len(finales) > 0 and finales.notna().all() else None
            fechas_i = [limpiar_texto_tabla(x) for x in g.get("fecha_actualizacion", pd.Series(dtype=str)).tolist() if limpiar_texto_tabla(x)]
            fechas_f = [limpiar_texto_tabla(x) for x in g.get("fecha_actualizacion_final", pd.Series(dtype=str)).tolist() if limpiar_texto_tabla(x)]
            obs = []
            for x in g.get("observaciones", pd.Series(dtype=str)).tolist():
                t = limpiar_texto_tabla(x)
                if t and t not in obs:
                    obs.append(t)
            cur.execute("""
                INSERT INTO inscriptos_asignatura_periodo
                (periodo_id, materia_id, opcion_curricular_id, cantidad, cantidad_final,
                 fecha_actualizacion, fecha_actualizacion_final, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(pid), int(mid), int(oid), cantidad, cantidad_final,
                max(fechas_i) if fechas_i else "",
                max(fechas_f) if fechas_f else "",
                " | ".join(obs),
            ))
            claves_existentes.add(clave); migrados += 1
        conn.commit()
        st.session_state["_migracion_inscriptos_asignatura_periodo_v248_ok"] = True
        if migrados:
            try: invalidar_cache_rendimiento_v191("migración inscriptos por asignatura v248")
            except Exception: pass
        return {"migrados": int(migrados)}
    except Exception:
        try: conn.rollback()
        except Exception: pass
        raise
    finally:
        conn.close()


# --- entry l. 53580-53595
def _inscriptos_guardados_periodo_v248(periodo_id):
    asegurar_esquema_inscriptos_asignatura_periodo_v248()
    conn = get_conn()
    try:
        return pd.read_sql("""
            SELECT id, periodo_id, materia_id, COALESCE(opcion_curricular_id,0) AS opcion_curricular_id,
                   COALESCE(cantidad,0) AS cantidad, cantidad_final,
                   COALESCE(fecha_actualizacion,'') AS fecha_actualizacion,
                   COALESCE(fecha_actualizacion_final,'') AS fecha_actualizacion_final,
                   COALESCE(observaciones,'') AS observaciones_inscriptos
            FROM inscriptos_asignatura_periodo
            WHERE periodo_id=?
            ORDER BY materia_id, opcion_curricular_id
        """, conn, params=[int(periodo_id)])
    finally:
        conn.close()


# --- entry l. 53660-53732
def _inscriptos_asignaturas_periodo_raw_v248(periodo_id):
    pid = int(periodo_id)
    try:
        df_integrado = get_comisiones_integradas_periodo(pid)
    except Exception:
        df_integrado = pd.DataFrame()
    if df_integrado is None or df_integrado.empty:
        return pd.DataFrame(columns=[
            "materia_id_inscriptos", "opcion_curricular_id_inscriptos", "codigo_materia", "asignatura",
            "cantidad", "cantidad_final", "cantidad_comisiones", "comisiones_relacionadas", "combinaciones_relacionadas"
        ])

    # Mismo criterio temporal que usa el indicador: activas hoy; todas en foto histórica.
    try:
        df_ctx = _comisiones_contexto_alumnos_v188(pid)
        ids_ctx = set(pd.to_numeric(df_ctx.get("id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist()) if isinstance(df_ctx, pd.DataFrame) else set()
    except Exception:
        ids_ctx = set()
    if ids_ctx and "id" in df_integrado.columns:
        df_integrado = df_integrado[pd.to_numeric(df_integrado["id"], errors="coerce").isin(ids_ctx)].copy()
    if df_integrado.empty:
        return pd.DataFrame()

    datos = {}
    combos_por_item = {}
    for _, co in df_integrado.iterrows():
        try: cid = int(co.get("id"))
        except Exception: continue
        items = _items_asignaturas_comision_v248(cid, co.to_dict())
        if not items:
            continue
        claves_combo = tuple(sorted((int(x["materia_id_inscriptos"]), int(x["opcion_curricular_id_inscriptos"])) for x in items))
        etiqueta_combo = " + ".join(_etiqueta_item_v248(x) for x in sorted(items, key=lambda z: (str(z.get("codigo_materia","")), str(z.get("asignatura","")))))
        etiqueta_com = _etiqueta_comision_derivada_v248(co.to_dict())
        for item in items:
            k = (int(item["materia_id_inscriptos"]), int(item["opcion_curricular_id_inscriptos"]))
            rec = datos.setdefault(k, {**item, "comisiones": [], "comision_ids": set()})
            if etiqueta_com and etiqueta_com not in rec["comisiones"]:
                rec["comisiones"].append(etiqueta_com)
            rec["comision_ids"].add(cid)
            combos_por_item.setdefault(k, {})[claves_combo] = etiqueta_combo

    guardados = _inscriptos_guardados_periodo_v248(pid)
    mapa = {}
    if isinstance(guardados, pd.DataFrame) and not guardados.empty:
        for _, r in guardados.iterrows():
            try:
                mapa[(int(r.get("materia_id")), _opcion_id_inscriptos_v248(r.get("opcion_curricular_id")))] = r.to_dict()
            except Exception:
                pass

    filas = []
    for k, rec in datos.items():
        g = mapa.get(k, {})
        fila = {kk: vv for kk, vv in rec.items() if kk not in {"comisiones", "comision_ids"}}
        fila.update({
            "periodo_id": pid,
            "cantidad": _entero_no_negativo_v248(g.get("cantidad", 0)),
            "cantidad_final": g.get("cantidad_final", pd.NA),
            "fecha_actualizacion": limpiar_texto_tabla(g.get("fecha_actualizacion", "")),
            "fecha_actualizacion_final": limpiar_texto_tabla(g.get("fecha_actualizacion_final", "")),
            "observaciones_inscriptos": limpiar_texto_tabla(g.get("observaciones_inscriptos", "")),
            "cantidad_comisiones": int(len(rec["comision_ids"])),
            "comisiones_relacionadas": " | ".join(rec["comisiones"]),
            "combinaciones_relacionadas": " | ".join(sorted(set(combos_por_item.get(k, {}).values()))),
        })
        filas.append(fila)
    out = pd.DataFrame(filas)
    if out.empty:
        return out
    out["cantidad"] = pd.to_numeric(out["cantidad"], errors="coerce").fillna(0).astype(int)
    out["cantidad_final"] = pd.to_numeric(out["cantidad_final"], errors="coerce")
    return out.sort_values([c for c in ["codigo_materia", "asignatura"] if c in out.columns], kind="stable").reset_index(drop=True)


# --- entry l. 53736-53737
def _inscriptos_asignaturas_periodo_cache_v248(periodo_id, db_url, inst, dep, version):
    return _inscriptos_asignaturas_periodo_raw_v248(int(periodo_id))


# --- entry l. 53740-53748
def get_inscriptos_asignaturas_periodo_v248(periodo_id):
    asegurar_esquema_inscriptos_asignatura_periodo_v248()
    try:
        migrar_inscriptos_a_asignatura_periodo_v248()
    except Exception as exc:
        st.session_state["_migracion_inscriptos_asignatura_periodo_v248_error"] = str(exc)
    db_url, inst, dep, version = _scope_rendimiento_v191()
    df = _inscriptos_asignaturas_periodo_cache_v248(int(periodo_id), db_url, inst, dep, version)
    return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()


# --- entry l. 53806-53832
def _docentes_comisiones_periodo_v248(periodo_id):
    pid = int(periodo_id)
    try:
        df_ctx = _comisiones_contexto_alumnos_v188(pid)
    except Exception:
        df_ctx = pd.DataFrame()
    ids = set(pd.to_numeric(df_ctx.get("id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist()) if isinstance(df_ctx, pd.DataFrame) and not df_ctx.empty else set()
    try:
        df = get_asignaciones_comisiones_periodo(pid)
    except Exception:
        df = pd.DataFrame()
    df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if df.empty or "comision_id" not in df.columns:
        return pd.DataFrame(columns=["comision_id", "cuil", "docente"])
    df["_cid_v248"] = pd.to_numeric(df["comision_id"], errors="coerce")
    if ids:
        df = df[df["_cid_v248"].isin(ids)].copy()
    try:
        historico = bool(es_periodo_historico_contexto_v182(pid))
    except Exception:
        historico = False
    if not historico and "estado" in df.columns:
        est = df["estado"].fillna("Activa").astype(str).str.strip().str.casefold()
        df = df[est.eq("activa")].copy()
    df["_cuil_v248"] = df.get("cuil", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).map(_clave_cuil)
    df = df[df["_cuil_v248"].ne("")].copy()
    return df


# --- entry l. 53835-53917
def get_analisis_alumnos_por_docente_grupos_v248(periodo_id):
    """Una fila por combinación exacta de asignaturas que surge de las comisiones."""
    pid = int(periodo_id)
    try:
        df_ctx = _comisiones_contexto_alumnos_v188(pid)
        ids_ctx = set(pd.to_numeric(df_ctx.get("id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist()) if isinstance(df_ctx, pd.DataFrame) else set()
    except Exception:
        ids_ctx = set()
    try:
        df_com = get_comisiones_integradas_periodo(pid)
    except Exception:
        df_com = pd.DataFrame()
    if df_com is None or df_com.empty:
        return pd.DataFrame()
    if ids_ctx and "id" in df_com.columns:
        df_com = df_com[pd.to_numeric(df_com["id"], errors="coerce").isin(ids_ctx)].copy()
    if df_com.empty:
        return pd.DataFrame()

    df_ins = get_inscriptos_asignaturas_periodo_v248(pid)
    mapa_ins = {}
    if isinstance(df_ins, pd.DataFrame) and not df_ins.empty:
        for _, r in df_ins.iterrows():
            try:
                mapa_ins[(int(r.get("materia_id_inscriptos")), _opcion_id_inscriptos_v248(r.get("opcion_curricular_id_inscriptos")))] = r.to_dict()
            except Exception:
                pass
    df_doc = _docentes_comisiones_periodo_v248(pid)
    docs_por_com = {}
    nombres_doc = {}
    if isinstance(df_doc, pd.DataFrame) and not df_doc.empty:
        for _, r in df_doc.iterrows():
            try: cid = int(r.get("comision_id"))
            except Exception: continue
            ck = _clave_cuil(r.get("cuil"))
            if not ck: continue
            docs_por_com.setdefault(cid, set()).add(ck)
            nom = limpiar_texto_tabla(r.get("docente", "")) or limpiar_texto_tabla(r.get("cuil", ""))
            if nom: nombres_doc[ck] = nom

    grupos = {}
    for _, co in df_com.iterrows():
        try: cid = int(co.get("id"))
        except Exception: continue
        items = _items_asignaturas_comision_v248(cid, co.to_dict())
        if not items: continue
        key = tuple(sorted((int(x["materia_id_inscriptos"]), int(x["opcion_curricular_id_inscriptos"])) for x in items))
        g = grupos.setdefault(key, {"items": items, "comision_ids": set(), "comisiones": []})
        g["comision_ids"].add(cid)
        et = _etiqueta_comision_derivada_v248(co.to_dict())
        if et and et not in g["comisiones"]: g["comisiones"].append(et)

    filas = []
    for key, g in grupos.items():
        items = g["items"]
        cantidades = []
        finales = []
        for k in key:
            r = mapa_ins.get(k, {})
            cantidades.append(_entero_no_negativo_v248(r.get("cantidad", 0)))
            finales.append(pd.to_numeric(r.get("cantidad_final", pd.NA), errors="coerce"))
        total = int(sum(cantidades))
        final_total = int(sum(int(v) for v in finales if not pd.isna(v))) if finales and all(not pd.isna(v) for v in finales) else pd.NA
        docs = set()
        for cid in g["comision_ids"]:
            docs.update(docs_por_com.get(cid, set()))
        ratio = round(float(total) / float(len(docs)), 2) if docs else 0.0
        items_ord = sorted(items, key=lambda x: (str(x.get("codigo_materia", "")), str(x.get("asignatura", ""))))
        filas.append({
            "codigos": " + ".join([limpiar_texto_tabla(x.get("codigo_materia", "")) for x in items_ord if limpiar_texto_tabla(x.get("codigo_materia", ""))]),
            "asignaturas": " + ".join([limpiar_texto_tabla(x.get("asignatura", "")) for x in items_ord if limpiar_texto_tabla(x.get("asignatura", ""))]),
            "inscriptos_totales": total,
            "regulares_finales": final_total,
            "cantidad_comisiones": int(len(g["comision_ids"])),
            "comisiones": " | ".join(g["comisiones"]),
            "docentes_unicos": int(len(docs)),
            "docentes": " | ".join(sorted([nombres_doc.get(c, c) for c in docs])),
            "alumnos_por_docente": float(ratio),
            "clave_combinacion": "+".join(f"{a}:{b}" for a,b in key),
        })
    out = pd.DataFrame(filas)
    if out.empty: return out
    return out.sort_values([c for c in ["codigos", "asignaturas"] if c in out.columns], kind="stable").reset_index(drop=True)


# --- entry l. 53920-53924
def _total_inscriptos_asignaturas_periodo_v248(periodo_id):
    df = get_inscriptos_asignaturas_periodo_v248(int(periodo_id))
    if df is None or df.empty:
        return 0
    return int(pd.to_numeric(df.get("cantidad", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())


# --- entry l. 53929-53963
def get_inscriptos_comision(comision_id, materia_id=None):
    try: cid = int(comision_id)
    except Exception: return {"cantidad": 0, "cantidad_final": None}
    co = _fila_comision_v248(cid)
    if not co:
        return {"comision_id": cid, "cantidad": 0, "cantidad_final": None}
    try: pid = int(co.get("periodo_id"))
    except Exception: return {"comision_id": cid, "cantidad": 0, "cantidad_final": None}
    items = _items_asignaturas_comision_v248(cid, co)
    df = get_inscriptos_asignaturas_periodo_v248(pid)
    mapa = {}
    if isinstance(df, pd.DataFrame) and not df.empty:
        for _, r in df.iterrows():
            try: mapa[(int(r.get("materia_id_inscriptos")), _opcion_id_inscriptos_v248(r.get("opcion_curricular_id_inscriptos")))] = r.to_dict()
            except Exception: pass
    if materia_id is not None:
        mid = _materia_representante_inscriptos_v123(materia_id)
        candidatos = [x for x in items if int(x.get("materia_id_inscriptos", -1)) == int(mid or -1)]
        item = candidatos[0] if candidatos else None
        if not item:
            return {"comision_id": cid, "materia_id": int(mid or 0), "cantidad": 0, "cantidad_final": None}
        r = dict(mapa.get((int(item["materia_id_inscriptos"]), int(item["opcion_curricular_id_inscriptos"])), {}))
        r.update({"comision_id": cid, "materia_id": int(item["materia_id_inscriptos"])})
        return r
    rows = [mapa.get((int(x["materia_id_inscriptos"]), int(x["opcion_curricular_id_inscriptos"])), {}) for x in items]
    cantidades = [_entero_no_negativo_v248(r.get("cantidad",0)) for r in rows]
    finales = [pd.to_numeric(r.get("cantidad_final", pd.NA), errors="coerce") for r in rows]
    return {
        "comision_id": cid,
        "cantidad": int(sum(cantidades)),
        "cantidad_final": int(sum(int(v) for v in finales)) if finales and all(not pd.isna(v) for v in finales) else None,
        "fecha_actualizacion": max([limpiar_texto_tabla(r.get("fecha_actualizacion", "")) for r in rows] + [""]),
        "fecha_actualizacion_final": max([limpiar_texto_tabla(r.get("fecha_actualizacion_final", "")) for r in rows] + [""]),
        "observaciones": "",
    }


# --- entry l. 53966-54024
def get_inscriptos_comisiones_periodo(periodo_id):
    """Vista derivada por comisión; el dato fuente sigue existiendo una sola vez por asignatura."""
    pid = int(periodo_id)
    df_asig = get_inscriptos_asignaturas_periodo_v248(pid)
    try: df_com = get_comisiones_integradas_periodo(pid)
    except Exception: df_com = pd.DataFrame()
    if df_com is None or df_com.empty:
        return pd.DataFrame()
    try:
        df_ctx = _comisiones_contexto_alumnos_v188(pid)
        ids_ctx = set(pd.to_numeric(df_ctx.get("id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist()) if isinstance(df_ctx,pd.DataFrame) else set()
    except Exception: ids_ctx=set()
    if ids_ctx:
        df_com = df_com[pd.to_numeric(df_com.get("id"), errors="coerce").isin(ids_ctx)].copy()
    mapa = {}
    if isinstance(df_asig, pd.DataFrame) and not df_asig.empty:
        for _, r in df_asig.iterrows():
            try: mapa[(int(r.get("materia_id_inscriptos")), _opcion_id_inscriptos_v248(r.get("opcion_curricular_id_inscriptos")))] = r.to_dict()
            except Exception: pass
    grupos = get_analisis_alumnos_por_docente_grupos_v248(pid)
    grupo_por_clave = {str(r.get("clave_combinacion")): r.to_dict() for _,r in grupos.iterrows()} if isinstance(grupos,pd.DataFrame) and not grupos.empty else {}
    filas=[]
    for _,co in df_com.iterrows():
        try: cid=int(co.get("id"))
        except Exception: continue
        items=_items_asignaturas_comision_v248(cid, co.to_dict())
        if not items: continue
        key_tuple=tuple(sorted((int(x["materia_id_inscriptos"]),int(x["opcion_curricular_id_inscriptos"])) for x in items))
        key_str="+".join(f"{a}:{b}" for a,b in key_tuple)
        g=grupo_por_clave.get(key_str,{})
        total=int(g.get("inscriptos_totales",0) or 0)
        total_final=g.get("regulares_finales",pd.NA)
        for item in items:
            k=(int(item["materia_id_inscriptos"]),int(item["opcion_curricular_id_inscriptos"]))
            ins=mapa.get(k,{})
            filas.append({
                "comision_id":cid,
                "materia_id_inscriptos":k[0],
                "opcion_curricular_id_inscriptos":k[1],
                "periodo":co.get("periodo",""),
                "codigo_materia":item.get("codigo_materia",""),
                "asignatura":item.get("asignatura",""),
                "materia_especifica":item.get("materia_especifica",""),
                "carrera":item.get("carrera",""), "escuela":item.get("escuela",""), "plan_version":item.get("plan_version",""),
                "nombre_comision":co.get("nombre_comision",""), "turno":co.get("turno",""), "sede":co.get("sede",""), "modalidad":co.get("modalidad",""), "horarios":co.get("horarios",""),
                "cantidad":_entero_no_negativo_v248(ins.get("cantidad",0)),
                "cantidad_final":ins.get("cantidad_final",pd.NA),
                "total_comision":total,
                "total_final_comision":total_final,
                "fecha_actualizacion":ins.get("fecha_actualizacion","") or "",
                "fecha_actualizacion_final":ins.get("fecha_actualizacion_final","") or "",
                "observaciones_inscriptos":ins.get("observaciones_inscriptos","") or "",
                "cantidad_comisiones_conjunto":int(g.get("cantidad_comisiones",1) or 1),
                "comisiones_conjunto":g.get("comisiones",_etiqueta_comision_derivada_v248(co.to_dict())),
                "docentes_unicos_conjunto":int(g.get("docentes_unicos",0) or 0),
                "alumnos_por_docente_conjunto":float(g.get("alumnos_por_docente",0) or 0),
                "legacy_total_sin_discriminar":0,
            })
    return pd.DataFrame(filas)


# --- entry l. 54078-54083
def _total_inscriptos_comisiones_periodo_v188(periodo_id):
    """v248: suma cada asignatura una sola vez; las comisiones no multiplican alumnos."""
    total=_total_inscriptos_asignaturas_periodo_v248(int(periodo_id))
    try: grupos=get_analisis_alumnos_por_docente_grupos_v248(int(periodo_id)); n=int(len(grupos))
    except Exception: n=0
    return int(total), int(n)


# --- entry l. 54086-54100
def _alumnos_por_docente_periodo_v188(periodo_id, metricas=None):
    """v248: alumnos únicos por código / docentes únicos que efectivamente integran comisiones."""
    total_alumnos=_total_inscriptos_asignaturas_periodo_v248(int(periodo_id))
    df_doc=_docentes_comisiones_periodo_v248(int(periodo_id))
    docentes=int(df_doc.get("_cuil_v248",pd.Series(dtype=str)).nunique()) if isinstance(df_doc,pd.DataFrame) and not df_doc.empty else 0
    ratio=round(float(total_alumnos)/float(docentes),2) if docentes>0 else 0.0
    return {
        "alumnos_inscriptos":int(total_alumnos),
        # Se conserva la clave histórica para no romper consumidores, pero desde
        # v248 significa docentes únicos efectivamente asignados a comisiones.
        "docentes_activos_calculo":int(docentes),
        "docentes_en_comisiones_calculo":int(docentes),
        "comisiones_consideradas":int(len(set(pd.to_numeric(df_doc.get("comision_id",pd.Series(dtype=float)),errors="coerce").dropna().astype(int).tolist()))) if isinstance(df_doc,pd.DataFrame) and not df_doc.empty else 0,
        "alumnos_por_docente":float(ratio),
    }


# --- entry l. 54116-54297
def asegurar_esquema_actos_administrativos_v266():
    """Crea vínculos documento↔designación y documento↔movimiento y migra lo inequívoco."""
    # La migración de datos es departamental. No alcanza con recordar que las tablas
    # ya existen: si el usuario cambia de departamento en la misma sesión también
    # hay que migrar las referencias manuales de ese nuevo ámbito.
    if USE_POSTGRESQL:
        _inst_scope_v266 = _pg_current_inst_id(); _dep_scope_v266 = _pg_current_dep_id()
        _scope_key_v266 = f"pg_{_inst_scope_v266}_{_dep_scope_v266}"
    else:
        _scope_key_v266 = "sqlite_" + hashlib.md5(str(DB_PATH).encode("utf-8", errors="ignore")).hexdigest()[:12]
    _state_key_v266 = f"_esquema_actos_admin_v266_ok_{_scope_key_v266}"
    if st.session_state.get(_state_key_v266):
        return

    asegurar_esquema_documentos_respaldo_v249()
    asegurar_esquema_documentos_respaldo_docentes_v251()
    asegurar_esquema_dependencias_documentales_v262()

    if USE_POSTGRESQL:
        inst = _inst_scope_v266; dep = _dep_scope_v266
        conn = _pg_raw_conn(); cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documentos_respaldo_designaciones (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT NOT NULL,
                    documento_id BIGINT NOT NULL REFERENCES documentos_respaldo(id) ON DELETE CASCADE,
                    designacion_id BIGINT NOT NULL REFERENCES designaciones(id) ON DELETE CASCADE,
                    fecha_vinculacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usuario_vinculacion TEXT,
                    UNIQUE (institucion_id, departamento_id, designacion_id)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_docresp_designaciones_doc_v266
                ON documentos_respaldo_designaciones (institucion_id, departamento_id, documento_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_docresp_designaciones_desig_v266
                ON documentos_respaldo_designaciones (institucion_id, departamento_id, designacion_id)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documentos_respaldo_movimientos (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT NOT NULL,
                    documento_id BIGINT NOT NULL REFERENCES documentos_respaldo(id) ON DELETE CASCADE,
                    movimiento_id BIGINT NOT NULL REFERENCES movimientos(id) ON DELETE CASCADE,
                    fecha_vinculacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usuario_vinculacion TEXT,
                    UNIQUE (institucion_id, departamento_id, movimiento_id)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_docresp_movimientos_doc_v266
                ON documentos_respaldo_movimientos (institucion_id, departamento_id, documento_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_docresp_movimientos_mov_v266
                ON documentos_respaldo_movimientos (institucion_id, departamento_id, movimiento_id)
            """)

            # Números manuales históricos: solo se vinculan si el número identifica
            # exactamente un documento del repositorio dentro del departamento.
            cur.execute("""
                INSERT INTO documentos_respaldo_designaciones
                    (institucion_id, departamento_id, documento_id, designacion_id, usuario_vinculacion)
                SELECT d.institucion_id, d.departamento_id,
                       MIN(doc.id) AS documento_id, d.id, 'migracion-v266'
                FROM designaciones d
                JOIN documentos_respaldo doc
                  ON doc.institucion_id=d.institucion_id
                 AND doc.departamento_id=d.departamento_id
                 AND TRIM(COALESCE(doc.numero,''))=TRIM(COALESCE(d.numero_resolucion,''))
                LEFT JOIN documentos_respaldo_designaciones rel
                  ON rel.institucion_id=d.institucion_id
                 AND rel.departamento_id=d.departamento_id
                 AND rel.designacion_id=d.id
                WHERE d.institucion_id=%s AND d.departamento_id=%s
                  AND TRIM(COALESCE(d.numero_resolucion,''))<>''
                  AND rel.id IS NULL
                GROUP BY d.institucion_id, d.departamento_id, d.id
                HAVING COUNT(DISTINCT doc.id)=1
                ON CONFLICT (institucion_id, departamento_id, designacion_id) DO NOTHING
            """, [int(inst), int(dep)])

            # PDFs creados por v263 para movimientos: transforma el vínculo genérico
            # por CUIL/tipo/detalle en una relación exacta al movimiento, si es único.
            cur.execute("""
                INSERT INTO documentos_respaldo_movimientos
                    (institucion_id, departamento_id, documento_id, movimiento_id, usuario_vinculacion)
                SELECT m.institucion_id, m.departamento_id,
                       MIN(rd.documento_id) AS documento_id, m.id, 'migracion-v266'
                FROM movimientos m
                JOIN documentos_respaldo_docentes rd
                  ON rd.institucion_id=m.institucion_id
                 AND rd.departamento_id=m.departamento_id
                 AND TRIM(COALESCE(rd.cuil,''))=TRIM(COALESCE(m.cuil,''))
                 AND TRIM(COALESCE(rd.tipo_movimiento,''))=TRIM(COALESCE(m.tipo_movimiento,''))
                 AND TRIM(COALESCE(rd.detalle_vinculo,''))=TRIM(COALESCE(m.detalle,''))
                LEFT JOIN documentos_respaldo_movimientos rm
                  ON rm.institucion_id=m.institucion_id
                 AND rm.departamento_id=m.departamento_id
                 AND rm.movimiento_id=m.id
                WHERE m.institucion_id=%s AND m.departamento_id=%s
                  AND rm.id IS NULL
                GROUP BY m.institucion_id, m.departamento_id, m.id
                HAVING COUNT(DISTINCT rd.documento_id)=1
                ON CONFLICT (institucion_id, departamento_id, movimiento_id) DO NOTHING
            """, [int(inst), int(dep)])
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        conn = get_conn(); c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS documentos_respaldo_designaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                documento_id INTEGER NOT NULL,
                designacion_id INTEGER NOT NULL UNIQUE,
                fecha_vinculacion TEXT,
                usuario_vinculacion TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS documentos_respaldo_movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                documento_id INTEGER NOT NULL,
                movimiento_id INTEGER NOT NULL UNIQUE,
                fecha_vinculacion TEXT,
                usuario_vinculacion TEXT
            )
        """)
        try:
            candidatos = pd.read_sql("""
                SELECT d.id AS designacion_id, TRIM(COALESCE(d.numero_resolucion,'')) AS numero
                FROM designaciones d
                LEFT JOIN documentos_respaldo_designaciones r ON r.designacion_id=d.id
                WHERE TRIM(COALESCE(d.numero_resolucion,''))<>'' AND r.id IS NULL
            """, conn)
            for _, row in candidatos.iterrows():
                docs = pd.read_sql(
                    "SELECT id FROM documentos_respaldo WHERE TRIM(COALESCE(numero,''))=TRIM(?)",
                    conn, params=[str(row.get("numero") or "")]
                )
                if len(docs) == 1:
                    c.execute("""
                        INSERT OR IGNORE INTO documentos_respaldo_designaciones
                            (documento_id, designacion_id, fecha_vinculacion, usuario_vinculacion)
                        VALUES (?,?,?,?)
                    """, (int(docs.iloc[0]["id"]), int(row["designacion_id"]), datetime.now().isoformat(timespec="seconds"), "migracion-v266"))
        except Exception:
            pass
        try:
            candidatos_mov = pd.read_sql("""
                SELECT m.id AS movimiento_id, m.cuil, m.tipo_movimiento, m.detalle
                FROM movimientos m
                LEFT JOIN documentos_respaldo_movimientos r ON r.movimiento_id=m.id
                WHERE r.id IS NULL
            """, conn)
            for _, row in candidatos_mov.iterrows():
                docs = pd.read_sql("""
                    SELECT DISTINCT documento_id
                    FROM documentos_respaldo_docentes
                    WHERE TRIM(COALESCE(cuil,''))=TRIM(?)
                      AND TRIM(COALESCE(tipo_movimiento,''))=TRIM(?)
                      AND TRIM(COALESCE(detalle_vinculo,''))=TRIM(?)
                """, conn, params=[str(row.get("cuil") or ""), str(row.get("tipo_movimiento") or ""), str(row.get("detalle") or "")])
                if len(docs) == 1:
                    c.execute("""
                        INSERT OR IGNORE INTO documentos_respaldo_movimientos
                            (documento_id, movimiento_id, fecha_vinculacion, usuario_vinculacion)
                        VALUES (?,?,?,?)
                    """, (int(docs.iloc[0]["documento_id"]), int(row["movimiento_id"]), datetime.now().isoformat(timespec="seconds"), "migracion-v266"))
        except Exception:
            pass
        conn.commit(); conn.close()

    st.session_state[_state_key_v266] = True


# --- entry l. 54344-54378
def _mapa_actos_designaciones_v266(ids_designacion):
    asegurar_esquema_actos_administrativos_v266()
    ids = sorted({int(x) for x in ids_designacion if pd.notna(x)})
    if not ids:
        return {}
    if USE_POSTGRESQL:
        inst = _pg_current_inst_id(); dep = _pg_current_dep_id()
        ph = ",".join(["%s"] * len(ids))
        df = _pg_read_dataframe(f"""
            SELECT r.designacion_id, d.id AS documento_id, d.tipo_documento,
                   COALESCE(d.numero,'') AS numero, d.fecha,
                   COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                            CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                                 WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora
            FROM documentos_respaldo_designaciones r
            JOIN documentos_respaldo d ON d.id=r.documento_id
              AND d.institucion_id=r.institucion_id AND d.departamento_id=r.departamento_id
            LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
            WHERE r.institucion_id=%s AND r.departamento_id=%s
              AND r.designacion_id IN ({ph})
        """, [int(inst), int(dep)] + ids)
    else:
        conn = get_conn(); ph = ",".join(["?"] * len(ids))
        df = pd.read_sql(f"""
            SELECT r.designacion_id, d.id AS documento_id, d.tipo_documento,
                   COALESCE(d.numero,'') AS numero, d.fecha,
                   COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                            CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                                 WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora
            FROM documentos_respaldo_designaciones r
            JOIN documentos_respaldo d ON d.id=r.documento_id
            LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id
            WHERE r.designacion_id IN ({ph})
        """, conn, params=ids); conn.close()
    return {int(r["designacion_id"]): r.to_dict() for _, r in df.iterrows()}


# --- entry l. 55154-55183
def _enriquecer_designaciones_acto_v266(df):
    if df is None or df.empty:
        return df
    out=df.copy()
    if "id" not in out.columns:
        return out
    mapa=_mapa_actos_designaciones_v266(pd.to_numeric(out["id"],errors="coerce").dropna().astype(int).tolist())
    out["numero_resolucion_legacy"] = out.get("numero_resolucion", pd.Series("", index=out.index)).fillna("").astype(str)
    out["acto_documento_id"] = pd.NA
    out["acto_administrativo"] = ""
    out["acto_dependencia"] = ""
    out["acto_fecha"] = ""
    for idx,row in out.iterrows():
        try: did=int(row.get("id"))
        except Exception: continue
        act=mapa.get(did)
        legacy=str(row.get("numero_resolucion_legacy") or "").strip()
        if act:
            out.at[idx,"acto_documento_id"] = int(act.get("documento_id"))
            out.at[idx,"acto_administrativo"] = _etiqueta_acto_v263(act.get("tipo_documento"),act.get("numero"),act.get("dependencia_emisora"))
            out.at[idx,"acto_dependencia"] = str(act.get("dependencia_emisora") or "")
            out.at[idx,"acto_fecha"] = str(act.get("fecha") or "")
            # El campo físico numero_resolucion NO se modifica ni se maquilla:
            # carga rápida conserva exactamente su comportamiento histórico y
            # los módulos nuevos consumen acto_documento_id/acto_administrativo.
        elif legacy:
            out.at[idx,"acto_administrativo"] = f"Resolución {legacy} — pendiente de vincular al repositorio"
        else:
            out.at[idx,"acto_administrativo"] = "Pendiente de vincular"
    return out


# --- entry l. 55186
_get_designaciones_pre_v266 = get_designaciones


# --- entry l. 55187-55188
def get_designaciones(periodo_id=None):
    return _enriquecer_designaciones_acto_v266(_get_designaciones_pre_v266(periodo_id))


# --- entry l. 55201
_get_designaciones_legacy_v282 = get_designaciones


# --- entry l. 55204-55211
def _modo_lectura_designaciones_v282():
    try:
        from analisis.motor.ref.integration.designations_pilot import normalize_designations_mode
        return normalize_designations_mode(
            _valor_configuracion("DEPTIT_DESIGNATIONS_READ_MODE", "off")
        )
    except Exception:
        return "off"


# --- entry l. 55215-55222
def _get_designaciones_nuevo_cache_v282(periodo_id, db_url, inst, dep, version):
    from analisis.motor.ref.integration.designations_pilot import build_designation_service
    from analisis.motor.ref.integration.periods_pilot import build_runtime_database

    db = build_runtime_database(_pg_raw_conn)
    service = build_designation_service(db, int(inst), int(dep))
    pid = int(periodo_id) if periodo_id is not None else None
    return service.list(pid, include_document=True)


# --- entry l. 55225-55254
def _guardar_diagnostico_designaciones_v282(decision, inst=None, dep=None, periodo_id=None, error=None):
    try:
        diag = decision.diagnostics() if decision is not None else {}
    except Exception:
        diag = {}
    try:
        diag.update({
            "institucion_id": int(inst) if inst is not None else None,
            "departamento_id": int(dep) if dep is not None else None,
            "periodo_id": int(periodo_id) if periodo_id is not None else None,
            "error": str(error)[:500] if error is not None else "",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        st.session_state["_v282_designations_read_diag"] = diag
        try:
            mostrar_stdout = str(_valor_configuracion("DEPTIT_DESIGNATIONS_DIAG_STDOUT", "0")).strip().casefold() in {"1", "true", "yes", "si", "sí"}
            if mostrar_stdout:
                print(
                    "[DEPTIT v282 designaciones] "
                    f"mode={diag.get('mode')} source={diag.get('source')} "
                    f"equivalent={diag.get('equivalent')} "
                    f"inst={diag.get('institucion_id')} dep={diag.get('departamento_id')} "
                    f"periodo={diag.get('periodo_id')} "
                    f"legacy_rows={diag.get('legacy_rows')} new_rows={diag.get('new_rows')} "
                    f"reason={diag.get('reason')} error={diag.get('error')}"
                )
        except Exception:
            pass
    except Exception:
        pass


# --- entry l. 55265-55318
def get_designaciones(periodo_id=None):
    legacy = _get_designaciones_legacy_v282(periodo_id)
    mode = _modo_lectura_designaciones_v282()

    if mode == "off":
        try:
            from analisis.motor.ref.integration.designations_pilot import choose_designations_frame
            decision = choose_designations_frame(mode="off", legacy=legacy)
            _guardar_diagnostico_designaciones_v282(decision, periodo_id=periodo_id)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)

    if not USE_POSTGRESQL or not DATABASE_URL:
        try:
            from analisis.motor.ref.integration.designations_pilot import choose_designations_frame
            decision = choose_designations_frame(
                mode=mode,
                legacy=legacy,
                new_error=RuntimeError("PostgreSQL no disponible para el piloto v282"),
            )
            _guardar_diagnostico_designaciones_v282(decision, periodo_id=periodo_id)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)

    db_url = str(DATABASE_URL)
    inst = dep = None
    try:
        db_url, inst, dep, version = _scope_rendimiento_v191()
        new_df = _get_designaciones_nuevo_cache_v282(
            int(periodo_id) if periodo_id is not None else None,
            str(db_url), int(inst), int(dep), version
        )
        from analisis.motor.ref.integration.designations_pilot import choose_designations_frame
        decision = choose_designations_frame(
            mode=mode,
            legacy=legacy,
            new=new_df,
        )
        _guardar_diagnostico_designaciones_v282(decision, inst, dep, periodo_id)
        return _copiar_resultado_cache_v191(decision.frame)
    except Exception as exc:
        try:
            from analisis.motor.ref.integration.designations_pilot import choose_designations_frame
            decision = choose_designations_frame(
                mode=mode,
                legacy=legacy,
                new_error=exc,
            )
            _guardar_diagnostico_designaciones_v282(decision, inst, dep, periodo_id, error=exc)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)
