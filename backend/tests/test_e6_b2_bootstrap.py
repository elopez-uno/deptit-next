"""Etapa 6A-B2: bootstrap del primer superadmin y cuentas semilla (docs/ETAPA6_6AB2_OPERATION_RECOVERY.md).
El caso positivo REAL (base nueva desde el esquema base) esta en ``test_e6_b2_recuperacion_real.py``; aca: reglas,
transaccion con una conexion falsa y el rechazo real sobre deptit_next_dev (que ya tiene superadmins)."""

from __future__ import annotations

import io
import json
import re

import psycopg
import pytest

from auth import core
from operacion import bootstrap as BS

CLAVE = "Clave-Bootstrap-Segura-2026!"


class FakeConn:
    def __init__(self, usuarios=(), base="deptit_next_dev"):
        self.usuarios = list(usuarios)
        self.base = base
        self.sql = []
        self.commits = self.rollbacks = 0
        self.insertado = None

    def execute(self, sql, params=None):
        self.sql.append(sql)
        r = FakeCursor()
        if sql.startswith("SELECT current_database()"):
            r.rows = [(self.base,)]
        elif sql.startswith("SELECT email, rol, estado"):
            r.rows = [(u["email"], u["rol"], u["estado"]) for u in self.usuarios]
        elif sql.startswith("INSERT INTO app_usuarios"):
            self.insertado = params
            r.rows = [(77,)]
        elif sql.startswith("SELECT rol, estado, salt, password_hash"):
            p = self.insertado
            r.rows = [(p[4], p[7], p[5], p[6])]
        return r

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeCursor:
    rows = ()

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


def _prov(conn, email="ops@universidad.edu.ar", password=CLAVE, **kw):
    kw.setdefault("esperada", "deptit_next_dev")
    kw.setdefault("entorno", "desarrollo")
    return BS.provisionar(conn, email, password, "Operaciones", execute=True, today="2026-11-03", **kw)


@pytest.mark.parametrize("email,password,fragmento", [
    ("ops@universidad.edu.ar", "corta", "al menos 12"),
    ("ops@universidad.edu.ar", "", "falta la contraseña"),
    ("admin@local", CLAVE, "cuenta de prueba heredada"),
    ("Coordinador@Uno.Local", CLAVE, "cuenta de prueba heredada"),
    ("sin-arroba", CLAVE, "email invalido"),
    ("ops@universidad.edu.ar", "ops@universidad.edu.ar", "igual al email")])
def test_reglas_de_solicitud(email, password, fragmento):
    r = BS.provisionar(None, email, password, execute=True, esperada="x", entorno="desarrollo")
    assert r["result"] == "FAIL" and r["code"] == "INVALID_REQUEST" and fragmento in r["detail"], r
    assert password not in json.dumps(r) or not password


def test_contrasena_publica_heredada_rechazada():
    publicas = [p for p in ("admin123", "Admin123!", "deptit123", "coordinador123", "informatica123",
                            "Coordinador123!", "Informatica123!", "admin1234567", "Deptit2024!")
                if core.is_public_default_password(p)]
    for p in publicas:
        assert "publica" in BS.problemas_solicitud("ops@x.edu", p, "N")[-1] or BS.problemas_solicitud("ops@x.edu", p,
                                                                                                         "N")
    original = core.is_public_default_password
    core.is_public_default_password = lambda p: p == CLAVE
    try:
        assert "la contraseña es una credencial publica conocida" in BS.problemas_solicitud("ops@x.edu", CLAVE, "N")
    finally:
        core.is_public_default_password = original


def test_bootstrap_valido_con_hash_actual():
    conn = FakeConn(usuarios=[])
    r = _prov(conn)
    assert r["result"] == "PASS" and r["code"] == "PROVISIONED" and conn.commits == 1 and conn.rollbacks == 0, r
    inst, depto, nombre, email, rol, salt, digest, estado, fecha = conn.insertado
    assert (inst, depto, rol, estado, email) == (None, None, "superadmin", "Activo", "ops@universidad.edu.ar")
    assert re.fullmatch(r"[0-9a-f]{32}", salt) and digest.startswith("pbkdf2_sha256$600000$")
    assert core.verify_password(CLAVE, salt, digest) and not core.needs_rehash(digest)
    assert conn.sql[1] == "LOCK TABLE app_usuarios IN SHARE ROW EXCLUSIVE MODE"
    assert CLAVE not in json.dumps(r) and digest not in json.dumps(r) and salt not in json.dumps(r)


def test_segundo_bootstrap_rechazado_sin_escribir():
    for usuarios in ([{"email": "otro@x.edu", "rol": "superadmin", "estado": "Activo"}],
                     [{"email": "ops@universidad.edu.ar", "rol": "usuario", "estado": "Inactivo"}]):
        conn = FakeConn(usuarios=usuarios)
        r = _prov(conn)
        assert r["code"] == "ALREADY_PROVISIONED" and conn.insertado is None and conn.commits == 0, r
    conn = FakeConn(usuarios=[{"email": "viejo@x.edu", "rol": "superadmin", "estado": "Inactivo"}])
    assert _prov(conn)["code"] == "PROVISIONED"  # solo cuentan los superadmins ACTIVOS


@pytest.mark.parametrize("base,esperada,entorno,ok", [
    ("deptit", "deptit", "desarrollo", False), ("deptit_next_prod", "deptit_next_dev", "desarrollo", False),
    ("deptit_next_restore_test_x", "deptit_next_prod", "produccion", False),
    ("deptit_next_restore_test_x", "deptit_next_dev", "desarrollo", True),
    ("deptit_next_prod", "deptit_next_prod", "produccion", True), ("postgres", "postgres", "desarrollo", False)])
def test_base_incorrecta_rechazada(base, esperada, entorno, ok):
    conn = FakeConn(base=base)
    r = _prov(conn, esperada=esperada, entorno=entorno)
    assert (r["code"] == "PROVISIONED") is ok, r
    if not ok:
        assert r["code"] == "TARGET_REFUSED" and conn.insertado is None and conn.commits == 0


def test_dry_run_no_conecta():
    r = BS.provisionar(None, "ops@x.edu", CLAVE, "N", esperada="x", entorno="desarrollo")
    assert r["result"] == "PLANNED" and CLAVE not in json.dumps(r)


def test_cli_no_expone_la_contrasena(capsys, monkeypatch):
    from operacion import __main__ as cli
    conexiones = []

    def connect(dsn, **kw):
        conexiones.append(dsn)
        return _Ctx(FakeConn(usuarios=[]))
    rc = cli.main(["bootstrap-superadmin", "--email", "ops@x.edu", "--execute", "--password-stdin"],
                  stdin=io.StringIO(CLAVE + "\n"), connect=connect)
    salida = capsys.readouterr()
    assert rc == 0 and json.loads(salida.out)["code"] == "PROVISIONED"
    assert CLAVE not in salida.out and CLAVE not in salida.err and "pbkdf2_sha256$600000$" not in salida.out
    assert len(conexiones) == 1 and CLAVE not in conexiones[0]
    prompts = iter([CLAVE, CLAVE + "x"])
    rc = cli.main(["bootstrap-superadmin", "--email", "ops@x.edu", "--execute"], prompt=lambda _: next(prompts),
                  connect=connect)
    assert rc == 2 and json.loads(capsys.readouterr().out)["code"] == "PASSWORD_MISMATCH"


class _Ctx:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *a):
        return False


def test_real_dev_ya_provisionada_no_escribe():
    """deptit_next_dev real tiene superadmins activos: ALREADY_PROVISIONED y ROLLBACK (0 filas nuevas)."""
    import settings as S
    s = S.get()
    with psycopg.connect(s.db.conninfo, autocommit=False) as conn:
        antes = conn.execute("SELECT count(*), max(id) FROM app_usuarios").fetchone()
        conn.rollback()
        r = BS.provisionar(conn, "nuevo.superadmin@universidad.edu.ar", CLAVE, "Nuevo", esperada="deptit_next_dev",
                           entorno="desarrollo", execute=True)
        assert r["code"] == "ALREADY_PROVISIONED" and r["superadmins_activos"] >= 1, r
        assert conn.execute("SELECT count(*), max(id) FROM app_usuarios").fetchone() == antes
        conn.rollback()


def test_semillas_auditadas_en_dev():
    import settings as S
    with psycopg.connect(S.get().db.conninfo) as conn:
        conn.read_only = True
        r = BS.auditar_semillas(conn)
    assert r["semillas_presentes"] == sorted(BS.LEGACY_SEED_EMAILS) and r["ok_para_produccion"] is False
