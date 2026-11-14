"""B11 — backup PostgreSQL verificable (P0-01).

Secuencia (fail-closed; ante cualquier fallo NO queda manifest y los temporales se eliminan):

1. ``DATABASE_URL`` -> identidad saneada + contraseña aparte (``db_identity``); la contraseña viaja SOLO en un passfile
   temporal privado (``PGPASSFILE``), nunca en argv, stdout, logs ni manifest.
2. ``pg_dump`` y ``pg_restore`` deben existir (``DEPTIT_PG_BIN_DIR`` o ``PATH``); se registran sus versiones.
3. Nombres finales ``deptit_<db>_<YYYYmmddTHHMMSSZ>.dump`` / ``.manifest.json``: si alguno existe -> error (nunca se
   sobrescribe un backup previo).
4. ``pg_dump --format=custom --no-owner --no-privileges --no-password`` (esquema + datos) escribe a
   ``.<nombre>.dump.partial`` reservado con O_EXCL; luego fsync.
5. Validación del temporal: ``pg_restore --list`` (rc=0, TOC no vacío) + verificación independiente en Python
   (``pg_archive``: TOC, cadena de bloques hasta EOF, base de origen == identidad, tablas críticas presentes).
6. SHA-256 + tamaño; publicación atómica temp -> final SIN sobrescritura (``os.link`` + unlink; en Windows
   ``os.rename``, que falla si el destino existe).
7. Manifest (``backup_manifest``) a ``.partial`` + fsync + publicación atómica: el manifest es el marcador de commit.

Nunca se ejecuta dentro de una transacción de la app ni desde un clic: es una herramienta operativa no interactiva
(``tools/b11_backup_postgresql.py``) para Task Scheduler / cron / systemd.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from . import pg_archive
from .backup_manifest import (CRITICAL_TABLES, DUMP_SUFFIX, MANIFEST_SUFFIX, PARTIAL_SUFFIX, TOOL_VERSION,
                              backup_basename, build_manifest, sha256_file, utc_now, validate_manifest_document)
from .db_identity import DatabaseUrlError, libpq_environment, parse_database_url, redact

PG_BIN_DIR_ENV = "DEPTIT_PG_BIN_DIR"
LOCK_WAIT_TIMEOUT = "120s"
STDERR_LIMIT = 2000


class BackupError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


@dataclass
class BackupResult:
    ok: bool
    code: str
    dump_path: Optional[str] = None
    manifest_path: Optional[str] = None
    manifest: Optional[dict] = None
    steps: List[str] = field(default_factory=list)

    def report(self) -> dict:
        return {"result": "PASS" if self.ok else "FAIL", "code": self.code, "dump": self.dump_path,
                "manifest": self.manifest_path, "steps": self.steps,
                "sha256": (self.manifest or {}).get("dump", {}).get("sha256")}


def find_binary(name: str, *, which: Callable = shutil.which, bin_dir: Optional[str] = None) -> Optional[str]:
    if bin_dir:
        found = which(name, path=str(bin_dir))
        if found:
            return found
        return None
    return which(name)


def pg_dump_command(pg_dump: str, output: str) -> List[str]:
    """Conexión 100% por entorno libpq (PGHOST/PGPORT/PGUSER/PGDATABASE/PGPASSFILE): argv sin secretos."""
    return [pg_dump, "--format=custom", "--no-owner", "--no-privileges", "--no-password",
            f"--lock-wait-timeout={LOCK_WAIT_TIMEOUT}", "--file", output]


def pg_restore_list_command(pg_restore: str, dump: str) -> List[str]:
    return [pg_restore, "--list", dump]


def tool_version(binary: str, runner: Callable) -> str:
    proc = runner([binary, "--version"], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise BackupError("TOOL_VERSION_FAILED", f"{os.path.basename(binary)} --version rc={proc.returncode}")
    return (proc.stdout or "").strip().splitlines()[0][:120] if (proc.stdout or "").strip() else "unknown"


def _fsync_file(path) -> None:
    with open(path, "rb+") as fh:
        os.fsync(fh.fileno())


def _fsync_dir(path) -> None:
    if os.name == "nt":
        return
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish_no_overwrite(tmp: Path, final: Path) -> None:
    """Publicación atómica temp -> final que FALLA si el destino existe (nunca sobrescribe)."""
    if final.exists() or final.is_symlink():
        raise BackupError("TARGET_EXISTS", f"{final.name} ya existe; no se sobrescribe")
    try:
        os.link(tmp, final)
    except FileExistsError:
        raise BackupError("TARGET_EXISTS", f"{final.name} ya existe; no se sobrescribe") from None
    except OSError:
        if os.name != "nt":
            raise BackupError("PUBLISH_FAILED", "el filesystem no soporta publicación atómica sin sobrescritura") from None
        try:
            os.rename(tmp, final)  # Windows: falla si final existe
        except FileExistsError:
            raise BackupError("TARGET_EXISTS", f"{final.name} ya existe; no se sobrescribe") from None
        return
    os.unlink(tmp)


def _reserve(path: Path) -> None:
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)


def check_backup_dir(backup_dir) -> Path:
    d = Path(backup_dir)
    if not str(backup_dir or "").strip():
        raise BackupError("BACKUP_DIR_MISSING", "falta el directorio de backups (DEPTIT_BACKUP_DIR)")
    if not d.is_absolute():
        raise BackupError("BACKUP_DIR_INVALID", "el directorio de backups debe ser una ruta absoluta")
    if d.is_symlink() or not d.is_dir():
        raise BackupError("BACKUP_DIR_INVALID", "el directorio de backups no existe o es un enlace")
    return d.resolve()


def run_backup(database_url, backup_dir, *, runner: Callable = subprocess.run, which: Callable = shutil.which,
               bin_dir: Optional[str] = None, now: Optional[_dt.datetime] = None, deptit: Optional[dict] = None,
               critical_tables=CRITICAL_TABLES) -> BackupResult:
    """Ejecuta un backup completo.  Nunca levanta: devuelve ``BackupResult`` (ok/code/steps)."""
    res = BackupResult(False, "UNSTARTED")
    password = None
    tmp_dump = tmp_manifest = None
    try:
        try:
            identity, password, extra = parse_database_url(database_url)
        except DatabaseUrlError as exc:
            raise BackupError("DATABASE_URL_INVALID", str(exc)) from None
        d = check_backup_dir(backup_dir)
        bin_dir = bin_dir if bin_dir is not None else (os.environ.get(PG_BIN_DIR_ENV) or None)
        pg_dump = find_binary("pg_dump", which=which, bin_dir=bin_dir)
        pg_restore = find_binary("pg_restore", which=which, bin_dir=bin_dir)
        if not pg_dump:
            raise BackupError("PG_DUMP_MISSING", "pg_dump no está instalado o no está en PATH/DEPTIT_PG_BIN_DIR")
        if not pg_restore:
            raise BackupError("PG_RESTORE_MISSING", "pg_restore no está instalado o no está en PATH/DEPTIT_PG_BIN_DIR")
        tools = {"pg_dump_version": tool_version(pg_dump, runner), "pg_restore_version": tool_version(pg_restore, runner)}
        res.steps.append("tools")
        created = (now or utc_now()).astimezone(_dt.timezone.utc).replace(microsecond=0)
        base = backup_basename(identity, created)
        final_dump, final_manifest = d / (base + DUMP_SUFFIX), d / (base + MANIFEST_SUFFIX)
        if final_dump.exists() or final_manifest.exists():
            raise BackupError("TARGET_EXISTS", f"{base} ya existe; no se sobrescribe")
        tmp_dump = d / f".{base}{DUMP_SUFFIX}{PARTIAL_SUFFIX}"
        tmp_manifest = d / f".{base}{MANIFEST_SUFFIX}{PARTIAL_SUFFIX}"
        try:
            _reserve(tmp_dump)
        except FileExistsError:
            tmp_dump = None
            raise BackupError("TARGET_EXISTS", "ya hay un backup en curso con el mismo nombre") from None
        with libpq_environment(identity, password, extra) as env:
            proc = runner(pg_dump_command(pg_dump, str(tmp_dump)), env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            raise BackupError("PG_DUMP_FAILED", f"pg_dump rc={proc.returncode}: "
                                                f"{redact(proc.stderr, password)[-STDERR_LIMIT:]}")
        res.steps.append("pg_dump")
        if not tmp_dump.is_file() or tmp_dump.stat().st_size == 0:
            raise BackupError("DUMP_EMPTY", "pg_dump no produjo contenido")
        _fsync_file(tmp_dump)
        listing = runner(pg_restore_list_command(pg_restore, str(tmp_dump)), capture_output=True, text=True)
        list_entries = sum(1 for ln in (listing.stdout or "").splitlines() if ln.strip() and not ln.startswith(";"))
        if listing.returncode != 0 or list_entries == 0:
            raise BackupError("PG_RESTORE_LIST_FAILED", f"pg_restore --list rc={listing.returncode} "
                                                        f"entradas={list_entries}")
        res.steps.append("pg_restore_list")
        inspection = pg_archive.inspect_archive(tmp_dump, required_tables=critical_tables,
                                                expected_dbname=identity.name)
        if not inspection["ok"]:
            raise BackupError("ARCHIVE_INVALID", "; ".join(inspection["problems"])[:STDERR_LIMIT])
        res.steps.append("archive_inspection")
        size, sha = tmp_dump.stat().st_size, sha256_file(tmp_dump)
        validation = {"status": "PASS", "pg_restore_list": True, "pg_restore_list_entries": list_entries,
                      "toc_parsed": True, "structure_walk": True, "archive_dbname_matches": True,
                      "data_blocks": inspection.get("data_blocks"), "critical_tables": list(critical_tables),
                      "missing_critical_tables": []}
        meta = {"checkpoint": "B11", "tool": "deptit_refactor.operations.backup", "tool_version": TOOL_VERSION,
                "entrypoint": None, "entrypoint_sha256": None}
        meta.update(deptit or {})
        manifest = build_manifest(created=created, identity=identity, dump_filename=final_dump.name, size=size,
                                  sha256=sha, archive=inspection, tools=tools, deptit=meta, validation=validation)
        problems = validate_manifest_document(manifest, manifest_name=final_manifest.name)
        if problems:
            raise BackupError("MANIFEST_INVALID", "; ".join(problems))
        publish_no_overwrite(tmp_dump, final_dump)
        tmp_dump = None
        res.steps.append("publish_dump")
        _reserve(tmp_manifest)
        with open(tmp_manifest, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        publish_no_overwrite(tmp_manifest, final_manifest)
        tmp_manifest = None
        _fsync_dir(d)
        res.steps.append("publish_manifest")
        res.ok, res.code = True, "PASS"
        res.dump_path, res.manifest_path, res.manifest = str(final_dump), str(final_manifest), manifest
    except BackupError as exc:
        res.code = exc.code
        res.steps.append(f"error:{exc.code}:{redact(exc.message, password)[:STDERR_LIMIT]}")
    except Exception as exc:  # cualquier otra falla -> FAIL, nunca backup válido
        res.code = "UNEXPECTED"
        res.steps.append(f"error:UNEXPECTED:{type(exc).__name__}:{redact(str(exc), password)[:500]}")
    finally:
        for p in (tmp_dump, tmp_manifest):
            if p is not None:
                try:
                    os.unlink(p)
                except OSError:
                    pass
    return res


_ENTRY_RE = re.compile(r"^app_postgresql_refactor_b\d+_[a-z0-9_]+\.py$")


def deptit_metadata(app_root, entrypoint_name: str) -> dict:
    """Entrypoint + SHA-256 para el manifest (identifica la versión de DEPTIT que generó el backup)."""
    meta = {"entrypoint": entrypoint_name, "entrypoint_sha256": None}
    p = Path(app_root) / entrypoint_name
    if _ENTRY_RE.match(entrypoint_name) and p.is_file():
        meta["entrypoint_sha256"] = sha256_file(p)
    return meta
