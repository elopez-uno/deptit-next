"""Endpoints de Administración SaaS.  La sesión se revalida en cada request (``authenticated``); todo POST exige la
cabecera del proxy Next.js (CSRF).  Una acción = un endpoint explícito con su esquema (sin endpoint genérico de
actualización).  Ninguna respuesta incluye SQL, trazas, rutas ni secretos; nunca se devuelven ``salt`` ni
``password_hash``."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from analisis.routes import content_disposition
from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated
from inicio.service import XLSX

from .service import MSG_INVALIDO, SaasError, SaasService

log = logging.getLogger("deptit_next.saas")

router = APIRouter(prefix="/saas", tags=["saas"])


class Body(BaseModel):
    """Cuerpo libre a nivel HTTP: el esquema EXACTO de cada acción lo valida el servicio (422 sin eco del valor)."""
    model_config = {"extra": "allow"}


def _service(request: Request) -> SaasService:
    return request.app.state.saas


def _fail(exc: SaasError) -> JSONResponse:
    if exc.tone == "error":
        return _error(exc.status, exc.code, exc.message)
    return JSONResponse(status_code=exc.status, headers={"Cache-Control": "no-store"},
                        content={"error": {"code": exc.code, "message": exc.message, "tone": exc.tone}})


def _handle(fn):
    try:
        return _ok(fn())
    except SaasError as exc:
        return _fail(exc)
    except Exception as exc:
        log.error("saas: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


def _guard(request: Request, auth: Authenticated, write: bool = True) -> Optional[Any]:
    if write and (denied := _require_csrf(request)) is not None:
        return denied
    return auth.failure


def _datos(body: Body) -> dict:
    return body.model_dump()


@router.get("")
def overview(request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth, write=False)) is not None:
        return stop
    return _handle(lambda: _service(request).overview(auth.record))


@router.post("/descargas/excel")
def excel(body: Body, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    try:
        contenido, nombre = _service(request).excel(auth.record, _datos(body))
    except SaasError as exc:
        return _fail(exc)
    except Exception as exc:
        log.error("saas: Excel fallido: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    return Response(content=contenido, media_type=XLSX,
                    headers={"Content-Disposition": content_disposition(nombre), "Cache-Control": "no-store",
                             "X-Content-Type-Options": "nosniff"})


def _post(path: str, method: str):
    def endpoint(body: Body, request: Request, auth: Authenticated = Depends(authenticated)):
        if (stop := _guard(request, auth)) is not None:
            return stop
        return _handle(lambda: getattr(_service(request), method)(auth.record, _datos(body)))
    endpoint.__name__ = f"saas_{method}"
    router.add_api_route(path, endpoint, methods=["POST"])


# lectura por POST (el proxy no reenvía query strings)
_post("/planes", "planes")
# Instituciones
_post("/instituciones", "crear_institucion")
_post("/instituciones/cupo", "actualizar_cupo")
_post("/instituciones/comercial", "actualizar_comercial")
_post("/instituciones/bloquear", "bloquear")
_post("/instituciones/desbloquear", "desbloquear")
_post("/instituciones/eliminar", "eliminar_institucion")
# Departamentos
_post("/departamentos", "crear_departamento")
_post("/departamentos/editar", "editar_departamento")
_post("/departamentos/eliminar", "eliminar_departamento")
# Usuarios
_post("/usuarios", "crear_usuario")
_post("/usuarios/estado", "estado_usuario")
_post("/usuarios/editar", "editar_usuario")
_post("/usuarios/eliminar", "eliminar_usuario")

ACCIONES = ("planes", "instituciones", "instituciones/cupo", "instituciones/comercial", "instituciones/bloquear",
            "instituciones/desbloquear", "instituciones/eliminar", "departamentos", "departamentos/editar",
            "departamentos/eliminar", "usuarios", "usuarios/estado", "usuarios/editar", "usuarios/eliminar")
__all__ = ["router", "ACCIONES", "MSG_INVALIDO"]
