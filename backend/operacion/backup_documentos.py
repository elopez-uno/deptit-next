"""Backup / verificacion / restore del storage documental (``DEPTIT_DOCUMENTS_DIR``), 6A-B2.

Formato (en ``<DEPTIT_BACKUP_DIR>/documents/``)::

    deptit_docs_<entorno>_<YYYYmmddTHHMMSSZ>/                 copia de la estructura relativa (solo archivos regulares)
    deptit_docs_<entorno>_<YYYYmmddTHHMMSSZ>.manifest.json    marcador de commit (se publica al final)

    {"format_version": 1, "kind": "deptit-next-documents-backup", "backup_id", "set_id", "entorno",
     "created_at_utc", "finished_at_utc", "source_root", "count", "total_bytes", "tree_sha256",
     "files": [{"path": "inst_1/plantillas/disposicion.docx", "size": N, "sha256": "..."}],
     "excluded": [{"path", "reason"}], "validation": {"status": "PASS", "copy_verified": true, "source_stable": true}}

Protecciones (fail-closed): enlaces simbolicos, junctions y reparse points en el origen -> FAIL (nunca se siguen);
rutas del manifest solo relativas POSIX sin ``..``, sin unidad ni ``:``; un archivo que cambia durante la copia
(tamaño o mtime antes/despues, o hash de la copia distinto) -> FAIL; la copia se arma en ``.partial`` y se publica
por rename (sin sobrescritura); el manifest se escribe al final: un backup sin manifest nunca cuenta.  Se excluyen (y se
informan) temporales, logs, ``.env*``, dumps/SQL y codigo: no son documentos.

Restore: verifica el backup completo ANTES de escribir; el destino no debe existir o debe estar vacio, nunca dentro del
directorio de backups ni de un arbol protegido; se copia a un temporal hermano y se publica por rename; despues se
verifica el arbol restaurado contra el manifest (cantidad, nombres, bytes, SHA-256, sin archivos extra).
"""
from __future__ import annotations

import datetime as _dt
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional

import settings as app_settings
from integraciones.ciclo_periodos.ref_b11.backup import BackupError, publish_no_overwrite
from integraciones.ciclo_periodos.ref_b11.backup_manifest import format_ts, parse_ts, sha256_file, utc_now

FORMAT_VERSION = 1
KIND = "deptit-next-documents-backup"
MANIFEST_SUFFIX = ".manifest.json"
PARTIAL_SUFFIX = ".partial"
NAME_RE = re.compile(r"^deptit_docs_(desarrollo|preproduccion|produccion)_\d{8}T\d{6}Z$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_MANIFEST_BYTES = 64 * 1024 * 1024
CHUNK = 1 << 20
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
EXCLUIDOS = (("*.tmp", "temporal"), ("~$*", "temporal"), (".~lock.*", "temporal"), ("*.partial", "temporal"),
             ("*.swp", "temporal"), ("Thumbs.db", "sistema"), ("desktop.ini", "sistema"), ("*.log", "log"),
             (".env*", "secreto"), ("*.dump", "dump"), ("*.sql", "sql"), ("*.py", "codigo"), ("*.pyc", "codigo"))
DIRS_EXCLUIDOS = ("__pycache__", ".git", "logs", "tmp", "temp")
TOP_KEYS = {"format_version", "kind", "backup_id", "set_id", "entorno", "created_at_utc", "finished_at_utc",
            "source_root", "count", "total_bytes", "tree_sha256", "files", "excluded", "validation"}


class DocumentosError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


def backup_id_de(entorno: str, created: _dt.datetime) -> str:
    return f"deptit_docs_{entorno}_{created.astimezone(_dt.timezone.utc):%Y%m%dT%H%M%SZ}"


def _es_enlace(path: str) -> bool:
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode):
        return True
    if getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
        return True
    return bool(getattr(os.path, "isjunction", lambda p: False)(path))


def ruta_segura(rel: str) -> bool:
    """Ruta relativa POSIX normalizada, sin ``..``, sin raiz, sin unidad, sin ``\\`` ni ``:`` (ADS)."""
    if not isinstance(rel, str) or not rel or "\\" in rel or ":" in rel or "\x00" in rel:
        return False
    p = PurePosixPath(rel)
    return not p.is_absolute() and all(part not in ("", ".", "..") for part in p.parts) and str(p) == rel


def _excluido(nombre: str) -> Optional[str]:
    for patron, motivo in EXCLUIDOS:
        if fnmatch.fnmatchcase(nombre.lower(), patron.lower()):
            return motivo
    return None


def inventario(raiz: Path) -> tuple[List[str], List[dict]]:
    """(archivos relativos POSIX, excluidos).  Recorre sin seguir enlaces; un enlace o un tipo especial -> FAIL."""
    archivos, excluidos = [], []
    pendientes = [""]
    while pendientes:
        rel_dir = pendientes.pop()
        actual = raiz / rel_dir if rel_dir else raiz
        with os.scandir(actual) as it:
            entradas = sorted(it, key=lambda e: e.name)
        for e in entradas:
            rel = f"{rel_dir}/{e.name}" if rel_dir else e.name
            if _es_enlace(e.path):
                raise DocumentosError("HOSTILE_ENTRY", f"{rel}: enlace, junction o reparse point (no se sigue)")
            st = os.lstat(e.path)
            if stat.S_ISDIR(st.st_mode):
                if e.name.lower() in DIRS_EXCLUIDOS:
                    excluidos.append({"path": rel + "/", "reason": "directorio no documental"})
                else:
                    pendientes.append(rel)
                continue
            if not stat.S_ISREG(st.st_mode):
                raise DocumentosError("HOSTILE_ENTRY", f"{rel}: no es un archivo regular")
            if not ruta_segura(rel):
                raise DocumentosError("HOSTILE_ENTRY", f"{rel}: nombre no representable de forma segura")
            if (motivo := _excluido(e.name)) is not None:
                excluidos.append({"path": rel, "reason": motivo})
                continue
            archivos.append(rel)
    return sorted(archivos), sorted(excluidos, key=lambda x: x["path"])


def _copiar_estable(origen: Path, destino: Path) -> dict:
    """Copia con hash en vuelo; FAIL si el origen cambia durante la copia o la copia no coincide."""
    antes = os.lstat(origen)
    h = hashlib.sha256()
    fd = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with open(origen, "rb") as src, os.fdopen(fd, "wb") as dst:
        while chunk := src.read(CHUNK):
            h.update(chunk)
            dst.write(chunk)
        dst.flush()
        os.fsync(dst.fileno())
    despues = os.lstat(origen)
    if (antes.st_size, antes.st_mtime_ns) != (despues.st_size, despues.st_mtime_ns):
        raise DocumentosError("SOURCE_CHANGED", f"{origen.name}: el archivo cambio durante la copia")
    sha = h.hexdigest()
    if destino.stat().st_size != antes.st_size or sha256_file(destino) != sha:
        raise DocumentosError("COPY_MISMATCH", f"{origen.name}: la copia no coincide con el origen")
    return {"size": antes.st_size, "sha256": sha}


def tree_sha256(files: List[dict]) -> str:
    texto = "\n".join(f"{f['path']}\t{f['size']}\t{f['sha256']}" for f in sorted(files, key=lambda f: f["path"]))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def respaldar(raiz_documentos: Path, destino_backups: Path, *, entorno: str, set_id: Optional[str] = None,
              now: Optional[_dt.datetime] = None) -> dict:
    """Backup completo del storage documental.  Nunca levanta: devuelve un reporte (``result`` PASS/FAIL)."""
    created = (now or utc_now()).astimezone(_dt.timezone.utc).replace(microsecond=0)
    backup_id = backup_id_de(entorno, created)
    report = {"kind": "deptit-next-documents-backup-run", "backup_id": backup_id, "set_id": set_id,
              "entorno": entorno, "result": "FAIL", "code": None}
    staging = destino_backups / f".{backup_id}{PARTIAL_SUFFIX}"
    final_dir = destino_backups / backup_id
    final_manifest = destino_backups / f"{backup_id}{MANIFEST_SUFFIX}"
    tmp_manifest = destino_backups / f".{backup_id}{MANIFEST_SUFFIX}{PARTIAL_SUFFIX}"
    publicado = False
    try:
        raiz = Path(raiz_documentos)
        if not raiz.is_absolute() or not raiz.is_dir() or _es_enlace(str(raiz)):
            raise DocumentosError("SOURCE_INVALID", "la raiz documental no existe, no es absoluta o es un enlace")
        if not destino_backups.is_dir() or _es_enlace(str(destino_backups)):
            raise DocumentosError("BACKUP_DIR_INVALID", "el directorio de backups documentales no existe")
        r, d = os.path.normcase(str(raiz.resolve())), os.path.normcase(str(destino_backups.resolve()))
        if d == r or d.startswith(r + os.sep) or r.startswith(d + os.sep):
            raise DocumentosError("BACKUP_DIR_INVALID", "origen y destino no pueden contenerse")
        for p in (final_dir, final_manifest):
            if p.exists() or p.is_symlink():
                raise DocumentosError("TARGET_EXISTS", f"{p.name} ya existe; no se sobrescribe")
        archivos, excluidos = inventario(raiz)
        staging.mkdir(mode=0o700)
        files = []
        for rel in archivos:
            destino = staging.joinpath(*PurePosixPath(rel).parts)
            destino.parent.mkdir(parents=True, exist_ok=True)
            files.append({"path": rel, **_copiar_estable(raiz.joinpath(*PurePosixPath(rel).parts), destino)})
        segundo, _ = inventario(raiz)
        if segundo != archivos:
            raise DocumentosError("SOURCE_CHANGED", "el conjunto de archivos cambio durante el backup")
        manifest = {"format_version": FORMAT_VERSION, "kind": KIND, "backup_id": backup_id, "set_id": set_id,
                    "entorno": entorno, "created_at_utc": format_ts(created), "finished_at_utc": format_ts(utc_now()),
                    "source_root": str(raiz), "count": len(files), "total_bytes": sum(f["size"] for f in files),
                    "tree_sha256": tree_sha256(files), "files": files, "excluded": excluidos,
                    "validation": {"status": "PASS", "copy_verified": True, "source_stable": True}}
        if problemas := validar_documento(manifest, f"{backup_id}{MANIFEST_SUFFIX}"):
            raise DocumentosError("MANIFEST_INVALID", "; ".join(problemas))
        os.rename(staging, final_dir)  # falla si el destino existe (verificado arriba)
        publicado = True
        fd = os.open(tmp_manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        publish_no_overwrite(tmp_manifest, final_manifest)
        chk = verificar(final_manifest)
        report.update({"manifest": str(final_manifest), "count": len(files), "total_bytes": manifest["total_bytes"],
                       "tree_sha256": manifest["tree_sha256"], "excluded": len(excluidos),
                       "verificacion": chk.summary()})
        if not chk.ok:
            raise DocumentosError(f"POST_VERIFY_{chk.code}", "; ".join(chk.problems))
        report["result"], report["code"] = "PASS", "PASS"
    except (DocumentosError, BackupError) as exc:
        report["code"], report["detail"] = exc.code, exc.message
    except OSError as exc:
        report["code"], report["detail"] = "IO_ERROR", type(exc).__name__
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if tmp_manifest.exists():
            tmp_manifest.unlink()
        if report["result"] != "PASS" and publicado and not final_manifest.exists():
            shutil.rmtree(final_dir, ignore_errors=True)  # sin manifest no es un backup: no dejar copias huerfanas
    return report


def validar_documento(doc, manifest_name: Optional[str] = None) -> List[str]:
    p = []
    if not isinstance(doc, dict):
        return ["manifest no es un objeto JSON"]
    if set(doc) != TOP_KEYS:
        p.append(f"claves inesperadas: faltan={sorted(TOP_KEYS - set(doc))} sobran={sorted(set(doc) - TOP_KEYS)}")
        return p
    if doc["format_version"] != FORMAT_VERSION or doc["kind"] != KIND:
        p.append("format_version/kind no soportado")
    if not isinstance(doc["backup_id"], str) or not NAME_RE.match(doc["backup_id"]):
        p.append("backup_id invalido")
    elif manifest_name is not None and manifest_name != doc["backup_id"] + MANIFEST_SUFFIX:
        p.append("el manifest no corresponde al backup (nombres distintos)")
    elif doc["backup_id"].split("_")[2] != doc["entorno"]:
        p.append("entorno no coincide con backup_id")
    for k in ("created_at_utc", "finished_at_utc"):
        try:
            parse_ts(doc[k])
        except (TypeError, ValueError):
            p.append(f"{k} invalido")
    files = doc["files"]
    if not isinstance(files, list):
        return p + ["files invalido"]
    vistos = set()
    for f in files:
        if not isinstance(f, dict) or set(f) != {"path", "size", "sha256"}:
            p.append("entrada de files invalida")
            continue
        if not ruta_segura(f["path"]):
            p.append(f"ruta hostil o invalida: {str(f['path'])[:80]!r}")
        if f["path"].casefold() in vistos:
            p.append(f"ruta duplicada: {f['path'][:80]!r}")
        vistos.add(str(f["path"]).casefold())
        if not isinstance(f["size"], int) or isinstance(f["size"], bool) or f["size"] < 0:
            p.append("size invalido")
        if not isinstance(f["sha256"], str) or not SHA_RE.match(f["sha256"]):
            p.append("sha256 invalido")
    if not p:
        if doc["count"] != len(files) or doc["total_bytes"] != sum(f["size"] for f in files):
            p.append("count/total_bytes no coinciden con files")
        if doc["tree_sha256"] != tree_sha256(files):
            p.append("tree_sha256 no coincide con files")
    v = doc["validation"]
    if not isinstance(v, dict) or v.get("status") != "PASS" or v.get("copy_verified") is not True \
            or v.get("source_stable") is not True:
        p.append("validation != PASS")
    return p


@dataclass
class Verificacion:
    manifest_path: str
    ok: bool = False
    code: str = "UNCHECKED"
    problems: List[str] = field(default_factory=list)
    manifest: Optional[dict] = None

    @property
    def backup_dir(self) -> Path:
        return Path(self.manifest_path).parent / self.manifest["backup_id"]

    def summary(self) -> dict:
        return {"manifest": os.path.basename(self.manifest_path), "ok": self.ok, "code": self.code,
                "problems": self.problems[:5],
                "count": (self.manifest or {}).get("count"), "tree_sha256": (self.manifest or {}).get("tree_sha256")}


def cargar(path: Path) -> dict:
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("manifest inexistente o no es un archivo regular")
    if st.st_size > MAX_MANIFEST_BYTES:
        raise ValueError("manifest demasiado grande")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def comparar_arbol(raiz: Path, files: List[dict], *, check_hash: bool = True) -> tuple[str, List[str]]:
    """(codigo, problemas) del arbol ``raiz`` frente a ``files``: faltantes, extra, tamaño y SHA-256."""
    try:
        presentes, excl = inventario(raiz)
    except DocumentosError as exc:
        return exc.code, [exc.message]
    presentes = set(presentes) | {e["path"] for e in excl if not e["path"].endswith("/")}
    esperados = {f["path"]: f for f in files}
    faltan = sorted(set(esperados) - presentes)
    sobran = sorted(presentes - set(esperados))
    if faltan:
        return "FILE_MISSING", [f"falta {x}" for x in faltan[:10]]
    if sobran:
        return "UNEXPECTED_FILE", [f"sobra {x}" for x in sobran[:10]]
    for rel, f in sorted(esperados.items()):
        ruta = raiz.joinpath(*PurePosixPath(rel).parts)
        if ruta.stat().st_size != f["size"]:
            return "SIZE_MISMATCH", [f"{rel}: tamaño distinto"]
        if check_hash and sha256_file(ruta) != f["sha256"]:
            return "HASH_MISMATCH", [f"{rel}: SHA-256 distinto"]
    return "VALID", []


def verificar(manifest_path, *, entorno: Optional[str] = None, check_hash: bool = True) -> Verificacion:
    path = Path(manifest_path)
    res = Verificacion(str(path))
    try:
        doc = cargar(path)
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        res.code, res.problems = "MANIFEST_INVALID", [f"manifest ilegible: {type(exc).__name__}"]
        return res
    res.manifest = doc
    if problemas := validar_documento(doc, path.name):
        res.code, res.problems = "MANIFEST_INVALID", problemas
        return res
    if entorno is not None and doc["entorno"] != entorno:
        res.code, res.problems = "OTHER_ENVIRONMENT", ["el backup documental es de otro entorno"]
        return res
    d = res.backup_dir
    if not d.is_dir() or _es_enlace(str(d)):
        res.code, res.problems = "BACKUP_MISSING", ["falta el directorio del backup documental"]
        return res
    res.code, res.problems = comparar_arbol(d, doc["files"], check_hash=check_hash)
    res.ok = res.code == "VALID"
    return res


def listar(directorio: Path) -> List[Path]:
    if not Path(directorio).is_dir():
        return []
    return sorted(p for p in Path(directorio).iterdir()
                  if p.name.endswith(MANIFEST_SUFFIX) and NAME_RE.match(p.name[:-len(MANIFEST_SUFFIX)])
                  and stat.S_ISREG(os.lstat(p).st_mode))


def restaurar(manifest_path, destino: Path, *, backups_dir: Path, entorno: Optional[str] = None,
              env: Optional[Dict[str, str]] = None) -> dict:
    """Restaura en ``destino`` (inexistente o vacio).  Verifica antes y despues.  Nunca sobrescribe."""
    report = {"kind": "deptit-next-documents-restore", "manifest": Path(manifest_path).name, "result": "FAIL",
              "code": None, "destino": str(destino)}
    tmp = None
    creado = False
    try:
        chk = verificar(manifest_path, entorno=entorno)
        report["verificacion_previa"] = chk.summary()
        if not chk.ok:
            raise DocumentosError("BACKUP_INVALID", f"el backup documental no verifica ({chk.code})")
        destino = Path(destino)
        if not destino.is_absolute():
            raise DocumentosError("TARGET_INVALID", "el destino debe ser una ruta absoluta")
        if (motivo := app_settings.documents_dir_problem(destino, env)) is not None:
            raise DocumentosError("TARGET_PROTECTED", f"destino {motivo}")
        dn, bn = os.path.normcase(os.path.normpath(str(destino))), os.path.normcase(str(Path(backups_dir).resolve()))
        if dn == bn or dn.startswith(bn + os.sep) or bn.startswith(dn + os.sep):
            raise DocumentosError("TARGET_PROTECTED", "el destino no puede estar dentro del directorio de backups")
        if destino.is_symlink() or (destino.exists() and _es_enlace(str(destino))):
            raise DocumentosError("TARGET_INVALID", "el destino es un enlace")
        if destino.exists() and (not destino.is_dir() or any(destino.iterdir())):
            raise DocumentosError("TARGET_NOT_EMPTY", "el destino existe y no esta vacio: nunca se sobrescribe")
        if not destino.parent.is_dir():
            raise DocumentosError("TARGET_INVALID", "no existe el directorio padre del destino")
        tmp = destino.parent / f".{destino.name}.restoring"
        tmp.mkdir(mode=0o700)
        origen = chk.backup_dir
        for f in chk.manifest["files"]:
            partes = PurePosixPath(f["path"]).parts
            dst = tmp.joinpath(*partes)
            dst.parent.mkdir(parents=True, exist_ok=True)
            copia = _copiar_estable(origen.joinpath(*partes), dst)
            if copia["sha256"] != f["sha256"]:
                raise DocumentosError("HASH_MISMATCH", f"{f['path']}: el backup cambio durante el restore")
        if destino.exists():
            destino.rmdir()  # vacio (verificado)
        os.rename(tmp, destino)
        tmp, creado = None, True
        code, problemas = comparar_arbol(destino, chk.manifest["files"])
        report["verificacion_posterior"] = {"code": code, "problems": problemas[:5],
                                            "count": chk.manifest["count"], "tree_sha256": chk.manifest["tree_sha256"]}
        if code != "VALID":
            raise DocumentosError(f"POST_VERIFY_{code}", "; ".join(problemas))
        report["result"], report["code"] = "PASS", "RESTORE_VERIFIED"
        report["count"], report["total_bytes"] = chk.manifest["count"], chk.manifest["total_bytes"]
    except DocumentosError as exc:
        report["code"], report["detail"] = exc.code, exc.message
        if creado:
            report["detail"] += " (el destino restaurado NO es confiable: revisarlo antes de usarlo)"
    except OSError as exc:
        report["code"], report["detail"] = "IO_ERROR", type(exc).__name__
    finally:
        if tmp is not None and tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return report
