"""Endpoints de Analisis — incluye Productividad.  La sesion se revalida en cada request (``authenticated``); todo POST
exige la cabecera del proxy Next.js (tambien las consultas y descargas, que viajan por POST porque el proxy no reenvia
query strings).  Las descargas son binarias con ``Content-Disposition`` seguro (``filename`` ASCII + ``filename*``
UTF-8), ``nosniff`` y ``no-store``; nunca se escriben en disco.  Ninguna respuesta incluye SQL, trazas ni rutas."""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated

from .service import AnalisisError, AnalisisService, Descarga

log = logging.getLogger("deptit_next.analisis")

router = APIRouter(prefix="/analisis", tags=["analisis"])
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_ASCII_UNSAFE = re.compile(r"[^A-Za-z0-9._\- ]")


class Body(BaseModel):
    model_config = {"extra": "allow"}


def content_disposition(nombre: str) -> str:
    visible = _CONTROL.sub("", str(nombre or "")).replace("/", "_").replace("\\", "_").strip()[:200] or "descarga"
    ascii_name = unicodedata.normalize("NFKD", visible).encode("ascii", "ignore").decode("ascii")
    ascii_name = _ASCII_UNSAFE.sub("_", ascii_name).strip(" .") or "descarga"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(visible, safe='')}"


def _service(request: Request) -> AnalisisService:
    return request.app.state.analisis


def _fail(exc: AnalisisError) -> JSONResponse:
    if exc.tone == "error":
        return _error(exc.status, exc.code, exc.message)
    return JSONResponse(status_code=exc.status, headers={"Cache-Control": "no-store"},
                        content={"error": {"code": exc.code, "message": exc.message, "tone": exc.tone}})


def _handle(fn):
    try:
        return _ok(fn())
    except AnalisisError as exc:
        return _fail(exc)
    except Exception as exc:
        log.error("analisis: error no controlado: %s", type(exc).__name__)
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
    endpoint.__name__ = f"analisis_{method}"
    router.add_api_route(f"/{name}", endpoint, methods=["POST"])


def _descarga(name: str, method: str):
    def endpoint(body: Body, request: Request, auth: Authenticated = Depends(authenticated)):
        if (stop := _guard(request, auth)) is not None:
            return stop
        try:
            d: Descarga = getattr(_service(request), method)(auth.record, body.model_dump())
        except AnalisisError as exc:
            return _fail(exc)
        except Exception as exc:
            log.error("analisis: descarga no controlada: %s", type(exc).__name__)
            return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
        media = d.media_type + ("; charset=utf-8" if d.media_type.startswith("text/") else "")
        return Response(d.contenido, media_type=media, headers={
            "Content-Disposition": content_disposition(d.nombre), "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store"})
    endpoint.__name__ = f"analisis_descarga_{method}"
    router.add_api_route(f"/descargas/{name}", endpoint, methods=["POST"])


_post("periodo", "periodo")
_post("comparacion", "comparacion")
_post("porcentaje", "guardar_porcentaje")
_descarga("word", "word")
_descarga("indicador", "csv_indicador")
_descarga("alertas", "csv_alertas")
_descarga("prompt", "prompt")
