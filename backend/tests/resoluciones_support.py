"""Soporte de los tests de Resoluciones y respaldos.

- Reutiliza la conexion real que NUNCA confirma (``db_conn``), los SAVEPOINT y la auditoria falsa de
  ``periodos_support``; las conexiones certificadas (``_ConnAislada``: COMMIT = RELEASE SAVEPOINT y registro de COMMITs
  por writer) de ``comisiones_support``; el inyector efectivo (v193 + B12J) de ``materias_support``.
- ``certified_resoluciones``: ejecuta, EN EL ORDEN DEL ENTRY y hasta el ruteo de la pagina (l. 68551), todas las
  definiciones y alias simples del cierre transitivo de nombres que usa ``render_repositorio_documental_v249``
  (l. 51514-52129) mas las funciones documentales que otros modulos invocan (Resumen v263/v266, acto contextual v267,
  vinculos v266).  Las cadenas de redefinicion (``get_documentos_respaldo_v251`` v251 -> v266 -> v286,
  ``get_actos_docente_resumen_v263`` v263 -> v266, ``get_designaciones`` ... -> v282) quedan enlazadas igual que en el
  entry, con los pilotos en modo ``off``.  Nada de reference_fix02 se modifica ni se compila a bytecode.
- Los ``asegurar_esquema_*`` documentales (DDL + siembras + migraciones) se reemplazan por no-ops (B12F / D-AK7).
- PDF de prueba: sinteticos minimos generados en memoria (``pdf_sintetico``); nunca se leen PDF productivos a disco.
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
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import psycopg
import pytest
from psycopg.rows import dict_row

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from comisiones_support import (  # noqa: E402,F401  (fixtures re-exportados)
    FIXED_NOW, USER_EMAIL, _ConnAislada, _FixedDateTime, _Session, _instalar_execute_values, audit_rows, lock_conn,
)
from designaciones_support import _Frames, _St  # noqa: E402
from materias_support import planes_injector  # noqa: E402
from periodos_support import (  # noqa: E402,F401  (fixtures re-exportados)
    ENTRY, EXTRA_DEPARTMENTS, FIXED_TODAY, FakeAuditStore, _FixedDate, _tree, audit_store, db_conn, savepoint,
    session_for,
)

PAGE = (51514, 52129)
CUTOFF = 68551  # ruteo ``elif modulo == "📂 Resoluciones y respaldos"``: lo definido antes es lo efectivo
EXTRA_START = {
    "get_actos_docente_resumen_v263", "_resolver_acto_contextual_v267", "_eliminar_acto_recien_creado_v267",
    "vincular_acto_designacion_v266", "vincular_acto_movimiento_v266", "eliminar_documento_respaldo_v249",
    "_render_nuevo_acto_inline_v267", "get_documentos_proyectos_v263", "vincular_acto_designaciones_masivo_v267",
    "desvincular_acto_designaciones_masivo_v267", "vincular_acto_movimientos_masivo_v267",
    "desvincular_acto_movimientos_masivo_v267", "desvincular_acto_proyectos_masivo_v267",
}
BUSINESS = (
    "guardar_documento_respaldo_v249", "guardar_documento_respaldo_v251", "adjuntar_pdf_documento_respaldo_v272",
    "actualizar_dependencia_documento_v262", "guardar_dependencia_documental_v262",
    "actualizar_dependencia_documental_v262", "_vincular_proyectos_documento_v261", "eliminar_documento_respaldo_v249",
    "eliminar_documento_respaldo_v251", "vincular_acto_designacion_v266", "vincular_acto_movimiento_v266",
    "_eliminar_acto_recien_creado_v267", "registrar_movimiento", "vincular_acto_designaciones_masivo_v267",
    "desvincular_acto_designaciones_masivo_v267", "vincular_acto_movimientos_masivo_v267",
    "desvincular_acto_movimientos_masivo_v267", "desvincular_acto_proyectos_masivo_v267",
)
EXCLUDE = {
    "st", "_modo_document_business_write_v291", "_ejecutar_document_business_write_v291",
    "_guardar_diagnostico_document_business_write_v291", "seleccionar_registro_desde_tabla",
    "_download_button_directo_v222",
}


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


def certified_resoluciones(raw_conn, institution_id: int, department_id: int, rol: str = "usuario_departamento",
                           email: str = USER_EMAIL) -> dict:
    """Namespace con las lecturas y writers certificados del repositorio documental sobre ``raw_conn``."""
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
        "USE_POSTGRESQL": True, "DATABASE_URL": "postgresql://test", "MODO_SANEAMIENTO_MATERIAS_INDIVIDUAL": False,
        "get_conn": get_conn, "get_planes_conn": lambda: _ConnAislada(raw_conn, frames, {
            "kind": "planes", "institucion_id": int(institution_id)}, injector),
        "get_auth_conn": lambda: _ConnAislada(raw_conn, frames, {"kind": "auth"}, injector),
        "_pg_raw_conn": _pg_raw_conn, "_pg_read_dataframe": _pg_read_dataframe,
        "_pg_current_inst_id": lambda: institution_id, "_pg_current_dep_id": lambda: department_id,
        "_institucion_id_operativa": lambda: institution_id,
        "current_role": lambda: rol,
        "current_user": lambda: {"email": email, "rol": rol, "departamento_nombre": ""},
        "pd": pd, "re": re, "json": json, "math": math, "hashlib": hashlib, "time": time, "functools": functools,
        "inspect": inspect, "date": _FixedDate, "datetime": _FixedDateTime, "timedelta": timedelta, "BytesIO": BytesIO,
        "st": _St,
        "_scope_rendimiento_v191": lambda: ("postgresql://test", institution_id, department_id, 0),
        "_copiar_resultado_cache_v191": lambda x: x.copy() if hasattr(x, "copy") else x,
        "_version_dependencias_v200": lambda *a, **k: 0, "invalidar_cache_rendimiento_v191": noop,
        "_envolver_funcion_perf_v193": noop,
        "_cache_scope_proyectos_v127": lambda *a, **k: ("postgresql://test", institution_id, department_id, 0),
        # B12F / D-AK7: DDL, siembras y migraciones al leer omitidos
        "asegurar_esquema_documentos_respaldo_v249": noop, "asegurar_tipo_resolucion_documentos_v255": noop,
        "asegurar_esquema_dependencias_documentales_v262": noop,
        "asegurar_esquema_documentos_respaldo_docentes_v251": noop,
        "asegurar_esquema_documentos_respaldo_proyectos_v261": noop,
        "asegurar_esquema_actos_administrativos_v266": noop,
        "asegurar_esquema_investigacion_separado": noop, "asegurar_esquema_extension_separado": noop,
        "asegurar_esquema_prestamos_docentes_v174": noop, "asegurar_esquema_v95": noop,
        "asegurar_esquema_config_productividad_v148": noop, "asegurar_esquema_planes_db": noop,
        "asegurar_esquema_inscriptos_asignatura_periodo_v248": noop, "asegurar_esquema_sedes_institucionales": noop,
        "asegurar_esquema_inscriptos_comision": noop, "asegurar_esquema_materia_especifica_comision": noop,
        "asegurar_esquema_materias_compartidas_comision_v118": noop,
        "asegurar_esquema_opciones_curriculares_v120": noop, "asegurar_esquema_comparticion_materias_v137": noop,
        "asegurar_esquema_v162_funciones_y_disposiciones": noop,
        "asegurar_esquema_resolucion_designacion_v155": noop,
        "sincronizar_planes_si_corresponde": noop, "sincronizar_vencimientos_concursados_v268": lambda *_: 0,
        "reconciliar_fechas_finalizacion_desde_movimientos_v212": lambda *a, **k: 0,
        "migrar_inscriptos_a_asignatura_periodo_v248": lambda *a, **k: 0,
        "_b12f_arranque_omitido": noop, "_versiones_scope_v199": lambda *a, **k: (0, 0, 0),
        "limpiar_cache_comisiones_operativas": noop,
        # pilotos apagados (modo off = legado exacto)
        "_modo_lectura_proyectos_v283": lambda: "off", "_modo_lectura_documentos_v286": lambda: "off",
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


# ------------------------------------------------------------------------------------------ PDF sintetico
def pdf_sintetico(texto: str = "ZZNEXT", relleno: int = 0) -> bytes:
    """PDF minimo valido generado en memoria (nunca un documento productivo)."""
    cuerpo = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
              b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n% " + texto.encode("utf-8") + b"\n")
    return cuerpo + (b"%" + b"0" * max(relleno - 1, 0) + b"\n" if relleno else b"") + b"trailer<</Root 1 0 R>>\n%%EOF\n"


# ------------------------------------------------------------------------------------------ estado comparable
_TABLAS = [
    ("documentos_respaldo", {}),
    ("documentos_respaldo_docentes", {"documento_id": "documentos_respaldo"}),
    ("documentos_respaldo_proyectos", {"documento_id": "documentos_respaldo"}),
    ("documentos_respaldo_designaciones", {"documento_id": "documentos_respaldo"}),
    ("documentos_respaldo_movimientos", {"documento_id": "documentos_respaldo"}),
    ("dependencias_documentales", {}),
    ("movimientos", {}),
]
MAX_IDS: dict = {}


def baseline(conn) -> None:
    for tabla, _ in _TABLAS:
        MAX_IDS[tabla] = conn.execute(f"SELECT coalesce(max(id),0) FROM {tabla}").fetchone()[0]


def state(conn, inst: int) -> dict:
    """Contenido de las tablas documentales (binario como md5 + largo); ids nuevos -> orden de creacion (N1, N2...)."""
    datos, nuevos = {}, {}
    with conn.cursor(row_factory=dict_row) as cur:
        for tabla, _ in _TABLAS:
            cur.execute(f"SELECT * FROM {tabla} WHERE institucion_id=%s ORDER BY id", [inst])
            filas = list(cur.fetchall())
            ids_nuevos = [r["id"] for r in filas if r["id"] > MAX_IDS.get(tabla, 0)]
            nuevos[tabla] = {i: f"N{n}" for n, i in enumerate(ids_nuevos, start=1)}
            datos[tabla] = filas
    out = {}
    for tabla, fks in _TABLAS:
        filas = []
        for r in datos[tabla]:
            d = dict(r)
            d["id"] = nuevos[tabla].get(r["id"], r["id"])
            for volatil in ("fecha_vinculacion", "fecha_creacion", "fecha_actualizacion"):
                d.pop(volatil, None)  # CURRENT_TIMESTAMP de la transaccion
            if "archivo_pdf" in d:
                pdf = bytes(d.pop("archivo_pdf") or b"")
                d["archivo_pdf_md5"] = hashlib.md5(pdf).hexdigest()
                d["archivo_pdf_len"] = len(pdf)
            for col, ref in fks.items():
                if d.get(col) is not None:
                    d[col] = nuevos[ref].get(d[col], d[col])
            filas.append(json.dumps(d, sort_keys=True, default=str))
        out[tabla] = filas
    return out


# ------------------------------------------------------------------------------------------ fixtures de servicio
def make_resoluciones(service, audit_store, db_conn, **kwargs):
    from resoluciones_respaldos.service import ResolucionesService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return ResolucionesService(None, service, audit_store, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, **kwargs)


@pytest.fixture
def resoluciones(service, repo, db_conn, audit_store):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    return make_resoluciones(service, audit_store, db_conn)


@pytest.fixture
def http(service, resoluciones):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from resoluciones_respaldos.routes import router as resoluciones_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(resoluciones_router)
    application.state.auth = service
    application.state.resoluciones_respaldos = resoluciones
    return TestClient(application, base_url="http://localhost")


def record_for(service, repo, dep=1, superadmin=False, user_id=None, **scope):
    """Sesion real del AuthService: usuario_departamento del departamento (1: info, 2: admin) o superadmin."""
    if user_id is not None:
        return session_for(service, repo, user_id, **scope)[0]
    if not superadmin:
        return session_for(service, repo, {1: 3, 2: 6}[dep], **scope)[0]
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, dep, False)
    return sup


__all__ = ["certified_resoluciones", "baseline", "state", "make_resoluciones", "audit_rows", "pdf_sintetico",
           "record_for", "FIXED_TODAY", "FIXED_NOW", "session_for", "dict_row", "datetime", "date"]
