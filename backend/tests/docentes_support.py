"""Soporte de los tests de Docentes.

- Reutiliza de ``periodos_support`` la conexion real que NUNCA confirma (``db_conn``), los SAVEPOINT, el inyector de
  scope certificado y la auditoria falsa para DENIED/FAILED/POST_OPERATION.
- ``certified_docentes``: funciones del entry certificado (AST, sin modificar reference_fix02, sin bytecode) ejecutadas
  sobre la base real con dos conexiones certificadas: ``get_conn()`` (inyector B12B) y ``_pg_raw_conn()`` (sin
  inyector).  Sus COMMIT son RELEASE SAVEPOINT dentro de la transaccion del test, que se revierte al terminar.
- Datos temporales: CUIL sinteticos ``27-9900xxxx-x`` / ``20-9900xxxx-x`` (no existen en deptit_next_dev; se
  verifica antes de usarlos).  Todo se revierte; las secuencias pueden avanzar (documentado).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from contextlib import nullcontext
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from psycopg.rows import dict_row

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from periodos_support import (  # noqa: E402,F401  (fixtures re-exportados)
    ENTRY, EXTRA_DEPARTMENTS, FIXED_TODAY, READONLY_QUERIES, CertifiedConnection, CertifiedCursor, FakeAuditStore,
    _FixedDate, _tree, audit_store, certified_injector, db_conn, entry_defs, savepoint, session_for, sql_constants,
)

FIXED_NOW = datetime(2026, 10, 26, 10, 30, 0)
TABLES_CUIL = ["docentes", "designaciones", "asignaciones_docentes_comision", "investigacion_docente",
               "extension_docente", "actividad_especial_docente", "movimientos", "disposiciones",
               "estado_consulta_designacion", "correcciones_historial_horas", "disposicion_docente_parametros",
               "disposicion_docente_designaciones", "prestamos_docentes", "horarios_asignacion_docente_comision"]


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW


# ------------------------------------------------------------------------------------------ conexiones certificadas
class DescCursor(CertifiedCursor):
    """``PgCursorCompat`` con ``description``/``close`` (lo que usa ``pandas.read_sql`` sobre una conexion DBAPI)."""

    description = None

    def execute(self, sql, params=None):
        super().execute(sql, params)
        self.description = self.cur.description

    def close(self):
        pass


class DescConnection(CertifiedConnection):
    def cursor(self):
        return DescCursor(self)


class RawConnection:
    """``_pg_raw_conn()`` certificado: cursor psycopg sin inyector; su COMMIT = RELEASE de un SAVEPOINT propio."""

    _n = 0

    def __init__(self, raw, commits, stack):
        RawConnection._n += 1
        self.raw = raw
        self.name = f"raw_cert_{RawConnection._n}"
        self.pending = 0
        self._commits, self._stack = commits, stack
        self.raw.execute(f"SAVEPOINT {self.name}")
        self.open = True

    def cursor(self):
        conn = self

        class _Cur:
            def __init__(self):
                self.cur = conn.raw.cursor()

            def execute(self, sql, params=None):
                from deptit_refactor.b12h.audit_actor import is_mutating
                if is_mutating(sql):
                    conn.pending += 1
                self.cur.execute(sql, list(params or []))

            def __getattr__(self, item):
                return getattr(self.cur, item)

        return _Cur()

    def commit(self):
        if self.pending:
            self._commits.append({"commit_seq": len(self._commits) + 1, "mutating_statements": self.pending,
                                  "committing_writer": self._stack[-1] if self._stack else None})
        self.pending = 0
        if self.open:
            self.raw.execute(f"RELEASE SAVEPOINT {self.name}")
            self.open = False

    def rollback(self):
        self.pending = 0
        if self.open:
            self.raw.execute(f"ROLLBACK TO SAVEPOINT {self.name}")
            self.raw.execute(f"RELEASE SAVEPOINT {self.name}")
            self.open = False

    def close(self):
        self.rollback()


class _StStub:
    """``streamlit`` minimo para las funciones certificadas (caches no-op, session_state vacio)."""

    session_state: dict = {}

    class cache_data:  # noqa: N801
        @staticmethod
        def clear():
            return None


# ------------------------------------------------------------------------------------------ carga de definiciones
def _top_assign(name: str) -> ast.Assign:
    for node in _tree(ENTRY).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == name:
            return node
    raise KeyError(name)


def exec_entry(picks: list[tuple[str, int]], namespace: dict, assigns: tuple[str, ...] = ()) -> dict:
    """Ejecuta definiciones certificadas (nombre, indice) SIN decoradores (caches de Streamlit / lru_cache)."""
    nodes = [_top_assign(a) for a in assigns]
    for name, index in picks:
        node = entry_defs(ENTRY, name)[index]
        node.decorator_list = []
        nodes.append(node)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ENTRY), "exec"), namespace)
    return namespace


def certified_docentes(raw_conn, institution_id: int, department_id: int) -> dict:
    """Namespace con los writers/lecturas certificados de Docentes sobre ``raw_conn`` y el scope indicado."""
    injector = certified_injector()
    commits: list[dict] = []
    stack: list[str] = []

    def get_conn():
        return DescConnection(raw_conn, injector, institution_id, department_id, commits, stack)

    def _pg_raw_conn():
        return RawConnection(raw_conn, commits, stack)

    def _pg_read_dataframe(sql, params=None):
        with raw_conn.cursor() as cur:
            cur.execute(sql, list(params or []))
            rows = cur.fetchall() if cur.description else []
            cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    def _row_dict(sql):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
        names = [d.name for d in cur.description] if cur.description else []
        conn.close()
        return None if row is None else dict(zip(names, row))

    abierto_sql = sql_constants(ENTRY, "get_periodo_abierto")[0]
    ultimo_sql = sql_constants(READONLY_QUERIES, "get_ultimo_periodo")[0]
    ns = {
        "USE_POSTGRESQL": True, "get_conn": get_conn, "_pg_raw_conn": _pg_raw_conn, "pd": pd, "re": re, "json": json,
        "date": _FixedDate, "datetime": _FixedDateTime, "BytesIO": BytesIO, "st": _StStub,
        "_pg_current_inst_id": lambda: institution_id, "_pg_current_dep_id": lambda: department_id,
        "_pg_read_dataframe": _pg_read_dataframe,
        "invalidar_cache_rendimiento_v191": lambda *_: None, "limpiar_cache_comisiones_operativas": lambda *_: None,
        "asegurar_esquema_prestamos_docentes_v174": lambda: None,  # DDL de arranque: la tabla ya existe
        "_departamento_contexto_prestamo_v174": lambda: department_id,
        "get_periodo_abierto": lambda: _row_dict(abierto_sql),
        "get_ultimo_periodo": lambda: _row_dict(ultimo_sql),
    }
    from deptit_refactor.catalogs.designaciones import ESTADOS_DOCENTE
    ns["ESTADOS_DOCENTE"] = ESTADOS_DOCENTE
    exec_entry([
        ("safe_date", 0), ("nombre_completo", 0), ("limpiar_texto_tabla", 0), ("limpiar_cuil", 0), ("_clave_cuil", 0),
        ("normalizar_clave", 0), ("add_column_if_not_exists", 0), ("registrar_movimiento", 0),
        ("get_docentes", 0), ("docente_existe", 0), ("guardar_docente", 0),
        ("_condicion_cuil_normalizado_sql", 0), ("_diagnosticar_referencias_docente_conn", 0),
        ("diagnosticar_referencias_docente", 0), ("eliminar_docente", 0),
        ("_nivel_posgrado_salarial_normalizado_v256", 0),
        ("_conn_identidad_v168", 0), ("_columnas_tabla_v168", 0), ("_tabla_existe_v168", 0),
        ("_where_cuil_raw_v168", 0), ("_fetch_rows_cuil_v168", 0), ("_es_vacio_v168", 0), ("_firma_fila_v168", 0),
        ("_delete_id_v168", 0), ("_update_id_cuil_v168", 0), ("_actualizar_cuil_directo_v168", 0),
        ("_merge_parametros_disposicion_v168", 0), ("_actualizar_variables_disposiciones_v168", 0),
        ("_migrar_referencias_cuil_conn_v168", 0), ("migrar_referencias_cuil_v168", 0),
        ("_docentes_cuil_institucion_v168", 0), ("_sincronizar_nombre_referencias_v168", 0),
        ("actualizar_docente", 1), ("get_cuiles_huerfanos_v168", 0),
        ("get_prestamos_docentes_periodo_v174", 0), ("prestamo_docente_activo_v174", 0),
        ("registrar_prestamo_docente_v174", 0), ("finalizar_prestamo_docente_v174", 0),
        ("get_docentes_otros_departamentos_para_prestamo", 0), ("get_docentes_mismo_cuil_otro_departamento", 0),
        ("_guardar_docente_local_desde_registro_existente", 0),
        ("leer_tabla_pegada", 0), ("normalizar_columna_generica", 0), ("normalizar_columnas_docentes_pegados", 0),
        ("separar_docente_en_apellido_nombres", 0), ("parsear_docentes_pegados", 0),
        ("detectar_docentes_duplicados_carga", 0), ("generar_excel_modelo_carga_rapida_docentes", 0),
    ], ns, assigns=("_TABLAS_CUIL_V168", "_CLAVES_DUPLICADO_CUIL_V168"))
    # B12A sobre actualizar_docente + normalizador (b12a/posgrado.py::install_posgrado_integrity, sin cambios).
    from deptit_refactor.b12a.posgrado import install_posgrado_integrity
    install_posgrado_integrity(ns)
    for name in ("guardar_docente", "actualizar_docente", "eliminar_docente", "registrar_movimiento",
                 "registrar_prestamo_docente_v174", "finalizar_prestamo_docente_v174", "migrar_referencias_cuil_v168"):
        def framed(*args, _fn=ns[name], _name=name, **kwargs):
            stack.append(_name)
            try:
                return _fn(*args, **kwargs)
            finally:
                stack.pop()
        ns[name] = framed
    ns["_commits"] = commits
    return ns


# ------------------------------------------------------------------------------------------ estado de la base
def free_cuil(conn, base: str) -> str:
    digits = re.sub(r"\D", "", base)
    for table in TABLES_CUIL:
        cols = [r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s",
                                           [table]).fetchall()]
        if "cuil" not in cols:
            continue
        n = conn.execute(f"SELECT count(*) FROM {table} WHERE regexp_replace(COALESCE(cuil,''),'[^0-9]','','g')=%s",
                         [digits]).fetchone()[0]
        assert n == 0, f"el CUIL sintetico {base} ya existe en {table}"
    return base


def state(conn, digits_list, exclude=("id",)) -> dict:
    """Filas (sin ``id`` ni marcas temporales) de las tablas con CUIL para los CUIL indicados (por digitos)."""
    out = {}
    for table in TABLES_CUIL:
        if table == "horarios_asignacion_docente_comision":
            continue
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"SELECT * FROM {table} WHERE regexp_replace(COALESCE(cuil,''),'[^0-9]','','g') = ANY(%s)",
                        [list(digits_list)])
            rows = [{k: v for k, v in r.items() if k not in exclude and k not in ("fecha_registro",)}
                    for r in cur.fetchall()]
        out[table] = sorted((json.dumps(r, sort_keys=True, default=str) for r in rows))
    return out


def audit_rows(conn) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM b12h_audit_log WHERE occurred_at >= transaction_timestamp() "
                    "ORDER BY occurred_at, correlation_id, event_seq")
        return list(cur.fetchall())


# ------------------------------------------------------------------------------------------ fixtures de servicio
def make_docentes(service, audit_store, db_conn, **kwargs):
    from docentes.service import DocentesService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return DocentesService(None, service, audit_store, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, **kwargs)


@pytest.fixture
def docentes(service, repo, db_conn, audit_store):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    return make_docentes(service, audit_store, db_conn)


@pytest.fixture
def http(service, docentes):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from docentes.routes import router as docentes_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(docentes_router)
    application.state.auth = service
    application.state.docentes = docentes
    return TestClient(application, base_url="http://localhost")


def nullctx():
    return nullcontext()
