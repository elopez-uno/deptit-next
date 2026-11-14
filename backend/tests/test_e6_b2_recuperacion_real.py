"""Etapa 6A-B2: recuperacion REAL de punta a punta con los roles operativos de desarrollo (``backend/.env.ops``):

1. backup completo de deptit_next_dev con ``deptit_next_backup`` (en un directorio temporal);
2. restore a ``deptit_next_restore_test_pytest_*`` con ``deptit_next_restore`` + comparacion semantica con el origen
   (esquema + contenido de TODAS las tablas) + DROP de la base de prueba;
3. esquema base versionado aplicado a una base de prueba VACIA, bootstrap del primer superadmin alli (hash B1),
   segundo bootstrap rechazado, DROP;
4. ninguna base ``deptit_next_restore_test_*`` queda en el servidor.

Requiere los roles operativos (``migration/db_setup/03_create_ops_roles.template.sql``): sin ellos el test FALLA (no
se omite): la recuperacion es parte del contrato del bloque."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import subprocess

import psycopg
import pytest

from integraciones.ciclo_periodos.ref_b11.db_identity import identity_from_url, libpq_environment
from operacion import backup_db, bootstrap, config, esquema, restore_db as R

CLAVE = "Clave-Bootstrap-Prueba-Real-2026!"


@pytest.fixture(scope="module")
def cfg(tmp_path_factory):
    c = config.load()
    assert c.backup is not None and c.restore is not None, "faltan los roles operativos en backend/.env.ops"
    d = tmp_path_factory.mktemp("b2_real")
    yield dataclasses.replace(c, backup_dir=d, env={**c.env, "DEPTIT_BACKUP_DIR": str(d)})
    assert R.bases_de_prueba(c) == []


def _sufijo() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S%f")


def _createdb(cfg, nombre):
    with libpq_environment(identity_from_url(cfg.url(cfg.restore, "postgres")), cfg.restore.password,
                           {"PGSSLMODE": cfg.app.db.sslmode}) as env:
        exe = f"{cfg.pg_bin_dir}\\createdb.exe"
        p = subprocess.run(R.createdb_command(exe, nombre, "postgres"), env=env, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-500:]


def _dropdb(cfg, nombre):
    which = lambda name, path=None: f"{path}\\{name}.exe"  # noqa: E731
    return R._cleanup(cfg, True, nombre, True, nombre, subprocess.run, which)


def test_backup_completo_restore_y_comparacion(cfg):
    rep = backup_db.respaldar(cfg)
    assert rep["result"] == "PASS", rep
    assert rep["backup_user"] == "deptit_next_backup" and rep["conexion"]["tablas"] >= 58
    m = json.loads(open(rep["manifest"], encoding="utf-8").read())
    assert m["database"]["user"] == "deptit_next_backup" and m["dump"]["tables"] == rep["conexion"]["tablas"]
    target = f"deptit_next_restore_test_pytest_{_sufijo()}"
    r = R.restaurar(cfg, rep["manifest"], target=target, execute=True, drop_after=True, confirm=target)
    assert r["result"] == "PASS" and r["code"] == "RESTORE_VERIFIED", json.dumps(r, default=str)[:3000]
    comp = r["comparacion"]
    assert comp["equivalentes"] and comp["diferencias"] == []
    assert comp["origen"]["tablas"] == comp["destino"]["tablas"] >= 58
    assert comp["origen"]["datos_sha256"] == comp["destino"]["datos_sha256"]
    assert comp["origen"]["esquema_sha256"] == comp["destino"]["esquema_sha256"] == m["deptit"]["esquema_sha256"]
    assert r["checks"]["app_usuarios"]["accounts"] == 9 and r["checks"]["objetos_de_otro_owner"] == 0
    assert r["cleanup"]["dropped"] is True
    assert target not in R.bases_de_prueba(cfg)


def test_esquema_base_y_bootstrap_en_base_nueva(cfg):
    chk = esquema.verificar_archivo()
    assert chk["ok"], chk
    texto = (esquema.SCHEMA_DIR / esquema.BASELINE).read_text(encoding="utf-8")
    assert not any(e in texto for e in bootstrap.LEGACY_SEED_EMAILS) and "pbkdf2" not in texto
    target = f"deptit_next_restore_test_pytest_{_sufijo()}"
    _createdb(cfg, target)
    try:
        r = esquema.aplicar_en_prueba(cfg, target)
        assert r["result"] == "PASS" and r["filas"] == 0, r
        with psycopg.connect(cfg.url(cfg.restore, target), autocommit=False) as conn:
            p = bootstrap.provisionar(conn, "primer.superadmin@universidad.edu.ar", CLAVE, "Primer superadmin",
                                      esperada=target, entorno="desarrollo", execute=True)
            assert p["result"] == "PASS" and p["code"] == "PROVISIONED", p
            fila = conn.execute("SELECT rol, estado, salt, password_hash FROM app_usuarios").fetchall()
            assert len(fila) == 1 and fila[0][0] == "superadmin" and fila[0][1] == "Activo"
            assert fila[0][3].startswith("pbkdf2_sha256$600000$")
            from auth import core
            assert core.verify_password(CLAVE, fila[0][2], fila[0][3])
            conn.rollback()
            segundo = bootstrap.provisionar(conn, "otro@universidad.edu.ar", CLAVE, "Otro", esperada=target,
                                            entorno="desarrollo", execute=True)
            assert segundo["code"] == "ALREADY_PROVISIONED"
            assert conn.execute("SELECT count(*) FROM app_usuarios").fetchone()[0] == 1
            conn.rollback()
            assert bootstrap.auditar_semillas(conn)["ok_para_produccion"] is True
    finally:
        assert _dropdb(cfg, target)["dropped"] is True
    assert target not in R.bases_de_prueba(cfg)
