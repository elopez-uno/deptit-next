"""Soporte de los tests de Periodos.

- ``db_conn``: UNA conexion real a deptit_next_dev (guarda pre y post conexion) que NUNCA confirma: cada operacion
  corre dentro de un SAVEPOINT y la transaccion completa se revierte al terminar el test (FASE G: ROLLBACK).
- ``FakeAuditStore``: los eventos DENIED/FAILED/POST_OPERATION (transaccion propia en produccion) quedan en memoria.
  Los SUCCESS van a ``b12h_audit_log`` dentro de la transaccion del test y se revierten con ella.
- Codigo certificado: funciones del entry y SQL extraidos por AST de reference_fix02 (solo lectura, sin bytecode).
"""

from __future__ import annotations

import ast
import re
import sys
from contextlib import contextmanager, nullcontext
from datetime import date
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

sys.dont_write_bytecode = True  # nunca escribir __pycache__ dentro de reference_fix02
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402

REFERENCE = Path(r"C:\DEPTIT_NEXT\reference_fix02")
ENTRY = REFERENCE / "app_postgresql_refactor_b13fix02_uat_fixes.py"
READONLY_QUERIES = REFERENCE / "deptit_refactor" / "extracted_batch03" / "readonly_queries.py"
if str(REFERENCE) not in sys.path:
    sys.path.append(str(REFERENCE))

FIXED_TODAY = date(2026, 10, 26)

_TREES: dict[Path, ast.Module] = {}


def _tree(path: Path) -> ast.Module:
    if path not in _TREES:
        _TREES[path] = ast.parse(path.read_text(encoding="utf-8"))
    return _TREES[path]


def entry_defs(path: Path, name: str) -> list[ast.FunctionDef]:
    """Todas las definiciones de nivel superior de ``name``, en orden de aparicion."""
    return [n for n in _tree(path).body if isinstance(n, ast.FunctionDef) and n.name == name]


def sql_constants(path: Path, name: str, index: int = 0) -> list[str]:
    """SQL literales pasados a ``execute``/``read_sql`` dentro de la definicion ``index`` de ``name``."""
    node = entry_defs(path, name)[index]
    out = []
    for call in sorted(ast.walk(node), key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0))):
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) \
                and call.func.attr in ("execute", "read_sql") and call.args \
                and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
            out.append(call.args[0].value)
    return out


def exec_defs(path: Path, picks: list[tuple[str, int]], namespace: dict) -> dict:
    """Ejecuta definiciones certificadas elegidas (nombre, indice de definicion) en ``namespace``."""
    nodes = []
    for name, index in picks:
        node = entry_defs(path, name)[index]
        node.decorator_list = [d for d in node.decorator_list if "lru_cache" not in ast.unparse(d)]
        nodes.append(node)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


# ----------------------------------------------------------------------------------- inyector certificado
def certified_injector() -> dict:
    """Inyector de scope efectivo del entry: v193 para SELECT (sin cache), original para INSERT/UPDATE/DELETE."""
    import functools

    ns = {"re": re, "functools": functools, "USE_POSTGRESQL": True}
    exec(compile("\n".join(
        f"{name} = {repr(value)}" for name, value in _table_sets().items()), "<sets>", "exec"), ns)
    exec_defs(ENTRY, [("_pg_quote_literal_text", 0), ("_pg_split_sql_args", 0), ("_pg_convert_group_concat", 0), ("_pg_convert_sql", 0), ("_pg_top_level_positions", 0),
                      ("_pg_insert_conditions", 0), ("_pg_aliases_select_v193", 0),
                      ("_pg_scope_select_template_v193", 0), ("_pg_scope_insert", 0),
                      ("_pg_scope_update_delete", 0)], ns)
    ns["_pg_current_inst_id"] = lambda: (_ for _ in ()).throw(AssertionError("scope implicito"))
    ns["_pg_current_dep_id"] = ns["_pg_current_inst_id"]
    return ns


def _table_sets() -> dict:
    out = {}
    for node in _tree(ENTRY).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in ("PG_INSTITUTION_TABLES", "PG_DEPARTMENT_TABLES") \
                and node.targets[0].id not in out:
            out[node.targets[0].id] = ast.literal_eval(node.value)
    out["PG_ALL_SCOPED_TABLES"] = out["PG_INSTITUTION_TABLES"] | out["PG_DEPARTMENT_TABLES"]
    return out


class CertifiedCursor:
    """``PgCursorCompat`` minimo: aplica ``_pg_prepare_sql`` certificado con el scope tenant explicito."""

    def __init__(self, conn: "CertifiedConnection"):
        self.conn = conn
        self.cur = conn.raw.cursor()
        self.rowcount = -1
        self.lastrowid = None
        self._rows: list = []

    def execute(self, sql, params=None):
        inj, scope = self.conn.injector, self.conn.scope
        head = str(sql).lstrip().upper()
        if head.startswith("SELECT") or head.startswith("WITH"):
            q, extra = inj["_pg_scope_select_template_v193"](str(sql), "tenant", scope["institucion_id"],
                                                             scope["departamento_id"])
            q, p = q, list(params or []) + list(extra)
        elif head.startswith("INSERT"):
            q, p = inj["_pg_scope_insert"](sql, params, scope)
        elif head.startswith("UPDATE") or head.startswith("DELETE"):
            q, p = inj["_pg_scope_update_delete"](sql, params, scope)
        else:
            q, p = inj["_pg_convert_sql"](sql), list(params or [])
        self.conn.statements.append(q)
        self.conn.note(sql)
        self.conn.begin()
        self.cur.execute(q, p)
        self.rowcount = self.cur.rowcount
        self._rows = self.cur.fetchall() if self.cur.description else []
        if head.startswith("INSERT") and self._rows:
            self.lastrowid = self._rows[0][0]

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        rows, self._rows = self._rows, []
        return rows


_SAVEPOINTS = __import__("itertools").count(1)


class CertifiedConnection:
    """``get_conn()`` certificado sobre la conexion del test: commit/close no confirman (unidad del test).

    Reproduce el acoplamiento B12H (``AuditedConnectionMixin``): cada COMMIT con sentencias mutantes pendientes
    (``audit_actor.is_mutating`` certificado) registra (commit_seq, mutating_statements, committing_writer)."""

    def __init__(self, raw, injector, institution_id, department_id, commits, stack):
        self.raw, self.injector = raw, injector
        self.scope = {"kind": "tenant", "institucion_id": int(institution_id), "departamento_id": int(department_id)}
        self.statements: list[str] = []
        self.pending = 0
        self._commits, self._stack = commits, stack
        self._savepoint = None

    def begin(self):
        """La transaccion propia de esta conexion del pool = un SAVEPOINT dentro de la transaccion del test."""
        if self._savepoint is None:
            self._savepoint = f"certificado_{next(_SAVEPOINTS)}"
            self.raw.execute(f"SAVEPOINT {self._savepoint}")

    def _end(self, commit: bool):
        if self._savepoint is not None:
            if not commit:
                self.raw.execute(f"ROLLBACK TO SAVEPOINT {self._savepoint}")
            self.raw.execute(f"RELEASE SAVEPOINT {self._savepoint}")
            self._savepoint = None

    def note(self, sql):
        from deptit_refactor.b12h.audit_actor import is_mutating

        if is_mutating(sql):
            self.pending += 1

    def cursor(self):
        return CertifiedCursor(self)

    def commit(self):
        if self.pending:
            self._commits.append({"commit_seq": len(self._commits) + 1, "mutating_statements": self.pending,
                                  "committing_writer": self._stack[-1]})
        self.pending = 0
        self._end(commit=True)

    def rollback(self):
        self.pending = 0
        self._end(commit=False)

    def close(self):
        # _pg_return_raw_connection certificado: la conexion vuelve al pool con ROLLBACK.
        self.rollback()


class _FixedDate(date):
    @classmethod
    def today(cls):
        return FIXED_TODAY


def certified_period_writers(raw_conn, institution_id: int, department_id: int) -> dict:
    """``abrir_periodo_emergencia``, ``volver_periodo_actual`` y ``registrar_movimiento`` del entry, sin cambios,
    sobre ``raw_conn`` con el scope tenant indicado."""
    injector = certified_injector()
    conns: list[CertifiedConnection] = []
    commits: list[dict] = []
    stack: list[str] = []

    def get_conn():
        conn = CertifiedConnection(raw_conn, injector, institution_id, department_id, commits, stack)
        conns.append(conn)
        return conn

    def _row_dict(sql):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
        names = [d.name for d in cur.cur.description]
        conn.close()
        return None if row is None else dict(zip(names, row))

    abierto_sql = sql_constants(ENTRY, "get_periodo_abierto")[0]
    ultimo_sql = sql_constants(READONLY_QUERIES, "get_ultimo_periodo")[0]
    ns = {
        "USE_POSTGRESQL": True, "get_conn": get_conn, "date": _FixedDate,
        "_pg_current_inst_id": lambda: institution_id, "_pg_current_dep_id": lambda: department_id,
        "safe_date": lambda value, default=None: default, "invalidar_cache_rendimiento_v191": lambda *_: None,
        "get_periodo_abierto": lambda: _row_dict(abierto_sql),
        "get_ultimo_periodo": lambda: _row_dict(ultimo_sql),
    }
    exec_defs(ENTRY, [("add_column_if_not_exists", 0), ("registrar_movimiento", 0),
                      ("abrir_periodo_emergencia", 0), ("volver_periodo_actual", 0)], ns)
    # Marco "business" de la frontera B10 (enforcement._Frame): el writer en curso es el ``committing_writer``.
    for name in ("registrar_movimiento", "abrir_periodo_emergencia", "volver_periodo_actual"):
        def framed(*args, _fn=ns[name], _name=name, **kwargs):
            stack.append(_name)
            try:
                return _fn(*args, **kwargs)
            finally:
                stack.pop()
        ns[name] = framed
    ns["_connections"], ns["_commits"] = conns, commits
    return ns


# ----------------------------------------------------------------------------------- base real con ROLLBACK
@pytest.fixture
def db_conn():
    settings = db.load_settings()
    db.check_config(settings)
    conn = psycopg.connect(settings["database_url"], connect_timeout=5, application_name="deptit_next_tests")
    try:
        db.verify_identity(conn)  # abre la transaccion del test (implicita, nunca se confirma)
        yield conn
    finally:
        conn.rollback()
        conn.close()


@contextmanager
def savepoint(conn):
    """Unidad de trabajo de los tests: SAVEPOINT (sale sin error -> RELEASE; excepcion -> ROLLBACK TO)."""
    with conn.transaction():
        yield conn


def snapshot(conn, institution_id: int, department_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones FROM periodos "
                    "WHERE institucion_id = %s AND departamento_id = %s ORDER BY id",
                    [institution_id, department_id])
        periods = list(cur.fetchall())
        cur.execute("SELECT count(*) AS n, coalesce(max(id), 0) AS max_id FROM movimientos")
        mov = cur.fetchone()
    return {"periodos": periods, "movimientos": int(mov["n"]), "max_mov_id": int(mov["max_id"])}


def movements_after(conn, max_id: int) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT periodo_id, fecha, tipo_movimiento, cuil, nombre, detalle, observaciones, "
                    "horas_variacion, institucion_id, departamento_id FROM movimientos WHERE id > %s ORDER BY id",
                    [max_id])
        return list(cur.fetchall())


def audit_after(conn, correlation_ids=None) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM b12h_audit_log WHERE occurred_at >= transaction_timestamp() "
                    "ORDER BY occurred_at, event_seq")
        rows = list(cur.fetchall())
    return [r for r in rows if correlation_ids is None or str(r["correlation_id"]) in correlation_ids]


class FakeAuditStore:
    def __init__(self):
        self.events = []
        self.fail = False

    def append_separate(self, event):
        if self.fail:
            raise ConnectionError("audit down")
        self.events.append(event.validate())


# ----------------------------------------------------------------------------------- fixtures de servicio
# Departamentos reales de la institucion 1 que el FakeRepo de auth no trae (ids/instituciones de deptit_next_dev).
EXTRA_DEPARTMENTS = [
    {"id": 3, "institucion_id": 1, "nombre": "Departamento de Educación", "estado": "Activo"},
    {"id": 9, "institucion_id": 1, "nombre": "Departamento de Ciencias Exactas y Naturales", "estado": "Activo"},
    {"id": 11, "institucion_id": 1, "nombre": "Posgrado", "estado": "Activo"},
]


@pytest.fixture
def audit_store():
    return FakeAuditStore()


@pytest.fixture
def lock_conn():
    """Conexion dedicada al lock de SESION B12I (como el certificado).  Solo pg_try_advisory_lock/unlock."""
    settings = db.load_settings()
    db.check_config(settings)
    conn = psycopg.connect(settings["database_url"], autocommit=True, connect_timeout=5,
                           application_name="deptit_next_tests_lock")
    try:
        db.verify_identity(conn)
        yield conn
    finally:
        conn.close()


def make_service(service, audit_store, db_conn, lock_conn, **kwargs):
    from periodos.service import PeriodosService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return PeriodosService(None, service, audit_store, today=lambda: FIXED_TODAY,
                           lock_connection=lambda: nullcontext(lock_conn), **kwargs)


@pytest.fixture
def periodos(service, repo, db_conn, lock_conn, audit_store):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    return make_service(service, audit_store, db_conn, lock_conn)


def session_for(service, repo, user_id: int, **scope):
    """Sesion real del AuthService (misma ruta que un login exitoso) para un usuario del FakeRepo."""
    from auth import core
    from auth.service import LoginResult

    row = repo.user_by_id(user_id)[0]
    outcome = core.commercial_outcome(row)
    result = LoginResult(core.derive_session_user(row, outcome), core.new_metadata(row, outcome, now=service.clock()),
                         "")
    token = service.start_session(result)
    service.store.get(token).scope.update(scope)
    return service.validate(token), token


@pytest.fixture
def http(service, periodos):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from periodos.routes import router as periodos_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(periodos_router)
    application.state.auth = service
    application.state.periodos = periodos
    return TestClient(application, base_url="http://localhost")
