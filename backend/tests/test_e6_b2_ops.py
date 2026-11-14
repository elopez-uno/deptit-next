"""Etapa 6A-B2: scripts operativos locales (``ops/deptit-ops.ps1``): start / status / doble arranque / stop / estado
obsoleto / PID reutilizado / rotacion de logs.  Los procesos son servidores HTTP de prueba (``python -m http.server``)
en puertos propios: nunca se toca la aplicacion real ni ningun proceso ajeno.  La prueba con backend y frontend reales
es el smoke operativo del bloque."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[2] / "ops" / "deptit-ops.ps1"


def _libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _escucha(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture
def ops(tmp_path):
    pb, pf = _libre(), _libre()
    (tmp_path / "www_b").mkdir()
    (tmp_path / "www_f").mkdir()
    py = sys.executable.replace("'", "''")
    cfg = tmp_path / "ops.test.psd1"
    cfg.write_text(f"""@{{
    BackendExe = '{py}'
    BackendArgs = @('-m', 'http.server', '{pb}', '--bind', '127.0.0.1')
    BackendDir = '{tmp_path / "www_b"}'
    BackendPort = {pb}
    BackendHealthPath = '/'
    FrontendExe = '{py}'
    FrontendArgs = @('-m', 'http.server', '{pf}', '--bind', '127.0.0.1')
    FrontendDir = '{tmp_path / "www_f"}'
    FrontendPort = {pf}
    FrontendHealthPath = '/'
    RunDir = '{tmp_path / "run"}'
    LogDir = '{tmp_path / "logs"}'
    LogMaxBytes = 100
    LogKeep = 2
    StartTimeoutSec = 30
}}
""", encoding="utf-8")

    def run(action, env=None):
        # Salida a ARCHIVO, no a un pipe: los procesos que arranca el script heredan los handles del padre y un pipe
        # quedaria abierto mientras vivan (subprocess esperaria el EOF).
        salida = tmp_path / f"salida_{action}_{time.time_ns()}.txt"
        with open(salida, "wb") as fh:
            p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(OPS), "-Entorno",
                                "desarrollo", "-Action", action, "-Config", str(cfg)], stdout=fh, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, timeout=120, env={**os.environ, **(env or {})})
        return p.returncode, salida.read_bytes().decode("utf-8", "replace")
    yield run, tmp_path, pb, pf
    run("stop")
    assert not _escucha(pb) and not _escucha(pf)


def _estado(tmp_path, name):
    return json.loads((tmp_path / "run" / f"{name}.json").read_text(encoding="utf-8-sig"))


def test_start_status_doble_start_stop(ops):
    run, tmp, pb, pf = ops
    rc, out = run("status")
    assert rc == 1 and '"stopped"' in out
    rc, out = run("start")
    assert rc == 0, out
    assert _escucha(pb) and _escucha(pf)
    pid_b, pid_f = _estado(tmp, "backend")["pid"], _estado(tmp, "frontend")["pid"]
    rc, out = run("status")
    assert rc == 0 and out.count('"running"') == 2, out
    rc, out = run("start")
    assert rc == 2 and "doble arranque rechazado" in out, out
    assert _estado(tmp, "backend")["pid"] == pid_b and _estado(tmp, "frontend")["pid"] == pid_f
    assert _escucha(pb) and _escucha(pf)  # el segundo start no toco los procesos vivos
    rc, out = run("stop")
    assert rc == 0 and "detenido" in out, out
    assert not _escucha(pb) and not _escucha(pf)
    assert not (tmp / "run" / "backend.json").exists() and not (tmp / "run" / "frontend.json").exists()
    rc, out = run("status")
    assert rc == 1
    assert (tmp / "logs" / "backend.err.log").exists() and not list((tmp / "logs").glob("*.current"))


def test_estado_obsoleto_y_pid_reutilizado_no_se_tocan(ops):
    run, tmp, pb, pf = ops
    (tmp / "run").mkdir(exist_ok=True)
    # PID inexistente
    (tmp / "run" / "backend.json").write_text(json.dumps({"pid": 999999, "creation_utc": "x", "marker": "x"}),
                                             encoding="utf-8")
    # PID VIVO pero de otro proceso (este mismo pytest): jamas se detiene
    (tmp / "run" / "frontend.json").write_text(json.dumps({"pid": os.getpid(), "creation_utc": "2000-01-01",
                                                           "marker": "http.server"}), encoding="utf-8")
    rc, out = run("status")
    assert rc == 1 and out.count('"stale"') == 2, out
    rc, out = run("stop")
    assert rc == 0 and out.count("no se detuvo ningun proceso") == 2, out
    assert not (tmp / "run" / "backend.json").exists() and not (tmp / "run" / "frontend.json").exists()
    # seguimos vivos (el PID del pytest no fue detenido)


def test_puerto_ocupado_impide_arrancar(ops):
    run, tmp, pb, pf = ops
    with socket.socket() as s:
        s.bind(("127.0.0.1", pb))
        s.listen()
        rc, out = run("start")
    assert rc == 2 and "ya esta en uso" in out, out
    assert not (tmp / "run" / "backend.json").exists() and not _escucha(pf)


def test_rotacion_de_logs_conservadora(ops):
    run, tmp, pb, pf = ops
    logs = tmp / "logs"
    logs.mkdir(exist_ok=True)
    (logs / "backend.out.log").write_text("x" * 500, encoding="utf-8")
    for i, stamp in enumerate(("20260101-000000", "20260102-000000", "20260103-000000", "20260104-000000")):
        (logs / f"backend.out.log.{stamp}").write_text("viejo", encoding="utf-8")
    ajeno = tmp / "ajeno.log"
    ajeno.write_text("fuera de la raiz", encoding="utf-8")
    (logs / "notas.txt").write_text("no es un log rotado", encoding="utf-8")
    rc, out = run("rotate-logs")
    assert rc == 0, out
    rotados = sorted(p.name for p in logs.glob("backend.out.log.*"))
    assert len(rotados) == 2 and not (logs / "backend.out.log").exists(), rotados
    assert ajeno.exists() and (logs / "notas.txt").exists()


FALSA_CLI = r'''import json, os, sys
sys.stderr.write("2026-01-01T00:00:00 deptit.operacion inicio comando=%s\n" % sys.argv[1])
sys.stderr.write("evento por stderr\n")
print(json.dumps({"kind": "falsa", "comando": sys.argv[1], "argv": sys.argv[2:]}))
sys.exit(int(os.environ.get("ZZ_FALSA_RC", "0")))
'''


def _cli_falsa(tmp):
    """``python -m operacion`` falso en el BackendDir (cwd del script): escribe eventos por stderr como la real."""
    pkg = tmp / "www_b" / "operacion"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "__main__.py").write_text(FALSA_CLI, encoding="utf-8")


def test_health_y_backup_toleran_stderr_de_la_cli(ops):
    """Windows PowerShell 5.1 con ErrorActionPreference=Stop convertia el stderr de la CLI en NativeCommandError
    (hallazgo del smoke real de B2): ``health`` y ``backup`` deben propagar el codigo de la CLI, no una excepcion."""
    run, tmp, pb, pf = ops
    _cli_falsa(tmp)
    rc, out = run("start")
    assert rc == 0, out
    rc, out = run("health")
    assert rc == 0 and "NativeCommandError" not in out and '"comando": "health"' in out, out
    assert "--backend-url" in out and f"127.0.0.1:{pb}/" in out
    rc, out = run("health", env={"ZZ_FALSA_RC": "2"})
    assert rc == 2 and "NativeCommandError" not in out, out
    rc, out = run("backup")
    assert rc == 0 and "NativeCommandError" not in out and '"comando": "backup-set"' in out, out
    log = (tmp / "logs" / "backup.log").read_text(encoding="utf-8-sig")
    assert "backup-set rc=0" in log and "evento por stderr" in log  # stderr de la CLI queda en el log como texto
    rc, out = run("backup", env={"ZZ_FALSA_RC": "2"})
    assert rc == 2 and "NativeCommandError" not in out, out
