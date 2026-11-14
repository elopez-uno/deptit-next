"""Diferencial de los 12 writers de Administración SaaS: el writer CERTIFICADO (entry l. 2931-3336, ejecutado desde
``reference_fix02`` con su conexión ``auth``) y el writer NEXT corren sobre los MISMOS datos sintéticos, cada uno en un
SAVEPOINT que se revierte (``aislado``), y se comparan las filas resultantes.

A. EQUIVALENCIA: mismo efecto en la base (salvo ``id`` y, en contraseñas, ``salt``/``password_hash`` aleatorios, que
   se verifican con PBKDF2).
B. HARDENING APROBADO (D-AP1/D-AP2/D-AP4/D-AP7): el certificado hace X (oráculo medido aquí) y NEXT hace Y por decisión;
   no es un fallo diferencial.
Ningún dato real se modifica: todo ocurre dentro de la transacción del test (ROLLBACK)."""

from __future__ import annotations

import inspect

import pytest

from auth import core
from saas import escrituras as E
from saas.service import SaasError
from saas_support import SUPER, nueva_institucion, nuevo_departamento, nuevo_usuario, render, savepoint, scalar
from saas_support import audit_store, auth_db, db_conn, saas, superadmin  # noqa: F401  (fixtures)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")
PWD = "Zznext-clave-segura-2026"


@pytest.fixture
def cert(db_conn):
    return render(db_conn, SUPER, {"superadmin_institucion_id": 1}).ns


class _Revertir(Exception):
    pass


def aislado(conn, fn):
    """Ejecuta ``fn`` y toma la foto en un SAVEPOINT que se revierte: devuelve (resultado|excepción, foto)."""
    out = {}
    try:
        with conn.transaction():
            try:
                out["r"] = fn()
            except Exception as exc:  # noqa: BLE001  (se compara el rechazo)
                out["r"] = exc
            out["foto"] = foto(conn)
            raise _Revertir
    except _Revertir:
        pass
    return out["r"], out["foto"]


def foto(conn) -> dict:
    def filas(sql):
        with conn.cursor() as cur:
            cur.execute(sql)
            return [tuple(r) for r in cur.fetchall()]
    return {
        "inst": filas("SELECT nombre, slug, max_usuarios, estado, plan, fecha_alta, fecha_vencimiento, estado_pago, "
                      "suscripcion, fecha_ultima_actualizacion_comercial, observaciones FROM instituciones "
                      "WHERE nombre LIKE 'ZZNEXT%' ORDER BY nombre"),
        "deps": filas("SELECT i.nombre, d.nombre, d.slug, d.estado, d.observaciones FROM departamentos d JOIN "
                      "instituciones i ON i.id = d.institucion_id WHERE d.nombre LIKE 'ZZNEXT%' ORDER BY 1, 2"),
        "users": filas("SELECT email, nombre, rol, estado, institucion_id, departamento_id, fecha_alta, observaciones "
                       "FROM app_usuarios WHERE email LIKE 'zznext%' ORDER BY email"),
        "docentes": filas("SELECT COUNT(*) FROM docentes"),
        "creds": filas("SELECT email, salt, password_hash FROM app_usuarios WHERE email LIKE 'zznext%' ORDER BY email"),
    }


def _sin_creds(f):
    return {k: v for k, v in f.items() if k != "creds"}


def _ambos(db_conn, certificado, nuevo):
    rc, fc = aislado(db_conn, certificado)
    rn, fn = aislado(db_conn, nuevo)
    return rc, fc, rn, fn


# ------------------------------------------------------------------------------------------ A. equivalencia
def test_a_instituciones_alta_cupo_comercial_estado(db_conn, cert, saas, superadmin):
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["crear_institucion_auth"](
        "ZZNEXT Alta", 7, "Profesional", "obs", "2027-01-31", "Pendiente", "Prueba", "Activa"),
        lambda: saas.crear_institucion(superadmin, {"nombre": "ZZNEXT Alta", "max_usuarios": 7, "plan": "Profesional",
                                                    "fecha_vencimiento": "2027-01-31", "estado_pago": "Pendiente",
                                                    "suscripcion": "Prueba", "estado": "Activa",
                                                    "observaciones": "obs"}))
    assert not isinstance(rc, Exception) and not isinstance(rn, Exception)
    assert fc == fn and len(fc["inst"]) == 1
    iid = nueva_institucion(db_conn, "ZZNEXT Comercial")
    for c, n in ((lambda: cert["actualizar_cupo_institucion"](iid, 11),
                  lambda: saas.actualizar_cupo(superadmin, {"institucion_id": iid, "max_usuarios": 11})),
                 (lambda: cert["actualizar_comercial_institucion"](iid, "Enterprise", 9, "", "Vencido", "Activa",
                                                                   "Solo lectura", "zz"),
                  lambda: saas.actualizar_comercial(superadmin, {"institucion_id": iid, "plan": "Enterprise",
                                                                 "max_usuarios": 9, "fecha_vencimiento": "",
                                                                 "estado_pago": "Vencido", "suscripcion": "Activa",
                                                                 "estado": "Solo lectura", "observaciones": "zz"})),
                 (lambda: cert["cambiar_estado_institucion_auth"](iid, "Bloqueada"),
                  lambda: saas.bloquear(superadmin, {"institucion_id": iid})),
                 (lambda: cert["cambiar_estado_institucion_auth"](iid, "Activa"),
                  lambda: saas.desbloquear(superadmin, {"institucion_id": iid}))):
        rc, fc, rn, fn = _ambos(db_conn, c, n)
        assert fc == fn


def test_a_departamentos_alta_edicion_y_baja_de_vacio(db_conn, cert, saas, superadmin):
    iid = nueva_institucion(db_conn, "ZZNEXT Deps")
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["crear_departamento_auth"](iid, "ZZNEXT Física", "o"),
                            lambda: saas.crear_departamento(superadmin, {"institucion_id": iid,
                                                                         "nombre": "ZZNEXT Física", "observaciones": "o"}))
    assert fc == fn and len(fc["deps"]) == 1
    did = nuevo_departamento(db_conn, iid, "ZZNEXT Química")
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["actualizar_departamento_auth"](did, "ZZNEXT Biología", "Inactivo", "x"),
                            lambda: saas.editar_departamento(superadmin, {"departamento_id": did,
                                                                          "nombre": "ZZNEXT Biología",
                                                                          "estado": "Inactivo", "observaciones": "x"}))
    assert fc == fn
    # duplicado: mismo rechazo funcional
    otro = nuevo_departamento(db_conn, iid, "ZZNEXT Otro")
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["actualizar_departamento_auth"](otro, "zznext química"),
                            lambda: saas.editar_departamento(superadmin, {"departamento_id": otro,
                                                                          "nombre": "zznext química",
                                                                          "estado": "Activo", "observaciones": ""}))
    assert str(rc) in rn.message and fc == fn
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["eliminar_departamento_auth"](did, eliminar_base=True),
                            lambda: saas.eliminar_departamento(superadmin, {"departamento_id": did, "confirmado": True}))
    assert fc == fn and not [d for d in fc["deps"] if d[1] == "ZZNEXT Química"]


def test_a_baja_de_institucion_vacia(db_conn, cert, saas, superadmin):
    iid = nueva_institucion(db_conn, "ZZNEXT Vacía")
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["eliminar_institucion_auth"](iid, eliminar_datos=False),
                            lambda: saas.eliminar_institucion(superadmin, {"institucion_id": iid, "confirmado": True,
                                                                           "texto": "ELIMINAR"}))
    assert fc == fn and not [i for i in fc["inst"] if i[0] == "ZZNEXT Vacía"]


def test_a_usuarios_alta_edicion_estado_baja(db_conn, cert, saas, superadmin):
    iid = nueva_institucion(db_conn, "ZZNEXT Usuarios")
    did = nuevo_departamento(db_conn, iid)
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["crear_usuario_auth"](iid, did, "ZZNEXT U", " ZZNEXT.U@test.local ",
                                                                        "usuario_departamento", PWD, "Activo", "o"),
                            lambda: saas.crear_usuario(superadmin, {
                                "institucion_id": iid, "departamento_id": did, "nombre": "ZZNEXT U",
                                "email": " ZZNEXT.U@test.local ", "rol": "usuario_departamento", "password": PWD,
                                "password_confirmacion": PWD, "estado": "Activo", "observaciones": "o"}))
    assert _sin_creds(fc) == _sin_creds(fn) and len(fc["users"]) == 1
    for f in (fc, fn):  # mismo PBKDF2 certificado (salt aleatorio en ambos)
        email, salt, h = f["creds"][0]
        assert len(salt) == 32 and core.verify_password(PWD, salt, h)
    uid = nuevo_usuario(db_conn, "zznext.e@test.local", "usuario_departamento", iid, did)
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["actualizar_usuario_auth"](uid, iid, did, "ZZNEXT E2", "zznext.e2@test.local",
                                                                             "solo_lectura", "Activo", "x", ""),
                            lambda: saas.editar_usuario(superadmin, {
                                "usuario_id": uid, "institucion_id": iid, "departamento_id": did, "nombre": "ZZNEXT E2",
                                "email": "zznext.e2@test.local", "rol": "solo_lectura", "estado": "Activo",
                                "observaciones": "x", "password": ""}))
    assert fc == fn
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["cambiar_estado_usuario_auth"](uid, "Inactivo"),
                            lambda: saas.estado_usuario(superadmin, {"usuario_id": uid, "estado": "Inactivo"}))
    assert fc == fn
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["eliminar_usuario_auth"](uid),
                            lambda: saas.eliminar_usuario(superadmin, {"usuario_id": uid, "confirmado": True}))
    assert fc == fn and not [u for u in fc["users"] if u[0] == "zznext.e@test.local"]
    # cupo agotado al CREAR: mismo rechazo
    llena = nueva_institucion(db_conn, "ZZNEXT Llena", max_usuarios=1)
    nuevo_usuario(db_conn, "zznext.ocupa@test.local", "usuario_departamento", llena)
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["crear_usuario_auth"](llena, None, "Z", "zznext.z@test.local",
                                                                        "usuario_departamento", PWD),
                            lambda: saas.crear_usuario(superadmin, {
                                "institucion_id": llena, "departamento_id": None, "nombre": "Z",
                                "email": "zznext.z@test.local", "rol": "usuario_departamento", "password": PWD,
                                "password_confirmacion": PWD, "estado": "Activo", "observaciones": ""}))
    assert isinstance(rc, ValueError) and str(rc) in rn.message and fc == fn


# ------------------------------------------------------------------------------------------ B. hardening aprobado
def test_b_d_ap1_d_ap2_certificado_borra_en_cascada_next_rechaza(db_conn, cert, saas, superadmin):
    iid = nueva_institucion(db_conn, "ZZNEXT Con datos")
    did = nuevo_departamento(db_conn, iid)
    with savepoint(db_conn):
        db_conn.execute("INSERT INTO docentes (cuil, nombre, institucion_id, departamento_id) VALUES "
                        "('20-99999999-1', 'ZZNEXT', %s, %s)", [iid, did])
    antes = foto(db_conn)
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["eliminar_institucion_auth"](iid, eliminar_datos=False),
                            lambda: saas.eliminar_institucion(superadmin, {"institucion_id": iid, "confirmado": True,
                                                                           "texto": "ELIMINAR"}))
    assert fc["docentes"][0][0] == antes["docentes"][0][0] - 1  # certificado: CASCADE borró el docente
    assert not [i for i in fc["inst"] if i[0] == "ZZNEXT Con datos"]
    assert isinstance(rn, SaasError) and "contiene datos" in rn.message and fn == antes  # NEXT: nada borrado
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["eliminar_departamento_auth"](did, eliminar_base=True),
                            lambda: saas.eliminar_departamento(superadmin, {"departamento_id": did, "confirmado": True}))
    assert fc["docentes"][0][0] == antes["docentes"][0][0] - 1
    assert isinstance(rn, SaasError) and fn == antes


def test_b_d_ap4_cross_tenant_cupo_y_ultimo_superadmin(db_conn, cert, saas, superadmin):
    iid = nueva_institucion(db_conn, "ZZNEXT Tenant", max_usuarios=1)
    payload = {"institucion_id": iid, "departamento_id": 1, "nombre": "Z", "email": "zznext.ct@test.local",
               "rol": "usuario_departamento", "password": PWD, "password_confirmacion": PWD, "estado": "Activo",
               "observaciones": ""}
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["crear_usuario_auth"](iid, 1, "Z", "zznext.ct@test.local",
                                                                        "usuario_departamento", PWD),
                            lambda: saas.crear_usuario(superadmin, payload))
    assert fc["users"][0][4:6] == (iid, 1)  # certificado: usuario de la inst sintética con el depto 1 (otra inst)
    assert isinstance(rn, SaasError) and "no pertenece" in rn.message and fn["users"] == []
    # superadmin con departamento: el alta certificada lo guardaba; NEXT lo anula (regla de la edición)
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["crear_usuario_auth"](iid, 1, "S", "zznext.sa@test.local",
                                                                        "superadmin", PWD),
                            lambda: saas.crear_usuario(superadmin, {**payload, "email": "zznext.sa@test.local",
                                                                    "rol": "superadmin"}))
    assert fc["users"][0][4:6] == (None, 1) and fn["users"][0][4:6] == (None, None)
    # activar por encima del cupo: el certificado lo permite, NEXT no
    nuevo_usuario(db_conn, "zznext.ocupa@test.local", "usuario_departamento", iid)
    ina = nuevo_usuario(db_conn, "zznext.ina@test.local", "usuario_departamento", iid, estado="Inactivo")
    rc, fc, rn, fn = _ambos(db_conn, lambda: cert["cambiar_estado_usuario_auth"](ina, "Activo"),
                            lambda: saas.estado_usuario(superadmin, {"usuario_id": ina, "estado": "Activo"}))
    activos = lambda f: len([u for u in f["users"] if u[3] == "Activo" and u[4] == iid])  # noqa: E731
    assert activos(fc) == 2 and isinstance(rn, SaasError) and "cupo" in rn.message and activos(fn) == 1
    # último superadmin: el certificado deja 0 activos; NEXT no
    yo = superadmin.user["id"]
    with savepoint(db_conn):
        db_conn.execute("UPDATE app_usuarios SET estado = 'Inactivo' WHERE rol = 'superadmin' AND id <> %s", [yo])
    cuenta = "SELECT COUNT(*) FROM app_usuarios WHERE rol = 'superadmin' AND estado = 'Activo'"
    rc, _, rn, _ = _ambos(db_conn, lambda: (cert["cambiar_estado_usuario_auth"](yo, "Inactivo"), scalar(db_conn, cuenta))[1],
                          lambda: saas.estado_usuario(superadmin, {"usuario_id": yo, "estado": "Inactivo"}))
    assert rc == 0 and isinstance(rn, SaasError) and "al menos un superadmin" in rn.message


def test_b_d_ap7_entity_id_de_las_altas(cert):
    """Oráculo B12H certificado (``_entity_param``): las altas de usuario/departamento registraban la INSTITUCIÓN y el
    alta de institución no tenía entity_id; NEXT registra el id creado (verificado en test_saas_service)."""
    from deptit_refactor.b12h.audit_actor import _entity_param
    assert _entity_param(inspect.signature(cert["crear_usuario_auth"]), "usuario") == "institucion_id"
    assert _entity_param(inspect.signature(cert["crear_departamento_auth"]), "departamento") == "institucion_id"
    assert _entity_param(inspect.signature(cert["crear_institucion_auth"]), "institucion") is None
    for w, esperado in ((E.W_CUPO, "institucion_id"), (E.W_ACTUALIZAR_DEPARTAMENTO, "departamento_id"),
                        (E.W_ACTUALIZAR_USUARIO, "usuario_id"), (E.W_ELIMINAR_USUARIO, "usuario_id"),
                        (E.W_ELIMINAR_INSTITUCION, "institucion_id")):
        from saas.service import SPECS
        etiqueta = SPECS[w].entity_type
        assert _entity_param(inspect.signature(cert[w]), etiqueta) == esperado == SPECS[w].entity_param


def test_registro_b10_identico_al_certificado():
    from deptit_refactor.security.legacy_write_actions import BUSINESS_WRITERS
    from saas.service import SPECS
    assert set(SPECS) == set(E.WRITERS) and len(SPECS) == 12
    for w, spec in SPECS.items():
        cert_action = BUSINESS_WRITERS[w]
        assert (spec.action.domain, spec.action.operation, spec.action.scope) == \
            (cert_action.domain, cert_action.operation, cert_action.scope)
