"""Servicio de Docentes sobre deptit_next_dev con ROLLBACK: permisos por rol (B10), multitenant (B12B), auditoria B12H,
B12I (huella), fallas intermedias y mensajes certificados.  Usuarios del FakeRepo de auth (sin credenciales humanas)."""

from __future__ import annotations

import pytest

import audit
from docentes import service as svc
from docentes.repository import DocentesRepository
from docentes.service import DocentesError
from docentes_support import (  # noqa: F401  (fixtures)
    audit_rows, audit_store, db_conn, docentes, free_cuil, session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST = 1
C1 = "27-99000011-6"
C2 = "20-99000012-3"


def alta_data(cuil=C1, **kw):
    data = dict(apellido="Prueba", nombres="Docente", cuil=cuil, legajo="", titulo="", titulo_posgrado="",
                nivel_posgrado_salarial="", antiguedad_anios=None, email="", telefono="", ref_legajo_fisico="",
                fecha_alta="2026-10-26", observaciones="")
    data.update(kw)
    return data


def count_cuil(conn, cuil, table="docentes"):
    return conn.execute(f"SELECT count(*) FROM {table} WHERE regexp_replace(cuil,'[^0-9]','','g') = %s",
                        [cuil.replace("-", "")]).fetchone()[0]


def local_cuils(conn, dep):
    return {r[0] for r in conn.execute("SELECT cuil FROM docentes WHERE institucion_id = 1 AND departamento_id = %s",
                                       [dep]).fetchall()}


@pytest.fixture
def records(service, repo):
    out = {"dep1": session_for(service, repo, 3)[0], "dep2": session_for(service, repo, 6)[0],
           "lector": session_for(service, repo, 7)[0], "coord": session_for(service, repo, 2)[0],
           "uba": session_for(service, repo, 4)[0]}
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, INST, 1, False)
    out["super"] = sup
    return out


# ------------------------------------------------------------------------------------------------ lectura y roles
def test_overview_permissions_by_role(docentes, records, service, db_conn):
    dep1 = docentes.overview(records["dep1"])
    assert dep1["permisos"] == {"puede_escribir": True, "puede_borrar": False, "es_superadmin": False}
    assert {r["cuil"] for r in dep1["docentes"]} == local_cuils(db_conn, 1)
    sup = docentes.overview(records["super"])
    assert sup["permisos"] == {"puede_escribir": True, "puede_borrar": True, "es_superadmin": True}
    lector = docentes.overview(records["lector"])
    assert lector["permisos"]["puede_escribir"] is False and lector["permisos"]["puede_borrar"] is False
    with pytest.raises(DocentesError) as exc:
        docentes.overview(records["coord"])   # coordinador sin departamento: vista institucional
    assert exc.value.code == "SCOPE_INSTITUTIONAL"
    service.set_context(records["coord"], INST, 2, False)
    coord = docentes.overview(records["coord"])
    assert coord["contexto"]["departamento"]["id"] == 2 and coord["permisos"]["puede_escribir"] is False
    assert {r["cuil"] for r in coord["docentes"]} == local_cuils(db_conn, 2)
    assert docentes.overview(records["uba"])["docentes"] == []  # institucion 2 / departamento 5 sin docentes


def test_tenant_isolation_and_manipulated_ids(docentes, records, db_conn, audit_store):
    only_dep2 = sorted(local_cuils(db_conn, 2) - local_cuils(db_conn, 1))[0]
    with pytest.raises(DocentesError) as exc:
        docentes.ficha(records["dep1"], only_dep2)
    assert exc.value.code == "NOT_FOUND"
    before = count_cuil(db_conn, only_dep2)
    with pytest.raises(DocentesError) as exc:  # editar un docente de otro departamento: B12I rechaza, nada cambia
        docentes.editar(records["dep1"], dict(alta_data(cuil=only_dep2), cuil_original=only_dep2, huella="x" * 32,
                                              estado="Activo", tipo_docente="Propio"))
    assert exc.value.code == "STALE"
    with pytest.raises(DocentesError) as exc:  # eliminar desde el departamento 1 (superadmin): idem
        docentes.eliminar(records["super"], {"cuil": only_dep2, "huella": "x" * 32, "confirmar": True})
    assert exc.value.code == "STALE" and count_cuil(db_conn, only_dep2) == before
    assert [e.outcome for e in audit_store.events] == ["FAILED", "FAILED"]
    assert {e.error_code for e in audit_store.events} == {"StaleDecisionError"}


@pytest.mark.parametrize("who,code", [("lector", "DENY_READ_ONLY_ROLE"), ("coord_dep", "DENY_ROLE_NOT_PERMITTED")])
def test_write_denied_for_read_roles(docentes, records, service, db_conn, audit_store, who, code):
    free_cuil(db_conn, C1)
    record = records["lector"] if who == "lector" else records["coord"]
    if who == "coord_dep":
        service.set_context(record, INST, 1, False)
    with pytest.raises(DocentesError) as exc:
        docentes.alta(record, alta_data())
    assert exc.value.status == 403
    assert exc.value.message.startswith(svc.PREFIX_ALTA + "⛔ ")
    assert "(permiso requerido: docentes.write)" in exc.value.message
    assert count_cuil(db_conn, C1) == 0
    assert [(e.outcome, e.operation, e.error_code) for e in audit_store.events] == [("DENIED", "guardar_docente", code)]


def test_delete_only_superadmin(docentes, records, db_conn, audit_store):
    cuil = sorted(local_cuils(db_conn, 1))[0]
    h = next(r["huella"] for r in docentes.overview(records["dep1"])["docentes"] if r["cuil"] == cuil)
    with pytest.raises(DocentesError) as exc:
        docentes.eliminar(records["dep1"], {"cuil": cuil, "huella": h, "confirmar": True})
    assert exc.value.status == 403 and "(permiso requerido: docentes.delete)" in exc.value.message
    assert audit_store.events[-1].outcome == "DENIED" and audit_store.events[-1].operation == "eliminar_docente"


def test_commercial_read_only_blocks_writes(docentes, service, repo, db_conn, audit_store):
    repo.institutions_rows[0]["estado_pago"] = "Vencido"
    record = session_for(service, repo, 3)[0]
    free_cuil(db_conn, C1)
    with pytest.raises(DocentesError) as exc:
        docentes.alta(record, alta_data())
    assert exc.value.status == 403 and audit_store.events[-1].error_code == "DENY_COMMERCIAL_READ_ONLY"
    assert docentes.overview(record)["permisos"]["puede_escribir"] is False


# ------------------------------------------------------------------------------------------------ alta
@pytest.mark.parametrize("kw,msg", [
    (dict(apellido=""), svc.MSG_ALTA_REQUERIDOS),
    (dict(nombres=""), svc.MSG_ALTA_REQUERIDOS),
    (dict(cuil="20-1234567-8"), "El CUIL debe tener 11 dígitos, con o sin guiones (por ejemplo 20-12345678-9)."),
    (dict(email="mal@correo"), "El correo electrónico no tiene un formato válido (por ejemplo nombre@dominio.com)."),
    (dict(nivel_posgrado_salarial="Licenciado"), svc.MSG_VALOR_INVALIDO),
    (dict(antiguedad_anios=81), svc.MSG_VALOR_INVALIDO),
])
def test_alta_validations_without_writes(docentes, records, db_conn, audit_store, kw, msg):
    free_cuil(db_conn, C1)
    with pytest.raises(DocentesError) as exc:
        docentes.alta(records["dep1"], alta_data(**kw))
    assert exc.value.message == msg and exc.value.status == 422
    assert audit_store.events == [] and count_cuil(db_conn, C1) == 0


def test_alta_branches_existing_cuil(docentes, records, db_conn):
    local = sorted(local_cuils(db_conn, 1) - local_cuils(db_conn, 2))[0]
    with pytest.raises(DocentesError) as exc:
        docentes.alta(records["dep1"], alta_data(cuil=local))
    assert exc.value.code == "CUIL_LOCAL" and exc.value.message.startswith(
        "Este CUIL ya está registrado en el departamento actual como ")
    other = sorted(local_cuils(db_conn, 2) - local_cuils(db_conn, 1))[0]
    with pytest.raises(DocentesError) as exc:
        docentes.alta(records["dep1"], alta_data(cuil=other))
    assert exc.value.code == "CUIL_OTRO_DEPARTAMENTO" and exc.value.message == svc.MSG_OTRO_DEPTO
    v = docentes.verificar_cuil(records["dep1"], other)
    assert v["local"] is None and v["otros_departamentos"]


def test_alta_success_audit_two_operations(docentes, records, db_conn, audit_store):
    free_cuil(db_conn, C1)
    res = docentes.alta(records["dep1"], alta_data(apellido="Gómez", nombres="Ana"))
    assert res["mensaje"] == "Docente registrado correctamente."
    row = db_conn.execute("SELECT institucion_id, departamento_id, nombre, estado, tipo_docente FROM docentes WHERE "
                          "cuil = %s", [C1]).fetchone()
    assert row == (1, 1, "Gómez, Ana", "Activo", "Propio")
    mov = db_conn.execute("SELECT tipo_movimiento, nombre, detalle, periodo_id, departamento_id FROM movimientos "
                          "WHERE cuil = %s", [C1]).fetchall()
    assert mov == [("Alta de docente", "Gómez, Ana", "Se registró el docente en la base maestra.", 9, 1)]
    events = audit_rows(db_conn)
    assert [(e["operation"], e["outcome"], e["audit_mode"], e["entity_type"], e["entity_id"], e["action"])
            for e in events] == [
        ("guardar_docente", "SUCCESS", "IN_TRANSACTION", "docente", C1, "docentes.write"),
        ("registrar_movimiento", "SUCCESS", "IN_TRANSACTION", "movimiento", C1, "movimientos.write")]
    assert events[0]["correlation_id"] != events[1]["correlation_id"]
    assert all(e["actor_user_id"] == 3 and e["departamento_id"] == 1 for e in events)
    assert audit_store.events == []


def test_movement_failure_keeps_committed_teacher(docentes, records, db_conn, audit_store, monkeypatch):
    free_cuil(db_conn, C1)

    def boom(self, **kw):
        raise RuntimeError("falla simulada")
    monkeypatch.setattr(DocentesRepository, "insert_movement", boom)
    with pytest.raises(DocentesError) as exc:
        docentes.alta(records["dep1"], alta_data())
    assert exc.value.message == svc.PREFIX_ALTA + svc.MSG_DB_TRANSACTION
    assert count_cuil(db_conn, C1) == 1 and count_cuil(db_conn, C1, "movimientos") == 0  # COMMITs separados
    assert [(e.operation, e.outcome) for e in audit_store.events] == [("registrar_movimiento", "FAILED")]


def test_audit_insert_failure_rolls_back_business(docentes, records, db_conn, audit_store, monkeypatch):
    free_cuil(db_conn, C1)

    def boom(conn, event):
        raise RuntimeError("audit down")
    monkeypatch.setattr(audit, "insert_on", boom)
    with pytest.raises(DocentesError) as exc:
        docentes.alta(records["dep1"], alta_data())
    assert exc.value.code == "AUDIT" and count_cuil(db_conn, C1) == 0
    assert audit_store.events[-1].outcome == "FAILED"


# ------------------------------------------------------------------------------------------------ edicion / B12I
def test_edit_stale_huella_and_movement_types(docentes, records, db_conn, audit_store):
    free_cuil(db_conn, C1)
    docentes.alta(records["dep1"], alta_data())
    fila = next(r for r in docentes.overview(records["dep1"])["docentes"] if r["cuil"] == C1)
    base = dict(alta_data(), cuil_original=C1, estado="Fallecido", tipo_docente="Propio")
    with pytest.raises(DocentesError) as exc:
        docentes.editar(records["dep1"], dict(base, huella="0" * 32))
    assert exc.value.code == "STALE" and exc.value.message.startswith(svc.MSG_STALE)
    docentes.editar(records["dep1"], dict(base, huella=fila["huella"]))
    fila2 = next(r for r in docentes.overview(records["dep1"])["docentes"] if r["cuil"] == C1)
    docentes.editar(records["dep1"], dict(base, estado="Activo", huella=fila2["huella"]))
    tipos = [r[0] for r in db_conn.execute("SELECT tipo_movimiento FROM movimientos WHERE cuil = %s ORDER BY id",
                                           [C1]).fetchall()]
    assert tipos == ["Alta de docente", "Baja de docente", "Alta de docente"]
    detalle = db_conn.execute("SELECT detalle FROM movimientos WHERE cuil = %s ORDER BY id DESC LIMIT 1",
                              [C1]).fetchone()[0]
    assert detalle == "Se reactivó el docente. Estado anterior: Fallecido."
    with pytest.raises(DocentesError) as exc:  # la huella vista con estado Fallecido ya no corresponde
        docentes.editar(records["dep1"], dict(base, huella=fila2["huella"]))
    assert exc.value.code == "STALE"
    # Como B12I (huella de contenido), volver exactamente al estado visto no es una decision obsoleta.
    assert fila["huella"] == next(r for r in docentes.overview(records["dep1"])["docentes"] if r["cuil"] == C1)["huella"]


def test_edit_validation_only_changed_values(docentes, records, db_conn):
    free_cuil(db_conn, C1)
    docentes.alta(records["dep1"], alta_data())
    fila = next(r for r in docentes.overview(records["dep1"])["docentes"] if r["cuil"] == C1)
    with pytest.raises(DocentesError) as exc:
        docentes.editar(records["dep1"], dict(alta_data(cuil="27-9900001"), cuil_original=C1, huella=fila["huella"],
                                              estado="Activo", tipo_docente="Propio"))
    assert "11 dígitos" in exc.value.message
    with pytest.raises(DocentesError) as exc:  # B12A: nivel no reconocido, FAILED sin cambios
        docentes.editar(records["dep1"], dict(alta_data(nivel_posgrado_salarial="Licenciado"), cuil_original=C1,
                                              huella=fila["huella"], estado="Activo", tipo_docente="Propio"))
    assert exc.value.message.startswith("Nivel de posgrado salarial no reconocido: 'Licenciado'.")


# ------------------------------------------------------------------------------------------------ eliminar / periodo
def test_delete_requires_confirmation(docentes, records, audit_store):
    with pytest.raises(DocentesError) as exc:
        docentes.eliminar(records["super"], {"cuil": "x", "huella": "y", "confirmar": False})
    assert exc.value.message == "Primero confirmá la eliminación." and audit_store.events == []


def test_historic_open_period_blocks_operational_label(docentes, records, db_conn):
    previous = db_conn.execute("SELECT id FROM periodos WHERE institucion_id = 1 AND departamento_id = 1 AND id <> 9 "
                               "ORDER BY id DESC LIMIT 1").fetchone()[0]
    db_conn.execute("UPDATE periodos SET estado = 'Cerrado' WHERE institucion_id = 1 AND departamento_id = 1")
    db_conn.execute("UPDATE periodos SET estado = 'Abierto' WHERE id = %s", [previous])
    data = docentes.overview(records["dep1"])
    assert data["historico"] is True
    assert {r["estado_periodo_abierto"] for r in data["docentes"]} == {svc.MSG_HISTORICO_NO_DISPONIBLE}


# ------------------------------------------------------------------------------------------------ carga rapida
def test_carga_preview_and_duplicates_need_confirmation(docentes, records, db_conn):
    free_cuil(db_conn, C1)
    existing = sorted(local_cuils(db_conn, 1))[0]
    texto = f"cuil\tapellido\tnombres\n{C1}\tNuevo\tUno\n{existing}\tExiste\tYa\n{C1}\tRepe\tTida\n"
    prev = docentes.carga_preview(records["dep1"], texto)
    assert [d["motivo"] for d in prev["duplicados"]] == ["Ya existe en la base maestra",
                                                         "Duplicado dentro de la tabla pegada"]
    with pytest.raises(DocentesError) as exc:
        docentes.carga_ejecutar(records["dep1"], texto, False)
    assert exc.value.message == svc.MSG_CARGA_DUPLICADOS and count_cuil(db_conn, C1) == 0
    assert docentes.carga_preview(records["dep1"], "x\n")["aviso"] == svc.MSG_CARGA_SIN_FILAS
    assert docentes.carga_preview(records["dep1"], "")["aviso"] is None


def test_carga_solo_lectura_denied(docentes, records, db_conn, audit_store):
    free_cuil(db_conn, C2)
    with pytest.raises(DocentesError) as exc:
        docentes.carga_ejecutar(records["lector"], f"cuil\tapellido\tnombres\n{C2}\tA\tB\n", False)
    assert exc.value.status == 403 and "La carga se interrumpió en la fila 1:" in exc.value.message
    assert count_cuil(db_conn, C2) == 0


def test_modelo_excel_and_prestables(docentes, records):
    assert docentes.modelo_excel(records["lector"])[:2] == b"PK"
    rows = docentes.prestables(records["dep1"])["docentes"]
    assert rows and all(r["departamento_origen"] != "Departamento de Informática e Ingeniería" for r in rows)
