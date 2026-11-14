"""Soporte de los tests de Consolidado institucional.

- ``certified_consolidado``: namespace con el cierre transitivo de ``render_consolidado_institucional`` (efectiva v242
  l. 53184; ruteo l. 59795) mas ``_convertir_tabla_a_excel_bytes`` (l. 316, Excel global), ejecutado DESDE
  ``reference_fix02`` en el orden del entry y sin decoradores de cache.  Como en el runtime certificado:
  ``get_conn()`` usa el inyector efectivo B12B/B12J y su departamento sigue a
  ``st.session_state["tenant_scope_departamento_id"]`` (``_pg_current_dep_id`` l. 949), ``_pg_current_inst_id``
  replica l. 932 y ``_pg_read_dataframe`` no inyecta (l. 968).  Tareas de sistema B12F: reconciliation/migration ->
  None, schema -> no-op; pilotos en ``off``.  Nada de reference_fix02 se modifica ni se compila a bytecode.
- ``render``: ejecuta el render certificado con un Streamlit que GRABA cada llamada; los ``st.dataframe`` guardan el
  DataFrame real mostrado y su Excel global (``_convertir_tabla_a_excel_bytes``, como el wrapper v191/v200 l. 445-488),
  los ``download_button`` sus bytes.
- Fixtures de servicio/HTTP del bloque.
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
import re
import time
from datetime import timedelta
from io import BytesIO

import pandas as pd
import psycopg
import pytest

from comisiones_support import FIXED_NOW, _ConnAislada, _FixedDateTime, _Session, _instalar_execute_values  # noqa: F401
from designaciones_support import _Frames
from materias_support import planes_injector
from periodos_support import ENTRY, FIXED_TODAY, _FixedDate, _tree, db_conn, savepoint, session_for  # noqa: F401

RUTEO = 59795
START = {"render_consolidado_institucional", "_convertir_tabla_a_excel_bytes"}


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


# ------------------------------------------------------------------------------------------ st grabador
class _Ctx:
    def __init__(self, st, kind, label=None):
        self.st, self.kind, self.label = st, kind, label

    def __enter__(self):
        if self.kind == "expander":
            self.st.ev.append(("expander", *self.label))
        return self

    def __exit__(self, *a):
        if self.kind == "expander":
            self.st.ev.append(("/expander",))
        return False

    def metric(self, label, value, *a, **k):
        self.st.metric(label, value, *a, **k)


class Grabador:
    """Streamlit que graba la pagina.  ``selects``/``textos``: valores elegidos por ``key``."""

    def __init__(self, session, ns_ref, selects=None, textos=None):
        self.session_state = session
        self.ev: list[tuple] = []
        self.frames: list[pd.DataFrame] = []
        self.descargas: list[dict] = []
        self.selects, self.textos, self._ns = selects or {}, textos or {}, ns_ref

    def title(self, t, *a, **k): self.ev.append(("title", t))
    def markdown(self, t, *a, **k): self.ev.append(("markdown", t))
    def caption(self, t, *a, **k): self.ev.append(("caption", t))
    def info(self, t, *a, **k): self.ev.append(("info", t))
    def warning(self, t, *a, **k): self.ev.append(("warning", t))
    def error(self, t, *a, **k): self.ev.append(("error", t))
    def metric(self, label, value, *a, **k): self.ev.append(("metric", label, value))

    def dataframe(self, data=None, *a, **k):
        # wrapper Excel global (l. 445-488): tras cada st.dataframe, Excel bajo demanda de ESA tabla
        excel = self._ns["_convertir_tabla_a_excel_bytes"](data)
        self.frames.append(data.copy())
        self.ev.append(("dataframe", len(self.frames) - 1, bool(excel)))
        self.descargas.append({"tipo": "excel", "frame": len(self.frames) - 1, "bytes": excel})

    def columns(self, spec, *a, **k):
        n = spec if isinstance(spec, int) else len(spec)
        self.ev.append(("columns", n))
        return [_Ctx(self, "col") for _ in range(n)]

    def expander(self, label, expanded=False, *a, **k):
        return _Ctx(self, "expander", (label, expanded))

    def selectbox(self, label, options, index=0, key=None, **k):
        opts = list(options)
        val = self.selects.get(key, opts[index])
        self.ev.append(("selectbox", label, opts, key, val))
        return val

    def text_input(self, label, value="", key=None, placeholder=None, help=None, **k):
        val = self.textos.get(key, value)
        self.ev.append(("text_input", label, key, placeholder, help, val))
        return val

    def download_button(self, label, data=None, file_name=None, mime=None, **k):
        self.ev.append(("download_button", label, file_name, mime))
        self.descargas.append({"tipo": "csv", "label": label, "nombre": file_name, "mime": mime, "bytes": bytes(data)})

    def __getattr__(self, name):
        def _otro(*a, **k):
            self.ev.append((f"st.{name}",))
        return _otro


def certified_consolidado(raw_conn, user: dict, session: _Session) -> dict:
    """Namespace certificado del Consolidado para ``user``/``session`` sobre ``raw_conn`` (lecturas)."""
    injector = planes_injector()
    frames = _Frames()

    def inst_actual():
        if user.get("rol") == "superadmin" and session.get("superadmin_institucion_id"):
            return int(session["superadmin_institucion_id"])
        if user.get("institucion_id"):
            return int(user["institucion_id"])
        return int(session.get("superadmin_institucion_id") or 0)

    def dep_actual():
        if session.get("tenant_scope_departamento_id"):
            return int(session["tenant_scope_departamento_id"])
        if user.get("departamento_id"):
            return int(user["departamento_id"])
        r = raw_conn.execute("SELECT id FROM departamentos WHERE institucion_id=%s ORDER BY id LIMIT 1",
                             [inst_actual()]).fetchone()
        return int(r[0]) if r else None

    def tenant():
        return {"kind": "tenant", "institucion_id": inst_actual(), "departamento_id": dep_actual()}

    def _pg_read_dataframe(sql, params=None):
        with raw_conn.transaction():
            cur = psycopg.ClientCursor(raw_conn)
            cur.execute(sql, list(params or []))
            rows = cur.fetchall() if cur.description else []
            cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    _instalar_execute_values()
    code, names, lits = _closure()
    noop = lambda *a, **k: None  # noqa: E731
    from deptit_refactor.security.legacy_write_actions import SYSTEM_WRITERS
    ns = {"__builtins__": __builtins__, "USE_POSTGRESQL": True, "DATABASE_URL": "postgresql://test", "DB_PATH": "",
          "MODO_SANEAMIENTO_MATERIAS_INDIVIDUAL": False,
          "get_conn": lambda: _ConnAislada(raw_conn, frames, tenant(), injector),
          "get_planes_conn": lambda: _ConnAislada(raw_conn, frames, {"kind": "planes",
                                                                      "institucion_id": inst_actual()}, injector),
          "get_auth_conn": lambda: _ConnAislada(raw_conn, frames, {"kind": "auth"}, injector),
          "_pg_raw_conn": lambda: _ConnAislada(raw_conn, frames), "_pg_read_dataframe": _pg_read_dataframe,
          "_pg_current_inst_id": inst_actual, "_pg_current_dep_id": dep_actual,
          "_institucion_id_operativa": inst_actual, "current_role": lambda: user.get("rol", ""),
          "current_user": lambda: user,
          "pd": pd, "re": re, "json": json, "math": math, "hashlib": hashlib, "time": time, "functools": functools,
          "inspect": inspect, "date": _FixedDate, "datetime": _FixedDateTime, "timedelta": timedelta,
          "BytesIO": BytesIO, "st": None,
          "_scope_rendimiento_v191": lambda: ("postgresql://test", inst_actual(), dep_actual(), 0),
          "_copiar_resultado_cache_v191": lambda x: x.copy() if hasattr(x, "copy") else x,
          "_version_dependencias_v200": lambda *a, **k: 0, "invalidar_cache_rendimiento_v191": noop,
          "_envolver_funcion_perf_v193": noop, "_versiones_scope_v199": lambda *a, **k: (0, 0, 0),
          "_cache_scope_proyectos_v127": lambda *a, **k: ("postgresql://test", inst_actual(), dep_actual(), 0),
          "limpiar_cache_comisiones_operativas": noop, "_b12f_arranque_omitido": noop,
          "sincronizar_planes_si_corresponde": noop, "sincronizar_vencimientos_concursados_v268": lambda *_: 0,
          "reconciliar_fechas_finalizacion_desde_movimientos_v212": lambda *a, **k: 0,
          "migrar_inscriptos_a_asignatura_periodo_v248": lambda *a, **k: 0}
    for k in [n for n in names if n.startswith("asegurar_esquema")]:
        ns[k] = noop
    for k in [n for n in names if n.startswith("_modo_lectura_")]:
        ns[k] = lambda: "off"
    for w, (cat_, _d) in SYSTEM_WRITERS.items():
        ns[w] = noop if cat_ == "schema" else (lambda *a, **k: None)
    for k, v in lits.items():
        ns.setdefault(k, v)
    from deptit_refactor.catalogs import comisiones as c1, designaciones as c2, materias as c3, movimientos as c4
    for mod in (c1, c2, c3, c4):
        for k in dir(mod):
            if k.isupper() or (k.startswith("_") and k[1:2].isupper()):
                ns.setdefault(k, getattr(mod, k))
    infra = {k: v for k, v in ns.items() if callable(v) and k not in (
        "pd", "re", "json", "math", "hashlib", "time", "functools", "inspect", "date", "datetime", "timedelta",
        "BytesIO")}
    exec(code, ns)
    ns.update(infra)
    ns["_frames"], ns["_session"] = frames, session
    return ns


USUARIOS = {
    "coord1": {"email": "coord@test.local", "rol": "coordinador_institucional", "institucion_id": 1,
               "departamento_id": None},
    "coord2": {"email": "coord2@test.local", "rol": "coordinador_institucional", "institucion_id": 2,
               "departamento_id": None},
    "super": {"email": "super@test.local", "rol": "superadmin", "institucion_id": None, "departamento_id": None},
    "dep": {"email": "info@test.local", "rol": "usuario_departamento", "institucion_id": 1, "departamento_id": 1},
    "lector": {"email": "lector@test.local", "rol": "solo_lectura", "institucion_id": 1, "departamento_id": 1},
    "comercial": {"email": "coord@test.local", "rol": "solo_lectura", "rol_original": "coordinador_institucional",
                  "modo_solo_lectura_comercial": True, "institucion_id": 1, "departamento_id": None},
}


def render(raw_conn, usuario: str, session: dict | None = None, selects=None, textos=None):
    """Ejecuta ``render_consolidado_institucional`` certificado y devuelve el grabador (eventos, frames, descargas)."""
    sess = _Session(**(session or {}))
    ns = certified_consolidado(raw_conn, USUARIOS[usuario], sess)
    st = Grabador(sess, ns, selects, textos)
    ns["st"] = st
    ns["render_consolidado_institucional"]()
    st.ns = ns
    return st


# ------------------------------------------------------------------------------------------ fixtures de servicio
def make_consolidado(service, db_conn, **kwargs):
    from consolidado.service import ConsolidadoService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return ConsolidadoService(None, service, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, **kwargs)


@pytest.fixture
def consolidado(service, repo, db_conn):
    return make_consolidado(service, db_conn)


@pytest.fixture
def http(service, consolidado):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from consolidado.routes import router as consolidado_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(consolidado_router)
    application.state.auth = service
    application.state.consolidado = consolidado
    return TestClient(application, base_url="http://localhost")
