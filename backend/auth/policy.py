"""Politica de autorizacion B10 (pura) y adaptadores de sesion/UX.

Origen certificado (reference_fix02): ``security/authorization.py`` (decide, matriz), ``security/session_adapter.py``
(actor desde la sesion), ``security/ui_messages.py`` (visual_can) y el entry l. 52131-52140 (modulos visibles).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from .core import to_int_or_none

ROLE_SUPERADMIN = "superadmin"
ROLE_COORDINADOR = "coordinador_institucional"
ROLE_DEPARTAMENTO = "usuario_departamento"
ROLE_SOLO_LECTURA = "solo_lectura"
KNOWN_ROLES = frozenset({ROLE_SUPERADMIN, ROLE_COORDINADOR, ROLE_DEPARTAMENTO, ROLE_SOLO_LECTURA})

ACCESS_NORMAL = "normal"
ACCESS_READ_ONLY = "read_only"
ACCESS_BLOCKED = "blocked"
KNOWN_ACCESS_MODES = frozenset({ACCESS_NORMAL, ACCESS_READ_ONLY, ACCESS_BLOCKED})

OP_READ = "read"
OP_WRITE = "write"
OP_DELETE = "delete"
OP_ADMIN = "admin"
KNOWN_OPERATIONS = frozenset({OP_READ, OP_WRITE, OP_DELETE, OP_ADMIN})

SCOPE_DEPARTMENT = "department"
SCOPE_INSTITUTION = "institution"
SCOPE_GLOBAL = "global"
KNOWN_SCOPES = frozenset({SCOPE_DEPARTMENT, SCOPE_INSTITUTION, SCOPE_GLOBAL})

DOMAIN_SAAS = "saas"
DOMAIN_MATERIAS = "materias"
BUSINESS_DOMAINS = frozenset({
    "docentes", "designaciones", "periodos", DOMAIN_MATERIAS, "comisiones", "investigacion", "extension",
    "proyectos", "movimientos", "documentos", "disposiciones", "actividades_especiales", "sueldos",
    "configuracion",
})
KNOWN_DOMAINS = BUSINESS_DOMAINS | {DOMAIN_SAAS}

_MUTATION_MATRIX = {
    ROLE_SUPERADMIN: {OP_WRITE: KNOWN_DOMAINS, OP_DELETE: KNOWN_DOMAINS, OP_ADMIN: KNOWN_DOMAINS},
    ROLE_DEPARTAMENTO: {OP_WRITE: BUSINESS_DOMAINS, OP_DELETE: frozenset({DOMAIN_MATERIAS})},
    ROLE_COORDINADOR: {OP_WRITE: frozenset({DOMAIN_MATERIAS}), OP_DELETE: frozenset({DOMAIN_MATERIAS})},
    ROLE_SOLO_LECTURA: {},
}
_READ_MATRIX = {
    ROLE_SUPERADMIN: KNOWN_DOMAINS,
    ROLE_DEPARTAMENTO: BUSINESS_DOMAINS,
    ROLE_COORDINADOR: BUSINESS_DOMAINS,
    ROLE_SOLO_LECTURA: BUSINESS_DOMAINS,
}

ALLOW = "ALLOW"
DENY_UNAUTHENTICATED = "DENY_UNAUTHENTICATED"
DENY_MISSING_CONTEXT = "DENY_MISSING_CONTEXT"
DENY_UNKNOWN_ROLE = "DENY_UNKNOWN_ROLE"
DENY_UNKNOWN_ACCESS_MODE = "DENY_UNKNOWN_ACCESS_MODE"
DENY_ACCESS_BLOCKED = "DENY_ACCESS_BLOCKED"
DENY_COMMERCIAL_READ_ONLY = "DENY_COMMERCIAL_READ_ONLY"
DENY_READ_ONLY_ROLE = "DENY_READ_ONLY_ROLE"
DENY_ROLE_NOT_PERMITTED = "DENY_ROLE_NOT_PERMITTED"
DENY_UNKNOWN_ACTION = "DENY_UNKNOWN_ACTION"
DENY_SCOPE_MISSING = "DENY_SCOPE_MISSING"
DENY_SCOPE_MISMATCH = "DENY_SCOPE_MISMATCH"

# Claves de la sesion (mismos nombres que la sesion Streamlit certificada).
SUPERADMIN_INSTITUTION_KEY = "superadmin_institucion_id"
DEPARTMENT_SCOPE_KEY = "tenant_scope_departamento_id"
SCOPE_MODE_KEY = "tenant_scope_modo"


@dataclass(frozen=True)
class ActorContext:
    authenticated: bool
    role: Optional[str]
    access_mode: Optional[str]
    user_ref: str = ""
    institution_id: Optional[int] = None
    department_id: Optional[int] = None
    home_institution_id: Optional[int] = None
    home_department_id: Optional[int] = None
    scope_mode: str = ""


@dataclass(frozen=True)
class Action:
    domain: str
    operation: str
    scope: str = SCOPE_DEPARTMENT

    @property
    def key(self) -> str:
        return f"{self.domain}.{self.operation}"


@dataclass(frozen=True)
class Decision:
    allowed: bool
    code: str
    reason: str = ""


def _deny(code: str, reason: str) -> Decision:
    return Decision(False, code, reason)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_action(action: Any) -> Optional[str]:
    if not isinstance(action, Action):
        return "acción ausente o de tipo inválido"
    if action.domain not in KNOWN_DOMAINS:
        return f"dominio desconocido {action.domain!r}"
    if action.operation not in KNOWN_OPERATIONS:
        return f"operación desconocida {action.operation!r}"
    if action.scope not in KNOWN_SCOPES:
        return f"alcance desconocido {action.scope!r}"
    if action.domain == DOMAIN_SAAS and action.scope != SCOPE_GLOBAL:
        return "las acciones SaaS son de alcance global"
    return None


def _check_scope(actor: ActorContext, action: Action) -> Optional[Decision]:
    role = actor.role
    if action.scope == SCOPE_GLOBAL:
        return None
    inst = actor.institution_id
    if not _is_int(inst):
        return _deny(DENY_SCOPE_MISSING, "no hay institución operativa explícita")
    if role != ROLE_SUPERADMIN:
        if not _is_int(actor.home_institution_id):
            return _deny(DENY_SCOPE_MISSING, "el usuario no tiene institución asignada")
        if inst != actor.home_institution_id:
            return _deny(DENY_SCOPE_MISMATCH, "la institución operativa no es la del usuario")
    if action.scope == SCOPE_DEPARTMENT:
        dep = actor.department_id
        if not _is_int(dep):
            return _deny(DENY_SCOPE_MISSING, "la operación exige un departamento explícito")
        if role in (ROLE_DEPARTAMENTO, ROLE_SOLO_LECTURA):
            if not _is_int(actor.home_department_id):
                return _deny(DENY_SCOPE_MISSING, "el usuario no tiene departamento asignado")
            if dep != actor.home_department_id:
                return _deny(DENY_SCOPE_MISMATCH, "el departamento operativo no es el del usuario")
    return None


def decide(actor: Optional[ActorContext], action: Optional[Action]) -> Decision:
    """Decision pura y total; ante cualquier duda, DENY (B10 ``decide`` sin ``Target``)."""
    problem = _validate_action(action)
    if problem:
        return _deny(DENY_UNKNOWN_ACTION, problem)
    if not isinstance(actor, ActorContext):
        return _deny(DENY_MISSING_CONTEXT, "no hay contexto de actor")
    if actor.authenticated is not True:
        return _deny(DENY_UNAUTHENTICATED, "usuario no autenticado")
    role = actor.role
    if role not in KNOWN_ROLES:
        return _deny(DENY_UNKNOWN_ROLE, f"rol desconocido {role!r}")
    if actor.access_mode not in KNOWN_ACCESS_MODES:
        return _deny(DENY_UNKNOWN_ACCESS_MODE, f"modo de acceso desconocido {actor.access_mode!r}")
    if actor.access_mode == ACCESS_BLOCKED:
        return _deny(DENY_ACCESS_BLOCKED, "acceso bloqueado por estado institucional")
    if action.operation == OP_READ:
        if action.domain not in _READ_MATRIX.get(role, frozenset()):
            return _deny(DENY_ROLE_NOT_PERMITTED, "el rol no puede consultar este dominio")
    else:
        if actor.access_mode == ACCESS_READ_ONLY:
            return _deny(DENY_COMMERCIAL_READ_ONLY, "la institución está en modo solo lectura")
        if role == ROLE_SOLO_LECTURA:
            return _deny(DENY_READ_ONLY_ROLE, "el rol solo_lectura no puede modificar datos")
        if action.domain not in _MUTATION_MATRIX.get(role, {}).get(action.operation, frozenset()):
            return _deny(DENY_ROLE_NOT_PERMITTED, f"el rol no tiene permiso {action.key}")
    scope_problem = _check_scope(actor, action)
    if scope_problem is not None:
        return scope_problem
    return Decision(True, ALLOW, "permitido por la política")


# --- actor desde la sesion (session_adapter) -------------------------------------------------------------
def normalize_role(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    role = value.strip().casefold()
    return role or None


def _fold(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip().casefold()


def commercial_access_mode(user: Mapping[str, Any], role: Optional[str]) -> str:
    if user.get("modo_solo_lectura_comercial") is True:
        return ACCESS_READ_ONLY
    original = normalize_role(user.get("rol_original"))
    if role == ROLE_SUPERADMIN and original in (None, ROLE_SUPERADMIN):
        return ACCESS_NORMAL
    inst_state = _fold(user.get("institucion_estado"))
    if inst_state in ("bloqueada", "suspendida") or _fold(user.get("suscripcion")) in ("inactiva", "cancelada"):
        return ACCESS_BLOCKED
    if inst_state == "solo lectura" or _fold(user.get("estado_pago")) == "vencido":
        return ACCESS_READ_ONLY
    return ACCESS_NORMAL


def actor_from_session(user: Optional[Mapping[str, Any]], scope: Mapping[str, Any]) -> ActorContext:
    if not isinstance(user, Mapping) or not user:
        return ActorContext(authenticated=False, role=None, access_mode=None)
    role = normalize_role(user.get("rol"))
    email = user.get("email")
    user_ref = str(email).strip() if isinstance(email, str) else f"id:{to_int_or_none(user.get('id'))}"
    home_inst = to_int_or_none(user.get("institucion_id"))
    home_dep = to_int_or_none(user.get("departamento_id"))
    if role == ROLE_SUPERADMIN:
        inst = to_int_or_none(scope.get(SUPERADMIN_INSTITUTION_KEY))
        if inst is None:
            inst = home_inst
    else:
        inst = home_inst
    dep = to_int_or_none(scope.get(DEPARTMENT_SCOPE_KEY))
    if dep is None:
        dep = home_dep
    scope_mode = scope.get(SCOPE_MODE_KEY)
    return ActorContext(authenticated=bool(role), role=role, access_mode=commercial_access_mode(user, role),
                        user_ref=user_ref, institution_id=inst, department_id=dep,
                        home_institution_id=home_inst, home_department_id=home_dep,
                        scope_mode=str(scope_mode) if isinstance(scope_mode, str) else "")


def operative_role(user: Mapping[str, Any]) -> Optional[str]:
    """``rol_operativo`` heredado: con solo lectura comercial manda ``rol_original`` para el modelo de scope."""
    if user.get("modo_solo_lectura_comercial") is True and normalize_role(user.get("rol_original")):
        return normalize_role(user.get("rol_original"))
    return normalize_role(user.get("rol"))


# --- modulos visibles (entry l. 52131-52140) + permisos visuales (ui_messages.visual_can) -----------------
MODULE_INICIO = ("inicio", "Inicio", None)
MODULE_CONSOLIDADO = ("consolidado", "Consolidado institucional", None)
MODULE_MATERIAS = ("materias", "Materias", "materias")
MODULE_SAAS = ("administracion_saas", "Administración SaaS", "saas")
MODULES_BASE = (
    MODULE_INICIO,
    ("periodos", "Períodos", "periodos"),
    ("docentes", "Docentes", "docentes"),
    ("sueldos", "Sueldos", "sueldos"),
    ("designaciones", "Designaciones", "designaciones"),
    MODULE_MATERIAS,
    ("comisiones", "Comisiones", "comisiones"),
    ("investigacion", "Investigación", "investigacion"),
    ("extension", "Extensión", "extension"),
    ("actividades_especiales", "Actividades Especiales", "actividades_especiales"),
    ("analisis", "Análisis", "configuracion"),
    ("movimientos", "Movimientos", "movimientos"),
    ("disposiciones", "Disposiciones", "disposiciones"),
    ("resoluciones_respaldos", "Resoluciones y respaldos", "documentos"),
)
_DOMAIN_SCOPE = {"materias": SCOPE_INSTITUTION, "sueldos": SCOPE_INSTITUTION, "saas": SCOPE_GLOBAL}


def visible_modules(effective_role: Optional[str], department_scope: Any) -> list[tuple]:
    modules = list(MODULES_BASE)
    if effective_role in (ROLE_COORDINADOR, ROLE_SUPERADMIN):
        modules.insert(1, MODULE_CONSOLIDADO)
    if effective_role == ROLE_SUPERADMIN:
        modules.append(MODULE_SAAS)
    if effective_role == ROLE_COORDINADOR and department_scope is None:
        return [MODULE_INICIO, MODULE_CONSOLIDADO, MODULE_MATERIAS]
    return modules


def visual_can(actor: ActorContext, operation: str, domain: Optional[str]) -> bool:
    """Solo UX: si un boton de ``operation`` se ve habilitado en un modulo (la autoridad es el backend)."""
    if operation not in (OP_WRITE, OP_DELETE):
        return False
    if domain is not None:
        return decide(actor, Action(domain, operation, _DOMAIN_SCOPE.get(domain, SCOPE_DEPARTMENT))).allowed
    return any(decide(actor, Action(d, operation, _DOMAIN_SCOPE.get(d, SCOPE_DEPARTMENT))).allowed
               for d in sorted(BUSINESS_DOMAINS))
