"""Soporte de los tests de Movimientos.

- Reutiliza la conexion real que NUNCA confirma (``db_conn``), los SAVEPOINT y la auditoria falsa de
  ``periodos_support``; las conexiones certificadas (``_ConnAislada``: COMMIT = RELEASE SAVEPOINT y registro de COMMITs
  por writer) de ``comisiones_support``; el inyector efectivo (v193 + B12J) de ``materias_support``.
- ``certified_movimientos``: ejecuta, EN EL ORDEN DEL ENTRY y hasta el ruteo de la pagina (l. 67764), todas las
  definiciones y alias simples del cierre transitivo de nombres que usa la pagina ``📜 Movimientos`` (l. 67764-67810)
  mas los writers que invoca.  ``get_movimientos`` queda enlazada igual que en el entry (l. 4824 -> alias legacy v284 ->
  l. 4946) con el piloto v284 en modo ``off`` (D-AL11); las cachés v191/v199/v200 son infraestructura y no se ejecutan.
  Nada de reference_fix02 se modifica ni se compila a bytecode.
- ``asegurar_esquema_actos_administrativos_v266`` (DDL) se reemplaza por un no-op (B12F).
- Datos temporales: filas sinteticas con prefijo ``ZZNEXT`` dentro de la transaccion del test (ROLLBACK).
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
import psycopg
import pytest
from psycopg.rows import dict_row

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from comisiones_support import (  # noqa: E402,F401  (fixtures re-exportados)
    FIXED_NOW, USER_EMAIL, _ConnAislada, _FixedDateTime, _Session, _instalar_execute_values, audit_rows,
)
from designaciones_support import _Frames, _St  # noqa: E402
from materias_support import planes_injector  # noqa: E402
from periodos_support import (  # noqa: E402,F401  (fixtures re-exportados)
    ENTRY, EXTRA_DEPARTMENTS, FIXED_TODAY, FakeAuditStore, _FixedDate, _tree, audit_store, db_conn, savepoint,
    session_for,
)

PAGE = (67764, 67810)
CUTOFF = 67764  # ruteo ``elif modulo == "📜 Movimientos"``: lo definido antes es lo efectivo
EXTRA_START = {"eliminar_movimiento", "vincular_acto_movimientos_masivo_v267", "desvincular_acto_movimientos_masivo_v267",
               "_mapa_actos_movimientos_v266", "_documentos_repo_v266", "_etiqueta_documento_id_v266"}
BUSINESS = ("eliminar_movimiento", "vincular_acto_movimientos_masivo_v267", "desvincular_acto_movimientos_masivo_v267")
EXCLUDE = {"st", "seleccionar_registro_desde_tabla"}


@functools.lru_cache(maxsize=1)
def _closure_nodes() -> tuple:
    tree = _tree(ENTRY)
    defs = collections.defaultdict(list)
    aliases = {}
    for node in tree.body:
        if node.lineno >= CUTOFF:
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
        if node.lineno >= CUTOFF:
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
        if node.lineno >= CUTOFF:
            break
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in names and name not in out:
                try:
                    out[name] = ast.literal_eval(node.value)
                except Exception:
                    pass
    return out


def certified_movimientos(raw_conn, institution_id: int, department_id: int, rol: str = "usuario_departamento",
                          email: str = USER_EMAIL) -> dict:
    """Namespace con las lecturas y writers certificados de la pagina Movimientos sobre ``raw_conn``."""
    injector = planes_injector()
    frames = _Frames()
    session = _Session()

    def tenant():
        return {"kind": "tenant", "institucion_id": int(institution_id), "departamento_id": int(department_id)}

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
    noop = lambda *a, **k: None  # noqa: E731
    ns = {
        "__builtins__": __builtins__,
        "USE_POSTGRESQL": True, "DATABASE_URL": "postgresql://test",
        "get_conn": get_conn, "_pg_raw_conn": _pg_raw_conn, "_pg_read_dataframe": _pg_read_dataframe,
        "get_auth_conn": lambda: _ConnAislada(raw_conn, frames, {"kind": "auth"}, injector),
        "_pg_current_inst_id": lambda: institution_id, "_pg_current_dep_id": lambda: department_id,
        "_institucion_id_operativa": lambda: institution_id,
        "current_role": lambda: rol,
        "current_user": lambda: {"email": email, "rol": rol, "departamento_nombre": ""},
        "pd": pd, "re": re, "json": json, "math": math, "hashlib": hashlib, "time": time, "functools": functools,
        "date": _FixedDate, "datetime": _FixedDateTime, "timedelta": timedelta, "BytesIO": BytesIO, "st": _St,
        "_scope_rendimiento_v191": lambda: ("postgresql://test", institution_id, department_id, 0),
        "_copiar_resultado_cache_v191": lambda x: x.copy() if hasattr(x, "copy") else x,
        "_version_dependencias_v200": lambda *a, **k: 0, "invalidar_cache_rendimiento_v191": noop,
        "_envolver_funcion_perf_v193": noop, "_versiones_scope_v199": lambda *a, **k: (0, 0, 0),
        # B12F: DDL incidental omitido
        "asegurar_esquema_actos_administrativos_v266": noop,
        # pilotos apagados (modo off = legado exacto, D-AL11)
        "_modo_lectura_movimientos_v284": lambda: "off", "_modo_lectura_periodos_v280": lambda: "off",
        "_modo_lectura_documentos_v286": lambda: "off",
    }
    for k, v in _literal_assigns(names).items():
        ns.setdefault(k, v)
    ns.setdefault("DB_PATH", "")  # alias legacy SQLite (``LEGACY_DB_PATH = DB_PATH``); rama SQLite no se ejecuta
    from deptit_refactor.catalogs import movimientos as cat_mov
    for k in dir(cat_mov):
        if k.isupper():
            ns.setdefault(k, getattr(cat_mov, k))
    infra = {k: v for k, v in ns.items() if callable(v) and k not in ("pd", "re", "json", "math", "hashlib", "time",
                                                                       "functools", "date", "datetime", "timedelta",
                                                                       "BytesIO", "st")}
    exec(compile(ast.Module(body=list(nodes), type_ignores=[]), str(ENTRY), "exec"), ns)
    ns.update(infra)
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


def pagina_certificada(ns: dict, periodo_sel: str | None = None, buscar: str = "") -> dict:
    """Reproduce la pagina l. 67764-67797 con el namespace certificado: opciones del selector, opcion por defecto, filas
    enriquecidas (tabla) y la vista del buscador.  ``seleccionar_registro_desde_tabla`` devuelve la primera fila."""
    df_periodos = ns["get_periodos"]()
    periodo_id_mov = None
    opciones, default = [], None
    if not df_periodos.empty:
        opciones_periodos = {"Todos los períodos": None}
        opciones_periodos.update({row["nombre"]: row["id"] for _, row in df_periodos.iterrows()})
        opciones = list(opciones_periodos.keys())
        pctx = ns["get_periodo_abierto"]() or ns["get_ultimo_periodo"]()
        dflt = str((pctx or {}).get("nombre") or "Todos los períodos")
        default = opciones[opciones.index(dflt) if dflt in opciones else 0]
        elegido = default if periodo_sel is None else periodo_sel
        periodo_id_mov = opciones_periodos[elegido]
    df_mov = ns["_enriquecer_movimientos_acto_v266"](ns["get_movimientos"](periodo_id_mov))
    vista = ns["filtrar_dataframe_por_texto"](df_mov, buscar, ["periodo", "fecha", "tipo_movimiento", "nombre", "cuil",
                                                               "detalle", "acto_administrativo", "observaciones"])
    return {"opciones": opciones, "default": default, "df": df_mov, "vista": vista,
            "primera": None if vista is None or vista.empty else int(vista.iloc[0]["id"])}


# ------------------------------------------------------------------------------------------ estado comparable
def state(conn, inst: int = 1) -> dict:
    """Contenido de ``movimientos`` y ``documentos_respaldo_movimientos`` (sin la marca de tiempo de vinculacion)."""
    out = {}
    with conn.cursor(row_factory=dict_row) as cur:
        for tabla in ("movimientos", "documentos_respaldo_movimientos"):
            cur.execute(f"SELECT * FROM {tabla} WHERE institucion_id=%s ORDER BY id", [inst])
            filas = []
            for r in cur.fetchall():
                d = dict(r)
                d.pop("fecha_vinculacion", None)  # CURRENT_TIMESTAMP de la transaccion
                if tabla == "documentos_respaldo_movimientos":
                    d.pop("id", None)  # la secuencia avanza en ambos lados (ROLLBACK no la retrocede)
                filas.append(json.dumps(d, sort_keys=True, default=str))
            out[tabla] = sorted(filas)
    return out


# ------------------------------------------------------------------------------------------ fixtures de servicio
def make_movimientos(service, audit_store, db_conn, **kwargs):
    from movimientos.service import MovimientosService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return MovimientosService(None, service, audit_store, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, **kwargs)


@pytest.fixture
def movimientos(service, repo, db_conn, audit_store):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    return make_movimientos(service, audit_store, db_conn)


@pytest.fixture
def http(service, movimientos):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from movimientos.routes import router as movimientos_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(movimientos_router)
    application.state.auth = service
    application.state.movimientos = movimientos
    return TestClient(application, base_url="http://localhost")


__all__ = ["certified_movimientos", "pagina_certificada", "state", "make_movimientos", "audit_rows", "FIXED_TODAY",
           "FIXED_NOW", "session_for"]
