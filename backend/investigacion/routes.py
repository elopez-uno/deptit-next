"""Endpoints de Investigacion.  La sesion se revalida en cada request (``authenticated``); todo POST exige la cabecera
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

from .excel import NOMBRE_MODELO
from .service import InvestigacionError, InvestigacionService

log = logging.getLogger("deptit_next.investigacion")

router = APIRouter(prefix="/investigacion", tags=["investigacion"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class Body(BaseModel):
    model_config = {"extra": "allow"}


def _service(request: Request) -> InvestigacionService:
    return request.app.state.investigacion


def _handle(fn):
    try:
        return _ok(fn())
    except InvestigacionError as exc:
        if exc.tone == "error":
            return _error(exc.status, exc.code, exc.message)
        return JSONResponse(status_code=exc.status, headers={"Cache-Control": "no-store"},
                            content={"error": {"code": exc.code, "message": exc.message, "tone": exc.tone}})
    except Exception as exc:
        log.error("investigacion: error no controlado: %s", type(exc).__name__)
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
    except InvestigacionError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("investigacion: Excel: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    return Response(content, media_type=XLSX, headers={
        "content-disposition": f'attachment; filename="{NOMBRE_MODELO}"', "cache-control": "no-store"})


def _post_sin_body(name: str, method: str):
    def endpoint(request: Request, auth: Authenticated = Depends(authenticated)):
        if (stop := _guard(request, auth)) is not None:
            return stop
        return _handle(lambda: getattr(_service(request), method)(auth.record))
    endpoint.__name__ = f"investigacion_{method}"
    router.add_api_route(f"/{name}", endpoint, methods=["POST"])


def _post(name: str, method: str):
    def endpoint(body: Body, request: Request, auth: Authenticated = Depends(authenticated)):
        if (stop := _guard(request, auth)) is not None:
            return stop
        return _handle(lambda: getattr(_service(request), method)(auth.record, body.model_dump()))
    endpoint.__name__ = f"investigacion_{method}"
    router.add_api_route(f"/{name}", endpoint, methods=["POST"])


# lecturas por POST (el proxy no reenvia query strings)
_post_sin_body("alertas", "alertas")
_post("post-accion", "post_accion")
_post_sin_body("vigentes", "vigentes")
_post("vigentes/ficha", "ficha")
_post_sin_body("actos", "actos")
_post_sin_body("asignar/proyectos", "asignar_proyectos")
_post("asignar/detalle", "asignar_detalle")
_post("capacidad", "capacidad")
_post("asignaciones", "asignaciones")
_post_sin_body("historial", "historial")
_post("historial/asignaciones", "historial_asignaciones")
_post_sin_body("editar/proyectos", "editar_proyectos")
_post_sin_body("editar/asignaciones", "editar_asignaciones")
_post("editar/asignacion/opciones", "editar_asignacion_opciones")
_post_sin_body("bajas/suspender/proyectos", "suspender_proyectos")
_post_sin_body("bajas/archivar/proyectos", "archivar_proyectos")
_post("carga-rapida/previsualizar", "carga_preview")
# escrituras
_post("proyecto/guardar", "guardar_proyecto")
_post("actos/vincular", "vincular_acto")
_post("actos/desvincular", "desvincular_acto")
_post("asignar", "asignar")
_post("asignar/eliminar-error", "eliminar_asignacion_error")
_post("editar/proyecto", "editar_proyecto")
_post("editar/asignacion", "editar_asignacion")
_post("bajas/asignacion", "baja_asignacion")
_post("bajas/suspender", "suspender")
_post("bajas/archivar", "archivar")
_post("bajas/eliminar", "eliminar_proyecto")
_post("carga-rapida", "carga_ejecutar")
