"""Soporte de los tests de Sueldos.

- Reutiliza la conexion real que NUNCA confirma (``db_conn``), los SAVEPOINT y la auditoria falsa de
  ``periodos_support``; las conexiones certificadas (``_ConnAislada``: COMMIT = RELEASE SAVEPOINT y registro de COMMITs
  por writer) de ``comisiones_support``; el inyector efectivo (v193 + B12J) de ``materias_support``.
- ``certified_sueldos``: ejecuta, EN EL ORDEN DEL ENTRY, todas las definiciones (``def``) y alias simples del cierre
  transitivo de nombres que usan la pagina certificada de Sueldos (l. 61762-61931), la seccion "💰 Sueldo estimado" del
  Resumen docente (``construir_tabla_sueldo_docente_v256``) y los costos de proyectos (``render_proyectos_vigentes_v101``
  -> ``calcular_costos_asignaciones_proyecto_v257``), sin decoradores de cache.  Despues re-enlaza el normalizador de
  posgrado con el de B12A (``_b12a_instalar_integridad_posgrado``, l. 59081) y deja ``asegurar_esquema_sueldos_v256`` en
  el modo verificacion de B12F (sin DDL ni semilla: no-op).  Nada de reference_fix02 se modifica ni compila a bytecode.
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
from datetime import timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import psycopg
import pytest
from psycopg.rows import dict_row

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from comisiones_support import (  # noqa: E402,F401  (fixtures re-exportados)
    FIXED_NOW, _ConnAislada, _FixedDateTime, _Session, _instalar_execute_values, audit_rows, lock_conn,
)
from designaciones_support import _Frames, _St  # noqa: E402
from materias_support import planes_injector  # noqa: E402
from periodos_support import (  # noqa: E402,F401  (fixtures re-exportados)
    ENTRY, EXTRA_DEPARTMENTS, FIXED_TODAY, FakeAuditStore, _FixedDate, _tree, audit_store, db_conn, savepoint,
    session_for,
)

PAGE = (61762, 61931)
EXTRA_START = {
    "construir_tabla_sueldo_docente_v256", "calcular_costos_asignaciones_proyecto_v257",
    "get_designaciones_docente_todos_departamentos_pg", "guardar_escala_salarial_v256",
    "get_investigacion_docente", "get_extension_docente", "_filtrar_asignaciones_proyecto_cierre_v183",
    "_mes_ref_desde_periodo_v256", "es_periodo_historico_contexto_v182", "_meses_ejecucion_proyecto_v258",
    "get_resumen_docente",
}
BUSINESS = ("guardar_escala_salarial_v256",)
EXCLUDE = {
    "st", "_ejecutar_project_business_write_v292", "_ejecutar_research_assignment_business_write_v294",
    "_guardar_diagnostico_project_business_write_v292", "_guardar_diagnostico_research_assignment_business_write_v294",
    "_modo_project_business_write_v292", "_modo_research_assignment_business_write_v294",
    "_ejecutar_extension_project_business_write_v293", "_ejecutar_extension_assignment_business_write_v295",
    "_guardar_diagnostico_extension_project_business_write_v293",
    "_guardar_diagnostico_extension_assignment_business_write_v295",
    "_modo_extension_project_business_write_v293", "_modo_extension_assignment_business_write_v295",
    "seleccionar_registro_desde_tabla", "asegurar_esquema_sueldos_v256",
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


def _literal_assigns(names) -> dict:
    out = {}
    for node in _tree(ENTRY).body:
        if node.lineno >= PAGE[0]:
            break
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in names and name not in out:
                try:
                    out[name] = ast.literal_eval(node.value)
                except Exception:
                    pass
    return out


USER_NOMBRE = {3: "Usuario 3", 6: "Usuario 6", 1: "Usuario 1"}


def certified_sueldos(raw_conn, institution_id: int, department_id, rol: str = "usuario_departamento",
                      email: str = "info@test.local", nombre: str = "Usuario 3") -> dict:
    """Namespace con las lecturas, el motor y el writer certificados de Sueldos sobre ``raw_conn``."""
    injector = planes_injector()
    frames = _Frames()
    session = _Session()

    def dep_actual():
        return session.get("tenant_scope_departamento_id", department_id)

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
        "current_user": lambda: {"email": email, "nombre": nombre, "rol": rol},
        "pd": pd, "re": re, "json": json, "math": math, "hashlib": hashlib, "time": time, "functools": functools,
        "inspect": inspect, "date": _FixedDate, "datetime": _FixedDateTime, "timedelta": timedelta, "BytesIO": BytesIO,
        "st": _St,
        "_scope_rendimiento_v191": lambda: ("postgresql://test", institution_id, dep_actual(), 0),
        "_copiar_resultado_cache_v191": lambda x: x.copy() if hasattr(x, "copy") else x,
        "_version_dependencias_v200": lambda *a, **k: 0, "invalidar_cache_rendimiento_v191": lambda *a, **k: None,
        "_envolver_funcion_perf_v193": lambda *a, **k: None,
        "_cache_scope_proyectos_v127": lambda *a, **k: ("postgresql://test", institution_id, dep_actual(), 0),
        # B12F modo verificacion: las asegurar_* no ejecutan DDL ni semillas; las reparaciones al leer se omiten.
        "asegurar_esquema_sueldos_v256": lambda: None,
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
        "asegurar_esquema_v162_funciones_y_disposiciones": lambda: None,
        "asegurar_esquema_resolucion_designacion_v155": lambda: None,
        "sincronizar_planes_si_corresponde": lambda: None,
        "sincronizar_vencimientos_concursados_v268": lambda *_: 0,
        "reconciliar_fechas_finalizacion_desde_movimientos_v212": lambda *a, **k: 0,
        "migrar_inscriptos_a_asignatura_periodo_v248": lambda *a, **k: 0,
        "_b12f_arranque_omitido": lambda *a, **k: None,
        "_versiones_scope_v199": lambda *a, **k: (0, 0, 0),
        "limpiar_cache_comisiones_operativas": lambda *a, **k: None,
        "_modo_lectura_proyectos_v283": lambda: "off",
        "_modo_designaciones_read_v282": lambda: "off",
        "_modo_teachers_read_v281": lambda: "off",
    }
    for k, v in _literal_assigns(names).items():
        ns.setdefault(k, v)
    from deptit_refactor.catalogs import comisiones as cat_com
    from deptit_refactor.catalogs import designaciones as cat_des
    from deptit_refactor.catalogs import materias as cat_mat
    from deptit_refactor.catalogs import salarios as cat_sal
    for mod in (cat_com, cat_des, cat_mat, cat_sal):
        for k in dir(mod):
            if k.isupper() or k.startswith("_") and k[1:2].isupper():
                ns.setdefault(k, getattr(mod, k))
    infra = {k: v for k, v in ns.items() if callable(v) and k not in ("pd", "re", "json", "math", "hashlib", "time",
                                                                       "functools", "inspect", "date", "datetime",
                                                                       "timedelta", "BytesIO", "st")}
    exec(compile(ast.Module(body=list(nodes), type_ignores=[]), str(ENTRY), "exec"), ns)
    ns.update(infra)
    # B12A (entry l. 59081-59086): el normalizador de posgrado efectivo es el de b12a/posgrado.py.
    from deptit_refactor.b12a.posgrado import _normalizer_b12a
    ns["_nivel_posgrado_salarial_normalizado_v256"] = _normalizer_b12a
    for name in BUSINESS:
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
def state(conn, inst: int) -> list[str]:
    """Contenido de ``escalas_salariales_docentes`` de la institucion (unica tabla que escribe Sueldos), sin ``id``
    (secuencia) y con ``movimientos`` contados (no debe cambiar)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT institucion_id, mes_referencia, cargo, basico_simple, fecha_actualizacion, "
                    "usuario_actualizacion FROM escalas_salariales_docentes WHERE institucion_id=%s "
                    "ORDER BY mes_referencia, cargo", [inst])
        filas = [json.dumps(dict(r), sort_keys=True, default=str) for r in cur.fetchall()]
        cur.execute("SELECT count(*) AS n FROM movimientos")
        filas.append(f"movimientos={cur.fetchone()['n']}")
    return filas


# ------------------------------------------------------------------------------------------ fixtures de servicio
def make_sueldos(service, audit_store, db_conn, **kwargs):
    from sueldos.service import SueldosService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return SueldosService(None, service, audit_store, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, **kwargs)


@pytest.fixture
def sueldos(service, repo, db_conn, audit_store):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    return make_sueldos(service, audit_store, db_conn)


@pytest.fixture
def http(service, sueldos):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from sueldos.routes import router as sueldos_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(sueldos_router)
    application.state.auth = service
    application.state.sueldos = sueldos
    return TestClient(application, base_url="http://localhost")


__all__ = ["certified_sueldos", "state", "make_sueldos", "audit_rows", "FIXED_TODAY", "FIXED_NOW", "session_for",
           "dict_row"]
