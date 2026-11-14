"""Entorno de ejecucion por request del motor de LECTURA certificado de Analisis (``certificado.py`` generado).

Equivalencia con el runtime certificado B13-FIX02 (docs/analisis_productividad_analysis.md §9-§10, §30):
- ``get_conn()``: conexion "tenant" con el inyector B12B efectivo (``inyector.py`` + B12J) y el ambito de la SESION;
  ``_pg_raw_conn()`` / ``_pg_read_dataframe``: sin inyector (el SQL certificado lleva su ambito explicito).  Cada
  conexion certificada es un SAVEPOINT de la transaccion READ ONLY del request: un error deja fallida solo esa
  conexion, como una conexion propia del pool (psycopg2).  Parametros con enlace del lado cliente (psycopg2).
  Hardening NEXT ``DQ-SCOPE-OR-B12B`` (Etapa 5, ``ambito.py``): un WHERE de nivel superior con OR se envuelve
  entre parentesis antes de inyectar el ambito; sin OR de nivel superior el SQL queda identico.
  ``DQ-SCOPE-SUBQUERY-B12B``: las subconsultas / CTE que leen tablas con ambito reciben el ambito de la sesion.
- B12F: las tareas de sistema ``reconciliation``/``migration`` devuelven ``None`` fuera de una operacion de negocio
  (D-AM2: v208/v212/v214 no se ejecutan al leer); las ``schema`` no hacen nada (sin DDL).  Los writers de negocio del
  cierre levantan ``EscrituraEnLectura`` (el unico writer real, ``guardar_porcentaje_horas_no_lectivas_v148``, es del
  servicio NEXT).  Ademas toda sentencia mutante se rechaza antes de llegar a la base y la transaccion es READ ONLY.
- Pilotos de lectura en ``off``.  Caches Streamlit -> memoizacion REQUEST-SCOPED de las funciones que el certificado
  decoraba con cache (D-AM12): misma clave = mismos argumentos; nada sobrevive al request.
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

from . import metadata
from .ambito import proteger_or, proteger_subconsultas

_DIR = Path(__file__).resolve().parent
_MUTANTE = re.compile(r"^\s*(INSERT|UPDATE|DELETE|MERGE|UPSERT|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|COMMENT|VACUUM)\b",
                      re.I)


@functools.lru_cache(maxsize=1)
def _codigo_certificado():
    return compile((_DIR / "certificado.py").read_text(encoding="utf-8"), str(_DIR / "certificado.py"), "exec")


@functools.lru_cache(maxsize=1)
def _inyector() -> dict:
    """``periodos_support.certified_injector`` + ``materias_support.planes_injector`` (texto literal del entry)."""
    from .ref.b12j.left_join_scope import install_left_join_scope

    ns = {"re": re, "functools": functools, "USE_POSTGRESQL": True}
    exec(compile((_DIR / "inyector.py").read_text(encoding="utf-8"), str(_DIR / "inyector.py"), "exec"), ns)
    ns["PG_ALL_SCOPED_TABLES"] = ns["PG_INSTITUTION_TABLES"] | ns["PG_DEPARTMENT_TABLES"]
    ns["_pg_current_inst_id"] = lambda: (_ for _ in ()).throw(AssertionError("ambito implicito"))
    ns["_pg_current_dep_id"] = ns["_pg_current_inst_id"]
    install_left_join_scope(ns)
    return ns


class EscrituraEnLectura(RuntimeError):
    """El motor de lectura intento escribir (nunca debe ocurrir: B12F + READ ONLY)."""


class _SessionState(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as exc:
            raise AttributeError(k) from exc

    def __setattr__(self, k, v):
        self[k] = v


class _St:
    """``streamlit`` minimo para las funciones certificadas de lectura (sin UI)."""

    def __init__(self):
        self.session_state = _SessionState()
        self.avisos: list[str] = []

    class cache_data:  # noqa: N801
        @staticmethod
        def clear():
            return None

    def warning(self, msg, *a, **k):
        self.avisos.append(str(msg))

    info = error = success = caption = markdown = write = warning


class _Cursor:
    def __init__(self, conn: "_Conexion"):
        self.conn = conn
        self.cur = psycopg.ClientCursor(conn.raw)
        self.rowcount = -1
        self.lastrowid = None
        self.description = None
        self._rows: list = []

    def execute(self, sql, params=None):
        if self.conn.fallida:
            raise psycopg.errors.InFailedSqlTransaction(
                "current transaction is aborted, commands ignored until end of transaction block")
        if _MUTANTE.match(str(sql)):
            raise EscrituraEnLectura("sentencia mutante en el motor de lectura")
        q, p = self.conn.preparar(str(sql), params)
        self.conn.abrir()
        try:
            self.cur.execute(q, p)
        except psycopg.Error:
            self.conn.rollback()
            self.conn.fallida = True
            raise
        self.rowcount = self.cur.rowcount
        self.description = self.cur.description
        self._rows = self.cur.fetchall() if self.cur.description else []

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

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Conexion:
    """Conexion certificada (``get_conn`` con ambito o ``_pg_raw_conn``) = SAVEPOINT del request."""

    _n = 0

    def __init__(self, raw: psycopg.Connection, ambito: Optional[dict]):
        self.raw, self.ambito = raw, ambito
        self.fallida = False
        self._sp: Optional[str] = None

    def preparar(self, sql: str, params):
        if self.ambito is None:
            return sql, list(params or [])
        inj, head = _inyector(), sql.lstrip().upper()
        if head.startswith("SELECT") or head.startswith("WITH"):
            # Etapa 5 / Tanda A: DQ-SCOPE-OR-B12B (WHERE de nivel superior con OR entre parentesis) y
            # DQ-SCOPE-SUBQUERY-B12B (ambito de la sesion en subconsultas / CTE) antes del inyector certificado.
            sql = proteger_subconsultas(proteger_or(sql), self.ambito, inj["PG_INSTITUTION_TABLES"],
                                        inj["PG_DEPARTMENT_TABLES"])
            return inj["_pg_scope_select"](sql, params, self.ambito)
        return inj["_pg_convert_sql"](sql), list(params or [])

    def abrir(self):
        if self._sp is None:
            _Conexion._n += 1
            self._sp = f"analisis_{_Conexion._n}"
            self.raw.execute(f"SAVEPOINT {self._sp}")

    def cursor(self, *a, **k):
        return _Cursor(self)

    def commit(self):
        if self._sp is not None:
            self.raw.execute(f"RELEASE SAVEPOINT {self._sp}")
            self._sp = None

    def rollback(self):
        if self._sp is not None:
            self.raw.execute(f"ROLLBACK TO SAVEPOINT {self._sp}")
            self.raw.execute(f"RELEASE SAVEPOINT {self._sp}")
            self._sp = None
        self.fallida = False

    def close(self):
        self.rollback()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _memo(fn: Callable, almacen: dict, nombre: str) -> Callable:
    @functools.wraps(fn)
    def memo(*a, **k):
        clave = (nombre, repr(a), repr(sorted(k.items())))
        if clave not in almacen:
            almacen[clave] = fn(*a, **k)
        v = almacen[clave]
        return v.copy() if hasattr(v, "copy") else v
    return memo


def _bloqueado(nombre: str) -> Callable:
    def writer(*a, **k):
        raise EscrituraEnLectura(f"{nombre}: escritura fuera del motor de lectura")
    return writer


def construir(raw: psycopg.Connection, institucion_id: int, departamento_id: int, *,
              usuario: Optional[dict] = None,
              hoy: Callable[[], date] = date.today, ahora: Callable[[], datetime] = datetime.now) -> dict:
    """Namespace del motor para UN request (ambito = sesion).  ``raw`` debe estar en una transaccion READ ONLY."""
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

    def _pg_read_dataframe(sql, params=None):
        with raw.transaction():
            cur = psycopg.ClientCursor(raw)
            if _MUTANTE.match(str(sql)):
                raise EscrituraEnLectura("sentencia mutante en el motor de lectura")
            cur.execute(sql, list(params or []))
            rows = cur.fetchall() if cur.description else []
            cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    usuario = dict(usuario or {})
    ns: dict[str, Any] = {
        "__builtins__": __builtins__, "__name__": "analisis.motor.certificado",
        "USE_POSTGRESQL": True, "DATABASE_URL": "postgresql://deptit_next", "DB_PATH": "",
        "MODO_SANEAMIENTO_MATERIAS_INDIVIDUAL": False,
        "get_conn": lambda: _Conexion(raw, ambito), "_pg_raw_conn": lambda: _Conexion(raw, None),
        "get_planes_conn": lambda: _Conexion(raw, {"kind": "planes", "institucion_id": inst}),
        "_pg_read_dataframe": _pg_read_dataframe,
        "_pg_current_inst_id": lambda: inst, "_pg_current_dep_id": lambda: dep,
        "_institucion_id_operativa": lambda: inst,
        "current_role": lambda: usuario.get("rol"), "current_user": lambda: usuario,
        "pd": pd, "re": re, "json": json, "math": math, "hashlib": hashlib, "time": time, "functools": functools,
        "date": _Date, "datetime": _DateTime, "timedelta": timedelta, "BytesIO": BytesIO, "st": st,
        "_scope_rendimiento_v191": lambda: ("postgresql://deptit_next", inst, dep, 0),
        "_copiar_resultado_cache_v191": lambda x: x.copy() if hasattr(x, "copy") else x,
        "_version_dependencias_v200": lambda *a, **k: 0, "invalidar_cache_rendimiento_v191": noop,
        "_envolver_funcion_perf_v193": noop, "_versiones_scope_v199": lambda *a, **k: (0, 0, 0),
        "_cache_scope_proyectos_v127": lambda *a, **k: ("postgresql://deptit_next", inst, dep, 0),
        "limpiar_cache_comisiones_operativas": noop, "_b12f_arranque_omitido": noop,
    }
    for nombre, categoria in metadata.TAREAS_SISTEMA.items():
        ns[nombre] = noop if categoria == "schema" else (lambda *a, **k: None)
    for nombre in metadata.WRITERS_NEGOCIO:
        ns[nombre] = _bloqueado(nombre)
    from .ref.catalogs import comisiones as c1, designaciones as c2, materias as c3, movimientos as c4
    for mod in (c1, c2, c3, c4):
        for k in dir(mod):
            if k.isupper() or (k.startswith("_") and k[1:2].isupper()):
                ns.setdefault(k, getattr(mod, k))
    infra = {k: v for k, v in ns.items() if callable(v) and k not in (
        "pd", "re", "json", "math", "hashlib", "time", "functools", "date", "datetime", "timedelta", "BytesIO", "st")}
    exec(_codigo_certificado(), ns)
    ns.update(infra)
    for k in [n for n in ns if n.startswith("_modo_lectura_")]:
        ns[k] = lambda: "off"
    almacen: dict = {}
    # Caches certificadas: decoradas (``@st.cache_data``) e instaladas en tiempo de ejecucion (v199 / v200).
    for nombre in sorted(set(metadata.CACHEADAS) | set(metadata.CACHEADAS_RUNTIME)):
        if nombre in ns and callable(ns[nombre]):
            ns[nombre] = _memo(ns[nombre], almacen, nombre)
    ns["_motor_st"] = st
    ns["_motor_memo"] = almacen
    return ns
