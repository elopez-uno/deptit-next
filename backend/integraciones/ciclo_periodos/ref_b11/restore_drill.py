"""B11 — restore drill a una base AISLADA (P0-01, parte runtime).

Protecciones (todas fail-closed, antes de cualquier efecto):

* el backup se verifica completo (manifest + tamaño + SHA-256 + estructura del archivo) antes de tocar el servidor;
* la base destino SIEMPRE se llama ``deptit_restore_drill_<sufijo>`` (generada por defecto con sello UTC); nunca puede
  ser la base de origen del backup, la de ``DATABASE_URL`` (producción), la base de mantenimiento ni
  ``postgres``/``template0``/``template1``;
* el servidor del drill se indica aparte (``DEPTIT_RESTORE_DRILL_DATABASE_URL``, apuntando a una base de
  mantenimiento).  Si es el MISMO servidor que el origen del backup se exige ``allow_same_server=True`` explícito;
* sin ``execute=True`` solo se planifica (ningún comando, ninguna conexión);
* ``createdb`` falla si la base ya existe: nunca se restaura sobre una base preexistente ni se la borra;
* ``pg_restore --no-owner --no-privileges --exit-on-error --single-transaction``; contraseñas solo vía passfile;
* DROP solo de la base creada por ESTE drill, solo si ``drop_after=True`` y ``confirm_drop`` == nombre exacto.

Checks post-restore (solo lectura): conexión; tablas de ``public``; tablas críticas presentes; todas las tablas del TOC
del dump restauradas; cantidad mínima de tablas; filas por tabla crítica; ``app_usuarios`` (cuentas y superadmins
activos); marcador de esquema (la app no tiene tabla de migraciones: DDL en runtime -> se informa ``sistema_flags``).
Reporte ``restore_drill_report.json``: SHA del backup, base aislada, timestamps, checks, PASS/FAIL, identidad saneada.
"""
from __future__ import annotations

import datetime as _dt
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from . import pg_archive
from .backup_manifest import CRITICAL_TABLES, format_ts, utc_now, verify_backup
from .db_identity import DatabaseIdentity, DatabaseUrlError, libpq_environment, parse_database_url, redact

DRILL_URL_ENV = "DEPTIT_RESTORE_DRILL_DATABASE_URL"
DRILL_PREFIX = "deptit_restore_drill_"
DRILL_RE = re.compile(r"^deptit_restore_drill_[a-z0-9_]{1,40}$")
RESERVED = {"postgres", "template0", "template1"}
TABLE_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
STDERR_LIMIT = 2000


class DrillRefused(ValueError):
    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


def default_target(now: _dt.datetime) -> str:
    return f"{DRILL_PREFIX}{now.astimezone(_dt.timezone.utc):%Y%m%d%H%M%S}"


def target_problems(target: str, *, source_name: str, production_name: Optional[str], maintenance_name: str) -> list:
    p = []
    if not DRILL_RE.match(str(target or "")):
        p.append("TARGET_NOT_ISOLATED: el destino debe llamarse deptit_restore_drill_<[a-z0-9_]>")
    for label, name in (("origen del backup", source_name), ("producción (DATABASE_URL)", production_name),
                        ("base de mantenimiento", maintenance_name)):
        if name and str(target).casefold() == str(name).casefold():
            p.append(f"TARGET_IS_PROTECTED: el destino coincide con {label}")
    if str(target).casefold() in RESERVED:
        p.append("TARGET_IS_PROTECTED: base reservada del servidor")
    return p


def createdb_command(binary, target, maintenance_db):
    return [binary, "--no-password", f"--maintenance-db={maintenance_db}", "--template=template0", "--encoding=UTF8",
            target]


def pg_restore_command(binary, target, dump):
    return [binary, "--no-owner", "--no-privileges", "--exit-on-error", "--single-transaction", "--no-password",
            f"--dbname={target}", dump]


def dropdb_command(binary, target, maintenance_db):
    return [binary, "--no-password", f"--maintenance-db={maintenance_db}", target]


def default_connector(identity: DatabaseIdentity, password: Optional[str], dbname: str):
    import psycopg2
    conn = psycopg2.connect(host=identity.host, port=identity.port, user=identity.user, dbname=dbname,
                            password=password, connect_timeout=15)
    conn.set_session(readonly=True, autocommit=False)
    return conn


def post_restore_checks(conn, *, required_tables, toc_tables) -> dict:
    """Checks de solo lectura sobre la base restaurada."""
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' "
                "AND table_type = 'BASE TABLE' ORDER BY table_name")
    tables = sorted(r[0] for r in cur.fetchall())
    missing_required = sorted(set(required_tables) - set(tables))
    missing_toc = sorted(set(toc_tables) - set(tables))
    counts = {}
    for t in sorted(set(required_tables) & set(tables)):
        if TABLE_RE.match(t):
            cur.execute(f'SELECT COUNT(*) FROM public."{t}"')
            counts[t] = int(cur.fetchone()[0])
    users = {}
    if "app_usuarios" in tables:
        cur.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE rol = 'superadmin' AND estado = 'Activo') FROM app_usuarios")
        total, superadmins = cur.fetchone()
        users = {"accounts": int(total), "active_superadmins": int(superadmins)}
    marker = {"kind": "none (el esquema evoluciona por DDL en runtime; no hay tabla de migraciones)"}
    if "sistema_flags" in tables:
        marker["sistema_flags_rows"] = counts.get("sistema_flags")
    checks = {
        "connection": True,
        "tables_found": len(tables),
        "min_tables": len(required_tables),
        "min_tables_ok": len(tables) >= len(required_tables),
        "required_tables_missing": missing_required,
        "toc_tables": len(toc_tables),
        "toc_tables_missing": missing_toc,
        "row_counts": counts,
        "app_usuarios": users,
        "schema_marker": marker,
    }
    checks["ok"] = checks["min_tables_ok"] and not missing_required and not missing_toc and bool(users)
    return checks


def run_restore_drill(manifest_path, drill_database_url, *, production_database_url=None, target=None,
                      execute=False, allow_same_server=False, drop_after=False, confirm_drop=None,
                      runner: Callable = subprocess.run, which: Callable = shutil.which, bin_dir=None,
                      connector: Callable = default_connector, now: Optional[_dt.datetime] = None,
                      required_tables=CRITICAL_TABLES) -> dict:
    now = (now or utc_now()).replace(microsecond=0)
    report = {"kind": "deptit-restore-drill", "format_version": 1, "started_at_utc": format_ts(now),
              "mode": "execute" if execute else "plan", "result": "FAIL", "code": None, "steps": [], "checks": {}}
    drill_password = None
    created = False
    target_name = None
    drill_id = None
    try:
        chk = verify_backup(manifest_path, now=now)
        report["backup"] = {"manifest": Path(manifest_path).name, "verification": chk.code}
        if not chk.ok:
            raise DrillRefused("BACKUP_INVALID", f"el backup no verifica ({chk.code})")
        m = chk.manifest
        report["backup"].update({"sha256": m["dump"]["sha256"], "size": m["dump"]["size"],
                                 "created_at_utc": m["created_at_utc"], "source": m["database"]})
        archive = pg_archive.inspect_archive(chk.dump_path, required_tables=required_tables,
                                             expected_dbname=m["database"]["name"])
        if not archive["ok"]:
            raise DrillRefused("ARCHIVE_INVALID", "; ".join(archive["problems"]))
        toc_tables = pg_archive.read_archive(chk.dump_path).table_names()
        report["steps"].append("backup_verified")
        try:
            drill_id, drill_password, extra = parse_database_url(drill_database_url)
        except DatabaseUrlError as exc:
            raise DrillRefused("DRILL_URL_INVALID", f"{DRILL_URL_ENV}: {exc}") from None
        report["drill_server"] = drill_id.sanitized()
        production_name = None
        if production_database_url:
            try:
                production_name = parse_database_url(production_database_url)[0].name
            except DatabaseUrlError:
                raise DrillRefused("PRODUCTION_URL_INVALID", "DATABASE_URL no interpretable") from None
        target_name = target or default_target(now)
        problems = target_problems(target_name, source_name=m["database"]["name"], production_name=production_name,
                                   maintenance_name=drill_id.name)
        if problems:
            raise DrillRefused(problems[0].split(":", 1)[0], "; ".join(problems))
        source = DatabaseIdentity(m["database"]["host"], m["database"]["port"], m["database"]["name"], m["database"]["user"])
        same_server = DatabaseIdentity(drill_id.host, drill_id.port, source.name, "").same_database(source)
        report["same_server_as_source"] = same_server
        if same_server and not allow_same_server:
            raise DrillRefused("SAME_SERVER", "el servidor del drill es el mismo que el de origen; usar un servidor "
                                              "aislado o confirmar explícitamente --allow-same-server")
        report["target"] = {"database": target_name, "server": drill_id.sanitized()}
        report["steps"].append("target_validated")
        if not execute:
            report["result"], report["code"] = "PLANNED", "PLAN_ONLY"
            return report
        bins = {}
        for b in ("createdb", "pg_restore", "dropdb"):
            found = which(b, path=str(bin_dir)) if bin_dir else which(b)
            if not found:
                raise DrillRefused("BINARY_MISSING", f"{b} no está instalado")
            bins[b] = found
        with libpq_environment(drill_id, drill_password, extra) as env:
            proc = runner(createdb_command(bins["createdb"], target_name, drill_id.name), env=env,
                          capture_output=True, text=True)
            if proc.returncode != 0:
                raise DrillRefused("CREATEDB_FAILED", f"createdb rc={proc.returncode} (¿la base ya existe?): "
                                                      f"{redact(proc.stderr, drill_password)[-STDERR_LIMIT:]}")
            created = True
            report["steps"].append("createdb")
            proc = runner(pg_restore_command(bins["pg_restore"], target_name, chk.dump_path), env=env,
                          capture_output=True, text=True)
            if proc.returncode != 0:
                raise DrillRefused("PG_RESTORE_FAILED", f"pg_restore rc={proc.returncode}: "
                                                        f"{redact(proc.stderr, drill_password)[-STDERR_LIMIT:]}")
            report["steps"].append("pg_restore")
        conn = connector(drill_id, drill_password, target_name)
        try:
            checks = post_restore_checks(conn, required_tables=required_tables, toc_tables=toc_tables)
        finally:
            try:
                conn.rollback()
            finally:
                conn.close()
        report["checks"] = checks
        report["steps"].append("post_restore_checks")
        if not checks["ok"]:
            raise DrillRefused("CHECKS_FAILED", "faltan tablas/filas esperadas en la base restaurada")
        report["result"], report["code"] = "PASS", "RESTORE_VERIFIED"
    except DrillRefused as exc:
        report["code"] = exc.code
        report["error"] = redact(exc.message, drill_password)[:STDERR_LIMIT]
    except Exception as exc:
        report["code"] = "UNEXPECTED"
        report["error"] = redact(f"{type(exc).__name__}: {exc}", drill_password)[:500]
    finally:
        report["cleanup"] = _cleanup(created, target_name, drill_id, drill_password, drop_after, confirm_drop,
                                     production_database_url, report, runner, which, bin_dir)
        report["finished_at_utc"] = format_ts(utc_now())
    return report


def _cleanup(created, target_name, drill_id, password, drop_after, confirm_drop, production_url, report, runner,
             which, bin_dir) -> dict:
    if not created:
        return {"dropped": False, "reason": "no se creó ninguna base"}
    if not drop_after:
        return {"dropped": False, "reason": "base de drill conservada (sin --drop-after)", "database": target_name}
    if confirm_drop != target_name:
        return {"dropped": False, "reason": "confirmación de DROP ausente o distinta del nombre exacto",
                "database": target_name}
    prod = None
    if production_url:
        try:
            prod = parse_database_url(production_url)[0].name
        except DatabaseUrlError:
            prod = None
    if not DRILL_RE.match(target_name) or (prod and prod.casefold() == target_name.casefold()):
        return {"dropped": False, "reason": "nombre no aislado: DROP rechazado", "database": target_name}
    dropdb = which("dropdb", path=str(bin_dir)) if bin_dir else which("dropdb")
    if not dropdb:
        return {"dropped": False, "reason": "dropdb no disponible", "database": target_name}
    with libpq_environment(drill_id, password) as env:
        proc = runner(dropdb_command(dropdb, target_name, drill_id.name), env=env, capture_output=True, text=True)
    return {"dropped": proc.returncode == 0, "database": target_name,
            "reason": "DROP de la base de drill confirmado" if proc.returncode == 0 else f"dropdb rc={proc.returncode}"}
