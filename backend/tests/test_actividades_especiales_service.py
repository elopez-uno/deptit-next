"""Servicio y HTTP de Actividades Especiales sobre deptit_next_dev con ROLLBACK: lecturas de las 5 pestañas sin
escrituras, permisos B10 por rol (eliminaciones solo superadmin, coordinador y solo lectura sin escritura, otro
departamento), B12H (DENIED que corta el bucle / FAILED / auditoria que falla), B12D, B12I capa U sin lock de capa T,
lectura institucional G5, ausencia de movimientos y de funciones inexistentes (Excel, actos, costos, horas) y contrato
HTTP.  Usuarios del FakeRepo."""

from __future__ import annotations

import psycopg
import pytest

import audit
from actividades_especiales import service as S
from actividades_especiales.service import ActividadesError, ActividadesService
from actividades_support import (  # noqa: F401  (fixtures)
    actividades, audit_rows, audit_store, db_conn, http, session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "DELETE ", "Traceback", "psycopg", "institucion_id =")


@pytest.fixture
def records(service, repo):
    out = {"dep": session_for(service, repo, 3)[0], "lector": session_for(service, repo, 7)[0],
           "coord": session_for(service, repo, 2)[0], "dep2": session_for(service, repo, 6)[0]}
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, 1, False)
    out["super"] = sup
    coord_dep = session_for(service, repo, 2)[0]
    service.set_context(coord_dep, 1, 1, False)
    out["coord_dep"] = coord_dep
    return out


def _contar(db_conn):
    return db_conn.execute(
        "SELECT (SELECT count(*) FROM actividades_especiales), (SELECT count(*) FROM actividad_especial_docente), "
        "(SELECT count(*) FROM movimientos), "
        "(SELECT md5(string_agg(md5(a::text), '' ORDER BY a.id)) FROM actividades_especiales a), "
        "(SELECT md5(string_agg(md5(p::text), '' ORDER BY p.id)) FROM actividad_especial_docente p), "
        "(SELECT count(*) FROM b12h_audit_log)").fetchone()


def _abierto(svc, rec):
    return svc.overview(rec)["abierto"]["id"]


def _crear(svc, rec, titulo="ZZNEXT svc"):
    ov = svc.overview(rec)
    return svc.crear(rec, {"periodo_id": ov["abierto"]["id"], "titulo": titulo, "huella_periodos": ov["huella_periodos"]})


# ------------------------------------------------------------------------------------------ lecturas
def test_lecturas_de_las_cinco_pestanas_no_escriben(actividades, records, db_conn, audit_store):
    rec = records["dep"]
    antes = _contar(db_conn)
    ov = actividades.overview(rec)
    assert ov["abierto"]["nombre"] == "2026-2" and ov["estados"] == ["Activa", "Finalizada", "Suspendida"]
    assert "no consumen horas de dedicación" in ov["info"]
    for p in ov["periodos"]:
        actividades.actividades_periodo(rec, {"periodo_id": p["id"]})
        actividades.asignar_datos(rec, {"periodo_id": p["id"]})
    tab1 = actividades.actividades_periodo(rec, {"periodo_id": ov["abierto"]["id"]})
    assert len(tab1["actividades"]) == 1 and len(tab1["participaciones"]) == 5
    assert "id" not in tab1["actividades"][0] and "periodo_id" not in tab1["actividades"][0]
    assert len(actividades.historial(rec)["filas"]) == 5
    filas = actividades.editar_datos(rec)["filas"]
    actividades.participaciones_actividad(rec, {"actividad_id": filas[0]["id"]})
    assert _contar(db_conn) == antes and audit_store.events == []


def test_permisos_por_rol(actividades, records):
    p = {k: actividades.overview(records[k])["permisos"] for k in ("dep", "lector", "coord_dep", "super")}
    assert p["dep"] == {"puede_escribir": True, "puede_borrar": False}
    assert p["lector"] == p["coord_dep"] == {"puede_escribir": False, "puede_borrar": False}
    assert p["super"] == {"puede_escribir": True, "puede_borrar": True}


def test_coordinador_sin_departamento_no_ve_el_modulo(actividades, records):
    with pytest.raises(ActividadesError) as e:
        actividades.overview(records["coord"])
    assert e.value.code == "SCOPE_INSTITUTIONAL"


@pytest.mark.parametrize("quien", ["lector", "coord_dep"])
def test_coordinador_y_solo_lectura_no_escriben(actividades, records, db_conn, audit_store, quien):
    antes = _contar(db_conn)
    with pytest.raises(ActividadesError) as e:
        _crear(actividades, records[quien])
    assert e.value.status == 403
    assert [(x.operation, x.outcome, x.audit_mode) for x in audit_store.events] == [
        ("guardar_actividad_especial", "DENIED", "SEPARATE_TRANSACTION")]
    assert _contar(db_conn) == antes


def test_denegacion_b10_corta_el_bucle_de_asignar(actividades, records, db_conn, audit_store):
    """``st.error`` + ``st.stop()``: con 2 docentes, solo la primera operacion queda DENIED y nada se escribe."""
    rec = records["lector"]
    pid = _abierto(actividades, rec)
    datos = actividades.asignar_datos(rec, {"periodo_id": pid})
    act = datos["actividades"][0]
    docs = [{"cuil": d["cuil"], "rol": "X"} for d in datos["docentes"][:2]]
    with pytest.raises(ActividadesError) as e:
        actividades.asignar(rec, {"periodo_id": pid, "actividad_id": act["id"], "huella": act["huella"], "docentes": docs})
    assert e.value.status == 403
    assert [(x.operation, x.outcome) for x in audit_store.events] == [("asignar_docente_actividad_especial", "DENIED")]


def test_otro_departamento_y_ids_manipulados(actividades, records, db_conn):
    rec = records["dep"]
    per_dep2 = db_conn.execute("SELECT id FROM periodos WHERE departamento_id=2 AND nombre='2026-2'").fetchone()[0]
    with pytest.raises(ActividadesError) as e:
        actividades.actividades_periodo(rec, {"periodo_id": per_dep2, "institucion_id": 1, "departamento_id": 2})
    assert e.value.status == 404
    with pytest.raises(ActividadesError) as e:
        actividades.actividades_periodo(rec, {"periodo_id": "1 OR 1=1"})
    assert e.value.status == 422
    with pytest.raises(ActividadesError):
        actividades.participaciones_actividad(rec, {"actividad_id": 2})  # actividad del dep 2
    assert all(f["id"] != 2 for f in actividades.editar_datos(rec)["filas"])


# ------------------------------------------------------------------------------------------ B12H / B12D
def test_alta_auditada_y_sin_movimientos(actividades, records, db_conn):
    movs = db_conn.execute("SELECT count(*) FROM movimientos").fetchone()[0]
    _crear(actividades, records["dep"])
    ev = audit_rows(db_conn)
    assert [(e["operation"], e["entity_type"], e["outcome"], e["audit_mode"]) for e in ev] == [
        ("guardar_actividad_especial", "actividad_especial", "SUCCESS", "IN_TRANSACTION")]
    assert ev[0]["metadata"]["entity_param"] == "periodo_id"
    assert db_conn.execute("SELECT count(*) FROM movimientos").fetchone()[0] == movs
    fila = db_conn.execute("SELECT estado, fecha_carga, departamento_id FROM actividades_especiales WHERE titulo='ZZNEXT svc'"
                           ).fetchone()
    assert fila[0] == "Activa" and fila[2] == 1 and len(fila[1]) >= 19  # str(datetime.now()): fecha y hora


def test_auditoria_que_falla_revierte_el_commit(actividades, records, db_conn, audit_store, monkeypatch):
    antes = _contar(db_conn)

    def falla(conn, event):
        raise RuntimeError("audit down")
    monkeypatch.setattr(audit, "insert_on", falla)
    with pytest.raises(ActividadesError) as e:
        _crear(actividades, records["dep"])
    assert e.value.code == "AUDIT" and _contar(db_conn) == antes
    assert audit_store.events[-1].error_code == "AuditPersistenceError:AUDIT_INSERT_FAILED"


def test_fallo_de_base_es_failed_sin_escrituras(actividades, records, db_conn, audit_store, monkeypatch):
    from actividades_especiales.repository import ActividadesRepository

    def roto(self, *a, **k):
        raise psycopg.errors.DeadlockDetected("deadlock detected")
    monkeypatch.setattr(ActividadesRepository, "update_actividad", roto)
    rec = records["dep"]
    f = actividades.editar_datos(rec)["filas"][0]
    antes = _contar(db_conn)
    with pytest.raises(ActividadesError) as e:
        actividades.editar(rec, {"actividad_id": f["id"], "huella": f["huella"], "titulo": "x", "estado": "Activa"})
    assert e.value.status == 503 and "deadlock" not in e.value.message
    assert _contar(db_conn) == antes
    assert (audit_store.events[-1].outcome, audit_store.events[-1].error_code) == ("FAILED", "DeadlockDetected")


# ------------------------------------------------------------------------------------------ B12I
def test_capa_u_revalida_y_no_escribe(actividades, records, db_conn, audit_store, monkeypatch):
    rec = records["dep"]
    f = actividades.editar_datos(rec)["filas"][0]
    real = ActividadesService._actividad_vista

    def selecciona_y_otro_cambia(self, scope, data):
        out = real(self, scope, data)
        db_conn.execute("UPDATE actividades_especiales SET observaciones='cambio concurrente' WHERE id=%s", [f["id"]])
        return out
    monkeypatch.setattr(ActividadesService, "_actividad_vista", selecciona_y_otro_cambia)
    with pytest.raises(ActividadesError) as e:
        actividades.editar(rec, {"actividad_id": f["id"], "huella": f["huella"], "titulo": "x", "estado": "Activa"})
    assert e.value.code == "STALE"
    assert db_conn.execute("SELECT titulo FROM actividades_especiales WHERE id=%s", [f["id"]]).fetchone()[0] != "x"
    assert (audit_store.events[-1].outcome, audit_store.events[-1].error_code) == ("FAILED", "StaleDecisionError")


def test_sin_lock_de_capa_t(actividades, records, db_conn):
    """Ninguna familia B12I certificada incluye estos writers: el servicio no tiene lock ni conexion de lock."""
    assert not hasattr(actividades, "_consistency_lock") and not hasattr(S, "PROJECT_LOCK_FORMAT")
    probe = psycopg.connect(__import__("db").load_settings()["database_url"], autocommit=True)
    try:
        _crear(actividades, records["dep"])
        assert probe.execute("SELECT count(*) FROM pg_locks WHERE locktype='advisory'").fetchone()[0] == 0
    finally:
        probe.close()


# ------------------------------------------------------------------------------------------ G5 y ausencias
def test_lectura_institucional_g5_sin_endpoint(actividades, records, http):
    rec = records["dep"]
    scope = actividades.scope(rec)
    df = actividades.participaciones_docente_institucion(scope, periodo_id=_abierto(actividades, rec))
    assert len(df) == 6 and set(df["departamento_asignacion_id"]) == {1, 2}
    from actividades_especiales.routes import router
    rutas = {r.path for r in router.routes}
    assert len(rutas) == 11
    assert not any(x in p for p in rutas for x in ("excel", "acto", "costo", "hora", "movimiento", "institucion"))
    assert not [n for n in dir(ActividadesService) if any(x in n for x in ("excel", "acto", "costo", "horas",
                                                                           "movimiento"))]


# ------------------------------------------------------------------------------------------ HTTP
def login(client, repo, email):
    r = client.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF)
    assert r.status_code == 200


def clean(response, repo):
    for word in FORBIDDEN:
        assert word not in response.text, word
    for pwd in repo.passwords.values():
        assert pwd not in response.text


def test_http_sesion_csrf_y_respuestas_limpias(http, repo, clock):
    assert http.get("/actividades-especiales").status_code == 401
    assert http.post("/actividades-especiales/historial", json={}, headers=CSRF).status_code == 401
    login(http, repo, "info@test.local")
    r = http.get("/actividades-especiales")
    assert r.status_code == 200
    clean(r, repo)
    assert http.post("/actividades-especiales/historial", json={}).json()["error"]["code"] == "CSRF"
    for ruta in ("historial", "editar/actividades"):
        r = http.post(f"/actividades-especiales/{ruta}", json={}, headers=CSRF)
        assert r.status_code == 200, ruta
        clean(r, repo)
    r = http.post("/actividades-especiales/periodo", json={"periodo_id": "9 OR 1=1"}, headers=CSRF)
    assert r.status_code == 422
    clean(r, repo)
    clock.advance(30 * 60)
    assert http.get("/actividades-especiales").json()["error"]["code"] == "IDLE_TIMEOUT"


def test_http_solo_lectura(http, repo, db_conn):
    login(http, repo, "lector@test.local")
    ov = http.get("/actividades-especiales").json()
    assert not any(ov["permisos"].values())
    r = http.post("/actividades-especiales/crear", json={"periodo_id": ov["abierto"]["id"], "titulo": "ZZ",
                                                         "huella_periodos": ov["huella_periodos"]}, headers=CSRF)
    assert r.status_code == 403
