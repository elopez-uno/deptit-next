"""Etapa 6A-B3: preproduccion local (docs/ETAPA6_6AB3_LOCAL_PILOT.md).

* Aislamiento: un proceso de preproduccion nunca completa su configuracion con ``backend/.env`` ni
  ``backend/.env.ops`` (de desarrollo).
* ``preprod-seed`` (``operacion.preprod.sembrar``): guardas (entorno, destino, snapshot de privilegios con SHA, origen
  de desarrollo verificado, confirmacion) sin tocar ninguna base.
* La TRANSFORMACION real (GRANT replicados de deptit_next_app + verificacion privilegio por privilegio, rol de backup
  sin escritura, cuentas heredadas desactivadas sin credencial utilizable, unica tabla cambiada app_usuarios) sobre una
  base de prueba ``deptit_next_restore_test_*`` restaurada desde un backup real de desarrollo; DROP al final.
deptit_next_dev solo se LEE (backup con el rol de solo lectura y snapshot del catalogo)."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
import shutil
import subprocess
from pathlib import Path

import psycopg
import pytest

import settings as S
from auth import core
from operacion import backup_db, bootstrap, comparacion, config, preprod as P, restore_db as R

NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


@pytest.fixture(scope="module")
def dev(tmp_path_factory):
    c = config.load()
    assert c.backup is not None and c.restore is not None, "faltan los roles operativos en backend/.env.ops"
    d = tmp_path_factory.mktemp("b3_dev_backup")
    c = dataclasses.replace(c, backup_dir=d, env={**c.env, "DEPTIT_BACKUP_DIR": str(d)})
    rep = backup_db.respaldar(c)
    assert rep["result"] == "PASS", rep
    with psycopg.connect(c.url(c.backup, "deptit_next_dev")) as conn:
        conn.read_only = True
        snap = P.snapshot_privilegios(conn)
        conn.rollback()
    yield c, Path(rep["manifest"]), snap
    assert R.bases_de_prueba(c) == []


def _env_preprod(tmp: Path) -> dict:
    docs, backups = tmp / "documents", tmp / "backups"
    docs.mkdir(exist_ok=True)
    backups.mkdir(exist_ok=True)
    return {"DEPTIT_ENTORNO": "preproduccion", "DEPTIT_DB_HOST": "127.0.0.1", "DEPTIT_DB_PORT": "5432",
            "DEPTIT_DB_NAME": "deptit_next_preprod", "DEPTIT_DB_USER": "deptit_next_preprod_app",
            "DEPTIT_DB_PASSWORD": "x" * 20, "DEPTIT_DB_SSLMODE": "disable",
            "DEPTIT_EXPECTED_DATABASE": "deptit_next_preprod", "DEPTIT_EXPECTED_DB_USER": "deptit_next_preprod_app",
            "DEPTIT_SESSION_COOKIE_SECURE": "1", "DEPTIT_API_DOCS": "0", "DEPTIT_DOCUMENTS_DIR": str(docs),
            "DEPTIT_BACKUP_DIR": str(backups), "DEPTIT_BACKUP_GATE_CREAR_PERIODO": "activo",
            "DEPTIT_CRITICAL_BACKUP_MAX_AGE_HOURS": "24",
            "DEPTIT_BACKUP_DB_USER": "deptit_next_preprod_backup", "DEPTIT_BACKUP_DB_PASSWORD": "y" * 20,
            "DEPTIT_OWNER_DB_USER": "deptit_next_preprod_owner", "DEPTIT_OWNER_DB_PASSWORD": "z" * 20,
            "DEPTIT_PG_BIN_DIR": r"C:\Program Files\PostgreSQL\18\bin"}


@pytest.fixture
def cfg_preprod(tmp_path):
    import main  # noqa: F401  (registra el validador del gate, como en el arranque)
    return config.load(_env_preprod(tmp_path), read_files=False)


# ------------------------------------------------------------------------------------------ aislamiento
def test_backend_env_de_desarrollo_no_se_lee_fuera_de_desarrollo(monkeypatch):
    assert S.proceso_de_desarrollo({}) and S.proceso_de_desarrollo({"DEPTIT_ENTORNO": "desarrollo"})
    assert not S.proceso_de_desarrollo({"DEPTIT_ENTORNO": "preproduccion"})
    assert not S.proceso_de_desarrollo({"DEPTIT_ENTORNO": "produccion"})
    leidos = []
    monkeypatch.setattr(S, "load_dotenv", lambda *a, **k: leidos.append(a))
    monkeypatch.setenv("DEPTIT_ENTORNO", "preproduccion")
    S.load_env_file()
    assert leidos == []
    monkeypatch.setenv("DEPTIT_ENTORNO", "desarrollo")
    S.load_env_file()
    assert len(leidos) == 1


def test_env_ops_de_desarrollo_no_completa_preproduccion(monkeypatch, tmp_path):
    for k in list(os.environ):
        if k.startswith("DEPTIT_") or k == "DATABASE_URL":
            monkeypatch.delenv(k)
    for k, v in _env_preprod(tmp_path).items():
        if not k.startswith(("DEPTIT_BACKUP_DB", "DEPTIT_OWNER_DB")):
            monkeypatch.setenv(k, v)
    import main  # noqa: F401
    c = config.load()  # lee archivos: en preproduccion NO debe tomar backend/.env.ops
    assert config.OPS_ENV_FILE.is_file()
    assert c.backup is None and c.restore is None and c.owner is None and c.entorno == "preproduccion"


def test_roles_operativos_distintos(tmp_path):
    import main  # noqa: F401
    env = {**_env_preprod(tmp_path), "DEPTIT_OWNER_DB_USER": "deptit_next_preprod_backup"}
    with pytest.raises(config.OpsConfigError, match="deben ser distintos"):
        config.load(env, read_files=False)
    env = {**_env_preprod(tmp_path), "DEPTIT_OWNER_DB_USER": "deptit_next_preprod_app"}
    with pytest.raises(config.OpsConfigError, match="no puede ser"):
        config.load(env, read_files=False)


# ------------------------------------------------------------------------------------------ guardas de la siembra
def test_snapshot_de_privilegios_y_alteracion(dev):
    _, _, snap = dev
    assert P.validar_privilegios(snap) is None
    assert snap["base_origen"] == "deptit_next_dev" and snap["rol_origen"] == "deptit_next_app"
    assert len(snap["relaciones"]) >= 80 and snap["relaciones"]["app_usuarios"]["privilegios"]
    alterado = json.loads(json.dumps(snap))
    alterado["relaciones"]["app_usuarios"]["privilegios"].append("TRUNCATE")
    assert "SHA-256" in P.validar_privilegios(alterado)
    otro = json.loads(json.dumps(snap))
    otro["rol_origen"] = "deptit_app"
    assert "desarrollo" in P.validar_privilegios(otro)
    raro = json.loads(json.dumps(snap))
    raro["relaciones"]["app_usuarios"]["privilegios"] = ["ALL"]
    raro["sha256"] = P._sha_privilegios(raro)
    assert "invalidos" in P.validar_privilegios(raro)
    assert P.validar_privilegios(None) and P.validar_privilegios({"kind": "x"})


def test_siembra_rechazada_fuera_de_preproduccion(dev):
    c, manifest, snap = dev
    r = P.sembrar(c, manifest, snap, execute=True, confirm="deptit_next_preprod")
    assert r["result"] == "FAIL" and r["code"] == "ENVIRONMENT_REFUSED", r


def test_siembra_plan_y_confirmacion(dev, cfg_preprod):
    _, manifest, snap = dev
    r = P.sembrar(cfg_preprod, manifest, snap)
    assert r["code"] == "CONFIRMATION_REQUIRED" and r["steps"] == ["backup_verified"], r
    assert r["origen"]["verification"] == "VALID" and r["origen"]["backup_id"].startswith("deptit_deptit_next_dev_")
    r = P.sembrar(cfg_preprod, manifest, snap, confirm="deptit_next_preprod")
    assert r["result"] == "PLANNED" and r["code"] == "PLAN_ONLY", r
    for malo in ("deptit_next_dev", "deptit", "deptit_next_prod", ""):
        assert P.sembrar(cfg_preprod, manifest, snap, confirm=malo, execute=True)["code"] == "CONFIRMATION_REQUIRED"


def test_siembra_rechaza_privilegios_y_origenes_invalidos(dev, cfg_preprod, tmp_path):
    _, manifest, snap = dev
    assert P.sembrar(cfg_preprod, manifest, {"kind": "x"}, confirm="deptit_next_preprod")["code"] == "PRIVILEGES_INVALID"
    sin_owner = dataclasses.replace(cfg_preprod, owner=None)
    assert P.sembrar(sin_owner, manifest, snap, confirm="deptit_next_preprod")["code"] == "ROLES_MISSING"
    # copia del backup de desarrollo con el manifest alterado: otro entorno declarado / dump alterado
    d = tmp_path / "copia"
    d.mkdir()
    dump = manifest.with_suffix("").with_suffix(".dump")
    shutil.copy2(dump, d / dump.name)
    m = json.loads(manifest.read_text(encoding="utf-8"))
    m["deptit"]["entorno"] = "preproduccion"
    (d / manifest.name).write_text(json.dumps(m), encoding="utf-8")
    assert P.sembrar(cfg_preprod, d / manifest.name, snap, confirm="deptit_next_preprod")["code"] \
        == "SOURCE_NOT_DEVELOPMENT"
    m["deptit"]["entorno"] = "desarrollo"
    (d / manifest.name).write_text(json.dumps(m), encoding="utf-8")
    with open(d / dump.name, "r+b") as fh:
        fh.seek(200)
        fh.write(b"XX")
    r = P.sembrar(cfg_preprod, d / manifest.name, snap, confirm="deptit_next_preprod")
    assert r["code"] == "BACKUP_INVALID" and "HASH" in r["error"], r
    # un backup de OTRA base (identidad distinta) no verifica contra deptit_next_dev
    m["database"]["name"] = "deptit_next_preprod"
    (d / manifest.name).write_text(json.dumps(m), encoding="utf-8")
    assert P.sembrar(cfg_preprod, d / manifest.name, snap, confirm="deptit_next_preprod")["code"] == "BACKUP_INVALID"


def test_marcador_de_credencial_deshabilitada_nunca_verifica():
    assert core._parse_hash(P.HASH_DESHABILITADO) is None
    for clave in ("", "admin", "admin123", P.HASH_DESHABILITADO):
        assert core.verify_password(clave, "00" * 16, P.HASH_DESHABILITADO) is False
    assert not core.needs_rehash(P.HASH_DESHABILITADO)


# ------------------------------------------------------------------------------------------ transformacion REAL
def test_transformacion_real_sobre_base_de_prueba(dev):
    """Restore del backup real de dev en una base de prueba (rol de restore = owner de sus objetos) + la MISMA
    transformacion que la siembra, con el rol de la app de desarrollo y el de backup como destinatarios de los GRANT
    (solo dentro de la base de prueba).  DROP al final."""
    c, manifest, snap = dev
    target = f"deptit_next_restore_test_b3seed_{NOW.strftime('%H%M%S')}"
    r = R.restaurar(c, manifest, target=target, execute=True, confirm=target, drop_after=False,
                    comparar_con_origen=False)
    assert r["result"] == "PASS" and r["checks"]["objetos_de_otro_owner"] == 0, json.dumps(r, default=str)[:2000]
    try:
        with psycopg.connect(c.url(c.restore, target), autocommit=False) as conn:
            antes = comparacion.huella(conn)
            n = P.otorgar_app(conn, "deptit_next_app", snap)
            assert n["relaciones"] == len(snap["relaciones"])
            assert P.diferencias_privilegios(conn, "deptit_next_app", snap) == []
            # una diferencia se detecta (privilegio de mas)
            conn.execute("GRANT TRUNCATE ON public.app_usuarios TO deptit_next_app")
            assert P.diferencias_privilegios(conn, "deptit_next_app", snap) == ["app_usuarios.TRUNCATE: sobra"]
            conn.execute("REVOKE TRUNCATE ON public.app_usuarios FROM deptit_next_app")
            P.otorgar_backup(conn, c.restore.user, "deptit_next_backup")
            assert P.problemas_backup(conn, "deptit_next_backup") == []
            cuentas = P.desactivar_cuentas_heredadas(conn)
            assert cuentas["cuentas"] == 9 and cuentas["activas_antes"] == 9
            assert cuentas["activas_despues"] == 0 and cuentas["credenciales_utilizables_despues"] == 0
            assert cuentas["semillas"]["semillas_activas"] == [] and cuentas["semillas"]["ok_para_produccion"]
            assert sorted(cuentas["semillas"]["semillas_presentes"]) == sorted(bootstrap.LEGACY_SEED_EMAILS)
            filas = conn.execute("SELECT estado, salt, password_hash, observaciones FROM app_usuarios").fetchall()
            assert all(f[0] == "Inactivo" and f[2] == P.HASH_DESHABILITADO and P.MARCA in f[3] for f in filas)
            assert len({f[1] for f in filas}) == 9  # salt nuevo por cuenta
            difs = comparacion.diferencias(antes, comparacion.huella(conn))
            assert difs and all(d.startswith("datos.app_usuarios") for d in difs), difs
            assert "pbkdf2" not in json.dumps(cuentas) and "$" not in json.dumps(cuentas["semillas"])
            conn.rollback()
    finally:
        assert R._cleanup(c, True, target, True, target, subprocess.run,
                          lambda n, path=None: f"{path}\\{n}.exe")["dropped"] is True
