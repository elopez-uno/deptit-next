"""E4-05 — Docentes: pestaña "📊 Resumen docente" (lectura).

Certificado (B13-FIX02): ``tab5`` (entry l. 60845-61275).  E4-05 cubre las secciones de LECTURA (l. 60846-61197);
la seccion "Mensaje para consultar la designación" (estado de consulta: lectura + radio + writer
``guardar_estado_consulta_designacion``; mensaje ``generar_mensaje_consulta_designacion_docente``) es E4-06.

E4-06 agrega esa seccion: lectura del estado (Disposiciones, D12), el writer en su owner (Designaciones,
``DesignacionesService.guardar_estado_consulta``: B10 ``designaciones.write`` + B12H) y el mensaje
(``generar_mensaje_consulta_designacion_docente`` literal, ``resumen_motor/complemento_mensaje.py``), solo lectura.

Composicion (D-E4-01): el Resumen cruza Docentes, Designaciones, Comisiones, Materias, Periodos, Sueldos,
Investigacion, Extension, Actividades Especiales, Resoluciones/Disposiciones y Productividad.  Fuentes:
- motor de LECTURA certificado de Analisis (``analisis.motor.entorno``, texto literal ya validado; contiene 216 de las
  251 funciones del cierre de la pagina, sin redefiniciones entre l. 60845 y su corte l. 66604) + el complemento
  generado ``integraciones/resumen_motor/complemento.py`` (texto literal de las 18 funciones restantes, ver
  ``tools_generar_complemento_resumen.py``), en una transaccion READ ONLY con el ambito de la sesion;
- owners NEXT ya validados: ``SueldosService.sueldo_docente_resumen`` (seccion 💰; deudas H2 corregidas en la Etapa 5 / B1: Ad Honorem, estados, ficha) y
  ``ActividadesService.participaciones_docente_institucion`` (G5);
- ambito y permiso: contrato publico de Docentes (``DocentesService.scope``, ``docentes.read``).
Solo lectura: READ ONLY, sentencias mutantes rechazadas por el entorno del motor, sin writers, sin B12H, sin locks.
"""
from __future__ import annotations

import functools
import logging
from contextlib import AbstractContextManager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional

from psycopg import Connection

from actividades_especiales.service import ActividadesError, ActividadesService
from actividades_especiales.service import Scope as ActividadesScope
from analisis import pagina as P
from analisis.motor import entorno
from auth import policy
from auth.service import AuthService, SessionRecord
from designaciones.service import DesignacionesError, DesignacionesService
from disposiciones.lecturas import Lecturas as DisposicionesLecturas
from disposiciones.repository import DisposicionesRepository
from docentes.service import ACTION_READ, DocentesError, DocentesService
from materias.rules import formatear_nombre_escuela
from periodos.service import MSG_DB_READ, denial_message
from sueldos.service import Scope as SueldosScope
from sueldos.service import SueldosError, SueldosService

from . import resumen_pagina as RP
from .resumen_motor import metadata as complemento_meta
from .resumen_motor import metadata_mensaje as complemento_mensaje_meta

log = logging.getLogger("deptit_next.integraciones")

MSG_DOCENTE_INVALIDO = "El docente seleccionado no figura en el departamento."
MSG_PERIODO_INVALIDO = "El período seleccionado no existe en el departamento."
ETIQUETA_ESTIMACION = "ESTIMACIÓN"
ADVERTENCIA_ESTIMACION = ("El sueldo es una estimación: usa la lógica salarial certificada y puede no contemplar todos "
                          "los conceptos.")


@functools.lru_cache(maxsize=2)
def _codigo_complemento(archivo: str = "complemento.py"):
    ruta = Path(__file__).resolve().parent / "resumen_motor" / archivo
    return compile(ruta.read_text(encoding="utf-8"), str(ruta), "exec")


class ResumenDocenteService:
    def __init__(self, pool, auth: AuthService, docentes: DocentesService, sueldos: SueldosService,
                 actividades: ActividadesService, *, designaciones: Optional[DesignacionesService] = None,
                 today: Callable[[], date] = date.today,
                 now: Callable[[], datetime] = datetime.now,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None):
        self.auth = auth
        self.docentes = docentes
        self.sueldos = sueldos
        self.actividades = actividades
        self.designaciones = designaciones
        self.today = today
        self.now = now
        self._transaction = transaction or (lambda: pool.connection(timeout=5))

    # ------------------------------------------------------------------ motor (lectura certificada)
    def _motor(self, record: SessionRecord, scope, fn: Callable[[dict], Any], mensaje: bool = False) -> Any:
        if mensaje:  # ``current_user()`` del mensaje = la sesion (campos seguros B12G) y su institucion elegida
            usuario = {k: v for k, v in record.user.items() if k not in ("salt", "password_hash")}
        else:
            usuario = {"email": record.user.get("email"), "rol": record.user.get("rol"),
                       "departamento_nombre": record.user.get("departamento_nombre") or ""}
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                ns = entorno.construir(conn, scope.institution_id, scope.department_id, usuario=usuario,
                                       hoy=self.today, ahora=self.now)
                metas = [("complemento.py", complemento_meta)]
                if mensaje:
                    metas.append(("complemento_mensaje.py", complemento_mensaje_meta))
                    sup = record.scope.get(policy.SUPERADMIN_INSTITUTION_KEY)
                    if usuario.get("rol") == "superadmin" and sup:
                        ns["_motor_st"].session_state["superadmin_institucion_id"] = sup
                for archivo, meta in metas:
                    exec(_codigo_complemento(archivo), ns)
                    for nombre in meta.WRITERS_NEGOCIO:
                        ns[nombre] = entorno._bloqueado(nombre)
                    for nombre, categoria in meta.TAREAS_SISTEMA.items():
                        ns[nombre] = (lambda *a, **k: None)
                # 6A-B3: el complemento es literal del certificado (copia ``analisis.motor.ref`` del formateador, que
                # antepone "Escuela de" a todo); la presentación usa la fuente común de unidades académicas.
                ns["formatear_nombre_escuela"] = formatear_nombre_escuela
                if mensaje:
                    # 6A-B3: el mensaje nombra la institución ACTIVA del contexto, no la de pertenencia del usuario
                    # (``current_user()``) ni el valor por defecto literal del certificado.
                    nombre_institucion = str(scope.institution.get("nombre") or "")
                    ns["institucion_actual_nombre"] = lambda: nombre_institucion
                return fn(ns)
        except DocentesError:
            raise
        except Exception as exc:
            log.error("resumen_docente: lectura fallida: %s", type(exc).__name__)
            raise DocentesError(503, "DB_READ", MSG_DB_READ) from None

    def _reader(self, record: SessionRecord):
        scope = self.docentes.scope(record)
        decision = policy.decide(policy.actor_from_session(record.user, record.scope), ACTION_READ)
        if not decision.allowed:
            raise DocentesError(403, "DENIED", denial_message(decision, ACTION_READ))
        return scope

    @staticmethod
    def _entrada(cuil: Any, periodo_id: Any) -> str:
        if not isinstance(cuil, str) or not cuil.strip():
            raise DocentesError(422, "VALIDATION", MSG_DOCENTE_INVALIDO)
        if periodo_id is not None and (isinstance(periodo_id, bool) or not isinstance(periodo_id, int)):
            raise DocentesError(422, "VALIDATION", MSG_PERIODO_INVALIDO)
        return cuil.strip()

    @staticmethod
    def _seleccion(cuil: str, periodo_id: Any) -> Callable[[dict], dict]:
        """Docente de la base maestra del departamento y periodo del selector "Período a analizar" (l. 60852-60897)."""
        def seleccion(ns: dict) -> dict:
            df_doc = ns["get_docentes"]()
            if df_doc.empty:
                return {"sin_docentes": RP.MSG_SIN_DOCENTES}
            per = P.periodos(ns)
            if per["vacio"]:
                return {"sin_periodos": RP.MSG_SIN_PERIODOS}
            if cuil not in set(df_doc["cuil"].fillna("").astype(str)):
                raise DocentesError(404, "NOT_FOUND", MSG_DOCENTE_INVALIDO)
            ids = per["ids"]
            if periodo_id is None:
                nombre = per["default"]
            else:
                nombre = next((n for n, i in ids.items() if i == periodo_id), None)
                if nombre is None:
                    raise DocentesError(404, "NOT_FOUND", MSG_PERIODO_INVALIDO)
            pid = ids[nombre]
            return {"periodos": [{"id": i, "nombre": n} for n, i in ids.items()],
                    "seleccionado": {"id": pid, "nombre": nombre},
                    "fila_periodo": {k: P.jsonable(v) for k, v in P.fila_periodo(per["df"], pid).items()}}
        return seleccion

    def _estado_consulta(self, scope, cuil: str, periodo_id: int) -> str:
        """``get_estado_consulta_designacion`` (l. 23842) = lectura de Disposiciones (D12), en su transaccion."""
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                L = DisposicionesLecturas(DisposicionesRepository(conn, scope.institution_id, scope.department_id),
                                          self.today())
                return str(L.estado_consulta(cuil, periodo_id).get("estado") or "")
        except Exception as exc:
            log.error("resumen_docente: lectura del estado de consulta fallida: %s", type(exc).__name__)
            raise DocentesError(503, "DB_READ", MSG_DB_READ) from None

    # ------------------------------------------------------------------ pestaña
    def resumen(self, record: SessionRecord, cuil: Any, periodo_id: Any = None) -> dict:
        scope = self._reader(record)
        cuil = self._entrada(cuil, periodo_id)
        cabecera = {"subtitulo": RP.SUBTITULO, "info": RP.INFO}
        sel = self._motor(record, scope, self._seleccion(cuil, periodo_id))
        if "sin_docentes" in sel or "sin_periodos" in sel:
            return {**cabecera, **sel}
        pid, nombre = sel["seleccionado"]["id"], sel["seleccionado"]["nombre"]
        # owners (cada uno en su transaccion READ ONLY)
        try:
            sueldo = self.sueldos.sueldo_docente_resumen(
                SueldosScope(scope.institution_id, scope.department_id, scope.institution, scope.department,
                             policy.normalize_role(record.user.get("rol"))), cuil, sel["fila_periodo"])
            actividades = self.actividades.participaciones_docente_institucion(
                ActividadesScope(scope.institution_id, scope.department_id, scope.institution, scope.department,
                                 policy.normalize_role(record.user.get("rol"))),
                cuil=cuil, periodo_id=pid, incluir_bajas=True)
        except (SueldosError, ActividadesError) as exc:
            raise DocentesError(exc.status, exc.code, exc.message) from None
        secciones = self._motor(record, scope, lambda ns: RP.resumen(ns, cuil, pid, nombre, sel["fila_periodo"],
                                                                    sueldo, actividades))
        if "error" in secciones:
            return {**cabecera, "periodos": sel["periodos"], "seleccionado": sel["seleccionado"],
                    "error": secciones["error"]}
        return {
            **cabecera,
            "periodos": sel["periodos"],
            "seleccionado": sel["seleccionado"],
            "secciones": secciones,
            "estimacion": {"etiqueta": ETIQUETA_ESTIMACION, "advertencia": ADVERTENCIA_ESTIMACION},
            "consulta": RP.consulta(self._estado_consulta(scope, cuil, pid), nombre),
        }

    # ------------------------------------------------------------------ E4-06: estado de consulta y mensaje
    def guardar_estado(self, record: SessionRecord, data: dict) -> dict:
        """"💾 Guardar estado de la consulta": coordina; el writer es de Designaciones (owner B10)."""
        self._reader(record)
        if self.designaciones is None:
            raise DocentesError(503, "UNAVAILABLE", MSG_DB_READ)
        datos = {k: data.get(k) for k in ("cuil", "periodo_id", "estado")}
        try:
            r = self.designaciones.guardar_estado_consulta(record, datos)
        except DesignacionesError as exc:
            raise DocentesError(exc.status, exc.code, exc.message) from None
        r["semaforo"] = RP.semaforo_consulta(r["estado"])
        return r

    def mensaje(self, record: SessionRecord, cuil: Any, periodo_id: Any) -> dict:
        """"✉️ Generar mensaje para el docente": ``generar_mensaje_consulta_designacion_docente`` (l. 24088) literal."""
        scope = self._reader(record)
        if periodo_id is None:
            raise DocentesError(422, "VALIDATION", MSG_PERIODO_INVALIDO)
        cuil = self._entrada(cuil, periodo_id)

        def read(ns: dict) -> dict:
            sel = self._seleccion(cuil, periodo_id)(ns)
            if "seleccionado" not in sel:
                raise DocentesError(409, "SIN_DATOS", sel.get("sin_docentes") or sel.get("sin_periodos"))
            asunto, cuerpo, advertencias = ns["generar_mensaje_consulta_designacion_docente"](cuil, periodo_id)
            return {"asunto": asunto, "cuerpo": cuerpo, "advertencias": list(advertencias)}
        return self._motor(record, scope, read, mensaje=True)


__all__ = ["ResumenDocenteService"]
