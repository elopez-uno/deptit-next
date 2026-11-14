"""Servicio y HTTP de Analisis — incluye Productividad: lectura para todos los roles con departamento (D-AM7), writer
``guardar_porcentaje_horas_no_lectivas_v148`` (B10 D-AM4, capa U D-AM5, B12H con ``entity_id`` NULL D-AM6, 1 COMMIT /
1 UPSERT), exportaciones (Word, CSV del indicador, CSV de alertas, TXT del prompt; D-AM1 / D-AM11), ausencias y
respuestas limpias.  Datos sinteticos dentro de la transaccion del test (ROLLBACK)."""

from __future__ import annotations

import json

import psycopg
import pytest

from analisis import pagina as P
from analisis.service import AnalisisError, huella_porcentaje
from analisis_support import (  # noqa: F401  (fixtures)
    analisis, audit_store, certified_analisis, db_conn, http, session_for,
)
from comisiones_support import audit_rows

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "DELETE ", "Traceback", "psycopg", "C:\\", "C:/", "source_db", "sqlite", "reference_fix02",
             "analisis.motor", "deptit_refactor")


@pytest.fixture
def records(service, repo):
    out = {"dep": session_for(service, repo, 3)[0], "lector": session_for(service, repo, 7)[0]}
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, 1, False)
    out["super"] = sup
    coord = session_for(service, repo, 2)[0]
    service.set_context(coord, 1, 1, False)
    out["coord_dep"] = coord
    out["coord"] = session_for(service, repo, 2)[0]
    repo.institutions_rows[0]["estado_pago"] = "Vencido"
    out["ro"] = session_for(service, repo, 3)[0]
    repo.institutions_rows[0]["estado_pago"] = "Al día"
    return out


def _config(db_conn, dep=1):
    return db_conn.execute("SELECT porcentaje_horas_no_lectivas, fecha_actualizacion FROM "
                           "config_productividad_departamento WHERE institucion_id=1 AND departamento_id=%s",
                           [dep]).fetchone()


def _foto(db_conn):
    return db_conn.execute(
        "SELECT (SELECT md5(string_agg(md5(c::text),'' ORDER BY c.id)) FROM config_productividad_departamento c), "
        "(SELECT md5(string_agg(md5(d::text),'' ORDER BY d.id)) FROM designaciones d), "
        "(SELECT md5(string_agg(md5(m::text),'' ORDER BY m.id)) FROM movimientos m), "
        "(SELECT count(*) FROM b12h_audit_log)").fetchone()


# ------------------------------------------------------------------------------------------ B10 por rol (D-AM7 / D-AM4)
def test_lectura_para_todos_los_roles_con_departamento(analisis, records, db_conn):
    """D-AM7 no reduce el acceso certificado: todos los roles con departamento ven Analisis."""
    esperado = {"dep": True, "super": True, "lector": False, "coord_dep": False, "ro": False}
    antes = _foto(db_conn)
    for rol, puede in esperado.items():
        ov = analisis.overview(records[rol])
        assert ov["tabs"] == P.TABS and ov["periodo"] == "2026-2", rol
        assert ov["permisos"] == {"puede_guardar": puede}, rol
        assert ov["parametro"]["texto"] == "50 %"
    with pytest.raises(AnalisisError) as exc:  # coordinador sin departamento: modulo no visible (como el certificado)
        analisis.overview(records["coord"])
    assert exc.value.code == "SCOPE_INSTITUTIONAL"
    assert _foto(db_conn) == antes  # las lecturas no escriben (D-AM2)
    assert db_conn.execute("SELECT count(*) FROM pg_locks WHERE locktype='advisory'").fetchone()[0] == 0


def test_guardar_denegado_sin_configuracion_write(analisis, records, db_conn, audit_store):
    with db_conn.transaction() as tx:
        antes = _foto(db_conn)
        h = analisis.overview(records["dep"])["parametro"]["huella"]
        for rol, codigo in (("lector", "DENY_READ_ONLY_ROLE"), ("coord_dep", "DENY_ROLE_NOT_PERMITTED"),
                            ("ro", "DENY_COMMERCIAL_READ_ONLY")):
            n = len(audit_store.events)
            with pytest.raises(AnalisisError) as exc:
                analisis.guardar_porcentaje(records[rol], {"porcentaje": 40, "huella": h})
            assert exc.value.status == 403
            ev = audit_store.events[n:]
            assert [(e.outcome, e.audit_mode, e.metadata["b10_decision"], e.entity_id, e.action) for e in ev] == [
                ("DENIED", "SEPARATE_TRANSACTION", codigo, None, "configuracion.write")]
        assert _foto(db_conn) == antes
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ writer + B12H + capa U
def test_guardar_porcentaje_b12h_capa_u_e_idempotencia(analisis, records, db_conn, audit_store):
    with db_conn.transaction() as tx:
        h = analisis.overview(records["dep"])["parametro"]["huella"]
        r = analisis.guardar_porcentaje(records["dep"], {"porcentaje": 45.5, "huella": h})
        assert r == {"mensaje": "Porcentaje guardado: 45.5 %. Se recalculará la productividad del departamento.",
                     "tono": "success"}
        assert float(_config(db_conn)[0]) == 45.5
        ev = audit_rows(db_conn)
        assert [(e["operation"], e["outcome"], e["audit_mode"], e["action"], e["action_scope"], e["entity_type"],
                 e["entity_id"], e["metadata"]["commit_seq"], e["metadata"]["mutating_statements"],
                 e["metadata"]["committing_writer"]) for e in ev] == [
            ("guardar_porcentaje_horas_no_lectivas_v148", "SUCCESS", "IN_TRANSACTION", "configuracion.write",
             "department", "configuracion", None, 1, 1, "guardar_porcentaje_horas_no_lectivas_v148")]
        assert "entity_param" not in ev[0]["metadata"]
        texto = json.dumps(ev[0]["metadata"], default=str)
        assert "info@" not in texto and "45.5" not in texto and "SELECT" not in texto
        # huella obsoleta (el valor cambio desde que se vio) -> 409 + FAILED, sin escribir
        n = len(audit_store.events)
        with pytest.raises(AnalisisError) as exc:
            analisis.guardar_porcentaje(records["dep"], {"porcentaje": 60, "huella": h})
        assert (exc.value.status, exc.value.code, exc.value.error_class) == (409, "STALE", "StaleDecisionError")
        assert [(e.outcome, e.error_code) for e in audit_store.events[n:]] == [("FAILED", "StaleDecisionError")]
        assert float(_config(db_conn)[0]) == 45.5 and len(audit_rows(db_conn)) == 1
        # huella vigente con el mismo valor: el UPSERT vuelve a escribir (1 COMMIT), como el certificado
        h2 = analisis.overview(records["dep"])["parametro"]["huella"]
        assert h2 == huella_porcentaje(45.5)
        analisis.guardar_porcentaje(records["super"], {"porcentaje": 45.5, "huella": h2})
        assert len(audit_rows(db_conn)) == 2 and float(_config(db_conn)[0]) == 45.5
        assert db_conn.execute("SELECT count(*) FROM pg_locks WHERE locktype='advisory'").fetchone()[0] == 0
        raise psycopg.Rollback(tx)


def test_guardar_en_departamento_sin_fila_y_valores_invalidos(analisis, service, repo, db_conn, audit_store):
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, 3, False)
    with db_conn.transaction() as tx:
        ov = analisis.overview(sup)
        assert ov["parametro"]["texto"] == "0 %" and ov["parametro"]["huella"] == huella_porcentaje(None)
        n = len(audit_store.events)
        for malo in ({"porcentaje": "50", "huella": ov["parametro"]["huella"]}, {"porcentaje": True, "huella": "x"},
                     {"porcentaje": -1, "huella": "x"}, {"porcentaje": 200.5, "huella": "x"},
                     {"porcentaje": 10}, {"porcentaje": None, "huella": "x"}):
            with pytest.raises(AnalisisError) as exc:
                analisis.guardar_porcentaje(sup, malo)
            assert exc.value.status == 422
        assert audit_store.events[n:] == []
        analisis.guardar_porcentaje(sup, {"porcentaje": 200, "huella": ov["parametro"]["huella"]})
        assert float(_config(db_conn, 3)[0]) == 200
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ lecturas de pantalla
def test_periodo_comparacion_y_errores(analisis, records, db_conn):
    p = analisis.periodo(records["dep"], {"periodo": "2026-2"})
    assert set(p) == {"periodo", "historico", "info_historico", "dashboard", "plantel", "movimiento", "automatico"}
    assert p["historico"] is False and p["info_historico"] is None
    h = analisis.periodo(records["dep"], {"periodo": "2026-1"})
    assert h["historico"] is True and h["info_historico"] == P.INFO_HISTORICO
    assert h["dashboard"]["dotacion"][0]["label"] == "Docentes del período"
    for malo, status in (({"periodo": "ZZNEXT"}, 409), ({"periodo": 9}, 422)):
        with pytest.raises(AnalisisError) as exc:
            analisis.periodo(records["dep"], malo)
        assert exc.value.status == status
    cmp_ = analisis.comparacion(records["dep"], {"periodos": ["2026-1"]})
    assert cmp_["incluidos"] == ["2026-2", "2026-1"] and set(cmp_["graficos"]) == {
        "horas", "porcentajes", "alumnos", "comisiones", "docentes"}
    assert analisis.comparacion(records["dep"], {"periodos": []}) == {"vacio": "Seleccioná al menos un período anterior "
                                                                                "para construir la comparación."}
    with pytest.raises(AnalisisError) as exc:
        analisis.comparacion(records["dep"], {"periodos": ["2026-2"]})  # el actual no es un "anterior"
    assert exc.value.status == 409


def test_graficos_con_semantica_vega_lite(analisis, records):
    p = analisis.periodo(records["dep"], {"periodo": "2026-2"})
    t = p["dashboard"]["torta_horas"]
    assert t["titulo"] == "Distribución de la dedicación contratada" and not t["vacio"]
    assert t["spec"]["mark"] == {"type": "arc", "tooltip": True}
    assert t["spec"]["encoding"]["theta"] == {"field": "horas", "type": "quantitative"}
    assert [v["concepto"] for v in t["spec"]["data"]["values"]][:5] == [
        "Comisiones (lectivas)", "Horas no lectivas", "Investigación", "Extensión", "Funciones no docentes"]
    vacio = P.torta({}, __import__("pandas").DataFrame({"c": ["a"], "v": [0]}), "c", "v", "T")
    assert vacio == {"titulo": "T", "vacio": True, "mensaje": "No hay datos para graficar.", "spec": None}
    g = analisis.comparacion(records["dep"], {"periodos": ["2026-1"]})["graficos"]
    assert g["horas"]["mark"] == {"type": "bar", "tooltip": True, "opacity": 0.58}
    assert g["horas"]["encoding"]["color"]["sort"] == ["2026-1", "2026-2"]
    assert g["porcentajes"]["mark"]["type"] == "line" and g["porcentajes"]["encoding"]["y"]["scale"] == {"domainMin": 0}
    assert g["comisiones"]["mark"]["opacity"] == 0.62 and g["docentes"]["mark"] == {"type": "bar", "tooltip": True}


# ------------------------------------------------------------------------------------------ exportaciones (HTTP)
def _login(http, repo, email="info@test.local"):
    assert http.post("/auth/login", json={"email": email, "password": repo.passwords[email]},
                     headers=CSRF).status_code == 200
    return http


def test_http_exportaciones_iguales_al_certificado(http, repo, db_conn):
    c = _login(http, repo)
    cert = certified_analisis(db_conn, 1, 1)
    df = P.movimientos_analisis(cert, cert["get_metricas_analisis_periodo"](9))
    r = c.post("/analisis/descargas/indicador", json={"periodo": "2026-2", "indicador": "Altas designaciones"},
               headers=CSRF)
    assert r.status_code == 200 and r.content == df[df["categoria_movimiento"] == "Altas de designaciones"].to_csv(
        index=False).encode("utf-8-sig")
    assert r.headers["content-disposition"].startswith('attachment; filename="movimiento_altas_designaciones_2026-2.csv"')
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"
    al = cert["construir_alertas_periodo"](9)
    cat = sorted(al["categoria"].unique())[0]
    r = c.post("/analisis/descargas/alertas", json={"periodo": "2026-2", "categoria": cat,
                                                    "gravedades": ["Alta", "Media", "Baja"]}, headers=CSRF)
    assert r.status_code == 200 and r.content == al[al["categoria"] == cat].to_csv(index=False).encode("utf-8-sig")
    assert P.nombre_alerta_csv(cat, "2026-2") in r.headers["content-disposition"] or "filename*" in \
        r.headers["content-disposition"]
    r = c.post("/analisis/descargas/prompt", json={"periodo": "2026-2"}, headers=CSRF)
    assert r.status_code == 200 and "Departamento de Informática e Ingeniería" in r.content.decode("utf-8")
    assert r.headers["content-type"].startswith("text/plain")
    r = c.post("/analisis/descargas/word", json={"periodo": "2026-2"}, headers=CSRF)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert r.headers["content-disposition"].startswith('attachment; filename="informe_movimiento_docente_2026-2.docx"')
    for ruta, body, status in (("indicador", {"periodo": "2026-2", "indicador": "ZZ"}, 422),
                               ("alertas", {"periodo": "2026-2", "categoria": "ZZ", "gravedades": ["Alta"]}, 409),
                               ("alertas", {"periodo": "2026-2", "categoria": cat, "gravedades": ["ZZ"]}, 422),
                               ("prompt", {"periodo": "ZZNEXT"}, 409)):
        r = c.post(f"/analisis/descargas/{ruta}", json=body, headers=CSRF)
        assert r.status_code == status and not any(x in r.text for x in FORBIDDEN)


def test_http_sesion_csrf_respuestas_limpias_y_ausencias(http, repo):
    assert http.get("/analisis").status_code == 401
    c = _login(http, repo)
    assert c.post("/analisis/periodo", json={"periodo": "2026-2"}).status_code == 403
    assert c.post("/analisis/porcentaje", json={"porcentaje": 1, "huella": "x"}).status_code == 403
    for ruta in ("excel", "xlsx", "pdf", "zip", "exportar", "imprimir", "ia", "reconciliar", "reparar"):
        assert c.post(f"/analisis/{ruta}", json={}, headers=CSRF).status_code in (404, 405), ruta
        assert c.post(f"/analisis/descargas/{ruta}", json={}, headers=CSRF).status_code in (404, 405), ruta
    for r in (c.get("/analisis"), c.post("/analisis/periodo", json={"periodo": "2026-2"}, headers=CSRF),
              c.post("/analisis/comparacion", json={"periodos": ["2026-1"]}, headers=CSRF)):
        assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
        assert not any(x in r.text for x in FORBIDDEN), [x for x in FORBIDDEN if x in r.text]
