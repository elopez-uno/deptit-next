"""Endpoints de Actividades Especiales.  La sesion se revalida en cada request (``authenticated``); todo POST exige la
cabecera del proxy Next.js (tambien las consultas que viajan por POST porque el proxy no reenvia query strings).  Ninguna
respuesta incluye SQL, trazas ni secretos.  No hay endpoints de Excel, actos, costos, horas ni movimientos (no existen
en el certificado)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated

from .service import ActividadesError, ActividadesService

log = logging.getLogger("deptit_next.actividades_especiales")

router = APIRouter(prefix="/actividades-especiales", tags=["actividades_especiales"])


class Body(BaseModel):
    model_config = {"extra": "allow"}


def _service(request: Request) -> ActividadesService:
    return request.app.state.actividades_especiales


def _handle(fn):
    try:
        return _ok(fn())
    except ActividadesError as exc:
        if exc.tone == "error":
            return _error(exc.status, exc.code, exc.message)
        return JSONResponse(status_code=exc.status, headers={"Cache-Control": "no-store"},
                            content={"error": {"code": exc.code, "message": exc.message, "tone": exc.tone}})
    except Exception as exc:
        log.error("actividades_especiales: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


def _guard(request: Request, auth: Authenticated, write: bool = True) -> Optional[Any]:
    if write and (denied := _require_csrf(request)) is not None:
        return denied
    return auth.failure


@router.get("")
def overview(request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth, write=False)) is not None:
        return stop
    return _handle(lambda: _service(request).overview(auth.record))


def _post_sin_body(name: str, method: str):
    def endpoint(request: Request, auth: Authenticated = Depends(authenticated)):
        if (stop := _guard(request, auth)) is not None:
            return stop
        return _handle(lambda: getattr(_service(request), method)(auth.record))
    endpoint.__name__ = f"actividades_{method}"
    router.add_api_route(f"/{name}", endpoint, methods=["POST"])


def _post(name: str, method: str):
    def endpoint(body: Body, request: Request, auth: Authenticated = Depends(authenticated)):
        if (stop := _guard(request, auth)) is not None:
            return stop
        return _handle(lambda: getattr(_service(request), method)(auth.record, body.model_dump()))
    endpoint.__name__ = f"actividades_{method}"
    router.add_api_route(f"/{name}", endpoint, methods=["POST"])


# lecturas por POST (el proxy no reenvia query strings)
_post("periodo", "actividades_periodo")
_post("asignar/datos", "asignar_datos")
_post_sin_body("historial", "historial")
_post_sin_body("editar/actividades", "editar_datos")
_post("editar/participaciones", "participaciones_actividad")
# escrituras
_post("crear", "crear")
_post("asignar", "asignar")
_post("editar", "editar")
_post("editar/quitar-participacion", "quitar_participacion")
_post("editar/eliminar", "eliminar")
