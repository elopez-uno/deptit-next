"""Soporte de E4-05 (Resumen docente): ejecuta la pestaña certificada LITERAL y la compara con NEXT seccion por seccion.

- ``certified_resumen``: namespace con el cierre transitivo de la pestaña (l. 60845-61197) ejecutado DESDE
  ``reference_fix02`` (no desde el motor vendorizado de NEXT), en el orden del entry y con las definiciones anteriores
  a l. 60845 (Streamlit ejecuta de arriba hacia abajo), sobre las conexiones certificadas del harness (inyector
  B12B/B12J efectivo).  Igual que ``certified_analisis``: tareas de sistema B12F anuladas, pilotos en ``off``, caches
  Streamlit por memoizacion; ademas el normalizador de posgrado de B12A (l. 59081) y el catalogo salarial (el sueldo
  del lado certificado lo calcula ``construir_tabla_sueldo_docente_v256`` literal).
- ``pagina``: el bloque LITERAL ``with tab5:`` (l. 60845) cortado antes de l. 61198 (la seccion Estado de consulta /
  Mensaje es E4-06), ejecutado con un Streamlit que GRABA cada llamada.
- ``stream_next``: la misma secuencia de llamadas reconstruida desde la respuesta de NEXT; las tablas se comparan con
  ``analisis.pagina.tabla`` y los dos bloques HTML (tarjeta, cronograma) por sus textos y celdas.
"""
from __future__ import annotations

import ast
import collections
import copy
import functools
import hashlib
import html
import json
import math
import re
import time
from datetime import timedelta
from io import BytesIO

import pandas as pd

from analisis import pagina as P
from comisiones_support import _ConnAislada, _instalar_execute_values
from designaciones_support import _Frames, _St
from materias_support import planes_injector
from periodos_support import ENTRY, _FixedDate, _tree
from comisiones_support import _FixedDateTime, _Session

PAGE = (60845, 61197)
CUTOFF = PAGE[0]
CORTE_E406 = 61198
EXCLUDE = {"st", "seleccionar_registro_desde_tabla", "guardar_estado_consulta_designacion",
           "generar_mensaje_consulta_designacion_docente", "mostrar_estado_consulta_designacion",
           "get_estado_consulta_designacion"}
# E4-06: la pestaña COMPLETA (l. 60845-61275) incluye la seccion Estado de consulta / Mensaje y su writer
PAGE_COMPLETA = (60845, 61275)
EXCLUDE_COMPLETA = frozenset({"st", "seleccionar_registro_desde_tabla"})


@functools.lru_cache(maxsize=2)
def _closure(page=PAGE, exclude=frozenset(EXCLUDE)):
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
    start = {x.id for x in ast.walk(tree) if isinstance(x, ast.Name) and page[0] <= getattr(x, "lineno", 0) <= page[1]}
    seen, queue = set(), list(start)
    while queue:
        n = queue.pop()
        if n in seen or n in exclude:
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


@functools.lru_cache(maxsize=2)
def pagina(completa: bool = False):
    """``with tab5:`` (l. 60845) literal, cortado en l. 61198 (sin la seccion E4-06) salvo ``completa`` (E4-06)."""
    nodo = copy.deepcopy(next(n for n in ast.walk(_tree(ENTRY)) if isinstance(n, ast.With) and n.lineno == PAGE[0]))
    assert ast.unparse(nodo.items[0].context_expr) == "tab5"
    if completa:
        return compile(ast.Module(body=nodo.body, type_ignores=[]), str(ENTRY), "exec")
    cortes = 0
    for padre in ast.walk(nodo):
        for campo in ("body", "orelse"):
            lista = getattr(padre, campo, None)
            if isinstance(lista, list):
                idx = next((i for i, s in enumerate(lista) if getattr(s, "lineno", 0) == CORTE_E406), None)
                if idx is not None:
                    assert ast.unparse(lista[idx]) == "st.divider()"
                    assert "Mensaje para consultar la designación" in ast.unparse(lista[idx + 1])
                    del lista[idx:]
                    cortes += 1
    assert cortes == 1
    return compile(ast.Module(body=nodo.body, type_ignores=[]), str(ENTRY), "exec")


def certified_resumen(raw_conn, institution_id: int, department_id: int, email: str = "info@test.local",
                      usuario: dict | None = None, completa: bool = False) -> dict:
    from deptit_refactor.b12a.posgrado import _normalizer_b12a
    from deptit_refactor.catalogs import salarios as cat_sal
    from deptit_refactor.security.legacy_write_actions import SYSTEM_WRITERS

    from periodos_support import FIXED_TODAY  # noqa: F401  (fecha fija del harness via _FixedDate)

    injector = planes_injector()
    frames = _Frames()
    tenant = {"kind": "tenant", "institucion_id": int(institution_id), "departamento_id": int(department_id)}

    def _pg_read_dataframe(sql, params=None):
        import psycopg
        with raw_conn.transaction():
            cur = psycopg.ClientCursor(raw_conn)
            cur.execute(sql, list(params or []))
            rows = cur.fetchall() if cur.description else []
            cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    _instalar_execute_values()
    code, names, lits, cacheadas = _closure(PAGE_COMPLETA, EXCLUDE_COMPLETA) if completa else _closure()
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
          "current_user": (lambda: dict(usuario)) if usuario is not None else
          (lambda: {"email": email, "rol": "usuario_departamento", "departamento_nombre": ""}),
          "pd": pd, "re": re, "json": json, "math": math, "hashlib": hashlib, "time": time, "functools": functools,
          "date": _FixedDate, "datetime": _FixedDateTime, "timedelta": timedelta, "BytesIO": BytesIO, "st": _St,
          "_scope_rendimiento_v191": lambda: ("postgresql://test", institution_id, department_id, 0),
          "_copiar_resultado_cache_v191": lambda x: x.copy() if hasattr(x, "copy") else x,
          "_version_dependencias_v200": lambda *a, **k: 0, "invalidar_cache_rendimiento_v191": noop,
          "_envolver_funcion_perf_v193": noop, "_versiones_scope_v199": lambda *a, **k: (0, 0, 0),
          "_cache_scope_proyectos_v127": lambda *a, **k: ("postgresql://test", institution_id, department_id, 0),
          "limpiar_cache_comisiones_operativas": noop, "_b12f_arranque_omitido": noop}
    for w, (categoria, _d) in SYSTEM_WRITERS.items():
        ns[w] = noop if categoria == "schema" else (lambda *a, **k: None)
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
    ns["_nivel_posgrado_salarial_normalizado_v256"] = _normalizer_b12a  # B12A (l. 59081)
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
    ns["_frames"] = frames
    return ns


# ------------------------------------------------------------------------------------------ grabacion
class _Parar(Exception):
    pass


class _Bloque:
    def __init__(self, st):
        self.st = st

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        return getattr(self.st, name)


class StResumen:
    def __init__(self, session_state, cuil, periodo_nombre):
        self.ev: list = []
        self.session_state = session_state
        self.cuil, self.periodo = cuil, periodo_nombre

    def columns(self, spec, **k):
        return [_Bloque(self) for _ in range(spec if isinstance(spec, int) else len(spec))]

    def container(self, *a, **k):
        return _Bloque(self)

    def expander(self, label, *a, **k):
        self.ev.append(("expander", label))
        return _Bloque(self)

    def text_input(self, label, *a, **k):
        self.ev.append(("text_input", label, k.get("placeholder")))
        return ""

    def radio(self, label, options, index=0, horizontal=False, key=None, **k):
        self.ev.append(("radio", label, list(options), index))
        forzado = getattr(self, "radio_forzado", None)
        return forzado if forzado is not None else list(options)[index]

    def button(self, label, *a, **k):
        self.ev.append(("button", label))
        return False

    def selectbox(self, label, options, index=0, key=None, **k):
        self.ev.append(("selectbox", label, list(options), index))
        return self.periodo if self.periodo is not None else list(options)[index]

    def stop(self):
        raise _Parar()

    def __getattr__(self, name):
        def grabar(*a, **k):
            self.ev.append((name,) + tuple(a))
        return grabar


def certificado(ns: dict, cuil: str, periodo_nombre=None, completa: bool = False, radio=None) -> list:
    st = StResumen(ns.get("_session_state", _St.session_state), cuil, periodo_nombre)
    st.radio_forzado = radio
    ns["st"] = st

    def seleccionar(df, key=None, id_col="cuil", columnas=None, renombres=None, titulo=None, **k):
        st.ev.append(("seleccion", titulo, [renombres[c] for c in columnas]))
        fila = df[df[id_col].astype(str) == str(cuil)]
        return fila.iloc[0]
    ns["seleccionar_registro_desde_tabla"] = seleccionar
    try:
        exec(pagina(completa), ns)
    except _Parar:
        pass
    return st.ev


def normalizar(ev: list) -> list:
    out = []
    for e in ev:
        k = e[0]
        if k == "dataframe":
            out.append(("dataframe", P.tabla(e[1])))
        elif k == "metric":
            out.append(("metric", e[1], e[2] if isinstance(e[2], str) else P.valor(e[2])))
        elif k == "vega_lite_chart":
            spec = dict(e[2])
            out.append(("torta", P.tabla_registros(e[1]), spec))
        elif k == "markdown" and "<div" in str(e[1]):
            out.append(("html", html_textos(e[1])) if "cron-v98" not in e[1] else ("cronograma", cronograma_html(e[1])))
        else:
            out.append(tuple(e))
    return out


def html_textos(s: str) -> list:
    """Textos visibles de un bloque HTML de la tarjeta (``<div style>texto</div>``) con su color si lo tiene."""
    out = []
    for estilo, texto in re.findall(r'<div style="([^"]*)">([^<]*(?:<br>[^<]*)*)</div>', s):
        color = re.search(r"color:(#[0-9a-f]{6})", estilo)
        out.append((texto.strip(), color.group(1) if color else None))
    return out


def cronograma_html(s: str) -> dict:
    dias = [html.unescape(x) for x in re.findall(r"<th>([^<]*)</th>", s)][1:]
    filas = []
    for hora, resto in re.findall(r'<tr><td class="hora">([^<]*)</td>(.*?)</tr>', s):
        celdas = []
        for titulo, contenido, vacia in re.findall(r'<td class="ocup" title="([^"]*)">(.*?)</td>|<td>()</td>', resto):
            if contenido or titulo:
                celdas.append({"labels": [html.unescape(x) for x in re.findall(r"<span>(.*?)</span>", contenido)],
                               "titulo": html.unescape(titulo)})
            else:
                celdas.append(None)
        filas.append({"hora": hora, "celdas": celdas})
    return {"dias": dias, "filas": filas}


# ------------------------------------------------------------------------------------------ secuencia NEXT
COLOR = {"positivo": "#15803d", "negativo": "#b91c1c", "neutro": "#374151"}


def _tabla_o_vacio(ev, s):
    if s["tabla"] is None:
        ev.append((s["vacio"]["tono"], s["vacio"]["texto"]))
    else:
        ev.append(("dataframe", s["tabla"]))


def stream_next(r: dict) -> list:
    """Secuencia de llamadas Streamlit equivalente a la respuesta de NEXT (desde "### Datos generales")."""
    s, per = r["secciones"], r["seleccionado"]["nombre"]
    ev = [("markdown", "### Datos generales")]
    d = s["datos_generales"]
    ev += [("markdown", f"#### 👤 {d['nombre']}"), ("caption", f"CUIL {d['cuil']}  •  Legajo {d['legajo']}"),
           ("markdown", "**Situación en el período**"), (d["situacion"]["tono"], d["situacion"]["texto"]),
           ("markdown", "#### 📅 Trayectoria"),
           ("markdown", f"**Inicio histórico:** {d['trayectoria']['inicio_historico']}"),
           ("markdown", f"**Última alta:** {d['trayectoria']['ultima_alta']}"),
           ("markdown", f"**Finalización / vencimiento:** {d['trayectoria']['finalizacion']}"),
           ("markdown", "#### ✉️ Contacto"), ("markdown", f"**Mail:** {d['contacto']['mail']}"),
           ("markdown", f"**Teléfono:** {d['contacto']['telefono']}"),
           ("markdown", "#### 🎓 Formación"), ("markdown", f"**Título de grado:** {d['formacion']['grado']}"),
           ("markdown", f"**Título de posgrado:** {d['formacion']['posgrado']}"),
           ("markdown", f"**Nivel adicional salarial:** {d['formacion']['nivel']}"),
           ("markdown", d["formacion"]["antiguedad"])]
    if d["observaciones"]:
        ev += [("markdown", "#### 📝 Observaciones"), ("write", d["observaciones"])]
    ev.append(("divider",))
    t = s["tarjeta"]
    if t["aviso_prestado"]:
        ev.append(("info", t["aviso_prestado"]))
    ev.append(("markdown", f"### {t['titulo']}"))
    if t["estado_designacion"]:
        ev.append(("warning", t["estado_designacion"]))
    if t["funciones_no_docentes"]:
        f = t["funciones_no_docentes"]
        ev += [("markdown", f"#### {f['titulo']}"), ("caption", f["caption"]), ("dataframe", f["tabla"])]
    ev.append(("html", [(t["cargos"]["label"], None), ("<br>".join(t["cargos"]["lineas"]), None),
                        (t["horas"]["label"], None), (t["horas"]["valor"], None),
                        (t["variacion"]["label"], None), (t["variacion"]["valor"], COLOR[t["variacion"]["tono"]]),
                        (t["variacion"]["caption"], None), (t["cambios"]["label"], None),
                        ("<br>".join(t["cambios"]["lineas"]), None)]))
    if t["evolucion"]:
        e = t["evolucion"]
        ev.append(("html", [(e["titulo"], None), (e["base"]["label"], None), (e["base"]["valor"], None),
                            (e["movimiento"]["label"], None), (e["movimiento"]["valor"], COLOR[e["movimiento"]["tono"]]),
                            (e["resultado"]["label"], None), (e["resultado"]["valor"], None)]))
    if t["compartido"]:
        ev.append(("warning", t["compartido"]))
    elif t["caption_origen"]:
        ev.append(("caption", t["caption_origen"]))
    if t["departamentos"] is not None:
        ev.append(("dataframe", t["departamentos"]))
    ev.append(("divider",))
    for clave in ("designaciones", "actos"):
        x = s[clave]
        ev += [("markdown", f"### {x['titulo']}"), ("caption", x["caption"])]
        _tabla_o_vacio(ev, x)
    su = s["sueldo"]
    ev.append(("markdown", f"### {su['titulo']}"))
    if su["vacio"]:
        ev.append((su["vacio"]["tono"], su["vacio"]["texto"]))
    else:
        ev += [("caption", su["caption"]), ("dataframe", su["tabla"]), ("metric", su["total"]["label"],
                                                                       su["total"]["valor"])]
    ev.append(("divider",))
    for clave in ("investigacion", "extension", "actividades"):
        x = s[clave]
        ev += [("markdown", f"### {x['titulo']}"), ("caption", x["caption"])]
        _tabla_o_vacio(ev, x)
        ev.append(("divider",))
    x = s["comisiones"]
    ev += [("markdown", f"### {x['titulo']}"), ("caption", x["caption"])]
    _tabla_o_vacio(ev, x)
    c = s["cronograma"]
    ev += [("markdown", f"### {c['titulo']}"), ("cronograma", {"dias": c["dias"], "filas": c["filas"]}),
           ("caption", c["caption"])]
    x = s["superposiciones"]
    ev.append(("markdown", f"### {x['titulo']}"))
    if x["tabla"] is None:
        ev.append((x["vacio"]["tono"], x["vacio"]["texto"]))
    else:
        ev += [("warning", x["aviso"]), ("dataframe", x["tabla"])]
    p = s["productividad"]
    ev += [("markdown", f"### {p['titulo']}"), ("caption", p["caption"])]
    ev += [("metric", m["label"], m["valor"]) for m in p["metricas"]]
    if p["detalle_no_lectivas"]:
        ev += [("expander", p["detalle_no_lectivas"]["titulo"]), ("dataframe", p["detalle_no_lectivas"]["tabla"])]
    if p["torta"]:
        spec = {k: v for k, v in p["torta"]["spec"].items() if k != "data"}
        ev.append(("torta", p["torta"]["spec"]["data"]["values"], spec))
    else:
        ev.append(("info", p["sin_torta"]))
    ev.append(("divider",))
    x = s["materias_historicas"]
    ev += [("markdown", f"### {x['titulo']}"), ("caption", x["caption"])]
    _tabla_o_vacio(ev, x)
    return ev


def _segmento_sueldo(ev: list) -> tuple[int, int]:
    """[inicio, fin) de la seccion "💰 Sueldo estimado" (titulo .. antes del divider)."""
    i = next(k for k, e in enumerate(ev) if e[0] == "markdown" and str(e[1]).startswith("### 💰 Sueldo estimado"))
    return i, next(k for k in range(i, len(ev)) if ev[k] == ("divider",))


def _segmento_tarjeta(ev: list) -> tuple[int, int]:
    """[inicio, fin) de la tarjeta del resumen: entre el divider que cierra "Datos generales" y el siguiente."""
    i = ev.index(("divider",)) + 1
    return i, next(k for k in range(i, len(ev)) if ev[k] == ("divider",))


def _hs(valor: str) -> float:
    return float(str(valor).replace("hs", "").replace("+", "").strip())


def tarjeta_consistente(r: dict) -> bool:
    """fix-horas-en-resumen-docente: la tarjeta NEXT corrige los Bugs A y B del certificado (fusión de designaciones
    iguales de departamentos distintos en periodos cerrados; evolución que ignoraba altas y bajas).  Solo se acepta
    si cumple la regla corregida y coincide con la tabla "Designaciones institucionales del docente" de la MISMA
    respuesta (casos funcionales: ``tests/test_resumen_horas.py``)."""
    s = r["secciones"]
    t = s["tarjeta"]
    e = t["evolucion"]
    base, var, fin = _hs(e["base"]["valor"]), _hs(e["movimiento"]["valor"]), _hs(e["resultado"]["valor"])
    assert abs(base + var - fin) < 1e-6, ("base + variación != final", base, var, fin)
    assert _hs(t["horas"]["valor"]) == fin
    assert t["variacion"]["valor"] == e["movimiento"]["valor"], "indicador superior distinto de la variación neta"
    deps = t["departamentos"]
    if deps is not None:
        assert abs(sum(float(f[2]) for f in deps["filas"]) - fin) < 1e-6
        tabla = s["designaciones"]["tabla"]
        assert tabla is not None, "la tarjeta informa departamentos que no están en Designaciones institucionales"
        col = tabla["columnas"].index("departamento")
        assert {f[0] for f in deps["filas"]} <= {f[col] for f in tabla["filas"]}
    assert bool(t["compartido"]) == (deps is not None and len(deps["filas"]) > 1)
    return True


def comparar(cert_ev: list, r: dict, verificar_sueldo=None) -> list:
    """Compara desde "### Datos generales"; devuelve la lista de secciones comparadas (por su encabezado).

    Etapa 5 / Tanda B (B1): la seccion "💰 Sueldo estimado" del Resumen NEXT CORRIGE las deudas H2 del certificado
    (Ad Honorem $0, solo Activas en el periodo no cerrado, antiguedad/posgrado de la ficha).  Si esa seccion difiere
    del certificado, la diferencia solo se acepta si ``verificar_sueldo(r)`` la valida contra el calculo independiente
    (``e5_b_support``); el resto del Resumen debe seguir identico."""
    norm = normalizar(cert_ev)
    i = norm.index(("markdown", "### Datos generales"))
    cabeza, cuerpo = norm[:i], norm[i:]
    # cabecera y selector certificados
    assert cabeza[0] == ("subheader", r["subtitulo"]) and cabeza[1] == ("info", r["info"])
    (_, label, opciones, index), = [e for e in cabeza if e[0] == "selectbox"]
    assert label == "Período a analizar" and [p["nombre"] for p in r["periodos"]] == opciones
    esperado = stream_next(r)
    # fix-horas-en-resumen-docente: la tarjeta puede diferir del certificado SOLO por la corrección (verificada).
    ti, tj = _segmento_tarjeta(cuerpo)
    ei, ej = _segmento_tarjeta(esperado)
    if cuerpo[ti:tj] != esperado[ei:ej]:
        assert tarjeta_consistente(r), "tarjeta distinta del certificado sin verificar"
        cuerpo = cuerpo[:ti] + esperado[ei:ej] + cuerpo[tj:]
    ci, cj = _segmento_sueldo(cuerpo)
    ni, nj = _segmento_sueldo(esperado)
    if cuerpo[ci:cj] != esperado[ni:nj]:
        assert verificar_sueldo is not None and verificar_sueldo(r), "sueldo distinto del certificado sin verificar"
        cuerpo = cuerpo[:ci] + esperado[ni:nj] + cuerpo[cj:]
    for n, (a, b) in enumerate(zip(cuerpo, esperado)):
        assert a == b, f"evento {n}: certificado={a!r}\nNEXT={b!r}"
    assert len(cuerpo) == len(esperado), (len(cuerpo), len(esperado), cuerpo[len(esperado):][:3])
    return [e[1] for e in esperado if e[0] == "markdown" and str(e[1]).startswith("### ")]
