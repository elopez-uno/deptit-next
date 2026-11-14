"""Reglas de pantalla de Comisiones (B13-FIX02, entry l. 70015-72307) sobre la sesion y el contexto de ``auth``.

Alcance (decision humana, docs/comisiones_analysis.md §19): las 8 pestañas certificadas y sus 13 subpestañas.
Efectos cruzados portados fielmente: docente prestado local (Docentes) y reajuste de horas de proyectos v184
(Investigacion/Extension).  Sin desbloqueos de otros bloques.  Excluidos: piloto 8F, reparaciones de cargos,
reparacion de optativas 2026-1 y migraciones al leer.

Cada writer certificado que la UI invoca es una operacion B12H propia (``correlation_id`` por writer):
1. comprobaciones de la pantalla sobre lecturas frescas (mismo orden y mensajes que el certificado): sin evento;
2. B10 del writer (``comisiones.write`` / ``comisiones.delete``; ``movimientos.write`` para registrar_movimiento):
   DENIED en transaccion propia;
3. B12I capa T (solo ``guardar_comision``, ``actualizar_comision``, ``actualizar_nombre_comision_correccion_v180``,
   ``actualizar_nombres_comisiones_lote_v195`` y ``cargar_comisiones_rapidas_lote_v232``): lock de SESION
   ``deptit_b12i_comision_identidad:{inst}:{dep}`` en conexion dedicada, espera hasta 30 s, ANTES de validar;
4. B12I capa U: en el primer writer del clic se relee fresco lo que el usuario vio (``huella``); si cambio ->
   FAILED ``StaleDecisionError`` sin escribir;
5. cada COMMIT certificado con su SUCCESS (``commit_seq``) en esa transaccion; sin COMMITs -> SUCCESS POST_OPERATION;
   error -> FAILED con ``coupled_commits`` (lo ya confirmado queda, como el certificado).
El ambito (institucion/departamento) sale SIEMPRE de la sesion revalidada; ningun id de tenant llega del cliente.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Iterator, Optional

import pandas as pd
from psycopg import Connection

import audit
from auth import policy
from auth.service import AuthService, SessionRecord
from periodos.service import MSG_AUDIT_POST, MSG_DB_READ, MSG_DB_TRANSACTION, MSG_INSTITUTIONAL, MSG_STALE
from periodos.service import denial_message, scope_message
import uploads

from . import escrituras as E
from . import rules as R
from .lecturas import Lector
from .repository import ComisionesRepository

log = logging.getLogger("deptit_next.comisiones")

DEP = policy.SCOPE_DEPARTMENT
INST = policy.SCOPE_INSTITUTION
ACTION_READ = policy.Action("comisiones", policy.OP_READ, DEP)
ACTION_WRITE = policy.Action("comisiones", policy.OP_WRITE, DEP)
ACTION_DELETE = policy.Action("comisiones", policy.OP_DELETE, DEP)
ACTION_WRITE_INST = policy.Action("comisiones", policy.OP_WRITE, INST)
ACTION_DELETE_INST = policy.Action("comisiones", policy.OP_DELETE, INST)
ACTION_MOVEMENT = policy.Action("movimientos", policy.OP_WRITE, DEP)

# B12I (cache_decision_integrity.py l. 130-168): familia "comision_identidad".
LOCK_FAMILY = "comision_identidad"
COMMISSION_LOCK_FORMAT = "deptit_b12i_comision_identidad:{inst}:{dep}"
LOCK_WRITERS = frozenset({E.W_GUARDAR_COMISION, E.W_ACTUALIZAR_COMISION, E.W_NOMBRE_V180, E.W_NOMBRES_LOTE,
                          E.W_CARGA_LOTE})
LOCK_WAIT_SECONDS = 30.0
LOCK_POLL_SECONDS = 0.1
TRY_SESSION_LOCK_SQL = "SELECT pg_try_advisory_lock(hashtext(%s))"
SESSION_UNLOCK_SQL = "SELECT pg_advisory_unlock(hashtext(%s))"
MSG_LOCK = "Hay otra operación concurrente sobre los mismos datos. No se guardó nada: reintentá en unos instantes."


@dataclass(frozen=True)
class WriterSpec:
    """Writer del registro B10 (legacy_write_actions.py) y su etiqueta B12H (``writer_catalog``/``_entity_param``)."""
    name: str
    action: policy.Action
    entity_type: str
    entity_param: Optional[str]


SPEC_GUARDAR_COMISION = WriterSpec(E.W_GUARDAR_COMISION, ACTION_WRITE, "comision", "materia_id")
SPEC_ACTUALIZAR_COMISION = WriterSpec(E.W_ACTUALIZAR_COMISION, ACTION_WRITE, "comision", "comision_id")
SPEC_NOMBRE_V180 = WriterSpec(E.W_NOMBRE_V180, ACTION_WRITE, "comision", "comision_id")
SPEC_NOMBRES_LOTE = WriterSpec(E.W_NOMBRES_LOTE, ACTION_WRITE, "comision", None)
SPEC_CARGA_LOTE = WriterSpec(E.W_CARGA_LOTE, ACTION_WRITE, "comision", None)
SPEC_GUARDAR_HORARIO = WriterSpec(E.W_GUARDAR_HORARIO, ACTION_WRITE, "horario_comision", "comision_id")
SPEC_ACTUALIZAR_HORARIO = WriterSpec(E.W_ACTUALIZAR_HORARIO, ACTION_WRITE, "horario_comision", "horario_id")
SPEC_GUARDAR_ASIGNACION = WriterSpec(E.W_GUARDAR_ASIGNACION, ACTION_WRITE, "asignacion_docente_comision", "comision_id")
SPEC_HORARIOS_REALES = WriterSpec(E.W_HORARIOS_REALES, ACTION_WRITE, "horario_comision", "asignacion_id")
SPEC_ESTADO_ASIGNACION = WriterSpec(E.W_ESTADO_ASIGNACION, ACTION_WRITE, "asignacion_docente_comision", "asignacion_id")
SPEC_INSCRIPTOS = WriterSpec(E.W_INSCRIPTOS, ACTION_WRITE, "inscriptos", "materia_id")
SPEC_GUARDAR_SEDE = WriterSpec(E.W_GUARDAR_SEDE, ACTION_WRITE_INST, "sede_institucional", None)
SPEC_ACTUALIZAR_SEDE = WriterSpec(E.W_ACTUALIZAR_SEDE, ACTION_WRITE_INST, "sede_institucional", "sede_id")
SPEC_ELIMINAR_COMISION = WriterSpec(E.W_ELIMINAR_COMISION, ACTION_DELETE, "comision", "comision_id")
SPEC_ELIMINAR_HORARIO = WriterSpec(E.W_ELIMINAR_HORARIO, ACTION_DELETE, "horario_comision", "horario_id")
SPEC_ELIMINAR_ASIGNACION = WriterSpec(E.W_ELIMINAR_ASIGNACION, ACTION_DELETE, "asignacion_docente_comision",
                                      "asignacion_id")
SPEC_ELIMINAR_SEDE = WriterSpec(E.W_ELIMINAR_SEDE, ACTION_DELETE_INST, "sede_institucional", "sede_id")
SPEC_COMPENSACION = WriterSpec(E.W_COMPENSACION, ACTION_WRITE, "comision", "comision_id")
SPEC_MOVIMIENTO = WriterSpec(E.W_MOVIMIENTO, ACTION_MOVEMENT, "movimiento", "cuil")

# --- textos certificados (entry l. 70015-72307) ---------------------------------------------------------------
MSG_VALOR_INVALIDO = "Uno de los valores enviados no es válido para este formulario."
MSG_EXCEL_INVALIDO = "el archivo no es un .xlsx válido."  # 6A-B1; se antepone el texto certificado
MSG_COMISION_NO_ENCONTRADA = "No se encontró la comisión seleccionada. Actualizá la pantalla."
MSG_SELECCION_INVALIDA = "La selección no corresponde a las filas mostradas. Actualizá la pantalla."
MSG_PERIODO_NO_ENCONTRADO = "No se encontró el período seleccionado."
MSG_NO_OPERAR_ALTA = "Solo podés abrir comisiones en el período actual abierto."
MSG_NO_PERIODO_ACTUAL_ALTA = "No hay un período actual abierto para registrar la comisión."
MSG_NO_OPERAR_CAMBIO = "Solo podés registrar modificaciones de asignaciones en el período actual abierto."
MSG_NO_PERIODO_CAMBIO = "No hay período actual para operar cambios de comisiones."
MSG_NO_OPERAR_CARGA = "Solo podés hacer carga rápida de comisiones en el período actual abierto."
MSG_NO_PERIODO_CARGA = "No hay período actual para cargar comisiones."
MSG_NO_CORREGIR = "No hay un período abierto habilitado para corregir comisiones."


class ComisionesError(Exception):
    """Error controlado para la UI.  ``error_class`` = clase de la excepcion certificada equivalente (B12H)."""

    def __init__(self, status: int, code: str, message: str, error_class: str = "ValueError", tone: str = "error"):
        super().__init__(message)
        self.status, self.code, self.message, self.error_class, self.tone = status, code, message, error_class, tone


@dataclass(frozen=True)
class Scope:
    institution_id: int
    department_id: int
    institution: dict
    department: dict


def _named(row: dict) -> dict:
    return {"id": int(row["id"]), "nombre": row.get("nombre")}


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return [_jsonable(v) for v in sorted(value, key=str)]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return value.item()
        except Exception:
            return value
    return value


def _clean(row: dict) -> dict:
    return {str(k): _jsonable(v) for k, v in row.items()}


def records(df: Optional[pd.DataFrame], cols: Optional[list] = None) -> list[dict]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    base = df[[c for c in cols if c in df.columns]] if cols else df
    return [_clean(r) for r in base.to_dict(orient="records")]


def _hash(payload: Any) -> str:
    raw = json.dumps(_jsonable(payload), sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _period(row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    return {k: _jsonable(row.get(k)) for k in ("id", "nombre", "anio", "semestre", "fecha_inicio", "fecha_fin",
                                                "estado")}


def py_str(value: Any) -> str:
    """``f"{valor}"`` de Python sobre el valor tal como lo tiene el certificado (numeric -> float)."""
    if isinstance(value, Decimal):
        value = float(value)
    return str(value)


def _id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _opt_id(value: Any) -> Optional[int]:
    return None if value in (None, "") else _id(value)


def _ids(values: Any) -> list[int]:
    if values in (None, ""):
        return []
    if not isinstance(values, list):
        raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return [_id(v) for v in values]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return str(value)


def _opcion(value: Any, opciones: list) -> str:
    if not isinstance(value, str) or value not in opciones:
        raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _fecha(value: Any) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO) from None


def _hora(value: Any) -> str:
    """Hora ``HH:MM`` (el ``st.time_input`` certificado entrega ``time`` y la pantalla usa ``strftime('%H:%M')``)."""
    txt = str(value or "").strip()
    try:
        return datetime.strptime(txt, "%H:%M").strftime("%H:%M")
    except ValueError:
        raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO) from None


class ComisionesService:
    def __init__(self, pool, auth: AuthService, audit_store: audit.AuditStore, *,
                 today: Callable[[], date] = date.today, now: Callable[[], datetime] = datetime.now,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None,
                 lock_connection: Optional[Callable[[], AbstractContextManager[Connection]]] = None,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
                 lock_wait_seconds: float = LOCK_WAIT_SECONDS):
        self.auth = auth
        self.audit_store = audit_store
        self.today = today
        self.now = now
        self._transaction = transaction or (lambda: pool.connection(timeout=5))
        self._lock_connection = lock_connection or (lambda: pool.connection(timeout=5))
        self.clock, self.sleep, self.lock_wait_seconds = clock, sleep, float(lock_wait_seconds)

    # ------------------------------------------------------------------ contexto (B12B) y modulo visible
    def scope(self, record: SessionRecord) -> Scope:
        self.auth.apply_default_context(record)
        user, session_scope = record.user, record.scope
        visible = policy.visible_modules(policy.normalize_role(user.get("rol")),
                                         session_scope.get(policy.DEPARTMENT_SCOPE_KEY))
        resolution = self.auth.resolve_scope(record)
        if resolution.reason is not None:
            raise ComisionesError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        if not any(m[0] == "comisiones" for m in visible) or resolution.department is None:
            raise ComisionesError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        return Scope(int(resolution.institution["id"]), int(resolution.department["id"]),
                     resolution.institution, resolution.department)

    def _require_read(self, record: SessionRecord) -> policy.ActorContext:
        actor = policy.actor_from_session(record.user, record.scope)
        decision = policy.decide(actor, ACTION_READ)
        if not decision.allowed:
            raise ComisionesError(403, "DENIED", denial_message(decision, ACTION_READ))
        return actor

    def _read(self, scope: Scope, fn: Callable[[Lector], Any]) -> Any:
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                return fn(Lector(ComisionesRepository(conn, scope.institution_id, scope.department_id), self.today()))
        except ComisionesError:
            raise
        except Exception as exc:
            log.error("comisiones: lectura fallida: %s", type(exc).__name__)
            raise ComisionesError(503, "DB_READ", MSG_DB_READ) from None

    def reader(self, record: SessionRecord) -> Scope:
        scope = self.scope(record)
        self._require_read(record)
        return scope

    # ------------------------------------------------------------------ B10 + B12H + B12I por writer
    def _separate(self, op: audit.Operation, outcome: str, *, error_code: Optional[str] = None,
                  metadata: Optional[dict] = None) -> bool:
        mode = audit.MODE_POST_OPERATION if outcome == audit.OUTCOME_SUCCESS else audit.MODE_SEPARATE
        try:
            self.audit_store.append_separate(op.event(outcome, mode, error_code=error_code, metadata=metadata))
            return True
        except Exception as exc:
            log.error("B12H: el evento %s de %s no pudo persistirse (%s)", outcome, op.name, audit.error_code_of(exc))
            return False

    @contextmanager
    def _consistency_lock(self, scope: Scope) -> Iterator[None]:
        """B12I capa T: ``pg_try_advisory_lock`` de sesion en conexion dedicada, espera acotada, unlock al final."""
        key = COMMISSION_LOCK_FORMAT.format(inst=scope.institution_id, dep=scope.department_id)
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
                        raise ComisionesError(409, "LOCK", f"{MSG_LOCK} [B12I: {LOCK_FAMILY}]", "ConsistencyLockError")
                    self.sleep(LOCK_POLL_SECONDS)
                yield
            finally:
                if acquired:
                    try:
                        conn.execute(SESSION_UNLOCK_SQL, [key])
                        conn.commit()
                    except Exception:
                        conn.close()  # sesion descartada: PostgreSQL libera sus locks al cerrarla

    def _op(self, record: SessionRecord, scope: Scope, spec: WriterSpec, fn: Callable[[E.Unidad], Any], *,
            entity_raw: Any = None, stale: Optional[Callable[[], None]] = None) -> tuple[Any, list[str]]:
        """Un writer certificado completo: B10 -> B12I (T y U) -> sus COMMITs con SUCCESS, o FAILED."""
        actor = policy.actor_from_session(record.user, record.scope)
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(spec.name, spec.action, spec.entity_type, audit_actor, spec.entity_param, entity_raw)
        decision = policy.decide(actor, spec.action)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code, metadata={"b10_decision": decision.code})
            raise ComisionesError(403, "DENIED", denial_message(decision, spec.action), "PermissionError")
        unidad = E.Unidad(self._transaction, op, scope.institution_id, scope.department_id, today=self.today(),
                          now=self.now(), usuario=str(record.user.get("email") or ""))

        def run():
            if stale is not None:
                stale()
            return fn(unidad)
        try:
            if spec.name in LOCK_WRITERS:
                with self._consistency_lock(scope):
                    result = run()
            else:
                result = run()
        except ComisionesError as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code=exc.error_class,
                           metadata={"coupled_commits": op.coupled_commits})
            raise
        except ValueError as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code="ValueError",
                           metadata={"coupled_commits": op.coupled_commits})
            raise ComisionesError(422, "REJECTED", str(exc)) from None
        except E.AuditoriaFallida:
            self._separate(op, audit.OUTCOME_FAILED, error_code="AuditPersistenceError:AUDIT_INSERT_FAILED",
                           metadata={"coupled_commits": op.coupled_commits})
            raise ComisionesError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]",
                                  "AuditPersistenceError") from None
        except Exception as exc:
            log.error("comisiones: %s falló tras %d COMMIT(s): %s", spec.name, op.coupled_commits, type(exc).__name__)
            self._separate(op, audit.OUTCOME_FAILED, error_code=audit.error_code_of(exc),
                           metadata={"coupled_commits": op.coupled_commits})
            raise ComisionesError(503, "DB_ERROR", MSG_DB_TRANSACTION) from None
        if op.coupled_commits == 0:
            if not self._separate(op, audit.OUTCOME_SUCCESS,
                                  metadata={"coupled_commits": 0, "post_reason": "NO_POOLED_COMMIT"}):
                raise ComisionesError(503, "AUDIT", MSG_AUDIT_POST)
        return result, unidad.avisos

    def _stale(self, scope: Scope, esperado: Any, fresh: Callable[[Lector], Any], label: str) -> Callable[[], None]:
        """B12I capa U: lo que el usuario vio se relee fresco antes del primer SQL del writer."""
        def check() -> None:
            try:
                actual = self._read(scope, fresh)
            except ComisionesError:
                raise ComisionesError(503, "FRESH_READ", MSG_DB_READ, "FreshReadError") from None
            if _hash(actual) != esperado:
                raise ComisionesError(409, "STALE", f"{MSG_STALE} [B12I: {label}]", "StaleDecisionError")
        return check

    # ------------------------------------------------------------------ compuertas de periodo (l. 70030-70060)
    @staticmethod
    def _gates(L: Lector) -> dict:
        abierto, actual = L.periodo_abierto(), L.ultimo_periodo()
        puede_operar, _, _, motivo = R.puede_operar_comisiones_periodo_actual(abierto, actual)
        puede_corregir, periodo_correccion, motivo_corr = R.puede_corregir_comisiones_periodo_abierto(abierto)
        hist_abierto = bool(abierto and actual and int(abierto["id"]) != int(actual["id"]))
        return {"abierto": abierto, "actual": actual, "puede_operar": puede_operar, "motivo_bloqueo": motivo,
                "puede_corregir": puede_corregir, "periodo_correccion": periodo_correccion,
                "motivo_correccion": motivo_corr, "historico_abierto": hist_abierto}

    @staticmethod
    def _huella_gates(g: dict) -> str:
        return _hash({"abierto": _period(g["abierto"]), "actual": _period(g["actual"])})

    # ------------------------------------------------------------------ huellas de lo que el usuario ve
    @staticmethod
    def comision_vista(L: Lector, comision_id: int) -> Optional[dict]:
        """Foto de una comision (fila, horarios, asignaciones y franjas) para la huella B12I."""
        df = L.comisiones(periodo_id=None, solo_activas=False)
        fila = df[pd.to_numeric(df["id"], errors="coerce").eq(int(comision_id))] if not df.empty else df
        if fila.empty:
            return None
        asign = L.asignaciones_comision(comision_id)
        reales = {int(a): records(L.horarios_reales_asignacion(int(a)))
                  for a in (asign["id"].tolist() if not asign.empty and "id" in asign.columns else [])}
        return {"fila": records(fila)[0], "horarios": records(L.horarios_comision(comision_id)),
                "asignaciones": records(asign), "reales": reales,
                "materias": L.materias_conceptuales_comision_v122(comision_id)}

    def huella_comision(self, L: Lector, comision_id: int) -> Optional[str]:
        vista = self.comision_vista(L, comision_id)
        return None if vista is None else _hash(vista)

    # ------------------------------------------------------------------ overview
    def overview(self, record: SessionRecord) -> dict:
        scope = self.scope(record)
        actor = self._require_read(record)

        def read(L: Lector) -> dict:
            g = self._gates(L)
            return {"g": g, "periodos": L.repo.periods(), "sedes": L.opciones_sedes_comision()}

        data = self._read(scope, read)
        g = data["g"]
        decide = lambda action: policy.decide(actor, action).allowed  # noqa: E731
        return {
            "contexto": {"institucion": _named(scope.institution), "departamento": _named(scope.department)},
            "periodos": [_period(p) for p in data["periodos"]],
            "abierto": _period(g["abierto"]), "actual": _period(g["actual"]),
            "puede_operar": g["puede_operar"], "motivo_bloqueo": g["motivo_bloqueo"],
            "puede_corregir": g["puede_corregir"], "motivo_correccion": g["motivo_correccion"],
            "periodo_correccion": _period(g["periodo_correccion"]), "historico_abierto": g["historico_abierto"],
            "huella_periodos": self._huella_gates(g),
            "catalogos": {"turnos": R.TURNOS_COMISION, "modalidades": R.MODALIDADES_COMISION, "dias": R.DIAS_SEMANA,
                          "roles": R.ROLES_DOCENTE_COMISION, "sedes": data["sedes"], "estados_sede": R.ESTADOS_SEDE},
            "permisos": {"puede_escribir": decide(ACTION_WRITE), "puede_borrar": decide(ACTION_DELETE),
                         "puede_escribir_sedes": decide(ACTION_WRITE_INST),
                         "puede_borrar_sedes": decide(ACTION_DELETE_INST),
                         "puede_movimiento": decide(ACTION_MOVEMENT)},
        }

    # ------------------------------------------------------------------ pestaña 1: comisiones del periodo
    COLUMNAS_INTEGRADAS = [
        "periodo", "escuela", "carrera", "plan_version", "codigo_materia", "asignatura", "materia_especifica",
        "anio", "cuatrimestre", "carga_semanal", "carga_total",
        "nombre_comision", "turno", "sede", "modalidad", "estado", "alumnos_conjunto",
        "horarios", "horas_semanales_horario", "cantidad_docentes", "docentes_asignados_detalle",
        "modificaciones_asignaciones_periodo", "observaciones",
    ]

    def periodo(self, record: SessionRecord, periodo_id: Any) -> dict:
        scope = self.reader(record)
        pid = _id(periodo_id)

        def read(L: Lector) -> dict:
            if L.periodo_info(pid) is None:
                raise ComisionesError(404, "NOT_FOUND", MSG_PERIODO_NO_ENCONTRADO)
            df_com = L.comisiones(periodo_id=pid, solo_activas=False)
            if df_com.empty:
                return {"vacio": True}
            df_integrado = L.comisiones_integradas_periodo(pid)
            df_ins = L.inscriptos_comisiones_periodo(pid)
            if not df_ins.empty and "comision_id" in df_ins.columns:
                df_totales = (df_ins[["comision_id", "total_comision"]].drop_duplicates(subset=["comision_id"])
                              .rename(columns={"comision_id": "id", "total_comision": "alumnos_conjunto"})) \
                    if "total_comision" in df_ins.columns else pd.DataFrame()
                if not df_totales.empty:
                    df_integrado = df_integrado.merge(df_totales, on="id", how="left")
            if "alumnos_conjunto" not in df_integrado.columns:
                df_integrado["alumnos_conjunto"] = 0
            df_integrado["alumnos_conjunto"] = pd.to_numeric(df_integrado["alumnos_conjunto"], errors="coerce").fillna(0).astype(int)
            total_alumnos = L.total_inscriptos_asignaturas_periodo_v248(pid)
            horas = float(pd.to_numeric(df_integrado.get('horas_semanales_horario', pd.Series(dtype=float)),
                                        errors='coerce').fillna(0).sum())
            docentes = int(pd.to_numeric(df_integrado.get('cantidad_docentes', pd.Series(dtype=float)),
                                         errors='coerce').fillna(0).sum())
            caption = (f"Total comisiones: {len(df_integrado)} | Horas semanales cargadas por horarios: {horas} | "
                       f"Docentes asignados únicos por comisión: {docentes} | "
                       f"Alumnos inscriptos del período (sin duplicar por comisión): {int(total_alumnos)}")
            df_h = L.horarios_comisiones_periodo(pid)
            df_a = L.asignaciones_comisiones_periodo(pid)
            caption_h = (f"Total horarios: {len(df_h)} | Horas semanales cargadas: "
                         f"{float(pd.to_numeric(df_h['horas'], errors='coerce').fillna(0).sum())}") if not df_h.empty else ""
            return {"vacio": False, "filas": records(df_integrado, self.COLUMNAS_INTEGRADAS), "caption": caption,
                    "horarios": records(df_h), "caption_horarios": caption_h, "asignaciones": records(df_a),
                    "caption_asignaciones": f"Total asignaciones docentes: {len(df_a)}" if not df_a.empty else ""}

        return self._read(scope, read)

    # ------------------------------------------------------------------ pestaña alertas
    def alertas(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(L: Lector) -> dict:
            g = self._gates(L)
            periodo = g["abierto"] or g["actual"]
            if periodo is None:
                return {"periodo": None}
            return {"periodo": _period(periodo), "superposiciones": records(L.superposiciones_periodo(periodo["id"])),
                    "sin_docentes": records(L.comisiones_sin_docentes_periodo(periodo["id"]))}

        return self._read(scope, read)

    # ------------------------------------------------------------------ pestaña sedes
    def sedes(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(L: Lector) -> dict:
            df = L.sedes_institucionales(solo_activas=False)
            filas = records(df)
            for f in filas:
                f["huella"] = _hash(f)
            activas = df[df["estado"].fillna("Activa").astype(str).eq("Activa")] if not df.empty else df
            return {"sedes": filas, "activas": 0 if activas is None else len(activas),
                    "opciones": len(L.opciones_sedes_comision())}

        return self._read(scope, read)

    # ------------------------------------------------------------------ pestaña inscriptos
    COLUMNAS_INSCRIPTOS = [
        "codigo_materia", "asignatura", "asignatura_base", "materia_especifica",
        "cantidad", "cantidad_final", "cantidad_comisiones", "comisiones_relacionadas",
        "combinaciones_relacionadas", "carrera", "escuela",
        "fecha_actualizacion", "fecha_actualizacion_final", "observaciones_inscriptos",
    ]

    @staticmethod
    def _fila_inscriptos_clave(row: dict) -> str:
        return f"{int(row.get('materia_id_inscriptos'))}:{R.opcion_id_inscriptos_v248(row.get('opcion_curricular_id_inscriptos'))}"

    def inscriptos(self, record: SessionRecord, periodo_id: Any) -> dict:
        scope = self.reader(record)
        pid = _id(periodo_id)

        def read(L: Lector) -> dict:
            if L.periodo_info(pid) is None:
                raise ComisionesError(404, "NOT_FOUND", MSG_PERIODO_NO_ENCONTRADO)
            df = L.inscriptos_asignaturas_periodo_v248(pid)
            legacy = L.legacy_inscriptos_sin_discriminar_v248(pid)
            out = {"legacy": records(legacy), "vacio": df.empty}
            if df.empty:
                return out
            total_alumnos = int(pd.to_numeric(df.get("cantidad"), errors="coerce").fillna(0).sum())
            grupos = L.analisis_alumnos_por_docente_grupos_v248(pid)
            docs = L.docentes_comisiones_periodo_v248(pid)
            total_docs = int(docs.get("_cuil_v248", pd.Series(dtype=str)).nunique()) \
                if isinstance(docs, pd.DataFrame) and not docs.empty else 0
            total_com = int(pd.to_numeric(grupos.get("cantidad_comisiones", pd.Series(dtype=float)), errors="coerce")
                            .fillna(0).sum()) if isinstance(grupos, pd.DataFrame) and not grupos.empty else 0
            editor = df.copy()
            editor["cantidad"] = pd.to_numeric(editor.get("cantidad", 0), errors="coerce").fillna(0).astype(int)
            filas = []
            for r in records(editor):
                r["clave"] = self._fila_inscriptos_clave(r)
                r["huella"] = _hash({k: r.get(k) for k in ("cantidad", "cantidad_final", "observaciones_inscriptos",
                                                           "fecha_actualizacion", "fecha_actualizacion_final")})
                filas.append(r)
            hist = L.historial_inscriptos_materias()
            hist_comb = L.historial_inscriptos_por_cuatrimestre() if not hist.empty else pd.DataFrame()
            out.update({
                "metricas": {"asignaturas": len(df), "alumnos": total_alumnos, "comisiones": total_com,
                             "docentes": total_docs},
                "filas": filas, "columnas": self.COLUMNAS_INSCRIPTOS,
                "grupos": records(grupos.drop(columns=["clave_combinacion"], errors="ignore")
                                  if isinstance(grupos, pd.DataFrame) else grupos),
                "historial": records(hist),
                "historial_combinaciones": records(hist_comb.drop(columns=["clave_combinacion"], errors="ignore")
                                                   if isinstance(hist_comb, pd.DataFrame) else hist_comb),
            })
            return out

        return self._read(scope, read)

    # ================================================================== utilidades de pantalla (lecturas frescas)
    @staticmethod
    def _filas(df: Optional[pd.DataFrame]) -> list[dict]:
        """Filas con los tipos que ve el certificado (para textos ``f"{valor}"``), sin pasar por JSON."""
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return []
        return df.to_dict(orient="records")

    @staticmethod
    def _fila_por_id(df: Optional[pd.DataFrame], valor: int, col: str = "id") -> Optional[dict]:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty or col not in df.columns:
            return None
        sel = df[pd.to_numeric(df[col], errors="coerce").eq(int(valor))]
        return None if sel.empty else sel.iloc[0].to_dict()

    @staticmethod
    def _fila_por_cuil(df: Optional[pd.DataFrame], cuil: str) -> Optional[dict]:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty or "cuil" not in df.columns:
            return None
        sel = df[df["cuil"].astype(str).eq(str(cuil))]
        return None if sel.empty else sel.iloc[0].to_dict()

    @staticmethod
    def _rol(roles: list, enviado: Any) -> str:
        """Cargo de la pantalla: uno solo -> automatico; varios -> uno de ellos; ninguno -> catalogo."""
        if len(roles) == 1:
            return roles[0]
        return _opcion(enviado, list(roles) if len(roles) > 1 else list(R.ROLES_DOCENTE_COMISION))

    @staticmethod
    def _seleccion(valor: Any, n: int) -> list[dict]:
        """Casillas de ``formulario_horarios_reales_asignacion``: una por horario de la comision."""
        if not isinstance(valor, list) or len(valor) != n:
            raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        out = []
        for item in valor:
            if not isinstance(item, dict) or not isinstance(item.get("usar"), bool):
                raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            out.append({"usar": item["usar"], "desde": _hora(item.get("desde")), "hasta": _hora(item.get("hasta"))})
        return out

    @staticmethod
    def _franjas(fuente, seleccion: list[dict]) -> tuple[list, float]:
        resultado, horas, _ = R.horarios_reales_desde_seleccion_v95(fuente, seleccion)
        return resultado, horas

    @staticmethod
    def _horarios_form(valor: Any) -> list[dict]:
        if not isinstance(valor, list) or not 1 <= len(valor) <= 7:
            raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        out = []
        for h in valor:
            if not isinstance(h, dict):
                raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            dia = _opcion(h.get("dia"), R.DIAS_SEMANA)
            hi, hf = _hora(h.get("hora_inicio")), _hora(h.get("hora_fin"))
            out.append({"dia": dia, "hora_inicio": hi, "hora_fin": hf, "horas": R.calcular_horas_desde_texto(hi, hf)})
        return out

    @staticmethod
    def _docente_label(row: dict) -> str:
        """Etiqueta del multiselect de "Abrir comisión" (l. 70448)."""
        prestado = (str(row.get('tipo_docente', 'Propio')).strip() == 'Prestado'
                    and str(row.get('departamento_origen', '')).strip())
        return (f"{row['nombre_completo']} - {row['cuil']} "
                f"({row.get('horas_designadas', 0)} hs designadas - {row.get('tipo_docente', 'Propio')}"
                f"{(' desde ' + str(row.get('departamento_origen'))) if prestado else ''})")

    def _asignacion_duplicada(self, scope: Scope, comision_id: int, cuil: str) -> bool:
        sql = E.ASIGNACION_DUP_SQL.replace("{excluir}", "")
        return self._read(scope, lambda L: not L.repo.read_sql(sql, [comision_id, cuil] + L.repo._scope).empty)

    def _horario_duplicado(self, scope: Scope, comision_id: int, dia: str, hi: str, hf: str) -> bool:
        sql = E.HORARIO_DUP_SQL.replace("{excluir}", "")
        return self._read(scope, lambda L: not L.repo.read_sql(sql, [comision_id, dia, hi, hf] + L.repo._scope).empty)

    def _stale_huella(self, scope: Scope, esperado: Any, fresh: Callable[[Lector], Any], label: str):
        if not isinstance(esperado, str) or not esperado:
            raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        return self._stale(scope, esperado, fresh, label)

    @staticmethod
    def _docentes_opciones(df: pd.DataFrame) -> list[dict]:
        cols = ["cuil", "nombre_completo", "tipo_docente", "cargo", "dedicacion", "horas_designadas",
                "departamento_origen"]
        filas = records(df, cols)
        for f, row in zip(filas, ComisionesService._filas(df)):
            f["etiqueta_alta"] = ComisionesService._docente_label(row)
            f["etiqueta_cambio"] = (f"{row['nombre_completo']} - {row['cuil']} ({row.get('tipo_docente', 'Propio')}; "
                                    f"{row.get('horas_designadas', 0)} hs)")
        return filas

    # ================================================================== pestaña 2: abrir comisión (lecturas)
    def _gate_operar(self, g: dict, msg_operar: str, msg_actual: str, tono_actual: str = "warning") -> dict:
        if not g["puede_operar"]:
            raise ComisionesError(409, "NO_OPERAR", msg_operar, tone="warning")
        if g["actual"] is None:
            raise ComisionesError(409, "NO_PERIODO", msg_actual, tone=tono_actual)
        return g["actual"]

    def abrir_materias(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        filtros = {k: _text(data.get(k)) for k in ("codigo", "nombre", "cuatrimestre", "escuela", "carrera")}

        def read(L: Lector) -> dict:
            self._gate_operar(self._gates(L), MSG_NO_OPERAR_ALTA, MSG_NO_PERIODO_ACTUAL_ALTA)
            df = L.materias_para_comisiones()
            if df.empty:
                raise ComisionesError(409, "SIN_MATERIAS", "Primero cargá materias en los planes de estudio.",
                                      tone="warning")
            cuats = ["Todos"] + sorted([str(x).strip() for x in df["cuatrimestre"].dropna().unique() if str(x).strip()])
            escuelas = ["Todas"] + sorted([str(x).strip() for x in df["escuela"].dropna().unique() if str(x).strip()])
            escuela = filtros["escuela"] or "Todas"
            cuat = filtros["cuatrimestre"] or "Todos"
            base = df.copy()
            if escuela != "Todas":
                base = base[base["escuela"].astype(str).str.strip() == escuela]
            carreras = ["Todas"] + sorted([str(x).strip() for x in base["carrera"].dropna().unique() if str(x).strip()])
            carrera = filtros["carrera"] or "Todas"
            filtrado = R.filtrar_materias_para_comisiones(df, codigo_parcial=filtros["codigo"],
                                                          nombre_parcial=filtros["nombre"], cuatrimestre=cuat,
                                                          escuela=escuela, carrera=carrera)
            cols = ["materia_id", "codigo", "asignatura", "carrera", "escuela", "plan_version", "anio", "cuatrimestre",
                    "carga_semanal"]
            return {"cuatrimestres": cuats, "escuelas": escuelas, "carreras": carreras,
                    "caption": f"Materias encontradas: {len(filtrado)}", "materias": records(filtrado, cols)}

        return self._read(scope, read)

    @staticmethod
    def _adicionales_df(df_materias: pd.DataFrame, codigo: str, asignatura: str) -> pd.DataFrame:
        clave_principal = R.clave_materia_unica_codigo_nombre(codigo, asignatura)
        df = df_materias.copy()
        if not df.empty:
            claves = df.apply(lambda r: R.clave_materia_unica_codigo_nombre(r.get("codigo", ""), r.get("asignatura", "")),
                              axis=1)
            no_oe = ~df.apply(lambda r: R.es_materia_optativa_electiva(r.get("codigo", ""), r.get("asignatura", "")),
                              axis=1)
            df = df[(claves != clave_principal) & no_oe].copy()
        return df

    def _abrir_materia(self, L: Lector, materia_id: int, adicionales: list[int]) -> dict:
        df_materias = L.materias_para_comisiones()
        if df_materias.empty:
            raise ComisionesError(409, "SIN_MATERIAS", "Primero cargá materias en los planes de estudio.", tone="warning")
        if self._fila_por_id(df_materias, materia_id, "materia_id") is None:
            raise ComisionesError(404, "NOT_FOUND", MSG_SELECCION_INVALIDA)
        info = L.materia_comision(materia_id) or {}
        codigo = R.limpiar_texto_tabla(info.get("codigo", ""))
        asignatura = R.limpiar_texto_tabla(info.get("asignatura", ""))
        es_oe = R.es_materia_optativa_electiva(codigo, asignatura)
        out = {"es_oe": es_oe, "codigo": codigo, "asignatura": asignatura, "adicionales": [], "resumen": [],
               "info_multicodigo": "", "info_compartida": "", "tipo_espacio": ""}
        if not es_oe:
            opciones = R.opciones_desde_df_materias_comisiones(self._adicionales_df(df_materias, codigo, asignatura))
            validos = set(int(v) for v in opciones.values())
            if any(a not in validos for a in adicionales):
                raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            out["adicionales"] = [{"etiqueta": k, "materia_id": int(v)} for k, v in opciones.items()]
            if adicionales:
                sel = L.materias_conceptuales_seleccionadas_v122(materia_id, adicionales)
                out["info_multicodigo"] = f"Comisión multicódigo: quedará asociada a {len(sel)} códigos/materias."
                out["resumen"] = [{"Código": x.get("codigo", ""), "Asignatura": x.get("asignatura", ""),
                                   "Carrera/s": R.limpiar_texto_tabla(x.get("info", {}).get("carrera", "")),
                                   "Plan/es": R.limpiar_texto_tabla(x.get("info", {}).get("plan_version", ""))}
                                  for x in sel]
            try:
                vinc = L.preparar_vinculos_multiples_materias_comision_v122(materia_id, adicionales,
                                                                            incluir_historicas=False)
                carreras = R.deptit_join_unicos([v.get("carrera_snapshot", "") for v in vinc], sep=" / ")
                planes = R.deptit_join_unicos([v.get("plan_version_snapshot", "") for v in vinc], sep=" / ")
                if len(vinc) > 1:
                    texto = (f"Esta materia está en {len(vinc)} apariciones de plan activas. "
                             "Se abrirá una sola comisión compartida y quedarán guardadas explícitamente esas pertenencias.")
                    if carreras:
                        texto += f" Carrera/s: {carreras}."
                    if planes:
                        texto += f" Plan/es: {planes}."
                    out["info_compartida"] = texto
            except Exception:
                pass
        else:
            if adicionales:
                raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            out["tipo_espacio"] = R.tipo_espacio_curricular_v120(codigo, asignatura)
        return out

    def abrir_materia(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        mid = _id(data.get("materia_id"))
        adicionales = _ids(data.get("adicionales"))
        buscar = _text(data.get("buscar_opcion"))
        opcion = _opt_id(data.get("opcion_curricular_id"))

        def read(L: Lector) -> dict:
            self._gate_operar(self._gates(L), MSG_NO_OPERAR_ALTA, MSG_NO_PERIODO_ACTUAL_ALTA)
            out = self._abrir_materia(L, mid, adicionales)
            if out["es_oe"]:
                df_op = L.opciones_curriculares_para_materia_v120(mid)
                df_op = R.filtrar_dataframe_por_texto(
                    df_op, buscar, ["codigo", "nombre", "escuela_oferente", "carreras_habilitadas", "espacios_plan"])
                out["opciones"] = records(df_op, ["id", "codigo", "nombre", "tipo", "escuela_oferente",
                                                  "carreras_habilitadas", "espacios_plan"])
                if opcion is not None:
                    vinc = L.vinculos_opcion_para_espacio_seleccionado_v128(mid, opcion, solo_vigentes=True)
                    out["vinculos_opcion"] = records(vinc, ["codigo", "asignatura", "carrera", "escuela", "plan_version",
                                                            "anio", "cuatrimestre"])
            return out

        return self._read(scope, read)

    def docentes(self, record: SessionRecord, data: dict) -> dict:
        """Docentes disponibles: periodo actual (Abrir / Modificación) o periodo de corrección (Editar)."""
        scope = self.reader(record)
        contexto = _opcion(data.get("contexto"), ["actual", "correccion"])

        def read(L: Lector) -> dict:
            g = self._gates(L)
            periodo = g["actual"] if contexto == "actual" else (g["periodo_correccion"] if g["puede_corregir"] else None)
            if periodo is None:
                raise ComisionesError(409, "NO_PERIODO", MSG_NO_CORREGIR if contexto == "correccion"
                                      else MSG_NO_PERIODO_ACTUAL_ALTA, tone="warning")
            return {"periodo": _period(periodo),
                    "docentes": self._docentes_opciones(L.docentes_activos_para_comisiones(int(periodo["id"])))}

        return self._read(scope, read)

    def docente_roles(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        contexto = _opcion(data.get("contexto"), ["actual", "correccion"])
        cuil = _text(data.get("cuil")).strip()

        def read(L: Lector) -> dict:
            g = self._gates(L)
            periodo = g["actual"] if contexto == "actual" else (g["periodo_correccion"] if g["puede_corregir"] else None)
            if periodo is None or not cuil:
                raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            return {"roles": L.roles_docente_periodo(cuil, int(periodo["id"])),
                    "prestado_local": bool(L.es_docente_prestado_local(cuil))}

        return self._read(scope, read)

    # ================================================================== pestaña 2: abrir comisión (escritura)
    def abrir(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        mid = _id(data.get("materia_id"))
        adicionales = _ids(data.get("adicionales"))
        opcion_id = _opt_id(data.get("opcion_curricular_id"))
        nombre = _text(data.get("nombre"))
        turno = _opcion(data.get("turno"), R.TURNOS_COMISION)
        modalidad = _opcion(data.get("modalidad"), R.MODALIDADES_COMISION)
        fecha_apertura = _fecha(data.get("fecha_apertura"))
        obs_com = _text(data.get("observaciones"))
        obs_asig = _text(data.get("observaciones_asignaciones"))
        horarios = self._horarios_form(data.get("horarios"))
        docentes_in = data.get("docentes") or []
        if not isinstance(docentes_in, list):
            raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)

        def screen(L: Lector) -> dict:
            g = self._gates(L)
            actual = self._gate_operar(g, MSG_NO_OPERAR_ALTA, MSG_NO_PERIODO_ACTUAL_ALTA)
            m = self._abrir_materia(L, mid, adicionales)
            sede = _opcion(data.get("sede"), L.opciones_sedes_comision())
            materia_especifica, opcion_lista = "", not m["es_oe"]
            if m["es_oe"] and opcion_id is not None:
                fila_op = self._fila_por_id(L.opciones_curriculares_para_materia_v120(mid), opcion_id)
                if fila_op is None:
                    raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
                materia_especifica, opcion_lista = R.limpiar_texto_tabla(fila_op.get("nombre", "")), True
            elif not m["es_oe"] and opcion_id is not None:
                raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            df_doc = L.docentes_activos_para_comisiones(int(actual["id"]))
            configurados = []
            for d in docentes_in:
                if not isinstance(d, dict):
                    raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
                fila = self._fila_por_cuil(df_doc, _text(d.get("cuil")))
                if fila is None:
                    raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
                cuil = fila["cuil"]
                rol = self._rol(L.roles_docente_periodo(cuil, int(actual["id"])), d.get("rol"))
                reales, horas = self._franjas(horarios, self._seleccion(d.get("franjas"), len(horarios)))
                configurados.append({"etiqueta": self._docente_label(fila), "cuil": cuil, "rol": rol,
                                     "horarios_reales": reales, "horas_reales": horas})
            nombre_limpio = str(nombre or "").strip()
            duplicada = (not L.existe_comision_duplicada(
                actual["id"], mid, nombre_limpio, turno, sede, modalidad, opcion_curricular_id=opcion_id,
                materia_especifica=materia_especifica, materia_ids_adicionales=adicionales).empty
            ) if nombre_limpio and opcion_lista else False
            return {"g": g, "actual": actual, "es_oe": m["es_oe"], "sede": sede, "opcion_lista": opcion_lista,
                    "materia_especifica": materia_especifica, "docentes": configurados, "duplicada": duplicada,
                    "nombre": nombre_limpio}

        s = self._read(scope, screen)
        actual, docentes = s["actual"], s["docentes"]
        horas_totales = float(sum(float(h.get("horas", 0) or 0) for h in horarios))
        claves = [(str(h["dia"]).strip().lower(), h["hora_inicio"], h["hora_fin"]) for h in horarios]
        cuiles = [str(d.get("cuil") or "").strip() for d in docentes]
        error = None
        if not s["nombre"]:
            error = "Indicá el nombre o número de comisión."
        elif s["es_oe"] and not s["opcion_lista"]:
            error = "Seleccioná la opción curricular concreta que se dictará en esta comisión."
        elif s["duplicada"]:
            error = "La comisión ya existe."
        elif [h for h in horarios if float(h.get("horas", 0) or 0) <= 0]:
            error = "Hay uno o más horarios inválidos. Revisá las horas de inicio y finalización."
        elif len(claves) != len(set(claves)):
            error = "Hay horarios repetidos dentro de la nueva comisión."
        elif horas_totales <= 0:
            error = "La carga horaria total debe ser mayor que cero."
        elif not docentes:
            error = "Seleccioná al menos un docente para abrir la comisión completa."
        elif [d for d in docentes if float(d.get("horas_reales", 0) or 0) <= 0]:
            error = "Cada docente seleccionado debe cubrir al menos una franja horaria válida de la comisión."
        elif len(cuiles) != len(set(cuiles)):
            error = "Un mismo docente fue seleccionado más de una vez."
        if error:
            raise ComisionesError(422, "VALIDATION", error)

        huella = data.get("huella_periodos")
        stale = self._stale_huella(scope, huella, lambda L: {"abierto": _period(L.periodo_abierto()),
                                                             "actual": _period(L.ultimo_periodo())},
                                   "get_periodo_abierto")
        pid, nombre_c = int(actual["id"]), s["nombre"]
        avisos: list[str] = []
        nuevo_id = None
        alertas = 0
        try:
            nuevo_id, av = self._op(record, scope, SPEC_GUARDAR_COMISION, lambda u: E.guardar_comision(
                u, pid, mid, nombre_c, turno, s["sede"], modalidad, "Activa", obs_com, fecha_apertura,
                materia_especifica=s["materia_especifica"] if s["es_oe"] else "", opcion_curricular_id=opcion_id,
                materia_ids_adicionales=adicionales), entity_raw=mid, stale=stale)
            avisos += av
            for h in horarios:
                _, av = self._op(record, scope, SPEC_GUARDAR_HORARIO, lambda u: E.guardar_horario_comision(
                    u, nuevo_id, h["dia"], h["hora_inicio"], h["hora_fin"], "Cargado al abrir la comisión."),
                    entity_raw=nuevo_id)
                avisos += av
            movimientos_docentes = []
            for cfg in docentes:
                sup = self._read(scope, lambda L: L.detectar_superposiciones_horarios_candidato(
                    cfg["cuil"], pid, cfg.get("horarios_reales", []), excluir_comision_id=nuevo_id))
                obs_doc = str(obs_asig or "").strip()
                if not sup.empty:
                    alertas += 1
                    obs_doc = (obs_doc + " | " if obs_doc else "") + "ALERTA: asignación con superposición horaria detectada."
                if self._read(scope, lambda L: L.es_docente_prestado_local(cfg["cuil"])):
                    obs_doc = (obs_doc + " | " if obs_doc else "") + "Docente prestado: asignado sin designación local."
                _, av = self._op(record, scope, SPEC_GUARDAR_ASIGNACION, lambda u: E.guardar_asignacion_docente_comision(
                    u, nuevo_id, cfg["cuil"], cfg["rol"], cfg.get("horas_reales", 0), "Activa", obs_doc,
                    horarios_reales=cfg.get("horarios_reales", [])), entity_raw=nuevo_id)
                avisos += av
                movimientos_docentes.append((cfg, obs_doc))
            descripcion = self._read(scope, lambda L: L.descripcion_materias_comision_v122(mid, adicionales))
            self._op(record, scope, SPEC_MOVIMIENTO, lambda u: E.registrar_movimiento(
                u, "Apertura de comisión", "", "",
                (f"Se abrió comisión {nombre_c} para {descripcion or 'materia'} en {actual['nombre']}, "
                 f"con {len(horarios)} horario/s y {len(docentes)} docente/s."), obs_com, pid), entity_raw="")
            for cfg, obs_doc in movimientos_docentes:
                self._op(record, scope, SPEC_MOVIMIENTO, lambda u: E.registrar_movimiento(
                    u, "Asignación docente a comisión", cfg["cuil"], cfg["etiqueta"],
                    (f"Se asignó a la comisión {nombre_c} como {cfg['rol']} "
                     f"({float(cfg.get('horas_reales', 0) or 0):g} hs)."), obs_doc, pid), entity_raw=cfg["cuil"])
        except ComisionesError as exc:
            if nuevo_id is not None:
                try:
                    self._op(record, scope, SPEC_COMPENSACION,
                             lambda u: E.revertir_alta_comision_incompleta(u, nuevo_id), entity_raw=nuevo_id)
                except Exception:
                    pass
            raise ComisionesError(exc.status, exc.code, f"No se pudo abrir la comisión completa: {exc.message}",
                                  exc.error_class) from None
        if alertas:
            return {"mensaje": (f"Comisión abierta correctamente. Se detectaron {alertas} "
                                "asignación/es con posible superposición horaria."), "tono": "warning",
                    "avisos": avisos, "id": nuevo_id}
        return {"mensaje": "Comisión abierta correctamente con todos sus horarios y docentes asignados.",
                "tono": "success", "avisos": avisos, "id": nuevo_id}

    # ================================================================== detalle de una comisión (pestañas 4 y 7)
    def _contexto_comisiones(self, L: Lector, contexto: str) -> tuple[dict, Optional[dict], pd.DataFrame, dict]:
        """(gates, periodo de la pestaña, tabla de comisiones, opciones label->id) como en la pantalla certificada."""
        g = self._gates(L)
        if contexto == "modificacion":
            actual = self._gate_operar(g, MSG_NO_OPERAR_CAMBIO, MSG_NO_PERIODO_CAMBIO, tono_actual="info")
            df = L.comisiones_integradas_periodo(actual["id"])
            if df.empty:
                raise ComisionesError(409, "SIN_COMISIONES", "No hay comisiones en el período actual para registrar "
                                      "modificaciones de asignaciones.", tone="info")
            opciones = {R.label_comision_desde_row(row): int(row["id"]) for _, row in df.iterrows()}
            return g, actual, df, opciones
        periodo = g["periodo_correccion"] if g["puede_corregir"] else None
        opciones, df = L.opciones_comisiones(periodo_id=periodo["id"] if periodo else None, solo_activas=False)
        return g, periodo, df, opciones

    def _vista_comision_ctx(self, L: Lector, contexto: str, comision_id: int) -> dict:
        """Lo que el usuario ve de la comision seleccionada (B12I capa U): compuertas, fila y detalle."""
        g, periodo, df, _ = self._contexto_comisiones(L, contexto)
        fila = self._fila_por_id(df, comision_id)
        return {"g": self._huella_gates(g), "fila": _clean(fila) if fila else None,
                "vista": self.comision_vista(L, comision_id)}

    def comisiones_lista(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        contexto = _opcion(data.get("contexto"), ["modificacion", "edicion"])
        busqueda = _text(data.get("busqueda"))

        def read(L: Lector) -> dict:
            g, periodo, df, opciones = self._contexto_comisiones(L, contexto)
            out = {"periodo": _period(periodo), "historico_abierto": g["historico_abierto"],
                   "puede_corregir": g["puede_corregir"]}
            if contexto == "edicion" and not opciones:
                return {**out, "aviso": "No hay comisiones para editar en el período abierto seleccionado.", "filas": []}
            filtradas = R.filtrar_opciones_comisiones_por_busqueda(opciones, busqueda)
            if not filtradas:
                return {**out, "aviso": "No encontré comisiones con esa búsqueda.", "filas": []}
            if contexto == "edicion" and not L.opciones_materias_comisiones()[0]:
                return {**out, "aviso": "No hay materias disponibles.", "filas": []}
            ids = set(int(v) for v in filtradas.values())
            base = df[df["id"].astype(int).isin(ids)].reset_index(drop=True)
            cols = ["id", "codigo_materia", "asignatura", "materia_especifica", "nombre_comision", "turno", "sede",
                    "modalidad", "periodo", "carrera", "horarios", "docentes_asignados_detalle"]
            filas = records(base, cols)
            return {**out, "aviso": None, "filas": filas,
                    "huella_lote": _hash({int(f["id"]): str(f.get("nombre_comision") or "").strip() for f in filas})}

        return self._read(scope, read)

    def comision_detalle(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        contexto = _opcion(data.get("contexto"), ["modificacion", "edicion"])
        cid = _id(data.get("comision_id"))

        def read(L: Lector) -> dict:
            g, periodo, df, _ = self._contexto_comisiones(L, contexto)
            fila = self._fila_por_id(df, cid)
            if fila is None:
                raise ComisionesError(404, "NOT_FOUND", MSG_SELECCION_INVALIDA)
            df_h = L.horarios_comision(cid)
            df_a = L.asignaciones_comision(cid)
            horas = float(pd.to_numeric(df_h.get("horas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) \
                if isinstance(df_h, pd.DataFrame) and not df_h.empty else 0.0
            if isinstance(df_a, pd.DataFrame) and not df_a.empty:
                activos = int(df_a["estado"].fillna("Activa").astype(str).str.strip().eq("Activa").sum()) \
                    if "estado" in df_a.columns else len(df_a)
            else:
                activos = 0
            asign = records(df_a)
            for a, row in zip(asign, self._filas(df_a)):
                a["etiqueta"] = f"{row.get('docente','')} - {row.get('rol','')} ({row.get('horas_asignadas',0)} hs)"
                a["etiqueta_baja"] = (f"{row.get('docente','')} - {row.get('cuil','')} | {row.get('rol','')} "
                                      f"({row.get('horas_asignadas',0)} hs)")
            horarios = records(df_h)
            for h, row in zip(horarios, self._filas(df_h)):
                h["etiqueta"] = f"{row['dia']} {row['hora_inicio']}-{row['hora_fin']}"
                h["etiqueta_eliminar"] = f"{row['dia']} {row['hora_inicio']}-{row['hora_fin']} ({row['horas']} hs)"
            out = {"fila": _clean(fila), "etiqueta": R.label_comision_desde_row(fila), "horarios": horarios,
                   "asignaciones": asign,
                   "metricas": {"horarios": int(len(df_h)) if isinstance(df_h, pd.DataFrame) else 0,
                                "horas": f"{horas:g} hs", "docentes_activos": activos},
                   "franjas_alta": R.franjas_formulario_v95(df_h, default_full=True),
                   "huella": _hash(self._vista_comision_ctx(L, contexto, cid))}
            if contexto == "modificacion":
                out["historial"] = records(L.movimientos_comision_en_curso(cid, periodo["id"]))
            return out

        return self._read(scope, read)

    def asignacion_franjas(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        cid = _id(data.get("comision_id"))
        aid = _id(data.get("asignacion_id"))

        def read(L: Lector) -> dict:
            df_a = L.asignaciones_comision(cid)
            if self._fila_por_id(df_a, aid) is None:
                raise ComisionesError(404, "NOT_FOUND", MSG_SELECCION_INVALIDA)
            df_h = L.horarios_comision(cid)
            return {"franjas": R.franjas_formulario_v95(df_h, default_full=True,
                                                        horarios_actuales=L.horarios_reales_asignacion(aid))}

        return self._read(scope, read)

    # ================================================================== pestaña 4: modificación de asignaciones
    def _stale_ctx(self, scope: Scope, data: dict, contexto: str, cid: int):
        return self._stale_huella(scope, data.get("huella"), lambda L: self._vista_comision_ctx(L, contexto, cid),
                                  "get_comisiones")

    def alta_real(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cid = _id(data.get("comision_id"))
        cuil_sel = _text(data.get("cuil"))
        fecha = _fecha(data.get("fecha"))
        obs = _text(data.get("observaciones"))

        def screen(L: Lector) -> dict:
            g, actual, df, _ = self._contexto_comisiones(L, "modificacion")
            fila = self._fila_por_id(df, cid)
            if fila is None:
                raise ComisionesError(404, "NOT_FOUND", MSG_SELECCION_INVALIDA)
            df_doc = L.docentes_activos_para_comisiones(actual["id"])
            if df_doc.empty:
                raise ComisionesError(409, "SIN_DOCENTES", "No hay docentes disponibles para asignar.", tone="warning")
            fila_doc = self._fila_por_cuil(df_doc, cuil_sel)
            if fila_doc is None:
                raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            cuil = str(fila_doc.get("cuil") or "").strip()
            rol = self._rol(L.roles_docente_periodo(cuil, actual["id"]), data.get("rol"))
            df_h = L.horarios_comision(cid)
            reales, hs = self._franjas(df_h, self._seleccion(data.get("franjas"), len(df_h)))
            return {"actual": actual, "fila": fila, "cuil": cuil, "rol": rol, "reales": reales, "hs": hs,
                    "doc_sel": f"{fila_doc.get('nombre_completo','')} - {cuil}"}

        s = self._read(scope, screen)
        actual, cuil, rol, reales, hs = s["actual"], s["cuil"], s["rol"], s["reales"], s["hs"]
        if hs <= 0:
            raise ComisionesError(422, "VALIDATION", "La comisión no tiene horarios cargados.")
        if self._asignacion_duplicada(scope, cid, cuil):
            raise ComisionesError(422, "VALIDATION", "Ese docente ya está asignado a esta comisión. No puede figurar "
                                                     "dos veces, aunque se intente usar otro rol.")
        stale = self._stale_ctx(scope, data, "modificacion", cid)
        sup = self._read(scope, lambda L: L.detectar_superposiciones_horarios_candidato(
            cuil, actual["id"], reales, excluir_comision_id=cid))
        obs_final = (obs + " | " if obs else "") + (f"Alta por modificación de asignación. Fecha efectiva: {fecha}. "
                                                   f"Comisión ID {cid}.")
        if not sup.empty:
            obs_final += " | ALERTA: asignación con superposición horaria detectada."
        _, avisos = self._op(record, scope, SPEC_GUARDAR_ASIGNACION, lambda u: E.guardar_asignacion_docente_comision(
            u, cid, cuil, rol, hs, "Activa", obs_final, horarios_reales=reales), entity_raw=cid, stale=stale)
        com_sel = R.label_comision_desde_row(s["fila"])
        detalle = (f"Alta docente por modificación de asignación: Comisión ID {cid} - {com_sel}. Docente {s['doc_sel']}, "
                   f"rol {rol}, {hs:g} hs. Fecha efectiva: {fecha}.")
        self._op(record, scope, SPEC_MOVIMIENTO, lambda u: E.registrar_movimiento(
            u, "Alta docente por modificación de asignación", cuil, s["doc_sel"], detalle, obs_final, actual["id"]),
            entity_raw=cuil)
        return {"mensaje": "Alta registrada y guardada en historial.", "tono": "success", "avisos": avisos}

    def baja_real(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cid = _id(data.get("comision_id"))
        aid = _id(data.get("asignacion_id"))
        fecha = _fecha(data.get("fecha"))
        obs = _text(data.get("observaciones"))

        def screen(L: Lector) -> dict:
            g, actual, df, _ = self._contexto_comisiones(L, "modificacion")
            fila = self._fila_por_id(df, cid)
            if fila is None:
                raise ComisionesError(404, "NOT_FOUND", MSG_SELECCION_INVALIDA)
            df_baja = L.asignaciones_comision(cid)
            if df_baja.empty:
                raise ComisionesError(409, "SIN_DOCENTES", "No hay docentes para dar de baja en esta comisión.",
                                      tone="info")
            if "estado" in df_baja.columns:
                df_baja = df_baja[df_baja["estado"].fillna("Activa").astype(str).str.strip() == "Activa"].copy()
            if df_baja.empty:
                raise ComisionesError(409, "SIN_ACTIVAS", "No hay asignaciones activas para dar de baja.", tone="info")
            fila_baja = self._fila_por_id(df_baja, aid)
            if fila_baja is None:
                raise ComisionesError(404, "NOT_FOUND", MSG_SELECCION_INVALIDA)
            return {"actual": actual, "fila": fila, "baja": fila_baja}

        s = self._read(scope, screen)
        if data.get("confirmar") is not True:
            raise ComisionesError(422, "CONFIRMAR", "Primero confirmá la baja en comisión.")
        fila_baja, actual = s["baja"], s["actual"]
        stale = self._stale_ctx(scope, data, "modificacion", cid)
        obs_final = (obs + " | " if obs else "") + (f"Baja por modificación de asignación. Fecha efectiva: {fecha}. "
                                                   f"Comisión ID {cid}.")
        self._op(record, scope, SPEC_ESTADO_ASIGNACION, lambda u: E.actualizar_estado_asignacion_docente_comision(
            u, aid, "Finalizada", obs_final), entity_raw=aid, stale=stale)
        com_sel = R.label_comision_desde_row(s["fila"])
        detalle = (f"Baja docente por modificación de asignación: Comisión ID {cid} - {com_sel}. "
                   f"Docente {fila_baja.get('docente','')} [{fila_baja.get('cuil','')}], rol {fila_baja.get('rol','')}, "
                   f"{fila_baja.get('horas_asignadas',0)} hs. Fecha efectiva: {fecha}.")
        self._op(record, scope, SPEC_MOVIMIENTO, lambda u: E.registrar_movimiento(
            u, "Baja docente por modificación de asignación", fila_baja.get("cuil", ""), fila_baja.get("docente", ""),
            detalle, obs_final, actual["id"]), entity_raw=fila_baja.get("cuil", ""))
        return {"mensaje": "Baja registrada y guardada en historial.", "tono": "success"}

    # ================================================================== pestaña 7: editar / eliminar
    def _edicion(self, L: Lector, cid: int) -> dict:
        g, periodo, df, _ = self._contexto_comisiones(L, "edicion")
        fila = self._fila_por_id(df, cid)
        if fila is None:
            raise ComisionesError(404, "NOT_FOUND", MSG_SELECCION_INVALIDA)
        return {"g": g, "periodo": periodo, "fila": fila, "etiqueta": R.label_comision_desde_row(fila)}

    def _form_datos(self, L: Lector, fila: dict, cid: int, mat_edit_id: Optional[int]) -> dict:
        """Contexto del formulario "Datos generales" (l. 71559-71767): opciones y valores por defecto."""
        opciones_materias, df_mat = L.opciones_materias_comisiones()
        if not opciones_materias:
            raise ComisionesError(409, "SIN_MATERIAS", "No hay materias disponibles.", tone="warning")
        materia_actual_id = int(fila["materia_id"])
        valores = list(opciones_materias.values())
        idx_actual = valores.index(materia_actual_id) if materia_actual_id in valores else 0
        if materia_actual_id not in valores and isinstance(df_mat, pd.DataFrame) and not df_mat.empty:
            info_actual = L.materia_comision(materia_actual_id) or {}
            clave_actual = (R.limpiar_texto_tabla(info_actual.get("_clave_unica", ""))
                            or R.clave_materia_conceptual_v137(info_actual))
            for pos_m, (_, fila_m) in enumerate(df_mat.iterrows()):
                if R.clave_materia_conceptual_v137(fila_m) == clave_actual:
                    idx_actual = pos_m
                    break
        if mat_edit_id is None:
            mat_edit_id = valores[idx_actual]
        elif mat_edit_id not in valores:
            raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        actuales = L.materias_conceptuales_comision_v122(cid)
        info = L.materia_comision(mat_edit_id) or {}
        codigo = R.limpiar_texto_tabla(info.get("codigo", ""))
        asignatura = R.limpiar_texto_tabla(info.get("asignatura", ""))
        es_oe = R.es_materia_optativa_electiva(codigo, asignatura)
        estado_edit = (fila["estado"] if pd.notna(fila.get("estado")) and str(fila["estado"]).strip() else "Activa")
        misma_principal = L.materias_mismo_grupo_conceptual_v118(materia_actual_id, mat_edit_id)
        opciones_adicionales, defaults, avisos = {}, [], []
        if not es_oe:
            opciones_adicionales = R.opciones_desde_df_materias_comisiones(self._adicionales_df(df_mat, codigo, asignatura))
            if misma_principal:
                extra = set(int(x) for x in actuales[1:])
                defaults = [int(mid) for _, mid in opciones_adicionales.items() if int(mid) in extra]
        else:
            if len(actuales) > 1:
                avisos.append("Se detectó una comisión Optativa/Electiva vinculada a varios códigos. Al guardar esta "
                              "edición se conservará únicamente el código/espacio formal seleccionado.")
        raw = fila.get("opcion_curricular_id")
        try:
            opcion_actual = int(raw) if raw is not None and not pd.isna(raw) else None
        except Exception:
            opcion_actual = None
        misma_materia = L.materias_mismo_grupo_conceptual_v118(materia_actual_id, mat_edit_id)
        especifica_actual = str(fila.get("materia_especifica") or "").strip()
        placeholder = "— Seleccionar opción curricular concreta —"
        mapa, labels, indice = {}, [], 0
        actual_en_validas = False
        sin_opciones = False
        if es_oe:
            df_op = L.opciones_curriculares_para_materia_v120(mat_edit_id)
            if opcion_actual is not None and not df_op.empty and "id" in df_op.columns:
                ids = pd.to_numeric(df_op["id"], errors="coerce").astype("Int64")
                actual_en_validas = bool((ids == opcion_actual).any())
                if actual_en_validas:
                    df_op = pd.concat([df_op[ids == opcion_actual].copy(), df_op[ids != opcion_actual].copy()],
                                      ignore_index=True)
            if opcion_actual is None and misma_materia and especifica_actual:
                avisos.append("Esta es una comisión histórica creada antes del catálogo de opciones curriculares. "
                              "Podés conservarla tal como está o seleccionar una opción del catálogo para normalizarla.")
            elif opcion_actual is not None and misma_materia and not actual_en_validas:
                op_actual = L.opcion_curricular_v120(opcion_actual) or {}
                avisos.append(f"La opción actual ({R.limpiar_texto_tabla(op_actual.get('nombre', especifica_actual))}) "
                              "ya no está habilitada para nuevas comisiones. Se conservará mientras no selecciones "
                              "otra opción.")
            if df_op.empty:
                sin_opciones = True
            else:
                for _, rop in df_op.iterrows():
                    try:
                        oid = int(rop.get("id"))
                    except Exception:
                        continue
                    cod = R.limpiar_texto_tabla(rop.get("codigo", ""))
                    nom = R.limpiar_texto_tabla(rop.get("nombre", ""))
                    esc = R.limpiar_texto_tabla(rop.get("escuela_oferente", ""))
                    etiqueta = f"{cod} - {nom}" if cod else nom
                    if esc:
                        etiqueta += f" — {esc}"
                    mapa[etiqueta] = {"id": oid, "nombre": nom}
                labels = [placeholder] + list(mapa.keys())
                if opcion_actual is not None and misma_materia:
                    for pos, (lab, dat) in enumerate(mapa.items(), start=1):
                        if int(dat["id"]) == int(opcion_actual):
                            indice = pos
                            break
                    if indice == 0:
                        op_p = L.opcion_curricular_v120(opcion_actual) or {}
                        nom_p = R.limpiar_texto_tabla(op_p.get("nombre", especifica_actual)) or f"ID {opcion_actual}"
                        etiqueta_p = f"Conservar opción actual: {nom_p}"
                        labels.insert(1, etiqueta_p)
                        mapa[etiqueta_p] = {"id": int(opcion_actual), "nombre": nom_p}
                        indice = 1
                elif misma_materia and especifica_actual:
                    etiqueta_l = f"Conservar denominación histórica sin opción vinculada: {especifica_actual}"
                    labels.insert(1, etiqueta_l)
                    mapa[etiqueta_l] = {"id": None, "nombre": especifica_actual}
                    indice = 1
        opciones_sede = L.opciones_sedes_comision()
        return {
            "materias": [{"etiqueta": k, "materia_id": int(v)} for k, v in opciones_materias.items()],
            "materia_id": int(mat_edit_id), "indice_materia_actual": idx_actual, "es_oe": es_oe,
            "estado": estado_edit, "adicionales": [{"etiqueta": k, "materia_id": int(v)}
                                                   for k, v in opciones_adicionales.items()],
            "adicionales_default": defaults, "opciones_curriculares": labels, "indice_opcion": indice,
            "sin_opciones": sin_opciones, "avisos": avisos, "placeholder": placeholder, "_mapa": mapa,
            "opcion_actual": opcion_actual, "misma_materia": misma_materia, "especifica_actual": especifica_actual,
            "valores": {"nombre": fila.get("nombre_comision") or "",
                        "turno": R.TURNOS_COMISION[R.safe_index(R.TURNOS_COMISION,
                                                                R.normalizar_turno_comision(fila.get("turno") or "")
                                                                or "mañana")],
                        "sede": opciones_sede[R.safe_index(opciones_sede, fila.get("sede") or "Sin especificar")],
                        "modalidad": R.MODALIDADES_COMISION[R.safe_index(
                            R.MODALIDADES_COMISION, R.normalizar_modalidad_comision(fila.get("modalidad") or "Presencial"))],
                        "observaciones": fila.get("observaciones") or ""},
            "opciones_sede": opciones_sede,
        }

    def edicion_datos(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        cid = _id(data.get("comision_id"))
        mat = _opt_id(data.get("materia_id"))

        def read(L: Lector) -> dict:
            e = self._edicion(L, cid)
            form = self._form_datos(L, e["fila"], cid, mat)
            form.pop("_mapa")
            return form

        return self._read(scope, read)

    def editar_datos(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cid = _id(data.get("comision_id"))
        mat = _id(data.get("materia_id"))
        nombre_edit = _text(data.get("nombre"))
        turno = _opcion(data.get("turno"), R.TURNOS_COMISION)
        modalidad = _opcion(data.get("modalidad"), R.MODALIDADES_COMISION)
        obs = _text(data.get("observaciones"))
        adicionales_sel = _ids(data.get("adicionales"))
        opcion_label = data.get("opcion_curricular")

        def screen(L: Lector) -> dict:
            e = self._edicion(L, cid)
            f = self._form_datos(L, e["fila"], cid, mat)
            sede = _opcion(data.get("sede"), f["opciones_sede"])
            if not f["es_oe"]:
                validos = {a["materia_id"] for a in f["adicionales"]}
                if any(a not in validos for a in adicionales_sel):
                    raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
                adicionales, opcion_id, especifica = adicionales_sel, None, ""
            else:
                if adicionales_sel:
                    raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
                label = f["placeholder"]
                if f["opcion_curricular"]:
                    label = _opcion(opcion_label, f["opcion_curricular"])
                adicionales = []
                opcion_id = f["opcion_actual"] if f["misma_materia"] else None
                especifica = f["especifica_actual"] if f["misma_materia"] else ""
                if label != f["placeholder"]:
                    dato = f["_mapa"].get(label, {})
                    oid = dato.get("id")
                    opcion_id = int(oid) if oid is not None else None
                    especifica = R.limpiar_texto_tabla(dato.get("nombre", especifica))
                elif f["opcion_actual"] is None:
                    opcion_id = None
            periodo = e["periodo"]
            if nombre_edit and periodo is None:
                raise ComisionesError(409, "NO_CORREGIR", "No podés editar comisiones si no hay un período abierto "
                                                          "para corrección.")
            dup = (not L.existe_comision_duplicada(
                periodo["id"], mat, nombre_edit, turno, sede, modalidad, excluir_id=cid, opcion_curricular_id=opcion_id,
                materia_especifica=especifica, materia_ids_adicionales=adicionales).empty) if nombre_edit else False
            return {"e": e, "f": f, "sede": sede, "adicionales": adicionales, "opcion_id": opcion_id,
                    "especifica": especifica, "dup": dup}

        s = self._read(scope, screen)
        e, f = s["e"], s["f"]
        if not e["g"]["puede_corregir"]:
            raise ComisionesError(409, "NO_CORREGIR", "No podés editar comisiones si no hay un período abierto para "
                                                      "corrección.")
        if not nombre_edit.strip():
            raise ComisionesError(422, "VALIDATION", "Indicá el nombre o número de comisión.")
        if f["es_oe"] and s["opcion_id"] is None and not s["especifica"]:
            raise ComisionesError(422, "VALIDATION", "Seleccioná la opción curricular concreta de esta Optativa/Electiva.")
        if s["dup"]:
            raise ComisionesError(422, "VALIDATION", "Operación bloqueada: duplicaría una comisión existente.")
        stale = self._stale_ctx(scope, data, "edicion", cid)
        self._op(record, scope, SPEC_ACTUALIZAR_COMISION, lambda u: E.actualizar_comision(
            u, cid, mat, nombre_edit.strip(), turno, s["sede"], modalidad, f["estado"], obs,
            materia_especifica=s["especifica"] if f["es_oe"] else "", opcion_curricular_id=s["opcion_id"],
            materia_ids_adicionales=s["adicionales"]), entity_raw=cid, stale=stale)
        return {"mensaje": "Datos generales de la comisión actualizados.", "tono": "success"}

    def editar_nombres_lote(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        busqueda = _text(data.get("busqueda"))
        filas_in = data.get("filas")
        if not isinstance(filas_in, list):
            raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        editadas = {}
        for item in filas_in:
            if not isinstance(item, dict):
                raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            editadas[_id(item.get("id"))] = _text(item.get("comision"))

        def base(L: Lector) -> dict:
            _, _, df, opciones = self._contexto_comisiones(L, "edicion")
            filtradas = R.filtrar_opciones_comisiones_por_busqueda(opciones, busqueda)
            ids = set(int(v) for v in filtradas.values())
            b = df[df["id"].astype(int).isin(ids)].reset_index(drop=True) if not df.empty else df
            return {int(r["id"]): str(r.get("nombre_comision") or "").strip() for _, r in b.iterrows()}

        mapa_original = self._read(scope, base)
        if any(cid not in mapa_original for cid in editadas):
            raise ComisionesError(422, "INVALID", MSG_SELECCION_INVALIDA)
        cambios = [(cid, mapa_original[cid], str(nuevo or "").strip()) for cid, nuevo in editadas.items()
                   if str(nuevo or "").strip() != mapa_original[cid]]
        if not cambios:
            return {"mensaje": "No hay cambios de Comisión para guardar.", "tono": "info", "sin_cambios": True}
        stale = self._stale_huella(scope, data.get("huella_lote"), base, "get_opciones_comisiones")
        try:
            res, _ = self._op(record, scope, SPEC_NOMBRES_LOTE, lambda u: E.actualizar_nombres_comisiones_lote_v195(
                u, cambios), stale=stale)
        except ComisionesError as exc:
            raise ComisionesError(exc.status, exc.code, "No se pudieron guardar todos los cambios. "
                                  "No se aplicó un lote parcial.\n\n" + exc.message, exc.error_class) from None
        return {"mensaje": (f"Se actualizaron {int(res.get('aplicados', 0) or 0)} comisión/es en "
                            f"{float(res.get('segundos', 0) or 0):.2f} s."), "tono": "success"}

    def _horario_de(self, L: Lector, cid: int, hid: int) -> dict:
        fila = self._fila_por_id(L.horarios_comision(cid), hid)
        if fila is None:
            raise ComisionesError(404, "NOT_FOUND", MSG_SELECCION_INVALIDA)
        return fila

    def editar_horario(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cid, hid = _id(data.get("comision_id")), _id(data.get("horario_id"))
        dia = _opcion(data.get("dia"), R.DIAS_SEMANA)
        hi, hf = _hora(data.get("hora_inicio")), _hora(data.get("hora_fin"))
        obs = _text(data.get("observaciones"))
        e = self._read(scope, lambda L: {**self._edicion(L, cid), "h": self._horario_de(L, cid, hid)})
        stale = self._stale_ctx(scope, data, "edicion", cid)
        (ok, mensaje), avisos = self._op(record, scope, SPEC_ACTUALIZAR_HORARIO, lambda u: E.actualizar_horario_comision(
            u, hid, dia, hi, hf, obs), entity_raw=hid, stale=stale)
        if not ok:
            raise ComisionesError(422, "VALIDATION", mensaje)
        if e["periodo"] is None:
            # El certificado indexa ``periodo_edicion_com["id"]`` con None aqui (TypeError tras el UPDATE confirmado).
            raise ComisionesError(409, "NO_CORREGIR", MSG_NO_CORREGIR)
        self._op(record, scope, SPEC_MOVIMIENTO, lambda u: E.registrar_movimiento(
            u, "Modificación de horario de comisión", "", "",
            f"Se modificó un horario de {e['etiqueta']} a {dia} {hi}-{hf}.", obs, e["periodo"]["id"]), entity_raw="")
        return {"mensaje": mensaje, "tono": "success", "avisos": avisos}

    def agregar_horario(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cid = _id(data.get("comision_id"))
        dia = _opcion(data.get("dia"), R.DIAS_SEMANA)
        hi, hf = _hora(data.get("hora_inicio")), _hora(data.get("hora_fin"))
        obs = _text(data.get("observaciones"))
        horas = R.calcular_horas_desde_texto(hi, hf)
        e = self._read(scope, lambda L: self._edicion(L, cid))
        dup = self._horario_duplicado(scope, cid, dia, hi, hf)
        if not e["g"]["puede_corregir"]:
            raise ComisionesError(409, "NO_CORREGIR", "No podés agregar horarios si no hay un período abierto para "
                                                      "corrección.")
        if horas <= 0:
            raise ComisionesError(422, "VALIDATION", "El horario no es válido. Revisá las horas.")
        if dup:
            raise ComisionesError(422, "VALIDATION", "Ese horario ya existe en la comisión.")
        stale = self._stale_ctx(scope, data, "edicion", cid)
        _, avisos = self._op(record, scope, SPEC_GUARDAR_HORARIO, lambda u: E.guardar_horario_comision(
            u, cid, dia, hi, hf, obs), entity_raw=cid, stale=stale)
        self._op(record, scope, SPEC_MOVIMIENTO, lambda u: E.registrar_movimiento(
            u, "Alta de horario de comisión", "", "", f"Se agregó el horario {dia} {hi}-{hf} en {e['etiqueta']}.", obs,
            e["periodo"]["id"]), entity_raw="")
        return {"mensaje": "Horario agregado correctamente.", "tono": "success", "avisos": avisos}

    def eliminar_horario(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cid, hid = _id(data.get("comision_id")), _id(data.get("horario_id"))
        e = self._read(scope, lambda L: {**self._edicion(L, cid), "h": self._horario_de(L, cid, hid)})
        if not e["g"]["puede_corregir"]:
            raise ComisionesError(409, "NO_CORREGIR", "No podés eliminar horarios si no hay un período abierto para "
                                                      "corrección.")
        if data.get("confirmar") is not True:
            raise ComisionesError(422, "CONFIRMAR", "Primero confirmá la eliminación.")
        h = e["h"]
        label = f"{h['dia']} {h['hora_inicio']}-{h['hora_fin']} ({h['horas']} hs)"
        stale = self._stale_ctx(scope, data, "edicion", cid)
        self._op(record, scope, SPEC_ELIMINAR_HORARIO, lambda u: E.eliminar_horario_comision(u, hid), entity_raw=hid,
                 stale=stale)
        self._op(record, scope, SPEC_MOVIMIENTO, lambda u: E.registrar_movimiento(
            u, "Eliminación de horario de comisión", "", "", f"Se eliminó el horario {label} de {e['etiqueta']}.",
            "Corrección de error de carga.", e["periodo"]["id"]), entity_raw="")
        return {"mensaje": "Horario eliminado.", "tono": "warning"}

    def asignar_correccion(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cid = _id(data.get("comision_id"))
        cuil_sel = _text(data.get("cuil"))
        obs = _text(data.get("observaciones"))

        def screen(L: Lector) -> dict:
            e = self._edicion(L, cid)
            if e["periodo"] is None:
                raise ComisionesError(409, "NO_CORREGIR", MSG_NO_CORREGIR, tone="warning")
            pid = int(e["periodo"]["id"])
            df_doc = L.docentes_activos_para_comisiones(pid)
            if df_doc.empty:
                raise ComisionesError(409, "SIN_DOCENTES", "No hay docentes disponibles para asignar en este período.",
                                      tone="info")
            fila_doc = self._fila_por_cuil(df_doc, cuil_sel)
            if fila_doc is None:
                raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            cuil = str(fila_doc.get("cuil") or "").strip()
            rol = self._rol(L.roles_docente_periodo(cuil, pid), data.get("rol"))
            df_h = L.horarios_comision(cid)
            reales, hs = self._franjas(df_h, self._seleccion(data.get("franjas"), len(df_h)))
            return {"cuil": cuil, "rol": rol, "reales": reales, "hs": hs}

        s = self._read(scope, screen)
        if s["hs"] <= 0:
            raise ComisionesError(422, "VALIDATION", "La comisión no tiene horarios válidos cargados.")
        if self._asignacion_duplicada(scope, cid, s["cuil"]):
            raise ComisionesError(422, "VALIDATION", "Ese docente ya está asignado a esta comisión. No puede figurar "
                                                     "dos veces, aunque cambie el rol.")
        stale = self._stale_ctx(scope, data, "edicion", cid)
        obs_final = (obs + " | " if obs else "") + "Asignación agregada como corrección de carga; sin movimiento académico."
        _, avisos = self._op(record, scope, SPEC_GUARDAR_ASIGNACION, lambda u: E.guardar_asignacion_docente_comision(
            u, cid, s["cuil"], s["rol"], s["hs"], "Activa", obs_final, horarios_reales=s["reales"]),
            entity_raw=cid, stale=stale)
        return {"mensaje": "Docente asignado correctamente como corrección de carga.", "tono": "success",
                "avisos": avisos}

    def guardar_franjas(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cid, aid = _id(data.get("comision_id")), _id(data.get("asignacion_id"))

        def screen(L: Lector) -> dict:
            e = self._edicion(L, cid)
            df_a = L.asignaciones_comision(cid)
            activas = df_a[df_a["estado"].fillna("Activa").astype(str).str.strip().eq("Activa")] \
                if isinstance(df_a, pd.DataFrame) and not df_a.empty and "estado" in df_a.columns else df_a
            if self._fila_por_id(activas, aid) is None:
                raise ComisionesError(404, "NOT_FOUND", MSG_SELECCION_INVALIDA)
            df_h = L.horarios_comision(cid)
            reales, hs = self._franjas(df_h, self._seleccion(data.get("franjas"), len(df_h)))
            return {"e": e, "reales": reales, "hs": hs}

        s = self._read(scope, screen)
        if not s["e"]["g"]["puede_corregir"]:
            raise ComisionesError(409, "NO_CORREGIR", "No podés modificar horarios si no hay un período abierto para "
                                                      "corrección.")
        if s["hs"] <= 0:
            raise ComisionesError(422, "VALIDATION", "El docente debe conservar al menos una franja horaria válida.")
        stale = self._stale_ctx(scope, data, "edicion", cid)
        self._op(record, scope, SPEC_HORARIOS_REALES, lambda u: E.guardar_horarios_reales_asignacion(
            u, aid, s["reales"]), entity_raw=aid, stale=stale)
        return {"mensaje": "Horario efectivo actualizado. Se usará en resumen, cronograma, superposiciones, horas y "
                           "disposiciones.", "tono": "success"}

    def quitar_asignacion(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cid, aid = _id(data.get("comision_id")), _id(data.get("asignacion_id"))

        def screen(L: Lector) -> dict:
            e = self._edicion(L, cid)
            fila = self._fila_por_id(L.asignaciones_comision(cid), aid)
            if fila is None:
                raise ComisionesError(404, "NOT_FOUND", MSG_SELECCION_INVALIDA)
            return {"e": e, "a": fila}

        s = self._read(scope, screen)
        e, a = s["e"], s["a"]
        if not e["g"]["puede_corregir"]:
            raise ComisionesError(409, "NO_CORREGIR", "No podés eliminar asignaciones si no hay un período abierto para "
                                                      "corrección.")
        if data.get("confirmar") is not True:
            raise ComisionesError(422, "CONFIRMAR", "Primero confirmá la eliminación.")
        label = f"{a.get('docente','')} - {a.get('rol','')} ({a.get('horas_asignadas',0)} hs)"
        stale = self._stale_ctx(scope, data, "edicion", cid)
        self._op(record, scope, SPEC_ELIMINAR_ASIGNACION, lambda u: E.eliminar_asignacion_docente_comision(u, aid),
                 entity_raw=aid, stale=stale)
        self._op(record, scope, SPEC_MOVIMIENTO, lambda u: E.registrar_movimiento(
            u, "Eliminación de asignación docente a comisión", "", "",
            f"Se eliminó por error de carga la asignación {label} de {e['etiqueta']}.", "Corrección de error de carga.",
            e["periodo"]["id"]), entity_raw="")
        return {"mensaje": "Asignación eliminada.", "tono": "warning"}

    def eliminar_comision(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cid = _id(data.get("comision_id"))
        e = self._read(scope, lambda L: self._edicion(L, cid))
        if not e["g"]["puede_corregir"]:
            raise ComisionesError(409, "NO_CORREGIR", "No podés eliminar comisiones si no hay un período abierto para "
                                                      "corrección.")
        if data.get("confirmar") is not True:
            raise ComisionesError(422, "CONFIRMAR", "Primero confirmá la eliminación.")
        stale = self._stale_ctx(scope, data, "edicion", cid)
        self._op(record, scope, SPEC_ELIMINAR_COMISION, lambda u: E.eliminar_comision(u, cid), entity_raw=cid,
                 stale=stale)
        return {"mensaje": "Comisión eliminada junto con sus horarios y asignaciones.", "tono": "warning"}

    # ================================================================== pestaña inscriptos (escritura)
    def guardar_inscriptos(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        pid = _id(data.get("periodo_id"))
        filas_in = data.get("filas")
        if not isinstance(filas_in, list):
            raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        editadas = {}
        for item in filas_in:
            if not isinstance(item, dict) or not isinstance(item.get("clave"), str):
                raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            for k in ("cantidad", "cantidad_final"):
                v = item.get(k)
                if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
                    raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            editadas[item["clave"]] = item

        def screen(L: Lector) -> pd.DataFrame:
            if L.periodo_info(pid) is None:
                raise ComisionesError(404, "NOT_FOUND", MSG_PERIODO_NO_ENCONTRADO)
            df = L.inscriptos_asignaturas_periodo_v248(pid)
            if df.empty:
                raise ComisionesError(409, "VACIO", "No hay asignaturas vinculadas a comisiones en este período.",
                                      tone="info")
            df = df.copy()
            df["cantidad"] = pd.to_numeric(df.get("cantidad", 0), errors="coerce").fillna(0).astype(int)
            return df

        def huellas(L: Lector) -> dict:
            out = {}
            for r in records(screen(L)):
                out[self._fila_inscriptos_clave(r)] = _hash({k: r.get(k) for k in (
                    "cantidad", "cantidad_final", "observaciones_inscriptos", "fecha_actualizacion",
                    "fecha_actualizacion_final")})
            return out

        df = self._read(scope, screen)
        filas = self._filas(df)
        claves = [self._fila_inscriptos_clave(r) for r in records(df)]
        if any(k not in claves for k in editadas):
            raise ComisionesError(422, "INVALID", MSG_SELECCION_INVALIDA)
        pendientes = []
        for clave, fila in zip(claves, filas):
            ed = editadas.get(clave)
            if ed is None:
                continue
            cantidad_anterior = int(pd.to_numeric(pd.Series([fila.get("cantidad")]), errors="coerce").fillna(0).iloc[0])
            cantidad_nueva = max(int(pd.to_numeric(pd.Series([ed.get("cantidad", 0)]), errors="coerce").fillna(0).iloc[0]), 0)
            fa = pd.to_numeric(pd.Series([fila.get("cantidad_final")]), errors="coerce").iloc[0]
            fn = pd.to_numeric(pd.Series([ed.get("cantidad_final")]), errors="coerce").iloc[0]
            final_anterior = None if pd.isna(fa) else max(int(fa), 0)
            final_nuevo = None if pd.isna(fn) else max(int(fn), 0)
            cambio_inicio = cantidad_nueva != cantidad_anterior
            cambio_final = final_nuevo != final_anterior
            if cambio_inicio or cambio_final:
                pendientes.append((clave, fila, ed, cantidad_nueva, final_nuevo, cambio_inicio, cambio_final))
        if not pendientes:
            return {"mensaje": "No había cambios para guardar.", "tono": "info", "sin_cambios": True}
        esperado = {p[0]: p[2].get("huella") for p in pendientes}

        def stale() -> None:
            try:
                actual = self._read(scope, huellas)
            except ComisionesError:
                raise ComisionesError(503, "FRESH_READ", MSG_DB_READ, "FreshReadError") from None
            if any(actual.get(k) != v for k, v in esperado.items()):
                raise ComisionesError(409, "STALE", f"{MSG_STALE} [B12I: get_inscriptos_asignaturas_periodo_v248]",
                                      "StaleDecisionError")

        hoy = self.today()
        actualizadas = 0
        for i, (clave, fila, ed, cantidad_nueva, final_nuevo, cambio_inicio, cambio_final) in enumerate(pendientes):
            self._op(record, scope, SPEC_INSCRIPTOS, lambda u: E.guardar_inscriptos_asignatura_periodo_v248(
                u, pid, int(fila.get("materia_id_inscriptos")), cantidad_nueva,
                opcion_curricular_id=int(fila.get("opcion_curricular_id_inscriptos", 0) or 0),
                observaciones=str(fila.get("observaciones_inscriptos", "") or ""),
                fecha_actualizacion=hoy if cambio_inicio else fila.get("fecha_actualizacion", ""),
                cantidad_final=final_nuevo,
                fecha_actualizacion_final=hoy if cambio_final else fila.get("fecha_actualizacion_final", ""),
                actualizar_final=cambio_final), entity_raw=fila.get("materia_id_inscriptos"),
                stale=stale if i == 0 else None)
            actualizadas += 1
        return {"mensaje": f"Se actualizaron {actualizadas} asignatura/s o código/s del período.", "tono": "success"}

    # ================================================================== pestaña sedes (escritura)
    def _sede(self, scope: Scope, sede_id: int) -> dict:
        def read(L: Lector) -> dict:
            fila = self._fila_por_id(L.sedes_institucionales(solo_activas=False), sede_id)
            if fila is None:
                raise ComisionesError(404, "NOT_FOUND", MSG_SELECCION_INVALIDA)
            return _clean(fila)
        return self._read(scope, read)

    def _stale_sede(self, scope: Scope, data: dict, sede_id: int):
        def fresh(L: Lector):
            fila = self._fila_por_id(L.sedes_institucionales(solo_activas=False), sede_id)
            return _clean(fila) if fila else None
        return self._stale_huella(scope, data.get("huella"), fresh, "get_sedes_institucionales")

    def agregar_sede(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        args = [_text(data.get(k)) for k in ("nombre", "direccion", "localidad", "observaciones")]
        self._op(record, scope, SPEC_GUARDAR_SEDE, lambda u: E.guardar_sede_institucional(u, *args))
        return {"mensaje": "Sede institucional agregada. Ya está disponible en todos los departamentos.",
                "tono": "success"}

    def editar_sede(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        sid = _id(data.get("id"))
        nombre, direccion, localidad, obs = [_text(data.get(k)) for k in ("nombre", "direccion", "localidad",
                                                                          "observaciones")]
        estado = _opcion(data.get("estado"), R.ESTADOS_SEDE)
        self._sede(scope, sid)
        stale = self._stale_sede(scope, data, sid)
        self._op(record, scope, SPEC_ACTUALIZAR_SEDE, lambda u: E.actualizar_sede_institucional(
            u, sid, nombre, direccion, localidad, estado, obs), entity_raw=sid, stale=stale)
        return {"mensaje": "Sede actualizada para toda la institución.", "tono": "success"}

    def eliminar_sede(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        sid = _id(data.get("id"))
        self._sede(scope, sid)
        if data.get("confirmar") is not True:
            raise ComisionesError(422, "CONFIRMAR", "Primero confirmá la eliminación.")
        stale = self._stale_sede(scope, data, sid)
        self._op(record, scope, SPEC_ELIMINAR_SEDE, lambda u: E.eliminar_sede_institucional(u, sid), entity_raw=sid,
                 stale=stale)
        return {"mensaje": "Sede eliminada del catálogo institucional.", "tono": "success"}

    # ================================================================== pestaña 5: carga rápida
    MAX_EXCEL_BYTES = 15 * 1024 * 1024

    @classmethod
    def _excel_bytes(cls, valor: Any) -> Optional[bytes]:
        if valor in (None, ""):
            return None
        if not isinstance(valor, str):
            raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        import base64
        import binascii
        try:
            contenido = base64.b64decode(valor, validate=True)
        except (binascii.Error, ValueError):
            raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO) from None
        if len(contenido) > cls.MAX_EXCEL_BYTES:
            raise ComisionesError(413, "TOO_LARGE", "El archivo supera el tamaño máximo admitido.")
        return contenido

    def _preview(self, L: Lector, texto: str, contenido: Optional[bytes]) -> dict:
        from . import carga
        g = self._gates(L)
        actual = self._gate_operar(g, MSG_NO_OPERAR_CARGA, MSG_NO_PERIODO_CARGA)
        sedes = L.opciones_sedes_comision()
        mensajes: list[dict] = []
        df_excel = pd.DataFrame()
        if contenido is not None:
            try:
                # 6A-B1: contenido real validado ANTES del lector (bombas de descompresion, no-OOXML); se informa con
                # el mismo mensaje y tono certificados de un Excel ilegible.
                if (motivo := uploads.problema_xlsx(contenido)) is not None:
                    log.info("comisiones: Excel rechazado (%s)", motivo)
                    raise ValueError(MSG_EXCEL_INVALIDO)
                df_excel = carga.leer_excel_integral_comisiones_v149(contenido, sedes)
                if df_excel.empty:
                    mensajes.append({"tono": "warning",
                                     "texto": "El Excel subido no contiene filas con comisión para procesar."})
                else:
                    mensajes.append({"tono": "success", "texto": (
                        f"Excel leído correctamente: {len(df_excel)} fila/s candidata/s. La vista previa de abajo "
                        "todavía no guarda nada.")})
            except Exception as exc:
                mensajes.append({"tono": "error", "texto": f"No se pudo leer el Excel integral de comisiones: {exc}"})
                df_excel = pd.DataFrame()
        if contenido is not None and not df_excel.empty:
            df = df_excel.copy()
            if texto.strip():
                mensajes.append({"tono": "info", "texto": (
                    "Hay un Excel subido y también texto pegado: se usará el **Excel subido**. Quitá el archivo si "
                    "querés procesar el texto manual.")})
        else:
            try:
                df = carga.parsear_comisiones_pegadas(texto, sedes)
            except Exception as exc:
                log.info("comisiones: texto pegado no interpretable: %s", type(exc).__name__)
                df = pd.DataFrame()
        if texto and df.empty and contenido is None:
            mensajes.append({"tono": "warning", "texto": (
                "No encontré filas con comisión para cargar. Revisá que Comisión tenga valor y que exista al menos "
                "Código o Asignatura.")})
        if df.empty:
            return {"actual": actual, "mensajes": mensajes, "df": pd.DataFrame()}
        preview = carga.Validador(L, int(actual["id"])).preparar_preview_comisiones_rapidas(df)
        return {"actual": actual, "mensajes": mensajes, "df": preview}

    @staticmethod
    def _totales(df: pd.DataFrame) -> dict:
        col = df["estado_validacion"]
        return {"ok": int((col == "OK").sum()), "advertencia": int((col == "ADVERTENCIA").sum()),
                "duplicada": int((col == "DUPLICADA").sum()), "error": int((col == "ERROR").sum())}

    def carga_preview(self, record: SessionRecord, data: dict) -> dict:
        from . import carga
        scope = self.reader(record)
        texto = _text(data.get("texto"))
        contenido = self._excel_bytes(data.get("excel"))
        p = self._read(scope, lambda L: self._preview(L, texto, contenido))
        df = p["df"]
        if df.empty:
            return {"mensajes": p["mensajes"], "filas": [], "totales": None, "huella": None}
        return {"mensajes": p["mensajes"], "filas": records(df, carga.COLUMNAS_PREVIEW), "totales": self._totales(df),
                "huella": _hash(records(df))}

    def carga_ejecutar(self, record: SessionRecord, data: dict) -> dict:
        from . import carga
        scope = self.scope(record)
        texto = _text(data.get("texto"))
        contenido = self._excel_bytes(data.get("excel"))
        p = self._read(scope, lambda L: self._preview(L, texto, contenido))
        df = p["df"]
        if df.empty:
            raise ComisionesError(422, "SIN_FILAS", "No hay comisiones válidas para cargar.")
        tot = self._totales(df)
        if tot["ok"] + tot["advertencia"] == 0:
            raise ComisionesError(422, "SIN_VALIDAS", "No hay comisiones válidas para cargar.")
        if data.get("confirmar") is not True:
            raise ComisionesError(422, "CONFIRMAR", "Primero marcá la confirmación de carga.")
        esperado = data.get("huella")
        if not isinstance(esperado, str) or not esperado:
            raise ComisionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        fresca: dict = {}

        def stale() -> None:
            try:
                q = self._read(scope, lambda L: self._preview(L, texto, contenido))
            except ComisionesError as exc:
                if exc.code in ("NO_OPERAR", "NO_PERIODO"):
                    raise
                raise ComisionesError(503, "FRESH_READ", MSG_DB_READ, "FreshReadError") from None
            if q["df"].empty or _hash(records(q["df"])) != esperado:
                raise ComisionesError(409, "STALE", f"{MSG_STALE} [B12I: preparar_preview_comisiones_rapidas]",
                                      "StaleDecisionError")
            fresca.update(q)

        def lote(u: E.Unidad) -> dict:
            df_f = fresca["df"]
            df_ok = df_f[df_f["estado_validacion"].isin(list(carga.ESTADOS_CARGABLES))].copy()
            return carga.cargar_comisiones_rapidas_lote_v232(u, df_ok, fresca["actual"])

        try:
            res, _ = self._op(record, scope, SPEC_CARGA_LOTE, lote, stale=stale)
        except ComisionesError as exc:
            raise ComisionesError(exc.status, exc.code, f"No se pudo completar la carga rápida masiva: {exc.message}",
                                  exc.error_class) from None
        mensaje = (f"Se cargaron {res.get('comisiones',0)} comisiones, {res.get('horarios',0)} horarios y "
                   f"{res.get('docentes',0)} asignaciones docentes en {float(res.get('segundos',0) or 0):g} s. "
                   f"Duplicadas omitidas: {tot['duplicada']}. Errores omitidos: {tot['error']}.")
        avisos = []
        if int(res.get("ajustes_proyectos", 0) or 0) > 0:
            avisos.append(f"Se aplicaron {int(res.get('ajustes_proyectos',0))} ajuste/s de horas de proyectos por la "
                          "nueva carga de comisiones.")
        return {"mensaje": mensaje, "tono": "success", "avisos": avisos}

    # ================================================================== Excel (descargas: sin compuerta)
    def _fuente_excel(self, scope: Scope, L: Lector):
        from .excel import FuenteExcel
        return FuenteExcel(L, str(scope.institution.get("nombre") or ""), str(scope.department.get("nombre") or ""))

    def modelo_excel(self, record: SessionRecord) -> bytes:
        from .excel import generar_excel_modelo_carga_rapida_comisiones
        scope = self.reader(record)

        def read(L: Lector) -> bytes:
            actual = L.ultimo_periodo()
            return generar_excel_modelo_carga_rapida_comisiones(self._fuente_excel(scope, L),
                                                                actual["id"] if actual else None)

        return self._read(scope, read)

    def periodo_excel(self, record: SessionRecord, periodo_id: Any) -> tuple[bytes, str]:
        from .excel import generar_excel_comisiones_periodo_completado_v175
        scope = self.reader(record)
        pid = _id(periodo_id)

        def read(L: Lector) -> tuple[bytes, str]:
            info = L.periodo_info(pid)
            if info is None:
                raise ComisionesError(404, "NOT_FOUND", MSG_PERIODO_NO_ENCONTRADO)
            contenido = generar_excel_comisiones_periodo_completado_v175(self._fuente_excel(scope, L), pid)
            return contenido, f"comisiones_integral_{R.nombre_archivo_seguro(str(info.get('nombre')))}.xlsx"

        return self._read(scope, read)
