"""Restore de base (6A-B2) sobre las piezas certificadas B11 (``ref_b11/restore_drill.py``: comandos ``createdb`` /
``pg_restore --no-owner --no-privileges --exit-on-error --single-transaction`` / ``dropdb`` y checks post-restore).

Dos modos, ambos fail-closed y siempre ANTES de cualquier efecto: backup verificado completo (manifest + identidad +
tamaño + SHA-256 + lector independiente del archivo) y destino validado.

* ``prueba`` (restore drill): crea ``deptit_next_restore_test_<id>`` con el rol de restore (CREATEDB, sin acceso a las
  bases reales); ``createdb`` falla si ya existe (nunca se restaura sobre una base preexistente).  Compara la base
  restaurada con el ORIGEN (``comparacion``: esquema + contenido) y la borra solo si la creo esta misma corrida y se
  confirmo el nombre exacto.
* ``recuperacion`` (desastre): restaura en la base del entorno (``deptit_next_prod`` / ``..._preprod`` / ``..._dev``) que
  el owner creo VACIA.  Exige confirmar el nombre exacto y que no tenga ninguna tabla en ``public``: una base con datos
  (``deptit_next_dev`` hoy) se rechaza siempre.  Nunca borra nada.

Destinos prohibidos en ambos modos: ``deptit``, las bases de sistema y cualquier nombre fuera de la regla del modo.
"""
from __future__ import annotations

import datetime as _dt
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

import psycopg

import settings as app_settings
from integraciones.ciclo_periodos.ref_b11 import pg_archive
from integraciones.ciclo_periodos.ref_b11.backup_manifest import CRITICAL_TABLES, format_ts, utc_now, verify_backup
from integraciones.ciclo_periodos.ref_b11.db_identity import identity_from_url, libpq_environment, redact
from integraciones.ciclo_periodos.ref_b11.restore_drill import (createdb_command, dropdb_command, pg_restore_command,
                                                                post_restore_checks)

from . import comparacion
from .config import RESTORE_TEST_PREFIX, RESTORE_TEST_RE, Credencial, OpsConfig

PRUEBA, RECUPERACION = "prueba", "recuperacion"
MAINTENANCE_DB = "postgres"
STDERR_LIMIT = 2000


class RestoreRefused(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


def target_default(now: _dt.datetime) -> str:
    return f"{RESTORE_TEST_PREFIX}{now.astimezone(_dt.timezone.utc):%Y%m%d%H%M%S}"


def problemas_destino(target: str, *, modo: str, cfg: OpsConfig, source_name: str) -> list:
    t = str(target or "")
    p = []
    if t.casefold() in app_settings.BASES_PROHIBIDAS:
        p.append("TARGET_FORBIDDEN: base prohibida para DEPTIT NEXT")
    if modo == PRUEBA:
        if not RESTORE_TEST_RE.match(t):
            p.append(f"TARGET_NOT_ISOLATED: el destino de prueba debe llamarse {RESTORE_TEST_PREFIX}<[a-z0-9_]>")
        for nombre in set(app_settings.BASES.values()) | {source_name, cfg.app.expected_database}:
            if t.casefold() == nombre.casefold():
                p.append(f"TARGET_IS_PROTECTED: el destino coincide con {nombre!r}")
    elif modo == RECUPERACION:
        if t != app_settings.BASES[cfg.entorno] or t != cfg.app.expected_database:
            p.append("TARGET_NOT_ENVIRONMENT_DB: la recuperacion solo restaura en la base del entorno configurado")
    else:
        p.append("MODE_INVALID: modo desconocido")
    return p


def _connect(cfg: OpsConfig, cred: Credencial, database: str, connect: Callable):
    conn = connect(cfg.url(cred, database), connect_timeout=15, autocommit=False)
    conn.read_only = True
    return conn


def huella_base(cfg: OpsConfig, cred: Credencial, database: str, *, connect: Callable = psycopg.connect) -> dict:
    with _connect(cfg, cred, database, connect) as conn:
        real = conn.execute("SELECT current_database()").fetchone()[0]
        if real != database:
            raise RestoreRefused("IDENTITY", "la conexion no apunta a la base esperada")
        h = comparacion.huella(conn)
        conn.rollback()
    return h


def _vacia(cfg: OpsConfig, cred: Credencial, database: str, connect: Callable) -> bool:
    with _connect(cfg, cred, database, connect) as conn:
        n = conn.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                         "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'S')").fetchone()[0]
        conn.rollback()
    return n == 0


def restaurar(cfg: OpsConfig, manifest_path, *, modo: str = PRUEBA, target: Optional[str] = None,
              execute: bool = False, confirm: Optional[str] = None, drop_after: bool = False,
              comparar_con_origen: bool = True, runner: Callable = subprocess.run, which: Callable = shutil.which,
              connect: Callable = psycopg.connect, now: Optional[_dt.datetime] = None) -> dict:
    now = (now or utc_now()).replace(microsecond=0)
    report = {"kind": "deptit-next-db-restore", "format_version": 1, "modo": modo,
              "mode": "execute" if execute else "plan", "started_at_utc": format_ts(now), "result": "FAIL",
              "code": None, "steps": [], "checks": {}}
    cred = cfg.restore
    password = cred.password if cred else None
    created = False
    target_name = None
    try:
        if cred is None:
            raise RestoreRefused("RESTORE_ROLE_MISSING", "faltan DEPTIT_RESTORE_DB_USER/PASSWORD")
        identity = identity_from_url(cfg.identity_url())
        chk = verify_backup(manifest_path, expected_identity=identity, now=now)
        report["backup"] = {"manifest": Path(manifest_path).name, "verification": chk.code}
        if not chk.ok:
            raise RestoreRefused("BACKUP_INVALID", f"el backup no verifica ({chk.code})")
        m = chk.manifest
        if m["deptit"].get("entorno") != cfg.entorno:
            raise RestoreRefused("OTHER_ENVIRONMENT", "el backup es de otro entorno")
        report["backup"].update({"sha256": m["dump"]["sha256"], "size": m["dump"]["size"],
                                 "created_at_utc": m["created_at_utc"], "backup_id": m["deptit"].get("backup_id"),
                                 "set_id": m["deptit"].get("set_id"), "source": m["database"]["name"]})
        archive = pg_archive.inspect_archive(chk.dump_path, required_tables=CRITICAL_TABLES,
                                             expected_dbname=m["database"]["name"])
        if not archive["ok"]:
            raise RestoreRefused("ARCHIVE_INVALID", "; ".join(archive["problems"]))
        toc_tables = pg_archive.read_archive(chk.dump_path).table_names()
        report["steps"].append("backup_verified")
        target_name = target or (target_default(now) if modo == PRUEBA else None)
        if problemas := problemas_destino(target_name, modo=modo, cfg=cfg, source_name=m["database"]["name"]):
            raise RestoreRefused(problemas[0].split(":", 1)[0], "; ".join(problemas))
        report["target"] = {"database": target_name, "user": cred.user}
        report["steps"].append("target_validated")
        if modo == RECUPERACION and confirm != target_name:
            raise RestoreRefused("CONFIRMATION_REQUIRED", "la recuperacion exige --confirm con el nombre exacto")
        if not execute:
            report["result"], report["code"] = "PLANNED", "PLAN_ONLY"
            return report
        bins = {}
        for b in ("createdb", "pg_restore", "dropdb"):
            found = which(b, path=str(cfg.pg_bin_dir)) if cfg.pg_bin_dir else which(b)
            if not found:
                raise RestoreRefused("BINARY_MISSING", f"{b} no esta instalado")
            bins[b] = found
        drill_id = identity_from_url(cfg.url(cred, MAINTENANCE_DB))
        with libpq_environment(drill_id, password, {"PGSSLMODE": cfg.app.db.sslmode}) as env:
            if modo == PRUEBA:
                proc = runner(createdb_command(bins["createdb"], target_name, MAINTENANCE_DB), env=env,
                              capture_output=True, text=True)
                if proc.returncode != 0:
                    raise RestoreRefused("CREATEDB_FAILED", f"createdb rc={proc.returncode} (¿la base ya existe?): "
                                                            f"{redact(proc.stderr, password)[-STDERR_LIMIT:]}")
                created = True
                report["steps"].append("createdb")
            elif not _vacia(cfg, cred, target_name, connect):
                raise RestoreRefused("TARGET_NOT_EMPTY", "la base destino tiene objetos: nunca se restaura encima")
            proc = runner(pg_restore_command(bins["pg_restore"], target_name, chk.dump_path), env=env,
                          capture_output=True, text=True)
            if proc.returncode != 0:
                raise RestoreRefused("PG_RESTORE_FAILED", f"pg_restore rc={proc.returncode}: "
                                                          f"{redact(proc.stderr, password)[-STDERR_LIMIT:]}")
            report["steps"].append("pg_restore")
        with _connect(cfg, cred, target_name, connect) as conn:
            checks = post_restore_checks(conn, required_tables=CRITICAL_TABLES, toc_tables=toc_tables)
            owner = conn.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                 "WHERE n.nspname = 'public' AND pg_get_userbyid(c.relowner) <> current_user"
                                 ).fetchone()[0]
            conn.rollback()
        checks["objetos_de_otro_owner"] = int(owner)
        report["checks"] = checks
        report["steps"].append("post_restore_checks")
        if not checks["ok"]:
            raise RestoreRefused("CHECKS_FAILED", "faltan tablas/filas esperadas en la base restaurada")
        if comparar_con_origen and modo == PRUEBA:
            if cfg.backup is None:
                raise RestoreRefused("BACKUP_ROLE_MISSING", "la comparacion con el origen usa el rol de backup")
            origen = huella_base(cfg, cfg.backup, m["database"]["name"], connect=connect)
            destino = huella_base(cfg, cred, target_name, connect=connect)
            difs = comparacion.diferencias(origen, destino)
            report["comparacion"] = {"origen": comparacion.resumen(origen), "destino": comparacion.resumen(destino),
                                     "diferencias": difs[:50], "equivalentes": not difs}
            report["steps"].append("comparacion_semantica")
            if difs:
                raise RestoreRefused("COMPARISON_FAILED", f"{len(difs)} diferencias entre origen y restore")
        report["result"], report["code"] = "PASS", "RESTORE_VERIFIED"
    except RestoreRefused as exc:
        report["code"] = exc.code
        report["error"] = redact(exc.message, password)[:STDERR_LIMIT]
    except Exception as exc:
        report["code"] = "UNEXPECTED"
        report["error"] = redact(f"{type(exc).__name__}: {exc}", password)[:500]
    finally:
        report["cleanup"] = _cleanup(cfg, created, target_name, drop_after, confirm, runner, which)
        report["finished_at_utc"] = format_ts(utc_now())
    return report


def _cleanup(cfg: OpsConfig, created: bool, target_name, drop_after: bool, confirm, runner, which) -> dict:
    if not created:
        return {"dropped": False, "reason": "esta corrida no creo ninguna base"}
    if not drop_after:
        return {"dropped": False, "reason": "base de prueba conservada (sin --drop-after)", "database": target_name}
    if confirm != target_name:
        return {"dropped": False, "reason": "confirmacion de DROP ausente o distinta del nombre exacto",
                "database": target_name}
    if not RESTORE_TEST_RE.match(target_name) or target_name in app_settings.BASES.values():
        return {"dropped": False, "reason": "nombre no aislado: DROP rechazado", "database": target_name}
    dropdb = which("dropdb", path=str(cfg.pg_bin_dir)) if cfg.pg_bin_dir else which("dropdb")
    if not dropdb:
        return {"dropped": False, "reason": "dropdb no disponible", "database": target_name}
    cred = cfg.restore
    with libpq_environment(identity_from_url(cfg.url(cred, MAINTENANCE_DB)), cred.password,
                           {"PGSSLMODE": cfg.app.db.sslmode}) as env:
        proc = runner(dropdb_command(dropdb, target_name, MAINTENANCE_DB), env=env, capture_output=True, text=True)
    return {"dropped": proc.returncode == 0, "database": target_name,
            "reason": "DROP de la base de prueba confirmado" if proc.returncode == 0 else f"dropdb rc={proc.returncode}"}


def bases_de_prueba(cfg: OpsConfig, *, connect: Callable = psycopg.connect) -> list:
    """Bases ``deptit_next_restore_test_*`` presentes en el servidor (deben ser 0 al terminar una prueba)."""
    cred = cfg.restore or cfg.backup
    with _connect(cfg, cred, MAINTENANCE_DB if cred is cfg.restore else cfg.app.expected_database, connect) as conn:
        rows = conn.execute("SELECT datname FROM pg_database WHERE datname LIKE %s ORDER BY 1",
                            (RESTORE_TEST_PREFIX.replace("_", r"\_") + "%",)).fetchall()
        conn.rollback()
    return [r[0] for r in rows]
