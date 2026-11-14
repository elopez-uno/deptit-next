"""Servicio y HTTP de Extension (variante propia del servicio de Investigacion) sobre deptit_next_dev con ROLLBACK: lecturas de las 8 pestañas, permisos B10 por rol
(departamento creador, eliminaciones solo superadmin, coordinador y solo lectura sin escritura), B12I capa T (lock
``asignacion_proyecto`` por institucion, solo 3 writers, 30 s / 0,1 s) y capa U (revalidacion), B12H (DENIED / FAILED /
POST_OPERATION / auditoria que falla), B12D (fallo de base -> FAILED, sin escrituras), periodo actual / historico
abierto por excepcion / sin periodo, capacidad diagnostica y contrato HTTP.  Usuarios del FakeRepo."""

from __future__ import annotations

import base64

import psycopg
import pytest

import audit
from extension import escrituras as E
from extension.service import MSG_CARGA_SIN_PERIODO, ExtensionError, ExtensionService
from extension_support import (  # noqa: F401  (fixtures)
    EXTRA_DEPARTMENTS, audit_rows, audit_store, db_conn, http, extension, lock_conn, make_extension,
    session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "DELETE ", "Traceback", "psycopg", "institucion_id =")
LOCK_KEY = "deptit_b12i_asignacion_proyecto:1"


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
        "SELECT (SELECT count(*) FROM proyectos_extension), (SELECT count(*) FROM extension_docente), "
        "(SELECT count(*) FROM movimientos), (SELECT count(*) FROM documentos_respaldo_proyectos), "
        "(SELECT md5(string_agg(md5(p::text), '' ORDER BY p.id)) FROM proyectos_extension p), "
        "(SELECT md5(string_agg(md5(i::text), '' ORDER BY i.id)) FROM extension_docente i), "
        "(SELECT count(*) FROM b12h_audit_log)").fetchone()


def _probe():
    import db
    settings = db.load_settings()
    conn = psycopg.connect(settings["database_url"], autocommit=True, connect_timeout=5,
                           application_name="deptit_next_tests_probe")
    db.verify_identity(conn)
    return conn


def _proyecto_propio(svc, rec):
    return svc.editar_proyectos(rec)["filas"][0]


def _asignar_uno(svc, rec, horas=1.0, rol="Integrante"):
    ov = svc.overview(rec)
    proy = svc.asignar_proyectos(rec)["proyectos"][0]
    det = svc.asignar_detalle(rec, {"proyecto_id": proy["id"]})
    d = det["docentes"][0]
    return svc.asignar(rec, {"proyecto_id": proy["id"], "huella_proyecto": proy["huella"],
                             "huella_periodo": ov["huella_periodo"], "huella_integrantes": det["huella_integrantes"],
                             "docentes": [{"cuil": d["cuil"], "rol": rol, "horas": horas}]})


# ------------------------------------------------------------------------------------------ lecturas
def test_lecturas_de_las_ocho_pestanas_no_escriben(extension, records, db_conn, audit_store):
    rec = records["dep"]
    antes = _contar(db_conn)
    ov = extension.overview(rec)
    assert ov["abierto"]["nombre"] == "2026-2" and not ov["historico_abierto"]
    extension.alertas(rec)
    vig = extension.vigentes(rec)
    assert vig["filas"] and vig["lista"]
    assert "costo_total_sueldos_v258" not in vig["filas"][0]  # D3: pendiente de Sueldos
    ficha = extension.ficha(rec, {"proyecto_id": vig["filas"][0]["id"]})
    assert ficha["encabezado"]["nombre"] and "participacion" in ficha
    extension.actos(rec)
    proy = extension.asignar_proyectos(rec)["proyectos"]
    det = extension.asignar_detalle(rec, {"proyecto_id": proy[0]["id"]})
    assert det["padron"]["consolidado"] == det["padron"]["selector"]
    for p in ov["periodos"]:
        extension.asignaciones(rec, {"periodo_id": p["id"]})
    hist = extension.historial(rec)
    assert len(hist["filas"]) == 14 and hist["situaciones"][0] == "Todos"
    extension.historial_asignaciones(rec, {"proyecto_id": hist["filas"][0]["id"]})
    extension.editar_proyectos(rec)
    filas = extension.editar_asignaciones(rec)["filas"]
    extension.editar_asignacion_opciones(rec, {"asignacion_id": filas[0]["id"]})
    extension.capacidad(rec, {"cuiles": [filas[0]["cuil"]], "excluir_id": filas[0]["id"]})
    extension.suspender_proyectos(rec)
    extension.archivar_proyectos(rec)
    extension.post_accion(rec, {"cuil": filas[0]["cuil"], "periodo_id": ov["abierto"]["id"]})
    assert extension.modelo_excel(rec)[:2] == b"PK"
    assert _contar(db_conn) == antes and audit_store.events == []


def test_overview_permisos_por_rol(extension, records):
    p = {k: extension.overview(records[k])["permisos"] for k in ("dep", "lector", "coord_dep", "super")}
    assert p["dep"] == {"puede_escribir": True, "puede_borrar": False, "puede_cargar": True, "puede_movimiento": True,
                        "puede_vincular_acto": True, "puede_desvincular_acto": False}
    assert not any(p["lector"].values()) and not any(p["coord_dep"].values())
    assert all(p["super"].values())


def test_coordinador_sin_departamento_no_ve_el_modulo(extension, records):
    with pytest.raises(ExtensionError) as e:
        extension.overview(records["coord"])
    assert e.value.code == "SCOPE_INSTITUTIONAL"


@pytest.mark.parametrize("quien", ["lector", "coord_dep"])
def test_coordinador_y_solo_lectura_no_escriben(extension, records, db_conn, audit_store, quien):
    antes = _contar(db_conn)
    with pytest.raises(ExtensionError) as e:
        extension.guardar_proyecto(records[quien], dict(nombre="ZZNEXT", codigo="", instituto="", anio_llamado=2025,
                                                            fecha_inicio="2025-01-01", fecha_fin="2025-12-31",
                                                            estado="Activo", observaciones=""))
    assert e.value.status == 403
    assert [(x.operation, x.outcome, x.audit_mode) for x in audit_store.events] == [
        ("guardar_proyecto_extension", "DENIED", "SEPARATE_TRANSACTION")]
    assert _contar(db_conn) == antes


def test_usuario_departamento_no_elimina_asignacion_por_error(extension, records, db_conn, audit_store):
    rec = records["dep"]
    proy = extension.asignar_proyectos(rec)["proyectos"]
    det = next(d for d in (extension.asignar_detalle(rec, {"proyecto_id": p["id"]}) for p in proy) if d["eliminables"])
    f = det["eliminables"][0]
    with pytest.raises(ExtensionError) as e:
        extension.eliminar_asignacion_error(rec, {"proyecto_id": f["proyecto_id"], "asignacion_id": f["id"],
                                                      "huella": f["huella"], "confirmar": True})
    assert e.value.status == 403
    assert audit_store.events[-1].operation == "eliminar_extension_docente_definitivamente"


def test_ids_manipulados_y_tenant_del_cliente_ignorado(extension, records, db_conn):
    rec = records["dep"]
    with pytest.raises(ExtensionError) as e:
        extension.ficha(rec, {"proyecto_id": "1 OR 1=1"})
    assert e.value.status == 422
    with pytest.raises(ExtensionError) as e:
        extension.asignaciones(rec, {"periodo_id": 999999, "institucion_id": 2, "departamento_id": 5})
    assert e.value.status == 404
    ajeno = extension.asignaciones(records["dep2"], {"periodo_id": extension.overview(records["dep2"])["abierto"]["id"]})
    propios = {f["cuil"] for f in extension.editar_asignaciones(rec)["filas"]}
    with pytest.raises(ExtensionError):
        extension.baja_asignacion(rec, {"asignacion_id": 10, "huella": "x", "confirmar": True,
                                            "fecha_baja": "2026-10-26", "motivo": ""})  # asignacion del dep 4
    assert ajeno is not None and propios


# ------------------------------------------------------------------------------------------ B12H
def test_alta_auditada_por_operacion_y_commit(extension, records, db_conn, audit_store):
    rec = records["dep"]
    extension.guardar_proyecto(rec, dict(nombre="ZZNEXT B12H", codigo="ZZNEXT-H", instituto="", anio_llamado=2025,
                                             fecha_inicio="2025-01-01", fecha_fin="2026-12-31", estado="Activo",
                                             observaciones=""))
    ev = audit_rows(db_conn)
    assert [(e["operation"], e["action"], e["action_scope"], e["entity_type"], e["outcome"], e["audit_mode"])
            for e in ev] == [("guardar_proyecto_extension", "extension.write", "institution",
                              "proyecto_extension", "SUCCESS", "IN_TRANSACTION")]
    assert ev[0]["metadata"]["commit_seq"] == 1 and ev[0]["entity_id"] is None


def test_asignar_son_dos_operaciones_por_docente(extension, records, db_conn, audit_store):
    res = _asignar_uno(extension, records["dep"])
    assert res["mensaje"] == "Asignación finalizada: 1 nueva/s."
    ev = audit_rows(db_conn)
    assert [(e["operation"], e["action"], e["entity_type"]) for e in ev] == [
        ("guardar_extension_docente", "extension.write", "asignacion_extension"),
        ("registrar_movimiento", "movimientos.write", "movimiento")]
    assert len({e["correlation_id"] for e in ev}) == 2
    assert ev[0]["entity_id"] is not None and ev[0]["metadata"]["entity_param"] == "proyecto_id"


def test_auditoria_que_falla_revierte_el_commit(extension, records, db_conn, audit_store, monkeypatch):
    antes = _contar(db_conn)

    def falla(conn, event):
        raise RuntimeError("audit down")
    monkeypatch.setattr(audit, "insert_on", falla)
    with pytest.raises(ExtensionError) as e:
        extension.guardar_proyecto(records["dep"], dict(nombre="ZZNEXT A", codigo="", instituto="",
                                                            anio_llamado=2025, fecha_inicio="2025-01-01",
                                                            fecha_fin="2025-12-31", estado="Activo", observaciones=""))
    assert e.value.code == "AUDIT"
    assert _contar(db_conn) == antes
    assert audit_store.events[-1].error_code == "AuditPersistenceError:AUDIT_INSERT_FAILED"


def test_fallo_de_base_en_writer_es_failed_sin_escrituras(extension, records, db_conn, audit_store, monkeypatch):
    """B12D: el texto del driver nunca llega a la pantalla; 0 escrituras después del fallo."""
    antes = _contar(db_conn)
    from extension.repository import ExtensionRepository

    def roto(self, *a, **k):
        raise psycopg.errors.DeadlockDetected("deadlock detected")
    monkeypatch.setattr(ExtensionRepository, "mutate_rowcount", roto)
    rec = records["dep2"]  # el dep 1 no creo proyectos de Extension (datos reales)
    f = _proyecto_propio(extension, rec)
    with pytest.raises(ExtensionError) as e:
        extension.editar_proyecto(rec, {"proyecto_id": f["id"], "huella": f["huella"], "nombre": "x",
                                            "codigo": f["codigo_proyecto"], "instituto": "",
                                            "anio_llamado": int(f["anio_llamado"]), "fecha_inicio": f["fecha_inicio"],
                                            "fecha_fin": f["fecha_fin"], "estado": "Activo", "observaciones": ""})
    assert e.value.status == 503 and "deadlock" not in e.value.message
    assert _contar(db_conn) == antes
    assert (audit_store.events[-1].outcome, audit_store.events[-1].error_code) == ("FAILED", "DeadlockDetected")


def test_rechazos_de_negocio_sin_escritura_quedan_post_operation(extension, records, db_conn, audit_store):
    rec = records["dep2"]  # el dep 1 no creo proyectos de Extension (datos reales)
    f = _proyecto_propio(extension, rec)
    with pytest.raises(ExtensionError):
        extension.editar_proyecto(rec, {"proyecto_id": f["id"], "huella": f["huella"], "nombre": " ",
                                            "codigo": "", "instituto": "", "anio_llamado": 2025,
                                            "fecha_inicio": "2025-01-01", "fecha_fin": "2025-12-31", "estado": "Activo",
                                            "observaciones": ""})
    assert [(e.operation, e.outcome, e.audit_mode, e.metadata.get("post_reason")) for e in audit_store.events] == [
        ("actualizar_proyecto_extension", "SUCCESS", "POST_OPERATION", "NO_POOLED_COMMIT")]


# ------------------------------------------------------------------------------------------ B12I
def test_lock_solo_en_los_tres_writers_de_asignacion(extension, records, db_conn, monkeypatch):
    usados = []
    real = extension._consistency_lock

    def espia(scope):
        usados.append("lock")
        return real(scope)
    monkeypatch.setattr(extension, "_consistency_lock", espia)
    rec = records["dep2"]  # el dep 1 no creo proyectos de Extension (datos reales)
    _asignar_uno(extension, rec)
    assert usados == ["lock"]  # alta (guardar_extension_docente); el movimiento no toma lock
    f = extension.editar_asignaciones(rec)["filas"][0]
    extension.baja_asignacion(rec, {"asignacion_id": f["id"], "huella": f["huella"], "confirmar": True,
                                        "fecha_baja": "2026-10-26", "motivo": ""})
    p = _proyecto_propio(extension, rec)
    extension.archivar(rec, {"proyecto_id": p["id"], "huella": p["huella"], "confirmar": True, "motivo": ""})
    extension.guardar_proyecto(rec, dict(nombre="ZZNEXT L", codigo="", instituto="", anio_llamado=2025,
                                             fecha_inicio="2025-01-01", fecha_fin="2025-12-31", estado="Activo",
                                             observaciones=""))
    assert usados == ["lock"]  # baja, archivo y alta de proyecto sin lock


def test_lock_timeout_en_alta_se_informa_y_el_bucle_sigue(service, repo, db_conn, lock_conn, audit_store):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    svc = make_extension(service, audit_store, db_conn, lock_connection=lock_conn, lock_wait_seconds=0.3)
    rec = session_for(service, repo, 3)[0]
    antes = _contar(db_conn)
    holder = _probe()
    try:
        holder.execute("SELECT pg_advisory_lock(hashtext(%s))", [LOCK_KEY])
        res = _asignar_uno(svc, rec)
    finally:
        holder.execute("SELECT pg_advisory_unlock(hashtext(%s))", [LOCK_KEY])
        holder.close()
    assert res["mensaje"].startswith("Asignación finalizada: 0 nueva/s, 1 error/es. ")
    assert "[B12I: asignacion_proyecto]" in res["mensaje"]
    assert _contar(db_conn) == antes
    assert (audit_store.events[-1].error_code, audit_store.events[-1].metadata["coupled_commits"]) == (
        "ConsistencyLockError", 0)


def test_lock_espera_30_segundos_con_reintento_cada_100ms(service, repo, db_conn, lock_conn, audit_store):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    reloj = {"t": 0.0, "sleeps": 0}

    def sleep(s):
        assert s == 0.1
        reloj["t"] += s
        reloj["sleeps"] += 1
    svc = make_extension(service, audit_store, db_conn, lock_connection=lock_conn, clock=lambda: reloj["t"],
                             sleep=sleep)
    rec = session_for(service, repo, 3)[0]
    f = svc.editar_asignaciones(rec)["filas"][0]
    actual = next(o for o in svc.editar_asignacion_opciones(rec, {"asignacion_id": f["id"]})["docentes"] if o["actual"])
    holder = _probe()
    try:
        holder.execute("SELECT pg_advisory_lock(hashtext(%s))", [LOCK_KEY])
        with pytest.raises(ExtensionError) as e:
            svc.editar_asignacion(rec, {"asignacion_id": f["id"], "huella": f["huella"], "proyecto_id": int(f["proyecto_id"]),
                                        "docente_etiqueta": actual["etiqueta"], "rol": "Integrante", "horas": 1})
    finally:
        holder.execute("SELECT pg_advisory_unlock(hashtext(%s))", [LOCK_KEY])
        holder.close()
    assert e.value.code == "LOCK" and 299 <= reloj["sleeps"] <= 301 and reloj["t"] >= 30.0


def test_lock_tomado_durante_la_escritura_y_liberado(extension, records, db_conn, monkeypatch):
    probe = _probe()
    visto = []
    real = E.guardar_extension_docente

    def espia(u, *a, **k):
        visto.append(probe.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s))", [LOCK_KEY]).fetchone()[0])
        return real(u, *a, **k)
    monkeypatch.setattr(E, "guardar_extension_docente", espia)
    try:
        _asignar_uno(extension, records["dep"])
        assert visto == [False]
        assert probe.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s))", [LOCK_KEY]).fetchone()[0] is True
    finally:
        probe.close()


def test_revalidacion_capa_u_no_escribe(extension, records, db_conn, audit_store, monkeypatch):
    rec = records["dep2"]  # el dep 1 no creo proyectos de Extension (datos reales)
    f = _proyecto_propio(extension, rec)
    real = ExtensionService._proyecto_administrable

    def selecciona_y_otro_cambia(self, scope, pid, huella, filtro):
        out = real(self, scope, pid, huella, filtro)
        db_conn.execute("UPDATE proyectos_extension SET observaciones='cambio concurrente' WHERE id=%s", [pid])
        return out
    monkeypatch.setattr(ExtensionService, "_proyecto_administrable", selecciona_y_otro_cambia)
    with pytest.raises(ExtensionError) as e:
        extension.archivar(rec, {"proyecto_id": f["id"], "huella": f["huella"], "confirmar": True, "motivo": ""})
    assert e.value.code == "STALE"
    assert db_conn.execute("SELECT estado FROM proyectos_extension WHERE id=%s", [f["id"]]).fetchone()[0] != "Archivado"
    assert (audit_store.events[-1].outcome, audit_store.events[-1].error_code) == ("FAILED", "StaleDecisionError")


# ------------------------------------------------------------------------------------------ periodos / historico
def test_historico_abierto_por_excepcion_permite_asignar(extension, records, db_conn):
    per = dict(db_conn.execute("SELECT nombre, id FROM periodos WHERE institucion_id=1 AND departamento_id=1").fetchall())
    db_conn.execute("UPDATE periodos SET estado='Cerrado' WHERE institucion_id=1 AND departamento_id=1")
    db_conn.execute("UPDATE periodos SET estado='Abierto' WHERE id=%s", [per["2026-1"]])
    rec = records["dep"]
    ov = extension.overview(rec)
    assert ov["abierto"]["id"] == per["2026-1"] and ov["historico_abierto"]
    antes = db_conn.execute("SELECT count(*) FROM extension_docente WHERE periodo_id=%s", [per["2026-1"]]).fetchone()[0]
    res = _asignar_uno(extension, rec)
    assert res["mensaje"] == "Asignación finalizada: 1 nueva/s."
    assert db_conn.execute("SELECT count(*) FROM extension_docente WHERE periodo_id=%s",
                           [per["2026-1"]]).fetchone()[0] == antes + 1
    # Foto al cierre v183 (comportamiento heredado): la asignacion recien creada tiene ``fecha_carga`` posterior al
    # cierre del historico, asi que Editar/Bajas no la listan; igual que el certificado.
    from extension_support import certified_extension
    cert = certified_extension(db_conn, 1, 1)["get_extension_docente"](periodo_id=per["2026-1"])
    assert len(extension.editar_asignaciones(rec)["filas"]) == len(cert) == antes


def test_sin_periodo_abierto(extension, records, db_conn):
    db_conn.execute("UPDATE periodos SET estado='Cerrado' WHERE institucion_id=1 AND departamento_id=1")
    rec = records["dep"]
    ov = extension.overview(rec)
    assert ov["abierto"] is None
    assert extension.vigentes(rec)["caption"].startswith("No hay un período abierto")
    assert extension.asignar_proyectos(rec)["periodo"] is None
    assert extension.editar_asignaciones(rec)["periodo"] is None
    with pytest.raises(ExtensionError) as e:
        extension.suspender(rec, {"proyecto_id": 1, "confirmar": True, "motivo": "x", "fecha_suspension": "2026-10-26"})
    assert e.value.message == "No hay período abierto para aplicar la suspensión."
    r = extension.guardar_proyecto(rec, dict(nombre="ZZNEXT sin periodo", codigo="", instituto="",
                                                 anio_llamado=2025, fecha_inicio="2025-01-01", fecha_fin="2025-12-31",
                                                 estado="Activo", observaciones=""))
    assert r["tono"] == "success"  # el catalogo no depende del periodo
    from openpyxl import load_workbook
    from io import BytesIO
    wb = load_workbook(BytesIO(extension.modelo_excel(rec)))
    ws = wb["Asignar docentes"]
    ws.cell(row=2, column=2, value="Proyecto")
    ws.cell(row=2, column=3, value="X | 20-1")
    out = BytesIO()
    wb.save(out)
    with pytest.raises(ExtensionError) as e:
        extension.carga_ejecutar(rec, {"archivo": base64.b64encode(out.getvalue()).decode(), "confirmar": True,
                                           "huella_periodo": ov["huella_periodo"]})
    assert e.value.message == MSG_CARGA_SIN_PERIODO


def test_capacidad_diagnostica_no_bloquea_el_exceso(extension, records, db_conn):
    res = _asignar_uno(extension, records["dep"], horas=100)
    assert res["mensaje"] == "Asignación finalizada: 1 nueva/s."
    with pytest.raises(ExtensionError):
        _asignar_uno(extension, records["dep"], horas=101)  # rango 0-100 de la pantalla


def test_carga_rapida_vacia_es_informativa(extension, records):
    rec = records["dep"]
    archivo = base64.b64encode(extension.modelo_excel(rec)).decode()
    with pytest.raises(ExtensionError) as e:
        extension.carga_preview(rec, {"archivo": archivo})
    assert e.value.tone == "info" and "no contiene proyectos nuevos" in e.value.message


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
    assert http.get("/extension").status_code == 401
    assert http.post("/extension/vigentes", json={}, headers=CSRF).status_code == 401
    login(http, repo, "info@test.local")
    r = http.get("/extension")
    assert r.status_code == 200
    clean(r, repo)
    assert http.post("/extension/vigentes", json={}).json()["error"]["code"] == "CSRF"
    for ruta in ("vigentes", "historial", "editar/proyectos", "editar/asignaciones", "asignar/proyectos", "actos",
                 "alertas", "bajas/suspender/proyectos", "bajas/archivar/proyectos"):
        r = http.post(f"/extension/{ruta}", json={}, headers=CSRF)
        assert r.status_code == 200, ruta
        clean(r, repo)
    r = http.post("/extension/asignaciones", json={"periodo_id": "9 OR 1=1"}, headers=CSRF)
    assert r.status_code == 422
    clean(r, repo)
    r = http.get("/extension/modelo-excel")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert 'filename="modelo_carga_rapida_proyectos_y_docentes_extension.xlsx"' in r.headers["content-disposition"]
    clock.advance(30 * 60)
    assert http.get("/extension").json()["error"]["code"] == "IDLE_TIMEOUT"


def test_http_solo_lectura(http, repo):
    login(http, repo, "lector@test.local")
    assert not any(http.get("/extension").json()["permisos"].values())
    r = http.post("/extension/proyecto/guardar", json={"nombre": "ZZ", "codigo": "", "instituto": "",
                                                          "anio_llamado": 2025, "fecha_inicio": "2025-01-01",
                                                          "fecha_fin": "2025-12-31", "estado": "Activo"},
                  headers=CSRF)
    assert r.status_code == 403


def test_lock_compartido_con_investigacion(extension, records, db_conn, lock_conn, service, repo, audit_store):
    """B12I: la familia ``asignacion_proyecto`` es UNA para Investigacion y Extension (misma clave por institucion, mismos
    30 s / 0,1 s); una asignacion de Investigacion en curso bloquea la de Extension y viceversa."""
    from investigacion import service as IS
    from extension import service as XS
    assert XS.PROJECT_LOCK_FORMAT == IS.PROJECT_LOCK_FORMAT == "deptit_b12i_asignacion_proyecto:{inst}"
    assert (XS.LOCK_WAIT_SECONDS, XS.LOCK_POLL_SECONDS, XS.LOCK_FAMILY) == (IS.LOCK_WAIT_SECONDS, IS.LOCK_POLL_SECONDS,
                                                                           IS.LOCK_FAMILY)
    assert XS.LOCK_WRITERS == {"guardar_extension_docente", "actualizar_extension_docente",
                               "cargar_asignaciones_proyectos_excel_v217"}
    from investigacion_support import make_investigacion
    inv = make_investigacion(service, audit_store, db_conn, lock_connection=lock_conn)
    rec = records["dep"]
    scope = inv.scope(rec)
    with inv._consistency_lock(scope):  # Investigacion tiene el lock de la institucion
        svc = make_extension(service, audit_store, db_conn, lock_connection=_probe(), lock_wait_seconds=0.2)
        res = _asignar_uno(svc, rec)
    assert "[B12I: asignacion_proyecto]" in res["mensaje"] and res["mensaje"].startswith("Asignación finalizada: 0 nueva/s")


def test_asignar_exige_horas_mayores_a_cero_y_valor_inicial_uno(extension, records, db_conn, audit_store):
    rec = records["dep"]
    assert extension.overview(rec)["horas_defecto_asignar"] == 1.0
    antes = _contar(db_conn)
    with pytest.raises(ExtensionError) as e:
        _asignar_uno(extension, rec, horas=0)
    assert e.value.message.endswith("las horas deben ser mayores a 0.") and audit_store.events == []
    assert _contar(db_conn) == antes
    res = _asignar_uno(extension, rec)  # sin "horas": 1 por defecto
    assert res["mensaje"] == "Asignación finalizada: 1 nueva/s."
    mov = db_conn.execute("SELECT tipo_movimiento, detalle FROM movimientos ORDER BY id DESC LIMIT 1").fetchone()
    assert mov[0] == "Asignación a extensión" and "Se asignaron 1 hs semanales al proyecto" in mov[1]


def test_bajas_suspension_archivo_y_eliminacion_sin_movimientos(extension, records, db_conn, audit_store):
    """Ningun writer de proyecto, baja ni eliminacion registra movimientos (solo asignar / editar / carga rapida)."""
    rec, sup = records["dep2"], records["super"]
    movs = db_conn.execute("SELECT count(*) FROM movimientos").fetchone()[0]
    f = extension.editar_asignaciones(rec)["filas"][0]
    extension.baja_asignacion(rec, {"asignacion_id": f["id"], "huella": f["huella"], "confirmar": True,
                                    "fecha_baja": "2026-10-26", "motivo": "ZZNEXT"})
    ov = extension.overview(rec)
    p = extension.suspender_proyectos(rec)["filas"][0]
    extension.suspender(rec, {"proyecto_id": p["id"], "huella": p["huella"], "huella_periodo": ov["huella_periodo"],
                              "confirmar": True, "motivo": "ZZNEXT", "fecha_suspension": "2026-10-26"})
    a = extension.archivar_proyectos(rec)["filas"][0]
    extension.archivar(rec, {"proyecto_id": a["id"], "huella": a["huella"], "confirmar": True, "motivo": "ZZNEXT"})
    extension.guardar_proyecto(rec, dict(nombre="ZZNEXT eliminar", codigo="ZZNEXT-DEL", instituto="", anio_llamado=2025,
                                         fecha_inicio="2025-01-01", fecha_fin="2026-12-31", estado="Activo",
                                         observaciones=""))
    service_sup = extension.editar_proyectos(sup)["filas"]
    d = next(x for x in service_sup if x["codigo_proyecto"] == "ZZNEXT-DEL")
    extension.eliminar_proyecto(sup, {"proyecto_id": d["id"], "huella": d["huella"], "confirmar": True,
                                      "confirmacion": "ZZNEXT-DEL"})
    assert db_conn.execute("SELECT count(*) FROM movimientos").fetchone()[0] == movs
    ops = [e["operation"] for e in audit_rows(db_conn)]
    assert ops == ["eliminar_extension_docente", "suspender_proyecto_extension", "archivar_proyecto_extension",
                   "guardar_proyecto_extension", "eliminar_proyecto_extension"]
