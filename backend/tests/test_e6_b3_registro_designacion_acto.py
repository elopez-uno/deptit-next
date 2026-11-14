"""6A-B3 (aceptacion, ultimo ajuste) — Docentes → Registrar designacion con acto administrativo.

Los tres caminos de E4-08 reciben el MISMO acto contextual que el alta de Designaciones (E4-07): elegir del
repositorio, cargar un nuevo acto ahora (multipart, puerto ``ActoNuevo``) o dejar pendiente.  Se verifica, sobre
``deptit_next_dev`` con ROLLBACK:
- sin acto / pendiente: la secuencia certificada intacta (los diferenciales E4-08 siguen comparando contra B13);
- el vinculo REAL por ``documento_id`` en ``documentos_respaldo_designaciones`` (``vincular_acto_designacion_v266``)
  y, si el camino registra movimiento, en ``documentos_respaldo_movimientos`` (``vincular_acto_movimiento_v266``);
- acto nuevo: ``guardar_documento_respaldo_v251`` antes del primer writer y compensacion
  ``_eliminar_acto_recien_creado_v267`` si la designacion no llega a existir;
- designacion identica ya existente (caminos 2 y 3 la devuelven sin crearla): su acto NO se reemplaza;
- errores de seleccion, modo nuevo por JSON, permisos B10 y la ruta HTTP multipart.
"""
from __future__ import annotations

import json
import re

import psycopg
import pytest

import designaciones_support as DS
from designaciones import escrituras as DE
from designaciones_support import (  # noqa: F401  (fixtures)
    audit_rows, audit_store, db_conn, designaciones, session_for,
)
from resoluciones_support import make_resoluciones, pdf_sintetico
from test_e4_07_acto_nuevo import _dependencia, archivo_next, payload_next, valores
from test_e4_08_registro_designacion import (  # noqa: F401  (fixture docentes)
    C1, C2, C3, DEP, DEP2, INST, _contexto, _dep_nombre, _huella_docente, _ops, _payload, _record, _valores, docentes,
    seed_designacion, seed_docente,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

SUFIJO_ALTA = " El nuevo acto también fue guardado en Resoluciones y respaldos."
AVISO_EXISTENTE = ("Ya existía una designación idéntica para este docente en el período: no se creó otra y su acto "
                   "administrativo no se modificó.")


@pytest.fixture
def resoluciones(service, audit_store, db_conn):
    return make_resoluciones(service, audit_store, db_conn)


@pytest.fixture
def acto(designaciones, resoluciones):
    from integraciones.acto_contextual import ActoContextualService
    return ActoContextualService(designaciones, resoluciones)


@pytest.fixture
def registro(docentes, designaciones, acto):
    from integraciones.registro_designacion import RegistroDesignacionService
    return RegistroDesignacionService(docentes, designaciones, acto)


def _doc_existente(designaciones, rec) -> int:
    """Un acto del repositorio del departamento (lo que el selector "Elegir del repositorio" ofrece)."""
    docs = designaciones._read(designaciones.scope(rec), lambda repo: repo.documentos())
    return int(docs[0]["id"])


def _vinculos(conn, cuil):
    des = conn.execute("SELECT r.designacion_id, r.documento_id FROM documentos_respaldo_designaciones r JOIN "
                       "designaciones d ON d.id=r.designacion_id WHERE d.cuil=%s ORDER BY 1", [cuil]).fetchall()
    mov = conn.execute("SELECT m.tipo_movimiento, r.documento_id FROM documentos_respaldo_movimientos r JOIN "
                       "movimientos m ON m.id=r.movimiento_id WHERE m.cuil=%s ORDER BY m.id", [cuil]).fetchall()
    return des, mov


def _nuevo(db_conn, nombre, numero="ZZNEXT-B3-1/2026"):
    dep_id, dep_nom = _dependencia(db_conn)
    val = valores(dep=dep_nom, numero=numero, pdf=("ZZNEXT b3.pdf", "application/pdf", pdf_sintetico("b3")))
    return val, {"modo": "nuevo", "payload": payload_next(val, {dep_nom: dep_id}, f"Designación — {nombre}", "det")}


def _registrar(db_conn, registro, rec, datos, cuil, archivo=None, acto_nuevo=False):
    """Registra dentro de una transaccion revertida y devuelve resultado, vinculos, operaciones B12H y documentos."""
    with db_conn.transaction() as tx:
        r = registro.registrar(rec, datos, archivo, acto_nuevo=acto_nuevo)
        des, mov = _vinculos(db_conn, cuil)
        ops = [o["op"] for o in _ops(audit_rows(db_conn))]
        docs = db_conn.execute("SELECT id, categoria, numero, length(archivo_pdf) FROM documentos_respaldo WHERE "
                               "numero LIKE 'ZZNEXT-B3%%' ORDER BY id").fetchall()
        raise psycopg.Rollback(tx)
    return {"r": r, "des": des, "mov": mov, "ops": ops, "docs": docs}


# ------------------------------------------------------------------------------------------ sin acto / pendiente
@pytest.mark.parametrize("acto_cfg", [None, {"modo": "pendiente", "documento_id": None}], ids=["sin_clave", "pendiente"])
def test_sin_acto_secuencia_certificada(db_conn, registro, service, repo, acto_cfg):
    seed_docente(db_conn, C1, "Zeta", "Ana")
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    datos = _payload(_valores(), ctx["abierto_huella"], camino="reincorporar", cuil=C1, huella=_huella_docente(ctx, C1))
    if acto_cfg is not None:
        datos["acto"] = acto_cfg
    out = _registrar(db_conn, registro, rec, datos, C1)
    assert out["r"]["mensaje"] == "Docente reincorporado y designación registrada correctamente."
    assert out["ops"] == ["guardar_designacion", "registrar_movimiento"]
    assert out["des"] == [] and out["mov"] == [] and out["r"]["acto_documento_id"] is None


# ------------------------------------------------------------------------------------------ acto existente
def test_existente_reincorporar_vincula_designacion_y_movimiento(db_conn, registro, designaciones, service, repo):
    seed_docente(db_conn, C1, "Zeta", "Ana")
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    doc = _doc_existente(designaciones, rec)
    datos = _payload(_valores(), ctx["abierto_huella"], camino="reincorporar", cuil=C1,
                     huella=_huella_docente(ctx, C1), acto={"modo": "existente", "documento_id": doc})
    out = _registrar(db_conn, registro, rec, datos, C1)
    assert out["r"]["mensaje"] == "Docente reincorporado y designación registrada correctamente."  # sin sufijo
    assert out["ops"] == ["guardar_designacion", "vincular_acto_designacion_v266", "registrar_movimiento",
                          "vincular_acto_movimiento_v266"]
    assert out["des"] == [(out["r"]["id"], doc)]  # vinculo real por documento_id (misma tabla del alta)
    assert out["mov"] == [("Alta de designación", doc)] and out["r"]["acto_documento_id"] == doc


def test_existente_cuil_local_vincula_solo_la_designacion(db_conn, registro, designaciones, service, repo):
    """Camino 3: el certificado no registra movimiento, asi que solo hay vinculo a la designacion."""
    seed_docente(db_conn, C3, "Local", "Luis")
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    doc = _doc_existente(designaciones, rec)
    datos = _payload(_valores(dedicacion="Simple"), ctx["abierto_huella"], camino="cuil_local",
                     cuil_alta=C3.replace("-", ""), acto={"modo": "existente", "documento_id": doc})
    out = _registrar(db_conn, registro, rec, datos, C3)
    assert out["ops"] == ["guardar_designacion", "vincular_acto_designacion_v266"]
    assert out["des"] == [(out["r"]["id"], doc)] and out["mov"] == []


# ------------------------------------------------------------------------------------------ acto nuevo
def test_nuevo_cuil_existente_crea_acto_y_vincula(db_conn, registro, service, repo):
    """Camino 2 con "Cargar un nuevo acto ahora": el acto se crea antes del primer writer (alta local del docente),
    con la categoria del alta, el PDF en ``documentos_respaldo`` y el vinculo real a designacion y movimiento."""
    seed_docente(db_conn, C2, "Otra", "Dora", dep=DEP2)
    origen = _dep_nombre(db_conn, DEP2)
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    val, cfg = _nuevo(db_conn, "Otra, Dora")
    datos = _payload(_valores(), ctx["abierto_huella"], camino="cuil_existente", cuil=C2, departamento_origen=origen,
                     cuil_alta=C2, acto=cfg)
    out = _registrar(db_conn, registro, rec, datos, C2, archivo_next(val), acto_nuevo=True)
    assert out["r"]["mensaje"] == "Docente propio/compartido y designación registrados correctamente." + SUFIJO_ALTA
    assert out["ops"] == ["guardar_documento_respaldo_v251", "guardar_docente", "guardar_designacion",
                          "vincular_acto_designacion_v266", "registrar_movimiento", "vincular_acto_movimiento_v266"]
    (doc_id, categoria, numero, largo), = out["docs"]
    assert (categoria, numero, largo) == ("Designación docente", "ZZNEXT-B3-1/2026", len(pdf_sintetico("b3")))
    assert out["des"] == [(out["r"]["id"], doc_id)] and out["mov"] == [("Alta de designación", doc_id)]
    assert out["r"]["acto_documento_id"] == doc_id


def test_nuevo_falla_la_designacion_y_compensa(db_conn, registro, service, repo, audit_store, monkeypatch):
    """Si la designacion no llega a existir, ``_eliminar_acto_recien_creado_v267`` borra el acto: nada queda."""
    from docentes.service import DocentesError
    seed_docente(db_conn, C1, "Zeta", "Ana")
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    val, cfg = _nuevo(db_conn, "Zeta, Ana")
    datos = _payload(_valores(), ctx["abierto_huella"], camino="reincorporar", cuil=C1,
                     huella=_huella_docente(ctx, C1), acto=cfg)

    def roto(*a, **k):
        raise RuntimeError("fallo inyectado")
    monkeypatch.setattr(DE, "guardar_designacion", roto)
    with db_conn.transaction() as tx:
        with pytest.raises(DocentesError):
            registro.registrar(rec, datos, archivo_next(val), acto_nuevo=True)
        ops = [o["op"] for o in _ops(audit_rows(db_conn))]
        quedan = db_conn.execute("SELECT count(*) FROM documentos_respaldo WHERE numero LIKE 'ZZNEXT-B3%%'").fetchone()[0]
        des, mov = _vinculos(db_conn, C1)
        raise psycopg.Rollback(tx)
    assert ops == ["guardar_documento_respaldo_v251", "_eliminar_acto_recien_creado_v267"]
    assert quedan == 0 and des == [] and mov == []
    assert ("guardar_designacion", "FAILED") in [(e.operation, e.outcome) for e in audit_store.events]


def test_nuevo_falla_el_docente_del_camino_2_y_compensa(db_conn, registro, service, repo, audit_store):
    """Camino 2: el primer writer es ``guardar_docente`` (B12I del periodo); si falla, el acto recien creado se borra."""
    from docentes.service import DocentesError
    seed_docente(db_conn, C2, "Otra", "Dora", dep=DEP2)
    origen = _dep_nombre(db_conn, DEP2)
    rec = _record(service, repo)
    val, cfg = _nuevo(db_conn, "Otra, Dora")
    datos = _payload(_valores(), "vieja", camino="cuil_existente", cuil=C2, departamento_origen=origen, cuil_alta=C2,
                     acto=cfg)
    with db_conn.transaction() as tx:
        with pytest.raises(DocentesError) as exc:
            registro.registrar(rec, datos, archivo_next(val), acto_nuevo=True)
        ops = [o["op"] for o in _ops(audit_rows(db_conn))]
        quedan = db_conn.execute("SELECT count(*) FROM documentos_respaldo WHERE numero LIKE 'ZZNEXT-B3%%'").fetchone()[0]
        raise psycopg.Rollback(tx)
    assert exc.value.code == "STALE"
    assert ops == ["guardar_documento_respaldo_v251", "_eliminar_acto_recien_creado_v267"]
    assert ("guardar_docente", "FAILED") in [(e.operation, e.outcome) for e in audit_store.events]
    assert quedan == 0


# ------------------------------------------------------------------------------------------ designacion ya existente
@pytest.mark.parametrize("modo", ["existente", "nuevo"])
def test_identica_existente_no_reemplaza_su_acto(db_conn, registro, designaciones, service, repo, modo):
    """Camino 3 con una designacion identica: ``guardar_designacion`` devuelve la existente sin crear otra.  Su acto
    (R1) NO se reemplaza; un acto recien creado se compensa; el usuario recibe el aviso."""
    seed_docente(db_conn, C3, "Local", "Luis")
    v = _valores(dedicacion="Simple")
    seed_designacion(db_conn, C3, v)
    did = db_conn.execute("SELECT id FROM designaciones WHERE cuil=%s", [C3]).fetchone()[0]
    rec = _record(service, repo)
    docs = designaciones._read(designaciones.scope(rec), lambda repo_: repo_.documentos())
    previo, otro = int(docs[0]["id"]), int(docs[1]["id"])
    db_conn.execute("INSERT INTO documentos_respaldo_designaciones (institucion_id, departamento_id, documento_id, "
                    "designacion_id, usuario_vinculacion) VALUES (%s,%s,%s,%s,'zz')", [INST, DEP, previo, did])
    ctx = _contexto(registro, rec)
    archivo = None
    if modo == "existente":
        cfg = {"modo": "existente", "documento_id": otro}
    else:
        val, cfg = _nuevo(db_conn, "Local, Luis")
        archivo = archivo_next(val)
    datos = _payload(v, ctx["abierto_huella"], camino="cuil_local", cuil_alta=C3.replace("-", ""), acto=cfg)
    out = _registrar(db_conn, registro, rec, datos, C3, archivo, acto_nuevo=modo == "nuevo")
    assert out["des"] == [(did, previo)] and out["r"]["id"] == did
    assert AVISO_EXISTENTE in out["r"]["avisos"] and out["r"]["acto_documento_id"] is None
    assert not out["r"]["mensaje"].endswith(SUFIJO_ALTA) and out["docs"] == []
    assert out["ops"] == ([] if modo == "existente" else
                          ["guardar_documento_respaldo_v251", "_eliminar_acto_recien_creado_v267"])


# ------------------------------------------------------------------------------------------ errores y permisos
def test_errores_de_seleccion_no_escriben(db_conn, registro, service, repo, audit_store):
    from docentes.service import DocentesError
    seed_docente(db_conn, C1, "Zeta", "Ana")
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    base = _payload(_valores(), ctx["abierto_huella"], camino="reincorporar", cuil=C1, huella=_huella_docente(ctx, C1))
    max_mov = DS.baseline(db_conn)
    antes = DS.state(db_conn, INST, DEP, max_mov)
    casos = (({"modo": "existente", "documento_id": None}, 422, "ACTO_SIN_SELECCION"),
             ({"modo": "existente", "documento_id": 999999999}, 409, "ACTO_NO_ENCONTRADO"),
             ({"modo": "existente", "documento_id": "7"}, 422, "INVALID"),
             ({"modo": "nuevo", "payload": {}}, 409, "ACTO_NUEVO_PENDIENTE"))  # "nuevo" solo por multipart
    for cfg, status, code in casos:
        with pytest.raises(DocentesError) as exc:
            registro.registrar(rec, {**base, "acto": cfg})
        assert (exc.value.status, exc.value.code) == (status, code), cfg
    with pytest.raises(DocentesError) as exc:  # payload del acto invalido: rechazo antes de escribir
        registro.registrar(rec, {**base, "acto": {"modo": "nuevo", "payload": {"tipo_documento": "x"}}}, None,
                           acto_nuevo=True)
    assert exc.value.status == 422
    assert audit_store.events == [] and DS.state(db_conn, INST, DEP, max_mov) == antes


def test_permisos_b10(db_conn, registro, designaciones, service, repo, audit_store):
    """Solo lectura con acto nuevo: el primer writer es ``guardar_documento_respaldo_v251`` -> 403 + DENIED, sin
    escrituras; con acto existente, ``guardar_designacion`` -> 403 + DENIED (mismos limites que el alta)."""
    from docentes.service import DocentesError
    seed_docente(db_conn, C1, "Zeta", "Ana")
    lector = _record(service, repo, 7)
    ctx = _contexto(registro, lector)
    base = _payload(_valores(), ctx["abierto_huella"], camino="reincorporar", cuil=C1, huella=_huella_docente(ctx, C1))
    val, cfg = _nuevo(db_conn, "Zeta, Ana")
    doc = _doc_existente(designaciones, _record(service, repo, 1, dep=DEP))
    for datos, archivo, nuevo, writer in (({**base, "acto": cfg}, archivo_next(val), True,
                                           "guardar_documento_respaldo_v251"),
                                          ({**base, "acto": {"modo": "existente", "documento_id": doc}}, None, False,
                                           "guardar_designacion")):
        n = len(audit_store.events)
        with pytest.raises(DocentesError) as exc:
            registro.registrar(lector, datos, archivo, acto_nuevo=nuevo)
        assert exc.value.status == 403
        assert [(e.operation, e.outcome) for e in audit_store.events[n:]] == [(writer, "DENIED")]
    assert db_conn.execute("SELECT count(*) FROM documentos_respaldo WHERE numero LIKE 'ZZNEXT-B3%%'").fetchone()[0] == 0


# ------------------------------------------------------------------------------------------ HTTP
def test_http_multipart(db_conn, registro, service, repo):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from integraciones.routes import docentes_router

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(docentes_router)
    app.state.auth, app.state.registro_designacion = service, registro
    http = TestClient(app, base_url="http://localhost")
    ruta, csrf = "/docentes/designacion/acto-nuevo", {"X-DEPTIT-Request": "1"}
    assert http.post(ruta, headers=csrf).status_code == 401
    http.cookies.set("deptit_session", session_for(service, repo, 3)[1])
    assert http.post(ruta).status_code == 403  # sin cabecera del proxy
    assert http.post(ruta, headers=csrf, json={}).status_code == 415  # solo multipart
    seed_docente(db_conn, C1, "Zeta", "Ana")
    ctx = http.post("/docentes/designacion/contexto", headers=csrf).json()
    val, cfg = _nuevo(db_conn, "Zeta, Ana")
    datos = _payload(_valores(), ctx["abierto_huella"], camino="reincorporar", cuil=C1,
                     huella=_huella_docente(ctx, C1), acto=cfg)
    pdf = pdf_sintetico("b3")
    with db_conn.transaction() as tx:
        r = http.post(ruta, headers=csrf, data={"datos": json.dumps(datos)},
                      files={"archivo": ("ZZNEXT b3.pdf", pdf, "application/pdf")})
        assert r.status_code == 200, r.text
        doc = r.json()["acto_documento_id"]
        des, mov = _vinculos(db_conn, C1)
        raise psycopg.Rollback(tx)
    assert r.json()["mensaje"].endswith(SUFIJO_ALTA)
    assert des == [(r.json()["id"], doc)] and mov == [("Alta de designación", doc)]
    r = http.post(ruta, headers=csrf, files={"datos": (None, json.dumps({**datos, "acto": {
        "modo": "nuevo", "payload": {**cfg["payload"], "tipo_documento": "x"}}}))})
    assert r.status_code == 422 and not re.search(r"(?i)select\s|traceback|psycopg|insert\s", r.text)
