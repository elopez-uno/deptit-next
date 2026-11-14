"""E4-03 — Docentes: pestaña "👥 Equipos docentes".

Diferencial contra B13-FIX02:
- PESTAÑA: el bloque LITERAL ``with tab7:`` del entry (l. 60828-60844) con un Streamlit que GRABA subheader, aviso,
  selector, tabla y caption, sobre las funciones efectivas del certificado (``certified_comisiones``: ``get_periodos``,
  ``get_periodo_abierto``, ``get_comisiones``, ``get_materia_comision``) y la ``get_equipos_docentes_periodo`` literal
  (l. 24248; el cache v199 no cambia el resultado).  Se compara con ``DocentesPeriodoService.equipos`` y
  ``POST /docentes/equipos``.
- ANOMALIA CERTIFICADA: el SELECT de asignaciones no tiene ``ORDER BY``; el orden fisico de las filas define el orden de
  ``equipo_docente`` (y el rol visible de un docente repetido).  Se demuestra con un UPDATE sin efecto (revertido) que
  mueve la tupla: el certificado cambia y NEXT cambia igual.
Datos reales de deptit_next_dev y fixtures sinteticas ``zznext``; todo se revierte.
"""
from __future__ import annotations

import ast
import copy
import re
from pathlib import Path

import pytest

from comisiones_support import FIXED_TODAY, certified_comisiones
from periodos_support import ENTRY, _tree, audit_store, db_conn, savepoint  # noqa: F401
from saas_support import auth_db, ids_por_rol, nueva_institucion, nuevo_departamento, sesion  # noqa: F401
from test_e4_01_contexto_periodo import periodo
from test_e4_02_plantel import _StPlantel, _ev, departamentos_con_periodos, make_plantel, superadmin_en

from analisis.pagina import tabla
from comisiones.lecturas import Lector
from comisiones.repository import ComisionesRepository
from docentes.service import DocentesError
from integraciones.docentes_periodo import (MSG_EQUIPOS_INFO, MSG_EQUIPOS_SIN_PERIODOS, MSG_EQUIPOS_VACIO,
                                            equipos_docentes_periodo)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning", "ignore::DeprecationWarning")

BACKEND = Path(__file__).resolve().parents[1]
TAB7 = 60828
READER = 24248


# ------------------------------------------------------------------------------------------ certificado
@pytest.fixture(scope="module")
def cert_code():
    arbol = _tree(ENTRY)
    nodo = next(n for n in ast.walk(arbol) if isinstance(n, ast.With) and n.lineno == TAB7)
    assert ast.unparse(nodo.items[0].context_expr) == "tab7"
    cuerpo = copy.deepcopy(nodo.body)
    assert ast.unparse(cuerpo[2]) == "df_periodos_eq = get_periodos()"
    fn = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.lineno == READER)
    assert fn.name == "get_equipos_docentes_periodo"
    # sin redefiniciones posteriores: la efectiva es la de l. 24248 (envuelta por el cache v199)
    assert [n.lineno for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == fn.name] == [READER]
    return (compile(ast.Module(body=[fn], type_ignores=[]), str(ENTRY), "exec"),
            compile(ast.Module(body=cuerpo, type_ignores=[]), str(ENTRY), "exec"))


def certificado(conn, inst, dep, cert_code) -> dict:
    ns = certified_comisiones(conn, inst, dep)
    exec(cert_code[0], ns)
    return ns


def certificado_tab(ns: dict, cert_code, elegir=None) -> _StPlantel:
    st = _StPlantel(elegir)
    st.session_state = ns["st"].session_state  # la lectura de materias consulta la version del catalogo (v196)
    ns["st"], ns["periodo_abierto"] = st, ns["get_periodo_abierto"]()  # global del entry (l. 26123)
    exec(cert_code[1], ns)
    return st


def comparar_tab(st: _StPlantel, out: dict, ns: dict):
    """Pestaña certificada grabada vs respuesta de NEXT (exacta: incluye el orden de ``equipo_docente``)."""
    assert [e[1] for e in _ev(st, "subheader")] == ["Equipos docentes por materia"]
    infos = [e[1] for e in _ev(st, "info")]
    assert out["info"] == infos[0] == MSG_EQUIPOS_INFO
    if _ev(st, "warning"):
        assert out["sin_periodos"] == _ev(st, "warning")[0][1] == MSG_EQUIPOS_SIN_PERIODOS
        assert out["periodos"] == [] and out["seleccionado"] is None and not _ev(st, "selectbox")
        return
    (_, label, opciones, index, key), = _ev(st, "selectbox")
    assert (label, key) == ("Seleccioná el período", "equipos_docentes_periodo")
    assert [p["nombre"] for p in out["periodos"]] == opciones
    assert {p["nombre"]: p["id"] for p in out["periodos"]} == {k: int(v) for k, v in ns["opciones_eq"].items()}
    assert out["seleccionado"]["id"] == int(ns["opciones_eq"][ns["periodo_eq_sel"]])
    if len(infos) == 2:  # sin equipos
        assert out["vacio"] == infos[1] == MSG_EQUIPOS_VACIO
        assert out["tabla"] is None and out["total_materias"] is None and not _ev(st, "dataframe")
    else:
        (_, df), = [e[:2] for e in _ev(st, "dataframe")]
        assert out["vacio"] is None and out["tabla"] == tabla(df)
        (_, caption), = _ev(st, "caption")
        assert caption == f"Total materias con equipo docente registrado: {out['total_materias']}"


def make_equipos(auth, db_conn):
    return make_plantel(auth, db_conn)


# ------------------------------------------------------------------------------------------ diferencial pestaña
def test_pestana_por_defecto_todos_los_departamentos(auth_db, db_conn, cert_code):
    svc = make_equipos(auth_db, db_conn)
    pares = departamentos_con_periodos(db_conn)
    assert len(pares) >= 6
    con_filas = 0
    for inst, dep in pares:
        ns = certificado(db_conn, inst, dep, cert_code)
        record, _ = superadmin_en(auth_db, db_conn, inst, dep)
        out = svc.equipos(record)
        comparar_tab(certificado_tab(ns, cert_code), out, ns)
        abierto = ns["get_periodo_abierto"]()
        if abierto:
            assert out["seleccionado"]["nombre"] == abierto["nombre"]  # por defecto: el periodo abierto
        con_filas += out["tabla"] is not None
    assert con_filas >= 4


def test_pestana_cada_periodo_actual_e_historico(auth_db, db_conn, cert_code):
    """Cada periodo de cada departamento (la funcion certificada no aplica foto al cierre: lee todas las asignaciones)."""
    svc = make_equipos(auth_db, db_conn)
    vistos = vacios = 0
    for inst, dep in departamentos_con_periodos(db_conn):
        ns = certificado(db_conn, inst, dep, cert_code)
        record, _ = superadmin_en(auth_db, db_conn, inst, dep)
        for p in svc.equipos(record)["periodos"]:
            out = svc.equipos(record, p["id"])
            assert out["seleccionado"] == p
            comparar_tab(certificado_tab(ns, cert_code, elegir=p["nombre"]), out, ns)
            vistos += 1
            vacios += out["tabla"] is None
    assert vistos >= 11 and vacios >= 1


def test_reader_exacto_y_columnas(db_conn, cert_code):
    ns = certificado(db_conn, 1, 1, cert_code)
    cert = ns["get_equipos_docentes_periodo"](9)
    next_ = equipos_docentes_periodo(Lector(ComisionesRepository(db_conn, 1, 1), FIXED_TODAY), 9)
    assert list(next_.columns) == list(cert.columns) == [
        "periodo", "codigo_materia", "asignatura", "materia_especifica", "carrera", "escuela", "plan_version",
        "comisiones", "turnos", "modalidades", "equipo_docente", "cantidad_comisiones", "cantidad_docentes",
        "horas_docentes_asignadas"]
    assert next_.dtypes.to_dict() == cert.dtypes.to_dict()
    assert tabla(next_) == tabla(cert) and len(cert) > 0
    # agrupacion por dictado real: varias comisiones por materia y ningun docente repetido en un equipo
    assert (cert["cantidad_comisiones"] > 1).any()
    for eq, n in zip(cert["equipo_docente"], cert["cantidad_docentes"]):
        partes = [x for x in eq.split(" | ") if x]
        assert len(partes) == n == len(set(partes))


def test_sintetico_ramas_de_agrupacion_y_vacios(auth_db, db_conn, cert_code):
    """Sin periodos; periodo sin comisiones; comisiones sin asignaciones; optativas separadas por materia especifica;
    docente repetido en dos comisiones (queda el primer rol); CUIL sin docente; docente solo con ``nombre``."""
    inst = nueva_institucion(db_conn, nombre="ZZNEXT E4-03 Instituto")
    dep = nuevo_departamento(db_conn, inst, nombre="ZZNEXT E4-03 Depto")
    svc = make_equipos(auth_db, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, inst, dep)
    ns = certificado(db_conn, inst, dep, cert_code)
    out = svc.equipos(record)
    assert out["sin_periodos"] == "Todavía no hay períodos registrados."
    comparar_tab(certificado_tab(ns, cert_code), out, ns)

    sin_com = periodo(db_conn, inst, dep, "2025-2", 2025, 2, "Cerrado")
    sin_asig = periodo(db_conn, inst, dep, "2026-1", 2026, 1, "Cerrado")
    actual = periodo(db_conn, inst, dep, "2026-2", 2026, 2, "Abierto")

    def materia(codigo, asignatura):
        return db_conn.execute(
            "INSERT INTO materias (institucion_id, codigo, asignatura, carrera, escuela, plan_version, estado, en_plan) "
            "VALUES (%s,%s,%s,'ZZ Carrera','ZZ Escuela','2020','Activa',1) RETURNING id",
            [inst, codigo, asignatura]).fetchone()[0]

    def comision(pid, mid, nombre, turno="", modalidad="", especifica=""):
        return db_conn.execute(
            "INSERT INTO comisiones (institucion_id, departamento_id, periodo_id, materia_id, nombre_comision, turno, "
            "sede, modalidad, estado, observaciones, materia_especifica) "
            "VALUES (%s,%s,%s,%s,%s,%s,'Sede ZZ',%s,'Activa','',%s) RETURNING id",
            [inst, dep, pid, mid, nombre, turno, modalidad, especifica]).fetchone()[0]

    def asignacion(cid, cuil, rol, horas):
        db_conn.execute(
            "INSERT INTO asignaciones_docentes_comision (institucion_id, departamento_id, comision_id, cuil, rol, "
            "horas_asignadas, estado, observaciones) VALUES (%s,%s,%s,%s,%s,%s,'Activa','')",
            [inst, dep, cid, cuil, rol, horas])

    def docente(cuil, apellido, nombres, nombre):
        db_conn.execute(
            "INSERT INTO docentes (institucion_id, departamento_id, cuil, nombre, apellido, nombres, estado, "
            "tipo_docente, observaciones) VALUES (%s,%s,%s,%s,%s,%s,'Activo','Propio','')",
            [inst, dep, cuil, nombre, apellido, nombres])

    alg, opt = materia("ZZ1", "ZZ Algebra"), materia("ZZ9", "Optativa I")
    comision(sin_asig, alg, "A")
    c1 = comision(actual, alg, "A", "mañana", "Presencial")
    c2 = comision(actual, alg, "B")
    c3 = comision(actual, opt, "", "noche", "", "Robótica")
    c4 = comision(actual, opt, "C", "", "Virtual", "Teatro")
    docente("20-90000001-1", "Zeta", "Uno", None)
    docente("20-90000002-2", None, None, "Solo Nombre")
    asignacion(c1, "20-90000001-1", "Adjunto", 6)
    asignacion(c2, "20-90000001-1", "JTP", 4)
    asignacion(c2, "20-90000002-2", None, None)
    asignacion(c3, "20-90000009-9", "Responsable", 3)

    for pid, nombre in [(actual, "2026-2"), (sin_asig, "2026-1"), (sin_com, "2025-2")]:
        ns = certificado(db_conn, inst, dep, cert_code)
        out = svc.equipos(record, pid)
        comparar_tab(certificado_tab(ns, cert_code, elegir=nombre), out, ns)
    assert svc.equipos(record, sin_com)["vacio"] == MSG_EQUIPOS_VACIO

    out = svc.equipos(record)
    assert out["seleccionado"]["id"] == actual and out["total_materias"] == 3
    filas = [dict(zip(out["tabla"]["columnas"], f)) for f in out["tabla"]["filas"]]
    alg_fila = next(f for f in filas if f["asignatura"] == "ZZ Algebra")
    assert alg_fila["comisiones"] == "A (mañana / Presencial) | B" and alg_fila["cantidad_comisiones"] == 2
    assert alg_fila["equipo_docente"] == "Zeta, Uno (Adjunto) | Solo Nombre" and alg_fila["cantidad_docentes"] == 2
    assert alg_fila["horas_docentes_asignadas"] == 10.0
    assert sorted(f["materia_especifica"] for f in filas if f["asignatura"] == "Optativa I") == ["Robótica", "Teatro"]
    rob = next(f for f in filas if f["materia_especifica"] == "Robótica")
    assert rob["comisiones"] == "noche" and rob["equipo_docente"] == "20-90000009-9 (Responsable)"
    sin = svc.equipos(record, sin_asig)
    assert sin["total_materias"] == 1 and dict(zip(sin["tabla"]["columnas"], sin["tabla"]["filas"][0]))[
        "equipo_docente"] == ""


def test_anomalia_orden_fisico_sin_order_by(auth_db, db_conn, cert_code):
    """El certificado no ordena las asignaciones: un UPDATE sin efecto mueve la tupla y cambia ``equipo_docente``.  NEXT
    replica el resultado en ambos estados (no se corrige); el contenido como multiconjunto no cambia."""
    inst, dep, pid = 1, 1, 9
    svc = make_equipos(auth_db, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, inst, dep)
    antes = certificado(db_conn, inst, dep, cert_code)["get_equipos_docentes_periodo"](pid)
    assert svc.equipos(record, pid)["tabla"] == tabla(antes)
    with db_conn.cursor() as cur:
        cur.execute("SELECT a.id, a.comision_id FROM asignaciones_docentes_comision a "
                    "JOIN comisiones co ON co.id = a.comision_id "
                    "WHERE co.periodo_id = %s AND a.institucion_id = %s AND a.departamento_id = %s", [pid, inst, dep])
        filas = cur.fetchall()
        multiples = {c for c in [f[1] for f in filas] if [f[1] for f in filas].count(c) >= 2}
        primera = next(a for a, c in filas if c in multiples)
        cur.execute("UPDATE asignaciones_docentes_comision SET rol = rol WHERE id = %s", [primera])
    despues = certificado(db_conn, inst, dep, cert_code)["get_equipos_docentes_periodo"](pid)
    assert tabla(despues) != tabla(antes)  # mismo dato, otro orden fisico: otra salida certificada
    assert svc.equipos(record, pid)["tabla"] == tabla(despues)
    for a, d in zip(antes["equipo_docente"], despues["equipo_docente"]):
        assert sorted(a.split(" | ")) == sorted(d.split(" | "))


# ------------------------------------------------------------------------------------------ roles, scope, validacion
def test_roles_y_scope(auth_db, db_conn):
    svc = make_equipos(auth_db, db_conn)
    ids = ids_por_rol(db_conn)
    record, _ = sesion(auth_db, ids["usuario_departamento"])
    out = svc.equipos(record)
    propio = auth_db.resolve_scope(record).department["id"]
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM periodos WHERE departamento_id <> %s ORDER BY id LIMIT 1", [propio])
        ajeno = cur.fetchone()[0]
    assert out["seleccionado"] is not None and ajeno not in {p["id"] for p in out["periodos"]}
    with pytest.raises(DocentesError) as exc:
        svc.equipos(record, ajeno)  # periodo de otro departamento: no existe en el scope
    assert exc.value.status == 404
    for malo in ("1", True, 1.5):
        with pytest.raises(DocentesError) as exc:
            svc.equipos(record, malo)
        assert exc.value.status == 422
    coord, _ = sesion(auth_db, ids["coordinador_institucional"])  # sin departamento: Docentes no aplica
    with pytest.raises(DocentesError) as exc:
        svc.equipos(coord)
    assert exc.value.status == 409


def test_sin_datos_de_otro_tenant(auth_db, db_conn, cert_code):
    """Un docente con el mismo CUIL en otro departamento no presta su nombre: el join a docentes es por tenant."""
    inst = nueva_institucion(db_conn, nombre="ZZNEXT E4-03 Tenant")
    dep_a = nuevo_departamento(db_conn, inst, nombre="ZZNEXT E4-03 A")
    dep_b = nuevo_departamento(db_conn, inst, nombre="ZZNEXT E4-03 B")
    pid = periodo(db_conn, inst, dep_a, "2026-2", 2026, 2, "Abierto")
    mid = db_conn.execute("INSERT INTO materias (institucion_id, codigo, asignatura, estado, en_plan) "
                          "VALUES (%s,'ZZT','ZZ Tenant','Activa',1) RETURNING id", [inst]).fetchone()[0]
    cid = db_conn.execute("INSERT INTO comisiones (institucion_id, departamento_id, periodo_id, materia_id, "
                          "nombre_comision, estado) VALUES (%s,%s,%s,%s,'T','Activa') RETURNING id",
                          [inst, dep_a, pid, mid]).fetchone()[0]
    db_conn.execute("INSERT INTO asignaciones_docentes_comision (institucion_id, departamento_id, comision_id, cuil, "
                    "rol, horas_asignadas, estado) VALUES (%s,%s,%s,'20-90000077-7','JTP',2,'Activa')",
                    [inst, dep_a, cid])
    db_conn.execute("INSERT INTO docentes (institucion_id, departamento_id, cuil, apellido, nombres, estado) "
                    "VALUES (%s,%s,'20-90000077-7','Ajeno','Nombre','Activo')", [inst, dep_b])
    svc = make_equipos(auth_db, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, inst, dep_a)
    out = svc.equipos(record)
    ns = certificado(db_conn, inst, dep_a, cert_code)
    comparar_tab(certificado_tab(ns, cert_code), out, ns)
    assert "Ajeno" not in str(out) and "20-90000077-7 (JTP)" in str(out)
    record_b, _ = superadmin_en(auth_db, db_conn, inst, dep_b)
    assert svc.equipos(record_b)["sin_periodos"] == MSG_EQUIPOS_SIN_PERIODOS


# ------------------------------------------------------------------------------------------ HTTP y seguridad
@pytest.fixture
def http(auth_db, db_conn):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from integraciones.routes import docentes_router

    app = FastAPI()
    app.state.auth = auth_db
    app.state.docentes_periodo = make_equipos(auth_db, db_conn)
    app.include_router(auth_router)
    app.include_router(docentes_router)
    return TestClient(app, base_url="http://localhost")


def test_http_csrf_sesion_y_respuesta_limpia(http, auth_db, db_conn):
    csrf = {"X-DEPTIT-Request": "1"}
    assert http.post("/docentes/equipos", json={}, headers=csrf).status_code == 401
    _, token = superadmin_en(auth_db, db_conn, 1, 1)
    http.cookies.set("deptit_session", token)
    assert http.post("/docentes/equipos", json={}).status_code == 403  # sin cabecera del proxy
    assert http.get("/docentes/equipos").status_code == 405
    r = http.post("/docentes/equipos", json={"periodo_id": None, "departamento_id": 2, "sql": "x"}, headers=csrf)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert set(r.json()) == {"info", "periodos", "seleccionado", "sin_periodos", "vacio", "tabla", "total_materias"}
    assert not re.search(r"(?i)select\s|traceback|psycopg|C:\\\\|password|salt", r.text)
    assert http.post("/docentes/equipos", json={"periodo_id": 999999}, headers=csrf).status_code == 404
    assert http.post("/docentes/equipos", json={"periodo_id": "9"}, headers=csrf).status_code == 422


# ------------------------------------------------------------------------------------------ arquitectura
def test_composicion_solo_lectura_y_sin_ciclos():
    fuente = (BACKEND / "integraciones" / "docentes_periodo.py").read_text(encoding="utf-8")
    codigo = re.sub(r'"""[\s\S]*?"""', "", fuente)
    codigo = "\n".join(linea.split("#")[0] for linea in codigo.splitlines())
    assert "SET TRANSACTION READ ONLY" in codigo
    assert not re.search(r"(?i)\b(INSERT|UPDATE|DELETE|AuditStore)\b", codigo)
    assert "ORDER BY" not in codigo.split("ASIGNACIONES_EQUIPOS_SQL = (")[1].split(")\n")[0]  # como el certificado
    for paquete in ("docentes", "comisiones", "materias", "periodos", "designaciones"):
        src = "\n".join(p.read_text(encoding="utf-8") for p in (BACKEND / paquete).glob("*.py"))
        assert not re.search(r"^\s*(from|import)\s+integraciones\b", src, re.M)
    docentes_src = "\n".join(p.read_text(encoding="utf-8") for p in (BACKEND / "docentes").glob("*.py"))
    assert not re.search(r"^\s*(from|import)\s+(comisiones|materias)\b", docentes_src, re.M)
