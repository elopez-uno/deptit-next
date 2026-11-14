"""Reglas, permisos, multitenant y auditoria de Periodos contra deptit_next_dev REAL, siempre con ROLLBACK.

Usuarios/instituciones/departamentos de la sesion: FakeRepo (contrasenas aleatorias, sin credenciales humanas).
Periodos/movimientos/b12h_audit_log: base real, en la transaccion del test (nunca se confirma).
"""

import json
import re

import psycopg
import pytest

import audit
from auth import policy
from periodos import repository as period_repo
from periodos.service import PeriodosError
from periodos_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_after, audit_store, db_conn, lock_conn, make_service, movements_after, periodos, savepoint,
    session_for, snapshot,
)

OPEN_COMMITS = [  # B12H certificado: un SUCCESS por COMMIT del writer externo, en esa misma transaccion
    {"commit_seq": 1, "committing_writer": "abrir_periodo_emergencia", "entity_param": "periodo_id",
     "mutating_statements": 2},
    {"commit_seq": 2, "committing_writer": "registrar_movimiento", "entity_param": "periodo_id",
     "mutating_statements": 1},
]
RETURN_COMMITS = [
    {"commit_seq": 1, "committing_writer": "volver_periodo_actual", "mutating_statements": 2},
    {"commit_seq": 2, "committing_writer": "registrar_movimiento", "mutating_statements": 1},
]

INST = 1


def state(conn, dep):
    snap = snapshot(conn, INST, dep)
    opened = [p for p in snap["periodos"] if p["estado"] == "Abierto"]
    closed = [p for p in snap["periodos"] if p["estado"] != "Abierto"]
    return snap, opened, closed


def other_tables(conn, dep):
    """Conteos de las tablas de otros modulos que referencian periodos: Periodos no debe tocarlas."""
    tables = ["designaciones", "comisiones", "disposiciones", "investigacion_docente", "extension_docente",
              "actividades_especiales", "actividad_especial_docente", "estado_consulta_designacion",
              "prestamos_docentes", "correcciones_historial_horas"]
    out = {}
    with conn.cursor() as cur:
        for t in tables:
            cur.execute(f"SELECT count(*), coalesce(sum(hashtext(t::text)::bigint), 0) FROM {t} t "
                        "WHERE institucion_id = %s AND departamento_id = %s", [INST, dep])
            out[t] = cur.fetchone()
    return out


# ------------------------------------------------------------------------------------------------ lectura
def test_baseline_one_open_period_per_department(db_conn):
    for dep in (1, 2, 3, 4, 9, 11):
        _, opened, _ = state(db_conn, dep)
        assert len(opened) == 1, dep


def test_overview_department_user_reads_own_department(periodos, service, repo, db_conn):
    record, _ = session_for(service, repo, 3)
    data = periodos.overview(record)
    snap, opened, _ = state(db_conn, 1)
    assert data["contexto"]["institucion"]["id"] == 1 and data["contexto"]["departamento"]["id"] == 1
    assert [p["id"] for p in data["periodos"]] == [p["id"] for p in sorted(
        snap["periodos"], key=lambda p: (-p["anio"], -p["semestre"], -p["id"]))]
    assert data["abierto"]["id"] == opened[0]["id"]
    assert data["actual"]["id"] == data["periodos"][0]["id"]
    assert data["permisos"] == {"puede_escribir": True, "es_superadmin": False}
    assert set(data["periodos"][0]) == {"id", "nombre", "anio", "semestre", "fecha_inicio", "fecha_fin", "estado",
                                        "observaciones"}


def test_overview_solo_lectura_sees_data_without_write(periodos, service, repo):
    record, _ = session_for(service, repo, 7)
    data = periodos.overview(record)
    assert data["periodos"] and data["permisos"]["puede_escribir"] is False


def test_overview_coordinator_requires_department_then_sees_it(periodos, service, repo, db_conn):
    record, _ = session_for(service, repo, 2)
    with pytest.raises(PeriodosError) as exc:
        periodos.overview(record)
    assert exc.value.status == 409 and exc.value.code == "SCOPE_INSTITUTIONAL"
    service.set_context(record, None, 2, False)
    data = periodos.overview(record)
    assert data["contexto"]["departamento"]["id"] == 2
    assert {p["id"] for p in data["periodos"]} == {p["id"] for p in snapshot(db_conn, INST, 2)["periodos"]}
    assert data["permisos"]["puede_escribir"] is False  # B10: el coordinador no escribe periodos


def test_overview_superadmin_default_and_selected_context(periodos, service, repo, db_conn):
    record, _ = session_for(service, repo, 1)
    data = periodos.overview(record)  # contexto certificado por defecto: primera institucion/departamento por nombre
    assert data["contexto"]["institucion"]["id"] == 2 and data["periodos"] == [] and data["abierto"] is None
    service.set_context(record, 1, 9, False)
    data = periodos.overview(record)
    assert data["contexto"]["departamento"]["id"] == 9 and data["permisos"]["es_superadmin"] is True
    assert {p["id"] for p in data["periodos"]} == {p["id"] for p in snapshot(db_conn, INST, 9)["periodos"]}


def test_superadmin_institution_without_departments_is_institutional_view(periodos, service, repo):
    record, _ = session_for(service, repo, 1)
    service.set_context(record, 5, None, False)
    with pytest.raises(PeriodosError) as exc:
        periodos.overview(record)
    assert exc.value.code == "SCOPE_INSTITUTIONAL"


@pytest.mark.parametrize("dep", [5, 999, "x", 0])
def test_invalid_or_foreign_context_is_rejected_not_replaced(periodos, service, repo, dep):
    record, _ = session_for(service, repo, 3)
    record.scope[policy.DEPARTMENT_SCOPE_KEY] = dep  # manipulacion del contexto de la sesion
    with pytest.raises(PeriodosError) as exc:
        periodos.overview(record)
    assert exc.value.status == 409 and exc.value.code == "SCOPE_NOT_VERIFIED"
    assert "Ámbito no verificado" in exc.value.message


# ------------------------------------------------------------------------------------------------ abrir anterior
def test_open_previous_switches_state_registers_movement_and_audit(periodos, service, repo, db_conn, audit_store):
    record, _ = session_for(service, repo, 3)
    before, opened, closed = state(db_conn, 1)
    others = other_tables(db_conn, 1)
    target, current = closed[0], opened[0]
    out = periodos.open_previous(record, target["id"], "corrección puntual", True, True)
    assert out["cambio"] is True and out["periodo"]["id"] == target["id"]
    assert out["mensaje"] == (f"Período {target['nombre']} abierto excepcionalmente. "
                              "Revisá bien antes de modificar datos.")
    after, opened_after, _ = state(db_conn, 1)
    assert [p["id"] for p in opened_after] == [target["id"]]
    assert {p["id"]: {k: v for k, v in p.items() if k != "estado"} for p in after["periodos"]} == \
        {p["id"]: {k: v for k, v in p.items() if k != "estado"} for p in before["periodos"]}
    movs = movements_after(db_conn, before["max_mov_id"])
    assert movs == [{
        "periodo_id": target["id"], "fecha": FIXED_TODAY.isoformat(), "tipo_movimiento": "Apertura excepcional de período",
        "cuil": "", "nombre": "",
        "detalle": (f"Se cerró excepcionalmente el período {current['nombre']} y se abrió el período anterior "
                    f"{target['nombre']} ({target['fecha_inicio']} al {target['fecha_fin']}) para realizar "
                    "correcciones puntuales."),
        "observaciones": "corrección puntual", "horas_variacion": 0, "institucion_id": 1, "departamento_id": 1}]
    assert other_tables(db_conn, 1) == others
    rows = audit_after(db_conn)
    assert len(rows) == 2 and audit_store.events == []
    assert [r["metadata"] for r in rows] == OPEN_COMMITS
    assert [r["event_seq"] for r in rows] == [1, 2] and len({r["correlation_id"] for r in rows}) == 1
    assert len({r["session_ref"] for r in rows}) == 1
    row = rows[0]
    assert {k: rows[1][k] for k in ("operation", "action", "entity_type", "entity_id", "outcome", "audit_mode")} ==         {k: row[k] for k in ("operation", "action", "entity_type", "entity_id", "outcome", "audit_mode")}
    assert {k: row[k] for k in ("subsystem", "app_batch", "event_version", "event_seq", "actor_kind", "actor_source",
                                "actor_user_id", "actor_email_normalized", "actor_role", "actor_is_superadmin",
                                "actor_home_institucion_id", "actor_home_departamento_id", "institucion_id",
                                "departamento_id", "scope_source", "operation", "action", "action_scope",
                                "entity_type", "entity_id", "outcome", "audit_mode", "error_code")} == {
        "subsystem": "B12H", "app_batch": "B12H", "event_version": 1, "event_seq": 1, "actor_kind": "USER",
        "actor_source": "B12G_REVALIDATED_DB", "actor_user_id": 3, "actor_email_normalized": "info@test.local",
        "actor_role": "usuario_departamento", "actor_is_superadmin": False, "actor_home_institucion_id": 1,
        "actor_home_departamento_id": 1, "institucion_id": 1, "departamento_id": 1, "scope_source": "ACTOR_HOME",
        "operation": "_abrir_periodo_emergencia_control_v300", "action": "periodos.write",
        "action_scope": "department", "entity_type": "periodo", "entity_id": str(target["id"]),
        "outcome": "SUCCESS", "audit_mode": "IN_TRANSACTION", "error_code": None}
    assert re.fullmatch(r"[0-9a-f]{32}", row["session_ref"])


def test_open_previous_already_open_is_noop_with_post_operation_event(periodos, service, repo, db_conn, audit_store):
    record, _ = session_for(service, repo, 3)
    before, opened, _ = state(db_conn, 1)
    out = periodos.open_previous(record, opened[0]["id"], "", True, True)
    assert out["cambio"] is False
    assert snapshot(db_conn, INST, 1) == before and audit_after(db_conn) == []
    [event] = audit_store.events
    assert (event.outcome, event.audit_mode, event.metadata) == (
        "SUCCESS", "POST_OPERATION", {"coupled_commits": 0, "entity_param": "periodo_id",
                                      "post_reason": "NO_POOLED_COMMIT"})


def test_open_previous_without_open_period_uses_certified_detail(periodos, service, repo, db_conn):
    record, _ = session_for(service, repo, 3)
    db_conn.execute("UPDATE periodos SET estado = 'Cerrado' WHERE institucion_id = 1 AND departamento_id = 1")
    before, _, closed = state(db_conn, 1)
    target = closed[-1]
    periodos.open_previous(record, target["id"], "", True, True)
    [mov] = movements_after(db_conn, before["max_mov_id"])
    assert mov["detalle"] == (f"Se abrió excepcionalmente el período {target['nombre']} ({target['fecha_inicio']} "
                              f"al {target['fecha_fin']}) para realizar correcciones puntuales.")


@pytest.mark.parametrize("flags", [(False, False), (True, False), (False, True)])
def test_open_previous_requires_both_confirmations(periodos, service, repo, db_conn, audit_store, flags):
    record, _ = session_for(service, repo, 3)
    before, _, closed = state(db_conn, 1)
    with pytest.raises(PeriodosError) as exc:
        periodos.open_previous(record, closed[0]["id"], "", *flags)
    assert exc.value.status == 422
    assert exc.value.message == "Tenés que marcar ambas confirmaciones antes de abrir un período anterior."
    assert snapshot(db_conn, INST, 1) == before and audit_store.events == [] and audit_after(db_conn) == []


@pytest.mark.parametrize("raw", ["abc", None, True, 1.5, ""])
def test_open_previous_invalid_id(periodos, service, repo, db_conn, audit_store, raw):
    record, _ = session_for(service, repo, 3)
    before = snapshot(db_conn, INST, 1)
    with pytest.raises(PeriodosError) as exc:
        periodos.open_previous(record, raw, "", True, True)
    assert exc.value.status == 422
    assert exc.value.message == "No se pudo abrir el período seleccionado: El período seleccionado no es válido."
    assert snapshot(db_conn, INST, 1) == before and audit_after(db_conn) == []
    [event] = audit_store.events
    assert (event.outcome, event.error_code, event.audit_mode) == ("FAILED", "ValueError", "SEPARATE_TRANSACTION")


def test_tenant_manipulation_cannot_open_period_of_other_department(periodos, service, repo, db_conn, audit_store):
    record, _ = session_for(service, repo, 3)  # usuario del departamento 1
    foreign = state(db_conn, 2)[2][0]  # periodo cerrado del departamento 2
    before1, before2 = snapshot(db_conn, INST, 1), snapshot(db_conn, INST, 2)
    with pytest.raises(PeriodosError) as exc:
        periodos.open_previous(record, foreign["id"], "", True, True)
    assert exc.value.status == 404
    assert exc.value.message == "No se pudo abrir el período seleccionado: No se encontró el período seleccionado."
    assert snapshot(db_conn, INST, 1) == before1 and snapshot(db_conn, INST, 2) == before2
    [event] = audit_store.events
    assert event.outcome == "FAILED" and event.entity_id == str(foreign["id"]) and event.actor.department_id == 1


@pytest.mark.parametrize("user_id, code", [(2, policy.DENY_ROLE_NOT_PERMITTED), (7, policy.DENY_READ_ONLY_ROLE)])
def test_roles_without_write_permission_are_denied(periodos, service, repo, db_conn, audit_store, user_id, code):
    record, _ = session_for(service, repo, user_id, **{policy.DEPARTMENT_SCOPE_KEY: 1})
    before, _, closed = state(db_conn, 1)
    with pytest.raises(PeriodosError) as exc:
        periodos.open_previous(record, closed[0]["id"], "", True, True)
    assert exc.value.status == 403 and exc.value.code == "DENIED"
    assert exc.value.message.startswith("⛔ ") and "(permiso requerido: periodos.write)" in exc.value.message
    assert snapshot(db_conn, INST, 1) == before and audit_after(db_conn) == []
    [event] = audit_store.events
    assert (event.outcome, event.error_code, event.metadata["b10_decision"]) == ("DENIED", code, code)
    with pytest.raises(PeriodosError) as exc:
        periodos.return_current(record, "", True, True)
    assert exc.value.status in (403, 409)


def test_commercial_read_only_is_denied(periodos, service, repo, db_conn, audit_store):
    repo.institutions_rows[0]["estado"] = "Solo lectura"
    record, _ = session_for(service, repo, 3)
    assert record.user["rol"] == "solo_lectura" and record.user["modo_solo_lectura_comercial"] is True
    assert periodos.overview(record)["permisos"]["puede_escribir"] is False
    with pytest.raises(PeriodosError) as exc:
        periodos.open_previous(record, state(db_conn, 1)[2][0]["id"], "", True, True)
    assert exc.value.status == 403
    assert audit_store.events[0].error_code == policy.DENY_COMMERCIAL_READ_ONLY


def test_superadmin_writes_only_in_selected_department(periodos, service, repo, db_conn):
    record, _ = session_for(service, repo, 1)
    service.set_context(record, 1, 2, False)
    before1 = snapshot(db_conn, INST, 1)
    _, _, closed2 = state(db_conn, 2)
    periodos.open_previous(record, closed2[0]["id"], "", True, True)
    assert [p["id"] for p in state(db_conn, 2)[1]] == [closed2[0]["id"]]
    assert snapshot(db_conn, INST, 1)["periodos"] == before1["periodos"]
    rows = audit_after(db_conn)
    assert [(r["actor_is_superadmin"], r["scope_source"], r["departamento_id"]) for r in rows] ==         [(True, "SUPERADMIN_SELECTED", 2)] * 2


def test_denied_event_failure_keeps_denial(periodos, service, repo, db_conn, audit_store):
    audit_store.fail = True
    record, _ = session_for(service, repo, 7)
    with pytest.raises(PeriodosError) as exc:
        periodos.open_previous(record, state(db_conn, 1)[2][0]["id"], "", True, True)
    assert exc.value.status == 403


# ------------------------------------------------------------------------------------------------ volver al actual
def _open_previous_directly(conn, dep):
    _, opened, closed = state(conn, dep)
    conn.execute("UPDATE periodos SET estado = 'Cerrado' WHERE id = %s", [opened[0]["id"]])
    conn.execute("UPDATE periodos SET estado = 'Abierto' WHERE id = %s", [closed[0]["id"]])
    return opened[0], closed[0]


def test_return_current_after_exceptional_opening(periodos, service, repo, db_conn):
    record, _ = session_for(service, repo, 3)
    current, previous = _open_previous_directly(db_conn, 1)
    before = snapshot(db_conn, INST, 1)
    out = periodos.return_current(record, "fin de corrección", True, True)
    assert out == {"mensaje": "Se volvió al período actual correctamente.", "periodo": out["periodo"], "cambio": True}
    assert out["periodo"]["id"] == current["id"]
    assert [p["id"] for p in state(db_conn, 1)[1]] == [current["id"]]
    [mov] = movements_after(db_conn, before["max_mov_id"])
    assert (mov["tipo_movimiento"], mov["periodo_id"], mov["observaciones"]) == (
        "Retorno al período actual", current["id"], "fin de corrección")
    assert mov["detalle"] == (f"Se cerró el período abierto {previous['nombre']} y se volvió al período actual "
                              f"{current['nombre']} ({current['fecha_inicio']} al {current['fecha_fin']}).")
    rows = audit_after(db_conn)
    assert [(r["operation"], r["entity_id"], r["event_seq"], r["metadata"]) for r in rows] == [
        ("_volver_periodo_actual_control_v300", None, i + 1, m) for i, m in enumerate(RETURN_COMMITS)]


def test_return_current_without_open_period_single_confirmation(periodos, service, repo, db_conn):
    record, _ = session_for(service, repo, 3)
    db_conn.execute("UPDATE periodos SET estado = 'Cerrado' WHERE institucion_id = 1 AND departamento_id = 1")
    before = snapshot(db_conn, INST, 1)
    with pytest.raises(PeriodosError) as exc:
        periodos.return_current(record, "", False, False)
    assert exc.value.message == "Tenés que confirmar la acción antes de continuar."
    out = periodos.return_current(record, "", False, True)
    assert out["mensaje"] == "Se abrió el período actual correctamente."
    last = max(before["periodos"], key=lambda p: (p["anio"], p["semestre"], p["id"]))
    [mov] = movements_after(db_conn, before["max_mov_id"])
    assert mov["detalle"] == (f"Se volvió al período actual {last['nombre']} "
                              f"({last['fecha_inicio']} al {last['fecha_fin']}).")
    assert [(r["operation"], r["metadata"]) for r in audit_after(db_conn)] == [
        ("volver_periodo_actual", m) for m in RETURN_COMMITS]


def test_return_current_when_already_current_is_rejected(periodos, service, repo, db_conn, audit_store):
    record, _ = session_for(service, repo, 3)
    before, opened, _ = state(db_conn, 1)
    with pytest.raises(PeriodosError) as exc:
        periodos.return_current(record, "", True, True)
    assert exc.value.status == 409 and exc.value.code == "ALREADY_CURRENT"
    assert exc.value.message == (f"Ya estás trabajando sobre el período actual: {opened[0]['nombre']} "
                                 f"({opened[0]['fecha_inicio']} al {opened[0]['fecha_fin']}).")
    assert snapshot(db_conn, INST, 1) == before and audit_store.events == []


@pytest.mark.parametrize("flags", [(False, True), (True, False), (False, False)])
def test_return_current_requires_both_confirmations(periodos, service, repo, db_conn, flags):
    record, _ = session_for(service, repo, 3)
    _open_previous_directly(db_conn, 1)
    before = snapshot(db_conn, INST, 1)
    with pytest.raises(PeriodosError) as exc:
        periodos.return_current(record, "", *flags)
    assert exc.value.message == "Tenés que marcar ambas confirmaciones antes de volver al período actual."
    assert snapshot(db_conn, INST, 1) == before


def test_return_current_no_periods(periodos, service, repo):
    record, _ = session_for(service, repo, 1)  # superadmin en UBA / dep 8: sin periodos
    with pytest.raises(PeriodosError) as exc:
        periodos.return_current(record, "", True, True)
    assert (exc.value.status, exc.value.message) == (409, "Todavía no hay períodos registrados.")


def test_stale_screen_state_writes_nothing(service, repo, db_conn, lock_conn, audit_store):
    """B12I: entre la lectura de la pantalla y la escritura otro proceso cambio el abierto -> 0 escrituras."""
    from periodos_support import EXTRA_DEPARTMENTS

    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    calls = {"n": 0}
    current, previous = _open_previous_directly(db_conn, 1)

    def transaction():
        calls["n"] += 1
        if calls["n"] == 2:  # tras la lectura de la pantalla y el lock: "otra sesion" vuelve al actual
            db_conn.execute("UPDATE periodos SET estado = 'Cerrado' WHERE id = %s", [previous["id"]])
            db_conn.execute("UPDATE periodos SET estado = 'Abierto' WHERE id = %s", [current["id"]])
        return savepoint(db_conn)

    svc = make_service(service, audit_store, db_conn, lock_conn, transaction=transaction)
    record, _ = session_for(service, repo, 3)
    with pytest.raises(PeriodosError) as exc:
        svc.return_current(record, "", True, True)
    assert exc.value.code == "STALE" and "cambiaron en otra sesión" in exc.value.message
    assert exc.value.message.endswith("[B12I: get_periodo_abierto, get_periodos, get_ultimo_periodo]")
    before = snapshot(db_conn, INST, 1)
    assert movements_after(db_conn, before["max_mov_id"]) == [] and audit_after(db_conn) == []
    assert audit_store.events[-1].error_code == "StaleDecisionError"


# ------------------------------------------------------------------------------------------------ COMMITs / B12I
def _probe_conn():
    import db

    conn = psycopg.connect(db.load_settings()["database_url"], autocommit=True)
    db.verify_identity(conn)
    return conn


def _lock_free(conn, key="deptit_crear_periodo:1:1"):
    # xact lock en autocommit: se toma y se libera en la misma sentencia (no deja nada tomado).
    return conn.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s))", [key]).fetchone()[0]


def test_first_commit_audit_failure_rolls_back_everything(periodos, service, repo, db_conn, audit_store,
                                                          monkeypatch):
    record, _ = session_for(service, repo, 3)
    before, _, closed = state(db_conn, 1)

    def broken(conn, event):
        raise psycopg.errors.InsufficientPrivilege("simulado")

    monkeypatch.setattr(audit, "insert_on", broken)
    with pytest.raises(PeriodosError) as exc:
        periodos.open_previous(record, closed[0]["id"], "", True, True)
    assert exc.value.status == 503
    assert exc.value.message == ("No se pudo abrir el período seleccionado: " + audit.MSG_PERSIST
                                 + " [AUDIT_INSERT_FAILED]")
    assert snapshot(db_conn, INST, 1) == before
    [event] = audit_store.events
    assert (event.error_code, event.metadata["coupled_commits"]) == ("AuditPersistenceError:AUDIT_INSERT_FAILED", 0)


def test_second_commit_failure_keeps_first_commit_like_certified(periodos, service, repo, db_conn, audit_store,
                                                                 monkeypatch):
    """Certificado: el cambio de estado ya confirmado (COMMIT 1) no se deshace si falla el movimiento (COMMIT 2)."""
    record, _ = session_for(service, repo, 3)
    before, _, closed = state(db_conn, 1)
    real, calls = audit.insert_on, {"n": 0}

    def second_fails(conn, event):
        calls["n"] += 1
        if calls["n"] == 2:
            raise psycopg.errors.InsufficientPrivilege("simulado")
        real(conn, event)

    monkeypatch.setattr(audit, "insert_on", second_fails)
    with pytest.raises(PeriodosError) as exc:
        periodos.open_previous(record, closed[0]["id"], "", True, True)
    assert exc.value.status == 503
    assert [p["id"] for p in state(db_conn, 1)[1]] == [closed[0]["id"]]
    assert movements_after(db_conn, before["max_mov_id"]) == []
    assert [r["metadata"] for r in audit_after(db_conn)] == OPEN_COMMITS[:1]
    [event] = audit_store.events
    assert (event.outcome, event.event_seq, event.error_code, event.metadata) == (
        "FAILED", 3, "AuditPersistenceError:AUDIT_INSERT_FAILED",  # seq 2 consumido por el SUCCESS fallido (B12H)
        {"coupled_commits": 1, "entity_param": "periodo_id"})


def test_database_error_in_movement_keeps_state_change_like_certified(periodos, service, repo, db_conn,
                                                                      audit_store, monkeypatch):
    record, _ = session_for(service, repo, 3)
    current, previous = _open_previous_directly(db_conn, 1)
    before = snapshot(db_conn, INST, 1)

    def broken(self, **kwargs):
        self._conn.execute("SELECT 1/0")

    monkeypatch.setattr(period_repo.PeriodosRepository, "insert_movement", broken)
    with pytest.raises(PeriodosError) as exc:
        periodos.return_current(record, "", True, True)
    assert exc.value.status == 503 and exc.value.code == "DB_ERROR"
    assert exc.value.message.startswith("No se pudo volver al período actual: ")
    assert [p["id"] for p in state(db_conn, 1)[1]] == [current["id"]]
    assert movements_after(db_conn, before["max_mov_id"]) == []
    assert [r["metadata"] for r in audit_after(db_conn)] == RETURN_COMMITS[:1]
    assert (audit_store.events[-1].error_code, audit_store.events[-1].metadata) == (
        "DivisionByZero", {"coupled_commits": 1})


def test_database_error_in_first_commit_changes_nothing(periodos, service, repo, db_conn, audit_store,
                                                        monkeypatch):
    record, _ = session_for(service, repo, 3)
    before, _, closed = state(db_conn, 1)

    def broken(self, period_id):
        self._conn.execute("SELECT 1/0")

    monkeypatch.setattr(period_repo.PeriodosRepository, "close_open_except", broken)
    with pytest.raises(PeriodosError) as exc:
        periodos.open_previous(record, closed[0]["id"], "", True, True)
    assert exc.value.code == "DB_ERROR" and "la transacción se revirtió completa" in exc.value.message
    assert snapshot(db_conn, INST, 1) == before and audit_after(db_conn) == []
    assert audit_store.events[-1].metadata == {"coupled_commits": 0, "entity_param": "periodo_id"}


def test_session_lock_held_across_both_commits_and_released(periodos, service, repo, db_conn, monkeypatch):
    record, _ = session_for(service, repo, 3)
    probe = _probe_conn()
    seen = []
    real_close, real_insert = period_repo.PeriodosRepository.close_open_except, \
        period_repo.PeriodosRepository.insert_movement

    def close_spy(self, period_id):
        seen.append(("commit1", _lock_free(probe), _lock_free(probe, "deptit_crear_periodo:1:2")))
        return real_close(self, period_id)

    def insert_spy(self, **kwargs):
        seen.append(("commit2", _lock_free(probe), _lock_free(probe, "deptit_crear_periodo:1:2")))
        return real_insert(self, **kwargs)

    monkeypatch.setattr(period_repo.PeriodosRepository, "close_open_except", close_spy)
    monkeypatch.setattr(period_repo.PeriodosRepository, "insert_movement", insert_spy)
    try:
        periodos.open_previous(record, state(db_conn, 1)[2][0]["id"], "", True, True)
        assert seen == [("commit1", False, True), ("commit2", False, True)]
        assert _lock_free(probe) is True  # liberado al terminar el writer (pg_advisory_unlock)
    finally:
        probe.close()


def test_lock_timeout_is_controlled_and_writes_nothing(service, repo, db_conn, lock_conn, audit_store):
    from periodos_support import EXTRA_DEPARTMENTS

    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    svc = make_service(service, audit_store, db_conn, lock_conn, lock_wait_seconds=0.3)
    record, _ = session_for(service, repo, 3)
    before, _, closed = state(db_conn, 1)
    holder = _probe_conn()
    try:
        holder.execute("SELECT pg_advisory_lock(hashtext('deptit_crear_periodo:1:1'))")
        with pytest.raises(PeriodosError) as exc:
            svc.open_previous(record, closed[0]["id"], "", True, True)
    finally:
        holder.execute("SELECT pg_advisory_unlock(hashtext('deptit_crear_periodo:1:1'))")
        holder.close()
    assert exc.value.status == 409 and exc.value.code == "LOCK"
    assert exc.value.message == ("No se pudo abrir el período seleccionado: Hay otra operación concurrente sobre los "
                                 "mismos datos. No se guardó nada: reintentá en unos instantes. "
                                 "[B12I: periodo_estado]")
    assert snapshot(db_conn, INST, 1) == before and audit_after(db_conn) == []
    assert (audit_store.events[-1].error_code, audit_store.events[-1].metadata["coupled_commits"]) == (
        "ConsistencyLockError", 0)


def test_long_observaciones_are_stored_unchanged(periodos, service, repo, db_conn):
    """Sin limite de longitud (como el certificado): ``observaciones`` es ``text`` en el esquema."""
    record, _ = session_for(service, repo, 3)
    before, _, closed = state(db_conn, 1)
    texto = ("Corrección ñ áéíóú 🙂 " * 4000)[:60_000]
    periodos.open_previous(record, closed[0]["id"], texto, True, True)
    [mov] = movements_after(db_conn, before["max_mov_id"])
    assert mov["observaciones"] == texto and len(mov["observaciones"]) == 60_000


def test_audit_metadata_policy_rejects_unknown_keys():
    with pytest.raises(audit.AuditError):
        audit.check_metadata({"observaciones": "texto libre"})
    assert json.loads(json.dumps(audit.check_metadata({"commit_seq": 1, "entity_param": None}))) == {"commit_seq": 1}
