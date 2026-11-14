"""Funciones puras de autenticacion y sesion (sin base de datos, sin FastAPI).

Origen certificado (reference_fix02):
- hash/verificacion: entry ``_hash_password`` / ``_verify_password``;
- contrasenas publicas: ``security/credentials.py``;
- login/sesion: ``security/session_b12g.py`` (B12G);
- vencimiento: entry ``fecha_vencimiento_vencida`` + ``extracted_batch04/fechas._date_to_iso``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Mapping, Optional

# --- mensajes visibles (textos identicos a B12G) ---------------------------------------------------------
GENERIC_LOGIN_MESSAGE = "Credenciales inválidas o acceso temporalmente no disponible."
UNAVAILABLE_MESSAGE = ("No se pudo verificar tu sesión en este momento. Por seguridad no se muestra información ni se "
                       "permiten cambios: reintentá en unos instantes.")
PUBLIC_DEFAULT_MESSAGE = ("Esa contraseña es una credencial pública conocida y está deshabilitada. "
                          "Solicitá al administrador que restablezca tu contraseña.")
BLOCKED_INSTITUTION_MESSAGE = "La institución está bloqueada o suspendida. Contactá al administrador."
BLOCKED_SUBSCRIPTION_MESSAGE = "La suscripción de la institución está inactiva."
NOTICE_EXPIRED = "Tu sesión expiró. Volvé a ingresar."
NOTICE_REVOKED = "Tu sesión se cerró porque cambiaron tus datos de acceso o los de tu institución. Volvé a ingresar."
NOTICE_INVALID = "Tu sesión no es válida. Volvé a ingresar."

# --- motivos de fin de sesion (B12G) ---------------------------------------------------------------------
END_LOGOUT = "LOGOUT"
END_NO_IDENTITY = "NO_IDENTITY"
END_METADATA_INVALID = "METADATA_INVALID"
END_IDLE_TIMEOUT = "IDLE_TIMEOUT"
END_ABSOLUTE_TIMEOUT = "ABSOLUTE_TIMEOUT"
END_USER_DELETED = "USER_DELETED"
END_USER_INACTIVE = "USER_INACTIVE"
END_IDENTITY_AMBIGUOUS = "IDENTITY_AMBIGUOUS"
END_CREDENTIALS_CHANGED = "CREDENTIALS_CHANGED"
END_IDENTITY_CHANGED = "IDENTITY_CHANGED"
END_COMMERCIAL_BLOCKED = "COMMERCIAL_BLOCKED"
END_COMMERCIAL_CHANGED = "COMMERCIAL_STATE_CHANGED"
EXPIRY_REASONS = frozenset({END_IDLE_TIMEOUT, END_ABSOLUTE_TIMEOUT})
REVOCATION_REASONS = frozenset({END_USER_DELETED, END_USER_INACTIVE, END_IDENTITY_AMBIGUOUS, END_CREDENTIALS_CHANGED,
                                END_IDENTITY_CHANGED, END_COMMERCIAL_BLOCKED, END_COMMERCIAL_CHANGED})

# --- estado comercial ------------------------------------------------------------------------------------
COMMERCIAL_NORMAL = "normal"
COMMERCIAL_READ_ONLY = "read_only"
COMMERCIAL_BLOCKED_INSTITUTION = "blocked_institution"
COMMERCIAL_BLOCKED_SUBSCRIPTION = "blocked_subscription"
COMMERCIAL_BLOCKED = frozenset({COMMERCIAL_BLOCKED_INSTITUTION, COMMERCIAL_BLOCKED_SUBSCRIPTION})
SESSION_COMMERCIAL_MODES = frozenset({COMMERCIAL_NORMAL, COMMERCIAL_READ_ONLY})

# --- usuario de sesion: allowlist (nunca salt ni password_hash) -------------------------------------------
SAFE_USER_FIELDS = ("id", "email", "nombre", "rol", "estado", "institucion_id", "departamento_id",
                    "institucion_nombre", "institucion_slug", "institucion_estado", "fecha_vencimiento", "estado_pago",
                    "suscripcion", "departamento_nombre", "departamento_slug")
SECRET_FIELDS = ("salt", "password_hash")
_INT_FIELDS = ("id", "institucion_id", "departamento_id")

# --- PBKDF2 (entry _hash_password) -----------------------------------------------------------------------
PBKDF2_ITERATIONS = 120000
DUMMY_SALT = hashlib.sha256(b"deptit-b12g-dummy-salt-v1").hexdigest()[:32]
DUMMY_HASH = hashlib.sha256(b"deptit-b12g-dummy-hash-v1").hexdigest()

# --- 6A-B1: formato versionado ``pbkdf2_sha256$<iteraciones>$<hex>`` (mismo salt hex como texto) ---------------
# Los hashes legados (hex de 64, 120 000 iteraciones) se siguen verificando; al autenticar se re-hashean con las
# iteraciones actuales (migracion progresiva, sin invalidar a nadie).  Las altas y cambios de SaaS usan el actual.
HASH_PREFIX = "pbkdf2_sha256$"
PBKDF2_ITERATIONS_ACTUAL = 600000
PBKDF2_ITERATIONS_MAX = 5000000
# Equivalente del hash dummy con el costo actual: el rechazo de un email inexistente cuesta lo mismo que una cuenta.
DUMMY_HASH_ACTUAL = f"{HASH_PREFIX}{PBKDF2_ITERATIONS_ACTUAL}${DUMMY_HASH}"

# --- contrasenas publicas heredadas (B10 credentials.py): solo huellas SHA-256, sin texto en claro --------
PUBLIC_DEFAULT_PASSWORD_SHA256 = frozenset({
    "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9",
    "8c63a2fc2b14d8ae6f9d0bf2e2c4227ac2dc4bd84768e1259226b0c3d84f1c65",
    "7dac80609816447418101ae609dc167a95934d95ddff0815938846ea69155dc5",
})

SUBJECT_PREFIX = "b12g1:"

# --- configuracion (defaults tecnicos B12G, mismos nombres y rangos) -------------------------------------
CFG_IDLE = "DEPTIT_SESSION_IDLE_TIMEOUT_MINUTES"
CFG_ABSOLUTE = "DEPTIT_SESSION_ABSOLUTE_HOURS"
CFG_MAX_FAILED = "DEPTIT_LOGIN_MAX_FAILED_ATTEMPTS"
CFG_WINDOW = "DEPTIT_LOGIN_FAILURE_WINDOW_MINUTES"
CFG_LOCKOUT = "DEPTIT_LOGIN_LOCKOUT_MINUTES"
CONFIG_SPEC = {
    CFG_IDLE: (30, 5, 240),
    CFG_ABSOLUTE: (8, 1, 24),
    CFG_MAX_FAILED: (5, 3, 20),
    CFG_WINDOW: (15, 1, 1440),
    CFG_LOCKOUT: (15, 1, 1440),
}


class ConfigError(RuntimeError):
    """Configuracion de sesion invalida (fail-closed)."""


@dataclass(frozen=True)
class Config:
    idle_seconds: float
    absolute_seconds: float
    max_failed_attempts: int
    failure_window_seconds: float
    lockout_seconds: float


def _config_int(get_value: Callable[[str], Optional[str]], name: str) -> int:
    default, low, high = CONFIG_SPEC[name]
    raw = get_value(name)
    text = "" if raw is None else str(raw).strip()
    if not text:
        return default
    if not text.isdigit():
        raise ConfigError(f"{name} debe ser un entero entre {low} y {high}")
    value = int(text)
    if not low <= value <= high:
        raise ConfigError(f"{name} debe estar entre {low} y {high}")
    return value


def load_config(get_value: Callable[[str], Optional[str]] = os.environ.get) -> Config:
    return Config(idle_seconds=_config_int(get_value, CFG_IDLE) * 60.0,
                  absolute_seconds=_config_int(get_value, CFG_ABSOLUTE) * 3600.0,
                  max_failed_attempts=_config_int(get_value, CFG_MAX_FAILED),
                  failure_window_seconds=_config_int(get_value, CFG_WINDOW) * 60.0,
                  lockout_seconds=_config_int(get_value, CFG_LOCKOUT) * 60.0)


# --- contrasenas -----------------------------------------------------------------------------------------
def hash_password(password: Any, salt: str) -> str:
    """Igual que el ``_hash_password`` certificado: el salt hex se usa como texto UTF-8."""
    return hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt.encode("utf-8"),
                               PBKDF2_ITERATIONS).hex()


def hash_password_actual(password: Any, salt: str, iterations: int = PBKDF2_ITERATIONS_ACTUAL) -> str:
    """Formato versionado (6A-B1): ``pbkdf2_sha256$<iteraciones>$<hex>``."""
    digest = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt.encode("utf-8"), int(iterations)).hex()
    return f"{HASH_PREFIX}{int(iterations)}${digest}"


def _parse_hash(password_hash: str) -> Optional[tuple[int, str]]:
    """(iteraciones, hex) de un hash versionado o legado; None si el formato no es valido."""
    if password_hash.startswith(HASH_PREFIX):
        partes = password_hash[len(HASH_PREFIX):].split("$")
        if len(partes) != 2 or not partes[0].isdigit():
            return None
        iteraciones = int(partes[0])
        if not 1 <= iteraciones <= PBKDF2_ITERATIONS_MAX:
            return None
        return iteraciones, partes[1]
    return PBKDF2_ITERATIONS, password_hash


def verify_password(password: Any, salt: Any, password_hash: Any) -> bool:
    if not salt or not password_hash:
        return False
    parsed = _parse_hash(str(password_hash))
    if parsed is None:
        return False
    iteraciones, esperado = parsed
    if iteraciones == PBKDF2_ITERATIONS and not str(password_hash).startswith(HASH_PREFIX):
        return secrets.compare_digest(hash_password(password, str(salt)), esperado)
    calculado = hash_password_actual(password, str(salt), iteraciones)[len(HASH_PREFIX) + len(str(iteraciones)) + 1:]
    return secrets.compare_digest(calculado, esperado)


def needs_rehash(password_hash: Any) -> bool:
    """True si el hash es legado o usa menos iteraciones que las actuales."""
    parsed = _parse_hash(str(password_hash or ""))
    return parsed is not None and (not str(password_hash).startswith(HASH_PREFIX)
                                   or parsed[0] < PBKDF2_ITERATIONS_ACTUAL)


def is_public_default_password(password: Any) -> bool:
    if password is None:
        return False
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest() in PUBLIC_DEFAULT_PASSWORD_SHA256


# --- utilidades ------------------------------------------------------------------------------------------
def normalize_email(value: Any) -> str:
    if value is None:
        return ""
    return unicodedata.normalize("NFC", str(value)).strip().lower()


def subject_key(email: Any) -> str:
    digest = hashlib.sha256(("deptit-b12g-login-v1\x00" + normalize_email(email)).encode("utf-8")).hexdigest()
    return SUBJECT_PREFIX + digest


# 6A-B3: 6 caracteres, como SUBJECT_PREFIX.  ``auth_login_throttle`` exige ``length(subject_key) = 70`` (6 + 64 hex);
# el prefijo original de 6A-B1 ("nextip1:", 8) producia 72 y cada fallo de login con origen confiable terminaba en
# CheckViolation (503 fail-closed).  En desarrollo nunca se ejercitaba: sin proxy confiable no hay limite por origen.
IP_SUBJECT_PREFIX = "nxip1:"


def ip_subject_key(ip: str) -> str:
    """Clave del limite por origen (6A-B1), en la misma tabla ``auth_login_throttle`` (sin DDL); la IP no se guarda
    en claro.  Misma longitud que ``subject_key`` (restriccion de la tabla)."""
    return IP_SUBJECT_PREFIX + hashlib.sha256(("deptit-next-login-ip-v1\x00" + ip).encode("utf-8")).hexdigest()


def _text(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value)


def to_int_or_none(value: Any) -> Optional[int]:
    """Entero estricto (session_adapter.to_int_or_none): rechaza None, NaN, bool y textos no numericos."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float):
        if math.isnan(value) or not value.is_integer():
            return None
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def fecha_vencimiento_vencida(value: Any, today: Optional[date] = None) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, datetime):
        txt = value.date().isoformat()
    elif isinstance(value, date):
        txt = value.isoformat()
    else:
        txt = str(value)[:10]
    try:
        return datetime.strptime(txt, "%Y-%m-%d").date() < (today or date.today())
    except ValueError:
        return False


# --- huellas y derivaciones (B12G) -----------------------------------------------------------------------
def credential_fingerprint(row: Mapping[str, Any]) -> str:
    payload = b"deptit-b12g-credential-v1\x00" + _text(row.get("salt")).encode("utf-8") + b"\x00" + \
        _text(row.get("password_hash")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def identity_fingerprint(row: Mapping[str, Any]) -> str:
    rol = row.get("rol")
    payload = ["deptit-b12g-identity-v1", to_int_or_none(row.get("id")), normalize_email(row.get("email")),
               None if rol is None else _text(rol), to_int_or_none(row.get("institucion_id")),
               to_int_or_none(row.get("departamento_id"))]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()


def commercial_outcome(row: Mapping[str, Any], expired: Callable[[Any], bool] = fecha_vencimiento_vencida) -> str:
    if row.get("rol") == "superadmin":
        return COMMERCIAL_NORMAL
    inst_estado = str(row.get("institucion_estado") or "Activa").strip()
    suscripcion = str(row.get("suscripcion") or "Activa").strip()
    estado_pago = str(row.get("estado_pago") or "Activo").strip()
    if inst_estado in ("Bloqueada", "Suspendida"):
        return COMMERCIAL_BLOCKED_INSTITUTION
    if suscripcion in ("Inactiva", "Cancelada"):
        return COMMERCIAL_BLOCKED_SUBSCRIPTION
    if inst_estado == "Solo lectura" or estado_pago == "Vencido" or bool(expired(row.get("fecha_vencimiento"))):
        return COMMERCIAL_READ_ONLY
    return COMMERCIAL_NORMAL


def derive_session_user(row: Mapping[str, Any], outcome: str) -> dict:
    user = {}
    for key in SAFE_USER_FIELDS:
        value = row.get(key)
        if key in _INT_FIELDS:
            value = to_int_or_none(value)
        elif isinstance(value, float) and math.isnan(value):
            value = None
        user[key] = value
    if outcome == COMMERCIAL_READ_ONLY and row.get("rol") != "superadmin":
        user["rol_original"] = row.get("rol")
        user["rol"] = "solo_lectura"
        user["modo_solo_lectura_comercial"] = True
    return user


def new_metadata(row: Mapping[str, Any], outcome: str, *, now: float) -> dict:
    return {"user_id": to_int_or_none(row.get("id")), "issued_mono": float(now), "last_activity_mono": float(now),
            "identity_fp": identity_fingerprint(row), "credential_fp": credential_fingerprint(row),
            "commercial": outcome}


def check_metadata(meta: Any, now: float, cfg: Config) -> Optional[str]:
    """Motivo de fin por metadata/expiracion (B12G ``check_metadata``; el nonce de proceso es implicito: el almacen
    vive en memoria del proceso)."""
    if not isinstance(meta, Mapping):
        return END_METADATA_INVALID
    uid = meta.get("user_id")
    if not isinstance(uid, int) or isinstance(uid, bool) or uid <= 0 \
            or meta.get("commercial") not in SESSION_COMMERCIAL_MODES:
        return END_METADATA_INVALID
    issued, last = float(meta["issued_mono"]), float(meta["last_activity_mono"])
    if not issued <= last <= now:
        return END_METADATA_INVALID
    if now - issued >= cfg.absolute_seconds:
        return END_ABSOLUTE_TIMEOUT
    if now - last >= cfg.idle_seconds:
        return END_IDLE_TIMEOUT
    return None


def evaluate_fresh(meta: Mapping[str, Any], rows: list, expired: Callable[[Any], bool] = fecha_vencimiento_vencida):
    """(motivo, None) o (None, usuario fresco): misma secuencia que B12G ``evaluate_fresh``."""
    if not rows:
        return END_USER_DELETED, None
    if len(rows) != 1:
        return END_IDENTITY_AMBIGUOUS, None
    row = rows[0]
    if to_int_or_none(row.get("id")) != meta.get("user_id"):
        return END_IDENTITY_CHANGED, None
    if _text(row.get("estado")) != "Activo":
        return END_USER_INACTIVE, None
    if credential_fingerprint(row) != meta.get("credential_fp"):
        return END_CREDENTIALS_CHANGED, None
    if identity_fingerprint(row) != meta.get("identity_fp"):
        return END_IDENTITY_CHANGED, None
    outcome = commercial_outcome(row, expired)
    if outcome in COMMERCIAL_BLOCKED:
        return END_COMMERCIAL_BLOCKED, None
    if outcome != meta.get("commercial"):
        return END_COMMERCIAL_CHANGED, None
    return None, derive_session_user(row, outcome)


def notice_for(reason: str) -> Optional[str]:
    if reason == END_LOGOUT:
        return None
    if reason in EXPIRY_REASONS:
        return NOTICE_EXPIRED
    if reason in REVOCATION_REASONS:
        return NOTICE_REVOKED
    return NOTICE_INVALID
