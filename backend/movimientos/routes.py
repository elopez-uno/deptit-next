"""Endpoints de Movimientos.  La sesion se revalida en cada request (``authenticated``); todo POST exige la cabecera del
proxy Next.js (tambien las consultas que viajan por POST porque el proxy no reenvia query strings).  Ninguna respuesta
incluye SQL, trazas, secretos, rutas ni columnas legacy.  No hay Excel, CSV, PDF, ZIP ni exportacion (D-AL9), ni alta,
edicion o eliminacion masiva de movimientos (D-AL1)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated

from .service import MovimientosError, MovimientosService

log = logging.getLogger("deptit_next.movimientos")

router = APIRouter(prefix="/movimientos", tags=["movimientos"])


class Body(BaseModel):
    model_config = {"extra": "allow"}


def _service(request: Request) -> MovimientosService:
    return request.app.state.movimientos


def _handle(fn):
    try:
        return _ok(fn())
    except MovimientosError as exc:
        if exc.tone == "error":
            return _error(exc.status, exc.code, exc.message)
        return JSONResponse(status_code=exc.status, headers={"Cache-Control": "no-store"},
                            content={"error": {"code": exc.code, "message": exc.message, "tone": exc.tone}})
    except Exception as exc:
        log.error("movimientos: error no controlado: %s", type(exc).__name__)
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


@router.post("/actos")
def actos(request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).actos(auth.record))


def _post(name: str, method: str, *args):
    def endpoint(body: Body, request: Request, auth: Authenticated = Depends(authenticated)):
        if (stop := _guard(request, auth)) is not None:
            return stop
        return _handle(lambda: getattr(_service(request), method)(auth.record, body.model_dump(), *args))
    endpoint.__name__ = f"movimientos_{method}_{'_'.join(str(a) for a in args)}"
    router.add_api_route(f"/{name}", endpoint, methods=["POST"])


_post("listado", "listado")
_post("eliminar", "eliminar")
_post("actos/vincular", "vincular", False)
_post("actos/desvincular", "vincular", True)
