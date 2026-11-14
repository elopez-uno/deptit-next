"""E4-02 — Docentes: pestaña "📋 Plantel del período abierto" y estado operativo historico de la base maestra.

Diferencial contra B13-FIX02:
- PESTAÑA: el bloque LITERAL ``with tab1:`` del entry (l. 59813; se ejecutan ``df_periodos = get_periodos()`` y la rama
  ``if df_periodos.empty`` l. 59890-59925, sin el piloto v304 apagado por defecto) con un Streamlit que GRABA selector,
  avisos, tabla y caption, sobre las funciones efectivas del certificado (``certified_comisiones``: ``get_periodos``
  v280, ``get_periodo_abierto``, ``get_plantel_periodo`` v191 -> v183).  Se compara con ``POST /docentes/plantel``.
- BASE MAESTRA: ``get_docentes`` efectiva (v281 -> v191 -> v183 -> v182 -> base) con un periodo anterior abierto
  (fixture DENTRO de la transaccion del test: se abre el 2026-1 y se cierra el 2026-2; ROLLBACK al final) vs la base
  maestra de NEXT con el puerto ``plantel_cuiles`` conectado.
Datos reales de deptit_next_dev y fixtures sinteticas ``zznext``; todo se revierte.
"""
from __future__ import annotations

import ast
import copy
import re
from pathlib import Path

import pandas as pd
import pytest

from comisiones_support import FIXED_TODAY, certified_comisiones
from periodos_support import ENTRY, _tree, audit_store, db_conn, savepoint  # noqa: F401
from saas_support import auth_db, ids_por_rol, nueva_institucion, nuevo_departamento, sesion  # noqa: F401
from test_e4_01_contexto_periodo import periodo

from analisis.pagina import tabla
from auth import policy
from docentes.service import (ESTADO_HISTORICO_FUERA, ESTADO_HISTORICO_VIGENTE, MSG_HISTORICO_NO_DISPONIBLE,
                              DocentesError, DocentesService)
from integraciones.docentes_periodo import DocentesPeriodoService

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning", "ignore::DeprecationWarning")

BACKEND = Path(__file__).resolve().parents[1]
TAB1 = 59813


# ------------------------------------------------------------------------------------------ certificado: pestaña
class _StPlantel:
    """Streamlit que graba la pestaña; ``selectbox`` devuelve la opcion pedida (o la del indice por defecto)."""

    def __init__(self, elegir=None):
        self.elegir, self.ev = elegir, []

    def selectbox(self, label, options, index=0, key=None, **k):
        self.ev.append(("selectbox", label, list(options), index, key))
        return self.elegir if self.elegir is not None else list(options)[index]

    def __getattr__(self, name):
        def grabar(*a, **k):
            self.ev.append((name,) + tuple(x for x in a))
        return grabar


@pytest.fixture(scope="module")
def tab1_code():
    nodo = next(n for n in ast.walk(_tree(ENTRY)) if isinstance(n, ast.With) and n.lineno == TAB1)
    cuerpo = copy.deepcopy(nodo.body)
    assert ast.unparse(cuerpo[1]) == "df_periodos = get_periodos()"
    assert "_modo_period_creation_copy_designations_write_v304" in ast.unparse(cuerpo[2])  # piloto v304: excluido
    assert ast.unparse(cuerpo[-1].test) == "df_periodos.empty"
    return compile(ast.Module(body=[cuerpo[1], cuerpo[-1]], type_ignores=[]), str(ENTRY), "exec")


def certificado_tab(ns: dict, code, elegir=None) -> _StPlantel:
    st = _StPlantel(elegir)
    ns["st"], ns["periodo_abierto"] = st, ns["get_periodo_abierto"]()  # global del entry (l. 26123)
    exec(code, ns)
    return st


def _ev(st, kind):
    return [e for e in st.ev if e[0] == kind]


def sin_orden_detalle(t: dict) -> dict:
    """``detalle_designaciones`` sale de ``STRING_AGG`` sin ``ORDER BY`` (certificado l. 4701): el ORDEN de sus partes
    no es determinista entre ejecuciones (anomalia certificada, D-AO6).  Etapa 5 / Tanda C (C1): NEXT ordena por
    ``d.id``; el certificado no, asi que se comparan las partes como multiconjunto; todo lo demas, exacto."""
    if not t or "detalle_designaciones" not in t["columnas"]:
        return t
    j = t["columnas"].index("detalle_designaciones")
    filas = [list(f) for f in t["filas"]]
    for f in filas:
        if isinstance(f[j], str):
            f[j] = sorted(f[j].split(" | "))
    return {"columnas": t["columnas"], "filas": filas}


def comparar_tab(st: _StPlantel, out: dict, ns: dict):
    """Pestaña certificada grabada vs respuesta de NEXT."""
    if _ev(st, "warning"):
        assert out["sin_periodos"] == _ev(st, "warning")[0][1] and out["periodos"] == []
        return
    (_, label, opciones, index, key), = _ev(st, "selectbox")
    assert (label, key) == ("Seleccioná el período", "docentes_periodo_plantel")
    assert [p["nombre"] for p in out["periodos"]] == opciones
    assert {p["nombre"]: p["id"] for p in out["periodos"]} == {k: int(v) for k, v in ns["opciones_periodos"].items()}
    assert out["seleccionado"]["id"] == int(ns["opciones_periodos"][ns["periodo_plantel_sel"]])
    infos = [e[1] for e in _ev(st, "info")]
    assert out["info"] == infos[0]
    elegido = out["seleccionado"]["nombre"]
    assert elegido in opciones
    if len(infos) == 2:  # plantel vacio
        assert out["vacio"] == infos[1] and out["tabla"] is None and not _ev(st, "dataframe")
    else:
        (_, df), = [e[:2] for e in _ev(st, "dataframe")]
        assert out["vacio"] is None and sin_orden_detalle(out["tabla"]) == sin_orden_detalle(tabla(df))
        (_, caption), = _ev(st, "caption")
        assert caption == ("Total docentes activos con designaciones activas en el período seleccionado: "
                           f"{out['total_activos']}")


# ------------------------------------------------------------------------------------------ servicios NEXT
def make_plantel(auth, db_conn):
    docentes = DocentesService(None, auth, None, today=lambda: FIXED_TODAY, transaction=lambda: savepoint(db_conn))
    return DocentesPeriodoService(None, auth, docentes, today=lambda: FIXED_TODAY,
                                  transaction=lambda: savepoint(db_conn))


def superadmin_en(auth, db_conn, inst, dep):
    record, token = sesion(auth, ids_por_rol(db_conn)["superadmin"], **{policy.SUPERADMIN_INSTITUTION_KEY: inst,
                                                                         policy.DEPARTMENT_SCOPE_KEY: dep})
    return record, token


def departamentos_con_periodos(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT institucion_id, departamento_id FROM periodos ORDER BY 1, 2")
        return cur.fetchall()


# ------------------------------------------------------------------------------------------ diferencial pestaña
def test_pestana_por_defecto_todos_los_departamentos(auth_db, db_conn, tab1_code):
    svc = make_plantel(auth_db, db_conn)
    pares = departamentos_con_periodos(db_conn)
    assert len(pares) >= 6
    con_filas = 0
    for inst, dep in pares:
        ns = certified_comisiones(db_conn, inst, dep)
        record, _ = superadmin_en(auth_db, db_conn, inst, dep)
        out = svc.plantel(record)
        comparar_tab(certificado_tab(ns, tab1_code), out, ns)
        abierto = ns["get_periodo_abierto"]()
        if abierto:
            assert out["seleccionado"]["nombre"] == abierto["nombre"]  # por defecto: el periodo abierto
        con_filas += out["tabla"] is not None
    assert con_filas >= 5


def test_pestana_cada_periodo_actual_e_historico(auth_db, db_conn, tab1_code):
    """Cada periodo de cada departamento (actuales e historicos: el plantel historico aplica la foto v182/v183)."""
    svc = make_plantel(auth_db, db_conn)
    vistos = 0
    for inst, dep in departamentos_con_periodos(db_conn):
        ns = certified_comisiones(db_conn, inst, dep)
        record, _ = superadmin_en(auth_db, db_conn, inst, dep)
        for p in svc.plantel(record)["periodos"]:
            out = svc.plantel(record, p["id"])
            assert out["seleccionado"] == p
            comparar_tab(certificado_tab(ns, tab1_code, elegir=p["nombre"]), out, ns)
            vistos += 1
    assert vistos >= 11


def test_sin_periodos_vacio_y_nombres_repetidos(auth_db, db_conn, tab1_code):
    inst = nueva_institucion(db_conn, nombre="ZZNEXT E4-02 Instituto")
    dep = nuevo_departamento(db_conn, inst, nombre="ZZNEXT E4-02 Depto")
    svc = make_plantel(auth_db, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, inst, dep)
    ns = certified_comisiones(db_conn, inst, dep)
    out = svc.plantel(record)  # sin periodos: aviso certificado
    assert out["sin_periodos"] == "Todavía no hay períodos registrados. Creá uno en el módulo Períodos para ver el plantel."
    comparar_tab(certificado_tab(ns, tab1_code), out, ns)
    a = periodo(db_conn, inst, dep, "2026-1", 2026, 1, "Cerrado")
    b = periodo(db_conn, inst, dep, "2026-1", 2026, 1, "Cerrado")
    periodo(db_conn, inst, dep, "2026-2", 2026, 2, "Abierto")
    out = svc.plantel(record)
    comparar_tab(certificado_tab(ns, tab1_code), out, ns)
    assert [p["nombre"] for p in out["periodos"]] == ["2026-2", "2026-1"]
    # get_periodos ordena por anio, semestre, id DESC (b antes que a): el dict certificado se queda con el ultimo, a
    assert {p["nombre"]: p["id"] for p in out["periodos"]}["2026-1"] == a
    assert out["vacio"] == "No hay docentes con designaciones registradas en el período seleccionado."
    comparar_tab(certificado_tab(ns, tab1_code, elegir="2026-1"), svc.plantel(record, a), ns)
    with pytest.raises(DocentesError) as exc:
        svc.plantel(record, b)  # id tapado por el nombre repetido: no es una opcion del selector certificado
    assert exc.value.status == 404


# ------------------------------------------------------------------------------------------ roles, scope, validacion
def test_roles_y_scope(auth_db, db_conn):
    svc = make_plantel(auth_db, db_conn)
    ids = ids_por_rol(db_conn)
    record, _ = sesion(auth_db, ids["usuario_departamento"])
    out = svc.plantel(record)
    propio = auth_db.resolve_scope(record).department["id"]
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM periodos WHERE departamento_id <> %s ORDER BY id LIMIT 1", [propio])
        ajeno = cur.fetchone()[0]
    assert ajeno not in {p["id"] for p in out["periodos"]}
    with pytest.raises(DocentesError) as exc:
        svc.plantel(record, ajeno)  # periodo de otro departamento: no existe en el scope
    assert exc.value.status == 404
    for malo in ("1", True, 1.5):
        with pytest.raises(DocentesError) as exc:
            svc.plantel(record, malo)
        assert exc.value.status == 422
    coord, _ = sesion(auth_db, ids["coordinador_institucional"])  # sin departamento: Docentes no aplica
    with pytest.raises(DocentesError) as exc:
        svc.plantel(coord)
    assert exc.value.status == 409


# ------------------------------------------------------------------------------------------ base maestra historica
def test_base_maestra_estado_historico_v183(auth_db, db_conn):
    """Periodo anterior abierto (fixture revertida): etiqueta v183 por CUIL = certificado; sin puerto, texto previo."""
    inst, dep, viejo, actual = 1, 1, 5, 9
    with db_conn.cursor() as cur:
        cur.execute("SELECT id, estado FROM periodos WHERE id IN (%s, %s) AND departamento_id = %s ORDER BY id",
                    [viejo, actual, dep])
        assert cur.fetchall() == [(viejo, "Cerrado"), (actual, "Abierto")]
        cur.execute("UPDATE periodos SET estado = CASE WHEN id = %s THEN 'Abierto' ELSE 'Cerrado' END "
                    "WHERE id IN (%s, %s)", [viejo, viejo, actual])
    ns = certified_comisiones(db_conn, inst, dep)
    cert = ns["get_docentes"]()
    cert_estado = {str(r["cuil"]): r["estado_periodo_abierto"] for _, r in cert.iterrows()}
    assert set(cert_estado.values()) == {ESTADO_HISTORICO_VIGENTE, ESTADO_HISTORICO_FUERA}

    plantel = make_plantel(auth_db, db_conn)
    con_puerto = DocentesService(None, auth_db, None, today=lambda: FIXED_TODAY, transaction=lambda: savepoint(db_conn),
                                 plantel_cuiles=plantel.plantel_cuiles)
    record, _ = superadmin_en(auth_db, db_conn, inst, dep)
    filas = con_puerto.overview(record)["docentes"]
    assert {str(f["cuil"]): f["estado_periodo_abierto"] for f in filas} == cert_estado
    assert con_puerto.overview(record)["historico"] is True
    # todos los caminos que arman la base maestra usan el puerto (misma huella en lecturas y writers)
    fila = filas[0]
    assert con_puerto.ficha(record, fila["cuil"])["docente"]["huella"] == fila["huella"]

    sin_puerto = DocentesService(None, auth_db, None, today=lambda: FIXED_TODAY, transaction=lambda: savepoint(db_conn))
    assert {f["estado_periodo_abierto"] for f in sin_puerto.overview(record)["docentes"]} == {MSG_HISTORICO_NO_DISPONIBLE}


def test_base_maestra_no_historica_sin_cambios(auth_db, db_conn):
    """Con el periodo actual abierto el puerto no se consulta y las filas son las de siempre."""
    llamadas = []

    def espia(*a):
        llamadas.append(a)
        return []

    record, _ = superadmin_en(auth_db, db_conn, 1, 1)
    con = DocentesService(None, auth_db, None, today=lambda: FIXED_TODAY, transaction=lambda: savepoint(db_conn),
                          plantel_cuiles=espia)
    sin = DocentesService(None, auth_db, None, today=lambda: FIXED_TODAY, transaction=lambda: savepoint(db_conn))
    assert con.overview(record)["docentes"] == sin.overview(record)["docentes"] and llamadas == []


# ------------------------------------------------------------------------------------------ HTTP y seguridad
@pytest.fixture
def http(auth_db, db_conn):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from integraciones.routes import docentes_router

    app = FastAPI()
    app.state.auth = auth_db
    app.state.docentes_periodo = make_plantel(auth_db, db_conn)
    app.include_router(auth_router)
    app.include_router(docentes_router)
    return TestClient(app, base_url="http://localhost")


def test_http_csrf_sesion_y_respuesta_limpia(http, auth_db, db_conn):
    csrf = {"X-DEPTIT-Request": "1"}
    assert http.post("/docentes/plantel", json={}, headers=csrf).status_code == 401
    _, token = superadmin_en(auth_db, db_conn, 1, 1)
    http.cookies.set("deptit_session", token)
    assert http.post("/docentes/plantel", json={}).status_code == 403  # sin cabecera del proxy
    assert http.get("/docentes/plantel").status_code == 405
    r = http.post("/docentes/plantel", json={"periodo_id": None, "departamento_id": 2, "sql": "x"}, headers=csrf)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert set(r.json()) == {"periodos", "seleccionado", "sin_periodos", "info", "vacio", "tabla", "total_activos"}
    assert not re.search(r"(?i)select\s|traceback|psycopg|C:\\\\|password|salt", r.text)
    assert http.post("/docentes/plantel", json={"periodo_id": 999999}, headers=csrf).status_code == 404
    assert http.post("/docentes/plantel", json={"periodo_id": "9"}, headers=csrf).status_code == 422


# ------------------------------------------------------------------------------------------ arquitectura
def test_composicion_solo_lectura_y_sin_ciclos():
    fuente = (BACKEND / "integraciones" / "docentes_periodo.py").read_text(encoding="utf-8")
    codigo = re.sub(r'"""[\s\S]*?"""', "", fuente)
    assert "SET TRANSACTION READ ONLY" in codigo
    assert not re.search(r"(?i)\b(INSERT|UPDATE|DELETE|AuditStore)\b", codigo)
    docentes_src = "\n".join(p.read_text(encoding="utf-8") for p in (BACKEND / "docentes").glob("*.py"))
    assert not re.search(r"^\s*(from|import)\s+(comisiones|integraciones)\b", docentes_src, re.M)
