"""Etapa 6A-B2: release reproducible sin secretos (docs/ETAPA6_6AB2_OPERATION_RECOVERY.md).  Se arma una release REAL
del arbol de trabajo en un directorio temporal; el escaneo busca los VALORES secretos reales (sin imprimirlos)."""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path

import pytest

from integraciones.ciclo_periodos.ref_b11.backup_manifest import sha256_file
from operacion import release as RL


@pytest.fixture(scope="module")
def armada(tmp_path_factory):
    dist = tmp_path_factory.mktemp("dist")
    r = RL.construir(dist=dist, pg_bin_dir=r"C:\Program Files\PostgreSQL\18\bin")
    assert r["result"] == "PASS", r
    return r, Path(r["dir"])


def test_release_contenido_y_exclusiones(armada):
    r, d = armada
    rels = {p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file()}
    for obligatorio in ("backend/serve.py", "backend/main.py", "backend/settings.py", "backend/requirements.txt",
                        "backend/.env.example", "backend/operacion/__main__.py",
                        "backend/integraciones/ciclo_periodos/ref_b11/backup.py", "frontend/package.json",
                        "frontend/package-lock.json", "frontend/next.config.ts", "frontend/src/app/layout.tsx",
                        "frontend/.env.example", "ops/deptit-ops.ps1", "ops/services/linux/deptit-next-backend.service",
                        "migration/schema/0001_baseline_schema.sql", "migration/db_setup/03_create_ops_roles.template.sql",
                        "docs/RUNBOOK_DEPTIT_NEXT.md", "RELEASE.json", "release_manifest.json"):
        assert obligatorio in rels, obligatorio
    prohibidos = re.compile(r"(^|/)(\.env|\.env\.ops|\.env\.local|\.venv|node_modules|\.next|\.git|__pycache__|storage|"
                            r"tests|audit|dist|reference_fix02)(/|$)|\.(dump|log|pyc|partial)$|generated\.sql$|"
                            r"^backend/tools_|pgpass")
    malos = sorted(x for x in rels if prohibidos.search(x))
    assert malos == [], malos[:10]
    assert r["auditoria"]["ok"] and r["auditoria"]["valores_buscados"] >= 3 and r["auditoria"]["secretos"] == []


def test_release_metadatos_y_manifest(armada):
    r, d = armada
    meta = json.loads((d / "RELEASE.json").read_text(encoding="utf-8"))
    assert re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{12}", meta["release_id"]) and meta["release_id"] in d.name
    assert meta["git"] is None and "no es un repositorio Git" in meta["git_nota"]
    v = meta["versiones"]
    assert v["python_build"].startswith("3.14") and v["node_build"].startswith("v") and v["next"] == "16.4.1"
    assert v["postgresql_cliente_build"].startswith("pg_dump (PostgreSQL) 18")
    assert meta["requisitos"]["postgresql"] == "18.x" and any(x.startswith("fastapi==")
                                                                for x in meta["requisitos"]["backend_requirements"])
    m = json.loads((d / "release_manifest.json").read_text(encoding="utf-8"))
    assert m["count"] == len(m["files"]) == r["count"]
    for f in m["files"][:50]:
        assert sha256_file(d / f["path"]) == f["sha256"]
    assert RL.verificar(d) == {"ok": True, "code": "VALID", "release_id": meta["release_id"], "count": m["count"]}
    z = Path(r["zip"])
    assert sha256_file(z) == r["zip_sha256"] == (z.parent / f"{z.name}.sha256").read_text().split()[0]
    with zipfile.ZipFile(z) as zf:
        assert len([n for n in zf.namelist() if not n.endswith("/")]) == m["count"] + 2


def test_release_alterada_no_verifica(armada, tmp_path):
    _, d = armada
    copia = tmp_path / "r"
    shutil.copytree(d, copia)
    (copia / "backend" / "serve.py").write_text("# alterado\n", encoding="utf-8")
    assert RL.verificar(copia)["code"] == "HASH_MISMATCH"
    shutil.copytree(d, tmp_path / "r2")
    (tmp_path / "r2" / "backend" / "extra.py").write_text("x = 1\n", encoding="utf-8")
    assert RL.verificar(tmp_path / "r2")["code"] == "UNEXPECTED_FILE"
    shutil.copytree(d, tmp_path / "r3")
    (tmp_path / "r3" / "backend" / "serve.py").unlink()
    assert RL.verificar(tmp_path / "r3")["code"] == "FILE_MISSING"


def test_auditoria_detecta_secretos_plantados(tmp_path):
    arbol = tmp_path / "arbol"
    (arbol / "backend").mkdir(parents=True)
    (arbol / "backend" / "ok.py").write_text("x = 'sin secretos'\n", encoding="utf-8")
    assert RL.auditar(arbol, secretos=[b"valor-secreto-real-123"])["ok"]
    casos = {"backend/.env": b"DEPTIT_DB_PASSWORD=algo\n",
             "backend/config.py": b"PW = 'valor-secreto-real-123'\n",
             "migration/x.sql": b"PASSWORD 'SCRAM-SHA-256$4096:c2FsdHNhbHQ=$a2V5:a2V5'\n",
             "docs/x.md": b"conexion postgresql://deptit_next_app:hunter2hunter2@127.0.0.1/deptit_next_dev\n",
             "ops/k.txt": b"-----BEGIN RSA PRIVATE KEY-----\n",
             "ops/env.txt": b"DEPTIT_BACKUP_DB_PASSWORD=abcdefgh\n",
             "backend/x.dump": b"PGDMP"}
    for rel, datos in casos.items():
        p = arbol / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(datos)
    a = RL.auditar(arbol, secretos=[b"valor-secreto-real-123"])
    assert not a["ok"]
    nombres = {x["path"] for x in a["nombres_prohibidos"]}
    tipos = {(x["path"], x["tipo"]) for x in a["secretos"]}
    assert {"backend/.env", "backend/x.dump"} <= nombres
    assert {("backend/config.py", "valor_secreto_real"), ("migration/x.sql", "scram_verifier"),
            ("docs/x.md", "url_con_credenciales"), ("ops/k.txt", "clave_privada"),
            ("ops/env.txt", "password_asignada")} <= tipos
    assert "valor-secreto-real-123" not in json.dumps(a) and "hunter2" not in json.dumps(a)


def test_seleccion_respeta_exclusiones_del_arbol_real():
    sel = RL.seleccionar()
    assert "backend/.env" not in sel and "backend/.env.ops" not in sel and "frontend/.env.local" not in sel
    assert "backend/.env.example" in sel and "frontend/.env.example" in sel
    # ``**`` abarca cero directorios: los modulos de nivel superior del backend entran; tests y tools no
    assert {"backend/main.py", "backend/serve.py", "backend/settings.py", "backend/db.py"} <= set(sel)
    assert not any(s.startswith(("backend/tools_", "backend/tests_guard")) for s in sel)
    assert not any(s.startswith(("backend/tests/", "frontend/node_modules/", "storage/", "docs/audit/")) for s in sel)
