"""B11 — precondición "backup reciente y verificado" para operaciones críticas (Crear período).

Política explícita (sin ventanas silenciosas):

* ``DEPTIT_BACKUP_DIR``: ruta ABSOLUTA del directorio donde ``tools/b11_backup_postgresql.py`` publica backups.
* ``DEPTIT_CRITICAL_BACKUP_MAX_AGE_HOURS``: antigüedad máxima aceptada, entero 1..168.  Valor recomendado y
  documentado: 24 (``.env.example``).  Ausente o inválido -> DENY (fail-closed): la app nunca inventa una ventana.
* Se exige PostgreSQL + ``DATABASE_URL`` interpretable: el backup debe ser de ESA base (host+puerto+nombre).
* Evidencia aceptada: un manifest de la herramienta B11 que pase ``verify_backup`` completo (esquema, validación PASS,
  identidad, edad <= máximo, no futuro, dump presente, tamaño y SHA-256).  "Hay un .dump en una carpeta" no alcanza.
* El restore drill es requisito de despliegue/staging (``deploy_preflight``), no de cada Crear período.

``install_backup_precondition`` envuelve los nombres indicados de un namespace (los ``globals()`` del entrypoint) en
un ÚNICO punto, ANTES de la frontera B10: la cadena resultante es  B10 autorización -> B11 backup -> cuerpo original.
Si la evidencia no alcanza: hook de UI (mensaje + comando operativo) y ``BackupPreconditionError``; el cuerpo no se
ejecuta (0 conexiones, 0 SQL, 0 commits).  Nunca ejecuta pg_dump ni abre conexiones a la base.
"""
from __future__ import annotations

import datetime as _dt
import functools
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, MutableMapping, Optional

from .backup_manifest import MANIFEST_SUFFIX, list_manifests, utc_now, verify_backup
from .db_identity import DatabaseUrlError, identity_from_url

BACKUP_DIR_ENV = "DEPTIT_BACKUP_DIR"
MAX_AGE_ENV = "DEPTIT_CRITICAL_BACKUP_MAX_AGE_HOURS"
RECOMMENDED_MAX_AGE_HOURS = 24
MAX_AGE_LIMIT_HOURS = 168
GATE_ATTR = "_b11_backup_precondition"
BACKUP_COMMAND_HINT = "python tools/b11_backup_postgresql.py backup"

ALLOW = "ALLOW_RECENT_VERIFIED_BACKUP"
DENY_CODES = {
    "DENY_NOT_POSTGRESQL": "la operación exige PostgreSQL (la evidencia de backup es de PostgreSQL)",
    "DENY_DATABASE_URL": "DATABASE_URL ausente o no interpretable",
    "DENY_CONFIG_BACKUP_DIR": f"{BACKUP_DIR_ENV} ausente, relativo o inexistente",
    "DENY_CONFIG_MAX_AGE": f"{MAX_AGE_ENV} ausente o fuera de 1..{MAX_AGE_LIMIT_HOURS}",
    "DENY_NO_BACKUP": "no hay ningún manifest de backup B11 en el directorio",
    "DENY_MANIFEST_INVALID": "manifest malformado o no corresponde a su dump",
    "DENY_VALIDATION_NOT_PASSED": "el backup no pasó la validación al crearse",
    "DENY_OTHER_DATABASE": "el backup es de otra base de datos",
    "DENY_FUTURE_TIMESTAMP": "el backup tiene fecha futura",
    "DENY_EXPIRED": "el backup más reciente supera la antigüedad máxima",
    "DENY_DUMP_MISSING": "falta el archivo de dump del manifest",
    "DENY_SIZE_MISMATCH": "el tamaño del dump no coincide con el manifest",
    "DENY_HASH_MISMATCH": "el SHA-256 del dump no coincide con el manifest",
    "DENY_EVIDENCE_ERROR": "no se pudo evaluar la evidencia de backup",
}


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    code: str
    detail: str = ""
    evidence: dict = field(default_factory=dict, compare=False)


class BackupPreconditionError(RuntimeError):
    def __init__(self, decision: GateDecision, operation: str = ""):
        super().__init__(f"{decision.code}: {decision.detail}")
        self.decision, self.operation = decision, operation


class GateInstallError(RuntimeError):
    pass


def _deny(code: str, detail: str = "", **evidence) -> GateDecision:
    return GateDecision(False, code, detail or DENY_CODES.get(code, ""), evidence)


def load_policy(get_value: Callable[[str, Any], Any]):
    """(backup_dir: Path, max_age_hours: int) o GateDecision de denegación."""
    raw_dir = str(get_value(BACKUP_DIR_ENV, "") or "").strip()
    if not raw_dir:
        return _deny("DENY_CONFIG_BACKUP_DIR")
    d = Path(raw_dir)
    if not d.is_absolute() or d.is_symlink() or not d.is_dir():
        return _deny("DENY_CONFIG_BACKUP_DIR")
    raw_age = str(get_value(MAX_AGE_ENV, "") or "").strip()
    try:
        age = int(raw_age)
    except ValueError:
        return _deny("DENY_CONFIG_MAX_AGE")
    if not 1 <= age <= MAX_AGE_LIMIT_HOURS:
        return _deny("DENY_CONFIG_MAX_AGE")
    return d.resolve(), age


def validate_backup_evidence(backup_dir, *, database_url, max_age_hours, now: Optional[_dt.datetime] = None,
                             use_postgresql: bool = True) -> GateDecision:
    """Decisión pura sobre la evidencia en ``backup_dir``.  Acepta el backup válido más reciente; si ninguno es
    válido, devuelve el motivo del más reciente (el más informativo para el operador)."""
    if not use_postgresql:
        return _deny("DENY_NOT_POSTGRESQL")
    try:
        identity = identity_from_url(database_url)
    except DatabaseUrlError:
        return _deny("DENY_DATABASE_URL")
    now = now or utc_now()
    manifests = list_manifests(backup_dir)
    if not manifests:
        return _deny("DENY_NO_BACKUP", backup_dir=str(backup_dir))

    def stamp(p):  # deptit_<db>_<YYYYmmddTHHMMSSZ>.manifest.json -> sello UTC (orden cronológico, no por nombre)
        return p.name[:-len(MANIFEST_SUFFIX)][-16:]

    checks = []
    for m in sorted(manifests, key=lambda p: (stamp(p), p.name), reverse=True):
        chk = verify_backup(m, expected_identity=identity, max_age_hours=max_age_hours, now=now)
        checks.append(chk.summary())
        if chk.ok:
            return GateDecision(True, ALLOW, f"backup verificado {chk.created_at_utc} ({chk.age_hours:.1f} h)",
                                {"manifest": m.name, "sha256": chk.manifest["dump"]["sha256"],
                                 "age_hours": round(chk.age_hours, 2), "max_age_hours": max_age_hours,
                                 "rejected_newer": checks[:-1]})
    newest = checks[0]
    return _deny(f"DENY_{newest['code']}", "", candidates=checks[:10], max_age_hours=max_age_hours)


def require_recent_backup(get_value: Callable[[str, Any], Any], *, database_url, use_postgresql: bool,
                          now: Optional[_dt.datetime] = None) -> GateDecision:
    """Política completa: configuración + evidencia.  Nunca levanta (errores -> DENY_EVIDENCE_ERROR)."""
    try:
        if not use_postgresql:
            return _deny("DENY_NOT_POSTGRESQL")
        policy = load_policy(get_value)
        if isinstance(policy, GateDecision):
            return policy
        backup_dir, max_age = policy
        return validate_backup_evidence(backup_dir, database_url=database_url, max_age_hours=max_age, now=now,
                                        use_postgresql=use_postgresql)
    except Exception as exc:  # evidencia no evaluable -> denegar, nunca permitir
        return _deny("DENY_EVIDENCE_ERROR", f"{DENY_CODES['DENY_EVIDENCE_ERROR']} ({type(exc).__name__})")


def mensaje_precondicion_backup(decision: GateDecision) -> str:
    """Mensaje operativo para la UI.  Sin rutas internas sensibles ni secretos."""
    motivo = DENY_CODES.get(decision.code, decision.detail or decision.code)
    return ("No se puede crear el período: falta un backup reciente y verificado de la base de datos "
            f"({motivo}; código {decision.code}).  Pedí al operador que ejecute `{BACKUP_COMMAND_HINT}` "
            f"(ver docs/B11_OPERATIONAL_READINESS.md) y volvé a intentar.  No se realizó ningún cambio.")


def guard_with_backup_precondition(fn: Callable, name: str, evidence_provider: Callable[[], GateDecision],
                                   on_denied: Optional[Callable[[str, GateDecision], None]] = None,
                                   recorder: Optional[Callable[[dict], None]] = None) -> Callable:
    if not callable(fn):
        raise GateInstallError(f"{name}: no es invocable")
    if inspect.isgeneratorfunction(fn) or inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn):
        raise GateInstallError(f"{name}: una función perezosa escaparía a la precondición")

    @functools.wraps(fn)
    def gated(*args, **kwargs):
        try:
            decision = evidence_provider()
            if not isinstance(decision, GateDecision):
                decision = _deny("DENY_EVIDENCE_ERROR", "el proveedor de evidencia no devolvió una decisión")
        except Exception as exc:
            decision = _deny("DENY_EVIDENCE_ERROR", f"{DENY_CODES['DENY_EVIDENCE_ERROR']} ({type(exc).__name__})")
        if recorder is not None:
            recorder({"operation": name, "allowed": decision.allowed, "code": decision.code})
        if not decision.allowed:
            if on_denied is not None:
                on_denied(name, decision)
            raise BackupPreconditionError(decision, name)
        return fn(*args, **kwargs)

    setattr(gated, GATE_ATTR, {"name": name, "wrapped": fn})
    return gated


def is_gated(obj) -> bool:
    return hasattr(obj, GATE_ATTR)


def install_backup_precondition(namespace: MutableMapping[str, Any], *, names: Iterable[str],
                                evidence_provider: Callable[[], GateDecision],
                                on_denied: Optional[Callable[[str, GateDecision], None]] = None,
                                recorder: Optional[Callable[[dict], None]] = None) -> dict:
    """Instala la precondición en un único punto.  Fail-closed: nombre ausente, ya instalado, o frontera B10 ya
    instalada sobre el nombre (el orden exigido es B11 primero, B10 por fuera) -> ``GateInstallError``."""
    names = list(names)
    if not names:
        raise GateInstallError("sin operaciones críticas a proteger")
    missing = [n for n in names if not callable(namespace.get(n))]
    if missing:
        raise GateInstallError(f"operaciones críticas ausentes del namespace: {missing}")
    twice = [n for n in names if is_gated(namespace[n])]
    if twice:
        raise GateInstallError(f"precondición instalada dos veces: {twice}")
    b10 = [n for n in names if hasattr(namespace[n], "_b10_write_guard")]
    if b10:
        raise GateInstallError(f"la frontera B10 ya envuelve {b10}: instalar la precondición B11 antes")
    wrapped = {n: guard_with_backup_precondition(namespace[n], n, evidence_provider, on_denied, recorder) for n in names}
    namespace.update(wrapped)
    return {"installed": sorted(wrapped)}
