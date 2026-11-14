"""Contrato HTTP de Periodos: sesion revalidada, expiracion, CSRF, tenant ignorado del cliente y respuestas limpias.
Base real con ROLLBACK (periodos_support); usuarios del FakeRepo con contrasenas aleatorias."""

import pytest

from periodos_support import (  # noqa: F401  (fixtures)
    audit_after, audit_store, db_conn, http, lock_conn, movements_after, periodos, snapshot,
)

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "Traceback", "psycopg")


def login(client, repo, email):
    r = client.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF)
    assert r.status_code == 200
    return r


def clean(response, repo):
    for word in FORBIDDEN:
        assert word not in response.text, word
    for pwd in repo.passwords.values():
        assert pwd not in response.text
    assert response.headers["cache-control"] == "no-store"


def closed_and_open(conn, dep=1):
    rows = snapshot(conn, 1, dep)["periodos"]
    return [p for p in rows if p["estado"] != "Abierto"], [p for p in rows if p["estado"] == "Abierto"]


def test_requires_session(http):
    assert http.get("/periodos").json()["error"]["code"] == "NO_SESSION"
    r = http.post("/periodos/volver-actual", json={}, headers=CSRF)
    assert r.status_code == 401
    r = http.post("/periodos/apertura-excepcional", json={"periodo_id": 1}, headers=CSRF)
    assert r.status_code == 401


def test_writes_require_proxy_header(http, repo, db_conn):
    login(http, repo, "info@test.local")
    before = snapshot(db_conn, 1, 1)
    closed, _ = closed_and_open(db_conn)
    r = http.post("/periodos/apertura-excepcional",
                  json={"periodo_id": closed[0]["id"], "confirmar_cierre": True, "confirmar_excepcional": True})
    assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF"
    assert snapshot(db_conn, 1, 1) == before


def test_expired_session_is_rejected(http, repo, clock, db_conn):
    login(http, repo, "info@test.local")
    assert http.get("/periodos").status_code == 200
    clock.advance(30 * 60)
    r = http.get("/periodos")
    assert r.status_code == 401 and r.json()["error"]["code"] == "IDLE_TIMEOUT"
    assert http.get("/periodos").json()["error"]["code"] == "NO_SESSION"  # la sesion se elimino


def test_full_flow_open_previous_and_return(http, repo, db_conn):
    login(http, repo, "info@test.local")
    r = http.get("/periodos")
    clean(r, repo)
    data = r.json()
    closed, opened = closed_and_open(db_conn)
    assert data["abierto"]["id"] == opened[0]["id"] and data["permisos"]["puede_escribir"] is True
    before = snapshot(db_conn, 1, 1)
    r = http.post("/periodos/apertura-excepcional", headers=CSRF, json={
        "periodo_id": closed[0]["id"], "observaciones": "revisión", "confirmar_cierre": True,
        "confirmar_excepcional": True})
    clean(r, repo)
    assert r.status_code == 200 and r.json()["periodo"]["id"] == closed[0]["id"]
    assert http.get("/periodos").json()["abierto"]["id"] == closed[0]["id"]
    r = http.post("/periodos/volver-actual", headers=CSRF, json={
        "observaciones": "listo", "confirmar_cierre_anterior": True, "confirmar_retorno": True})
    assert r.status_code == 200 and r.json()["mensaje"] == "Se volvió al período actual correctamente."
    assert http.get("/periodos").json()["abierto"]["id"] == opened[0]["id"]
    tipos = [m["tipo_movimiento"] for m in movements_after(db_conn, before["max_mov_id"])]
    assert tipos == ["Apertura excepcional de período", "Retorno al período actual"]
    assert [(r["operation"], r["metadata"]["committing_writer"]) for r in audit_after(db_conn)] == [
        ("_abrir_periodo_emergencia_control_v300", "abrir_periodo_emergencia"),
        ("_abrir_periodo_emergencia_control_v300", "registrar_movimiento"),
        ("_volver_periodo_actual_control_v300", "volver_periodo_actual"),
        ("_volver_periodo_actual_control_v300", "registrar_movimiento")]


def test_tenant_fields_in_body_are_ignored(http, repo, db_conn):
    login(http, repo, "info@test.local")
    foreign_closed, _ = closed_and_open(db_conn, dep=2)
    before1, before2 = snapshot(db_conn, 1, 1), snapshot(db_conn, 1, 2)
    r = http.post("/periodos/apertura-excepcional", headers=CSRF, json={
        "periodo_id": foreign_closed[0]["id"], "institucion_id": 1, "departamento_id": 2,
        "confirmar_cierre": True, "confirmar_excepcional": True})
    assert r.status_code == 404 and r.json()["error"]["code"] == "PERIOD_NOT_FOUND"
    clean(r, repo)
    assert snapshot(db_conn, 1, 1) == before1 and snapshot(db_conn, 1, 2) == before2
    assert http.get("/periodos", params={"departamento_id": 2}).json()["contexto"]["departamento"]["id"] == 1


def test_coordinator_reads_after_selecting_department_but_cannot_write(http, repo, db_conn):
    login(http, repo, "coord@test.local")
    r = http.get("/periodos")
    assert r.status_code == 409 and r.json()["error"]["code"] == "SCOPE_INSTITUTIONAL"
    assert http.put("/auth/context", json={"departamento_id": 1}, headers=CSRF).status_code == 200
    assert http.get("/periodos").status_code == 200
    closed, _ = closed_and_open(db_conn)
    before = snapshot(db_conn, 1, 1)
    r = http.post("/periodos/apertura-excepcional", headers=CSRF, json={
        "periodo_id": closed[0]["id"], "confirmar_cierre": True, "confirmar_excepcional": True})
    assert r.status_code == 403
    assert r.json()["error"]["message"] == ("⛔ Tu rol no tiene permiso para esta operación. No se realizó ningún "
                                            "cambio. (permiso requerido: periodos.write)")
    assert snapshot(db_conn, 1, 1) == before


def test_coordinator_cannot_select_department_of_other_institution(http, repo):
    login(http, repo, "coord@test.local")
    assert http.put("/auth/context", json={"departamento_id": 5}, headers=CSRF).status_code == 403
    assert http.get("/periodos").json()["error"]["code"] == "SCOPE_INSTITUTIONAL"


@pytest.mark.parametrize("body", [{"confirmar_cierre": "true", "confirmar_excepcional": True, "periodo_id": 1},
                                  {"observaciones": 123, "confirmar_cierre": True, "confirmar_excepcional": True,
                                   "periodo_id": 1}])
def test_malformed_bodies_are_rejected_without_writing(http, repo, db_conn, body):
    login(http, repo, "info@test.local")
    before = snapshot(db_conn, 1, 1)
    assert http.post("/periodos/apertura-excepcional", headers=CSRF, json=body).status_code == 422
    assert snapshot(db_conn, 1, 1) == before


def test_long_observaciones_are_accepted_without_limit(http, repo, db_conn):
    login(http, repo, "info@test.local")
    closed, _ = closed_and_open(db_conn)
    before = snapshot(db_conn, 1, 1)
    texto = "x" * 100_000
    r = http.post("/periodos/apertura-excepcional", headers=CSRF, json={
        "periodo_id": closed[0]["id"], "observaciones": texto, "confirmar_cierre": True,
        "confirmar_excepcional": True})
    assert r.status_code == 200
    assert movements_after(db_conn, before["max_mov_id"])[0]["observaciones"] == texto


def test_database_unavailable_is_controlled(http, repo, periodos, monkeypatch):
    login(http, repo, "info@test.local")

    def down():
        raise ConnectionError("db down")

    monkeypatch.setattr(periodos, "_transaction", down)
    r = http.get("/periodos")
    assert r.status_code == 503 and r.json()["error"]["code"] == "DB_READ"
    clean(r, repo)
