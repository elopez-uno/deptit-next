"""Entorno de ESCRITURA del motor certificado de Periodos (E4-10..E4-12) para UNA operacion.

Equivalencia con el runtime certificado B13-FIX02 (B12C ``crear_periodo_atomico``):
- Toda la operacion corre sobre la conexion de UNA transaccion NEXT (la del pool, o el SAVEPOINT de los tests).  La
  unidad B12C literal (``motor/ref/b12c/periodo_atomico.py``: ``TransactionUnit``) la recibe como su "conexion
  fisica": ``commit()`` de la unidad solo la marca lista (el COMMIT real lo hace la operacion NEXT despues de insertar
  su evento B12H en esa misma transaccion, D-E4-06); ``rollback()`` no hace nada (la excepcion revierte la transaccion
  NEXT completa).
- ``_pg_raw_conn`` = ``raw_connection_router`` literal de B12C: dentro de la unidad, un manejador NO propietario
  (``commit``/``close`` suprimidos, ``rollback`` envenena, todo error SQL envenena).  Fuera de la unidad no hay
  conexion (fail closed).
- ``get_conn()`` = ``PgConnectionCompat`` certificado: el SQL pasa por el inyector B12B/B12J literal
  (``analisis/motor/inyector.py``) con el ambito de la SESION, parametros enlazados del lado cliente (psycopg2).
- Tareas de sistema ``schema`` (DDL de arranque) no hacen nada; las de reconciliacion corren porque siempre estan
  DENTRO del writer de negocio de Periodos (compuerta B12F).  Invalidaciones de cache: no-op (NEXT no tiene esas
  caches).  Pilotos de lectura v280/v282: ``off``.
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
import re
import time
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd
import psycopg

from analisis.motor.entorno import _St, _inyector
from analisis.motor.ambito import proteger_or, proteger_subconsultas  # Etapa 5: hardening central del ambito B12B

from .motor import metadata
from .motor.ref.b12c import periodo_atomico as B12C

_DIR = Path(__file__).resolve().parent / "motor"


@functools.lru_cache(maxsize=1)
def _codigo():
    ruta = _DIR / "complemento.py"
    return compile(ruta.read_text(encoding="utf-8"), str(ruta), "exec")


class _RawCursor:
    """Cursor psycopg con enlace del lado cliente (psycopg2) sobre la conexion de la transaccion."""

    def __init__(self, conn: psycopg.Connection):
        self.cur = psycopg.ClientCursor(conn)
        self.rowcount = -1
        self.description = None
        self._rows: list = []

    def execute(self, sql, params=None):
        self.cur.execute(sql, list(params) if params is not None else None)
        self.rowcount = self.cur.rowcount
        self.description = self.cur.description
        self._rows = self.cur.fetchall() if self.cur.description else []

    def executemany(self, sql, seq):
        for params in seq:
            self.execute(sql, params)

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        rows, self._rows = self._rows, []
        return rows

    def fetchmany(self, size=None):
        n = len(self._rows) if size is None else int(size)
        rows, self._rows = self._rows[:n], self._rows[n:]
        return rows

    def close(self):
        pass

    def __iter__(self):
        return iter(self.fetchall())


class RawTx:
    """"Conexion fisica" de la unidad B12C = la transaccion NEXT.  El COMMIT real lo decide la operacion."""

    def __init__(self, conn: psycopg.Connection):
        self.conn = conn
        self.listo = False

    def cursor(self, *a, **k):
        return _RawCursor(self.conn)

    def commit(self):
        self.listo = True

    def rollback(self):
        self.listo = False

    def close(self, *a, **k):
        pass


class _TenantCursor:
    """``PgCursorCompat`` certificado (entry l. 1192): inyector B12B sobre el cursor de la conexion de la unidad."""

    def __init__(self, conn: "_TenantConn"):
        self.conn = conn
        self.cur = conn.raw.cursor()
        self.rowcount = -1
        self.lastrowid = None
        self.description = None

    def execute(self, sql, params=None):
        texto = str(sql or "")
        if texto.strip().upper().startswith("PRAGMA"):
            self.description, self.rowcount = [], 0
            return self
        if "sqlite_master" in texto.lower():
            table = (params or [None])[0]
            self.cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND "
                             "table_name=%s LIMIT 1", [table])
        else:
            q, p = self.conn.preparar(texto, params)
            self.cur.execute(q, p)
        self.rowcount = self.cur.rowcount
        self.description = self.cur.description
        self.lastrowid = None
        if texto.lstrip().upper().startswith("INSERT") and self.cur.description:
            row = self.cur.fetchone()
            if row:
                self.lastrowid = row[0]
        return self

    def fetchone(self):
        return self.cur.fetchone()

    def fetchall(self):
        return self.cur.fetchall()

    def close(self):
        pass

    def __iter__(self):
        return iter(self.fetchall())


class _TenantConn:
    """``PgConnectionCompat`` certificado (entry l. 1247) sobre ``_pg_raw_conn()`` (el router de la unidad)."""

    def __init__(self, raw, ambito: dict):
        self.raw, self.ambito = raw, ambito

    def preparar(self, sql: str, params):
        inj, head = _inyector(), sql.lstrip().upper()
        if not head.startswith("INSERT"):  # Etapa 5 / Tanda A: OR de nivel superior + subconsultas con ambito
            sql = proteger_subconsultas(proteger_or(sql), self.ambito, inj["PG_INSTITUTION_TABLES"],
                                        inj["PG_DEPARTMENT_TABLES"])
        if head.startswith("SELECT") or head.startswith("WITH"):
            return inj["_pg_scope_select"](sql, params, self.ambito)
        if head.startswith("INSERT"):
            return inj["_pg_scope_insert"](sql, params, self.ambito)
        if head.startswith("UPDATE") or head.startswith("DELETE"):
            return inj["_pg_scope_update_delete"](sql, params, self.ambito)
        return inj["_pg_convert_sql"](sql), list(params or [])

    def cursor(self):
        return _TenantCursor(self)

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.rollback()
        self.close()
        return False


def _sin_unidad():
    raise B12C.TransactionAborted("Operación de Períodos fuera de su unidad de trabajo: no hay conexión.")


def construir(institucion_id: int, departamento_id: int, *, usuario: Optional[dict] = None,
              hoy: Callable[[], date] = date.today, ahora: Callable[[], datetime] = datetime.now) -> dict:
    """Namespace del motor para UNA operacion.  Las conexiones solo existen dentro de una ``TransactionUnit``."""
    inst, dep = int(institucion_id), int(departamento_id)
    ambito = {"kind": "tenant", "institucion_id": inst, "departamento_id": dep}
    st = _St()
    noop = lambda *a, **k: None  # noqa: E731

    class _Date(date):
        @classmethod
        def today(cls):
            return hoy()

    class _DateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return ahora()

        @classmethod
        def today(cls):
            return ahora()

    usuario = dict(usuario or {})
    ns: dict[str, Any] = {}
    raw_router = B12C.raw_connection_router(_sin_unidad)

    def _pg_read_dataframe(sql, params=None):
        cur = raw_router().cursor()
        cur.execute(sql, list(params or []))
        rows = cur.fetchall() if cur.description else []
        cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    ns.update({
        "__builtins__": __builtins__, "__name__": "integraciones.ciclo_periodos.motor.complemento",
        "USE_POSTGRESQL": True, "DATABASE_URL": "postgresql://deptit_next", "DB_PATH": "",
        "_pg_raw_conn": raw_router, "get_conn": lambda: _TenantConn(ns["_pg_raw_conn"](), ambito),
        "get_planes_conn": lambda: _TenantConn(ns["_pg_raw_conn"](), {"kind": "planes", "institucion_id": inst}),
        "_pg_read_dataframe": _pg_read_dataframe,
        "_pg_current_inst_id": lambda: inst, "_pg_current_dep_id": lambda: dep,
        "_institucion_id_operativa": lambda: inst, "estado_scope_b12b": lambda: None,
        "current_role": lambda: usuario.get("rol"), "current_user": lambda: usuario,
        "pd": pd, "re": re, "json": json, "math": math, "hashlib": hashlib, "time": time, "functools": functools,
        "date": _Date, "datetime": _DateTime, "timedelta": timedelta, "BytesIO": BytesIO, "st": st,
        "_scope_rendimiento_v191": lambda: ("postgresql://deptit_next", inst, dep, 0),
        "_copiar_resultado_cache_v191": lambda x: x.copy() if hasattr(x, "copy") else x,
        "_version_dependencias_v200": lambda *a, **k: 0, "invalidar_cache_rendimiento_v191": noop,
        "_envolver_funcion_perf_v193": noop, "_versiones_scope_v199": lambda *a, **k: (0, 0, 0),
        "_cache_scope_proyectos_v127": lambda *a, **k: ("postgresql://deptit_next", inst, dep, 0),
        "limpiar_cache_comisiones_operativas": noop, "_b12f_arranque_omitido": noop,
        "_perf_registrar_sql_v191": noop,
        "_modo_lectura_designaciones_v282": lambda: "off", "_modo_lectura_periodos_v280": lambda: "off",
        "_get_designaciones_nuevo_cache_v282": lambda *a, **k: _sin_unidad(),
        "_get_periodos_nuevo_cache_v280": lambda *a, **k: _sin_unidad(),
    })
    from analisis.motor.ref.catalogs import comisiones as c1, designaciones as c2, materias as c3, movimientos as c4
    for mod in (c1, c2, c3, c4):
        for k in dir(mod):
            if k.isupper() or (k.startswith("_") and k[1:2].isupper()):
                ns.setdefault(k, getattr(mod, k))
    infra = {k: v for k, v in ns.items() if callable(v) and k not in (
        "pd", "re", "json", "math", "hashlib", "time", "functools", "date", "datetime", "timedelta", "BytesIO", "st")}
    exec(_codigo(), ns)
    ns.update(infra)
    for nombre, categoria in metadata.TAREAS_SISTEMA.items():
        if categoria == "schema" and nombre in ns:
            ns[nombre] = noop  # DDL de arranque: el esquema ya existe (sin DDL en Etapa 4)
    for k in [n for n in ns if n.startswith("_modo_lectura_") or (n.startswith("_modo_") and n.endswith("_read_v281"))]:
        ns[k] = lambda: "off"
    return ns


__all__ = ["RawTx", "construir", "B12C"]
