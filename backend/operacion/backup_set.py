"""Backup set (6A-B2): UN identificador comun para el backup de base y el documental de una misma corrida.

``<DEPTIT_BACKUP_DIR>/sets/deptit_set_<entorno>_<YYYYmmddTHHMMSSZ>.manifest.json``::

    {"format_version": 1, "kind": "deptit-next-backup-set", "set_id", "entorno", "created_at_utc", "finished_at_utc",
     "modo": "en_linea" | "app_detenida",
     "db": {"backup_id", "manifest", "manifest_sha256", "dump_sha256"},
     "documents": {"backup_id", "manifest", "manifest_sha256", "tree_sha256", "count"},
     "consistencia": {"db_snapshot_utc", "documents_from_utc", "documents_to_utc", "ventana_segundos", "nivel"},
     "validation": {"status": "PASS"}}

Consistencia (sin promesas falsas): el dump es una foto TRANSACCIONAL de la base (``pg_dump`` usa un snapshot); el
storage documental se copia DESPUES, archivo por archivo, sin transaccion comun con la base.  Orden elegido: base
primero, documentos inmediatamente despues -> en un restore, todo documento referenciado por la base existe salvo que se
haya BORRADO durante la ventana; pueden sobrar documentos creados durante la ventana (inocuo).  ``modo=app_detenida``
(el script operativo detiene la app antes y la levanta despues; aca se verifica que el backend no responda) elimina la
ventana de escritura: consistencia completa entre ambos.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import socket
import stat
from pathlib import Path
from typing import Callable, List, Optional

from integraciones.ciclo_periodos.ref_b11.backup import publish_no_overwrite
from integraciones.ciclo_periodos.ref_b11.backup_manifest import format_ts, parse_ts, sha256_file, utc_now, verify_backup
from integraciones.ciclo_periodos.ref_b11.db_identity import identity_from_url

from . import backup_db, backup_documentos
from .config import OpsConfig

FORMAT_VERSION = 1
KIND = "deptit-next-backup-set"
NAME_RE = re.compile(r"^deptit_set_(desarrollo|preproduccion|produccion)_\d{8}T\d{6}Z$")
EN_LINEA, APP_DETENIDA = "en_linea", "app_detenida"
NIVEL = {EN_LINEA: "base transaccional; documentos copiados despues (ventana indicada, sin transaccion comun)",
         APP_DETENIDA: "aplicacion detenida durante el set: base y documentos consistentes entre si"}


def set_id_de(entorno: str, created: _dt.datetime) -> str:
    return f"deptit_set_{entorno}_{created.astimezone(_dt.timezone.utc):%Y%m%dT%H%M%SZ}"


def backend_responde(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _escribir(path: Path, doc: dict) -> None:
    tmp = path.parent / f".{path.name}.partial"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        publish_no_overwrite(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def respaldar(cfg: OpsConfig, *, modo: str = EN_LINEA, now: Optional[_dt.datetime] = None,
              backup_db_fn: Callable = backup_db.respaldar, docs_fn: Callable = backup_documentos.respaldar,
              responde: Callable = backend_responde) -> dict:
    created = (now or utc_now()).astimezone(_dt.timezone.utc).replace(microsecond=0)
    set_id = set_id_de(cfg.entorno, created)
    report = {"kind": "deptit-next-backup-set-run", "set_id": set_id, "entorno": cfg.entorno, "modo": modo,
              "result": "FAIL", "code": None}
    if modo not in NIVEL:
        return {**report, "code": "MODE_INVALID"}
    if modo == APP_DETENIDA and responde(cfg.app.backend_host, cfg.app.backend_port):
        return {**report, "code": "APP_RUNNING", "detail": "modo app_detenida pero el backend responde"}
    db = backup_db_fn(cfg, set_id=set_id, now=created)
    report["db"] = db
    if db.get("result") != "PASS":
        report["code"] = "DB_BACKUP_FAILED"
        return report
    desde = utc_now()
    docs = docs_fn(cfg.app.documents_dir, cfg.documentos_dir, entorno=cfg.entorno, set_id=set_id, now=created)
    hasta = utc_now()
    report["documents"] = docs
    if docs.get("result") != "PASS":
        report["code"] = "DOCUMENTS_BACKUP_FAILED"
        report["detail"] = "el backup de base es valido por si mismo; el set NO se publico"
        return report
    db_manifest, docs_manifest = Path(db["manifest"]), Path(docs["manifest"])
    doc = {"format_version": FORMAT_VERSION, "kind": KIND, "set_id": set_id, "entorno": cfg.entorno,
           "created_at_utc": format_ts(created), "finished_at_utc": format_ts(utc_now()), "modo": modo,
           "db": {"backup_id": db["backup_id"], "manifest": db_manifest.name,
                  "manifest_sha256": sha256_file(db_manifest), "dump_sha256": db["sha256"]},
           "documents": {"backup_id": docs["backup_id"], "manifest": docs_manifest.name,
                         "manifest_sha256": sha256_file(docs_manifest), "tree_sha256": docs["tree_sha256"],
                         "count": docs["count"]},
           "consistencia": {"db_snapshot_utc": format_ts(created), "documents_from_utc": format_ts(desde),
                            "documents_to_utc": format_ts(hasta),
                            "ventana_segundos": int((hasta - created).total_seconds()), "nivel": NIVEL[modo]},
           "validation": {"status": "PASS"}}
    destino = cfg.sets_dir / f"{set_id}.manifest.json"
    _escribir(destino, doc)
    chk = verificar(cfg, destino)
    report.update({"manifest": str(destino), "verificacion": chk})
    report["result"], report["code"] = ("PASS", "PASS") if chk["ok"] else ("FAIL", f"POST_VERIFY_{chk['code']}")
    return report


def verificar(cfg: OpsConfig, manifest_path, *, check_hash: bool = True) -> dict:
    """Set valido = manifest propio + ambos miembros presentes, intactos (SHA-256 del manifest) y validos."""
    path = Path(manifest_path)
    out = {"manifest": path.name, "ok": False, "code": "UNCHECKED", "problems": []}
    try:
        st = os.lstat(path)
        if not stat.S_ISREG(st.st_mode) or not NAME_RE.match(path.name[:-len(".manifest.json")]):
            raise ValueError("nombre o tipo invalido")
        doc = json.loads(path.read_text(encoding="utf-8"))
        parse_ts(doc["created_at_utc"])
        if doc.get("kind") != KIND or doc.get("format_version") != FORMAT_VERSION or \
                doc.get("set_id") + ".manifest.json" != path.name or doc.get("validation", {}).get("status") != "PASS":
            raise ValueError("manifest de set invalido")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        out.update(code="MANIFEST_INVALID", problems=[type(exc).__name__])
        return out
    if doc["entorno"] != cfg.entorno:
        out.update(code="OTHER_ENVIRONMENT", problems=["el set es de otro entorno"])
        return out
    db_m = cfg.backup_dir / Path(doc["db"]["manifest"]).name
    docs_m = cfg.documentos_dir / Path(doc["documents"]["manifest"]).name
    for m, esperado in ((db_m, doc["db"]["manifest_sha256"]), (docs_m, doc["documents"]["manifest_sha256"])):
        if not m.is_file() or sha256_file(m) != esperado:
            out.update(code="MEMBER_MISSING_OR_CHANGED", problems=[f"{m.name}: falta o cambio"])
            return out
    db_chk = verify_backup(db_m, expected_identity=identity_from_url(cfg.identity_url()), check_hash=check_hash)
    docs_chk = backup_documentos.verificar(docs_m, entorno=cfg.entorno, check_hash=check_hash)
    out["db"], out["documents"] = db_chk.summary(), docs_chk.summary()
    if not db_chk.ok or not docs_chk.ok:
        out.update(code="MEMBER_INVALID", problems=[f"db={db_chk.code}", f"documents={docs_chk.code}"])
        return out
    if db_chk.manifest["deptit"].get("set_id") != doc["set_id"] or docs_chk.manifest["set_id"] != doc["set_id"]:
        out.update(code="SET_ID_MISMATCH", problems=["los miembros no pertenecen a este set"])
        return out
    out.update(ok=True, code="VALID", set_id=doc["set_id"], modo=doc["modo"], consistencia=doc["consistencia"])
    return out


def listar(cfg: OpsConfig) -> List[Path]:
    d = cfg.sets_dir
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.name.endswith(".manifest.json")
                  and NAME_RE.match(p.name[:-len(".manifest.json")]))

