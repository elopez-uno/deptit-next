"""E4-10 — Períodos → "➕ Crear nuevo período" (B12C) en UNA transacción, con el gate de backup B11 (D-E4-04).

Diferencial contra B13-FIX02 desde el mismo estado real de ``deptit_next_dev`` (SAVEPOINT + ROLLBACK):
- lado certificado: ``crear_periodo_atomico`` del modulo B12C ORIGINAL de reference_fix02 sobre la cascada certificada
  compilada desde el AST del entry (``ciclo_support.certified_ns``);
- lado NEXT: ``CicloPeriodosService.crear`` (motor vendorizado literal + B10 + B11 + B12H en la transaccion).
Se comparan periodos, designaciones, movimientos nuevos, investigacion, extension, asignaciones, vinculos documentales y
estado de consulta; ademas atomicidad (fallo inyectado en cada paso), lock, gate, permisos, ambito, HTTP y P-01b.
"""
from __future__ import annotations

import ast
import hashlib
import re
from datetime import datetime
from pathlib import Path

import psycopg
import pytest

import ciclo_support as CS
from periodos_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_store, db_conn, lock_conn, periodos, savepoint, session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST, DEP = 1, 1
BACKEND = Path(__file__).resolve().parents[1]
FIXED_NOW = datetime(2026, 10, 26, 10, 30, 0)


@pytest.fixture
def ciclo(db_conn, periodos, audit_store):
    from integraciones.ciclo_periodos.service import CicloPeriodosService
    return CicloPeriodosService(None, periodos, audit_store, transaction=lambda: savepoint(db_conn),
                                today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, env=CS.DEV)


def _rec(service, repo, uid=3, dep=None):
    rec = session_for(service, repo, uid)[0]
    if dep is not None:
        service.set_context(rec, INST, dep, False)
    return rec


def _cert(db_conn, anio, semestre, copiar=True, obs="", dep=DEP, inst=INST):
    from integraciones.ciclo_periodos import entorno
    ns = CS.certified_ns(inst, dep, hoy=lambda: FIXED_TODAY, ahora=lambda: FIXED_NOW,
                         usuario={"email": "info@test.local", "rol": "usuario_departamento"})
    trazas = {}
    pid = ns["_B12C"].crear_periodo_atomico(ns, lambda: entorno.RawTx(db_conn), lambda t: trazas.setdefault("t", t),
                                            anio, semestre, copiar, obs)
    return {"periodo_id": pid, "pasos": list(trazas["t"].steps), "escrituras": len(trazas["t"].writes)}


def comparar(db_conn, cert, nxt):
    CS.baseline(db_conn)
    rc, ec, st_c, _ = CS.correr(db_conn, cert)
    rn, en, st_n, filas = CS.correr(db_conn, nxt)
    assert (ec is None) == (en is None), (ec, en)
    for k in st_c:
        assert st_c[k] == st_n[k], k
    return rc, ec, rn, en, st_n, filas


# ------------------------------------------------------------------------------------------ diferencial
@pytest.mark.parametrize("copiar", [True, False])
def test_crear_equivalente_con_datos_reales(db_conn, ciclo, service, repo, audit_store, copiar):
    """2027-1 sobre el departamento real (2026-2 abierto con designaciones, investigacion y comisiones)."""
    rec = _rec(service, repo)
    rc, ec, rn, en, st, filas = comparar(
        db_conn, lambda: _cert(db_conn, 2027, 1, copiar, "ZZNEXT obs"),
        lambda: ciclo.crear(rec, {"anio": 2027, "semestre": 1, "copiar_anterior": copiar, "observaciones": "ZZNEXT obs"}))
    assert ec is None and en is None, en
    assert rn["pasos"] == rc["pasos"] == ["S0_bloqueo", "S1_duplicado", "S2_periodo_anterior", "S3_cierre_y_alta",
                                          "S4_movimiento_apertura", "S5_vencimientos", "S6_copia_designaciones",
                                          "S7_investigacion", "S8_extension", "S9_finalizacion"]
    assert rn["escrituras"] == rc["escrituras"] > 0
    assert rn["mensaje"] == "Período creado correctamente." and rn["periodo_cambiado"] is True
    nuevos = [x for x in st["periodos"] if '"NUEVO"' in x]
    assert len(nuevos) == 1 and '"estado": "Abierto"' in nuevos[0] and '"nombre": "2027-1"' in nuevos[0]
    assert sum('"estado": "Abierto"' in x for x in st["periodos"]) == 1
    tipos = [__import__("json").loads(m)["tipo_movimiento"] for m in st["movimientos_nuevos"]]
    assert tipos.count("Apertura de período") == 1
    assert ("Renovación automática de designación" in tipos) is copiar
    assert [(f["operation"], f["outcome"], f["metadata"]["commit_seq"]) for f in filas] == [
        ("crear_periodo", "SUCCESS", 1)]
    assert filas[0]["metadata"]["mutating_statements"] == rn["escrituras"]


def test_crear_sin_periodo_anterior(db_conn, ciclo, service, repo):
    """Departamento real SIN periodos (institucion 2, departamento 5): solo S0-S6, como el certificado."""
    rec = _rec(service, repo, 4)
    CS.baseline(db_conn)
    rc, ec, _, _ = CS.correr(db_conn, lambda: _cert(db_conn, 2027, 1, inst=2, dep=5))
    rn, en, _, filas = CS.correr(db_conn, lambda: ciclo.crear(rec, {"anio": 2027, "semestre": 1}))
    assert ec is None and en is None, en
    assert rn["pasos"] == rc["pasos"] == ["S0_bloqueo", "S1_duplicado", "S2_periodo_anterior", "S3_cierre_y_alta",
                                          "S4_movimiento_apertura", "S5_vencimientos", "S6_copia_designaciones"]
    assert rn["escrituras"] == rc["escrituras"] == 3  # cierre (UPDATE sin filas) + alta + movimiento de apertura
    assert [(f["operation"], f["institucion_id"], f["departamento_id"]) for f in filas] == [("crear_periodo", 2, 5)]


def test_crear_periodo_mas_antiguo(db_conn, ciclo, service, repo):
    """Un periodo anterior al actual (2025-2): el certificado lo crea y lo abre (queda historico); NEXT igual."""
    rec = _rec(service, repo)
    rc, ec, rn, en, st, _ = comparar(db_conn, lambda: _cert(db_conn, 2025, 2),
                                     lambda: ciclo.crear(rec, {"anio": 2025, "semestre": 2}))
    assert ec is None and en is None and rn["pasos"] == rc["pasos"]


# ------------------------------------------------------------------------------------------ validaciones y duplicado
def test_duplicado_y_contexto(db_conn, ciclo, service, repo, audit_store):
    from periodos.service import PeriodosError
    rec = _rec(service, repo)
    ctx = ciclo.crear_contexto(rec, {"anio": 2026, "semestre": 2})
    assert ctx["existente"]["nombre"] == "2026-2" and ctx["objetivo"] == {
        "nombre": "2026-2", "fecha_inicio": "2026-08-01", "fecha_fin": "2026-12-31"}
    assert ctx["aviso"].startswith("Al crear un período nuevo, cualquier período abierto anterior quedará cerrado.")
    assert ctx["anio_default"] == FIXED_TODAY.year and [s["etiqueta"] for s in ctx["semestres"]] == [
        "1° período: 01/01 al 31/07", "2° período: 01/08 al 31/12"]
    CS.baseline(db_conn)
    antes = CS.estado(db_conn)
    rc, ec, _, _ = CS.correr(db_conn, lambda: _cert(db_conn, 2026, 2))
    with pytest.raises(PeriodosError) as exc:
        ciclo.crear(rec, {"anio": 2026, "semestre": 2})
    assert exc.value.status == 409 and exc.value.message == str(ec) == (
        "El período 2026-2 ya está registrado. No se creó ningún período nuevo ni se modificó el período abierto.")
    assert CS.estado(db_conn) == antes
    assert [(e.operation, e.outcome, e.error_code) for e in audit_store.events] == [
        ("crear_periodo", "FAILED", "PeriodoDuplicadoError")]


@pytest.mark.parametrize("datos", [{"anio": 2019, "semestre": 1}, {"anio": 2101, "semestre": 1},
                                   {"anio": "2027", "semestre": 1}, {"anio": True, "semestre": 1},
                                   {"anio": 2027, "semestre": 3}, {"anio": 2027, "semestre": 1, "copiar_anterior": "si"},
                                   {"anio": 2027, "semestre": 1, "observaciones": 5}])
def test_valores_invalidos(db_conn, ciclo, service, repo, audit_store, datos):
    from periodos.service import PeriodosError
    with pytest.raises(PeriodosError) as exc:
        ciclo.crear(_rec(service, repo), datos)
    assert exc.value.status == 422 and audit_store.events == []


# ------------------------------------------------------------------------------------------ gate de backup (D-E4-04)
def test_gate_configuracion_fail_closed():
    from integraciones.ciclo_periodos import backup_gate as G
    assert G.configuracion({}) == G.Configuracion("produccion", True)
    assert G.configuracion({"DEPTIT_ENTORNO": "desarrollo"}).activo is True  # default: activo
    assert G.configuracion(CS.DEV) == G.Configuracion("desarrollo", False)
    for env in ({"DEPTIT_BACKUP_GATE_CREAR_PERIODO": "desactivado"},
                {"DEPTIT_ENTORNO": "produccion", "DEPTIT_BACKUP_GATE_CREAR_PERIODO": "desactivado"},
                {"DEPTIT_ENTORNO": "Desarrollo2", "DEPTIT_BACKUP_GATE_CREAR_PERIODO": "desactivado"},
                {"DEPTIT_BACKUP_GATE_CREAR_PERIODO": "apagado"}):
        with pytest.raises(G.GateConfigError):
            G.validar_arranque(env)


def test_gate_activo_deniega_sin_backup_verificado(db_conn, periodos, service, repo, audit_store, tmp_path):
    """Produccion (gate activo): sin configuracion, con directorio vacio o con evidencia vencida -> DENY B11 con el
    mensaje certificado, FAILED B12H y 0 SQL de la operacion.  Con evidencia valida (decision ALLOW inyectada, como el
    proveedor de evidencia certificado) crea."""
    from integraciones.ciclo_periodos.ref_b11 import backup_gate as B11
    from integraciones.ciclo_periodos.service import CicloPeriodosService
    from periodos.service import PeriodosError
    rec = _rec(service, repo)
    CS.baseline(db_conn)
    antes = CS.estado(db_conn)
    casos = [({}, None, "DENY_CONFIG_BACKUP_DIR"),
             ({"DEPTIT_BACKUP_DIR": str(tmp_path), "DEPTIT_CRITICAL_BACKUP_MAX_AGE_HOURS": "24"}, None,
              "DENY_NO_BACKUP"),
             ({"DEPTIT_BACKUP_DIR": str(tmp_path), "DEPTIT_CRITICAL_BACKUP_MAX_AGE_HOURS": "0"}, None,
              "DENY_CONFIG_MAX_AGE"),
             ({}, lambda: B11._deny("DENY_EXPIRED"), "DENY_EXPIRED")]
    for env, evidencia, codigo in casos:
        c = CicloPeriodosService(None, periodos, audit_store, transaction=lambda: savepoint(db_conn),
                                 today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, env={"DEPTIT_ENTORNO": "produccion",
                                                                                         **env},
                                 evidencia=evidencia, database_url="postgresql://u@127.0.0.1:5432/deptit_next_dev")
        n = len(audit_store.events)
        with pytest.raises(PeriodosError) as exc:
            c.crear(rec, {"anio": 2027, "semestre": 1})
        assert exc.value.status == 409 and f"código {codigo}" in exc.value.message, exc.value.message
        assert exc.value.message.startswith("No se puede crear el período: falta un backup reciente y verificado")
        assert "No se realizó ningún cambio." in exc.value.message and "C:\\" not in exc.value.message
        assert [(e.operation, e.outcome, e.error_code) for e in audit_store.events[n:]] == [
            ("crear_periodo", "FAILED", "BackupPreconditionError")]
        assert CS.estado(db_conn) == antes
    ok = CicloPeriodosService(None, periodos, audit_store, transaction=lambda: savepoint(db_conn),
                              today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, env={"DEPTIT_ENTORNO": "produccion"},
                              evidencia=lambda: B11.GateDecision(True, B11.ALLOW, "backup verificado (test)"))
    assert ok.crear_contexto(rec, {})["gate"] == {"activo": True, "entorno": "produccion", "aviso": None}
    with db_conn.transaction() as tx:
        assert ok.crear(rec, {"anio": 2027, "semestre": 1})["mensaje"] == "Período creado correctamente."
        raise psycopg.Rollback(tx)


def test_gate_desactivado_en_desarrollo_es_visible(ciclo, service, repo):
    g = ciclo.crear_contexto(_rec(service, repo), {})["gate"]
    assert g["activo"] is False and g["entorno"] == "desarrollo"
    assert "DESACTIVADO por configuración explícita" in g["aviso"] and "En producción es obligatorio" in g["aviso"]


# ------------------------------------------------------------------------------------------ atomicidad, lock, permisos
@pytest.mark.parametrize("paso", ["S1_duplicado", "S3_cierre_y_alta", "S4_movimiento_apertura", "S6_copia_designaciones",
                                  "S7_investigacion", "S9_finalizacion"])
def test_fallo_intermedio_revierte_todo(db_conn, ciclo, service, repo, audit_store, paso):
    from integraciones.ciclo_periodos import entorno
    from periodos.service import PeriodosError
    rec = _rec(service, repo)
    CS.baseline(db_conn)
    antes = CS.estado(db_conn)

    def falla(unit, nombre):
        if nombre == paso:
            raise RuntimeError("fallo inyectado")
    entorno.B12C.CHECKPOINT_HOOKS.append(falla)
    try:
        with pytest.raises(PeriodosError) as exc:
            ciclo.crear(rec, {"anio": 2027, "semestre": 1})
    finally:
        entorno.B12C.CHECKPOINT_HOOKS.remove(falla)
    assert exc.value.status == 503 and "fallo inyectado" not in exc.value.message
    assert CS.estado(db_conn) == antes and CS.audit_rows(db_conn) == []
    assert [(e.operation, e.outcome) for e in audit_store.events] == [("crear_periodo", "FAILED")]


def test_lock_concurrente(db_conn, ciclo, service, repo, audit_store, lock_conn):
    """Otra operacion de estado de periodos (B12I/B12C, misma clave) en curso: espera acotada -> 409 sin escribir."""
    from periodos.service import PeriodosError
    ciclo.lock_timeout = "300ms"
    lock_conn.execute("SELECT pg_advisory_lock(hashtext(%s))", ["deptit_crear_periodo:1:1"])
    try:
        CS.baseline(db_conn)
        antes = CS.estado(db_conn)
        with pytest.raises(PeriodosError) as exc:
            ciclo.crear(_rec(service, repo), {"anio": 2027, "semestre": 1})
        assert exc.value.status == 409 and exc.value.code == "LOCK"
        assert CS.estado(db_conn) == antes
        assert [(e.operation, e.outcome, e.error_code) for e in audit_store.events] == [
            ("crear_periodo", "FAILED", "ConsistencyLockError")]
    finally:
        lock_conn.execute("SELECT pg_advisory_unlock(hashtext(%s))", ["deptit_crear_periodo:1:1"])


def test_permisos_y_ambito(db_conn, ciclo, service, repo, audit_store):
    """B10 ``periodos.write``: solo lectura -> DENIED; coordinador sin departamento -> 409 de ambito; superadmin con
    contexto crea en el departamento elegido (los ids del cliente se ignoran)."""
    from periodos.service import PeriodosError
    with pytest.raises(PeriodosError) as exc:
        ciclo.crear(_rec(service, repo, 7), {"anio": 2027, "semestre": 1})
    assert exc.value.status == 403 and "periodos.write" in exc.value.message
    assert [(e.operation, e.outcome) for e in audit_store.events] == [("crear_periodo", "DENIED")]
    with pytest.raises(PeriodosError) as exc:
        ciclo.crear(_rec(service, repo, 2), {"anio": 2027, "semestre": 1})
    assert exc.value.status == 409
    sup = _rec(service, repo, 1, dep=2)
    with db_conn.transaction() as tx:
        r = ciclo.crear(sup, {"anio": 2027, "semestre": 1, "institucion_id": 1, "departamento_id": 1})
        assert db_conn.execute("SELECT departamento_id FROM periodos WHERE id=%s", [r["periodo_id"]]).fetchone()[0] == 2
        raise psycopg.Rollback(tx)


def test_p01b_contexto_historico_inmediato(db_conn, ciclo, service, repo):
    """P-01b: inmediatamente despues de crear un periodo MAS ANTIGUO (queda abierto y es historico) la lectura del aviso
    global E4-01 ya lo refleja, sin otra accion (el frontend la pide al recibir ``periodo_cambiado``)."""
    from integraciones.contexto_periodo import ContextoPeriodoService
    rec = _rec(service, repo)
    contexto = ContextoPeriodoService(None, service, transaction=lambda: savepoint(db_conn))
    assert contexto.aviso(rec)["aviso"] is None
    with db_conn.transaction() as tx:
        r = ciclo.crear(rec, {"anio": 2025, "semestre": 2})
        assert r["periodo_cambiado"] is True
        aviso = contexto.aviso(rec)["aviso"]
        assert aviso is not None and "2025-2" in aviso["texto"]
        raise psycopg.Rollback(tx)
    assert contexto.aviso(rec)["aviso"] is None


# ------------------------------------------------------------------------------------------ HTTP, literalidad, arquitectura
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
    rutas = ["/periodos/crear/contexto", "/periodos/crear", "/periodos/revertir/diagnostico", "/periodos/revertir",
             "/periodos/eliminar/diagnostico", "/periodos/eliminar"]
    for r in rutas:
        assert c.post(r, headers=h, json={}).status_code == 401
    c.cookies.set("deptit_session", session_for(service, repo, 3)[1])
    for r in rutas:
        assert c.post(r, json={}).status_code == 403
    assert c.post(rutas[0], headers=h, json={"anio": 2027, "semestre": 1}).json()["objetivo"]["nombre"] == "2027-1"
    r = c.post(rutas[1], headers=h, json={"anio": 2026, "semestre": 2})
    assert r.status_code == 409 and "ya está registrado" in r.json()["error"]["message"]
    assert not re.search(r"(?i)traceback|select\s|psycopg|C:\\\\", r.text)


def test_motor_literal():
    """El motor vendorizado es texto LITERAL del entry certificado, bloque por bloque; B12C y B11 copias exactas."""
    from integraciones.ciclo_periodos.motor import metadata
    from periodos_support import ENTRY
    src = ENTRY.read_text(encoding="utf-8")
    assert hashlib.sha256(src.encode("utf-8")).hexdigest() == metadata.ENTRY_SHA256
    tree = ast.parse(src)
    por_linea = {n.lineno: n for n in tree.body}
    texto = (BACKEND / "integraciones" / "ciclo_periodos" / "motor" / "complemento.py").read_text(encoding="utf-8")
    bloques = re.findall(r"# --- entry l\. (\d+)(?:-(\d+))?\n(.*?)(?=\n# --- entry|\Z)", texto, re.S)
    assert len(bloques) == metadata.BLOQUES
    for ini, _fin, cuerpo in bloques:
        original = "\n".join(l for l in ast.get_source_segment(src, por_linea[int(ini)]).splitlines()
                             if not l.lstrip().startswith("@"))
        original = re.sub(r"\bdeptit_refactor\.integration\.", "integraciones.ciclo_periodos.motor.pilotos_no_portados.",
                          original)
        original = re.sub(r"\bdeptit_refactor\.", "", original)
        cuerpo = re.sub(r"\b(analisis\.motor\.ref|integraciones\.ciclo_periodos\.motor\.ref)\.", "", cuerpo)
        assert cuerpo.strip() == original.strip(), ini
    ref = Path(r"C:\DEPTIT_NEXT\reference_fix02\deptit_refactor")
    b12c = (BACKEND / "integraciones/ciclo_periodos/motor/ref/b12c/periodo_atomico.py").read_text(encoding="utf-8")
    assert b12c == (ref / "b12c/periodo_atomico.py").read_text(encoding="utf-8")
    for nombre in ("backup_gate.py", "backup_manifest.py", "db_identity.py"):
        assert (BACKEND / "integraciones/ciclo_periodos/ref_b11" / nombre).read_bytes() == \
            (ref / "operations" / nombre).read_bytes()


def test_arquitectura():
    for owner in ("periodos", "designaciones", "docentes", "investigacion", "extension", "comisiones"):
        for archivo in (BACKEND / owner).glob("*.py"):
            assert not re.search(r"(?m)^\s*(from|import) integraciones", archivo.read_text(encoding="utf-8")), archivo
