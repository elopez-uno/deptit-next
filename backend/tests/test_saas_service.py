"""Servicio y HTTP de Administración SaaS sobre deptit_next_dev: cada operación en un SAVEPOINT de UNA transacción que
se revierte completa al terminar el test.  Datos SINTÉTICOS (``zznext``) para toda escritura; nunca se borran ni
modifican instituciones, departamentos o usuarios reales de forma persistente.

Cubre: los 12 writers, B10 por rol, D-AP1/D-AP2 (eliminación solo de entidades vacías, sin cascada ni disco), D-AP4
(coherencia multi-tenant, cupo en alta/activación/edición, último superadmin), D-AP5 (PBKDF2 de ``auth.core``, K4,
nada de secretos en respuestas/eventos), D-AP7 (``entity_id`` real en altas), B12H, B12G, CSRF, esquemas sin mass
assignment, errores genéricos y Excel."""

from __future__ import annotations

import io
import os
import re
from contextlib import contextmanager

import pandas as pd
import psycopg
import pytest

import audit
import db
from auth import core
from auth.service import SessionEnded
from saas import escrituras as E
from saas import lecturas as L
from saas import textos as T
from saas.service import SaasError
from saas_support import (  # noqa: F401  (fixtures)
    FakeAuditStore, audit_saas, audit_store, auth_db, db_conn, http, ids_por_rol, make_saas, nueva_institucion,
    nuevo_departamento, nuevo_usuario, saas, savepoint, scalar, sesion, superadmin,
)

CSRF = {"X-DEPTIT-Request": "1"}
PWD = "Zznext-clave-segura-2026"


def _inst_payload(nombre="ZZNEXT Instituto Nuevo", **kw):
    base = {"nombre": nombre, "max_usuarios": 5, "plan": "Institucional", "fecha_vencimiento": None,
            "estado_pago": "Activo", "suscripcion": "Activa", "estado": "Activa", "observaciones": ""}
    return {**base, **kw}


def _user_payload(email="zznext.nuevo@test.local", **kw):
    base = {"institucion_id": 5, "departamento_id": None, "nombre": "ZZNEXT Usuario", "email": email,
            "rol": "usuario_departamento", "password": PWD, "password_confirmacion": PWD, "estado": "Activo",
            "observaciones": ""}
    return {**base, **kw}


def _edit_payload(uid, **kw):
    base = {"usuario_id": uid, "institucion_id": 5, "departamento_id": None, "nombre": "ZZNEXT", "email":
            "zznext.edit@test.local", "rol": "usuario_departamento", "estado": "Activo", "observaciones": "",
            "password": ""}
    return {**base, **kw}


def _rechazo(fn, status=422, contiene=None) -> SaasError:
    with pytest.raises(SaasError) as exc:
        fn()
    assert exc.value.status == status, exc.value.message
    if contiene:
        assert contiene in exc.value.message
    return exc.value


def _fila(conn, sql, params):
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchone()


# ------------------------------------------------------------------------------------------ roles / B10
def test_solo_superadmin_lee_y_escribe_b10_por_request(db_conn, saas, auth_db, audit_store):
    ids = ids_por_rol(db_conn)
    for rol in ("coordinador_institucional", "usuario_departamento"):
        record = sesion(auth_db, ids[rol])[0]
        _rechazo(lambda: saas.overview(record), 403, T.MSG_SOLO_SUPERADMIN)
        e = _rechazo(lambda: saas.crear_institucion(record, _inst_payload()), 403)
        assert "permiso requerido: saas.admin" in e.message
        e = _rechazo(lambda: saas.eliminar_usuario(record, {"usuario_id": 1, "confirmado": True}), 403)
        assert "permiso requerido: saas.delete" in e.message
    # read_only comercial: el coordinador de una institución en "Solo lectura" ingresa como solo_lectura -> 403
    iid = nueva_institucion(db_conn, "ZZNEXT Comercial", estado="Solo lectura")
    uid = nuevo_usuario(db_conn, "zznext.comercial@test.local", "coordinador_institucional", iid)
    record = sesion(auth_db, uid)[0]
    assert record.user["rol"] == "solo_lectura" and record.user["modo_solo_lectura_comercial"] is True
    _rechazo(lambda: saas.overview(record), 403)
    e = _rechazo(lambda: saas.bloquear(record, {"institucion_id": iid}), 403)
    assert "solo lectura" in e.message
    # DENIED en transacción propia con el código B10; nunca SUCCESS
    denied = [ev for ev in audit_store.events if ev.outcome == audit.OUTCOME_DENIED]
    assert len(denied) == 5 and {ev.metadata["b10_decision"] for ev in denied} >= {"DENY_ROLE_NOT_PERMITTED",
                                                                                  "DENY_COMMERCIAL_READ_ONLY"}
    assert audit_saas(db_conn) == []


def test_lectura_inicial_superadmin(saas, superadmin):
    ov = saas.overview(superadmin)
    assert ov["ui"]["pestanas"] == T.PESTANAS and ov["actor_id"] == superadmin.user["id"]
    texto = str(ov)
    for prohibido in ("salt", "password_hash", "sqlite_id", "source_db", "datos_instituciones", ".db'", "C:\\"):
        assert prohibido not in texto
    # instituciones reales con datos: NO eliminables; inst 5 (sin departamentos ni usuarios) sí
    estado = {i["id"]: i["eliminable"] for i in ov["instituciones"]}
    assert estado[1] is False and estado[2] is False and estado[5] is True
    assert all(d["eliminable"] is False for d in ov["departamentos"] if d["institucion_id"] == 1)


# ------------------------------------------------------------------------------------------ instituciones
def test_instituciones_crear_cupo_comercial_bloquear(db_conn, saas, superadmin, audit_store):
    r = saas.crear_institucion(superadmin, _inst_payload(fecha_vencimiento="2027-03-01"))
    assert r["mensaje"] == "Institución creada."
    iid = r["id"]
    fila = _fila(db_conn, "SELECT * FROM instituciones WHERE id = %s", [iid])
    assert (fila["nombre"], fila["slug"], fila["max_usuarios"], fila["estado"], fila["fecha_vencimiento"]) == \
        ("ZZNEXT Instituto Nuevo", "zznext_instituto_nuevo", 5, "Activa", "2027-03-01")
    e = _rechazo(lambda: saas.crear_institucion(superadmin, _inst_payload("  zznext instituto NUEVO ")))
    assert e.message == "No se pudo crear: Esa institución ya existe. No se creó nuevamente."
    _rechazo(lambda: saas.crear_institucion(superadmin, _inst_payload("   ")), 422, "Indicá el nombre")
    assert saas.actualizar_cupo(superadmin, {"institucion_id": iid, "max_usuarios": 9})["mensaje"] == "Cupo actualizado."
    saas.actualizar_comercial(superadmin, {"institucion_id": iid, "plan": "Enterprise", "max_usuarios": 7,
                                           "fecha_vencimiento": "", "estado_pago": "Pendiente", "suscripcion": "Prueba",
                                           "estado": "Solo lectura", "observaciones": "zz"})
    fila = _fila(db_conn, "SELECT * FROM instituciones WHERE id = %s", [iid])
    assert (fila["plan"], fila["max_usuarios"], fila["fecha_vencimiento"], fila["estado_pago"], fila["suscripcion"],
            fila["estado"]) == ("Enterprise", 7, None, "Pendiente", "Prueba", "Solo lectura")
    assert saas.bloquear(superadmin, {"institucion_id": iid}) == {"mensaje": "Institución bloqueada.", "tono": "warning"}
    assert scalar(db_conn, "SELECT estado FROM instituciones WHERE id = %s", [iid]) == "Bloqueada"
    saas.desbloquear(superadmin, {"institucion_id": iid})
    assert scalar(db_conn, "SELECT estado FROM instituciones WHERE id = %s", [iid]) == "Activa"
    _rechazo(lambda: saas.actualizar_cupo(superadmin, {"institucion_id": 987654321, "max_usuarios": 3}), 422,
             "Institución inexistente.")
    eventos = audit_saas(db_conn)
    assert [e["operation"] for e in eventos] == [E.W_CREAR_INSTITUCION, E.W_CUPO, E.W_COMERCIAL,
                                                 E.W_ESTADO_INSTITUCION, E.W_ESTADO_INSTITUCION]
    assert all(e["outcome"] == "SUCCESS" and e["audit_mode"] == "IN_TRANSACTION" and e["entity_type"] == "institucion"
               and e["entity_id"] == str(iid) and e["action_scope"] == "global" for e in eventos)  # D-AP7 en el alta
    assert eventos[0]["metadata"]["entity_param"] == "id" and eventos[1]["metadata"]["entity_param"] == "institucion_id"
    assert eventos[0]["action"] == "saas.admin"
    fallidos = [ev for ev in audit_store.events if ev.outcome == audit.OUTCOME_FAILED]
    assert [ev.error_code for ev in fallidos] == ["ValueError"] * 3


def test_eliminar_institucion_solo_vacia_d_ap1(db_conn, saas, superadmin, audit_store):
    vacia = nueva_institucion(db_conn, "ZZNEXT Vacía")
    payload = {"institucion_id": vacia, "confirmado": True, "texto": "eliminar"}
    _rechazo(lambda: saas.eliminar_institucion(superadmin, {**payload, "texto": "BORRAR"}), 422, "escribí ELIMINAR")
    assert saas.eliminar_institucion(superadmin, payload)["mensaje"] == "Institución eliminada."
    assert scalar(db_conn, "SELECT COUNT(*) FROM instituciones WHERE id = %s", [vacia]) == 0
    ev = audit_saas(db_conn)[-1]
    assert (ev["operation"], ev["action"], ev["entity_id"]) == (E.W_ELIMINAR_INSTITUCION, "saas.delete", str(vacia))

    contador = iter(range(100))

    def bloqueada(preparar, contiene):
        iid = nueva_institucion(db_conn, f"ZZNEXT Con {contiene} {next(contador)}")
        preparar(iid)
        antes = _huella(db_conn)
        e = _rechazo(lambda: saas.eliminar_institucion(superadmin, {"institucion_id": iid, "confirmado": True,
                                                                     "texto": "ELIMINAR"}))
        assert "contiene datos y no puede eliminarse" in e.message and contiene in e.message
        assert "Bloqueada" in e.message and "Suspendida" in e.message
        assert scalar(db_conn, "SELECT COUNT(*) FROM instituciones WHERE id = %s", [iid]) == 1
        assert _huella(db_conn) == antes  # nada borrado: ni cascada ni huérfanos
    bloqueada(lambda i: nuevo_usuario(db_conn, "zznext.inst@test.local", "coordinador_institucional", i), "usuario")
    bloqueada(lambda i: nuevo_departamento(db_conn, i), "departamento")
    # 1 fila académica en tabla CON FK (carreras -> instituciones ON DELETE CASCADE)
    bloqueada(lambda i: _sql(db_conn, "INSERT INTO carreras (nombre, institucion_id) VALUES ('ZZNEXT', %s)", [i]),
              "registro")
    # 1 fila en tabla SIN FK (sedes_institucion)
    bloqueada(lambda i: _sql(db_conn, "INSERT INTO sedes_institucion (nombre, institucion_id) VALUES ('ZZNEXT', %s)",
                             [i]), "registro")
    # instituciones reales con datos
    for real in (1, 2):
        _rechazo(lambda: saas.eliminar_institucion(superadmin, {"institucion_id": real, "confirmado": True,
                                                                "texto": "ELIMINAR"}), 422, "contiene datos")


def test_eliminar_institucion_operativa_de_una_sesion_activa(db_conn, saas, auth_db, superadmin):
    iid = nueva_institucion(db_conn, "ZZNEXT Operativa")
    otra = sesion(auth_db, ids_por_rol(db_conn)["superadmin"], superadmin_institucion_id=iid)[0]
    assert otra.scope["superadmin_institucion_id"] == iid
    _rechazo(lambda: saas.eliminar_institucion(superadmin, {"institucion_id": iid, "confirmado": True,
                                                            "texto": "ELIMINAR"}), 422, "institución operativa")
    otra.scope["superadmin_institucion_id"] = 1
    saas.eliminar_institucion(superadmin, {"institucion_id": iid, "confirmado": True, "texto": "ELIMINAR"})


def test_eliminar_rollback_si_falla_la_auditoria(db_conn, auth_db, superadmin, audit_store, monkeypatch):
    iid = nueva_institucion(db_conn, "ZZNEXT Rollback")
    servicio = make_saas(auth_db, audit_store, db_conn)

    def falla(conn, event):
        raise RuntimeError("audit down")
    monkeypatch.setattr(audit, "insert_on", falla)
    e = _rechazo(lambda: servicio.eliminar_institucion(superadmin, {"institucion_id": iid, "confirmado": True,
                                                                    "texto": "ELIMINAR"}), 503)
    assert "[AUDIT_INSERT_FAILED]" in e.message
    assert scalar(db_conn, "SELECT COUNT(*) FROM instituciones WHERE id = %s", [iid]) == 1  # ROLLBACK completo
    assert audit_store.events[-1].error_code == "AuditPersistenceError:AUDIT_INSERT_FAILED"


# ------------------------------------------------------------------------------------------ departamentos
def test_departamentos_crear_editar_y_eliminar_solo_vacio_d_ap2(db_conn, saas, superadmin):
    iid = nueva_institucion(db_conn, "ZZNEXT Deps")
    r = saas.crear_departamento(superadmin, {"institucion_id": iid, "nombre": "ZZNEXT Física", "observaciones": ""})
    did = r["id"]
    assert r["mensaje"] == "Departamento creado."
    assert _fila(db_conn, "SELECT slug, estado FROM departamentos WHERE id = %s", [did]) == \
        {"slug": "zznext_fisica", "estado": "Activo"}
    _rechazo(lambda: saas.crear_departamento(superadmin, {"institucion_id": iid, "nombre": "zznext física",
                                                          "observaciones": ""}), 422, "ya existe")
    saas.editar_departamento(superadmin, {"departamento_id": did, "nombre": "ZZNEXT Química", "estado": "Inactivo",
                                          "observaciones": "zz"})
    assert _fila(db_conn, "SELECT nombre, slug, estado FROM departamentos WHERE id = %s", [did]) == \
        {"nombre": "ZZNEXT Química", "slug": "zznext_quimica", "estado": "Inactivo"}
    bloq = nueva_institucion(db_conn, "ZZNEXT Bloqueada", estado="Bloqueada")
    _rechazo(lambda: saas.crear_departamento(superadmin, {"institucion_id": bloq, "nombre": "ZZNEXT X",
                                                          "observaciones": ""}), 422, "no está disponible")
    eventos = audit_saas(db_conn)
    assert eventos[0]["entity_id"] == str(did) and eventos[0]["entity_type"] == "departamento"  # D-AP7
    assert eventos[1]["entity_id"] == str(did)
    # eliminar: con usuario / con dato / con préstamo que lo nombra -> bloqueado; vacío -> permitido
    p = {"departamento_id": did, "confirmado": True}
    _rechazo(lambda: saas.eliminar_departamento(superadmin, {**p, "confirmado": False}), 422, "Primero confirmá")
    uid = nuevo_usuario(db_conn, "zznext.dep@test.local", "usuario_departamento", iid, did)
    antes = _huella(db_conn)
    _rechazo(lambda: saas.eliminar_departamento(superadmin, p), 422, "hay usuarios asignados")
    _sql(db_conn, "DELETE FROM app_usuarios WHERE id = %s", [uid])
    _sql(db_conn, "INSERT INTO docentes (cuil, nombre, institucion_id, departamento_id) VALUES "
                  "('20-99999999-1', 'ZZNEXT', %s, %s)", [iid, did])  # tabla con FK CASCADE
    _rechazo(lambda: saas.eliminar_departamento(superadmin, p), 422, "contiene datos")
    _sql(db_conn, "DELETE FROM docentes WHERE departamento_id = %s", [did])
    _sql(db_conn, "INSERT INTO extension_docente (cuil, institucion_id, departamento_id) VALUES "
                  "('20-99999999-1', %s, %s)", [iid, did])  # tabla SIN FK
    _rechazo(lambda: saas.eliminar_departamento(superadmin, p), 422, "contiene datos")
    _sql(db_conn, "DELETE FROM extension_docente WHERE departamento_id = %s", [did])
    otro = nuevo_departamento(db_conn, iid, "ZZNEXT Otro")
    _sql(db_conn, "INSERT INTO prestamos_docentes (periodo_id, cuil, institucion_id, departamento_id, departamento_origen) "
                  "VALUES (1, '20-99999999-1', %s, %s, 'zznext química')", [iid, otro])  # lo nombra como origen
    _rechazo(lambda: saas.eliminar_departamento(superadmin, p), 422, "contiene datos")
    _sql(db_conn, "DELETE FROM prestamos_docentes WHERE departamento_id = %s", [otro])
    assert saas.eliminar_departamento(superadmin, p)["mensaje"] == "Departamento eliminado."
    assert scalar(db_conn, "SELECT COUNT(*) FROM departamentos WHERE id = %s", [did]) == 0
    assert audit_saas(db_conn)[-1]["entity_id"] == str(did)
    for real in (1, 2):
        _rechazo(lambda: saas.eliminar_departamento(superadmin, {"departamento_id": real, "confirmado": True}), 422)
    assert antes  # huella tomada con datos reales intactos


def test_eliminar_departamento_operativo_de_una_sesion(db_conn, saas, auth_db, superadmin):
    iid = nueva_institucion(db_conn, "ZZNEXT DepOp")
    did = nuevo_departamento(db_conn, iid)
    sesion(auth_db, ids_por_rol(db_conn)["superadmin"], superadmin_institucion_id=iid, tenant_scope_departamento_id=did)
    _rechazo(lambda: saas.eliminar_departamento(superadmin, {"departamento_id": did, "confirmado": True}), 422,
             "departamento operativo")


# ------------------------------------------------------------------------------------------ usuarios
def test_crear_usuario_coherencia_tenant_y_cupo_d_ap4(db_conn, saas, superadmin):
    iid = nueva_institucion(db_conn, "ZZNEXT Usuarios", max_usuarios=2)
    did = nuevo_departamento(db_conn, iid)
    r = saas.crear_usuario(superadmin, _user_payload(institucion_id=iid, departamento_id=did,
                                                     email="  ZZNEXT.Uno@Test.Local "))
    uid = r["id"]
    fila = _fila(db_conn, "SELECT * FROM app_usuarios WHERE id = %s", [uid])
    assert (fila["email"], fila["institucion_id"], fila["departamento_id"], fila["estado"]) == \
        ("zznext.uno@test.local", iid, did, "Activo")
    assert re.fullmatch(r"[0-9a-f]{32}", fila["salt"]) and core.verify_password(PWD, fila["salt"], fila["password_hash"])
    ev = audit_saas(db_conn)[-1]
    assert (ev["entity_type"], ev["entity_id"]) == ("usuario", str(uid))  # D-AP7: id del usuario, no la institución
    assert PWD not in str(ev) and fila["password_hash"] not in str(ev)
    # departamento de OTRA institución (request manipulado) -> rechazo
    _rechazo(lambda: saas.crear_usuario(superadmin, _user_payload(institucion_id=iid, departamento_id=1,
                                                                  email="zznext.x@test.local")), 422,
             "no pertenece a la institución")
    # superadmin / coordinador: sin departamento (misma regla que la edición)
    c = saas.crear_usuario(superadmin, _user_payload(institucion_id=iid, departamento_id=did,
                                                     rol="coordinador_institucional", email="zznext.c@test.local"))
    assert scalar(db_conn, "SELECT departamento_id FROM app_usuarios WHERE id = %s", [c["id"]]) is None
    # cupo 2 alcanzado
    _rechazo(lambda: saas.crear_usuario(superadmin, _user_payload(institucion_id=iid, email="zznext.y@test.local")),
             422, "alcanzó el cupo de 2 usuarios activos")
    # inactivo: se crea; activarlo con cupo agotado -> rechazo (D-AP4)
    ina = saas.crear_usuario(superadmin, _user_payload(institucion_id=iid, email="zznext.i@test.local",
                                                       estado="Inactivo"))["id"]
    _rechazo(lambda: saas.estado_usuario(superadmin, {"usuario_id": ina, "estado": "Activo"}), 422, "alcanzó el cupo")
    # superadmin no consume cupo
    s = saas.crear_usuario(superadmin, _user_payload(institucion_id=iid, email="zznext.s@test.local", rol="superadmin"))
    assert _fila(db_conn, "SELECT institucion_id, departamento_id FROM app_usuarios WHERE id = %s", [s["id"]]) == \
        {"institucion_id": None, "departamento_id": None}
    # duplicados y contraseñas
    _rechazo(lambda: saas.crear_usuario(superadmin, _user_payload(institucion_id=iid, email="ZZNEXT.UNO@test.local")),
             422, "Ya existe una cuenta con ese mail")
    _rechazo(lambda: saas.crear_usuario(superadmin, _user_payload(password="corta", password_confirmacion="corta")),
             422, "al menos 12 caracteres")
    _rechazo(lambda: saas.crear_usuario(superadmin, _user_payload(password="x" * 12, password_confirmacion="y" * 12)),
             422, "Las contraseñas no coinciden.")
    _rechazo(lambda: saas.crear_usuario(superadmin, _user_payload(email="zznext.mail@test.local",
                                                                  password="zznext.mail@test.local",
                                                                  password_confirmacion="zznext.mail@test.local")),
             422, "igual al mail")
    _rechazo(lambda: saas.crear_usuario(superadmin, _user_payload(institucion_id=987654321)), 422, "Institución")


def test_editar_usuario_coherencia_cupo_y_password(db_conn, saas, superadmin):
    iid = nueva_institucion(db_conn, "ZZNEXT Edit", max_usuarios=1)
    did = nuevo_departamento(db_conn, iid)
    otra = nueva_institucion(db_conn, "ZZNEXT Edit Otra", max_usuarios=1)
    uid = nuevo_usuario(db_conn, "zznext.edit@test.local", "usuario_departamento", iid, did)
    nuevo_usuario(db_conn, "zznext.ocupa@test.local", "usuario_departamento", otra)
    saas.editar_usuario(superadmin, _edit_payload(uid, institucion_id=iid, departamento_id=did, rol="solo_lectura"))
    assert scalar(db_conn, "SELECT rol FROM app_usuarios WHERE id = %s", [uid]) == "solo_lectura"
    _rechazo(lambda: saas.editar_usuario(superadmin, _edit_payload(uid, institucion_id=iid, departamento_id=1)), 422,
             "no pertenece")
    _rechazo(lambda: saas.editar_usuario(superadmin, _edit_payload(uid, institucion_id=otra)), 422, "cupo de 1")
    salt0 = scalar(db_conn, "SELECT salt FROM app_usuarios WHERE id = %s", [uid])
    _rechazo(lambda: saas.editar_usuario(superadmin, _edit_payload(uid, institucion_id=iid, password="corta")), 422,
             "12 caracteres")
    saas.editar_usuario(superadmin, _edit_payload(uid, institucion_id=iid, password=PWD + "x"))
    fila = _fila(db_conn, "SELECT salt, password_hash FROM app_usuarios WHERE id = %s", [uid])
    assert fila["salt"] != salt0 and core.verify_password(PWD + "x", fila["salt"], fila["password_hash"])
    _rechazo(lambda: saas.editar_usuario(superadmin, _edit_payload(uid, institucion_id=iid,
                                                                   email="zznext.ocupa@test.local")), 422,
             "Ya existe otra cuenta con ese mail.")
    _rechazo(lambda: saas.editar_usuario(superadmin, _edit_payload(uid, institucion_id=None)), 422,
             "deben tener institución")


def test_ultimo_superadmin_activo_d_ap4(db_conn, saas, auth_db, superadmin):
    yo = superadmin.user["id"]
    otros = [r[0] for r in db_conn.execute("SELECT id FROM app_usuarios WHERE rol='superadmin' AND estado='Activo' "
                                           "AND id <> %s", [yo]).fetchall()]
    for o in otros:  # dentro de la transacción del test (ROLLBACK): solo queda el actor
        _sql(db_conn, "UPDATE app_usuarios SET estado = 'Inactivo' WHERE id = %s", [o])
    msg = "Debe quedar al menos un superadmin activo"
    _rechazo(lambda: saas.estado_usuario(superadmin, {"usuario_id": yo, "estado": "Inactivo"}), 422, msg)
    _rechazo(lambda: saas.editar_usuario(superadmin, _edit_payload(yo, rol="coordinador_institucional",
                                                                   email=superadmin.user["email"], institucion_id=1)),
             422, msg)
    _rechazo(lambda: saas.editar_usuario(superadmin, _edit_payload(yo, rol="superadmin", estado="Inactivo",
                                                                   email=superadmin.user["email"])), 422, msg)
    _rechazo(lambda: saas.eliminar_usuario(superadmin, {"usuario_id": yo, "confirmado": True}), 422,
             "No podés eliminar tu propio usuario")
    s2 = nuevo_usuario(db_conn, "zznext.super@test.local", "superadmin")
    saas.estado_usuario(superadmin, {"usuario_id": s2, "estado": "Inactivo"})  # quedan activos: el actor
    saas.estado_usuario(superadmin, {"usuario_id": s2, "estado": "Activo"})
    saas.estado_usuario(superadmin, {"usuario_id": yo, "estado": "Inactivo"})  # queda s2 activo: permitido
    assert scalar(db_conn, "SELECT estado FROM app_usuarios WHERE id = %s", [yo]) == "Inactivo"
    s2_rec = sesion(auth_db, s2)[0]
    _rechazo(lambda: saas.eliminar_usuario(s2_rec, {"usuario_id": s2, "confirmado": True}), 422, "propio usuario")


def test_estado_y_eliminar_usuario(db_conn, saas, superadmin):
    iid = nueva_institucion(db_conn, "ZZNEXT Estado")
    uid = nuevo_usuario(db_conn, "zznext.estado@test.local", "usuario_departamento", iid)
    assert saas.estado_usuario(superadmin, {"usuario_id": uid, "estado": "Inactivo"})["mensaje"] == "Estado actualizado."
    _rechazo(lambda: saas.eliminar_usuario(superadmin, {"usuario_id": uid, "confirmado": False}), 422,
             "Primero confirmá la eliminación.")
    assert saas.eliminar_usuario(superadmin, {"usuario_id": uid, "confirmado": True})["mensaje"] == "Usuario eliminado."
    assert scalar(db_conn, "SELECT COUNT(*) FROM app_usuarios WHERE id = %s", [uid]) == 0
    _rechazo(lambda: saas.estado_usuario(superadmin, {"usuario_id": uid, "estado": "Activo"}), 422, "Usuario inexistente")
    ops = [e["operation"] for e in audit_saas(db_conn)]
    assert ops == [E.W_ESTADO_USUARIO, E.W_ELIMINAR_USUARIO]
    assert all(e["entity_id"] == str(uid) for e in audit_saas(db_conn))


def test_b12g_revoca_las_sesiones_afectadas(db_conn, saas, auth_db, superadmin):
    iid = nueva_institucion(db_conn, "ZZNEXT B12G")
    did = nuevo_departamento(db_conn, iid)
    casos = {
        "CREDENTIALS_CHANGED": lambda uid: saas.editar_usuario(superadmin, _edit_payload(
            uid, institucion_id=iid, departamento_id=did, email=f"zznext.b{uid}@test.local", password=PWD)),
        "IDENTITY_CHANGED": lambda uid: saas.editar_usuario(superadmin, _edit_payload(
            uid, institucion_id=iid, departamento_id=did, email=f"zznext.b{uid}@test.local", rol="solo_lectura")),
        "USER_INACTIVE": lambda uid: saas.estado_usuario(superadmin, {"usuario_id": uid, "estado": "Inactivo"}),
        "USER_DELETED": lambda uid: saas.eliminar_usuario(superadmin, {"usuario_id": uid, "confirmado": True}),
        "COMMERCIAL_BLOCKED": lambda uid: saas.bloquear(superadmin, {"institucion_id": iid}),
    }
    for motivo, accion in casos.items():
        saas.desbloquear(superadmin, {"institucion_id": iid})
        uid = nuevo_usuario(db_conn, f"zznext.b12g.{motivo.lower()}@test.local", "usuario_departamento", iid, did)
        _sql(db_conn, "UPDATE app_usuarios SET email = %s WHERE id = %s", [f"zznext.b{uid}@test.local", uid])
        record, token = sesion(auth_db, uid)
        accion(uid)
        with pytest.raises(SessionEnded) as exc:
            auth_db.validate(token)
        assert exc.value.reason == motivo


# ------------------------------------------------------------------------------------------ esquemas / HTTP
def test_esquemas_estrictos_sin_mass_assignment(saas, superadmin):
    for data in ({**_inst_payload(), "slug": "x"}, {**_inst_payload(), "id": 1}, {**_inst_payload(), "max_usuarios": "5"},
                 {**_inst_payload(), "max_usuarios": 0}, {**_inst_payload(), "max_usuarios": 501},
                 {**_inst_payload(), "plan": "Gratis"}, {**_inst_payload(), "estado": "Borrada"},
                 {**_inst_payload(), "fecha_vencimiento": "30/10/2026"}, {**_inst_payload(), "nombre": {"a": 1}},
                 {**_inst_payload(), "max_usuarios": True}):
        e = _rechazo(lambda: saas.crear_institucion(superadmin, data), 422)
        assert e.message == "La solicitud no es válida."
    for data in ({**_user_payload(), "rol": "root"}, {**_user_payload(), "salt": "x"},
                 {**_user_payload(), "password_hash": "x"}, {**_user_payload(), "institucion_id": "1"},
                 {**_user_payload(), "departamento_id": -3}, {**_user_payload(), "email": "a" * 400}):
        _rechazo(lambda: saas.crear_usuario(superadmin, data), 422, "La solicitud no es válida.")
    _rechazo(lambda: saas.excel(superadmin, {"tabla": "app_usuarios", "id": None}), 422)
    _rechazo(lambda: saas.excel(superadmin, {"tabla": "usuario", "id": None}), 422)


def test_http_csrf_sesion_respuestas_limpias(db_conn, http, auth_db):
    ids = ids_por_rol(db_conn)
    assert http.get("/saas").status_code == 401
    assert http.post("/saas/instituciones", json=_inst_payload(), headers=CSRF).status_code == 401
    _, token = sesion(auth_db, ids["superadmin"])
    http.cookies.set("deptit_session", token)
    r = http.get("/saas")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    for prohibido in ("salt", "password_hash", "sqlite_id", "source_db", "C:\\\\", "datos_instituciones"):
        assert prohibido not in r.text
    for ruta in ("/saas/instituciones", "/saas/usuarios", "/saas/usuarios/eliminar", "/saas/instituciones/eliminar",
                 "/saas/descargas/excel"):
        assert http.post(ruta, json={}).status_code == 403  # sin cabecera CSRF
    r = http.post("/saas/instituciones", json={**_inst_payload(), "nombre": "SELECT 1 FROM x"} | {"extra": "DROP"},
                  headers=CSRF)
    assert r.status_code == 422 and "DROP" not in r.text and "SELECT" not in r.text
    r = http.post("/saas/usuarios", json=_user_payload(email="zznext.http@test.local"), headers=CSRF)
    assert r.status_code == 200 and PWD not in r.text and "hash" not in r.text
    for ruta in ("/saas/update", "/saas/sql", "/saas/importar", "/saas/descargas/csv", "/saas/sesiones"):
        assert http.post(ruta, json={}, headers=CSRF).status_code in (404, 405)
    r = http.post("/saas/descargas/excel", json={"tabla": "usuarios", "id": None}, headers=CSRF)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    disp = r.headers["content-disposition"]
    assert "Administraci" in disp and "SaaS_" in disp and ".xlsx" in disp and "@" not in disp
    df = pd.read_excel(io.BytesIO(r.content), sheet_name="Datos")
    assert list(df.columns) == ["id", "institucion_id", "departamento_id", "nombre", "email", "rol", "estado",
                                "fecha_alta", "observaciones", "institucion", "departamento"]
    _, coord = sesion(auth_db, ids["coordinador_institucional"])
    http.cookies.set("deptit_session", coord)
    r = http.get("/saas")
    assert r.status_code == 403 and r.json()["error"]["message"] == T.MSG_SOLO_SUPERADMIN


def test_excel_de_las_8_tablas_sin_columnas_tecnicas(saas, superadmin, db_conn):
    for clave, ident in (("instituciones", None), ("departamentos", None), ("usuarios", None), ("uso", None),
                         ("institucion", 1), ("comercial", 2), ("departamento", 1),
                         ("usuario", superadmin.user["id"])):
        contenido, nombre = saas.excel(superadmin, {"tabla": clave, "id": ident})
        df = pd.read_excel(io.BytesIO(contenido), sheet_name="Datos")
        assert not df.empty and nombre.startswith("Administración_SaaS_") and nombre.endswith(".xlsx")
        assert not {"sqlite_id", "source_db", "slug", "salt", "password_hash"} & set(df.columns), clave


def test_errores_de_base_genericos(db_conn, auth_db, superadmin, audit_store):
    @contextmanager
    def rota():
        raise psycopg.OperationalError("connection to server at 10.0.0.1 failed: password authentication failed")
        yield  # noqa
    servicio = make_saas(auth_db, audit_store, db_conn, transaction=rota)
    e = _rechazo(lambda: servicio.overview(superadmin), 503)
    assert "10.0.0.1" not in e.message and "password" not in e.message
    e = _rechazo(lambda: servicio.crear_institucion(superadmin, _inst_payload()), 503)
    assert e.message.startswith("La base de datos devolvió un error") and "10.0.0.1" not in e.message
    assert audit_store.events[-1].error_code == "OperationalError"


# ------------------------------------------------------------------------------------------ concurrencia
def test_bloqueos_de_fila_serializan_cupo_superadmin_y_vaciedad(db_conn):
    """Estrategia sin B12I: el lock de fila tomado por un writer (transacción abierta) hace esperar al otro."""
    s = db.load_settings()
    with psycopg.connect(s["database_url"], application_name="deptit_next_tests_lock") as otra:
        db.verify_identity(otra)
        repo = E.Repo(db_conn)
        with savepoint(db_conn):
            E._controlar_cupo(repo, 5)  # FOR UPDATE de la institución 5 (sin escribir)
            otra.execute("SET lock_timeout = '300ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                otra.execute("SELECT id FROM instituciones WHERE id = 5 FOR UPDATE")
            otra.rollback()
        with savepoint(db_conn):
            E._controlar_ultimo_superadmin(repo, 0)
            otra.execute("SET lock_timeout = '300ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                otra.execute("SELECT id FROM app_usuarios WHERE rol='superadmin' AND estado='Activo' FOR UPDATE")
            otra.rollback()
        otra.rollback()


def test_estatico_sin_disco_sin_ddl_sin_secretos():
    base = os.path.join(os.path.dirname(__file__), "..", "saas")
    texto = "".join(open(os.path.join(base, f), encoding="utf-8").read() for f in os.listdir(base) if f.endswith(".py") and f != "textos.py")
    for prohibido in ("shutil", "os.remove", "rmtree", "sqlite3", "open(", "CREATE TABLE", "ALTER TABLE", "DROP ",
                      "TRUNCATE", "ON DELETE", "datos_instituciones", "tenant_db_path", "log.info(f", "print("):
        assert prohibido not in texto, prohibido
    assert "hash_password" in texto and "core.hash_password" in texto
    assert texto.count("pd.read_sql") == 0


# ------------------------------------------------------------------------------------------ utilidades
def _sql(conn, query, params=None):
    with savepoint(conn):
        conn.execute(query, params or [])


def _huella(conn):
    return conn.execute("SELECT (SELECT COUNT(*) FROM docentes), (SELECT COUNT(*) FROM designaciones), "
                        "(SELECT COUNT(*) FROM departamentos), (SELECT COUNT(*) FROM app_usuarios), "
                        "(SELECT COUNT(*) FROM carreras), (SELECT COUNT(*) FROM sedes_institucion)").fetchone()


def test_fixture_del_frontend_igual_a_los_textos_del_backend(saas, superadmin):
    """El test del frontend usa ``frontend/tests/fixtures/saas_ui.json``: debe ser exactamente lo que envía el backend."""
    import json
    ruta = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "tests", "fixtures", "saas_ui.json")
    with open(ruta, encoding="utf-8") as fh:
        fixture = json.load(fh)
    ov = saas.overview(superadmin)
    assert fixture == {"ui": json.loads(json.dumps(ov["ui"])), "catalogos": json.loads(json.dumps(ov["catalogos"]))}
