"""Etapa 6A-B3: perfiles de entorno de ``ops/deptit-ops.ps1`` (docs/ETAPA6_6AB3_LOCAL_PILOT.md).

* ``-Entorno`` es obligatorio: sin el, el script no hace nada.
* Los procesos de un perfil arrancan SIN las variables DEPTIT_* / DATABASE_URL heredadas y solo con las de sus
  archivos de entorno; un archivo que declara otro ``DEPTIT_ENTORNO`` que el pedido aborta el arranque.
* ``cli`` ejecuta ``python -m operacion`` con el entorno del perfil.
Servidores falsos (``python -m http.server`` envuelto) en puertos propios: nunca se toca la aplicacion real."""

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

SERVIDOR = r'''import json, os, sys, http.server, socketserver
claves = sorted(k for k in os.environ if k.startswith(("DEPTIT_", "DATABASE_URL", "ZZ_")))
with open(sys.argv[2], "w", encoding="utf-8") as fh:
    json.dump({k: os.environ[k] for k in claves}, fh)
http.server.test(HandlerClass=http.server.SimpleHTTPRequestHandler, port=int(sys.argv[1]), bind="127.0.0.1")
'''

CLI = r'''import json, os, sys
print(json.dumps({"argv": sys.argv[1:], "entorno": os.environ.get("DEPTIT_ENTORNO"),
                  "heredada": os.environ.get("DEPTIT_ZZ_HEREDADA")}))
'''


def _libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _escucha(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture
def perfil(tmp_path):
    pb, pf = _libre(), _libre()
    for d in ("www_b", "www_f"):
        (tmp_path / d).mkdir()
    (tmp_path / "srv.py").write_text(SERVIDOR, encoding="utf-8")
    pkg = tmp_path / "www_b" / "operacion"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "__main__.py").write_text(CLI, encoding="utf-8")
    env_b = tmp_path / "backend.env"
    env_b.write_text("# comentario\nDEPTIT_ENTORNO=desarrollo\nDEPTIT_ZZ_DEL_ARCHIVO=valor-archivo\n", encoding="utf-8")
    py = sys.executable.replace("'", "''")

    def config(env_files):
        cfg = tmp_path / f"ops_{time.time_ns()}.psd1"
        lista = ", ".join(f"'{p}'" for p in env_files)
        cfg.write_text(f"""@{{
    BackendExe = '{py}'
    BackendArgs = @('{tmp_path / "srv.py"}', '{pb}', '{tmp_path / "env_backend.json"}')
    BackendDir = '{tmp_path / "www_b"}'
    BackendPort = {pb}
    BackendHealthPath = '/'
    FrontendExe = '{py}'
    FrontendArgs = @('{tmp_path / "srv.py"}', '{pf}', '{tmp_path / "env_frontend.json"}')
    FrontendDir = '{tmp_path / "www_f"}'
    FrontendPort = {pf}
    FrontendHealthPath = '/'
    RunDir = '{tmp_path / "run"}'
    LogDir = '{tmp_path / "logs"}'
    BackendEnvFiles = @({lista})
    CliEnvFiles = @({lista})
    StartTimeoutSec = 30
}}
""", encoding="utf-8")
        return cfg

    def run(cfg, action, *extra, entorno="desarrollo"):
        salida = tmp_path / f"salida_{action}_{time.time_ns()}.txt"
        args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(OPS)]
        if entorno:
            args += ["-Entorno", entorno]
        args += ["-Action", action, "-Config", str(cfg), *extra]
        # variables "heredadas" del proceso padre que el perfil debe borrar
        env = {**os.environ, "DEPTIT_ZZ_HEREDADA": "no-debe-llegar", "DATABASE_URL": "postgresql://x@y/z"}
        with open(salida, "wb") as fh:
            p = subprocess.run(args, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=120,
                               env=env)
        return p.returncode, salida.read_bytes().decode("utf-8", "replace")

    yield config, run, tmp_path, env_b, pb, pf
    run(config([env_b]), "stop")
    assert not _escucha(pb) and not _escucha(pf)


def test_entorno_obligatorio(perfil):
    config, run, tmp, env_b, pb, pf = perfil
    rc, out = run(config([env_b]), "status", entorno=None)
    assert rc != 0 and "Entorno" in out, out
    assert not (tmp / "run").exists()


def test_el_perfil_borra_lo_heredado_y_carga_solo_sus_archivos(perfil):
    config, run, tmp, env_b, pb, pf = perfil
    cfg = config([env_b])
    rc, out = run(cfg, "start")
    assert rc == 0, out
    vb = json.loads((tmp / "env_backend.json").read_text(encoding="utf-8"))
    assert vb == {"DEPTIT_ENTORNO": "desarrollo", "DEPTIT_ZZ_DEL_ARCHIVO": "valor-archivo"}, vb
    # el frontend no declara archivos: hereda el entorno del script (perfil de desarrollo, sin aislamiento extra)
    vf = json.loads((tmp / "env_frontend.json").read_text(encoding="utf-8"))
    assert vf.get("DEPTIT_ZZ_HEREDADA") == "no-debe-llegar"
    rc, out = run(cfg, "status")
    assert rc == 0 and '"entorno":  "desarrollo"' in out, out
    rc, out = run(cfg, "cli", "-CliArgs", "verify-db")
    assert rc == 0, out
    r = json.loads(out.strip().splitlines()[-1])
    assert r == {"argv": ["verify-db"], "entorno": "desarrollo", "heredada": None}
    rc, out = run(cfg, "stop")
    assert rc == 0 and not _escucha(pb) and not _escucha(pf)


def test_archivo_de_otro_entorno_aborta(perfil):
    config, run, tmp, env_b, pb, pf = perfil
    otro = tmp / "otro.env"
    otro.write_text("DEPTIT_ENTORNO=preproduccion\n", encoding="utf-8")
    rc, out = run(config([otro]), "start")
    assert rc == 2 and "declaran DEPTIT_ENTORNO=preproduccion" in out, out
    assert not _escucha(pb) and not _escucha(pf) and not (tmp / "run" / "backend.json").exists()
    rc, out = run(config([otro]), "cli", "-CliArgs", "verify-db")
    assert rc != 0 and "declaran DEPTIT_ENTORNO=preproduccion" in out, out


def test_archivo_faltante_o_invalido_aborta(perfil):
    config, run, tmp, env_b, pb, pf = perfil
    rc, out = run(config([tmp / "no_existe.env"]), "start")
    assert rc == 2 and "falta el archivo de entorno" in out, out
    malo = tmp / "malo.env"
    malo.write_text("SIN_IGUAL\n", encoding="utf-8")
    rc, out = run(config([malo]), "start")
    assert rc == 2 and "linea invalida" in out, out
    assert not _escucha(pb)


def test_preproduccion_sin_instalar_no_arranca(tmp_path):
    """Sin var\\preprod\\config\\ops.psd1 el perfil de preproduccion se niega (no cae al de desarrollo).  Copia del
    script bajo una raiz temporal: el resultado no depende de que esta PC tenga la preproduccion instalada."""
    (tmp_path / "ops").mkdir()
    copia = tmp_path / "ops" / "deptit-ops.ps1"
    copia.write_bytes(OPS.read_bytes())
    salida = tmp_path / "salida.txt"
    with open(salida, "wb") as fh:
        p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(copia), "-Entorno",
                            "preproduccion", "-Action", "status"], stdout=fh, stderr=subprocess.STDOUT,
                           stdin=subprocess.DEVNULL, timeout=120)
    out = salida.read_bytes().decode("utf-8", "replace")
    assert p.returncode != 0 and "preproduccion no instalada" in out, out
    assert not (tmp_path / "var" / "preprod" / "run").exists()
