"""Servicio y HTTP de Sueldos sobre deptit_next_dev con ROLLBACK: lecturas de las 3 pestañas sin escrituras, permisos
B10 por rol (superadmin y usuario_departamento escriben la escala INSTITUCIONAL; coordinador, solo lectura y modo
comercial solo lectura: DENIED), ambito (coordinador sin departamento, institucion sin departamentos), B12H (DENIED /
FAILED / auditoria que falla con ROLLBACK), B12D, B12I sin lock de capa T ni huella, ausencia de funciones inexistentes
(Excel, importacion, exportacion, eliminacion, movimientos) y contrato HTTP.  Usuarios del FakeRepo."""

from __future__ import annotations

import psycopg
import pytest

import audit
from sueldos import rules as SR
from sueldos import service as S
from sueldos.repository import SueldosRepository
from sueldos.service import SueldosError, SueldosService
from sueldos_support import (  # noqa: F401  (fixtures)
    audit_rows, audit_store, db_conn, http, session_for, state, sueldos,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "INSERT ", "DELETE ", "Traceback", "psycopg", "institucion_id =")
VALORES = dict(SR.BASICOS_JUNIO_2026_V256)


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
        "SELECT (SELECT count(*) FROM escalas_salariales_docentes), (SELECT count(*) FROM movimientos), "
        "(SELECT md5(string_agg(md5(e::text), '' ORDER BY e.id)) FROM escalas_salariales_docentes e), "
        "(SELECT count(*) FROM b12h_audit_log), (SELECT count(*) FROM docentes), (SELECT count(*) FROM designaciones)"
    ).fetchone()


def _guardar(svc, rec, mes=10, valores=None):
    return svc.guardar_escala(rec, {"anio": 2026, "mes": mes, "valores": valores or VALORES})


# ------------------------------------------------------------------------------------------ lecturas
def test_lecturas_de_las_tres_pestanas_no_escriben(sueldos, records, db_conn, audit_store):
    rec = records["dep"]
    antes = _contar(db_conn)
    ov = sueldos.overview(rec)
    assert ov["info"].startswith("Configurá el básico mensual de la dedicación **Simple**")
    assert ov["hoy"] == {"anio": 2026, "mes": 10} and ov["cargos"] == SR.CARGOS
    assert ov["dedicaciones"] == ["Simple", "Parcial", "Parcial + Simple", "Exclusiva", "Exclusiva + Simple"]
    assert ov["niveles"] == ["", "Especialista", "Magíster", "Doctor"] and len(ov["meses"]) == 12
    assert ov["plantel"]["periodo_defecto"] == "2026-2"
    e = sueldos.escalas(rec, {"anio": 2026, "mes": 10})
    assert e["valores"] == VALORES and len(e["historico"]) == 6
    assert e["historico"][0]["Mes"] == "06/2026" and e["historico"][0]["Usuario"] == "Inicial v256"
    t = sueldos.tabla(rec, {})
    assert t["mes"] == "2026-06" and t["filas"][0]["0–4 años"] == "$ 584.573,72"
    assert t["caption"] == ("Escala 06/2026 · Simple · Sin adicional por posgrado. La antigüedad mínima (0 años) ya "
                            "aplica 20%.")
    for p in ov["plantel"]["periodos"]:
        sueldos.plantel(rec, {"periodo_id": p["id"]})
    assert _contar(db_conn) == antes and audit_store.events == []


def test_permisos_por_rol(sueldos, records):
    p = {k: sueldos.overview(records[k])["permisos"]["puede_escribir"] for k in
         ("dep", "dep2", "lector", "coord_dep", "super")}
    assert p == {"dep": True, "dep2": True, "lector": False, "coord_dep": False, "super": True}
    ov = sueldos.overview(records["lector"])
    assert ov["ayuda_sin_permiso"] == "Tu rol permite visualizar, pero no cargar, editar ni generar cambios."


def test_coordinador_sin_departamento_no_ve_el_modulo(sueldos, records):
    with pytest.raises(SueldosError) as e:
        sueldos.overview(records["coord"])
    assert e.value.code == "SCOPE_INSTITUTIONAL"


@pytest.mark.parametrize("quien,codigo", [("lector", "DENY_READ_ONLY_ROLE"), ("coord_dep", "DENY_ROLE_NOT_PERMITTED")])
def test_coordinador_y_solo_lectura_no_escriben(sueldos, records, db_conn, audit_store, quien, codigo):
    antes = _contar(db_conn)
    with pytest.raises(SueldosError) as e:
        _guardar(sueldos, records[quien])
    assert e.value.status == 403 and e.value.message.startswith("⛔ ")
    assert e.value.message.endswith("(permiso requerido: sueldos.write)")
    assert [(x.operation, x.outcome, x.audit_mode, x.error_code, x.action_scope) for x in audit_store.events] == [
        ("guardar_escala_salarial_v256", "DENIED", "SEPARATE_TRANSACTION", codigo, "institution")]
    assert _contar(db_conn) == antes


def test_modo_comercial_solo_lectura(service, repo, sueldos, db_conn, audit_store):
    repo.institutions_rows[0]["estado_pago"] = "Vencido"
    rec = session_for(service, repo, 3)[0]
    assert sueldos.overview(rec)["permisos"]["puede_escribir"] is False
    with pytest.raises(SueldosError) as e:
        _guardar(sueldos, rec)
    assert e.value.status == 403 and [x.error_code for x in audit_store.events] == ["DENY_COMMERCIAL_READ_ONLY"]


def test_usuario_departamento_escribe_la_escala_de_toda_la_institucion(sueldos, records, db_conn):
    """H11 (CANDIDATO A REVISION DE PERMISOS POST-EQUIVALENCIA): la escala que guarda el departamento 2 es la que
    usa el plantel del departamento 1."""
    _guardar(sueldos, records["dep2"], mes=9, valores={c: v * 2 for c, v in VALORES.items()})
    r = sueldos.plantel(records["dep"], {"periodo_id": 9})
    assert r["caption_escala"] == "Escala aplicada automáticamente: **09/2026**."


def test_institucion_sin_departamentos(service, repo, sueldos, db_conn):
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 5, None, False)
    ov = sueldos.overview(sup)
    assert ov["contexto"]["institucion"]["id"] == 5 and ov["contexto"]["departamento"] is None
    assert ov["plantel"]["disponible"] is False
    with pytest.raises(SueldosError) as e:
        sueldos.plantel(sup, {"periodo_id": 9})
    assert e.value.code == "SCOPE_INSTITUTIONAL"
    assert sueldos.escalas(sup, {"anio": 2026, "mes": 10})["historico"] == []


# ------------------------------------------------------------------------------------------ B12H / B12D / B12I
def test_alta_auditada_sin_movimientos(sueldos, records, db_conn):
    antes = _contar(db_conn)
    r = _guardar(sueldos, records["dep"])
    assert r == {"mensaje": "Escala 10/2026 guardada correctamente.", "tono": "success"}
    despues = _contar(db_conn)
    assert despues[0] == antes[0] + 6 and despues[1] == antes[1] and despues[3] == antes[3] + 1
    ev = audit_rows(db_conn)[-1]
    assert (ev["operation"], ev["outcome"], ev["audit_mode"], ev["entity_type"], ev["entity_id"],
            ev["actor_email_normalized"]) == ("guardar_escala_salarial_v256", "SUCCESS", "IN_TRANSACTION",
                                              "escala_salarial", None, "info@test.local")


def test_auditoria_que_falla_revierte_el_commit(sueldos, records, db_conn, audit_store, monkeypatch):
    antes = _contar(db_conn)

    def falla(conn, event):
        raise RuntimeError("audit down")
    monkeypatch.setattr(audit, "insert_on", falla)
    with pytest.raises(SueldosError) as e:
        _guardar(sueldos, records["dep"])
    assert e.value.code == "AUDIT" and _contar(db_conn) == antes
    assert [(x.outcome, x.error_code) for x in audit_store.events] == [
        ("FAILED", "AuditPersistenceError:AUDIT_INSERT_FAILED")]


def test_fallo_de_base_es_failed_sin_escrituras(sueldos, records, db_conn, audit_store, monkeypatch):
    antes = _contar(db_conn)
    llamadas = []
    original = SueldosRepository.upsert_escala

    def roto(self, mes, cargo, basico, usuario):
        llamadas.append(cargo)
        if len(llamadas) == 4:
            raise psycopg.errors.QueryCanceled("boom")
        return original(self, mes, cargo, basico, usuario)
    monkeypatch.setattr(SueldosRepository, "upsert_escala", roto)
    with pytest.raises(SueldosError) as e:
        _guardar(sueldos, records["dep"])
    assert e.value.code == "DB_ERROR" and e.value.message.startswith("No se pudo guardar la escala: ")
    assert "boom" not in e.value.message and _contar(db_conn) == antes and len(llamadas) == 4
    assert [(x.outcome, x.error_code) for x in audit_store.events] == [("FAILED", "QueryCanceled")]


def test_sin_lock_de_capa_t_ni_huella(sueldos, records, db_conn):
    """Ninguna familia B12I certificada incluye el writer: sin lock, sin conexion de lock, sin huella (H6)."""
    assert not hasattr(sueldos, "_consistency_lock") and not hasattr(S, "PROJECT_LOCK_FORMAT")
    assert not [n for n in dir(SueldosService) if "stale" in n or "huella" in n or "lock" in n]
    probe = psycopg.connect(__import__("db").load_settings()["database_url"], autocommit=True)
    try:
        _guardar(sueldos, records["dep"])
        assert probe.execute("SELECT count(*) FROM pg_locks WHERE locktype='advisory'").fetchone()[0] == 0
    finally:
        probe.close()


def test_lectura_falla_cerrado(sueldos, records, monkeypatch):
    def roto(self):
        raise psycopg.OperationalError("down")
    monkeypatch.setattr(SueldosRepository, "escalas", roto)
    with pytest.raises(SueldosError) as e:
        sueldos.escalas(records["dep"], {"anio": 2026, "mes": 10})
    assert e.value.code == "DB_READ"


# ------------------------------------------------------------------------------------------ ausencias y helpers
def test_ausencias_y_helpers_internos_sin_endpoint(sueldos, records):
    from sueldos.routes import router
    rutas = {r.path for r in router.routes}
    assert rutas == {"/sueldos", "/sueldos/escalas", "/sueldos/tabla", "/sueldos/plantel", "/sueldos/escalas/guardar"}
    assert not any(x in p for p in rutas for x in ("excel", "import", "export", "elimin", "delete", "movimiento",
                                                    "resumen", "costo", "carga"))
    metodos = [n for n in dir(SueldosService) if not n.startswith("_")]
    assert not [n for n in metodos if any(x in n for x in ("excel", "import", "export", "elimin", "movimiento", "carga"))]
    from sueldos import escrituras as E
    assert [n for n in dir(E) if n.startswith("W_")] == ["W_GUARDAR_ESCALA"]
    scope = sueldos.scope(records["dep"])
    # Etapa 5 / C2: el total es la suma de su detalle (el valor contra el certificado lo verifica E4-04 /
    # test_costos_proyectos_vigentes_referencias_2026_2); antes literal 87148362.24 de la base dev.
    costos = sueldos.costos_proyectos_vigentes(scope, "extension")
    assert costos["total"] > 0 and costos["total"] == round(float(costos["detalle"]["costo_total_proyecto_v258"].sum()), 2)
    with pytest.raises(SueldosError):
        sueldos.costos_proyectos_vigentes(scope, "docencia")


# ------------------------------------------------------------------------------------------ HTTP
def login(client, repo, email):
    r = client.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF)
    assert r.status_code == 200


def clean(response, repo):
    for word in FORBIDDEN:
        assert word not in response.text, word
    for pwd in repo.passwords.values():
        assert pwd not in response.text


def test_http_sesion_csrf_y_respuestas_limpias(http, repo, clock, db_conn):
    assert http.get("/sueldos").status_code == 401
    assert http.post("/sueldos/escalas", json={"anio": 2026, "mes": 10}, headers=CSRF).status_code == 401
    login(http, repo, "info@test.local")
    r = http.get("/sueldos")
    assert r.status_code == 200
    clean(r, repo)
    assert http.post("/sueldos/escalas", json={"anio": 2026, "mes": 10}).json()["error"]["code"] == "CSRF"
    for ruta, body in (("escalas", {"anio": 2026, "mes": 10}), ("tabla", {"dedicacion": "Exclusiva", "nivel": "Doctor"}),
                       ("plantel", {"periodo_id": r.json()["plantel"]["periodos"][0]["id"]})):
        rr = http.post(f"/sueldos/{ruta}", json=body, headers=CSRF)
        assert rr.status_code == 200, ruta
        clean(rr, repo)
    rr = http.post("/sueldos/plantel", json={"periodo_id": "9 OR 1=1"}, headers=CSRF)
    assert rr.status_code == 422
    clean(rr, repo)
    rr = http.post("/sueldos/escalas/guardar", json={"anio": 2026, "mes": 10, "valores": VALORES}, headers=CSRF)
    assert rr.status_code == 200 and rr.json()["mensaje"] == "Escala 10/2026 guardada correctamente."
    rr = http.post("/sueldos/escalas/guardar", json={"anio": 2026, "mes": 10, "valores": {**VALORES, "JTP": 0}},
                   headers=CSRF)
    assert rr.status_code == 422 and rr.json()["error"]["message"] == ("No se pudo guardar la escala: El básico de "
                                                                        "JTP debe ser mayor a cero.")
    clock.advance(30 * 60)
    assert http.get("/sueldos").json()["error"]["code"] == "IDLE_TIMEOUT"


def test_http_solo_lectura(http, repo, db_conn):
    login(http, repo, "lector@test.local")
    antes = _contar(db_conn)
    ov = http.get("/sueldos").json()
    assert ov["permisos"]["puede_escribir"] is False
    r = http.post("/sueldos/escalas/guardar", json={"anio": 2026, "mes": 10, "valores": VALORES}, headers=CSRF)
    assert r.status_code == 403 and _contar(db_conn) == antes
    assert http.delete("/sueldos/escalas").status_code in (404, 405)
