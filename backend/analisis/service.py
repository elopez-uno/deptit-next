"""Servicio de Analisis — incluye Productividad (B13-FIX02, pagina ``📊 Análisis`` l. 66604-67763).

Decisiones D-AM1..D-AM14 (docs/analisis_productividad_analysis.md §40):
- Lecturas: motor certificado vendorizado (``analisis.motor``) por request, en UNA transaccion READ ONLY, con el ambito
  de la SESION; reconciliaciones v207-v214 y vistas v205/v206 sin efecto (D-AM2/D-AM3); memoizacion request-scoped
  (D-AM12).  La pagina se transcribe en ``pagina.py`` sin formulas propias (D-AM13 / D-AM14).
- Permiso de lectura ``configuracion.read`` / department (D-AM7): todos los roles con departamento operativo.
- Unico writer: ``guardar_porcentaje_horas_no_lectivas_v148`` (``configuracion.write`` / department -> superadmin y
  usuario_departamento; D-AM4).  B10 -> capa U (huella del valor que se vio, D-AM5) -> 1 COMMIT con 1 UPSERT y su
  SUCCESS (``entity_id`` NULL, D-AM6).  DENIED / FAILED en transaccion propia.  Sin locks.
- Descargas (D-AM1 / D-AM11): Word del movimiento docente, CSV del indicador, CSV por categoria de alerta y TXT del
  prompt (sin llamada a ninguna IA, D-AM9).  Mismos bytes que el certificado (``to_csv(...).encode("utf-8-sig")``).
Ninguna respuesta incluye SQL, trazas, rutas ni columnas legacy; nunca se escriben archivos en disco.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Optional

import pandas as pd
from psycopg import Connection

import audit
from auth import policy
from auth.service import AuthService, SessionRecord
from periodos.service import MSG_AUDIT_POST, MSG_DB_READ, MSG_DB_TRANSACTION, MSG_INSTITUTIONAL, MSG_STALE
from periodos.service import denial_message, scope_message

from . import escrituras as E
from . import pagina as P
from .motor import entorno

log = logging.getLogger("deptit_next.analisis")

MODULO = "analisis"
DEP = policy.SCOPE_DEPARTMENT
ACTION_READ = policy.Action("configuracion", policy.OP_READ, DEP)
ACTION_WRITE = policy.Action("configuracion", policy.OP_WRITE, DEP)
ENTITY_TYPE = "configuracion"

MSG_VALOR_INVALIDO = "Uno de los valores enviados no es válido para este formulario."
MSG_PERIODO_NO_ENCONTRADO = "El período seleccionado ya no existe. Actualizá la pantalla."
MSG_INDICADOR = "El indicador seleccionado no es válido."
MSG_CATEGORIA = "La categoría de alertas seleccionada ya no existe con los filtros actuales. Actualizá la pantalla."
MSG_WORD = "No se pudo preparar el informe Word de movimiento."
MSG_PERIODO_CMP = "Uno de los períodos de comparación ya no está disponible. Actualizá la pantalla."
MSG_REFERENCIA_CMP = "Seleccioná al menos un período anterior para construir la comparación."
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class AnalisisError(Exception):
    def __init__(self, status: int, code: str, message: str, error_class: str = "ValueError", tone: str = "error"):
        super().__init__(message)
        self.status, self.code, self.message, self.error_class, self.tone = status, code, message, error_class, tone


@dataclass(frozen=True)
class Scope:
    institution_id: int
    department_id: int
    institution: dict
    department: dict


@dataclass(frozen=True)
class Descarga:
    contenido: bytes
    nombre: str
    media_type: str


def huella_porcentaje(valor: Any) -> str:
    raw = json.dumps(None if valor is None else float(valor), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _named(row: dict) -> dict:
    return {"id": int(row["id"]), "nombre": row.get("nombre")}


def _texto(value: Any) -> str:
    if not isinstance(value, str):
        raise AnalisisError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


class AnalisisService:
    def __init__(self, pool, auth: AuthService, audit_store: audit.AuditStore, *,
                 today: Callable[[], date] = date.today, now: Callable[[], datetime] = datetime.now,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None):
        self.auth = auth
        self.audit_store = audit_store
        self.today = today
        self.now = now
        self._transaction = transaction or (lambda: pool.connection(timeout=5))

    # ------------------------------------------------------------------ contexto (B12B) y modulo visible
    def scope(self, record: SessionRecord) -> Scope:
        self.auth.apply_default_context(record)
        user, session_scope = record.user, record.scope
        visible = policy.visible_modules(policy.normalize_role(user.get("rol")),
                                         session_scope.get(policy.DEPARTMENT_SCOPE_KEY))
        resolution = self.auth.resolve_scope(record)
        if resolution.reason is not None:
            raise AnalisisError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        if not any(m[0] == MODULO for m in visible) or resolution.department is None:
            raise AnalisisError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        return Scope(int(resolution.institution["id"]), int(resolution.department["id"]), resolution.institution,
                     resolution.department)

    def reader(self, record: SessionRecord) -> Scope:
        scope = self.scope(record)
        decision = policy.decide(policy.actor_from_session(record.user, record.scope), ACTION_READ)
        if not decision.allowed:
            raise AnalisisError(403, "DENIED", denial_message(decision, ACTION_READ))
        return scope

    def _motor(self, record: SessionRecord, scope: Scope, fn: Callable[[dict, Connection], Any]) -> Any:
        """Una ejecucion del motor certificado: transaccion READ ONLY + namespace del request (memo incluido)."""
        usuario = {"email": record.user.get("email"), "rol": record.user.get("rol"),
                   "departamento_nombre": record.user.get("departamento_nombre") or ""}
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                ns = entorno.construir(conn, scope.institution_id, scope.department_id, usuario=usuario,
                                       hoy=self.today, ahora=self.now)
                return fn(ns, conn)
        except AnalisisError:
            raise
        except Exception as exc:
            log.error("analisis: lectura fallida: %s", type(exc).__name__)
            raise AnalisisError(503, "DB_READ", MSG_DB_READ) from None

    @staticmethod
    def _permisos(record: SessionRecord) -> dict:
        actor = policy.actor_from_session(record.user, record.scope)
        return {"puede_guardar": policy.decide(actor, ACTION_WRITE).allowed}

    @staticmethod
    def _periodo(ns: dict, nombre: Any) -> tuple[dict, int, dict]:
        per = P.periodos(ns)
        if per["vacio"]:
            raise AnalisisError(409, "SIN_PERIODOS", P.MSG_SIN_PERIODOS)
        nombre = _texto(nombre)
        if nombre not in per["ids"]:
            raise AnalisisError(409, "PERIODO", MSG_PERIODO_NO_ENCONTRADO)
        pid = per["ids"][nombre]
        return per, pid, P.fila_periodo(per["df"], pid)

    # ------------------------------------------------------------------ lecturas
    def overview(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(ns, conn) -> dict:
            per = P.periodos(ns)
            out = {"vacio": per["vacio"], "periodos": per["opciones"], "periodo": per["default"]}
            pct = float(ns["get_porcentaje_horas_no_lectivas_v148"]() or 0)
            crudo = E.ConfigRepository(conn, scope.institution_id, scope.department_id).porcentaje()
            out["parametro"] = {"valor": pct, "texto": f"{pct:g} %", "huella": huella_porcentaje(crudo),
                                "caption": P.CAPTION_NOLECT, "ayuda": P.HELP_NOLECT}
            out["comparacion"] = None if per["vacio"] else \
                {k: v for k, v in P.comparacion_opciones(ns, per["df"], per["base"]).items() if k != "ids"}
            return out

        data = self._read_payload(record, scope, read)
        data.update({"contexto": {"institucion": _named(scope.institution), "departamento": _named(scope.department)},
                     "titulo": "📊 Análisis", "info": P.INFO, "tabs": P.TABS, "subtabs_comparacion": P.SUBTABS_CMP,
                     "mensaje_sin_periodos": P.MSG_SIN_PERIODOS, "permisos": self._permisos(record),
                     "leyenda_semaforo": P.LEYENDA_SEMAFORO})
        return data

    def _read_payload(self, record, scope, fn):
        return self._motor(record, scope, fn)

    def periodo(self, record: SessionRecord, data: dict) -> dict:
        """Pestañas 1-4 del periodo elegido (un unico calculo central reutilizado por todas, D-AM12)."""
        scope = self.reader(record)

        def read(ns, conn) -> dict:
            per, pid, fila = self._periodo(ns, data.get("periodo"))
            nombre = str(data.get("periodo"))
            m = ns["get_metricas_analisis_periodo"](pid)
            alum = ns["_alumnos_por_docente_periodo_v188"](pid, metricas=m)
            es_hist = bool(m.get("lectura_historica_periodo"))
            mov = P.movimiento(ns, m, alum, pid, nombre, fila, es_hist)
            mov.pop("_df", None)
            auto = P.automatico(ns, m, pid, nombre)
            auto.pop("_alertas", None)
            return {"periodo": nombre, "historico": es_hist, "info_historico": P.INFO_HISTORICO if es_hist else None,
                    "dashboard": P.dashboard(ns, m, alum, pid, nombre, es_hist),
                    "plantel": P.plantel(ns, m, nombre, es_hist), "movimiento": mov, "automatico": auto}

        return self._motor(record, scope, read)

    def comparacion(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        seleccion = data.get("periodos")
        if not isinstance(seleccion, list) or not all(isinstance(x, str) for x in seleccion):
            raise AnalisisError(422, "INVALID", MSG_VALOR_INVALIDO)

        def read(ns, conn) -> dict:
            per = P.periodos(ns)
            if per["vacio"]:
                raise AnalisisError(409, "SIN_PERIODOS", P.MSG_SIN_PERIODOS)
            op = P.comparacion_opciones(ns, per["df"], per["base"])
            if op["actual"] is None:
                return {"vacio": "No se pudo determinar el período actual para comparar."}
            if any(x not in op["ids"] for x in seleccion):
                raise AnalisisError(409, "PERIODO_CMP", MSG_PERIODO_CMP)
            if not seleccion:
                return {"vacio": MSG_REFERENCIA_CMP if op["opciones"] else None}
            return P.comparacion(ns, per["df"], op, list(dict.fromkeys(seleccion)))

        return self._motor(record, scope, read)

    # ------------------------------------------------------------------ descargas
    def word(self, record: SessionRecord, data: dict) -> Descarga:
        scope = self.reader(record)

        def read(ns, conn) -> Descarga:
            per, pid, fila = self._periodo(ns, data.get("periodo"))
            nombre = str(data.get("periodo"))
            m = ns["get_metricas_analisis_periodo"](pid)
            df = P.movimientos_analisis(ns, m)
            try:
                contenido = ns["generar_informe_movimiento_docente_word_v175"](
                    nombre, ns["_departamento_actual_operativo_nombre"](), df, periodo_id=pid)
            except Exception as exc:
                log.error("analisis: Word de movimiento: %s", type(exc).__name__)
                raise AnalisisError(503, "WORD", MSG_WORD, "WordError", tone="warning") from None
            return Descarga(bytes(contenido), f"informe_movimiento_docente_{ns['nombre_archivo_seguro'](nombre)}.docx",
                            DOCX)

        return self._motor(record, scope, read)

    def csv_indicador(self, record: SessionRecord, data: dict) -> Descarga:
        scope = self.reader(record)
        indicador = _texto(data.get("indicador"))
        if indicador not in P.INDICADORES_MOV:
            raise AnalisisError(422, "INDICADOR", MSG_INDICADOR)

        def read(ns, conn) -> Descarga:
            per, pid, fila = self._periodo(ns, data.get("periodo"))
            nombre = str(data.get("periodo"))
            df = P.movimientos_analisis(ns, ns["get_metricas_analisis_periodo"](pid))
            f = df[df["categoria_movimiento"] == P.INDICADORES_MOV[indicador]].copy() if not df.empty else df
            return Descarga(f.to_csv(index=False).encode("utf-8-sig"),
                            f"movimiento_{indicador.lower().replace(' ', '_')}_{nombre}.csv", "text/csv")

        return self._motor(record, scope, read)

    def csv_alertas(self, record: SessionRecord, data: dict) -> Descarga:
        scope = self.reader(record)
        categoria = _texto(data.get("categoria"))
        gravedades = data.get("gravedades")
        if not isinstance(gravedades, list) or any(gv not in P.GRAVEDADES for gv in gravedades):
            raise AnalisisError(422, "INVALID", MSG_VALOR_INVALIDO)

        def read(ns, conn) -> Descarga:
            per, pid, fila = self._periodo(ns, data.get("periodo"))
            nombre = str(data.get("periodo"))
            al = ns["construir_alertas_periodo"](pid)
            al = al[al["gravedad"].isin(gravedades)].copy()
            f = al[al["categoria"].astype(str) == categoria].copy()
            if f.empty:
                raise AnalisisError(409, "CATEGORIA", MSG_CATEGORIA)
            return Descarga(f.to_csv(index=False).encode("utf-8-sig"), P.nombre_alerta_csv(categoria, nombre),
                            "text/csv")

        return self._motor(record, scope, read)

    def prompt(self, record: SessionRecord, data: dict) -> Descarga:
        scope = self.reader(record)

        def read(ns, conn) -> Descarga:
            per, pid, fila = self._periodo(ns, data.get("periodo"))
            nombre = str(data.get("periodo"))
            m = ns["get_metricas_analisis_periodo"](pid)
            texto = ns["construir_prompt_ia_periodo"](nombre, m, ns["construir_alertas_periodo"](pid),
                                                      ns["get_docentes_productividad_periodo"](pid))
            return Descarga(texto.encode("utf-8"), f"prompt_analisis_ia_{nombre}.txt", "text/plain")

        return self._motor(record, scope, read)

    # ------------------------------------------------------------------ writer (B10 -> B12I U -> B12H)
    def _separate(self, op: audit.Operation, outcome: str, *, error_code: Optional[str] = None,
                  metadata: Optional[dict] = None) -> bool:
        mode = audit.MODE_POST_OPERATION if outcome == audit.OUTCOME_SUCCESS else audit.MODE_SEPARATE
        try:
            self.audit_store.append_separate(op.event(outcome, mode, error_code=error_code, metadata=metadata))
            return True
        except Exception as exc:
            log.error("B12H: el evento %s de %s no pudo persistirse (%s)", outcome, op.name, audit.error_code_of(exc))
            return False

    def guardar_porcentaje(self, record: SessionRecord, data: dict) -> dict:
        """"💾 Guardar porcentaje de horas no lectivas" (l. 66642-66650)."""
        scope = self.scope(record)
        valor = data.get("porcentaje")
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(float(valor)) \
                or not 0.0 <= float(valor) <= 200.0:
            raise AnalisisError(422, "INVALID", MSG_VALOR_INVALIDO)
        h = data.get("huella")
        if not isinstance(h, str):
            raise AnalisisError(422, "INVALID", MSG_VALOR_INVALIDO)
        actor = policy.actor_from_session(record.user, record.scope)
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(E.W_GUARDAR, ACTION_WRITE, ENTITY_TYPE, audit_actor, None, None)  # D-AM6: sin entity_id
        decision = policy.decide(actor, ACTION_WRITE)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code, metadata={"b10_decision": decision.code})
            raise AnalisisError(403, "DENIED", denial_message(decision, ACTION_WRITE), "PermissionError")
        unidad = E.Unidad(self._transaction, op, scope.institution_id, scope.department_id, today=self.today(),
                          now=self.now())

        def failed(code: str) -> None:
            self._separate(op, audit.OUTCOME_FAILED, error_code=code, metadata={"coupled_commits": op.coupled_commits})
        try:
            fresca = unidad.read(lambda repo: repo.porcentaje())
            if huella_porcentaje(fresca) != h:
                raise AnalisisError(409, "STALE", f"{MSG_STALE} [B12I: get_porcentaje_horas_no_lectivas_v148]",
                                    "StaleDecisionError")
            guardado = E.guardar_porcentaje_horas_no_lectivas_v148(unidad, float(valor))
        except AnalisisError as exc:
            failed(exc.error_class)
            raise
        except E.AuditoriaFallida:
            failed("AuditPersistenceError:AUDIT_INSERT_FAILED")
            raise AnalisisError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]",
                                "AuditPersistenceError") from None
        except Exception as exc:
            log.error("analisis: %s falló tras %d COMMIT(s): %s", E.W_GUARDAR, op.coupled_commits, type(exc).__name__)
            failed(audit.error_code_of(exc))
            raise AnalisisError(503, "DB_ERROR", MSG_DB_TRANSACTION, type(exc).__name__) from None
        if op.coupled_commits == 0 and not self._separate(
                op, audit.OUTCOME_SUCCESS, metadata={"coupled_commits": 0, "post_reason": "NO_POOLED_COMMIT"}):
            raise AnalisisError(503, "AUDIT", MSG_AUDIT_POST)
        return {"mensaje": f"Porcentaje guardado: {guardado:g} %. Se recalculará la productividad del departamento.",
                "tono": "success"}
