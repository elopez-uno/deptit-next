"""Soporte de E4-04: ejecuta la pagina certificada "📚 Proyectos vigentes" (``render_proyectos_vigentes_v101``,
entry l. 33122) con un Streamlit que GRABA tabla, listado, metricas, leyenda e integrantes.

- Namespace: ``certified_investigacion`` / ``certified_extension`` (cierre transitivo de sus paginas, que incluye la
  render y el motor v256/v257/v258) con los mismos ajustes que ``certified_sueldos``: B12F en modo verificacion
  (``asegurar_esquema_sueldos_v256`` sin DDL), normalizador de posgrado de B12A y catalogo salarial.
- ``seleccionar_registro_desde_tabla`` (excluido del cierre por ser UI) graba la tabla y devuelve la fila elegida.
- La gestion de actos (v266/v267) es UI de escritura ajena a los costos: no se ejecuta.
"""
from __future__ import annotations

import pandas as pd

from extension_support import certified_extension
from investigacion_support import certified_investigacion

PAGINA = {
    "investigacion": ("get_proyectos_investigacion", "get_investigacion_docente", "inv",
                      "Instituto / Departamento responsable"),
    "extension": ("get_proyectos_extension", "get_extension_docente", "ext", "Área / Secretaría responsable"),
}


class _Bloque:
    def __init__(self, st, nombre):
        self.st, self.nombre = st, nombre

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        return getattr(self.st, name)


class StGrabador:
    """Streamlit que graba (tipo, args) en orden."""

    def __init__(self, session_state, elegir_id=None):
        self.ev: list = []
        self.session_state = session_state
        self.elegir_id = elegir_id

    def columns(self, spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_Bloque(self, f"col{i}") for i in range(n)]

    def container(self, *a, **k):
        return _Bloque(self, "container")

    def expander(self, label, *a, **k):
        self.ev.append(("expander", label))
        return _Bloque(self, "expander")

    def __getattr__(self, name):
        def grabar(*a, **k):
            self.ev.append((name,) + tuple(a))
        return grabar


def certificado(conn, tipo: str, inst: int, dep: int) -> dict:
    ns = (certified_investigacion if tipo == "investigacion" else certified_extension)(conn, inst, dep)
    from deptit_refactor.b12a.posgrado import _normalizer_b12a
    from deptit_refactor.catalogs import salarios as cat_sal
    ns["asegurar_esquema_sueldos_v256"] = lambda: None  # B12F: verificacion, sin DDL
    ns["_nivel_posgrado_salarial_normalizado_v256"] = _normalizer_b12a  # B12A (l. 59081)
    ns["_modo_designaciones_read_v282"] = lambda: "off"
    ns["_modo_teachers_read_v281"] = lambda: "off"
    for k in dir(cat_sal):
        if k.isupper() or k.startswith("_") and k[1:2].isupper():
            ns.setdefault(k, getattr(cat_sal, k))
    ns.pop("_render_gestion_actos_proyectos_masivo_v267", None)
    ns.pop("_render_gestion_acto_proyecto_v266", None)
    return ns


def render(ns: dict, tipo: str, elegir_id=None) -> dict:
    """Ejecuta la pagina (l. 65005-65021 / 65794-65810) y devuelve lo grabado."""
    proyectos, asignaciones, prefijo, etiqueta = PAGINA[tipo]
    st = StGrabador(ns["_session"], elegir_id)
    ns["st"] = st
    tabla = {}

    def seleccionar(df, key=None, id_col="id", columnas=None, renombres=None, titulo=None, **k):
        tabla["df"] = df[columnas].rename(columns=renombres)
        tabla["ids"] = [int(x) for x in df[id_col]]
        ids = tabla["ids"]
        elegido = elegir_id if elegir_id in ids else ids[0]
        return df[pd.to_numeric(df[id_col], errors="coerce").eq(elegido)].iloc[0]
    ns["seleccionar_registro_desde_tabla"] = seleccionar
    abierto = ns["get_periodo_abierto"]()
    if abierto is not None:
        df = ns[proyectos](solo_activos=True, periodo_id=abierto["id"])
    else:
        df = ns[proyectos](solo_activos=True)
        if not df.empty:
            df = df[df["situacion"].isin(["En ejecución", "Programado"])].copy()
    ns["render_proyectos_vigentes_v101"](df, ns[asignaciones], abierto, prefijo, etiqueta)
    return {"tabla": tabla, "ev": st.ev}


def salida_certificada(grab: dict) -> dict:
    """Extrae del grabado lo que muestra costos: columna de la tabla, listado, metrica, leyenda e integrantes."""
    ev = grab["ev"]
    out = {"tabla": None, "lista": None, "metrica": None, "leyenda": None, "integrantes": [], "info": None}
    infos = [e for e in ev if e[0] == "info"]
    if grab["tabla"].get("df") is None:
        out["info"] = infos[0][1] if infos else None
        return out
    t = grab["tabla"]["df"]
    out["tabla"] = dict(zip(grab["tabla"]["ids"], t["Costo total sueldos"]))
    out["columnas_tabla"] = list(t.columns)
    dfs = [e[1] for e in ev if e[0] == "dataframe" and "Costo total sueldos" in getattr(e[1], "columns", [])]
    if dfs:
        lista = dfs[-1]
        out["lista"] = list(lista["Costo total sueldos"])
        out["columnas_lista"] = list(lista.columns)
    out["metrica"] = next(e[2] for e in ev if e[0] == "metric" and e[1] == "Costo total en sueldos")
    out["leyenda"] = next(e[1] for e in ev if e[0] == "caption" and str(e[1]).startswith("Las horas totales"))
    # integrantes: cada uno abre con "**👤 ...**"; el caption de cargo (opcional) y el write tras "Costo total imputado"
    actual = None
    for i, e in enumerate(ev):
        if e[0] == "markdown" and str(e[1]).startswith("**👤 "):
            actual = {"salarial": None, "costo": None}
            out["integrantes"].append(actual)
            j = i + 2  # markdown, caption CUIL, [caption cargo]
            if ev[j][0] == "caption" and not str(ev[j][1]).startswith("Rol"):
                actual["salarial"] = ev[j][1]
        elif actual is not None and e[0] == "caption" and e[1] == "Costo total imputado":
            actual["costo"] = str(ev[i + 1][1]).strip("*")
    return out
