"""Soporte de los tests de Analisis — incluye Productividad.

- ``certified_analisis``: namespace con el cierre transitivo de la pagina ``📊 Análisis`` (l. 66604-67763) ejecutado
  DESDE ``reference_fix02`` (no desde la copia vendorizada), en el orden del entry, sobre la conexion del test con las
  conexiones certificadas de ``comisiones_support`` (SAVEPOINT por conexion + inyector B12B/B12J efectivo).  Igual que
  el runtime certificado: tareas de sistema ``reconciliation``/``migration`` -> ``None`` (compuerta B12F), ``schema``
  -> no-op, pilotos en ``off``, caches Streamlit (decoradas y de tiempo de ejecucion v199/v200) emuladas por memoizacion
  del namespace.  Nada de reference_fix02 se modifica ni se compila a bytecode.
- Fixtures de servicio/HTTP del bloque.  Datos sinteticos ``ZZNEXT`` dentro de la transaccion del test (ROLLBACK).
"""

from __future__ import annotations

import ast
import collections
import functools
import hashlib
import json
import math
import re
import sys
import time
from datetime import timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from comisiones_support import FIXED_NOW, _ConnAislada, _FixedDateTime, _Session, _instalar_execute_values  # noqa: E402
from designaciones_support import _Frames, _St  # noqa: E402
from materias_support import planes_injector  # noqa: E402
from periodos_support import (  # noqa: E402,F401  (fixtures re-exportados)
    ENTRY, EXTRA_DEPARTMENTS, FIXED_TODAY, FakeAuditStore, _FixedDate, _tree, audit_store, db_conn, savepoint,
    session_for,
)

PAGE = (66604, 67763)
CUTOFF = PAGE[0]


@functools.lru_cache(maxsize=1)
def _closure():
    import copy
    tree = copy.deepcopy(_tree(ENTRY))
    defs, aliases = collections.defaultdict(list), {}
    for node in tree.body:
        if node.lineno >= CUTOFF:
            continue
        if isinstance(node, ast.FunctionDef):
            defs[node.name].append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name):
            aliases.setdefault(node.targets[0].id, []).append(node)
    start = {x.id for x in ast.walk(tree) if isinstance(x, ast.Name) and PAGE[0] <= getattr(x, "lineno", 0) <= PAGE[1]}
    seen, queue = set(), list(start)
    while queue:
        n = queue.pop()
        if n in seen or n == "st":
            continue
        seen.add(n)
        for d in defs.get(n, []):
            queue.extend({x.id for x in ast.walk(d) if isinstance(x, ast.Name)} - seen)
        for a in aliases.get(n, []):
            queue.append(a.value.id)
    picked, cacheadas = [], set()
    for node in tree.body:
        if node.lineno >= CUTOFF:
            continue
        if isinstance(node, ast.FunctionDef) and node.name in seen:
            if any("cache" in ast.unparse(d) for d in node.decorator_list):
                cacheadas.add(node.name)
            node.decorator_list = []
            picked.append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name) and node.targets[0].id in seen:
            picked.append(node)
    lits, runtime = {}, set()
    for node in tree.body:
        if node.lineno >= CUTOFF:
            break
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            nombre = node.targets[0].id
            if nombre in ("_LECTURAS_CACHE_V199", "_DEPENDENCIAS_LECTURAS_V200"):
                valor = ast.literal_eval(node.value)
                runtime |= set(valor if isinstance(valor, list) else valor.keys())
            elif nombre in seen and nombre not in lits:
                try:
                    lits[nombre] = ast.literal_eval(node.value)
                except Exception:
                    pass
    code = compile(ast.Module(body=picked, type_ignores=[]), str(ENTRY), "exec")
    return code, frozenset(seen), lits, frozenset(cacheadas | (runtime & seen))


def certified_analisis(raw_conn, institution_id: int, department_id: int, email: str = "info@test.local",
                       departamento_nombre: str = "") -> dict:
    """Namespace certificado de la pagina Analisis sobre ``raw_conn`` (ver docstring del modulo)."""
    from deptit_refactor.security.legacy_write_actions import SYSTEM_WRITERS

    injector = planes_injector()
    frames = _Frames()
    tenant = {"kind": "tenant", "institucion_id": int(institution_id), "departamento_id": int(department_id)}

    def _pg_read_dataframe(sql, params=None):
        import psycopg
        with raw_conn.transaction():
            cur = psycopg.ClientCursor(raw_conn)
            cur.execute(sql, list(params or []))
            rows = cur.fetchall() if cur.description else []
            cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    _instalar_execute_values()
    code, names, lits, cacheadas = _closure()
    _St.warnings, _St.session_state = [], _Session()
    noop = lambda *a, **k: None  # noqa: E731
    ns = {"__builtins__": __builtins__, "USE_POSTGRESQL": True, "DATABASE_URL": "postgresql://test", "DB_PATH": "",
          "MODO_SANEAMIENTO_MATERIAS_INDIVIDUAL": False,
          "get_conn": lambda: _ConnAislada(raw_conn, frames, tenant, injector),
          "get_planes_conn": lambda: _ConnAislada(raw_conn, frames, {"kind": "planes",
                                                                     "institucion_id": int(institution_id)}, injector),
          "_pg_raw_conn": lambda: _ConnAislada(raw_conn, frames), "_pg_read_dataframe": _pg_read_dataframe,
          "_pg_current_inst_id": lambda: institution_id, "_pg_current_dep_id": lambda: department_id,
          "_institucion_id_operativa": lambda: institution_id, "current_role": lambda: "usuario_departamento",
          "current_user": lambda: {"email": email, "rol": "usuario_departamento",
                                   "departamento_nombre": departamento_nombre},
          "pd": pd, "re": re, "json": json, "math": math, "hashlib": hashlib, "time": time, "functools": functools,
          "date": _FixedDate, "datetime": _FixedDateTime, "timedelta": timedelta, "BytesIO": BytesIO, "st": _St,
          "_scope_rendimiento_v191": lambda: ("postgresql://test", institution_id, department_id, 0),
          "_copiar_resultado_cache_v191": lambda x: x.copy() if hasattr(x, "copy") else x,
          "_version_dependencias_v200": lambda *a, **k: 0, "invalidar_cache_rendimiento_v191": noop,
          "_envolver_funcion_perf_v193": noop, "_versiones_scope_v199": lambda *a, **k: (0, 0, 0),
          "_cache_scope_proyectos_v127": lambda *a, **k: ("postgresql://test", institution_id, department_id, 0),
          "limpiar_cache_comisiones_operativas": noop, "_b12f_arranque_omitido": noop}
    for w, (categoria, _d) in SYSTEM_WRITERS.items():
        ns[w] = noop if categoria == "schema" else (lambda *a, **k: None)
    for k, v in lits.items():
        ns.setdefault(k, v)
    from deptit_refactor.catalogs import comisiones as c1, designaciones as c2, materias as c3, movimientos as c4
    for mod in (c1, c2, c3, c4):
        for k in dir(mod):
            if k.isupper() or (k.startswith("_") and k[1:2].isupper()):
                ns.setdefault(k, getattr(mod, k))
    infra = {k: v for k, v in ns.items() if callable(v) and k not in (
        "pd", "re", "json", "math", "hashlib", "time", "functools", "date", "datetime", "timedelta", "BytesIO", "st")}
    exec(code, ns)
    ns.update(infra)
    for k in [n for n in ns if n.startswith("_modo_lectura_")]:
        ns[k] = lambda: "off"
    almacen: dict = {}
    for nombre in sorted(cacheadas):
        if nombre in ns and callable(ns[nombre]):
            def memo(*a, _f=ns[nombre], _n=nombre, **k):
                clave = (_n, repr(a), repr(sorted(k.items())))
                if clave not in almacen:
                    almacen[clave] = _f(*a, **k)
                v = almacen[clave]
                return v.copy() if hasattr(v, "copy") else v
            ns[nombre] = memo
    ns["_frames"] = frames
    return ns


def motor(raw_conn, institution_id: int, department_id: int, departamento_nombre: str = "", **kw) -> dict:
    """Namespace del motor NEXT vendorizado (mismo usuario logico que ``certified_analisis``)."""
    from analisis.motor import entorno
    return entorno.construir(raw_conn, institution_id, department_id,
                             usuario={"email": "info@test.local", "rol": "usuario_departamento",
                                      "departamento_nombre": departamento_nombre},
                             hoy=lambda: FIXED_TODAY, ahora=lambda: FIXED_NOW, **kw)


def igual_df(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    if not isinstance(a, pd.DataFrame) or not isinstance(b, pd.DataFrame):
        return a is b or a == b
    return list(a.columns) == list(b.columns) and a.astype(str).to_dict("records") == b.astype(str).to_dict("records")


def escalares(d: dict) -> dict:
    return {k: v for k, v in d.items() if not isinstance(v, pd.DataFrame)}


# ------------------------------------------------------------------------------------------ fixtures de servicio
def make_analisis(service, audit_store, db_conn, **kwargs):
    from analisis.service import AnalisisService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return AnalisisService(None, service, audit_store, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, **kwargs)


@pytest.fixture
def analisis(service, repo, db_conn, audit_store):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    return make_analisis(service, audit_store, db_conn)


@pytest.fixture
def http(service, analisis):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from analisis.routes import router as analisis_router
    from auth.routes import router as auth_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(analisis_router)
    application.state.auth = service
    application.state.analisis = analisis
    return TestClient(application, base_url="http://localhost")


__all__ = ["certified_analisis", "motor", "igual_df", "escalares", "make_analisis", "FIXED_TODAY", "FIXED_NOW",
           "session_for"]
