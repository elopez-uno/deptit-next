import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import settings as app_settings

from audit import AuditStore
from auth import core as auth_core
from auth.repository import AuthRepository
from analisis.routes import router as analisis_router
from analisis.service import AnalisisService
from auth.routes import router as auth_router
from auth.routes import Authenticated, authenticated
from auth.routes import _error as auth_error
from auth import policy
from auth.service import AuthService
from actividades_especiales.routes import router as actividades_especiales_router
from actividades_especiales.service import ActividadesService
from comisiones.routes import router as comisiones_router
from comisiones.service import ComisionesService
from db import DatabaseGuardError, create_pool, verify_identity
from designaciones.routes import router as designaciones_router
from disposiciones.routes import router as disposiciones_router
from disposiciones.service import DisposicionesService
from designaciones.service import DesignacionesService
from docentes.routes import router as docentes_router
from docentes.service import DocentesService
from extension.routes import router as extension_router
from extension.service import ExtensionService
from consolidado.routes import router as consolidado_router
from consolidado.service import ConsolidadoService
from saas.routes import router as saas_router
from saas.service import SaasService
from inicio.routes import router as inicio_router
from inicio.service import InicioService
from integraciones.acto_contextual import ActoContextualService
from integraciones.carga_integral import CargaIntegralService
from integraciones.ciclo_periodos.service import CicloPeriodosService
from integraciones.ciclo_periodos import backup_gate
from integraciones.registro_designacion import RegistroDesignacionService
from integraciones.contexto_periodo import ContextoPeriodoService
from integraciones.costos_proyectos import CostosProyectosService
from integraciones.resumen_docente import ResumenDocenteService
from integraciones.docentes_periodo import DocentesPeriodoService
from integraciones.routes import contexto_router, docentes_router as docentes_integracion_router
from integraciones.routes import designaciones_router as designaciones_integracion_router
from integraciones.routes import periodos_router as periodos_integracion_router
from integraciones.routes import extension_router as extension_integracion_router
from integraciones.routes import investigacion_router as investigacion_integracion_router
from investigacion.routes import router as investigacion_router
from investigacion.service import InvestigacionService
from materias.routes import router as materias_router
from materias.service import MateriasService
from movimientos.routes import router as movimientos_router
from movimientos.service import MovimientosService
from periodos.routes import router as periodos_router
from periodos.service import PeriodosService
from resoluciones_respaldos.routes import router as resoluciones_respaldos_router
from resoluciones_respaldos.service import ResolucionesService
from sueldos.routes import router as sueldos_router
from sueldos.service import SueldosService

SERVICE = "deptit-next-backend"

logger = logging.getLogger("deptit_next")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 6A-B1: configuracion centralizada y validada ANTES de abrir conexiones (settings.py); fail-closed.
    try:
        cfg = app_settings.get()
        aviso_tz = app_settings.apply_timezone(cfg)
    except app_settings.ConfigError as exc:
        logger.critical("CONFIGURACION INVALIDA: el backend se niega a arrancar: %s", exc)
        raise
    if aviso_tz:
        logger.warning("desarrollo: %s", aviso_tz)
    try:
        app.state.pool = create_pool()
    except DatabaseGuardError as exc:
        logger.critical("GUARDA FAIL-CLOSED: el backend se niega a arrancar: %s", exc)
        raise
    logger.info("Guarda OK (%s): conectado a %s como %s; el rol no puede ejecutar DDL",
                cfg.entorno, cfg.expected_database, cfg.expected_db_user)
    try:
        auth_core.load_config()
    except auth_core.ConfigError as exc:
        app.state.pool.close()
        logger.critical("Configuracion de sesion invalida: el backend se niega a arrancar: %s", exc)
        raise
    app.state.auth = AuthService(AuthRepository(app.state.pool))
    app.state.periodos = PeriodosService(app.state.pool, app.state.auth, AuditStore(app.state.pool))
    app.state.docentes = DocentesService(
        app.state.pool, app.state.auth, AuditStore(app.state.pool),
        # Puerto E4-02 (D-E4-01): plantel historico desde la capa de composicion (Docentes no importa Comisiones).
        plantel_cuiles=lambda *a: app.state.docentes_periodo.plantel_cuiles(*a))
    app.state.materias = MateriasService(app.state.pool, app.state.auth, AuditStore(app.state.pool))
    app.state.designaciones = DesignacionesService(app.state.pool, app.state.auth, AuditStore(app.state.pool))
    app.state.comisiones = ComisionesService(app.state.pool, app.state.auth, AuditStore(app.state.pool))
    app.state.investigacion = InvestigacionService(app.state.pool, app.state.auth, AuditStore(app.state.pool))
    app.state.extension = ExtensionService(app.state.pool, app.state.auth, AuditStore(app.state.pool))
    app.state.actividades_especiales = ActividadesService(app.state.pool, app.state.auth, AuditStore(app.state.pool))
    app.state.sueldos = SueldosService(app.state.pool, app.state.auth, AuditStore(app.state.pool))
    app.state.disposiciones = DisposicionesService(app.state.pool, app.state.auth, AuditStore(app.state.pool))
    app.state.resoluciones_respaldos = ResolucionesService(app.state.pool, app.state.auth, AuditStore(app.state.pool))
    app.state.movimientos = MovimientosService(app.state.pool, app.state.auth, AuditStore(app.state.pool))
    app.state.analisis = AnalisisService(app.state.pool, app.state.auth, AuditStore(app.state.pool))
    app.state.inicio = InicioService(app.state.pool, app.state.auth)
    app.state.consolidado = ConsolidadoService(app.state.pool, app.state.auth)
    app.state.saas = SaasService(app.state.pool, app.state.auth, AuditStore(app.state.pool))
    # Etapa 4 — capa de composicion (D-E4-01): solo consume contratos publicos de los modulos propietarios.
    app.state.contexto_periodo = ContextoPeriodoService(app.state.pool, app.state.auth)
    app.state.docentes_periodo = DocentesPeriodoService(app.state.pool, app.state.auth, app.state.docentes)
    app.state.costos_proyectos = CostosProyectosService(app.state.sueldos, app.state.investigacion,
                                                        app.state.extension)
    app.state.resumen_docente = ResumenDocenteService(app.state.pool, app.state.auth, app.state.docentes,
                                                      app.state.sueldos, app.state.actividades_especiales,
                                                      designaciones=app.state.designaciones)
    # E4-07: "Cargar un nuevo acto ahora" (puerto ActoNuevo de Designaciones con los writers de Resoluciones).
    app.state.acto_contextual = ActoContextualService(app.state.designaciones, app.state.resoluciones_respaldos)
    # E4-08: registrar designacion desde Docentes (contratos de Docentes y Designaciones).
    app.state.registro_designacion = RegistroDesignacionService(app.state.docentes, app.state.designaciones,
                                                                app.state.acto_contextual)
    # E4-09: carga rapida integral (lectura certificada literal + writers de Docentes y Designaciones).
    app.state.carga_integral = CargaIntegralService(app.state.pool, app.state.docentes, app.state.designaciones)
    # E4-10..E4-12: operaciones de Periodos en UNA transaccion; gate de backup B11 (D-E4-04): una configuracion
    # insegura (gate desactivado fuera de desarrollo) impide arrancar.  6A-B2: el gate recibe la URL de IDENTIDAD de la
    # base (sin credenciales); la conninfo libpq de la conexion no es una URL y B11 la rechazaria (DENY_DATABASE_URL).
    app.state.ciclo_periodos = CicloPeriodosService(app.state.pool, app.state.periodos, AuditStore(app.state.pool),
                                                    database_url=app_settings.get().db.identity_url)
    try:
        yield
    finally:
        app.state.pool.close()


# 6A-B1: la raiz de composicion registra los contratos de configuracion de ``integraciones`` (D-E4-01).
app_settings.registrar_validador(backup_gate.validar_arranque)

# Swagger / ReDoc / OpenAPI: solo en desarrollo explicito (6A-B1); en preproduccion/produccion no existen las rutas.
_API_DOCS = app_settings.api_docs_habilitada()
app = FastAPI(
    title="DEPTIT NEXT API",
    version="0.9.0",
    lifespan=lifespan,
    docs_url="/docs" if _API_DOCS else None,
    redoc_url="/redoc" if _API_DOCS else None,
    openapi_url="/openapi.json" if _API_DOCS else None,
)

INTERNAL_MESSAGE = "Ocurrió un error interno. Reintentá en unos instantes."
INVALID_MESSAGE = "La solicitud no es válida."


# 6A-B1: el navegador nunca recibe trazas, SQL, rutas ni detalles de PostgreSQL; el detalle queda en el log del servidor.
@app.exception_handler(Exception)
async def _error_no_controlado(request: Request, exc: Exception):
    logger.exception("error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, headers={"Cache-Control": "no-store"},
                        content={"error": {"code": "INTERNAL", "message": INTERNAL_MESSAGE}})


@app.exception_handler(RequestValidationError)
async def _solicitud_invalida(request: Request, exc: RequestValidationError):
    # Sin eco del valor recibido (Pydantic incluye ``input``); solo la ubicacion de los campos.
    campos = sorted({".".join(str(p) for p in e.get("loc", ())[1:]) for e in exc.errors()} - {""})
    return JSONResponse(status_code=422, headers={"Cache-Control": "no-store"},
                        content={"error": {"code": "INVALID_REQUEST", "message": INVALID_MESSAGE, "campos": campos}})


@app.exception_handler(StarletteHTTPException)
async def _http(request: Request, exc: StarletteHTTPException):
    mensajes = {404: "Ruta no disponible.", 405: "Método no permitido."}
    return JSONResponse(status_code=exc.status_code, headers={"Cache-Control": "no-store", **(exc.headers or {})},
                        content={"error": {"code": f"HTTP_{exc.status_code}",
                                           "message": mensajes.get(exc.status_code, INVALID_MESSAGE)}})
app.include_router(auth_router)
app.include_router(periodos_router)
app.include_router(docentes_router)
app.include_router(materias_router)
app.include_router(designaciones_router)
app.include_router(comisiones_router)
app.include_router(investigacion_router)
app.include_router(extension_router)
app.include_router(actividades_especiales_router)
app.include_router(sueldos_router)
app.include_router(disposiciones_router)
app.include_router(resoluciones_respaldos_router)
app.include_router(movimientos_router)
app.include_router(analisis_router)
app.include_router(inicio_router)
app.include_router(consolidado_router)
app.include_router(saas_router)
app.include_router(contexto_router)
app.include_router(docentes_integracion_router)
app.include_router(investigacion_integracion_router)
app.include_router(extension_integracion_router)
app.include_router(designaciones_integracion_router)
app.include_router(periodos_integracion_router)


@app.get("/health")
def health():
    """Respuesta publica minima para monitoreo (6A-B1): sin nombre de base, rol, rutas ni versiones.  La guarda de
    identidad se sigue ejecutando: una base o rol inesperado da 503."""
    try:
        with app.state.pool.connection(timeout=5) as conn:
            verify_identity(conn)
    except Exception as exc:
        logger.error("health: base de datos no disponible: %s", type(exc).__name__)
        return JSONResponse(status_code=503, headers={"Cache-Control": "no-store"},
                            content={"status": "error", "service": SERVICE})
    return JSONResponse(headers={"Cache-Control": "no-store"}, content={"status": "ok", "service": SERVICE})


@app.get("/system/info")
def system_info(auth: Authenticated = Depends(authenticated)):
    # Etapa 5 / Tanda A (A4): conteos globales (todos los tenants) -> solo con sesion superadmin revalidada.
    if auth.failure is not None:
        return auth.failure
    if policy.normalize_role(auth.record.user.get("rol")) != policy.ROLE_SUPERADMIN:
        return auth_error(403, "DENIED", "Solo el superadmin puede consultar la información del sistema.")
    with app.state.pool.connection(timeout=5) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            database, db_user = verify_identity(conn)
            usuarios, instituciones, departamentos = conn.execute(
                """
                SELECT (SELECT count(*) FROM public.app_usuarios),
                       (SELECT count(*) FROM public.instituciones),
                       (SELECT count(*) FROM public.departamentos)
                """
            ).fetchone()
    return {
        "database": database,
        "db_user": db_user,
        "usuarios": usuarios,
        "instituciones": instituciones,
        "departamentos": departamentos,
    }
