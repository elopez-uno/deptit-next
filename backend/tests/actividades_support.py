"""Soporte de los tests de Actividades Especiales.

- Reutiliza la conexion real que NUNCA confirma (``db_conn``), los SAVEPOINT y la auditoria falsa de
  ``periodos_support``; las conexiones certificadas (``_ConnAislada``: COMMIT = RELEASE SAVEPOINT y registro de COMMITs
  por writer) de ``comisiones_support``; el inyector efectivo (v193 + B12J) de ``materias_support``.
- ``certified_actividades``: ejecuta, EN EL ORDEN DEL ENTRY, todas las definiciones (``def``) y alias simples del cierre
  transitivo de nombres que usa la pagina certificada de Actividades Especiales (l. 66418-66603), sin decoradores de
  cache.  Nada de reference_fix02 se modifica ni se compila a bytecode.
- Datos temporales: filas sinteticas con prefijo ``ZZNEXT`` dentro de la transaccion del test (ROLLBACK).
"""

from __future__ import annotations

import ast
import collections
import functools
import hashlib
import inspect
import json
import math
import re
import sys
import time
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import psycopg
import pytest
from psycopg.rows import dict_row

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from comisiones_support import (  # noqa: E402,F401  (fixtures re-exportados)
    FIXED_NOW, USER_EMAIL, _ConnAislada, _FixedDateTime, _Session, _instalar_execute_values, _literal_assigns,
    audit_rows, lock_conn,
)
from designaciones_support import _Frames, _St  # noqa: E402
from materias_support import planes_injector  # noqa: E402
from periodos_support import (  # noqa: E402,F401  (fixtures re-exportados)
    ENTRY, EXTRA_DEPARTMENTS, FIXED_TODAY, FakeAuditStore, _FixedDate, _tree, audit_store, db_conn, savepoint,
    session_for,
)

PAGE = (66418, 66603)
EXTRA_START = {
    "get_actividades_especiales_docente", "get_actividades_especiales", "guardar_actividad_especial",
    "actualizar_actividad_especial", "asignar_docente_actividad_especial", "eliminar_actividad_especial",
    "eliminar_asignacion_actividad_especial", "get_actividades_especiales_docente_disposicion_v159",
    "texto_actividades_especiales_docente", "get_docentes",
}
BUSINESS = (
    "guardar_actividad_especial", "actualizar_actividad_especial", "asignar_docente_actividad_especial",
    "eliminar_actividad_especial", "eliminar_asignacion_actividad_especial",
)
EXCLUDE = {
    "st", "_ejecutar_project_business_write_v292", "_ejecutar_research_assignment_business_write_v294",
    "_guardar_diagnostico_project_business_write_v292", "_guardar_diagnostico_research_assignment_business_write_v294",
    "_modo_project_business_write_v292", "_modo_research_assignment_business_write_v294",
    "_ejecutar_extension_project_business_write_v293", "_ejecutar_extension_assignment_business_write_v295",
    "_guardar_diagnostico_extension_project_business_write_v293",
    "_guardar_diagnostico_extension_assignment_business_write_v295",
    "_modo_extension_project_business_write_v293", "_modo_extension_assignment_business_write_v295",
    "seleccionar_registro_desde_tabla",
}


@functools.lru_cache(maxsize=1)
def _closure_nodes() -> tuple:
    tree = _tree(ENTRY)
    defs = collections.defaultdict(list)
    aliases = {}
    for node in tree.body:
        if node.lineno >= PAGE[0]:
            continue
        if isinstance(node, ast.FunctionDef):
            defs[node.name].append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name):
            aliases.setdefault(node.targets[0].id, []).append(node)

    def names_in(node):
        return {x.id for x in ast.walk(node) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)}

    start = set(EXTRA_START)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and PAGE[0] <= getattr(node, "lineno", 0) <= PAGE[1]:
            start.add(node.id)
    seen, queue = set(), list(start)
    while queue:
        name = queue.pop()
        if name in seen or name in EXCLUDE:
            continue
        seen.add(name)
        for d in defs.get(name, []):
            queue.extend(names_in(d) - seen)
        for a in aliases.get(name, []):
            queue.append(a.value.id)
    picked = []
    for node in tree.body:
        if node.lineno >= PAGE[0]:
            continue
        if isinstance(node, ast.FunctionDef) and node.name in seen:
            picked.append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name) and node.targets[0].id in seen:
            picked.append(node)
    for node in picked:
        if isinstance(node, ast.FunctionDef):
            node.decorator_list = []
    return tuple(picked), frozenset(seen)


DEP_NOMBRES = {1: "Departamento de Informática e Ingeniería", 2: "Departamento de Administración"}


def certified_actividades(raw_conn, institution_id: int, department_id: int, rol: str = "usuario_departamento",
                            email: str = USER_EMAIL, dep_nombre: str | None = None) -> dict:
    """Namespace con las lecturas y writers certificados de Actividades Especiales sobre ``raw_conn``."""
    injector = planes_injector()
    frames = _Frames()
    session = _Session()

    def dep_actual():
        return int(session.get("tenant_scope_departamento_id", department_id))

    def tenant():
        return {"kind": "tenant", "institucion_id": int(institution_id), "departamento_id": dep_actual()}

    def get_conn():
        return _ConnAislada(raw_conn, frames, tenant(), injector)

    def _pg_raw_conn():
        return _ConnAislada(raw_conn, frames)

    def _pg_read_dataframe(sql, params=None):
        with raw_conn.transaction():
            cur = psycopg.ClientCursor(raw_conn)
            cur.execute(sql, list(params or []))
            rows = cur.fetchall() if cur.description else []
            cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    _instalar_execute_values()
    nodes, names = _closure_nodes()
    _St.warnings = []
    _St.session_state = session
    nombre_dep = dep_nombre if dep_nombre is not None else DEP_NOMBRES.get(int(department_id), "")
    ns = {
        "__builtins__": __builtins__,
        "USE_POSTGRESQL": True, "DATABASE_URL": "postgresql://test", "MODO_SANEAMIENTO_MATERIAS_INDIVIDUAL": False,
        "get_conn": get_conn, "get_planes_conn": lambda: _ConnAislada(raw_conn, frames, {"kind": "planes",
                                                                                         "institucion_id": int(institution_id)}, injector),
        "get_auth_conn": lambda: _ConnAislada(raw_conn, frames, {"kind": "auth"}, injector),
        "_pg_raw_conn": _pg_raw_conn, "_pg_read_dataframe": _pg_read_dataframe,
        "_pg_current_inst_id": lambda: institution_id, "_pg_current_dep_id": dep_actual,
        "_institucion_id_operativa": lambda: institution_id,
        "current_role": lambda: rol,
        "current_user": lambda: {"email": email, "rol": rol, "departamento_nombre": nombre_dep},
        "pd": pd, "re": re, "json": json, "math": math, "hashlib": hashlib, "time": time, "functools": functools,
        "inspect": inspect, "date": _FixedDate, "datetime": _FixedDateTime, "timedelta": timedelta, "BytesIO": BytesIO,
        "st": _St,
        "_scope_rendimiento_v191": lambda: ("postgresql://test", institution_id, dep_actual(), 0),
        "_copiar_resultado_cache_v191": lambda x: x.copy() if hasattr(x, "copy") else x,
        "_version_dependencias_v200": lambda *a, **k: 0, "invalidar_cache_rendimiento_v191": lambda *a, **k: None,
        "_envolver_funcion_perf_v193": lambda *a, **k: None,
        "_cache_scope_proyectos_v127": lambda *a, **k: ("postgresql://test", institution_id, dep_actual(), 0),
        "asegurar_esquema_investigacion_separado": lambda: None, "asegurar_esquema_extension_separado": lambda: None,
        "asegurar_esquema_documentos_respaldo_proyectos_v261": lambda: None,
        "asegurar_esquema_dependencias_documentales_v262": lambda: None,
        "asegurar_esquema_actos_administrativos_v266": lambda: None,
        "asegurar_esquema_prestamos_docentes_v174": lambda: None, "asegurar_esquema_v95": lambda: None,
        "asegurar_esquema_config_productividad_v148": lambda: None, "asegurar_esquema_planes_db": lambda: None,
        "asegurar_esquema_inscriptos_asignatura_periodo_v248": lambda: None,
        "asegurar_esquema_sedes_institucionales": lambda: None, "asegurar_esquema_inscriptos_comision": lambda: None,
        "asegurar_esquema_materia_especifica_comision": lambda: None,
        "asegurar_esquema_materias_compartidas_comision_v118": lambda: None,
        "asegurar_esquema_opciones_curriculares_v120": lambda: None,
        "asegurar_esquema_comparticion_materias_v137": lambda: None,
        "sincronizar_planes_si_corresponde": lambda: None,
        "sincronizar_vencimientos_concursados_v268": lambda *_: 0,
        "reconciliar_fechas_finalizacion_desde_movimientos_v212": lambda *a, **k: 0,
        "migrar_inscriptos_a_asignatura_periodo_v248": lambda *a, **k: 0,
        "_b12f_arranque_omitido": lambda *a, **k: None,
        "_versiones_scope_v199": lambda *a, **k: (0, 0, 0),
        "limpiar_cache_comisiones_operativas": lambda *a, **k: None,
        "_modo_lectura_proyectos_v283": lambda: "off",
    }
    for k, v in _literal_assigns(names).items():
        ns.setdefault(k, v)
    from deptit_refactor.catalogs import comisiones as cat_com
    from deptit_refactor.catalogs import designaciones as cat_des
    from deptit_refactor.catalogs import materias as cat_mat
    for mod in (cat_com, cat_des, cat_mat):
        for k in dir(mod):
            if k.isupper() or k.startswith("_") and k[1:2].isupper():
                ns.setdefault(k, getattr(mod, k))
    infra = {k: v for k, v in ns.items() if callable(v) and k not in ("pd", "re", "json", "math", "hashlib", "time",
                                                                       "functools", "inspect", "date", "datetime",
                                                                       "timedelta", "BytesIO", "st")}
    exec(compile(ast.Module(body=list(nodes), type_ignores=[]), str(ENTRY), "exec"), ns)
    ns.update(infra)
    _unif = ns.get("_materias_para_comisiones_unificadas_y_mapa")
    if _unif is not None:
        _memo: dict = {}

        def _unificadas_memo():
            key = len(frames.commits)
            if key not in _memo:
                _memo.clear()
                _memo[key] = _unif()
            unicas, mapa = _memo[key]
            return unicas.copy(), mapa.copy()
        ns["_materias_para_comisiones_unificadas_y_mapa"] = _unificadas_memo
    for name in BUSINESS:
        if name not in ns:
            continue

        def framed(*args, _fn=ns[name], _name=name, **kwargs):
            frames.enter("business", _name)
            try:
                return _fn(*args, **kwargs)
            finally:
                frames.stack.pop()
        ns[name] = framed
    ns["_frames"] = frames
    ns["_session"] = session
    return ns


# ------------------------------------------------------------------------------------------ estado comparable
_TABLAS = [
    ("actividades_especiales", {}),
    ("actividad_especial_docente", {"actividad_id": "actividades_especiales"}),
    ("movimientos", {}),
]
MAX_IDS: dict = {}


def baseline(conn) -> None:
    for tabla, _ in _TABLAS:
        MAX_IDS[tabla] = conn.execute(f"SELECT coalesce(max(id),0) FROM {tabla}").fetchone()[0]


def state(conn, inst: int) -> dict:
    """Contenido de las tablas que tocan los writers de Actividades Especiales; ids nuevos -> orden de creacion."""
    datos, nuevos = {}, {}
    with conn.cursor(row_factory=dict_row) as cur:
        for tabla, _ in _TABLAS:
            cur.execute(f"SELECT * FROM {tabla} WHERE institucion_id=%s ORDER BY id", [inst])
            filas = list(cur.fetchall())
            ids_nuevos = [r["id"] for r in filas if r["id"] > MAX_IDS.get(tabla, 0)]
            nuevos[tabla] = {i: f"N{n}" for n, i in enumerate(ids_nuevos, start=1)}
            datos[tabla] = filas
    out = {}
    for tabla, fks in _TABLAS:
        filas = []
        for r in datos[tabla]:
            d = dict(r)
            d["id"] = nuevos[tabla].get(r["id"], r["id"])
            d.pop("fecha_vinculacion", None)  # CURRENT_TIMESTAMP de la transaccion
            for col, ref in fks.items():
                if d.get(col) is not None:
                    d[col] = nuevos[ref].get(d[col], d[col])
            filas.append(json.dumps(d, sort_keys=True, default=str))
        out[tabla] = filas
    return out


# ------------------------------------------------------------------------------------------ fixtures de servicio
def make_actividades(service, audit_store, db_conn, **kwargs):
    from actividades_especiales.service import ActividadesService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return ActividadesService(None, service, audit_store, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, **kwargs)


@pytest.fixture
def actividades(service, repo, db_conn, audit_store):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    return make_actividades(service, audit_store, db_conn)


@pytest.fixture
def http(service, actividades):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from actividades_especiales.routes import router as actividades_router
    from auth.routes import router as auth_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(actividades_router)
    application.state.auth = service
    application.state.actividades_especiales = actividades
    return TestClient(application, base_url="http://localhost")


__all__ = ["certified_actividades", "baseline", "state", "make_actividades", "audit_rows", "FIXED_TODAY",
           "FIXED_NOW", "session_for", "dict_row", "datetime", "date"]
