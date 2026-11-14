"""Servicio de Inicio (B13-FIX02, pagina ``🏠 Inicio`` l. 59280-59794).

Decisiones D-AN1..D-AN9 (docs/inicio_analysis.md §39):
- D-AN1: el tablero es ``_inicio_datos_tablero_cache`` (v188 -> v165 -> v146) ejecutado por el motor de LECTURA de
  Analisis (``analisis.motor.entorno``, importado sin cambios), en UNA transaccion READ ONLY por request y con el ambito
  de la SESION; memoizacion request-scoped (sin la cache de 60 s, D-AN3).  ``pagina.py`` solo transcribe.
- D-AN2: sin permiso de negocio propio (el certificado no tiene guarda B10 de lectura): sesion valida + modulo Inicio
  visible + ambito verificado.  Coordinador sin departamento -> estado "institucional" sin calcular nada.  Cualquier
  otro rol sin departamento operativo -> 409 (fail-closed; el certificado caia al primer departamento).
- D-AN3: "🔄 Actualizar tablero" vuelve a pedir los datos (no escribe) y esta habilitado para todos los roles.
- D-AN4: titulo con el departamento OPERATIVO de la sesion.
- D-AN6: unica exportacion, el Excel de "Próximos vencimientos" (las <= 8 filas visibles, hoja "Datos", mismo
  conversor que ``_convertir_tabla_a_excel_bytes`` l. 316 y mismo nombre que ``_nombre_archivo_excel_tabla`` l. 355).
- Cero writers, cero B12H de negocio, cero locks.  Ningun mensaje expone excepciones, SQL, rutas ni trazas.
"""
from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import Any, Callable, Optional

import pandas as pd
from psycopg import Connection

from analisis.motor import entorno
from auth import policy
from auth.service import AuthService, SessionRecord
from periodos.service import MSG_DB_READ, MSG_INSTITUTIONAL, scope_message

from . import pagina as P

log = logging.getLogger("deptit_next.inicio")

MODULO = "inicio"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MSG_TABLERO = "No se pudo construir el tablero operativo del período. Reintentá con «🔄 Actualizar tablero»."
MSG_SIN_VENCIMIENTOS = "No hay designaciones activas con vencimiento previsto dentro de los próximos 30 días."


class InicioError(Exception):
    def __init__(self, status: int, code: str, message: str, tone: str = "error"):
        super().__init__(message)
        self.status, self.code, self.message, self.tone = status, code, message, tone


@dataclass(frozen=True)
class Scope:
    institution: dict
    department: Optional[dict]


@dataclass(frozen=True)
class Descarga:
    contenido: bytes
    nombre: str
    media_type: str


def _named(row: Optional[dict]) -> Optional[dict]:
    return None if row is None else {"id": int(row["id"]), "nombre": row.get("nombre")}


def excel_bytes(df: pd.DataFrame) -> bytes:
    """``_convertir_tabla_a_excel_bytes`` (l. 316): hoja "Datos", sin indice; si falla, todo como texto."""
    out = BytesIO()
    try:
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Datos")
    except Exception:
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df.copy().astype(str).to_excel(writer, index=False, sheet_name="Datos")
    return out.getvalue()


class InicioService:
    def __init__(self, pool, auth: AuthService, *, today: Callable[[], date] = date.today,
                 now: Callable[[], datetime] = datetime.now,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None):
        self.auth = auth
        self.today = today
        self.now = now
        self._transaction = transaction or (lambda: pool.connection(timeout=5))

    # ------------------------------------------------------------------ contexto (B12B) y modulo visible (D-AN2)
    def scope(self, record: SessionRecord) -> Scope:
        self.auth.apply_default_context(record)
        user, session_scope = record.user, record.scope
        role = policy.normalize_role(user.get("rol"))
        visible = policy.visible_modules(role, session_scope.get(policy.DEPARTMENT_SCOPE_KEY))
        if not any(m[0] == MODULO for m in visible):
            raise InicioError(403, "DENIED", "Tu rol no tiene acceso a este módulo.")
        resolution = self.auth.resolve_scope(record)
        if resolution.reason is not None:
            raise InicioError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        if resolution.department is None and not (role == policy.ROLE_COORDINADOR
                                                   and session_scope.get(policy.DEPARTMENT_SCOPE_KEY) is None):
            raise InicioError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        return Scope(resolution.institution, resolution.department)

    def _motor(self, record: SessionRecord, scope: Scope, fn: Callable[[dict], Any]) -> Any:
        """Una ejecucion del motor certificado: transaccion READ ONLY + namespace del request (memo incluido)."""
        usuario = {"email": record.user.get("email"), "rol": record.user.get("rol"),
                   "departamento_nombre": record.user.get("departamento_nombre") or ""}
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                ns = entorno.construir(conn, int(scope.institution["id"]), int(scope.department["id"]),
                                       usuario=usuario, hoy=self.today, ahora=self.now)
                return fn(ns)
        except InicioError:
            raise
        except Exception as exc:
            log.error("inicio: lectura fallida: %s", type(exc).__name__)
            raise InicioError(503, "DB_READ", MSG_DB_READ) from None

    @staticmethod
    def _datos(ns: dict, periodo: dict) -> dict:
        pid = int(periodo["id"])
        hoy = ns["fecha_referencia_contexto_v182"](pid)
        return ns["_inicio_datos_tablero_cache"](pid, ns["_pg_current_inst_id"](), ns["_pg_current_dep_id"](),
                                                 str(hoy))

    # ------------------------------------------------------------------ lectura (un unico calculo del tablero)
    def tablero(self, record: SessionRecord) -> dict:
        scope = self.scope(record)
        out: dict = {"contexto": {"institucion": _named(scope.institution), "departamento": _named(scope.department)},
                     "titulo": P.titulo(scope.department)}
        if scope.department is None:  # coordinador en el ambito institucional (l. 59286)
            out.update({"estado": "institucional", "institucional": P.institucional()})
            return out

        def read(ns: dict) -> dict:
            periodo = ns["get_periodo_abierto"]()
            if not periodo:
                return {"estado": "sin_periodo", "sin_periodo": P.sin_periodo()}
            hoy = ns["fecha_referencia_contexto_v182"](int(periodo["id"]))
            cab = P.encabezado(ns, periodo, hoy)
            try:
                datos = self._datos(ns, periodo)
            except Exception as exc:  # l. 59363: el certificado mostraba el texto de la excepcion (hardening NEXT)
                log.error("inicio: tablero no construido: %s", type(exc).__name__)
                return {"estado": "tablero", "tablero": {"periodo": cab, "error": MSG_TABLERO}}
            return {"estado": "tablero", "tablero": {"periodo": cab, "error": None, **P.tablero(ns, datos)}}

        out.update(self._motor(record, scope, read))
        return out

    # ------------------------------------------------------------------ Excel de "Próximos vencimientos" (D-AN6)
    def excel_vencimientos(self, record: SessionRecord) -> Descarga:
        scope = self.scope(record)
        if scope.department is None:
            raise InicioError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)

        def read(ns: dict) -> pd.DataFrame:
            periodo = ns["get_periodo_abierto"]()
            if not periodo:
                raise InicioError(409, "SIN_PERIODO", P.MSG_SIN_PERIODO, tone="warning")
            vis = P.vencimientos_visibles(self._datos(ns, periodo))
            if vis is None:
                raise InicioError(409, "SIN_VENCIMIENTOS", MSG_SIN_VENCIMIENTOS, tone="info")
            return vis

        df = self._motor(record, scope, read)
        return Descarga(excel_bytes(df), f"Inicio_{self.now().strftime('%Y%m%d_%H%M%S')}.xlsx", XLSX)
