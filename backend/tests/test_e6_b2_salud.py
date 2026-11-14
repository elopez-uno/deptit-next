"""Etapa 6A-B2: health operativo detallado (``python -m operacion health``; docs/ETAPA6_6AB2_OPERATION_RECOVERY.md).

Contra deptit_next_dev REAL (identidad de la conexion de la app, auditoria de semillas) y con respuestas HTTP falsas.
Hallazgo del smoke real de B2: la identidad se verificaba con un dict en vez de la tupla (base, usuario) y el health
fallaba siempre con DatabaseGuardError; ademas, sin base, las semillas se informaban como "0 activas"."""

from __future__ import annotations

import dataclasses
import json

import pytest

from operacion import config, salud


@pytest.fixture(scope="module")
def cfg():
    return config.load()


def _get(respuestas):
    return lambda url: respuestas[url]


OK_BACKEND = {"ok": True, "status": 200, "body": json.dumps({"status": "ok", "service": "deptit-next"})}
OK_FRONTEND = {"ok": True, "status": 200, "body": "{}"}
URLS = {"http://b/health": OK_BACKEND, "http://f/api/backend-health": OK_FRONTEND}


def test_health_real_en_desarrollo(cfg):
    r = salud.revisar(cfg, backend_url="http://b/health", frontend_url="http://f/api/backend-health", get=_get(URLS))
    assert r["result"] == "PASS", r
    c = r["checks"]
    assert c["db"]["ok"] and c["db"]["database"] == "deptit_next_dev"
    assert c["semillas"] == {"ok": True, "activas": 3, "bloqueante": False}  # dev: informadas, no bloquean
    assert c["backend"] == {"ok": True, "status": 200} and c["frontend"] == {"ok": True, "status": 200}
    assert c["storage"]["ok"] and "nota" in r


def test_semillas_bloquean_fuera_de_desarrollo(cfg):
    # misma base real (dev tiene las 3 semillas); solo cambia el entorno declarado
    prod = dataclasses.replace(cfg, app=dataclasses.replace(cfg.app, entorno="produccion"))
    assert prod.entorno == "produccion"
    r = salud.revisar(prod, get=_get(URLS))
    assert r["result"] == "FAIL" and r["checks"]["semillas"] == {"ok": False, "activas": 3, "bloqueante": True}


def test_identidad_incorrecta_o_base_caida(cfg):
    otra = dataclasses.replace(cfg, app=dataclasses.replace(cfg.app, expected_db_user="deptit_next_otro"))
    r = salud.revisar(otra, get=_get(URLS))
    assert r["result"] == "FAIL" and r["checks"]["db"] == {"ok": False, "error": "DatabaseGuardError"}
    assert r["checks"]["semillas"]["activas"] is None and r["checks"]["semillas"]["ok"] is False

    def caida(*a, **k):
        raise OSError("sin servidor")
    r = salud.revisar(cfg, connect=caida, get=_get(URLS))
    assert r["result"] == "FAIL" and r["checks"]["db"]["error"] == "OSError"
    assert r["checks"]["semillas"]["activas"] is None


def test_backend_o_frontend_caidos(cfg):
    malas = {"http://b/health": {"ok": True, "status": 200, "body": "no json"},
             "http://f/api/backend-health": {"ok": False, "status": 502}}
    r = salud.revisar(cfg, backend_url="http://b/health", frontend_url="http://f/api/backend-health", get=_get(malas))
    assert r["result"] == "FAIL" and not r["checks"]["backend"]["ok"] and r["checks"]["frontend"]["status"] == 502


def test_salida_sin_secretos(cfg):
    r = json.dumps(salud.revisar(cfg, backend_url="http://b/health", get=_get(URLS)))
    for secreto in (cfg.app.db.password, getattr(cfg.backup, "password", None), getattr(cfg.restore, "password", None)):
        assert not secreto or secreto not in r
    assert "postgresql://" not in r and "pbkdf2" not in r
