"""Health operativo DETALLADO (6A-B2): herramienta administrativa local, nunca un endpoint publico.

El ``/health`` publico sigue minimo (``{status, service}``, B1).  Esta herramienta reune lo que un operador necesita:
configuracion valida, base (identidad real de la conexion de la app), storage documental (existe, lectura/escritura),
backup verificado reciente del MISMO entorno (la misma evaluacion que el gate de Crear periodo, forzado activo),
cuentas semilla activas (bloqueante fuera de desarrollo), y respuesta HTTP del backend y del frontend.
Salida: JSON sin secretos ni rutas de datos personales.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Callable, Optional

import psycopg

from db import verify_identity
from integraciones.ciclo_periodos import backup_gate

from . import bootstrap
from .config import OpsConfig


def http_get(url: str, timeout: float = 5.0) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (URL local de configuracion)
            cuerpo = r.read(4096).decode("utf-8", "replace")
            return {"ok": r.status == 200, "status": r.status, "body": cuerpo[:200]}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code}
    except (urllib.error.URLError, OSError) as exc:
        return {"ok": False, "status": 0, "error": type(exc).__name__}


def _base(cfg: OpsConfig, connect: Callable) -> dict:
    try:
        with connect(cfg.app.db.conninfo, connect_timeout=10, autocommit=False) as conn:
            conn.read_only = True
            verify_identity(conn, (cfg.app.expected_database, cfg.app.expected_db_user))
            semillas = bootstrap.auditar_semillas(conn)
            conn.rollback()
        return {"ok": True, "database": cfg.app.expected_database, "semillas": semillas}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def _storage(cfg: OpsConfig) -> dict:
    d = cfg.app.documents_dir
    ok = d.is_dir() and os.access(d, os.R_OK | os.W_OK | os.X_OK)
    return {"ok": ok, "existe": d.is_dir()}


def _backup(cfg: OpsConfig) -> dict:
    env = {**cfg.env, backup_gate.GATE_ENV: backup_gate.ACTIVO}
    d = backup_gate.evaluar(cfg.identity_url(), env=env)
    return {"ok": d.permitido, "code": d.codigo}


def revisar(cfg: OpsConfig, *, backend_url: Optional[str] = None, frontend_url: Optional[str] = None,
            connect: Callable = psycopg.connect, get: Callable = http_get) -> dict:
    checks = {"config": {"ok": True, "entorno": cfg.entorno}, "db": _base(cfg, connect), "storage": _storage(cfg),
              "backup": _backup(cfg)}
    semillas = checks["db"].get("semillas")
    if semillas is None:  # sin base no hay auditoria: desconocido, nunca "0 activas"
        checks["semillas"] = {"ok": False, "activas": None, "bloqueante": cfg.entorno != "desarrollo",
                              "error": "auditoria no disponible (base inaccesible)"}
    else:
        checks["semillas"] = {"ok": cfg.entorno == "desarrollo" or semillas["ok_para_produccion"],
                              "activas": len(semillas["semillas_activas"]),
                              "bloqueante": cfg.entorno != "desarrollo"}
    if backend_url:
        r = get(backend_url)
        checks["backend"] = {"ok": r["ok"] and _json(r).get("status") == "ok", "status": r["status"]}
    if frontend_url:
        r = get(frontend_url)
        checks["frontend"] = {"ok": r["ok"], "status": r["status"]}
    obligatorios = [k for k in checks if not (k == "backup" and cfg.entorno == "desarrollo")]
    ok = all(checks[k]["ok"] for k in obligatorios)
    return {"kind": "deptit-next-health", "result": "PASS" if ok else "FAIL", "checks": checks,
            "nota": "en desarrollo el backup reciente se informa pero no bloquea" if cfg.entorno == "desarrollo"
            else None}


def _json(r: dict) -> dict:
    try:
        return json.loads(r.get("body") or "")
    except ValueError:
        return {}
