"""Soporte de los tests de Disposiciones.

- Reutiliza la conexion real que NUNCA confirma (``db_conn``), los SAVEPOINT y la auditoria falsa de
  ``periodos_support``; las conexiones certificadas (``_ConnAislada``: COMMIT = RELEASE SAVEPOINT y registro de COMMITs
  por writer) de ``comisiones_support``; el inyector efectivo (v193 + B12J) de ``materias_support``.
- ``certified_disposiciones``: ejecuta, EN EL ORDEN DEL ENTRY, todas las definiciones (``def``) y alias simples del
  cierre transitivo de nombres que usa la pagina certificada de Disposiciones (l. 67812-68550) mas el contexto, la
  preparacion masiva, el generador Word y los writers, sin decoradores de cache.  B12F modo verificacion: la DDL
  idempotente incidental (``CREATE TABLE IF NOT EXISTS`` de los parametros por docente, ``asegurar_esquema_*``) NO llega
  a la base.  Nada de reference_fix02 se modifica ni se compila a bytecode.
- ``certified_b12e``: el runtime B12E certificado (``deptit_refactor/b12e/document_isolation.py``) sobre ese namespace y
  una raiz temporal, con el actor ya autorizado (la frontera B10 la reproduce el test).
- Filesystem: cada test usa su propia raiz temporal (``tmp_path``); nunca ``C:\\DEPTIT_NEXT\\storage\\documents``.
- Datos temporales: filas sinteticas ``ZZNEXT`` / CUIL ``20-9913xxxx-x`` dentro de la transaccion del test (ROLLBACK).
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
    FIXED_NOW, USER_EMAIL, _ConnAislada, _CursorAislado, _FixedDateTime, _Session, _instalar_execute_values,
    _literal_assigns, audit_rows, lock_conn,
)
from designaciones_support import _Frames, _St  # noqa: E402
from materias_support import planes_injector  # noqa: E402
from periodos_support import (  # noqa: E402,F401  (fixtures re-exportados)
    ENTRY, EXTRA_DEPARTMENTS, FIXED_TODAY, FakeAuditStore, _FixedDate, _tree, audit_store, db_conn, savepoint,
    session_for,
)

PAGE = (67812, 68550)
EXTRA_START = {
    "obtener_contexto_docente_disposicion", "get_docentes_activos_para_disposiciones_v155",
    "preparar_disposicion_automatica_v158", "_estado_funcional_disposicion_v163",
    "_texto_funcion_no_docente_para_disposicion_v164", "get_numero_inicial_disposiciones_v162", "get_disposiciones",
    "get_estado_consulta_designacion", "get_parametros_disposicion", "construir_considerandos_designaciones_docente",
    "texto_departamento_disposicion_docente", "_ambito_disposicion_v159", "generar_word_desde_plantilla_disposicion",
    "guardar_disposicion", "eliminar_disposicion", "registrar_movimiento", "guardar_parametros_disposicion",
    "guardar_parametros_docente_disposicion", "guardar_datos_designaciones_docente_disposicion",
    "guardar_numero_inicial_disposiciones_v162", "get_datos_designaciones_docente_disposicion",
}
BUSINESS = ("guardar_parametros_disposicion", "guardar_parametros_docente_disposicion",
            "guardar_datos_designaciones_docente_disposicion", "guardar_disposicion", "eliminar_disposicion",
            "registrar_movimiento")
EXCLUDE = {
    "st", "seleccionar_registro_desde_tabla", "_download_button_directo_v222", "mostrar_estado_consulta_designacion",
    "_ejecutar_project_business_write_v292", "_ejecutar_research_assignment_business_write_v294",
    "_guardar_diagnostico_project_business_write_v292", "_guardar_diagnostico_research_assignment_business_write_v294",
    "_modo_project_business_write_v292", "_modo_research_assignment_business_write_v294",
    "_ejecutar_extension_project_business_write_v293", "_ejecutar_extension_assignment_business_write_v295",
    "_guardar_diagnostico_extension_project_business_write_v293",
    "_guardar_diagnostico_extension_assignment_business_write_v295",
    "_modo_extension_project_business_write_v293", "_modo_extension_assignment_business_write_v295",
}
DEP_NOMBRES = {1: "Departamento de Informática e Ingeniería", 2: "Departamento de Administración",
               9: "Departamento de Ciencias Exactas y Naturales"}
USERS = {1: 3, 2: 6}  # departamento -> usuario_departamento del FakeRepo


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


# B12F modo verificacion: la DDL idempotente incidental se verifica como no-op y NO se envia (tampoco cuenta como
# sentencia mutante del COMMIT: en produccion B12F no la ejecuta).
_DDL_IDEMPOTENTE = re.compile(r"^\s*(CREATE\s+(UNIQUE\s+)?(TABLE|INDEX)\s+IF\s+NOT\s+EXISTS|"
                              r"ALTER\s+TABLE\s+\w+\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS)", re.I)


class _CursorB12F(_CursorAislado):
    def execute(self, sql, params=None):
        if _DDL_IDEMPOTENTE.match(str(sql)):
            self.description, self._rows, self.rowcount = None, [], -1
            return
        return super().execute(sql, params)


class _ConnB12F(_ConnAislada):
    def cursor(self):
        return _CursorB12F(self)


def certified_disposiciones(raw_conn, institution_id: int, department_id: int, rol: str = "usuario_departamento",
                            email: str = USER_EMAIL, dep_nombre: str | None = None) -> dict:
    """Namespace con las lecturas, el generador Word y los writers certificados de Disposiciones sobre ``raw_conn``."""
    injector = planes_injector()
    frames = _Frames()
    session = _Session()

    def dep_actual():
        return int(session.get("tenant_scope_departamento_id", department_id))

    def tenant():
        return {"kind": "tenant", "institucion_id": int(institution_id), "departamento_id": dep_actual()}

    def get_conn():
        return _ConnB12F(raw_conn, frames, tenant(), injector)

    def _pg_raw_conn():
        return _ConnB12F(raw_conn, frames)

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
    noop = lambda *a, **k: None  # noqa: E731
    from deptit_refactor.catalogs.documentos import VARIABLES_ASIGNATURAS_DISPOSICION
    ns = {
        "__builtins__": __builtins__,
        "USE_POSTGRESQL": True, "DATABASE_URL": "postgresql://test", "MODO_SANEAMIENTO_MATERIAS_INDIVIDUAL": False,
        "get_conn": get_conn,
        "get_planes_conn": lambda: _ConnB12F(raw_conn, frames, {"kind": "planes", "institucion_id": int(institution_id)},
                                             injector),
        "get_auth_conn": lambda: _ConnB12F(raw_conn, frames, {"kind": "auth"}, injector),
        "_pg_raw_conn": _pg_raw_conn, "_pg_read_dataframe": _pg_read_dataframe,
        "_pg_current_inst_id": lambda: institution_id, "_pg_current_dep_id": dep_actual,
        "_institucion_id_operativa": lambda: institution_id,
        "current_role": lambda: rol,
        "current_user": lambda: {"email": email, "rol": rol, "departamento_nombre": nombre_dep},
        "pd": pd, "re": re, "json": json, "math": math, "hashlib": hashlib, "time": time, "functools": functools,
        "inspect": inspect, "date": _FixedDate, "datetime": _FixedDateTime, "timedelta": timedelta, "BytesIO": BytesIO,
        "st": _St, "VARIABLES_ASIGNATURAS_DISPOSICION": VARIABLES_ASIGNATURAS_DISPOSICION,
        "_scope_rendimiento_v191": lambda: ("postgresql://test", institution_id, dep_actual(), 0),
        "_copiar_resultado_cache_v191": lambda x: x.copy() if hasattr(x, "copy") else x,
        "_version_dependencias_v200": lambda *a, **k: 0, "invalidar_cache_rendimiento_v191": noop,
        "_envolver_funcion_perf_v193": noop,
        "_cache_scope_proyectos_v127": lambda *a, **k: ("postgresql://test", institution_id, dep_actual(), 0),
        # B12F: esquema en modo verificacion y reparaciones al leer omitidas
        "asegurar_esquema_disposicion_docente_designaciones": noop,
        "asegurar_esquema_estado_consulta_designacion": noop,
        "asegurar_esquema_v162_funciones_y_disposiciones": noop,
        "asegurar_esquema_documentos_respaldo_v249": noop, "asegurar_esquema_documentos_respaldo_docentes_v251": noop,
        "asegurar_tipo_resolucion_documentos_v255": noop,
        "asegurar_esquema_investigacion_separado": noop, "asegurar_esquema_extension_separado": noop,
        "asegurar_esquema_documentos_respaldo_proyectos_v261": noop,
        "asegurar_esquema_dependencias_documentales_v262": noop, "asegurar_esquema_actos_administrativos_v266": noop,
        "asegurar_esquema_prestamos_docentes_v174": noop, "asegurar_esquema_v95": noop,
        "asegurar_esquema_config_productividad_v148": noop, "asegurar_esquema_planes_db": noop,
        "asegurar_esquema_inscriptos_asignatura_periodo_v248": noop, "asegurar_esquema_sedes_institucionales": noop,
        "asegurar_esquema_inscriptos_comision": noop, "asegurar_esquema_materia_especifica_comision": noop,
        "asegurar_esquema_materias_compartidas_comision_v118": noop, "asegurar_esquema_opciones_curriculares_v120": noop,
        "asegurar_esquema_comparticion_materias_v137": noop, "asegurar_esquema_resolucion_designacion_v155": noop,
        "sincronizar_planes_si_corresponde": noop, "sincronizar_vencimientos_concursados_v268": lambda *_: 0,
        "reconciliar_fechas_finalizacion_desde_movimientos_v212": lambda *a, **k: 0,
        "migrar_inscriptos_a_asignatura_periodo_v248": lambda *a, **k: 0, "_b12f_arranque_omitido": noop,
        "_versiones_scope_v199": lambda *a, **k: (0, 0, 0), "limpiar_cache_comisiones_operativas": noop,
        "_modo_lectura_proyectos_v283": lambda: "off", "_modo_designaciones_read_v282": lambda: "off",
        "_modo_teachers_read_v281": lambda: "off", "_modo_lectura_docentes_v281": lambda: "off",
        "_modo_lectura_periodos_v280": lambda: "off", "_modo_lectura_comisiones_v285": lambda: "off",
        "_modo_lectura_designaciones_v282": lambda: "off",
    }
    for k, v in _literal_assigns(names).items():
        ns.setdefault(k, v)
    from deptit_refactor.catalogs import comisiones as cat_com
    from deptit_refactor.catalogs import designaciones as cat_des
    from deptit_refactor.catalogs import materias as cat_mat
    from deptit_refactor.catalogs import movimientos as cat_mov
    for mod in (cat_com, cat_des, cat_mat, cat_mov):
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


class _StB12E:
    def __init__(self, session):
        self.session_state = session


def certified_b12e(ns: dict, root, institution_id: int, department_id: int, rol: str = "usuario_departamento"):
    """Runtime B12E certificado sobre ``ns`` y ``root``; ``generate`` corre con el actor YA autorizado (como despues de
    ``guard_business_writer``) y enmarcado como la operacion ``generar_disposicion_word_b12e``."""
    from deptit_refactor.b12e import document_isolation as B
    from deptit_refactor.security.authorization import ActorContext

    actor = ActorContext(authenticated=True, role=rol, access_mode="normal", user_ref=USER_EMAIL,
                         institution_id=institution_id, department_id=department_id,
                         home_institution_id=institution_id,
                         home_department_id=None if rol == "superadmin" else department_id)
    rns = {"_valor_configuracion": lambda key, default="": str(root), "APP_BASE_DIR": str(root), "USE_POSTGRESQL": True,
           "_pg_current_inst_id": lambda: institution_id, "_pg_current_dep_id": lambda: department_id,
           "_b12g_actor_validado": lambda: actor, "st": _StB12E(ns["_session"]),
           "_pg_read_dataframe": ns["_pg_read_dataframe"],
           "generar_word_desde_plantilla_disposicion": ns["generar_word_desde_plantilla_disposicion"],
           "guardar_disposicion": ns["guardar_disposicion"], "registrar_movimiento": ns["registrar_movimiento"]}
    rt = B.DocumentIsolationRuntime(rns)

    def generar(*args):
        token = B._AUTHORIZED.set({"actor": actor})
        frames = ns["_frames"]
        frames.enter("business", "generar_disposicion_word_b12e")
        try:
            return rt.generate(*args)
        finally:
            frames.stack.pop()
            B._AUTHORIZED.reset(token)
    rt.generar = generar
    return rt


# ------------------------------------------------------------------------------------------ estado comparable
_TABLAS = [
    ("disposiciones", "institucion_id=%s"),
    ("disposicion_parametros", "institucion_id=%s"),
    ("disposicion_docente_parametros", "institucion_id=%s"),
    ("disposicion_docente_designaciones", "institucion_id=%s"),
    ("movimientos", "institucion_id=%s"),
    ("estado_consulta_designacion", "institucion_id=%s"),
]
MAX_IDS: dict = {}
_RE_SALIDA = re.compile(r"b12e:inst_(\d+)/dep_(\d+)/disposiciones/\d{8}-\d{6}_([A-Za-z0-9_-]{1,60})_[0-9a-f]{32}\.docx")


def baseline(conn) -> None:
    for tabla, _ in _TABLAS:
        MAX_IDS[tabla] = conn.execute(f"SELECT coalesce(max(id),0) FROM {tabla}").fetchone()[0]


def state(conn, inst: int) -> dict:
    """Contenido de las tablas que tocan (o no deben tocar) los writers; ids nuevos -> orden de creacion.  En
    ``archivo_word`` la marca de tiempo y los 128 bits aleatorios del nombre B12E se normalizan."""
    out = {}
    with conn.cursor(row_factory=dict_row) as cur:
        for tabla, filtro in _TABLAS:
            cur.execute(f"SELECT * FROM {tabla} WHERE {filtro} ORDER BY id", [inst])
            filas = []
            nuevos = 0
            for r in cur.fetchall():
                d = dict(r)
                if d["id"] > MAX_IDS.get(tabla, 0):
                    nuevos += 1
                    d["id"] = f"N{nuevos}"
                if tabla == "disposiciones" and isinstance(d.get("archivo_word"), str):
                    d["archivo_word"] = _RE_SALIDA.sub(r"b12e:inst_\1/dep_\2/disposiciones/<AAAAMMDD-HHMMSS>_\3_<128>",
                                                       d["archivo_word"])
                filas.append(json.dumps(d, sort_keys=True, default=str))
            out[tabla] = filas
    return out


def free_cuil(conn, base: str) -> str:
    digits = re.sub(r"\D", "", base)
    for table in ("docentes", "designaciones", "disposiciones", "disposicion_docente_parametros"):
        n = conn.execute(f"SELECT count(*) FROM {table} WHERE regexp_replace(COALESCE(cuil,''),'[^0-9]','','g')=%s",
                         [digits]).fetchone()[0]
        assert n == 0, f"el CUIL sintetico {base} ya existe en {table}"
    return base


# ------------------------------------------------------------------------------------------ fixtures de servicio
def make_disposiciones(service, audit_store, db_conn, root, **kwargs):
    from disposiciones.service import DisposicionesService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return DisposicionesService(None, service, audit_store, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW,
                                storage_root=lambda: str(root), **kwargs)


@pytest.fixture
def storage_root(tmp_path):
    """Raiz documental AISLADA del test (D2): se borra con ``tmp_path``."""
    root = tmp_path / "documents"
    root.mkdir()
    return root


@pytest.fixture
def disposiciones(service, repo, db_conn, audit_store, storage_root):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    return make_disposiciones(service, audit_store, db_conn, storage_root)


@pytest.fixture
def http(service, disposiciones):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from disposiciones.routes import router as disposiciones_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(disposiciones_router)
    application.state.auth = service
    application.state.disposiciones = disposiciones
    return TestClient(application, base_url="http://localhost")


def record_for(service, repo, dep=1, superadmin=False, user_id=None, **scope):
    if user_id is not None:
        return session_for(service, repo, user_id, **scope)[0]
    if not superadmin:
        return session_for(service, repo, USERS[dep], **scope)[0]
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, dep, False)
    return sup


def periodo_id(conn, dep: int, nombre: str) -> int:
    return conn.execute("SELECT id FROM periodos WHERE institucion_id=1 AND departamento_id=%s AND nombre=%s",
                        [dep, nombre]).fetchone()[0]


def normal(valor):
    """Valor comparable: NaN -> None, escalares numpy -> python, tuplas -> listas, fechas -> texto."""
    if isinstance(valor, dict):
        return {str(k): normal(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [normal(v) for v in valor]
    if hasattr(valor, "item") and not isinstance(valor, (str, bytes)):
        try:
            valor = valor.item()
        except Exception:
            pass
    if isinstance(valor, float) and math.isnan(valor):
        return None
    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor
    return str(valor)


__all__ = [n for n in dir() if not n.startswith("__")]
