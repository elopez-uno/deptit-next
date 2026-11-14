"""Reglas de pantalla de Investigacion (B13-FIX02, entry l. 64859-65647) sobre la sesion y el contexto de ``auth``.

Alcance (decisiones humanas D1-D9, docs/investigacion_analysis.md §15): las 8 pestañas certificadas y sus 13 writers
(sin los pilotos 8H/8J).  Pendientes visibles: costo salarial (Sueldos) y alta de actos/PDF (Resoluciones y respaldos).

Cada writer certificado que la UI invoca es una operacion B12H propia (``correlation_id`` por writer):
1. comprobaciones de la pantalla sobre lecturas frescas (mismo orden y mensajes que el certificado): sin evento;
2. B10 del writer (``investigacion.write`` / ``investigacion.delete`` / ``proyectos.write`` / ``movimientos.write`` /
   ``documentos.write`` / ``documentos.delete``, con el alcance del registro certificado): DENIED en transaccion propia;
3. B12I capa T (solo ``guardar_investigacion_docente``, ``actualizar_investigacion_docente`` y
   ``cargar_asignaciones_proyectos_excel_v217``): lock de SESION ``deptit_b12i_asignacion_proyecto:{inst}`` en conexion
   dedicada, espera hasta 30 s, ANTES de validar.  Ningun otro writer toma lock;
4. B12I capa U: en el primer writer del clic se relee fresco lo que el usuario vio (``huella``); si cambio -> FAILED
   ``StaleDecisionError`` sin escribir;
5. cada COMMIT certificado con su SUCCESS (``commit_seq``) en esa transaccion; sin COMMITs -> SUCCESS POST_OPERATION
   (tambien cuando el writer devuelve un rechazo de negocio sin escribir); error -> FAILED con ``coupled_commits``.
El ambito (institucion/departamento) sale SIEMPRE de la sesion revalidada; ningun id de tenant llega del cliente.
"""

from __future__ import annotations

import base64
import binascii
import logging
import time
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Iterator, Optional

import pandas as pd
from psycopg import Connection

import audit
from auth import policy
from auth.service import AuthService, SessionRecord
from comisiones.service import _hash, _jsonable, _period, records
from designaciones.repository import DesignacionesRepository
from periodos.service import MSG_AUDIT_POST, MSG_DB_READ, MSG_DB_TRANSACTION, MSG_INSTITUTIONAL, MSG_STALE
from periodos.service import denial_message, scope_message
import uploads

from . import escrituras as E
from . import excel as X
from . import rules as IR
from .lecturas import Lecturas
from .repository import InvestigacionRepository

log = logging.getLogger("deptit_next.investigacion")

DEP = policy.SCOPE_DEPARTMENT
INST = policy.SCOPE_INSTITUTION
ACTION_READ = policy.Action("investigacion", policy.OP_READ, DEP)
ACTION_WRITE = policy.Action("investigacion", policy.OP_WRITE, DEP)
ACTION_WRITE_INST = policy.Action("investigacion", policy.OP_WRITE, INST)
ACTION_DELETE = policy.Action("investigacion", policy.OP_DELETE, DEP)
ACTION_PROY_WRITE = policy.Action("proyectos", policy.OP_WRITE, DEP)
ACTION_PROY_WRITE_INST = policy.Action("proyectos", policy.OP_WRITE, INST)
ACTION_MOVEMENT = policy.Action("movimientos", policy.OP_WRITE, DEP)
ACTION_DOC_WRITE = policy.Action("documentos", policy.OP_WRITE, DEP)
ACTION_DOC_DELETE = policy.Action("documentos", policy.OP_DELETE, DEP)

# B12I (cache_decision_integrity.py l. 130-168): familia "asignacion_proyecto", por institucion (sin departamento).
LOCK_FAMILY = "asignacion_proyecto"
PROJECT_LOCK_FORMAT = "deptit_b12i_asignacion_proyecto:{inst}"
LOCK_WRITERS = frozenset({E.W_GUARDAR_ASIGNACION, E.W_ACTUALIZAR_ASIGNACION, E.W_CARGA_ASIGNACIONES})
LOCK_WAIT_SECONDS = 30.0
LOCK_POLL_SECONDS = 0.1
TRY_SESSION_LOCK_SQL = "SELECT pg_try_advisory_lock(hashtext(%s))"
SESSION_UNLOCK_SQL = "SELECT pg_advisory_unlock(hashtext(%s))"
MSG_LOCK = "Hay otra operación concurrente sobre los mismos datos. No se guardó nada: reintentá en unos instantes."


@dataclass(frozen=True)
class WriterSpec:
    """Writer del registro B10 (legacy_write_actions.py) y su etiqueta B12H (``entity_type_for``/``_entity_param``)."""
    name: str
    action: policy.Action
    entity_type: str
    entity_param: Optional[str]


SPEC_GUARDAR_PROYECTO = WriterSpec(E.W_GUARDAR_PROYECTO, ACTION_WRITE_INST, "proyecto_investigacion", None)
SPEC_ACTUALIZAR_PROYECTO = WriterSpec(E.W_ACTUALIZAR_PROYECTO, ACTION_WRITE, "proyecto_investigacion", "proyecto_id")
SPEC_SUSPENDER_PROYECTO = WriterSpec(E.W_SUSPENDER_PROYECTO, ACTION_WRITE, "proyecto_investigacion", "proyecto_id")
SPEC_ARCHIVAR_PROYECTO = WriterSpec(E.W_ARCHIVAR_PROYECTO, ACTION_WRITE_INST, "proyecto_investigacion", "proyecto_id")
SPEC_ELIMINAR_PROYECTO = WriterSpec(E.W_ELIMINAR_PROYECTO, ACTION_DELETE, "proyecto_investigacion", "proyecto_id")
SPEC_GUARDAR_ASIGNACION = WriterSpec(E.W_GUARDAR_ASIGNACION, ACTION_WRITE, "asignacion_investigacion", "proyecto_id")
SPEC_ACTUALIZAR_ASIGNACION = WriterSpec(E.W_ACTUALIZAR_ASIGNACION, ACTION_WRITE, "asignacion_investigacion",
                                        "proyecto_id")
SPEC_BAJA_ASIGNACION = WriterSpec(E.W_BAJA_ASIGNACION, ACTION_WRITE, "asignacion_investigacion", None)
SPEC_ELIMINAR_ASIGNACION = WriterSpec(E.W_ELIMINAR_ASIGNACION, ACTION_DELETE, "asignacion_investigacion", None)
SPEC_CARGA_PROYECTOS = WriterSpec(E.W_CARGA_PROYECTOS, ACTION_PROY_WRITE_INST, "proyecto", None)
SPEC_CARGA_ASIGNACIONES = WriterSpec(E.W_CARGA_ASIGNACIONES, ACTION_PROY_WRITE, "proyecto", "periodo_id")
SPEC_MOVIMIENTO = WriterSpec(E.W_MOVIMIENTO, ACTION_MOVEMENT, "movimiento", "cuil")
SPEC_VINCULAR_ACTO = WriterSpec(E.W_VINCULAR_ACTO, ACTION_DOC_WRITE, "documento", "documento_id")
SPEC_DESVINCULAR_ACTO = WriterSpec(E.W_DESVINCULAR_ACTO, ACTION_DOC_DELETE, "acto_administrativo", "documento_id")

# --- textos certificados (entry l. 64859-65647; v217 l. 48390-48870 / 49210-49290; v266/v267) ------------------------
MSG_VALOR_INVALIDO = "Uno de los valores enviados no es válido para este formulario."
MSG_SELECCION_INVALIDA = "La selección no corresponde a las filas mostradas. Actualizá la pantalla."
MSG_PERIODO_NO_ENCONTRADO = "No se encontró el período seleccionado."
MSG_NOMBRE = "Completá el nombre del proyecto."
MSG_FECHAS = "La fecha de finalización no puede ser anterior a la fecha de inicio."
MSG_ALTA_OK = "Proyecto institucional registrado. Ya está disponible en todos los departamentos."
MSG_ALTA_DUP = "Ya existe un proyecto con ese código o con esos mismos datos."
MSG_EDIT_PROY_OK = "Proyecto actualizado. Las asignaciones históricas conservaron su vínculo."
MSG_ROL = "Completá el rol."
MSG_SIN_PERIODO_EDITAR = "No hay período abierto. Solo se editan asignaciones activas del período abierto."
MSG_SIN_PERIODO_BAJA = "No hay período abierto."
MSG_SIN_PERIODO_SUSP = "No hay período abierto para aplicar la suspensión."
MSG_SIN_PERIODO_ASIGNAR = "No hay período abierto. Primero creá o abrí un período."
MSG_CONFIRMAR_BAJA = "Primero confirmá la baja."
MSG_SEL_ASIGNACION = "Seleccioná una asignación desde la tabla."
MSG_BAJA_OK = "Asignación dada de baja. Se conserva en el historial."
MSG_CONFIRMAR_SUSP = "Primero confirmá la suspensión."
MSG_MOTIVO_SUSP = "Completá el motivo de la suspensión."
MSG_SEL_PROYECTO = "Seleccioná un proyecto desde la tabla."
MSG_CONFIRMAR_ARCHIVO = "Primero confirmá el archivo."
MSG_CONFIRMAR_ELIMINAR = "Primero confirmá que entendés el alcance de la eliminación."
MSG_TEXTO_ELIMINAR = "El código o nombre escrito no coincide exactamente."
MSG_CONFIRMAR_ELIMINAR_ERROR = "Primero confirmá la eliminación definitiva."
MSG_CARGA_VACIA = "El archivo no contiene proyectos nuevos ni asignaciones nuevas para procesar."
MSG_CARGA_SIN_PERIODO = "Hay asignaciones docentes en el Excel, pero no existe un período abierto para asociarlas."
MSG_EXCEL_INVALIDO = "No se pudo procesar el Excel: el archivo no es un .xlsx válido."
MSG_EXCEL_GRANDE = "El archivo supera el tamaño máximo admitido (15 MB)."
MSG_ACTO_PROYECTO_OK = "Acto administrativo vinculado al proyecto."
MAX_EXCEL_BYTES = 15 * 1024 * 1024


class InvestigacionError(Exception):
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
    rol: Optional[str]
    dep_nombre: str


def _id_o_none(value: Any) -> Optional[int]:
    """Id de asignacion de un integrante (E4-04: cruza el costo imputado del detalle v257, l. 33519)."""
    try:
        return None if value is None or pd.isna(value) else int(value)
    except (TypeError, ValueError):
        return None


def _named(row: dict) -> dict:
    return {"id": int(row["id"]), "nombre": row.get("nombre")}


def _id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _ids(values: Any) -> list[int]:
    if values in (None, ""):
        return []
    if not isinstance(values, list):
        raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
    return [_id(v) for v in values]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
    return str(value)


def _bool(value: Any) -> bool:
    if value in (None, ""):
        return False
    if not isinstance(value, bool):
        raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _fecha(value: Any) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO) from None


def _numero(value: Any, minimo: float, maximo: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
    v = float(value)
    if v != v or v < minimo or v > maximo:
        raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
    return v


def _anio(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1900 or value > 2100:
        raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


# --- huellas B12I capa U (lo que el usuario vio) ------------------------------------------------------------------
_CAMPOS_PROYECTO = ("id", "nombre_proyecto", "codigo_proyecto", "instituto_proyecto", "anio_llamado", "fecha_inicio",
                    "fecha_fin", "periodo_ejecucion", "observaciones", "estado", "fecha_suspension",
                    "motivo_suspension", "departamento_creador_id")


def huella_proyecto(p: Optional[dict]) -> str:
    return _hash({k: (p or {}).get(k) for k in _CAMPOS_PROYECTO} if p else None)


def huella_asignacion(a: Optional[dict]) -> str:
    if not a:
        return _hash(None)
    return _hash({"id": a.get("id"), "proyecto_id": a.get("proyecto_id"), "periodo_id": a.get("periodo_id"),
                  "cuil": a.get("cuil"), "rol": a.get("rol"), "horas": float(a.get("horas_asignadas") or 0),
                  "estado": str(a.get("estado_asignacion") or "Activa"), "obs": str(a.get("observaciones") or ""),
                  "dep": a.get("departamento_asignacion_id", a.get("departamento_id"))})


ASIG_HUELLA_SQL = """
    SELECT id, proyecto_id, periodo_id, cuil, rol, horas_asignadas,
           COALESCE(estado_asignacion, 'Activa') AS estado_asignacion, observaciones,
           departamento_id AS departamento_asignacion_id
    FROM investigacion_docente
    WHERE id = %s AND institucion_id = %s
    LIMIT 1
"""


def _con_huella(rows: list[dict], fn: Callable[[dict], str]) -> list[dict]:
    for r in rows:
        r["huella"] = fn(r)
    return rows


class InvestigacionService:
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
            raise InvestigacionError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        if not any(m[0] == "investigacion" for m in visible) or resolution.department is None:
            raise InvestigacionError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        actor = policy.actor_from_session(user, session_scope)
        # _departamento_actual_operativo_nombre (l. 6616): nombre del usuario o, si no tiene, el del ambito.
        dep_nombre = str(user.get("departamento_nombre") or "") or str(resolution.department.get("nombre") or "")
        return Scope(int(resolution.institution["id"]), int(resolution.department["id"]), resolution.institution,
                     resolution.department, actor.role, dep_nombre)

    def _require_read(self, record: SessionRecord) -> None:
        actor = policy.actor_from_session(record.user, record.scope)
        decision = policy.decide(actor, ACTION_READ)
        if not decision.allowed:
            raise InvestigacionError(403, "DENIED", denial_message(decision, ACTION_READ))

    def _read(self, scope: Scope, fn: Callable[[Lecturas], Any]) -> Any:
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                repo = InvestigacionRepository(conn, scope.institution_id, scope.department_id)
                return fn(Lecturas(repo, self.today(), scope.rol))
        except InvestigacionError:
            raise
        except Exception as exc:
            log.error("investigacion: lectura fallida: %s", type(exc).__name__)
            raise InvestigacionError(503, "DB_READ", MSG_DB_READ) from None

    def reader(self, record: SessionRecord) -> Scope:
        scope = self.scope(record)
        self._require_read(record)
        return scope

    def _permisos(self, record: SessionRecord) -> dict:
        actor = policy.actor_from_session(record.user, record.scope)

        def ok(action):
            return policy.decide(actor, action).allowed
        return {"puede_escribir": ok(ACTION_WRITE), "puede_borrar": ok(ACTION_DELETE),
                "puede_cargar": ok(ACTION_PROY_WRITE), "puede_movimiento": ok(ACTION_MOVEMENT),
                "puede_vincular_acto": ok(ACTION_DOC_WRITE), "puede_desvincular_acto": ok(ACTION_DOC_DELETE)}

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
        key = PROJECT_LOCK_FORMAT.format(inst=scope.institution_id)
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
                        raise InvestigacionError(409, "LOCK", f"{MSG_LOCK} [B12I: {LOCK_FAMILY}]", "ConsistencyLockError")
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
            entity_raw: Any = None, stale: Optional[Callable[[], None]] = None) -> Any:
        """Un writer certificado completo: B10 -> B12I (T y U) -> sus COMMITs con SUCCESS, o FAILED."""
        actor = policy.actor_from_session(record.user, record.scope)
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(spec.name, spec.action, spec.entity_type, audit_actor, spec.entity_param, entity_raw)
        decision = policy.decide(actor, spec.action)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code, metadata={"b10_decision": decision.code})
            raise InvestigacionError(403, "DENIED", denial_message(decision, spec.action), "PermissionError")
        unidad = E.Unidad(self._transaction, op, scope.institution_id, scope.department_id, today=self.today(),
                          now=self.now(), usuario=str(record.user.get("email") or ""), rol=scope.rol,
                          dep_nombre=scope.dep_nombre)

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
        except InvestigacionError as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code=exc.error_class,
                           metadata={"coupled_commits": op.coupled_commits})
            raise
        except ValueError as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code="ValueError",
                           metadata={"coupled_commits": op.coupled_commits})
            raise InvestigacionError(422, "REJECTED", str(exc)) from None
        except E.AuditoriaFallida:
            self._separate(op, audit.OUTCOME_FAILED, error_code="AuditPersistenceError:AUDIT_INSERT_FAILED",
                           metadata={"coupled_commits": op.coupled_commits})
            raise InvestigacionError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]",
                                     "AuditPersistenceError") from None
        except Exception as exc:
            log.error("investigacion: %s falló tras %d COMMIT(s): %s", spec.name, op.coupled_commits,
                      type(exc).__name__)
            self._separate(op, audit.OUTCOME_FAILED, error_code=audit.error_code_of(exc),
                           metadata={"coupled_commits": op.coupled_commits})
            raise InvestigacionError(503, "DB_ERROR", MSG_DB_TRANSACTION) from None
        if op.coupled_commits == 0:
            if not self._separate(op, audit.OUTCOME_SUCCESS,
                                  metadata={"coupled_commits": 0, "post_reason": "NO_POOLED_COMMIT"}):
                raise InvestigacionError(503, "AUDIT", MSG_AUDIT_POST)
        return result

    def _stale(self, scope: Scope, esperado: Any, fresh: Callable[[Lecturas], Any], label: str) -> Callable[[], None]:
        """B12I capa U: lo que el usuario vio se relee fresco antes del primer SQL del writer."""
        def check() -> None:
            try:
                actual = self._read(scope, fresh)
            except InvestigacionError:
                raise InvestigacionError(503, "FRESH_READ", MSG_DB_READ, "FreshReadError") from None
            if actual != esperado:
                raise InvestigacionError(409, "STALE", f"{MSG_STALE} [B12I: {label}]", "StaleDecisionError")
        return check

    @staticmethod
    def _huella_periodo(L: Lecturas) -> str:
        return _hash(_period(L.periodo_abierto()))

    def _stale_proyecto(self, scope: Scope, proyecto_id: int, huella: Any, con_periodo: Any = None):
        def fresh(L: Lecturas):
            out = huella_proyecto(L.proyecto_por_id(proyecto_id))
            return out if con_periodo is None else (out, self._huella_periodo(L))
        esperado = huella if con_periodo is None else (huella, con_periodo)
        return self._stale(scope, esperado, fresh, "proyectos_investigacion")

    def _stale_asignacion(self, scope: Scope, asignacion_id: int, huella: Any, con_periodo: Any = None):
        def fresh(L: Lecturas):
            fila = L.repo.read_raw(ASIG_HUELLA_SQL, [asignacion_id, scope.institution_id])
            out = huella_asignacion(fila.iloc[0].to_dict() if not fila.empty else None)
            return out if con_periodo is None else (out, self._huella_periodo(L))
        esperado = huella if con_periodo is None else (huella, con_periodo)
        return self._stale(scope, esperado, fresh, "get_investigacion_docente")

    # ------------------------------------------------------------------ overview (encabezado l. 64860-64873)
    def overview(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(L: Lecturas):
            abierto = L.periodo_abierto()
            periodos = L.periodos()
            return {
                "periodos": [_period(r) for r in periodos.to_dict(orient="records")] if not periodos.empty else [],
                "abierto": _period(abierto),
                "historico_abierto": bool(abierto and L.es_historico(abierto["id"])),
                "huella_periodo": self._huella_periodo(L),
            }
        data = self._read(scope, read)
        return {"contexto": {"institucion": _named(scope.institution), "departamento": _named(scope.department)},
                **data, "rol": scope.rol, "permisos": self._permisos(record),
                "ayuda_radicacion": IR.ayuda_radicacion_v216(scope.dep_nombre),
                "estados_alta": IR.ESTADOS_ALTA, "roles_sugeridos": IR.ROLES_EXCEL_V217}

    def alertas(self, record: SessionRecord) -> dict:
        """``render_alertas_exceso_proyectos_v184`` (l. 40634): solo con periodo abierto."""
        scope = self.reader(record)

        def read(L: Lecturas):
            abierto = L.periodo_abierto()
            if abierto is None:
                return {"excesos": []}
            return {"excesos": records(L.detectar_excesos(int(abierto["id"])))}
        return self._read(scope, read)

    def post_accion(self, record: SessionRecord, data: dict) -> dict:
        """``render_alerta_post_accion_proyecto_v187`` (l. 40751): balance actual del docente tras la accion."""
        scope = self.reader(record)
        cuil = _text(data.get("cuil")).strip()
        periodo_id = _id(data.get("periodo_id"))

        def read(L: Lecturas):
            abierto = L.periodo_abierto()
            if abierto is None or int(abierto["id"]) != periodo_id:
                return {"vigente": False}
            cap = L.capacidad(cuil, periodo_id)
            return {"vigente": True, "capacidad": cap,
                    "detalle": records(L.detalle_proyectos_docente_v187(cuil, periodo_id))}
        return self._read(scope, read)

    # ------------------------------------------------------------------ Pestaña 1: proyectos vigentes (v101)
    def _vista_vigentes(self, L: Lecturas) -> tuple[pd.DataFrame, Optional[dict], pd.DataFrame, pd.DataFrame]:
        abierto = L.periodo_abierto()
        if abierto is not None:
            df = L.proyectos(solo_activos=True, periodo_id=int(abierto["id"]))
        else:
            df = L.proyectos(solo_activos=True)
            if not df.empty:
                df = df[df["situacion"].isin(["En ejecución", "Programado"])].copy()
        if df is None or df.empty:
            return pd.DataFrame(), abierto, pd.DataFrame(), pd.DataFrame()
        vista = df.copy().reset_index(drop=True)
        rad = vista["instituto_proyecto"].fillna("").astype(str).str.strip()
        creador = vista["departamento_creador"].fillna("").astype(str).str.strip()
        vista["instituto_proyecto"] = rad.where(rad.ne(""), creador)
        vista["responsable_proyecto_v244"] = vista["instituto_proyecto"].fillna("").astype(str).str.strip()
        docs, mapa = L.actos_por_proyecto(pd.to_numeric(vista["id"], errors="coerce").dropna().astype(int).tolist())
        vista["actos_documentales_v263"] = vista["id"].apply(lambda x: mapa.get(int(x), "Sin acto vinculado"))
        nombre_periodo = str((abierto or {}).get("nombre") or "").strip()
        asig = L.asignaciones(incluir_bajas=True, todos_departamentos=True)
        if asig is None:
            asig = pd.DataFrame()
        horas_por_proyecto = {}
        if not asig.empty and "proyecto_id" in asig.columns and nombre_periodo and "periodo" in asig.columns:
            act = self._activas_del_periodo(L, asig, abierto)
            if not act.empty:
                act["_pid"] = pd.to_numeric(act["proyecto_id"], errors="coerce")
                act["_hs"] = pd.to_numeric(act.get("horas_asignadas", pd.Series(index=act.index, dtype=float)),
                                           errors="coerce").fillna(0)
                horas_por_proyecto = act.dropna(subset=["_pid"]).groupby("_pid")["_hs"].sum().to_dict()
        vista["horas_semanales"] = vista["id"].apply(lambda x: round(float(horas_por_proyecto.get(float(x), 0.0) or 0), 2))
        vista["meses_ejecucion_v258"] = vista.apply(lambda r: IR.meses_ejecucion_v258(r.get("fecha_inicio"),
                                                                                       r.get("fecha_fin")), axis=1)
        vista["horas_totales_periodo"] = vista.apply(
            lambda r: IR.horas_totales_ejecucion_v162(r.get("horas_semanales", 0), r.get("fecha_inicio"),
                                                      r.get("fecha_fin")), axis=1)
        if abierto is not None and not asig.empty:
            try:
                from .lecturas import enriquecer_v277
                asig = enriquecer_v277(asig, L.padron())
            except Exception:
                pass
        return vista, abierto, asig, docs

    @staticmethod
    def _activas_del_periodo(L: Lecturas, df: pd.DataFrame, abierto: Optional[dict]) -> pd.DataFrame:
        """``_asignaciones_activas_del_periodo`` (l. 33322): por NOMBRE del periodo; en historico, foto al cierre."""
        nombre = str((abierto or {}).get("nombre") or "").strip()
        if df is None or df.empty or not nombre or "periodo" not in df.columns:
            return pd.DataFrame(columns=df.columns if isinstance(df, pd.DataFrame) else None)
        salida = df[df["periodo"].fillna("").astype(str).str.strip() == nombre].copy()
        if abierto is not None and L.es_historico(abierto.get("id")):
            from .lecturas import filtrar_cierre_v183
            salida = filtrar_cierre_v183(salida, True, L.fecha_cierre(abierto.get("id")))
        elif "estado_asignacion" in salida.columns:
            salida = salida[salida["estado_asignacion"].fillna("Activa").astype(str).str.strip().str.lower() == "activa"].copy()
        return salida

    def vigentes(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(L: Lecturas):
            vista, abierto, asig, _ = self._vista_vigentes(L)
            caption = (f"Se muestran los proyectos cuyas fechas se superponen con {abierto['nombre']}."
                       if abierto is not None else
                       "No hay un período abierto; se muestran proyectos activos o programados según la fecha actual.")
            if vista.empty:
                return {"caption": caption, "filas": [], "lista": []}
            filas = records(vista)
            for f in filas:
                f["huella"] = huella_proyecto(f)
            lista = self._lista_completa(L, vista, asig, abierto)
            return {"caption": caption, "filas": filas, "lista": lista}
        return self._read(scope, read)

    def _lista_completa(self, L: Lecturas, vista: pd.DataFrame, asig: pd.DataFrame, abierto) -> list[dict]:
        """Expander "📋 Ver listado completo de proyectos vigentes" (l. 33577)."""
        df_lista = vista.copy()
        if not asig.empty and "proyecto_id" in asig.columns:
            actuales, historicos = {}, {}
            for pid, grupo in asig.groupby(pd.to_numeric(asig["proyecto_id"], errors="coerce"), dropna=True):
                try:
                    pid_int = int(pid)
                except Exception:
                    continue
                g_actual = self._activas_del_periodo(L, grupo, abierto)
                actuales[pid_int] = {"docentes_periodo_activo": _nunique(g_actual, "cuil"),
                                     "asignaciones_periodo_activo": int(len(g_actual)),
                                     "horas_semanales": _sum_horas(g_actual)}
                comp = grupo.copy()
                if "estado_asignacion" in comp.columns:
                    comp = comp[comp["estado_asignacion"].fillna("Activa").astype(str).str.strip().str.lower() != "baja"].copy()
                historicos[pid_int] = {"docentes_historicos_v102": _nunique(grupo, "cuil"),
                                       "asignaciones_historicas_v102": int(len(comp)),
                                       "horas_historicas_v102": _sum_horas(comp)}
            for c in ("docentes_periodo_activo", "asignaciones_periodo_activo", "horas_semanales"):
                df_lista[c] = df_lista["id"].apply(lambda x, c=c: actuales.get(int(x), {}).get(c, 0))
            df_lista["horas_totales_periodo"] = df_lista.apply(
                lambda r: IR.horas_totales_ejecucion_v162(r.get("horas_semanales", 0), r.get("fecha_inicio"),
                                                          r.get("fecha_fin")), axis=1)
            for c in ("docentes_historicos_v102", "asignaciones_historicas_v102", "horas_historicas_v102"):
                df_lista[c] = df_lista["id"].apply(lambda x, c=c: historicos.get(int(x), {}).get(c, 0))
        else:
            for c in ["docentes_periodo_activo", "asignaciones_periodo_activo", "horas_semanales",
                      "docentes_historicos_v102", "asignaciones_historicas_v102", "horas_historicas_v102"]:
                df_lista[c] = 0
            df_lista["horas_totales_periodo"] = 0.0
        cols = ["codigo_proyecto", "nombre_proyecto", "actos_documentales_v263", "horas_semanales",
                "meses_ejecucion_v258", "horas_totales_periodo", "instituto_proyecto", "anio_llamado", "fecha_inicio",
                "fecha_fin", "periodo_ejecucion", "situacion", "estado", "departamento_creador",
                "docentes_periodo_activo", "asignaciones_periodo_activo", "docentes_historicos_v102",
                "asignaciones_historicas_v102", "horas_historicas_v102", "fecha_carga", "fecha_suspension",
                "motivo_suspension", "observaciones"]
        return records(df_lista, cols)

    def ficha(self, record: SessionRecord, data: dict) -> dict:
        """Ficha del proyecto seleccionado (l. 33274-33575).  El costo salarial queda pendiente de Sueldos (D1/D3)."""
        scope = self.reader(record)
        proyecto_id = _id(data.get("proyecto_id"))

        def read(L: Lecturas):
            vista, abierto, asig, docs = self._vista_vigentes(L)
            if vista.empty or proyecto_id not in set(pd.to_numeric(vista["id"], errors="coerce").dropna().astype(int)):
                raise InvestigacionError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            fila = vista[pd.to_numeric(vista["id"], errors="coerce").eq(proyecto_id)].iloc[0].to_dict()
            integrantes = asig[pd.to_numeric(asig["proyecto_id"], errors="coerce") == proyecto_id].copy() \
                if not asig.empty and "proyecto_id" in asig.columns else pd.DataFrame()
            activos = self._activas_del_periodo(L, integrantes, abierto)
            historico_comp = integrantes.copy()
            if not historico_comp.empty and "estado_asignacion" in historico_comp.columns:
                historico_comp = historico_comp[historico_comp["estado_asignacion"].fillna("Activa").astype(str)
                                                .str.strip().str.lower() != "baja"].copy()
            hist_ctx = bool(abierto is not None and L.es_historico(abierto.get("id")))
            docs_sel = docs[pd.to_numeric(docs["proyecto_id"], errors="coerce").eq(float(proyecto_id))].copy() \
                if isinstance(docs, pd.DataFrame) and not docs.empty else pd.DataFrame()
            actos = []
            for _, r in docs_sel.iterrows():
                actos.append({"codigo": IR.etiqueta_acto_v263(r.get("tipo_documento"), r.get("numero")),
                              "acto": IR.etiqueta_acto_v263(r.get("tipo_documento"), r.get("numero"),
                                                            r.get("dependencia_emisora")),
                              "documento_id": int(r.get("documento_id")),
                              "dependencia_emisora": r.get("dependencia_emisora"), "fecha": _jsonable(r.get("fecha")),
                              "categoria": r.get("categoria"), "detalle": r.get("detalle")})
            orden = [c for c in ["departamento_origen_docente", "docente"] if c in activos.columns]
            vista_activos = activos.sort_values(orden) if orden and not activos.empty else activos
            hs_sem = float(pd.to_numeric(pd.Series([fila.get("horas_semanales")]), errors="coerce").fillna(0).iloc[0])
            v = IR.valor_proyecto_v101
            hist_cols = ["periodo", "departamento_origen_docente", "docente", "cuil", "rol", "horas_asignadas",
                         "estado_asignacion", "fecha_carga", "fecha_baja", "motivo_baja", "observaciones"]
            historial = records(integrantes, hist_cols)
            for h in historial:
                h["computa"] = "No" if str(h.get("estado_asignacion") or "Activa").strip().lower() == "baja" else "Sí"
            return {
                "proyecto_id": proyecto_id,
                "encabezado": {"nombre": v(fila.get("nombre_proyecto"), "Proyecto sin nombre"),
                               "codigo": v(fila.get("codigo_proyecto"), "Sin código"),
                               "situacion": v(fila.get("situacion"), "Sin situación"),
                               "estado": v(fila.get("estado"), "Activo")},
                "datos": {"area": v(fila.get("instituto_proyecto")), "inicio": v(_jsonable(fila.get("fecha_inicio"))),
                          "fin": v(_jsonable(fila.get("fecha_fin"))), "anio": v(fila.get("anio_llamado")),
                          "periodo_ejecucion": v(fila.get("periodo_ejecucion")),
                          "creador": v(fila.get("departamento_creador")), "fecha_carga": v(fila.get("fecha_carga")),
                          "observaciones": v(fila.get("observaciones"), ""),
                          "fecha_suspension": v(_jsonable(fila.get("fecha_suspension")), ""),
                          "motivo_suspension": v(fila.get("motivo_suspension"), "")},
                "actos": actos,
                "metricas": {"horas_semanales": IR.horas_proyecto_v101(hs_sem),
                             "meses": IR.meses_ejecucion_v258(fila.get("fecha_inicio"), fila.get("fecha_fin")),
                             "horas_totales": IR.horas_proyecto_v101(IR.horas_totales_ejecucion_v162(
                                 hs_sem, fila.get("fecha_inicio"), fila.get("fecha_fin")))},
                "periodo_activo": str((abierto or {}).get("nombre") or "").strip(),
                "historico_contexto": hist_ctx,
                "participacion": {
                    "docentes_activos": _nunique(activos, "cuil"), "asignaciones_activas": int(len(activos)),
                    "horas_activas": IR.horas_proyecto_v101(_sum_horas(activos)),
                    "departamentos_activos": _nunique_deps(activos),
                    "docentes_historicos": _nunique(integrantes, "cuil"),
                    "asignaciones_historicas": int(len(historico_comp)),
                    "horas_historicas": IR.horas_proyecto_v101(_sum_horas(historico_comp)),
                    "departamentos_historicos": _nunique_deps(integrantes)},
                "integrantes": [{"id": _id_o_none(r.get("id")), "docente": v(r.get("docente"), "Docente"), "cuil": v(r.get("cuil")),
                                 "departamento": v(r.get("departamento_origen_docente") or r.get("departamento_asignacion")),
                                 "rol": v(r.get("rol")), "horas": IR.horas_proyecto_v101(r.get("horas_asignadas")),
                                 "observaciones": v(r.get("observaciones"), "")}
                                for _, r in vista_activos.iterrows()],
                "historial": historial,
                "proyecto": {"nombre": str(fila.get("nombre_proyecto") or ""),
                             "codigo": v(fila.get("codigo_proyecto"), "Sin código")},
            }
        return self._read(scope, read)

    # ------------------------------------------------------------------ actos (v266 / v267 / v261)
    def actos(self, record: SessionRecord) -> dict:
        """Repositorio de Resoluciones y respaldos para el selector v266 (solo lectura)."""
        scope = self.reader(record)
        docs = self._read(scope, lambda L: DesignacionesRepository.documentos(L.repo))
        out = []
        for d in docs:
            row = {k: _jsonable(d.get(k)) for k in ("id", "fecha", "tipo_documento", "numero", "dependencia_emisora",
                                                     "categoria", "titulo", "detalle", "periodo")}
            row["etiqueta"] = IR.etiqueta_acto_v263(d.get("tipo_documento"), d.get("numero"), d.get("dependencia_emisora"))
            out.append(row)
        return {"documentos": out}

    def _documento_valido(self, scope: Scope, documento_id: Any) -> int:
        did = _id(documento_id)
        docs = self._read(scope, lambda L: DesignacionesRepository.documentos(L.repo))
        if did not in {int(d["id"]) for d in docs}:
            raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
        return did

    def vincular_acto(self, record: SessionRecord, data: dict) -> dict:
        """Vincular un acto existente a uno o varios proyectos (v266 individual / v267 masivo)."""
        scope = self.reader(record)
        ids = _ids(data.get("proyecto_ids"))
        if not ids:
            raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
        documento_id = self._documento_valido(scope, data.get("documento_id"))
        huellas = data.get("huellas") or {}
        catalogo = self._read(scope, lambda L: {int(r["id"]): r for r in L.proyectos().to_dict(orient="records")})
        proyectos = []
        for pid in ids:
            if pid not in catalogo or huella_proyecto(catalogo[pid]) != huellas.get(str(pid)):
                raise InvestigacionError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            p = catalogo[pid]
            proyectos.append({"tipo": IR.TIPO, "id": pid, "nombre": str(p.get("nombre_proyecto") or ""),
                              "codigo": str(p.get("codigo_proyecto") or "")})
        esperado = {pid: huellas.get(str(pid)) for pid in ids}

        def fresh(L: Lecturas):
            return {pid: huella_proyecto(L.proyecto_por_id(pid)) for pid in ids}
        stale = self._stale(scope, esperado, fresh, "proyectos_investigacion")
        n = self._op(record, scope, SPEC_VINCULAR_ACTO, lambda u: E.vincular_proyectos_documento_v261(
            u, documento_id, proyectos), entity_raw=documento_id, stale=stale)
        if data.get("individual"):
            return {"mensaje": MSG_ACTO_PROYECTO_OK, "tono": "success"}
        return {"mensaje": f"Acto administrativo vinculado a {n} proyecto/s.", "tono": "success"}

    def desvincular_acto(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        ids = _ids(data.get("proyecto_ids"))
        if not ids:
            raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
        documento_id = self._documento_valido(scope, data.get("documento_id"))
        huellas = data.get("huellas") or {}
        catalogo = self._read(scope, lambda L: {int(r["id"]): huella_proyecto(r)
                                                for r in L.proyectos().to_dict(orient="records")})
        for pid in ids:
            if catalogo.get(pid) is None or catalogo[pid] != huellas.get(str(pid)):
                raise InvestigacionError(409, "SELECCION", MSG_SELECCION_INVALIDA)

        def fresh(L: Lecturas):
            return {pid: huella_proyecto(L.proyecto_por_id(pid)) for pid in ids}
        stale = self._stale(scope, {pid: huellas.get(str(pid)) for pid in ids}, fresh, "proyectos_investigacion")
        n = self._op(record, scope, SPEC_DESVINCULAR_ACTO, lambda u: E.desvincular_acto_proyectos_masivo_v267(
            u, documento_id, IR.TIPO, ids), entity_raw=documento_id, stale=stale)
        return {"mensaje": f"Se quitaron {n} vínculo/s de proyecto con ese acto administrativo.", "tono": "warning"}

    # ------------------------------------------------------------------ Pestaña 2: nuevo proyecto
    def guardar_proyecto(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        nombre = _text(data.get("nombre"))
        codigo = _text(data.get("codigo"))
        instituto = _text(data.get("instituto"))
        anio = _anio(data.get("anio_llamado"))
        inicio, fin = _fecha(data.get("fecha_inicio")), _fecha(data.get("fecha_fin"))
        estado = _text(data.get("estado"))
        if estado not in IR.ESTADOS_ALTA:
            raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
        obs = _text(data.get("observaciones"))
        documento_id = None
        if data.get("documento_id") not in (None, ""):
            documento_id = self._documento_valido(scope, data.get("documento_id"))
        if not nombre.strip():
            raise InvestigacionError(422, "VALIDATION", MSG_NOMBRE)
        if fin < inicio:
            raise InvestigacionError(422, "VALIDATION", MSG_FECHAS)
        pid, creado = self._op(record, scope, SPEC_GUARDAR_PROYECTO, lambda u: E.guardar_proyecto_investigacion(
            u, nombre, codigo, instituto, int(anio), inicio, fin, obs, estado))
        if not creado:
            return {"mensaje": MSG_ALTA_DUP, "tono": "warning", "sin_cambios": True}
        if documento_id is not None and pid is not None:
            self._op(record, scope, SPEC_VINCULAR_ACTO, lambda u: E.vincular_proyectos_documento_v261(
                u, documento_id, [{"tipo": IR.TIPO, "id": int(pid), "nombre": nombre, "codigo": codigo}]),
                entity_raw=documento_id)
        return {"mensaje": MSG_ALTA_OK, "tono": "success", "pestana": "vigentes"}

    # ------------------------------------------------------------------ Pestaña 3: asignar docentes (v217 / v270)
    def asignar_proyectos(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(L: Lecturas):
            abierto = L.periodo_abierto()
            if abierto is None:
                return {"periodo": None, "proyectos": []}
            df = L.proyectos(solo_activos=True, periodo_id=int(abierto["id"]))
            filas = _con_huella(records(df), huella_proyecto)
            return {"periodo": _period(abierto), "proyectos": filas}
        return self._read(scope, read)

    @staticmethod
    def _padron_info(df: pd.DataFrame) -> dict:
        return {"consolidado": df.attrs.get("consolidado_docentes_unicos_v276"),
                "selector": df.attrs.get("selector_docentes_unicos_v276"),
                "diagnosticos": list(df.attrs.get("diagnostico_v276", []) or [])}

    def asignar_detalle(self, record: SessionRecord, data: dict) -> dict:
        """Integrantes actuales del proyecto + padron v276 sin los ya asignados + eliminables por error."""
        scope = self.reader(record)
        proyecto_id = _id(data.get("proyecto_id"))

        def read(L: Lecturas):
            abierto = L.periodo_abierto()
            if abierto is None:
                raise InvestigacionError(409, "NO_PERIODO", MSG_SIN_PERIODO_ASIGNAR, tone="warning")
            pid_per = int(abierto["id"])
            vigentes = L.proyectos(solo_activos=True, periodo_id=pid_per)
            if proyecto_id not in set(pd.to_numeric(vigentes.get("id", pd.Series(dtype=float)), errors="coerce")
                                      .dropna().astype(int)):
                raise InvestigacionError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            integrantes = L.integrantes(proyecto_id, pid_per)
            padron = L.padron()
            info = self._padron_info(padron)
            asignados = {IR.clave_cuil(x) for x in integrantes.get("cuil", pd.Series(dtype=str)).dropna().astype(str)
                         if IR.clave_cuil(x)} if not integrantes.empty else set()
            disponibles = padron.copy()
            if not disponibles.empty:
                disponibles = disponibles[~disponibles["cuil"].astype(str).map(IR.clave_cuil).isin(asignados)].copy()
                orden = [c for c in ["nombre_completo", "cuil"] if c in disponibles.columns]
                disponibles = disponibles.sort_values(orden, kind="stable").reset_index(drop=True)
            eliminables = integrantes.copy()
            if scope.rol not in ["superadmin", "coordinador_institucional"] and not eliminables.empty \
                    and "departamento_asignacion_id" in eliminables.columns:
                eliminables = eliminables[pd.to_numeric(eliminables["departamento_asignacion_id"], errors="coerce")
                                          == int(scope.department_id)].copy()
            repetidos = bool(not integrantes.empty and integrantes.duplicated(subset=["cuil"], keep=False).any())
            filas_int = records(integrantes)
            return {"periodo": _period(abierto), "integrantes": _con_huella(filas_int, huella_asignacion),
                    "huella_integrantes": _hash([r["huella"] for r in filas_int]),
                    "duplicados_legacy": repetidos, "padron": info,
                    "docentes": records(disponibles, ["cuil", "nombre_completo", "legajo", "cargo_final", "cargo",
                                                      "horas_designadas", "tipo_docente", "departamento_origen"]),
                    "eliminables": _con_huella(records(eliminables), huella_asignacion)}
        return self._read(scope, read)

    def capacidad(self, record: SessionRecord, data: dict) -> dict:
        """``_capacidad_proyecto_ui_v217`` / capacidad con exclusion al editar (solo informativa)."""
        scope = self.reader(record)
        cuiles = data.get("cuiles")
        if not isinstance(cuiles, list) or not cuiles or len(cuiles) > 500:
            raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
        excluir_id = data.get("excluir_id")
        excluir_id = _id(excluir_id) if excluir_id not in (None, "") else None

        def read(L: Lecturas):
            abierto = L.periodo_abierto()
            if abierto is None:
                return {"capacidades": {}}
            out = {}
            for c in cuiles:
                cuil = _text(c).strip()
                if not cuil:
                    continue
                cap = L.capacidad(cuil, int(abierto["id"]), excluir_tipo="investigacion" if excluir_id else None,
                                  excluir_id=excluir_id)
                out[cuil] = {**cap, "mensaje": IR.mensaje_capacidad_v184(cap)}
            return {"capacidades": out}
        return self._read(scope, read)

    def asignar(self, record: SessionRecord, data: dict) -> dict:
        """Boton "💾 Asignar N docente/s al proyecto": 2N operaciones independientes (alta + movimiento por docente)."""
        scope = self.reader(record)
        proyecto_id = _id(data.get("proyecto_id"))
        docentes = data.get("docentes")
        if not isinstance(docentes, list) or not docentes:
            raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)

        def read(L: Lecturas):
            abierto = L.periodo_abierto()
            if abierto is None:
                raise InvestigacionError(409, "NO_PERIODO", MSG_SIN_PERIODO_ASIGNAR, tone="warning")
            vig = L.proyectos(solo_activos=True, periodo_id=int(abierto["id"]))
            fila = vig[pd.to_numeric(vig.get("id", pd.Series(dtype=float)), errors="coerce").eq(proyecto_id)] \
                if not vig.empty else vig
            if fila.empty:
                raise InvestigacionError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            integrantes = L.integrantes(proyecto_id, int(abierto["id"]))
            huellas_int = [huella_asignacion(r) for r in records(integrantes)]
            return {"abierto": abierto, "proyecto": fila.iloc[0].to_dict(), "padron": L.padron(),
                    "huella_integrantes": _hash(huellas_int), "huella_periodo": self._huella_periodo(L)}
        ctx = self._read(scope, read)
        abierto, proyecto = ctx["abierto"], ctx["proyecto"]
        padron = ctx["padron"]
        nombres = {IR.clave_cuil(r.get("cuil")): (str(r.get("cuil") or ""), str(r.get("nombre_completo") or r.get("cuil") or ""))
                   for _, r in padron.iterrows()} if not padron.empty else {}
        configs = []
        for d in docentes:
            if not isinstance(d, dict):
                raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
            k = IR.clave_cuil(_text(d.get("cuil")))
            if k not in nombres:
                raise InvestigacionError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            cuil, docente = nombres[k]
            configs.append({"cuil": cuil.strip(), "docente": docente.strip(), "rol": _text(d.get("rol")).strip(),
                            "horas": _numero(d.get("horas", 0), -1e9, 100.0),
                            "observaciones": _text(d.get("observaciones")).strip()})
        errores = []
        for cfg in configs:
            if not cfg["cuil"]:
                errores.append(f"{cfg['docente'] or 'Docente sin identificar'}: falta el CUIL.")
            if not cfg["rol"]:
                errores.append(f"{cfg['docente']}: completá el rol del docente en el proyecto.")
            if cfg["horas"] < 0:
                errores.append(f"{cfg['docente']}: las horas deben ser 0 o más.")
        if errores:
            raise InvestigacionError(422, "VALIDATION", "\n".join(errores[:10]))
        periodo_id = int(abierto["id"])
        nombre_proyecto = str(proyecto.get("nombre_proyecto", "") or "")
        esperado = (data.get("huella_proyecto"), data.get("huella_periodo"), data.get("huella_integrantes"))

        def fresh(L: Lecturas):
            integ = L.integrantes(proyecto_id, periodo_id) if L.periodo_abierto() else pd.DataFrame()
            return (huella_proyecto(L.proyecto_por_id(proyecto_id)), self._huella_periodo(L),
                    _hash([huella_asignacion(r) for r in records(integ)]))
        primera = {"stale": self._stale(scope, esperado, fresh, "get_integrantes_activos_proyecto_periodo")}

        def tomar_stale():
            # El registro de lecturas B12I se vacia despues de cada writer: solo la primera operacion revalida.
            s, primera["stale"] = primera["stale"], None
            return s

        creados, omitidos, errores_op = 0, 0, []
        for cfg in configs:
            existente = self._read(scope, lambda L: L.buscar_activa(periodo_id, proyecto_id, cfg["cuil"]))
            if existente:
                omitidos += 1
                continue
            try:
                proyecto_actual = self._read(scope, lambda L: L.proyecto_por_id(proyecto_id))
                if proyecto_actual:
                    self._op(record, scope, SPEC_GUARDAR_ASIGNACION, lambda u: E.guardar_investigacion_docente(
                        u, periodo_id, cfg["cuil"], proyecto_actual.get("nombre_proyecto", ""), cfg["rol"],
                        proyecto_actual.get("anio_llamado"), proyecto_actual.get("periodo_ejecucion", ""),
                        float(cfg["horas"]), cfg["observaciones"], proyecto_actual.get("codigo_proyecto", ""),
                        proyecto_actual.get("instituto_proyecto", ""), proyecto_id=proyecto_id),
                        entity_raw=proyecto_id, stale=tomar_stale())
                self._op(record, scope, SPEC_MOVIMIENTO, lambda u: E.registrar_movimiento(
                    u, "Asignación a investigación", cfg["cuil"], cfg["docente"],
                    f"Se asignaron {cfg['horas']:g} hs semanales al proyecto {nombre_proyecto} como {cfg['rol']}.",
                    cfg["observaciones"], periodo_id), entity_raw=cfg["cuil"], stale=tomar_stale())
                creados += 1
            except InvestigacionError as exc:
                if exc.code == "DENIED":
                    raise  # st.error + st.stop(): la denegacion B10 corta el bucle
                errores_op.append(f"{cfg['docente']}: {exc.message}")
        resumen = f"Asignación finalizada: {creados} nueva/s"
        if omitidos:
            resumen += f", {omitidos} duplicada/s omitida/s"
        if errores_op:
            resumen += f", {len(errores_op)} error/es. " + " | ".join(errores_op[:5])
        return {"mensaje": resumen + ".", "tono": "success", "pestana": "asignar"}

    def eliminar_asignacion_error(self, record: SessionRecord, data: dict) -> dict:
        """"Eliminar una asignación cargada por error" (l. 48786): borrado sin historial ni movimiento."""
        scope = self.reader(record)
        if not _bool(data.get("confirmar")):
            raise InvestigacionError(422, "VALIDATION", MSG_CONFIRMAR_ELIMINAR_ERROR)
        if data.get("asignacion_id") in (None, ""):
            raise InvestigacionError(422, "VALIDATION", MSG_SEL_ASIGNACION)
        aid = _id(data.get("asignacion_id"))
        proyecto_id = _id(data.get("proyecto_id"))
        detalle = self.asignar_detalle(record, {"proyecto_id": proyecto_id})
        fila = next((r for r in detalle["eliminables"] if r.get("id") == aid), None)
        if fila is None or fila["huella"] != data.get("huella"):
            raise InvestigacionError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        stale = self._stale_asignacion(scope, aid, fila["huella"])
        ok, mensaje = self._op(record, scope, SPEC_ELIMINAR_ASIGNACION,
                               lambda u: E.eliminar_investigacion_docente_definitivamente(u, aid), stale=stale)
        if not ok:
            raise InvestigacionError(422, "REJECTED", mensaje)
        return {"mensaje": mensaje, "tono": "success", "pestana": "asignar"}

    # ------------------------------------------------------------------ Pestaña 4: asignaciones por periodo
    def asignaciones(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        periodo_id = _id(data.get("periodo_id"))

        def read(L: Lecturas):
            dfp = L.periodos()
            if dfp.empty or periodo_id not in set(pd.to_numeric(dfp["id"], errors="coerce").astype(int)):
                raise InvestigacionError(404, "NOT_FOUND", MSG_PERIODO_NO_ENCONTRADO)
            df = L.asignaciones(periodo_id=periodo_id, incluir_bajas=L.es_historico(periodo_id))
            if df.empty:
                return {"filas": [], "caption": ""}
            cols = ["periodo", "docente", "cuil", "nombre_proyecto", "codigo_proyecto", "instituto_proyecto", "rol",
                    "fecha_inicio", "fecha_fin", "horas_asignadas", "observaciones", "fecha_carga"]
            total = float(pd.to_numeric(df["horas_asignadas"], errors="coerce").fillna(0).sum())
            caption = f"Asignaciones: {len(df)} | Docentes: {df['cuil'].nunique()} | Horas semanales: {total:g}"
            return {"filas": records(df, cols), "caption": caption}
        return self._read(scope, read)

    # ------------------------------------------------------------------ Pestaña 5: historial
    def historial(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(L: Lecturas):
            df = L.proyectos()
            if df.empty:
                return {"filas": [], "situaciones": ["Todos"]}
            try:
                _, mapa = L.actos_por_proyecto(pd.to_numeric(df["id"], errors="coerce").dropna().astype(int).tolist())
                df["actos_documentales_v263"] = df["id"].apply(lambda x: mapa.get(int(x), "Sin acto vinculado"))
            except Exception:
                df["actos_documentales_v263"] = "Sin acto vinculado"
            situaciones = ["Todos"] + sorted(df["situacion"].dropna().astype(str).unique().tolist())
            return {"filas": _con_huella(records(df), huella_proyecto), "situaciones": situaciones}
        return self._read(scope, read)

    def historial_asignaciones(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        proyecto_id = _id(data.get("proyecto_id"))

        def read(L: Lecturas):
            df = L.asignaciones(incluir_bajas=True, todos_departamentos=True)
            if not df.empty:
                df = df[pd.to_numeric(df["proyecto_id"], errors="coerce") == proyecto_id].copy()
            cols = ["departamento_asignacion", "periodo", "docente", "cuil", "rol", "horas_asignadas",
                    "estado_asignacion", "fecha_carga", "fecha_baja", "motivo_baja", "observaciones"]
            return {"filas": records(df, cols)}
        return self._read(scope, read)

    # ------------------------------------------------------------------ Pestaña 6: editar
    def editar_proyectos(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(L: Lecturas):
            df = L.proyectos()
            if not df.empty and "puede_administrar" in df.columns:
                df = df[df["puede_administrar"]].copy()
            return {"filas": _con_huella(records(df), huella_proyecto)}
        return self._read(scope, read)

    def _proyecto_administrable(self, scope: Scope, proyecto_id: int, huella: Any, filtro: Callable[[pd.DataFrame], pd.DataFrame]) -> dict:
        def read(L: Lecturas):
            df = filtro(L)
            fila = df[pd.to_numeric(df.get("id", pd.Series(dtype=float)), errors="coerce").eq(proyecto_id)] \
                if not df.empty else df
            return fila.iloc[0].to_dict() if not fila.empty else None
        fila = self._read(scope, read)
        if fila is None or huella_proyecto(fila) != huella:
            raise InvestigacionError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        return fila

    @staticmethod
    def _administrables(L: Lecturas) -> pd.DataFrame:
        df = L.proyectos()
        if not df.empty and "puede_administrar" in df.columns:
            df = df[df["puede_administrar"]].copy()
        return df

    def editar_proyecto(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        proyecto_id = _id(data.get("proyecto_id"))
        fila = self._proyecto_administrable(scope, proyecto_id, data.get("huella"), self._administrables)
        estados = ["Activo", "Finalizado", "Archivado"]
        if str(fila.get("estado") or "Activo") == "Suspendido":
            estados.insert(1, "Suspendido")
        estado = _text(data.get("estado"))
        if estado not in estados:
            raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
        nombre, codigo = _text(data.get("nombre")), _text(data.get("codigo"))
        instituto, obs = _text(data.get("instituto")), _text(data.get("observaciones"))
        anio = _anio(data.get("anio_llamado"))
        inicio, fin = _fecha(data.get("fecha_inicio")), _fecha(data.get("fecha_fin"))
        stale = self._stale_proyecto(scope, proyecto_id, data.get("huella"))
        ok, mensaje = self._op(record, scope, SPEC_ACTUALIZAR_PROYECTO, lambda u: E.actualizar_proyecto_investigacion(
            u, proyecto_id, nombre, codigo, instituto, int(anio), inicio, fin, obs, estado),
            entity_raw=proyecto_id, stale=stale)
        if not ok:
            raise InvestigacionError(422, "REJECTED", mensaje, tone="warning")
        return {"mensaje": MSG_EDIT_PROY_OK, "tono": "success"}

    def _asignaciones_abiertas(self, L: Lecturas) -> tuple[Optional[dict], pd.DataFrame]:
        abierto = L.periodo_abierto()
        if abierto is None:
            return None, pd.DataFrame()
        return abierto, L.asignaciones(periodo_id=int(abierto["id"]))

    def editar_asignaciones(self, record: SessionRecord) -> dict:
        """Asignaciones activas del periodo abierto (en un historico: foto al cierre, comportamiento heredado)."""
        scope = self.reader(record)

        def read(L: Lecturas):
            abierto, df = self._asignaciones_abiertas(L)
            return {"periodo": _period(abierto), "filas": _con_huella(records(df), huella_asignacion)}
        return self._read(scope, read)

    @staticmethod
    def _etiqueta_docente(r: dict) -> str:
        return f"{r['nombre_completo']} - {r['cuil']} ({r['horas_designadas']} hs designadas - {r.get('tipo_docente', 'Propio')})"

    def editar_asignacion_opciones(self, record: SessionRecord, data: dict) -> dict:
        """Selectores de "Asignación de un docente": proyectos vigentes y padron v276 (+ el docente actual)."""
        scope = self.reader(record)
        aid = _id(data.get("asignacion_id"))

        def read(L: Lecturas):
            abierto, df = self._asignaciones_abiertas(L)
            if abierto is None:
                raise InvestigacionError(409, "NO_PERIODO", MSG_SIN_PERIODO_EDITAR, tone="warning")
            fila = df[pd.to_numeric(df.get("id", pd.Series(dtype=float)), errors="coerce").eq(aid)] if not df.empty else df
            if fila.empty:
                raise InvestigacionError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            row = fila.iloc[0].to_dict()
            vig = L.proyectos(solo_activos=True, periodo_id=int(abierto["id"]))
            proyectos = []
            for _, r in vig.iterrows():
                cod = str(r.get("codigo_proyecto") or "").strip()
                proyectos.append({"id": int(r["id"]), "etiqueta": f"{cod + ' - ' if cod else ''}{r['nombre_proyecto']}"})
            opciones = self._opciones_docente(L.padron(), row)
            return {"proyectos": proyectos, "docentes": opciones}
        return self._read(scope, read)

    def _opciones_docente(self, padron: pd.DataFrame, row: dict) -> list[dict]:
        opciones: dict = {}
        for _, r in padron.iterrows():
            opciones[self._etiqueta_docente(r.to_dict())] = r["cuil"]
        actual = next((k for k, v in opciones.items() if str(v) == str(row.get("cuil", ""))), None)
        if actual is None:
            actual = f"{row.get('docente')} - {row.get('cuil')}"
            opciones[actual] = row.get("cuil", "")
        return [{"etiqueta": k, "cuil": v, "actual": k == actual} for k, v in opciones.items()]

    def editar_asignacion(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        aid = _id(data.get("asignacion_id"))
        proyecto_id = _id(data.get("proyecto_id"))
        etiqueta = _text(data.get("docente_etiqueta"))
        rol = _text(data.get("rol"))
        horas = _numero(data.get("horas"), 0.0, 100.0)
        obs = _text(data.get("observaciones"))

        def read(L: Lecturas):
            abierto, df = self._asignaciones_abiertas(L)
            if abierto is None:
                raise InvestigacionError(409, "NO_PERIODO", MSG_SIN_PERIODO_EDITAR, tone="warning")
            fila = df[pd.to_numeric(df.get("id", pd.Series(dtype=float)), errors="coerce").eq(aid)] if not df.empty else df
            if fila.empty:
                raise InvestigacionError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            row = fila.iloc[0].to_dict()
            vig = L.proyectos(solo_activos=True, periodo_id=int(abierto["id"]))
            ids = set(pd.to_numeric(vig.get("id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int))
            opciones = {o["etiqueta"]: o["cuil"] for o in self._opciones_docente(L.padron(), row)}
            cap = L.capacidad(opciones.get(etiqueta, ""), int(abierto["id"]), excluir_tipo="investigacion",
                              excluir_id=aid) if etiqueta in opciones else None
            return {"abierto": abierto, "row": row, "ids": ids, "opciones": opciones, "cap": cap,
                    "huella_periodo": self._huella_periodo(L)}
        ctx = self._read(scope, read)
        if proyecto_id not in ctx["ids"] or etiqueta not in ctx["opciones"]:
            raise InvestigacionError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        if huella_asignacion(ctx["row"]) != data.get("huella"):
            raise InvestigacionError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        if not rol.strip():
            raise InvestigacionError(422, "VALIDATION", MSG_ROL)
        cuil = ctx["opciones"][etiqueta]
        periodo_id = int(ctx["abierto"]["id"])
        proyecto = self._read(scope, lambda L: L.proyecto_por_id(proyecto_id))
        stale = self._stale_asignacion(scope, aid, data.get("huella"), data.get("huella_periodo"))
        ok, mensaje = self._op(record, scope, SPEC_ACTUALIZAR_ASIGNACION, lambda u: E.actualizar_investigacion_docente(
            u, aid, periodo_id, cuil, proyecto.get("nombre_proyecto", ""), rol.strip(), proyecto.get("anio_llamado"),
            proyecto.get("periodo_ejecucion", ""), float(horas), obs, proyecto.get("codigo_proyecto", ""),
            proyecto.get("instituto_proyecto", ""), proyecto_id=proyecto_id), entity_raw=proyecto_id, stale=stale)
        if not ok:
            raise InvestigacionError(422, "REJECTED", mensaje)
        self._op(record, scope, SPEC_MOVIMIENTO, lambda u: E.registrar_movimiento(
            u, "Modificación de investigación", cuil, etiqueta,
            f"Se modificó la asignación al proyecto {proyecto.get('nombre_proyecto', '')} como {rol.strip()} "
            f"({float(horas):g} hs semanales).", obs, periodo_id), entity_raw=cuil)
        cap = ctx["cap"] or {}
        alerta = {"tipo_modulo": "investigacion", "periodo_id": periodo_id, "cuil": str(cuil or "").strip(),
                  "docente": str(etiqueta or cuil or "").strip(), "accion": "Modificación de Investigación",
                  "horas_accion": round(float(horas or 0), 2),
                  "horas_disponibles_antes": round(float(cap.get("horas_disponibles_proyectos", 0) or 0), 2)}
        return {"mensaje": mensaje, "tono": "success", "alerta_post_accion": alerta}

    # ------------------------------------------------------------------ Pestaña 7: bajas, suspension, archivo, eliminacion
    def baja_asignacion(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        if not _bool(data.get("confirmar")):
            raise InvestigacionError(422, "VALIDATION", MSG_CONFIRMAR_BAJA)
        if data.get("asignacion_id") in (None, ""):
            raise InvestigacionError(422, "VALIDATION", MSG_SEL_ASIGNACION)
        aid = _id(data.get("asignacion_id"))
        fecha = _fecha(data.get("fecha_baja"))
        motivo = _text(data.get("motivo"))

        def read(L: Lecturas):
            abierto, df = self._asignaciones_abiertas(L)
            if abierto is None:
                raise InvestigacionError(409, "NO_PERIODO", MSG_SIN_PERIODO_BAJA, tone="warning")
            fila = df[pd.to_numeric(df.get("id", pd.Series(dtype=float)), errors="coerce").eq(aid)] if not df.empty else df
            return None if fila.empty else huella_asignacion(fila.iloc[0].to_dict())
        huella = self._read(scope, read)
        if huella is None or huella != data.get("huella"):
            raise InvestigacionError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        stale = self._stale_asignacion(scope, aid, huella)
        self._op(record, scope, SPEC_BAJA_ASIGNACION, lambda u: E.eliminar_investigacion_docente(u, aid, motivo, fecha),
                 stale=stale)
        return {"mensaje": MSG_BAJA_OK, "tono": "success"}

    def suspender_proyectos(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(L: Lecturas):
            abierto = L.periodo_abierto()
            if abierto is None:
                return {"periodo": None, "filas": []}
            df = L.proyectos(solo_activos=True, periodo_id=int(abierto["id"]))
            if not df.empty and "puede_administrar" in df.columns:
                df = df[df["puede_administrar"]].copy()
            return {"periodo": _period(abierto), "filas": _con_huella(records(df), huella_proyecto)}
        return self._read(scope, read)

    def suspender(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        fecha = _fecha(data.get("fecha_suspension"))
        motivo = _text(data.get("motivo"))
        if not _bool(data.get("confirmar")):
            raise InvestigacionError(422, "VALIDATION", MSG_CONFIRMAR_SUSP)
        if not motivo.strip():
            raise InvestigacionError(422, "VALIDATION", MSG_MOTIVO_SUSP)
        if data.get("proyecto_id") in (None, ""):
            raise InvestigacionError(422, "VALIDATION", MSG_SEL_PROYECTO)
        proyecto_id = _id(data.get("proyecto_id"))
        abierto = self._read(scope, lambda L: L.periodo_abierto())
        if abierto is None:
            raise InvestigacionError(409, "NO_PERIODO", MSG_SIN_PERIODO_SUSP, tone="warning")

        def filtro(L: Lecturas):
            df = L.proyectos(solo_activos=True, periodo_id=int(abierto["id"]))
            if not df.empty and "puede_administrar" in df.columns:
                df = df[df["puede_administrar"]].copy()
            return df
        self._proyecto_administrable(scope, proyecto_id, data.get("huella"), filtro)
        stale = self._stale_proyecto(scope, proyecto_id, data.get("huella"), data.get("huella_periodo"))
        ok, mensaje, _ = self._op(record, scope, SPEC_SUSPENDER_PROYECTO, lambda u: E.suspender_proyecto_investigacion(
            u, proyecto_id, int(abierto["id"]), motivo, fecha), entity_raw=proyecto_id, stale=stale)
        if not ok:
            raise InvestigacionError(422, "REJECTED", mensaje)
        return {"mensaje": mensaje, "tono": "success"}

    def archivar_proyectos(self, record: SessionRecord) -> dict:
        scope = self.reader(record)
        return self._read(scope, lambda L: {"filas": _con_huella(records(self._archivables(L)), huella_proyecto)})

    @staticmethod
    def _archivables(L: Lecturas) -> pd.DataFrame:
        df = L.proyectos()
        if not df.empty:
            df = df[(df["estado"] != "Archivado") & (df.get("puede_administrar", True))].copy()
        return df

    def archivar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        motivo = _text(data.get("motivo"))
        if not _bool(data.get("confirmar")):
            raise InvestigacionError(422, "VALIDATION", MSG_CONFIRMAR_ARCHIVO)
        if data.get("proyecto_id") in (None, ""):
            raise InvestigacionError(422, "VALIDATION", MSG_SEL_PROYECTO)
        proyecto_id = _id(data.get("proyecto_id"))
        self._proyecto_administrable(scope, proyecto_id, data.get("huella"), self._archivables)
        stale = self._stale_proyecto(scope, proyecto_id, data.get("huella"))
        ok, mensaje = self._op(record, scope, SPEC_ARCHIVAR_PROYECTO, lambda u: E.archivar_proyecto_investigacion(
            u, proyecto_id, motivo), entity_raw=proyecto_id, stale=stale)
        if not ok:
            raise InvestigacionError(422, "REJECTED", mensaje)
        return {"mensaje": mensaje, "tono": "success"}

    def eliminar_proyecto(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        proyecto_id = _id(data.get("proyecto_id"))
        fila = self._proyecto_administrable(scope, proyecto_id, data.get("huella"), self._administrables)
        if not _bool(data.get("confirmar")):
            raise InvestigacionError(422, "VALIDATION", MSG_CONFIRMAR_ELIMINAR)
        codigo = str(fila.get("codigo_proyecto") or "").strip()
        texto = codigo or str(fila.get("nombre_proyecto") or "").strip()
        if _text(data.get("confirmacion")).strip() != texto:
            raise InvestigacionError(422, "VALIDATION", MSG_TEXTO_ELIMINAR)
        stale = self._stale_proyecto(scope, proyecto_id, data.get("huella"))
        ok, mensaje = self._op(record, scope, SPEC_ELIMINAR_PROYECTO, lambda u: E.eliminar_proyecto_investigacion(
            u, proyecto_id), entity_raw=proyecto_id, stale=stale)
        if not ok:
            raise InvestigacionError(422, "REJECTED", mensaje)
        return {"mensaje": mensaje, "tono": "success"}

    # ------------------------------------------------------------------ Pestaña 8: carga rapida (v217)
    def modelo_excel(self, record: SessionRecord) -> bytes:
        scope = self.reader(record)

        def read(L: Lecturas):
            abierto = L.periodo_abierto()
            proyectos = L.proyectos()
            if abierto is None:
                return X.integral_v217(proyectos, pd.DataFrame(), pd.DataFrame())
            pid = int(abierto["id"])
            return X.integral_v217(proyectos, L.padron(), L.asignaciones(periodo_id=pid, incluir_bajas=False))
        return self._read(scope, read)

    @staticmethod
    def _contenido(data: dict) -> bytes:
        raw = data.get("archivo")
        if not isinstance(raw, str) or not raw:
            raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
        if len(raw) > (MAX_EXCEL_BYTES * 4) // 3 + 8:
            raise InvestigacionError(413, "TOO_LARGE", MSG_EXCEL_GRANDE)
        try:
            contenido = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO) from None
        if len(contenido) > MAX_EXCEL_BYTES:
            raise InvestigacionError(413, "TOO_LARGE", MSG_EXCEL_GRANDE)
        if (motivo := uploads.problema_xlsx(contenido)) is not None:  # 6A-B1: contenido real, antes del lector
            log.info("investigacion: Excel rechazado (%s)", motivo)
            raise InvestigacionError(422, "EXCEL", MSG_EXCEL_INVALIDO)
        return contenido

    @staticmethod
    def _leer(contenido: bytes) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        try:
            df_carga = X.leer_carga_rapida_v127(contenido)
            df_nuevas = X.filas_nuevas(df_carga) if not df_carga.empty else df_carga
            df_asig = X.leer_asignaciones_v217(contenido)
            df_asig_nuevas = df_asig[df_asig["id"].apply(IR.parse_id_excel_v127).isna()].copy() \
                if not df_asig.empty else df_asig
        except ValueError as exc:
            raise InvestigacionError(422, "EXCEL", str(exc)) from None
        except Exception as exc:
            log.info("investigacion: Excel ilegible: %s", type(exc).__name__)
            raise InvestigacionError(422, "EXCEL", MSG_EXCEL_INVALIDO) from None
        return df_carga, df_nuevas, df_asig, df_asig_nuevas

    def carga_preview(self, record: SessionRecord, data: dict) -> dict:
        self.reader(record)
        _, df_nuevas, _, df_asig_nuevas = self._leer(self._contenido(data))
        if df_nuevas.empty and df_asig_nuevas.empty:
            raise InvestigacionError(422, "VACIO", MSG_CARGA_VACIA, tone="info")
        return {"proyectos": records(df_nuevas.astype(object).where(df_nuevas.notna(), None)),
                "asignaciones": records(df_asig_nuevas.astype(object).where(df_asig_nuevas.notna(), None))}

    def carga_ejecutar(self, record: SessionRecord, data: dict) -> dict:
        """"🚀 Procesar carga rápida": Op 1 proyectos y Op 2 asignaciones, independientes (si falla la 2, la 1 queda)."""
        scope = self.reader(record)
        contenido = self._contenido(data)
        if not _bool(data.get("confirmar")):
            raise InvestigacionError(422, "INVALID", MSG_VALOR_INVALIDO)
        df_carga, df_nuevas, df_asig, df_asig_nuevas = self._leer(contenido)
        if df_nuevas.empty and df_asig_nuevas.empty:
            raise InvestigacionError(422, "VACIO", MSG_CARGA_VACIA, tone="info")
        abierto = self._read(scope, lambda L: L.periodo_abierto())
        primera = {"stale": self._stale(scope, data.get("huella_periodo"), self._huella_periodo, "get_periodo_abierto")}

        def tomar_stale():
            s, primera["stale"] = primera["stale"], None
            return s
        res_proy = {"creados": 0, "existentes": 0, "omitidos_existentes": 0, "detalle": pd.DataFrame()}
        if not df_nuevas.empty:
            res_proy = self._op(record, scope, SPEC_CARGA_PROYECTOS,
                                lambda u: E.cargar_proyectos_excel_v127(u, df_carga), stale=tomar_stale())
        res_asig = {"creadas": 0, "omitidas": 0, "detalle": pd.DataFrame()}
        if not df_asig_nuevas.empty:
            if abierto is None:
                raise InvestigacionError(422, "NO_PERIODO", MSG_CARGA_SIN_PERIODO)
            periodo_id = int(abierto["id"])
            res_asig = self._op(record, scope, SPEC_CARGA_ASIGNACIONES,
                                lambda u: E.cargar_asignaciones_proyectos_excel_v217(u, df_asig, periodo_id),
                                entity_raw=periodo_id, stale=tomar_stale())
        mensaje = (f"Carga completada. Proyectos creados: {res_proy.get('creados',0)}; "
                   f"proyectos ya existentes: {res_proy.get('existentes',0)}; "
                   f"asignaciones docentes creadas: {res_asig.get('creadas',0)}; "
                   f"asignaciones omitidas: {res_asig.get('omitidas',0)}.")
        return {"mensaje": mensaje, "tono": "success", "detalle_proyectos": records(res_proy.get("detalle")),
                "detalle_asignaciones": records(res_asig.get("detalle"))}


def _nunique(df: Optional[pd.DataFrame], col: str) -> int:
    if df is None or df.empty or col not in df.columns:
        return 0
    s = df[col].fillna("").astype(str).str.strip()
    return int(s[s != ""].nunique())


def _sum_horas(df: Optional[pd.DataFrame]) -> float:
    if df is None or df.empty or "horas_asignadas" not in df.columns:
        return 0.0
    return float(pd.to_numeric(df["horas_asignadas"], errors="coerce").fillna(0).sum())


def _nunique_deps(df: Optional[pd.DataFrame]) -> int:
    """``_nunique_departamentos_origen_v277`` (l. 33347)."""
    if df is None or df.empty:
        return 0
    col = "departamento_origen_docente" if "departamento_origen_docente" in df.columns else "departamento_asignacion"
    if col not in df.columns:
        return 0
    deps = set()
    for valor in df[col].fillna("").astype(str).tolist():
        for dep in [x.strip() for x in str(valor).split(" / ") if x.strip()]:
            deps.add(dep)
    return len(deps)
