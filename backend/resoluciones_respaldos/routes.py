"""Endpoints de Resoluciones y respaldos.  La sesion se revalida en cada request (``authenticated``); todo POST exige la
cabecera del proxy Next.js (tambien las consultas que viajan por POST porque el proxy no reenvia query strings).

- D-AK1: el PDF llega por ``multipart/form-data`` (sin base64).  El cuerpo se lee con tope de transporte estricto
  (50 MiB de PDF + margen del multipart) ANTES de parsear; el servicio vuelve a validar los 50 MiB de contenido real.
- D-AK3 / D-AK10: la descarga es un binario ``application/pdf`` con ``Content-Disposition`` seguro, ``nosniff`` y
  ``no-store`` (patron minimo copiado aca; Disposiciones no se modifica).
Ninguna respuesta incluye SQL, trazas, secretos, rutas ni bytes dentro de JSON.  No hay ZIP, Excel ni import/export.
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Callable, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated

from . import rules as R
from .service import Archivo, ResolucionesError, ResolucionesService

log = logging.getLogger("deptit_next.resoluciones_respaldos")

router = APIRouter(prefix="/resoluciones-respaldos", tags=["resoluciones-respaldos"])

MAX_TRANSPORTE = R.MAX_PDF_BYTES + 1024 * 1024  # PDF de 50 MiB + encabezados y campos del multipart
MAX_CAMPO = 256 * 1024
MSG_DEMASIADO_GRANDE = "La solicitud es demasiado grande: el PDF no puede superar 50 MB."
MSG_MULTIPART = "La solicitud de carga del archivo no es válida."


class Body(BaseModel):
    model_config = {"extra": "allow"}


def _service(request: Request) -> ResolucionesService:
    return request.app.state.resoluciones_respaldos


def _fail(exc: ResolucionesError) -> JSONResponse:
    if exc.tone == "error":
        return _error(exc.status, exc.code, exc.message)
    return JSONResponse(status_code=exc.status, headers={"Cache-Control": "no-store"},
                        content={"error": {"code": exc.code, "message": exc.message, "tone": exc.tone}})


def _handle(fn: Callable[[], Any]):
    try:
        return _ok(fn())
    except ResolucionesError as exc:
        return _fail(exc)
    except Exception as exc:
        log.error("resoluciones_respaldos: error no controlado: %s", type(exc).__name__)
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
    endpoint.__name__ = f"resoluciones_{method}"
    router.add_api_route(f"/{name}", endpoint, methods=["POST"])


# lecturas por POST (el proxy no reenvia query strings)
_post("documento", "documento")
_post("docentes", "docentes")
_post("proyectos", "proyectos")
_post("designaciones", "designaciones")  # 6A-B3: designaciones concretas de los docentes elegidos
# escrituras JSON
_post("documento/designaciones", "vincular_designaciones")  # 6A-B3: vinculo acto <-> designaciones (ids reales)
_post("documento/docentes", "agregar_docentes")  # 6A-B3: agregar docentes a un acto ya cargado
_post("documento/proyectos", "vincular_proyectos")  # 6A-B3: proyectos de un acto de Investigacion / Extension
_post("documento/dependencia", "dependencia_documento")
_post("documento/eliminar", "eliminar")
_post("dependencias/agregar", "agregar_dependencia")
_post("dependencias/editar", "editar_dependencia")


# ------------------------------------------------------------------ descarga (D-AK3 / D-AK12)
@router.post("/documento/pdf")
def descargar(body: Body, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    try:
        contenido, nombre = _service(request).descargar(auth.record, body.model_dump())
    except ResolucionesError as exc:
        return _fail(exc)
    except Exception as exc:
        log.error("resoluciones_respaldos: descarga: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    return Response(contenido, media_type=R.PDF_MIME,
                    headers={"content-disposition": R.content_disposition(nombre), "cache-control": "no-store",
                             "x-content-type-options": "nosniff"})


# ------------------------------------------------------------------ multipart (D-AK1)
class _Parser(MultiPartParser):
    """El PDF queda en memoria: el spool no vuelca a un archivo temporal (sin filesystem para los PDF)."""
    spool_max_size = MAX_TRANSPORTE


class _Rechazo(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


async def _leer_cuerpo(request: Request) -> bytes:
    """Cuerpo completo con tope estricto (Content-Length declarado y bytes realmente recibidos)."""
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        raise _Rechazo(415, "UNSUPPORTED", MSG_MULTIPART)
    declarado = request.headers.get("content-length")
    if declarado is not None:
        try:
            if int(declarado) > MAX_TRANSPORTE:
                raise _Rechazo(413, "TOO_LARGE", MSG_DEMASIADO_GRANDE)
        except ValueError:
            raise _Rechazo(400, "INVALID", MSG_MULTIPART) from None
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > MAX_TRANSPORTE:
            raise _Rechazo(413, "TOO_LARGE", MSG_DEMASIADO_GRANDE)
    return bytes(buf)


async def _multipart(request: Request) -> tuple[dict, Optional[Archivo]]:
    cuerpo = await _leer_cuerpo(request)

    async def stream() -> AsyncGenerator[bytes, None]:
        yield cuerpo
        yield b""

    try:
        form = await _Parser(request.headers, stream(), max_files=1, max_fields=4,
                                     max_part_size=MAX_CAMPO).parse()
    except MultiPartException:
        raise _Rechazo(400, "INVALID", MSG_MULTIPART) from None
    try:
        crudo = form.get("datos")
        if crudo is not None and not isinstance(crudo, str):
            raise _Rechazo(400, "INVALID", MSG_MULTIPART)
        try:
            datos = json.loads(crudo) if crudo else {}
        except ValueError:
            raise _Rechazo(400, "INVALID", MSG_MULTIPART) from None
        if not isinstance(datos, dict):
            raise _Rechazo(400, "INVALID", MSG_MULTIPART)
        parte = form.get("archivo")
        archivo = None
        if parte is not None:
            if not isinstance(parte, UploadFile):
                raise _Rechazo(400, "INVALID", MSG_MULTIPART)
            contenido = await parte.read()
            # Nombre y MIME tal como los declaro el navegador (``archivo.name`` / ``archivo.type`` del certificado).
            # Una parte vacia equivale a "sin archivo" (el certificado lo trata como PDF pendiente).
            if contenido:
                archivo = Archivo(nombre=str(parte.filename or ""), mime=str(parte.content_type or ""),
                                  contenido=contenido)
            elif parte.filename:
                archivo = Archivo(nombre=str(parte.filename), mime=str(parte.content_type or ""), contenido=b"")
        return datos, archivo
    finally:
        await form.close()


def _multipart_endpoint(name: str, method: str):
    async def endpoint(request: Request, auth: Authenticated = Depends(authenticated)):
        if (stop := _guard(request, auth)) is not None:
            return stop
        try:
            datos, archivo = await _multipart(request)
        except _Rechazo as exc:
            return _error(exc.status, exc.code, exc.message)
        return await run_in_threadpool(
            lambda: _handle(lambda: getattr(_service(request), method)(auth.record, datos, archivo)))
    endpoint.__name__ = f"resoluciones_{method}"
    router.add_api_route(f"/{name}", endpoint, methods=["POST"])


_multipart_endpoint("actos/guardar", "guardar_acto")
_multipart_endpoint("documento/adjuntar-pdf", "adjuntar_pdf")
