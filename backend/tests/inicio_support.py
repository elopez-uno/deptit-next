"""Soporte de los tests de Inicio.

- ``certified_inicio``: namespace con el cierre transitivo de la pagina ``🏠 Inicio`` (l. 59280-59794, mas
  ``get_periodo_abierto`` de la global ``periodo_abierto`` l. 26123) ejecutado DESDE ``reference_fix02``.  Reutiliza
  sin cambios la maquinaria de ``analisis_support.certified_analisis`` (conexiones certificadas con SAVEPOINT +
  inyector B12B/B12J, B12F, pilotos en ``off``, caches emuladas por memoizacion) cambiando solo el cierre.
- ``pagina_certificada``: ejecuta el bloque ``if modulo == "🏠 Inicio":`` LITERAL del entry sobre ese namespace con un
  Streamlit que graba cada llamada (titulo, metricas, captions, expanders, botones con su destino, tablas con o sin el
  Excel global v191/v200, graficos Vega-Lite).  ``eventos_payload`` produce la misma secuencia desde el payload NEXT
  (``GET /inicio``): asi se compara el contrato de UI contra la pagina certificada real.
- Fixtures de servicio/HTTP del bloque.
"""

from __future__ import annotations

import ast
import collections
import copy
import functools
import textwrap
from typing import Any

import pytest

import analisis_support as A
from analisis.pagina import tabla, tabla_registros, valor
from inicio import pagina as P
from periodos_support import ENTRY, EXTRA_DEPARTMENTS, FIXED_TODAY, _tree, db_conn, savepoint, session_for  # noqa: F401
from comisiones_support import FIXED_NOW  # noqa: F401
from designaciones_support import _St

PAGE = (59280, 59794)
CUTOFF = PAGE[0]
EXTRA_START = {"get_periodo_abierto"}
# Diferencias conscientes NEXT (docs/INICIO_BLOCK_CLOSE.md): D-AN3 (caption sin cache de 60 s) y D-AN4 (titulo).
CAPTION_CERT = ("El tablero reutiliza datos durante hasta 60 segundos para mantener una navegación más fluida. Podés "
                "forzar la actualización con el botón.")


@functools.lru_cache(maxsize=1)
def _closure_inicio():
    """Mismo algoritmo que ``analisis_support._closure`` con el rango de la pagina Inicio."""
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
    seen, queue = set(), list(start | EXTRA_START)
    while queue:
        n = queue.pop()
        if n in seen or n == "st":
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
                valor_ = ast.literal_eval(node.value)
                runtime |= set(valor_ if isinstance(valor_, list) else valor_.keys())
            elif nombre in seen and nombre not in lits:
                try:
                    lits[nombre] = ast.literal_eval(node.value)
                except Exception:
                    pass
    code = compile(ast.Module(body=picked, type_ignores=[]), str(ENTRY), "exec")
    return code, frozenset(seen), lits, frozenset(cacheadas | (runtime & seen))


def certified_inicio(raw_conn, institution_id: int, department_id: int, **kw) -> dict:
    original = A._closure
    A._closure = _closure_inicio
    try:
        return A.certified_analisis(raw_conn, institution_id, department_id, **kw)
    finally:
        A._closure = original


motor = A.motor


@functools.lru_cache(maxsize=1)
def _bloque_pagina():
    tree = _tree(ENTRY)
    nodo = copy.deepcopy(next(n for n in tree.body if isinstance(n, ast.If) and n.lineno == PAGE[0]))
    nodo.orelse = []  # solo la rama "🏠 Inicio" (el resto de la cadena elif son otros modulos)
    assert nodo.body[-1].end_lineno < PAGE[1]
    return compile(ast.Module(body=[nodo], type_ignores=[]), str(ENTRY), "exec")


# ------------------------------------------------------------------------------------------ Streamlit que graba
def _md(texto: Any) -> str:
    return textwrap.dedent(str(texto)).strip()


class _Bloque:
    def __init__(self, rec: "Grabador", cierre: tuple | None = None):
        self.rec, self.cierre = rec, cierre

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.cierre:
            self.rec.ev.append(self.cierre)
        return False

    def __getattr__(self, nombre):  # columna usada como ``i1.metric(...)``
        return getattr(self.rec, nombre)


class Grabador:
    def __init__(self):
        self.ev: list[tuple] = []
        self.session_state = _St.session_state

    def __getattr__(self, nombre):
        return getattr(_St, nombre)

    def title(self, t, *a, **k):
        self.ev.append(("title", str(t)))

    def info(self, t, *a, **k):
        self.ev.append(("info", str(t)))

    def warning(self, t, *a, **k):
        self.ev.append(("warning", str(t)))

    def success(self, t, *a, **k):
        self.ev.append(("success", str(t)))

    def error(self, t, *a, **k):
        self.ev.append(("error", str(t)))

    def markdown(self, t, *a, **k):
        self.ev.append(("markdown", _md(t)))

    def caption(self, t, *a, **k):
        self.ev.append(("caption", str(t)))

    def write(self, t, *a, **k):
        self.ev.append(("write", str(t)))

    def divider(self, *a, **k):
        self.ev.append(("divider",))

    def progress(self, v, *a, **k):
        self.ev.append(("progress", round(float(v), 9)))

    def metric(self, label, value, *a, **k):
        self.ev.append(("metric", str(label), value if isinstance(value, str) else valor(value)))

    def button(self, label, *a, on_click=None, args=None, **k):
        destino = P.DESTINOS[args[0]] if args else None
        self.ev.append(("button", str(label), destino))
        return False

    def columns(self, spec, *a, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_Bloque(self) for _ in range(n)]

    def container(self, *a, **k):
        return _Bloque(self)

    def expander(self, label, expanded=False, *a, **k):
        self.ev.append(("expander", str(label), bool(expanded)))
        return _Bloque(self, ("/expander",))

    def dataframe(self, df, *a, **k):  # st.dataframe envuelto (Excel global v191/v200)
        self.ev.append(("dataframe", tabla(df), True))

    def _dataframe_original_deptit(self, df, *a, **k):  # renderer original (sin Excel)
        self.ev.append(("dataframe", tabla(df), False))

    def vega_lite_chart(self, df, spec, *a, **k):
        self.ev.append(("vega", {"data": {"values": tabla_registros(df)}, **spec}))


def pagina_certificada(ns: dict, periodo_abierto: Any, *, rol: str = "usuario_departamento",
                       departamento_scope: Any = 1) -> list[tuple]:
    """Ejecuta el bloque literal de la pagina sobre ``ns`` y devuelve los eventos grabados."""
    rec = Grabador()
    _St.session_state["tenant_scope_departamento_id"] = departamento_scope
    ns.update({"st": rec, "modulo": "🏠 Inicio", "periodo_abierto": periodo_abierto, "current_role": lambda: rol})
    exec(_bloque_pagina(), ns)
    return rec.ev


def _casos(c: dict) -> list[tuple]:
    if c["tabla"] is None:
        return [("caption", c["caption"])]
    return [("dataframe", c["tabla"], False), ("caption", c["caption"])]


def eventos_payload(p: dict) -> list[tuple]:
    """Misma secuencia de la pagina, construida desde el payload NEXT."""
    ev: list[tuple] = [("title", p["titulo"])]
    if p["estado"] == "institucional":
        i = p["institucional"]
        return ev + [("info", i["mensaje"]), ("button", i["boton"]["label"], i["boton"]["destino"])]
    if p["estado"] == "sin_periodo":
        s = p["sin_periodo"]
        return ev + [("warning", s["mensaje"]), ("button", s["boton"]["label"], s["boton"]["destino"]),
                     ("expander", s["ayuda"]["titulo"], s["ayuda"]["abierto"]), ("markdown", s["ayuda"]["texto"]),
                     ("/expander",)]
    t = p["tablero"]
    c = t["periodo"]
    ev.append(("markdown", c["linea"]))
    if c["progreso"] is not None:
        ev += [("progress", round(float(c["progreso"]), 9)), ("caption", c["caption_progreso"])]
    ev += [("button", c["actualizar"]["label"], None), ("caption", c["actualizar"]["caption"])]
    if t["error"]:
        return ev + [("error", t["error"])]
    s = t["situacion"]
    ev.append(("markdown", f"## {s['titulo']}"))
    for m in s["tarjetas"]:
        ev += [("metric", m["label"], m["valor"]), ("caption", m["caption"])]
    ev.append(("caption", s["caption_dotacion"]))
    for lista in s["listas"]:
        ev.append(("expander", lista["titulo"], False))
        if lista["vacio"]:
            ev.append(("caption", lista["vacio"]))
        for per in lista["personas"]:
            ev.append(("markdown", per["encabezado"]))
            for k, d in enumerate(per["designaciones"], start=1):
                ev.append(("markdown", d["linea"]))
                if d["funciones"]:
                    ev.append(("markdown", d["funciones"]))
                ev.append(("caption", d["caption"]))
                if k < len(per["designaciones"]):
                    ev.append(("divider",))
        ev.append(("/expander",))
    a = t["acciones"]
    ev.append(("markdown", f"## {a['titulo']}"))
    if a["vacio"]:
        ev.append(("success", a["vacio"]))
    for it in a["items"]:
        ev += [("markdown", f"### {it['icono']} {it['titulo']}"), ("write", it["detalle"]),
               ("expander", it["expander"], False), *_casos(it["casos"]), ("/expander",),
               ("button", it["boton"]["label"], it["boton"]["destino"])]
    sa = t["salud"]
    ev += [("markdown", f"## {sa['titulo']}"), ("caption", sa["caption"])]
    for ctl in sa["controles"]:
        ev += [("expander", ctl["titulo"], False), *_casos(ctl["casos"]), ("/expander",)]
    ev += [("divider",), ("markdown", sa["estado_general"]), ("progress", round(sa["porcentaje"] / 100.0, 9)),
           ("caption", sa["caption_indice"]), ("button", sa["boton"]["label"], sa["boton"]["destino"])]
    ind = t["indicadores"]
    ev.append(("markdown", f"## {ind['titulo']}"))
    for fila in ind["filas"]:
        for m in fila:
            ev.append(("metric", m["label"], m["valor"]))
            if m["caption"]:
                ev.append(("caption", m["caption"]))
    for gr in t["graficos"]:
        ev.append(("markdown", f"#### {gr['titulo']}"))
        ev.append(("info", gr["mensaje"]) if gr["vacio"] else ("vega", gr["spec"]))
        ev.append(("caption", gr["caption"]))
    v = t["vencimientos"]
    ev.append(("markdown", f"## {v['titulo']}"))
    if v["vacio"]:
        ev.append(("success", v["vacio"]))
    else:
        ev += [("dataframe", v["tabla"], v["excel"]), ("button", v["boton"]["label"], v["boton"]["destino"])]
    ay = t["ayuda"]
    return ev + [("expander", ay["titulo"], ay["abierto"]), ("markdown", ay["texto"]), ("/expander",)]


# 6A-B3 (D-UA1): DEPTIT no usa "escuelas" como categoria generica; la ayuda dice "unidades academicas".
AYUDA_UA_CERT, AYUDA_UA = "mantener escuelas, carreras,", "mantener unidades académicas, carreras,"


def normalizar_certificado(ev: list[tuple], titulo: str) -> list[tuple]:
    """Aplica al certificado las diferencias conscientes NEXT: D-AN4 (titulo), D-AN3 (caption de Actualizar) y
    D-UA1 (ayuda con "unidades académicas")."""
    out = []
    for e in ev:
        if e[0] == "title":
            e = ("title", titulo)
        elif e[0] == "caption" and e[1].endswith(CAPTION_CERT):
            e = ("caption", e[1][: -len(CAPTION_CERT)] + P.CAPTION_ACTUALIZAR)
        else:
            e = tuple(x.replace(AYUDA_UA_CERT, AYUDA_UA) if isinstance(x, str) else x for x in e)
        out.append(e)
    return out


def payload_motor(ns: dict, departamento: dict, periodo: Any) -> dict:
    """Payload de ``GET /inicio`` (estados sin_periodo / tablero) sobre un namespace, para un periodo dado."""
    out = {"titulo": P.titulo(departamento)}
    if not periodo:
        return {**out, "estado": "sin_periodo", "sin_periodo": P.sin_periodo()}
    pid = int(periodo["id"])
    hoy = ns["fecha_referencia_contexto_v182"](pid)
    datos = ns["_inicio_datos_tablero_cache"](pid, ns["_pg_current_inst_id"](), ns["_pg_current_dep_id"](), str(hoy))
    return {**out, "estado": "tablero",
            "tablero": {"periodo": P.encabezado(ns, periodo, hoy), "error": None, **P.tablero(ns, datos)}}


# ------------------------------------------------------------------------------------------ fixtures de servicio
def make_inicio(service, db_conn, **kwargs):
    from inicio.service import InicioService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return InicioService(None, service, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, **kwargs)


@pytest.fixture
def inicio(service, repo, db_conn):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    return make_inicio(service, db_conn)


@pytest.fixture
def http(service, inicio):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from inicio.routes import router as inicio_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(inicio_router)
    application.state.auth = service
    application.state.inicio = inicio
    return TestClient(application, base_url="http://localhost")
