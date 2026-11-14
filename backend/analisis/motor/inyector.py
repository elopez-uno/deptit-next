"""GENERADO -- NO EDITAR.  Inyector de ambito B12B efectivo del entry (v193 para SELECT; original para
INSERT/UPDATE/DELETE), texto literal; ``_pg_scope_select`` lo re-enlaza B12J (``ref.b12j.left_join_scope``)."""
# flake8: noqa
# fmt: off

PG_INSTITUTION_TABLES = {"carreras", "materias", "proyectos_investigacion", "proyectos_extension", "disposicion_docente_designaciones", "opciones_curriculares", "opcion_curricular_materias", "escalas_salariales_docentes", "dependencias_documentales"}
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

# --- entry l. 824-827 (_pg_quote_literal_text #0)
def _pg_quote_literal_text(valor, default=', '):
    'Convierte un literal SQL simple a texto seguro para usar como separador.'
    from analisis.motor.ref.extracted_batch01.infra_db import _pg_quote_literal_text as _b01_core__pg_quote_literal_text
    return _b01_core__pg_quote_literal_text(valor, default)


# --- entry l. 780-821 (_pg_split_sql_args #0)
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


# --- entry l. 830-895 (_pg_convert_group_concat #0)
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


# --- entry l. 896-904 (_pg_convert_sql #0)
def _pg_convert_sql(sql):
    sql = str(sql or "")
    # placeholders SQLite -> psycopg2
    sql = sql.replace("?", "%s")
    # funciones SQLite frecuentes
    sql = re.sub(r"\bIFNULL\s*\(", "COALESCE(", sql, flags=re.I)
    # GROUP_CONCAT de SQLite -> STRING_AGG de PostgreSQL, con parseo seguro.
    sql = _pg_convert_group_concat(sql)
    return sql


# --- entry l. 997-1047 (_pg_top_level_positions #0)
def _pg_top_level_positions(sql, patterns):
    """Busca palabras/cláusulas SQL solo en nivel superior, ignorando subconsultas."""
    sql = str(sql or "")
    results = []
    depth = 0
    i = 0
    in_single = False
    in_double = False
    while i < len(sql):
        ch = sql[i]
        if in_single:
            if ch == "'" and (i + 1 >= len(sql) or sql[i + 1] != "'"):
                in_single = False
            elif ch == "'" and i + 1 < len(sql) and sql[i + 1] == "'":
                i += 1
            i += 1
            continue
        if in_double:
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
            i += 1
            continue
        if ch == '"':
            in_double = True
            i += 1
            continue
        if ch == '(':
            depth += 1
            i += 1
            continue
        if ch == ')':
            depth = max(0, depth - 1)
            i += 1
            continue
        if depth == 0:
            tail = sql[i:]
            for name, pattern in patterns:
                m = re.match(pattern, tail, flags=re.I)
                if m:
                    results.append((name, i, i + m.end()))
                    i += max(1, m.end())
                    break
            else:
                i += 1
        else:
            i += 1
    return results


# --- entry l. 1079-1103 (_pg_insert_conditions #0)
def _pg_insert_conditions(sql, conditions, params, cond_values):
    """Inserta condiciones en el WHERE principal sin tocar subconsultas."""
    if not conditions:
        return sql, params
    sql = str(sql or "")
    clause = " AND ".join([f"({c})" for c in conditions])
    positions = _pg_top_level_positions(sql, [
        ("where", r"\bWHERE\b"),
        ("group", r"\bGROUP\s+BY\b"),
        ("having", r"\bHAVING\b"),
        ("order", r"\bORDER\s+BY\b"),
        ("limit", r"\bLIMIT\b"),
        ("offset", r"\bOFFSET\b"),
    ])
    insert_pos = len(sql)
    for name, start, _ in positions:
        if name in {"group", "having", "order", "limit", "offset"}:
            insert_pos = min(insert_pos, start)
    where_positions = [(s, e) for name, s, e in positions if name == "where" and s < insert_pos]
    before, after = sql[:insert_pos], sql[insert_pos:]
    if where_positions:
        before = before.rstrip() + " AND " + clause + " "
    else:
        before = before.rstrip() + " WHERE " + clause + " "
    return before + after, list(params or []) + list(cond_values or [])


# --- entry l. 42842-42869 (_pg_aliases_select_v193 #0)
def _pg_aliases_select_v193(sql_convertido):
    """Parsea FROM/JOIN una sola vez por SQL y devuelve (tabla, alias)."""
    sql_convertido = str(sql_convertido or "")
    pares = []
    reservadas = {
        "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "ON",
        "GROUP", "ORDER", "LIMIT", "HAVING", "OFFSET", "CROSS", "UNION",
    }
    posiciones = _pg_top_level_positions(
        sql_convertido,
        [("from", r"\bFROM\b"), ("join", r"\bJOIN\b")],
    )
    for _, _, fin_kw in posiciones:
        resto = sql_convertido[fin_kw:]
        m = re.match(
            r'\s+"?([A-Za-z_][A-Za-z0-9_]*)"?'
            r'(?:\s+(?:AS\s+)?"?([A-Za-z_][A-Za-z0-9_]*)"?)?',
            resto,
            flags=re.I,
        )
        if not m:
            continue
        tabla = str(m.group(1) or "").lower()
        alias = str(m.group(2) or m.group(1) or "")
        if alias.upper() in reservadas:
            alias = str(m.group(1) or "")
        pares.append((tabla, alias))
    return tuple(pares)


# --- entry l. 42873-42893 (_pg_scope_select_template_v193 #0)
def _pg_scope_select_template_v193(sql_original, kind, inst_id, dep_id):
    """Genera SQL scoped una sola vez para una combinación SQL/tenant."""
    sql_conv = _pg_convert_sql(sql_original)
    if str(kind or "") == "auth" or "information_schema" in sql_conv.lower():
        return sql_conv, tuple()

    condiciones = []
    valores = []
    for tabla, alias in _pg_aliases_select_v193(sql_conv):
        if tabla in PG_INSTITUTION_TABLES:
            condiciones.append(f"{alias}.institucion_id = %s")
            valores.append(int(inst_id))
        if str(kind or "") == "tenant" and tabla in PG_DEPARTMENT_TABLES:
            condiciones.append(f"{alias}.institucion_id = %s")
            valores.append(int(inst_id))
            if dep_id is not None:
                condiciones.append(f"{alias}.departamento_id = %s")
                valores.append(int(dep_id))

    q, scope_params = _pg_insert_conditions(sql_conv, condiciones, [], valores)
    return q, tuple(scope_params)


# --- entry l. 1131-1157 (_pg_scope_insert #0)
def _pg_scope_insert(sql, params, scope):
    sql = _pg_convert_sql(sql)
    params = list(params or [])
    m = re.match(r"\s*INSERT\s+INTO\s+\"?([A-Za-z_][A-Za-z0-9_]*)\"?\s*\((.*?)\)\s*VALUES\s*\((.*?)\)(.*)$", sql, flags=re.I|re.S)
    if not m or not isinstance(scope, dict) or scope.get("kind") == "auth":
        return sql, params
    table, cols_raw, vals_raw, rest = m.group(1), m.group(2), m.group(3), m.group(4) or ""
    table_l = table.lower()
    if table_l not in PG_ALL_SCOPED_TABLES:
        return sql, params
    cols = [c.strip().strip('"') for c in cols_raw.split(',')]
    vals = [v.strip() for v in vals_raw.split(',')]
    inst_id = scope.get("institucion_id") or _pg_current_inst_id()
    dep_id = scope.get("departamento_id") or _pg_current_dep_id()
    if "institucion_id" not in [c.lower() for c in cols]:
        cols.append("institucion_id")
        vals.append("%s")
        params.append(int(inst_id))
    if table_l in PG_DEPARTMENT_TABLES and "departamento_id" not in [c.lower() for c in cols] and dep_id is not None:
        cols.append("departamento_id")
        vals.append("%s")
        params.append(int(dep_id))
    # Para compatibilidad con cursor.lastrowid.
    if "returning" not in rest.lower():
        rest = (rest.rstrip() + " RETURNING id")
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(vals)}) {rest}"
    return sql, params


# --- entry l. 1160-1178 (_pg_scope_update_delete #0)
def _pg_scope_update_delete(sql, params, scope):
    sql = _pg_convert_sql(sql)
    params = list(params or [])
    if not isinstance(scope, dict) or scope.get("kind") == "auth":
        return sql, params
    m = re.match(r"\s*(UPDATE|DELETE\s+FROM)\s+\"?([A-Za-z_][A-Za-z0-9_]*)\"?", sql, flags=re.I)
    if not m:
        return sql, params
    table_l = m.group(2).lower()
    if table_l not in PG_ALL_SCOPED_TABLES:
        return sql, params
    inst_id = scope.get("institucion_id") or _pg_current_inst_id()
    dep_id = scope.get("departamento_id") or _pg_current_dep_id()
    conds = [f"{table_l}.institucion_id = %s"]
    vals = [int(inst_id)]
    if table_l in PG_DEPARTMENT_TABLES and dep_id is not None:
        conds.append(f"{table_l}.departamento_id = %s")
        vals.append(int(dep_id))
    return _pg_insert_conditions(sql, conds, params, vals)


# --- entry l. 42898-42918 (_pg_scope_select #1)
def _pg_scope_select(sql, params, scope):
    if not USE_POSTGRESQL or not isinstance(scope, dict) or scope.get("kind") == "auth":
        return _pg_convert_sql(sql), list(params or [])
    if "information_schema" in str(sql or "").lower():
        return _pg_convert_sql(sql), list(params or [])

    kind = str(scope.get("kind") or "tenant")
    inst_id = scope.get("institucion_id")
    dep_id = scope.get("departamento_id")
    if inst_id is None:
        inst_id = _pg_current_inst_id()
    if kind == "tenant" and dep_id is None:
        dep_id = _pg_current_dep_id()

    q, scope_vals = _pg_scope_select_template_v193(
        str(sql or ""),
        kind,
        int(inst_id or 0),
        int(dep_id) if dep_id is not None else None,
    )
    return q, list(params or []) + list(scope_vals)
