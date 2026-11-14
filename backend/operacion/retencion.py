"""Retencion de backups (6A-B2).  IMPLEMENTADO: el mecanismo seguro y configurable.  POLITICA INSTITUCIONAL: pendiente
(6A-B4; propuesta en docs/ETAPA6_6AB2_OPERATION_RECOVERY.md).

* Base: politica certificada B11 (``ref_b11/retention.py``, copia LITERAL): solo backups VERIFICADOS; se conserva el
  mas reciente de cada uno de los N dias UTC con backups y SIEMPRE el mas reciente de todos; lo no verificable
  (manifest corrupto, hash distinto, dump faltante, ``.partial``, huerfanos, ajenos) nunca se borra; dry-run por
  defecto; ``apply`` re-verifica cada backup antes de borrarlo.
* Documentos: la misma politica sobre los manifests documentales (``backup_documentos``).
* NEXT agrega, sobre ambos planes: nunca se borra un backup mas nuevo que ``DEPTIT_BACKUP_RETENTION_MIN_HOURS``
  (default 48, 1..720) aunque la regla por dia lo marque.
* Los manifests de set son minimos y NUNCA se borran automaticamente (se informan los que quedaron sin miembros).
* ``DEPTIT_BACKUP_RETENTION_DAYS`` es obligatoria (sin default: la app nunca inventa una politica).
"""
from __future__ import annotations

import datetime as _dt
import os
import shutil
import stat
from pathlib import Path
from typing import Mapping, Optional

from integraciones.ciclo_periodos.ref_b11 import retention as R
from integraciones.ciclo_periodos.ref_b11.backup_manifest import parse_ts, utc_now

from . import backup_documentos as D
from . import backup_set
from .config import OpsConfig

MIN_HOURS_ENV = "DEPTIT_BACKUP_RETENTION_MIN_HOURS"
DEFAULT_MIN_HOURS = 48


def min_hours(env: Mapping[str, str]) -> int:
    raw = str(env.get(MIN_HOURS_ENV, "") or "").strip()
    if not raw:
        return DEFAULT_MIN_HOURS
    if not raw.isdigit() or not 1 <= int(raw) <= 720:
        raise R.RetentionError(f"{MIN_HOURS_ENV} debe ser un entero entre 1 y 720")
    return int(raw)


def _proteger_recientes(plan: dict, horas: int, now: _dt.datetime) -> dict:
    limite = now - _dt.timedelta(hours=horas)
    recientes = [r for r in plan["delete"] if parse_ts(r["created_at_utc"]) > limite]
    plan["delete"] = [r for r in plan["delete"] if r not in recientes]
    plan["keep"] = plan["keep"] + recientes
    plan["protected_recent"] = len(recientes)
    return plan


def _dentro(directorio: Path, path: Path) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return path.resolve().parent == directorio and not stat.S_ISLNK(st.st_mode) and \
        not (getattr(st, "st_file_attributes", 0) & D.FILE_ATTRIBUTE_REPARSE_POINT)


def plan_documentos(directorio: Path, keep_days: int, *, now: _dt.datetime) -> dict:
    d = Path(directorio).resolve()
    keep_days = R.parse_retention_days(keep_days)
    verified, unverifiable = [], []
    for m in D.listar(d):
        chk = D.verificar(m)
        if chk.ok and _dentro(d, m) and _dentro(d, chk.backup_dir):
            verified.append({"manifest": m.name, "dir": chk.manifest["backup_id"],
                             "created_at_utc": chk.manifest["created_at_utc"],
                             "tree_sha256": chk.manifest["tree_sha256"]})
        else:
            unverifiable.append({"file": m.name, "code": chk.code})
    conocidos = {r["manifest"] for r in verified} | {r["dir"] for r in verified} | {u["file"] for u in unverifiable}
    otros = [{"file": p.name} for p in sorted(d.iterdir()) if p.name not in conocidos]
    verified.sort(key=lambda r: r["created_at_utc"], reverse=True)
    keep, days = set(), []
    if verified:
        keep.add(verified[0]["manifest"])
    for r in verified:
        day = parse_ts(r["created_at_utc"]).date().isoformat()
        if day not in days and len(days) < keep_days:
            days.append(day)
            keep.add(r["manifest"])
    return {"backup_dir": str(d), "keep_days": keep_days, "verified": len(verified),
            "keep": [r for r in verified if r["manifest"] in keep],
            "delete": [r for r in verified if r["manifest"] not in keep], "kept_days": days,
            "unverifiable_never_deleted": unverifiable, "other_files_never_deleted": otros}


def aplicar_documentos(plan: dict) -> dict:
    d = Path(plan["backup_dir"]).resolve()
    if not plan["keep"] and plan["delete"]:
        raise R.RetentionError("plan invalido: borraria todos los backups documentales validos")
    if plan["delete"] and not any(D.verificar(d / r["manifest"]).ok for r in plan["keep"]):
        raise R.RetentionError("los backups documentales a conservar ya no verifican: no se borra nada")
    deleted, skipped = [], []
    for r in plan["delete"]:
        m, carpeta = d / r["manifest"], d / r["dir"]
        chk = D.verificar(m)
        if not (chk.ok and _dentro(d, m) and _dentro(d, carpeta) and chk.manifest["tree_sha256"] == r["tree_sha256"]):
            skipped.append({"manifest": r["manifest"], "reason": chk.code})
            continue
        os.unlink(m)  # primero se revoca la evidencia
        shutil.rmtree(carpeta)
        deleted.append(r["manifest"])
    return {"deleted": deleted, "skipped": skipped, "kept": [r["manifest"] for r in plan["keep"]]}


def ejecutar(cfg: OpsConfig, *, keep_days=None, apply: bool = False, now: Optional[_dt.datetime] = None) -> dict:
    now = now or utc_now()
    try:
        dias = keep_days if keep_days is not None else cfg.env.get(R.RETENTION_ENV, "")
        horas = min_hours(cfg.env)
        plan_db = _proteger_recientes(R.plan_retention(cfg.backup_dir, dias, now=now), horas, now)
        plan_docs = _proteger_recientes(plan_documentos(cfg.documentos_dir, dias, now=now), horas, now)
    except R.RetentionError as exc:
        return {"result": "FAIL", "code": "RETENTION_CONFIG", "detail": str(exc)}
    out = {"mode": "apply" if apply else "dry-run", "min_hours": horas, "db": {"plan": plan_db},
           "documents": {"plan": plan_docs}, "sets": _sets(cfg)}
    if apply:
        try:
            out["db"]["applied"] = R.apply_retention(plan_db, now=now)
            out["documents"]["applied"] = aplicar_documentos(plan_docs)
        except R.RetentionError as exc:
            return {**out, "result": "FAIL", "code": "RETENTION_REFUSED", "detail": str(exc)}
    out["result"] = "PASS"
    return out


def _sets(cfg: OpsConfig) -> dict:
    total, incompletos = 0, []
    for m in backup_set.listar(cfg):
        total += 1
        chk = backup_set.verificar(cfg, m, check_hash=False)
        if not chk["ok"]:
            incompletos.append({"manifest": m.name, "code": chk["code"]})
    return {"total": total, "never_deleted": True, "sin_miembros_validos": incompletos}
