"""E4-12 — Períodos → "🗑️ Eliminar período" — NEXT SOLO VACÍO (D-E4-03, P-12), en UNA transacción.

``eliminar_periodo_con_datos_admin`` (purga certificada) NO se porta.  Escenarios SINTETICOS en un departamento real sin
periodos (institucion 2, departamento 5), dentro de un SAVEPOINT:
- periodo realmente vacio (sin movimientos) y vacio + UNICA apertura automatica (P-12): se elimina; diferencial contra
  ``eliminar_periodo`` CERTIFICADO (el borrado de periodos vacios del entry, l. 11558) en el caso en que coinciden;
- cada familia de datos -> rechazo "El período contiene información y no puede eliminarse.", 0 escrituras;
- apertura ambigua (texto, CUIL, horas, dos aperturas, otro movimiento) -> fail closed;
- cierres automaticos que la creacion del periodo hizo en el anterior -> rechazo (corresponde Revertir);
- permisos (solo superadmin + ``periodos.delete``), confirmaciones, stale, lock, fallo interno, P-01b.
"""
from __future__ import annotations

import json
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
CUIL = "20-99120002-4"
MSG = "El período contiene información y no puede eliminarse."


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


def _datos(diag, **kw):
    return {"periodo_id": diag["periodo"]["id"], "confirmar": True, "texto_confirmacion": diag["texto_confirmacion"],
            "huella": diag["huella"], **kw}


def _dos_periodos(ciclo, sup, audit_store):
    """2027-1 y 2027-2 (creados por NEXT: cada uno con su apertura automatica; 2027-2 queda abierto y vacio)."""
    p1 = ciclo.crear(sup, {"anio": 2027, "semestre": 1})["periodo_id"]
    p2 = ciclo.crear(sup, {"anio": 2027, "semestre": 2})["periodo_id"]
    audit_store.events.clear()
    return p1, p2


def _cert_eliminar(db_conn, pid, obs):
    from integraciones.ciclo_periodos import entorno
    ns = CS.certified_ns(INST, DEP, hoy=lambda: FIXED_TODAY, ahora=lambda: FIXED_NOW,
                         extra=("eliminar_periodo", "reactivar_finalizaciones_automaticas_periodo"))
    unit = ns["_B12C"].TransactionUnit(lambda: entorno.RawTx(db_conn))
    with unit:
        ns["eliminar_periodo"](pid, obs)
        unit.trace.lock_statement = 0
        unit.commit()


def test_vacio_con_apertura_automatica_equivalente_al_certificado(db_conn, ciclo, sup, audit_store):
    with db_conn.transaction() as tx:
        p1, p2 = _dos_periodos(ciclo, sup, audit_store)
        diag = ciclo.eliminar_diagnostico(sup, {"periodo_id": p2})
        assert diag["vacio"] is True and diag["bloqueos"] == [] and diag["movimientos"] == 1
        assert diag["apertura_automatica"] is not None and diag["proximo_activo"]["id"] == p1
        assert diag["texto_confirmacion"] == "ELIMINAR 2027-2"
        CS.baseline(db_conn)
        _, ec, st_c, _ = CS.correr(db_conn, lambda: _cert_eliminar(db_conn, p2, "ZZNEXT elim"), INST, DEP)
        rn, en, st_n, filas = CS.correr(db_conn, lambda: ciclo.eliminar(sup, _datos(diag, observaciones="ZZNEXT elim")),
                                        INST, DEP)
        assert ec is None and en is None, en
        for k in st_c:
            assert st_c[k] == st_n[k], k
        assert [(json.loads(p)["nombre"], json.loads(p)["estado"]) for p in st_n["periodos"]] == [("2027-1", "Abierto")]
        movs = [json.loads(m) for m in st_n["movimientos_nuevos"]]
        assert [m["tipo_movimiento"] for m in movs] == ["Eliminación de período vacío"]  # la apertura de 2027-2 se borro
        assert movs[0]["detalle"] == ("Se eliminó el período vacío 2027-2 (2027-08-01 al 2027-12-31). Movimientos "
                                      "automáticos de apertura eliminados: 1. Luego se abrió automáticamente el período "
                                      "2027-1.")
        assert rn["mensaje"] == ("Período 2027-2 eliminado correctamente. Quedó activo: 2027-1 (2027-01-01 al "
                                 "2027-07-31).") and rn["periodo_cambiado"] is True
        assert [(f["operation"], f["outcome"], f["action"]) for f in filas if f["operation"] != "crear_periodo"] == [
            ("eliminar_periodo", "SUCCESS", "periodos.delete")]
        raise psycopg.Rollback(tx)


def test_realmente_vacio_sin_movimientos_y_unico_periodo(db_conn, ciclo, sup, audit_store):
    with db_conn.transaction() as tx:
        pid = db_conn.execute("INSERT INTO periodos (institucion_id, departamento_id, nombre, anio, semestre, fecha_inicio,"
                              " fecha_fin, estado, observaciones) VALUES (2,5,'2027-1',2027,1,'2027-01-01','2027-07-31',"
                              "'Abierto','') RETURNING id").fetchone()[0]
        diag = ciclo.eliminar_diagnostico(sup, {"periodo_id": pid})
        assert diag["vacio"] and diag["movimientos"] == 0 and diag["apertura_automatica"] is None
        assert diag["proximo_activo"] is None
        r = ciclo.eliminar(sup, _datos(diag))
        assert r["mensaje"] == "Período 2027-1 eliminado correctamente. No quedan períodos disponibles para abrir."
        assert db_conn.execute("SELECT count(*) FROM periodos WHERE departamento_id=5").fetchone()[0] == 0
        mov = db_conn.execute("SELECT periodo_id, detalle FROM movimientos WHERE departamento_id=5").fetchall()
        assert mov == [(None, "Se eliminó el período vacío 2027-1 (2027-01-01 al 2027-07-31). Movimientos automáticos "
                              "de apertura eliminados: 0.")]
        raise psycopg.Rollback(tx)


FAMILIAS = {
    "designaciones": "INSERT INTO designaciones (institucion_id, departamento_id, periodo_id, cuil, cargo, estado) VALUES "
                     "(2,5,{p},'{c}','JTP','Activa')",
    "movimiento adicional": "INSERT INTO movimientos (institucion_id, departamento_id, periodo_id, tipo_movimiento, cuil,"
                            " nombre, detalle, horas_variacion) VALUES (2,5,{p},'Alta de designación','{c}','X','x',10)",
    "comisiones": "INSERT INTO comisiones (institucion_id, departamento_id, periodo_id, nombre_comision) VALUES "
                  "(2,5,{p},'ZZNEXT')",
    "investigacion_docente": "INSERT INTO investigacion_docente (institucion_id, departamento_id, periodo_id, cuil,"
                             " nombre_proyecto) VALUES (2,5,{p},'{c}','ZZ')",
    "extension_docente": "INSERT INTO extension_docente (institucion_id, departamento_id, periodo_id, cuil, "
                         "nombre_proyecto) VALUES (2,5,{p},'{c}','ZZ')",
    "disposiciones": "INSERT INTO disposiciones (institucion_id, departamento_id, periodo_id, tipo, numero, cuil) VALUES "
                     "(2,5,{p},'Designación','ZZ','{c}')",
    "estado_consulta_designacion": "INSERT INTO estado_consulta_designacion (institucion_id, departamento_id, periodo_id,"
                                   " cuil, estado) VALUES (2,5,{p},'{c}','Consulta Enviada')",
    "actividades_especiales": "INSERT INTO actividades_especiales (institucion_id, departamento_id, periodo_id, titulo) "
                              "VALUES (2,5,{p},'ZZ')",
    "correcciones_historial_horas": "INSERT INTO correcciones_historial_horas (institucion_id, departamento_id, "
                                    "periodo_id, cuil, horas_inicio_reales) VALUES (2,5,{p},'{c}',1)",
    "prestamos_docentes": "INSERT INTO prestamos_docentes (institucion_id, departamento_id, periodo_id, cuil) VALUES "
                          "(2,5,{p},'{c}')",
    "documentos_respaldo": "INSERT INTO documentos_respaldo (institucion_id, departamento_id, tipo_documento, categoria,"
                           " archivo_nombre, archivo_pdf, periodo_id) VALUES (2,5,'Resolución','X','z.pdf','\\x00',{p})",
    "dato de otro departamento": "INSERT INTO designaciones (institucion_id, departamento_id, periodo_id, cuil, cargo, "
                                 "estado) VALUES (1,1,{p},'{c}','JTP','Activa')",
}


@pytest.mark.parametrize("familia", sorted(FAMILIAS))
def test_con_datos_rechazo_cero_escrituras(db_conn, ciclo, sup, audit_store, familia):
    from periodos.service import PeriodosError
    with db_conn.transaction() as tx:
        _, p2 = _dos_periodos(ciclo, sup, audit_store)
        db_conn.execute(FAMILIAS[familia].format(p=p2, c=CUIL))
        diag = ciclo.eliminar_diagnostico(sup, {"periodo_id": p2})
        assert diag["vacio"] is False and diag["mensaje"] == MSG and diag["bloqueos"]
        CS.baseline(db_conn)
        antes = CS.estado(db_conn, INST, DEP)
        with pytest.raises(PeriodosError) as exc:
            ciclo.eliminar(sup, _datos(diag))
        assert exc.value.status == 409 and exc.value.message == "No se pudo eliminar el período: " + MSG
        assert CS.estado(db_conn, INST, DEP) == antes
        assert [f for f in CS.audit_rows(db_conn) if f["operation"] == "eliminar_periodo"] == []
        assert [(e.operation, e.outcome, e.error_code) for e in audit_store.events] == [
            ("eliminar_periodo", "FAILED", "PeriodoConDatos")]
        raise psycopg.Rollback(tx)


AMBIGUAS = {
    "detalle distinto": "UPDATE movimientos SET detalle = detalle || ' ' WHERE id = {m}",
    "con CUIL": "UPDATE movimientos SET cuil = '{c}' WHERE id = {m}",
    "con horas": "UPDATE movimientos SET horas_variacion = 1 WHERE id = {m}",
    "tipo distinto": "UPDATE movimientos SET tipo_movimiento = 'Apertura de período ' WHERE id = {m}",
    "dos aperturas": "INSERT INTO movimientos (institucion_id, departamento_id, periodo_id, fecha, tipo_movimiento, cuil,"
                     " nombre, detalle, observaciones, horas_variacion) SELECT institucion_id, departamento_id, periodo_id,"
                     " fecha, tipo_movimiento, cuil, nombre, detalle, observaciones, horas_variacion FROM movimientos "
                     "WHERE id = {m}",
}


@pytest.mark.parametrize("caso", sorted(AMBIGUAS))
def test_apertura_ambigua_fail_closed(db_conn, ciclo, sup, audit_store, caso):
    from periodos.service import PeriodosError
    with db_conn.transaction() as tx:
        _, p2 = _dos_periodos(ciclo, sup, audit_store)
        m = db_conn.execute("SELECT id FROM movimientos WHERE periodo_id=%s", [p2]).fetchone()[0]
        db_conn.execute(AMBIGUAS[caso].format(m=m, c=CUIL))
        diag = ciclo.eliminar_diagnostico(sup, {"periodo_id": p2})
        assert diag["vacio"] is False and diag["apertura_automatica"] is None
        assert [b["tabla"] for b in diag["bloqueos"]] == ["movimientos"]
        with pytest.raises(PeriodosError):
            ciclo.eliminar(sup, _datos(diag))
        assert db_conn.execute("SELECT count(*) FROM periodos WHERE id=%s", [p2]).fetchone()[0] == 1
        raise psycopg.Rollback(tx)


def test_cierres_del_anterior_bloquean_corresponde_revertir(db_conn, ciclo, sup, audit_store):
    """2027-2 creado sin copiar no concursadas: queda vacio pero su creacion CERRO la designacion de 2027-1.  Borrarlo
    exigiria deshacer historia de otro periodo: se rechaza (la herramienta es Revertir ultimo cierre)."""
    with db_conn.transaction() as tx:
        p1 = ciclo.crear(sup, {"anio": 2027, "semestre": 1})["periodo_id"]
        db_conn.execute("INSERT INTO designaciones (institucion_id, departamento_id, cuil, cargo, dedicacion, horas,"
                        " tipo_designacion, ad_honorem, fecha_desde, fecha_hasta, estado, periodo_id) VALUES (2,5,%s,"
                        "'JTP','Simple',10,'Interino','No','2027-01-01','2027-07-31','Activa',%s)", [CUIL, p1])
        p2 = ciclo.crear(sup, {"anio": 2027, "semestre": 2, "copiar_anterior": False})["periodo_id"]
        diag = ciclo.eliminar_diagnostico(sup, {"periodo_id": p2})
        assert diag["vacio"] is False and diag["apertura_automatica"] is not None
        assert [b["etiqueta"] for b in diag["bloqueos"]] == [
            "Finalizaciones automáticas del período anterior generadas al crear este período"]
        raise psycopg.Rollback(tx)


def test_permisos_confirmaciones_y_stale(db_conn, ciclo, sup, service, repo, audit_store):
    from periodos.service import PeriodosError
    with db_conn.transaction() as tx:
        _, p2 = _dos_periodos(ciclo, sup, audit_store)
        diag = ciclo.eliminar_diagnostico(sup, {"periodo_id": p2})
        usuario = session_for(service, repo, 4)[0]
        d_u = ciclo.eliminar_diagnostico(usuario, {"periodo_id": p2})
        assert d_u == {"info": d_u["info"], "es_superadmin": False,
                       "mensaje_permiso": "Solo el superadmin puede eliminar períodos."}
        with pytest.raises(PeriodosError) as exc:
            ciclo.eliminar(usuario, _datos(diag))
        assert exc.value.status == 403
        for datos, msg in ((_datos(diag, confirmar=False), "Tenés que marcar la confirmación antes de eliminar el período."),):
            with pytest.raises(PeriodosError) as exc:
                ciclo.eliminar(sup, datos)
            assert exc.value.status == 422 and exc.value.message == msg
        assert audit_store.events == []
        with pytest.raises(PeriodosError) as exc:
            ciclo.eliminar(sup, _datos(diag, texto_confirmacion="ELIMINAR 2027-1"))
        assert exc.value.message == "No se pudo eliminar el período: La confirmación escrita no coincide. Escribí: " \
                                    "ELIMINAR 2027-2"
        with pytest.raises(PeriodosError) as exc:
            ciclo.eliminar(sup, _datos(diag, huella="vieja"))
        assert exc.value.code == "STALE"
        with pytest.raises(PeriodosError) as exc:  # periodo de otro departamento: no existe en el ambito
            ciclo.eliminar(sup, _datos(diag, periodo_id=9))
        assert exc.value.status == 404
        assert db_conn.execute("SELECT count(*) FROM periodos WHERE id IN (%s, 9)", [p2]).fetchone()[0] == 2
        raise psycopg.Rollback(tx)


def test_lock_concurrente(ciclo, sup, audit_store, lock_conn):
    from periodos.service import PeriodosError
    ciclo.lock_timeout = "300ms"
    lock_conn.execute("SELECT pg_advisory_lock(hashtext(%s))", ["deptit_crear_periodo:2:5"])
    try:
        with pytest.raises(PeriodosError) as exc:
            ciclo.eliminar(sup, {"periodo_id": 1, "confirmar": True, "texto_confirmacion": "x", "huella": "x"})
        assert exc.value.code == "LOCK"
    finally:
        lock_conn.execute("SELECT pg_advisory_unlock(hashtext(%s))", ["deptit_crear_periodo:2:5"])


def test_fallo_interno_rollback_total(db_conn, ciclo, sup, audit_store, monkeypatch):
    from periodos.service import PeriodosError
    original = ciclo._ns

    def ns_roto(record, scope):
        ns = original(record, scope)
        ns["registrar_movimiento"] = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fallo inyectado"))
        return ns
    with db_conn.transaction() as tx:
        _, p2 = _dos_periodos(ciclo, sup, audit_store)
        diag = ciclo.eliminar_diagnostico(sup, {"periodo_id": p2})
        CS.baseline(db_conn)
        antes = CS.estado(db_conn, INST, DEP)
        monkeypatch.setattr(ciclo, "_ns", ns_roto)
        with pytest.raises(PeriodosError) as exc:
            ciclo.eliminar(sup, _datos(diag))
        assert exc.value.status == 503 and "fallo inyectado" not in exc.value.message
        assert CS.estado(db_conn, INST, DEP) == antes
        raise psycopg.Rollback(tx)


def test_p01b_y_ninguna_purga(db_conn, ciclo, sup, periodos, audit_store):
    """Tras eliminar el abierto, la lectura del periodo abierto ya muestra el reabierto.  Y la purga certificada con
    datos (``eliminar_periodo_con_datos_admin``) no existe en NEXT."""
    import integraciones.ciclo_periodos.motor.metadata as M
    assert "eliminar_periodo_con_datos_admin" not in M.NOMBRES
    with db_conn.transaction() as tx:
        p1, p2 = _dos_periodos(ciclo, sup, audit_store)
        diag = ciclo.eliminar_diagnostico(sup, {"periodo_id": p2})
        assert periodos.overview(sup)["abierto"]["id"] == p2
        assert ciclo.eliminar(sup, _datos(diag))["periodo_cambiado"] is True
        assert periodos.overview(sup)["abierto"]["id"] == p1
        raise psycopg.Rollback(tx)
