"""E4-12 / P-12b — Períodos → "🗑️ Eliminar período" → "♻️ Reparar finalizaciones automáticas del período abierto".

Decision del usuario (2026-10-31): se porta dentro de E4-12, como operacion PROPIA (no es eliminar ni revertir).
Certificado (entry l. 63264-63284 / 11818-11945): ``diagnosticar_finalizaciones_automaticas_periodo`` +
``reactivar_finalizaciones_automaticas_periodo`` sobre el periodo abierto; reactiva designaciones finalizadas por cierre
y borra los movimientos "Finalización automática por cierre de período"; un COMMIT; solo superadmin; B10 periodos.write.

Escenario SINTETICO (institucion 2, departamento 5, dentro de un SAVEPOINT): el estado heredado que la reparacion
certificada corrige: 2027-1 con designaciones, 2027-2 creado SIN copiar (S9 cierra las de 2027-1) y luego borrado sin
reactivar los cierres (como lo hacia el borrado certificado previo a la reversion automatica), 2027-1 reabierto.
- reparable -> diferencial contra el writer CERTIFICADO (mismo estado final) + B12H en la transaccion;
- nada para reparar / sin periodo abierto -> 0 escrituras;
- finalizacion manual: no se toca;
- casos ambiguos / no huerfanos / vinculos / ambito -> fail closed (el certificado SI reparaba: diferencia consciente);
- permisos, stale, lock, fallo interno, verificacion posterior, HTTP.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

import psycopg
import pytest

import ciclo_support as CS
from periodos_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_store, db_conn, lock_conn, periodos, savepoint, session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")
FIXED_NOW = datetime(2026, 10, 26, 10, 30, 0)
INST, DEP = 2, 5
CUIL_A, CUIL_B, CUIL_C = "20-99120101-2", "20-99120102-0", "20-99120103-9"
TIPO = "Finalización automática por cierre de período"
OP = "reactivar_finalizaciones_automaticas_periodo"


@pytest.fixture
def ciclo(db_conn, periodos, audit_store):
    from integraciones.ciclo_periodos.service import CicloPeriodosService
    return CicloPeriodosService(None, periodos, audit_store, transaction=lambda: savepoint(db_conn),
                                today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, env=CS.DEV)


@pytest.fixture
def sup(service, repo):
    rec = session_for(service, repo, 1)[0]
    service.set_context(rec, INST, DEP, False)
    return rec


def _designacion(conn, pid, cuil, cargo, dedicacion, horas, estado="Activa"):
    return conn.execute("INSERT INTO designaciones (institucion_id, departamento_id, cuil, cargo, dedicacion, horas, "
                        "tipo_designacion, ad_honorem, fecha_desde, fecha_hasta, estado, periodo_id) VALUES (2,5,%s,%s,"
                        "%s,%s,'Interino','No','2027-01-01','',%s,%s) RETURNING id",
                        [cuil, cargo, dedicacion, horas, estado, pid]).fetchone()[0]


def escenario(conn, ciclo, sup, audit_store, *, borrar_nuevo=True):
    """2027-1 abierto con 3 finalizaciones automaticas huerfanas (+ 1 finalizacion manual de CUIL_C)."""
    p1 = ciclo.crear(sup, {"anio": 2027, "semestre": 1})["periodo_id"]
    ids = {"a1": _designacion(conn, p1, CUIL_A, "JTP", "Simple", 10),
           "a2": _designacion(conn, p1, CUIL_A, "Adjunto", "Parcial", 20),
           "b": _designacion(conn, p1, CUIL_B, "JTP", "Simple", 10)}
    p2 = ciclo.crear(sup, {"anio": 2027, "semestre": 2, "copiar_anterior": False})["periodo_id"]
    ids["manual"] = _designacion(conn, p1, CUIL_C, "JTP", "Simple", 10, "Finalizada")
    if borrar_nuevo:
        for tabla in ("designaciones", "movimientos", "estado_consulta_designacion"):
            conn.execute(f"DELETE FROM {tabla} WHERE periodo_id = %s", [p2])
        conn.execute("DELETE FROM periodos WHERE id = %s", [p2])
    else:  # "Abrir período anterior por excepción": 2027-2 sigue existiendo
        conn.execute("UPDATE periodos SET estado = 'Cerrado' WHERE id = %s", [p2])
    conn.execute("UPDATE periodos SET estado = 'Abierto' WHERE id = %s", [p1])
    audit_store.events.clear()
    return p1, ids


def _estado_designaciones(conn, ids):
    return {k: conn.execute("SELECT estado FROM designaciones WHERE id=%s", [v]).fetchone()[0] for k, v in ids.items()}


def _cierres(conn, pid):
    return conn.execute("SELECT count(*) FROM movimientos WHERE periodo_id=%s AND tipo_movimiento=%s",
                        [pid, TIPO]).fetchone()[0]


def _cert_ns():
    return CS.certified_ns(INST, DEP, hoy=lambda: FIXED_TODAY, ahora=lambda: FIXED_NOW,
                           extra=("reactivar_finalizaciones_automaticas_periodo",
                                  "diagnosticar_finalizaciones_automaticas_periodo"))


def _cert(db_conn, nombre, *args):
    from integraciones.ciclo_periodos import entorno
    ns = _cert_ns()
    unit = ns["_B12C"].TransactionUnit(lambda: entorno.RawTx(db_conn))
    with unit:
        r = ns[nombre](*args)
        if nombre.startswith("reactivar"):
            unit.trace.lock_statement = 0
            unit.commit()
    return r


def test_reparable_equivalente_al_certificado(db_conn, ciclo, sup, audit_store):
    with db_conn.transaction() as tx:
        p1, ids = escenario(db_conn, ciclo, sup, audit_store)
        assert _cierres(db_conn, p1) == 3
        diag = ciclo.reparar_diagnostico(sup)
        assert diag["visible"] and diag["puede_reparar"] and diag["bloqueos"] == []
        assert (diag["designaciones_reactivables"], diag["movimientos_cierre"]) == (3, 3)
        assert diag["mensaje"] == ("El período abierto 2027-1 todavía tiene finalizaciones automáticas por cierre. Se "
                                   "pueden reactivar 3 designación/es y limpiar 3 movimiento/s automático/s.")
        assert diag["boton"] == "♻️ Reparar finalizaciones automáticas del período abierto"
        assert _cert(db_conn, "diagnosticar_finalizaciones_automaticas_periodo", p1) == {
            "designaciones_reactivables": 3, "movimientos_cierre": 3}
        CS.baseline(db_conn)
        rc, ec, st_c, _ = CS.correr(db_conn, lambda: _cert(db_conn, OP, p1), INST, DEP)
        rn, en, st_n, filas = CS.correr(db_conn, lambda: ciclo.reparar(sup, {"huella": diag["huella"]}), INST, DEP)
        assert ec is None and en is None, en
        for k in st_c:
            assert st_c[k] == st_n[k], k
        assert rc == rn["resultado"] == {"designaciones_reactivadas": 3, "movimientos_cierre_eliminados": 3}
        assert rn["mensaje"] == ("Reparación realizada: 3 designación/es reactivada/s y 3 movimiento/s automático/s "
                                 "eliminado/s.") and rn["periodo_cambiado"] is False
        assert [(f["operation"], f["outcome"], f["action"], f["audit_mode"]) for f in filas
                if f["operation"] != "crear_periodo"] == [(OP, "SUCCESS", "periodos.write", "IN_TRANSACTION")]
        # lectura independiente posterior (dentro de la transaccion del test, despues del SAVEPOINT revertido: se
        # vuelve a ejecutar para leer el estado reparado)
        ciclo.reparar(sup, {"huella": diag["huella"]})
        assert _estado_designaciones(db_conn, ids) == {"a1": "Activa", "a2": "Activa", "b": "Activa",
                                                       "manual": "Finalizada"}
        assert _cierres(db_conn, p1) == 0
        assert ciclo.reparar_diagnostico(sup)["visible"] is False
        raise psycopg.Rollback(tx)


def test_nada_para_reparar_y_sin_periodo_abierto(db_conn, ciclo, sup, audit_store):
    from periodos.service import PeriodosError
    with db_conn.transaction() as tx:
        d0 = ciclo.reparar_diagnostico(sup)
        assert d0["visible"] is False and d0["periodo"] is None
        ciclo.crear(sup, {"anio": 2027, "semestre": 1})
        audit_store.events.clear()
        diag = ciclo.reparar_diagnostico(sup)
        assert diag["visible"] is False and diag["periodo"]["nombre"] == "2027-1" and "mensaje" not in diag
        CS.baseline(db_conn)
        antes = CS.estado(db_conn, INST, DEP)
        with pytest.raises(PeriodosError) as exc:
            ciclo.reparar(sup, {"huella": diag["huella"]})
        assert exc.value.status == 409 and exc.value.message == (
            "No se pudo reparar el período abierto: El período abierto no tiene finalizaciones automáticas por cierre "
            "para reparar. No se realizó ningún cambio.")
        assert CS.estado(db_conn, INST, DEP) == antes
        assert [(e.operation, e.outcome) for e in audit_store.events] == [(OP, "FAILED")]
        raise psycopg.Rollback(tx)


def _manual_mismo_texto(conn, p1, ids):
    _designacion(conn, p1, CUIL_B, "JTP", "Simple", 10, "Finalizada")


def _designacion_modificada(conn, p1, ids):  # el certificado la reactiva por "unica finalizada del CUIL"
    conn.execute("UPDATE designaciones SET cargo = 'Titular' WHERE id = %s", [ids["b"]])


def _detalle_alterado(conn, p1, ids):  # el certificado compara por subcadena
    conn.execute("UPDATE movimientos SET detalle = detalle || ' (editado)' WHERE periodo_id=%s AND cuil=%s",
                 [p1, CUIL_B])


def _movimiento_ajeno(conn, p1, ids):
    conn.execute("INSERT INTO movimientos (institucion_id, departamento_id, periodo_id, tipo_movimiento, cuil, nombre, "
                 "detalle, horas_variacion) VALUES (1,1,%s,%s,%s,'','Al cerrar 2027-1, se finalizó: x',0)",
                 [p1, TIPO, CUIL_A])


def _vinculo_documental(conn, p1, ids):
    doc = conn.execute("INSERT INTO documentos_respaldo (institucion_id, departamento_id, tipo_documento, categoria, "
                       "archivo_nombre, archivo_pdf, periodo_id) VALUES (2,5,'Resolución','Designación docente',"
                       "'zz.pdf','\\x00'::bytea,%s) RETURNING id", [p1]).fetchone()[0]
    mov = conn.execute("SELECT min(id) FROM movimientos WHERE periodo_id=%s AND tipo_movimiento=%s",
                       [p1, TIPO]).fetchone()[0]
    conn.execute("INSERT INTO documentos_respaldo_movimientos (institucion_id, departamento_id, documento_id, "
                 "movimiento_id) VALUES (2,5,%s,%s)", [doc, mov])


FAIL_CLOSED = {
    "finalización manual con el mismo texto": (_manual_mismo_texto, True, "caso ambiguo o finalización manual"),
    "designación modificada (fallback certificado por CUIL)": (_designacion_modificada, True, "caso ambiguo"),
    "detalle alterado (subcadena certificada)": (_detalle_alterado, True, "caso ambiguo"),
    "período posterior existente (abierto por excepción)": (None, False, "no es el último del departamento"),
    "movimiento de otro ámbito": (_movimiento_ajeno, True, "movimientos de otro ámbito"),
    "vínculo documental del movimiento": (_vinculo_documental, True, "documentos_respaldo_movimientos"),
}


@pytest.mark.parametrize("caso", sorted(FAIL_CLOSED))
def test_fail_closed_cero_escrituras(db_conn, ciclo, sup, audit_store, caso):
    """El certificado repararia igual (reactivaciones > 0); NEXT rechaza sin escribir (diferencia de seguridad)."""
    from periodos.service import PeriodosError
    preparar, borrar_nuevo, motivo = FAIL_CLOSED[caso]
    with db_conn.transaction() as tx:
        p1, ids = escenario(db_conn, ciclo, sup, audit_store, borrar_nuevo=borrar_nuevo)
        if preparar:
            preparar(db_conn, p1, ids)
        assert _cert(db_conn, "diagnosticar_finalizaciones_automaticas_periodo", p1)["designaciones_reactivables"] >= 3
        diag = ciclo.reparar_diagnostico(sup)
        assert diag["visible"] and diag["puede_reparar"] is False and diag["bloqueos"]
        assert diag["mensaje"].startswith("El período abierto 2027-1 tiene ") and motivo in diag["mensaje"]
        assert diag["mensaje"].endswith("No se realizará ningún cambio.")
        CS.baseline(db_conn)
        antes = CS.estado(db_conn, INST, DEP)
        with pytest.raises(PeriodosError) as exc:
            ciclo.reparar(sup, {"huella": diag["huella"]})
        assert exc.value.status == 409 and exc.value.code == "NO_REPARABLE"
        assert exc.value.message == "No se pudo reparar el período abierto: " + diag["mensaje"]
        assert CS.estado(db_conn, INST, DEP) == antes
        assert [f for f in CS.audit_rows(db_conn) if f["operation"] == OP] == []
        assert [(e.operation, e.outcome, e.error_code) for e in audit_store.events] == [
            (OP, "FAILED", "ReparacionBloqueada")]
        raise psycopg.Rollback(tx)


def test_permisos_y_stale(db_conn, ciclo, sup, service, repo, audit_store):
    from periodos.service import PeriodosError
    with db_conn.transaction() as tx:
        escenario(db_conn, ciclo, sup, audit_store)
        diag = ciclo.reparar_diagnostico(sup)
        usuario = session_for(service, repo, 4)[0]  # usuario_departamento del departamento 5
        assert ciclo.reparar_diagnostico(usuario) == {"es_superadmin": False, "visible": False}
        with pytest.raises(PeriodosError) as exc:
            ciclo.reparar(usuario, {"huella": diag["huella"]})
        assert exc.value.status == 403 and exc.value.message == ("Solo el superadmin puede reparar finalizaciones "
                                                                 "automáticas.")
        with pytest.raises(PeriodosError) as exc:
            ciclo.reparar(sup, {})
        assert exc.value.status == 422
        assert audit_store.events == []
        CS.baseline(db_conn)
        antes = CS.estado(db_conn, INST, DEP)
        with pytest.raises(PeriodosError) as exc:
            ciclo.reparar(sup, {"huella": "vieja"})
        assert exc.value.code == "STALE" and CS.estado(db_conn, INST, DEP) == antes
        # cambio real entre diagnostico y confirmacion -> stale
        db_conn.execute("DELETE FROM movimientos WHERE cuil=%s AND tipo_movimiento=%s AND departamento_id=5",
                        [CUIL_B, TIPO])
        with pytest.raises(PeriodosError) as exc:
            ciclo.reparar(sup, {"huella": diag["huella"]})
        assert exc.value.code == "STALE"
        assert [(e.operation, e.outcome) for e in audit_store.events] == [(OP, "FAILED"), (OP, "FAILED")]
        raise psycopg.Rollback(tx)


def test_lock_concurrente(ciclo, sup, audit_store, lock_conn):
    from periodos.service import PeriodosError
    ciclo.lock_timeout = "300ms"
    lock_conn.execute("SELECT pg_advisory_lock(hashtext(%s))", ["deptit_crear_periodo:2:5"])
    try:
        with pytest.raises(PeriodosError) as exc:
            ciclo.reparar(sup, {"huella": "x"})
        assert exc.value.code == "LOCK"
        assert [(e.operation, e.outcome, e.error_code) for e in audit_store.events] == [
            (OP, "FAILED", "ConsistencyLockError")]
    finally:
        lock_conn.execute("SELECT pg_advisory_unlock(hashtext(%s))", ["deptit_crear_periodo:2:5"])


@pytest.mark.parametrize("falla", ["excepcion despues de escribir", "resultado distinto del diagnostico"])
def test_fallo_interno_rollback_total(db_conn, ciclo, sup, audit_store, monkeypatch, falla):
    from periodos.service import PeriodosError
    original = ciclo._ns

    def ns_roto(record, scope):
        ns = original(record, scope)
        writer = ns[OP]

        def roto(*a, **k):
            res = writer(*a, **k)
            if falla.startswith("excepcion"):
                raise RuntimeError("fallo inyectado")
            return {**res, "designaciones_reactivadas": 99}
        ns[OP] = roto
        return ns
    with db_conn.transaction() as tx:
        p1, ids = escenario(db_conn, ciclo, sup, audit_store)
        diag = ciclo.reparar_diagnostico(sup)
        CS.baseline(db_conn)
        antes = CS.estado(db_conn, INST, DEP)
        monkeypatch.setattr(ciclo, "_ns", ns_roto)
        with pytest.raises(PeriodosError) as exc:
            ciclo.reparar(sup, {"huella": diag["huella"]})
        assert exc.value.status in (409, 503) and "fallo inyectado" not in exc.value.message
        assert CS.estado(db_conn, INST, DEP) == antes and _cierres(db_conn, p1) == 3
        assert [f for f in CS.audit_rows(db_conn) if f["operation"] == OP] == []
        assert [(e.operation, e.outcome) for e in audit_store.events] == [(OP, "FAILED")]
        raise psycopg.Rollback(tx)


def test_separada_de_eliminar_y_motor_literal():
    """P-12b es una operacion propia: writer certificado vendorizado literal; no borra periodos."""
    import inspect

    import integraciones.ciclo_periodos.motor.metadata as M
    from integraciones.ciclo_periodos.service import CicloPeriodosService
    assert {"diagnosticar_finalizaciones_automaticas_periodo", "reactivar_finalizaciones_automaticas_periodo",
            "_finalizaciones_automaticas_reactivables"} <= set(M.NOMBRES)
    assert "reactivar_finalizaciones_automaticas_periodo" in M.WRITERS_NEGOCIO
    fuente = inspect.getsource(CicloPeriodosService.reparar) + inspect.getsource(CicloPeriodosService._reparacion)
    assert "delete_period" not in fuente and "eliminar" not in fuente


def test_http(db_conn, ciclo, service, repo):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from integraciones.routes import periodos_router
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(periodos_router)
    app.state.auth = service
    app.state.ciclo_periodos = ciclo
    c = TestClient(app, base_url="http://localhost")
    h = {"X-DEPTIT-Request": "1"}
    rutas = ["/periodos/reparar-finalizaciones/diagnostico", "/periodos/reparar-finalizaciones"]
    for r in rutas:
        assert c.post(r, headers=h, json={}).status_code == 401
    c.cookies.set("deptit_session", session_for(service, repo, 4)[1])
    for r in rutas:
        assert c.post(r, json={}).status_code == 403  # sin cabecera del proxy
    assert c.post(rutas[0], headers=h, json={}).json() == {"es_superadmin": False, "visible": False}
    r = c.post(rutas[1], headers=h, json={"huella": "x"})
    assert r.status_code == 403 and not re.search(r"(?i)traceback|select\s|psycopg", r.text)
    assert json.loads(r.text)["error"]["message"] == "Solo el superadmin puede reparar finalizaciones automáticas."
