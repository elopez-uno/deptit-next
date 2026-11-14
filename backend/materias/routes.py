"""Endpoints de Materias.  La sesion se revalida en cada request; todo POST exige la cabecera del proxy Next.js (tambien
las consultas que viajan por POST porque el proxy no reenvia query strings).  El Excel de opciones viaja en base64
dentro del JSON (el proxy del modulo solo reenvia texto).  Ninguna respuesta incluye SQL, trazas ni secretos."""

from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import Response

from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated

from .service import MateriasError, MateriasService

log = logging.getLogger("deptit_next.materias")

router = APIRouter(prefix="/materias", tags=["materias"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_BODY_BYTES = 16 * 1024 * 1024  # base64 del Excel (10 MB) + margen


def _service(request: Request) -> MateriasService:
    return request.app.state.materias


def _handle(fn: Callable[[], dict]):
    try:
        return _ok(fn())
    except MateriasError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("materias: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


@router.get("")
def overview(request: Request, auth: Authenticated = Depends(authenticated)):
    if auth.failure is not None:
        return auth.failure
    return _handle(lambda: _service(request).overview(auth.record))


@router.get("/opciones/modelo-excel")
def modelo_excel(request: Request, auth: Authenticated = Depends(authenticated)):
    if auth.failure is not None:
        return auth.failure
    try:
        content = _service(request).modelo_excel(auth.record)
    except MateriasError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("materias: modelo Excel: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    return Response(content, media_type=XLSX, headers={
        "content-disposition": 'attachment; filename="modelo_carga_rapida_opciones_curriculares.xlsx"',
        "cache-control": "no-store"})


# POST: ruta -> metodo del servicio (consultas y escrituras; todas reciben el body JSON como dict).
POST_ROUTES = {
    "carreras/consulta": "carreras_consulta",
    "carreras/duplicado": "carrera_duplicada",
    "carreras/alta": "carrera_alta",
    "carreras/editar": "carrera_editar",
    "carreras/eliminar": "carrera_eliminar",
    "plan": "plan",
    "plan/guardar": "plan_guardar",
    "plan/quitar": "plan_quitar",
    "materias/existentes": "materias_existentes",
    "materias/duplicado": "materia_duplicada",
    "materias/alta": "materia_alta",
    "materias/consulta": "materias_consulta",
    "materias/detalle": "materia_detalle",
    "materias/editar": "materia_editar",
    "materias/eliminar": "materia_eliminar",
    "carga-rapida/previsualizar": "carga_preview",
    "carga-rapida": "carga_ejecutar",
    "totales": "totales",
    "totales/limpiar": "limpiar_fuera_plan",
    "unicas": "unicas",
    "opciones/consulta": "opciones_consulta",
    "opciones/alta": "opcion_alta",
    "opciones/editar": "opcion_editar",
    "opciones/eliminar": "opcion_eliminar",
    "opciones/habilitaciones": "habilitaciones",
    "opciones/habilitaciones/agregar": "agregar_habilitaciones",
    "opciones/habilitaciones/quitar": "quitar_habilitacion",
    "opciones/excel/previsualizar": "excel_preview",
    "opciones/excel/cargar": "excel_cargar",
}


def _make_post(method_name: str):
    def endpoint(request: Request, body: Any = Body(default=None), auth: Authenticated = Depends(authenticated)):
        if (denied := _require_csrf(request)) is not None:
            return denied
        if auth.failure is not None:
            return auth.failure
        size = int(request.headers.get("content-length") or 0)
        if size > MAX_BODY_BYTES:
            return _error(413, "TOO_LARGE", "La solicitud es demasiado grande.")
        data = body if isinstance(body, dict) else {}
        return _handle(lambda: getattr(_service(request), method_name)(auth.record, data))
    endpoint.__name__ = f"post_{method_name}"
    return endpoint


for _path, _method in POST_ROUTES.items():
    router.add_api_route(f"/{_path}", _make_post(_method), methods=["POST"])
