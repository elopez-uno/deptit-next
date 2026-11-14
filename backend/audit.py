"""Auditoria backend-autoritativa del actor (B12H) sobre ``b12h_audit_log`` (esquema public).

Origen certificado (reference_fix02): ``deptit_refactor/b12h/audit_actor.py`` (evento, validacion, metadata) y
``deploy/postgresql/b12h_audit_log.sql`` (tabla append-only; esta app nunca crea ni altera la tabla).

- SUCCESS: en la MISMA transaccion que el negocio (``IN_TRANSACTION``); si el INSERT falla, el negocio no confirma.
  Una operacion sin cambios confirmados registra SUCCESS ``POST_OPERATION`` en transaccion propia.
- DENIED / FAILED: transaccion propia (``SEPARATE_TRANSACTION``), best-effort observable.
- El actor sale SIEMPRE de la sesion recien revalidada contra la base (``AuthService.validate``).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from psycopg import Connection
from psycopg_pool import ConnectionPool

from auth import core, policy

log = logging.getLogger("deptit_next.audit")

AUDIT_TABLE = "b12h_audit_log"
EVENT_VERSION = 1
SUBSYSTEM = "B12H"
APP_BATCH = "B12H"

OUTCOME_SUCCESS, OUTCOME_DENIED, OUTCOME_FAILED = "SUCCESS", "DENIED", "FAILED"
MODE_IN_TRANSACTION = "IN_TRANSACTION"
MODE_POST_OPERATION = "POST_OPERATION"
MODE_SEPARATE = "SEPARATE_TRANSACTION"
ACTOR_USER = "USER"
SOURCE_B12G = "B12G_REVALIDATED_DB"
SCOPE_SRC_HOME = "ACTOR_HOME"
SCOPE_SRC_SUPERADMIN = "SUPERADMIN_SELECTED"

MSG_PERSIST = "No se pudo registrar la auditoría obligatoria de la operación: no se confirmó ningún cambio."

# Writers de negocio que esta app ejecuta (nombres del registro B10 certificado, legacy_write_actions.py).
WRITER_NAMES = frozenset({
    "_abrir_periodo_emergencia_control_v300", "abrir_periodo_emergencia",
    "_volver_periodo_actual_control_v300", "volver_periodo_actual",
    # E4-10..E4-12: Crear periodo (B12C), Revertir ultimo cierre, Eliminar periodo vacio, Reparar finalizaciones
    # automaticas (P-12b) (legacy_write_actions)
    "crear_periodo", "revertir_ultimo_cierre_periodo", "eliminar_periodo", "reactivar_finalizaciones_automaticas_periodo",
    "registrar_movimiento",
    # Docentes
    "guardar_docente", "actualizar_docente", "eliminar_docente", "registrar_prestamo_docente_v174",
    "finalizar_prestamo_docente_v174", "migrar_referencias_cuil_v168",
    # Materias
    "guardar_carrera", "actualizar_carrera", "eliminar_carrera", "guardar_materia", "actualizar_materia",
    "actualizar_codigo_nombre_materias_desde_plan", "guardar_configuracion_comparticion_materia_v137",
    "quitar_materia_del_plan", "eliminar_materia", "limpiar_registros_materias_fuera_del_plan",
    "guardar_opcion_curricular_v120", "actualizar_opcion_curricular_v120", "eliminar_opcion_curricular_v120",
    "agregar_vinculos_opcion_curricular_v120", "quitar_vinculo_opcion_curricular_v120",
    "cargar_opciones_curriculares_excel_v124",
    # Designaciones
    "guardar_designacion", "actualizar_designacion", "actualizar_designacion_por_error", "eliminar_designacion",
    "guardar_estado_consulta_designacion",
    "eliminar_designaciones_por_error_masivo", "finalizar_designacion_anticipadamente",
    "actualizar_resolucion_fechas_designacion_directo_v171", "_limpiar_metadatos_finalizacion_si_reactivada_v233",
    "sincronizar_movimiento_baja_designacion_v207", "vincular_acto_designacion_v266", "vincular_acto_movimiento_v266",
    "vincular_acto_designaciones_masivo_v267", "desvincular_acto_designaciones_masivo_v267",
    "vincular_acto_movimientos_masivo_v267", "desvincular_acto_movimientos_masivo_v267",
    # Comisiones (+ efectos anidados certificados: prestado local en Docentes y reajuste de proyectos v184)
    "guardar_comision", "actualizar_comision", "actualizar_nombre_comision_correccion_v180",
    "actualizar_nombres_comisiones_lote_v195", "cargar_comisiones_rapidas_lote_v232", "guardar_horario_comision",
    "actualizar_horario_comision", "_reparar_horarios_personalizados_por_horario_comision_v95",
    "guardar_asignacion_docente_comision", "guardar_horarios_reales_asignacion",
    "actualizar_estado_asignacion_docente_comision", "sincronizar_horas_asignaciones_comision",
    "guardar_inscriptos_asignatura_periodo_v248", "guardar_sede_institucional", "actualizar_sede_institucional",
    "eliminar_comision", "eliminar_horario_comision", "eliminar_asignacion_docente_comision",
    "eliminar_sede_institucional", "_b10_revertir_alta_comision_incompleta",
    "asegurar_docente_prestado_local_si_corresponde", "_actualizar_horas_proyecto_directo_v184",
    # Investigacion (sin los pilotos 8H/8J)
    "guardar_proyecto_investigacion", "actualizar_proyecto_investigacion", "suspender_proyecto_investigacion",
    "archivar_proyecto_investigacion", "eliminar_proyecto_investigacion", "guardar_investigacion_docente",
    "actualizar_investigacion_docente", "eliminar_investigacion_docente",
    "eliminar_investigacion_docente_definitivamente", "cargar_proyectos_excel_v127",
    "cargar_asignaciones_proyectos_excel_v217", "_vincular_proyectos_documento_v261",
    "desvincular_acto_proyectos_masivo_v267",
    # Extension (sin los pilotos 8I/8K; las cargas rapidas y los actos son los mismos writers de Investigacion)
    "guardar_proyecto_extension", "actualizar_proyecto_extension", "suspender_proyecto_extension",
    "archivar_proyecto_extension", "eliminar_proyecto_extension", "guardar_extension_docente",
    "actualizar_extension_docente", "eliminar_extension_docente", "eliminar_extension_docente_definitivamente",
    # Actividades Especiales
    "guardar_actividad_especial", "actualizar_actividad_especial", "asignar_docente_actividad_especial",
    "eliminar_actividad_especial", "eliminar_asignacion_actividad_especial",
    # Sueldos (unico writer del dominio)
    "guardar_escala_salarial_v256",
    # Disposiciones (+ comandos B12E; ``registrar_movimiento`` ya figura arriba)
    "guardar_parametros_disposicion", "guardar_parametros_docente_disposicion",
    "guardar_datos_designaciones_docente_disposicion", "guardar_disposicion", "eliminar_disposicion",
    "generar_disposicion_word_b12e", "reemplazar_plantilla_disposicion_b12e",
    # Resoluciones y respaldos (D-AK11; los vinculos de designacion/movimiento/proyecto ya figuran arriba)
    "guardar_documento_respaldo_v251", "guardar_documento_respaldo_v249", "adjuntar_pdf_documento_respaldo_v272",
    "actualizar_dependencia_documento_v262", "guardar_dependencia_documental_v262",
    "actualizar_dependencia_documental_v262", "eliminar_documento_respaldo_v251", "eliminar_documento_respaldo_v249",
    # 6A-B3: edicion posterior de los docentes de un acto (writer del catalogo certificado, l. 58257)
    "_asegurar_docente_en_documento_v266",
    # E4-07: compensacion del acto creado en linea desde Designaciones (B10 COMPENSATIONS, legacy_write_actions l. 261)
    "_eliminar_acto_recien_creado_v267",
    # Movimientos (D-AL6; ``registrar_movimiento`` y los vinculos masivos v267 ya figuran arriba)
    "eliminar_movimiento",
    # Analisis / Productividad (unico writer del bloque)
    "guardar_porcentaje_horas_no_lectivas_v148",
    # Administracion SaaS (legacy_write_actions.py l. 231-243)
    "crear_institucion_auth", "actualizar_cupo_institucion", "actualizar_comercial_institucion",
    "cambiar_estado_institucion_auth", "crear_departamento_auth", "actualizar_departamento_auth",
    "crear_usuario_auth", "actualizar_usuario_auth", "cambiar_estado_usuario_auth", "eliminar_institucion_auth",
    "eliminar_departamento_auth", "eliminar_usuario_auth",
})

# Tareas de sistema (registro B10 ``SYSTEM_WRITERS``, categoria reconciliacion) que esta app ejecuta anidadas dentro de
# una operacion de negocio autorizada (B12F); su COMMIT lleva ``nested_system_task``.
SYSTEM_TASK_NAMES = frozenset({
    "sincronizar_cargos_asignaciones_docente_periodo", "_finalizar_comisiones_si_sin_designacion_docente_v214",
})

EVENT_COLUMNS = ("audit_id", "correlation_id", "event_seq", "event_version", "subsystem", "app_batch", "actor_kind",
                 "actor_source", "actor_user_id", "actor_email_normalized", "actor_role", "actor_is_superadmin",
                 "actor_home_institucion_id", "actor_home_departamento_id", "institucion_id", "departamento_id",
                 "scope_source", "session_ref", "operation", "action", "action_scope", "entity_type", "entity_id",
                 "outcome", "audit_mode", "error_code", "metadata")
INSERT_SQL = (f"INSERT INTO {AUDIT_TABLE} (" + ", ".join(EVENT_COLUMNS) + ") VALUES ("
              + ", ".join(["%s"] * len(EVENT_COLUMNS)) + ")")

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]{0,63}$")
_ENTITY_VALUE_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._:/-]{0,63}$")
_CLASS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_CODE_RE = re.compile(r"^[A-Z0-9_]{1,40}$")
_ERROR_CODE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}(:[A-Z0-9_]{1,40})?$")

# Un nonce por proceso: igual que el nonce B12G, separa las sesiones de procesos distintos.
_PROCESS_NONCE = secrets.token_hex(16)


def _int_0(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 1_000_000


METADATA_POLICY: dict[str, Callable[[Any], bool]] = {
    "commit_seq": _int_0,
    "mutating_statements": _int_0,
    "coupled_commits": _int_0,
    "committing_writer": lambda v: v in WRITER_NAMES,
    "nested_system_task": lambda v: v in SYSTEM_TASK_NAMES,
    "post_reason": lambda v: v in ("NO_POOLED_COMMIT", "FILESYSTEM_ONLY"),  # FILESYSTEM_ONLY: plantilla B12E
    "b10_decision": lambda v: isinstance(v, str) and (v == policy.ALLOW or v.startswith("DENY_")),
    "entity_param": lambda v: isinstance(v, str) and bool(_IDENT_RE.match(v)),
}


class AuditError(RuntimeError):
    """El evento violaria la politica o no pudo persistirse."""


def check_metadata(meta: Mapping[str, Any]) -> dict:
    """Allowlist estricta B12H: clave conocida + valor valido; los ``None`` se omiten."""
    out = {}
    for key, value in meta.items():
        check = METADATA_POLICY.get(key)
        if check is None:
            raise AuditError(f"clave de metadata no permitida: {str(key)[:40]!r}")
        if value is None:
            continue
        if not check(value):
            raise AuditError(f"valor de metadata no permitido para {key!r}")
        out[key] = value
    return out


def error_code_of(exc: BaseException) -> str:
    """Codigo sanitizado: clase (+ ``:CODIGO`` funcional estable si existe).  Nunca ``str(exc)``."""
    name = type(exc).__name__
    if not _CLASS_RE.match(name):
        name = "Exception"
    code = getattr(exc, "code", None)
    if isinstance(code, str) and _CODE_RE.match(code):
        return f"{name}:{code}"
    return name


def entity_value(value: Any) -> Optional[str]:
    if isinstance(value, bool) or value is None:
        return None
    iv = core.to_int_or_none(value)
    if iv is not None and not isinstance(value, str):
        return str(iv) if iv > 0 else None
    if isinstance(value, str):
        text = value.strip()
        return text if _ENTITY_VALUE_RE.fullmatch(text) else None
    return None


@dataclass(frozen=True)
class AuditActor:
    user_id: int
    email: Optional[str]
    role: Optional[str]
    home_institution_id: Optional[int]
    home_department_id: Optional[int]
    institution_id: Optional[int]
    department_id: Optional[int]
    scope_source: str
    session_ref: Optional[str]

    @property
    def is_superadmin(self) -> bool:
        return self.role == policy.ROLE_SUPERADMIN


def session_ref_of(meta: Mapping[str, Any]) -> Optional[str]:
    """Referencia NO reversible de la sesion (correlacion entre operaciones de una misma sesion).  Nunca deriva del
    token: usa el nonce de proceso, el usuario y el instante de emision (mismo criterio que B12H)."""
    try:
        payload = json.dumps(["deptit-next-b12h-session-v1", _PROCESS_NONCE, int(meta.get("user_id")),
                              float(meta.get("issued_mono"))])
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def actor_from_record(user: Mapping[str, Any], scope: Mapping[str, Any], meta: Mapping[str, Any]) -> AuditActor:
    """``actor_from_validation`` B12H: copia del actor B10 construido desde el usuario fresco de la sesion."""
    uid = meta.get("user_id")
    if not isinstance(uid, int) or isinstance(uid, bool) or uid <= 0:
        raise AuditError("sesion sin usuario revalidado")
    actor = policy.actor_from_session(user, scope)
    ref = str(actor.user_ref or "")
    email = None if ref.startswith("id:") else (core.normalize_email(ref) or None)
    if email is not None and len(email) > 320:
        email = None
    scope_src = SCOPE_SRC_HOME
    if actor.role == policy.ROLE_SUPERADMIN and \
            core.to_int_or_none(scope.get(policy.SUPERADMIN_INSTITUTION_KEY)) is not None:
        scope_src = SCOPE_SRC_SUPERADMIN
    return AuditActor(user_id=uid, email=email, role=actor.role, home_institution_id=actor.home_institution_id,
                      home_department_id=actor.home_department_id, institution_id=actor.institution_id,
                      department_id=actor.department_id, scope_source=scope_src, session_ref=session_ref_of(meta))


@dataclass(frozen=True)
class AuditEvent:
    audit_id: str
    correlation_id: str
    event_seq: int
    actor: AuditActor
    operation: str
    action: str
    action_scope: str
    entity_type: str
    entity_id: Optional[str]
    outcome: str
    audit_mode: str
    error_code: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def validate(self) -> "AuditEvent":
        """Mismas invariantes que los CHECK de la tabla (defensa en profundidad)."""
        problems = []
        if not _UUID_RE.match(self.audit_id) or not _UUID_RE.match(self.correlation_id):
            problems.append("uuid")
        if not isinstance(self.event_seq, int) or self.event_seq < 1:
            problems.append("event_seq")
        if self.outcome == OUTCOME_SUCCESS and self.audit_mode not in (MODE_IN_TRANSACTION, MODE_POST_OPERATION):
            problems.append("SUCCESS fuera de IN_TRANSACTION/POST_OPERATION")
        if self.outcome in (OUTCOME_DENIED, OUTCOME_FAILED) and self.audit_mode != MODE_SEPARATE:
            problems.append("DENIED/FAILED fuera de SEPARATE_TRANSACTION")
        if self.outcome not in (OUTCOME_SUCCESS, OUTCOME_DENIED, OUTCOME_FAILED):
            problems.append("outcome")
        if not isinstance(self.actor.user_id, int) or self.actor.user_id <= 0:
            problems.append("actor USER sin user_id revalidado")
        if self.operation not in WRITER_NAMES:
            problems.append("operación no registrada")
        if self.action_scope not in (policy.SCOPE_DEPARTMENT, policy.SCOPE_INSTITUTION, policy.SCOPE_GLOBAL):
            problems.append("action_scope")
        if self.error_code is not None and not _ERROR_CODE_RE.match(self.error_code):
            problems.append("error_code")
        if self.outcome == OUTCOME_SUCCESS and self.error_code is not None:
            problems.append("SUCCESS con error_code")
        if self.entity_id is not None and not _ENTITY_VALUE_RE.fullmatch(self.entity_id):
            problems.append("entity_id")
        if check_metadata(self.metadata) != self.metadata:
            problems.append("metadata con valores nulos")
        if problems:
            raise AuditError("evento inválido: " + ", ".join(problems))
        return self

    def params(self) -> list:
        a = self.actor
        return [self.audit_id, self.correlation_id, self.event_seq, EVENT_VERSION, SUBSYSTEM, APP_BATCH, ACTOR_USER,
                SOURCE_B12G, a.user_id, a.email, a.role, a.is_superadmin, a.home_institution_id,
                a.home_department_id, a.institution_id, a.department_id, a.scope_source, a.session_ref, self.operation,
                self.action, self.action_scope, self.entity_type, self.entity_id, self.outcome, self.audit_mode,
                self.error_code, json.dumps(self.metadata, ensure_ascii=True, sort_keys=True, separators=(",", ":"))]


class Operation:
    """Una operacion auditada (``correlation_id`` comun a todos sus eventos, ``event_seq`` creciente).

    Como en B12H, cada COMMIT con sentencias mutantes dentro de la operacion lleva su propio SUCCESS
    (``commit_seq`` = numero de ese COMMIT); ``coupled_commits`` cuenta los ya confirmados."""

    def __init__(self, name: str, action: policy.Action, entity_type: str, actor: AuditActor,
                 entity_param: Optional[str] = None, entity_raw: Any = None):
        self.name = name
        self.action = action
        self.entity_type = entity_type
        self.actor = actor
        self.entity_id = entity_value(entity_raw) if entity_param else None
        self.entity_param = entity_param if self.entity_id is not None else None
        self.correlation_id = str(uuid.uuid4())
        self.coupled_commits = 0
        self._seq = 0

    def event(self, outcome: str, mode: str, *, error_code: Optional[str] = None,
              metadata: Optional[Mapping[str, Any]] = None) -> AuditEvent:
        self._seq += 1
        meta = dict(metadata or {})
        if self.entity_param:
            meta.setdefault("entity_param", self.entity_param)
        return AuditEvent(audit_id=str(uuid.uuid4()), correlation_id=self.correlation_id, event_seq=self._seq,
                          actor=self.actor, operation=self.name, action=self.action.key,
                          action_scope=self.action.scope, entity_type=self.entity_type, entity_id=self.entity_id,
                          outcome=outcome, audit_mode=mode, error_code=error_code,
                          metadata=check_metadata(meta)).validate()


def insert_on(conn: Connection, event: AuditEvent) -> None:
    """INSERT en la transaccion de ``conn`` (sin COMMIT): confirma junto con el negocio."""
    conn.execute(INSERT_SQL, event.validate().params())


class AuditStore:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def append_separate(self, event: AuditEvent) -> None:
        """Transaccion propia: INSERT + COMMIT (ante un fallo el pool hace ROLLBACK y el error se propaga)."""
        with self._pool.connection(timeout=5) as conn:
            insert_on(conn, event)
