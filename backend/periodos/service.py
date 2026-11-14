"""Reglas de negocio de Periodos (B13-FIX02) sobre la sesion y el contexto de ``auth``.

Alcance de este bloque (decision humana, ver docs/periodos_analysis.md §11): listado + periodo abierto, "Abrir periodo
anterior" (``abrir_periodo_emergencia``) y "Volver al periodo actual" (``volver_periodo_actual``).  Crear, Revertir
y Eliminar escriben en Designaciones/Investigacion/Extension/Comisiones y quedan pendientes de migracion.

Secuencia certificada de cada escritura (B12H -> B10 -> B12D -> B12I -> cuerpo) y sus eventos B12H:
1. comprobaciones de la UI (confirmaciones, estado de pantalla) sobre las lecturas de la pantalla: sin evento;
2. B10 ``periodos.write`` del writer externo (el ``registrar_movimiento`` anidado es ``ALLOW_NESTED``): DENIED;
3. B12I: lock de SESION ``deptit_crear_periodo:{inst}:{dep}`` en conexion dedicada (espera acotada) y revalidacion
   fresca de las lecturas de la pantalla (si cambiaron: 0 escrituras, FAILED ``StaleDecisionError``);
4. COMMIT 1 (cuerpo del writer: cambio de estado) -> SUCCESS ``commit_seq`` 1, en esa transaccion;
5. COMMIT 2 (``registrar_movimiento``: movimiento) -> SUCCESS ``commit_seq`` 2, en esa transaccion;
6. ningun COMMIT con cambios -> SUCCESS ``POST_OPERATION``; cualquier error -> ROLLBACK de la transaccion en curso y
   FAILED con ``coupled_commits`` = COMMITs ya confirmados (un COMMIT 1 confirmado no se deshace, como el certificado).
El ambito (institucion/departamento) sale SIEMPRE de la sesion revalidada; ningun id de tenant llega del cliente.
"""

from __future__ import annotations

import logging
import time
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Iterator, Optional

from psycopg import Connection

import audit
from auth import core, policy
from auth.service import AuthService, ScopeResolution, SessionRecord

from .repository import (
    EMERGENCY_OPEN_LOCK, PERIOD_STATE_LOCK, SESSION_UNLOCK_SQL, TRY_SESSION_LOCK_SQL, PeriodosRepository,
)

log = logging.getLogger("deptit_next.periodos")

ACTION_WRITE = policy.Action("periodos", policy.OP_WRITE, policy.SCOPE_DEPARTMENT)
ACTION_READ = policy.Action("periodos", policy.OP_READ, policy.SCOPE_DEPARTMENT)

# B12I (cache_decision_integrity.py): familia "periodo_estado"; espera y sondeo del lock de sesion.
LOCK_FAMILY = "periodo_estado"
LOCK_WAIT_SECONDS = 30.0
LOCK_POLL_SECONDS = 0.1
# Lecturas de la pantalla Periodos que B12I revalida frescas (capa U).
READ_SET = ("get_periodos", "get_periodo_abierto", "get_ultimo_periodo")

# Writers del registro B10 (legacy_write_actions.py) que invoca la UI certificada.
OP_OPEN_CONTROL = "_abrir_periodo_emergencia_control_v300"
OP_OPEN_BODY = "abrir_periodo_emergencia"
OP_RETURN_CONTROL = "_volver_periodo_actual_control_v300"
OP_RETURN_BODY = "volver_periodo_actual"
OP_MOVEMENT = "registrar_movimiento"

MOV_OPEN = "Apertura excepcional de período"
MOV_RETURN = "Retorno al período actual"

# --- textos certificados (entry l. 61933-63391, 11394-11547; b12b, b12d, b12i, security/ui_messages.py)
MSG_NO_PERIODS = "Todavía no hay períodos registrados."
MSG_OPEN_CONFIRM = "Tenés que marcar ambas confirmaciones antes de abrir un período anterior."
MSG_RETURN_CONFIRM = "Tenés que marcar ambas confirmaciones antes de volver al período actual."
MSG_RETURN_CONFIRM_SINGLE = "Tenés que confirmar la acción antes de continuar."
MSG_INVALID_PERIOD = "El período seleccionado no es válido."
MSG_PERIOD_NOT_FOUND = "No se encontró el período seleccionado."
MSG_OPEN_FAILED = "No se pudo abrir el período seleccionado."
MSG_NO_PERIODS_REGISTERED = "No hay períodos registrados."
PREFIX_OPEN_ERROR = "No se pudo abrir el período seleccionado: "
PREFIX_RETURN_ERROR = "No se pudo volver al período actual: "
MSG_STALE = ("Los datos que se usaron para esta operación cambiaron en otra sesión o instancia. No se guardó nada. "
             "La pantalla se actualizó con el estado real: revisá y repetí la operación.")
MSG_LOCK = ("Hay otra operación concurrente sobre los mismos datos. No se guardó nada: reintentá en unos instantes.")
MSG_DB_TRANSACTION = "La base de datos devolvió un error durante la operación: la transacción se revirtió completa."
MSG_DB_READ = "La lectura de la base de datos falló (no es un resultado vacío)."
MSG_INSTITUTIONAL = ("Estás en el ámbito institucional. Seleccioná un departamento desde la barra lateral "
                     "para ver su tablero operativo.")
MSG_AUDIT_POST = ("La operación terminó pero su evento de auditoría no pudo registrarse. Avisá al administrador "
                  "(la falta del registro quedó informada en el log del servidor).")

_DENIAL_TEXT = {
    policy.DENY_UNAUTHENTICATED: "La sesión no es válida. Volvé a ingresar al sistema.",
    policy.DENY_MISSING_CONTEXT: "La sesión no es válida. Volvé a ingresar al sistema.",
    policy.DENY_UNKNOWN_ROLE: "Tu usuario no tiene un rol habilitado para modificar datos.",
    policy.DENY_UNKNOWN_ACCESS_MODE: "No se pudo determinar el estado de acceso de tu institución.",
    policy.DENY_ACCESS_BLOCKED: "El acceso de la institución está bloqueado. Contactá al administrador.",
    policy.DENY_COMMERCIAL_READ_ONLY: "La institución está en modo solo lectura: no se pueden registrar cambios.",
    policy.DENY_READ_ONLY_ROLE: "Tu usuario es de solo lectura: no puede cargar, editar ni eliminar datos.",
    policy.DENY_ROLE_NOT_PERMITTED: "Tu rol no tiene permiso para esta operación.",
    policy.DENY_UNKNOWN_ACTION: "Operación no reconocida: no se ejecutó.",
    policy.DENY_SCOPE_MISSING: "Falta seleccionar la institución o el departamento sobre el que se quiere operar.",
    policy.DENY_SCOPE_MISMATCH: "La operación apunta a una institución o departamento que no corresponde a tu usuario.",
}

_SCOPE_REASON_TEXT = {
    "INSTITUTION_ABSENT": "la sesión no tiene una institución asignada o seleccionada",
    "INSTITUTION_INVALID": "la institución de la sesión no es un identificador válido",
    "INSTITUTION_NOT_FOUND": "la institución de la sesión ya no existe",
    "DEPARTMENT_ABSENT": "el usuario no tiene un departamento asignado",
    "DEPARTMENT_INVALID": "el departamento de la sesión no es un identificador válido",
    "DEPARTMENT_NOT_FOUND": "el departamento de la sesión ya no existe",
    "DEPARTMENT_MISMATCH": "el departamento de la sesión no pertenece a la institución",
}


def denial_message(decision: policy.Decision, action: policy.Action) -> str:
    """``ui_messages.mensaje_denegacion`` certificado."""
    base = _DENIAL_TEXT.get(decision.code, "Operación no autorizada.")
    return f"⛔ {base} No se realizó ningún cambio. (permiso requerido: {action.key})"


def scope_message(resolution: ScopeResolution) -> str:
    """``scope_fail_closed.scope_denied_message`` certificado."""
    reason = resolution.reason
    detail = _SCOPE_REASON_TEXT.get(reason or "", reason or "ámbito no verificable")
    if resolution.institution is not None:
        alcance = ("Las vistas departamentales quedan vacías y sus operaciones bloqueadas hasta elegir un "
                   "departamento válido de la institución.")
    else:
        alcance = ("Por seguridad no se muestran datos de ninguna institución ni departamento: las vistas aparecen "
                   "vacías y las operaciones quedan bloqueadas. Cerrá sesión y volvé a ingresar, o pedí al "
                   "administrador que revise tu usuario.")
    return f"🔒 Ámbito no verificado: {detail}. {alcance} [B12B {reason}]"


class PeriodosError(Exception):
    """Error controlado para la UI.  ``error_class`` = clase de la excepcion certificada equivalente (B12H)."""

    def __init__(self, status: int, code: str, message: str, error_class: str = "ValueError"):
        super().__init__(message)
        self.status, self.code, self.message, self.error_class = status, code, message, error_class


@dataclass(frozen=True)
class Scope:
    institution_id: int
    department_id: int
    institution: dict
    department: dict


def _named(row: dict) -> dict:
    return {"id": int(row["id"]), "nombre": row.get("nombre")}


def _period(row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    return {k: row.get(k) for k in ("id", "nombre", "anio", "semestre", "fecha_inicio", "fecha_fin", "estado",
                                     "observaciones")}


def _fingerprint(value: Any) -> tuple:
    """Huella independiente del orden de filas (B12I ``fingerprint``)."""
    if value is None:
        return ()
    rows = value if isinstance(value, list) else [value]
    return tuple(sorted(tuple(sorted((k, repr(v)) for k, v in row.items())) for row in rows))


class PeriodosService:
    def __init__(self, pool, auth: AuthService, audit_store: audit.AuditStore, *,
                 today: Callable[[], date] = date.today,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None,
                 lock_connection: Optional[Callable[[], AbstractContextManager[Connection]]] = None,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
                 lock_wait_seconds: float = LOCK_WAIT_SECONDS):
        self.auth = auth
        self.audit_store = audit_store
        self.today = today
        # Unidad de trabajo = un COMMIT certificado: conexion del pool que confirma al salir sin error y revierte
        # ante cualquier excepcion.  El lock B12I usa otra conexion dedicada, como el certificado.
        self._transaction = transaction or (lambda: pool.connection(timeout=5))
        self._lock_connection = lock_connection or (lambda: pool.connection(timeout=5))
        self.clock, self.sleep, self.lock_wait_seconds = clock, sleep, float(lock_wait_seconds)

    # ------------------------------------------------------------------ contexto (B12B) y modulo visible
    def scope(self, record: SessionRecord) -> Scope:
        self.auth.apply_default_context(record)
        user, session_scope = record.user, record.scope
        effective = policy.normalize_role(user.get("rol"))
        visible = policy.visible_modules(effective, session_scope.get(policy.DEPARTMENT_SCOPE_KEY))
        resolution = self.auth.resolve_scope(record)
        if resolution.reason is not None:
            raise PeriodosError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        if not any(m[0] == "periodos" for m in visible) or resolution.department is None:
            raise PeriodosError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        return Scope(int(resolution.institution["id"]), int(resolution.department["id"]),
                     resolution.institution, resolution.department)

    # ------------------------------------------------------------------ lecturas de la pantalla
    def _read_set(self, scope: Scope) -> dict:
        with self._transaction() as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            repo = PeriodosRepository(conn, scope.institution_id, scope.department_id)
            return {"get_periodos": repo.list(), "get_periodo_abierto": repo.open_period(),
                    "get_ultimo_periodo": repo.last_period()}

    def _screen(self, scope: Scope) -> dict:
        try:
            return self._read_set(scope)
        except Exception as exc:
            log.error("periodos: lectura fallida: %s", type(exc).__name__)
            raise PeriodosError(503, "DB_READ", MSG_DB_READ) from None

    def overview(self, record: SessionRecord) -> dict:
        scope = self.scope(record)
        actor = policy.actor_from_session(record.user, record.scope)
        read = policy.decide(actor, ACTION_READ)
        if not read.allowed:
            raise PeriodosError(403, "DENIED", denial_message(read, ACTION_READ))
        screen = self._screen(scope)
        return {
            "contexto": {"institucion": _named(scope.institution), "departamento": _named(scope.department)},
            "periodos": [_period(r) for r in screen["get_periodos"]],
            "abierto": _period(screen["get_periodo_abierto"]),
            "actual": _period(screen["get_ultimo_periodo"]),
            "permisos": {
                # ui_messages.visual_can certificado: dominio del modulo (periodos.write)
                "puede_escribir": policy.decide(actor, ACTION_WRITE).allowed,
                "es_superadmin": policy.normalize_role(record.user.get("rol")) == policy.ROLE_SUPERADMIN,
            },
        }

    # ------------------------------------------------------------------ B10 + DENIED B12H
    def _authorize(self, record: SessionRecord, name: str, entity_param: Optional[str] = None,
                   entity_raw: Any = None) -> audit.Operation:
        actor = policy.actor_from_session(record.user, record.scope)
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(name, ACTION_WRITE, "periodo", audit_actor, entity_param, entity_raw)
        decision = policy.decide(actor, ACTION_WRITE)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code,
                           metadata={"b10_decision": decision.code})
            raise PeriodosError(403, "DENIED", denial_message(decision, ACTION_WRITE), "PermissionError")
        return op

    def _separate(self, op: audit.Operation, outcome: str, *, error_code: Optional[str] = None,
                  metadata: Optional[dict] = None) -> bool:
        mode = audit.MODE_POST_OPERATION if outcome == audit.OUTCOME_SUCCESS else audit.MODE_SEPARATE
        try:
            self.audit_store.append_separate(op.event(outcome, mode, error_code=error_code, metadata=metadata))
            return True
        except Exception as exc:
            log.error("B12H: el evento %s de %s no pudo persistirse (%s)", outcome, op.name, audit.error_code_of(exc))
            return False

    # ------------------------------------------------------------------ B12I capa T y capa U
    @contextmanager
    def _consistency_lock(self, scope: Scope) -> Iterator[None]:
        key = PERIOD_STATE_LOCK.format(inst=scope.institution_id, dep=scope.department_id)
        with self._lock_connection() as conn:
            acquired = False
            try:
                deadline = self.clock() + self.lock_wait_seconds
                while True:
                    row = conn.execute(TRY_SESSION_LOCK_SQL, [key]).fetchone()
                    conn.commit()
                    if row and bool(row[0]):
                        acquired = True
                        break
                    if self.clock() >= deadline:
                        raise PeriodosError(409, "LOCK", f"{MSG_LOCK} [B12I: {LOCK_FAMILY}]", "ConsistencyLockError")
                    self.sleep(LOCK_POLL_SECONDS)
                yield
            finally:
                if acquired:
                    try:
                        conn.execute(SESSION_UNLOCK_SQL, [key])
                        conn.commit()
                    except Exception:
                        conn.close()  # sesion descartada: PostgreSQL libera sus locks al cerrarla

    def _validate_read_set(self, scope: Scope, seen: dict) -> None:
        fresh = self._read_set(scope)
        stale = [label for label in READ_SET if _fingerprint(fresh[label]) != _fingerprint(seen[label])]
        if stale:
            raise PeriodosError(409, "STALE", f"{MSG_STALE} [B12I: {', '.join(sorted(stale))}]",
                                "StaleDecisionError")

    # ------------------------------------------------------------------ COMMITs acoplados a B12H
    def _commit(self, op: audit.Operation, scope: Scope, writer: str,
                body: Callable[[PeriodosRepository], Any]) -> Any:
        """Un COMMIT certificado: ``body`` + (si hubo mutaciones) su SUCCESS en la MISMA transaccion."""
        with self._transaction() as conn:
            repo = PeriodosRepository(conn, scope.institution_id, scope.department_id)
            result = body(repo)
            if repo.mutating_statements:
                try:
                    audit.insert_on(conn, op.event(audit.OUTCOME_SUCCESS, audit.MODE_IN_TRANSACTION, metadata={
                        "commit_seq": op.coupled_commits + 1, "mutating_statements": repo.mutating_statements,
                        "committing_writer": writer}))
                except Exception as exc:
                    log.error("B12H: el evento SUCCESS de %s no pudo insertarse (%s): ROLLBACK", op.name,
                              audit.error_code_of(exc))
                    raise PeriodosError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]",
                                        "AuditPersistenceError:AUDIT_INSERT_FAILED") from None
        if repo.mutating_statements:
            op.coupled_commits += 1
        return result

    def _run(self, op: audit.Operation, error_prefix: str, steps: Callable[[], dict]) -> dict:
        """Operacion B12H: FAILED propio ante error; sin COMMITs con cambios, SUCCESS POST_OPERATION."""
        try:
            result = steps()
        except PeriodosError as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code=exc.error_class,
                           metadata={"coupled_commits": op.coupled_commits})
            raise PeriodosError(exc.status, exc.code, error_prefix + exc.message, exc.error_class) from None
        except Exception as exc:
            log.error("periodos: %s falló tras %d COMMIT(s): %s", op.name, op.coupled_commits, type(exc).__name__)
            self._separate(op, audit.OUTCOME_FAILED, error_code=audit.error_code_of(exc),
                           metadata={"coupled_commits": op.coupled_commits})
            raise PeriodosError(503, "DB_ERROR", error_prefix + MSG_DB_TRANSACTION) from None
        if op.coupled_commits == 0:
            if not self._separate(op, audit.OUTCOME_SUCCESS,
                                  metadata={"coupled_commits": 0, "post_reason": "NO_POOLED_COMMIT"}):
                raise PeriodosError(503, "AUDIT", MSG_AUDIT_POST)
        return result

    def _movement(self, op: audit.Operation, scope: Scope, period_id: int, tipo: str, detalle: str,
                  observaciones: str) -> None:
        """``registrar_movimiento`` anidado: su propio COMMIT con su SUCCESS."""
        self._commit(op, scope, OP_MOVEMENT, lambda repo: repo.insert_movement(
            period_id=period_id, fecha=str(self.today()), tipo=tipo, detalle=detalle, observaciones=observaciones,
            horas_variacion=0))

    # ------------------------------------------------------------------ Abrir periodo anterior (excepcional)
    def open_previous(self, record: SessionRecord, period_raw: Any, observaciones: str,
                      confirm_close: bool, confirm_exceptional: bool) -> dict:
        scope = self.scope(record)
        if confirm_close is not True or confirm_exceptional is not True:
            raise PeriodosError(422, "CONFIRMATION_REQUIRED", MSG_OPEN_CONFIRM)
        seen = self._screen(scope)
        op = self._authorize(record, OP_OPEN_CONTROL, "periodo_id", period_raw)
        observaciones = "" if observaciones is None else str(observaciones)

        def state_change(period_id: int):
            def body(repo: PeriodosRepository) -> dict:
                repo.lock(EMERGENCY_OPEN_LOCK)
                target = repo.by_id(period_id)
                if target is None:
                    raise PeriodosError(404, "PERIOD_NOT_FOUND", MSG_PERIOD_NOT_FOUND)
                current = repo.open_period()
                if current is not None and int(current["id"]) == period_id:
                    # Ya esta abierto: sin falso cierre/apertura ni movimiento redundante.
                    return {"changed": False, "periodo": target, "current": current}
                repo.close_open_except(period_id)
                if repo.open_one(period_id) <= 0:
                    raise PeriodosError(409, "OPEN_FAILED", MSG_OPEN_FAILED)
                return {"changed": True, "periodo": target, "current": current}
            return body

        def steps() -> dict:
            with self._consistency_lock(scope):
                self._validate_read_set(scope, seen)
                period_id = core.to_int_or_none(period_raw)
                if period_id is None:
                    raise PeriodosError(422, "INVALID_PERIOD", MSG_INVALID_PERIOD)
                result = self._commit(op, scope, OP_OPEN_BODY, state_change(period_id))
                if not result["changed"]:
                    return result
                target, current = result["periodo"], result["current"]
                if current is not None:
                    detalle = (f"Se cerró excepcionalmente el período {current['nombre']} y "
                               f"se abrió el período anterior {target['nombre']} "
                               f"({target.get('fecha_inicio', '')} al {target.get('fecha_fin', '')}) "
                               "para realizar correcciones puntuales.")
                else:
                    detalle = (f"Se abrió excepcionalmente el período {target['nombre']} "
                               f"({target.get('fecha_inicio', '')} al {target.get('fecha_fin', '')}) "
                               "para realizar correcciones puntuales.")
                self._movement(op, scope, int(target["id"]), MOV_OPEN, detalle, observaciones)
                return result

        result = self._run(op, PREFIX_OPEN_ERROR, steps)
        target = result["periodo"]
        return {"mensaje": f"Período {target['nombre']} abierto excepcionalmente. "
                           "Revisá bien antes de modificar datos.",
                "periodo": _period(target), "cambio": result["changed"]}

    # ------------------------------------------------------------------ Volver al periodo actual
    def return_current(self, record: SessionRecord, observaciones: str, confirm_close_previous: bool,
                       confirm_return: bool) -> dict:
        scope = self.scope(record)
        seen = self._screen(scope)
        seen_last, seen_open = seen["get_ultimo_periodo"], seen["get_periodo_abierto"]
        # Estados de la pestaña certificada "Volver al período actual".
        if seen_last is None:
            raise PeriodosError(409, "NO_PERIODS", MSG_NO_PERIODS)
        if seen_open is None:
            if confirm_return is not True:
                raise PeriodosError(422, "CONFIRMATION_REQUIRED", MSG_RETURN_CONFIRM_SINGLE)
            name, success = OP_RETURN_BODY, "Se abrió el período actual correctamente."
        elif int(seen_open["id"]) == int(seen_last["id"]):
            raise PeriodosError(409, "ALREADY_CURRENT",
                                f"Ya estás trabajando sobre el período actual: {seen_last['nombre']} "
                                f"({seen_last['fecha_inicio']} al {seen_last['fecha_fin']}).")
        else:
            if confirm_close_previous is not True or confirm_return is not True:
                raise PeriodosError(422, "CONFIRMATION_REQUIRED", MSG_RETURN_CONFIRM)
            name, success = OP_RETURN_CONTROL, "Se volvió al período actual correctamente."
        op = self._authorize(record, name)
        observaciones = "" if observaciones is None else str(observaciones)

        def state_change(repo: PeriodosRepository) -> dict:
            last, open_now = repo.last_period(), repo.open_period()
            if last is None:
                raise PeriodosError(409, "NO_PERIODS", MSG_NO_PERIODS_REGISTERED)
            repo.close_all_open()
            repo.open_one(int(last["id"]))
            return {"periodo": last, "abierto_previo": open_now}

        def steps() -> dict:
            with self._consistency_lock(scope):
                self._validate_read_set(scope, seen)
                result = self._commit(op, scope, OP_RETURN_BODY, state_change)
                last, open_now = result["periodo"], result["abierto_previo"]
                detalle = (f"Se volvió al período actual {last['nombre']} "
                           f"({last['fecha_inicio']} al {last['fecha_fin']}).")
                if open_now is not None:
                    detalle = (f"Se cerró el período abierto {open_now['nombre']} y "
                               f"se volvió al período actual {last['nombre']} "
                               f"({last['fecha_inicio']} al {last['fecha_fin']}).")
                self._movement(op, scope, int(last["id"]), MOV_RETURN, detalle, observaciones)
                return result

        result = self._run(op, PREFIX_RETURN_ERROR, steps)
        return {"mensaje": success, "periodo": _period(result["periodo"]), "cambio": True}
