"""Servicio y HTTP de Resoluciones y respaldos: permisos B10 por rol, contrato B12H, multipart (D-AK1), firma PDF
(D-AK2), descarga segura (D-AK3 / D-AK12), boton Eliminar (D-AK6) y ausencias.  Datos sinteticos ``ZZNEXT`` dentro de la
transaccion del test (ROLLBACK); PDF sinteticos generados en memoria."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import psycopg
import pytest

from resoluciones_respaldos import rules as R
from resoluciones_respaldos.routes import MAX_TRANSPORTE, _Parser
from resoluciones_respaldos.service import Archivo, ResolucionesError
from resoluciones_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_rows, audit_store, db_conn, http, pdf_sintetico, record_for, resoluciones, session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "DELETE ", "Traceback", "psycopg", "institucion_id =", "C:\\", "C:/", "storage", "archivo_pdf",
             "%PDF-1.4", "%%EOF")


@pytest.fixture
def records(service, repo):
    out = {"dep": session_for(service, repo, 3)[0], "lector": session_for(service, repo, 7)[0],
           "uba": session_for(service, repo, 4)[0]}
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, 1, False)
    out["super"] = sup
    coord = session_for(service, repo, 2)[0]
    service.set_context(coord, 1, 1, False)
    out["coord_dep"] = coord
    out["coord"] = session_for(service, repo, 2)[0]
    return out


def _doc(db_conn, dep=1, pdf=b"", nombre="", mime=""):
    return db_conn.execute(
        "INSERT INTO documentos_respaldo (institucion_id,departamento_id,tipo_documento,categoria,numero,archivo_nombre,"
        "archivo_mime,archivo_pdf,archivo_bytes,dependencia_id,dependencia_nombre) VALUES (1,%s,'Otro','Otro',"
        "'ZZNEXT-S',%s,%s,%s,%s,NULL,'') RETURNING id", [dep, nombre, mime, pdf, len(pdf)]).fetchone()[0]


# Huella determinista de documentos_respaldo (cierre de Etapa 4): columnas explicitas, orden por PK y el PDF (bytea en
# TOAST) comparado por md5 de su contenido.  NO se usa ``d::text``: la serializacion de la fila completa con un bytea
# grande en TOAST puede variar transitoriamente bajo actividad TOAST concurrente de otra sesion (reproducido fuera de
# pytest; el contenido real no cambia), lo que hacia fallar este test de forma intermitente.
_DOCS_COLUMNAS = ("id", "institucion_id", "departamento_id", "tipo_documento", "categoria", "numero", "fecha",
                  "periodo_id", "cuil", "docente_nombre", "proyecto_tipo", "proyecto_id", "referencia_texto", "titulo",
                  "detalle", "observaciones", "archivo_nombre", "archivo_mime", "archivo_bytes", "fecha_carga",
                  "usuario_carga", "tipo_resolucion", "dependencia_id", "dependencia_nombre")
_DOCS_HUELLA = ("SELECT md5(string_agg(md5(json_build_array(" + ", ".join(f"d.{c}" for c in _DOCS_COLUMNAS) +
                ")::text) || ':' || COALESCE(md5(d.archivo_pdf), '-'), ',' ORDER BY d.id)) FROM documentos_respaldo d")


def _contar(db_conn):
    columnas = {r[0] for r in db_conn.execute("SELECT column_name FROM information_schema.columns WHERE "
                                              "table_schema='public' AND table_name='documentos_respaldo'")}
    assert columnas == set(_DOCS_COLUMNAS) | {"archivo_pdf"}, "documentos_respaldo cambio de columnas: actualizar"
    return db_conn.execute(
        "SELECT (" + _DOCS_HUELLA + "), "
        "(SELECT md5(string_agg(md5(x::text), '' ORDER BY x.id)) FROM dependencias_documentales x), "
        "(SELECT count(*) FROM documentos_respaldo_docentes), (SELECT count(*) FROM documentos_respaldo_proyectos), "
        "(SELECT count(*) FROM documentos_respaldo_designaciones), (SELECT count(*) FROM movimientos), "
        "(SELECT md5(string_agg(md5(r::text), '' ORDER BY r.id)) FROM resoluciones r), "
        "(SELECT count(*) FROM b12h_audit_log)").fetchone()


# ------------------------------------------------------------------------------------------ B10 por rol
def test_permisos_visuales_por_rol(resoluciones, records):
    esperado = {"dep": (True, False), "lector": (False, False), "super": (True, True), "coord_dep": (False, False)}
    for rol, (w, d) in esperado.items():
        assert resoluciones.overview(records[rol])["permisos"] == {"puede_escribir": w, "puede_borrar": d}, rol
    with pytest.raises(ResolucionesError) as exc:  # coordinador sin departamento: modulo no visible
        resoluciones.overview(records["coord"])
    assert exc.value.code == "SCOPE_INSTITUTIONAL"


def test_roles_sin_escritura_y_modo_comercial_read_only(resoluciones, service, repo, db_conn, audit_store, records):
    repo.institutions_rows[0]["estado_pago"] = "Vencido"
    ro = session_for(service, repo, 3)[0]
    with db_conn.transaction() as tx:
        did = _doc(db_conn, pdf=pdf_sintetico("ro"), nombre="ro.pdf", mime="application/pdf")
        antes = _contar(db_conn)
        for rec, codigo in ((ro, "DENY_COMMERCIAL_READ_ONLY"), (records["lector"], "DENY_READ_ONLY_ROLE"),
                            (records["coord_dep"], "DENY_ROLE_NOT_PERMITTED")):
            assert resoluciones.overview(rec)["permisos"] == {"puede_escribir": False, "puede_borrar": False}
            n = len(audit_store.events)
            llamadas = [
                lambda: resoluciones.guardar_acto(rec, {"categoria": "Otro", "tipo_documento": "Otro",
                                                        "fecha": "2026-10-20"}, None),
                lambda: resoluciones.adjuntar_pdf(rec, {"id": did}, Archivo("a.pdf", "application/pdf",
                                                                           pdf_sintetico())),
                lambda: resoluciones.dependencia_documento(rec, {"id": did, "dependencia_id": db_conn.execute(
                    "SELECT min(id) FROM dependencias_documentales WHERE institucion_id=1").fetchone()[0]}),
                lambda: resoluciones.agregar_dependencia(rec, {"nombre": "ZZNEXT Nueva"}),
                lambda: resoluciones.eliminar(rec, {"id": did, "confirmar": True}),
            ]
            for llamar in llamadas:
                with pytest.raises(ResolucionesError) as exc:
                    llamar()
                assert exc.value.status == 403
            eventos = audit_store.events[n:]
            assert [e.outcome for e in eventos] == ["DENIED"] * len(llamadas)
            assert {e.metadata["b10_decision"] for e in eventos} == {codigo}
            assert {e.audit_mode for e in eventos} == {"SEPARATE_TRANSACTION"}
            # lectura y descarga siguen permitidas
            assert resoluciones.descargar(rec, {"id": did})[0] == pdf_sintetico("ro")
        assert _contar(db_conn) == antes
        raise psycopg.Rollback(tx)


def test_eliminar_solo_superadmin(resoluciones, db_conn, audit_store, records):
    with db_conn.transaction() as tx:
        did = _doc(db_conn)
        with pytest.raises(ResolucionesError) as exc:
            resoluciones.eliminar(records["dep"], {"id": did, "confirmar": True})
        assert exc.value.status == 403
        assert audit_store.events[-1].outcome == "DENIED"
        assert audit_store.events[-1].metadata["b10_decision"] == "DENY_ROLE_NOT_PERMITTED"
        with pytest.raises(ResolucionesError) as exc:
            resoluciones.eliminar(records["super"], {"id": did})
        assert exc.value.message == "Primero confirmá la eliminación."
        assert resoluciones.eliminar(records["super"], {"id": did, "confirmar": True})["mensaje"] == \
            "Acto/documento eliminado del repositorio."
        raise psycopg.Rollback(tx)


def test_dependencias_son_institucionales_para_usuario_departamento(resoluciones, db_conn, records):
    with db_conn.transaction() as tx:
        rows_n = len(audit_rows(db_conn))
        resoluciones.agregar_dependencia(records["dep"], {"nombre": "ZZNEXT Institucional"})
        ev = audit_rows(db_conn)[rows_n:]
        assert [(e["operation"], e["action"], e["action_scope"], e["entity_type"], e["entity_id"]) for e in ev] == [
            ("guardar_dependencia_documental_v262", "documentos.write", "institution", "dependencia_documental", None)]
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ B12H
def test_contrato_b12h_y_metadata_sin_contenido(resoluciones, db_conn, audit_store, records):
    with db_conn.transaction() as tx:
        did = _doc(db_conn)
        dep_id = db_conn.execute("SELECT id FROM dependencias_documentales WHERE institucion_id=1 AND nombre='Rectorado'"
                                 ).fetchone()[0]
        n = len(audit_rows(db_conn))
        resoluciones.adjuntar_pdf(records["dep"], {"id": did}, Archivo("Secreto-ñ.pdf", "application/x-raro",
                                                                       pdf_sintetico("contenido secreto")))
        resoluciones.dependencia_documento(records["dep"], {"id": did, "dependencia_id": dep_id})
        resoluciones.editar_dependencia(records["dep"], {"id": dep_id, "nombre": "Rectorado", "estado": "Activa",
                                                         "observaciones": ""})
        ev = audit_rows(db_conn)[n:]
        assert [(e["operation"], e["entity_type"], e["entity_id"], e["outcome"], e["audit_mode"]) for e in ev] == [
            ("adjuntar_pdf_documento_respaldo_v272", "documento", str(did), "SUCCESS", "IN_TRANSACTION"),
            ("actualizar_dependencia_documento_v262", "documento", str(did), "SUCCESS", "IN_TRANSACTION"),
            ("actualizar_dependencia_documental_v262", "dependencia_documental", str(dep_id), "SUCCESS",
             "IN_TRANSACTION")]
        for e in ev:
            assert set(e["metadata"]) <= {"commit_seq", "mutating_statements", "committing_writer", "entity_param",
                                          "nested_system_task"}
            texto = json.dumps(e, default=str)
            for prohibido in ("Secreto", "x-raro", "%PDF", "contenido secreto", ".pdf"):
                assert prohibido not in texto
        assert {e["actor_email_normalized"] for e in ev} == {"info@test.local"}
        raise psycopg.Rollback(tx)


def test_failed_con_coupled_commits_y_sin_texto_de_error(resoluciones, db_conn, audit_store, records):
    with db_conn.transaction() as tx:
        did = _doc(db_conn)
        with pytest.raises(ResolucionesError) as exc:
            resoluciones.adjuntar_pdf(records["dep"], {"id": did}, Archivo("v.pdf", "application/pdf", b""))
        assert exc.value.message == "Seleccioná un PDF válido."
        e = audit_store.events[-1]
        assert (e.outcome, e.audit_mode, e.error_code, e.metadata["coupled_commits"]) == \
            ("FAILED", "SEPARATE_TRANSACTION", "ValueError", 0)
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ HTTP: multipart (D-AK1/2)
def _login(http, repo, email):
    r = http.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF)
    assert r.status_code == 200, r.text


@pytest.fixture
def cliente(http, repo):
    _login(http, repo, "info@test.local")
    return http


def _guardar(cliente, datos, archivo=None, headers=CSRF):
    files = {"datos": (None, json.dumps(datos), "application/json")}
    if archivo is not None:
        files["archivo"] = archivo
    return cliente.post("/resoluciones-respaldos/actos/guardar", files=files, headers=headers)


def _limpio(r):
    for prohibido in FORBIDDEN:
        assert prohibido not in r.text, prohibido


def test_http_alta_multipart_guarda_byte_a_byte_y_lista_sin_binario(cliente, db_conn):
    with db_conn.transaction() as tx:
        pdf = pdf_sintetico("http", 4096) + bytes(range(256))
        r = _guardar(cliente, {"categoria": "Otro", "tipo_documento": "Otro", "numero": "ZZNEXT-H/2026",
                               "fecha": "2026-10-20"}, ("ZZNEXT Resolución ñ.pdf", pdf, "application/x-raro-zz"))
        assert r.status_code == 200, r.text
        did = r.json()["id"]
        fila = db_conn.execute("SELECT archivo_nombre, archivo_mime, archivo_pdf, archivo_bytes FROM documentos_respaldo "
                               "WHERE id=%s", [did]).fetchone()
        assert (fila[0], bytes(fila[2]), fila[3]) == ("ZZNEXT Resolución ñ.pdf", pdf, len(pdf))
        assert fila[1] == "application/x-raro-zz"  # MIME declarado, conservado (D-AK3)
        ov = cliente.get("/resoluciones-respaldos")
        assert ov.status_code == 200
        _limpio(ov)
        assert any(f["id"] == did and f["estado_pdf"] == "Adjunto" for f in ov.json()["repositorio"]["filas"])
        det = cliente.post("/resoluciones-respaldos/documento", json={"id": did}, headers=CSRF)
        assert det.status_code == 200 and det.json()["tiene_pdf"] is True
        _limpio(det)
        raise psycopg.Rollback(tx)


def test_http_pdf_invalido_y_pdf_vacio_en_el_alta(cliente, db_conn):
    with db_conn.transaction() as tx:
        n = db_conn.execute("SELECT count(*) FROM documentos_respaldo").fetchone()[0]
        r = _guardar(cliente, {"categoria": "Otro", "tipo_documento": "Otro", "fecha": "2026-10-20"},
                     ("falso.pdf", b"PK\x03\x04no es pdf", "application/pdf"))
        assert r.status_code == 422 and r.json()["error"]["code"] == "PDF_INVALIDO"
        assert db_conn.execute("SELECT count(*) FROM documentos_respaldo").fetchone()[0] == n
        r = _guardar(cliente, {"categoria": "Otro", "tipo_documento": "Otro", "fecha": "2026-10-20"},
                     ("vacio.pdf", b"", "application/pdf"))
        assert r.status_code == 200 and r.json()["mensaje"].endswith("PDF pendiente de carga.")
        did = r.json()["id"]
        assert db_conn.execute("SELECT archivo_nombre, archivo_mime, archivo_bytes FROM documentos_respaldo WHERE id=%s",
                               [did]).fetchone() == ("", "", 0)
        raise psycopg.Rollback(tx)


def test_http_limites_50_mib(cliente, db_conn):
    with db_conn.transaction() as tx:
        did = _doc(db_conn)
        cabeza = b"%PDF-1.4\n"
        exacto = cabeza + b"0" * (R.MAX_PDF_BYTES - len(cabeza))
        r = cliente.post("/resoluciones-respaldos/documento/adjuntar-pdf", headers=CSRF,
                         files={"datos": (None, json.dumps({"id": did})), "archivo": ("exacto.pdf", exacto,
                                                                                     "application/pdf")})
        assert r.status_code == 200, r.text
        assert db_conn.execute("SELECT archivo_bytes FROM documentos_respaldo WHERE id=%s", [did]).fetchone()[0] == \
            R.MAX_PDF_BYTES
        r = cliente.post("/resoluciones-respaldos/documento/adjuntar-pdf", headers=CSRF,
                         files={"datos": (None, json.dumps({"id": did})), "archivo": ("grande.pdf", exacto + b"0",
                                                                                     "application/pdf")})
        assert r.status_code == 422 and r.json()["error"]["message"] == "El PDF supera 50 MB."
        r = _guardar(cliente, {"categoria": "Otro", "tipo_documento": "Otro", "fecha": "2026-10-20"},
                     ("grande.pdf", exacto + b"0", "application/pdf"))
        assert r.status_code == 422 and r.json()["error"]["message"] == ("El PDF supera 50 MB. Reducí su tamaño antes "
                                                                         "de cargarlo.")
        r = cliente.post("/resoluciones-respaldos/documento/adjuntar-pdf", headers=CSRF,
                         files={"datos": (None, json.dumps({"id": did})),
                                "archivo": ("enorme.pdf", exacto + b"0" * (2 * 1024 * 1024), "application/pdf")})
        assert r.status_code == 413
        raise psycopg.Rollback(tx)


def test_http_multipart_csrf_sesion_y_formato(http, cliente):
    assert _guardar(cliente, {"categoria": "Otro"}, headers={}).status_code == 403
    r = cliente.post("/resoluciones-respaldos/actos/guardar", json={"categoria": "Otro"}, headers=CSRF)
    assert r.status_code == 415
    r = cliente.post("/resoluciones-respaldos/actos/guardar", headers=CSRF,
                     files={"datos": (None, "no-es-json")})
    assert r.status_code == 400
    http.cookies.clear()
    assert _guardar(http, {"categoria": "Otro"}).status_code == 401


def test_parser_sin_volcado_a_disco():
    assert _Parser.spool_max_size >= MAX_TRANSPORTE  # el PDF no se escribe a un archivo temporal
    assert MAX_TRANSPORTE == R.MAX_PDF_BYTES + 1024 * 1024


# ------------------------------------------------------------------------------------------ HTTP: descarga (D-AK3/12)
def test_http_descarga_propia_ajena_inexistente_y_pendiente(cliente, http, repo, db_conn):
    with db_conn.transaction() as tx:
        pdf = pdf_sintetico("descarga")
        propio = _doc(db_conn, pdf=pdf, nombre="Acta\r\nSet-Cookie: x=1 \"ñ\".pdf", mime="text/html")
        ajeno = _doc(db_conn, dep=9, pdf=pdf, nombre="ajeno.pdf", mime="application/pdf")
        pendiente = _doc(db_conn)
        r = cliente.post("/resoluciones-respaldos/documento/pdf", json={"id": propio}, headers=CSRF)
        assert r.status_code == 200 and r.content == pdf
        assert r.headers["content-type"] == "application/pdf"
        assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"
        disp = r.headers["content-disposition"]
        assert disp.startswith("attachment; filename=\"") and "\r" not in disp and "\n" not in disp
        assert "Set-Cookie" not in r.headers.get("set-cookie", "") and "filename*=UTF-8''" in disp
        for did in (ajeno, 987654321):
            r = cliente.post("/resoluciones-respaldos/documento/pdf", json={"id": did}, headers=CSRF)
            assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
            _limpio(r)
        r = cliente.post("/resoluciones-respaldos/documento/pdf", json={"id": pendiente}, headers=CSRF)
        assert r.status_code == 404 and r.json()["error"]["code"] == "PDF_PENDIENTE"
        assert cliente.post("/resoluciones-respaldos/documento/pdf", json={"id": propio}).status_code == 403
        # otra institucion: el usuario de la UBA no ve el documento del dep 1 de la UNO
        http.cookies.clear()
        _login(http, repo, "uba@test.local")
        r = http.post("/resoluciones-respaldos/documento/pdf", json={"id": propio}, headers=CSRF)
        assert r.status_code in (404, 409)
        _limpio(r)
        raise psycopg.Rollback(tx)


def test_content_disposition_seguro():
    for nombre, ascii_esperado in [("Acta 1/2026.pdf", "Acta 1_2026.pdf"), ("Ñandú año.pdf", "Nandu ano.pdf"),
                                   ("a\r\nb\"c;d.pdf", "ab_c_d.pdf"), ("", "documento.pdf"), (None, "documento.pdf"),
                                   ("..\\..\\x.pdf", "_.._x.pdf")]:
        h = R.content_disposition(nombre)
        assert h.startswith(f"attachment; filename=\"{ascii_esperado}\"; filename*=UTF-8''"), (nombre, h)
        assert "\r" not in h and "\n" not in h and h.count('"') == 2


# ------------------------------------------------------------------------------------------ ausencias y legado
def test_rutas_inexistentes_y_tabla_legacy_intacta(cliente, db_conn):
    antes = _contar(db_conn)
    for ruta in ("/resoluciones-respaldos/zip", "/resoluciones-respaldos/excel", "/resoluciones-respaldos/exportar",
                 "/resoluciones-respaldos/importar", "/resoluciones-respaldos/documento/pdf/eliminar",
                 "/resoluciones-respaldos/dependencias/eliminar", "/resoluciones-respaldos/documento/editar"):
        assert cliente.post(ruta, json={}, headers=CSRF).status_code in (404, 405)
    cliente.get("/resoluciones-respaldos")
    assert _contar(db_conn) == antes  # las lecturas no escriben (D-AK7) ni tocan ``resoluciones`` (D-AK14)


def test_alta_no_escribe_en_el_filesystem(resoluciones, db_conn, records):
    raiz = Path(__file__).resolve().parents[2] / "storage"

    def huella():
        if not raiz.exists():
            return None
        return hashlib.md5("|".join(sorted(f"{p.relative_to(raiz)}:{p.stat().st_size}:{p.stat().st_mtime_ns}"
                                           for p in raiz.rglob("*"))).encode()).hexdigest()
    antes = huella()
    with db_conn.transaction() as tx:
        resoluciones.guardar_acto(records["dep"], {"categoria": "Otro", "tipo_documento": "Otro", "fecha": "2026-10-20"},
                                  Archivo("fs.pdf", "application/pdf", pdf_sintetico("fs", 2 * 1024 * 1024)))
        raise psycopg.Rollback(tx)
    assert huella() == antes
