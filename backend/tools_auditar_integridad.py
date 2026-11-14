"""Auditoria READ ONLY de integridad referencial y unicidad de ``deptit_next_dev`` (Etapa 5 / Tanda A, A2 + A3).

Una sola transaccion ``READ ONLY``; sin DDL, sin escrituras; solo conteos e identificadores tecnicos (ids), nunca datos
personales (CUIL, nombres, emails) en la salida.  Releva:
- FKs existentes (``pg_constraint``) y, por cada relacion logica (columna ``*_id`` / tenant), si tiene FK;
- huerfanos: hijo con id que no existe en el padre;
- desalineacion de tenant: hijo y padre con distinta institucion / departamento (o departamento de otra institucion);
- relaciones por CUIL (sin FK posible): filas sin docente del mismo departamento;
- unicidades logicas case-insensitive / por tenant y los indices UNIQUE existentes.
Uso: ``python -B tools_auditar_integridad.py <salida.json>``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import psycopg

import db

# (hija, columna, padre, columnas de tenant a comparar con el padre, condicion extra sobre la hija)
RELACIONES = [
    ("actividad_especial_docente", "actividad_id", "actividades_especiales", ("institucion_id", "departamento_id"), None),
    ("asignaciones_docentes_comision", "comision_id", "comisiones", ("institucion_id", "departamento_id"), None),
    ("comision_materias", "comision_id", "comisiones", ("institucion_id", "departamento_id"), None),
    ("comision_materias", "materia_id", "materias", ("institucion_id",), None),
    ("comisiones", "materia_id", "materias", ("institucion_id",), None),
    ("comisiones", "opcion_curricular_id", "opciones_curriculares", ("institucion_id",), None),
    ("designaciones", "resolucion_id", "resoluciones", ("institucion_id", "departamento_id"), None),
    ("disposicion_docente_designaciones", "designacion_id", "designaciones", ("institucion_id", "departamento_id"), None),
    ("documentos_respaldo", "dependencia_id", "dependencias_documentales", ("institucion_id",), None),
    ("documentos_respaldo", "proyecto_id", "proyectos_investigacion", ("institucion_id", "departamento_id"),
     "h.proyecto_tipo ILIKE 'invest%%'"),
    ("documentos_respaldo", "proyecto_id", "proyectos_extension", ("institucion_id", "departamento_id"),
     "h.proyecto_tipo ILIKE 'exten%%'"),
    ("documentos_respaldo_designaciones", "documento_id", "documentos_respaldo", ("institucion_id", "departamento_id"), None),
    ("documentos_respaldo_designaciones", "designacion_id", "designaciones", ("institucion_id", "departamento_id"), None),
    ("documentos_respaldo_docentes", "documento_id", "documentos_respaldo", ("institucion_id", "departamento_id"), None),
    ("documentos_respaldo_movimientos", "documento_id", "documentos_respaldo", ("institucion_id", "departamento_id"), None),
    ("documentos_respaldo_movimientos", "movimiento_id", "movimientos", ("institucion_id", "departamento_id"), None),
    ("documentos_respaldo_proyectos", "documento_id", "documentos_respaldo", ("institucion_id", "departamento_id"), None),
    ("documentos_respaldo_proyectos", "proyecto_id", "proyectos_investigacion", ("institucion_id", "departamento_id"),
     "h.proyecto_tipo ILIKE 'invest%%'"),
    ("documentos_respaldo_proyectos", "proyecto_id", "proyectos_extension", ("institucion_id", "departamento_id"),
     "h.proyecto_tipo ILIKE 'exten%%'"),
    ("extension_docente", "proyecto_id", "proyectos_extension", ("institucion_id", "departamento_id"), None),
    ("investigacion_docente", "proyecto_id", "proyectos_investigacion", ("institucion_id", "departamento_id"), None),
    ("horarios_asignacion_docente_comision", "asignacion_id", "asignaciones_docentes_comision",
     ("institucion_id", "departamento_id"), None),
    ("horarios_asignacion_docente_comision", "horario_comision_id", "horarios_comision",
     ("institucion_id", "departamento_id"), None),
    ("horarios_comision", "comision_id", "comisiones", ("institucion_id", "departamento_id"), None),
    ("inscriptos_asignatura_periodo", "materia_id", "materias", ("institucion_id",), None),
    ("inscriptos_asignatura_periodo", "opcion_curricular_id", "opciones_curriculares", ("institucion_id",), None),
    ("inscriptos_comision", "comision_id", "comisiones", ("institucion_id", "departamento_id"), None),
    ("inscriptos_comision_materia", "comision_id", "comisiones", ("institucion_id", "departamento_id"), None),
    ("inscriptos_comision_materia", "materia_id", "materias", ("institucion_id",), None),
    ("materias", "carrera_id", "carreras", ("institucion_id",), None),
    ("opcion_curricular_materias", "opcion_id", "opciones_curriculares", ("institucion_id",), None),
    ("opcion_curricular_materias", "materia_id", "materias", ("institucion_id",), None),
]
TABLAS_CON_PERIODO = ["actividad_especial_docente", "actividades_especiales", "comisiones", "correcciones_historial_horas",
                      "designaciones", "disposiciones", "documentos_respaldo", "estado_consulta_designacion",
                      "extension_docente", "inscriptos_asignatura_periodo", "investigacion_docente", "movimientos",
                      "prestamos_docentes"]
TABLAS_CUIL = ["designaciones", "movimientos", "asignaciones_docentes_comision", "investigacion_docente",
               "extension_docente", "actividad_especial_docente", "disposiciones", "estado_consulta_designacion",
               "prestamos_docentes", "disposicion_docente_designaciones", "disposicion_docente_parametros",
               "correcciones_historial_horas", "documentos_respaldo_docentes"]
_DIG = "regexp_replace(COALESCE({c}, ''), '[^0-9]', '', 'g')"
UNICIDADES = [
    ("instituciones.nombre (ci, trim)", "instituciones", "LOWER(TRIM(nombre))", None),
    ("instituciones.slug (ci)", "instituciones", "LOWER(TRIM(slug))", None),
    ("app_usuarios.email (ci, trim)", "app_usuarios", "LOWER(TRIM(email))", None),
    ("departamentos.nombre por institucion (ci)", "departamentos", "institucion_id, LOWER(TRIM(nombre))", None),
    ("departamentos.slug por institucion (ci)", "departamentos", "institucion_id, LOWER(TRIM(slug))", None),
    ("periodos anio+semestre por departamento", "periodos", "institucion_id, departamento_id, anio, semestre", None),
    ("periodos.nombre por departamento (ci)", "periodos", "institucion_id, departamento_id, UPPER(TRIM(nombre))", None),
    ("docentes.cuil (digitos) por departamento", "docentes",
     "institucion_id, departamento_id, " + _DIG.format(c="cuil"), _DIG.format(c="cuil") + " <> ''"),
    ("carreras.codigo por institucion (ci)", "carreras", "institucion_id, LOWER(TRIM(codigo))", "TRIM(COALESCE(codigo,'')) <> ''"),
    ("carreras.nombre por institucion (ci)", "carreras", "institucion_id, LOWER(TRIM(nombre))", None),
    ("dependencias_documentales.nombre por institucion (ci)", "dependencias_documentales",
     "institucion_id, LOWER(TRIM(nombre))", None),
    ("sedes_institucion.nombre por institucion (ci)", "sedes_institucion", "institucion_id, LOWER(TRIM(nombre))", None),
    ("proyectos_investigacion.codigo por departamento (ci)", "proyectos_investigacion",
     "institucion_id, departamento_id, LOWER(TRIM(codigo_proyecto))", "TRIM(COALESCE(codigo_proyecto,'')) <> ''"),
    ("proyectos_extension.codigo por departamento (ci)", "proyectos_extension",
     "institucion_id, departamento_id, LOWER(TRIM(codigo_proyecto))", "TRIM(COALESCE(codigo_proyecto,'')) <> ''"),
    ("opciones_curriculares.codigo por institucion (ci)", "opciones_curriculares", "institucion_id, LOWER(TRIM(codigo))",
     "TRIM(COALESCE(codigo,'')) <> ''"),
]


def _uno(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()[0]


def auditar(conn) -> dict:
    tablas = {r[0]: set(r[1]) for r in conn.execute(
        "SELECT table_name, array_agg(column_name::text) FROM information_schema.columns "
        "WHERE table_schema = 'public' GROUP BY 1")}
    todas = [r[0] for r in conn.execute(
        "SELECT relname FROM pg_class WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace ORDER BY 1")]
    fks = {}
    for t, cols, ref in conn.execute(
            "SELECT conrelid::regclass::text, (SELECT array_agg(a.attname::text) FROM pg_attribute a "
            "WHERE a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)), confrelid::regclass::text "
            "FROM pg_constraint c WHERE contype = 'f' AND connamespace = 'public'::regnamespace"):
        for col in cols:
            fks[(t, col)] = ref
    res: dict = {"tablas_fisicas": todas, "tablas_visibles": sorted(tablas),
                 "tablas_sin_privilegio_de_lectura": sorted(set(todas) - set(tablas)),
                 "tenant": [], "relaciones": [], "periodo": [], "cuil": [], "unicidades": [], "unique_existentes": []}
    # 1. tenant
    for t in sorted(tablas):
        cols = tablas[t]
        if t in ("instituciones", "b12h_audit_log"):
            continue
        fila = {"tabla": t, "filas": _uno(conn, f'SELECT count(*) FROM "{t}"')}
        if "institucion_id" in cols:
            fila["fk_institucion"] = fks.get((t, "institucion_id"))
            fila["inst_null"] = _uno(conn, f'SELECT count(*) FROM "{t}" WHERE institucion_id IS NULL')
            fila["inst_huerfana"] = _uno(conn, f'SELECT count(*) FROM "{t}" h WHERE institucion_id IS NOT NULL AND '
                                               "NOT EXISTS (SELECT 1 FROM instituciones i WHERE i.id = h.institucion_id)")
        if "departamento_id" in cols and t != "departamentos":
            fila["fk_departamento"] = fks.get((t, "departamento_id"))
            fila["dep_null"] = _uno(conn, f'SELECT count(*) FROM "{t}" WHERE departamento_id IS NULL')
            fila["dep_huerfano"] = _uno(conn, f'SELECT count(*) FROM "{t}" h WHERE departamento_id IS NOT NULL AND '
                                              "NOT EXISTS (SELECT 1 FROM departamentos d WHERE d.id = h.departamento_id)")
            if "institucion_id" in cols:
                fila["dep_de_otra_institucion"] = _uno(
                    conn, f'SELECT count(*) FROM "{t}" h JOIN departamentos d ON d.id = h.departamento_id '
                          "WHERE d.institucion_id IS DISTINCT FROM h.institucion_id")
        if len(fila) > 2:
            res["tenant"].append(fila)
    # auditoria B12H: informativo (es log; las referencias pueden apuntar a tenants eliminados a proposito)
    res["b12h_inst_inexistente"] = _uno(
        conn, "SELECT count(*) FROM b12h_audit_log h WHERE institucion_id IS NOT NULL AND "
              "NOT EXISTS (SELECT 1 FROM instituciones i WHERE i.id = h.institucion_id)")

    def relacion(hija, col, padre, tenant, extra):
        if hija not in tablas or padre not in tablas or col not in tablas[hija]:
            return {"hija": hija, "columna": col, "padre": padre, "omitida": "tabla/columna inexistente o sin privilegio"}
        cond = f" AND {extra}" if extra else ""
        r = {"hija": hija, "columna": col, "padre": padre, "fk": fks.get((hija, col)),
             "con_valor": _uno(conn, f'SELECT count(*) FROM "{hija}" h WHERE h."{col}" IS NOT NULL{cond}'),
             "huerfanos": _uno(conn, f'SELECT count(*) FROM "{hija}" h WHERE h."{col}" IS NOT NULL{cond} AND NOT EXISTS '
                                     f'(SELECT 1 FROM "{padre}" p WHERE p.id = h."{col}")')}
        comunes = [c for c in tenant if c in tablas[hija] and c in tablas[padre]]
        if comunes:
            dif = " OR ".join(f"p.{c} IS DISTINCT FROM h.{c}" for c in comunes)
            r["tenant_distinto"] = _uno(conn, f'SELECT count(*) FROM "{hija}" h JOIN "{padre}" p ON p.id = h."{col}" '
                                              f"WHERE ({dif}){cond}")
            if r["tenant_distinto"]:
                r["ids_tenant_distinto_muestra"] = [x[0] for x in conn.execute(
                    f'SELECT h.id FROM "{hija}" h JOIN "{padre}" p ON p.id = h."{col}" WHERE ({dif}){cond} '
                    "ORDER BY h.id LIMIT 20")]
        if r["huerfanos"]:
            r["ids_huerfanos_muestra"] = [x[0] for x in conn.execute(
                f'SELECT h.id FROM "{hija}" h WHERE h."{col}" IS NOT NULL{cond} AND NOT EXISTS '
                f'(SELECT 1 FROM "{padre}" p WHERE p.id = h."{col}") ORDER BY h.id LIMIT 20')]
        return r

    for rel in RELACIONES:
        res["relaciones"].append(relacion(*rel))
    for t in TABLAS_CON_PERIODO:
        res["periodo"].append(relacion(t, "periodo_id", "periodos", ("institucion_id", "departamento_id"), None))
    # 3. CUIL (relacion logica por departamento; sin FK posible: docentes no tiene clave unica por CUIL)
    for t in TABLAS_CUIL:
        if t not in tablas or "cuil" not in tablas[t]:
            continue
        dig_h, dig_d = _DIG.format(c="h.cuil"), _DIG.format(c="d.cuil")
        tiene_dep = "departamento_id" in tablas[t]
        mismo = "d.institucion_id = h.institucion_id" + (" AND d.departamento_id = h.departamento_id" if tiene_dep else "")
        res["cuil"].append({
            "tabla": t, "por_departamento": tiene_dep,
            "con_cuil": _uno(conn, f'SELECT count(*) FROM "{t}" h WHERE {dig_h} <> \'\''),
            "sin_docente_mismo_tenant": _uno(
                conn, f'SELECT count(*) FROM "{t}" h WHERE {dig_h} <> \'\' AND NOT EXISTS '
                      f"(SELECT 1 FROM docentes d WHERE {mismo} AND {dig_d} = {dig_h})"),
            "sin_docente_en_ningun_tenant": _uno(
                conn, f'SELECT count(*) FROM "{t}" h WHERE {dig_h} <> \'\' AND NOT EXISTS '
                      f"(SELECT 1 FROM docentes d WHERE {dig_d} = {dig_h})"),
            "cuil_vacio": _uno(conn, f'SELECT count(*) FROM "{t}" h WHERE {dig_h} = \'\''),
        })
    # 4. unicidad
    for nombre, t, clave, filtro in UNICIDADES:
        if t not in tablas:
            res["unicidades"].append({"regla": nombre, "omitida": "sin privilegio"})
            continue
        w = f"WHERE {filtro}" if filtro else ""
        grupos = conn.execute(f'SELECT count(*), coalesce(sum(n), 0) FROM (SELECT count(*) n FROM "{t}" {w} '
                              f"GROUP BY {clave} HAVING count(*) > 1) x").fetchone()
        res["unicidades"].append({"regla": nombre, "grupos_duplicados": grupos[0], "filas_en_duplicados": int(grupos[1])})
    res["unique_existentes"] = [{"tabla": a, "indice": b, "def": c} for a, b, c in conn.execute(
        "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexdef ILIKE "
        "'CREATE UNIQUE%%' AND indexname NOT LIKE '%%_pkey' ORDER BY 1, 2")]
    return res


if __name__ == "__main__":
    s = db.load_settings()
    db.check_config(s)
    with psycopg.connect(s["database_url"], connect_timeout=5, application_name="deptit_next_audit_e5") as conn:
        conn.read_only = True
        db.verify_identity(conn)
        with conn.transaction():
            out = auditar(conn)
    Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("ok")
