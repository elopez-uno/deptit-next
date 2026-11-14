"""E4-04 — Costos salariales de "📚 Proyectos vigentes" en Investigación y Extensión.

Diferencial contra B13-FIX02: la pagina LITERAL (``render_proyectos_vigentes_v101`` l. 33122 con el motor v256/v257/v258,
ejecutada en el namespace certificado de cada modulo; ver ``e4_04_support``) vs NEXT (``CostosProyectosService`` +
lecturas publicas de Investigacion/Extension).  Compara la columna "Costo total sueldos" de la tabla y del listado
completo, la metrica "Costo total en sueldos", la leyenda de calculo y, por integrante, cargo · dedicacion · condicion y
"Costo total imputado".  P-04: permiso demostrado por AST del certificado y por la matriz de decisiones de NEXT.
Datos reales de deptit_next_dev y fixtures sinteticas ``zznext``; todo se revierte.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from e4_04_support import certificado, render, salida_certificada
from periodos_support import ENTRY, FIXED_TODAY, _tree, audit_store, db_conn, savepoint  # noqa: F401
from saas_support import auth_db, ids_por_rol, nueva_institucion, nuevo_departamento, sesion  # noqa: F401
from test_e4_01_contexto_periodo import periodo
from test_e4_02_plantel import departamentos_con_periodos, superadmin_en

from auth import policy
from extension.service import ExtensionService
from integraciones.costos_proyectos import (ADVERTENCIA_ESTIMACION, ETIQUETA_ESTIMACION, CostosError,
                                            CostosProyectosService, leyenda_costo)
from investigacion.service import InvestigacionService
from sueldos.service import SueldosService

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning", "ignore::DeprecationWarning")

BACKEND = Path(__file__).resolve().parents[1]
TIPOS = ("investigacion", "extension")


def servicios(auth, audit_store, db_conn):
    kw = dict(today=lambda: FIXED_TODAY, transaction=lambda: savepoint(db_conn))
    inv = InvestigacionService(None, auth, audit_store, **kw)
    ext = ExtensionService(None, auth, audit_store, **kw)
    sue = SueldosService(None, auth, audit_store, **kw)
    return CostosProyectosService(sue, inv, ext), {"investigacion": inv, "extension": ext}


def salida_next(costos: CostosProyectosService, modulos: dict, record, tipo: str, proyecto_id: int) -> dict:
    """Lo que la UI de NEXT muestra, armado con las respuestas (sin logica: cruce por id)."""
    c = costos.costos(record, tipo)
    vig = modulos[tipo].vigentes(record)
    por_id = {p["proyecto_id"]: p for p in c["proyectos"]}
    assert [p["proyecto_id"] for p in c["proyectos"]] == [int(f["id"]) for f in vig["filas"]]
    ficha = modulos[tipo].ficha(record, {"proyecto_id": proyecto_id})
    integ = {i["asignacion_id"]: i for i in c["integrantes"]}
    integrantes = []
    for i in ficha["integrantes"]:
        d = integ.get(i["id"])
        integrantes.append({"salarial": d["detalle_salarial"] if d else None,
                            "costo": d["costo"] if d else c["sin_costo"]})
    return {"tabla": {p["proyecto_id"]: p["costo_tabla"] for p in c["proyectos"]},
            "lista": [p["costo_tabla"] for p in c["proyectos"]],
            "metrica": por_id[proyecto_id]["costo_ficha"], "leyenda": por_id[proyecto_id]["leyenda"],
            "integrantes": integrantes, "respuesta": c}


def comparar(cert: dict, nxt: dict):
    assert cert["columnas_tabla"][6] == "Costo total sueldos"
    assert cert["columnas_lista"][5] == "Costo total sueldos"
    assert nxt["tabla"] == cert["tabla"]
    assert nxt["lista"] == cert["lista"]
    assert nxt["metrica"] == cert["metrica"]
    assert nxt["leyenda"] == cert["leyenda"]
    assert nxt["integrantes"] == cert["integrantes"]


def _elegidos(c: dict) -> list[int]:
    """Por defecto (primera fila) + el proyecto con mas integrantes con costo + uno en $ 0,00 si existe."""
    ids = [p["proyecto_id"] for p in c["proyectos"]]
    out = [ids[0]]
    cuenta = {}
    for i in c["integrantes"]:
        cuenta[i["proyecto_id"]] = cuenta.get(i["proyecto_id"], 0) + 1
    if cuenta:
        out.append(max(cuenta, key=lambda k: (cuenta[k], -k)))
    cero = [p["proyecto_id"] for p in c["proyectos"] if p["costo_tabla"] == "$ 0,00"]
    if cero:
        out.append(cero[0])
    return list(dict.fromkeys(out))


# ------------------------------------------------------------------------------------------ diferencial
@pytest.mark.parametrize("tipo", TIPOS)
def test_diferencial_todos_los_departamentos(auth_db, audit_store, db_conn, tipo):
    costos, modulos = servicios(auth_db, audit_store, db_conn)
    vistos = con_integrantes = con_cero = 0
    for inst, dep in departamentos_con_periodos(db_conn):
        record, _ = superadmin_en(auth_db, db_conn, inst, dep)
        c = costos.costos(record, tipo)
        assert c["estimacion"] == {"etiqueta": ETIQUETA_ESTIMACION, "advertencia": ADVERTENCIA_ESTIMACION}
        ns = certificado(db_conn, tipo, inst, dep)
        if not c["proyectos"]:
            sal = salida_certificada(render(ns, tipo))
            assert sal["tabla"] is None and sal["info"] == "No hay proyectos vigentes para el período actual."
            continue
        for pid in _elegidos(c):
            cert = salida_certificada(render(ns, tipo, pid))
            nxt = salida_next(costos, modulos, record, tipo, pid)
            comparar(cert, nxt)
            vistos += 1
            con_integrantes += any(i["salarial"] for i in nxt["integrantes"])
            con_cero += nxt["metrica"] == "$ 0,00"
    assert vistos >= 6 and con_integrantes >= 1 and con_cero >= 1


@pytest.mark.parametrize("tipo,total,n", [("investigacion", 1301759612.16, 139), ("extension", 87148362.24, 17)])
def test_total_de_referencia_2026_2_al_centavo(auth_db, audit_store, db_conn, tipo, total, n):
    """Mismo total que el bloque Sueldos (§8): la composicion reutiliza su motor sin duplicarlo."""
    costos, _ = servicios(auth_db, audit_store, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, 1, 1)
    c = costos.costos(record, tipo)
    assert len(c["integrantes"]) == n
    suma = sum(float(i["costo"].replace("$ ", "").replace(".", "").replace(",", ".")) for i in c["integrantes"])
    assert round(suma, 2) == total


def test_varios_cargos_condicion_mixta_y_cero_horas(auth_db, audit_store, db_conn):
    costos, _ = servicios(auth_db, audit_store, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, 1, 1)
    det = [i["detalle_salarial"] for i in costos.costos(record, "investigacion")["integrantes"]]
    assert any(" + " in d for d in det)                                   # varios cargos
    assert any(d.endswith("Mixta (rentada + Ad Honorem)") for d in det)  # Ad Honorem fuera del costo
    assert any(i["costo"] == "$ 0,00" for i in costos.costos(record, "investigacion")["integrantes"])


def test_sin_periodo_abierto_y_sin_escala(auth_db, audit_store, db_conn):
    """Departamento sin periodos: sin proyectos.  Leyenda sin escala (rama certificada l. 33465)."""
    inst = nueva_institucion(db_conn, nombre="ZZNEXT E4-04 Instituto")
    dep = nuevo_departamento(db_conn, inst, nombre="ZZNEXT E4-04 Depto")
    costos, _ = servicios(auth_db, audit_store, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, inst, dep)
    for tipo in TIPOS:
        c = costos.costos(record, tipo)
        assert c["proyectos"] == [] and c["integrantes"] == []
    periodo(db_conn, inst, dep, "2026-2", 2026, 2, "Abierto")
    assert costos.costos(record, "investigacion")["proyectos"] == []
    assert leyenda_costo(None, 12).endswith(
        "No hay una escala salarial aplicable para calcular el costo total. Las designaciones Ad Honorem imputan $0.")


# ------------------------------------------------------------------------------------------ P-04
def test_p04_el_certificado_no_autoriza_lecturas_con_b10():
    """En el entry no hay ``decide(`` ni chequeos de rol/permiso en la render ni en el motor: los costos se ven con la
    pagina del modulo (modulos visibles l. 52131-52140: Investigacion, Extension y Sueldos van juntos)."""
    fuente = ENTRY.read_text(encoding="utf-8")
    assert "decide(" not in fuente
    arbol = _tree(ENTRY)
    for nombre in ("render_proyectos_vigentes_v101", "calcular_costos_asignaciones_proyecto_v257"):
        nodo = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == nombre)
        llamadas = {ast.unparse(x.func) for x in ast.walk(nodo) if isinstance(x, ast.Call)}
        assert not [c for c in llamadas if re.search(r"(?i)permis|current_role|rol\b|autoriz|sueldos\.read", c)]


def test_p04_matriz_de_decisiones():
    """Toda sesion que puede leer Investigacion/Extension tambien puede leer Sueldos: ``sueldos.read`` no agrega una
    condicion.  La unica diferencia (sin departamento) es moot: sin departamento no hay modulo ni costos."""
    acciones = {t: policy.Action(t, policy.OP_READ, policy.SCOPE_DEPARTMENT) for t in TIPOS}
    sueldos = policy.Action("sueldos", policy.OP_READ, policy.SCOPE_INSTITUTION)
    roles = (policy.ROLE_SUPERADMIN, policy.ROLE_COORDINADOR, policy.ROLE_DEPARTAMENTO, policy.ROLE_SOLO_LECTURA)
    for rol in roles:
        for modo in sorted(policy.KNOWN_ACCESS_MODES):
            for dep in (1, None):
                a = policy.ActorContext(authenticated=True, role=rol, access_mode=modo, user_ref="x", institution_id=1,
                                        department_id=dep, home_institution_id=1, home_department_id=dep, scope_mode="")
                for t, accion in acciones.items():
                    if policy.decide(a, accion).allowed:
                        assert policy.decide(a, sueldos).allowed and dep is not None


def test_p04_roles_y_scope(auth_db, audit_store, db_conn):
    """El costo se autoriza igual que la lectura del modulo (``reader``)."""
    costos, modulos = servicios(auth_db, audit_store, db_conn)
    ids = ids_por_rol(db_conn)
    for rol in ("usuario_departamento", "solo_lectura"):
        if rol not in ids:
            continue
        record, _ = sesion(auth_db, ids[rol])
        for t in TIPOS:
            modulos[t].reader(record)
            assert costos.costos(record, t)["estimacion"]["etiqueta"] == ETIQUETA_ESTIMACION
    coord, _ = sesion(auth_db, ids["coordinador_institucional"])  # sin departamento: el modulo no aplica
    for t in TIPOS:
        with pytest.raises(CostosError) as exc:
            costos.costos(coord, t)
        assert exc.value.status == 409
    record, _ = superadmin_en(auth_db, db_conn, 1, 2)
    otro = {p["proyecto_id"] for p in costos.costos(record, "investigacion")["proyectos"]}
    assert otro == {int(f["id"]) for f in modulos["investigacion"].vigentes(record)["filas"]}


def test_p04_modo_comercial_bloqueado(auth_db, audit_store, db_conn, monkeypatch):
    costos, _ = servicios(auth_db, audit_store, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, 1, 1)
    monkeypatch.setattr(policy, "commercial_access_mode", lambda *a, **k: policy.ACCESS_BLOCKED)
    with pytest.raises(CostosError) as exc:
        costos.costos(record, "investigacion")
    assert exc.value.status == 403


# ------------------------------------------------------------------------------------------ HTTP y seguridad
@pytest.fixture
def http(auth_db, audit_store, db_conn):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from integraciones.routes import extension_router, investigacion_router

    costos, _ = servicios(auth_db, audit_store, db_conn)
    app = FastAPI()
    app.state.auth = auth_db
    app.state.costos_proyectos = costos
    app.include_router(auth_router)
    app.include_router(investigacion_router)
    app.include_router(extension_router)
    return TestClient(app, base_url="http://localhost")


@pytest.mark.parametrize("tipo", TIPOS)
def test_http_csrf_sesion_y_respuesta_limpia(http, auth_db, db_conn, tipo):
    csrf = {"X-DEPTIT-Request": "1"}
    assert http.post(f"/{tipo}/costos", json={}, headers=csrf).status_code == 401
    _, token = superadmin_en(auth_db, db_conn, 1, 1)
    http.cookies.set("deptit_session", token)
    assert http.post(f"/{tipo}/costos", json={}).status_code == 403  # sin cabecera del proxy
    assert http.get(f"/{tipo}/costos").status_code == 405
    r = http.post(f"/{tipo}/costos", json={"departamento_id": 2, "institucion_id": 9, "sql": "x"}, headers=csrf)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert set(r.json()) == {"estimacion", "proyectos", "integrantes", "sin_costo"}
    assert not re.search(r"(?i)select\s|traceback|psycopg|C:\\\\|password|salt", r.text)
    assert not re.search(r"\b\d{2}-?\d{8}-?\d\b", r.text)  # sin CUIL en la respuesta de costos


# ------------------------------------------------------------------------------------------ arquitectura
def test_composicion_solo_lectura_y_sin_ciclos():
    fuente = (BACKEND / "integraciones" / "costos_proyectos.py").read_text(encoding="utf-8")
    codigo = re.sub(r'"""[\s\S]*?"""', "", fuente)
    assert not re.search(r"(?i)\b(INSERT|UPDATE|DELETE|AuditStore|_op\(|commit)\b", codigo)
    for paquete in ("investigacion", "extension", "sueldos"):
        src = "\n".join(p.read_text(encoding="utf-8") for p in (BACKEND / paquete).glob("*.py"))
        assert not re.search(r"^\s*(from|import)\s+integraciones\b", src, re.M)
    for paquete in ("investigacion", "extension"):
        src = "\n".join(p.read_text(encoding="utf-8") for p in (BACKEND / paquete).glob("*.py"))
        assert not re.search(r"^\s*(from|import)\s+sueldos\b", src, re.M)  # sueldos -> investigacion ya existe
