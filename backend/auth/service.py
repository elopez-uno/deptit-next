"""Servicio de autenticacion: login B12G, sesiones en memoria del proceso, revalidacion por request y contexto.

Sesion: equivalente directo de ``st.session_state`` certificado.  Vive en la memoria de ESTE proceso (un solo worker
de uvicorn); un reinicio invalida todas las sesiones (B12G: ``PROCESS_CHANGED``).  El navegador solo guarda un token
opaco aleatorio en una cookie HttpOnly; aqui se indexa por su SHA-256 (el token no se conserva).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Optional

from . import core, policy
from .repository import AuthRepository

log = logging.getLogger("deptit_next.auth")

TOKEN_BYTES = 32


def _ip_limits_de_settings() -> Optional[tuple[int, float, float]]:
    """Umbrales del limite por origen desde la configuracion central (validada al arrancar)."""
    import settings as app_settings
    s = app_settings.get()
    return s.login_ip_max_failed, s.login_ip_window_minutes * 60.0, s.login_ip_lockout_minutes * 60.0


class SessionEnded(Exception):
    """Hay evidencia de que la sesion no es valida: se elimina y se exige login."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class AuthUnavailable(Exception):
    """No se pudo completar o verificar de forma segura (base, configuracion): fail-closed sin revocar."""


class ContextError(Exception):
    """Seleccion de contexto no permitida para el rol o inexistente."""


@dataclass
class LoginResult:
    user: Optional[dict]
    meta: Optional[dict]
    message: str
    status: int = 200


@dataclass
class SessionRecord:
    user: dict
    meta: dict
    scope: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ScopeResolution:
    institution: Optional[dict]
    department: Optional[dict]
    reason: Optional[str]


def _absent(value: Any) -> bool:
    """B12B ``_is_absent``: None, texto vacio/espacios o NaN."""
    if value is None:
        return True
    if isinstance(value, float):
        return value != value
    if isinstance(value, str):
        return not value.strip()
    return False


def _token_id(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SessionStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._items: dict[str, SessionRecord] = {}

    def create(self, record: SessionRecord) -> str:
        token = secrets.token_urlsafe(TOKEN_BYTES)
        with self._lock:
            self._items[_token_id(token)] = record
        return token

    def get(self, token: Optional[str]) -> Optional[SessionRecord]:
        if not token:
            return None
        with self._lock:
            return self._items.get(_token_id(token))

    def delete(self, token: Optional[str]) -> bool:
        if not token:
            return False
        with self._lock:
            return self._items.pop(_token_id(token), None) is not None

    def purge(self, is_expired: Callable[[SessionRecord], bool]) -> None:
        with self._lock:
            for key in [k for k, rec in self._items.items() if is_expired(rec)]:
                del self._items[key]

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


class AuthService:
    def __init__(self, repo: AuthRepository, *, clock: Callable[[], float] = time.monotonic,
                 config_source: Callable[[str], Optional[str]] | None = None,
                 expired: Callable[[Any], bool] = core.fecha_vencimiento_vencida,
                 ip_limits: Callable[[], Optional[tuple[int, float, float]]] | None = None,
                 password_upgrade: bool = True):
        self.repo = repo
        self.store = SessionStore()
        self.clock = clock
        self._config_source = config_source
        self._expired = expired
        # 6A-B1: limite por origen (max fallos, ventana s, bloqueo s) y re-hash progresivo de contraseñas.
        self._ip_limits = ip_limits or _ip_limits_de_settings
        self._password_upgrade = password_upgrade

    def config(self) -> core.Config:
        return core.load_config(self._config_source) if self._config_source else core.load_config()

    # ------------------------------------------------------------------ login (B12G SessionSecurityRuntime.login)
    def login(self, email: Any, password: Any, client_ip: Optional[str] = None) -> LoginResult:
        """Levanta ``AuthUnavailable`` ante base/tabla/configuracion (fail-closed).  ``client_ip``: origen CONFIABLE
        (``auth.client_ip``) o None; sin origen confiable solo rige el limite por cuenta."""
        try:
            return self._login(email, password, client_ip)
        except core.ConfigError as exc:
            log.error("login no disponible (configuracion): %s", exc)
            raise AuthUnavailable() from None
        except AuthUnavailable:
            raise
        except Exception as exc:
            log.error("login no disponible (fail-closed): %s", type(exc).__name__)
            raise AuthUnavailable() from None

    def _login(self, email: Any, password: Any, client_ip: Optional[str] = None) -> LoginResult:
        cfg = self.config()
        pwd = "" if password is None else str(password)
        ip_key, ip_cfg = self._ip_throttle(cfg, client_ip)
        if pwd and core.is_public_default_password(pwd):
            self._ip_failure(ip_key, ip_cfg)
            return LoginResult(None, None, core.PUBLIC_DEFAULT_MESSAGE, 401)
        email_n = core.normalize_email(email)
        if not email_n or not pwd:
            core.verify_password(pwd, core.DUMMY_SALT, core.DUMMY_HASH_ACTUAL)
            self._ip_failure(ip_key, ip_cfg)
            return LoginResult(None, None, core.GENERIC_LOGIN_MESSAGE, 401)
        key = core.subject_key(email_n)
        # Origen bloqueado o cuenta bloqueada: misma respuesta y mismo costo que una credencial incorrecta.
        if (ip_key is not None and self.repo.lock_state(ip_key)) or self.repo.lock_state(key):
            core.verify_password(pwd, core.DUMMY_SALT, core.DUMMY_HASH_ACTUAL)
            return LoginResult(None, None, core.GENERIC_LOGIN_MESSAGE, 401)
        rows = self.repo.users_by_email(email_n)
        row = rows[0] if len(rows) == 1 else None
        if row is not None and core._text(row.get("salt")) and core._text(row.get("password_hash")):
            ok = core.verify_password(pwd, row.get("salt"), row.get("password_hash"))
        else:
            ok = core.verify_password(pwd, core.DUMMY_SALT, core.DUMMY_HASH_ACTUAL) and False
        if len(rows) > 1:
            log.error("login rechazado: el email coincide (sin distinguir mayúsculas) con %d cuentas; "
                      "DATA-VERIFICATION-PENDING", len(rows))
        if row is None or not ok or core._text(row.get("estado")) != "Activo":
            self.repo.register_failure(key, cfg)
            self._ip_failure(ip_key, ip_cfg)
            return LoginResult(None, None, core.GENERIC_LOGIN_MESSAGE, 401)
        self.repo.reset(key)  # el contador por origen NO se reinicia con un exito (una cuenta valida no lo limpia)
        row = self._upgrade_password(row, pwd)
        self.repo.purge(max(cfg.failure_window_seconds, cfg.lockout_seconds) + 86400.0)
        outcome = core.commercial_outcome(row, self._expired)
        if outcome == core.COMMERCIAL_BLOCKED_INSTITUTION:
            return LoginResult(None, None, core.BLOCKED_INSTITUTION_MESSAGE, 403)
        if outcome == core.COMMERCIAL_BLOCKED_SUBSCRIPTION:
            return LoginResult(None, None, core.BLOCKED_SUBSCRIPTION_MESSAGE, 403)
        meta = core.new_metadata(row, outcome, now=self.clock())
        return LoginResult(core.derive_session_user(row, outcome), meta, "")

    def _ip_throttle(self, cfg: core.Config, client_ip: Optional[str]):
        if not client_ip:
            return None, None
        limits = self._ip_limits()
        if limits is None:
            return None, None
        max_failed, window, lockout = limits
        return core.ip_subject_key(client_ip), replace(cfg, max_failed_attempts=int(max_failed),
                                                       failure_window_seconds=float(window),
                                                       lockout_seconds=float(lockout))

    def _ip_failure(self, ip_key: Optional[str], ip_cfg: Optional[core.Config]) -> None:
        if ip_key is not None:
            self.repo.register_failure(ip_key, ip_cfg)

    def _upgrade_password(self, row: dict, pwd: str) -> dict:
        """Re-hash progresivo (6A-B1): un hash legado o con menos iteraciones se reemplaza por el formato actual,
        con el mismo salt, solo si nadie lo cambio entretanto.  Un fallo no impide el login (se conserva el hash)."""
        old = core._text(row.get("password_hash"))
        if not self._password_upgrade or not core.needs_rehash(old):
            return row
        new = core.hash_password_actual(pwd, core._text(row.get("salt")))
        try:
            if self.repo.update_password_hash(int(row["id"]), old, new):
                row = dict(row, password_hash=new)
                log.info("contraseña re-hasheada al formato actual (usuario %s)", row.get("id"))
        except Exception as exc:
            log.error("re-hash de contraseña no aplicado: %s", type(exc).__name__)
        return row

    def start_session(self, result: LoginResult) -> str:
        """Token nuevo en cada login (sin fijacion de sesion).  Scope inicial = B12G ``start_session``."""
        user = dict(result.user)
        scope = {policy.DEPARTMENT_SCOPE_KEY: user.get("departamento_id"),
                 policy.SCOPE_MODE_KEY: "departamento" if user.get("departamento_id") else "consolidado"}
        self._purge_expired()
        return self.store.create(SessionRecord(user=user, meta=dict(result.meta), scope=scope))

    # ------------------------------------------------------------------ validacion (B12G validate)
    def validate(self, token: Optional[str]) -> SessionRecord:
        """Sesion vigente con el usuario FRESCO.  ``SessionEnded`` (y la sesion se elimina) ante evidencia de
        revocacion/expiracion; ``AuthUnavailable`` ante fallo de base (la sesion NO se revoca)."""
        record = self.store.get(token)
        if record is None:
            raise SessionEnded(core.END_NO_IDENTITY)
        try:
            cfg = self.config()
        except core.ConfigError as exc:
            log.error("sesión no verificable (configuracion): %s", exc)
            raise AuthUnavailable() from None
        now = float(self.clock())
        reason = core.check_metadata(record.meta, now, cfg)
        if reason is None:
            try:
                rows = self.repo.user_by_id(record.meta["user_id"])
            except Exception as exc:
                log.error("sesión no verificable (fail-closed): %s", type(exc).__name__)
                raise AuthUnavailable() from None
            reason, fresh = core.evaluate_fresh(record.meta, rows, self._expired)
        if reason is not None:
            self.store.delete(token)
            log.info("sesión terminada (%s)", reason)
            raise SessionEnded(reason)
        record.meta["last_activity_mono"] = now
        record.user = fresh
        return record

    def logout(self, token: Optional[str]) -> bool:
        return self.store.delete(token)

    def _purge_expired(self) -> None:
        try:
            cfg = self.config()
        except core.ConfigError:
            return
        now = float(self.clock())
        self.store.purge(lambda rec: core.check_metadata(rec.meta, now, cfg) is not None)

    # ------------------------------------------------------------------ contexto institucional / departamental
    def apply_default_context(self, record: SessionRecord) -> None:
        """``configurar_tenant_actual`` certificado: solo el superadmin recibe valores por defecto (primera institucion
        por nombre y su primer departamento por nombre); los demas roles no cambian su scope."""
        if policy.operative_role(record.user) != policy.ROLE_SUPERADMIN:
            return
        scope = record.scope
        institutions = self.repo.institutions()
        if not institutions:
            return
        if policy.SUPERADMIN_INSTITUTION_KEY not in scope:
            scope[policy.SUPERADMIN_INSTITUTION_KEY] = int(institutions[0]["id"])
        departments = self.repo.departments(int(scope[policy.SUPERADMIN_INSTITUTION_KEY]), only_active=False)
        if departments and not scope.get(policy.DEPARTMENT_SCOPE_KEY):
            scope[policy.DEPARTMENT_SCOPE_KEY] = int(departments[0]["id"])

    def resolve_scope(self, record: SessionRecord) -> ScopeResolution:
        """B12B ``ScopeResolver``: valida contra la base, nunca sustituye un valor invalido por otro."""
        user, scope = record.user, record.scope
        role = policy.operative_role(user)
        if policy.normalize_role(user.get("rol")) == policy.ROLE_SUPERADMIN:
            selected = scope.get(policy.SUPERADMIN_INSTITUTION_KEY)
            raw_inst = selected if not _absent(selected) else user.get("institucion_id")
        else:
            raw_inst = user.get("institucion_id")
        inst_id = core.to_int_or_none(raw_inst)
        if _absent(raw_inst):
            return ScopeResolution(None, None, "INSTITUTION_ABSENT")
        if inst_id is None or inst_id <= 0:
            return ScopeResolution(None, None, "INSTITUTION_INVALID")
        institution = self.repo.institution(inst_id)
        if institution is None:
            return ScopeResolution(None, None, "INSTITUTION_NOT_FOUND")
        selected_dep = scope.get(policy.DEPARTMENT_SCOPE_KEY)
        raw_dep = selected_dep if not _absent(selected_dep) else user.get("departamento_id")
        institutional = role in (policy.ROLE_SUPERADMIN, policy.ROLE_COORDINADOR)
        if _absent(raw_dep):
            if institutional:
                return ScopeResolution(institution, None, None)
            return ScopeResolution(None, None, "DEPARTMENT_ABSENT")
        dep_id = core.to_int_or_none(raw_dep)
        if dep_id is None or dep_id <= 0:
            return ScopeResolution(institution if institutional else None, None, "DEPARTMENT_INVALID")
        department = self.repo.department(dep_id)
        if department is None:
            return ScopeResolution(institution if institutional else None, None, "DEPARTMENT_NOT_FOUND")
        if core.to_int_or_none(department.get("institucion_id")) != inst_id:
            return ScopeResolution(institution if institutional else None, None, "DEPARTMENT_MISMATCH")
        return ScopeResolution(institution, department, None)

    def context_options(self, record: SessionRecord) -> dict:
        """Opciones del selector (``sidebar_auth_context``)."""
        role = policy.operative_role(record.user)
        if role == policy.ROLE_SUPERADMIN:
            inst_id = core.to_int_or_none(record.scope.get(policy.SUPERADMIN_INSTITUTION_KEY))
            return {"puede_elegir_institucion": True, "permite_consolidado": False,
                    "instituciones": [_option(r) for r in self.repo.institutions()],
                    "departamentos": [_option(r) for r in self.repo.departments(inst_id, only_active=False)]
                    if inst_id else []}
        if role == policy.ROLE_COORDINADOR:
            inst_id = core.to_int_or_none(record.user.get("institucion_id"))
            return {"puede_elegir_institucion": False, "permite_consolidado": True, "instituciones": [],
                    "departamentos": [_option(r) for r in self.repo.departments(inst_id, only_active=True)]
                    if inst_id else []}
        return {"puede_elegir_institucion": False, "permite_consolidado": False, "instituciones": [],
                "departamentos": []}

    def set_context(self, record: SessionRecord, institution_id: Any, department_id: Any,
                    consolidado: bool) -> None:
        role = policy.operative_role(record.user)
        scope = record.scope
        if role == policy.ROLE_SUPERADMIN:
            inst_id = core.to_int_or_none(institution_id)
            if inst_id is None or inst_id not in {int(r["id"]) for r in self.repo.institutions()}:
                raise ContextError("La institución seleccionada no existe.")
            if consolidado:
                raise ContextError("El superadmin opera siempre sobre un departamento.")
            if inst_id != core.to_int_or_none(scope.get(policy.SUPERADMIN_INSTITUTION_KEY)):
                # sidebar certificado: cambiar de institucion limpia el departamento (luego se toma el primero)
                scope[policy.SUPERADMIN_INSTITUTION_KEY] = inst_id
                scope[policy.DEPARTMENT_SCOPE_KEY] = None
                if department_id is None:
                    self.apply_default_context(record)
                    return
            dep_id = core.to_int_or_none(department_id)
            if dep_id is None:
                self.apply_default_context(record)
                return
            if dep_id not in {int(r["id"]) for r in self.repo.departments(inst_id, only_active=False)}:
                raise ContextError("El departamento no pertenece a la institución seleccionada.")
            scope[policy.DEPARTMENT_SCOPE_KEY] = dep_id
            return
        if role == policy.ROLE_COORDINADOR:
            if institution_id is not None and core.to_int_or_none(institution_id) != \
                    core.to_int_or_none(record.user.get("institucion_id")):
                raise ContextError("Tu rol no puede cambiar de institución.")
            if consolidado:
                scope[policy.DEPARTMENT_SCOPE_KEY] = None
                return
            dep_id = core.to_int_or_none(department_id)
            allowed = {int(r["id"]) for r in
                       self.repo.departments(core.to_int_or_none(record.user.get("institucion_id")) or -1,
                                             only_active=True)}
            if dep_id is None or dep_id not in allowed:
                raise ContextError("El departamento no está disponible para tu institución.")
            scope[policy.DEPARTMENT_SCOPE_KEY] = dep_id
            return
        raise ContextError("Tu rol opera con una institución y un departamento fijos.")


def _option(row: dict) -> dict:
    return {"id": int(row["id"]), "nombre": row.get("nombre"), "estado": row.get("estado")}
