"""Endpoints de Inicio.  La sesion se revalida en cada request (``authenticated``).  ``GET /inicio`` no recibe
parametros: institucion, departamento y periodo salen de la sesion y del periodo abierto (sin selector, como el
certificado).  La unica descarga (Excel de "Próximos vencimientos", D-AN6) viaja por POST con la cabecera del proxy
Next.js y responde con ``Content-Disposition`` seguro, ``nosniff`` y ``no-store``; nunca se escribe en disco.
Ninguna respuesta incluye SQL, trazas ni rutas."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response

from analisis.routes import content_disposition
from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated

from .service import InicioError, InicioService

log = logging.getLogger("deptit_next.inicio")

router = APIRouter(prefix="/inicio", tags=["inicio"])


def _service(request: Request) -> InicioService:
    return request.app.state.inicio


def _fail(exc: InicioError) -> JSONResponse:
    if exc.tone == "error":
        return _error(exc.status, exc.code, exc.message)
    return JSONResponse(status_code=exc.status, headers={"Cache-Control": "no-store"},
                        content={"error": {"code": exc.code, "message": exc.message, "tone": exc.tone}})


@router.get("")
def tablero(request: Request, auth: Authenticated = Depends(authenticated)):
    if auth.failure is not None:
        return auth.failure
    try:
        return _ok(_service(request).tablero(auth.record))
    except InicioError as exc:
        return _fail(exc)
    except Exception as exc:
        log.error("inicio: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


@router.post("/descargas/vencimientos")
def excel_vencimientos(request: Request, auth: Authenticated = Depends(authenticated)):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure
    try:
        d = _service(request).excel_vencimientos(auth.record)
    except InicioError as exc:
        return _fail(exc)
    except Exception as exc:
        log.error("inicio: descarga no controlada: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    return Response(d.contenido, media_type=d.media_type, headers={
        "Content-Disposition": content_disposition(d.nombre), "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store"})
