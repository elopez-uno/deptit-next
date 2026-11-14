"""Endpoints de Periodos.  La sesion se revalida en cada request (``authenticated``); las escrituras exigen la
cabecera del proxy Next.js.  Ninguna respuesta incluye SQL, trazas ni secretos."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, StrictBool

from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated

from .service import PeriodosError, PeriodosService

log = logging.getLogger("deptit_next.periodos")

router = APIRouter(prefix="/periodos", tags=["periodos"])


class OpenPreviousBody(BaseModel):
    periodo_id: Any = None
    observaciones: str = ""  # sin limite de longitud, como el certificado (columna text)
    confirmar_cierre: StrictBool = False
    confirmar_excepcional: StrictBool = False


class ReturnCurrentBody(BaseModel):
    observaciones: str = ""  # sin limite de longitud, como el certificado (columna text)
    confirmar_cierre_anterior: StrictBool = False
    confirmar_retorno: StrictBool = False


def _service(request: Request) -> PeriodosService:
    return request.app.state.periodos


def _handle(fn):
    try:
        return _ok(fn())
    except PeriodosError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("periodos: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


@router.get("")
def overview(request: Request, auth: Authenticated = Depends(authenticated)):
    if auth.failure is not None:
        return auth.failure
    return _handle(lambda: _service(request).overview(auth.record))


@router.post("/apertura-excepcional")
def open_previous(body: OpenPreviousBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure
    return _handle(lambda: _service(request).open_previous(
        auth.record, body.periodo_id, body.observaciones, body.confirmar_cierre, body.confirmar_excepcional))


@router.post("/volver-actual")
def return_current(body: ReturnCurrentBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure
    return _handle(lambda: _service(request).return_current(
        auth.record, body.observaciones, body.confirmar_cierre_anterior, body.confirmar_retorno))
