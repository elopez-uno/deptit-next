"""Endpoints de la capa de composicion (Etapa 4).  Sesion revalidada en cada request (``authenticated``).

- ``GET /contexto/periodo`` (E4-01, D-AN9): aviso global de contexto historico.  Sin parametros: el ambito sale de la
  sesion.  Solo lectura.
- ``POST /docentes/plantel`` (E4-02): pestaña Plantel de Docentes.  Consulta con parametro (``periodo_id``) por POST con
  la cabecera del proxy, como las demas consultas de Docentes (el proxy no reenvia query strings).  Solo lectura.
- ``POST /docentes/equipos`` (E4-03): pestaña Equipos docentes; mismo contrato que Plantel.  Solo lectura.
- ``POST /docentes/resumen`` (E4-05): pestaña Resumen docente (lectura) para ``{cuil, periodo_id}``; mismo contrato
  que Plantel.
- ``POST /docentes/resumen/estado-consulta`` (E4-06): writer del estado de consulta (owner Designaciones; B10 + B12H)
  y ``POST /docentes/resumen/mensaje`` (E4-06): mensaje para el docente (solo lectura).
- ``POST /investigacion/costos`` y ``POST /extension/costos`` (E4-04): costos salariales de Proyectos vigentes.  Sin
  parametros (ambito de la sesion); POST con la cabecera del proxy, como las demas consultas de esos modulos.
- ``POST /designaciones/acto-nuevo/contexto`` (E4-07): opciones del formulario en linea "Cargar un nuevo acto ahora"
  (solo lectura).  ``POST /designaciones/acto-nuevo/alta`` y ``/modificar`` (E4-07): alta y modificacion / baja de
  Designaciones con el acto nuevo y su PDF opcional, en ``multipart/form-data`` (parte ``datos`` JSON + parte
  ``archivo``) con el mismo lector y tope de transporte que Resoluciones y respaldos (D-AK1: sin base64, sin disco).
- ``POST /docentes/designacion/contexto`` y ``/docentes/designacion/duplicado`` (E4-08): pantalla "Registrar docente"
  (lectura); ``POST /docentes/designacion`` (E4-08): registra la designacion desde Docentes por uno de los tres caminos
  certificados (owners Docentes y Designaciones; B10 + B12H por writer).
- ``POST /docentes/carga-integral/modelo`` (E4-09): Excel integral de docentes y designaciones (binario);
  ``POST /docentes/carga-integral/previsualizar`` y ``POST /docentes/carga-integral`` (E4-09): revision y carga del
  Excel en ``multipart/form-data`` (parte ``datos`` JSON + parte ``archivo``), mismo lector y tope de transporte que
  Resoluciones y respaldos (sin base64, sin disco).
- ``POST /periodos/crear/contexto`` y ``/periodos/crear`` (E4-10), ``/periodos/revertir/diagnostico`` y
  ``/periodos/revertir`` (E4-11), ``/periodos/eliminar/diagnostico`` y ``/periodos/eliminar`` (E4-12),
  ``/periodos/reparar-finalizaciones/diagnostico`` y ``/periodos/reparar-finalizaciones`` (E4-12 / P-12b): operaciones de
  Periodos en UNA transaccion cada una (``ciclo_periodos``); las respuestas de escritura llevan ``periodo_cambiado``
  (P-01b: el shell recalcula el contexto historico de inmediato).
Ninguna respuesta incluye SQL, trazas ni rutas.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel

from auth import core
from auth.routes import Authenticated, _error, _ok, _require_csrf, authenticated
from designaciones.routes import _handle as _designaciones_handle
from docentes.service import DocentesError
from periodos.service import PeriodosError
from fastapi.concurrency import run_in_threadpool
from resoluciones_respaldos.routes import _multipart, _Rechazo

from .acto_contextual import ActoContextualService
from .carga_integral import CargaIntegralService
from .ciclo_periodos.service import CicloPeriodosService
from .registro_designacion import RegistroDesignacionService

from .contexto_periodo import ContextoError, ContextoPeriodoService
from .costos_proyectos import CostosError, CostosProyectosService
from .docentes_periodo import DocentesPeriodoService
from .resumen_docente import ResumenDocenteService

log = logging.getLogger("deptit_next.integraciones")

contexto_router = APIRouter(prefix="/contexto", tags=["integraciones"])
docentes_router = APIRouter(prefix="/docentes", tags=["integraciones"])
investigacion_router = APIRouter(prefix="/investigacion", tags=["integraciones"])
extension_router = APIRouter(prefix="/extension", tags=["integraciones"])
designaciones_router = APIRouter(prefix="/designaciones", tags=["integraciones"])
periodos_router = APIRouter(prefix="/periodos", tags=["integraciones"])


class PlantelBody(BaseModel):
    periodo_id: Any = None


class ResumenBody(BaseModel):
    cuil: Any = None
    periodo_id: Any = None


class LibreBody(BaseModel):
    model_config = {"extra": "allow"}


class EstadoConsultaBody(BaseModel):
    cuil: Any = None
    periodo_id: Any = None
    estado: Any = None


def _contexto(request: Request) -> ContextoPeriodoService:
    return request.app.state.contexto_periodo


@contexto_router.get("/periodo")
def contexto_periodo(request: Request, auth: Authenticated = Depends(authenticated)):
    if auth.failure is not None:
        return auth.failure
    try:
        return _ok(_contexto(request).aviso(auth.record))
    except ContextoError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("contexto_periodo: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


@docentes_router.post("/plantel")
def docentes_plantel(body: PlantelBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure
    service: DocentesPeriodoService = request.app.state.docentes_periodo
    try:
        return _ok(service.plantel(auth.record, body.periodo_id))
    except DocentesError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("docentes_periodo: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


@docentes_router.post("/equipos")
def docentes_equipos(body: PlantelBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure
    service: DocentesPeriodoService = request.app.state.docentes_periodo
    try:
        return _ok(service.equipos(auth.record, body.periodo_id))
    except DocentesError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("docentes_periodo: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)



@docentes_router.post("/resumen")
def docentes_resumen(body: ResumenBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure
    service: ResumenDocenteService = request.app.state.resumen_docente
    try:
        return _ok(service.resumen(auth.record, body.cuil, body.periodo_id))
    except DocentesError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("resumen_docente: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)



def _resumen_op(request: Request, auth: Authenticated, fn):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure
    service: ResumenDocenteService = request.app.state.resumen_docente
    try:
        return _ok(fn(service))
    except DocentesError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("resumen_docente: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


@docentes_router.post("/resumen/estado-consulta")
def docentes_resumen_estado(body: EstadoConsultaBody, request: Request, auth: Authenticated = Depends(authenticated)):
    return _resumen_op(request, auth, lambda s: s.guardar_estado(
        auth.record, {"cuil": body.cuil, "periodo_id": body.periodo_id, "estado": body.estado}))


@docentes_router.post("/resumen/mensaje")
def docentes_resumen_mensaje(body: ResumenBody, request: Request, auth: Authenticated = Depends(authenticated)):
    return _resumen_op(request, auth, lambda s: s.mensaje(auth.record, body.cuil, body.periodo_id))


# ------------------------------------------------------------------ E4-08: registrar designacion desde Docentes
def _registro_op(request: Request, auth: Authenticated, fn):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure
    service: RegistroDesignacionService = request.app.state.registro_designacion
    try:
        return _ok(fn(service))
    except DocentesError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("registro_designacion: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)


@docentes_router.post("/designacion/contexto")
def docentes_designacion_contexto(request: Request, auth: Authenticated = Depends(authenticated)):
    return _registro_op(request, auth, lambda s: s.contexto(auth.record))


@docentes_router.post("/designacion/duplicado")
def docentes_designacion_duplicado(body: LibreBody, request: Request, auth: Authenticated = Depends(authenticated)):
    return _registro_op(request, auth, lambda s: s.duplicado(auth.record, body.model_dump()))


@docentes_router.post("/designacion")
def docentes_designacion(body: LibreBody, request: Request, auth: Authenticated = Depends(authenticated)):
    return _registro_op(request, auth, lambda s: s.registrar(auth.record, body.model_dump()))


@docentes_router.post("/designacion/acto-nuevo")
async def docentes_designacion_acto_nuevo(request: Request, auth: Authenticated = Depends(authenticated)):
    """6A-B3: registrar designacion con "Cargar un nuevo acto ahora" (multipart, mismo lector que E4-07)."""
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure
    try:
        datos, archivo = await _multipart(request)
    except _Rechazo as exc:
        return _error(exc.status, exc.code, exc.message)
    return await run_in_threadpool(lambda: _registro_op(
        request, auth, lambda s: s.registrar(auth.record, datos, archivo, acto_nuevo=True)))


# ------------------------------------------------------------------ E4-09: carga rapida integral
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@docentes_router.post("/carga-integral/modelo")
def docentes_carga_integral_modelo(body: LibreBody, request: Request, auth: Authenticated = Depends(authenticated)):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure
    service: CargaIntegralService = request.app.state.carga_integral
    try:
        contenido, nombre = service.modelo(auth.record, body.model_dump())
    except DocentesError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:
        log.error("carga_integral: error no controlado: %s", type(exc).__name__)
        return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    return Response(content=contenido, media_type=XLSX, headers={
        "Content-Disposition": f'attachment; filename="{nombre}"', "Cache-Control": "no-store"})


def _carga_integral_endpoint(name: str, method: str):
    async def endpoint(request: Request, auth: Authenticated = Depends(authenticated)):
        if (denied := _require_csrf(request)) is not None:
            return denied
        if auth.failure is not None:
            return auth.failure
        try:
            datos, archivo = await _multipart(request)
        except _Rechazo as exc:
            return _error(exc.status, exc.code, exc.message)
        service: CargaIntegralService = request.app.state.carga_integral

        def run():
            try:
                return _ok(getattr(service, method)(auth.record, datos, archivo))
            except DocentesError as exc:
                return _error(exc.status, exc.code, exc.message)
            except Exception as exc:
                log.error("carga_integral: error no controlado: %s", type(exc).__name__)
                return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
        return await run_in_threadpool(run)
    endpoint.__name__ = f"docentes_carga_integral_{method}"
    docentes_router.add_api_route(f"/carga-integral{name}", endpoint, methods=["POST"])


_carga_integral_endpoint("/previsualizar", "previsualizar")
_carga_integral_endpoint("", "ejecutar")


# ------------------------------------------------------------------ E4-10..E4-12: ciclo de periodos
def _ciclo_endpoint(ruta: str, metodo: str):
    def endpoint(body: LibreBody, request: Request, auth: Authenticated = Depends(authenticated)):
        if (denied := _require_csrf(request)) is not None:
            return denied
        if auth.failure is not None:
            return auth.failure
        service: CicloPeriodosService = request.app.state.ciclo_periodos
        datos = body.model_dump()
        try:
            fn = getattr(service, metodo)
            return _ok(fn(auth.record) if metodo in ("revertir_diagnostico", "reparar_diagnostico")
                       else fn(auth.record, datos))
        except PeriodosError as exc:
            return _error(exc.status, exc.code, exc.message)
        except Exception as exc:
            log.error("ciclo_periodos: error no controlado: %s", type(exc).__name__)
            return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    endpoint.__name__ = f"periodos_{metodo}"
    periodos_router.add_api_route(ruta, endpoint, methods=["POST"])


for _ruta, _metodo in (("/crear/contexto", "crear_contexto"), ("/crear", "crear"),
                       ("/revertir/diagnostico", "revertir_diagnostico"), ("/revertir", "revertir"),
                       ("/eliminar/diagnostico", "eliminar_diagnostico"), ("/eliminar", "eliminar"),
                       ("/reparar-finalizaciones/diagnostico", "reparar_diagnostico"),
                       ("/reparar-finalizaciones", "reparar")):
    _ciclo_endpoint(_ruta, _metodo)


def _costos(tipo: str):
    def endpoint(request: Request, auth: Authenticated = Depends(authenticated)):
        if (denied := _require_csrf(request)) is not None:
            return denied
        if auth.failure is not None:
            return auth.failure
        service: CostosProyectosService = request.app.state.costos_proyectos
        try:
            return _ok(service.costos(auth.record, tipo))
        except CostosError as exc:
            return _error(exc.status, exc.code, exc.message)
        except Exception as exc:
            log.error("costos_proyectos: error no controlado: %s", type(exc).__name__)
            return _error(503, "UNAVAILABLE", core.UNAVAILABLE_MESSAGE)
    return endpoint


investigacion_router.add_api_route("/costos", _costos("investigacion"), methods=["POST"])
extension_router.add_api_route("/costos", _costos("extension"), methods=["POST"])


# ------------------------------------------------------------------ E4-07: "Cargar un nuevo acto ahora"
def _acto_contextual(request: Request) -> ActoContextualService:
    return request.app.state.acto_contextual


@designaciones_router.post("/acto-nuevo/contexto")
def designaciones_acto_nuevo_contexto(request: Request, auth: Authenticated = Depends(authenticated)):
    if (denied := _require_csrf(request)) is not None:
        return denied
    if auth.failure is not None:
        return auth.failure
    return _designaciones_handle(lambda: _acto_contextual(request).contexto(auth.record))


def _acto_nuevo_endpoint(name: str, method: str):
    async def endpoint(request: Request, auth: Authenticated = Depends(authenticated)):
        if (denied := _require_csrf(request)) is not None:
            return denied
        if auth.failure is not None:
            return auth.failure
        try:
            datos, archivo = await _multipart(request)
        except _Rechazo as exc:
            return _error(exc.status, exc.code, exc.message)
        return await run_in_threadpool(lambda: _designaciones_handle(
            lambda: getattr(_acto_contextual(request), method)(auth.record, datos, archivo)))
    endpoint.__name__ = f"designaciones_acto_nuevo_{method}"
    designaciones_router.add_api_route(f"/acto-nuevo/{name}", endpoint, methods=["POST"])


_acto_nuevo_endpoint("alta", "alta")
_acto_nuevo_endpoint("modificar", "modificar")
