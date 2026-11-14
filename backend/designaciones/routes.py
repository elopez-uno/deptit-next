"""Endpoints de Designaciones.  La sesion se revalida en cada request (``authenticated``); todo POST exige la cabecera
del proxy Next.js (tambien las consultas que viajan por POST porque el proxy no reenvia query strings).  Ninguna
respuesta incluye SQL, trazas ni secretos."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated

from .service import DesignacionesError, DesignacionesService

log = logging.getLogger("deptit_next.designaciones")

router = APIRouter(prefix="/designaciones", tags=["designaciones"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class Body(BaseModel):
    model_config = {"extra": "allow"}


class PeriodoBody(BaseModel):
    periodo_id: Any = None


class CargaBody(BaseModel):
    texto: Any = None
    confirmar_duplicados: Any = False


def _service(request: Request) -> DesignacionesService:
    return request.app.state.designaciones


def _handle(fn):
    try:
        return _ok(fn())
    except DesignacionesError as exc:
        if exc.tone == "error":
            return _error(exc.status, exc.code, exc.message)
        return JSONResponse(status_code=exc.status, headers={"Cache-Control": "no-store"},
                            content={"error": {"code": exc.code, "message": exc.message, "tone": exc.tone}})
    except Exception as exc:
        log.error("designaciones: error no controlado: %s", type(exc).__name__)
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


@router.get("/modelo-excel")
def modelo_excel(request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth, write=False)) is not None:
        return stop
    try:
        content = _service(request).modelo_excel(auth.record)
    except DesignacionesError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("designaciones: modelo Excel: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    return Response(content, media_type=XLSX, headers={
        "content-disposition": 'attachment; filename="modelo_carga_rapida_designaciones.xlsx"',
        "cache-control": "no-store"})


@router.post("/periodo")
def periodo(body: PeriodoBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).periodo(auth.record, body.periodo_id))


@router.post("/periodo/excel")
def periodo_excel(body: PeriodoBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    try:
        content, nombre = _service(request).periodo_excel(auth.record, body.periodo_id)
    except DesignacionesError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("designaciones: Excel de la tabla: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    return Response(content, media_type=XLSX, headers={
        "content-disposition": f'attachment; filename="{nombre}"', "cache-control": "no-store"})


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
    endpoint.__name__ = f"designaciones_{method}_{'_'.join(str(a) for a in args)}"
    router.add_api_route(f"/{name}", endpoint, methods=["POST"])


_post("duplicado", "duplicado")
_post("alta", "alta")
_post("modificar", "modificar")
_post("corregir", "corregir")
_post("eliminar", "eliminar")
_post("eliminar-masivo", "eliminar_masivo")
_post("fechas", "fechas")
_post("fechas-historicas", "fechas_historicas")
_post("actos/vincular", "vincular", False)
_post("actos/desvincular", "vincular", True)


@router.post("/carga-rapida/previsualizar")
def carga_preview(body: CargaBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).carga_preview(auth.record, body.texto))


@router.post("/carga-rapida")
def carga_ejecutar(body: CargaBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).carga_ejecutar(auth.record, body.texto, body.confirmar_duplicados))
