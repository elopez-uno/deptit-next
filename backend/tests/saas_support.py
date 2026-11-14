"""Soporte de los tests de Administración SaaS.

- ``certified_saas``: namespace con el cierre transitivo de ``render_admin_saas`` (l. 3339; ruteo l. 59798) ejecutado
  DESDE ``reference_fix02`` en el orden del entry, sin decoradores de cache.  Como en el runtime certificado:
  ``get_auth_conn()`` = conexión ``auth`` SIN ámbito (``_pg_scope_*`` con ``kind == "auth"``), ``pandas.read_sql`` con
  placeholders ``?``; ``_pg_read_dataframe`` sin inyector; la caché v199 de ``get_uso_instituciones`` se reemplaza por
  la función original (mismo resultado).  Nada de reference_fix02 se modifica ni se compila a bytecode.  Ningún writer
  certificado se ejecuta (los botones del grabador devuelven False).
- ``render``: ejecuta el render con un Streamlit que GRABA cada llamada (labels, tablas reales, captions).
- Fixtures: ``AuthService`` real sobre la transacción del test (revalidación B12G contra la base), ``SaasService`` con
  SAVEPOINT por operación, sesiones de usuarios reales (sin contraseña) y datos SINTÉTICOS ``zznext`` creados dentro de
  la transacción (ROLLBACK al final).  Nunca se imprimen emails ni nombres reales.
"""

from __future__ import annotations

import ast
import collections
import copy
import functools
import hashlib
import inspect
import json
import math
import os
import re
import secrets
import threading
import time
from datetime import timedelta
from io import BytesIO

import pandas as pd
import psycopg
import pytest

from comisiones_support import FIXED_NOW, _ConnAislada, _FixedDateTime, _Session, _instalar_execute_values  # noqa: F401
from conftest import Clock
from designaciones_support import _Frames
from materias_support import planes_injector
from periodos_support import (  # noqa: F401  (fixtures re-exportados)
    ENTRY, FIXED_TODAY, FakeAuditStore, _FixedDate, _tree, audit_store, db_conn, savepoint,
)

RUTEO = 59798
START = {"render_admin_saas", "_convertir_tabla_a_excel_bytes"}


@functools.lru_cache(maxsize=1)
def _closure():
    tree = copy.deepcopy(_tree(ENTRY))
    defs, aliases = collections.defaultdict(list), {}
    for node in tree.body:
        if node.lineno >= RUTEO:
            continue
        if isinstance(node, ast.FunctionDef):
            defs[node.name].append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name):
            aliases.setdefault(node.targets[0].id, []).append(node)
    seen, queue = set(), list(START)
    while queue:
        n = queue.pop()
        if n in seen or n == "st":
            continue
        seen.add(n)
        for d in defs.get(n, []):
            queue.extend({x.id for x in ast.walk(d) if isinstance(x, ast.Name)} - seen)
        for a in aliases.get(n, []):
            queue.append(a.value.id)
    picked = [n for n in tree.body if n.lineno < RUTEO and (
        (isinstance(n, ast.FunctionDef) and n.name in seen) or
        (isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
         and isinstance(n.value, ast.Name) and n.targets[0].id in seen))]
    for n in picked:
        if isinstance(n, ast.FunctionDef):
            n.decorator_list = []
    lits = {}
    for node in tree.body:
        if node.lineno >= RUTEO:
            break
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in seen and node.targets[0].id not in lits:
            try:
                lits[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    code = compile(ast.Module(body=list(picked), type_ignores=[]), str(ENTRY), "exec")
    return code, frozenset(seen), lits


def _original(nombre: str, indice: int = 0):
    """Definición ``indice`` de ``nombre`` en el entry (p. ej. ``get_uso_instituciones`` original l. 3204)."""
    nodes = [n for n in _tree(ENTRY).body if isinstance(n, ast.FunctionDef) and n.name == nombre]
    node = copy.deepcopy(nodes[indice])
    node.decorator_list = []
    return compile(ast.Module(body=[node], type_ignores=[]), str(ENTRY), "exec")


# ------------------------------------------------------------------------------------------ st grabador
class _Ctx:
    def __init__(self, st, kind, label=None):
        self.st, self.kind, self.label = st, kind, label

    def __enter__(self):
        if self.kind in ("expander", "tab"):
            self.st.ev.append((self.kind, self.label))
        return self

    def __exit__(self, *a):
        if self.kind in ("expander", "tab"):
            self.st.ev.append((f"/{self.kind}",))
        return False


class Grabador:
    """Streamlit que graba la página (sin clics: ``button`` devuelve False).  ``selects``: valor por ``key``."""

    def __init__(self, session, ns_ref, selects=None):
        self.session_state = session
        self.ev: list[tuple] = []
        self.frames: list[pd.DataFrame] = []
        self.selects, self._ns = selects or {}, ns_ref

    def title(self, t, *a, **k): self.ev.append(("title", t))
    def subheader(self, t, *a, **k): self.ev.append(("subheader", t))
    def markdown(self, t, *a, **k): self.ev.append(("markdown", t))
    def caption(self, t, *a, **k): self.ev.append(("caption", t))
    def info(self, t, *a, **k): self.ev.append(("info", t))
    def warning(self, t, *a, **k): self.ev.append(("warning", t))
    def error(self, t, *a, **k): self.ev.append(("error", t))
    def success(self, t, *a, **k): self.ev.append(("success", t))
    def code(self, t, *a, **k): self.ev.append(("code", t))
    def metric(self, label, value, *a, **k): self.ev.append(("metric", label, value))
    def rerun(self, *a, **k): raise AssertionError("rerun sin clic")

    def dataframe(self, data=None, *a, **k):
        self.frames.append(data.copy())
        self.ev.append(("dataframe", len(self.frames) - 1))

    def tabs(self, labels):
        self.ev.append(("tabs", list(labels)))
        return [_Ctx(self, "tab", lab) for lab in labels]

    def columns(self, spec, *a, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_Ctx(self, "col") for _ in range(n)]

    def expander(self, label, expanded=False, *a, **k):
        return _Ctx(self, "expander", label)

    def selectbox(self, label, options, index=0, key=None, **k):
        opts = list(options)
        val = self.selects.get(key, opts[index] if opts else None)
        self.ev.append(("selectbox", label, opts, key, val))
        return val

    def text_input(self, label, value="", key=None, **k):
        self.ev.append(("text_input", label, key, value, k.get("type")))
        return value

    def text_area(self, label, value="", key=None, **k):
        self.ev.append(("text_area", label, key, value))
        return value

    def number_input(self, label, min_value=None, max_value=None, value=None, step=None, key=None, **k):
        self.ev.append(("number_input", label, key, min_value, max_value, value))
        return value

    def date_input(self, label, value=None, key=None, **k):
        self.ev.append(("date_input", label, key, value))
        return value

    def checkbox(self, label, value=False, key=None, **k):
        self.ev.append(("checkbox", label, key, value))
        return value

    def button(self, label, key=None, disabled=False, **k):
        self.ev.append(("button", label, key, bool(disabled)))
        return False

    def __getattr__(self, name):
        def _otro(*a, **k):
            self.ev.append((f"st.{name}",))
        return _otro


class _ConnAuth(_ConnAislada):
    """``PgConnectionCompat`` (l. 1247) también expone ``execute`` (lo usa ``eliminar_departamento_auth`` l. 3065)."""

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur


class _SinDisco:
    """Trampa: el render certificado en modo PostgreSQL no debe tocar archivos al LEER (sin clics)."""

    def __getattr__(self, name):
        raise AssertionError(f"operación de disco/SQLite inesperada: {name}")


def certified_saas(raw_conn, user: dict, session: _Session) -> dict:
    """Namespace certificado de Administración SaaS para ``user``/``session`` sobre ``raw_conn`` (solo lecturas)."""
    injector = planes_injector()
    frames = _Frames()

    def _pg_read_dataframe(sql, params=None):
        with raw_conn.transaction():
            cur = psycopg.ClientCursor(raw_conn)
            cur.execute(sql, list(params or []))
            rows = cur.fetchall() if cur.description else []
            cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    def sin_inst():
        raise AssertionError("_pg_current_inst_id no debería alcanzarse en SaaS (slugs coherentes)")

    _instalar_execute_values()
    code, names, lits = _closure()
    noop = lambda *a, **k: None  # noqa: E731
    from deptit_refactor.security.legacy_write_actions import SYSTEM_WRITERS
    ns = {"__builtins__": __builtins__, "USE_POSTGRESQL": True, "DATABASE_URL": "postgresql://test", "DB_PATH": "",
          "TENANT_DATA_DIR": r"C:\deptit_test\datos_instituciones", "APP_BASE_DIR": r"C:\deptit_test",
          "get_auth_conn": lambda: _ConnAuth(raw_conn, frames, {"kind": "auth"}, injector),
          "_pg_raw_conn": lambda: _ConnAislada(raw_conn, frames), "_pg_read_dataframe": _pg_read_dataframe,
          "_pg_current_inst_id": sin_inst, "_pg_current_dep_id": lambda: None,
          "current_role": lambda: user.get("rol", ""), "current_user": lambda: user,
          "pd": pd, "re": re, "json": json, "math": math, "hashlib": hashlib, "time": time, "functools": functools,
          "inspect": inspect, "date": _FixedDate, "datetime": _FixedDateTime, "timedelta": timedelta,
          "BytesIO": BytesIO, "st": None, "threading": threading, "os": os, "shutil": _SinDisco(),
          "secrets": secrets, "sqlite3": _SinDisco(),
          "_copiar_resultado_cache_v191": lambda x: x.copy() if hasattr(x, "copy") else x,
          "_registro_versiones_v199": lambda: {"lock": threading.Lock(), "auth": 0, "epoch": 0},
          "_b12f_arranque_omitido": noop}
    for k in [n for n in names if n.startswith("asegurar_esquema")]:
        ns[k] = noop
    for w, (cat_, _d) in SYSTEM_WRITERS.items():
        ns[w] = noop if cat_ == "schema" else (lambda *a, **k: None)
    for k, v in lits.items():
        ns.setdefault(k, v)
    infra = {k: v for k, v in ns.items() if callable(v) and k not in (
        "pd", "re", "json", "math", "hashlib", "time", "functools", "inspect", "date", "datetime", "timedelta",
        "BytesIO", "threading", "os", "shutil", "secrets", "sqlite3")}
    exec(code, ns)
    ns.update(infra)
    # La v199 (l. 46084) solo cachea la original (l. 3204): el diferencial usa la original sin caché.
    exec(_original("get_uso_instituciones", 0), ns)
    ns["_session"] = session
    return ns


def render(raw_conn, user: dict, session: dict | None = None, selects=None) -> Grabador:
    sess = _Session(**(session or {}))
    ns = certified_saas(raw_conn, user, sess)
    st = Grabador(sess, ns, selects)
    ns["st"] = st
    ns["render_admin_saas"]()
    st.ns = ns
    return st


SUPER = {"id": 999_001, "email": "super@test.local", "rol": "superadmin", "institucion_id": None,
         "departamento_id": None}
COORD = {"id": 999_002, "email": "coord@test.local", "rol": "coordinador_institucional", "institucion_id": 1,
         "departamento_id": None}


# ------------------------------------------------------------------------------------------ Auth real sobre la base
class _PoolDB:
    """``ConnectionPool`` mínimo para ``AuthRepository``: cada operación en un SAVEPOINT de la conexión del test."""

    def __init__(self, conn):
        self._conn = conn

    def connection(self, timeout=None):
        return savepoint(self._conn)


@pytest.fixture
def auth_db(db_conn):
    from auth.repository import AuthRepository
    from auth.service import AuthService

    return AuthService(AuthRepository(_PoolDB(db_conn)), clock=Clock())


def sesion(auth, user_id: int, **scope):
    """Sesión real (misma ruta que un login exitoso) de un usuario de la base; devuelve (record, token)."""
    from auth import core
    from auth.service import LoginResult

    row = auth.repo.user_by_id(user_id)[0]
    outcome = core.commercial_outcome(row)
    token = auth.start_session(LoginResult(core.derive_session_user(row, outcome),
                                           core.new_metadata(row, outcome, now=auth.clock()), ""))
    auth.store.get(token).scope.update(scope)
    return auth.validate(token), token


def ids_por_rol(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT rol, MIN(id) FROM app_usuarios WHERE estado = 'Activo' GROUP BY rol")
        return dict(cur.fetchall())


def make_saas(auth, audit, db_conn, **kwargs):
    from saas.service import SaasService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return SaasService(None, auth, audit, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, **kwargs)


@pytest.fixture
def saas(auth_db, audit_store, db_conn):
    return make_saas(auth_db, audit_store, db_conn)


@pytest.fixture
def superadmin(auth_db, db_conn):
    return sesion(auth_db, ids_por_rol(db_conn)["superadmin"])[0]


@pytest.fixture
def http(auth_db, saas):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from saas.routes import router as saas_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(saas_router)
    application.state.auth = auth_db
    application.state.saas = saas
    return TestClient(application, base_url="http://localhost")


# ------------------------------------------------------------------------------------------ datos sintéticos
def scalar(conn, query, params=None):
    with conn.cursor() as cur:
        cur.execute(query, params or [])
        row = cur.fetchone()
        return None if row is None else row[0]


def nueva_institucion(conn, nombre="ZZNEXT Instituto Vacío", max_usuarios=5, estado="Activa") -> int:
    from investigacion.rules import _slugify
    with savepoint(conn):
        return int(scalar(conn, "INSERT INTO instituciones (nombre, slug, max_usuarios, estado, plan, estado_pago, "
                                "suscripcion) VALUES (%s, %s, %s, %s, 'Institucional', 'Activo', 'Activa') RETURNING id",
                          [nombre, _slugify(nombre), max_usuarios, estado]))


def nuevo_departamento(conn, institucion_id: int, nombre="ZZNEXT Departamento", estado="Activo") -> int:
    from investigacion.rules import _slugify
    with savepoint(conn):
        return int(scalar(conn, "INSERT INTO departamentos (institucion_id, nombre, slug, estado) VALUES "
                                "(%s, %s, %s, %s) RETURNING id", [institucion_id, nombre, _slugify(nombre), estado]))


def nuevo_usuario(conn, email: str, rol="usuario_departamento", institucion_id=None, departamento_id=None,
                  estado="Activo") -> int:
    from auth import core
    salt = "a" * 32
    with savepoint(conn):
        return int(scalar(conn, "INSERT INTO app_usuarios (institucion_id, departamento_id, nombre, email, rol, salt, "
                                "password_hash, estado, fecha_alta) VALUES (%s, %s, 'ZZNEXT', %s, %s, %s, %s, %s, "
                                "'2026-10-30') RETURNING id",
                          [institucion_id, departamento_id, email, rol, salt,
                           core.hash_password("zznext-clave-larga-1", salt), estado]))


def audit_saas(conn) -> list[dict]:
    from psycopg.rows import dict_row
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM b12h_audit_log WHERE occurred_at >= transaction_timestamp() AND action LIKE 'saas.%%' "
                    "ORDER BY occurred_at, event_seq")
        return list(cur.fetchall())
