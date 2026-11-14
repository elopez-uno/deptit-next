"""Esquema base versionado de NEXT (6A-B2; diseño 6A-01: "la base productiva se crea desde el esquema de
``deptit_next_dev``, versionado en ``migration/schema/``").

* ``generar``: ``pg_dump --schema-only --no-owner --no-privileges --format=plain`` con el rol de backup (solo lectura) a
  ``migration/schema/0001_baseline_schema.sql`` + ``.manifest.json`` (SHA-256, huella del catalogo, versiones).  Sin
  datos: una base nueva nace SIN cuentas (ni semillas ni credenciales); el primer superadmin se crea con el bootstrap.
* ``aplicar``: SOLO sobre una base de prueba ``deptit_next_restore_test_*`` (restore drill), con ``psql
  --single-transaction -v ON_ERROR_STOP=1`` como el rol de restore, y se compara la huella del esquema resultante con
  la del origen.  La instalacion real la ejecuta el owner siguiendo el runbook (nunca el arranque de la app).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

import psycopg

import settings as app_settings
from integraciones.ciclo_periodos.ref_b11.backup import find_binary, tool_version
from integraciones.ciclo_periodos.ref_b11.backup_manifest import format_ts, sha256_file, utc_now
from integraciones.ciclo_periodos.ref_b11.db_identity import identity_from_url, libpq_environment, redact

from . import comparacion
from .config import RESTORE_TEST_RE, OpsConfig
from .restore_db import huella_base

SCHEMA_DIR = app_settings.REPO_DIR / "migration" / "schema"
BASELINE = "0001_baseline_schema.sql"
DATOS = re.compile(r"^\s*(COPY|INSERT INTO)\s", re.M)
# Sin ``--schema=public``: pg_dump emitiria la creacion de ``public``, que ya existe en toda base nueva.  El volcado
# completo no la emite (ni la extension integrada plpgsql); cualquier esquema adicional se rechaza.
ESQUEMA_EXTRA = re.compile(r"^\s*CREATE\s+SCHEMA\s", re.M | re.I)


def generar(cfg: OpsConfig, *, destino: Path = SCHEMA_DIR, runner: Callable = subprocess.run,
            which: Callable = shutil.which, connect: Callable = psycopg.connect,
            now: Optional[_dt.datetime] = None) -> dict:
    report = {"kind": "deptit-next-schema-baseline", "result": "FAIL", "code": None}
    cred = cfg.backup
    if cred is None:
        return {**report, "code": "BACKUP_ROLE_MISSING"}
    pg_dump = find_binary("pg_dump", which=which, bin_dir=cfg.pg_bin_dir)
    if not pg_dump:
        return {**report, "code": "PG_DUMP_MISSING"}
    destino.mkdir(parents=True, exist_ok=True)
    sql, manifest = destino / BASELINE, destino / (BASELINE + ".manifest.json")
    tmp = destino / f".{BASELINE}.partial"
    ident = identity_from_url(cfg.url(cred))
    try:
        with libpq_environment(ident, cred.password, {"PGSSLMODE": cfg.app.db.sslmode}) as env:
            proc = runner([pg_dump, "--schema-only", "--no-owner", "--no-privileges", "--format=plain",
                           "--no-password", "--file", str(tmp)], env=env, capture_output=True,
                          text=True)
        if proc.returncode != 0:
            return {**report, "code": "PG_DUMP_FAILED",
                    "detail": redact(proc.stderr, cred.password)[-2000:]}
        texto = tmp.read_text(encoding="utf-8")
        if DATOS.search(texto):
            return {**report, "code": "DATA_IN_SCHEMA", "detail": "el esquema base no puede contener datos"}
        if ESQUEMA_EXTRA.search(texto):
            return {**report, "code": "UNEXPECTED_SCHEMA", "detail": "el esquema base solo admite el esquema public"}
        huella = huella_base(cfg, cred, cfg.app.expected_database, connect=connect)["esquema"]
        tmp.replace(sql)
        doc = {"format_version": 1, "kind": "deptit-next-schema-baseline", "archivo": BASELINE,
               "sha256": sha256_file(sql), "size": sql.stat().st_size,
               "generado_utc": format_ts((now or utc_now())), "origen": cfg.app.expected_database,
               "pg_dump_version": tool_version(pg_dump, runner), "esquema_sha256": huella["sha256"],
               "tablas": len(huella["tablas"]), "restricciones": len(huella["restricciones"]),
               "indices": len(huella["indices"]), "secuencias": len(huella["secuencias"]),
               "opciones": ["--schema-only", "--no-owner", "--no-privileges"],
               "contiene_datos": False}
        manifest.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        report.update(result="PASS", code="PASS", manifest=str(manifest), sha256=doc["sha256"],
                      esquema_sha256=doc["esquema_sha256"], tablas=doc["tablas"])
        return report
    finally:
        if tmp.exists():
            tmp.unlink()


def verificar_archivo(destino: Path = SCHEMA_DIR) -> dict:
    sql, manifest = destino / BASELINE, destino / (BASELINE + ".manifest.json")
    try:
        doc = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": False, "code": "MANIFEST_INVALID"}
    if not sql.is_file() or sha256_file(sql) != doc.get("sha256"):
        return {"ok": False, "code": "HASH_MISMATCH"}
    if DATOS.search(sql.read_text(encoding="utf-8")):
        return {"ok": False, "code": "DATA_IN_SCHEMA"}
    return {"ok": True, "code": "VALID", "esquema_sha256": doc["esquema_sha256"], "manifest": doc}


def aplicar_en_prueba(cfg: OpsConfig, target: str, *, destino: Path = SCHEMA_DIR, runner: Callable = subprocess.run,
                      which: Callable = shutil.which, connect: Callable = psycopg.connect) -> dict:
    """Aplica el esquema base en una base de prueba VACIA ya creada y compara la huella con la del manifest."""
    report = {"kind": "deptit-next-schema-apply-test", "target": target, "result": "FAIL", "code": None}
    if not RESTORE_TEST_RE.match(target or ""):
        return {**report, "code": "TARGET_NOT_ISOLATED"}
    cred = cfg.restore
    if cred is None:
        return {**report, "code": "RESTORE_ROLE_MISSING"}
    chk = verificar_archivo(destino)
    if not chk["ok"]:
        return {**report, "code": f"BASELINE_{chk['code']}"}
    psql = find_binary("psql", which=which, bin_dir=cfg.pg_bin_dir)
    if not psql:
        return {**report, "code": "PSQL_MISSING"}
    ident = identity_from_url(cfg.url(cred, target))
    with libpq_environment(ident, cred.password, {"PGSSLMODE": cfg.app.db.sslmode}, database=target) as env:
        proc = runner([psql, "-X", "--no-password", "--single-transaction", "-v", "ON_ERROR_STOP=1", "-q",
                       "-f", str(destino / BASELINE)], env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        return {**report, "code": "PSQL_FAILED", "detail": redact(proc.stderr, cred.password)[-2000:]}
    huella = huella_base(cfg, cred, target, connect=connect)
    report.update(esquema_sha256=huella["esquema"]["sha256"], esperado=chk["esquema_sha256"],
                  filas=sum(v["filas"] for v in huella["datos"]["tablas"].values()))
    if huella["esquema"]["sha256"] != chk["esquema_sha256"]:
        return {**report, "code": "SCHEMA_MISMATCH"}
    if report["filas"] != 0:
        return {**report, "code": "NOT_EMPTY"}
    report["result"], report["code"] = "PASS", "SCHEMA_APPLIED"
    report["huella"] = comparacion.resumen(huella)
    return report
