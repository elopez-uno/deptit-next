"""B11 — retención segura de backups.

Política (``DEPTIT_BACKUP_RETENTION_DAYS`` = N, 1..365; recomendado 14):

* se consideran SOLO backups verificados (manifest válido + dump presente + tamaño + SHA-256);
* se conserva el backup verificado más reciente de cada uno de los N días UTC más recientes con backups, y SIEMPRE el
  backup verificado más reciente de todos (nunca se borra el único/último válido);
* candidatos a borrar = el resto de los verificados;
* lo que NO se puede verificar (manifest corrupto, hash distinto, dump faltante, ``.partial``, ``.dump`` huérfano,
  archivos ajenos, enlaces) NUNCA se borra: se reporta para revisión manual;
* nunca se borra fuera del directorio configurado: solo nombres canónicos sin separadores, archivos regulares (no
  enlaces) cuyo ``resolve().parent`` es exactamente el directorio;
* dry-run por defecto; ``apply=True`` borra primero el manifest (revoca la evidencia) y después el dump, re-verificando
  cada backup inmediatamente antes de borrarlo.
"""
from __future__ import annotations

import datetime as _dt
import os
import stat
from pathlib import Path
from typing import List, Optional

from .backup_manifest import (DUMP_SUFFIX, MANIFEST_SUFFIX, NAME_RE, PARTIAL_SUFFIX, list_manifests, parse_ts,
                              utc_now, verify_backup)

RETENTION_ENV = "DEPTIT_BACKUP_RETENTION_DAYS"
RECOMMENDED_RETENTION_DAYS = 14
MAX_RETENTION_DAYS = 365


class RetentionError(ValueError):
    pass


def parse_retention_days(value) -> int:
    text = str(value if value is not None else "").strip()
    if not text:
        raise RetentionError(f"falta {RETENTION_ENV} (recomendado {RECOMMENDED_RETENTION_DAYS})")
    try:
        n = int(text)
    except ValueError:
        raise RetentionError(f"{RETENTION_ENV} debe ser un entero") from None
    if not 1 <= n <= MAX_RETENTION_DAYS:
        raise RetentionError(f"{RETENTION_ENV} debe estar entre 1 y {MAX_RETENTION_DAYS}")
    return n


def _inside(directory: Path, path: Path) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode) and path.resolve().parent == directory and os.sep not in path.name \
        and "/" not in path.name and ".." not in path.name


def plan_retention(backup_dir, keep_days: int, *, now: Optional[_dt.datetime] = None) -> dict:
    d = Path(backup_dir)
    if not d.is_absolute() or d.is_symlink() or not d.is_dir():
        raise RetentionError("el directorio de backups debe ser absoluto, existir y no ser un enlace")
    d = d.resolve()
    keep_days = parse_retention_days(keep_days)
    now = now or utc_now()
    verified, unverifiable = [], []
    referenced = set()
    for m in list_manifests(d):
        chk = verify_backup(m, now=now)
        if chk.manifest and isinstance(chk.manifest.get("dump"), dict):
            referenced.add(str(chk.manifest["dump"].get("filename")))
        if chk.ok and _inside(d, m) and _inside(d, Path(chk.dump_path)):
            verified.append({"manifest": m.name, "dump": Path(chk.dump_path).name,
                             "created_at_utc": chk.created_at_utc, "sha256": chk.manifest["dump"]["sha256"]})
        else:
            unverifiable.append({"file": m.name, "code": chk.code, "problems": chk.problems[:3]})
    others = []
    for p in sorted(d.iterdir()):
        if p.name.endswith(MANIFEST_SUFFIX) and NAME_RE.match(p.name[:-len(MANIFEST_SUFFIX)]):
            continue
        if p.name.endswith(DUMP_SUFFIX) and p.name in referenced:
            continue
        kind = ("partial" if p.name.endswith(PARTIAL_SUFFIX) else
                "orphan_dump" if p.name.endswith(DUMP_SUFFIX) else "foreign")
        others.append({"file": p.name, "kind": kind})
    verified.sort(key=lambda r: r["created_at_utc"], reverse=True)
    keep, days = set(), []
    if verified:
        keep.add(verified[0]["manifest"])
    for r in verified:
        day = parse_ts(r["created_at_utc"]).date().isoformat()
        if day not in days:
            if len(days) >= keep_days:
                continue
            days.append(day)
            keep.add(r["manifest"])
    delete = [r for r in verified if r["manifest"] not in keep]
    return {"backup_dir": str(d), "keep_days": keep_days, "now_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "verified": len(verified), "keep": [r for r in verified if r["manifest"] in keep], "delete": delete,
            "kept_days": days, "unverifiable_never_deleted": unverifiable, "other_files_never_deleted": others}


def apply_retention(plan: dict, *, now: Optional[_dt.datetime] = None) -> dict:
    """Borra los candidatos del plan.  Re-verifica cada uno antes de borrar; si algo cambió, no borra."""
    d = Path(plan["backup_dir"]).resolve()
    keep = [r["manifest"] for r in plan["keep"]]
    if not keep and plan["delete"]:
        raise RetentionError("plan inválido: borraría todos los backups válidos")
    still_valid_keep = [m for m in keep if verify_backup(d / m, now=now).ok]
    if not still_valid_keep and plan["delete"]:
        raise RetentionError("los backups a conservar ya no verifican: no se borra nada")
    deleted, skipped = [], []
    for r in plan["delete"]:
        m, dump = d / r["manifest"], d / r["dump"]
        chk = verify_backup(m, now=now)
        if not (chk.ok and _inside(d, m) and _inside(d, dump) and chk.manifest["dump"]["sha256"] == r["sha256"]):
            skipped.append({"manifest": r["manifest"], "reason": chk.code})
            continue
        os.unlink(m)
        os.unlink(dump)
        deleted.append(r["manifest"])
    return {"deleted": deleted, "skipped": skipped, "kept": keep}


def run_retention(backup_dir, keep_days, *, apply: bool = False, now: Optional[_dt.datetime] = None) -> dict:
    plan = plan_retention(backup_dir, keep_days, now=now)
    out = {"mode": "apply" if apply else "dry-run", "plan": plan}
    if apply:
        out["applied"] = apply_retention(plan, now=now)
    out["result"] = "PASS"
    return out
