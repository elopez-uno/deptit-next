"""E4-11 — Períodos → "↩️ Revertir último cierre" con PREFLIGHT completo (D-E4-05), en UNA transacción.

Escenarios SINTETICOS en un departamento real sin periodos (institucion 2, departamento 5): dentro de un SAVEPOINT se
crea 2027-1 con una designacion y luego 2027-2 (Crear periodo NEXT: copia + cierre automatico), y se revierte.
- reversible: diferencial contra ``revertir_ultimo_cierre_periodo`` CERTIFICADO (compilado desde reference_fix02) desde
  el mismo estado; B12H; P-01b;
- una familia de dependencias por caso en el periodo nuevo (y vinculos FK a sus designaciones / movimientos): rechazo
  funcional, 0 escrituras;
- permisos (solo superadmin), confirmaciones, stale, lock, fallo interno con rollback total.
Con los datos reales del departamento 1, revertir un Crear reciente queda BLOQUEADO (renovacion de investigacion S7
y vinculos documentales de la copia v266): el certificado fallaria por FK o borraria vinculos en cascada.
"""
from __future__ import annotations

import json
from datetime import date, datetime

import psycopg
import pytest

import ciclo_support as CS
from periodos_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_store, db_conn, lock_conn, periodos, savepoint, session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")
FIXED_NOW = datetime(2026, 10, 26, 10, 30, 0)
INST, DEP = 2, 5
CUIL = "20-99120001-6"
CONFIRMA = {"confirmar_1": True, "confirmar_2": True, "confirmar_3": True}


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


def escenario(db_conn, ciclo, sup, audit_store):
    """2027-1 (con una designacion Interina) y 2027-2 creado despues (renueva y cierra la de 2027-1)."""
    p1 = ciclo.crear(sup, {"anio": 2027, "semestre": 1})["periodo_id"]
    db_conn.execute("INSERT INTO designaciones (institucion_id, departamento_id, cuil, cargo, dedicacion, horas,"
                    " tipo_designacion, ad_honorem, fecha_desde, fecha_hasta, estado, periodo_id, observaciones,"
                    " numero_resolucion, funcion_no_docente, texto_funcion_no_docente) VALUES (2,5,%s,'JTP','Simple',"
                    "10,'Interino','No','2027-01-01','2027-07-31','Activa',%s,'ZZNEXT','',0,'')", [CUIL, p1])
    p2 = ciclo.crear(sup, {"anio": 2027, "semestre": 2})["periodo_id"]
    audit_store.events.clear()
    return p1, p2


def _cert_revertir(db_conn, obs):
    from integraciones.ciclo_periodos import entorno
    ns = CS.certified_ns(INST, DEP, hoy=lambda: FIXED_TODAY, ahora=lambda: FIXED_NOW, usuario={"email": "s@x"})
    unit = ns["_B12C"].TransactionUnit(lambda: entorno.RawTx(db_conn))
    with unit:
        r = ns["revertir_ultimo_cierre_periodo"](observaciones=obs)
        unit.trace.lock_statement = 0
        unit.commit()
    return r


def estado(conn) -> dict:
    out = CS.estado(conn, INST, DEP)
    return out


def test_reversible_equivalente_al_certificado(db_conn, ciclo, sup, audit_store):
    with db_conn.transaction() as tx:
        p1, p2 = escenario(db_conn, ciclo, sup, audit_store)
        diag = ciclo.revertir_diagnostico(sup)
        assert diag["ok"] and diag["puede_revertir"] and diag["bloqueos"] == []
        assert (diag["periodo_nuevo"]["id"], diag["periodo_anterior"]["id"]) == (p2, p1)
        assert (diag["designaciones_nuevo"], diag["cierres_anterior"], diag["activas_anterior"]) == (1, 1, 0)
        CS.baseline(db_conn)
        rc, ec, st_c, _ = CS.correr(db_conn, lambda: _cert_revertir(db_conn, "ZZNEXT rev"), INST, DEP)
        rn, en, st_n, filas = CS.correr(db_conn, lambda: ciclo.revertir(sup, {**CONFIRMA, "observaciones": "ZZNEXT rev",
                                                                              "huella": diag["huella"]}), INST, DEP)
        assert ec is None and en is None, en
        for k in st_c:
            assert st_c[k] == st_n[k], k
        assert rn["resultado"] == rc
        assert rn["mensaje"] == ("Cierre revertido. Período eliminado: 2027-2. Período reabierto: 2027-1. "
                                 "Designaciones reactivadas: 1.") and rn["periodo_cambiado"] is True
        assert [(f["operation"], f["outcome"], f["metadata"]["commit_seq"]) for f in filas
                if f["operation"] != "crear_periodo"] == [("revertir_ultimo_cierre_periodo", "SUCCESS", 1)]
        periodos = [json.loads(p) for p in st_n["periodos"]]
        assert [(p["nombre"], p["estado"]) for p in periodos] == [("2027-1", "Abierto")]
        movs = [json.loads(m)["tipo_movimiento"] for m in st_n["movimientos_nuevos"]]
        assert movs == ["Reversión de cierre de período"]
        raise psycopg.Rollback(tx)


def _sembrar(conn, familia, p1, p2):
    """Una fila de la familia en el periodo nuevo (o un vinculo a una fila que la reversion borraria)."""
    des = conn.execute("SELECT id FROM designaciones WHERE periodo_id=%s LIMIT 1", [p2]).fetchone()[0]
    mov = conn.execute("SELECT id FROM movimientos WHERE periodo_id=%s LIMIT 1", [p2]).fetchone()[0]
    doc = None
    if familia in ("documentos_respaldo", "documentos_respaldo_designaciones", "documentos_respaldo_movimientos"):
        doc = conn.execute("INSERT INTO documentos_respaldo (institucion_id, departamento_id, tipo_documento, categoria,"
                           " archivo_nombre, archivo_pdf, periodo_id) VALUES (2,5,'Resolución','Designación docente',"
                           "'zz.pdf','\\x00'::bytea,%s) RETURNING id",
                           [p2 if familia == "documentos_respaldo" else None]).fetchone()[0]
    sql = {
        "comisiones": ("INSERT INTO comisiones (institucion_id, departamento_id, periodo_id, nombre_comision) VALUES "
                       "(2,5,%s,'ZZNEXT')", [p2]),
        "disposiciones": ("INSERT INTO disposiciones (institucion_id, departamento_id, periodo_id, tipo, numero, cuil)"
                          " VALUES (2,5,%s,'Designación','ZZ-1',%s)", [p2, CUIL]),
        "investigacion_docente": ("INSERT INTO investigacion_docente (institucion_id, departamento_id, periodo_id, cuil,"
                                  " nombre_proyecto) VALUES (2,5,%s,%s,'ZZNEXT')", [p2, CUIL]),
        "extension_docente": ("INSERT INTO extension_docente (institucion_id, departamento_id, periodo_id, cuil,"
                              " nombre_proyecto) VALUES (2,5,%s,%s,'ZZNEXT')", [p2, CUIL]),
        "actividades_especiales": ("INSERT INTO actividades_especiales (institucion_id, departamento_id, periodo_id,"
                                   " titulo) VALUES (2,5,%s,'ZZNEXT')", [p2]),
        "correcciones_historial_horas": ("INSERT INTO correcciones_historial_horas (institucion_id, departamento_id,"
                                         " periodo_id, cuil, horas_inicio_reales) VALUES (2,5,%s,%s,1)", [p2, CUIL]),
        "prestamos_docentes": ("INSERT INTO prestamos_docentes (institucion_id, departamento_id, periodo_id, cuil)"
                               " VALUES (2,5,%s,%s)", [p2, CUIL]),
        "documentos_respaldo_designaciones": ("INSERT INTO documentos_respaldo_designaciones (institucion_id,"
                                              " departamento_id, documento_id, designacion_id) VALUES (2,5,%s,%s)",
                                              [doc, des]),
        "documentos_respaldo_movimientos": ("INSERT INTO documentos_respaldo_movimientos (institucion_id,"
                                            " departamento_id, documento_id, movimiento_id) VALUES (2,5,%s,%s)",
                                            [doc, mov]),
        "disposicion_docente_designaciones": ("INSERT INTO disposicion_docente_designaciones (institucion_id,"
                                              " departamento_id, designacion_id, cuil) VALUES (2,5,%s,%s)", [des, CUIL]),
    }.get(familia)
    if sql:
        conn.execute(*sql)


FAMILIAS = ["comisiones", "disposiciones", "investigacion_docente", "extension_docente", "actividades_especiales",
            "correcciones_historial_horas", "documentos_respaldo", "prestamos_docentes",
            "documentos_respaldo_designaciones", "documentos_respaldo_movimientos", "disposicion_docente_designaciones"]


@pytest.mark.parametrize("familia", FAMILIAS)
def test_no_reversible_por_dependencia_cero_escrituras(db_conn, ciclo, sup, audit_store, familia):
    from periodos.service import PeriodosError
    with db_conn.transaction() as tx:
        p1, p2 = escenario(db_conn, ciclo, sup, audit_store)
        _sembrar(db_conn, familia, p1, p2)
        diag = ciclo.revertir_diagnostico(sup)
        assert diag["ok"] and not diag["puede_revertir"]
        assert any(b["tabla"] == familia for b in diag["bloqueos"]), diag["bloqueos"]
        assert diag["mensaje_bloqueo"].startswith("No se puede revertir el último cierre: el período 2027-2 ya contiene")
        CS.baseline(db_conn)
        antes = estado(db_conn)
        with pytest.raises(PeriodosError) as exc:
            ciclo.revertir(sup, {**CONFIRMA, "huella": diag["huella"]})
        assert exc.value.status == 409 and exc.value.code == "DEPENDENCIAS"
        assert exc.value.message.endswith("No se realizó ningún cambio.")
        assert estado(db_conn) == antes
        assert [f for f in CS.audit_rows(db_conn) if f["operation"] != "crear_periodo"] == []
        assert [(e.operation, e.outcome, e.error_code) for e in audit_store.events] == [
            ("revertir_ultimo_cierre_periodo", "FAILED", "ReversionBloqueada")]
        raise psycopg.Rollback(tx)


def test_datos_reales_departamento_1_quedan_bloqueados(db_conn, ciclo, service, repo):
    """Datos reales del departamento 1: el inyector certificado sin parentesis sobre WHERE (a) OR (b) haria que
    ``get_periodo_anterior_cronologico`` devolviera un periodo de OTRO departamento; el entorno NEXT protege el OR
    (``proteger_or``) y el anterior correcto es 2026-2 propio.  Igual queda bloqueado por las dependencias del periodo
    nuevo (renovacion de investigacion S7)."""
    from analisis.motor.entorno import _inyector
    from integraciones.ciclo_periodos.entorno import proteger_or
    sql = "SELECT id FROM periodos WHERE (anio < ?) OR (anio = ? AND semestre < ?) ORDER BY anio DESC LIMIT 1"
    amb = {"kind": "tenant", "institucion_id": 1, "departamento_id": 1}
    crudo = _inyector()["_pg_scope_select"](sql, [2027, 2027, 1], amb)[0]
    assert "WHERE (anio < %s) OR" in crudo  # anomalia certificada: el primer termino queda sin ambito
    assert "WHERE ((anio < %s) OR" in _inyector()["_pg_scope_select"](proteger_or(sql), [2027, 2027, 1], amb)[0]
    sup1 = session_for(service, repo, 1)[0]
    service.set_context(sup1, 1, 1, False)
    with db_conn.transaction() as tx:
        ciclo.crear(sup1, {"anio": 2027, "semestre": 1})
        diag = ciclo.revertir_diagnostico(sup1)
        assert diag["ok"] and diag["periodo_anterior"]["id"] == 9 and not diag["puede_revertir"]
        assert "investigacion_docente" in {b["tabla"] for b in diag["bloqueos"]}
        raise psycopg.Rollback(tx)


def test_diagnostico_certificado_no_reversible(db_conn, ciclo, sup, audit_store):
    """Mensajes certificados: abierto que no es el ultimo / sin anterior.  "Sin anterior" en el departamento 5 exige el
    hardening de ambito: el get_periodo_anterior_cronologico certificado devuelve un periodo de OTRO departamento
    (inyector B12B sin parentesis sobre WHERE (a) OR (b))."""
    from periodos.service import PeriodosError
    with db_conn.transaction() as tx:
        ciclo.crear(sup, {"anio": 2027, "semestre": 1})
        d = ciclo.revertir_diagnostico(sup)
        assert (d["ok"], d["mensaje"]) == (False, "No hay período anterior para restaurar.")
        with pytest.raises(PeriodosError) as exc:
            ciclo.revertir(sup, {**CONFIRMA, "huella": d["huella"]})
        assert exc.value.message == "No se pudo revertir el cierre: No hay período anterior para restaurar."
        ciclo.crear(sup, {"anio": 2025, "semestre": 2})  # mas antiguo: queda abierto pero no es el ultimo
        d = ciclo.revertir_diagnostico(sup)
        assert (d["ok"], d["mensaje"]) == (False, "Solo se puede revertir el último período creado.")
        raise psycopg.Rollback(tx)


def test_permisos_confirmaciones_y_stale(db_conn, ciclo, sup, service, repo, audit_store):
    from periodos.service import PeriodosError
    with db_conn.transaction() as tx:
        escenario(db_conn, ciclo, sup, audit_store)
        diag = ciclo.revertir_diagnostico(sup)
        usuario = session_for(service, repo, 4)[0]  # usuario_departamento del departamento 5
        d_u = ciclo.revertir_diagnostico(usuario)
        assert d_u["es_superadmin"] is False and d_u["mensaje_permiso"] == ("Solo el superadmin puede revertir un "
                                                                            "cierre de período.")
        with pytest.raises(PeriodosError) as exc:
            ciclo.revertir(usuario, {**CONFIRMA, "huella": diag["huella"]})
        assert exc.value.status == 403
        with pytest.raises(PeriodosError) as exc:
            ciclo.revertir(sup, {"confirmar_1": True, "confirmar_2": True, "huella": diag["huella"]})
        assert exc.value.status == 422 and exc.value.message == ("Tenés que marcar las tres confirmaciones antes de "
                                                                 "revertir el cierre.")
        assert audit_store.events == []
        CS.baseline(db_conn)
        antes = estado(db_conn)
        with pytest.raises(PeriodosError) as exc:
            ciclo.revertir(sup, {**CONFIRMA, "huella": "vieja"})
        assert exc.value.code == "STALE" and estado(db_conn) == antes
        assert [(e.operation, e.outcome) for e in audit_store.events] == [
            ("revertir_ultimo_cierre_periodo", "FAILED")]
        raise psycopg.Rollback(tx)


def test_lock_concurrente(db_conn, ciclo, sup, audit_store, lock_conn):
    """Otra operacion de estado de periodos en curso (misma clave B12C / B12I): espera acotada -> 409, sin escribir.
    (Sin escenario previo en la transaccion del test: ese lock ya seria de esta misma sesion.)"""
    from periodos.service import PeriodosError
    ciclo.lock_timeout = "300ms"
    lock_conn.execute("SELECT pg_advisory_lock(hashtext(%s))", ["deptit_crear_periodo:2:5"])
    try:
        with pytest.raises(PeriodosError) as exc:
            ciclo.revertir(sup, {**CONFIRMA, "huella": "x"})
        assert exc.value.code == "LOCK"
        assert [(e.operation, e.outcome, e.error_code) for e in audit_store.events] == [
            ("revertir_ultimo_cierre_periodo", "FAILED", "ConsistencyLockError")]
    finally:
        lock_conn.execute("SELECT pg_advisory_unlock(hashtext(%s))", ["deptit_crear_periodo:2:5"])


def test_fallo_interno_rollback_total(db_conn, ciclo, sup, audit_store, monkeypatch):
    """Falla el movimiento final (despues de reactivar, borrar y reabrir): nada queda escrito."""
    from periodos.service import PeriodosError
    original = ciclo._ns

    def ns_roto(record, scope):
        ns = original(record, scope)

        def falla(*a, **k):
            raise RuntimeError("fallo inyectado")
        ns["registrar_movimiento"] = falla
        return ns
    with db_conn.transaction() as tx:
        escenario(db_conn, ciclo, sup, audit_store)
        diag = ciclo.revertir_diagnostico(sup)
        CS.baseline(db_conn)
        antes = estado(db_conn)
        monkeypatch.setattr(ciclo, "_ns", ns_roto)
        with pytest.raises(PeriodosError) as exc:
            ciclo.revertir(sup, {**CONFIRMA, "huella": diag["huella"]})
        assert exc.value.status == 503 and "fallo inyectado" not in exc.value.message
        assert estado(db_conn) == antes
        assert [f for f in CS.audit_rows(db_conn) if f["operation"] != "crear_periodo"] == []
        raise psycopg.Rollback(tx)


def test_p01b_overview_inmediato(db_conn, ciclo, sup, periodos):
    """Tras revertir, la lectura del periodo abierto (shell / modulo) ya muestra el anterior reabierto."""
    with db_conn.transaction() as tx:
        p1, p2 = escenario(db_conn, ciclo, sup, audit_store=type("A", (), {"events": []})())
        assert periodos.overview(sup)["abierto"]["id"] == p2
        diag = ciclo.revertir_diagnostico(sup)
        r = ciclo.revertir(sup, {**CONFIRMA, "huella": diag["huella"]})
        assert r["periodo_cambiado"] is True and periodos.overview(sup)["abierto"]["id"] == p1
        raise psycopg.Rollback(tx)
