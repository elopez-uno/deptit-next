"""Endpoints de Docentes.  La sesion se revalida en cada request (``authenticated``); todo POST exige la cabecera del
proxy Next.js (tambien las consultas que viajan por POST porque el proxy no reenvia query strings).  Ninguna respuesta
incluye SQL, trazas ni secretos."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel

from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated

from .service import DocentesError, DocentesService

log = logging.getLogger("deptit_next.docentes")

router = APIRouter(prefix="/docentes", tags=["docentes"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class CuilBody(BaseModel):
    cuil: Any = None


class AltaBody(BaseModel):
    apellido: Any = None
    nombres: Any = None
    cuil: Any = None
    legajo: Any = None
    titulo: Any = None
    titulo_posgrado: Any = None
    nivel_posgrado_salarial: Any = ""
    antiguedad_anios: Any = None
    email: Any = None
    telefono: Any = None
    ref_legajo_fisico: Any = None
    fecha_alta: Any = None
    observaciones: Any = None


class EditarBody(BaseModel):
    cuil_original: Any = None
    huella: Any = None
    apellido: Any = None
    nombres: Any = None
    cuil: Any = None
    legajo: Any = None
    titulo: Any = None
    titulo_posgrado: Any = None
    nivel_posgrado_salarial: Any = ""
    antiguedad_anios: Any = None
    email: Any = None
    telefono: Any = None
    ref_legajo_fisico: Any = None
    estado: Any = None
    tipo_docente: Any = None
    observaciones: Any = None


class EliminarBody(BaseModel):
    cuil: Any = None
    huella: Any = None
    confirmar: Any = False
    integral: Any = False


class PrestadoBody(BaseModel):
    flujo: Any = None
    cuil: Any = None
    departamento_origen: Any = None
    cuil_alta: Any = None


class FinalizarPrestamoBody(BaseModel):
    cuil: Any = None
    huella: Any = None
    fecha_fin: Any = None
    observaciones: Any = None
    confirmar: Any = False


class RepararCuilBody(BaseModel):
    cuil: Any = None
    huella: Any = None
    cuil_huerfano: Any = None
    confirmar: Any = False


class CargaBody(BaseModel):
    texto: Any = None
    confirmar_duplicados: Any = False


def _service(request: Request) -> DocentesService:
    return request.app.state.docentes


def _handle(fn):
    try:
        return _ok(fn())
    except DocentesError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("docentes: error no controlado: %s", type(exc).__name__)
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


@router.get("/prestables")
def prestables(request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth, write=False)) is not None:
        return stop
    return _handle(lambda: _service(request).prestables(auth.record))


@router.get("/modelo-excel")
def modelo_excel(request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth, write=False)) is not None:
        return stop
    try:
        content = _service(request).modelo_excel(auth.record)
    except DocentesError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("docentes: modelo Excel: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    return Response(content, media_type=XLSX, headers={
        "content-disposition": 'attachment; filename="modelo_carga_rapida_docentes.xlsx"',
        "cache-control": "no-store"})


@router.post("/ficha")
def ficha(body: CuilBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).ficha(auth.record, body.cuil))


@router.post("/verificar-cuil")
def verificar_cuil(body: CuilBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).verificar_cuil(auth.record, body.cuil))


@router.post("/alta")
def alta(body: AltaBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).alta(auth.record, body.model_dump()))


@router.post("/editar")
def editar(body: EditarBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).editar(auth.record, body.model_dump()))


@router.post("/eliminar")
def eliminar(body: EliminarBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).eliminar(auth.record, body.model_dump()))


@router.post("/prestado")
def prestado(body: PrestadoBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).prestado(auth.record, body.model_dump()))


@router.post("/finalizar-prestamo")
def finalizar_prestamo(body: FinalizarPrestamoBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).finalizar_prestamo(auth.record, body.model_dump()))


@router.post("/reparar-cuil")
def reparar_cuil(body: RepararCuilBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (stop := _guard(request, auth)) is not None:
        return stop
    return _handle(lambda: _service(request).reparar_cuil(auth.record, body.model_dump()))


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
