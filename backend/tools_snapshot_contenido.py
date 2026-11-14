"""Huella de CONTENIDO de deptit_next_dev (solo lectura) para las campañas BEFORE/AFTER (Etapa 5 / Tanda C, C2).

Reemplaza a ``docs/audit/e4_10_12/content_snapshot.py`` (evidencia historica, no se modifica), que usaba
``md5(fila::text)``: la misma huella fragil del flake TOAST de Resoluciones (``documentos_respaldo`` guarda un PDF de
2,8 MB y su ``::text`` puede variar transitoriamente bajo actividad TOAST concurrente de otra sesion, ETAPA4_CLOSE §11).
Aca cada fila se representa con COLUMNAS EXPLICITAS (orden de ``information_schema``), las ``bytea`` por el ``md5`` de
su contenido binario real, en orden estable por ``id``; ademas, la lista de columnas forma parte de la huella (un
cambio de esquema no pasa inadvertido).  Mismas 42 tablas que la herramienta anterior + las secuencias.
Uso: ``python -B tools_snapshot_contenido.py > snapshot.json``.
"""
from __future__ import annotations

import json
import sys

import psycopg

import db

TABLAS = ["docentes", "prestamos_docentes", "designaciones", "movimientos", "asignaciones_docentes_comision",
          "horarios_asignacion_docente_comision", "investigacion_docente", "extension_docente",
          "actividad_especial_docente", "estado_consulta_designacion", "correcciones_historial_horas",
          "disposicion_docente_parametros", "disposicion_docente_designaciones", "disposiciones", "periodos",
          "comisiones", "comision_materias", "opciones_curriculares", "opcion_curricular_materias", "carreras",
          "materias", "b12h_audit_log", "app_usuarios", "instituciones", "departamentos", "documentos_respaldo",
          "documentos_respaldo_designaciones", "documentos_respaldo_movimientos", "sedes_institucion",
          "inscriptos_asignatura_periodo", "inscriptos_comision", "inscriptos_comision_materia",
          "proyectos_investigacion", "documentos_respaldo_proyectos", "proyectos_extension",
          "escalas_salariales_docentes", "actividades_especiales", "disposicion_parametros",
          "dependencias_documentales", "documentos_respaldo_docentes", "resoluciones",
          "config_productividad_departamento"]


def huella(conn) -> dict:
    out: dict = {"tables": {}, "sequences": {}}
    for t in TABLAS:
        cols = conn.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = "
                            "'public' AND table_name = %s ORDER BY ordinal_position", [t]).fetchall()
        exprs = [f'md5("{c}")' if tipo == "bytea" else f'"{c}"::text' for c, tipo in cols]
        orden = '"id"' if any(c == "id" for c, _ in cols) else ", ".join(f'"{c}"::text' for c, _ in cols)
        fila = "json_build_array(" + ", ".join(exprs) + ")::text"
        n, h = conn.execute(f'SELECT count(*), md5(COALESCE(string_agg({fila}, E\'\\n\' ORDER BY {orden}), \'\')) '
                            f'FROM "{t}"').fetchone()
        out["tables"][t] = {"rows": n, "md5": h, "columns": [c for c, _ in cols]}
    for seq, last in conn.execute("SELECT sequencename, last_value FROM pg_sequences WHERE schemaname = 'public' "
                                  "ORDER BY 1").fetchall():
        out["sequences"][seq] = last
    return out


if __name__ == "__main__":
    s = db.load_settings()
    db.check_config(s)
    with psycopg.connect(s["database_url"], connect_timeout=5, application_name="deptit_next_audit") as c:
        db.verify_identity(c)
        c.execute("SET TRANSACTION READ ONLY")
        res = huella(c)
        c.rollback()
    json.dump(res, sys.stdout, indent=1, sort_keys=True)
