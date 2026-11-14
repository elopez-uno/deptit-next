"""Release reproducible de DEPTIT NEXT (6A-B2).

Estrategia: artefacto de FUENTES + lockfiles (sin binarios de terceros): la instalacion crea el entorno Python desde
``backend/requirements.txt`` (versiones fijadas) y el frontend con ``npm ci`` (``package-lock.json``) + ``next build``
UNA vez por release; en ejecucion solo ``python serve.py`` y ``next start`` (nada se compila ni descarga al arrancar).

Contenido: allowlist explicita (``INCLUIR``) + exclusiones obligatorias (``EXCLUIR``).  Antes de publicar,
``auditar`` revisa el arbol armado: nombres prohibidos (``.env``, dumps, SQL generado, logs, ``node_modules``, ``.venv``,
``.git``, caches, ``storage``, auditorias) y un escaneo de secretos por patrones + por VALOR (las contraseñas reales de
``backend/.env``, ``backend/.env.ops`` y ``frontend/.env.local`` se buscan en cada archivo sin imprimirlas nunca).
Si algo aparece, la release no se publica.

Salida: ``dist/deptit-next-<release_id>/`` (+ ``.zip`` y ``.zip.sha256``) con ``RELEASE.json`` (id, versiones de
Python / Node / Next / PostgreSQL requerido, requisitos, git = null si no hay repositorio) y ``release_manifest.json``
(cada archivo con tamaño y SHA-256).
"""
from __future__ import annotations

import datetime as _dt
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, List, Optional

from dotenv import dotenv_values

import settings as app_settings
from integraciones.ciclo_periodos.ref_b11.backup_manifest import format_ts, sha256_file, utc_now

REPO = app_settings.REPO_DIR
DIST = REPO / "dist"
INCLUIR = (
    "backend/**/*.py", "backend/requirements.txt", "backend/.env.example",
    "frontend/src/**", "frontend/public/**", "frontend/package.json", "frontend/package-lock.json",
    "frontend/next.config.ts", "frontend/tsconfig.json", "frontend/next-env.d.ts", "frontend/.env.example",
    "ops/**", "migration/schema/**", "migration/db_setup/*.template.sql",
    "docs/ETAPA6_6AB2_OPERATION_RECOVERY.md", "docs/ETAPA6_6AB3_LOCAL_PILOT.md", "docs/RUNBOOK_DEPTIT_NEXT.md",
)
EXCLUIR = (
    "**/.env", "**/.env.*", "**/*.dump", "**/*.generated.sql", "**/*.log", "**/*.partial", "**/__pycache__/**",
    "**/*.pyc", "**/node_modules/**", "**/.venv/**", "**/.git/**", "**/.next/**", "storage/**", "dist/**", "var/**",
    "docs/audit/**", "backend/tests/**", "backend/tests_guard_negative.py", "backend/tools_*.py", "frontend/tests/**",
    "ops/run/**", "ops/logs/**", "ops/*.local.*", "**/*.pem", "**/*.key", "**/pgpass*", "**/.pgpass",
)
PERMITIDOS_ENV = ("backend/.env.example", "frontend/.env.example")
PATRONES_SECRETO = (
    ("scram_verifier", re.compile(rb"SCRAM-SHA-256\$\d+:[A-Za-z0-9+/=]{8,}\$")),
    ("url_con_credenciales", re.compile(rb"postgres(?:ql)?(?:\+\w+)?://[^:/@\s'\"]+:[^@\s'\"<>{}]+@")),
    ("clave_privada", re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("password_asignada", re.compile(rb"(?m)^\s*DEPTIT_[A-Z_]*PASSWORD\s*=\s*[^\s#<]{6,}")),
)
ARCHIVOS_SECRETOS = (REPO / "backend" / ".env", REPO / "backend" / ".env.ops", REPO / "frontend" / ".env.local")
CLAVE_SECRETA = re.compile(r"PASSWORD|SECRET|TOKEN|KEY|DATABASE_URL", re.I)


class ReleaseError(RuntimeError):
    pass


def _coincide(rel: str, patrones: Iterable[str]) -> bool:
    """``**`` abarca cero o mas directorios: ``backend/**/*.py`` incluye ``backend/main.py`` (con fnmatch solo, el
    ``/`` posterior exigiria al menos un subdirectorio)."""
    return any(fnmatch.fnmatchcase(rel, p) or (p.startswith("**/") and fnmatch.fnmatchcase(rel, p[3:]))
               or ("/**/" in p and fnmatch.fnmatchcase(rel, p.replace("/**/", "/")))
               for p in patrones)


def seleccionar(raiz: Path = REPO) -> List[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(raiz):
        rel_dir = Path(dirpath).relative_to(raiz).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir
        dirnames[:] = sorted(d for d in dirnames if not _coincide(f"{rel_dir}/{d}/x".lstrip("/"), EXCLUIR)
                             and not os.path.islink(os.path.join(dirpath, d)))
        for f in sorted(filenames):
            rel = f"{rel_dir}/{f}".lstrip("/")
            if os.path.islink(os.path.join(dirpath, f)):
                continue
            if _coincide(rel, INCLUIR) and not (_coincide(rel, EXCLUIR) and rel not in PERMITIDOS_ENV):
                out.append(rel)
    return sorted(out)


def valores_secretos(archivos: Iterable[Path] = ARCHIVOS_SECRETOS) -> List[bytes]:
    """Valores reales a buscar (solo en memoria; nunca se imprimen).  Minimo 8 caracteres para evitar ruido."""
    out = set()
    for a in archivos:
        if a.is_file():
            for k, v in dotenv_values(a).items():
                if v and len(v) >= 8 and CLAVE_SECRETA.search(k):
                    out.add(v.encode("utf-8"))
    return sorted(out)


def auditar(arbol: Path, *, secretos: Optional[List[bytes]] = None) -> dict:
    """Revisa un arbol de release armado.  Solo informa rutas y TIPO de hallazgo, nunca el valor."""
    secretos = valores_secretos() if secretos is None else secretos
    nombres, contenido = [], []
    archivos = 0
    for p in sorted(arbol.rglob("*")):
        if p.is_symlink():
            nombres.append({"path": p.relative_to(arbol).as_posix(), "tipo": "enlace"})
            continue
        if not p.is_file():
            continue
        archivos += 1
        rel = p.relative_to(arbol).as_posix()
        if _coincide(rel, EXCLUIR) and rel not in PERMITIDOS_ENV:
            nombres.append({"path": rel, "tipo": "nombre_prohibido"})
        datos = p.read_bytes()
        for tipo, rx in PATRONES_SECRETO:
            if rx.search(datos):
                contenido.append({"path": rel, "tipo": tipo})
        if any(s in datos for s in secretos):
            contenido.append({"path": rel, "tipo": "valor_secreto_real"})
    return {"archivos": archivos, "nombres_prohibidos": nombres, "secretos": contenido,
            "valores_buscados": len(secretos), "ok": not nombres and not contenido}


def _version(cmd: List[str], runner: Callable) -> Optional[str]:
    try:
        r = runner(cmd, capture_output=True, text=True, timeout=60)
        return (r.stdout or "").strip().splitlines()[0][:120] if r.returncode == 0 and r.stdout.strip() else None
    except (OSError, subprocess.SubprocessError):
        return None


def metadatos(raiz: Path, contenido_sha: str, created: _dt.datetime, runner: Callable,
              pg_bin_dir: Optional[str]) -> dict:
    pkg = json.loads((raiz / "frontend" / "package.json").read_text(encoding="utf-8"))
    pg = shutil.which("pg_dump", path=pg_bin_dir) if pg_bin_dir else shutil.which("pg_dump")
    git = None
    if (raiz / ".git").exists():
        commit = _version(["git", "-C", str(raiz), "rev-parse", "HEAD"], runner)
        git = {"commit": commit} if commit else None
    req = [l.strip() for l in (raiz / "backend" / "requirements.txt").read_text(encoding="utf-8-sig").splitlines()
           if l.strip() and not l.lstrip().startswith("#")]
    return {
        "release_id": f"{created:%Y%m%dT%H%M%SZ}-{contenido_sha[:12]}", "producto": "deptit-next",
        "created_at_utc": format_ts(created), "contenido_sha256": contenido_sha,
        "git": git, "git_nota": None if git else "el arbol de trabajo no es un repositorio Git: no se registra commit",
        "versiones": {"python_build": sys.version.split()[0], "node_build": _version(["node", "--version"], runner),
                      "next": pkg["dependencies"].get("next"), "react": pkg["dependencies"].get("react"),
                      "postgresql_cliente_build": _version([pg, "--version"], runner) if pg else None},
        "requisitos": {"python": ">=3.14,<3.15", "node": ">=24 (LTS de la build)", "postgresql": "18.x",
                       "backend_requirements": req,
                       "frontend": "npm ci (package-lock.json) + next build; ejecucion con next start",
                       "procesos": "backend 1 worker (sesiones en memoria); FastAPI y Next.js solo en loopback / red "
                                   "interna detras del reverse proxy"},
        "instalacion": "docs/RUNBOOK_DEPTIT_NEXT.md",
    }


def construir(*, raiz: Path = REPO, dist: Path = DIST, runner: Callable = subprocess.run,
              now: Optional[_dt.datetime] = None, pg_bin_dir: Optional[str] = None, zip_: bool = True,
              secretos: Optional[List[bytes]] = None) -> dict:
    created = (now or utc_now()).astimezone(_dt.timezone.utc).replace(microsecond=0)
    archivos = seleccionar(raiz)
    if not archivos:
        raise ReleaseError("la seleccion de la release esta vacia")
    files = [{"path": rel, "size": (raiz / rel).stat().st_size, "sha256": sha256_file(raiz / rel)} for rel in archivos]
    contenido_sha = hashlib.sha256("\n".join(f"{f['path']}\t{f['sha256']}" for f in files).encode()).hexdigest()
    meta = metadatos(raiz, contenido_sha, created, runner, pg_bin_dir)
    nombre = f"deptit-next-{meta['release_id']}"
    destino = dist / nombre
    tmp = dist / f".{nombre}.partial"
    if destino.exists() or tmp.exists():
        raise ReleaseError(f"{nombre} ya existe; no se sobrescribe")
    dist.mkdir(parents=True, exist_ok=True)
    try:
        for f in files:
            dst = tmp.joinpath(*PurePosixPath(f["path"]).parts)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(raiz / f["path"], dst)
            if sha256_file(dst) != f["sha256"]:
                raise ReleaseError(f"{f['path']}: la copia no coincide")
        (tmp / "RELEASE.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        manifest = {"format_version": 1, "kind": "deptit-next-release-manifest", "release_id": meta["release_id"],
                    "count": len(files), "total_bytes": sum(f["size"] for f in files), "files": files}
        (tmp / "release_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
                                                   encoding="utf-8")
        audit = auditar(tmp, secretos=secretos)
        if not audit["ok"]:
            raise ReleaseError(f"la release no pasa la auditoria: {len(audit['nombres_prohibidos'])} nombres "
                               f"prohibidos, {len(audit['secretos'])} hallazgos de secretos")
        verif = verificar(tmp)
        if not verif["ok"]:
            raise ReleaseError(f"la release armada no verifica: {verif['code']}")
        os.rename(tmp, destino)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    out = {"result": "PASS", "release_id": meta["release_id"], "dir": str(destino), "count": len(files),
           "total_bytes": manifest["total_bytes"], "auditoria": audit, "metadatos": meta}
    if zip_:
        z = dist / f"{nombre}.zip"
        with zipfile.ZipFile(z, "x", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(destino.rglob("*")):
                if p.is_file():
                    zf.write(p, f"{nombre}/{p.relative_to(destino).as_posix()}")
        sha = sha256_file(z)
        (dist / f"{nombre}.zip.sha256").write_text(f"{sha}  {z.name}\n", encoding="utf-8")
        out["zip"], out["zip_sha256"] = str(z), sha
    return out


def verificar(arbol: Path) -> dict:
    """Release instalada/armada: cada archivo del manifest presente con su SHA-256 y sin archivos extra."""
    try:
        m = json.loads((arbol / "release_manifest.json").read_text(encoding="utf-8"))
        meta = json.loads((arbol / "RELEASE.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": False, "code": "MANIFEST_INVALID"}
    if m.get("release_id") != meta.get("release_id"):
        return {"ok": False, "code": "RELEASE_ID_MISMATCH"}
    esperados = {f["path"]: f for f in m["files"]}
    presentes = {p.relative_to(arbol).as_posix() for p in arbol.rglob("*") if p.is_file()} - {
        "release_manifest.json", "RELEASE.json"}
    if set(esperados) - presentes:
        return {"ok": False, "code": "FILE_MISSING", "faltan": sorted(set(esperados) - presentes)[:10]}
    if presentes - set(esperados):
        return {"ok": False, "code": "UNEXPECTED_FILE", "sobran": sorted(presentes - set(esperados))[:10]}
    for rel, f in esperados.items():
        if sha256_file(arbol / rel) != f["sha256"]:
            return {"ok": False, "code": "HASH_MISMATCH", "archivo": rel}
    contenido = hashlib.sha256("\n".join(f"{f['path']}\t{f['sha256']}" for f in m["files"]).encode()).hexdigest()
    if contenido != meta.get("contenido_sha256"):
        return {"ok": False, "code": "CONTENT_HASH_MISMATCH"}
    return {"ok": True, "code": "VALID", "release_id": m["release_id"], "count": m["count"]}
