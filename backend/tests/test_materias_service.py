"""Servicio y HTTP de Materias sobre deptit_next_dev con ROLLBACK: permisos (B10, alcance institucion), B12B sin
departamento, IDs manipulados, auditoria B12H (etiquetas vs catalogo certificado), B12I, fallas intermedias, cargas
fila por fila, Excel y contrato HTTP.  Usuarios del FakeRepo (sin credenciales humanas)."""

from __future__ import annotations

import ast
import base64
import inspect

import pytest

import audit
from materias import service as svc
from materias.repository import MateriasRepository
from materias.service import MateriasError
from materias_support import (  # noqa: F401  (fixtures)
    ENTRY, audit_rows, audit_store, db_conn, entry_defs, http, materias, session_for, uba_sintetica,
)

from deptit_refactor.b12h import audit_actor as ref_audit  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "DELETE ", "Traceback", "psycopg", "institucion_id =")
ESC = "ZZNEXT Escuela"


@pytest.fixture
def records(service, repo):
    out = {"dep": session_for(service, repo, 3)[0], "coord": session_for(service, repo, 2)[0],
           "lector": session_for(service, repo, 7)[0], "uba": session_for(service, repo, 4)[0]}
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, 1, False)
    out["super"] = sup
    return out


def carrera_data(**kw):
    d = dict(escuela=ESC, codigo="ZZ", nombre="ZZNEXT Servicio", titulo_otorga="", plan_version="Plan vigente",
             duracion="", estado="Activa", observaciones="")
    d.update(kw)
    return d


def count(conn, sql, params=()):
    return conn.execute(sql, list(params)).fetchone()[0]


# ------------------------------------------------------------------------------------------------ permisos / scope
def test_permissions_and_institutional_scope(materias, records, db_conn, uba_sintetica):
    dep = materias.overview(records["dep"])
    assert dep["permisos"] == {"puede_escribir": True, "puede_borrar": True}
    assert len(dep["carreras"]) == count(db_conn, "SELECT count(*) FROM carreras WHERE institucion_id = 1")
    coord = materias.overview(records["coord"])  # coordinador SIN departamento: el modulo opera a nivel institucion
    assert coord["contexto"]["departamento"] is None and coord["permisos"]["puede_escribir"] is True
    assert coord["carreras"] == dep["carreras"]
    assert materias.overview(records["lector"])["permisos"] == {"puede_escribir": False, "puede_borrar": False}
    uba = materias.overview(records["uba"])
    assert {c["id"] for c in uba["carreras"]} == {r[0] for r in db_conn.execute(
        "SELECT id FROM carreras WHERE institucion_id = 2").fetchall()}
    assert {c["id"] for c in uba["carreras"]} == set(uba_sintetica["carreras"])
    assert not ({c["id"] for c in uba["carreras"]} & {c["id"] for c in dep["carreras"]})
    abog_uno = materias.plan(records["dep"], {"escuela": "Todas", "carrera_id": 46})  # homonimo: cada uno ve el suyo
    abog_uba = materias.plan(records["uba"], {"escuela": "Todas", "carrera_id": uba_sintetica["carreras"][0]})
    assert abog_uno["carrera"]["nombre"] == abog_uba["carrera"]["nombre"] == "Abogacía"
    assert len(abog_uno["plan"]) == count(db_conn, "SELECT count(*) FROM materias WHERE carrera_id = 46 AND en_plan = 1")
    assert len(abog_uba["plan"]) == 2
    assert materias.plan(records["uba"], {"escuela": "Todas", "carrera_id": 46})["carrera"] is None
    assert materias.plan(records["dep"], {"escuela": "Todas", "carrera_id": uba_sintetica["carreras"][0]})["carrera"] is None


def test_institution_without_academic_structure(materias, records, db_conn):
    """UBA real quedo sin estructura academica (decision funcional 2026-10-26): el modulo lo muestra vacio."""
    for t in ("carreras", "materias", "opciones_curriculares", "opcion_curricular_materias"):
        assert count(db_conn, f"SELECT count(*) FROM {t} WHERE institucion_id = 2") == 0
    uba = materias.overview(records["uba"])
    assert uba["contexto"]["institucion"]["id"] == 2
    assert uba["carreras"] == [] and uba["conteos"]["carreras"] == 0 and uba["conteos"]["materias"] == 0
    plan = materias.plan(records["uba"], {"escuela": "Todas", "carrera_id": 46})
    assert plan["hay_carreras_activas"] is False and plan["opciones"] == [] and plan["carrera"] is None


def test_coordinator_without_department_can_write(materias, records, db_conn, audit_store):
    res = materias.carrera_alta(records["coord"], carrera_data())
    assert res["mensaje"] == "Carrera / plan registrado correctamente."
    assert count(db_conn, "SELECT count(*) FROM carreras WHERE nombre = 'ZZNEXT Servicio' AND institucion_id = 1") == 1
    ev = audit_rows(db_conn)[-1]
    assert (ev["operation"], ev["action"], ev["action_scope"], ev["entity_type"], ev["departamento_id"]) == (
        "guardar_carrera", "materias.write", "institution", "carrera", None)


@pytest.mark.parametrize("who", ["lector"])
def test_read_only_denied(materias, records, db_conn, audit_store, who):
    with pytest.raises(MateriasError) as exc:
        materias.carrera_alta(records[who], carrera_data())
    assert exc.value.status == 403 and "(permiso requerido: materias.write)" in exc.value.message
    assert [(e.outcome, e.operation, e.error_code) for e in audit_store.events] == [
        ("DENIED", "guardar_carrera", "DENY_READ_ONLY_ROLE")]
    assert count(db_conn, "SELECT count(*) FROM carreras WHERE nombre = 'ZZNEXT Servicio'") == 0


def test_commercial_read_only_blocks(materias, service, repo, audit_store):
    repo.institutions_rows[0]["estado_pago"] = "Vencido"
    record = session_for(service, repo, 3)[0]
    with pytest.raises(MateriasError) as exc:
        materias.carrera_alta(record, carrera_data())
    assert exc.value.status == 403 and audit_store.events[-1].error_code == "DENY_COMMERCIAL_READ_ONLY"


def test_unverifiable_institution_shows_nothing(materias, service, repo):
    repo.users[2]["institucion_id"] = 999  # usuario_departamento con institucion inexistente
    record = session_for(service, repo, 3)[0]
    with pytest.raises(MateriasError) as exc:
        materias.overview(record)
    assert exc.value.code == "SCOPE_NOT_VERIFIED" and "Ámbito no verificado" in exc.value.message


def test_manipulated_ids_from_other_institution(materias, records, db_conn, audit_store, uba_sintetica):
    carrera_uba, materia_uba = uba_sintetica["carreras"][0], uba_sintetica["materias"][0]
    antes = count(db_conn, "SELECT count(*) FROM materias WHERE institucion_id = 2")
    for fn, body in [
        (materias.carrera_editar, dict(carrera_data(), carrera_id=carrera_uba, huella="x")),
        (materias.carrera_eliminar, {"carrera_id": carrera_uba, "huella": "x", "confirmar": True}),
        (materias.materia_eliminar, {"id": materia_uba, "huella": "x", "confirmar": True}),
    ]:
        with pytest.raises(MateriasError) as exc:
            fn(records["dep"], body)
        assert exc.value.code == "STALE"
    with pytest.raises(MateriasError) as exc:
        materias.materia_detalle(records["dep"], {"id": materia_uba})
    assert exc.value.code == "NOT_FOUND"
    with pytest.raises(MateriasError):
        materias.materia_alta(records["dep"], dict(codigo="1", asignatura="X", anio="1° Año", cuatrimestre="1",
                                                   dictado="Presencial", carga_semanal=1, carga_total=1,
                                                   duracion="Anual", estado="Activa", observaciones="", orden=0,
                                                   carrera_id=carrera_uba))
    assert count(db_conn, "SELECT count(*) FROM materias WHERE institucion_id = 2") == antes
    assert {e.error_code for e in audit_store.events} == {"StaleDecisionError"}


# ------------------------------------------------------------------------------------------------ validaciones UI
@pytest.mark.parametrize("kw,msg", [
    (dict(escuela=""), svc.MSG_CARRERA_REQUERIDOS),
    (dict(nombre=""), svc.MSG_CARRERA_REQUERIDOS),
    (dict(plan_version=""), svc.MSG_CARRERA_REQUERIDOS),
    (dict(estado="Otra"), svc.MSG_VALOR_INVALIDO),
])
def test_carrera_validations_without_writes(materias, records, audit_store, kw, msg):
    with pytest.raises(MateriasError) as exc:
        materias.carrera_alta(records["dep"], carrera_data(**kw))
    assert exc.value.message == msg and audit_store.events == []


def test_duplicate_carrera_and_confirmations(materias, records, db_conn, audit_store):
    existente = db_conn.execute("SELECT escuela, codigo, nombre, plan_version FROM carreras WHERE institucion_id = 1 "
                                "LIMIT 1").fetchone()
    datos = carrera_data(escuela=existente[0], codigo=existente[1] or "", nombre=existente[2],
                         plan_version=existente[3])
    assert materias.carrera_duplicada(records["dep"], datos)["duplicadas"]
    with pytest.raises(MateriasError) as exc:
        materias.carrera_alta(records["dep"], datos)
    assert exc.value.message == svc.MSG_CARRERA_DUP_ALTA
    for fn, body in [(materias.carrera_eliminar, {"carrera_id": 1}), (materias.materia_eliminar, {"id": 1}),
                     (materias.opcion_eliminar, {"id": 1}), (materias.limpiar_fuera_plan, {"carrera_id": 1})]:
        with pytest.raises(MateriasError) as exc:
            fn(records["dep"], body)
        assert exc.value.code == "CONFIRMATION_REQUIRED"
    assert audit_store.events == []


# ------------------------------------------------------------------------------------------------ auditoria B12H
def _certified_signature(name):
    node = entry_defs(ENTRY, name)[0]
    ns = {}
    exec(compile(f"def {name}({ast.unparse(node.args)}): pass", "<sig>", "exec"), ns)
    return inspect.signature(ns[name])


def test_writer_labels_match_certified_b12h_catalog():
    catalog = ref_audit.writer_catalog()
    specs = [v for v in vars(svc).values() if isinstance(v, svc.WriterSpec)]
    assert len(specs) == 16
    for spec in specs:
        cert = catalog[spec.name]
        assert (spec.action.key, spec.action.scope, spec.entity_type) == (cert.action, cert.action_scope,
                                                                          cert.entity_type), spec.name
        assert cert.mode == "COUPLED"
        assert spec.entity_param == ref_audit._entity_param(_certified_signature(spec.name), cert.entity_type), spec.name
    assert {s.name for s in specs} <= audit.WRITER_NAMES <= set(catalog)


def test_audit_failure_rolls_back(materias, records, db_conn, audit_store, monkeypatch):
    def boom(conn, event):
        raise RuntimeError("audit down")
    monkeypatch.setattr(audit, "insert_on", boom)
    with pytest.raises(MateriasError) as exc:
        materias.carrera_alta(records["dep"], carrera_data())
    assert exc.value.code == "AUDIT"
    assert count(db_conn, "SELECT count(*) FROM carreras WHERE nombre = 'ZZNEXT Servicio'") == 0
    assert audit_store.events[-1].outcome == "FAILED"


def test_stale_huella_rejected(materias, records, db_conn, audit_store):
    materias.carrera_alta(records["dep"], carrera_data())
    cid = db_conn.execute("SELECT id FROM carreras WHERE nombre = 'ZZNEXT Servicio'").fetchone()[0]
    h = next(c["huella"] for c in materias.overview(records["dep"])["carreras"] if c["id"] == cid)
    db_conn.execute("UPDATE carreras SET observaciones = 'otra sesion' WHERE id = %s", [cid])
    with pytest.raises(MateriasError) as exc:
        materias.carrera_editar(records["dep"], dict(carrera_data(nombre="ZZNEXT Cambiada"), carrera_id=cid, huella=h))
    assert exc.value.code == "STALE" and exc.value.message.startswith(svc.MSG_STALE)
    assert count(db_conn, "SELECT count(*) FROM carreras WHERE nombre = 'ZZNEXT Cambiada'") == 0


def test_carga_rapida_interrupted_keeps_previous_rows(materias, records, db_conn, monkeypatch):
    materias.carrera_alta(records["dep"], carrera_data())
    cid = db_conn.execute("SELECT id FROM carreras WHERE nombre = 'ZZNEXT Servicio'").fetchone()[0]
    original = MateriasRepository.insert_materia
    calls = {"n": 0}

    def flaky(self, values):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("falla simulada")
        return original(self, values)

    monkeypatch.setattr(MateriasRepository, "insert_materia", flaky)
    texto = "codigo\tasignatura\nZZ-1\tZZNEXT A\nZZ-2\tZZNEXT B\nZZ-3\tZZNEXT C\n"
    with pytest.raises(MateriasError) as exc:
        materias.carga_ejecutar(records["dep"], {"carrera_id": cid, "texto": texto, "confirmar": True})
    assert exc.value.message.startswith("La carga se interrumpió en la fila 2:")
    assert count(db_conn, "SELECT count(*) FROM materias WHERE carrera_id = %s", [cid]) == 1  # fila 1 confirmada


def test_carga_preview_controls(materias, records, db_conn):
    materias.carrera_alta(records["dep"], carrera_data())
    cid = db_conn.execute("SELECT id FROM carreras WHERE nombre = 'ZZNEXT Servicio'").fetchone()[0]
    prev = materias.carga_preview(records["dep"], {"carrera_id": cid, "texto": "codigo\tasignatura\nZZ1\tA\nZZ1\tB\n"})
    assert prev["conflictos_tabla"] and prev["duplicadas"]
    with pytest.raises(MateriasError) as exc:
        materias.carga_ejecutar(records["dep"], {"carrera_id": cid, "texto": "codigo\tasignatura\nZZ1\tA\nZZ1\tB\n",
                                                 "confirmar": True})
    assert exc.value.message == svc.MSG_CARGA_CONFLICTOS
    assert materias.carga_preview(records["dep"], {"carrera_id": cid, "texto": "x"})["aviso"] == svc.MSG_CARGA_SIN_FILAS


def test_excel_upload_validation(materias, records):
    for bad in [None, "", "no-base64!!", base64.b64encode(b"texto plano").decode()]:
        with pytest.raises(MateriasError) as exc:
            materias.excel_preview(records["dep"], {"contenido_b64": bad})
        assert exc.value.message == svc.MSG_EXCEL_ARCHIVO
    big = base64.b64encode(b"PK\x03\x04" + b"0" * (svc.EXCEL_MAX_BYTES + 1)).decode()
    with pytest.raises(MateriasError):
        materias.excel_preview(records["dep"], {"contenido_b64": big})
    import io
    import zipfile
    # 6A-B1: un ZIP que no es un libro OOXML se rechaza por contenido ANTES del lector (uploads.problema_xlsx).
    with pytest.raises(MateriasError) as exc:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("a.txt", "x")
        materias.excel_preview(records["dep"], {"contenido_b64": base64.b64encode(buf.getvalue()).decode()})
    assert exc.value.message == svc.MSG_EXCEL_ARCHIVO
    from openpyxl import Workbook  # un libro OOXML valido supera la validacion de contenido y llega al lector
    buf = io.BytesIO()
    Workbook().save(buf)
    assert materias._decodificar_excel(base64.b64encode(buf.getvalue()).decode()) == buf.getvalue()


# ------------------------------------------------------------------------------------------------ HTTP
def login(client, repo, email):
    r = client.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF)
    assert r.status_code == 200


def clean(response, repo):
    for word in FORBIDDEN:
        assert word not in response.text, word
    for pwd in repo.passwords.values():
        assert pwd not in response.text


def test_http_session_csrf_and_cleanliness(http, repo, clock, db_conn):
    assert http.get("/materias").status_code == 401
    assert http.post("/materias/carreras/alta", json={}, headers=CSRF).status_code == 401
    login(http, repo, "info@test.local")
    r = http.get("/materias")
    assert r.status_code == 200
    clean(r, repo)
    assert http.post("/materias/carreras/alta", json=carrera_data()).json()["error"]["code"] == "CSRF"
    body = dict(carrera_data(), institucion_id=2, departamento_id=5)
    r = http.post("/materias/carreras/alta", json=body, headers=CSRF)
    assert r.status_code == 200
    assert db_conn.execute("SELECT institucion_id FROM carreras WHERE nombre = 'ZZNEXT Servicio'").fetchall() == [(1,)]
    r = http.post("/materias/totales", json={"busqueda": "zz"}, headers=CSRF)
    assert r.status_code == 200
    clean(r, repo)
    r = http.get("/materias/opciones/modelo-excel")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    clock.advance(30 * 60)
    assert http.get("/materias").json()["error"]["code"] == "IDLE_TIMEOUT"


def test_http_read_only_user(http, repo):
    login(http, repo, "lector@test.local")
    assert http.get("/materias").status_code == 200
    r = http.post("/materias/carreras/alta", json=carrera_data(), headers=CSRF)
    assert r.status_code == 403
    clean(r, repo)
