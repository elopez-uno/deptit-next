"""Backup PostgreSQL propio de NEXT (6A-B2) = herramienta certificada B11 (``ref_b11/backup.py``, copia LITERAL).

Secuencia B11 (fail-closed; ante cualquier fallo no queda manifest y los temporales se borran): ``pg_dump
--format=custom --no-owner --no-privileges`` a ``.partial`` reservado con O_EXCL -> ``pg_restore --list`` -> lector
independiente del archivo (TOC, cadena de bloques hasta EOF, base de origen, tablas criticas) -> SHA-256 + tamaño ->
publicacion atomica sin sobrescritura del dump -> manifest (marcador de commit).  La contraseña viaja solo en un
passfile temporal; argv, stdout, logs y manifest no la contienen.

Lo que agrega NEXT, antes y despues (nunca dentro del formato certificado):
* antes: la conexion del rol de backup apunta EXACTAMENTE a la base del entorno, con ese rol, sin superusuario;
* seccion libre ``deptit`` del manifest: producto, entorno, ``backup_id``, ``set_id``, release y huella del esquema;
* despues: re-verificacion independiente del manifest publicado (``verify_backup`` con identidad + SHA-256).
"""
from __future__ import annotations

import datetime as _dt
import json
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

import psycopg

import settings as app_settings
from integraciones.ciclo_periodos.ref_b11 import backup as B
from integraciones.ciclo_periodos.ref_b11.backup_manifest import (MANIFEST_SUFFIX, backup_basename, utc_now,
                                                                  verify_backup)
from integraciones.ciclo_periodos.ref_b11.db_identity import identity_from_url

from . import comparacion
from .config import Credencial, OpsConfig, OpsConfigError

CHECKPOINT = "NEXT-6A-B2"
TOOL = "operacion.backup_db"
TOOL_VERSION = 1
PRODUCTO = "deptit-next"
RELEASE_FILE = app_settings.REPO_DIR / "RELEASE.json"


def release_actual() -> str:
    """Identificador de la release instalada (``RELEASE.json`` del artefacto) o ``desarrollo`` (arbol de trabajo)."""
    try:
        return str(json.loads(RELEASE_FILE.read_text(encoding="utf-8"))["release_id"])
    except (OSError, ValueError, KeyError, TypeError):
        return "desarrollo"


def verificar_conexion(cfg: OpsConfig, cred: Credencial, *, connect: Callable = psycopg.connect) -> dict:
    """Base y rol reales de la conexion de backup + huella del esquema.  Solo lecturas, en modo read-only."""
    with connect(cfg.url(cred), connect_timeout=15, autocommit=False) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        base, usuario, superuser = conn.execute(
            "SELECT current_database(), current_user, (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)"
        ).fetchone()
        if base != cfg.app.expected_database:
            raise OpsConfigError(f"la conexion de backup apunta a {base!r}; se exige {cfg.app.expected_database!r}")
        if base.lower() in app_settings.BASES_PROHIBIDAS:
            raise OpsConfigError(f"la base {base!r} esta prohibida para DEPTIT NEXT")
        if usuario != cred.user:
            raise OpsConfigError("la conexion de backup no usa el rol configurado")
        if superuser:
            raise OpsConfigError("el rol de backup no puede ser superusuario")
        esquema = comparacion.huella_esquema(conn)
        conn.rollback()
    return {"database": base, "user": usuario, "esquema_sha256": esquema["sha256"],
            "tablas": len(esquema["tablas"])}


def respaldar(cfg: OpsConfig, *, set_id: Optional[str] = None, now: Optional[_dt.datetime] = None,
              runner: Callable = subprocess.run, which: Callable = shutil.which, connect: Callable = psycopg.connect,
              cred: Optional[Credencial] = None) -> dict:
    """Ejecuta UN backup.  Devuelve un reporte sin secretos (``result`` PASS/FAIL)."""
    cred = cred or cfg.backup
    if cred is None:
        return {"result": "FAIL", "code": "BACKUP_ROLE_MISSING",
                "detail": "faltan DEPTIT_BACKUP_DB_USER/PASSWORD (rol de solo lectura para pg_dump)"}
    created = (now or utc_now()).astimezone(_dt.timezone.utc).replace(microsecond=0)
    identity = identity_from_url(cfg.identity_url())
    backup_id = backup_basename(identity, created)
    report = {"kind": "deptit-next-db-backup", "backup_id": backup_id, "set_id": set_id, "entorno": cfg.entorno,
              "database": cfg.app.expected_database, "backup_user": cred.user}
    try:
        conexion = verificar_conexion(cfg, cred, connect=connect)
    except (OpsConfigError, psycopg.Error) as exc:
        detalle = str(exc) if isinstance(exc, OpsConfigError) else type(exc).__name__
        return {**report, "result": "FAIL", "code": "CONNECTION_CHECK_FAILED", "detail": detalle}
    report["conexion"] = conexion
    meta = {"checkpoint": CHECKPOINT, "tool": TOOL, "tool_version": TOOL_VERSION, "producto": PRODUCTO,
            "entorno": cfg.entorno, "backup_id": backup_id, "set_id": set_id, "release": release_actual(),
            "esquema_sha256": conexion["esquema_sha256"], "entrypoint": None, "entrypoint_sha256": None}
    res = B.run_backup(cfg.url(cred), str(cfg.backup_dir), runner=runner, which=which, bin_dir=cfg.pg_bin_dir or "",
                       now=created, deptit=meta)
    report.update(res.report())
    report["result"] = "PASS" if res.ok else "FAIL"
    if not res.ok:
        return report
    chk = verify_backup(res.manifest_path, expected_identity=identity, now=created)
    report["verificacion"] = chk.summary()
    if not chk.ok or chk.manifest["deptit"].get("entorno") != cfg.entorno:
        report["result"], report["code"] = "FAIL", f"POST_VERIFY_{chk.code}"
    return report


def manifest_de(cfg: OpsConfig, backup_id: str) -> Path:
    return cfg.backup_dir / f"{backup_id}{MANIFEST_SUFFIX}"
