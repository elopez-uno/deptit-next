"""Soporte de los tests de Comisiones.

- Reutiliza la conexion real que NUNCA confirma (``db_conn``), los SAVEPOINT y la auditoria falsa de
  ``periodos_support``; las conexiones certificadas (``_Conn`` tenant / raw con COMMIT = RELEASE SAVEPOINT y registro
  de COMMITs por writer) de ``designaciones_support``; el inyector efectivo (v193 + B12J) de ``materias_support``.
- ``certified_comisiones``: ejecuta, EN EL ORDEN DEL ENTRY, todas las definiciones (``def``) y alias simples
  (``_x_pre_vN = x``) del cierre transitivo de nombres que usa la pagina certificada de Comisiones (l. 70015-72307),
  sin decoradores de cache (``st.cache_data`` / ``lru_cache``: B12I las saltea dentro de un writer y fuera no cambian el
  resultado).  Asi las cadenas de redefinicion (base -> v95 -> v174 -> v184 ...) quedan enlazadas igual que en el
  entry.  Nada de reference_fix02 se modifica ni se compila a bytecode.
- Conexiones: ``get_conn()`` (tenant: inyector B12B/B12J), ``get_planes_conn()`` (fuente unica de planes),
  ``get_auth_conn()`` (sedes: sin inyector) y ``_pg_raw_conn()`` (sin inyector).  Cada COMMIT con sentencias mutantes
  se registra (commit_seq, mutating_statements, committing_writer, nested_system_task) como el acoplamiento B12H.
- Datos temporales: filas sinteticas con prefijo ``ZZNEXT`` / CUIL ``20-9912xxxx-x`` dentro de la transaccion del test.
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
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import psycopg
import pytest
from psycopg.rows import dict_row

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from designaciones_support import _Conn, _Cursor, _Frames, _St  # noqa: E402
from materias_support import planes_injector  # noqa: E402
from periodos_support import (  # noqa: E402,F401  (fixtures re-exportados)
    ENTRY, EXTRA_DEPARTMENTS, FIXED_TODAY, FakeAuditStore, _FixedDate, _tree, audit_store, db_conn, savepoint,
    session_for,
)

FIXED_NOW = datetime(2026, 10, 26, 10, 30, 0)
USER_EMAIL = "info@test.local"
PAGE = (70015, 72307)  # la pagina sigue tras l. 72214 (fin de "Eliminar" y pestaña Sedes) hasta l. 72307

# Writers de negocio del registro B10 (dominio comisiones + efectos anidados) y tareas de sistema.
BUSINESS = (
    "guardar_comision", "actualizar_comision", "actualizar_nombre_comision_correccion_v180",
    "actualizar_nombres_comisiones_lote_v195", "cargar_comisiones_rapidas_lote_v232", "guardar_horario_comision",
    "actualizar_horario_comision", "_reparar_horarios_personalizados_por_horario_comision_v95",
    "guardar_asignacion_docente_comision", "guardar_horarios_reales_asignacion",
    "actualizar_estado_asignacion_docente_comision", "sincronizar_horas_asignaciones_comision",
    "guardar_inscriptos_asignatura_periodo_v248", "guardar_sede_institucional", "actualizar_sede_institucional",
    "eliminar_comision", "eliminar_horario_comision", "eliminar_asignacion_docente_comision",
    "eliminar_sede_institucional", "_b10_revertir_alta_comision_incompleta", "registrar_movimiento",
    "asegurar_docente_prestado_local_si_corresponde", "_actualizar_horas_proyecto_directo_v184",
)
# Nombres que la pagina invoca pero que NO forman parte del comportamiento productivo (excluidos por decision K9) o que
# son de presentacion; no se siguen en el cierre.
EXCLUDE = {
    "st", "_ejecutar_commission_composite_write_v290", "_guardar_diagnostico_commission_composite_write_v290",
    "_modo_commission_composite_write_v290", "seleccionar_registro_desde_tabla", "mostrar_datos_actuales_seleccion",
    "formulario_horarios_reales_asignacion",
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
        out = set()
        for x in ast.walk(node):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load):
                out.add(x.id)
        return out

    start = set()
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
    """Constantes literales de modulo (primera asignacion) que usan las funciones del cierre."""
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


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW


class _Session(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as exc:
            raise AttributeError(k) from exc

    def __setattr__(self, k, v):
        self[k] = v


class _CursorAislado(_Cursor):
    """Como psycopg2: un error deja en estado fallido SOLO esa conexion certificada (la transaccion del test sigue
    sana); sus sentencias siguientes fallan hasta ``rollback``/``close``, igual que una conexion propia."""

    def execute(self, sql, params=None):
        if self.conn.failed:
            raise psycopg.errors.InFailedSqlTransaction(
                "current transaction is aborted, commands ignored until end of transaction block")
        try:
            super().execute(sql, params)
        except psycopg.Error:
            self.conn.rollback()
            self.conn.failed = True
            raise


class _ConnAislada(_Conn):
    failed = False

    def cursor(self):
        return _CursorAislado(self)

    def rollback(self):
        super().rollback()
        self.failed = False


def certified_comisiones(raw_conn, institution_id: int, department_id: int, email: str = USER_EMAIL) -> dict:
    """Namespace con las lecturas y writers certificados de Comisiones sobre ``raw_conn`` y el scope indicado."""
    injector = planes_injector()
    frames = _Frames()
    tenant = {"kind": "tenant", "institucion_id": int(institution_id), "departamento_id": int(department_id)}
    planes = {"kind": "planes", "institucion_id": int(institution_id)}

    def get_conn():
        return _ConnAislada(raw_conn, frames, tenant, injector)

    def get_planes_conn():
        return _ConnAislada(raw_conn, frames, planes, injector)

    def _pg_raw_conn():
        return _ConnAislada(raw_conn, frames)

    def _pg_read_dataframe(sql, params=None):
        # Conexion propia en el certificado: un error no contamina la transaccion del test (SAVEPOINT).
        with raw_conn.transaction():
            cur = psycopg.ClientCursor(raw_conn)
            cur.execute(sql, list(params or []))
            rows = cur.fetchall() if cur.description else []
            cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    _instalar_execute_values()
    nodes, names = _closure_nodes()
    session = _Session()
    _St.warnings = []
    _St.session_state = session
    ns = {
        "__builtins__": __builtins__,
        "USE_POSTGRESQL": True, "DATABASE_URL": "postgresql://test", "MODO_SANEAMIENTO_MATERIAS_INDIVIDUAL": False,
        "get_conn": get_conn, "get_planes_conn": get_planes_conn,
        "get_auth_conn": lambda: _ConnAislada(raw_conn, frames, {"kind": "auth"}, injector),
        "_pg_raw_conn": _pg_raw_conn, "_pg_read_dataframe": _pg_read_dataframe,
        "_pg_current_inst_id": lambda: institution_id, "_pg_current_dep_id": lambda: department_id,
        "_institucion_id_operativa": lambda: institution_id,
        "pd": pd, "re": re, "json": json, "math": math, "hashlib": hashlib, "time": time, "functools": functools,
        "date": _FixedDate, "datetime": _FixedDateTime, "timedelta": timedelta, "BytesIO": BytesIO, "st": _St,
        "current_user": lambda: {"email": email},
        # caches / rendimiento: solo versionado local, sin efecto en el resultado
        "_scope_rendimiento_v191": lambda: ("postgresql://test", institution_id, department_id, 0),
        "_copiar_resultado_cache_v191": lambda x: x.copy() if hasattr(x, "copy") else x,
        "_version_dependencias_v200": lambda *a, **k: 0, "invalidar_cache_rendimiento_v191": lambda *a, **k: None,
        "_envolver_funcion_perf_v193": lambda *a, **k: None,
        # B12F: esquema en modo verificacion y migraciones/reconciliaciones omitidas al leer
        "asegurar_esquema_inscriptos_asignatura_periodo_v248": lambda: None,
        "migrar_inscriptos_a_asignatura_periodo_v248": lambda *a, **k: 0,
        "asegurar_esquema_sedes_institucionales": lambda: None, "asegurar_esquema_inscriptos_comision": lambda: None,
        "asegurar_esquema_materia_especifica_comision": lambda: None,
        "asegurar_esquema_materias_compartidas_comision_v118": lambda: None,
        "asegurar_esquema_opciones_curriculares_v120": lambda: None,
        "asegurar_esquema_comparticion_materias_v137": lambda: None, "asegurar_esquema_planes_db": lambda: None,
        "asegurar_esquema_prestamos_docentes_v174": lambda: None, "asegurar_esquema_v95": lambda: None,
        "asegurar_esquema_actos_administrativos_v266": lambda: None,
        "asegurar_esquema_config_productividad_v148": lambda: None,
        "asegurar_esquema_investigacion_separado": lambda: None, "asegurar_esquema_extension_separado": lambda: None,
        "sincronizar_planes_si_corresponde": lambda: None,
        "sincronizar_vencimientos_concursados_v268": lambda *_: 0,
        "reconciliar_fechas_finalizacion_desde_movimientos_v212": lambda *a, **k: 0,
        "_b12f_arranque_omitido": lambda *a, **k: None,
        "_versiones_scope_v199": lambda *a, **k: (0, 0, 0),
        "limpiar_cache_comisiones_operativas": lambda *a, **k: None,
        "limpiar_cache_opciones_curriculares_v127": lambda *a, **k: None,
        "_invalidar_solo_comisiones_v196": lambda *a, **k: None,
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
                                                                       "functools", "date", "datetime", "timedelta",
                                                                       "BytesIO", "st")}
    exec(compile(ast.Module(body=list(nodes), type_ignores=[]), str(ENTRY), "exec"), ns)
    # La infraestructura (conexiones, scope, caches, esquema B12F) es la del harness, no la del entry.
    ns.update(infra)
    # Cache v196/v199 de la unificacion de materias: el certificado la reutiliza entre lecturas y B12I la memoiza
    # dentro de un writer hasta su proxima escritura.  Aqui: memo invalidado por cualquier COMMIT (sin la memo, cada
    # get_materia_comision recalcula todo el catalogo y las lecturas tardan minutos; el resultado es el mismo).
    _unif = ns["_materias_para_comisiones_unificadas_y_mapa"]
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
        kind = "business"

        def framed(*args, _fn=ns[name], _name=name, _kind=kind, **kwargs):
            frames.enter(_kind, _name)
            try:
                return _fn(*args, **kwargs)
            finally:
                frames.stack.pop()
        ns[name] = framed
    ns["_frames"] = frames
    ns["_session"] = session
    return ns


def _instalar_execute_values() -> None:
    """``psycopg2.extras.execute_values`` del lote v232 sobre el cursor del harness: un INSERT multi-fila por pagina
    (cada pagina es una sentencia, como psycopg2).  Solo si psycopg2 no esta instalado (no lo esta en NEXT)."""
    import types
    if "psycopg2.extras" in sys.modules:
        return

    def execute_values(cur, sql, argslist, template=None, page_size=100, fetch=False):
        out = []
        rows = list(argslist)
        for i in range(0, len(rows), page_size):
            page = rows[i:i + page_size]
            values = ",".join("(" + ",".join(["%s"] * len(r)) + ")" for r in page)
            cur.execute(sql.replace("%s", values, 1), [v for r in page for v in r])
            if fetch:
                out.extend(cur.fetchall())
        return out if fetch else None

    pkg = types.ModuleType("psycopg2")
    extras = types.ModuleType("psycopg2.extras")
    extras.execute_values = execute_values
    pkg.extras = extras
    sys.modules["psycopg2"] = pkg
    sys.modules["psycopg2.extras"] = extras


# ------------------------------------------------------------------------------------------ estado comparable
_TABLAS_ESTADO = [
    # (tabla, filtro de ambito, columnas FK a normalizar -> prefijo de la tabla referida)
    ("comisiones", "institucion_id=%s AND departamento_id=%s", {}),
    ("comision_materias", "institucion_id=%s", {"comision_id": "comisiones"}),
    ("horarios_comision", "institucion_id=%s", {"comision_id": "comisiones"}),
    ("asignaciones_docentes_comision", "institucion_id=%s", {"comision_id": "comisiones"}),
    ("horarios_asignacion_docente_comision", "institucion_id=%s",
     {"asignacion_id": "asignaciones_docentes_comision", "horario_comision_id": "horarios_comision"}),
    ("docentes", "institucion_id=%s", {}),
    ("investigacion_docente", "institucion_id=%s", {}),
    ("extension_docente", "institucion_id=%s", {}),
    ("inscriptos_asignatura_periodo", "institucion_id=%s", {}),
    ("inscriptos_comision", "institucion_id=%s", {"comision_id": "comisiones"}),
    ("inscriptos_comision_materia", "institucion_id=%s", {"comision_id": "comisiones"}),
    ("sedes_institucion", "institucion_id=%s", {}),
    ("movimientos", "institucion_id=%s", {}),
]
MAX_IDS: dict = {}


def baseline_comisiones(conn) -> None:
    """Ids maximos antes de la prueba: las filas nuevas se comparan sin id (las secuencias avanzan distinto)."""
    for tabla, _, _ in _TABLAS_ESTADO:
        MAX_IDS[tabla] = conn.execute(f"SELECT coalesce(max(id),0) FROM {tabla}").fetchone()[0]


def state_comisiones(conn, inst: int, dep: int) -> dict:
    """Contenido de las tablas que tocan los writers de Comisiones; ids nuevos -> orden de creacion (N1, N2...)."""
    datos, nuevos = {}, {}
    with conn.cursor(row_factory=dict_row) as cur:
        for tabla, filtro, _ in _TABLAS_ESTADO:
            params = [inst, dep] if filtro.count("%s") == 2 else [inst]
            cur.execute(f"SELECT * FROM {tabla} WHERE {filtro} ORDER BY id", params)
            filas = list(cur.fetchall())
            ids_nuevos = [r["id"] for r in filas if r["id"] > MAX_IDS.get(tabla, 0)]
            nuevos[tabla] = {i: f"N{n}" for n, i in enumerate(ids_nuevos, start=1)}
            datos[tabla] = filas
    out = {}
    for tabla, _, fks in _TABLAS_ESTADO:
        filas = []
        for r in datos[tabla]:
            d = dict(r)
            d["id"] = nuevos[tabla].get(r["id"], r["id"])
            for col, ref in fks.items():
                if d.get(col) is not None:
                    d[col] = nuevos[ref].get(d[col], d[col])
            filas.append(json.dumps(d, sort_keys=True, default=str))
        out[tabla] = filas
    return out


# ------------------------------------------------------------------------------------------ fixtures de servicio
def make_comisiones(service, audit_store, db_conn, lock_connection=None, **kwargs):
    """``ComisionesService`` sobre la transaccion del test (SAVEPOINT por unidad) y una conexion dedicada al lock."""
    from contextlib import nullcontext

    from comisiones.service import ComisionesService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    if lock_connection is not None:
        kwargs.setdefault("lock_connection", lambda: nullcontext(lock_connection))
    return ComisionesService(None, service, audit_store, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, **kwargs)


def audit_rows(conn) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM b12h_audit_log WHERE occurred_at >= transaction_timestamp() "
                    "ORDER BY occurred_at, correlation_id, event_seq")
        return list(cur.fetchall())


@pytest.fixture
def lock_conn():
    """Conexion dedicada al lock de SESION B12I (autocommit, como el certificado)."""
    import db

    settings = db.load_settings()
    db.check_config(settings)
    conn = psycopg.connect(settings["database_url"], autocommit=True, connect_timeout=5,
                           application_name="deptit_next_tests_lock")
    try:
        db.verify_identity(conn)
        yield conn
    finally:
        conn.close()


@pytest.fixture
def comisiones(service, repo, db_conn, audit_store, lock_conn):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    return make_comisiones(service, audit_store, db_conn, lock_connection=lock_conn)


@pytest.fixture
def http(service, comisiones):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from comisiones.routes import router as comisiones_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(comisiones_router)
    application.state.auth = service
    application.state.comisiones = comisiones
    return TestClient(application, base_url="http://localhost")
