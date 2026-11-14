"""Endpoints de Consolidado institucional.  La sesion se revalida en cada request (``authenticated``); la institucion
sale siempre de la sesion: ningun endpoint acepta ``institucion_id`` ni departamentos (campos extra -> 422).
``GET /consolidado`` trae la lectura inicial; ``POST /consolidado/tabla`` una tabla del visor (clave de allowlist +
texto de busqueda).  Las descargas (CSV completo y Excel de la tabla mostrada) viajan por POST con la cabecera del
proxy Next.js y responden con ``Content-Disposition`` seguro, ``nosniff`` y ``no-store``; nunca se escriben en disco.
Ninguna respuesta incluye SQL, trazas ni rutas."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from analisis.routes import content_disposition
from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated

from .service import ConsolidadoError, ConsolidadoService, Descarga

MSG_SOLICITUD = "La solicitud no es válida."

log = logging.getLogger("deptit_next.consolidado")

router = APIRouter(prefix="/consolidado", tags=["consolidado"])


class TablaBody(BaseModel):
    """Campos tipados ``Any`` y extras admitidos SOLO para rechazarlos en el servicio con un 422 propio: el 422 por
    defecto de FastAPI devolveria el valor enviado (p. ej. SQL) dentro de la respuesta."""
    model_config = ConfigDict(extra="allow")
    tabla: Any = None
    buscar: Any = None


class CsvBody(TablaBody):
    pass


def _sin_extras(body: TablaBody, permitidos: tuple[str, ...]) -> None:
    extras = set(body.model_extra or {}) | ({"buscar"} if "buscar" not in permitidos and body.buscar is not None
                                            else set())
    if extras:  # institucion_id, departamento_ids, sql, ... nunca vienen del cliente
        raise ConsolidadoError(422, "INVALID", MSG_SOLICITUD)


def _service(request: Request) -> ConsolidadoService:
    return request.app.state.consolidado


def _fail(exc: ConsolidadoError) -> JSONResponse:
    if exc.tone == "error":
        return _error(exc.status, exc.code, exc.message)
    return JSONResponse(status_code=exc.status, headers={"Cache-Control": "no-store"},
                        content={"error": {"code": exc.code, "message": exc.message, "tone": exc.tone}})


def _run(fn):
    try:
        return _ok(fn())
    except ConsolidadoError as exc:
        return _fail(exc)
    except Exception as exc:
        log.error("consolidado: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


def _archivo(fn):
    try:
        d: Descarga = fn()
    except ConsolidadoError as exc:
        return _fail(exc)
    except Exception as exc:
        log.error("consolidado: descarga no controlada: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    return Response(d.contenido, media_type=d.media_type, headers={
        "Content-Disposition": content_disposition(d.nombre), "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store"})


@router.get("")
def overview(request: Request, auth: Authenticated = Depends(authenticated)):
    if auth.failure is not None:
        return auth.failure
    return _run(lambda: _service(request).overview(auth.record))


@router.post("/tabla")
def tabla(body: TablaBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure

    def leer():
        _sin_extras(body, ("tabla", "buscar"))
        return _service(request).tabla(auth.record, body.tabla, body.buscar)

    return _run(leer)


@router.post("/descargas/csv")
def csv(body: CsvBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure

    def bajar():
        _sin_extras(body, ("tabla",))
        return _service(request).csv(auth.record, body.tabla)

    return _archivo(bajar)


@router.post("/descargas/excel")
def excel(body: TablaBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure

    def bajar():
        _sin_extras(body, ("tabla", "buscar"))
        return _service(request).excel(auth.record, body.tabla, body.buscar)

    return _archivo(bajar)
