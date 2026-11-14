"""Etapa 6A-B3: cuenta humana del piloto (``deptit-ops -Entorno preproduccion -Action cuenta-humana``).

Hallazgo del piloto humano: el email de la persona ya existia en ``deptit_next_preprod`` como cuenta HEREDADA de
desarrollo, desactivada por la siembra -> el alta respondia 422 (email existente).  Ahora:
* email inexistente               -> alta por Administracion SaaS (``POST /api/saas/usuarios``);
* cuenta heredada desactivada B3  -> la MISMA fila se reactiva por Administracion SaaS (``/usuarios/editar``): mismo id,
  una sola fila, Activo + superadmin + contraseña nueva, auditado;
* cualquier otra cuenta existente -> fail closed, nada se escribe.

Dos niveles:
1. Orquestacion de ``ops/preprod/piloto/cuenta_humana.py`` con dobles (sin red ni base): que llamadas hace cada camino,
   verificaciones posteriores y que la contraseña nunca aparece en el resultado.
2. REAL: backup de deptit_next_dev (solo lectura) -> base ``deptit_next_restore_test_*`` -> la MISMA transformacion de
   la siembra -> clasificacion (``operacion.preprod.clasificar_cuenta_humana``) + los writers REALES de Administracion
   SaaS con los payloads EXACTOS del script; ROLLBACK y DROP.  deptit_next_dev no se escribe."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest

from auth import core
from operacion import backup_db, config, preprod as P, restore_db as R

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ops" / "preprod" / "piloto"))
import cuenta_humana as CH  # noqa: E402

CLAVE = "Piloto-Humano-B3-clave-2026"
EMAIL = "persona.real@universidad.test"
CRED = {"ZZPILOT_AUTO_EMAIL": "zzpilotb3.automatizacion@pilot.invalid", "ZZPILOT_AUTO_PASSWORD": "auto-" + "x" * 20}


# ------------------------------------------------------------------------------------------ 1. orquestacion
class _Resp(SimpleNamespace):
    def json(self):
        return self.cuerpo


class _Cliente:
    """Doble del cliente HTTPS: registra cada request; respuestas segun el estado del ``_Mundo``."""

    def __init__(self, mundo):
        self.m, self.sesion = mundo, None

    def login(self, email, clave):
        self.m.llamadas.append(("login", email))
        ok = (email, clave) in self.m.credenciales
        self.sesion = email if ok else None
        return _Resp(status=200 if ok else 401, cuerpo={})

    def logout(self):
        self.m.llamadas.append(("logout", self.sesion))
        self.sesion = None
        return _Resp(status=204, cuerpo=None)

    def me(self):
        if not self.sesion:
            return _Resp(status=401, cuerpo={})
        fila = self.m.filas[self.sesion]
        return _Resp(status=200, cuerpo={"usuario": {"email": self.sesion, "rol": fila["rol"]}})

    def get(self, path):
        self.m.llamadas.append(("GET", path))
        if path == "/api/auth/context/options":
            return _Resp(status=200, cuerpo={"instituciones": [{"id": 1}]})
        assert path == "/api/saas"
        return _Resp(status=200, cuerpo={"usuarios": [{"email": e, **f} for e, f in self.m.filas.items()]})

    def post(self, path, body):
        self.m.llamadas.append(("POST", path, {k: v for k, v in body.items() if "password" not in k}))
        assert self.sesion == CRED["ZZPILOT_AUTO_EMAIL"]
        if path == "/api/saas/usuarios":
            self.m.filas[body["email"]] = {"id": 900, "nombre": body["nombre"], "rol": body["rol"],
                                           "estado": body["estado"], "observaciones": body["observaciones"]}
        else:
            assert path == "/api/saas/usuarios/editar"
            fila = next(f for f in self.m.filas.values() if f["id"] == body["usuario_id"])
            fila.update(rol=body["rol"], estado=body["estado"], observaciones=body["observaciones"])
        self.m.credenciales.add((body["email"], body["password"]))
        return _Resp(status=200, cuerpo={"ok": True})


class _Mundo:
    def __init__(self, filas):
        self.filas = filas
        self.llamadas = []
        self.credenciales = {(CRED["ZZPILOT_AUTO_EMAIL"], CRED["ZZPILOT_AUTO_PASSWORD"])}

    def clasificar(self, email):
        f = self.filas.get(email)
        if f is None:
            return {"clasificacion": CH.INEXISTENTE}
        base = {"id": f["id"], "nombre": f["nombre"], "rol_actual": f["rol"], "estado_actual": f["estado"]}
        if f["estado"] != "Inactivo":
            return {"clasificacion": CH.NO_ELEGIBLE, "motivo": "NO_INACTIVA", **base}
        if not f.get("b3"):
            return {"clasificacion": CH.NO_ELEGIBLE, "motivo": "CREDENCIAL_NO_DESHABILITADA_POR_B3", **base}
        return {"clasificacion": CH.HEREDADA, **base}

    def ejecutar(self):
        return CH.ejecutar(EMAIL, "Persona Real", CLAVE, cred=CRED, clasificar=self.clasificar,
                           nuevo_cliente=lambda: _Cliente(self))

    def escrituras(self):
        return [c for c in self.llamadas if c[0] == "POST"]


def test_email_inexistente_crea_por_saas():
    m = _Mundo({})
    r = m.ejecutar()
    assert r["result"] == "PASS" and r["code"] == "CREATED" and r["camino"] == CH.INEXISTENTE
    assert [c[1] for c in m.escrituras()] == ["/api/saas/usuarios"]
    assert r["verificacion"] == {"login_https": 200, "me_email": True, "me_rol": "superadmin", "logout": 204,
                                 "me_tras_logout": 401}
    assert CLAVE not in json.dumps(r)


def test_email_heredado_desactivado_reactiva_la_misma_fila_sin_duplicar():
    nota = P.NOTA_CUENTA
    m = _Mundo({EMAIL: {"id": 37, "nombre": "Nombre Heredado", "rol": "usuario_departamento", "estado": "Inactivo",
                        "observaciones": nota, "b3": True}})
    r = m.ejecutar()
    assert r["result"] == "PASS" and r["code"] == "REACTIVATED" and r["id"] == 37, r
    (post,) = m.escrituras()  # una sola escritura y es la EDICION (nunca un alta)
    assert post[1] == "/api/saas/usuarios/editar"
    assert post[2] == {"usuario_id": 37, "institucion_id": None, "departamento_id": None, "nombre": "Nombre Heredado",
                       "email": EMAIL, "rol": "superadmin", "estado": "Activo",
                       "observaciones": f"{nota} {CH.NOTA_REACTIVADA}"}
    assert list(m.filas) == [EMAIL] and m.filas[EMAIL]["id"] == 37 and m.filas[EMAIL]["rol"] == "superadmin"
    assert ("login", EMAIL) in m.llamadas and CLAVE not in json.dumps(r)


@pytest.mark.parametrize("fila", [
    {"id": 5, "nombre": "x", "rol": "superadmin", "estado": "Activo", "observaciones": "", "b3": True},
    {"id": 6, "nombre": "x", "rol": "usuario_departamento", "estado": "Inactivo", "observaciones": "", "b3": False},
])
def test_cuenta_existente_no_elegible_fail_closed(fila):
    m = _Mundo({EMAIL: dict(fila)})
    antes = json.dumps(m.filas, sort_keys=True)
    r = m.ejecutar()
    assert r["result"] == "FAIL" and r["code"] == "ACCOUNT_NOT_ELIGIBLE"
    assert m.llamadas == [] and json.dumps(m.filas, sort_keys=True) == antes  # ni login ni escrituras


def test_la_api_debe_confirmar_la_fila_antes_de_reactivar():
    """Segunda confirmacion: si el listado de Administracion SaaS no muestra esa fila Inactiva con ese email, no se
    escribe (p. ej. la fila cambio entre la clasificacion y la escritura)."""
    m = _Mundo({EMAIL: {"id": 37, "nombre": "x", "rol": "usuario_departamento", "estado": "Inactivo",
                        "observaciones": "", "b3": True}})
    original = _Cliente.get

    def get(self, path):
        r = original(self, path)
        if path == "/api/saas":
            r.cuerpo["usuarios"][0]["estado"] = "Activo"
        return r
    _Cliente.get = get
    try:
        r = m.ejecutar()
    finally:
        _Cliente.get = original
    assert r["code"] == "ACCOUNT_NOT_ELIGIBLE" and r["motivo"] == "API_NO_CONFIRMA" and m.escrituras() == []


# ------------------------------------------------------------------------------------------ 2. real
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


@pytest.fixture(scope="module")
def dev(tmp_path_factory):
    c = config.load()
    assert c.backup is not None and c.restore is not None, "faltan los roles operativos en backend/.env.ops"
    d = tmp_path_factory.mktemp("b3_cuenta_humana_backup")
    c = dataclasses.replace(c, backup_dir=d, env={**c.env, "DEPTIT_BACKUP_DIR": str(d)})
    rep = backup_db.respaldar(c)
    assert rep["result"] == "PASS", rep
    yield c, Path(rep["manifest"])
    assert R.bases_de_prueba(c) == []


def test_real_clasificacion_y_writers_saas_sobre_base_transformada(dev):
    from saas.service import SaasService
    from saas_support import Clock, FakeAuditStore, _PoolDB, savepoint, sesion
    from auth.repository import AuthRepository
    from auth.service import AuthService

    c, manifest = dev
    target = f"deptit_next_restore_test_b3humana_{NOW.strftime('%H%M%S')}"
    r = R.restaurar(c, manifest, target=target, execute=True, confirm=target, drop_after=False,
                    comparar_con_origen=False)
    assert r["result"] == "PASS", json.dumps(r, default=str)[:2000]
    try:
        with psycopg.connect(c.url(c.restore, target), autocommit=False) as conn:
            filas = conn.execute("SELECT id, email, rol FROM app_usuarios ORDER BY id").fetchall()
            P.desactivar_cuentas_heredadas(conn)  # la MISMA transformacion de la siembra

            def k(email):
                return P.clasificar_cuenta_humana(conn, email, base_esperada=target)
            with pytest.raises(ValueError):  # por defecto, solo deptit_next_preprod
                P.clasificar_cuenta_humana(conn, filas[0][1])
            actor_id = next(i for i, _, rol in filas if rol == "superadmin")
            uid, email, _ = next(f for f in filas if f[2] != "superadmin")
            antes = k(email.upper())  # sin distinguir mayusculas
            assert antes["clasificacion"] == P.CUENTA_HEREDADA and antes["id"] == uid
            assert antes["estado_actual"] == "Inactivo"
            nuevo = "zzpilotb3.persona.nueva@pilot.invalid"
            assert k(nuevo) == {"clasificacion": P.CUENTA_INEXISTENTE}
            assert "pbkdf2" not in json.dumps(antes) and P.HASH_DESHABILITADO not in json.dumps(antes)
            # casos que NO se tocan (cada uno en un savepoint revertido)
            for sql_, motivo in (("UPDATE app_usuarios SET estado = 'Activo' WHERE id = %s", "NO_INACTIVA"),
                                 ("UPDATE app_usuarios SET password_hash = 'otro' WHERE id = %s",
                                  "CREDENCIAL_NO_DESHABILITADA_POR_B3"),
                                 ("UPDATE app_usuarios SET observaciones = '' WHERE id = %s", "SIN_NOTA_DE_LA_SIEMBRA_B3")):
                with pytest.raises(_Revertir):
                    with conn.transaction():
                        conn.execute(sql_, (uid,))
                        assert k(email)["motivo"] == motivo
                        raise _Revertir
            assert k(email)["clasificacion"] == P.CUENTA_HEREDADA

            # actor: superadmin de automatizacion (en preprod, la cuenta del bootstrap); aca, una semilla reactivada
            conn.execute("UPDATE app_usuarios SET estado = 'Activo' WHERE id = %s", (actor_id,))
            auth = AuthService(AuthRepository(_PoolDB(conn)), clock=Clock())
            audit = FakeAuditStore()
            saas = SaasService(None, auth, audit, transaction=lambda: savepoint(conn))
            actor = sesion(auth, actor_id)[0]
            n_antes = conn.execute("SELECT count(*) FROM app_usuarios").fetchone()[0]
            audit_antes = {r[0] for r in conn.execute("SELECT audit_id::text FROM b12h_audit_log").fetchall()}

            # camino HEREDADA: payload EXACTO del script -> writer real de edicion
            fila_api = next(u for u in saas.overview(actor)["usuarios"] if u["id"] == uid)
            assert fila_api["email"].lower() == email.lower() and fila_api["estado"] == "Inactivo"
            saas.editar_usuario(actor, CH.payload_reactivacion(uid, email.lower(), fila_api["nombre"],
                                                               fila_api["observaciones"], CLAVE))
            row = conn.execute("SELECT id, estado, rol, institucion_id, departamento_id, salt, password_hash, "
                               "observaciones FROM app_usuarios WHERE lower(email) = lower(%s)", (email,)).fetchall()
            assert len(row) == 1 and row[0][:5] == (uid, "Activo", "superadmin", None, None)
            assert row[0][6] != P.HASH_DESHABILITADO and core.verify_password(CLAVE, row[0][5], row[0][6])
            assert P.NOTA_CUENTA in row[0][7] and CH.NOTA_REACTIVADA in row[0][7]
            despues = k(email)
            assert (despues["motivo"], despues["id"], despues["rol_actual"]) == ("NO_INACTIVA", uid, "superadmin")
            # camino INEXISTENTE: alta real
            saas.crear_usuario(actor, CH.payload_alta(nuevo, "Persona Nueva", CLAVE, 1))
            alta = k(nuevo)
            assert (alta["motivo"], alta["rol_actual"], alta["estado_actual"]) == ("NO_INACTIVA", "superadmin", "Activo")
            assert conn.execute("SELECT count(*) FROM app_usuarios").fetchone()[0] == n_antes + 1  # solo el alta
            # auditado (B12H, acoplado a la misma transaccion): edicion de ESA fila y el alta; sin la contraseña
            ev = [e for e in conn.execute("SELECT audit_id::text, operation, entity_id, outcome, actor_user_id, "
                                          "metadata::text FROM b12h_audit_log").fetchall() if e[0] not in audit_antes]
            assert len(ev) == 2 and all(e[3] == "SUCCESS" and e[4] == actor_id for e in ev), ev
            assert str(uid) in {str(e[2]) for e in ev}  # la edicion quedo registrada sobre ESA fila
            assert CLAVE not in json.dumps(ev, default=str) and audit.events == []
            conn.rollback()
    finally:
        assert R._cleanup(c, True, target, True, target, subprocess.run,
                          lambda n, path=None: f"{path}\\{n}.exe")["dropped"] is True


class _Revertir(Exception):
    pass
