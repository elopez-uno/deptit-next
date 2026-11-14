"""Endpoints de Sueldos.  La sesion se revalida en cada request (``authenticated``); todo POST exige la cabecera del
proxy Next.js (tambien las consultas que viajan por POST porque el proxy no reenvia query strings).  Ninguna respuesta
incluye SQL, trazas ni secretos.  No hay endpoints de Excel, importacion, exportacion, eliminacion de escalas,
movimientos, Resumen docente ni costos de proyectos (estos dos ultimos son helpers internos para la Etapa 4)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated

from .service import SueldosError, SueldosService

log = logging.getLogger("deptit_next.sueldos")

router = APIRouter(prefix="/sueldos", tags=["sueldos"])


class Body(BaseModel):
    model_config = {"extra": "allow"}


def _service(request: Request) -> SueldosService:
    return request.app.state.sueldos


def _handle(fn):
    try:
        return _ok(fn())
    except SueldosError as exc:
        if exc.tone == "error":
            return _error(exc.status, exc.code, exc.message)
        return JSONResponse(status_code=exc.status, headers={"Cache-Control": "no-store"},
                            content={"error": {"code": exc.code, "message": exc.message, "tone": exc.tone}})
    except Exception as exc:
        log.error("sueldos: error no controlado: %s", type(exc).__name__)
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


def _post(name: str, method: str):
    def endpoint(body: Body, request: Request, auth: Authenticated = Depends(authenticated)):
        if (stop := _guard(request, auth)) is not None:
            return stop
        return _handle(lambda: getattr(_service(request), method)(auth.record, body.model_dump()))
    endpoint.__name__ = f"sueldos_{method}"
    router.add_api_route(f"/{name}", endpoint, methods=["POST"])


# lecturas por POST (el proxy no reenvia query strings)
_post("escalas", "escalas")
_post("tabla", "tabla")
_post("plantel", "plantel")
# unica escritura
_post("escalas/guardar", "guardar_escala")
