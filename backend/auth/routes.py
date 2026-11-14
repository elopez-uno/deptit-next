"""Endpoints de autenticacion.  Ninguna respuesta incluye salt, password_hash, tokens ni secretos."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

import settings as app_settings

from . import core, policy
from .client_ip import client_ip
from .service import AuthService, AuthUnavailable, ContextError, SessionEnded, SessionRecord

COOKIE_NAME = "deptit_session"
CSRF_HEADER = "x-deptit-request"
CSRF_VALUE = "1"

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: str = Field(default="", max_length=320)
    password: str = Field(default="", max_length=1024)


class ContextBody(BaseModel):
    institucion_id: Optional[int] = None
    departamento_id: Optional[int] = None
    consolidado: bool = False


def _service(request: Request) -> AuthService:
    return request.app.state.auth


def _cookie_secure() -> bool:
    # 6A-B1: decision centralizada por entorno (settings.py).  Desarrollo admite HTTP local (default 0);
    # preproduccion/produccion exigen Secure y el arranque falla si se intenta desactivarlo.
    return app_settings.get().cookie_secure


# Atributos de la cookie de sesion (explicitos): HttpOnly, SameSite=Strict, Path=/ y vida maxima = expiracion absoluta.
COOKIE_ATTRS = {"path": "/", "httponly": True, "samesite": "strict"}


def _set_cookie(response: Response, token: str, cfg: core.Config) -> None:
    response.set_cookie(COOKIE_NAME, token, max_age=int(cfg.absolute_seconds), secure=_cookie_secure(),
                        **COOKIE_ATTRS)


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, secure=_cookie_secure(), **COOKIE_ATTRS)


def _error(status: int, code: str, message: str, *, clear_cookie: bool = False) -> JSONResponse:
    response = JSONResponse(status_code=status, content={"error": {"code": code, "message": message}},
                            headers={"Cache-Control": "no-store"})
    if clear_cookie:
        _clear_cookie(response)
    return response


def _require_csrf(request: Request) -> Optional[JSONResponse]:
    """Escrituras de sesion solo desde el proxy Next.js (que valida el Origin): exige cabecera propia."""
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        return _error(403, "CSRF", "Solicitud rechazada.")
    return None


class Authenticated:
    """Dependencia: sesion revalidada contra la base en CADA request (B12G puerta)."""

    def __init__(self, record: Optional[SessionRecord], failure: Optional[JSONResponse], token: Optional[str]):
        self.record, self.failure, self.token = record, failure, token


def authenticated(request: Request) -> Authenticated:
    token = request.cookies.get(COOKIE_NAME)
    service = _service(request)
    try:
        record = service.validate(token)
    except SessionEnded as exc:
        reason = exc.reason
        if reason == core.END_NO_IDENTITY:
            return Authenticated(None, _error(401, "NO_SESSION", "No hay una sesión activa.",
                                              clear_cookie=bool(token)), token)
        return Authenticated(None, _error(401, reason, core.notice_for(reason) or core.NOTICE_INVALID,
                                          clear_cookie=True), token)
    except AuthUnavailable:
        return Authenticated(None, _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE), token)
    return Authenticated(record, None, token)


def _named(row: Optional[dict]) -> Optional[dict]:
    return None if row is None else {"id": int(row["id"]), "nombre": row.get("nombre")}


def session_payload(service: AuthService, record: SessionRecord) -> dict:
    service.apply_default_context(record)
    user, scope = record.user, record.scope
    resolution = service.resolve_scope(record)
    effective_role = policy.normalize_role(user.get("rol"))
    actor = policy.actor_from_session(user, scope)
    modules = []
    for key, label, domain in policy.visible_modules(effective_role, scope.get(policy.DEPARTMENT_SCOPE_KEY)):
        modules.append({"clave": key, "nombre": label,
                        "puede_escribir": policy.visual_can(actor, policy.OP_WRITE, domain),
                        "puede_borrar": policy.visual_can(actor, policy.OP_DELETE, domain)})
    cfg = service.config()
    now = float(service.clock())
    meta = record.meta
    operative = policy.operative_role(user)
    # 6A-B4 (R-B3-10): el encabezado nombra la institución ACTIVA del contexto (no la de pertenencia del usuario);
    # sin institución activa no se muestra ningún nombre institucional (no hay universidad por defecto).
    institution_name = str((resolution.institution or {}).get("nombre") or "")
    return {
        "usuario": {
            "id": user.get("id"),
            "nombre": user.get("nombre"),
            "email": user.get("email"),
            "rol": user.get("rol"),
            "rol_original": user.get("rol_original"),
            "modo_solo_lectura_comercial": bool(user.get("modo_solo_lectura_comercial")),
            "es_superadmin": effective_role == policy.ROLE_SUPERADMIN,
        },
        "acceso": actor.access_mode,
        "pertenencia": {
            "institucion": None if user.get("institucion_id") is None else
            {"id": user.get("institucion_id"), "nombre": user.get("institucion_nombre")},
            "departamento": None if user.get("departamento_id") is None else
            {"id": user.get("departamento_id"), "nombre": user.get("departamento_nombre")},
        },
        "contexto": {
            "institucion_encabezado": institution_name,
            "institucion": _named(resolution.institution),
            "departamento": _named(resolution.department),
            "vista": ("departamento" if resolution.department is not None
                      else "consolidado" if resolution.institution is not None and resolution.reason is None
                      else "sin_ambito"),
            "problema": resolution.reason,
            "seleccionable": operative in (policy.ROLE_SUPERADMIN, policy.ROLE_COORDINADOR),
        },
        "modulos": modules,
        "sesion": {
            "inactividad_max_segundos": int(cfg.idle_seconds),
            "expira_por_inactividad_en": max(0, int(cfg.idle_seconds - (now - meta["last_activity_mono"]))),
            "expira_absoluta_en": max(0, int(cfg.absolute_seconds - (now - meta["issued_mono"]))),
        },
    }


def _ok(content: dict) -> JSONResponse:
    return JSONResponse(content=content, headers={"Cache-Control": "no-store"})


@router.post("/login")
def login(body: LoginBody, request: Request):
    if (denied := _require_csrf(request)) is not None:
        return denied
    service = _service(request)
    # Un login siempre descarta la sesion previa de este navegador (sin fijacion de sesion).
    service.logout(request.cookies.get(COOKIE_NAME))
    try:
        result = service.login(body.email, body.password, client_ip(request))
    except AuthUnavailable:
        return _error(503, "UNAVAILABLE", core.GENERIC_LOGIN_MESSAGE, clear_cookie=True)
    if result.user is None:
        return _error(result.status, "LOGIN_REJECTED", result.message, clear_cookie=True)
    token = service.start_session(result)
    record = service.store.get(token)
    try:
        payload = session_payload(service, record)
    except Exception:
        service.logout(token)
        return _error(503, "UNAVAILABLE", core.GENERIC_LOGIN_MESSAGE, clear_cookie=True)
    response = _ok(payload)
    _set_cookie(response, token, service.config())
    return response


@router.get("/me")
def me(request: Request, auth: Authenticated = Depends(authenticated)):
    if auth.failure is not None:
        return auth.failure
    try:
        return _ok(session_payload(_service(request), auth.record))
    except Exception:
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


@router.post("/logout")
def logout(request: Request):
    if (denied := _require_csrf(request)) is not None:
        return denied
    _service(request).logout(request.cookies.get(COOKIE_NAME))
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    _clear_cookie(response)
    return response


@router.get("/context/options")
def context_options(request: Request, auth: Authenticated = Depends(authenticated)):
    if auth.failure is not None:
        return auth.failure
    service = _service(request)
    try:
        service.apply_default_context(auth.record)
        return _ok(service.context_options(auth.record))
    except Exception:
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


@router.put("/context")
def set_context(body: ContextBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure
    service = _service(request)
    try:
        service.apply_default_context(auth.record)
        service.set_context(auth.record, body.institucion_id, body.departamento_id, body.consolidado)
        return _ok(session_payload(service, auth.record))
    except ContextError as exc:
        return _error(403, "CONTEXT_NOT_ALLOWED", str(exc))
    except Exception:
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
