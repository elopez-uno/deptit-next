"""Servicio y HTTP de Designaciones sobre deptit_next_dev con ROLLBACK: permisos B10 (alcance departamento), tenant,
IDs manipulados, B12I capa U, B12H (DENIED / FAILED / POST_OPERATION / fallas tras COMMIT parcial / auditoria que
falla), lecturas sin escrituras (B12F), acto nuevo pendiente y contrato HTTP.  Usuarios del FakeRepo (sin credenciales
humanas)."""

from __future__ import annotations

import psycopg
import pytest

import audit
from designaciones import rules
from designaciones.repository import DesignacionesRepository
from designaciones.service import DesignacionesError
from designaciones_support import (  # noqa: F401  (fixtures)
    audit_rows, audit_store, baseline, db_conn, designaciones, http, session_for, state,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "DELETE ", "Traceback", "psycopg", "institucion_id =")
ABIERTO = 9


@pytest.fixture
def records(service, repo):
    out = {"dep": session_for(service, repo, 3)[0], "lector": session_for(service, repo, 7)[0],
           "coord": session_for(service, repo, 2)[0], "otro_dep": session_for(service, repo, 6)[0]}
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, 1, False)
    out["super"] = sup
    return out


def _huella(svc, rec, did, pid=ABIERTO):
    return next(f for f in svc.periodo(rec, pid)["designaciones"] if f["id"] == did)


def _did(db_conn):
    return db_conn.execute("SELECT id FROM designaciones WHERE periodo_id=9 AND estado='Activa' AND "
                           "COALESCE(funcion_no_docente,0)=0 ORDER BY id LIMIT 1").fetchone()[0]


def _alta(svc, rec, db_conn, **extra):
    cuil = db_conn.execute("SELECT cuil FROM docentes WHERE institucion_id=1 AND departamento_id=1 ORDER BY id "
                           "LIMIT 1").fetchone()[0]
    data = {"cuil": cuil, "cargo": "JTP", "dedicacion": "Simple", "tipo_designacion": "Interino", "ad_honorem": "No",
            "fecha_desde": "2026-08-01", "fecha_hasta": "2026-12-31", "estado": "Activa", "observaciones": "ZZNEXT",
            "acto": {"modo": "pendiente"}, "abierto_huella": svc.overview(rec)["abierto_huella"]}
    data.update(extra)
    return svc.alta(rec, data)


def _contar(db_conn):
    return db_conn.execute("SELECT (SELECT count(*) FROM designaciones), (SELECT count(*) FROM movimientos), "
                           "(SELECT md5(string_agg(md5(d::text), '' ORDER BY d.id)) FROM designaciones d)").fetchone()


# ------------------------------------------------------------------------------------------ lecturas y permisos
def test_overview_permisos_por_rol(designaciones, records):
    dep = designaciones.overview(records["dep"])
    assert dep["permisos"] == {"puede_escribir": True, "puede_borrar": False, "puede_movimiento": True,
                               "puede_vincular": True, "puede_desvincular": False, "es_superadmin": False}
    assert dep["abierto"]["id"] == ABIERTO and dep["historico_abierto"] is False
    assert dep["catalogos"]["tipos_cambio"] == rules.TIPOS_CAMBIO and len(dep["docentes"]) > 0
    sup = designaciones.overview(records["super"])["permisos"]
    assert sup["puede_borrar"] and sup["puede_desvincular"] and sup["es_superadmin"]
    lector = designaciones.overview(records["lector"])["permisos"]
    assert not any(lector[k] for k in ("puede_escribir", "puede_borrar", "puede_movimiento", "puede_vincular"))


def test_coordinador_sin_departamento_no_ve_el_modulo(designaciones, records, service):
    with pytest.raises(DesignacionesError) as exc:
        designaciones.overview(records["coord"])
    assert exc.value.code == "SCOPE_INSTITUTIONAL"


def test_coordinador_con_departamento_lee_pero_no_escribe(designaciones, records, service, db_conn, audit_store):
    service.set_context(records["coord"], 1, 1, False)
    ov = designaciones.overview(records["coord"])
    assert ov["permisos"]["puede_escribir"] is False and len(designaciones.periodo(records["coord"], ABIERTO)[
        "designaciones"]) > 0
    antes = _contar(db_conn)
    with pytest.raises(DesignacionesError) as exc:
        _alta(designaciones, records["coord"], db_conn)
    assert exc.value.code == "DENIED" and "designaciones.write" in exc.value.message
    assert _contar(db_conn) == antes
    assert [(e.outcome, e.operation, e.error_code) for e in audit_store.events] == [
        ("DENIED", "guardar_designacion", "DENY_ROLE_NOT_PERMITTED")]


def test_solo_lectura_denegado(designaciones, records, db_conn, audit_store):
    antes = _contar(db_conn)
    with pytest.raises(DesignacionesError) as exc:
        _alta(designaciones, records["lector"], db_conn)
    assert exc.value.message.startswith("No se pudo registrar la designación: ⛔ Tu usuario es de solo lectura")
    assert _contar(db_conn) == antes and audit_store.events[0].outcome == "DENIED"


def test_usuario_departamento_no_elimina_ni_desvincula(designaciones, records, db_conn, audit_store):
    did = _did(db_conn)
    fila = _huella(designaciones, records["dep"], did)
    antes = _contar(db_conn)
    with pytest.raises(DesignacionesError) as exc:
        designaciones.eliminar(records["dep"], {"id": did, "huella": fila["huella"], "confirmar": True})
    assert exc.value.code == "DENIED" and "designaciones.delete" in exc.value.message
    with pytest.raises(DesignacionesError) as exc:
        designaciones.eliminar_masivo(records["dep"], {"confirmar": True, "seleccion": [{"id": did,
                                                                                        "huella": fila["huella"]}]})
    assert "designaciones.delete" in exc.value.message
    with pytest.raises(DesignacionesError) as exc:
        designaciones.vincular(records["dep"], {"destino": "designaciones", "periodo_id": ABIERTO,
                                                "seleccion": [{"id": did, "huella": fila["huella"]}]}, True)
    assert "documentos.delete" in exc.value.message
    assert _contar(db_conn) == antes
    assert [e.outcome for e in audit_store.events] == ["DENIED"] * 3


def test_lecturas_no_escriben(designaciones, records, db_conn, audit_store):
    """B12F: get_designaciones (v212) y el historial (v268) no reconcilian al leer."""
    antes = _contar(db_conn)
    for pid in (5, 9):
        designaciones.periodo(records["dep"], pid)
    designaciones.overview(records["dep"])
    designaciones.actos(records["dep"])
    designaciones.carga_preview(records["dep"], "cuil\tcargo\n20-11111111-1\tJTP\n")
    designaciones.modelo_excel(records["dep"])
    assert _contar(db_conn) == antes and audit_store.events == [] and audit_rows(db_conn) == []


# ------------------------------------------------------------------------------------------ tenant / IDs manipulados
def test_ids_de_otro_departamento(designaciones, records, db_conn, audit_store):
    ajeno = db_conn.execute("SELECT id FROM designaciones WHERE departamento_id=2 ORDER BY id LIMIT 1").fetchone()[0]
    periodo_ajeno = db_conn.execute("SELECT id FROM periodos WHERE departamento_id=2 LIMIT 1").fetchone()[0]
    rec = records["dep"]
    antes = _contar(db_conn)
    for fn, body in [
        (designaciones.modificar, {"id": ajeno, "tipo_cambio": "Cambio de cargo", "cargo": "Titular",
                                   "observaciones": ""}),
        (designaciones.corregir, {"id": ajeno, "cargo": "JTP", "dedicacion": "Simple", "tipo_designacion": "Interino",
                                  "ad_honorem": "No", "fecha_desde": "2026-08-01", "fecha_hasta": "2026-12-31",
                                  "estado": "Activa", "confirmar": True}),
        (designaciones.eliminar, {"id": ajeno, "confirmar": True}),
    ]:
        with pytest.raises(DesignacionesError) as exc:
            fn(rec, body)
        assert exc.value.code == "NOT_FOUND"
    for body in [{"seleccion": [{"id": ajeno, "huella": "x"}], "confirmar": True}]:
        with pytest.raises(DesignacionesError) as exc:
            designaciones.eliminar_masivo(records["super"], body)
        assert exc.value.code == "SELECCION"
    with pytest.raises(DesignacionesError) as exc:
        designaciones.periodo(rec, periodo_ajeno)
    assert exc.value.code == "NOT_FOUND"
    with pytest.raises(DesignacionesError) as exc:
        designaciones.vincular(rec, {"destino": "designaciones", "periodo_id": ABIERTO,
                                     "seleccion": [{"id": ajeno, "huella": "x"}], "documento_id": 1}, False)
    assert exc.value.code == "SELECCION"
    with pytest.raises(DesignacionesError) as exc:
        designaciones.fechas(rec, {"cambios": [{"id": ajeno, "desde": "2026-08-01", "hasta": "2026-12-31"}]})
    assert exc.value.code == "SELECCION"
    assert _contar(db_conn) == antes and audit_store.events == []


def test_acto_de_otro_departamento_y_acto_nuevo_pendiente(designaciones, records, db_conn, audit_store):
    ajeno = db_conn.execute("SELECT id FROM documentos_respaldo WHERE departamento_id<>1 LIMIT 1").fetchone()[0]
    antes = _contar(db_conn)
    with pytest.raises(DesignacionesError) as exc:
        _alta(designaciones, records["dep"], db_conn, acto={"modo": "existente", "documento_id": ajeno})
    assert exc.value.code == "ACTO_NO_ENCONTRADO"
    with pytest.raises(DesignacionesError) as exc:
        _alta(designaciones, records["dep"], db_conn, acto={"modo": "existente", "documento_id": None})
    assert exc.value.message == ("Elegiste vincular un acto existente, pero todavía no seleccionaste ninguno. "
                                 "Seleccionalo o elegí ‘Dejar pendiente’.")
    with pytest.raises(DesignacionesError) as exc:
        _alta(designaciones, records["dep"], db_conn, acto={"modo": "nuevo"})
    assert exc.value.code == "ACTO_NUEVO_PENDIENTE" and "Cargar un nuevo acto ahora" in exc.value.message
    assert "pendiente de migración" not in exc.value.message  # Etapa 5 / C6: texto actualizado tras E4-07
    assert _contar(db_conn) == antes and audit_store.events == []


def test_tenant_del_cliente_ignorado(designaciones, records, db_conn):
    max_mov = baseline(db_conn)
    _alta(designaciones, records["dep"], db_conn, institucion_id=2, departamento_id=5, periodo_id=1)
    fila = db_conn.execute("SELECT institucion_id, departamento_id, periodo_id FROM designaciones ORDER BY id DESC "
                           "LIMIT 1").fetchone()
    assert fila == (1, 1, ABIERTO)
    mov = db_conn.execute("SELECT institucion_id, departamento_id, periodo_id FROM movimientos WHERE id > %s",
                          [max_mov]).fetchall()
    assert mov == [(1, 1, ABIERTO)]


def test_docente_inexistente_y_valores_fuera_de_catalogo(designaciones, records, db_conn, audit_store):
    for extra, code in [({"cuil": "20-99119911-1"}, "NOT_FOUND"), ({"cargo": "Decano"}, "INVALID"),
                        ({"dedicacion": "Simple Ad Honorem"}, "INVALID"), ({"fecha_hasta": "31/12/2026"}, "INVALID")]:
        with pytest.raises(DesignacionesError) as exc:
            _alta(designaciones, records["dep"], db_conn, **extra)
        assert exc.value.code == code
    assert audit_store.events == []


# ------------------------------------------------------------------------------------------ validaciones de pantalla
def test_validaciones_de_alta(designaciones, records, db_conn):
    with pytest.raises(DesignacionesError) as exc:
        _alta(designaciones, records["dep"], db_conn, funcion_no_docente=True, texto_funcion_no_docente="  ")
    assert exc.value.message == "Completá las funciones no docentes antes de guardar la designación."


def test_validaciones_de_modificacion(designaciones, records, db_conn, audit_store):
    did = _did(db_conn)
    fila = _huella(designaciones, records["dep"], did)
    casos = [
        ({"tipo_cambio": "Aumento de dedicación", "dedicacion": "Simple"}, "debe aumentar las horas"),
        ({"tipo_cambio": "Cambio de tipo de designación", "tipo_designacion": fila["tipo_designacion"]},
         "el tipo de designación no cambió"),
        ({"tipo_cambio": "Cambio de condición Ad Honorem", "ad_honorem": fila["ad_honorem"]},
         "la condición Ad Honorem no cambió"),
        ({"tipo_cambio": "Cambio de función docente / no docente", "funcion_no_docente": True,
          "texto_funcion_no_docente": ""}, "Completá las funciones no docentes antes de guardar la modificación."),
    ]
    for datos, texto in casos:
        res = designaciones.modificar(records["dep"], {"id": did, "huella": fila["huella"], "observaciones":
                                                       fila["observaciones"] or "", **datos})
        assert res["tono"] == "info" and texto in res["mensaje"]
    assert audit_store.events == []


def test_confirmaciones_de_correccion_y_eliminacion(designaciones, records, db_conn):
    did = _did(db_conn)
    fila = _huella(designaciones, records["super"], did)
    base = {"id": did, "huella": fila["huella"], "cargo": "JTP", "dedicacion": "Simple",
            "tipo_designacion": "Interino", "ad_honorem": "No", "fecha_desde": "2026-08-01",
            "fecha_hasta": "2026-12-31", "estado": "Activa"}
    with pytest.raises(DesignacionesError) as exc:
        designaciones.corregir(records["dep"], base)
    assert exc.value.message == "Tenés que confirmar que es una corrección de error."
    with pytest.raises(DesignacionesError) as exc:
        designaciones.corregir(records["dep"], {**base, "funcion_no_docente": True, "confirmar": True})
    assert exc.value.message == "Completá las funciones no docentes antes de guardar la corrección."
    with pytest.raises(DesignacionesError) as exc:
        designaciones.eliminar(records["super"], {"id": did, "huella": fila["huella"]})
    assert exc.value.message == "Primero confirmá la eliminación por error."


def test_grillas_de_fechas_validan(designaciones, records, db_conn):
    did = _did(db_conn)
    with pytest.raises(DesignacionesError) as exc:
        designaciones.fechas(records["dep"], {"cambios": [{"id": did, "desde": "2026-12-31", "hasta": "2026-08-01"}]})
    assert exc.value.message == f"No se pueden guardar los cambios de fechas:\n- Designación ID {did}: Desde no puede ser posterior a Hasta."
    with pytest.raises(DesignacionesError) as exc:
        designaciones.fechas_historicas(records["dep"], {"periodo_id": ABIERTO, "cambios": []})
    assert exc.value.code == "NO_HISTORICO"
    hist = db_conn.execute("SELECT id FROM designaciones WHERE periodo_id=5 ORDER BY id LIMIT 1").fetchone()[0]
    with pytest.raises(DesignacionesError) as exc:
        designaciones.fechas_historicas(records["dep"], {"periodo_id": 5, "cambios": [{"id": hist, "desde": "",
                                                                                         "hasta": "2026-03-01"}]})
    assert exc.value.message == ("No se pueden guardar las correcciones de fechas:\n- "
                                 f"Designación ID {hist}: fecha_desde y fecha_hasta son obligatorias.")


# ------------------------------------------------------------------------------------------ B12I / B12H
def test_huella_obsoleta_no_escribe(designaciones, records, db_conn, audit_store):
    did = _did(db_conn)
    fila = _huella(designaciones, records["dep"], did)
    db_conn.execute("UPDATE designaciones SET observaciones = 'cambio de otra sesión' WHERE id = %s", [did])
    antes = _contar(db_conn)
    with pytest.raises(DesignacionesError) as exc:
        designaciones.modificar(records["dep"], {"id": did, "huella": fila["huella"], "tipo_cambio": "Cambio de cargo",
                                                 "cargo": "Titular" if fila["cargo"] != "Titular" else "JTP",
                                                 "observaciones": "x"})
    assert exc.value.code == "STALE" and "[B12I: get_designaciones]" in exc.value.message
    assert _contar(db_conn) == antes
    assert [(e.outcome, e.error_code, e.metadata.get("coupled_commits")) for e in audit_store.events] == [
        ("FAILED", "StaleDecisionError", 0)]


def test_alta_auditada_por_commit(designaciones, records, db_conn, audit_store):
    res = _alta(designaciones, records["dep"], db_conn)
    assert res["mensaje"] == "Designación registrada correctamente."
    eventos = audit_rows(db_conn)
    ops = {}
    for e in eventos:
        ops.setdefault(str(e["correlation_id"]), []).append(e)
    assert [v[0]["operation"] for v in ops.values()] == ["guardar_designacion", "registrar_movimiento"]
    guardar = list(ops.values())[0]
    assert [e["metadata"]["commit_seq"] for e in guardar] == list(range(1, len(guardar) + 1))
    assert all(e["outcome"] == "SUCCESS" and e["audit_mode"] == "IN_TRANSACTION" for e in eventos)
    assert guardar[0]["entity_type"] == "designacion" and guardar[0]["action"] == "designaciones.write"
    assert guardar[0]["entity_id"] and guardar[0]["metadata"]["entity_param"] == "cuil"
    assert list(ops.values())[1][0]["action"] == "movimientos.write"


def test_falla_del_movimiento_conserva_la_designacion(designaciones, records, db_conn, audit_store, monkeypatch):
    """Como el certificado: la designación ya quedó confirmada (COMMITs propios) aunque el movimiento falle."""
    def boom(*a, **k):
        raise psycopg.errors.InternalError("falla inyectada")

    monkeypatch.setattr(DesignacionesRepository, "insert_movement", boom)
    max_mov = baseline(db_conn)
    antes = db_conn.execute("SELECT count(*) FROM designaciones").fetchone()[0]
    with pytest.raises(DesignacionesError) as exc:
        _alta(designaciones, records["dep"], db_conn)
    assert exc.value.message == ("No se pudo registrar la designación: La base de datos devolvió un error durante la "
                                 "operación: la transacción se revirtió completa.")
    assert db_conn.execute("SELECT count(*) FROM designaciones").fetchone()[0] == antes + 1
    assert db_conn.execute("SELECT count(*) FROM movimientos WHERE id > %s", [max_mov]).fetchone()[0] == 0
    assert [(e.operation, e.outcome, e.metadata.get("coupled_commits")) for e in audit_store.events] == [
        ("registrar_movimiento", "FAILED", 0)]
    assert {e["operation"] for e in audit_rows(db_conn)} == {"guardar_designacion"}


def test_falla_entre_commits_de_un_writer(designaciones, records, db_conn, audit_store, monkeypatch):
    """Falla el UPDATE de función (último COMMIT de guardar_designacion): los anteriores quedan."""
    def boom(*a, **k):
        raise psycopg.errors.InternalError("falla inyectada")

    monkeypatch.setattr(DesignacionesRepository, "update_funcion", boom)
    with pytest.raises(DesignacionesError):
        _alta(designaciones, records["dep"], db_conn)
    exitos = [e for e in audit_rows(db_conn) if e["operation"] == "guardar_designacion"]
    fallo = [e for e in audit_store.events if e.outcome == "FAILED"]
    assert len(fallo) == 1 and fallo[0].metadata["coupled_commits"] == len(exitos) >= 2
    assert fallo[0].correlation_id == str(exitos[0]["correlation_id"])


def test_auditoria_que_falla_revierte_el_commit(designaciones, records, db_conn, audit_store, monkeypatch):
    real = audit.insert_on

    def boom(conn, event):
        raise RuntimeError("audit down")

    monkeypatch.setattr(audit, "insert_on", boom)
    antes = _contar(db_conn)
    with pytest.raises(DesignacionesError) as exc:
        _alta(designaciones, records["dep"], db_conn)
    assert exc.value.code == "AUDIT" and _contar(db_conn) == antes
    assert audit_store.events[-1].error_code == "AuditPersistenceError:AUDIT_INSERT_FAILED"
    monkeypatch.setattr(audit, "insert_on", real)


def test_post_operation_sin_commits(designaciones, records, db_conn, audit_store):
    """``guardar_designacion`` que devuelve la fila existente (misma función, sin confirmación) no confirma nada."""
    from designaciones import escrituras as E
    f = db_conn.execute("SELECT periodo_id, cuil, cargo, dedicacion, horas, tipo_designacion, ad_honorem, fecha_desde, "
                        "fecha_hasta, estado, COALESCE(numero_resolucion,''), COALESCE(funcion_no_docente,0) FROM "
                        "designaciones WHERE periodo_id=9 AND estado='Activa' ORDER BY id LIMIT 1").fetchone()
    scope = designaciones.scope(records["dep"])
    did, _ = designaciones._op(records["dep"], scope, E.W_GUARDAR, lambda u: E.guardar_designacion(
        u, f[0], f[1], f[2], f[3], f[4], f[5], f[6], f[7], f[8], f[9], "", numero_resolucion=f[10],
        funcion_no_docente=bool(f[11])),
        entity_raw=f[1])
    assert did is not None and audit_rows(db_conn) == []
    assert [(e.outcome, e.audit_mode, e.metadata.get("post_reason")) for e in audit_store.events] == [
        ("SUCCESS", "POST_OPERATION", "NO_POOLED_COMMIT")]


# ------------------------------------------------------------------------------------------ carga rapida
def test_carga_rapida_bloqueos(designaciones, records, db_conn):
    with pytest.raises(DesignacionesError) as exc:
        designaciones.carga_ejecutar(records["dep"], "cuil\tcargo\n20-99119911-1\tJTP\n", False)
    assert exc.value.message == "No se cargó nada. Primero registrá los docentes que faltan."
    fila = db_conn.execute("SELECT cuil, cargo, dedicacion, tipo_designacion, ad_honorem, fecha_desde, fecha_hasta "
                           "FROM designaciones WHERE periodo_id=9 ORDER BY id LIMIT 1").fetchone()
    texto = ("cuil\tcargo\tdedicacion\ttipo_designacion\tad_honorem\tfecha_desde\tfecha_hasta\n"
             + "\t".join(fila) + "\n" + "\t".join(fila) + "\n")
    prev = designaciones.carga_preview(records["dep"], texto)
    assert prev["duplicados"] and not prev["inexistentes"]
    with pytest.raises(DesignacionesError) as exc:
        designaciones.carga_ejecutar(records["dep"], texto, False)
    assert exc.value.code == "DUPLICATES"
    assert designaciones.carga_preview(records["dep"], "sin datos")["aviso"] == (
        "No pude detectar filas válidas. Revisá que la tabla tenga CUIL y datos de designación.")


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
    assert http.get("/designaciones").status_code == 401
    assert http.post("/designaciones/periodo", json={"periodo_id": ABIERTO}, headers=CSRF).status_code == 401
    login(http, repo, "info@test.local")
    r = http.get("/designaciones")
    assert r.status_code == 200
    clean(r, repo)
    assert http.post("/designaciones/periodo", json={"periodo_id": ABIERTO}).json()["error"]["code"] == "CSRF"
    r = http.post("/designaciones/periodo", json={"periodo_id": ABIERTO}, headers=CSRF)
    assert r.status_code == 200 and r.json()["periodo"]["id"] == ABIERTO
    clean(r, repo)
    r = http.post("/designaciones/periodo", json={"periodo_id": "9 OR 1=1"}, headers=CSRF)
    assert r.status_code == 422
    clean(r, repo)
    r = http.post("/designaciones/alta", json={"cuil": "x"}, headers=CSRF)
    assert r.status_code in (404, 422)
    clean(r, repo)
    r = http.get("/designaciones/modelo-excel")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    r = http.post("/designaciones/actos", json={}, headers=CSRF)
    assert r.status_code == 200 and "documentos" in r.json()
    clock.advance(30 * 60)
    assert http.get("/designaciones").json()["error"]["code"] == "IDLE_TIMEOUT"


def test_http_solo_lectura(http, repo):
    login(http, repo, "lector@test.local")
    assert http.get("/designaciones").json()["permisos"]["puede_escribir"] is False
