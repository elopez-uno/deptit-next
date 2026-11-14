"""Equivalencia de Periodos con el codigo CERTIFICADO de reference_fix02 (solo lectura: sin bytecode, sin escrituras).

- SQL de lectura: el SQL literal del entry pasado por el inyector de scope certificado vs el repositorio de NEXT, para
  TODOS los departamentos reales de deptit_next_dev.
- Escrituras: ``abrir_periodo_emergencia`` / ``volver_periodo_actual`` / ``registrar_movimiento`` del entry, ejecutados
  sin cambios sobre la base real dentro de un SAVEPOINT revertido, contra NEXT sobre el mismo estado inicial.
- Textos (B10, B12B, B12D, B12H, B12I, UI), claves de bloqueo y contrato de auditoria B12H.
"""

import inspect

import psycopg
import pytest

import audit
from auth import policy
from auth.service import ScopeResolution
from periodos import repository as period_repo
from periodos import service as period_service
from periodos.repository import PeriodosRepository
from periodos.service import PeriodosError
from periodos_support import (  # noqa: F401  (fixtures)
    ENTRY, READONLY_QUERIES, audit_after, audit_store, certified_injector, certified_period_writers, db_conn,
    lock_conn, movements_after, periodos, savepoint, session_for, snapshot, sql_constants,
)

from deptit_refactor.b12b import scope_fail_closed as ref_scope  # noqa: E402
from deptit_refactor.b12d import db_failure_integrity as ref_b12d  # noqa: E402
from deptit_refactor.b12h import audit_actor as ref_audit  # noqa: E402
from deptit_refactor.b12i import cache_decision_integrity as ref_b12i  # noqa: E402
from deptit_refactor.security import authorization as ref_authz  # noqa: E402
from deptit_refactor.security import legacy_write_actions as ref_registry  # noqa: E402
from deptit_refactor.security import ui_messages as ref_ui  # noqa: E402

ENTRY_TEXT = ENTRY.read_text(encoding="utf-8")


def departments(conn):
    return conn.execute("SELECT institucion_id, id FROM departamentos ORDER BY institucion_id, id").fetchall()


def certified_rows(conn, sql, inst, dep, params=()):
    inj = certified_injector()
    q, extra = inj["_pg_scope_select_template_v193"](sql, "tenant", inst, dep)
    with conn.cursor() as cur:
        cur.execute(q, list(params) + list(extra))
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


# ------------------------------------------------------------------------------------------------ lecturas
def test_read_sql_equivalent_for_every_real_department(db_conn):
    listado = sql_constants(ENTRY, "get_periodos", 0)[0]
    abierto = sql_constants(ENTRY, "get_periodo_abierto")[0]
    ultimo = sql_constants(READONLY_QUERIES, "get_ultimo_periodo")[0]
    por_id = sql_constants(ENTRY, "abrir_periodo_emergencia")[2]
    deps = departments(db_conn)
    assert len(deps) >= 10
    for inst, dep in deps:
        repo = PeriodosRepository(db_conn, inst, dep)
        assert repo.list() == certified_rows(db_conn, listado, inst, dep), (inst, dep)
        cert_open = certified_rows(db_conn, abierto, inst, dep)
        assert repo.open_period() == (cert_open[0] if cert_open else None)
        cert_last = certified_rows(db_conn, ultimo, inst, dep)
        assert repo.last_period() == (cert_last[0] if cert_last else None)
        for row in certified_rows(db_conn, listado, 1, 1) + certified_rows(db_conn, listado, inst, dep):
            cert = certified_rows(db_conn, por_id, inst, dep, [row["id"]])
            assert repo.by_id(row["id"]) == (cert[0] if cert else None)


def test_certified_sql_constants_match_next():
    # el listado del entry (l. 4713) ordena igual y trae las mismas columnas
    listado = " ".join(sql_constants(ENTRY, "get_periodos", 0)[0].split())
    assert listado == ("SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones "
                       "FROM periodos ORDER BY anio DESC, semestre DESC, id DESC")
    abrir = [" ".join(s.split()) for s in sql_constants(ENTRY, "abrir_periodo_emergencia")]
    assert abrir[0] == "SELECT pg_advisory_xact_lock(hashtext(?))" and abrir[1] == "BEGIN IMMEDIATE"  # rama SQLite
    assert abrir[3] == ("SELECT id, nombre, fecha_inicio, fecha_fin, estado FROM periodos "
                        "WHERE estado = 'Abierto' ORDER BY id DESC LIMIT 1")
    assert abrir[4:] == ["UPDATE periodos SET estado = 'Cerrado' WHERE estado = 'Abierto' AND id <> ?",
                         "UPDATE periodos SET estado = 'Abierto' WHERE id = ?"]
    volver = sql_constants(ENTRY, "volver_periodo_actual")
    assert volver == ["UPDATE periodos SET estado = 'Cerrado' WHERE estado = 'Abierto'",
                      "UPDATE periodos SET estado = 'Abierto' WHERE id = ?"]


def test_lock_keys_are_the_certified_ones():
    assert period_repo.PERIOD_STATE_LOCK == ref_b12i.PERIOD_LOCK_FORMAT
    assert 'f"deptit_abrir_periodo_emergencia:{_pg_current_inst_id() or 0}:"' in ENTRY_TEXT
    assert period_repo.EMERGENCY_OPEN_LOCK == "deptit_abrir_periodo_emergencia:{inst}:{dep}"
    family = next(f for f in ref_b12i.CONSISTENCY_FAMILIES if f.name == "periodo_estado")
    assert family.lock_format == period_repo.PERIOD_STATE_LOCK and family.needs_department is True
    assert {period_service.OP_RETURN_BODY, period_service.OP_RETURN_CONTROL,
            period_service.OP_OPEN_CONTROL} <= set(family.writers)


# ------------------------------------------------------------------------------------------------ escrituras
def run_certified(conn, inst, dep, call, prepare=None):
    """Ejecuta el writer certificado en un SAVEPOINT revertido.  Devuelve (error, periodos despues, movimientos,
    COMMITs acoplados B12H [(commit_seq, mutating_statements, committing_writer)])."""
    before = snapshot(conn, inst, dep)
    error, after, movs = None, None, None
    ns = certified_period_writers(conn, inst, dep)
    if prepare is not None:
        prepare(ns)
    with conn.transaction() as tx:
        try:
            call(ns)
        except ValueError as exc:
            error = str(exc)
        after = snapshot(conn, inst, dep)["periodos"]
        movs = movements_after(conn, before["max_mov_id"])
        raise psycopg.Rollback(tx)
    assert snapshot(conn, inst, dep) == before
    return error, after, movs, list(ns["_commits"])


def run_next(conn, inst, dep, call):
    """Lo mismo para NEXT; los COMMITs salen de los SUCCESS IN_TRANSACTION escritos en b12h_audit_log."""
    before = snapshot(conn, inst, dep)
    error, after, movs, commits = None, None, None, None
    with conn.transaction() as tx:
        try:
            call()
        except PeriodosError as exc:
            error = exc
        after = snapshot(conn, inst, dep)["periodos"]
        movs = movements_after(conn, before["max_mov_id"])
        commits = [{k: v for k, v in r["metadata"].items() if k != "entity_param"} for r in audit_after(conn)]
        raise psycopg.Rollback(tx)
    assert snapshot(conn, inst, dep) == before
    return error, after, movs, commits


def _states(conn, dep):
    snap = snapshot(conn, 1, dep)
    return ([p for p in snap["periodos"] if p["estado"] == "Abierto"],
            [p for p in snap["periodos"] if p["estado"] != "Abierto"])


SETUPS = {
    "con_abierto": lambda conn, dep: None,
    "sin_abierto": lambda conn, dep: conn.execute(
        "UPDATE periodos SET estado = 'Cerrado' WHERE institucion_id = 1 AND departamento_id = %s", [dep]),
}


@pytest.mark.parametrize("setup", sorted(SETUPS))
@pytest.mark.parametrize("dep", [1, 2, 11])
def test_open_previous_equivalent_to_certified(periodos, service, repo, db_conn, setup, dep):
    record, _ = session_for(service, repo, 1)
    service.set_context(record, 1, dep, False)
    with db_conn.transaction() as scenario:
        SETUPS[setup](db_conn, dep)
        snap = snapshot(db_conn, 1, dep)["periodos"]
        foreign = snapshot(db_conn, 1, 9)["periodos"][0]  # periodo de OTRO departamento
        written = 0
        for target in snap + [foreign]:
            obs = f"obs {target['id']}"
            cert = run_certified(db_conn, 1, dep, lambda ns: ns["abrir_periodo_emergencia"](target["id"], obs))
            ours = run_next(db_conn, 1, dep,
                            lambda: periodos.open_previous(record, target["id"], obs, True, True))
            assert ours[1:] == cert[1:], (setup, dep, target["id"])
            if cert[0] is None:
                assert ours[0] is None
            else:
                assert ours[0] is not None and ours[0].message.endswith(cert[0])
            written += len(cert[2] or [])
        # con un abierto previo hay al menos un periodo cerrado que el certificado realmente abre (no es vacuo)
        assert written >= (1 if len(snap) > 1 or setup == "sin_abierto" else 0)
        raise psycopg.Rollback(scenario)


@pytest.mark.parametrize("dep", [1, 2])
def test_return_current_equivalent_to_certified(periodos, service, repo, db_conn, dep):
    record, _ = session_for(service, repo, 1)
    service.set_context(record, 1, dep, False)
    with db_conn.transaction() as scenario:
        opened, closed = _states(db_conn, dep)
        variants = [
            ("anterior_abierto", [("Cerrado", opened[0]["id"]), ("Abierto", closed[0]["id"])], (True, True)),
            ("sin_abierto", [("Cerrado", opened[0]["id"])], (False, True)),
        ]
        for name, updates, flags in variants:
            with db_conn.transaction() as variant:
                for estado, pid in updates:
                    db_conn.execute("UPDATE periodos SET estado = %s WHERE id = %s", [estado, pid])
                cert = run_certified(db_conn, 1, dep, lambda ns: ns["volver_periodo_actual"]("motivo"))
                ours = run_next(db_conn, 1, dep, lambda: periodos.return_current(record, "motivo", *flags))
                assert cert[0] is None and ours[0] is None, name
                assert ours[1:] == cert[1:], name
                assert len(cert[2]) == 1 and cert[2][0]["tipo_movimiento"] == "Retorno al período actual"
                assert [c["committing_writer"] for c in cert[3]] == ["volver_periodo_actual", "registrar_movimiento"]
                raise psycopg.Rollback(variant)
        raise psycopg.Rollback(scenario)


def test_open_previous_commit_sequence_matches_b12h(periodos, service, repo, db_conn):
    """Los 2 SUCCESS que escribe NEXT son exactamente los COMMITs acoplados del codigo certificado."""
    record, _ = session_for(service, repo, 3)
    closed = _states(db_conn, 1)[1]
    cert = run_certified(db_conn, 1, 1, lambda ns: ns["abrir_periodo_emergencia"](closed[0]["id"], "x"))
    ours = run_next(db_conn, 1, 1, lambda: periodos.open_previous(record, closed[0]["id"], "x", True, True))
    assert cert[3] == ours[3] == [
        {"commit_seq": 1, "mutating_statements": 2, "committing_writer": "abrir_periodo_emergencia"},
        {"commit_seq": 2, "mutating_statements": 1, "committing_writer": "registrar_movimiento"}]


@pytest.mark.parametrize("writer", ["abrir", "volver"])
def test_failure_after_first_commit_equivalent_to_certified(periodos, service, repo, db_conn, monkeypatch, writer):
    """Si falla el movimiento (COMMIT 2), el cambio de estado ya confirmado queda, igual que en el certificado."""
    record, _ = session_for(service, repo, 3)
    with db_conn.transaction() as scenario:
        opened, closed = _states(db_conn, 1)
        if writer == "volver":
            db_conn.execute("UPDATE periodos SET estado = 'Cerrado' WHERE id = %s", [opened[0]["id"]])
            db_conn.execute("UPDATE periodos SET estado = 'Abierto' WHERE id = %s", [closed[0]["id"]])

        def fail_movement(ns):
            def broken(*args, **kwargs):
                raise ValueError("fallo simulado del movimiento")
            ns["registrar_movimiento"] = broken

        if writer == "abrir":
            cert = run_certified(db_conn, 1, 1, lambda ns: ns["abrir_periodo_emergencia"](closed[0]["id"], ""),
                                 prepare=fail_movement)
        else:
            cert = run_certified(db_conn, 1, 1, lambda ns: ns["volver_periodo_actual"](""), prepare=fail_movement)

        def broken_insert(self, **kwargs):
            raise ValueError("fallo simulado del movimiento")

        monkeypatch.setattr(PeriodosRepository, "insert_movement", broken_insert)
        if writer == "abrir":
            ours = run_next(db_conn, 1, 1, lambda: periodos.open_previous(record, closed[0]["id"], "", True, True))
        else:
            ours = run_next(db_conn, 1, 1, lambda: periodos.return_current(record, "", True, True))
        assert cert[0] == "fallo simulado del movimiento" and ours[0].code == "DB_ERROR"
        assert ours[1:] == cert[1:]
        assert cert[2] == [] and len(cert[3]) == 1  # estado confirmado, sin movimiento
        raise psycopg.Rollback(scenario)


# ------------------------------------------------------------------------------------------------ textos
ROLES = [None, "superadmin", "coordinador_institucional", "usuario_departamento", "solo_lectura", "rector"]
ACCESS = ["normal", "read_only", "blocked", "raro"]


def test_denial_messages_identical_to_b10():
    for role in ROLES:
        for access in ACCESS:
            for dep, home_dep in [(1, 1), (2, 1), (None, None)]:
                kwargs = dict(role=role, access_mode=access, user_ref="u@test", institution_id=1,
                              department_id=dep, home_institution_id=None if role == "superadmin" else 1,
                              home_department_id=home_dep)
                ours = policy.ActorContext(authenticated=role is not None, **kwargs)
                ref = ref_authz.ActorContext(authenticated=role is not None, **kwargs)
                for action, ref_action in [(period_service.ACTION_WRITE, ref_authz.Action("periodos", "write"))]:
                    decision = policy.decide(ours, action)
                    ref_decision = ref_authz.decide(ref, ref_action)
                    assert decision.allowed == ref_decision.allowed and decision.code == ref_decision.code
                    if not decision.allowed:
                        assert period_service.denial_message(decision, action) == \
                            ref_ui.mensaje_denegacion(ref_decision)


def test_period_writers_registered_as_in_b10():
    assert ref_registry.BUSINESS_WRITERS["abrir_periodo_emergencia"].key == period_service.ACTION_WRITE.key
    assert ref_registry.BUSINESS_WRITERS["_abrir_periodo_emergencia_control_v300"].key == "periodos.write"
    assert ref_registry.BUSINESS_WRITERS["volver_periodo_actual"].key == "periodos.write"
    assert ref_registry.BUSINESS_WRITERS["_volver_periodo_actual_control_v300"].key == "periodos.write"
    assert ref_registry.BUSINESS_WRITERS["registrar_movimiento"].key == "movimientos.write"
    assert ref_registry.BUSINESS_WRITERS["eliminar_periodo_con_datos_admin"].key == "periodos.delete"


@pytest.mark.parametrize("reason", ["INSTITUTION_ABSENT", "INSTITUTION_INVALID", "INSTITUTION_NOT_FOUND",
                                    "DEPARTMENT_ABSENT", "DEPARTMENT_INVALID", "DEPARTMENT_NOT_FOUND",
                                    "DEPARTMENT_MISMATCH"])
@pytest.mark.parametrize("with_institution", [True, False])
def test_scope_message_identical_to_b12b(reason, with_institution):
    ours = ScopeResolution({"id": 1, "nombre": "X"} if with_institution else None, None, reason)
    ref = ref_scope.ScopeResolution(1 if with_institution else None, None, "OK", "X", None, reason)
    assert period_service.scope_message(ours) == ref_scope.scope_denied_message(ref)


def test_infrastructure_messages_identical():
    assert period_service.MSG_STALE == ref_b12i.MSG_STALE
    assert period_service.MSG_DB_TRANSACTION == ref_b12d.MSG_TRANSACTION
    assert period_service.MSG_DB_READ == ref_b12d.MSG_READ
    assert audit.MSG_PERSIST == ref_audit.MSG_PERSIST
    assert period_service.MSG_AUDIT_POST == ref_audit.MSG_PERSIST_POST


def test_ui_and_writer_texts_appear_verbatim_in_certified_entry():
    texts = [period_service.MSG_NO_PERIODS, period_service.MSG_OPEN_CONFIRM, period_service.MSG_RETURN_CONFIRM,
             period_service.MSG_RETURN_CONFIRM_SINGLE, period_service.MSG_INVALID_PERIOD,
             period_service.MSG_PERIOD_NOT_FOUND, period_service.MSG_OPEN_FAILED,
             period_service.MSG_NO_PERIODS_REGISTERED, period_service.MOV_OPEN, period_service.MOV_RETURN,
             "Revisá bien antes de modificar datos.", "Se volvió al período actual correctamente.",
             "Se abrió el período actual correctamente.", period_service.PREFIX_OPEN_ERROR.rstrip(": "),
             period_service.PREFIX_RETURN_ERROR.rstrip(": "), "Ya estás trabajando sobre el período actual: ",
             "Estás en el ámbito institucional. Seleccioná un departamento desde la barra lateral "]
    for text in texts:
        assert text in ENTRY_TEXT, text


# ------------------------------------------------------------------------------------------------ B12H
def test_audit_contract_identical_to_b12h():
    assert audit.EVENT_COLUMNS == ref_audit.EVENT_COLUMNS
    assert audit.INSERT_SQL == ref_audit.INSERT_SQL
    assert (audit.EVENT_VERSION, audit.SUBSYSTEM, audit.APP_BATCH) == (
        ref_audit.EVENT_VERSION, ref_audit.SUBSYSTEM, ref_audit.APP_BATCH)
    catalog = ref_audit.writer_catalog()
    assert audit.WRITER_NAMES <= set(catalog)
    for name in (period_service.OP_OPEN_CONTROL, period_service.OP_RETURN_CONTROL, period_service.OP_RETURN_BODY):
        assert catalog[name].entity_type == "periodo" and catalog[name].action == "periodos.write"
        assert catalog[name].action_scope == "department" and catalog[name].mode == "COUPLED"
    assert catalog[period_service.OP_MOVEMENT].entity_type == "movimiento"


def _certified_signature(name):
    ns = {}
    node = next(n for n in __import__("periodos_support").entry_defs(ENTRY, name))
    exec(compile(f"def {name}({__import__('ast').unparse(node.args)}): pass", "<sig>", "exec"), ns)
    return inspect.signature(ns[name])


def test_entity_param_matches_b12h_rules():
    open_sig = inspect.signature(lambda periodo_id, observaciones="": None)
    assert ref_audit._entity_param(open_sig, "periodo") == "periodo_id"
    assert ref_audit._entity_param(_certified_signature("volver_periodo_actual"), "periodo") is None
    assert ref_audit._entity_param(_certified_signature("abrir_periodo_emergencia"), "periodo") == "periodo_id"
    for raw in [5, "5", "abc", "", None, True, -3, "x" * 80]:
        assert audit.entity_value(raw) == ref_audit.entity_value(raw), raw


def test_next_events_pass_certified_b12h_validation(periodos, service, repo, db_conn, audit_store):
    record, _ = session_for(service, repo, 3)
    closed = [p for p in snapshot(db_conn, 1, 1)["periodos"] if p["estado"] != "Abierto"]
    with db_conn.transaction() as tx:
        periodos.open_previous(record, closed[0]["id"], "", True, True)       # SUCCESS IN_TRANSACTION
        periodos.open_previous(record, closed[0]["id"], "", True, True)       # SUCCESS POST_OPERATION (sin cambios)
        with pytest.raises(PeriodosError):
            periodos.open_previous(record, "abc", "", True, True)             # FAILED
        deny, _ = session_for(service, repo, 7)
        with pytest.raises(PeriodosError):
            periodos.open_previous(deny, closed[0]["id"], "", True, True)     # DENIED
        rows = audit_after(db_conn)  # 2 SUCCESS IN_TRANSACTION: uno por COMMIT (estado, movimiento)
        assert [(r["event_seq"], r["metadata"]["commit_seq"], r["audit_mode"]) for r in rows] == [
            (1, 1, "IN_TRANSACTION"), (2, 2, "IN_TRANSACTION")]
        raise psycopg.Rollback(tx)
    assert [(e.outcome, e.audit_mode) for e in audit_store.events] == [
        ("SUCCESS", "POST_OPERATION"), ("FAILED", "SEPARATE_TRANSACTION"), ("DENIED", "SEPARATE_TRANSACTION")]
    for event in audit_store.events:
        a = event.actor
        ref_actor = ref_audit.AuditActor(
            ref_audit.ACTOR_USER, ref_audit.SOURCE_B12G, user_id=a.user_id, email=a.email, role=a.role,
            is_superadmin=a.is_superadmin, home_institution_id=a.home_institution_id,
            home_department_id=a.home_department_id, institution_id=a.institution_id,
            department_id=a.department_id, scope_source=a.scope_source, session_ref=a.session_ref)
        ref_event = ref_audit.AuditEvent(
            audit_id=event.audit_id, correlation_id=event.correlation_id, event_seq=event.event_seq,
            actor=ref_actor, operation=event.operation, action=event.action, action_scope=event.action_scope,
            entity_type=event.entity_type, entity_id=event.entity_id, outcome=event.outcome,
            audit_mode=event.audit_mode, error_code=event.error_code, metadata=event.metadata)
        ref_event.validate()
        assert ref_event.params() == event.params()


def test_metadata_policy_is_subset_of_b12h():
    samples = [{"commit_seq": 1}, {"mutating_statements": 3}, {"coupled_commits": 0},
               {"committing_writer": "abrir_periodo_emergencia"}, {"post_reason": "NO_POOLED_COMMIT"},
               {"b10_decision": "DENY_ROLE_NOT_PERMITTED"}, {"entity_param": "periodo_id"}]
    for sample in samples:
        assert audit.check_metadata(sample) == ref_audit.check_metadata(sample)
    for bad in [{"observaciones": "x"}, {"commit_seq": -1}, {"committing_writer": "eliminar_periodo_con_datos_admin"}]:  # E4-10 habilita crear_periodo
        with pytest.raises(audit.AuditError):
            audit.check_metadata(bad)
