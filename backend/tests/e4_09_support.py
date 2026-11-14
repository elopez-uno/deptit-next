"""Soporte de E4-09 (Carga rápida integral): ejecuta la seccion certificada LITERAL y la compara con NEXT.

- ``certified_carga``: namespace con el cierre transitivo de la seccion (entry l. 61278-61652) ejecutado DESDE
  ``reference_fix02`` (no desde el complemento vendorizado de NEXT), con las definiciones anteriores a l. 61278 en el
  orden del entry, sobre las conexiones certificadas del harness (inyector B12B/B12J efectivo).  Como en E4-05: caches
  Streamlit por memoizacion y pilotos en ``off``; B12A instalado igual que el entry (l. 59086: normalizador
  re-enlazado + guarda de ``actualizar_docente``); compuerta B12F: las tareas de sistema solo corren DENTRO de un writer
  de negocio.  Los writers de negocio registran sus COMMITs por operacion (``_Frames``), como el acoplamiento B12H.
- ``seccion``: el bloque LITERAL ``with tab6:`` (l. 61278) cortado en el ``st.divider()`` que abre la carga simple,
  ejecutado con un Streamlit que GRABA cada llamada y responde los controles (archivo, casillas, boton).
"""
from __future__ import annotations

import ast
import collections
import copy
import functools
import hashlib
import json
import math
import re
import time
from datetime import timedelta
from io import BytesIO

import pandas as pd

from comisiones_support import _ConnAislada, _FixedDateTime, _instalar_execute_values, _Session
from designaciones_support import _Frames, _St
from materias_support import planes_injector
from periodos_support import ENTRY, _FixedDate, _tree

PAGE = (61278, 61652)
CUTOFF = PAGE[0]
EXCLUDE = frozenset({"st", "seleccionar_registro_desde_tabla"})
BUSINESS = ("guardar_docente", "actualizar_docente", "registrar_movimiento", "guardar_designacion")


@functools.lru_cache(maxsize=1)
def _closure():
    tree = copy.deepcopy(_tree(ENTRY))
    defs, aliases = collections.defaultdict(list), {}
    for node in tree.body:
        if node.lineno >= CUTOFF:
            continue
        if isinstance(node, ast.FunctionDef):
            defs[node.name].append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name):
            aliases.setdefault(node.targets[0].id, []).append(node)
    start = {x.id for x in ast.walk(tree) if isinstance(x, ast.Name) and PAGE[0] <= getattr(x, "lineno", 0) <= PAGE[1]}
    seen, queue = set(), list(start) + ["get_periodo_abierto"]
    while queue:
        n = queue.pop()
        if n in seen or n in EXCLUDE:
            continue
        seen.add(n)
        for d in defs.get(n, []):
            queue.extend({x.id for x in ast.walk(d) if isinstance(x, ast.Name)} - seen)
        for a in aliases.get(n, []):
            queue.append(a.value.id)
    picked, cacheadas = [], set()
    for node in tree.body:
        if node.lineno >= CUTOFF:
            continue
        if isinstance(node, ast.FunctionDef) and node.name in seen:
            if any("cache" in ast.unparse(d) for d in node.decorator_list):
                cacheadas.add(node.name)
            node.decorator_list = []
            picked.append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name) and node.targets[0].id in seen:
            picked.append(node)
    lits, runtime = {}, set()
    for node in tree.body:
        if node.lineno >= CUTOFF:
            break
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            nombre = node.targets[0].id
            if nombre in ("_LECTURAS_CACHE_V199", "_DEPENDENCIAS_LECTURAS_V200"):
                valor = ast.literal_eval(node.value)
                runtime |= set(valor if isinstance(valor, list) else valor.keys())
            elif nombre in seen and nombre not in lits:
                try:
                    lits[nombre] = ast.literal_eval(node.value)
                except Exception:
                    pass
    code = compile(ast.Module(body=picked, type_ignores=[]), str(ENTRY), "exec")
    return code, frozenset(seen), lits, frozenset(cacheadas | (runtime & seen))


@functools.lru_cache(maxsize=1)
def seccion():
    """``with tab6:`` (l. 61278) literal, cortado en el ``st.divider()`` previo a "Carga rápida simple de docentes"."""
    nodo = copy.deepcopy(next(n for n in ast.walk(_tree(ENTRY)) if isinstance(n, ast.With) and n.lineno == PAGE[0]))
    assert ast.unparse(nodo.items[0].context_expr) == "tab6"
    idx = next(i for i, s in enumerate(nodo.body) if ast.unparse(s) == "st.divider()")
    assert "Carga rápida simple de docentes" in ast.unparse(nodo.body[idx + 1])
    assert nodo.body[idx - 1].end_lineno <= PAGE[1]
    return compile(ast.Module(body=nodo.body[:idx], type_ignores=[]), str(ENTRY), "exec")


def certified_carga(raw_conn, institution_id: int, department_id: int, email: str = "info@test.local",
                    literal: bool = False) -> dict:
    import psycopg
    from deptit_refactor.b12a.posgrado import install_posgrado_integrity
    from deptit_refactor.catalogs import salarios as cat_sal
    from deptit_refactor.security.legacy_write_actions import SYSTEM_WRITERS

    injector = planes_injector()
    frames = _Frames()
    tenant = {"kind": "tenant", "institucion_id": int(institution_id), "departamento_id": int(department_id)}

    def _pg_read_dataframe(sql, params=None):
        with raw_conn.transaction():
            cur = psycopg.ClientCursor(raw_conn)
            cur.execute(sql, list(params or []))
            rows = cur.fetchall() if cur.description else []
            cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    _instalar_execute_values()
    code, names, lits, cacheadas = _closure()
    _St.warnings, _St.session_state = [], _Session()
    noop = lambda *a, **k: None  # noqa: E731
    ns = {"__builtins__": __builtins__, "USE_POSTGRESQL": True, "DATABASE_URL": "postgresql://test", "DB_PATH": "",
          "MODO_SANEAMIENTO_MATERIAS_INDIVIDUAL": False,
          "get_conn": lambda: _ConnAislada(raw_conn, frames, tenant, injector),
          "get_planes_conn": lambda: _ConnAislada(raw_conn, frames, {"kind": "planes",
                                                                     "institucion_id": int(institution_id)}, injector),
          "_pg_raw_conn": lambda: _ConnAislada(raw_conn, frames), "_pg_read_dataframe": _pg_read_dataframe,
          "_pg_current_inst_id": lambda: institution_id, "_pg_current_dep_id": lambda: department_id,
          "_institucion_id_operativa": lambda: institution_id, "current_role": lambda: "usuario_departamento",
          "current_user": lambda: {"email": email, "rol": "usuario_departamento", "departamento_nombre": ""},
          "pd": pd, "re": re, "json": json, "math": math, "hashlib": hashlib, "time": time, "functools": functools,
          "date": _FixedDate, "datetime": _FixedDateTime, "timedelta": timedelta, "BytesIO": BytesIO, "st": _St,
          "_scope_rendimiento_v191": lambda: ("postgresql://test", institution_id, department_id, 0),
          "_copiar_resultado_cache_v191": lambda x: x.copy() if hasattr(x, "copy") else x,
          "_version_dependencias_v200": lambda *a, **k: 0, "invalidar_cache_rendimiento_v191": noop,
          "_invalidar_cache_rendimiento_pre_v219": noop,
          "_envolver_funcion_perf_v193": noop, "_versiones_scope_v199": lambda *a, **k: (0, 0, 0),
          "_cache_scope_proyectos_v127": lambda *a, **k: ("postgresql://test", institution_id, department_id, 0),
          "limpiar_cache_comisiones_operativas": noop, "_b12f_arranque_omitido": noop,
          "asegurar_esquema_actos_administrativos_v266": noop, "asegurar_esquema_prestamos_docentes_v174": noop}
    for k, v in lits.items():
        ns.setdefault(k, v)
    from deptit_refactor.catalogs import comisiones as c1, designaciones as c2, materias as c3, movimientos as c4
    for mod in (c1, c2, c3, c4, cat_sal):
        for k in dir(mod):
            if k.isupper() or (k.startswith("_") and k[1:2].isupper()):
                ns.setdefault(k, getattr(mod, k))
    infra = {k: v for k, v in ns.items() if callable(v) and k not in (
        "pd", "re", "json", "math", "hashlib", "time", "functools", "date", "datetime", "timedelta", "BytesIO", "st")}
    exec(code, ns)
    ns.update(infra)
    install_posgrado_integrity(ns)  # B12A (l. 59086)
    for k in [n for n in ns if n.startswith("_modo_lectura_") or n.startswith("_modo_") and n.endswith("_read_v281")]:
        ns[k] = lambda: "off"
    almacen: dict = {}
    for nombre in sorted(cacheadas):
        if nombre in ns and callable(ns[nombre]):
            def memo(*a, _f=ns[nombre], _n=nombre, **k):
                clave = (_n, repr(a), repr(sorted(k.items())))
                if clave not in almacen:
                    almacen[clave] = _f(*a, **k)
                v = almacen[clave]
                return v.copy() if hasattr(v, "copy") else v
            ns[nombre] = memo
    for name in BUSINESS:
        def framed(*args, _fn=ns[name], _name=name, **kwargs):
            frames.enter("business", _name)
            try:
                almacen.clear()  # B12I: dentro de un writer las caches se saltean (lectura fresca)
                return _fn(*args, **kwargs)
            finally:
                frames.stack.pop()
                almacen.clear()
        ns[name] = framed
    for w, (categoria, _d) in SYSTEM_WRITERS.items():
        if w not in ns or not callable(ns[w]):
            continue

        def compuerta(*a, _fn=ns[w], _name=w, _cat=categoria, **k):  # B12F
            if _cat == "schema" or not any(kind == "business" for kind, _ in frames.stack):
                return None
            frames.enter("system", _name)
            try:
                return _fn(*a, **k)
            finally:
                frames.stack.pop()
        ns[w] = compuerta
    ns["_frames"] = frames
    ns["_almacen"] = almacen
    ns["periodo_abierto"] = ns["get_periodo_abierto"]()  # global del entry (l. 26123)
    if not literal:
        # Etapa 5 / Tanda B (B4): NEXT reconoce "Años antigüedad" / "N° resolución" de su propio modelo (normalizador
        # endurecido).  Para que los diferenciales sigan comparando TODO lo demas contra el certificado, el lado
        # certificado usa el mismo normalizador; ``literal=True`` conserva el lector certificado tal cual (anomalia).
        from docentes.carga import normalizar_columna_generica
        ns["normalizar_columna_generica"] = normalizar_columna_generica
    return ns


# ------------------------------------------------------------------------------------------ grabacion
class _Rerun(BaseException):
    """``st.rerun()``: como el ``RerunException`` de Streamlit, NO lo atrapa un ``except Exception``."""


class _Bloque:
    def __init__(self, st):
        self.st = st

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        return getattr(self.st, name)


class _Archivo:
    def __init__(self, nombre, contenido):
        self.name, self._c = nombre, contenido

    def getvalue(self):
        return self._c


class StCarga:
    """Streamlit que graba cada llamada de la seccion y responde: archivo subido, casillas y boton."""

    def __init__(self, session_state, archivo=None, actualizar=False, confirmar=False, click=False):
        self.ev: list = []
        self.session_state = session_state
        self.archivo, self.actualizar, self.confirmar, self.click = archivo, actualizar, confirmar, click
        self.descargas: dict = {}

    def columns(self, spec, **k):
        return [_Bloque(self) for _ in range(spec if isinstance(spec, int) else len(spec))]

    def tabs(self, labels):
        self.ev.append(("tabs", list(labels)))
        return [_Bloque(self) for _ in labels]

    def expander(self, label, *a, **k):
        self.ev.append(("expander", label))
        return _Bloque(self)

    filas_modelo = None  # None = el default del control; un entero acelera los tests de escritura

    def number_input(self, label, min_value=None, max_value=None, value=None, step=None, key=None, **k):
        self.ev.append(("number_input", label, min_value, max_value, value, step))
        return value if self.filas_modelo is None else self.filas_modelo

    def download_button(self, label, data=None, file_name=None, mime=None, key=None, help=None, **k):
        self.ev.append(("download_button", label, file_name, mime, help))
        self.descargas[file_name] = data
        return False

    def file_uploader(self, label, type=None, key=None, help=None, **k):
        self.ev.append(("file_uploader", label, list(type or []), help))
        return self.archivo

    def checkbox(self, label, value=False, key=None, disabled=False, help=None, **k):
        self.ev.append(("checkbox", label, disabled, help))
        if "Actualizar los datos personales" in label:
            return self.actualizar
        return self.confirmar and not disabled

    def button(self, label, *a, disabled=False, **k):
        self.ev.append(("button", label, disabled))
        return self.click and not disabled

    def progress(self, valor, text=None):
        self.ev.append(("progress", text))
        return self

    def dataframe(self, df, **k):
        self.ev.append(("dataframe", df.copy() if hasattr(df, "copy") else df))

    def metric(self, label, value, *a, **k):
        self.ev.append(("metric", label, value))

    def rerun(self):
        raise _Rerun()

    def __getattr__(self, name):
        def grabar(*a, **k):
            self.ev.append((name,) + tuple(a))
        return grabar


def ejecutar_seccion(ns: dict, archivo=None, actualizar=False, confirmar=False, click=False,
                     filas_modelo=20) -> StCarga:
    """Un rerun de la seccion; si hubo carga (``st.rerun``), un segundo rerun muestra el resultado (session_state)."""
    StCarga.filas_modelo = filas_modelo
    st = StCarga(_St.session_state, archivo, actualizar, confirmar, click)
    ns["st"] = st
    try:
        exec(seccion(), ns)
    except _Rerun:
        st.ev.append(("rerun",))
        despues = StCarga(_St.session_state, archivo)
        ns["st"] = despues
        exec(seccion(), ns)
        st.resultado = despues
    return st
