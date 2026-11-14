"""Endpoints de Comisiones.  La sesion se revalida en cada request (``authenticated``); todo POST exige la cabecera
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

from .service import ComisionesError, ComisionesService

log = logging.getLogger("deptit_next.comisiones")

router = APIRouter(prefix="/comisiones", tags=["comisiones"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class Body(BaseModel):
    model_config = {"extra": "allow"}


class PeriodoBody(BaseModel):
    periodo_id: Any = None


def _service(request: Request) -> ComisionesService:
    return request.app.state.comisiones


def _handle(fn):
    try:
        return _ok(fn())
    except ComisionesError as exc:
        if exc.tone == "error":
            return _error(exc.status, exc.code, exc.message)
        return JSONResponse(status_code=exc.status, headers={"Cache-Control": "no-store"},
                            content={"error": {"code": exc.code, "message": exc.message, "tone": exc.tone}})
    except Exception as exc:
        log.error("comisiones: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


def _guard(request: Request, auth: Authenticated, write: bool = True) -> Optional[Any]:
    if write and (denied := _require_csrf(request)) is not None:
        return denied
    return auth.failure


def _xlsx(fn, nombre: Optional[str] = None):
    try:
        result = fn()
    except ComisionesError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("comisiones: Excel: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    content, filename = (result, nombre) if nombre else result
    return Response(content, media_type=XLSX, headers={
        "content-disposition": f'attachment; filename="{filename}"', "cache-control": "no-store"})


@router.get("")
def overview(request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth, write=False)) is not None:
        return stop
    return _handle(lambda: _service(request).overview(auth.record))


@router.get("/modelo-excel")
def modelo_excel(request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth, write=False)) is not None:
        return stop
    return _xlsx(lambda: _service(request).modelo_excel(auth.record), "modelo_integral_comisiones.xlsx")


@router.post("/periodo/excel")
def periodo_excel(body: PeriodoBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _xlsx(lambda: _service(request).periodo_excel(auth.record, body.periodo_id))


@router.post("/periodo")
def periodo(body: PeriodoBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).periodo(auth.record, body.periodo_id))


@router.post("/inscriptos")
def inscriptos(body: PeriodoBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).inscriptos(auth.record, body.periodo_id))


def _post_sin_body(name: str, method: str):
    def endpoint(request: Request, auth: Authenticated = Depends(authenticated)):
        if (stop := _guard(request, auth)) is not None:
            return stop
        return _handle(lambda: getattr(_service(request), method)(auth.record))
    endpoint.__name__ = f"comisiones_{method}"
    router.add_api_route(f"/{name}", endpoint, methods=["POST"])


def _post(name: str, method: str):
    def endpoint(body: Body, request: Request, auth: Authenticated = Depends(authenticated)):
        if (stop := _guard(request, auth)) is not None:
            return stop
        return _handle(lambda: getattr(_service(request), method)(auth.record, body.model_dump()))
    endpoint.__name__ = f"comisiones_{method}"
    router.add_api_route(f"/{name}", endpoint, methods=["POST"])


# lecturas por POST (el proxy no reenvia query strings)
_post_sin_body("alertas", "alertas")
_post_sin_body("sedes", "sedes")
_post("abrir/materias", "abrir_materias")
_post("abrir/materia", "abrir_materia")
_post("docentes", "docentes")
_post("docentes/roles", "docente_roles")
_post("lista", "comisiones_lista")
_post("detalle", "comision_detalle")
_post("asignacion/franjas", "asignacion_franjas")
_post("edicion/datos", "edicion_datos")
_post("carga-rapida/previsualizar", "carga_preview")
# escrituras
_post("abrir", "abrir")
_post("modificacion/alta", "alta_real")
_post("modificacion/baja", "baja_real")
_post("edicion/guardar-datos", "editar_datos")
_post("edicion/nombres", "editar_nombres_lote")
_post("edicion/horario/editar", "editar_horario")
_post("edicion/horario/agregar", "agregar_horario")
_post("edicion/horario/eliminar", "eliminar_horario")
_post("edicion/docente/asignar", "asignar_correccion")
_post("edicion/docente/franjas", "guardar_franjas")
_post("edicion/docente/quitar", "quitar_asignacion")
_post("edicion/eliminar", "eliminar_comision")
_post("inscriptos/guardar", "guardar_inscriptos")
_post("sedes/agregar", "agregar_sede")
_post("sedes/editar", "editar_sede")
_post("sedes/eliminar", "eliminar_sede")
_post("carga-rapida", "carga_ejecutar")
