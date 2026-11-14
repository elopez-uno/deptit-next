"""Servicio de Disposiciones: lecturas sin escrituras, permisos B10 por rol (eliminar solo superadmin; plantilla
institucional con institucion elegida; coordinador, solo lectura y modo comercial read_only sin escritura), B12H por
writer (entity_type/entity_param certificados, POST_OPERATION FILESYSTEM_ONLY de la plantilla), B12I sin lock,
almacenamiento B12E (aislamiento institucion/departamento, path traversal, documento ajeno, legado bloqueado sin tocar el
disco, plantilla de otra institucion), descargas y ZIP por FastAPI, HTTP (sesion, CSRF, respuestas limpias, rutas
inexistentes) y ausencias (sin PDF, Excel, edicion ni anulacion posterior, sin migracion de legado)."""

from __future__ import annotations

import base64
import inspect
import io
import os
import zipfile

import psycopg
import pytest

import disposiciones_plantilla as P
from disposiciones import service as SV
from disposiciones import storage as S
from disposiciones.service import DisposicionesError, DisposicionesService
from disposiciones_support import (  # noqa: F401  (fixtures)
    DEP_NOMBRES, FIXED_TODAY, audit_rows, audit_store, db_conn, disposiciones, http, make_disposiciones, periodo_id,
    record_for, session_for, storage_root,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")
CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "DELETE ", "Traceback", "psycopg", "institucion_id =", "C:\\", "C:/", "documents", "storage",
             "deptit_postgres", "disposiciones_generadas", ".docx\\")


@pytest.fixture
def records(service, repo):
    out = {"dep": session_for(service, repo, 3)[0], "lector": session_for(service, repo, 7)[0],
           "dep2": session_for(service, repo, 6)[0], "uba": session_for(service, repo, 4)[0]}
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, 1, False)
    out["super"] = sup
    coord = session_for(service, repo, 2)[0]
    service.set_context(coord, 1, 1, False)
    out["coord_dep"] = coord
    out["coord"] = session_for(service, repo, 2)[0]
    return out


def _contar(db_conn):
    return db_conn.execute(
        "SELECT (SELECT count(*) FROM disposiciones), (SELECT count(*) FROM movimientos), "
        "(SELECT md5(string_agg(md5(d::text), '' ORDER BY d.id)) FROM disposiciones d), "
        "(SELECT md5(string_agg(md5(p::text), '' ORDER BY p.id)) FROM disposicion_parametros p), "
        "(SELECT md5(string_agg(md5(p::text), '' ORDER BY p.id)) FROM disposicion_docente_parametros p), "
        "(SELECT md5(string_agg(md5(p::text), '' ORDER BY p.id)) FROM disposicion_docente_designaciones p), "
        "(SELECT count(*) FROM estado_consulta_designacion), (SELECT count(*) FROM b12h_audit_log)").fetchone()


def _plantilla(root, inst=1, data=None):
    d = root / f"inst_{inst}" / "plantillas"
    d.mkdir(parents=True, exist_ok=True)
    (d / "disposicion.docx").write_bytes(data or P.construir())


def _vista(svc, rec, db_conn, dep=1):
    pid = periodo_id(db_conn, dep, "2026-2")
    for f in svc.periodo(rec, {"periodo_id": pid})["habilitados"]:
        v = svc.docente(rec, {"periodo_id": pid, "cuil": f["cuil"]})
        if v["designaciones"] and not v["tiene_no_docente"]:
            return pid, v
    raise AssertionError


def _generar(svc, rec, pid, v, estado="Borrador"):
    return svc.generar(rec, {"periodo_id": pid, "cuil": v["cuil"], "huella": v["huella"],
                             "fecha": FIXED_TODAY.isoformat(), "tipo": "Asignación de funciones docentes",
                             "estado": estado, "observaciones": "", "incluir_concursado": v["tiene_concursado"],
                             "incluir_interino": v["tiene_interino"],
                             "incluir_investigacion": v["tiene_investigacion_o_extension"],
                             "designaciones": [{k: d[k] for k in ("designacion_id", "fecha_desde", "fecha_hasta",
                                                                  "observaciones")} for d in v["designaciones"]]})


# ------------------------------------------------------------------------------------------ lecturas
def test_lecturas_de_las_tres_pestanas_no_escriben(disposiciones, records, db_conn, audit_store, storage_root):
    antes = _contar(db_conn)
    for rol in ("dep", "lector", "super", "coord_dep"):
        rec = records[rol]
        ov = disposiciones.overview(rec)
        assert [c["clave"] for c in ov["campos"]] == [k for k, _ in SV.R.CAMPOS_CONFIGURACION]
        assert ov["estados"] == ["Borrador", "Emitida", "Anulada"] and ov["tipo_defecto"] == "Asignación de funciones docentes"
        assert ov["plantilla"]["status"] == "MISSING"  # D3: ausencia de plantilla = estado valido y visible
        assert ov["periodo_defecto"] == periodo_id(db_conn, 1, "2026-2")
        info = disposiciones.periodo(rec, {"periodo_id": ov["periodo_defecto"]})
        assert info["numero_inicial"] == 72 and info["habilitados"][0]["numero_disposicion_auto"] == 72
        v = disposiciones.docente(rec, {"periodo_id": ov["periodo_defecto"], "cuil": info["habilitados"][0]["cuil"]})
        assert v["numero"] == "72" and {"estado_consulta", "considerandos", "designaciones"} <= set(v)
        h = disposiciones.historial(rec, {"periodo_id": None})
        assert len(h["filas"]) >= 259 and h["zip"]["cantidad"] == 0
        assert h["zip"]["aviso"] == "No hay archivos Word disponibles para descargar en conjunto con este filtro."
    assert disposiciones.periodo(records["dep"], {"periodo_id": periodo_id(db_conn, 1, "2026-1")})["aviso"] == (
        "No hay docentes con designación activa en este período. No se puede generar una disposición nueva.")
    assert _contar(db_conn) == antes and audit_store.events == []
    assert os.listdir(storage_root) == []  # leer no crea directorios ni archivos


def test_permisos_visuales_por_rol(disposiciones, records, service, repo):
    esperado = {"dep": (True, False, True), "lector": (False, False, False), "super": (True, True, True),
                "coord_dep": (False, False, False), "dep2": (True, False, True)}
    for rol, (w, d, p) in esperado.items():
        perm = disposiciones.overview(records[rol])["permisos"]
        assert (perm["puede_escribir"], perm["puede_borrar"], perm["puede_plantilla"]) == (w, d, p), rol
    with pytest.raises(DisposicionesError) as exc:  # coordinador sin departamento: modulo no visible
        disposiciones.overview(records["coord"])
    assert exc.value.code == "SCOPE_INSTITUTIONAL"


def test_modo_comercial_read_only_y_roles_sin_escritura(disposiciones, service, repo, db_conn, audit_store,
                                                        storage_root, records):
    _plantilla(storage_root)
    repo.institutions_rows[0]["estado_pago"] = "Vencido"
    ro = session_for(service, repo, 3)[0]
    pid, v = _vista(disposiciones, records["dep"], db_conn)
    antes = _contar(db_conn)
    for rec, codigo in ((ro, "DENY_COMMERCIAL_READ_ONLY"), (records["lector"], "DENY_READ_ONLY_ROLE"),
                        (records["coord_dep"], "DENY_ROLE_NOT_PERMITTED")):
        n = len(audit_store.events)
        assert disposiciones.overview(rec)["permisos"] == {"puede_escribir": False, "puede_borrar": False,
                                                            "puede_plantilla": False}
        with pytest.raises(DisposicionesError) as e1:
            _generar(disposiciones, rec, pid, v)
        ov = disposiciones.overview(rec)
        with pytest.raises(DisposicionesError) as e2:
            disposiciones.guardar_configuracion(rec, {"valores": ov["configuracion"], "huella": ov["huella_configuracion"]})
        with pytest.raises(DisposicionesError) as e3:
            disposiciones.reemplazar_plantilla(rec, {"nombre_archivo": "p.docx",
                                                     "contenido_base64": base64.b64encode(P.construir()).decode()})
        assert e1.value.code == e2.value.code == e3.value.code == "DENIED"
        assert [(x.operation, x.outcome, x.error_code) for x in audit_store.events[n:]] == [
            ("generar_disposicion_word_b12e", "DENIED", codigo), ("guardar_parametros_disposicion", "DENIED", codigo),
            ("reemplazar_plantilla_disposicion_b12e", "DENIED", codigo)]
    assert _contar(db_conn)[:7] == antes[:7]
    assert [f for f in storage_root.rglob("*") if f.is_file() and "disposiciones" in str(f)] == []


def test_eliminar_solo_superadmin(disposiciones, records, db_conn, audit_store):
    fila = disposiciones.historial(records["dep"], {"periodo_id": None})["filas"][0]
    n = len(audit_store.events)
    with pytest.raises(DisposicionesError) as exc:
        disposiciones.eliminar(records["dep"], {"id": fila["id"], "huella": fila["huella"], "confirmar": True})
    assert exc.value.code == "DENIED"
    assert [(e.operation, e.action.key if hasattr(e.action, "key") else e.action, e.outcome, e.error_code)
            for e in audit_store.events[n:]] == [("eliminar_disposicion", "disposiciones.delete", "DENIED",
                                                  "DENY_ROLE_NOT_PERMITTED")]
    with pytest.raises(DisposicionesError) as exc:  # sin confirmar: ni writer ni evento
        disposiciones.eliminar(records["super"], {"id": fila["id"], "huella": fila["huella"], "confirmar": False})
    assert exc.value.message == "Primero confirmá la eliminación." and len(audit_store.events) == n + 1


def test_plantilla_reemplazo_b12h_y_validacion(disposiciones, records, storage_root, audit_store, db_conn):
    with db_conn.transaction() as tx:
        n = len(audit_store.events)
        res = disposiciones.reemplazar_plantilla(records["dep"], {
            "nombre_archivo": "Modelo.DOCX", "contenido_base64": base64.b64encode(P.construir()).decode()})
        assert res["mensaje"] == "Plantilla de la institución reemplazada." and res["plantilla"]["status"] == "OK"
        assert (storage_root / "inst_1" / "plantillas" / "disposicion.docx").read_bytes() == P.construir()
        ev = audit_store.events[n:]
        assert [(e.operation, e.action, e.action_scope, e.entity_type, e.entity_id, e.outcome, e.audit_mode,
                 e.metadata) for e in ev] == [
            ("reemplazar_plantilla_disposicion_b12e", "disposiciones.write", "institution", "plantilla_disposicion",
             None, "SUCCESS", "POST_OPERATION", {"coupled_commits": 0, "post_reason": "FILESYSTEM_ONLY"})]
        assert audit_rows(db_conn) == []  # solo disco: ningun COMMIT
        for nombre, data, codigo in (("p.doc", P.construir(), "DOCX_EXTENSION"),
                                     ("p.docx", b"no", "DOCX_INVALID"), ("p.docx", b"", None)):
            n = len(audit_store.events)
            with pytest.raises(DisposicionesError) as exc:
                disposiciones.reemplazar_plantilla(records["dep"], {"nombre_archivo": nombre,
                                                                    "contenido_base64": base64.b64encode(data).decode()})
            if codigo:
                assert exc.value.code == codigo and f"[{codigo}]" in exc.value.message
                assert [(e.outcome, e.error_code) for e in audit_store.events[n:]] == [
                    ("FAILED", f"DocxValidationError:{codigo}")]
        assert (storage_root / "inst_1" / "plantillas" / "disposicion.docx").read_bytes() == P.construir()
        raise psycopg.Rollback(tx)


def test_plantilla_superadmin_requiere_institucion_elegida(disposiciones, records, audit_store, storage_root):
    sup = records["super"]
    assert disposiciones._template_denial(sup, disposiciones.scope(sup)) is None
    scope = disposiciones.scope(sup)
    sup.scope.pop("superadmin_institucion_id")
    try:
        assert disposiciones._template_denial(sup, scope) in ("SUPERADMIN_SELECTION_REQUIRED", "DENY_SCOPE_MISSING")
    finally:
        sup.scope["superadmin_institucion_id"] = 1


def test_plantilla_de_otra_institucion_aislada(disposiciones, records, service, repo, storage_root):
    _plantilla(storage_root, inst=1)
    repo.departments_rows.append({"id": 5, "institucion_id": 2, "nombre": "Departamento de Estructuras",
                                  "estado": "Activo"})
    assert disposiciones.overview(records["dep"])["plantilla"]["status"] == "OK"
    assert disposiciones.overview(records["uba"])["plantilla"]["status"] == "MISSING"  # inst_2 no ve la de inst_1


# ------------------------------------------------------------------------------------------ generacion y descargas
def test_generar_descargar_y_aislamiento(disposiciones, records, db_conn, audit_store, storage_root, service, repo):
    _plantilla(storage_root)
    pid, v = _vista(disposiciones, records["dep"], db_conn)
    with db_conn.transaction() as tx:
        res = _generar(disposiciones, records["dep"], pid, v, estado="Anulada")
        fila = db_conn.execute("SELECT numero, estado, archivo_word, plantilla_usada, institucion_id, departamento_id "
                               "FROM disposiciones WHERE id=%s", [res["id"]]).fetchone()
        assert fila[:2] == (v["numero"], "Anulada") and fila[4:] == (1, 1)
        assert fila[2] == f"b12e:inst_1/dep_1/disposiciones/{res['file_name']}"
        assert fila[3].startswith("b12e:inst_1/plantillas/disposicion.docx#sha256=")
        mov = db_conn.execute("SELECT tipo_movimiento, detalle FROM movimientos WHERE cuil=%s ORDER BY id DESC LIMIT 1",
                              [v["cuil"]]).fetchone()
        assert mov == ("Generación de disposición", f"Se generó disposición N° {v['numero']}: Asignación de funciones docentes")
        payload = disposiciones.descargar(records["dep"], {"id": res["id"]})
        assert payload.file_name == res["file_name"] and payload.mime == S.DOCX_MIME
        S.validate_docx_bytes(payload.data, max_bytes=S.MAX_OUTPUT_BYTES)
        # lectura: solo_lectura y coordinador del departamento SI descargan
        assert disposiciones.descargar(records["lector"], {"id": res["id"]}).data == payload.data
        assert disposiciones.descargar(records["coord_dep"], {"id": res["id"]}).data == payload.data
        # otro departamento / otra institucion: la fila no existe en su ambito
        for rec in (records["dep2"],):
            with pytest.raises(DisposicionesError) as exc:
                disposiciones.descargar(rec, {"id": res["id"]})
            assert exc.value.code == "NOT_FOUND" and "[NOT_FOUND]" in exc.value.message
        h = disposiciones.historial(records["dep"], {"periodo_id": pid})
        nueva = next(f for f in h["filas"] if f["id"] == res["id"])
        assert nueva["documento"] == {"disponible": True, "mensaje": "", "legado": False}
        assert h["zip"]["cantidad"] == 1 and h["zip"]["detalle"].startswith("Se incluyeron 1 de")
        contenido, nombre = disposiciones.zip_historial(records["dep"], {"periodo_id": pid})
        assert nombre == "Disposiciones_2026-2.zip"
        with zipfile.ZipFile(io.BytesIO(contenido)) as zf:
            assert zf.namelist() == [S.safe_label(f"2026-2_Disposicion_{v['numero']}_{v['docente']}", 120) + ".docx"]
        # eliminar (superadmin): el registro se borra, el Word y el movimiento NO
        disposiciones.eliminar(records["super"], {"id": res["id"], "huella": nueva["huella"], "confirmar": True})
        assert db_conn.execute("SELECT count(*) FROM disposiciones WHERE id=%s", [res["id"]]).fetchone()[0] == 0
        assert (storage_root / "inst_1" / "dep_1" / "disposiciones" / res["file_name"]).is_file()
        assert db_conn.execute("SELECT count(*) FROM movimientos WHERE cuil=%s AND tipo_movimiento=%s",
                               [v["cuil"], "Generación de disposición"]).fetchone()[0] >= 1
        raise psycopg.Rollback(tx)


def test_descargas_rechazos_b12e(disposiciones, records, db_conn, storage_root):
    _plantilla(storage_root)
    legado = db_conn.execute("SELECT id FROM disposiciones WHERE institucion_id=1 AND departamento_id=1 "
                             "ORDER BY id LIMIT 1").fetchone()[0]
    with pytest.raises(DisposicionesError) as exc:
        disposiciones.descargar(records["dep"], {"id": legado})
    assert exc.value.code == "LEGACY_UNVERIFIED" and exc.value.message == S.MESSAGES["LEGACY_UNVERIFIED"] + \
        " [LEGACY_UNVERIFIED]"
    for valor, codigo in ((0, "INVALID_ID"), ("x", "INVALID_ID"), (True, "INVALID_ID"), (99999999, "NOT_FOUND")):
        with pytest.raises(DisposicionesError) as exc:
            disposiciones.descargar(records["dep"], {"id": valor})
        assert exc.value.code == codigo
    afuera = storage_root.parent / "secreto.docx"
    afuera.write_bytes(P.construir())
    nombre = "20261026-103000_X_" + "c" * 32 + ".docx"
    with db_conn.transaction() as tx:
        for ref, codigo in ((f"b12e:inst_1/dep_1/disposiciones/../../../secreto.docx", "PATH_REJECTED"),
                            (f"b12e:inst_1/dep_2/disposiciones/{nombre}", "OWNERSHIP_MISMATCH"),
                            (f"b12e:inst_1/dep_1/disposiciones/{nombre}", "FILE_MISSING"),
                            (str(afuera), "LEGACY_UNVERIFIED")):
            did = db_conn.execute("INSERT INTO disposiciones (institucion_id, departamento_id, periodo_id, numero, cuil, "
                                  "docente, estado, archivo_word) VALUES (1, 1, NULL, 'ZZ', 'ZZNEXT', 'ZZNEXT', "
                                  "'Borrador', %s) RETURNING id", [ref]).fetchone()[0]
            with pytest.raises(DisposicionesError) as exc:
                disposiciones.descargar(records["dep"], {"id": did})
            assert exc.value.code == codigo, ref
            assert "C:" not in exc.value.message and "secreto" not in exc.value.message
        raise psycopg.Rollback(tx)


def test_generacion_sin_plantilla_y_bloqueo_no_docente(disposiciones, records, db_conn, audit_store, storage_root):
    pid, v = _vista(disposiciones, records["dep"], db_conn)
    with db_conn.transaction() as tx:
        n = len(audit_store.events)
        with pytest.raises(DisposicionesError) as exc:
            _generar(disposiciones, records["dep"], pid, v)
        assert exc.value.message == "No se pudo generar el Word: " + S.MESSAGES["TEMPLATE_MISSING"] + " [TEMPLATE_MISSING]"
        assert [(e.outcome, e.error_code) for e in audit_store.events[n:]] == [
            ("FAILED", "DocumentAccessDenied:TEMPLATE_MISSING")]
        with pytest.raises(DisposicionesError) as exc:  # masiva: la plantilla se verifica antes de preparar
            disposiciones.generar_masiva(records["dep"], {"periodo_id": pid, "fecha": FIXED_TODAY.isoformat(),
                                                          "tipo": "x", "estado": "Borrador", "huella_padron": "x"})
        assert exc.value.code == "TEMPLATE"
        raise psycopg.Rollback(tx)
    with pytest.raises(DisposicionesError) as exc:  # seleccion vieja / ajena
        disposiciones.generar(records["dep"], {"periodo_id": pid, "cuil": v["cuil"], "huella": "otra", "estado": "Borrador",
                                               "fecha": "2026-10-26"})
    assert exc.value.code == "SELECCION"
    with pytest.raises(DisposicionesError):
        disposiciones.generar(records["dep"], {"periodo_id": pid, "cuil": v["cuil"], "huella": v["huella"],
                                               "estado": "Vigente", "fecha": "2026-10-26"})


def test_b12i_sin_lock_ni_reserva():
    fuente = "".join(inspect.getsource(m) for m in (SV, SV.E, SV.R, S, SV.D))
    assert "advisory" not in fuente.lower() and "lock_connection" not in fuente
    assert "lock_connection" not in inspect.signature(DisposicionesService).parameters


# ------------------------------------------------------------------------------------------ HTTP
def login(client, repo, email):
    r = client.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF)
    assert r.status_code == 200


def clean(response, repo):
    for word in FORBIDDEN:
        assert word not in response.text, word
    for pwd in repo.passwords.values():
        assert pwd not in response.text


def test_http_sesion_csrf_respuestas_limpias_y_binarios(http, repo, clock, db_conn, storage_root):
    assert http.get("/disposiciones").status_code == 401
    assert http.post("/disposiciones/historial", json={}, headers=CSRF).status_code == 401
    login(http, repo, "info@test.local")
    r = http.get("/disposiciones")
    assert r.status_code == 200 and r.json()["plantilla"]["status"] == "MISSING"
    clean(r, repo)
    assert http.post("/disposiciones/historial", json={}).json()["error"]["code"] == "CSRF"
    r = http.post("/disposiciones/historial", json={"periodo_id": None}, headers=CSRF)
    assert r.status_code == 200 and not any(f["documento"]["disponible"] for f in r.json()["filas"])
    clean(r, repo)
    legado = r.json()["filas"][0]["id"]
    r = http.post("/disposiciones/descargar", json={"id": legado}, headers=CSRF)
    assert r.status_code == 409 and r.json()["error"]["code"] == "LEGACY_UNVERIFIED"
    clean(r, repo)
    r = http.post("/disposiciones/historial/zip", json={"periodo_id": None}, headers=CSRF)
    assert r.status_code == 404 and r.json()["error"]["code"] == "ZIP_EMPTY"
    r = http.post("/disposiciones/periodo", json={"periodo_id": "9 OR 1=1"}, headers=CSRF)
    assert r.status_code == 422
    clean(r, repo)
    for ruta in ("pdf", "excel", "anular", "editar", "historial/editar", "plantilla/descargar", "migrar"):
        assert http.post(f"/disposiciones/{ruta}", json={}, headers=CSRF).status_code in (404, 405), ruta
    _plantilla(storage_root)
    pid = periodo_id(db_conn, 1, "2026-2")
    hab = http.post("/disposiciones/periodo", json={"periodo_id": pid}, headers=CSRF).json()["habilitados"]
    v = http.post("/disposiciones/docente", json={"periodo_id": pid, "cuil": hab[0]["cuil"]}, headers=CSRF).json()
    with db_conn.transaction() as tx:
        body = {"periodo_id": pid, "cuil": v["cuil"], "huella": v["huella"], "fecha": "2026-10-26",
                "tipo": "Asignación de funciones docentes", "estado": "Borrador", "observaciones": "",
                "incluir_concursado": v["tiene_concursado"], "incluir_interino": v["tiene_interino"],
                "incluir_investigacion": v["tiene_investigacion_o_extension"],
                "designaciones": [{k: d[k] for k in ("designacion_id", "fecha_desde", "fecha_hasta", "observaciones")}
                                  for d in v["designaciones"]]}
        r = http.post("/disposiciones/generar", json=body, headers=CSRF)
        if r.status_code == 200:
            clean(r, repo)
            d = http.post("/disposiciones/descargar", json={"id": r.json()["id"]}, headers=CSRF)
            assert d.status_code == 200 and d.headers["content-type"] == S.DOCX_MIME
            assert d.headers["content-disposition"].startswith('attachment; filename="')
            assert d.headers["cache-control"] == "no-store" and d.content[:4] == b"PK\x03\x04"
        else:  # docente no docente sin texto: bloqueo de pantalla
            assert r.status_code == 422
        raise psycopg.Rollback(tx)
    clock.advance(30 * 60)
    assert http.get("/disposiciones").json()["error"]["code"] == "IDLE_TIMEOUT"


def test_ausencias_del_certificado():
    from disposiciones.routes import router
    rutas = {r.path for r in router.routes}
    assert len(rutas) == 15
    assert not any(x in p for p in rutas for x in ("pdf", "excel", "anular", "editar", "migrar", "estado-consulta"))
    metodos = [n for n in dir(DisposicionesService) if not n.startswith("__")]
    assert not [n for n in metodos if any(x in n for x in ("pdf", "excel", "anular", "editar", "migrar",
                                                           "estado_consulta_guardar", "guardar_estado"))]
    assert "guardar_estado_consulta_designacion" not in inspect.getsource(SV.E)  # D12: solo lectura
