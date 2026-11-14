"""Endpoints de Disposiciones.  La sesion se revalida en cada request (``authenticated``); todo POST exige la cabecera
del proxy Next.js (tambien las consultas que viajan por POST porque el proxy no reenvia query strings).  Ninguna
respuesta incluye SQL, trazas, secretos ni rutas fisicas: el Word y los ZIP se sirven solo por estos endpoints (D11).
No hay endpoints de PDF, Excel, edicion o anulacion de disposiciones (no existen en el certificado)."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated

from . import storage as S
from .service import DisposicionesError, DisposicionesService

log = logging.getLogger("deptit_next.disposiciones")

router = APIRouter(prefix="/disposiciones", tags=["disposiciones"])
ZIP = "application/zip"


class Body(BaseModel):
    model_config = {"extra": "allow"}


def _service(request: Request) -> DisposicionesService:
    return request.app.state.disposiciones


def _fail(exc: DisposicionesError) -> JSONResponse:
    if exc.tone == "error":
        return _error(exc.status, exc.code, exc.message)
    return JSONResponse(status_code=exc.status, headers={"Cache-Control": "no-store"},
                        content={"error": {"code": exc.code, "message": exc.message, "tone": exc.tone}})


def _handle(fn):
    try:
        return _ok(fn())
    except DisposicionesError as exc:
        return _fail(exc)
    except Exception as exc:
        log.error("disposiciones: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


def _guard(request: Request, auth: Authenticated, write: bool = True) -> Optional[Any]:
    if write and (denied := _require_csrf(request)) is not None:
        return denied
    return auth.failure


def _attachment(nombre: str) -> str:
    ascii_name = nombre.encode("ascii", "ignore").decode("ascii") or "disposicion"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(nombre)}"


def _binary(fn: Callable[[], tuple[bytes, str, str]]):
    try:
        contenido, nombre, mime = fn()
    except DisposicionesError as exc:
        return _fail(exc)
    except Exception as exc:
        log.error("disposiciones: descarga: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    return Response(contenido, media_type=mime, headers={"content-disposition": _attachment(nombre),
                                                         "cache-control": "no-store",
                                                         "x-content-type-options": "nosniff"})


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
    endpoint.__name__ = f"disposiciones_{method}"
    router.add_api_route(f"/{name}", endpoint, methods=["POST"])


# lecturas por POST (el proxy no reenvia query strings)
_post("periodo", "periodo")
_post("docente", "docente")
_post("docente/vista-previa", "vista_previa")
_post("historial", "historial")
# escrituras
_post("configuracion/guardar", "guardar_configuracion")
_post("plantilla/reemplazar", "reemplazar_plantilla")
_post("numero-inicial/guardar", "guardar_numero_inicial")
_post("docente/guardar-datos", "guardar_datos")
_post("generar", "generar")
_post("generar-masiva", "generar_masiva")
_post("historial/eliminar", "eliminar")


@router.post("/descargar")
def descargar(body: Body, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop

    def run():
        payload = _service(request).descargar(auth.record, body.model_dump())
        return payload.data, payload.file_name, S.DOCX_MIME
    return _binary(run)


@router.post("/historial/zip")
def zip_historial(body: Body, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _binary(lambda: (*_service(request).zip_historial(auth.record, body.model_dump()), ZIP))


@router.post("/zip-lote")
def zip_lote(body: Body, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _binary(lambda: (*_service(request).zip_lote(auth.record, body.model_dump()), ZIP))
