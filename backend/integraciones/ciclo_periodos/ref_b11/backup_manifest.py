"""B11 — manifest versionado del backup PostgreSQL y verificador independiente.

Un backup es VÁLIDO solo si existe su manifest (escrito al final, después de publicar el dump) y el verificador lo
acepta.  Un ``.dump`` suelto, un ``.partial`` o un manifest que no coincide con su dump nunca cuentan como backup.

Manifest (``format_version`` 1, JSON UTF-8, sin secretos)::

    {
      "format_version": 1, "kind": "deptit-postgresql-backup",
      "created_at_utc": "2026-10-11T03:00:00Z",
      "database": {"host": ..., "port": 5432, "name": ..., "user": ...},          # saneado, sin contraseña
      "dump": {"filename": "deptit_<db>_<YYYYmmddTHHMMSSZ>.dump", "size": N, "sha256": "...", "format": "custom",
               "archive_version": "1.16.0", "archive_dbname": ..., "server_version": ..., "toc_entries": N,
               "tables": N},
      "tools": {"pg_dump_version": ..., "pg_restore_version": ...},
      "options": {"format": "custom", "schema": true, "data": true, "no_owner": true, "no_privileges": true},
      "deptit": {"checkpoint": "B11", "entrypoint": ..., "entrypoint_sha256": ..., "tool": ..., "tool_version": 1},
      "validation": {"status": "PASS", "pg_restore_list": true, "pg_restore_list_entries": N, "toc_parsed": true,
                     "structure_walk": true, "archive_dbname_matches": true, "critical_tables": [...],
                     "missing_critical_tables": []}
    }
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .db_identity import DatabaseIdentity

FORMAT_VERSION = 1
KIND = "deptit-postgresql-backup"
TOOL_VERSION = 1
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MANIFEST_SUFFIX = ".manifest.json"
DUMP_SUFFIX = ".dump"
PARTIAL_SUFFIX = ".partial"
NAME_RE = re.compile(r"^deptit_[A-Za-z0-9_.\-]{1,63}_\d{8}T\d{6}Z$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_MANIFEST_BYTES = 256 * 1024
FUTURE_SKEW = _dt.timedelta(minutes=5)
CHUNK = 1 << 20

# Tablas críticas que todo backup/restore debe contener.  Derivadas del código B10/B11 (tablas de tenant/identidad +
# tablas de negocio más referenciadas; ver tools/b11_readiness_lib.py::critical_tables_evidence).
CRITICAL_TABLES = (
    "instituciones", "departamentos", "app_usuarios", "sistema_flags", "periodos", "docentes", "designaciones",
    "movimientos", "materias", "carreras", "comisiones", "asignaciones_docentes_comision", "horarios_comision",
    "investigacion_docente", "extension_docente", "proyectos_investigacion", "proyectos_extension",
    "documentos_respaldo", "disposiciones",
)

TOP_KEYS = {"format_version", "kind", "created_at_utc", "database", "dump", "tools", "options", "deptit", "validation"}
DATABASE_KEYS = {"host", "port", "name", "user"}
DUMP_KEYS = {"filename", "size", "sha256", "format", "archive_version", "archive_dbname", "server_version",
             "toc_entries", "tables"}
VALIDATION_REQUIRED_TRUE = ("pg_restore_list", "toc_parsed", "structure_walk", "archive_dbname_matches")
SECRET_KEY = re.compile(r"pass|secret|token|credential", re.I)
URL_WITH_CREDENTIALS = re.compile(r"://[^/\s@]*:[^@\s]*@")


def secret_like_paths(obj, prefix=""):
    """Rutas de claves con nombre de secreto o valores con forma de URL con credenciales."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            if SECRET_KEY.search(str(k)):
                out.append(path)
            out += secret_like_paths(v, path)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += secret_like_paths(v, f"{prefix}[{i}]")
    elif isinstance(obj, str) and URL_WITH_CREDENTIALS.search(obj):
        out.append(prefix)
    return out


def utc_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)


def format_ts(ts: _dt.datetime) -> str:
    return ts.astimezone(_dt.timezone.utc).strftime(TIMESTAMP_FORMAT)


def parse_ts(text) -> _dt.datetime:
    return _dt.datetime.strptime(str(text), TIMESTAMP_FORMAT).replace(tzinfo=_dt.timezone.utc)


def backup_basename(identity: DatabaseIdentity, created: _dt.datetime) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.\-]", "_", identity.name)[:63] or "db"
    return f"deptit_{safe}_{created.astimezone(_dt.timezone.utc):%Y%m%dT%H%M%SZ}"


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def build_manifest(*, created: _dt.datetime, identity: DatabaseIdentity, dump_filename: str, size: int, sha256: str,
                   archive: dict, tools: dict, deptit: dict, validation: dict) -> dict:
    return {
        "format_version": FORMAT_VERSION, "kind": KIND, "created_at_utc": format_ts(created),
        "database": identity.sanitized(),
        "dump": {"filename": dump_filename, "size": int(size), "sha256": sha256, "format": "custom",
                 "archive_version": archive.get("archive_version"), "archive_dbname": archive.get("dbname"),
                 "server_version": archive.get("server_version"), "toc_entries": archive.get("toc_entries"),
                 "tables": archive.get("tables")},
        "tools": dict(tools),
        "options": {"format": "custom", "schema": True, "data": True, "no_owner": True, "no_privileges": True},
        "deptit": dict(deptit),
        "validation": dict(validation),
    }


def validate_manifest_document(doc, manifest_name: Optional[str] = None) -> List[str]:
    """Problemas de esquema del manifest (lista vacía = válido).  Puro: no toca el filesystem."""
    p = []
    if not isinstance(doc, dict):
        return ["manifest no es un objeto JSON"]
    if set(doc) != TOP_KEYS:
        p.append(f"claves de primer nivel inesperadas: faltan={sorted(TOP_KEYS - set(doc))} "
                 f"sobran={sorted(set(doc) - TOP_KEYS)}")
    if doc.get("format_version") != FORMAT_VERSION:
        p.append(f"format_version {doc.get('format_version')!r} no soportado")
    if doc.get("kind") != KIND:
        p.append("kind inválido")
    try:
        parse_ts(doc.get("created_at_utc"))
    except (TypeError, ValueError):
        p.append("created_at_utc inválido (se espera YYYY-mm-ddTHH:MM:SSZ)")
    db = doc.get("database")
    if not isinstance(db, dict) or set(db) != DATABASE_KEYS:
        p.append("database inválido")
    else:
        if not all(isinstance(db[k], str) and db[k] for k in ("host", "name", "user")):
            p.append("database.host/name/user deben ser strings no vacíos")
        if not isinstance(db["port"], int) or isinstance(db["port"], bool) or not 0 < db["port"] < 65536:
            p.append("database.port inválido")
    dump = doc.get("dump")
    if not isinstance(dump, dict) or set(dump) != DUMP_KEYS:
        p.append("dump inválido")
    else:
        fname = dump.get("filename")
        if not isinstance(fname, str) or not fname.endswith(DUMP_SUFFIX) or not NAME_RE.match(fname[:-len(DUMP_SUFFIX)]):
            p.append("dump.filename inválido (se espera deptit_<db>_<YYYYmmddTHHMMSSZ>.dump, sin rutas)")
        elif manifest_name is not None and manifest_name != fname[:-len(DUMP_SUFFIX)] + MANIFEST_SUFFIX:
            p.append("el manifest no corresponde al dump (nombres distintos)")
        if not isinstance(dump.get("size"), int) or isinstance(dump.get("size"), bool) or dump["size"] <= 0:
            p.append("dump.size inválido")
        if not isinstance(dump.get("sha256"), str) or not SHA_RE.match(dump["sha256"]):
            p.append("dump.sha256 inválido")
        if dump.get("format") != "custom":
            p.append("dump.format != custom")
    val = doc.get("validation")
    if not isinstance(val, dict):
        p.append("validation inválido")
    else:
        if val.get("status") != "PASS":
            p.append(f"validation.status {val.get('status')!r} != PASS")
        for k in VALIDATION_REQUIRED_TRUE:
            if val.get(k) is not True:
                p.append(f"validation.{k} != true")
        if val.get("missing_critical_tables") != []:
            p.append("validation.missing_critical_tables no vacío")
    opts = doc.get("options")
    if not isinstance(opts, dict) or opts.get("format") != "custom" or opts.get("schema") is not True \
            or opts.get("data") is not True:
        p.append("options inválido (se espera custom con esquema + datos)")
    for key in ("tools", "deptit"):
        if not isinstance(doc.get(key), dict):
            p.append(f"{key} inválido")
    leaked = secret_like_paths(doc)
    if leaked:
        p.append(f"el manifest contiene campos con forma de secreto: {leaked[:3]}")
    return p


@dataclass
class BackupCheck:
    """Resultado de verificar un manifest + su dump."""
    manifest_path: str
    ok: bool = False
    code: str = "UNCHECKED"
    problems: List[str] = field(default_factory=list)
    manifest: Optional[dict] = None
    created_at_utc: Optional[str] = None
    age_hours: Optional[float] = None
    dump_path: Optional[str] = None

    def summary(self) -> dict:
        return {"manifest": os.path.basename(self.manifest_path), "ok": self.ok, "code": self.code,
                "problems": self.problems[:5], "created_at_utc": self.created_at_utc,
                "age_hours": None if self.age_hours is None else round(self.age_hours, 2)}


def _is_plain_file(path: Path) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode)


def load_manifest(path) -> dict:
    path = Path(path)
    if not _is_plain_file(path):
        raise ValueError("manifest inexistente o no es un archivo regular")
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("manifest demasiado grande")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_backup(manifest_path, *, expected_identity: Optional[DatabaseIdentity] = None,
                  max_age_hours: Optional[float] = None, now: Optional[_dt.datetime] = None,
                  check_hash: bool = True) -> BackupCheck:
    """Verificación completa y fail-closed de UN backup.  Orden: esquema -> identidad -> edad -> archivo -> tamaño ->
    SHA-256 (lo caro al final).  ``code`` = primer motivo de rechazo o ``VALID``."""
    path = Path(manifest_path)
    res = BackupCheck(str(path))
    now = now or utc_now()
    try:
        doc = load_manifest(path)
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        res.code, res.problems = "MANIFEST_INVALID", [f"manifest ilegible: {type(exc).__name__}"]
        return res
    res.manifest = doc
    problems = validate_manifest_document(doc, manifest_name=path.name)
    if problems:
        only_validation = all(x.startswith("validation.") for x in problems)
        res.code = "VALIDATION_NOT_PASSED" if only_validation else "MANIFEST_INVALID"
        res.problems = problems
        return res
    created = parse_ts(doc["created_at_utc"])
    res.created_at_utc = doc["created_at_utc"]
    res.age_hours = (now - created).total_seconds() / 3600.0
    if expected_identity is not None:
        db = doc["database"]
        got = DatabaseIdentity(db["host"], db["port"], db["name"], db["user"])
        if not got.same_database(expected_identity) or doc["dump"].get("archive_dbname") != expected_identity.name:
            res.code, res.problems = "OTHER_DATABASE", ["el backup corresponde a otra base de datos"]
            return res
    if created - now > FUTURE_SKEW:
        res.code, res.problems = "FUTURE_TIMESTAMP", ["created_at_utc está en el futuro"]
        return res
    if max_age_hours is not None and res.age_hours > float(max_age_hours):
        res.code, res.problems = "EXPIRED", [f"backup de {res.age_hours:.1f} h > máximo {max_age_hours} h"]
        return res
    dump_path = path.parent / doc["dump"]["filename"]
    res.dump_path = str(dump_path)
    if dump_path.resolve().parent != path.parent.resolve() or not _is_plain_file(dump_path):
        res.code, res.problems = "DUMP_MISSING", ["el dump del manifest no existe en el directorio de backups"]
        return res
    size = dump_path.stat().st_size
    if size != doc["dump"]["size"]:
        res.code, res.problems = "SIZE_MISMATCH", [f"tamaño {size} != manifest {doc['dump']['size']}"]
        return res
    if check_hash:
        if sha256_file(dump_path) != doc["dump"]["sha256"]:
            res.code, res.problems = "HASH_MISMATCH", ["SHA-256 del dump != manifest"]
            return res
    res.ok, res.code = True, "VALID"
    return res


def list_manifests(backup_dir) -> List[Path]:
    """Manifests candidatos (no recursivo; solo archivos regulares con nombre canónico; sin enlaces)."""
    d = Path(backup_dir)
    out = []
    for p in sorted(d.iterdir()):
        if p.name.endswith(MANIFEST_SUFFIX) and NAME_RE.match(p.name[:-len(MANIFEST_SUFFIX)]) and _is_plain_file(p):
            out.append(p)
    return out
