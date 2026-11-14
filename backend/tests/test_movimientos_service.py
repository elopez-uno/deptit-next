"""Servicio y HTTP de Movimientos: permisos B10 por rol (D-AL2), contrato B12H (D-AL16), capa U con huella (D-AL5),
validacion fresca de ids y del ambito (D-AL4 / D-AL13), sin locks de capa T y ausencias (D-AL1 / D-AL9 / D-AL12).
Datos sinteticos ``ZZNEXT`` dentro de la transaccion del test (ROLLBACK)."""

from __future__ import annotations

import json

import psycopg
import pytest

from movimientos import rules as R
from movimientos.service import MovimientosError
from movimientos_support import (  # noqa: F401  (fixtures)
    audit_rows, audit_store, db_conn, http, movimientos, session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "DELETE ", "Traceback", "psycopg", "institucion_id", "departamento_id", "C:\\", "C:/", "\\\\",
             "source_db", "sqlite", "fuente_sqlite", "datos_instituciones", ".db")


@pytest.fixture
def records(service, repo):
    out = {"dep": session_for(service, repo, 3)[0], "lector": session_for(service, repo, 7)[0],
           "dep2": session_for(service, repo, 6)[0]}
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, 1, False)
    out["super"] = sup
    coord = session_for(service, repo, 2)[0]
    service.set_context(coord, 1, 1, False)
    out["coord_dep"] = coord
    out["coord"] = session_for(service, repo, 2)[0]
    return out


def _huellas(movimientos, rec, ids, periodo=R.TODOS):
    filas = {f["id"]: f for f in movimientos.listado(rec, {"periodo": periodo})["filas"]}
    return [{"id": i, "huella": filas[i]["huella"]} for i in ids]


def _ids(db_conn, condicion, n=1, dep=1):
    return [r[0] for r in db_conn.execute(f"SELECT id FROM movimientos WHERE institucion_id=1 AND departamento_id={dep} "
                                          f"AND {condicion} ORDER BY id LIMIT {int(n)}")]


def _doc(db_conn, dep=1):
    return db_conn.execute(
        "INSERT INTO documentos_respaldo (institucion_id,departamento_id,tipo_documento,categoria,numero,"
        "archivo_nombre,archivo_mime,archivo_pdf,archivo_bytes) VALUES (1,%s,'Resolución','Otro','ZZNEXT-S','','','',0) "
        "RETURNING id", [dep]).fetchone()[0]


def _foto(db_conn):
    return db_conn.execute(
        "SELECT (SELECT md5(string_agg(md5(m::text),'' ORDER BY m.id)) FROM movimientos m), "
        "(SELECT md5(COALESCE(string_agg(md5((r.documento_id, r.movimiento_id)::text),'' ORDER BY r.movimiento_id),'')) "
        "FROM documentos_respaldo_movimientos r), (SELECT count(*) FROM b12h_audit_log)").fetchone()


# ------------------------------------------------------------------------------------------ B10 por rol
def test_permisos_visuales_por_rol(movimientos, records):
    esperado = {"dep": (False, True, False), "lector": (False, False, False), "super": (True, True, True),
                "coord_dep": (False, False, False), "dep2": (False, True, False)}
    for rol, (e, v, d) in esperado.items():
        assert movimientos.overview(records[rol])["permisos"] == {"puede_eliminar": e, "puede_vincular": v,
                                                                   "puede_desvincular": d}, rol
    with pytest.raises(MovimientosError) as exc:  # coordinador sin departamento: modulo no visible
        movimientos.overview(records["coord"])
    assert exc.value.code == "SCOPE_INSTITUTIONAL"


def test_roles_sin_escritura_y_read_only_comercial(movimientos, service, repo, db_conn, audit_store, records):
    """Ver: todos.  Eliminar / vincular / quitar: DENIED (403) con su ``b10_decision`` y 0 escrituras."""
    repo.institutions_rows[0]["estado_pago"] = "Vencido"
    ro = session_for(service, repo, 3)[0]
    repo.institutions_rows[0]["estado_pago"] = "Al día"
    with db_conn.transaction() as tx:
        doc = _doc(db_conn)
        mid = _ids(db_conn, "tipo_movimiento='Alta de designación'")[0]
        antes = _foto(db_conn)
        for rec, codigo in ((ro, "DENY_COMMERCIAL_READ_ONLY"), (records["lector"], "DENY_READ_ONLY_ROLE"),
                            (records["coord_dep"], "DENY_ROLE_NOT_PERMITTED")):
            ov = movimientos.overview(rec)
            assert ov["permisos"] == {"puede_eliminar": False, "puede_vincular": False, "puede_desvincular": False}
            sel = _huellas(movimientos, rec, [mid])
            n = len(audit_store.events)
            for llamar in (lambda: movimientos.eliminar(rec, {"id": mid, "huella": sel[0]["huella"], "confirmar": True}),
                           lambda: movimientos.vincular(rec, {"documento_id": doc, "seleccion": sel}, False),
                           lambda: movimientos.vincular(rec, {"seleccion": sel}, True)):
                with pytest.raises(MovimientosError) as exc:
                    llamar()
                assert exc.value.status == 403
            eventos = audit_store.events[n:]
            assert [e.outcome for e in eventos] == ["DENIED"] * 3
            assert {e.metadata["b10_decision"] for e in eventos} == {codigo}
            assert {e.audit_mode for e in eventos} == {"SEPARATE_TRANSACTION"}
        assert _foto(db_conn) == antes
        raise psycopg.Rollback(tx)


def test_usuario_departamento_vincula_pero_no_elimina_ni_quita(movimientos, db_conn, audit_store, records):
    with db_conn.transaction() as tx:
        doc = _doc(db_conn)
        mid = _ids(db_conn, "tipo_movimiento='Alta de designación'")[0]
        sel = _huellas(movimientos, records["dep"], [mid])
        for llamar, accion in ((lambda: movimientos.eliminar(records["dep"], {"id": mid, "huella": sel[0]["huella"],
                                                                              "confirmar": True}), "movimientos.delete"),
                               (lambda: movimientos.vincular(records["dep"], {"seleccion": sel}, True),
                                "documentos.delete")):
            with pytest.raises(MovimientosError) as exc:
                llamar()
            assert exc.value.status == 403
            assert audit_store.events[-1].outcome == "DENIED" and audit_store.events[-1].action == accion
            assert audit_store.events[-1].metadata["b10_decision"] == "DENY_ROLE_NOT_PERMITTED"
        r = movimientos.vincular(records["dep"], {"documento_id": doc, "seleccion": sel}, False)
        assert r == {"mensaje": "Acto administrativo vinculado a 1 movimiento/s.", "tono": "success"}
        fila = next(f for f in movimientos.listado(records["dep"], {"periodo": R.TODOS})["filas"] if f["id"] == mid)
        assert fila["acto_documento_id"] == doc and fila["acto_administrativo"] != R.PENDIENTE
        assert db_conn.execute("SELECT usuario_vinculacion FROM documentos_respaldo_movimientos WHERE movimiento_id=%s",
                               [mid]).fetchone()[0] == "info@test.local"
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ B12H
def test_contrato_b12h_eliminar_entity_id_null_y_metadata(movimientos, db_conn, audit_store, records):
    with db_conn.transaction() as tx:
        mid = _ids(db_conn, "tipo_movimiento='Edición de docente'")[0]
        sel = _huellas(movimientos, records["super"], [mid])
        movimientos.eliminar(records["super"], {"id": mid, "huella": sel[0]["huella"], "confirmar": True})
        ev = audit_rows(db_conn)
        assert len(ev) == 1
        e = ev[0]
        assert (e["operation"], e["action"], e["action_scope"], e["entity_type"], e["entity_id"], e["outcome"],
                e["audit_mode"], e["institucion_id"], e["departamento_id"], e["actor_role"]) == (
            "eliminar_movimiento", "movimientos.delete", "department", "movimiento", None, "SUCCESS", "IN_TRANSACTION",
            1, 1, "superadmin")
        assert e["metadata"]["commit_seq"] == 1 and e["metadata"]["mutating_statements"] == 2
        assert e["metadata"]["committing_writer"] == "eliminar_movimiento" and "entity_param" not in e["metadata"]
        texto = json.dumps(e["metadata"], default=str)
        assert "20-" not in texto and "detalle" not in texto and "SELECT" not in texto
        assert db_conn.execute("SELECT count(*) FROM movimientos WHERE id=%s", [mid]).fetchone()[0] == 0
        raise psycopg.Rollback(tx)


def test_falla_de_base_registra_failed_sin_texto(movimientos, db_conn, audit_store, records, monkeypatch):
    from movimientos.repository import MovimientosRepository

    def roto(self, id_movimiento):
        raise psycopg.errors.QueryCanceled("canceling statement due to user request: SELECT secreto")
    monkeypatch.setattr(MovimientosRepository, "eliminar_movimiento", roto)
    with db_conn.transaction() as tx:
        mid = _ids(db_conn, "TRUE")[0]
        sel = _huellas(movimientos, records["super"], [mid])
        antes = _foto(db_conn)
        with pytest.raises(MovimientosError) as exc:
            movimientos.eliminar(records["super"], {"id": mid, "huella": sel[0]["huella"], "confirmar": True})
        assert exc.value.status == 503 and "SELECT" not in exc.value.message and "secreto" not in exc.value.message
        e = audit_store.events[-1]
        assert e.outcome == "FAILED" and e.metadata == {"coupled_commits": 0} and e.entity_id is None
        assert _foto(db_conn) == antes
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ B12I capa U y ambito
def test_huella_obsoleta_rechaza_sin_escribir(movimientos, db_conn, audit_store, records):
    """Cambio entre la lectura y la accion (otro usuario vinculo un acto / edito el detalle) -> 409 STALE + FAILED."""
    with db_conn.transaction() as tx:
        doc = _doc(db_conn)
        a, b = _ids(db_conn, "tipo_movimiento='Alta de designación'", 2)
        sel = _huellas(movimientos, records["super"], [a, b])
        db_conn.execute("INSERT INTO documentos_respaldo_movimientos (institucion_id,departamento_id,documento_id,"
                        "movimiento_id,usuario_vinculacion) VALUES (1,1,%s,%s,'otro')", [doc, b])
        antes = _foto(db_conn)
        for llamar in (lambda: movimientos.vincular(records["super"], {"documento_id": doc, "seleccion": sel}, False),
                       lambda: movimientos.vincular(records["super"], {"seleccion": sel}, True),
                       lambda: movimientos.eliminar(records["super"], {"id": b, "huella": sel[1]["huella"],
                                                                       "confirmar": True})):
            n = len(audit_store.events)
            with pytest.raises(MovimientosError) as exc:
                llamar()
            assert (exc.value.status, exc.value.code, exc.value.error_class) == (409, "STALE", "StaleDecisionError")
            assert [(e.outcome, e.error_code) for e in audit_store.events[n:]] == [("FAILED", "StaleDecisionError")]
        assert _foto(db_conn) == antes
        # huella valida (relectura) -> escribe
        sel = _huellas(movimientos, records["super"], [a, b])
        assert movimientos.vincular(records["super"], {"seleccion": sel}, True)["mensaje"] == \
            "Se quitaron 1 vínculo/s de movimiento."
        raise psycopg.Rollback(tx)


def test_ids_fuera_de_ambito_inexistentes_o_no_seleccionables(movimientos, db_conn, audit_store, records):
    """D-AL4 / D-AL13: el id del cliente se relee con el ambito de la sesion; nunca cruza departamentos."""
    with db_conn.transaction() as tx:
        doc1, doc2 = _doc(db_conn, 1), _doc(db_conn, 2)
        ajeno = _ids(db_conn, "tipo_movimiento='Alta de designación'", dep=2)[0]
        propio = _ids(db_conn, "tipo_movimiento='Alta de designación'")[0]
        no_elegible = _ids(db_conn, "tipo_movimiento='Generación de disposición'")[0]
        h_ajeno = _huellas(movimientos, records["dep2"], [ajeno])[0]["huella"]
        sel_propio = _huellas(movimientos, records["super"], [propio, no_elegible])
        antes = _foto(db_conn)
        casos = [
            (lambda: movimientos.eliminar(records["super"], {"id": ajeno, "huella": h_ajeno, "confirmar": True}), 404),
            (lambda: movimientos.eliminar(records["super"], {"id": 987654321, "huella": "x", "confirmar": True}), 404),
            (lambda: movimientos.vincular(records["super"], {"documento_id": doc1, "seleccion": [
                {"id": ajeno, "huella": h_ajeno}]}, False), 409),
            (lambda: movimientos.vincular(records["super"], {"documento_id": doc1, "seleccion": sel_propio}, False), 409),
            (lambda: movimientos.vincular(records["super"], {"documento_id": doc2, "seleccion": sel_propio[:1]}, False),
             409),
            (lambda: movimientos.vincular(records["super"], {"documento_id": 987654321, "seleccion": sel_propio[:1]},
                                          False), 409),
            (lambda: movimientos.vincular(records["super"], {"seleccion": [{"id": ajeno, "huella": h_ajeno}]}, True),
             409),
        ]
        for llamar, status in casos:
            with pytest.raises(MovimientosError) as exc:
                llamar()
            assert exc.value.status == status
            assert audit_store.events[-1].outcome == "FAILED"
        for malo in ({"seleccion": []}, {"seleccion": [{"id": "1", "huella": "x"}]}, {"seleccion": "x"},
                     {"documento_id": True, "seleccion": sel_propio[:1]}, {"seleccion": sel_propio[:1]}):
            with pytest.raises(MovimientosError) as exc:
                movimientos.vincular(records["super"], malo, False)
            assert exc.value.status == 422
        with pytest.raises(MovimientosError) as exc:
            movimientos.listado(records["super"], {"periodo": "ZZNEXT inexistente"})
        assert exc.value.status == 409
        assert _foto(db_conn) == antes
        assert ajeno not in {f["id"] for f in movimientos.listado(records["super"], {"periodo": R.TODOS})["filas"]}
        raise psycopg.Rollback(tx)


def test_sin_locks_de_capa_t(movimientos, db_conn, records):
    with db_conn.transaction() as tx:
        mid = _ids(db_conn, "TRUE")[0]
        sel = _huellas(movimientos, records["super"], [mid])
        movimientos.eliminar(records["super"], {"id": mid, "huella": sel[0]["huella"], "confirmar": True})
        assert db_conn.execute("SELECT count(*) FROM pg_locks WHERE locktype='advisory'").fetchone()[0] == 0
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ HTTP
def _login(http, repo, email):
    r = http.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF)
    assert r.status_code == 200
    return http


def test_http_lectura_limpia_y_sin_campos_internos(http, repo):
    c = _login(http, repo, "info@test.local")
    r = c.get("/movimientos")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    ov = r.json()
    assert ov["periodos"][0] == R.TODOS and ov["periodo"] == "2026-2" and ov["filas"]
    assert {f["periodo"] for f in ov["filas"]} == {"2026-2"}
    r = c.post("/movimientos/listado", json={"periodo": R.TODOS}, headers=CSRF)
    # Mantenimiento de tests (cierre de Etapa 4): sin conteos absolutos de la base persistente (antes 582 / 1171): el
    # periodo por defecto es exactamente el subconjunto 2026-2 de "Todos los períodos".
    todos = r.json()["filas"]
    assert r.status_code == 200 and len(todos) > len(ov["filas"])
    assert sorted(f["id"] for f in ov["filas"]) == sorted(f["id"] for f in todos if f["periodo"] == "2026-2")
    texto = r.text
    for prohibido in FORBIDDEN:
        assert prohibido not in texto, prohibido
    assert set(r.json()["filas"][0]) == set(R.CAMPOS_FILA) | {"huella"}
    r = c.post("/movimientos/actos", json={}, headers=CSRF)
    assert r.status_code == 200 and "archivo_pdf" not in r.text


def test_http_sesion_csrf_y_rutas_inexistentes(http, repo):
    assert http.get("/movimientos").status_code == 401
    assert http.post("/movimientos/listado", json={}).status_code in (401, 403)
    c = _login(http, repo, "super@test.local")
    assert c.post("/movimientos/eliminar", json={"id": 1, "huella": "x", "confirmar": True}).status_code == 403
    assert c.post("/movimientos/actos/vincular", json={"seleccion": []}).status_code == 403
    for ruta in ("excel", "csv", "exportar", "pdf", "zip", "imprimir", "alta", "editar", "anular", "regenerar",
                 "eliminar-masivo", "registrar", "pagina"):
        assert c.post(f"/movimientos/{ruta}", json={}, headers=CSRF).status_code in (404, 405), ruta
    assert c.get("/movimientos/listado").status_code == 405


def test_http_eliminar_y_errores_controlados(http, repo, db_conn):
    c = _login(http, repo, "super@test.local")
    with db_conn.transaction() as tx:
        r = c.post("/movimientos/eliminar", json={"id": 987654321, "huella": "x", "confirmar": True}, headers=CSRF)
        assert r.status_code in (404, 409)
        for prohibido in FORBIDDEN:
            assert prohibido not in r.text, prohibido
        r = c.post("/movimientos/eliminar", json={"id": 1, "huella": "x", "confirmar": False}, headers=CSRF)
        assert r.status_code == 422 and r.json()["error"]["message"] == "Primero confirmá la eliminación."
        raise psycopg.Rollback(tx)
